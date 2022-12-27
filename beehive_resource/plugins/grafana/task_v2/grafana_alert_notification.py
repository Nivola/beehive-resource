# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import logging
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.grafana.entity.grafana_alert_notification import GrafanaAlertNotification
from beehive_resource.plugins.grafana.controller import GrafanaContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager

logger = logging.getLogger(__name__)


class GrafanaAlertNotificationTask(AbstractResourceTask):
    """GrafanaAlertNotification task
    """
    name = 'grafana_alert_notification_task'
    entity_class = GrafanaAlertNotification

    @staticmethod
    @task_step()
    def grafana_alert_notification_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug('+++++ grafana_alert_notification_create_physical_step')
        
        cid = params.get('cid') # container id
        oid = params.get('id')
        logger.debug('+++++ cid: %s' % cid)
        logger.debug('+++++ oid: %s' % oid)
        
        # alert_notification_id = params.get('alert_notification_id')
        name = params.get('name')
        desc = params.get('desc')
        email = params.get('email')

        # logger.debug('alert_notification_id: %s: ' % alert_notification_id)
        logger.debug('+++++ name: %s' % name)
        logger.debug('+++++ desc: %s' % desc)
        logger.debug('+++++ email: %s' % email)
        
        task.progress(step_id, msg='Get configuration params')

        container: GrafanaContainer
        container = task.get_container(cid)
        conn_grafana = container.conn_grafana

        inst_id = None
        try:
            # controllare se esiste l'oggetto prima di crearlo 
            remote_entity = conn_grafana.alert_notification.get_by_name(name)
            # remote_entity = remote_entities[0]
            inst_id = remote_entity['uid']
            task.progress(step_id, msg=' Grafana alert_notification %s already exist - inst_id: %s' % (name, inst_id))
        except:
            task.progress(step_id, msg=' Grafana alert_notification %s does not exist yet' % name)
            inst = conn_grafana.alert_notification.add(alert_name=name, email=email)
            logger.debug('+++++ inst: %s' % inst)
            inst_id = inst['uid']
            task.progress(step_id, msg=' Grafana alert_notification created: %s' % inst_id)

        # save current data in shared area
        params['ext_id'] = inst_id
        params['attrib'] = {}
        task.progress(step_id, msg='Update shared area')

        return oid, params

    @staticmethod
    @task_step()
    def grafana_alert_notification_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def grafana_alert_notification_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug('+++++ grafana_alert_notification_delete_physical_step')

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
                # check if alert_notification exists
                conn_grafana.alert_notification.get(alert_notification_uid=resource.ext_id)
                # delete alert_notification
                conn_grafana.alert_notification.delete(alert_notification_uid=resource.ext_id)
                task.progress(step_id, msg=' Grafana alert_notification deleted %s' % resource.ext_id)
            except:
                task.progress(step_id, msg=' Grafana alert_notification %s does not exist anymore' % resource.ext_id)

        return oid, params


task_manager.tasks.register(GrafanaAlertNotificationTask())
