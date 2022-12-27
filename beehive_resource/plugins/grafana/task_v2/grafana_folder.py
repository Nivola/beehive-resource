# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import logging
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder
from beehive_resource.plugins.grafana.controller import GrafanaContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager

logger = logging.getLogger(__name__)


class GrafanaFolderTask(AbstractResourceTask):
    """GrafanaFolder task
    """
    name = 'grafana_folder_task'
    entity_class = GrafanaFolder

    @staticmethod
    @task_step()
    def grafana_folder_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug('+++++ grafana_folder_create_physical_step')
        
        cid = params.get('cid') # container id
        oid = params.get('id')
        logger.debug('+++++ cid: %s' % cid)
        logger.debug('+++++ oid: %s' % oid)
        
        # folder_id = params.get('folder_id')
        name = params.get('name')
        desc = params.get('desc')

        # logger.debug('folder_id: %s: ' % folder_id)
        logger.debug('+++++ name: %s' % name)
        logger.debug('+++++ desc: %s' % desc)
        
        task.progress(step_id, msg='Get configuration params')

        container: GrafanaContainer
        container = task.get_container(cid)
        conn_grafana = container.conn_grafana

        inst_id = None
        try:
            # controllare se esiste l'oggetto prima di crearlo 
            remote_entities = conn_grafana.folder.search(name)
            remote_entity = remote_entities[0]
            inst_id = remote_entity['uid']
            task.progress(step_id, msg=' Grafana folder %s already exist - inst_id: %s' % (name, inst_id))
        except:
            task.progress(step_id, msg=' Grafana folder %s does not exist yet' % name)
            inst = conn_grafana.folder.add(folder_name=name)
            logger.debug('+++++ inst: %s' % inst)
            inst_id = inst['uid']
            task.progress(step_id, msg=' Grafana folder created: %s' % inst_id)

        # save current data in shared area
        params['ext_id'] = inst_id
        params['attrib'] = {}
        task.progress(step_id, msg='Update shared area')

        return oid, params

    @staticmethod
    @task_step()
    def grafana_folder_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def grafana_folder_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug('+++++ grafana_folder_delete_physical_step')

        cid = params.get('cid')
        oid = params.get('id')
        logger.debug('+++++ cid %s: ' % cid)
        logger.debug('+++++ oid %s: ' % oid)

        container: GrafanaContainer
        container = task.get_container(cid)
        conn_grafana = container.conn_grafana
        resource = container.get_simple_resource(oid)
        logger.debug('+++++ resource.ext_id: %s: ' % resource.ext_id)

        if resource.is_ext_id_valid() is True:
            try:
                # check if folder exists
                conn_grafana.folder.get(folder_uid=resource.ext_id)
                # delete folder
                conn_grafana.folder.delete(folder_uid=resource.ext_id)
                task.progress(step_id, msg=' Grafana folder deleted %s' % resource.ext_id)
            except:
                task.progress(step_id, msg=' Grafana folder %s does not exist anymore' % resource.ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def add_dashboard_step(task, step_id, params, *args, **kvargs):
        """Add server dashboard

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        def add_dashboard_action(conn, cid, oid, ext_id, params):
            logger.debug('add_dashboard_action - params={}'.format(params))

            container: GrafanaContainer
            container = task.get_container(cid)
            conn_grafana = container.conn_grafana
            
            # conn_grafana.folder.add_dashboard(params['folder_id_from'], params['dashboard'], params['folder_id_to'], params['index_pattern'])
            dashboard_to_search = params['dashboard_to_search']
            folder_uid_to = params['folder_uid_to']
            dash_tag = params['dash_tag']

            organization = params['organization']
            division = params['division']
            account = params['account']
            
            res_folder = conn_grafana.folder.get(folder_uid_to)
            folder_id_to = res_folder['id']
            conn_grafana.dashboard.add_dashboard(dashboard_to_search, folder_id_to, organization, division, account, dash_tag)

        logger.debug('add_dashboard_step - params={}'.format(params))
        res = GrafanaFolderTask.folder_action(task, step_id, add_dashboard_action, 'Add dashboard',
                                        'Error adding dashboard', params)
        return res, params

    @staticmethod
    @task_step()
    def add_permission_step(task, step_id, params, *args, **kvargs):
        """Add permission

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        def add_permission_action(conn, cid, oid, ext_id, params):
            logger.debug('add_permission_action - params={}'.format(params))

            container: GrafanaContainer
            container = task.get_container(cid)
            conn_grafana = container.conn_grafana
            
            # conn_grafana.folder.add_permission(params['folder_id_from'], params['permission'], params['folder_id_to'], params['index_pattern'])
            folder_uid = params['folder_uid']
            team_viewer = params['team_viewer']
            team_editor = params['team_editor']

            team_viewer_id = None
            if team_viewer is not None:
                remote_entities = conn_grafana.team.get_by_name(team_viewer)
                if len(remote_entities) > 0:
                    remote_entity = remote_entities[0]
                    team_viewer_id = remote_entity['id']
            logger.debug('+++++ add_permission_action - team_viewer_id={}'.format(team_viewer_id))

            team_editor_id = None
            if team_editor is not None:
                remote_entities = conn_grafana.team.get_by_name(team_editor)
                if len(remote_entities) > 0:
                    remote_entity = remote_entities[0]
                    team_editor_id = remote_entity['id']
            logger.debug('+++++ add_permission_action - team_editor_id={}'.format(team_editor_id))

            conn_grafana.folder.add_permission(folder_uid, team_viewer_id, team_editor_id)

        logger.debug('add_permission_step - params={}'.format(params))
        res = GrafanaFolderTask.folder_action(task, step_id, add_permission_action, 'Add permission',
                                        'Error adding permission', params)
        return res, params

    #
    # action
    #
    @staticmethod
    def folder_action(task, step_id, action, success, error, params):
        """Execute a server action
    
        :param task: celery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param params: input params
        :return: ext_id
        :raise:
        """
        logger.debug('folder_action')
        task.progress(step_id, msg='start action %s' % action.__name__)
        cid = params.get('cid')
        oid = params.get('id')
        ext_id = params.get('ext_id')

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg='Get container %s' % cid)
    
        # execute action
        vs_task = action(conn, cid, oid, ext_id, params)
        if vs_task is not None:
            container.query_remote_task(task, step_id, vs_task, error=error)

        # update cache
        server_obj = task.get_resource(oid)
        server_obj.set_cache()

        task.progress(step_id, msg=success)
        task.progress(step_id, msg='stop action %s' % action.__name__)
        return True
        

task_manager.tasks.register(GrafanaFolderTask())
