# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from time import sleep
from logging import getLogger
import ujson as json
from beecell.simple import id_gen, dict_get, str2bool
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import task_step, TaskError
from beehive.common.task_v2.manager import task_manager
from beehive_resource.model import ResourceState
from beehive_resource.task_v2 import AbstractResourceTask
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer


logger = getLogger(__name__)


class ServerHelper(object):
    def __init__(self, task, step_id, container):
        self.task = task
        self.step_id = step_id
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

        volume_id = None

        # create boot volume
        if source_type in ["image", "snapshot", None]:
            # create volume resource
            parent = self.task.get_resource_by_extid(project_extid)
            objid = f"{parent.objid}//{id_gen()}"
            volume_size = config.get("volume_size")
            volume_type_id = config.get("volume_type", None)
            volume_type = None
            if volume_type_id is not None:
                volume_type = self.task.get_simple_resource(volume_type_id).ext_id
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
            self.task.progress(self.step_id, msg=f"create volume resource {volume.id}")

            # link volume id to server
            server.add_link(
                f"{server.oid}-{volume.id}-volume-link",
                "volume",
                volume.id,
                attributes={"boot": boot},
            )
            self.task.progress(
                self.step_id,
                msg=f"setup volume link from {volume.id} to server {server.oid}",
            )

            image = None
            snapshot = None
            if source_type == "image":
                image = config.get("uuid")
            elif source_type == "snapshot":
                snapshot = config.get("uuid")
            volume_ext = self.conn.volume_v3.create(
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
            self.task.progress(self.step_id, msg=f"create openstack volume {volume_id} - Starting")

            # attach remote volume
            self.container.update_resource(volume.id, ext_id=volume_id)
            self.task.progress(
                self.step_id,
                msg=f"Attach openstack volume {volume_id} to volume {volume.id}",
            )

            # loop until entity is not stopped or get error
            while True:
                inst = OpenstackVolume.get_remote_volume(
                    self.container.controller, volume_id, self.container, volume_id
                )
                status = inst.get("status", "error")
                if status == "available":
                    break
                if status == "error":
                    self.task.progress(
                        self.step_id,
                        msg=f"create openstack volume {volume_id} - Error",
                    )
                    raise Exception(f"Can not create openstack volume {volume_id}")

                self.task.progress(self.step_id, msg="")
                sleep(2)

            self.task.progress(self.step_id, msg=f"create openstack volume {volume_id} - End")

            # activate volume
            self.container.update_resource(volume.id, state=ResourceState.ACTIVE, active=True)
            self.task.progress(self.step_id, msg=f"Activate volume {volume_id}")

        # get existing volume
        elif source_type in ["volume"]:
            # get existing volume resource
            volume_uuid = config.get("uuid", None)
            volume_clone = config.get("clone", False)
            # volume_extid = config.get('ext_id', None)

            if volume_uuid is not None:
                volume = self.task.get_resource(volume_uuid)

                if volume_clone is True:
                    # create volume resource
                    parent = self.task.get_resource_by_extid(project_extid)
                    objid = "{parent.objid}//{id_gen()}"
                    volume_size = volume.get_size()
                    volume_type_id = config.get("volume_type", None)
                    volume_type = self.task.get_resource(volume_type_id)
                    final_volume_resource = self.container.add_resource(
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
                    self.task.progress(self.step_id, msg=f"create volume resource {final_volume_resource.id}")

                    # link volume id to server
                    server.add_link(
                        "{server.oid}-{final_volume_resource.id}-volume-link",
                        "volume",
                        final_volume_resource.id,
                        attributes={"boot": boot},
                    )
                    self.task.progress(
                        self.step_id, msg=f"Setup volume link from {final_volume_resource.id} to server {server.oid}"
                    )

                    # if original volume is in a different container you must clone it and generate a new one in the
                    # server container
                    if volume.container_id != self.container.oid:
                        # take a snapshot of the volume to be cloned
                        # create a volume from the snapshot
                        # I retype this volume to make it go to the target backend (e.g. Vercelli)
                        # in the target hypervisor (e.g. Vercelli) call the cinder manage of the cloned volume

                        # get origin container
                        orig_container = self.task.get_container(volume.container_id)

                        # get origin volume_type
                        backend = volume_type.get_backend()
                        backend_host = backend["name"]
                        origin_backend = orig_container.conn.volume_v3.get_backend_storage_pools(hostname=backend_host)
                        origin_backend_name = dict_get(origin_backend[0], "capabilities.volume_backend_name")
                        self.task.logger.warn(origin_backend_name)
                        origin_volume_type = orig_container.conn.volume_v3.type.list(backend_name=origin_backend_name)
                        if len(origin_volume_type) != 1:
                            msg = f"""\
no volume type found in container {orig_container.oid} for volume type {volume_type_id}"
"""
                            raise TaskError(msg)
                        origin_volume_type_id = origin_volume_type[0]["id"]

                        # clone volume
                        clone_volume = orig_container.conn.volume_v3.clone(name, volume.ext_id, project_extid)
                        clone_volume_id = clone_volume["id"]
                        self.task.progress(
                            self.step_id,
                            msg=f"clone openstack volume {volume.ext_id} to {clone_volume_id}",
                        )

                        # retype volume
                        orig_container.conn.volume_v3.change_type(clone_volume_id, origin_volume_type_id)
                        self.task.progress(self.step_id, msg=f"server retyping openstack volume {clone_volume_id}")
                        polling_freq = 20
                        while True:
                            res = orig_container.conn.volume_v3.get(clone_volume_id)
                            status = res["status"]
                            if status == "available":
                                break
                            if status == "error":
                                raise TaskError(f"openstack volume {clone_volume_id} change type error")
                            sleep(polling_freq)
                        self.task.progress(
                            self.step_id,
                            msg=f"retype openstack volume {clone_volume_id}",
                        )
                        self.task.progress(self.step_id, msg=f"server retyped openstack volume {clone_volume_id}")

                        # manage volume in server container
                        final_volume = self.container.conn.volume_v3.manage(
                            clone_volume_id,
                            name,
                            volume_type.ext_id,
                            bootable=boot,
                            desc=desc,
                            availability_zone="nova",
                            host=backend_host,
                        )
                        container_oid = self.container.oid
                        self.task.progress(
                            self.step_id, msg=f"manage openstack volume {clone_volume_id} on container {container_oid}"
                        )

                        # unmanage volume in original container
                        orig_container.conn.volume_v3.unmanage(clone_volume_id)
                        orig_container_oid = orig_container.oid
                        self.task.progress(
                            self.step_id,
                            msg=f"manage openstack volume {clone_volume_id} on container {orig_container_oid}",
                        )

                        # attach remote volume
                        self.container.update_resource(final_volume_resource.id, ext_id=final_volume["id"])
                        final_volume_id = final_volume["id"]
                        final_volume_resource_id = final_volume_resource.id
                        self.task.progress(
                            self.step_id,
                            msg=f"attach openstack volume {final_volume_id} to volume {final_volume_resource_id}",
                        )

                        # activate volume
                        self.container.update_resource(volume.id, state=ResourceState.ACTIVE, active=True)
                        self.task.progress(self.step_id, msg=f"Activate volume {volume.id}")

                        volume_id = final_volume["id"]
                    else:
                        pass
                        # todo: manage volume in the same container
                else:
                    volume_id = volume.ext_id

                    # link volume id to server
                    server.add_link(
                        f"{server.oid}-{volume.oid}-volume-link",
                        "volume",
                        volume.oid,
                        attributes={"boot": boot},
                    )
                    self.task.progress(self.step_id, msg=f"Setup volume link from {volume.oid} to server {server.oid}")

        return volume_id

    def delete_physical_server(self, server_ext_id):
        resource = self.container.get_resource_by_extid(server_ext_id)

        # check server exists
        rs = OpenstackServer.get_remote_server(resource.controller, server_ext_id, self.container, server_ext_id)
        if rs == {}:
            self.task.progress(self.step_id, msg=f"Server {server_ext_id} does not exist anymore")
            return False

        # remove server
        self.conn.server.delete(server_ext_id)
        self.task.progress(self.step_id, msg=f"Delete server {server_ext_id}- Starting")

        # loop until entity is not deleted or get error
        while True:
            try:
                inst = OpenstackServer.get_remote_server(
                    resource.controller, server_ext_id, self.container, server_ext_id
                )
                if inst == {}:
                    self.task.progress(self.step_id, msg="Server does not exist anymore")
                    raise Exception("Server does not exist anymore")
                status = inst["status"]
                if status == "DELETED":
                    break
                if status == "ERROR":
                    self.task.progress(self.step_id, msg=f"Delete server {server_ext_id} - Error")
                    raise Exception(f"Can not delete server {server_ext_id}")

                self.task.progress(self.step_id, msg="")
                sleep(2)
            except:
                # status DELETED was not been captured but server does not exists anymore
                break

        resource.update_internal(ext_id="")
        self.task.progress(self.step_id, msg=f"Delete server {server_ext_id} - Completed")

        return True

    def delete_physical_port(self, port_ext_id):
        # check volume exists
        try:
            OpenstackPort.get_remote_port(self.container.controller, port_ext_id, self.container, port_ext_id)
        except:
            self.task.progress(self.step_id, msg=f"Port {port_ext_id} does not exist anymore")
            return False

        # delete openstack volume
        self.conn.network.port.delete(port_ext_id)
        self.task.progress(self.step_id, msg=f"Delete port {port_ext_id} - Starting")

        # loop until entity is not deleted or get error
        while True:
            try:
                inst = OpenstackPort.get_remote_port(
                    self.container.controller, port_ext_id, self.container, port_ext_id
                )
                status = inst["status"]
                if status == "ERROR":
                    self.task.progress(self.step_id, msg=f"Delete port {port_ext_id} - Error")
                    raise Exception(f"Can not delete port {port_ext_id}")

                self.task.progress(self.step_id, msg="")
                sleep(1)
            except:
                # port does not exists anymore
                break

        self.task.progress(self.step_id, msg=f"Delete port {port_ext_id} - Completed")

        return True

    def delete_physical_volume(self, volume_ext_id):
        # check volume exists
        try:
            OpenstackVolume.get_remote_volume(self.container.controller, volume_ext_id, self.container, volume_ext_id)
        except:
            self.task.progress(self.step_id, msg=f"Volume {volume_ext_id} does not exist anymore")
            return False

        # remote server snapshots
        snapshots = self.conn.volume_v3.snapshot.list(volume_id=volume_ext_id)
        conn_vol_snap = self.conn.volume_v3.snapshot
        for snapshot in snapshots:
            snapshot_id = snapshot["id"]
            conn_vol_snap.delete(snapshot_id)
            while True:
                try:
                    conn_vol_snap.get(snapshot_id)
                    sleep(2)
                except:
                    self.task.progress(
                        self.step_id,
                        msg=f"Volume {volume_ext_id} snapshot {snapshot_id} deleted",
                    )
                    break

        # delete openstack volume
        self.conn.volume_v3.reset_status(volume_ext_id, "available", "detached", "success")
        self.conn.volume_v3.delete(volume_ext_id)
        self.task.progress(self.step_id, msg=f"Delete volume {volume_ext_id} - Starting")

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
                    self.task.progress(self.step_id, msg=f"Delete volume {volume_ext_id} - Error")
                    raise Exception(f"Can not delete volume {volume_ext_id}")
                if status == "error":
                    self.task.progress(self.step_id, msg=f"delete volume {volume_ext_id} - Error")
                    raise Exception(f"Can not delete volume {volume_ext_id}")

                self.task.progress(self.step_id, msg="")
                sleep(2)
            except:
                # volume does not exists anymore
                break

        # res.update_internal(ext_id=None)
        self.task.progress(self.step_id, msg=f"Delete volume {volume_ext_id} - Completed")

        return True


class ServerTask(AbstractResourceTask):
    """Server task"""

    name = "server_task"
    entity_class = OpenstackServer

    @staticmethod
    @task_step()
    def server_create_physical_step(task, step_id, params, *args, **kvargs):
        """create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
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

        container = task.get_container(cid, projectid=parent_id)
        resource = container.get_resource(oid)
        conn = container.conn
        task.progress(step_id, msg=f"Get container {cid}")

        main_volume = volumes.pop(0)

        helper = ServerHelper(task, step_id, container)

        # create main volume
        volume_name = f"{name}-root-volume"
        volume_desc = f"Root Volume {name}"
        boot_volume_id = helper.create_volume(
            volume_name,
            volume_desc,
            parent_id,
            project_extid,
            availability_zone,
            main_volume,
            resource,
            boot=True,
        )
        task.progress(step_id, msg=f"create boot volume: {boot_volume_id}")

        # get networks
        nets = []
        for network in networks:
            uuid = network.get("uuid")
            subnet = network.get("subnet_uuid")
            ip_address = dict_get(network, "fixed_ip.ip")

            # generate port with network and subnet
            if subnet is not None and uuid is not None:
                # create port
                fixed_ip = {"subnet_id": subnet}
                if ip_address is not None:
                    fixed_ip["ip_address"] = ip_address
                port_name = f"{name}-port"
                port = conn.network.port.create(
                    port_name,
                    uuid,
                    [fixed_ip],
                    tenant_id=project_extid,
                    security_groups=sgs_ext_id,
                )

                # append port
                nets.append({"port": port.get("id")})

                # create port resource
                network_resource = task.get_simple_resource(network.get("resource_id"))
                objid = f"{network_resource.objid}//{id_gen()}"
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
                resource_port_id = resource_port.id
                container.update_resource(resource_port_id, state=ResourceState.ACTIVE, active=True)
                task.progress(step_id, msg=f"create port resource {resource_port_id}")

            # set only network id
            elif uuid is not None:
                nets.append({"uuid": uuid})

        task.progress(step_id, msg=f"Get network config: {nets}")

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
        task.progress(step_id, msg=f"create server {server_id} - Starting")

        # attach remote server
        container.update_resource(oid, ext_id=server_id)
        task.progress(step_id, msg=f"Attach remote server {server_id}")

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackServer.get_remote_server(resource.controller, server_id, container, server_id)
            OpenstackVolume.get_remote_volume(resource.controller, boot_volume_id, container, boot_volume_id)
            status = inst["status"]
            if status == "ACTIVE":
                break
            if status == "ERROR":
                error = inst["fault"]["message"]
                task.progress(step_id, msg=f"create server {server_id} - Error {error}")
                raise Exception(f"Can not create server {server_id}: {error}")

            task.progress(step_id, msg="")
            sleep(2)

        task.progress(step_id, msg=f"create server {server_id} - Completed")

        # append other volumes to server
        index = 0
        for config in volumes:
            index += 1
            volume_name = f"{name}-other-volume-{index}"
            volume_desc = f"Volume {name} {index}"
            volume_id = helper.create_volume(
                volume_name,
                volume_desc,
                parent_id,
                project_extid,
                availability_zone,
                config,
                resource,
            )
            task.progress(step_id, msg=f"create other volume: {volume_id}")

            # attach volume to server
            conn.server.add_volume(server_id, volume_id)

            # loop until entity is not stopped or get error
            while True:
                inst = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
                status = inst["status"]
                if status == "in-use":
                    break
                if status == "error":
                    task.progress(step_id, msg=f"Attach openstack volume {volume_id} - Error")
                    raise Exception(f"Can not attach openstack volume {volume_id}")

                task.progress(step_id, msg="")
                sleep(2)

        # refresh server info
        OpenstackServer.get_remote_server(resource.controller, server_id, container, server_id)

        # save current data in shared area
        params["ext_id"] = server_id

        return oid, params

    @staticmethod
    @task_step()
    def server_expunge_physical_step(task, step_id, params, *args, **kvargs):
        """Delete openstack server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        parent_id = params.get("parent_id")

        container = task.get_container(cid, projectid=parent_id)
        resource = task.get_resource(oid)
        helper = ServerHelper(task, step_id, container)
        task.progress(step_id, msg="Get server resource")

        # remove snapshot nova images
        resource.delete_snapshots()
        task.progress(step_id, msg="Remove snapshots nova images")

        # get volumes
        params["volume_ids"] = []

        # get ports
        params["port_ids"] = []

        if resource.is_ext_id_valid():
            # get volumes
            params["volume_ids"] = [v["uuid"] for v in resource.get_volumes()]

            # get ports
            params["port_ids"] = [v["uuid"] for v in resource.get_ports()]

            helper.delete_physical_server(ext_id)

        task.set_shared_data(params)

        return oid, params

    @staticmethod
    @task_step()
    def patch_server_step(task, step_id, params, *args, **kvargs):
        """Patch openstack server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        task.progress(step_id, msg="Get configuration params")
        orchestrator = task.get_container(cid)
        vsphere_server = orchestrator.get_resource(oid)
        vsphere_server.do_patch()
        return oid, params

    @staticmethod
    @task_step()
    def server_expunge_ports_physical_step(task, step_id, params, *args, **kvargs):
        """Remove server ports

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent_id")
        port_ids = params.get("port_ids")

        container = task.get_container(cid, projectid=parent_id)
        helper = ServerHelper(task, step_id, container)
        task.progress(step_id, msg="Get server resource")

        # delete ports
        for port_id in port_ids:
            try:
                resource = task.get_simple_resource(port_id)
                if resource.is_ext_id_valid() is True:
                    # delete physical port
                    helper.delete_physical_port(resource.ext_id)

                # delete resource
                resource.expunge_internal()
                task.progress(step_id, msg=f"Delete port {port_id} resource")
            except Exception as ex:
                task.progress(step_id, msg=str(ex))

        return oid, params

    @staticmethod
    @task_step()
    def server_expunge_volumes_physical_step(task, step_id, params, *args, **kvargs):
        """Remove server volumes

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent_id")
        volume_ids = params.get("volume_ids")
        task.progress(step_id, msg="Get configuration params")

        # get server resource
        task.get_session()
        container = task.get_container(cid, projectid=parent_id)
        helper = ServerHelper(task, step_id, container)
        task.progress(step_id, msg="Get server resource")

        # delete volumes
        for volume_id in volume_ids:
            try:
                resource = task.get_simple_resource(volume_id)
                if resource.is_ext_id_valid() is True:
                    # delete physical volume
                    helper.delete_physical_volume(resource.ext_id)

                # delete resource
                resource.expunge_internal()
                task.progress(step_id, msg=f"Delete volume {volume_id} resource")
            except ApiManagerError as ex:
                task.progress(step_id, msg=ex)

        return oid, params

    @staticmethod
    def server_action(
        task,
        step_id,
        action,
        success,
        error,
        params,
        final_status="ACTIVE",
        projectid=None,
    ):
        """Execute a server action

        :param task: calery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param final_status: final status that server must raise. If ORIGINAL final status must be the original status
            [default=ACTIVE]
        :param params: input params
        :param projectid: projectid [optional]
        :return: action response
        :raise:
        """
        task.progress(step_id, msg=f"start action {action.__name__}")
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        # container = task.get_container(cid)
        container = task.get_container(cid, projectid=projectid)
        resource = task.get_simple_resource(oid)

        # get original state
        if final_status == "ORIGINAL":
            inst = OpenstackServer.get_remote_server(resource.controller, ext_id, container, ext_id)
            final_status = inst["status"]

        # execute action
        res = action(container, resource, **params)

        # loop until action completed or return error
        while True:
            inst = OpenstackServer.get_remote_server(resource.controller, ext_id, container, ext_id)
            status = inst["status"]
            task.progress(step_id, msg=f"Read server {ext_id} status: {status}")
            if status == final_status:
                break
            if status == "ERROR":
                raise Exception(error)

            sleep(2)

        task.progress(step_id, msg=success)
        task.progress(step_id, msg=f"stop action {action.__name__}")

        return res

    @staticmethod
    @task_step()
    def server_start_step(task, step_id, params, *args, **kvargs):
        """Start server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def start_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            conn.server.start(ext_id)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            start_action,
            "Start server",
            "Error starting server",
            params,
            final_status="ACTIVE",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_stop_step(task, step_id, params, *args, **kvargs):
        """Stop server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def stop_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            conn.server.stop(ext_id)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            stop_action,
            "Stop server",
            "Error stopping server",
            params,
            final_status="SHUTOFF",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_reboot_step(task, step_id, params, *args, **kvargs):
        """Reboot server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def reboot_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            conn.server.reboot(ext_id)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            reboot_action,
            "Reboot server",
            "Error rebootting server",
            params,
            final_status="ACTIVE",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_pause_step(task, step_id, params, *args, **kvargs):
        """Pause server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def pause_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            conn.server.pause(ext_id)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            pause_action,
            "Pause server",
            "Error pausing server",
            params,
            final_status="PAUSED",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_unpause_step(task, step_id, params, *args, **kvargs):
        """Unpause server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def unpause_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            conn.server.unpause(ext_id)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            unpause_action,
            "Unpause server",
            "Error unpausing server",
            params,
            final_status="ACTIVE",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_migrate_step(task, step_id, params, *args, **kvargs):
        """Migrate server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def migrate_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            live = params.get("live")
            host = params.get("host", None)
            if live is True:
                conn.server.live_migrate(ext_id, host=host)
            else:
                conn.server.migrate(ext_id)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            migrate_action,
            "Migrate server",
            "Error migrating server",
            params,
            final_status="ACTIVE",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_set_flavor_step(task, step_id, params, *args, **kvargs):
        """Set flavor to server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def set_flavor_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            flavor = params.get("flavor")
            conn.server.set_flavor(ext_id, flavor)
            return True

        res = ServerTask.server_action(
            task,
            step_id,
            set_flavor_action,
            "Set flavor to server",
            "Error setting flavor to server",
            params,
            final_status="ORIGINAL",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_add_volume_step(task, step_id, params, *args, **kvargs):
        """Attach volume to server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def add_volume_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            volume_extid = params.get("volume_extid")
            conn.server.add_volume(ext_id, volume_extid)

            # loop until entity is not stopped or get error
            while True:
                inst = OpenstackVolume.get_remote_volume(container.controller, volume_extid, container, volume_extid)
                status = inst["status"]
                if status == "in-use":
                    break
                if status == "error":
                    task.progress(step_id, msg=f"Attach openstack volume {volume_extid} - Error")
                    raise Exception(f"Can not attach openstack volume {volume_extid}")

                task.progress(step_id, msg="")
                sleep(2)

            # link volume id to server
            volume_obj = params["volume"]
            server_obj = params["server"]
            server_obj.add_link(
                "{volume_obj.oid}-{server_obj.oid}-volume-link",
                "volume",
                volume_obj.oid,
                attributes={"boot": False},
            )

            return True

        params["volume"] = task.get_resource(params.get("volume"))
        params["server"] = task.get_simple_resource(params.get("id"))
        res = ServerTask.server_action(
            task,
            step_id,
            add_volume_action,
            "Attach volume to server",
            "Error attaching volume to server",
            params,
            final_status="ACTIVE",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_del_volume_step(task, step_id, params, *args, **kvargs):
        """Delete server volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def del_volume_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            volume_extid = params.get("volume_extid")
            conn.server.remove_volume(ext_id, volume_extid)

            # delete link between volume and server
            volume_obj = params["volume"]
            server_obj = params["server"]
            server_obj.del_link(volume_obj.oid)

            # loop until entity is available or get error
            while True:
                inst = OpenstackVolume.get_remote_volume(container.controller, volume_extid, container, volume_extid)
                status = inst["status"]
                if status == "available":
                    break
                if status == "error":
                    task.progress(step_id, msg=f"Delete openstack volume {volume_extid} - Error")
                    raise Exception(f"Can not delete openstack volume {volume_extid}")

                sleep(2)

            return True

        params["volume"] = task.get_simple_resource(params.get("volume"))
        params["server"] = task.get_simple_resource(params.get("id"))
        res = ServerTask.server_action(
            task,
            step_id,
            del_volume_action,
            "Detach volume from server",
            "Error detaching volume from server",
            params,
            final_status="ACTIVE",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_extend_volume_step(task, step_id, params, *args, **kvargs):
        """extend volume of server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def extend_volume_action(container, resource, **params):
            conn = container.conn
            volume_ext_id = params.get("volume_extid")
            new_disk_gb = int(params["volume_size"])
            server_ext_id = params["server"].ext_id
            vol_v3 = conn.volume_v3
            volume = vol_v3.get(volume_ext_id)
            old_disk_gb = volume.get("size")
            if new_disk_gb < old_disk_gb:
                msg = f"""\
Cannot extend the volume {volume_ext_id} of server {server_ext_id} to {new_disk_gb} GB.
It is an extends. You can only increase the volume size!
The volume size is {old_disk_gb} GB.
"""
                raise Exception(msg)
            backend_host = volume.get("os-vol-host-attr:host")
            backend = next(
                b for b in vol_v3.get_backend_storage_pools(hostname=backend_host) if b["name"] == backend_host
            )
            if backend is None:
                raise Exception(f"Backend host {backend_host} does not exist")
            free_capacity_gb = backend["capabilities"]["free_capacity_gb"]
            if free_capacity_gb < (new_disk_gb - old_disk_gb):
                msg = f"""\
Cannot extend the volume {volume_ext_id} of server {server_ext_id} to {new_disk_gb} GB.
No space left on backend host {backend_host} the remaing space is {free_capacity_gb} GB.
"""
                raise Exception(msg)
            vol_v3.extend(volume_ext_id, new_disk_gb)
            task.progress(step_id, msg=f"Extending volume {volume_ext_id}")
            # loop until entity is extended or get error
            while True:
                sleep(5)
                try:
                    status = vol_v3.get(volume_ext_id)["status"]
                except:
                    status = "error"
                if status in ("error", "error_extending"):
                    task.progress(step_id, msg=f"Extend volume {volume_ext_id} - Error")
                    raise Exception(f"Can not extend volume {volume_ext_id}")
                if status in ("in-use", "available"):
                    break
            task.progress(step_id, msg=f"Extended volume {volume_ext_id} - Completed")
            return True

        params["volume"] = task.get_simple_resource(params.get("volume"))
        params["server"] = task.get_simple_resource(params.get("id"))
        res = ServerTask.server_action(
            task,
            step_id,
            extend_volume_action,
            "Extend volume of server",
            "Error extending volume from server",
            params,
            final_status="ORIGINAL",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_add_security_group_step(task, step_id, params, *args, **kvargs):
        """Attach security_group to server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def add_security_group_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            security_group_obj = params["security_group"]
            conn.server.add_security_group(ext_id, security_group_obj.ext_id)
            return True

        params["security_group"] = task.get_resource(params.get("security_group"))
        res = ServerTask.server_action(
            task,
            step_id,
            add_security_group_action,
            "Add security group to server",
            "Error adding security_group to server",
            params,
            final_status="ORIGINAL",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_del_security_group_step(task, step_id, params, *args, **kvargs):
        """Detach security_group from server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def del_security_group_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            security_group_obj = params["security_group"]
            conn.server.remove_security_group(ext_id, security_group_obj.ext_id)
            return True

        params["security_group"] = task.get_resource(params.get("security_group"))
        params["task"] = task
        params["step_id"] = step_id
        res = ServerTask.server_action(
            task,
            step_id,
            del_security_group_action,
            "Detach security group from server",
            "Error detaching security_group from server",
            params,
            final_status="ORIGINAL",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_add_snapshot_step(task, step_id, params, *args, **kvargs):
        """
        Add server snapshot

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.snapshot: the snapshot name
        :return: True, params
        """

        def add_snapshot_action(container, resource, **params):
            conn = container.conn
            server_id = resource.ext_id
            res = conn.server.create_image(server_id, params["snapshot"])
            # The nova image id
            snapshot_ext_id = res["image_id"]
            # loop until nova image is active or in error
            while True:
                inst = conn.image.get(oid=snapshot_ext_id)
                status = inst["status"]
                if status == "active":
                    break
                if status == "error":
                    task.progress(
                        step_id,
                        msg=f"Unable to make snapshot (nova image {snapshot_ext_id}) - Error",
                    )
                    raise Exception(f"Unable to make snapshot (nova image {snapshot_ext_id})")
                sleep(2)

            server_obj = params["server"]
            server_obj.add_snapshot_ext_id(snapshot_ext_id)
            return True

        server = task.get_resource(params.get("id"))
        parent = server.get_parent()
        params["server"] = server
        projectid = parent.oid
        res = ServerTask.server_action(
            task,
            step_id,
            add_snapshot_action,
            "Add server snapshot",
            "Error adding snapshot to server",
            params,
            projectid=projectid,
            final_status="ORIGINAL",
        )
        return res, params

    @staticmethod
    def __wait_for_snapshot(conn, snapshot_id):
        snapshot = conn.volume_v3.group.get_snapshot(snapshot_id)
        status = snapshot.get("status")
        while status not in ["deleted", "error"]:
            sleep(1)
            try:
                snapshot = conn.volume_v3.group.get_snapshot(snapshot_id)
                status = snapshot.get("status")
            except:
                status = "deleted"

        if status == "error":
            raise ApiManagerError(f"snapshot {snapshot_id} can not be deleted")

    @staticmethod
    @task_step()
    def server_del_snapshot_step(task, step_id, params, *args, **kvargs):
        """
        Delete server snapshot

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.snapshot: the snapshot name
        :return: True
        """

        def del_snapshot_action(container, resource, **params):
            conn = container.conn
            server_obj = params["server"]
            # Nova image id
            snapshot_ext_id = params["snapshot"]
            image_res = conn.image.get(oid=snapshot_ext_id)
            block_device_mapping = json.loads(image_res["block_device_mapping"])
            volume_snapshot_ids = [a["snapshot_id"] for a in block_device_mapping]
            for volume_snapshot_id in volume_snapshot_ids:
                conn.volume_v3.snapshot.delete(volume_snapshot_id)
            conn.image.delete(oid=snapshot_ext_id)
            server_obj.del_snapshot_ext_id(snapshot_ext_id)
            return True

        server = task.get_simple_resource(params.get("id"))
        parent = server.get_parent()
        params["server"] = server
        projectid = parent.oid
        res = ServerTask.server_action(
            task,
            step_id,
            del_snapshot_action,
            "Delete server snapshot",
            "Error removing snapshot from server",
            params,
            projectid=projectid,
            final_status="ORIGINAL",
        )
        return res, params

    @staticmethod
    @task_step()
    def server_revert_snapshot_step(task, step_id, params, *args, **kvargs):
        """Revert server to snapshot

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def revert_snapshot_action(container, resource, **params):
            conn = container.conn
            server_obj = params["server"]
            ext_id = server_obj.ext_id

            # stop server
            if server_obj.is_running():
                conn.server.stop(ext_id)

                # loop until action completed or return error
                while True:
                    inst = OpenstackServer.get_remote_server(resource.controller, ext_id, container, ext_id)
                    status = inst["status"]
                    task.progress(step_id, msg=f"Read server {ext_id} status: {status}")
                    if status == "SHUTOFF":
                        break
                    if status == "ERROR":
                        raise Exception(f"Failed to stop server {ext_id}")

                    sleep(2)

                task.progress(step_id, msg="Stop server")

            server_obj.revert_to_snapshot(conn, params["snapshot"])
            snap_param = params["snapshot"]
            task.progress(step_id, msg=f"Revert server to snapshot {snap_param}")

            # start server
            conn.server.start(ext_id)

            # loop until action completed or return error
            while True:
                inst = OpenstackServer.get_remote_server(resource.controller, ext_id, container, ext_id)
                status = inst["status"]
                task.progress(step_id, msg=f"Read server {ext_id} status: {status}")
                if status == "ACTIVE":
                    break
                if status == "ERROR":
                    raise Exception(f"Failed to start server {ext_id}")

                sleep(2)

            task.progress(step_id, msg="Start server")

            return True

        server = task.get_resource(params.get("id"))
        parent = server.get_parent()
        params["server"] = server
        projectid = parent.oid
        res = ServerTask.server_action(
            task,
            step_id,
            revert_snapshot_action,
            "Revert server to snapshot",
            "Error when revert server to snapshot",
            params,
            projectid=projectid,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_restore_from_backup(task, step_id, params, *args, **kvargs):
        """restore server from backup

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def restore_from_backup(container, resource, **params):
            server_obj = params["server"]
            server_name = params["server_name"]

            from beehive_resource.plugins.openstack.controller import OpenstackContainer

            openstack_container: OpenstackContainer = container
            trilio_conn = openstack_container.get_trilio_connection()

            # delete snapshot
            restore = trilio_conn.restore.server(
                params["restore_point"],
                server_obj.ext_id,
                server_name=server_name,
                target_network=None,
                target_subnet=None,
                keep_original_ip=False,
                overwrite=False,
                new_token=None,
            )
            restore_id = restore["id"]
            task.progress(
                step_id,
                msg=f"restore server {server_obj.ext_id} with restore: {restore_id} - START",
            )

            # loop until restore completed or return error
            while True:
                restore = trilio_conn.restore.get(restore_id)
                status = restore["status"]
                task.progress(step_id, msg=f"read restore {restore_id} status: {status}")
                if status == "available":
                    break
                if status == "error":
                    task.progress(step_id, msg=f"restore server {server_obj.ext_id} with restore: {restore_id} - ERROR")
                    raise TaskError(f"failed to restore server {server_obj.ext_id} with restore: {restore_id}")

                sleep(4)

            # get server info
            server_ext_id = dict_get(restore, "instances.0.id")
            project = server_obj.get_parent()
            project_id = project.oid

            # loop until server is running
            while True:
                inst = OpenstackServer.get_remote_server(resource.controller, server_ext_id, container, server_ext_id)
                status = inst["status"]
                task.progress(step_id, msg=f"read server {server_obj.ext_id} status: {status}")
                if status == "ACTIVE":
                    break
                if status == "ERROR":
                    task.progress(step_id, msg=f"failed to start server {server_ext_id}")
                    raise TaskError(f"failed to start server {server_ext_id}")

                sleep(2)

            # create server resource
            objid = f"{project.objid}//{id_gen()}"
            model = container.add_resource(
                objid=objid,
                name=server_name,
                resource_class=OpenstackServer,
                ext_id=server_ext_id,
                active=True,
                desc=server_name,
                attrib={},
                parent=project_id,
            )
            params.update({"id": model.id, "uuid": model.uuid})
            server = OpenstackServer(
                container.controller,
                oid=model.id,
                objid=objid,
                name=server_name,
                desc=server_name,
                active=True,
                model=model,
            )
            server.update_state(ResourceState.ACTIVE)
            task.progress(step_id, msg=f"DATA: server {server}")

            # link volumes to server
            for volume in inst.get("os-extended-volumes:volumes_attached", []):
                volume_ext_id = volume.get("id")
                volume_ext_obj = OpenstackVolume.get_remote_volume(
                    container.controller, volume_ext_id, container, volume_ext_id
                )
                volume_name = volume_ext_obj["name"]
                volume_boot = str2bool(volume_ext_obj["bootable"])
                objid = f"{project.objid}//{id_gen()}"
                model = container.add_resource(
                    objid=objid,
                    name=volume_name,
                    resource_class=OpenstackVolume,
                    ext_id=volume_ext_id,
                    active=True,
                    desc=volume_name,
                    attrib={},
                    parent=project_id,
                )
                volume = OpenstackVolume(
                    container.controller,
                    oid=model.id,
                    objid=objid,
                    name=volume_name,
                    desc=volume_name,
                    active=True,
                    model=model,
                )
                volume.update_state(ResourceState.ACTIVE)
                server.add_link(
                    f"{server.oid}-{model.id}-volume-link",
                    "volume",
                    model.id,
                    attributes={"boot": volume_boot},
                )
                task.progress(step_id, msg=f"Setup volume link from {model.id} to server {server.oid}")

            task.progress(
                step_id,
                msg=f"restore server {server_obj.ext_id} with restore: {restore_id} - STOP",
            )

            return server.oid

        server = task.get_resource(params.get("id"))
        parent = server.get_parent()
        params["server"] = server
        projectid = parent.oid
        res = ServerTask.server_action(
            task,
            step_id,
            restore_from_backup,
            "Restore server from backup",
            "Error restoring server from backup",
            params,
            projectid=projectid,
            final_status="ORIGINAL",
        )
        params["result"] = res
        return res, params


task_manager.tasks.register(ServerTask())
