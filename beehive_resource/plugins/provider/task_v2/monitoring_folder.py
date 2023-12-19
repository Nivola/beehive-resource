# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from copy import deepcopy
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.monitoring_folder import (
    ComputeMonitoringFolder,
    MonitoringFolder,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder
from logging import getLogger

logger = getLogger(__name__)


class ComputeMonitoringFolderTask(AbstractProviderResourceTask):
    """ComputeMonitoringFolder task"""

    name = "compute_monitoring_folder_task"
    entity_class = ComputeMonitoringFolder

    @staticmethod
    @task_step()
    def create_zone_monitoring_folder_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone monitoring folder.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")  # container id
        oid = params.get("id")  # id della risorsa
        logger.debug("create_zone_monitoring_folder_step - oid %s" % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # create zone monitoring_folder
        # fv - modifica il nome della risorsa
        monitoring_folder_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            # name rimane uguale
            # 'name': '%s' % (params.get('name')),
            "desc": "monitoring_folder %s" % params.get("desc"),
            "parent": availability_zone_id,
            "norescreate": params.get("norescreate"),
            "grafana_folder": params.get("grafana_folder"),
            "attribute": {
                "type": params.get("type"),
                "orchestrator_tag": params.get("orchestrator_tag"),
            },
        }
        logger.debug(
            "create_zone_monitoring_folder_step - monitoring_folder_params {} ".format(monitoring_folder_params)
        )
        prepared_task, code = provider.resource_factory(MonitoringFolder, **monitoring_folder_params)
        monitoring_folder_id = prepared_task["uuid"]

        # link monitoring_folder to compute monitoring_folder
        task.get_session(reopen=True)
        compute_monitoring_folder = task.get_simple_resource(oid)
        compute_monitoring_folder.add_link(
            "%s-monitoring_folder-link" % monitoring_folder_id,
            "relation.%s" % site_id,
            monitoring_folder_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link monitoring_folder %s to compute_monitoring_folder %s" % (monitoring_folder_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create monitoring folder %s in availability_zone %s" % (monitoring_folder_id, availability_zone_id),
        )

        return True, params

    @staticmethod
    @task_step()
    def send_action_to_monitoring_folder_step(task, step_id, params, monitoring_folder_id, *args, **kvargs):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        logger.debug("send_action_to_monitoring_folder_step - params {}".format(params))

        cid = params.get("cid")
        oid = params.get("id")
        action = params.get("action_name")
        logger.debug("send_action_to_monitoring_folder_step - action_name %s" % (action))

        configs = deepcopy(params)
        configs["id"] = monitoring_folder_id
        # hypervisor = params.get('hypervisor')
        # hypervisor_tag = params.get('hypervisor_tag')

        resource = task.get_simple_resource(oid)
        monitoring_folder: MonitoringFolder
        monitoring_folder = task.get_resource(monitoring_folder_id)
        task.progress(step_id, msg="Get resources")

        # send action
        logger.debug("send_action_to_monitoring_folder_step - configs {}".format(configs))
        prepared_task, code = monitoring_folder.action(action, configs)
        task.progress(step_id, msg="Send action to monitoring folder %s" % monitoring_folder_id)
        res = run_sync_task(prepared_task, task, step_id)

        return res, params


class MonitoringFolderTask(AbstractProviderResourceTask):
    """MonitoringFolder task"""

    name = "monitoring_folder_task"
    entity_class = MonitoringFolder

    @staticmethod
    @task_step()
    def create_grafana_folder_step(task, step_id, params, *args, **kvargs):
        """Create grafana folder resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        name = params.get("name")
        grafana_folder = params.get("grafana_folder")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        # get container from orchestrator
        from beehive_resource.plugins.grafana.controller import GrafanaContainer

        grafana_container: GrafanaContainer
        grafana_container = task.get_container(orchestrator["id"])

        grafana_folder_temp: GrafanaFolder
        grafana_folder_name = grafana_folder.get("name")
        try:
            logger.debug("create_grafana_folder_step - cerco folder per name: %s" % grafana_folder_name)
            grafana_folder_temp = grafana_container.get_simple_resource(grafana_folder_name)
            folder_id = grafana_folder_temp.oid
            logger.debug("create_grafana_folder_step - folder trovato - aggiungo link: %s" % folder_id)

            # reuse in cancellazione non cancella la risorsa fisica
            monitoring_folder: MonitoringFolder
            monitoring_folder = task.get_simple_resource(oid)
            monitoring_folder.add_link(
                "%s-grafana_folder-link" % folder_id,
                "relation",
                folder_id,
                attributes={"reuse": True},
            )
            logger.debug("create_grafana_folder_step - link creato")

            task.progress(step_id, msg="Link grafana_folder %s" % folder_id)

        except:
            logger.error("create_grafana_folder_step - norescreate: %s" % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error("create_grafana_folder_step - folder NOT found - name: %s" % grafana_folder_name)
                logger.error("create_grafana_folder_step - link non creato - MonitoringFolder - oid: %s" % oid)
                raise Exception("folder NOT found - name: %s" % grafana_folder_name)
            else:
                logger.debug("create_grafana_folder_step - folder NOT found - name: %s" % grafana_folder_name)

                grafana_folder_params = {
                    "name": grafana_folder_name,
                    "desc": grafana_folder.get("desc"),
                    # 'folder_id': grafana_folder.get('folder_id'),
                    "attribute": {},
                    "sync": True,
                }
                logger.debug("create_grafana_folder_step - grafana_container %s" % type(grafana_container).__name__)
                prepared_task, code = grafana_container.resource_factory(GrafanaFolder, **grafana_folder_params)

                # id of the physical resource
                folder_id = prepared_task["uuid"]

                # link grafana_folder to monitoring_folder
                task.get_session(reopen=True)
                monitoring_folder: MonitoringFolder
                monitoring_folder = task.get_simple_resource(oid)
                monitoring_folder.add_link(
                    "%s-grafana_folder-link" % folder_id,
                    "relation",
                    folder_id,
                    attributes={},
                )
                task.progress(
                    step_id,
                    msg="Link grafana_folder %s to monitoring_folder %s" % (folder_id, oid),
                )

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="Create grafana_folder %s" % folder_id)

        return True, params

    @staticmethod
    @task_step()
    # def instance_action_step(task, step_id, params, orchestrator, *args, **kvargs):
    def monitoring_folder_action_step(task: AbstractProviderResourceTask, step_id, params, *args, **kvargs):
        """Send action to physical server.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug("monitoring_folder_action_step - params {}".format(params))
        logger.debug("monitoring_folder_action_step - args {}".format(args))

        oid = params.get("id")
        cid = params.get("cid")
        folder_id = params.get("folder_id")
        action = params.get("action_name")

        grafana_folder: GrafanaFolder
        grafana_folder = task.get_simple_resource(folder_id)

        # cid è l'id di Podto1Grafana (non più ResourceProvider01)
        container = task.get_container(cid)
        grafana_folder.set_container(container)

        if action == "add_dashboard":
            dashboard_folder_from = params.get("dashboard_folder_from")
            dashboard_to_search = params.get("dashboard_to_search")

            dash_tag = params.get("dash_tag")
            organization = params.get("organization")
            division = params.get("division")
            account = params.get("account")

            # fv - attenzione folder id/uid
            folder_uid_to = grafana_folder.ext_id

            res, str = grafana_folder.add_dashboard(
                dashboard_folder_from,
                dashboard_to_search,
                folder_uid_to,
                organization,
                division,
                account,
                dash_tag,
                params,
            )
            logger.debug("monitoring_folder_action_step - action: %s - res: %s - str: %s" % (action, res, str))

            # se sync
            # ({'task': beehive_resource.task_v2.core.resource_action_task(), 'uuid': 'f5f7a13e-1338-4686-a65b-72768fad9e0b', 'params': {'dashboard_folder_from': 'default', 'dashboard_to_search': 'Mysql', 'folder_uid_to': 'e3HFClkSk', 'dash_tag': None, 'organization': 'CsiTest', 'division': 'DivCsi', 'account': 'account_csi', 'alias': 'GrafanaFolder.add_dashboard', 'cid': 19, 'id': 34183, 'objid': '1dcc06da3b//3b82ee774c', 'name': 'CsiTest.DivCsi.account_csi-folder', 'ext_id': 'e3HFClkSk', 'parent': None, 'action_name': 'add_dashboard', 'steps': ['beehive_resource.task_v2.core.AbstractResourceTask.action_resource_pre_step', 'beehive_resource.plugins.grafana.task_v2.grafana_folder.GrafanaFolderTask.add_dashboard_step', 'beehive_resource.task_v2.core.AbstractResourceTask.action_resource_post_step'], 'user': 'client-beehive@local', 'server': '10.42.0.135', 'identity': '7c6a83b3-d9c8-4396-8784-4f675b4da5e3', 'api_id': '5624ebd5-b0ca-400c-952f-e7a6a5c6a056', 'sync': True}}, 200)
            child_task = res[0]
            run_sync_task(child_task, task, step_id)

        elif action == "add_permission":
            # folder_uid = params.get('folder_uid')
            folder_uid = grafana_folder.ext_id
            team_viewer = params.get("team_viewer")
            team_editor = params.get("team_editor")

            res, str = grafana_folder.add_permission(folder_uid, team_viewer, team_editor, params)
            logger.debug("monitoring_folder_action_step - action: %s - str: %s" % (action, str))

        else:
            logger.error("monitoring_folder_action_step - action: %s - not managed" % (action))

        return True, params
