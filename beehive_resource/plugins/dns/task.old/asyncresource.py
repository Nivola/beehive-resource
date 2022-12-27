# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from gevent import sleep
from beehive.common.task.job import Job, job, job_task
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import ResourceJob, create_resource_pre,\
    create_resource_post, expunge_resource_post, expunge_resource_pre,\
    update_resource_post, update_resource_pre, ResourceJobTask
from beehive_resource.plugins.dummy.controller import DummyAsyncResource
from beehive.common.task.util import end_task, start_task


#
# TASK
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def asyncresource_wait(self, options):
    """Wait some second
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
    **Returns:**
    
        True             
    """
    params = self.get_shared_data()
    sleep(5)
    return True


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=DummyAsyncResource, name=u'insert', delta=1)
def job_asyncresource_create(self, objid, params):
    """Create asyncresource
    
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

    **Returns:**
    
        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        create_resource_post,
        asyncresource_wait,
        create_resource_pre,
        start_task,
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=DummyAsyncResource, name=u'update', delta=1)
def job_asyncresource_update(self, objid, params):
    """Update asyncresource
    
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

    Job.create([
        end_task,
        update_resource_post,
        asyncresource_wait,
        update_resource_pre,
        start_task,
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=DummyAsyncResource, name=u'delete', delta=1)
def job_asyncresource_delete(self, objid, params):
    """Delete asyncresource
    
    **Parameters:**
    
        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid

    **Returns:**
    
        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        expunge_resource_post,
        asyncresource_wait,
        expunge_resource_pre,
        start_task,
    ], ops).delay()
    return True