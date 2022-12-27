# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from celery.utils.log import get_task_logger
from beecell.simple import import_func
from beehive.common.task.job import Job, JobTask, task_local, job_task, job
from beehive_resource.container import *
from beehive_resource.plugins.openstack.controller import *
from beehive.common.task.util import end_task, start_task
from beecell.simple import jsonDumps

logger = get_task_logger(__name__)


#
# resource task
#
class ResourceTaskException(Exception):
    pass


#
# ResourceJob
#
class AbstractResourceTask(object):
    def __init__(self, *args, **kwargs):
        Job.__init__(self, *args, **kwargs)
        self.container = None
        self.token = None

    def is_ext_id_valid(self, ext_id):
        """Validate ext_id
        """
        if ext_id is not None and ext_id != '' and ext_id != '':
            return True
        return False

    def __get_openstack_connection(self, container, projectid=None):
        try:
            # get connection params
            conn_params = container.conn_params['api']
            uri = conn_params['uri']
            region = conn_params['region']
            user = conn_params['user']
            pwd = conn_params['pwd']
            domain = conn_params['domain']

            # get project
            project_name = conn_params['project']
            if projectid is not None:
                try:
                    project = container.manager.get_entity(ModelResource, projectid)
                except:
                    raise ApiManagerError('Openstack project %s not found' % projectid, code=404)

                project_name = project.name
            self.logger.debug('Use openstack project %s for connection' % project_name)

            # decrypt password
            pwd = container.decrypt_data(pwd)

            # create connection
            conn = OpenstackManager(uri=uri, default_region=region)
            conn.authorize(user=user, pwd=pwd, project=project_name, domain=domain)
            token = conn.get_token()
            # container.catalogs[project] = container.conn.get_catalog()
            self.logger.debug('Get openstack connection %s with token: %s' % (conn, token))
        except OpenstackError as ex:
            self.logger.error(ex, exc_info=True)
            raise ResourceTaskException(ex, code=400)

        return conn

    def get_container(self, container_oid, projectid=None):
        """Get resource container instance.

        :param container_oid: container oid
        :param projectid: projectid. Used only for container openstack            
        :return: container instance            
        :raise ApiManagerError:        
        """
        operation.cache = False
        local_container = task_local.controller.get_container(container_oid, connect=False, cache=False)
        if local_container.objdef == 'Openstack':
            local_container.conn = self.__get_openstack_connection(local_container, projectid=projectid)
        else:
            local_container.get_connection()
        self.logger.debug('Get container %s of type %s' % (local_container, local_container.objdef))
        return local_container

    def get_resource(self, oid, details=False, run_customize=True):
        """Get resource instance.
        
        :param oid: resource oid
        :param details: if True call custom method post_get()
        :param run_customize: if True run customize [default=True]
        :return: resource instance
        :raises ApiManagerError: if query empty return error.
        """
        return task_local.controller.get_resource(oid, details=details, run_customize=run_customize)

    def get_resource_with_no_detail(self, oid):
        """Get resource instance without detail.

        :param oid: resource oid
        :return: resource instance
        :raises ApiManagerError: if query empty return error.
        """
        return self.get_resource(oid, details=False, run_customize=False)

    def get_resource_with_detail(self, oid):
        """Get resource instance with detail.

        :param oid: resource oid
        :return: resource instance
        :raises ApiManagerError: if query empty return error.
        """
        return self.get_resource(oid, details=True, run_customize=True)
    
    def get_resource_by_extid(self, extid):
        """Get resource instance by external id.
        
        **Parameters:**
        
        :param extid: resource extid            
        :return: resource instance            
        :raise ApiManagerError:        
        """
        resource = task_local.controller.get_resource_by_extid(extid)
        return resource
    
    def get_link(self, oid):
        """Get link instance.
        
        :param oid: link oid            
        :return: link instance            
        :raise ApiManagerError:        
        """
        link = task_local.controller.get_link(oid)
        return link
    
    def get_tag(self, oid):
        """Get tag instance.
        
        :param oid: tag oid            
        :return: tag instance            
        :raise ApiManagerError:        
        """
        tag = task_local.controller.get_tag(oid)
        return tag

    def get_orm_linked_resources(self, resource, link_type=None, container_id=None, objdef=None):
        """Get linked resources from orm.

        :param resource: resource id
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :return: list of records
        :raise ApiManagerError:
        """
        manager = task_local.controller.manager
        entity = manager.get_entity(ModelResource, resource)
        resources = manager.get_linked_resources_internal(entity.id, link_type=link_type, container_id=container_id,
                                                          objdef=objdef)
        self.update('PROGRESS', msg='Get %s linked resources: %s' % (resource, resources))
        return resources

    def get_linked_resources(self, resource, link_type=None, container_id=None, objdef=None):
        """[DEPRECATED]
        """
        return self.get_orm_linked_resources(resource, link_type, container_id, objdef)

    def get_orm_link_among_resources(self, start, end):
        """Get links of a resource from orm

        :param start: start resource id
        :param end: end resource id
        :return: list of ModelResourceLink
        :raise ApiManagerError:
        """
        manager = task_local.controller.manager
        link = manager.get_link_among_resources_internal(start, end)
        return link

    def get_link_among_resources(self, start, end):
        """[DEPRECATED]
        """
        return self.get_orm_link_among_resources(start, end)

    def update_orm_link(self, link_id, attributes):
        """Update links of a resource from orm

        :param link_id: link id
        :param attributes: attributes
        :return: list of ModelResourceLink
        :raise ApiManagerError:
        """
        manager = task_local.controller.manager
        res = manager.update_link(oid=link_id, attributes=attributes)
        return res

    def update_link(self, link_id, attributes):
        """[DEPRECATED]
        """
        return self.update_orm_link(link_id, attributes)


