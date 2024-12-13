# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, task_local
from beehive_resource.model import ResourceState
import gevent


logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_volume(self, options):
    """Create openstack volume

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.objid: resource objid
    :param sharedarea.parent: resource parent id
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.ext_id: resource ext_id
    :param sharedarea.active: resource active
    :param sharedarea.attribute: attributes
    :param sharedarea.tags: comma separated resource tags to assign [default='']
    :param sharedarea.size: The size of the volume, in gibibytes (GiB).
    :param sharedarea.availability_zone: The availability zone. [optional]
    :param sharedarea.source_volid: The UUID of the source volume. The API creates a new volume with the same size as
        the source volume. [optional]
    :param sharedarea.multiattach: To enable this volume to attach to more than one server, set this value to true.
        Default is false. [optional] [todo]
    :param sharedarea.snapshot_id: To create a volume from an existing snapshot, specify the UUID of the volume
        snapshot. The volume is created in same availability zone and with same size as the snapshot. [optional]
    :param sharedarea.imageRef: The UUID of the image from which you want to create the volume. Required to create a
        bootable volume. [optional]
    :param sharedarea.volume_type: The volume type. To create an environment with multiple-storage back ends, you must
        specify a volume type. Block Storage volume back ends are spawned as children to cinder-volume, and they
        are keyed from a unique queue. They are named cinder- volume.HOST.BACKEND. For example,
        cinder-volume.ubuntu.lvmdriver. When a volume is created, the scheduler chooses an appropriate back end
        to handle the request based on the volume type. Default is None. For information about how to use
        volume typesto create multiple-storage back ends, see Configure multiple-storage back ends. [optional]
    :param sharedarea.metadata: One or more metadata key and value pairs that are associated with the volume. [optional]
    :param sharedarea.source_replica: The UUID of the primary volume to clone. [optional] [todo]
    :param sharedarea.consistencygroup_id: The UUID of the consistency group. [optional] [todo]
    :param sharedarea.scheduler_hints: The dictionary of data to send to the scheduler. [optional] [todo]
    :return: volume physical id
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.progress(msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    name = params.get("name")
    desc = params.get("desc")
    parent_id = params.get("parent")
    availability_zone = params.get("availability_zone")
    image = params.get("image")
    project_extid = params.get("project_extid")
    size = params.get("size")
    source_volid = params.get("volume")
    snapshot_id = params.get("snapshot_id")
    volume_type = params.get("volume_type")
    consistencygroup_id = params.get("consistencygroup_id")
    metadata = params.get("metadata")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn
    self.progress(msg="%s" % container)
    self.progress(msg="%s" % conn)
    self.progress(msg="%s" % parent_id)
    self.progress(msg="Get container %s" % cid)

    # create new volume
    volume_ext = conn.volume.create(
        size=int(size),
        availability_zone=availability_zone,
        source_volid=source_volid,
        description=desc,
        multiattach=False,
        snapshot_id=snapshot_id,
        name=name,
        imageRef=image,
        volume_type=volume_type,
        metadata=metadata,
        source_replica=None,
        consistencygroup_id=consistencygroup_id,
        scheduler_hints=None,
        tenant_id=project_extid,
    )

    volume_id = volume_ext["id"]
    self.progress(msg="Create openstack volume %s - Starting" % volume_id)

    # attach remote volume
    container.update_resource(oid, ext_id=volume_id)
    self.progress(msg="Attach openstack volume %s to volume %s" % (volume_id, oid))

    # loop until entity is not stopped or get error
    while True:
        inst = OpenstackVolume.get_remote_volume(container.controller, volume_id, container, volume_id)
        # inst = conn.volume.get(oid=volume_id)
        status = inst.get("status", "error")
        if status == "available":
            break
        elif status == "error":
            self.progress(msg="Create openstack volume %s - Error" % volume_id)
            raise Exception("Can not create openstack volume %s" % volume_id)

        self.update("PROGRESS")
        gevent.sleep(task_local.delta)

    self.progress(msg="Create volume %s - Completed" % volume_id)

    # acvitate volume
    container.update_resource(oid, state=ResourceState.ACTIVE, active=True)
    self.progress(msg="Acvitate volume %s" % volume_id)

    # save current data in shared area
    params["ext_id"] = volume_id
    self.set_shared_data(params)
    self.progress(msg="Update shared area")

    return volume_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_volume(self, options):
    """Delete openstack volume

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.parent_id: parent id
    :return: volume physical id
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.progress(msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    parent_id = params.get("parent_id")
    self.progress(msg="Get configuration params")

    # get server resource
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn

    if self.is_ext_id_valid(ext_id) is True:
        res = container.get_resource_by_extid(ext_id)

        # check volume exists
        rv = OpenstackVolume.get_remote_volume(container.controller, ext_id, container, ext_id)
        if rv == {}:
            self.progress(msg="Volume %s does not exist anymore" % ext_id)
            return False

        # remote volume snapshots
        snapshots = container.conn.volume.snapshot.list(volume_id=ext_id)
        for snapshot in snapshots:
            container.conn.volume.snapshot.delete(snapshot["id"])
            while True:
                try:
                    container.conn.volume.snapshot.get(snapshot["id"])
                    gevent.sleep(2)
                except:
                    self.progress("Volume %s snapshot %s deleted" % (ext_id, snapshot["id"]))
                    break

        # remove server
        conn.volume.delete(ext_id)
        self.progress(msg="Delete volume %s - Starting" % ext_id)

        # loop until entity is not deleted or get error
        while True:
            try:
                inst = OpenstackVolume.get_remote_volume(container.controller, ext_id, container, ext_id)
                # inst = conn.volume.get(oid=ext_id)
                if inst == {}:
                    self.task.progress("Volume does not exist anymore")
                    raise Exception("Volume does not exist anymore")
                status = inst["status"]
                self.progress(msg="Volume %s status: %s" % (ext_id, status))
                if status == "error_deleting":
                    self.progress(msg="Delete volume %s - Error" % ext_id)
                    raise Exception("Can not delete volume %s" % ext_id)
                elif status == "error":
                    self.progress(msg="delete volume %s - Error" % ext_id)
                    raise Exception("Can not delete volume %s" % ext_id)

                gevent.sleep(task_local.delta)
            except:
                # volume does not exists anymore
                break

        res.update_internal(ext_id=None)
        self.progress(msg="Delete volume %s - Completed" % ext_id)

    return ext_id
