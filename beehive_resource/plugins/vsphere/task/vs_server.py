# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

import gevent
from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import ResourceJobTask, ApiManagerError
from beehive.common.task.job import job_task, JobError
from beehive_resource.plugins.vsphere.task.util import VsphereServerHelper

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_server(self, options):
    """Create vsphere server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.objid: resource objid
    :param sharedarea.parent: resource parent id
    :param sharedarea.cid: container id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.ext_id: resource ext_id
    :param sharedarea.active: resource active
    :param sharedarea.attribute:: attributes
    :param sharedarea.tags: comma separated resource tags to assign [default='']
    :param sharedarea.accessIPv4: IPv4 address that should be used to access this server. [optional] [TODO]
    :param sharedarea.accessIPv6: IPv6 address that should be used to access this server. [optional] [TODO]
    :param sharedarea.flavorRef: server cpu, ram and operating system
    :param sharedarea.adminPass: The administrative password of the server. [TODO]
    :param sharedarea.availability_zone: Specify the availability zone
    :param sharedarea.metadata: server metadata
    :param sharedarea.metadata.admin_pwd: root admin password used for guest customization
    :param sharedarea.security_groups: One or more security groups.
    :param sharedarea.networks: A networks object. Required parameter when there are multiple networks defined for the
            tenant. When you do not specify the networks parameter, the server attaches to the only network created
            for the current tenant. Optionally, you can create one or more NICs on the server. To provision the
            server instance with a NIC for a network, specify the UUID of the network in the uuid attribute in a
            networks object. [TODO: support for multiple network]
    :param sharedarea.networks.x.uuid: is the id a tenant network.
    :param sharedarea.networks.x.subnet_pool: is the id a tenant network subnet.
    :param sharedarea.networks.x.fixed_ip: the network configuration. For static ip pass some fields
    :param sharedarea.networks.x.fixed_ip.ip:
    :param sharedarea.networks.x.fixed_ip.gw:
    :param sharedarea.networks.x.fixed_ip.hostname:
    :param sharedarea.networks.x.fixed_ip.dns:
    :param sharedarea.networks.x.fixed_ip.dnsname:
    :param sharedarea.user_data:  Configuration information or scripts to use upon launch. Must be Base64 encoded.
        [optional] Pass ssh_key using base64.b64decode({'pubkey':..})
    :param sharedarea.personality: The file path and contents, text only, to inject into the server at launch.
        The maximum size of the file path data is 255 bytes. The maximum limit is The number of allowed bytes in the
        decoded, rather than encoded, data. [optional] [TODO]
    :param sharedarea.block_device_mapping_v2: Enables fine grained control of the block device mapping for an instance.
    :param sharedarea.block_device_mapping_v2.device_name: A path to the device for the volume that you want to use to
        boot the server. [TODO]
    :param sharedarea.block_device_mapping_v2.source_type: The source type of the volume. A valid value is:
        snapshot - creates a volume backed by the given volume snapshot referenced via the
                   block_device_mapping_v2.uuid parameter and attaches it to the server
        volume: uses the existing persistent volume referenced via the block_device_mapping_v2.uuid parameter
                and attaches it to the server
        image: creates an image-backed volume in the block storage service and attaches it to the server
    :param sharedarea.block_device_mapping_v2.volume_size: size of volume in GB
    :param sharedarea.block_device_mapping_v2.uuid: This is the uuid of source resource. The uuid points to different
        resources based on the source_type.
        If source_type is image, the block device is created based on the specified image which is retrieved
        from the image service.
        If source_type is snapshot then the uuid refers to a volume snapshot in the block storage service.
        If source_type is volume then the uuid refers to a volume in the block storage service.
    :param sharedarea.block_device_mapping_v2.volume_type: The device volume_type. This can be used to specify the type
        of volume which the compute service will create and attach to the server. If not specified, the block
        storage service will provide a default volume type. It is only supported with source_type of image or
        snapshot.
    :param sharedarea.block_device_mapping_v2.destination_type: Defines where the volume comes from. A valid value is
        local or volume. [default=volume]
    :param sharedarea.block_device_mapping_v2.delete_on_termination: To delete the boot volume when the server is
        destroyed, specify true. Otherwise, specify false. [TODO]
    :param sharedarea.block_device_mapping_v2.guest_format: Specifies the guest server disk file system format, such as
        ephemeral or swap. [TODO]
    :param sharedarea.block_device_mapping_v2.boot_index: Defines the order in which a hypervisor tries devices when it
        attempts to boot the guest from storage. Give each device a unique boot index starting from 0. To
        disable a device from booting, set the boot index to a negative value or use the default boot index
        value, which is None. The simplest usage is, set the boot index of the boot device to 0 and use the
        default boot index value, None, for any other devices. Some hypervisors might not support booting from
        multiple devices; these hypervisors consider only the device with a boot index of 0. Some hypervisors
        support booting from multiple devices but only if the devices are of different types. For example, a
        disk and CD-ROM. [TODO]
    :param sharedarea.block_device_mapping_v2.tag: An arbitrary tag. [TODO]
    :return: server physical id, root volume physical id
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    name = params.get("name")
    folder_id = params.get("parent")
    # resource_pool_id = params.get('availability_zone')
    cluster_id = params.get("availability_zone")
    volumes = params.get("block_device_mapping_v2")
    self.progress("Get configuration params")

    # get orchestrator
    self.get_session()
    orchestrator = self.get_container(cid)
    resource = orchestrator.get_resource(oid)
    self.progress("Get orchestrator %s" % cid)

    helper = VsphereServerHelper(self, orchestrator, params)

    # get folder
    folder = self.get_resource_with_detail(folder_id)
    self.progress("Get parent folder %s" % folder)

    # get cluster
    cluster = self.get_resource_with_detail(cluster_id)
    self.progress("Get parent cluster %s" % cluster)

    # volumes index
    volume_idx = []

    # create main volume
    main_volume = volumes.pop(0)
    volume_name = "%s-root-volume" % name
    volume_desc = "Root Volume %s" % name
    source_type = main_volume.get("source_type")
    if source_type == "image":
        volume_type = main_volume.get("volume_type")
        image_id = main_volume.get("uuid")
    elif source_type == "volume":
        volume_obj = self.get_resource(main_volume.get("uuid"))
        volume_type = volume_obj.get_volume_type().oid
        image_id = volume_obj.get_attribs("source_image")
        main_volume["volume_size"] = volume_obj.get_attribs("size")

    main_volume["image_id"] = image_id
    boot_volume_id = helper.create_volume(
        volume_name,
        volume_desc,
        folder_id,
        resource,
        volume_type,
        main_volume,
        boot=True,
    )
    volume_idx.append(boot_volume_id)
    self.progress("Create boot volume: %s" % boot_volume_id)

    # create other volumes
    index = 0
    for volume in volumes:
        index += 1
        volume_name = "%s-other-volume-%s" % (name, index)
        volume_desc = "Volume %s %s" % (name, index)
        volume_id = helper.create_volume(
            volume_name,
            volume_desc,
            folder_id,
            resource,
            volume_type,
            volume,
            boot=False,
        )
        volume_idx.append(volume_id)
        self.progress("Create volume: %s" % volume_id)
    volumes.insert(0, main_volume)

    # get networks
    self.get_session(reopen=True)
    net_id = params.get("networks")[0]["uuid"]
    network = self.get_resource_with_detail(net_id)

    # reserve ip address
    helper.reserve_network_ip_address()

    # clone server from template
    if source_type in ["image", "volume"]:
        # create server
        inst = helper.clone_from_template(
            oid,
            name,
            folder,
            volume_type,
            volumes,
            network,
            resource_pool=None,
            cluster=cluster,
        )

        # set server disks reference to volumes
        helper.set_volumes_ext_id(inst, volume_idx)

    # # clone server from snapshot - linked clone
    # elif source_type == 'snapshot':
    #     inst = helper.linked_clone_from_server(oid, name, folder, volumes, network, resource_pool=None,
    #     cluster=cluster)
    #
    # # create new server
    # elif source_type == 'volume':
    #     inst = helper.create_new(oid, name, folder, volumes, network, resource_pool=None, cluster=cluster)

    else:
        raise JobError("Source type %s is not supported" % source_type)

    # # update resource
    # self.release_session()
    # self.get_session()
    # resource = self.get_resource(oid, details=False)
    # resource.update_internal(ext_id=inst._moId)
    # update resource
    # orchestrator.update_resource(oid, ext_id=inst._moId)

    # set server security groups
    helper.set_security_group(inst)

    # start server
    # helper.start(inst)

    # set network interface ip
    net_info = helper.setup_network(inst)
    # [{'uuid': networks[0].get('uuid'), 'ip': config.get('ip')}]
    attrib = {"subnet_pool": net_info[0]["subnet_pool"], "ip": net_info[0]["ip"]}
    orchestrator.add_link(
        name="%s-%s-network-link" % (oid, network.oid),
        type="network",
        start_resource=oid,
        end_resource=network.oid,
        attributes=attrib,
    )

    # setup ssh key
    helper.setup_ssh_key(inst)

    # setup ssh password
    helper.setup_ssh_pwd(inst)

    # check server is up and configured
    # helper.check_server_up_and_configured(inst)

    # reboot server if so is windows
    # helper.reboot_windows_server(inst)

    # save current data in shared area
    params["ext_id"] = inst._moId
    self.set_shared_data(params)
    self.progress("Update shared area")

    return inst._moId


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_patch_server(self, options):
    """Patch vsphere server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.objid: resource objid
    :param sharedarea.parent: resource parent id
    :param sharedarea.cid: container id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.ext_id: resource ext_id
    :param sharedarea.active: resource active
    :param sharedarea.attribute:: attributes
    :param sharedarea.volume_type:: volume_type
    :param sharedarea.image_id:: image_id
    :return: server physical id, root volume physical id
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    # volume_type = params.get('volume_type')
    # image_id = params.get('image_id')
    self.progress("Get configuration params")

    # get orchestrator
    self.get_session()
    orchestrator = self.get_container(cid)
    resource = orchestrator.get_resource(oid)
    folder_id = resource.parent_id
    self.progress("Get orchestrator %s" % cid)

    helper = VsphereServerHelper(self, orchestrator, params)

    # get vsphere server disks
    volumes = orchestrator.conn.server.detail(resource.ext_obj).get("volumes", [])
    volume_idx = {str(v.get("unit_number")): v for v in volumes}

    # create volumes
    for index, volume in volume_idx.items():
        volume_type = helper.get_volume_type(volume).oid
        if index == "0":
            volume_name = "%s-root-volume" % resource.name
            volume_desc = "Root Volume %s" % resource.name
            boot = True
        else:
            volume_name = "%s-other-volume-%s" % (resource.name, index)
            volume_desc = "Volume %s %s" % (resource.name, index)
            boot = False
        try:
            self.get_resource(volume_name)
            self.progress("Volume %s already linked" % volume_name)
            self.logger.warn("Volume %s already linked" % volume_name)
        except:
            config = {"source_type": None, "volume_size": volume.get("size")}
            volume_id = helper.create_volume(
                volume_name,
                volume_desc,
                folder_id,
                resource,
                volume_type,
                config,
                boot=boot,
            )
            self.get_session(reopen=True)
            volume_resource = self.get_resource(volume_id)
            orchestrator.update_resource(volume_resource.oid, ext_id=index)
            volume_resource.set_configs("bootable", boot)
            self.progress("Create volume: %s" % volume_id)

    return resource.ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_server(self, options):
    """Delete vsphere server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.volume_ext_id: boot volume physical id
    :param sharedarea.parent_id: parent id
    :param sharedarea.all: If True delete all the server attached volumes. If False delete only boot volume
    :return: server physical id, [volume physical id, ..]
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid", None)
    oid = params.get("id", None)
    self.progress("Get configuration params")

    # get server resource
    self.get_session()
    orchestrator = self.get_container(cid)
    resource = self.get_resource_with_detail(oid)
    self.progress("Get orchestrator %s" % cid)

    helper = VsphereServerHelper(self, orchestrator, params)

    # get vsphere server
    conn = orchestrator.conn
    inst = conn.server.get_by_morid(resource.ext_id)

    if inst is not None:
        # stop server
        helper.stop(inst)

        # delete server
        helper.delete(resource, inst)

    # update params
    params["oid"] = oid

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_volumes(self, options):
    """Remove server volumes

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :return: uuid of the removed resource
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    self.progress("Get configuration params")

    # get server resource
    self.get_session()
    container = self.get_container(cid)
    resource = container.get_resource(oid)
    self.progress("Get server resource")

    volumes, tot = resource.get_linked_resources(link_type="volume")
    volume_ids = [v.oid for v in volumes]
    self.progress("Get server volumes: %s" % volume_ids)

    # delete volumes
    for volume_id in volume_ids:
        try:
            resource = self.get_resource(volume_id)

            # delete resource
            resource.expunge_internal()
            self.progress("Delete volume %s resource" % volume_id)
        except ApiManagerError as ex:
            self.progress(ex)
            logger.warn(ex)


