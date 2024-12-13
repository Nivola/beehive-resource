# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

# from elasticsearch.client import logger
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.monitoring_alert import (
    ComputeMonitoringAlert,
    MonitoringAlert,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.grafana.entity.grafana_alert_notification import (
    GrafanaAlertNotification,
)
from logging import getLogger

logger = getLogger(__name__)


class ComputeMonitoringAlertTask(AbstractProviderResourceTask):
    """ComputeMonitoringAlert task"""

    name = "compute_monitoring_alert_task"
    entity_class = ComputeMonitoringAlert

    @staticmethod
    @task_step()
    def create_zone_monitoring_alert_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone monitoring alert.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("create_zone_monitoring_alert_step - oid %s" % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # create zone monitoring_alert
        # fv - modifica il nome della risorsa
        monitoring_alert_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            # name rimane uguale
            # 'name': '%s' % (params.get('name')),
            "desc": "Logica - monitoring_alert %s" % params.get("desc"),
            "parent": availability_zone_id,
            "norescreate": params.get("norescreate"),
            "grafana_alert": params.get("grafana_alert"),
            "attribute": {
                "type": params.get("type"),
                "orchestrator_tag": params.get("orchestrator_tag"),
            },
        }
        logger.debug("create_zone_monitoring_alert_step - monitoring_alert_params {} ".format(monitoring_alert_params))
        prepared_task, code = provider.resource_factory(MonitoringAlert, **monitoring_alert_params)
        monitoring_alert_id = prepared_task["uuid"]

        # link monitoring_alert to compute monitoring_alert
        task.get_session(reopen=True)
        compute_monitoring_alert = task.get_simple_resource(oid)
        compute_monitoring_alert.add_link(
            "%s-monitoring_alert-link" % monitoring_alert_id,
            "relation.%s" % site_id,
            monitoring_alert_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link monitoring_alert %s to compute_monitoring_alert %s" % (monitoring_alert_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create monitoring alert %s in availability_zone %s" % (monitoring_alert_id, availability_zone_id),
        )

        return True, params


class MonitoringAlertTask(AbstractProviderResourceTask):
    """MonitoringAlert task"""

    name = "monitoring_alert_task"
    entity_class = MonitoringAlert

    @staticmethod
    @task_step()
    def create_grafana_alert_step(task, step_id, params, *args, **kvargs):
        """Create grafana alert resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        name = params.get("name")
        grafana_alert = params.get("grafana_alert")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        # get container from orchestrator
        from beehive_resource.plugins.grafana.controller import GrafanaContainer

        grafana_container: GrafanaContainer
        grafana_container = task.get_container(orchestrator["id"])

        grafana_alert_temp: GrafanaAlertNotification
        grafana_alert_name = grafana_alert.get("name")
        try:
            logger.debug("create_grafana_alert_step - cerco alert per name: %s" % grafana_alert_name)
            grafana_alert_temp = grafana_container.get_simple_resource(grafana_alert_name)
            alert_id = grafana_alert_temp.oid
            logger.debug("create_grafana_alert_step - alert trovato - aggiungo link: %s" % alert_id)

            # reuse in cancellazione non cancella la risorsa fisica
            monitoring_alert: MonitoringAlert
            monitoring_alert = task.get_simple_resource(oid)
            monitoring_alert.add_link(
                "%s-grafana_alert-link" % alert_id,
                "relation",
                alert_id,
                attributes={"reuse": True},
            )
            logger.debug("create_grafana_alert_step - link creato")

            task.progress(step_id, msg="Link grafana_alert %s" % alert_id)

        except:
            logger.error("create_grafana_alert_step - norescreate: %s" % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error("create_grafana_alert_step - alert NOT found - name: %s" % grafana_alert_name)
                logger.error("create_grafana_alert_step - link non creato - MonitoringAlert - oid: %s" % oid)
                raise Exception("alert NOT found - name: %s" % grafana_alert_name)
            else:
                logger.debug("create_grafana_alert_step - alert NOT found - name: %s" % grafana_alert_name)
                # risorsa non trovata -> la creo
                # create grafana_alert
                # commentare se name deve rimanere uguale
                name = "%s-%s-%s" % (name, orchestrator["id"], id_gen())

                grafana_alert_params = {
                    # 'name': name,
                    "name": grafana_alert_name,
                    "desc": "Fisica - Grafana Alert %s" % name,
                    "email": grafana_alert.get("email"),
                    "attribute": {},
                    "sync": True,
                }
                logger.debug("create_grafana_alert_step - grafana_container %s" % type(grafana_container).__name__)
                prepared_task, code = grafana_container.resource_factory(
                    GrafanaAlertNotification, **grafana_alert_params
                )

                alert_id = prepared_task["uuid"]

                # link grafana_alert to monitoring_alert
                task.get_session(reopen=True)
                monitoring_alert: GrafanaAlertNotification
                monitoring_alert = task.get_simple_resource(oid)
                monitoring_alert.add_link(
                    "%s-grafana_alert-link" % alert_id,
                    "relation",
                    alert_id,
                    attributes={},
                )
                task.progress(
                    step_id,
                    msg="Link grafana_alert %s to monitoring_alert %s" % (alert_id, oid),
                )

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="Create grafana_alert %s" % alert_id)

        return True, params
