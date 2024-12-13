# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import task_step, TaskError
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.task_v2.util import VsphereServerHelper, VsphereServerBaseHelper
from beehive_resource.task_v2 import AbstractResourceTask, run_sync_task

logger = getLogger(__name__)


class ServerTask(AbstractResourceTask):
    """Server task"""

    name = "server_task"
    entity_class = VsphereServer

    @staticmethod
    @task_step()
    def create_server_step(task, step_id, params, *args, **kvargs):
        """Create vsphere server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        clone_source_server_oid = params.get("clone_source_oid")
        is_clone = clone_source_server_oid is not None
        cid = params.get("cid")
        oid = params.get("id")
        admin_username = params.get("admin_username")
        admin_password = params.get("adminPass")
        name = params.get("name")
        folder_id = params.get("parent")
        cluster_id = params.get("availability_zone")
        volumes = params.get("block_device_mapping_v2")
        customization_spec_name = params.get("customization_spec_name")
        task.progress(step_id, msg="Get configuration params")

        orchestrator = task.get_container(cid)
        resource = orchestrator.get_resource(oid)
        task.progress(step_id, msg="Get orchestrator %s" % cid)

        helper = VsphereServerBaseHelper(
            task, step_id, orchestrator, params, username=admin_username, password=admin_password
        )

        # get folder
        folder = task.get_resource(folder_id)
        task.progress(step_id, msg="Get parent folder %s" % folder)

        # get cluster
        cluster = task.get_resource(cluster_id)
        task.progress(step_id, msg="Get parent cluster %s" % cluster)

        # volumes index
        volume_idx = []

        # create main volume
        main_volume = volumes.pop(0)
        volume_name = "%s-root-volume" % name
        volume_desc = "Root Volume %s" % name

        source_type = main_volume.get("source_type")
        logger.debug("source_type: %s" % source_type)
        if source_type == "image":
            volume_type = main_volume.get("volume_type")
            image_id = main_volume.get("uuid")
        elif source_type == "volume":
            main_volume_uuid = main_volume.get("uuid")
            logger.debug("main_volume_uuid: %s" % main_volume_uuid)
            volume_obj = task.get_resource(main_volume_uuid)
            volume_type = volume_obj.get_volume_type().oid
            image_id = volume_obj.get_attribs("source_image")
            main_volume["volume_size"] = volume_obj.get_attribs("size")

        main_volume["image_id"] = image_id
        logger.debug("main_volume: %s" % main_volume)

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
        # task.progress(step_id, msg='Create boot volume: %s' % boot_volume_id)

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
            # task.progress(step_id, msg='Create volume: %s' % volume_id)
        volumes.insert(0, main_volume)

        # get networks
        task.get_session(reopen=True)

        # first network
        first_network = next(iter(params.get("networks")), {})
        net_id = first_network.get("uuid")

        network = task.get_resource(net_id)

        # reserve ip address
        helper.reserve_network_ip_address()

        net_attrib = {}
        inst = None
        # clone server from template
        if not is_clone and source_type in ["image", "volume"]:
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
                customization_spec_name=customization_spec_name,
            )
        # clone server from server
        elif is_clone and source_type == "volume":
            # The admin user is set with the template password
            inst = helper.clone_from_server(
                oid,
                clone_source_server_oid,
                name,
                folder,
                volume_type,
                volumes,
                network,
                dest_cluster=cluster,
                source_vm_username=admin_username,
                source_vm_password=admin_password,
            )
        else:
            raise TaskError("Source type %s is not supported" % source_type)
        """
        # clone server from snapshot - linked clone
        elif source_type == 'snapshot':
            inst = helper.linked_clone_from_server(oid, name, folder, volumes, network, resource_pool=None, cluster=cluster)
        """

        # set server disks reference to volumes
        helper.set_volumes_ext_id(inst, volume_idx)
        net_config = first_network.get("fixed_ip", {})
        net_attrib = {"subnet_pool": first_network.get("subnet_pool"), "ip": net_config.get("ip")}

        # set server security groups
        helper.set_security_group(inst)

        # add resource link for network
        orchestrator.add_link(
            name="%s-%s-network-link" % (oid, network.oid),
            type="network",
            start_resource=oid,
            end_resource=network.oid,
            attributes=net_attrib,
        )

        # setup ssh key
        helper.setup_ssh_key(inst)

        # setup ssh password
        helper.setup_ssh_pwd(inst)

        # save current data in shared area
        params["ext_id"] = inst._moId

        return oid, params

    @staticmethod
    @task_step()
    def patch_server_step(task, step_id, params, *args, **kvargs):
        """Patch vsphere server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        task.progress(step_id, msg="Get configuration params")

        orchestrator = task.get_container(cid)
        resource: VsphereServer = orchestrator.get_resource(oid)
        resource.do_patch()

        # folder_id = resource.parent_id
        # task.progress(step_id, msg='Get orchestrator %s' % cid)
        #
        # helper = VsphereServerHelper(task, step_id, orchestrator, params)
        #
        # # get vsphere server disks
        # volumes = orchestrator.conn.server.detail(resource.ext_obj).get('volumes', [])
        # volume_idx = {str(v.get('unit_number')): v for v in volumes}
        #
        # # create volumes
        # for index, volume in volume_idx.items():
        #     volume_type = helper.get_volume_type(volume).oid
        #     if index == '0':
        #         volume_name = '%s-root-volume' % resource.name
        #         volume_desc = 'Root Volume %s' % resource.name
        #         boot = True
        #     else:
        #         volume_name = '%s-other-volume-%s' % (resource.name, index)
        #         volume_desc = 'Volume %s %s' % (resource.name, index)
        #         boot = False
        #     try:
        #         orchestrator.get_resource(volume_name)
        #         task.progress(step_id, msg='Volume %s already linked' % volume_name)
        #         task.logger.warning('Volume %s already linked' % volume_name)
        #     except:
        #         config = {
        #             'source_type': None,
        #             'volume_size': volume.get('size')
        #         }
        #         volume_id = helper.create_volume(volume_name, volume_desc, folder_id, resource, volume_type, config,
        #                                          boot=boot)
        #         task.get_session(reopen=True)
        #         volume_resource = task.get_resource(volume_id)
        #         orchestrator.update_resource(volume_resource.oid, ext_id=index)
        #         volume_resource.set_configs('bootable', boot)
        #         task.progress(step_id, msg='Create volume: %s' % volume_id)

        return oid, params

    @staticmethod
    @task_step()
    def delete_server_step(task, step_id, params, *args, **kvargs):
        """Delete vsphere server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        task.progress(step_id, msg="Get shared area")

        # validate input params
        cid = params.get("cid", None)
        oid = params.get("id", None)
        task.progress(step_id, msg="Get configuration params")

        orchestrator = task.get_container(cid)
        resource = task.get_resource(oid)
        task.progress(step_id, msg="Get orchestrator %s" % cid)

        helper = VsphereServerHelper(task, step_id, orchestrator, params)

        # Release ip address
        helper.release_network_ip_address(resource)

        # get vsphere server
        from beedrones.vsphere.client import VsphereManager
        from pyVmomi import vim

        conn: VsphereManager = orchestrator.conn
        inst: vim.VirtualMachine = conn.server.get_by_morid(resource.ext_id)

        if inst is not None:
            # stop server
            helper.stop(inst)

            # delete server
            helper.delete(resource, inst)

        return oid, params

    @staticmethod
    @task_step()
    def delete_volumes_step(task, step_id, params, *args, **kvargs):
        """Delete vsphere volumes

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        task.progress(step_id, msg="Get configuration params")

        container = task.get_container(cid)
        resource = container.get_resource(oid)
        task.progress(step_id, msg="Get server resource")

        volumes, tot = resource.get_linked_resources(link_type="volume")
        volume_ids = [v.oid for v in volumes]
        task.progress(step_id, msg="Get server volumes: %s" % volume_ids)

        # delete volumes
        for volume_id in volume_ids:
            try:
                resource = task.get_resource(volume_id)

                # delete resource
                resource.expunge_internal()
                task.progress(step_id, msg="Delete volume %s resource" % volume_id)
            except ApiManagerError as ex:
                task.progress(step_id, msg=ex)
                logger.warning(ex)

        return oid, params

    #
    # action
    #
    @staticmethod
    def server_action(task, step_id, action, success, error, params):
        """Execute a server action

        :param task: calery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param params: input params
        :return: ext_id
        :raise:
        """
        task.progress(step_id, msg="start action %s" % action.__name__)
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # execute action
        vs_task = action(conn, cid, oid, ext_id, params)
        if vs_task is not None:
            container.query_remote_task(task, step_id, vs_task, error=error)

        # update cache
        server_obj = task.get_resource(oid)
        server_obj.set_cache()

        task.progress(step_id, msg=success)
        task.progress(step_id, msg="stop action %s" % action.__name__)
        return True

    @staticmethod
    @task_step()
    def server_start_step(task, step_id, params, *args, **kvargs):
        """Start server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def start_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.start(server)
            return task

        def guest_tool_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            conn.server.wait_guest_tools_is_running(server, delta=2, maxtime=180)

        res = ServerTask.server_action(task, step_id, start_action, "Start server", "Error starting server", params)
        ServerTask.server_action(
            task,
            step_id,
            guest_tool_action,
            "Wait server guest tool is running",
            "Error starting server",
            params,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_stop_step(task, step_id, params, *args, **kvargs):
        """Stop server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def stop_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.stop(server)
            return task

        res = ServerTask.server_action(task, step_id, stop_action, "Stop server", "Error stopping server", params)
        return res, params

    @staticmethod
    @task_step()
    def server_reboot_step(task, step_id, params, *args, **kvargs):
        """Reboot server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def reboot_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.reboot(server)
            return task

        def guest_tool_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            conn.server.wait_guest_tools_is_running(server, delta=2, maxtime=180)

        res = ServerTask.server_action(
            task,
            step_id,
            reboot_action,
            "Reboot server",
            "Error rebootting server",
            params,
        )
        ServerTask.server_action(
            task,
            step_id,
            guest_tool_action,
            "Wait server guest tool is running",
            "Error starting server",
            params,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_pause_step(task, step_id, params, *args, **kvargs):
        """Pause server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def pause_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.suspend(server)
            return task

        res = ServerTask.server_action(task, step_id, pause_action, "Pause server", "Error pausing server", params)
        return res, params

    @staticmethod
    @task_step()
    def server_unpause_step(task, step_id, params, *args, **kvargs):
        """Unpause server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def unpause_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.start(server)
            return task

        res = ServerTask.server_action(
            task,
            step_id,
            unpause_action,
            "Unpause server",
            "Error unpausing server",
            params,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_migrate_step(task, step_id, params, *args, **kvargs):
        """Migrate server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def migrate_step_action(conn, cid, oid, ext_id, params):
            live = params.get("live")
            host = params.get("host", None)
            if live is True:
                conn.server.live_migrate(ext_id, host=host)
            else:
                conn.server.migrate(ext_id)
            task = conn.server.migrate(ext_id)
            return task

        res = ServerTask.server_action(
            task,
            step_id,
            migrate_step_action,
            "Migrate server",
            "Error migrating server",
            params,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_set_flavor_step(task, step_id, params, *args, **kvargs):
        """Set flavor to server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def set_flavor_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            flavor_obj = params["flavor"]
            cpu = flavor_obj.get_attribs("vcpus")
            ram = flavor_obj.get_attribs("ram")
            task = conn.server.reconfigure(server, None, memoryMB=ram, numCPUs=cpu)

            return task

        def stop_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            if conn.server.is_running(server) is True:
                task = conn.server.stop(server)
            else:
                task = None
            return task

        def start_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.start(server)
            return task

        def guest_tool_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            conn.server.wait_guest_tools_is_running(server, delta=4, maxtime=600)

        params["flavor"] = task.get_simple_resource(params.get("flavor"))
        ServerTask.server_action(task, step_id, stop_action, "Stop server", "Error stopping server", params)
        res = ServerTask.server_action(
            task,
            step_id,
            set_flavor_action,
            "Set flavor to server",
            "Error setting flavor to server",
            params,
        )
        ServerTask.server_action(task, step_id, start_action, "Start server", "Error starting server", params)
        ServerTask.server_action(
            task,
            step_id,
            guest_tool_action,
            "Wait server guest tool is running",
            "Error starting server",
            params,
        )

        return res, params

    @staticmethod
    @task_step()
    def server_add_volume_step(task, step_id, params, *args, **kvargs):
        """Attach volume to server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def add_volume_action(conn, cid, oid, ext_id, params):
            # get server
            server = conn.server.get_by_morid(ext_id)
            # add new disk for the volume
            disk_unit_number = conn.server.get_available_hard_disk_unit_number(server)

            volume_obj = params["volume"]
            volume_type = volume_obj.get_volume_type()
            volume_size = volume_obj.get_size()
            datastore = volume_type.get_best_datastore(volume_size, tag="default")

            task = conn.server.hardware.add_hard_disk(
                server,
                volume_size,
                datastore.ext_obj,
                disk_unit_number=disk_unit_number,
            )

            # change volume ext_id
            volume_obj.update_internal(ext_id=disk_unit_number)

            # link volume id to server
            server_obj = params["server"]
            server_obj.add_link(
                "%s-%s-volume-link" % (oid, volume_obj.oid),
                "volume",
                volume_obj.oid,
                attributes={"boot": False},
            )

            return task

        # def rescan_scsi_bus(conn, cid, oid, ext_id, params):
        #     # get server
        #     server = conn.server.get_by_morid(ext_id)
        #     pwd = params.get('pwd', None)
        #     task.logger.warning('$$$$$$$$$$$$$$$$$$$$$$$$$$$')
        #     task.logger.warning(pwd)
        #     task.logger.warning('$$$$$$$$$$$$$$$$$$$$$$$$$$$')
        #     if pwd is not None:
        #         conn.server.guest_rescan_scsi_bus(server, 'root', pwd)

        params["volume"] = task.get_resource(params.get("volume"))
        params["server"] = task.get_simple_resource(params.get("id"))
        res = ServerTask.server_action(
            task,
            step_id,
            add_volume_action,
            "Attach volume to server",
            "Error attaching volume to server",
            params,
        )
        # ServerTask.server_action(task, step_id, rescan_scsi_bus, 'rescan scsi bus', 'Error rescanning scsi bus', params)
        return res, params

    @staticmethod
    @task_step()
    def server_del_volume_step(task, step_id, params, *args, **kvargs):
        """Detach volume from server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def del_volume_action(conn, cid, oid, ext_id, params):
            volume_obj = params["volume"]
            volume_extid = volume_obj.ext_id

            # get server
            server = conn.server.get_by_morid(ext_id)

            # add new disk for the volume
            task = conn.server.hardware.delete_hard_disk(server, volume_extid, delete_backing_file=False)

            # change volume ext_id
            volume_obj.update_internal(ext_id="")

            # delete link between volume and server
            server_obj = params["server"]
            server_obj.del_link(volume_obj.oid)

            return task

        params["volume"] = task.get_simple_resource(params.get("volume"))
        params["server"] = task.get_simple_resource(params.get("id"))
        res = ServerTask.server_action(
            task,
            step_id,
            del_volume_action,
            "Detach volume from server",
            "Error detaching volume from server",
            params,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_extend_volume_step(task, step_id, params, *args, **kvargs):
        """Extend volume of server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def extend_volume_action(conn, cid, oid, ext_id, params):
            volume_resource = params["volume"]
            volume_extid = volume_resource.ext_id
            volume_size = int(params["volume_size"])
            # get server
            server = conn.server.get_by_morid(ext_id)
            # extend disk
            ext_task = conn.server.hardware.extend_hard_disk(conn.server, volume_extid, volume_size)
            return ext_task

        params["volume"] = task.get_simple_resource(params.get("volume"))
        params["server"] = task.get_simple_resource(params.get("id"))
        res = ServerTask.server_action(
            task,
            step_id,
            extend_volume_action,
            "Extend volume of server",
            "Error extending volume of server",
            params,
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

        def add_security_group_action(conn, cid, oid, ext_id, params):
            security_group_obj = params["security_group"]
            prepared_task, code = security_group_obj.add_member({"member": oid, "sync": True})
            run_sync_task(prepared_task, params["task"], params["step_id"])

            return None

        params["security_group"] = task.get_resource(params.get("security_group"))
        params["task"] = task
        params["step_id"] = step_id
        res = ServerTask.server_action(
            task,
            step_id,
            add_security_group_action,
            "Add security group to server",
            "Error adding security_group to server",
            params,
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

        def del_security_group_action(conn, cid, oid, ext_id, params):
            security_group_obj = params["security_group"]
            prepared_task, code = security_group_obj.delete_member({"member": oid, "sync": True})
            run_sync_task(prepared_task, params["task"], params["step_id"])

            return None

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
        )
        return res, params

    @staticmethod
    @task_step()
    def server_add_snapshot_step(task, step_id, params, *args, **kvargs):
        """ADd server snapshot

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def add_snapshot_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            vs_task = conn.server.snapshot.create(server, params["snapshot"])
            return vs_task

        res = ServerTask.server_action(
            task,
            step_id,
            add_snapshot_action,
            "Add server snapshot",
            "Error adding snapshot to server",
            params,
        )
        return res, params

    @staticmethod
    @task_step()
    def server_del_snapshot_step(task, step_id, params, *args, **kvargs):
        """Delete server snapshot

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def del_snapshot_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            vs_task = conn.server.snapshot.remove(server, params["snapshot"])
            return vs_task

        res = ServerTask.server_action(
            task,
            step_id,
            del_snapshot_action,
            "Delete server snapshot",
            "Error removing snapshot from server",
            params,
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

        def revert_snapshot_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            vs_task = conn.server.snapshot.revert(server, params["snapshot"])
            hw = conn.server.hardware
            physical_volumes = {v.diskObjectId: v for v in hw.get_hard_disks(server)}
            params["physical_volumes"] = physical_volumes
            return vs_task

        def start_action(conn, cid, oid, ext_id, params):
            server = conn.server.get_by_morid(ext_id)
            task = conn.server.start(server)
            return task

        def align_volumes(conn, cid, oid, ext_id, params):
            server = conn.server
            physical_volumes = params.get("physical_volumes")
            task = params["task"]
            container = task.get_container(cid)
            resource = container.get_resource(oid)
            task = resource.align_resource_volumes(server=server, ext_id=ext_id, physical_volumes=physical_volumes)
            return task

        res = ServerTask.server_action(
            task,
            step_id,
            revert_snapshot_action,
            "Revert server to snapshot",
            "Error when revert server to snapshot",
            params,
        )
        ServerTask.server_action(task, step_id, start_action, "Start server", "Error starting server", params)
        params["task"] = task
        ServerTask.server_action(
            task,
            step_id,
            align_volumes,
            "Align volumes",
            "Error aligning volumes",
            params,
        )
        return res, params
