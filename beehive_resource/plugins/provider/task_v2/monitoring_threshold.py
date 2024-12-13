# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

# from elasticsearch.client import logger
from copy import deepcopy
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.monitoring_threshold import (
    ComputeMonitoringThreshold,
    MonitoringThreshold,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup
from beehive_resource.plugins.zabbix.entity.zbx_hostgroup import ZabbixHostgroup
from beehive_resource.plugins.zabbix.entity.zbx_action import ZabbixAction
from logging import getLogger

logger = getLogger(__name__)


class ComputeMonitoringThresholdTask(AbstractProviderResourceTask):
    """ComputeMonitoringThreshold task"""

    name = "compute_monitoring_threshold_task"
    entity_class = ComputeMonitoringThreshold

    @staticmethod
    @task_step()
    def create_zone_monitoring_threshold_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone monitoring threshold.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("create_zone_monitoring_threshold_step - oid %s" % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # create zone monitoring_threshold
        # fv - modifica il nome della risorsa
        monitoring_threshold_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            # name rimane uguale
            # 'name': '%s' % (params.get('name')),
            "desc": "Logica - monitoring_threshold %s" % params.get("desc"),
            "parent": availability_zone_id,
            "norescreate": params.get("norescreate"),
            "zabbix_threshold": params.get("zabbix_threshold"),
            "attribute": {
                "type": params.get("type"),
                "orchestrator_tag": params.get("orchestrator_tag"),
            },
        }
        logger.debug(
            "create_zone_monitoring_threshold_step - monitoring_threshold_params {} ".format(
                monitoring_threshold_params
            )
        )
        prepared_task, code = provider.resource_factory(MonitoringThreshold, **monitoring_threshold_params)
        monitoring_threshold_id = prepared_task["uuid"]

        # link monitoring_threshold to compute monitoring_threshold
        task.get_session(reopen=True)
        compute_monitoring_threshold = task.get_simple_resource(oid)
        compute_monitoring_threshold.add_link(
            "%s-monitoring_threshold-link" % monitoring_threshold_id,
            "relation.%s" % site_id,
            monitoring_threshold_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link monitoring_threshold %s to compute_monitoring_threshold %s" % (monitoring_threshold_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create monitoring threshold %s in availability_zone %s"
            % (monitoring_threshold_id, availability_zone_id),
        )

        return True, params

    @staticmethod
    @task_step()
    def send_action_to_monitoring_threshold_step(task, step_id, params, monitoring_threshold_id, *args, **kvargs):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        logger.debug("send_action_to_monitoring_threshold_step - params {}".format(params))

        cid = params.get("cid")
        oid = params.get("id")
        action = params.get("action_name")
        logger.debug("send_action_to_monitoring_threshold_step - action_name %s" % (action))

        configs = deepcopy(params)
        configs["id"] = monitoring_threshold_id
        # hypervisor = params.get('hypervisor')
        # hypervisor_tag = params.get('hypervisor_tag')

        resource = task.get_simple_resource(oid)
        monitoring_threshold: MonitoringThreshold
        monitoring_threshold = task.get_resource(monitoring_threshold_id)
        task.progress(step_id, msg="Get resources")

        # send action
        logger.debug("send_action_to_monitoring_threshold_step - configs {}".format(configs))
        prepared_task, code = monitoring_threshold.action(action, configs)
        task.progress(step_id, msg="Send action to monitoring threshold %s" % monitoring_threshold_id)
        res = run_sync_task(prepared_task, task, step_id)

        return res, params


class MonitoringThresholdTask(AbstractProviderResourceTask):
    """MonitoringThreshold task"""

    name = "monitoring_threshold_task"
    entity_class = MonitoringThreshold

    @staticmethod
    @task_step()
    def create_zabbix_threshold_step(task, step_id, params, *args, **kvargs):
        """Create zabbix threshold resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        name = params.get("name")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        zabbix_threshold = params.get("zabbix_threshold")
        triplet = zabbix_threshold.get("triplet")
        triplet_desc = zabbix_threshold.get("triplet_desc")
        str_users = zabbix_threshold.get("str_users")

        # get container from orchestrator
        from beehive_resource.plugins.zabbix.controller import ZabbixContainer

        zabbix_container: ZabbixContainer
        zabbix_container = task.get_container(orchestrator["id"])

        # check/add hostgroup
        hostgroup_id = MonitoringThresholdTask.create_hostgroup(task, step_id, zabbix_container, params)
        # add usergroup
        usergroup_id, usergroup_created = MonitoringThresholdTask.create_usergroup(
            task, step_id, zabbix_container, params, hostgroup_id
        )

        from beehive_resource.task_v2 import AbstractResourceTask

        abstractResourceTask: AbstractResourceTask = task
        # serve il container
        zabbix_usergroup: ZabbixUsergroup = abstractResourceTask.get_resource(usergroup_id)
        usergroup_id_to = zabbix_usergroup.ext_id

        # add action
        MonitoringThresholdTask.create_action(task, step_id, zabbix_container, params, usergroup_id_to, hostgroup_id)

        if usergroup_created:
            from beehive_resource.plugins.zabbix import ZabbixPlugin

            # default severity
            severity = ZabbixPlugin.SEVERITY_DESC_DISASTER
            severity += "," + ZabbixPlugin.SEVERITY_DESC_HIGH

            username = "Gruppo %s" % triplet_desc
            users_email = str_users

            # add user - ATTENZIONE al sync
            zabbix_usergroup.add_user(username, users_email, severity, usergroup_id_to, sync=False)

        return True, params

    @staticmethod
    def create_hostgroup(task, step_id, container, params):
        oid = params.get("id")
        name = params.get("name")
        zabbix_threshold = params.get("zabbix_threshold")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        from beehive_resource.plugins.zabbix.controller import ZabbixContainer

        zabbix_container: ZabbixContainer = container

        zabbix_hostgroup_temp: ZabbixHostgroup
        zabbix_hostgroup_name = zabbix_threshold.get("triplet")

        # try:
        logger.debug("create_zabbix_hostgroup_step - cerco hostgroup per name: %s" % zabbix_hostgroup_name)
        # zabbix_hostgroup_temp = zabbix_container.get_simple_resource(zabbix_hostgroup_name, entity_class=ZabbixHostgroup)
        res, total = zabbix_container.get_resources(
            objdef=ZabbixHostgroup.objdef, type=ZabbixHostgroup.objdef, name=zabbix_hostgroup_name, run_customize=False
        )
        if total > 0:
            zabbix_hostgroup_temp = res[0]

            hostgroup_id = zabbix_hostgroup_temp.oid
            hostgroup_ext_id = zabbix_hostgroup_temp.ext_id
            return hostgroup_ext_id

        else:
            # except:
            logger.debug("create_zabbix_hostgroup_step - hostgroup NOT found - name: %s" % zabbix_hostgroup_name)

            # risorsa non trovata -> la creo
            zabbix_hostgroup_params = {
                # 'name': name,
                "name": zabbix_hostgroup_name,
                "desc": "Fisica - Zabbix Hostgroup %s" % name,
                "attribute": {},
                "sync": True,
            }
            logger.debug("create_zabbix_hostgroup_step - zabbix_container %s" % type(zabbix_container).__name__)
            prepared_task, code = zabbix_container.resource_factory(ZabbixHostgroup, **zabbix_hostgroup_params)
            hostgroup_id = prepared_task["uuid"]

            # wait for task to complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg="Create zabbix_hostgroup %s" % hostgroup_id)

            zabbix_hostgroup_temp = zabbix_container.get_simple_resource(hostgroup_id)
            hostgroup_id = zabbix_hostgroup_temp.oid
            hostgroup_ext_id = zabbix_hostgroup_temp.ext_id
            return hostgroup_ext_id

    @staticmethod
    def create_usergroup(task, step_id, container, params, hostgroup_id):
        oid = params.get("id")
        name = params.get("name")
        zabbix_threshold = params.get("zabbix_threshold")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        from beehive_resource.plugins.zabbix.controller import ZabbixContainer

        zabbix_container: ZabbixContainer = container

        zabbix_usergroup_temp: ZabbixUsergroup
        zabbix_usergroup_name = "Gruppo %s" % zabbix_threshold.get("triplet_desc")

        # try:
        logger.debug("create_zabbix_usergroup_step - cerco usergroup per name: %s" % zabbix_usergroup_name)
        # zabbix_usergroup_temp = zabbix_container.get_simple_resource(zabbix_usergroup_name, entity_class=ZabbixUsergroup)
        res, total = zabbix_container.get_resources(
            objdef=ZabbixUsergroup.objdef, type=ZabbixUsergroup.objdef, name=zabbix_usergroup_name, run_customize=False
        )
        if total > 0:
            zabbix_usergroup_temp = res[0]

            usergroup_id = zabbix_usergroup_temp.oid
            logger.debug("create_zabbix_usergroup_step - usergroup trovato - aggiungo link: %s" % usergroup_id)

            # reuse True, in cancellazione non cancella la risorsa fisica
            reuse = False
            monitoring_threshold: MonitoringThreshold
            monitoring_threshold = task.get_simple_resource(oid)
            monitoring_threshold.add_link(
                "%s-zabbix_usergroup-link" % usergroup_id,
                "relation",
                usergroup_id,
                attributes={"reuse": reuse},
            )
            logger.debug("create_zabbix_usergroup_step - link creato")

            task.progress(step_id, msg="Link zabbix_usergroup %s" % usergroup_id)
            return usergroup_id, False

        else:
            # except:
            logger.error("create_zabbix_usergroup_step - norescreate: %s" % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error("create_zabbix_usergroup_step - usergroup NOT found - name: %s" % zabbix_usergroup_name)
                logger.error("create_zabbix_usergroup_step - link non creato - MonitoringThreshold - oid: %s" % oid)
                raise Exception("usergroup NOT found - name: %s" % zabbix_usergroup_name)
            else:
                logger.debug("create_zabbix_usergroup_step - usergroup NOT found - name: %s" % zabbix_usergroup_name)

                # risorsa non trovata -> la creo
                zabbix_usergroup_params = {
                    # 'name': name,
                    "name": zabbix_usergroup_name,
                    "desc": "Fisica - Zabbix Usergroup %s" % name,
                    "attribute": {},
                    "sync": True,
                    "hostgroup_id": hostgroup_id,
                }
                logger.debug("create_zabbix_usergroup_step - zabbix_container %s" % type(zabbix_container).__name__)
                prepared_task, code = zabbix_container.resource_factory(ZabbixUsergroup, **zabbix_usergroup_params)

                usergroup_id = prepared_task["uuid"]

                # link zabbix_usergroup to monitoring_threshold
                task.get_session(reopen=True)
                monitoring_threshold: MonitoringThreshold
                monitoring_threshold = task.get_simple_resource(oid)
                monitoring_threshold.add_link(
                    "%s-zabbix_usergroup-link" % usergroup_id, "relation", usergroup_id, attributes={}
                )
                task.progress(
                    step_id,
                    msg="Link zabbix_usergroup %s to monitoring_threshold %s" % (usergroup_id, oid),
                )

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="Create zabbix_usergroup %s" % usergroup_id)
                return usergroup_id, True

    @staticmethod
    def create_action(task, step_id, container, params, usrgrp_id, hostgroup_id):
        oid = params.get("id")
        name = params.get("name")
        zabbix_threshold = params.get("zabbix_threshold")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        from beedrones.zabbix.action import ZabbixAction as BeedronesZabbixAction
        from beehive_resource.plugins.zabbix.controller import ZabbixContainer

        zabbix_container: ZabbixContainer = container

        zabbix_action_temp: ZabbixAction
        zabbix_action_name = "Report problems to Gruppo %s" % zabbix_threshold.get("triplet_desc")
        logger.debug("create_zabbix_action_step - cerco action per name: %s" % zabbix_action_name)
        # zabbix_action_temp = zabbix_container.get_simple_resource(zabbix_action_name, entity_class=ZabbixAction)
        res, total = zabbix_container.get_resources(
            objdef=ZabbixAction.objdef, type=ZabbixAction.objdef, name=zabbix_action_name, run_customize=False
        )

        b_found = False
        if total > 0:
            for zabbix_action_temp in res:
                if "eventsource" in zabbix_action_temp.attribs:
                    eventsource = int(zabbix_action_temp.attribs.get("eventsource"))
                    if eventsource != BeedronesZabbixAction.EVENTSOURCE_TRIGGER:
                        logger.debug(
                            "create_zabbix_action_step - action trovato non trigger - oid: %s" % zabbix_action_temp.oid
                        )
                    else:
                        b_found = True

                        action_id = zabbix_action_temp.oid
                        logger.debug("create_zabbix_action_step - action trovato - aggiungo link: %s" % action_id)

                        # reuse True, in cancellazione non cancella la risorsa fisica
                        reuse = False
                        monitoring_threshold: MonitoringThreshold
                        monitoring_threshold = task.get_simple_resource(oid)
                        monitoring_threshold.add_link(
                            "%s-zabbix_action-link" % action_id,
                            "relation",
                            action_id,
                            attributes={"reuse": reuse},
                        )
                        logger.debug("create_zabbix_action_step - link creato")

                        task.progress(step_id, msg="Link zabbix_action %s" % action_id)
                        return action_id

        if b_found == False:
            logger.error("create_zabbix_action_step - norescreate: %s" % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error("create_zabbix_action_step - action NOT found - name: %s" % zabbix_action_name)
                logger.error("create_zabbix_action_step - link non creato - MonitoringThreshold - oid: %s" % oid)
                raise Exception("action NOT found - name: %s" % zabbix_action_name)
            else:
                logger.debug("create_zabbix_action_step - action NOT found - name: %s" % zabbix_action_name)

                # risorsa non trovata -> la creo
                zabbix_action_params = {
                    # 'name': name,
                    "name": zabbix_action_name,
                    "desc": "Fisica - Zabbix Action %s" % name,
                    "attribute": {"eventsource": "%s" % BeedronesZabbixAction.EVENTSOURCE_TRIGGER},
                    "sync": True,
                    "usrgrp_id": usrgrp_id,
                    "hostgroup_id": hostgroup_id,
                }
                logger.debug("create_zabbix_action_step - zabbix_container %s" % type(zabbix_container).__name__)
                prepared_task, code = zabbix_container.resource_factory(ZabbixAction, **zabbix_action_params)

                action_id = prepared_task["uuid"]

                # link zabbix_action to monitoring_threshold
                task.get_session(reopen=True)
                monitoring_threshold: MonitoringThreshold
                monitoring_threshold = task.get_simple_resource(oid)
                monitoring_threshold.add_link("%s-zabbix_action-link" % action_id, "relation", action_id, attributes={})
                task.progress(
                    step_id,
                    msg="Link zabbix_action %s to monitoring_threshold %s" % (action_id, oid),
                )

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="Create zabbix_action %s" % action_id)
                return action_id

    @staticmethod
    @task_step()
    def monitoring_threshold_action_step(task, step_id, params, *args, **kvargs):
        """Send action to physical server.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug("monitoring_threshold_action_step - params {}".format(params))
        logger.debug("monitoring_threshold_action_step - args {}".format(args))

        oid = params.get("id")
        cid = params.get("cid")
        action = params.get("action_name")

        # cid è l'id di Podto1Zabbix (non più ResourceProvider01)
        container = task.get_container(cid)

        usergroup_id = params.get("usergroup_id")
        zabbix_usergroup: ZabbixUsergroup = task.get_simple_resource(usergroup_id)
        zabbix_usergroup.set_container(container)

        if action == "add_user":
            username = "Gruppo %s" % params.get("triplet")
            users_email = params.get("users_email")
            severity = params.get("severity")
            usergroup_id_to = zabbix_usergroup.ext_id
            logger.debug("monitoring_threshold_action_step - usergroup_id_to %s" % usergroup_id_to)

            res, str = zabbix_usergroup.add_user(username, users_email, severity, usergroup_id_to, params)
            logger.debug("monitoring_threshold_action_step - action: %s - str: %s" % (action, str))

        elif action == "modify_user":
            username = "Gruppo %s" % params.get("triplet")
            users_email = params.get("users_email")
            severity = params.get("severity")
            usergroup_id_to = zabbix_usergroup.ext_id
            logger.debug("monitoring_threshold_action_step - usergroup_id_to %s" % usergroup_id_to)

            res, str = zabbix_usergroup.add_user(username, users_email, severity, usergroup_id_to, params)
            logger.debug("monitoring_threshold_action_step - action: %s - str: %s" % (action, str))

            # action update severity
            action_id = params.get("action_id")  # ATTENTION: zabbix action

            zabbix_action: ZabbixAction = task.get_simple_resource(action_id)
            zabbix_action.set_container(container)
            zabbix_action.update_severity(severity)

        else:
            logger.error("monitoring_threshold_action_step - action: %s - not managed" % (action))

        return True, params
