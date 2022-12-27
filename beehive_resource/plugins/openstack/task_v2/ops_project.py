# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.model import ResourceState
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.entity.ops_security_group import OpenstackSecurityGroup
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class ProjectTask(AbstractResourceTask):
    """Project task
    """
    name = 'project_task'
    entity_class = OpenstackProject

    @staticmethod
    @task_step()
    def project_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        name = params.get('name')
        description = params.get('desc')
        parent_extid = params.get('parent_extid')
        domain_ext_id = params.get('domain_ext_id')
        is_domain = params.get('is_domain')
        enabled = params.get('enabled')

        container = task.get_container(cid)
        conn = container.conn
        domain_name = domain_ext_id.split('-')[1]
        task.progress(step_id, msg='Get project domain')

        # create openstack project
        inst = conn.project.create(name, domain_name, is_domain=is_domain, parent_id=parent_extid,
                                   description=description, enabled=enabled)

        # assign admin role to project
        user = conn.identity.user.list(name='admin')[0]
        role_admin = conn.identity.role.list(name='admin')[0]
        role_trilio = conn.identity.role.list(name='trilio_backup_role')[0]
        conn.project.assign_member(inst['id'], user['id'], role_admin['id'])
        task.progress(step_id, msg='Assign admin role for project %s to admin user' % inst['id'])
        conn.project.assign_member(inst['id'], user['id'], role_trilio['id'])
        task.progress(step_id, msg='Assign trilio_backup_role role for project %s to admin user' % inst['id'])

        # save current data in shared area
        params['ext_id'] = inst['id']

        return oid, params

    @staticmethod
    @task_step()
    def project_register_securitygroup_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: security group id, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        description = params.get('desc')
        objid = params.get('objid')
        ext_id = params.get('ext_id')

        container = task.get_container(cid)
        conn = container.conn
    
        # get default security group
        sg = conn.network.security_group.list(tenant=ext_id)[0]
    
        # create default security group resource
        default_sg_objid = '%s//%s' % (objid, id_gen())
        desc = '%s default security group' % description
        model = container.add_resource(objid=default_sg_objid, name=sg['name'], resource_class=OpenstackSecurityGroup,
                                       ext_id=sg['id'], active=True, desc=desc, attrib=None, parent=oid)
        container.update_resource_state(model.id, ResourceState.ACTIVE)
    
        task.progress(step_id, msg='Register security group %s' % sg['name'])
    
        return sg['id'], params

    @staticmethod
    @task_step()
    def project_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        return oid, params

    @staticmethod
    @task_step()
    def project_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        # delete vsphere folder
        if resource.is_ext_id_valid() is True:
            try:
                # check project exists
                conn.project.get(oid=resource.ext_id)

                # delete openstack project
                conn.project.delete(resource.ext_id)
                task.progress(step_id, msg='Delete project %s' % resource.ext_id)
            except:
                pass

        return oid, params

    @staticmethod
    @task_step()
    def project_deregister_securitygroup_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')

        container = task.get_container(cid)
        conn = container.conn
        resource = task.get_resource(oid)
    
        sgs, tot = resource.get_security_groups()
        for sg in sgs:
            # delete remote entity
            if task.is_ext_id_valid(sg.ext_id) is True:
                try:
                    container.conn.network.security_group.get(sg.ext_id)
                except:
                    task.progress(step_id, msg='Security group %s does not already exist' % sg.ext_id)
                    return None
    
                conn.network.security_group.delete(sg.ext_id)
                task.progress(step_id, msg='Remove security group %s from openstack' % sg.ext_id)
    
            # delete resource
            sg.expunge_internal()
            task.progress(step_id, msg='Remove security group %s' % sg.uuid)
    
        return oid, params

    @staticmethod
    @task_step()
    def project_add_backup_restore_point(task, step_id, params, *args, **kvargs):
        """add physical backup restore point

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: restore point id, params
        """
        oid = params.get('id')
        cid = params.get('cid')
        job_id = params.get('restore_point_job_id')
        name = params.get('restore_point_name')
        desc = params.get('restore_point_desc')
        full = params.get('restore_point_full')

        from beehive_resource.plugins.openstack.controller import OpenstackContainer
        from beedrones.openstack.client import OpenstackManager

        # project = task.get_resource(oid)
        # job = project.get_backup_job()
        abstractResourceTask: AbstractResourceTask = task
        # openstackContainer: OpenstackContainer = abstractResourceTask.get_container(cid, projectid=oid)
        openstackContainer: OpenstackContainer = abstractResourceTask.get_simple_container(cid)
        openstackManager: OpenstackManager = openstackContainer.get_connection(projectid=oid)
        trilio_conn = openstackContainer.get_trilio_connection(openstackManager)

        restore_point = trilio_conn.snapshot.add(job_id, name=name, desc=desc, full=full)
        restore_point_id = restore_point['id']
        trilio_conn.snapshot.wait_for_status(restore_point_id, final_status='available')
        task.progress(step_id, msg='create restore point %s' % restore_point_id)
        return restore_point_id, params

    @staticmethod
    @task_step()
    def project_del_backup_restore_point(task, step_id, params, *args, **kvargs):
        """delete physical backup restore point

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get('id')
        cid = params.get('cid')
        # job_id = params.get('restore_point_job_id')
        restore_point_id = params.get('restore_point_id')
        abstractResourceTask: AbstractResourceTask = task

        # container = abstractResourceTask.get_container(cid, projectid=oid)
        # trilio_conn = container.get_trilio_connection()

        from beehive_resource.plugins.openstack.controller import OpenstackContainer
        from beedrones.openstack.client import OpenstackManager

        openstackContainer: OpenstackContainer = abstractResourceTask.get_simple_container(cid)
        openstackManager: OpenstackManager = openstackContainer.get_connection(projectid=oid)
        trilio_conn = openstackContainer.get_trilio_connection(openstackManager)

        trilio_conn.snapshot.delete(restore_point_id)
        trilio_conn.snapshot.wait_for_status(restore_point_id, final_status='deleted')
        task.progress(step_id, msg='delete restore point %s' % restore_point_id)
        return restore_point_id, params


task_manager.tasks.register(ProjectTask())
