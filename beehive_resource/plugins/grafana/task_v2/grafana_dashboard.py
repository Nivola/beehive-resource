# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.grafana.entity.grafana_dashboard import GrafanaDashboard
from beehive_resource.plugins.grafana.controller import GrafanaContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager

logger = logging.getLogger(__name__)


class GrafanaDashboardTask(AbstractResourceTask):
    """GrafanaDashboard task"""

    name = "grafana_dashboard_task"
    entity_class = GrafanaDashboard

    @staticmethod
    @task_step()
    def grafana_dashboard_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def grafana_dashboard_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def grafana_dashboard_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params


task_manager.tasks.register(GrafanaDashboardTask())