class ResourceJob(Job, AbstractResourceTask):
    """ResourceJob class. Use this class for task that execute create, update and delete of resources and childs.

    :param args: Free job params passed as list
    :param kwargs: Free job params passed as dict
    
    Example:
    
        .. code-block:: python
    
            @task_manager.task(bind=True, base=ResourceJob)
            @job(entity_class=OpenstackRouter, name='insert')
            def prova(self, objid, **kvargs):
                pass
    """
    abstract = True


class ResourceJobTask(JobTask, AbstractResourceTask):
    """ResourceJobTask class. Use this class for task that execute create, update and delete of resources and childs.
    
    :param args: Free job params passed as list
    :param kwargs: Free job params passed as dict 
    
    Example:
    
        .. code-block:: python
    
            @task_manager.task(bind=True, base=ResourceJobTask)
            @jobtask()
            def prova(self, options):
                pass            
    """
    abstract = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """This is run by the worker when the task fails.
        
        Parameters:
    
            exc - The exception raised by the task.
            task_id - Unique id of the failed task.
            args - Original arguments for the task that failed.
            kwargs - Original keyword arguments for the task that failed.
            einfo - ExceptionInfo instance, containing the traceback.
    
        The return value of this handler is ignored.
        """
        JobTask.on_failure(self, exc, task_id, args, kwargs, einfo)
        # get params from shared data
        params = self.get_shared_data()
        self.get_session()
    
        # get resource
        try:
            resource = self.get_resource(params.get('id'), details=False)
                    
            # update resource state
            resource.update_state(ResourceState.ERROR, error=str(exc))
        except ApiManagerError as ex:
            if ex.code == 404:
                self.logger.warning(ex)
            else:
                raise


#
# resource main job
#
def import_task(task_def):
    if isinstance(task_def, dict):
        components = task_def['task'].split('.')
        mod = __import__('.'.join(components[:-1]), globals(), locals(), [components[-1]], -1)
        func = getattr(mod, components[-1], None)

        task_def['task'] = import_func(task_def['task'])
        task = task_def
    else:
        logger.warning(task_def)
        task = import_func(task_def)
    return task


