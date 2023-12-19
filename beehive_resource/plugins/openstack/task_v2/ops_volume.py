# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from time import sleep

from beecell.simple import id_gen, dict_get
from beehive.common.task_v2 import task_step, TaskError
from beehive.common.task_v2.manager import task_manager
from beehive_resource.model import ResourceState
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class VolumeTask(AbstractResourceTask):
    """Volume task"""

    name = "volume_task"
    entity_class = OpenstackVolume

    @staticmethod
    @task_step()
    def volume_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

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
        image = params.get("image")
        project_extid = params.get("project_extid")
        size = params.get("size")
        source_volid = params.get("source_volid", None)
        snapshot_id = params.get("snapshot_id")
        volume_type_id = params.get("volume_type")
        consistencygroup_id = params.get("consistencygroup_id")
        metadata = params.get("metadata")

        # create volume from volume
        if source_volid is not None:
            source_volume = task.get_resource(source_volid)

            # create volume from volume in another container
            if source_volume.container_id != cid:
                # get origin container
                orig_container = task.get_container(source_volume.container_id)

                # get origin volume_type
                # backend = volume_type.get_backend()
                # backend_host = backend['name']
                # origin_backend = orig_container.conn.volume_v3.get_backend_storage_pools(hostname=backend_host)
                # origin_backend_name = dict_get(origin_backend[0], 'capabilities.volume_backend_name')
                #
                # origin_volume_type = orig_container.conn.volume_v3.type.list(backend_name=origin_backend_name)
                # if len(origin_volume_type) != 1:
                #     raise TaskError('no volume type found in container %s for volume type %s' %
                #                     (orig_container.oid, volume_type_id))
                # origin_volume_type_id = origin_volume_type[0]['id']

                # clone volume
                clone_volume = orig_container.conn.volume_v3.clone(name, source_volume.ext_id, project_extid)
                clone_volume_id = clone_volume["id"]
                task.progress(
                    step_id,
                    msg="clone openstack volume %s to %s" % (source_volume.ext_id, clone_volume_id),
                )

                ################
                # retype volume on intermediary volume type
                origin_intermediary_volume_type = orig_container.get_simple_resource("podto2-transito")

                orig_container.conn.volume_v3.change_type(clone_volume_id, origin_intermediary_volume_type.ext_id)
                cond = True
                while cond is True:
                    res = orig_container.conn.volume_v3.get(clone_volume_id)
                    status = res["status"]
                    if status == "available":
                        cond = False
                    elif status == "error":
                        raise TaskError("openstack volume %s change type error" % clone_volume_id)
                    sleep(2)
                task.progress(step_id, msg="retype openstack volume %s" % clone_volume_id)
                ################

                # get cloned volume migration id to use for manage
                clone_volume = orig_container.conn.volume_v3.get(clone_volume_id)
                migrated_clone_volume_id = clone_volume.get("os-vol-mig-status-attr:name_id")

                # # retype volume
                # orig_container.conn.volume_v3.change_type(clone_volume_id, origin_volume_type_id)
                # cond = True
                # while cond is True:
                #     res = orig_container.conn.volume_v3.get(clone_volume_id)
                #     status = res['status']
                #     if status == 'available':
                #         cond = False
                #     elif status == 'error':
                #         raise TaskError('openstack volume %s change type error' % clone_volume_id)
                #     sleep(2)
                # task.progress(step_id, msg='retype openstack volume %s' % clone_volume_id)

                # get destination container
                container = task.get_container(cid, projectid=parent_id)

                # manage volume in server container
                dest_intermediary_volume_type = container.get_resource("podto2-transito")
                backend = dest_intermediary_volume_type.get_backend()
                backend_host = backend["name"]
                final_volume = container.conn.volume_v3.manage(
                    migrated_clone_volume_id,
                    name,
                    dest_intermediary_volume_type.ext_id,
                    bootable=source_volume.is_bootable(),
                    desc=desc,
                    availability_zone="nova",
                    host=backend_host,
                )

                # attach remote volume
                volume_id = final_volume["id"]
                container.update_resource(oid, ext_id=volume_id)
                task.progress(
                    step_id,
                    msg="attach openstack volume %s to volume %s" % (volume_id, oid),
                )

                # loop volume status
                cond = True
                while cond is True:
                    res = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
                    status = res["status"]
                    if status == "available":
                        cond = False
                    elif status == "error":
                        raise TaskError("openstack volume %s change type error" % volume_id)
                    sleep(2)
                task.progress(
                    step_id,
                    msg="manage openstack volume %s on container %s" % (migrated_clone_volume_id, container.oid),
                )

                ################
                # retype volume from dest intermediary volume type
                volume_type = task.get_resource(volume_type_id)
                container.conn.volume_v3.change_type(volume_id, volume_type.ext_id)
                cond = True
                while cond is True:
                    res = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
                    status = res["status"]
                    if status == "available":
                        cond = False
                    elif status == "error":
                        raise TaskError("openstack volume %s change type error" % volume_id)
                    sleep(2)
                task.progress(step_id, msg="retype openstack volume %s" % volume_id)
                ################

                # unmanage volume in original container
                orig_container.conn.volume_v3.unmanage(clone_volume_id)
                task.progress(
                    step_id,
                    msg="unmanage openstack volume %s on container %s" % (clone_volume_id, orig_container.oid),
                )

                # activate volume
                container.update_resource(oid, state=ResourceState.ACTIVE, active=True)
                task.progress(step_id, msg="acvitate volume %s" % volume_id)

            # create volume from volume in the same container
            else:
                # get destination container
                container = task.get_container(cid, projectid=parent_id)
                conn = container.conn

                # get original volume type
                original_volume_type_id = source_volume.get_volume_type().ext_id
                dest_volume_type_id = task.get_simple_resource(volume_type_id).ext_id

                # clone volume
                clone_volume = conn.volume_v3.clone(name, source_volume.ext_id, project_extid)
                clone_volume_id = clone_volume["id"]
                volume_id = clone_volume["id"]
                task.progress(step_id, msg="Create openstack volume %s - Starting" % volume_id)

                # attach remote volume
                container.update_resource(oid, ext_id=volume_id)
                task.progress(
                    step_id,
                    msg="Attach openstack volume %s to volume %s" % (volume_id, oid),
                )

                # retype volume
                if original_volume_type_id != dest_volume_type_id:
                    conn.volume_v3.change_type(clone_volume_id, dest_volume_type_id)

                # loop until entity is not stopped or get error
                while True:
                    inst = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
                    status = inst.get("status", "error")
                    if status == "available":
                        break
                    elif status == "error":
                        task.progress(
                            step_id,
                            msg="Create openstack volume %s - Error" % volume_id,
                        )
                        raise Exception("Can not create openstack volume %s" % volume_id)

                    task.progress(step_id, msg="Create volume %s - Wait" % volume_id)
                    sleep(4)

                task.progress(step_id, msg="Create volume %s - Completed" % volume_id)

                # acvitate volume
                container.update_resource(oid, state=ResourceState.ACTIVE, active=True)
                task.progress(step_id, msg="acvitate volume %s" % volume_id)

        # create volume from image
        else:
            # get destination container
            container = task.get_container(cid, projectid=parent_id)
            conn = container.conn

            volume_type = task.get_resource(volume_type_id)
            volume_ext = conn.volume_v3.create(
                size=int(size),
                availability_zone=availability_zone,
                source_volid=source_volid,
                description=desc,
                multiattach=False,
                snapshot_id=snapshot_id,
                name=name,
                imageRef=image,
                volume_type=volume_type.ext_id,
                metadata=metadata,
                source_replica=None,
                consistencygroup_id=consistencygroup_id,
                scheduler_hints=None,
                tenant_id=project_extid,
            )

            volume_id = volume_ext["id"]
            task.progress(step_id, msg="Create openstack volume %s - Starting" % volume_id)

            # attach remote volume
            container.update_resource(oid, ext_id=volume_id)
            task.progress(
                step_id,
                msg="Attach openstack volume %s to volume %s" % (volume_id, oid),
            )

            # loop until entity is not stopped or get error
            while True:
                inst = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
                status = inst.get("status", "error")
                if status == "available":
                    break
                elif status == "error":
                    task.progress(step_id, msg="Create openstack volume %s - Error" % volume_id)
                    raise Exception("Can not create openstack volume %s" % volume_id)

                task.progress(step_id, msg="Create volume %s - Wait" % volume_id)
                sleep(4)

            task.progress(step_id, msg="Create volume %s - Completed" % volume_id)

            # acvitate volume
            container.update_resource(oid, state=ResourceState.ACTIVE, active=True)
            task.progress(step_id, msg="Acvitate volume %s" % volume_id)

        # save current data in shared area
        params["ext_id"] = volume_id

        return oid, params

    @staticmethod
    @task_step()
    def volume_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def volume_expunge_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")
        ext_id = params.get("ext_id")
        parent_id = params.get("parent_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        # delete vsphere folder
        if resource.is_ext_id_valid() is True:
            # check volume exists
            rv = OpenstackVolume.get_remote_volume(container.controller, ext_id, container, ext_id)
            if rv is None or rv == {}:
                task.progress(step_id, msg="Volume %s does not exist anymore" % ext_id)
                return oid, params

            # remote volume snapshots
            snapshots = container.conn.volume_v3.snapshot.list(volume_id=ext_id)
            for snapshot in snapshots:
                container.conn.volume_v3.snapshot.delete(snapshot["id"])
                while True:
                    try:
                        container.conn.volume_v3.snapshot.get(snapshot["id"])
                        sleep(2)
                    except:
                        task.progress(
                            step_id,
                            msg="Volume %s snapshot %s deleted" % (ext_id, snapshot["id"]),
                        )
                        break

            # remove volume
            conn.volume_v3.reset_status(ext_id, "available", "detached", "success")
            conn.volume_v3.delete(ext_id)
            task.progress(step_id, msg="Delete volume %s - Starting" % ext_id)

            # loop until entity is not deleted or get error
            while True:
                try:
                    inst = OpenstackVolume.get_remote_volume(container.controller, ext_id, container, ext_id)
                    if inst == {}:
                        task.progress(step_id, msg="Volume does not exist anymore")
                        raise Exception("Volume does not exist anymore")
                    status = inst["status"]
                    task.progress(step_id, msg="Volume %s status: %s" % (ext_id, status))
                    if status == "error_deleting":
                        task.progress(step_id, msg="Delete volume %s - Error" % ext_id)
                        raise Exception("Can not delete volume %s" % ext_id)
                    elif status == "error":
                        task.progress(step_id, msg="delete volume %s - Error" % ext_id)
                        raise Exception("Can not delete volume %s" % ext_id)

                    task.progress(step_id, msg="Delete volume %s - Wait" % ext_id)
                    sleep(4)
                except:
                    # volume does not exists anymore
                    break

            resource.update_internal(ext_id=None)
            task.progress(step_id, msg="Delete volume %s - Completed" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def volume_clone_step(task, step_id, params, *args, **kvargs):
        """Clone volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.name: cloned volume name
        :param params.project: cloned volume project
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        volume_ext_id = params.get("ext_id")
        cloned_name = params.get("cloned_name")
        parent_id = params.get("parent_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn

        project = task.get_simple_resource(parent_id)

        # clone volume
        volume_ext = conn.volume_v3.clone(cloned_name, volume_ext_id, project.ext_id)
        volume_ext_id = volume_ext["id"]
        task.progress(step_id, msg="Create openstack volume %s - Starting" % volume_ext_id)

        # create resource
        resource_params = {
            "resource_class": OpenstackVolume,
            "name": cloned_name,
            "desc": cloned_name,
            "objid": "%s//%s" % (project.objid, id_gen()),
            "parent": parent_id,
            "ext_id": volume_ext_id,
            "active": False,
            "attrib": {},
            "tags": [],
        }
        model = container.add_resource(**resource_params)
        task.progress(step_id, msg="Create resource %s for volume %s" % (model.id, volume_ext_id))

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackVolume.get_remote_volume(container.controller, volume_ext_id, container, volume_ext_id)
            status = inst.get("status", "error")
            if status == "available":
                break
            elif status == "error":
                task.progress(step_id, msg="Create openstack volume %s - Error" % volume_ext_id)
                raise Exception("Can not create openstack volume %s" % volume_ext_id)

            task.progress(step_id, msg="Create volume %s - Wait" % volume_ext_id)
            sleep(4)

        task.progress(step_id, msg="Create volume %s - Completed" % volume_ext_id)

        # acvitate volume
        container.update_resource(model.id, state=ResourceState.ACTIVE, active=True)
        task.progress(step_id, msg="Acvitate volume resource %s" % model.id)

        return model.id, params

    @staticmethod
    def volume_action(
        task,
        step_id,
        action,
        success,
        error,
        params,
        final_status="ACTIVE",
        projectid=None,
    ):
        """Execute a volume action

        :param task: calery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param final_status: final status that volume must raise. If ORIGINAL final status must be the original status
            [default=ACTIVE]
        :param params: input params
        :param projectid: projectid [optional]
        :return: action response
        :raise:
        """
        task.progress(step_id, msg="start action %s" % action.__name__)
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        # container = task.get_container(cid)
        container = task.get_container(cid, projectid=projectid)
        resource = task.get_simple_resource(oid)

        # get original state
        if final_status == "ORIGINAL":
            inst = OpenstackVolume.get_remote_volume(resource.controller, ext_id, container, ext_id)
            final_status = inst["status"]

        # execute action
        res = action(container, resource, **params)

        # loop until action completed or return error
        while True:
            inst = OpenstackVolume.get_remote_volume(resource.controller, ext_id, container, ext_id)
            status = inst["status"]
            task.progress(step_id, msg="Read volume %s status: %s" % (ext_id, status))
            if status == final_status:
                break
            elif status == "ERROR":
                raise Exception(error)

            sleep(5)

        task.progress(step_id, msg=success)
        task.progress(step_id, msg="stop action %s" % action.__name__)

        return res

    @staticmethod
    @task_step()
    def volume_set_flavor_step(task, step_id, params, *args, **kvargs):
        """Set flavor to volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        def set_flavor_action(container, resource, **params):
            conn = container.conn
            ext_id = resource.ext_id
            flavor = params.get("flavor")
            conn.volume.change_type(ext_id, flavor)
            return True

        res = VolumeTask.volume_action(
            task,
            step_id,
            set_flavor_action,
            "Set flavor to volume",
            "Error setting flavor to volume",
            params,
            final_status="ORIGINAL",
        )
        return res, params


task_manager.tasks.register(VolumeTask())
