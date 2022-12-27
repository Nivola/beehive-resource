# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import ResourceJobTask, ResourceJob, \
    create_resource_pre, create_resource_post, update_resource_post,\
    update_resource_pre, expunge_resource_pre
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.vsphere.task.util import VsphereServerHelper
from beehive_resource.plugins.vsphere.entity.vs_orchestrator import VsphereStack
from beecell.simple import truncate
from beehive.common.task.canvas import signature

logger = get_task_logger(__name__)

stack_entity_type_mapping = {
    'VS::Vsphere::Server': 'Vsphere.DataCenter.Folder.Server',
}


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def stack_create_entity(self, options):
    """Create opsck stack
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
            * **objid**: resource objid
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']

            * **template_uri**: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
            * **environment**: A JSON environment for the stack
            * **parameters**: 'Supplies arguments for parameters defined in the stack template
            * **files**: Supplies the contents of files referenced in the template or the environment
            * **owner**: stack owner name
        
    **Return:**
    
        stack id
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    template_uri = params.get('template_uri')
    parent_id = params.get('parent')
    name = params.get('name')
    environment = params.get('environment', None)
    parameters = params.get('parameters', None)
    files = params.get('files', None)
    tags = params.get('tags', '')
    stack_owner = params.get('owner')
    self.update('PROGRESS', msg='Get configuration params')

    # get orchestrator
    self.get_session()
    orchestrator = self.get_container(cid)
    self.update('PROGRESS', msg='Get orchestrator %s' % cid)

    # validate template
    orch = orchestrator.get_orchestrator_resource()
    template = orch.validate_template(template_uri)
    self.update('PROGRESS', msg='Validate template %s' % template_uri)

    # parse template
    outputs = template.get('outputs')
    parameters = template.get('parameters')
    resources = template.get('resources')

    servers = []
    for resname, resource in resources.items():
        logger.warn(resname)
        restype = resource.get('type')
        resconf = resource.get('properties')
        logger.warn(restype)
        logger.warn(resconf)
        if restype == 'VS::Vsphere::Server':
            '''
            server = {
                'name': '%s-%s' % (resname, id_gen()),
                'imageRef':
                'folder_id'
                'network_id'
                'block_device_mapping': {
                    'uuid': 'datastore_id',
                    'source_type': 'image',
                    'volume_size': '20',
                    'destination_type': 'volume',
                }
                'personality':
                'user_data':
                'networks': {'uuid':, 'fixed_ip': {
                        'ip':'172.25.5.154',
                        'gw':'172.25.5.18',
                        'hostname':name,
                        'dns':[8.8.8.8],
                        'dns_search':csi.it
                    }
                },
                'flavorRef': {
                    'guest_id':
                    'memory_mb':
                    'cp':
                    'core_x_socket':
                    'version':
                }
                'adminPass':
                'availability_zone': 'resource_pool_id'
                'metadata':
                'security_groups'
            }
            servers.append(server)'''
            pass

    # create all servers
    helper = VsphereServerHelper(self, orchestrator, params)
    for server in servers:
        node = helper.create_server(**server)

    # create new stack
    stack = {'id': 'pippo'}
    stack_id = stack['id']


    # stack_id = stack['id']
    # self.update('PROGRESS', msg='Create stack %s - Starting' % stack_id)
    #
    # # set ext_id
    # container.update_resource(oid, ext_id=stack_id)
    # self.update('PROGRESS', msg='Set stack remote openstack id %s' % stack_id)

    # # loop until entity is not stopped or get error
    # while True:
    #     inst = conn.heat.stack.get(stack_name=name, oid=stack_id)
    #     status = inst['stack_status']
    #     if status == 'CREATE_COMPLETE':
    #         break
    #     elif status == 'CREATE_FAILED':
    #         reason = inst['stack_status_reason']
    #         self.update('PROGRESS', msg='Create stack %s - Error: %s' % (stack_id, reason))
    #         raise Exception('Can not create stack %s: %s' % (stack_id, reason))
    #
    #     self.update('PROGRESS')
    #     gevent.sleep(task_local.delta)




    self.update('PROGRESS', msg='Create stack %s - Completed' % stack_id)

    # save current data in shared area
    params['ext_id'] = stack_id
    params['result'] = stack_id
    # params['attrib'] = {'volume':{'boot':volume.id}}
    self.set_shared_data(params)
    self.update('PROGRESS', msg='Update shared area')
    
    return stack_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def stack_register_child_entity(self, options):
    """Register opsck stack child entity

    **Parameters:**    

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):

            * **oid**: resource id
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']

            * **template_uri**: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
            * **environment**: A JSON environment for the stack
            * **parameters**: 'Supplies arguments for parameters defined in the stack template
            * **files**: Supplies the contents of files referenced in the template or the environment
            * **owner**: stack owner name

    **Return:**

        stack childs remote ids
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get('cid')
    # oid = params.get('id')
    ext_id = params.get('ext_id')
    name = params.get('name')
    parent_id = params.get('parent')
    self.update('PROGRESS', msg='Get configuration params')

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn
    self.update('PROGRESS', msg='Get container %s' % cid)

    # get resources
    resources = conn.heat.stack.resource.list(stack_name=name, oid=ext_id)
    self.update('PROGRESS', msg='Get child resources: %s' % truncate(resources))

    '''
    [{'resource_name': 'my_instance', 
      'links': [{}], 
      'logical_resource_id': 'my_instance',
      'creation_time': '2017-12-19T12:17:09Z', 
      'resource_status': 'CREATE_COMPLETE',
      'updated_time': '2017-12-19T12:17:09Z', 
      'required_by': [], 
      'resource_status_reason': 'state changed',
      'physical_resource_id': '9d06ea46-6ab0-4e93-88b9-72f32de0cc31', 
      'resource_type': 'OS::Nova::Server'}]
    '''

    # get child resources objdef
    objdefs = {}
    res_ext_ids = []
    for item in resources:
        # TODO : router should need additional operation for internal port and ha network
        mapping = stack_entity_type_mapping[item['resource_type']]
        if mapping is not None:
            objdefs[mapping] = None
            res_ext_ids.append(item['physical_resource_id'])
    self.update('PROGRESS', msg='get child resources objdef: %s' % objdefs)

    # run celery job
    if len(objdefs) > 0:
        params = {
            'cid': cid,
            'types': ','.join(objdefs.keys()),
            'new': True,
            'died': False,
            'changed': False
        }
        params.update(container.get_user())
        task = signature('beehive_resource.tasks.job_synchronize_container', (container.objid, params), app=task_manager,
                         queue=container.celery_broker_queue)
        job = task.apply_async()
        self.logger.info('Start job job_synchronize_container %s' % job.id)

        # wait job complete
        self.wait_for_job_complete(job.id)

    # save current data in shared area
    params['res_ext_ids'] = res_ext_ids
    self.set_shared_data(params)
    self.update('PROGRESS', msg='Update shared area')

    return res_ext_ids


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def stack_link_child_entity(self, options):
    """Link opsck stack child entity

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

            * **oid**: resource id
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']

            * **template_uri**: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
            * **environment**: A JSON environment for the stack
            * **parameters**: 'Supplies arguments for parameters defined in the stack template
            * **files**: Supplies the contents of files referenced in the template or the environment
            * **owner**: stack owner name

            * **res_ext_ids**: list of remote child entity

    **Return:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')
    res_ext_ids = params.get('res_ext_ids')
    self.update('PROGRESS', msg='Get configuration params')

    # link child resource to stack
    self.get_session()
    stack = self.get_resource(oid)
    for ext_id in res_ext_ids:
        child = self.get_resource_by_extid(ext_id)
        stack.add_link('%s-%s-stack-link' % (oid, child.oid), 'stack', child.oid, attributes={})
        self.update('PROGRESS', msg='Link stack %s to child %s' % (oid, child.oid))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def stack_update_entity(self, options):
    """Create opsck stack
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
            * **cid**: orchestrator id
            * **id**: stack id
        
    **Return:**
    
        stack id
    """
    pass


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def stack_delete_entity(self, options):
    """Delete opsck stack
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
            * **cid**: orchestrator id
            * **id**: stack id
        
    **Return:**
    
        stack id
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    ext_id = params.get('ext_id')
    parent_id = params.get('parent_id')
    self.update('PROGRESS', msg='Get configuration params')
    
    # get stack resource
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn
    self.update('PROGRESS', msg='Get container %s' % cid)

    # if self.is_ext_id_valid(ext_id) is True:
    #     res = container.get_resource_by_extid(ext_id)
    #
    #     # check stack
    #     inst = conn.heat.stack.get(stack_name=res.name, oid=ext_id)
    #     if inst['stack_status'] != 'DELETE_COMPLETE':
    #         # remove stack
    #         conn.heat.stack.delete(stack_name=res.name, oid=ext_id)
    #         self.update('PROGRESS', msg='Delete stack %s - Starting' % ext_id)
    #
    #         # loop until entity is not deleted or get error
    #         while True:
    #             inst = conn.heat.stack.get(stack_name=res.name, oid=ext_id)
    #             status = inst['stack_status']
    #             if status == 'DELETE_COMPLETE':
    #                 break
    #             elif status == 'DELETE_FAILED':
    #                 self.update('PROGRESS', msg='Delete stack %s - Error' % ext_id)
    #                 raise Exception('Can not delete stack %s' % ext_id)
    #
    #             self.update('PROGRESS')
    #             gevent.sleep(task_local.delta)
    #
    #     res.update_internal(ext_id=None)
    #     self.update('PROGRESS', msg='Delete stack %s - Completed' % ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def stack_expunge_resource_post(self, options):
    """Remove stack resource in cloudapi - post task.
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
            * **cid**: orchestrator id
            * **id**: stack id
        
    **Return:**
    
        stack child id
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    self.update('PROGRESS', msg='Get configuration params') 

    # get all child resources
    self.get_session()
    container = self.get_container(cid)
    resources = self.get_linked_resources(oid, link_type='stack', container_id=cid)

    # get child resources objdef
    objdefs = {}
    res_ids = []
    for item in resources:
        # TODO : router should need additional operation for internal port and ha network
        # objdefs[item.objdef] = None
        res_ids.append(item.id)
    for k, v in stack_entity_type_mapping.items():
        if v is not None:
            objdefs[v] = None
    self.update('PROGRESS', msg='Get child resources objdef: %s' % objdefs)
    self.update('PROGRESS', msg='Get child resources ext_id: %s' % res_ids)

    # # run celery job
    # if len(objdefs) > 0:
    #     params = {
    #         'cid': cid,
    #         'types': ','.join(objdefs.keys()),
    #         'new': False,
    #         'died': True,
    #         'changed': False
    #     }
    #     params.update(container.get_user())
    #     task = signature('beehive_resource.tasks.job_synchronize_container', (container.objid, params),
    #                      app=task_manager, queue=container.celery_broker_queue)
    #     job = task.apply_async()
    #     self.logger.info('Start job job_synchronize_container %s' % job.id)
    #
    #     # wait job complete
    #     self.wait_for_job_complete(job.id)

    # delete stack
    self.release_session()
    self.get_session()
    resource = self.get_resource(oid)
    resource.expunge_internal()
    self.update('PROGRESS', msg='Delete stack %s resource' % oid)

    return res_ids


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereStack, name='insert', delta=3)
def job_stack_create(self, objid, params):
    """Create opsck stack
    
    **Parameters:**
    
        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params    
    
            * **oid**: resource oid
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']

            * **template_uri**: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
            * **environment**: A JSON environment for the stack
            * **parameters**: 'Supplies arguments for parameters defined in the stack template
            * **files**: Supplies the contents of files referenced in the template or the environment
            * **owner**: stack owner name
                    
    **Returns:**
    
        True
    """
    ops = self.get_options()
    self.set_shared_data(params)
    
    Job.create([
        end_task,
        #stack_link_child_entity,
        #stack_register_child_entity,
        create_resource_post,
        stack_create_entity,
        create_resource_pre,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereStack, name='update', delta=3)
def job_stack_update(self, objid, params):
    """Update opsck stack
    
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
        stack_update_entity,
        update_resource_pre,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=VsphereStack, name='delete', delta=1)
def job_stack_delete(self, objid, params):
    """Delete opsck stack
    
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
    
    Job.create([
        end_task,
        stack_expunge_resource_post,
        stack_delete_entity,
        expunge_resource_pre,
        start_task
    ], ops).delay()
    return True
