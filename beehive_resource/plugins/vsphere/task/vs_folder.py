# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    expunge_resource_pre,
    expunge_resource_post,
    create_resource_pre,
    create_resource_post,
    update_resource_post,
    update_resource_pre,
)
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def vsphere_folder_create_entity(self, options):
    """Create vsphere folder

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
    name = params.get("name")
    desc = params.get("desc")
    folder_extid = params.get("folder")
    datacenter_extid = params.get("datacenter")
    folder_type = params.get("folder_type")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    folder = None
    dc = None
    if folder_extid is not None:
        folder = conn.folder.get(folder_extid)

    elif datacenter_extid is not None:
        dc = conn.datacenter.get(datacenter_extid)

    # get folder type
    host = False
    network = False
    storage = False
    vm = False

    if folder_type == "host":
        host = True
    elif folder_type == "network":
        network = True
    elif folder_type == "storage":
        storage = True
    elif folder_type == "vm":
        vm = True
    else:
        raise Exception("Vsphere %s folder type is not supported" % folder_type)

    # create vsphere folder
    inst = conn.folder.create(
        name,
        folder=folder,
        datacenter=dc,
        host=host,
        network=network,
        storage=storage,
        vm=vm,
        desc=desc,
    )
    inst_id = inst._moId

    # save current data in shared area
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def vsphere_folder_update_entity(self, options):
    """Update vsphere folder


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
    oid = params.get("id")
    name = params.get("name")

    # create session
    self.get_session()

    # get vsphere folder
    container = self.get_container(cid)
    resource = container.get_resource(oid)

    if resource.ext_id is not None and resource.ext_id != "":
        # update vsphere folder
        conn = container.conn
        folder = conn.folder.get(resource.ext_id)
        task = conn.folder.update(folder, name)

        # loop until vsphere task has finished
        container.query_remote_task(self, task)

    # save current data in shared area
    self.set_shared_data(params)

    return resource.ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def vsphere_folder_delete_entity(self, options):
    """Delete vsphere folder


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
    oid = params.get("id")

    # create session
    self.get_session()

    # get folder resource
    container = self.get_container(cid)
    resource = container.get_resource(oid)

    # delete vsphere folder
    conn = container.conn
    if resource.ext_id is not None and resource.ext_id != "":
        folder = conn.folder.get(resource.ext_id)
        if folder is None:
            self.progress("Folder %s does not exist anymore" % resource.ext_id)
        else:
            task = conn.folder.remove(folder)
            # loop until vsphere task has finished
            container.query_remote_task(self, task)

    # reset ext_id
    resource.update_internal(ext_id=None)

    # update params
    params["oid"] = resource.oid

    # update task
    self.update("PROGRESS")

    return oid


#
# resource management
#
'''
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def vsphere_folder_create_resource(self, options):
    """Create folder resource in cloudapi
    
    :param options: tupla that must contain (class_name, objid, job, job id, 
                                             start time, time before new query)
    :param params: [shared data] task input params
                    {
                        'cid':..,
                        'instance_id':.., 
                        'name':.., 
                        'desc':.., 
                        'parent':..
                    }

                   cid: container id
                   parent: parent vsphere id
                   instance_id: remote entity vsphere id
                   name: name of the new resource
                   desc: description of the new resource
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    ext_id = params.get('instance_id')
    name = params.get('name')
    desc = params.get('desc')
    parent_id = params.get('parent_id')
    resource_objid = params.get('resource_objid')
    attrib = params.get('attrib')

    # create session
    self.get_session()
    
    # get container
    container = self.get_container(cid)

    resource = task_local.entity_class(container.controller, container, 
                                 objid=resource_objid,
                                 name=name, desc=desc, active=True, 
                                 ext_id=ext_id, attribute=attrib, model=None, 
                                 parent_id=parent_id)
    oid = container.add_resource(resource)
    
    # create child objects and permission
    #VsphereServer(container.controller, container).register_object(
    #                 resource_objid.split('//'), desc=desc+' servers') 
    
    # set resource id in shared data
    params['result'] = oid
    self.set_shared_data(params)
    
    # update job status
    self.update('PROGRESS')
    return oid

@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def vsphere_folder_expunge_resource(self, options):
    """Remove folder resource in cloudapi
    
    :param options: tupla that must contain (class_name, objid, job, job id, 
                                             start time, time before new query)
    :param params: [shared data] task input params
    
                    {
                        'cid':..,
                        'id':..,
                    }
    
                   cid: container id
                   id: resource id               
    """
    # get params from shared data
    params = self.get_shared_data()    
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')   

    # create session
    self.get_session()
    
    # get container
    container = self.get_container(cid)
    
    # get resource
    resource = container.get_resources(oid)
    
    # prepare resource
    resource_class = import_class(resource.type.objclass)
    obj = resource_class(container.controller, container, oid=resource.id, 
                         objid=resource.objid, name=resource.name, desc=resource.desc, 
                         active=resource.active, ext_id=resource.ext_id,
                         attribute=resource.attribute, 
                         parent_id=resource.parent_id, model=resource)    
    # delete resource
    obj.expunge_resource()    
    
    # remove child objects and permissions
    #child_classes = [VsphereServer]
    #for child_class in child_classes:
    #    child_class(container.controller, container).deregister_object(
    #                                                        objid.split('//'))    
    
    # update job status
    self.update('PROGRESS')
    return oid
    '''


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereFolder, name="insert", delta=1)
def job_folder_create(self, objid, params):
    """Create openstack project

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
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']
            * **datacenter**: datacenter id
            * **type**: folder type. Can be: host, network, storage, vm

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            vsphere_folder_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereFolder, name="update", delta=1)
def job_folder_update(self, objid, params):
    """Update openstack project.

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
            vsphere_folder_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereFolder, name="delete", delta=1)
def job_folder_delete(self, objid, params):
    """Delete openstack project.

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
            vsphere_folder_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
