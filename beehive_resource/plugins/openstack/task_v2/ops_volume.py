# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from time import sleep
from typing import TYPE_CHECKING

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, TaskError
from beehive.common.task_v2.manager import task_manager
from beehive_resource.model import ResourceState
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.task_v2 import AbstractResourceTask

if TYPE_CHECKING:
    from beedrones.openstack.client import OpenstackManager
    from beehive_resource.plugins.openstack.controller import OpenstackContainer

logger = getLogger(__name__)


class VolumeTask(AbstractResourceTask):
    """
    Volume Celery task.
    """

    name = "volume_task"
    entity_class = OpenstackVolume

    @staticmethod
    def poll_volume_status(
        task,
        step_id,
        container,
        volume_id,
        action,
        polling_freq=20,
        success_states=("available"),
        error_states=("error"),
    ):
        """
        Poll the status of a volume until it becomes in success_states or error_states.

        :param task: Celery task Instance.
        :param str step_id: step id.
        :param OpenstackContainer container: Container managing the volume.
        :param str volume_id: ID of the volume to poll.
        :param str action: human readable action name used for logging.
        :param int polling_freq: Frequency (in seconds) of polling [default=20].
        :param tuple success_states: success states for exiting polling [default=("available")].
        :param tuple error_states: error states for exiting polling [fefault=("error")].
        :raises TaskError: If the volume encounters an error.
        """
        task.progress(step_id, msg=action)
        while True:
            inst = OpenstackVolume.get_remote_volume(
                container.controller,
                volume_id,
                container,
                volume_id,
                callbackRenewToken=task.renew_container_token,
                container_oid=container.oid,
                projectid=container.conn_params["api"]["project"],
            )
            status = inst.get("status")
            # If status is None reloop because in creation at the first step the volume
            # sometimes does not exist.
            if status is not None and status in success_states:
                break
            if status is not None and status in error_states:
                task.progress(step_id, msg=f"{action} {volume_id} - Error")
                raise Exception(f"Cannot {action.lower()} openstack volume {volume_id}")
            task.progress(step_id, msg=f"{action} {volume_id} - Wait")
            sleep(polling_freq)
        task.progress(step_id, msg=f"{action} {volume_id} - Completed")

    @staticmethod
    def change_volume_type(task, step_id, container, volume_id, new_type_id):
        """
        Change the type of a volume and wait for the operation to complete.

        :param task: Celery task Instance.
        :param str step_id: step id.
        :param OpenstackContainer container: Container managing the volume.
        :param str volume_id: ID of the volume to retype.
        :param str new_type_id: ID of the new volume type.
        """
        # Wait for the precondition to retype volume
        VolumeTask.poll_volume_status(
            task,
            step_id,
            container,
            volume_id,
            "pre change volume type",
            success_states=("available", "in-use"),
            polling_freq=2,
        )
        container.conn.volume_v3.change_type(volume_id, new_type_id)
        action = f"Changing type of OpenStack volume {volume_id} to {new_type_id}"
        # wait to complete
        VolumeTask.poll_volume_status(
            task, step_id, container, volume_id, action, success_states=("available", "in-use")
        )

    @staticmethod
    def manage_volume(task, step_id, params, source_volume, cid, parent_id, volume_type_id, name, desc, project_extid):
        """
        Handle the migration and management of a volume across different containers.

        This involves cloning, retyping, and managing a source volume into a new
        container or environment.

        :param task: Celery task Instance.
        :param str step_id: Unique identifier for the current step.
        :param source_volume: The source volume object to be managed.
        :param str cid: ID of the destination container.
        :param str parent_id: Parent resource ID of the destination container.
        :param str volume_type_id: ID of the final volume type.
        :param str name: Name of the new volume.
        :param str desc: Description of the new volume.
        :param str project_extid: Project external ID.
        :return: ID of the managed volume.
        """
        # get origin container
        orig_container: OpenstackContainer = task.get_container(source_volume.container_id)
        openstack_manager: OpenstackManager = orig_container.conn

        # This is the resource in the db with volume type share between different pods.
        pod_transit = "podto2-transito"

        # Clone the source volume.
        clone_volume = openstack_manager.volume_v3.clone(name, source_volume.ext_id, project_extid)
        clone_volume_id = clone_volume["id"]
        task.progress(step_id, msg=f"Cloned OpenStack volume {source_volume.ext_id} to {clone_volume_id}")

        # Change to the temporary volume type shared between pods.
        temporary_vol_type = orig_container.get_simple_resource(pod_transit)
        VolumeTask.change_volume_type(task, step_id, orig_container, clone_volume_id, temporary_vol_type.ext_id)

        # Get the migration ID for the clone.
        clone_volume = orig_container.conn.volume_v3.get(clone_volume_id)
        migrated_clone_volume_id = clone_volume.get("os-vol-mig-status-attr:name_id")

        # Manage volume in destination container.
        dest_container = task.get_container(cid, projectid=parent_id)
        dest_temporary_volume_type = dest_container.get_resource(pod_transit)
        backend = dest_temporary_volume_type.get_backend()

        final_volume = dest_container.conn.volume_v3.manage(
            migrated_clone_volume_id,
            name,
            dest_temporary_volume_type.ext_id,
            bootable=source_volume.is_bootable(),
            desc=desc,
            host=backend["name"],
        )
        volume_id = final_volume["id"]

        # Attach and activate volume.
        dest_container.update_resource(params["id"], ext_id=volume_id)
        VolumeTask.poll_volume_status(task, step_id, dest_container, volume_id, "manage and activate volume")
        dest_container.update_resource(params["id"], state=ResourceState.ACTIVE, active=True)
        task.progress(step_id, msg=f"Volume {volume_id} successfully managed and activated.")
        final_vol_type = dest_container.get_resource(volume_type_id)

        # Change to the final volume type.
        VolumeTask.change_volume_type(task, step_id, dest_container, volume_id, final_vol_type.ext_id)

        # Unmanage the original clone.
        orig_container.conn.volume_v3.unmanage(
            clone_volume_id,
            callbackRenewToken=task.renew_container_token,
            container_oid=orig_container.oid,
            projectid=orig_container.conn_params["api"]["project"],
        )
        task.progress(step_id, msg=f"Unmanaged OpenStack volume {clone_volume_id} from container {orig_container.oid}")
        return volume_id

    @staticmethod
    @task_step()
    def volume_create_physical_step(task, step_id, params, *args, **kvargs):
        """
        Create physical resource.

        :param task: Celery task Instance.
        :param str step_id: step id.
        :param dict params: step params.
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

        if source_volid is not None:
            # Create volume from existing volume.
            source_volume = task.get_resource(source_volid)
            if source_volume.container_id != cid:
                # Create volume from a source volume in another container.
                volume_id = VolumeTask.manage_volume(
                    task, step_id, params, source_volume, cid, parent_id, volume_type_id, name, desc, project_extid
                )
            else:
                # Create volume from a source volume in the same container.
                container = task.get_container(cid, projectid=parent_id)
                clone_volume = container.conn.volume_v3.clone(name, source_volume.ext_id, project_extid)
                volume_id = clone_volume["id"]
                # Attach and retype the volume.
                container.update_resource(oid, ext_id=volume_id)
                VolumeTask.poll_volume_status(task, step_id, container, volume_id, "clone volume")
                type_id = container.get_simple_resource(volume_type_id).ext_id
                # Get original volume type.
                original_volume_type_id = source_volume.get_volume_type().ext_id
                dest_volume_type_id = task.get_simple_resource(volume_type_id).ext_id
                if original_volume_type_id != dest_volume_type_id:
                    VolumeTask.change_volume_type(task, step_id, container, volume_id, type_id)
        else:
            # Create volume from image or other
            container = task.get_container(cid, projectid=parent_id)
            volume_type = task.get_resource(volume_type_id)
            volume_ext = container.conn.volume_v3.create(
                size=int(size),
                availability_zone=availability_zone,
                snapshot_id=snapshot_id,
                name=name,
                imageRef=image,
                volume_type=volume_type.ext_id,
                metadata=metadata,
                consistencygroup_id=consistencygroup_id,
                tenant_id=project_extid,
                description=desc,
            )
            volume_id = volume_ext["id"]
            VolumeTask.poll_volume_status(task, step_id, container, volume_id, "create volume")
            # Attach and activate volume.
            container.update_resource(oid, ext_id=volume_id)
            container.update_resource(oid, state=ResourceState.ACTIVE, active=True)
            task.progress(step_id, msg=f"Volume {volume_id} created and activated.")

        # Save current data in shared area
        params["ext_id"] = volume_id
        return oid, params

    @staticmethod
    @task_step()
    def volume_expunge_physical_step(task, step_id, params, *args, **kvargs):
        """
        Delete physical resource.

        :param task: Celery task Instance.
        :param str step_id: step id.
        :param dict params: step params.
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
        if resource.is_ext_id_valid():
            # check volume exists
            rv = OpenstackVolume.get_remote_volume(container.controller, ext_id, container, ext_id)
            if rv is None or rv == {}:
                task.progress(step_id, msg=f"Volume {ext_id} does not exist anymore")
                return oid, params

            # remote volume snapshots
            snapshots = container.conn.volume_v3.snapshot.list(volume_id=ext_id)
            for snapshot in snapshots:
                snapshot_id = snapshot["id"]
                container.conn.volume_v3.snapshot.delete(snapshot_id)
                while True:
                    try:
                        container.conn.volume_v3.snapshot.get(snapshot_id)
                        sleep(2)
                    except:
                        task.progress(step_id, msg=f"Volume {ext_id} snapshot {snapshot_id} deleted")
                        break

            # remove volume
            conn.volume_v3.reset_status(ext_id, "available", "detached", "success")
            conn.volume_v3.delete(ext_id)
            task.progress(step_id, msg=f"Delete volume {ext_id} - Starting")

            # loop until entity is not deleted or get error
            while True:
                try:
                    inst = OpenstackVolume.get_remote_volume(container.controller, ext_id, container, ext_id)
                    if inst == {}:
                        task.progress(step_id, msg="Volume does not exist anymore")
                        raise Exception("Volume does not exist anymore")
                    status = inst["status"]
                    task.progress(step_id, msg=f"Volume {ext_id} status: {status}")
                    if status == "error_deleting":
                        task.progress(step_id, msg=f"Delete volume {ext_id} - Error")
                        raise Exception(f"Can not delete volume {ext_id}")
                    if status == "error":
                        task.progress(step_id, msg=f"delete volume {ext_id} - Error")
                        raise Exception(f"Can not delete volume {ext_id}")

                    task.progress(step_id, msg=f"Delete volume {ext_id} - Wait")
                    sleep(4)
                except:
                    # volume does not exists anymore
                    break

            resource.update_internal(ext_id=None)
            task.progress(step_id, msg=f"Delete volume {ext_id} - Completed")

        return oid, params

    @staticmethod
    @task_step()
    def volume_clone_step(task, step_id, params, *args, **kvargs):
        """
        Clone volume.

        :param task: Celery task Instance.
        :param str step_id: step id.
        :param dict params: step params.
        :param params.name: cloned volume name.
        :param params.project: cloned volume project.
        :return: oid, params
        """
        cid = params.get("cid")
        volume_ext_id = params.get("ext_id")
        cloned_name = params.get("cloned_name")
        parent_id = params.get("parent_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn

        project = task.get_simple_resource(parent_id)

        # clone volume
        volume_ext = conn.volume_v3.clone(cloned_name, volume_ext_id, project.ext_id)
        volume_ext_id = volume_ext["id"]
        task.progress(step_id, msg=f"Create openstack volume {volume_ext_id} - Starting")

        # create resource
        resource_params = {
            "resource_class": OpenstackVolume,
            "name": cloned_name,
            "desc": cloned_name,
            "objid": f"{project.objid}//{id_gen()}",
            "parent": parent_id,
            "ext_id": volume_ext_id,
            "active": False,
            "attrib": {},
            "tags": [],
        }
        model = container.add_resource(**resource_params)
        task.progress(step_id, msg=f"Create resource {model.id} for volume {volume_ext_id}")
        VolumeTask.poll_volume_status(task, step_id, container, volume_ext_id, "create volume")
        task.progress(step_id, msg=f"Create volume {volume_ext_id} - Completed")
        container.update_resource(model.id, state=ResourceState.ACTIVE, active=True)  # actitate volume
        task.progress(step_id, msg=f"Activate volume resource {model.id}")
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
        """
        Execute a volume action.

        :param task: Celery task Instance.
        :param action: action to execute.
        :param success: success message.
        :param error: error message.
        :param final_status: final status that volume must raise.
            If ORIGINAL final status must be the original status [default=ACTIVE]
        :param params: input params.
        :param projectid: projectid [optional]
        :return: action response
        """
        task.progress(step_id, msg=f"start action {action.__name__}")
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        container = task.get_container(cid, projectid=projectid)
        resource = task.get_simple_resource(oid)

        # Get original state.
        if final_status == "ORIGINAL":
            inst = OpenstackVolume.get_remote_volume(resource.controller, ext_id, container, ext_id)
            final_status = inst["status"]

        # Execute action.
        res = action(container, resource, **params)

        # Loop until action completed or return error.
        while True:
            inst = OpenstackVolume.get_remote_volume(resource.controller, ext_id, container, ext_id)
            status = inst["status"]
            task.progress(step_id, msg=f"Read volume {ext_id} status: {status}")
            if status == final_status:
                break
            if status == "ERROR":
                raise Exception(error)

            sleep(5)

        task.progress(step_id, msg=success)
        task.progress(step_id, msg=f"stop action {action.__name__}")

        return res

    @staticmethod
    @task_step()
    def volume_set_flavor_step(task, step_id, params, *args, **kvargs):
        """
        Set flavor to volume.

        :param task: Celery task Instance.
        :param str step_id: step id.
        :param dict params: step params.
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
