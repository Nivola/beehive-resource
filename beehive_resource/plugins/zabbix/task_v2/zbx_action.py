# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beecell.types.type_dict import dict_get
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.zabbix.entity.zbx_action import ZabbixAction
from beehive_resource.plugins.zabbix.controller import ZabbixContainer, ZabbixManager
from beehive_resource.task_v2 import AbstractResourceTask, task_manager
import string
import os, random

logger = logging.getLogger(__name__)


class ZabbixActionTask(AbstractResourceTask):
    """ZabbixAction task"""

    name = "zabbix_action_task"
    entity_class = ZabbixAction

    @staticmethod
    @task_step()
    def zabbix_action_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("+++++ zabbix_action_create_physical_step")

        cid = params.get("cid")  # container id
        oid = params.get("id")
        logger.debug("+++++ cid: %s" % cid)
        logger.debug("+++++ oid: %s" % oid)

        # action_id = params.get('action_id')
        name = params.get("name")
        usrgrp_id = params.get("usrgrp_id")
        hostgroup_id = params.get("hostgroup_id")

        # logger.debug('action_id: %s: ' % action_id)
        logger.debug("+++++ name: %s" % name)
        logger.debug("+++++ usrgrp_id: %s" % usrgrp_id)
        logger.debug("+++++ hostgroup_id: %s" % hostgroup_id)

        task.progress(step_id, msg="Get configuration params")

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn

        task.progress(step_id, msg="Zabbix action %s does not exist yet" % name)
        inst = zabbixManager.action.add_trigger(name, usrgrp_id, hostgroup_id)
        logger.debug("+++++ inst: %s" % inst)
        inst_id = inst["actionids"][0]
        task.progress(step_id, msg="Zabbix action created: %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        # params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def zabbix_action_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def zabbix_action_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("+++++ zabbix_action_delete_physical_step")

        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("+++++ cid %s: " % cid)
        logger.debug("+++++ oid %s: " % oid)

        from beehive_resource.container import Resource

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn
        resource: Resource = zabbixContainer.get_simple_resource(oid)
        logger.debug("+++++ resource.ext_id: %s: " % resource.ext_id)

        if resource.is_ext_id_valid() is True:
            try:
                # check if action exists
                zabbixManager.action.get(action_id=resource.ext_id)
                # delete action
                zabbixManager.action.delete(action_id=resource.ext_id)
                task.progress(step_id, msg="Zabbix action deleted %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg="Zabbix action %s does not exist anymore" % resource.ext_id,
                )

        return oid, params

    @staticmethod
    @task_step()
    def update_severity_step(task, step_id, params, *args, **kvargs):
        """Update severity step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def update_severity_action(conn, cid, oid, ext_id, params):
            logger.debug("update_severity_action - update_severity_action - params={}".format(params))

            zabbixContainer: ZabbixContainer = task.get_container(cid)
            zabbixManager: ZabbixManager = zabbixContainer.conn

            severity: str = params["severity"]

            # convert array severity literal in integer severity
            severity_final = 10
            severity_array = severity.split(",")
            for severity_item in severity_array:
                from beedrones.zabbix.action import ZabbixAction as BeedronesZabbixAction
                from beehive_resource.plugins.zabbix import ZabbixPlugin

                if severity_item == ZabbixPlugin.SEVERITY_DESC_DISASTER:
                    severity_int = BeedronesZabbixAction.SEVERITY_DISASTER

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_HIGH:
                    severity_int = BeedronesZabbixAction.SEVERITY_HIGH

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_AVERAGE:
                    severity_int = BeedronesZabbixAction.SEVERITY_AVERAGE

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_WARNING:
                    severity_int = BeedronesZabbixAction.SEVERITY_WARNING

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_INFORMATION:
                    severity_int = BeedronesZabbixAction.SEVERITY_INFORMATION

                # set the smallest severity
                logger.debug(
                    "update_severity_action - update_severity_action - severity_item: %s - severity_int: %s"
                    % (severity_item, severity_int)
                )
                if severity_int < severity_final:
                    severity_final = severity_int

            logger.debug("update_severity_action - update_severity_action - severity_final: %s" % severity_final)
            res = zabbixManager.action.update_trigger_severity(action_id=ext_id, severity=severity_final)

        logger.debug("update_severity_step - params={}".format(params))
        res = ZabbixActionTask.action_action(
            task, step_id, update_severity_action, "Update severity", "Error updating severity action", params
        )
        return res, params

    #
    # action
    #
    @staticmethod
    def action_action(task, step_id, action, success, error, params):
        """Execute a server action

        :param task: celery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param params: input params
        :return: ext_id
        :raise:
        """
        logger.debug("action_action")
        task.progress(step_id, msg="start action %s" % action.__name__)
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # execute action
        vs_task = action(conn, cid, oid, ext_id, params)
        if vs_task is not None:
            container.query_remote_task(task, step_id, vs_task, error=error)

        # update cache
        server_obj = task.get_resource(oid)
        server_obj.set_cache()

        task.progress(step_id, msg=success)
        task.progress(step_id, msg="stop action %s" % action.__name__)
        return True


task_manager.tasks.register(ZabbixActionTask())
