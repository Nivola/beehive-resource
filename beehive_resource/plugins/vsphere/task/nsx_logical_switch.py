# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_pre,
    create_resource_post,
    expunge_resource_pre,
    expunge_resource_post,
    update_resource_pre,
    update_resource_post,
)
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task(module="ResourceModule")
def nsx_logical_switch_create_entity(self, options):
    """Create nsx logical_switch

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    # parent_id = params.get('parent')
    name = params.get("name")
    desc = params.get("desc")
    trasport_zone = params.get("trasport_zone")
    tenant = params.get("tenant")
    guest_allowed = params.get("guest_allowed", True)
    """if guest_allowed is True:
        guest_allowed = 'true'
    else:
        guest_allowed = 'false"""

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # create nsx logical_switch
    inst_id = conn.network.nsx.create_logical_switch(trasport_zone, name, desc, tenant, guest_allowed)

    # loop until vsphere task has finished
    # inst = container.query_remote_task(self, task)
    # inst_id = lsid

    # save current data in shared area
    # params['desc'] = desc
    # params['parent'] = parent_id
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task(module="ResourceModule")
def nsx_logical_switch_delete_entity(self, options):
    """Delete nsx logical_switch

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")

    # create session
    self.get_session()

    # get logical_switch resource
    container = self.get_container(cid)
    # resource = container.get_resources(oid)

    if ext_id is not None:
        # delete vsphere logical_switch
        conn = container.conn
        # logical_switch = conn.logical_switch.get_logical_switch(resource.ext_id)
        conn.network.nsx.delete_logical_switch(ext_id)

        # loop until vsphere task has finished
        # container.query_remote_task(self, task)

        self.update("PROGRESS", msg="Delete nsx logical switch: %s" % ext_id)

    return ext_id


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxLogicalSwitch, name="insert", delta=1)
def job_logical_switch_create(self, objid, params):
    """Create nsx logical_switch

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **name** (str): resource name
            * **desc** (str): resource desc
            * **parent** (int): resource parent
            * **ext_id** (str): physical id
            * **active** (bool): active
            * **attribute** (dict): attribute
            * **tags** (list): list of tags to add

            * **tenant**: [default='virtual wire tenant']
            * **guest_allowed**: [default=True]
            * **trasport_zone**: id of the trasport zone

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            nsx_logical_switch_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxLogicalSwitch, name="update", delta=1)
def job_logical_switch_update(self, objid, params):
    """Update nsx logical_switch

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): resource physical id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            update_resource_post,
            # vsphere_server_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxLogicalSwitch, name="delete", delta=1)
def job_logical_switch_delete(self, objid, params):
    """Delete nsx logical_switch

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): resource physical id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            expunge_resource_post,
            nsx_logical_switch_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