def job_helper(inst, objid, params):
    task_defs = params.pop('tasks')
    tasks = []
    for task_def in task_defs:
        if isinstance(task_def, list):
            sub_tasks = []
            for sub_task_def in task_def:
                sub_tasks.append(import_task(sub_task_def))
            tasks.append(sub_tasks)
        else:
            tasks.append(import_task(task_def))

    return Job.start(inst, tasks, params)


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Resource, name='create.insert', delta=4)
def job_resource_create(self, objid, params):
    """Create resource

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.objid: resource objid
    :param params.parent: resource parent id
    :param params.cid: container id
    :param params.name: resource name
    :param params.desc: resource desc
    :param params.ext_id: resource ext_id
    :param params.active: resource active
    :param params.attribute: attributes
    :param params.tags: comma separated resource tags to assign [default='']
    :param params.other:  ...
    :param params.tasks: list of task to execute. Set full module path for task. Task can be a string with task name or
        a dict like {'task':<task name>, 'args':..}
    :return: True
    """
    res = job_helper(self, objid, params)
    return res


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Resource, name='import.insert', delta=4)
def job_resource_import(self, objid, params):
    """Import resource

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.objid: resource objid
    :param params.parent: resource parent id
    :param params.cid: container id
    :param params.name: resource name
    :param params.desc: resource desc
    :param params.ext_id: resource ext_id
    :param params.active: resource active
    :param params.attribute: attributes
    :param params.tags: comma separated resource tags to assign [default='']
    :param params.resource_id: resource_id to import
    :param params.other:  ...
    :param params.tasks: list of task to execute. Set full module path for task. Task can be a string with task name or
        a dict like {'task':<task name>, 'args':..}
    :return: True
    """
    res = job_helper(self, objid, params)
    return res


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Resource, name='update.update', delta=4)
def job_resource_update(self, objid, params):
    """Update resource

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params {'cid':.., 'id':.., 'etx_id':..}
    :param params.cid: container id
    :param params.id: resource id
    :param params.uuid: resource uuid
    :param params.objid: resource objid
    :param params.ext_id: resource physical id
    :param params.tasks: list of task to execute. Set full module path for task. Task can be a string with task name or
        a dict like {'task':<task name>, 'args':..}
    :return: True
    """
    res = job_helper(self, objid, params)
    return res


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Resource, name='patch.update', delta=4)
def job_resource_patch(self, objid, params):
    """Patch resource

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params {'cid':.., 'id':.., 'etx_id':..}
    :param params.cid: container id
    :param params.id: resource id
    :param params.uuid: resource uuid
    :param params.objid: resource objid
    :param params.ext_id: resource physical id
    :param params.tasks: list of task to execute. Set full module path for task. Task can be a string with task name or
            a dict like {'task':<task name>, 'args':..}
    :return: True
    """
    res = job_helper(self, objid, params)
    return res


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Resource, name='remove.delete', delta=4)
def job_resource_expunge(self, objid, params):
    """Expunge resource

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params {'cid':.., 'id':.., 'etx_id':..}
    :param params.cid: container id
    :param params.id: resource id
    :param params.uuid: resource uuid
    :param params.objid: resource objid
    :param params.ext_id: resource physical id
    :param params.tasks: list of task to execute. Set full module path for task. Task can be a string with task name or
            a dict like {'task':<task name>, 'args':..}
    :return: True
    """
    res = job_helper(self, objid, params)
    return res


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Resource, name='action.update', delta=2)
def job_resource_action(self, objid, params):
    """Run resource action

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.ext_id: resource physical id
    :param params.tasks: list of task to execute. Set full module path for task. Task can be a string with task name or
            a dict like {'task':<task name>, 'args':..}
    :return: True
    """
    res = job_helper(self, objid, params)
    return res


