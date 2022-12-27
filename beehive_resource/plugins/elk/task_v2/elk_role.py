# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import logging
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.elk.entity.elk_role import ElkRole
from beehive_resource.plugins.elk.controller import ElkContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager


class ElkRoleTask(AbstractResourceTask):
    """ElkRole task
    """
    name = 'elk_role_task'
    entity_class = ElkRole

    @staticmethod
    @task_step()
    def elk_role_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger = logging.getLogger(__name__)
        logger.debug('+++++ elk_role_create_physical_step')

        cid = params.get('cid') #container id
        oid = params.get('id')
        
        # role_id = params.get('role_id')
        name = params.get('name')
        role_name = name
        # desc = params.get('desc')
        indice = params.get('indice')
        space_id = params.get('space_id')
        
        task.progress(step_id, msg='Get configuration params')

        container: ElkContainer
        container = task.get_container(cid)
        conn_kibana = container.conn_kibana

        inst_id = role_name
        try:
            # controllare se esiste l'oggetto prima di crearlo 
            remote_entity = conn_kibana.role.get(role_name)
            task.progress(step_id, msg=' -+-+- Elk role %s already exist ' % role_name)
        except:
            task.progress(step_id, msg=' -+-+- Elk role %s does not exist yet' % role_name)
            inst = conn_kibana.role.add(role_name, indice, space_id)
            # inst_id = inst['id']
            task.progress(step_id, msg=' -+-+- Elk role created %s' % inst_id)

        # save current data in shared area
        params['ext_id'] = inst_id
        params['attrib'] = {}
        task.progress(step_id, msg='Update shared area')

        return oid, params

    @staticmethod
    @task_step()
    def elk_role_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get('id')
        return oid, params

    @staticmethod
    @task_step()
    def elk_role_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')

        container: ElkContainer
        container = task.get_container(cid)
        conn_kibana = container.conn_kibana
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check if role exists
                conn_kibana.role.get(resource.ext_id)
                # delete role
                conn_kibana.role.delete(resource.ext_id)
                task.progress(step_id, msg='Elk role deleted %s' % resource.ext_id)
            except:
                task.progress(step_id, msg='Elk role %s does not exist anymore' % resource.ext_id)

        return oid, params

task_manager.tasks.register(ElkRoleTask())