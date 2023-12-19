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
from beehive_resource.plugins.vsphere.entity.vs_resource_pool import VsphereResourcePool

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def resource_pool_create_entity(self, options):
    """Create vsphere resourcepool

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Returns:**

    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid", None)
    name = params.get("name", None)
    cluster_ext_id = params.get("cluster_ext_id", None)
    cpu = params.get("cp", None)
    memory = params.get("memory", None)
    shares = params.get("shares", "normal")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # get parent dvs
    # cluster_obj = container.get_resource(cluster)
    cluster = conn.cluster.get(cluster_ext_id)

    # create vsphere resourcepool
    inst = conn.cluster.resource_pool.create(cluster, name, cpu, memory, shares)

    # loop until vsphere task has finished
    # inst = container.query_remote_task(self, task)
    inst_id = inst._moId

    # save current data in shared area
    # params['parent'] = cluster_obj.id
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)

    # update task
    self.update("PROGRESS", msg="Create vsphere resource pool: %s" % inst_id)

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def resource_pool_update_entity(self, options):
    """Update vsphere resourcepool

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Returns:**
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid", None)
    oid = params.get("id", None)
    name = params.get("name", None)
    cpu = params.get("cp", None)
    memory = params.get("memory", None)
    shares = params.get("shares", "normal")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # get parent dvs
    respool_obj = container.get_resource(oid)
    respool = conn.cluster.resource_pool.get(respool_obj.ext_id)

    # create vsphere resourcepool
    inst = conn.cluster.resource_pool.update(respool, name, cpu, memory, shares)

    # loop until vsphere task has finished
    # inst = container.query_remote_task(self, task)
    inst_id = respool_obj.ext_id

    # save current data in shared area
    params["attrib"] = None
    self.set_shared_data(params)

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def resource_pool_delete_entity(self, options):
    """Delete vsphere resourcepool

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Returns:**
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

    if ext_id is not None:
        # delete vsphere network
        conn = container.conn
        respool = conn.cluster.resource_pool.get(ext_id)
        task = conn.cluster.resource_pool.remove(respool)

        # loop until vsphere task has finished
        container.query_remote_task(self, task)

    # update params
    # params['oid'] = resource.id

    # update task
    self.update("PROGRESS", msg="Delete vsphere resource pool: %s" % ext_id)

    return ext_id


#
# resource management
#


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereResourcePool, name="insert", delta=1)
def job_resource_pool_create(self, objid, params):
    """Create openstack resourcepool

    **Parameters:**

        * **params** (:py:class:`dict`): add params

            * **objid**: resource objid
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']

            * **cluster_ext_id**: cluster ext id
            * **cpu**: cpu limit in MHz
            * **memory**: memory limit in MB
            * **shares**:
                high
                  For CPU: Shares = 2000 * number of virtual CPUs
                  For Memory: Shares = 20 * virtual machine memory size in megabytes
                  For Disk: Shares = 2000
                  For Network: Shares = networkResourcePoolHighShareValue
                low
                  For CPU: Shares = 500 * number of virtual CPUs
                  For Memory: Shares = 5 * virtual machine memory size in megabytes
                  For Disk: Shares = 500
                  For Network: Shares = 0.25 * networkResourcePoolHighShareValue
                normal
                  For CPU: Shares = 1000 * number of virtual CPUs
                  For Memory: Shares = 10 * virtual machine memory size in megabytes
                  For Disk: Shares = 1000
                  For Network: Shares = 0.5 * networkResourcePoolHighShareValue
                [default=normal]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            resource_pool_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereResourcePool, name="update", delta=1)
def job_resource_pool_update(self, objid, params):
    """Update openstack resourcepool

    **Parameters:**

        * **params** (:py:class:`dict`): add params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): physical id
            * **name**: resource name
            * **cpu**: cpu limit in MHz
            * **memory**: memory limit in MB
            * **shares**:
                high
                  For CPU: Shares = 2000 * number of virtual CPUs
                  For Memory: Shares = 20 * virtual machine memory size in megabytes
                  For Disk: Shares = 2000
                  For Network: Shares = networkResourcePoolHighShareValue
                low
                  For CPU: Shares = 500 * number of virtual CPUs
                  For Memory: Shares = 5 * virtual machine memory size in megabytes
                  For Disk: Shares = 500
                  For Network: Shares = 0.25 * networkResourcePoolHighShareValue
                normal
                  For CPU: Shares = 1000 * number of virtual CPUs
                  For Memory: Shares = 10 * virtual machine memory size in megabytes
                  For Disk: Shares = 1000
                  For Network: Shares = 0.5 * networkResourcePoolHighShareValue
                [default=normal]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            update_resource_post,
            resource_pool_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereResourcePool, name="delete", delta=1)
def job_resource_pool_delete(self, objid, params):
    """Delete openstack resourcepool

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
            resource_pool_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