#
# crud task
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def create_resource_pre(self, options):
    """Create resource in beehive - PRE TASK
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.objid: objid of the resource. Ex. 110//2222//334//*
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.parent: resource parent
    :param sharedarea.ext_id: physical id
    :param sharedarea.active: active
    :param sharedarea.attribute: attribute
    :param sharedarea.tags: list of tags to add
    :return: uuid of the created resource
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid')
    tags = params.get('tags')

    self.get_session()

    # get resource
    resource = self.get_resource(oid, details=False)
    # update resource state
    resource.update_state(ResourceState.BUILDING)
    self.update('PROGRESS', msg='Update resource %s state to %s' % (uuid, ResourceState.BUILDING))
    # add tags
    if tags is not None and tags != '':
        for tag in tags.split(','):
            try:
                resource.controller.add_tag(value=tag)
                self.update('PROGRESS', msg='Add resource tag %s' % tag)
            except ApiManagerError as ex:
                self.update('PROGRESS', msg='WARN: %s' % ex)
                self.logger.warning(ex)
            try:
                resource.add_tag(tag)
                self.update('PROGRESS', msg='Assign resource tag %s' % tag)
            except ApiManagerError as ex:
                self.update('PROGRESS', msg='WARN: %s' % ex)
                self.logger.warning(ex)

    # add tags
    for tag in tags:
        resource.add_tag(tag)
        self.update('PROGRESS', msg='Add resource tag %s' % tag)

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def create_resource_post(self, options):
    """Create resource in beehive database - POST TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.objid: objid of the resource. Ex. 110//2222//334//*
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.parent: resource parent
    :param sharedarea.ext_id: physical id
    :param sharedarea.active: active
    :param sharedarea.attribute: attribute
    :param sharedarea.tags: list of tags to add
    :return: uuid of the created resource
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid')
    ext_id = params.get('ext_id', None)
    attribute = params.get('attrib', None)

    # get container
    self.get_session()
    resource = self.get_resource(oid, details=False)
    
    # update resource
    resource.update_internal(active=True, attribute=attribute, ext_id=ext_id, state=ResourceState.ACTIVE)
    self.update('PROGRESS', msg='Update resource %s' % uuid)

    params['result'] = uuid
    self.set_shared_data(params)
    self.update('PROGRESS', msg='Update shared area')

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def update_resource_pre(self, options):
    """Update resource in beehive database - PRE TASK
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.parent: resource parent
    :param sharedarea.ext_id: physical id
    :param sharedarea.active: active
    :param sharedarea.attribute: attribute
    :return: uuid of the updated resource
    """
    # get params from shared data
    params = self.get_shared_data()
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid') 
    objid = params.get('objid')
    name = params.get('name', None)
    desc = params.get('desc', None)
    active = params.get('active', None)
    attrib = params.get('attribute', None)
    ext_id = params.get('ext_id', None)
    if attrib is not None:
        attrib = jsonDumps(attrib)
    
    # create session
    self.get_session()
    
    # get container
    resource = self.get_resource(oid, details=False)
    
    # update resource
    resource.update_internal(active=active, attribute=attrib, name=name, desc=desc, ext_id=ext_id,
                             state=ResourceState.UPDATING)
    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def update_resource_post(self, options):
    """Update resource in beehive database - POST TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.parent: resource parent
    :param sharedarea.ext_id: physical id
    :param sharedarea.active: active
    :param sharedarea.attribute: attribute
    :return: uuid of the updated resource
    """
    # get params from shared data
    params = self.get_shared_data()    
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid') 
    objid = params.get('objid')
    name = params.get('name', None)
    desc = params.get('desc', None)
    active = params.get('active', None)
    attrib = params.get('attribute', None)
    ext_id = params.get('ext_id', None)
    if attrib is not None:
        attrib = jsonDumps(attrib)
    
    # create session
    self.get_session()
    
    # get container
    resource = self.get_resource(oid, details=False)

    # update resource
    resource.update_internal(active=True, attribute=attrib, state=ResourceState.ACTIVE)
    self.update('PROGRESS', msg='Update resource %s' % uuid)

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def patch_resource_pre(self, options):
    """Patch resource in beehive database - PRE TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.parent: resource parent
    :param sharedarea.ext_id: physical id
    :param sharedarea.active: active
    :param sharedarea.attribute: attribute
    :return: uuid of the patchd resource
    """
    # get params from shared data
    params = self.get_shared_data()
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid')
    objid = params.get('objid')
    name = params.get('name', None)
    desc = params.get('desc', None)
    active = params.get('active', None)
    attrib = params.get('attribute', None)
    ext_id = params.get('ext_id', None)
    if attrib is not None:
        attrib = jsonDumps(attrib)

    # create session
    self.get_session()

    # get container
    resource = self.get_resource(oid, details=False)

    # patch resource
    resource.update_internal(active=False, state=ResourceState.UPDATING)
    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def patch_resource_post(self, options):
    """Patch resource in beehive database - POST TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.parent: resource parent
    :param sharedarea.ext_id: physical id
    :param sharedarea.active: active
    :param sharedarea.attribute: attribute
    :return: uuid of the patchd resource
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid')
    objid = params.get('objid')
    name = params.get('name', None)
    desc = params.get('desc', None)
    active = params.get('active', None)
    attrib = params.get('attribute', None)
    ext_id = params.get('ext_id', None)
    if attrib is not None:
        attrib = jsonDumps(attrib)

    # create session
    self.get_session()

    # get container
    resource = self.get_resource(oid, details=False)

    # patch resource
    resource.update_internal(active=True, state=ResourceState.ACTIVE)
    self.update('PROGRESS', msg='Patch resource %s' % uuid)

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def expunge_resource_pre(self, options):
    """Hard delete resource from beehive database - PRE TASK
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :return: uuid of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid') 
    objid = params.get('objid')
    ext_id = params.get('ext_id')
    
    # get resource
    self.get_session()
    container = self.get_container(cid)
    container.update_resource_state(oid, state=ResourceState.EXPUNGING)
    self.update('PROGRESS', msg='Expunging resource %s' % uuid)
        
    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def expunge_resource_post(self, options):
    """Hard delete resource from beehive database - POST TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :return: uuid of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid') 
    objid = params.get('objid')
    ext_id = params.get('ext_id')
    
    # get resource
    self.get_session()
    resource = self.get_resource(oid, details=False)
    
    # delete resource
    resource.expunge_internal()
    self.update('PROGRESS', msg='Expunge resource %s' % resource.uuid)
    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def action_resource_pre(self, options):
    """Run action on a resource - PRE TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.action_name: action name
    :return: uuid of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid')
    objid = params.get('objid')
    ext_id = params.get('ext_id')
    action_name = params.get('action_name')

    self.update('PROGRESS', msg='Run action %s on resource %s' % (action_name, uuid))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def action_resource_post(self, options):
    """Run action on a resource - POST TASK

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.uuid: resource uuid
    :param sharedarea.objid: resource objid
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.action_name: action name
    :return: uuid of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get('cid')
    oid = params.get('id')
    uuid = params.get('uuid')
    objid = params.get('objid')
    ext_id = params.get('ext_id')
    action_name = params.get('action_name')

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def delete_resource_list(self, options):
    """Remove resource list from beehive database.
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea: params read as dict from job shared area stored in redis
    :param sharedarea.cid: container id
    :param sharedarea.ids: resource id list
    :return: id list of the removed resource
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oids = params.get('ids')
    
    # get resource
    self.get_session()
    
    for oid in oids:
        resource = self.get_resourece(oid)
        resource.update_state(ResourceState.EXPUNGING)
        
        # delete resource
        resource.expunge()
        self.update('PROGRESS', msg='Delete resource %s' % resource.uuid)
    return oids


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def delete_resourcelink_list(self, options):
    """Remove resource link list from beehive database.
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea: params read as dict from job shared area stored in redis
    :param sharedarea.cid: container id
    :param sharedarea.ids: resource link id list
    :return: id list of the removed resource link
    """
    # get params from shared data
    params = self.get_shared_data()
    
    # validate input params
    cid = params.get('cid')
    oids = params.get('ids')
    
    # get resource
    self.get_session()
    
    for oid in oids:
        link = self.get_link(oid)

        # delete resource
        link.expunge()
        self.update('PROGRESS', msg='Delete resource link %s' % oid)
    return oids


