# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

import time
from celery.utils.log import get_task_logger
from beecell.simple import id_gen, truncate
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, task_local
from beehive_resource.model import ResourceState
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer

logger = get_task_logger(__name__)


class ServerHelper(object):
    def __init__(self, task, container):
        self.task = task
        self.container = container
        self.conn = self.container.conn

    def create_volume(
        self,
        name,
        desc,
        parent_id,
        project_extid,
        availability_zone,
        config,
        server,
        boot=False,
    ):
        source_type = config.get("source_type")

        # create boot volume
        if source_type in ["image", "snapshot", None]:
            # create volume resource
            parent = self.task.get_resource_by_extid(project_extid)
            objid = "%s//%s" % (parent.objid, id_gen())
            volume_size = config.get("volume_size")
            volume_type_id = config.get("volume_type", None)
            volume_type = None
            if volume_type_id is not None:
                volume_type = self.task.get_resource(volume_type_id).ext_id
            volume = self.container.add_resource(
                objid=objid,
                name=name,
                resource_class=OpenstackVolume,
                ext_id=None,
                active=False,
                desc=desc,
                attrib={"size": volume_size},
                parent=parent_id,
                tags=["openstack", "volume"],
            )
            self.task.progress("Create volume resource %s" % volume.id)

            # link volume id to server
            server.add_link(
                "%s-%s-volume-link" % (server.oid, volume.id),
                "volume",
                volume.id,
                attributes={"boot": boot},
            )
            self.task.progress("Setup volume link from %s to server %s" % (volume.id, server.oid))

            image = None
            snapshot = None
            if source_type == "image":
                image = config.get("uuid")
            elif source_type == "snapshot":
                snapshot = config.get("uuid")
            volume_ext = self.conn.volume.create(
                size=int(volume_size),
                availability_zone=availability_zone,
                source_volid=None,
                description=desc,
                multiattach=False,
                snapshot_id=snapshot,
                name=name,
                imageRef=image,
                volume_type=volume_type,
                metadata=None,
                source_replica=None,
                consistencygroup_id=None,
                scheduler_hints=None,
                tenant_id=project_extid,
            )
            volume_id = volume_ext["id"]
            self.task.progress("Create openstack volume %s - Starting" % volume_id)

            # attach remote volume
            self.container.update_resource(volume.id, ext_id=volume_id)
            self.task.progress("Attach openstack volume %s to volume %s" % (volume_id, volume.id))

            # loop until entity is not stopped or get error
            while True:
                inst = OpenstackVolume.get_remote_volume(
                    self.container.controller, volume_id, self.container, volume_id
                )
                # inst = self.conn.volume.get(oid=volume_id)
                status = inst.get("status", "error")
                if status == "available":
                    break
                elif status == "error":
                    self.task.progress("Create openstack volume %s - Error" % volume_id)
                    raise Exception("Can not create openstack volume %s" % volume_id)

                self.task.progress("")
                time.sleep(2)

            # acvitate volume
            self.container.update_resource(volume.id, state=ResourceState.ACTIVE, active=True)
            self.task.progress("Activate volume %s" % volume.id)

            self.task.progress("Create volume %s - Completed" % volume_id)

        # get existing volume
        elif source_type in ["volume"]:
            # get existing volume
            volume_uuid = config.get("uuid")
            volume = self.container.get_resource(volume_uuid)
            volume_id = volume.ext_id

            # link volume id to server
            server.add_link(
                "%s-%s-volume-link" % (server.oid, volume.oid),
                "volume",
                volume.oid,
                attributes={"boot": boot},
            )
            self.task.progress("Setup volume link from %s to server %s" % (volume.oid, server.oid))

        return volume_id

    def delete_physical_server(self, server_ext_id):
        resource = self.container.get_resource_by_extid(server_ext_id)

        # check server exists
        rs = OpenstackServer.get_remote_server(resource.controller, server_ext_id, self.container, server_ext_id)
        if rs == {}:
            self.task.progress("Server %s does not exist anymore" % server_ext_id)
            return False

        # get server attached volumes
        volumes = self.conn.server.get_volumes(server_ext_id)
        self.task.progress("Get server %s volumes: %s" % (server_ext_id, truncate(volumes, 200)))

        # remove server
        self.conn.server.delete(server_ext_id)
        self.task.progress("Delete server %s - Starting" % server_ext_id)

        # loop until entity is not deleted or get error
        while True:
            try:
                inst = OpenstackServer.get_remote_server(
                    resource.controller, server_ext_id, self.container, server_ext_id
                )
                if inst == {}:
                    self.task.progress("Server does not exist anymore")
                    raise Exception("Server does not exist anymore")
                status = inst["status"]
                if status == "DELETED":
                    break
                elif status == "ERROR":
                    self.task.progress("Delete server %s - Error" % server_ext_id)
                    raise Exception("Can not delete server %s" % server_ext_id)

                self.task.progress("")
                time.sleep(2)
            except:
                # status DELETED was not been captured but server does not exists anymore
                break

        resource.update_internal(ext_id="")
        self.task.progress("Delete server %s - Completed" % server_ext_id)

        return True

    def delete_physical_port(self, port_ext_id):
        # check volume exists
        try:
            OpenstackPort.get_remote_port(self.container.controller, port_ext_id, self.container, port_ext_id)
        except:
            self.task.progress("Port %s does not exist anymore" % port_ext_id)
            return False

        # delete openstack volume
        self.conn.network.port.delete(port_ext_id)
        self.task.progress("Delete port %s - Starting" % port_ext_id)

        # loop until entity is not deleted or get error
        while True:
            try:
                inst = OpenstackPort.get_remote_port(
                    self.container.controller, port_ext_id, self.container, port_ext_id
                )
                status = inst["status"]
                if status == "ERROR":
                    self.task.progress("Delete port %s - Error" % port_ext_id)
                    raise Exception("Can not delete port %s" % port_ext_id)

                self.task.progress("")
                time.sleep(1)
            except:
                # port does not exists anymore
                break

        self.task.progress("Delete port %s - Completed" % port_ext_id)

        return True

    def delete_physical_volume(self, volume_ext_id):
        # check volume exists
        try:
            OpenstackVolume.get_remote_volume(self.container.controller, volume_ext_id, self.container, volume_ext_id)
        except:
            self.task.progress("Volume %s does not exist anymore" % volume_ext_id)
            return False

        # remote server snapshots
        snapshots = self.conn.volume.snapshot.list(volume_id=volume_ext_id)
        for snapshot in snapshots:
            self.conn.volume.snapshot.delete(snapshot["id"])
            while True:
                try:
                    self.conn.volume.snapshot.get(snapshot["id"])
                    time.sleep(2)
                except:
                    self.task.progress("Volume %s snapshot %s deleted" % (volume_ext_id, snapshot["id"]))
                    break

        # delete openstack volume
        self.conn.volume.delete(volume_ext_id)
        self.task.progress("Delete volume %s - Starting" % volume_ext_id)

        # loop until entity is not deleted or get error
        while True:
            try:
                inst = OpenstackVolume.get_remote_volume(
                    self.container.controller,
                    volume_ext_id,
                    self.container,
                    volume_ext_id,
                )
                status = inst["status"]
                if status == "error_deleting":
                    self.task.progress("Delete volume %s - Error" % volume_ext_id)
                    raise Exception("Can not delete volume %s" % volume_ext_id)
                elif status == "error":
                    self.task.progress("delete volume %s - Error" % volume_ext_id)
                    raise Exception("Can not delete volume %s" % volume_ext_id)

                self.task.progress("")
                time.sleep(2)
            except:
                # volume does not exists anymore
                break

        # res.update_internal(ext_id=None)
        self.task.progress("Delete volume %s - Completed" % volume_ext_id)

        return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_server(self, options):
    """Create openstack server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: server physical id, root volume physical id
    """
    params = self.get_shared_data()
    cid = params.get("cid")
    oid = params.get("id")
    name = params.get("name")
    desc = params.get("desc")
    parent_id = params.get("parent")
    availability_zone = params.get("availability_zone")
    networks = params.get("networks")
    volumes = params.get("block_device_mapping_v2")
    admin_pass = params.get("adminPass", None)
    flavor = params.get("flavor")
    sgs = params.get("security_groups")
    sgs_ext_id = params.get("security_groups_ext_id")
    user_data = params.get("user_data")
    project_extid = params.get("project_extid")
    config_drive = params.get("config_drive")
    self.progress("Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    resource = container.get_resource(oid)
    conn = container.conn
    self.progress("Get container %s" % cid)

    main_volume = volumes.pop(0)

    helper = ServerHelper(self, container)

    # create main volume
    volume_name = "%s-root-volume" % name
    volume_desc = "Root Volume %s" % name
    boot_volume_id = helper.create_volume(
        volume_name,
        volume_desc,
        parent_id,
        project_extid,
        availability_zone,
        main_volume,
        resource,
    )
    self.progress("Create boot volume: %s" % boot_volume_id)

    # get networks
    nets = []
    for network in networks:
        uuid = network.get("uuid", None)
        subnet = network.get("subnet_uuid", None)

        # generate port with network and subnet
        if subnet is not None and uuid is not None:
            # create port
            fixed_ips = [{"subnet_id": subnet}]
            port_name = "%s-port" % name
            port = conn.network.port.create(
                port_name,
                uuid,
                fixed_ips,
                tenant_id=project_extid,
                security_groups=sgs_ext_id,
            )

            # append port
            nets.append({"port": port.get("id")})

            # create port resource
            network_resource = self.get_resource_with_no_detail(network.get("resource_id"))
            objid = "%s//%s" % (network_resource.objid, id_gen())
            resource_port = container.add_resource(
                objid=objid,
                name=port_name,
                resource_class=OpenstackPort,
                ext_id=port.get("id"),
                active=False,
                desc=port_name,
                attrib={},
                parent=network_resource.oid,
                tags=["openstack", "port"],
            )
            container.update_resource(resource_port.id, state=ResourceState.ACTIVE, active=True)
            self.progress("Create port resource %s" % resource_port.id)

        # set only network id
        elif uuid is not None:
            nets.append({"uuid": uuid})

    self.progress("Get network config: %s" % nets)

    # start server creation
    server = conn.server.create(
        name,
        flavor,
        accessipv4=None,
        accessipv6=None,
        networks=nets,
        boot_volume_id=boot_volume_id,
        adminpass=admin_pass,
        description=desc,
        metadata=None,
        image=None,
        security_groups=sgs,
        personality=None,
        user_data=user_data,
        availability_zone=availability_zone,
        config_drive=config_drive,
    )
    server_id = server["id"]
    self.progress("Create server %s - Starting" % server_id)

    # attach remote server
    container.update_resource(oid, ext_id=server_id)
    self.progress("Attach remote server %s" % server_id)

    # loop until entity is not stopped or get error
    while True:
        inst = OpenstackServer.get_remote_server(resource.controller, server_id, container, server_id)
        OpenstackVolume.get_remote_volume(resource.controller, boot_volume_id, container, boot_volume_id)
        # inst = conn.server.get(oid=server_id)
        status = inst["status"]
        if status == "ACTIVE":
            break
        elif status == "ERROR":
            error = inst["fault"]["message"]
            self.progress("Create server %s - Error%s" % (server_id, error))
            raise Exception("Can not create server %s: %s" % (server_id, error))

        self.progress("")
        time.sleep(task_local.delta)

    self.progress("Create server %s - Completed" % server_id)

    # append other volumes to server
    index = 0
    for config in volumes:
        index += 1
        volume_name = "%s-other-volume-%s" % (name, index)
        volume_desc = "Volume %s %s" % (name, index)
        volume_id = helper.create_volume(
            volume_name,
            volume_desc,
            parent_id,
            project_extid,
            availability_zone,
            config,
            resource,
        )
        self.progress("Create other volume: %s" % volume_id)

        # attach volume to server
        conn.server.add_volume(server_id, volume_id)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
            # inst = conn.volume.get(oid=volume_id)
            status = inst["status"]
            if status == "in-use":
                break
            elif status == "error":
                self.progress("Attach openstack volume %s - Error" % volume_id)
                raise Exception("Can not attach openstack volume %s" % volume_id)

            self.progress("")
            time.sleep(task_local.delta)

    # refresh server info
    OpenstackServer.get_remote_server(resource.controller, server_id, container, server_id)

    # save current data in shared area
    params["ext_id"] = server_id
    self.set_shared_data(params)
    self.progress("Update shared area")

    return [server_id, boot_volume_id]


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_server(self, options):
    """Delete openstack server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: server physical id, [volume physical id, ..]
    """
    params = self.get_shared_data()
    cid = params.get("cid")
    oid = params.get("id")
    ext_id = params.get("ext_id")
    parent_id = params.get("parent_id")
    self.progress("Get configuration params")

    # get server resource
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    resource = self.get_resource_with_detail(oid)
    helper = ServerHelper(self, container)
    self.progress("Get server resource")

    # get volumes
    params["volume_ids"] = [v["uuid"] for v in resource.get_volumes()]

    # get ports
    params["port_ids"] = [v["uuid"] for v in resource.get_ports()]

    self.set_shared_data(params)

    if self.is_ext_id_valid(ext_id) is True:
        helper.delete_physical_server(ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_ports(self, options):
    """Remove server ports

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: uuid of the removed resource
    """
    params = self.get_shared_data()
    cid = params.get("cid")
    parent_id = params.get("parent_id")
    port_ids = params.get("port_ids")
    self.progress("Get configuration params")

    # get server resource
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    helper = ServerHelper(self, container)
    self.progress("Get server resource")

    # delete ports
    for port_id in port_ids:
        try:
            resource = self.get_resource(port_id)
            ext_id = resource.ext_id
            if self.is_ext_id_valid(ext_id) is True:
                # delete physical port
                helper.delete_physical_port(ext_id)

            # delete resource
            resource.expunge_internal()
            self.progress("Delete port %s resource" % port_id)
        except Exception as ex:
            self.progress(ex)
            logger.warn(ex)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_volumes(self, options):
    """Remove server volumes

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: uuid of the removed resource
    """
    params = self.get_shared_data()
    cid = params.get("cid")
    parent_id = params.get("parent_id")
    volume_ids = params.get("volume_ids")
    self.progress("Get configuration params")

    # get server resource
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    helper = ServerHelper(self, container)
    self.progress("Get server resource")

    # delete volumes
    for volume_id in volume_ids:
        try:
            resource = self.get_resource(volume_id)
            ext_id = resource.ext_id
            if self.is_ext_id_valid(ext_id) is True:
                # delete physical volume
                helper.delete_physical_volume(ext_id)

            # delete resource
            resource.expunge_internal()
            self.progress("Delete volume %s resource" % volume_id)
        except ApiManagerError as ex:
            self.progress(ex)
            logger.warn(ex)


#
# action
#
def server_action(task, action, success, error, final_status="ACTIVE"):
    """Execute a server action

    :param task: calery task instance
    :param action: action to execute
    :param success: success message
    :param error: error message
    :param final_status: final status that server must raise [default=ACTIVE]
    :return: ext_id
    :raise:
    """
    task.set_operation()

    # get params from shared data
    params = task.get_shared_data()
    task.progress("Get shared area")

    # validate input params
    task.progress("Get configuration params: %s" % params)
    cid = params.pop("cid")
    oid = params.pop("id")
    ext_id = params.pop("ext_id")

    # get server resource
    task.get_session()
    container = task.get_container(cid)
    resource = task.get_resource(oid)
    conn = container.conn
    task.progress("Get container %s" % cid)

    # execute action
    action(container, resource, **params)

    # loop until action completed or return error
    while True:
        inst = OpenstackServer.get_remote_server(resource.controller, ext_id, container, ext_id)
        # inst = container.conn.server.get(oid=ext_id)
        status = inst["status"]
        task.progress("Read server %s status: %s" % (ext_id, status))
        if status == final_status:
            break
        elif status == "ERROR":
            raise Exception(error)

        time.sleep(task_local.delta)

    task.progress(success)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_start(self, options):
    """Start server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        conn.server.start(ext_id)

    res = server_action(self, action, "Start server", "Error starting server", final_status="ACTIVE")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_stop(self, options):
    """Stop server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        conn.server.stop(ext_id)

    res = server_action(self, action, "Stop server", "Error stopping server", final_status="SHUTOFF")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_reboot(self, options):
    """Reboot server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        conn.server.reboot(ext_id)

    res = server_action(self, action, "Reboot server", "Error rebootting server", final_status="ACTIVE")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_pause(self, options):
    """Pause server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        conn.server.pause(ext_id)

    res = server_action(self, action, "Pause server", "Error pausing server", final_status="PAUSED")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_unpause(self, options):
    """Unpause server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        conn.server.unpause(ext_id)

    res = server_action(self, action, "Unpause server", "Error unpausing server", final_status="ACTIVE")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_migrate(self, options):
    """Migrate server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.live** (bool): if True run live migration
    :param sharedarea.host: physical server where migrate [optional]
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        live = params.get("live")
        host = params.get("host", None)
        if live is True:
            conn.server.live_migrate(ext_id, host=host)
        else:
            conn.server.migrate(ext_id)
        conn.server.migrate(ext_id)

    res = server_action(self, action, "Migrate server", "Error migrating server", final_status="ACTIVE")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_set_flavor(self, options):
    """Set flavor to server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.flavor** (bool): :param flavor: flavor uuid or name
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        flavor = params.get("flavor")
        conn.server.set_flavor(ext_id, flavor)

    res = server_action(
        self,
        action,
        "Set flavor to server",
        "Error setting flavor to server",
        final_status="ACTIVE",
    )
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_add_volume(self, options):
    """Attach volume to server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.volume_extid: physical id of the volume
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        volume_extid = params.get("volume_extid")
        conn.server.add_volume(ext_id, volume_extid)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackVolume.get_remote_volume(container.controller, volume_extid, container, volume_extid)
            # inst = conn.volume.get(oid=volume_id)
            status = inst["status"]
            if status == "in-use":
                break
            elif status == "error":
                self.progress("Attach openstack volume %s - Error" % volume_extid)
                raise Exception("Can not attach openstack volume %s" % volume_extid)

            self.progress("")
            time.sleep(task_local.delta)

    res = server_action(
        self,
        action,
        "Attach volume to server",
        "Error attaching volume to server",
        final_status="ACTIVE",
    )
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_del_volume(self, options):
    """Detach volume from server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.volume_extid: physical id of the volume
    :return: True
    """

    def action(container, resource, **params):
        conn = container.conn
        ext_id = resource.ext_id
        volume_extid = params.get("volume_extid")
        conn.server.remove_volume(ext_id, volume_extid)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackVolume.get_remote_volume(container.controller, volume_extid, container, volume_extid)
            # inst = conn.volume.get(oid=volume_id)
            status = inst["status"]
            if status == "available":
                break
            elif status == "error":
                self.progress("Detach openstack volume %s - Error" % volume_extid)
                raise Exception("Can not detach openstack volume %s" % volume_extid)

    res = server_action(
        self,
        action,
        "Detach volume from server",
        "Error detaching volume from server",
        final_status="ACTIVE",
    )
    return res
