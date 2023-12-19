# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_post,
    create_resource_pre,
    expunge_resource_post,
    expunge_resource_pre,
    update_resource_post,
    update_resource_pre,
)
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def dvpg_create_entity(self, options):
    """Create vsphere network

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Returns:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid", None)
    name = params.get("name", None)
    desc = params.get("desc", None)
    dvs_ext_id = params.get("dvs_ext_id", None)
    # network_type = params.get('network_type', 'vlan')
    segmentation_id = params.get("segmentation_id", None)
    numports = params.get("numports", None)

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # get parent dvs
    # dvs = container.get_resource(physical_network)
    dvs_ext = conn.network.get_distributed_virtual_switch(dvs_ext_id)

    # create vsphere network
    task = conn.network.create_distributed_port_group(name, desc, segmentation_id, dvs_ext, numports)

    # loop until vsphere task has finished
    inst = container.query_remote_task(self, task)
    inst_id = inst._moId

    # save current data in shared area
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)

    # update task
    self.update("PROGRESS", msg="Create vsphere dvpg: %s" % inst_id)

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def dvpg_delete_entity(self, options):
    """Delete vsphere network

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Returns:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid", None)
    ext_id = params.get("ext_id", None)

    # create session
    self.get_session()

    # get network resource
    container = self.get_container(cid)
    # resource = container.get_resource(oid)

    # delete vsphere network
    conn = container.conn
    if ext_id is not None:
        network = conn.network.get_network(ext_id)
        if network is not None:
            task = conn.network.remove_network(network)
            # loop until vsphere task has finished
            container.query_remote_task(self, task)

    # update params
    # params['oid'] = resource.id

    # update task
    self.update("PROGRESS", msg="Delete vsphere dvpg: %s" % ext_id)

    return True


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereDvpg, name="insert", delta=1)
def job_dvpg_create(self, objid, params):
    """Create vsphere dvpg

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **objid**: resource objid
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributez
            * **tags**: comma separated resource tags to assign [default='']

            * **dvs_ext_id**: dvs ext id
            * **physical_network**: dvs id
            * **network_type**: only vlan is supported
            * **segmentation_id**: An isolated segment on he physical network.
                The network_type attribute defines the segmentation model.
                For example, if the network_type value is vlan, this ID is a
                vlan identifier. If the network_type value is gre, this ID
                is a gre key.
            * **numports**: port group intial ports number
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            dvpg_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereDvpg, name="update", delta=1)
def job_dvpg_update(self, objid, params):
    """Update vsphere dvpg
    TODO
    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): physical id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            update_resource_post,
            # dvpg_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereDvpg, name="delete", delta=1)
def job_dvpg_delete(self, objid, params):
    """Delete vsphere dvpg

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
            dvpg_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