#
# discover tasks and job
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def discover_new_entities(self, options, objdef):
    """Register new entity in remote platform.
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param objdef: resource objdef.
    :param sharedarea:
    :param sharedarea.cid: container id        
    :return: list of tuple (resource uuid, resource class)
    """
    self.update('PROGRESS', msg='Get resource objdef %s' % objdef)
    
    # get params from shared data
    params = self.get_shared_data()
    self.update('PROGRESS', msg='Get shared area')    
    
    # open db session
    operation.perms = []
    self.get_session()
    
    # get container
    cid = params.get('cid')
    # module = self.app.api_manager.modules['ResourceModule']
    # controller = module.get_controller()
    # container = controller.get_container(cid)
    # # container.get_connection()
    container = self.get_container(cid)
    self.update('PROGRESS', msg='Get container %s' % container)
    
    items = container.discover_new_entities(objdef)
    self.update('PROGRESS', msg='Discover new entities: %s' % len(items))  
    
    res = []
    
    for item in items:
        resclass = item[0]
        ext_id = item[1]
        name = item[4]
        
        resource = resclass.synchronize(container, item)
        self.update('PROGRESS', msg='Call resource %s synchronize method' % (resclass.objdef))

        # add resource reference in db
        model = container.add_resource(**resource)
        container.update_resource_state(model.id, ResourceState.ACTIVE)
        container.activate_resource(model.id)
        res.append((model.id, resclass.objdef))
        self.update('PROGRESS', msg='Add new resource: (%s, %s)' % (name, ext_id))

    logger.info('Discover container %s %s resources: %s' % (cid, objdef, truncate(res)))
    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def discover_died_entities(self, options, objdef):
    """Discover died/changed entities
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param objdef: resource objdef.
    :param sharedarea:
    :param sharedarea.cid: container id        
    :return: list of tuple (resource uuid, resource class)
    """
    self.update('PROGRESS', msg='Get resource objdef %s' % objdef)
    
    # get params from shared data
    params = self.get_shared_data()
    self.update('PROGRESS', msg='Get shared area')
    
    # validate input params
    cid = params.get('cid')
    died = params.get('died', True)
    changed = params.get('changed', True)    
    
    res = {'died': [], 'changed': []}
    
    # open db session
    self.get_session()    
    
    # get container
    # module = self.app.api_manager.modules['ResourceModule']
    # controller = module.get_controller()
    # container = controller.get_container(cid)
    # # container.get_connection()
    container = self.get_container(cid)
    self.update('PROGRESS', msg='Get container %s' % container)
    
    # get resources
    resources = container.discover_died_entities(objdef)

    # remove died resources
    if died is True:
        self.update('PROGRESS', msg='Get died entities: %s' % truncate(resources['died']))
        for r in resources['died']:
            # remove from beehive
            r.expunge_internal()
    
            obj = {'id': r.oid, 'name': r.name, 'extid': r.ext_id}
            res['died'].append(obj)
            logger.debug('Resource %s will be deleted.' % obj)

            self.update('PROGRESS', msg='Delete resource %s' % obj)

    # update changed resources
    if changed is True:
        self.update('PROGRESS', msg='Get changed entities: %s' % truncate(resources['changed']))
        for r in resources['changed']:
            r.update_state(ResourceState.UPDATING)
            params = {'name': r.name, 'desc': r.desc}
            r.update_internal(**params)    
    
            obj = {'id': r.oid, 'name': r.name, 'extid': r.ext_id}
            res['changed'].append(obj)
            r.update_state(ResourceState.ACTIVE)
            logger.debug('Resource %s will be changed.' % obj)
    
            self.update('PROGRESS', msg='Update resource %s' % obj)

    return res


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Orchestrator, name='discover.update', delta=2)
def job_synchronize_container(self, objid, params):
    """Synchronize remote platform entities

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param cid: container id        
    :param params: Params required        
    :param params.cid: container id
    :param params.types: List of resource objdef. If empty use all the available objdef.
    :param params.new: if True discover new entity
    :param params.died: if True remove orphaned resources
    :param params.changed: if True update changed resources        
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)
    cid = params.get('cid')
    
    # open db session
    self.get_session()    
    
    # get container
    module = self.app.api_manager.modules['ResourceModule']
    controller = module.get_controller()
    container = controller.get_container(cid, cache=False)
    container.get_connection()
    
    # get resource classes
    resource_types = params.get('types', None)
    new = params.get('new', True)
    died = params.get('died', True)
    changed = params.get('changed', True)

    resource_objdefs = []
    if resource_types is None:
        for resource_class in container.child_classes:
            resource_objdefs.append(resource_class.objdef)
    else:
        types = resource_types.split(',')
        for t in types: 
            resource_objdefs.append(t)
    
    g_discover = []
    for objdef in resource_objdefs:
        if new is True:
            g_discover.append(discover_new_entities.signature((ops, objdef), immutable=True,
                                                              queue=task_manager.conf.TASK_DEFAULT_QUEUE))
        if died is True or changed is True:
            g_discover.append(discover_died_entities.signature((ops, objdef), immutable=True,
                                                               queue=task_manager.conf.TASK_DEFAULT_QUEUE))

    Job.create([
        end_task,
        g_discover,
        start_task,
    ], ops).delay()    
    return True