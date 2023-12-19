# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_pre,
    create_resource_post,
    expunge_resource_pre,
    expunge_resource_post,
    update_resource_post,
    update_resource_pre,
)
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_flavor_create_entity(self, options):
    """Create openstack network flavor.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.vcpus: vcpus
    :param sharedarea.ram: ram
    :param sharedarea.disk: disk
    :return: remote entity id
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    name = params.get("name")
    desc = params.get("desc")
    vcpus = params.get("vcpus")
    ram = params.get("ram")
    disk = params.get("disk")
    self.update("PROGRESS", msg="Get configuration params")

    # openstack network object reference
    self.get_session()
    container = self.get_container(cid)

    # create openstack network flavor
    conn = container.conn
    inst = conn.flavor.create(name, vcpus, ram, disk, desc)
    inst_id = inst["id"]
    self.update("PROGRESS", msg="Create flavor %s" % inst_id)

    # save current data in shared area
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_flavor_update_entity(self, options):
    """Delete openstack network flavor.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator config
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :return: uuid of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_flavor_delete_entity(self, options):
    """Delete openstack network flavor

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator config
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :return: uuid of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get conatiner
    self.get_session()
    container = self.get_container(cid)
    if ext_id is not None:
        conn = container.conn

        try:
            # check flavor exists
            conn.flavor.get(ext_id)

            # delete openstack flavor
            conn.flavor.delete(ext_id)
            self.update("PROGRESS", msg="Delete flavor %s" % ext_id)
        except:
            pass

    return ext_id


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackFlavor, name="insert", delta=2)
def job_flavor_create(self, objid, params):
    """Create openstack network flavor.

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param dict params: input params
    :param params.objid resource objid
    :param params.parent resource parent id
    :param params.cid container id
    :param params.name: resource name
    :param params.desc: resource desc
    :param params.ext_id resource ext_id
    :param params.active resource active
    :param params.attribute** (:py:class:`dict`): attributes
    :param params.tags comma separated resource tags to assign [default='']
    :param params.vcpus: vcpus
    :param params.ram: ram
    :param params.disk: disk
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            task_flavor_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackFlavor, name="update", delta=1)
def job_flavor_update(self, objid, params):
    """Delete openstack network flavor

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param dict params: input params
    :param params.cid** (int): container id
    :param params.id** (int): resource id
    :param params.uuid** (uuid): resource uuid
    :param params.objid: resource objid
    :param params.ext_id: physical id
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            update_resource_post,
            task_flavor_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackFlavor, name="delete", delta=1)
def job_flavor_delete(self, objid, params):
    """Delete openstack network flavor

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param dict params: input params
    :param params.cid** (int): container id
    :param params.id** (int): resource id
    :param params.uuid** (uuid): resource uuid
    :param params.objid: resource objid
    :param params.ext_id: resource physical id
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            expunge_resource_post,
            task_flavor_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
