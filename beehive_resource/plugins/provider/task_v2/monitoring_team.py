# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

# from elasticsearch.client import logger
from copy import deepcopy
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.monitoring_team import (
    ComputeMonitoringTeam,
    MonitoringTeam,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.grafana.entity.grafana_team import GrafanaTeam
from logging import getLogger

logger = getLogger(__name__)


class ComputeMonitoringTeamTask(AbstractProviderResourceTask):
    """ComputeMonitoringTeam task"""

    name = "compute_monitoring_team_task"
    entity_class = ComputeMonitoringTeam

    @staticmethod
    @task_step()
    def create_zone_monitoring_team_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone monitoring team.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("create_zone_monitoring_team_step - oid %s" % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # create zone monitoring_team
        # fv - modifica il nome della risorsa
        monitoring_team_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            # name rimane uguale
            # 'name': '%s' % (params.get('name')),
            "desc": "Logica - monitoring_team %s" % params.get("desc"),
            "parent": availability_zone_id,
            "norescreate": params.get("norescreate"),
            "grafana_team": params.get("grafana_team"),
            "attribute": {
                "type": params.get("type"),
                "orchestrator_tag": params.get("orchestrator_tag"),
            },
        }
        logger.debug("create_zone_monitoring_team_step - monitoring_team_params {} ".format(monitoring_team_params))
        prepared_task, code = provider.resource_factory(MonitoringTeam, **monitoring_team_params)
        monitoring_team_id = prepared_task["uuid"]

        # link monitoring_team to compute monitoring_team
        task.get_session(reopen=True)
        compute_monitoring_team = task.get_simple_resource(oid)
        compute_monitoring_team.add_link(
            "%s-monitoring_team-link" % monitoring_team_id,
            "relation.%s" % site_id,
            monitoring_team_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link monitoring_team %s to compute_monitoring_team %s" % (monitoring_team_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create monitoring team %s in availability_zone %s" % (monitoring_team_id, availability_zone_id),
        )

        return True, params

    @staticmethod
    @task_step()
    def send_action_to_monitoring_team_step(task, step_id, params, monitoring_team_id, *args, **kvargs):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        logger.debug("send_action_to_monitoring_team_step - params {}".format(params))

        cid = params.get("cid")
        oid = params.get("id")
        action = params.get("action_name")
        logger.debug("send_action_to_monitoring_team_step - action_name %s" % (action))

        configs = deepcopy(params)
        configs["id"] = monitoring_team_id
        # hypervisor = params.get('hypervisor')
        # hypervisor_tag = params.get('hypervisor_tag')

        resource = task.get_simple_resource(oid)
        monitoring_team: MonitoringTeam
        monitoring_team = task.get_resource(monitoring_team_id)
        task.progress(step_id, msg="Get resources")

        # send action
        logger.debug("send_action_to_monitoring_team_step - configs {}".format(configs))
        prepared_task, code = monitoring_team.action(action, configs)
        task.progress(step_id, msg="Send action to monitoring team %s" % monitoring_team_id)
        res = run_sync_task(prepared_task, task, step_id)

        return res, params


class MonitoringTeamTask(AbstractProviderResourceTask):
    """MonitoringTeam task"""

    name = "monitoring_team_task"
    entity_class = MonitoringTeam

    @staticmethod
    @task_step()
    def create_grafana_team_step(task, step_id, params, *args, **kvargs):
        """Create grafana team resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        name = params.get("name")
        grafana_team = params.get("grafana_team")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        # get container from orchestrator
        from beehive_resource.plugins.grafana.controller import GrafanaContainer

        grafana_container: GrafanaContainer
        grafana_container = task.get_container(orchestrator["id"])

        grafana_team_temp: GrafanaTeam
        grafana_team_name = grafana_team.get("name")
        try:
            logger.debug("create_grafana_team_step - cerco team per name: %s" % grafana_team_name)
            grafana_team_temp = grafana_container.get_simple_resource(grafana_team_name)
            team_id = grafana_team_temp.oid
            logger.debug("create_grafana_team_step - team trovato - aggiungo link: %s" % team_id)

            # reuse in cancellazione non cancella la risorsa fisica
            monitoring_team: MonitoringTeam
            monitoring_team = task.get_simple_resource(oid)
            monitoring_team.add_link(
                "%s-grafana_team-link" % team_id,
                "relation",
                team_id,
                attributes={"reuse": True},
            )
            logger.debug("create_grafana_team_step - link creato")

            task.progress(step_id, msg="Link grafana_team %s" % team_id)

        except:
            logger.error("create_grafana_team_step - norescreate: %s" % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error("create_grafana_team_step - team NOT found - name: %s" % grafana_team_name)
                logger.error("create_grafana_team_step - link non creato - MonitoringTeam - oid: %s" % oid)
                raise Exception("team NOT found - name: %s" % grafana_team_name)
            else:
                logger.debug("create_grafana_team_step - team NOT found - name: %s" % grafana_team_name)

                # risorsa non trovata -> la creo
                # create grafana_team
                # name = '%s-%s-%s' % (name, orchestrator['id'], id_gen())
                # name rimane uguale

                grafana_team_params = {
                    # 'name': name,
                    "name": grafana_team_name,
                    "desc": "Fisica - Grafana Team %s" % name,
                    "attribute": {},
                    "sync": True,
                }
                logger.debug("create_grafana_team_step - grafana_container %s" % type(grafana_container).__name__)
                prepared_task, code = grafana_container.resource_factory(GrafanaTeam, **grafana_team_params)

                team_id = prepared_task["uuid"]

                # link grafana_team to monitoring_team
                task.get_session(reopen=True)
                monitoring_team: GrafanaTeam
                monitoring_team = task.get_simple_resource(oid)
                monitoring_team.add_link("%s-grafana_team-link" % team_id, "relation", team_id, attributes={})
                task.progress(
                    step_id,
                    msg="Link grafana_team %s to monitoring_team %s" % (team_id, oid),
                )

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="Create grafana_team %s" % team_id)

        return True, params

    @staticmethod
    @task_step()
    def monitoring_team_action_step(task, step_id, params, *args, **kvargs):
        """Send action to physical server.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug("monitoring_team_action_step - params {}".format(params))
        logger.debug("monitoring_team_action_step - args {}".format(args))

        oid = params.get("id")
        cid = params.get("cid")
        team_id = params.get("team_id")
        action = params.get("action_name")

        grafana_team: GrafanaTeam
        grafana_team = task.get_simple_resource(team_id)

        # cid è l'id di Podto1Grafana (non più ResourceProvider01)
        container = task.get_container(cid)
        grafana_team.set_container(container)

        if action == "add_user":
            users_email = params.get("users_email")
            team_id_to = grafana_team.ext_id

            res, str = grafana_team.add_user(users_email, team_id_to, params)
            logger.debug("monitoring_team_action_step - action: %s - str: %s" % (action, str))

        else:
            logger.error("monitoring_team_action_step - action: %s - not managed" % (action))

        return True, params