#
# action
#
def server_action(task, action, success, error):
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
    conn = container.conn
    task.progress("Get container %s" % cid)

    # execute action
    vs_task = action(conn, cid, oid, ext_id, **params)
    if vs_task is not None:
        container.query_remote_task(task, vs_task, error=error)

    # # loop until action completed or return error
    # while True:
    #     inst = container.conn.server.get(oid=ext_id)
    #     status = inst['status']
    #     task.progress('Read server %s status: %s' % (ext_id, status))
    #     if status == final_status:
    #         break
    #     elif status == 'ERROR':
    #         raise Exception(error)
    #
    #     gevent.sleep(task_local.delta)

    task.progress(success)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_start(self, options):
    """Start server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        task = conn.server.start(server)
        return task

    def guest_tool_action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        conn.server.wait_guest_tools_is_running(server, delta=2, maxtime=180, sleep=gevent.sleep)

    res = server_action(self, action, "Start server", "Error starting server")
    server_action(
        self,
        guest_tool_action,
        "Wait server guest tool is running",
        "Error starting server",
    )
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_stop(self, options):
    """Stop server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        task = conn.server.stop(server)
        return task

    res = server_action(self, action, "Stop server", "Error stopping server")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_reboot(self, options):
    """Reboot server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        task = conn.server.reboot(server)
        return task

    res = server_action(self, action, "Reboot server", "Error rebootting server")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_pause(self, options):
    """Pause server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        task = conn.server.suspend(server)
        return task

    res = server_action(self, action, "Pause server", "Error pausing server")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_unpause(self, options):
    """Unpause server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :return: True
    """

    def action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        task = conn.server.start(server)
        return task

    res = server_action(self, action, "Unpause server", "Error unpausing server")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_migrate(self, options):
    """Migrate server TODO

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.live** (bool): if True run live migration
    :param sharedarea.host: physical server where migrate [optional]
    :return: True
    """

    def action(conn, cid, oid, ext_id, **params):
        live = params.get("live")
        host = params.get("host", None)
        if live is True:
            conn.server.live_migrate(ext_id, host=host)
        else:
            conn.server.migrate(ext_id)
        task = conn.server.migrate(ext_id)
        return task

    res = server_action(self, action, "Migrate server", "Error migrating server")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_set_flavor(self, options):
    """Set flavor to server todo

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.flavor: flavor id
    :return: True
    """

    def set_flavor_action(conn, cid, oid, ext_id, flavor=None, **params):
        server = conn.server.get_by_morid(ext_id)
        flavor_obj = self.get_resource(flavor)
        cpu = flavor_obj.get_attribs("vcpus")
        ram = flavor_obj.get_attribs("ram")
        task = conn.server.reconfigure(server, None, memoryMB=ram, numCPUs=cpu)

        return task

    def stop_action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        if conn.server.is_running(server) is True:
            task = conn.server.stop(server)
        else:
            task = None
        return task

    def start_action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        task = conn.server.start(server)
        return task

    def guest_tool_action(conn, cid, oid, ext_id, **params):
        server = conn.server.get_by_morid(ext_id)
        conn.server.wait_guest_tools_is_running(server, delta=2, maxtime=180, sleep=gevent.sleep)

    server_action(self, stop_action, "Stop server", "Error stopping server")
    res = server_action(
        self,
        set_flavor_action,
        "Set flavor to server",
        "Error setting flavor to server",
    )
    server_action(self, start_action, "Start server", "Error starting server")
    server_action(
        self,
        guest_tool_action,
        "Wait server guest tool is running",
        "Error starting server",
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
    :param sharedarea.volume: volume id
    :return: True
    """

    def action(conn, cid, oid, ext_id, volume=None, **params):
        # get volume
        volume_obj = self.get_resource(volume)
        volume_type = volume_obj.get_volume_type()
        volume_size = volume_obj.get_size()
        datastore = volume_type.get_best_datastore(volume_size, tag="default")

        # get server
        server = conn.server.get_by_morid(ext_id)

        # add new disk for the volume
        disk_unit_number = conn.server.get_available_hard_disk_unit_number(server)
        task = conn.server.hardware.add_hard_disk(
            server, volume_size, datastore.ext_obj, disk_unit_number=disk_unit_number
        )

        # change volume ext_id
        volume_obj.update_internal(ext_id=disk_unit_number)

        # link volume id to server
        server_obj = self.get_resource(oid)
        server_obj.add_link(
            "%s-%s-volume-link" % (oid, volume_obj.oid),
            "volume",
            volume_obj.oid,
            attributes={"boot": False},
        )

        return task

    res = server_action(self, action, "Attach volume to server", "Error attaching volume to server")
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_server_del_volume(self, options):
    """Detach volume from server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.ext_id: remote entity id
    :param sharedarea.volume_extid: physical id of the volume
    :return: True
    """

    def action(conn, cid, oid, ext_id, volume=None, **params):
        # get volume
        volume_obj = self.get_resource(volume)
        volume_extid = int(volume_obj.ext_id) + 1

        # get server
        server = conn.server.get_by_morid(ext_id)

        # delete disk for the volume
        task = conn.server.hardware.delete_hard_disk(server, volume_extid)

        # change volume ext_id
        volume_obj.update_internal(ext_id="")

        # delete link between volume and server
        server_obj = self.get_resource(oid)
        server_obj.del_link(volume_obj.oid)

        return task

    res = server_action(self, action, "Detach volume from server", "Error detaching volume from server")
    return res
