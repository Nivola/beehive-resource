# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from celery.utils.log import get_task_logger
from celery import chain, chord, group, signature
from beecell.simple import get_value, import_class, id_gen
from beehive_resource.tasks import ResourceJobTask, ResourceJob,\
    create_resource_pre, create_resource_post, expunge_resource_pre,\
    expunge_resource_post, update_resource_post, update_resource_pre
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beedrones.openstack.client import OpenstackNotFound
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from beehive_resource.plugins.openstack.entity.ops_security_group import OpenstackSecurityGroup
from beehive_resource.model import ResourceState

logger = get_task_logger(__name__)

#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_project_create_entity(self, options):
    """Create openstack project

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return:
    """
    # get params from shared data
    params = self.get_shared_data()
    cid = params.get('cid')
    name = params.get('name')
    description = params.get('desc')
    parent_extid = params.get('parent_extid')
    domain_ext_id = params.get('domain_ext_id')
    is_domain = params.get('is_domain')
    enabled = params.get('enabled')
    self.progress('Get configuration params')
    
    # get container
    self.get_session()    
    container = self.get_container(cid)
    conn = container.conn
    domain_name = domain_ext_id.split('-')[1]
    self.progress('Get project domain')
    
    # create openstack project
    inst = conn.project.create(name, domain_name, is_domain=is_domain, parent_id=parent_extid, description=description, 
                               enabled=enabled)
    
    # assign admin role to project
    user = conn.identity.user.list(name='admin')[0]
    role_admin = conn.identity.role.list(name='admin')[0]
    role_trilio = conn.identity.role.list(name='trilio_backup_role')[0]    
    conn.project.assign_member(inst['id'], user['id'], role_admin['id'])
    self.progress('Assign admin role for project %s to admin user' % inst['id'])
    conn.project.assign_member(inst['id'], user['id'], role_trilio['id'])
    self.progress('Assign trilio_backup_role role for project %s to admin user' % inst['id'])
    
    # save current data in shared area
    params['ext_id'] = inst['id']
    #params['attrib'] = level
    self.set_shared_data(params)    

    # update task
    self.update('PROGRESS')
    return inst['id']


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_project_register_securitygroup(self, options):
    """Create openstack project default security group resource

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return:
    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress('Get shared area')
    
    # get input params
    cid = params.get('cid')
    oid = params.get('id')
    description = params.get('desc')
    objid = params.get('objid')
    ext_id = params.get('ext_id')
    self.progress('Get configuration params')
    
    # get container
    self.get_session()    
    container = self.get_container(cid)
    conn = container.conn

    # get default security group
    sg = conn.network.security_group.list(tenant=ext_id)[0]
    
    # create default security group resource
    default_sg_objid = '%s//%s' % (objid, id_gen())
    desc = '%s default security group' % description
    model = container.add_resource(
        objid=default_sg_objid, name=sg['name'],
        resource_class=OpenstackSecurityGroup, ext_id=sg['id'], active=True, 
        desc=desc, attrib=None, parent=oid)
    container.update_resource_state(model.id, ResourceState.ACTIVE)

    self.progress('Register security group %s' % sg['name'])
    
    return sg['id']


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_project_update_entity(self, options):
    """Update openstack project

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return:
    """
    # get params from shared data
    params = self.get_shared_data()
    cid = params.get('cid')
    oid = params.get('id')
    name = params.get('name')
    description = params.get('description')
    domain_id = params.get('domain_id')
    parent_id = params.get('parent_id')
    is_domain = params.get('is_domain')
    enabled = params.get('enabled')
    self.progress('Get configuration params')

    # get openstack project
    self.get_session()
    container = self.get_container(cid)
    resource = self.get_resource(oid)

    self.set_shared_data(params)
    self.progress('Update shared area')
    return resource.ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_project_delete_entity(self, options):
    """Delete openstack project
     
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return:    
    """
    # get params from shared data
    params = self.get_shared_data()
    cid = params.get('cid')
    #id = params.get('id')
    ext_id = params.get('ext_id')
    self.progress('Get configuration params')
    
    # get container
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn
    self.progress('Get container %s' % cid)

    if self.is_ext_id_valid(ext_id) is False:
        logger.warn('Remote project %s not found' % ext_id)
        self.progress('Remote project %s not found' % ext_id)        
    else:
        try:
            # get project
            conn.project.get(oid=ext_id)
                
            # delete openstack project
            conn.project.delete(ext_id)
            self.progress('Delete remote project %s' % ext_id)
        except OpenstackNotFound:
            logger.warn('Remote project %s not found' % ext_id)
            self.progress('Remote project %s not found' % ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_project_deregister_securitygroup(self, options):
    """Delete openstack project associated security group
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return:    
    """
    # get params from shared data
    params = self.get_shared_data()
    cid = params.get('cid')
    oid = params.get('id')
    # sgs = params.get('sgs')
    self.progress('Get configuration params')
    
    # get container
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn
    resource = self.get_resource(oid)
    self.progress('Get container %s' % cid)

    sgs, tot = resource.get_security_groups()
    for sg in sgs:
        # delete remote entity
        if self.is_ext_id_valid(sg.ext_id) is True:
            try:
                container.conn.network.security_group.get(sg.ext_id)
            except:
                self.progress('Security group %s does not already exist' % sg.ext_id)
                return None

            conn.network.security_group.delete(sg.ext_id)
            self.progress('Remove security group %s from openstack' % sg.ext_id)

        # delete resource
        sg.expunge_internal()
        self.progress('Remove security group %s' % sg.uuid)

    return True

# #
# # JOB
# #
# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=OpenstackProject, name='insert', delta=2)
# def job_project_create(self, objid, params):
#     """Create openstack project
#
#     **Parameters:**
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **objid**: resource objid
#             * **parent**: resource parent id
#             * **cid**: container id
#             * **name**: resource name
#             * **desc**: resource desc
#             * **ext_id**: resource ext_id
#             * **active**: resource active
#             * **attribute** (:py:class:`dict`): attributes
#             * **tags**: comma separated resource tags to assign [default='']
#             * **domain_id**: parent domain id or uuid
#             * **enabled**: True if enable [default=True]
#             * **is_domain**: parent domain id or uuid [default=False]
#
#     **Returns:**
#
#         True
#     """
#     ops = self.get_options()
#     self.set_shared_data(params)
#
#     Job.create([
#         end_task,
#         create_resource_post,
#         task_project_register_securitygroup,
#         task_project_create_entity,
#         create_resource_pre,
#         start_task
#     ], ops).delay()
#     return True
#
#
# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=OpenstackProject, name='update', delta=2)
# def job_project_update(self, objid, params):
#     """Update openstack project.
#     TODO
#
#     **Parameters:**
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **cid** (int): container id
#             * **id** (int): resource id
#             * **uuid** (uuid): resource uuid
#             * **objid** (str): resource objid
#             * **ext_id** (str): physical id
#
#     **Returns:**
#
#         True
#     """
#     ops = self.get_options()
#     self.set_shared_data(params)
#
#     Job.create([
#         end_task,
#         update_resource_post,
#         task_project_update_entity,
#         update_resource_pre,
#         start_task
#     ], ops).delay()
#     return True
#
#
# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=OpenstackProject, name='delete', delta=2)
# def job_project_delete(self, objid, params):
#     """Delete openstack project.
#
#     **Parameters:**
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **cid** (int): container id
#             * **id** (int): resource id
#             * **uuid** (uuid): resource uuid
#             * **objid** (str): resource objid
#             * **ext_id** (str): resource physical id
#
#     **Returns:**
#
#         True
#     """
#     ops = self.get_options()
#     self.set_shared_data(params)
#
#     Job.create([
#         end_task,
#         expunge_resource_post,
#         task_project_delete_entity,
#         task_project_deregister_securitygroup,
#         expunge_resource_pre,
#         start_task
#     ], ops).delay()
#     return True
