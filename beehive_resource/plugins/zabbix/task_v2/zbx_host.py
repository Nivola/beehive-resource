# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beehive.common.task_v2.manager import task_manager
from beehive_resource.task_v2 import AbstractResourceTask
from beehive_resource.plugins.zabbix.entity.zbx_host import ZabbixHost
from beehive_resource.plugins.zabbix.controller import ZabbixContainer, ZabbixManager
from beehive.common.task_v2 import task_step

logger = getLogger(__name__)


class ZabbixHostTask(AbstractResourceTask):
    """Host task"""

    name = "zbx_host_task"
    entity_class = ZabbixHost

    @staticmethod
    @task_step()
    def host_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        description = params.get("description")
        interfaces = params.get("interfaces")
        groups = params.get("groups")
        templates = params.get("templates")
        status = params.get("status")
        task.progress(step_id, msg="Get configuration params")

        # create host
        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn

        inst = zabbixManager.host.create(
            name,
            interfaces,
            groupids=groups,
            templateids=templates,
            description=description,
            status=status,
        )
        inst_id = inst["hostids"][0]
        task.progress(step_id, msg="Create host %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def host_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """

        cid = params.get("cid")
        oid = params.get("id")
        status = params.get("status")
        task.progress(step_id, msg="Get configuration params")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check whether host exists
                conn.host.get(resource.ext_id)
                # update host status
                conn.host.update(resource.ext_id, status=status)
                task.progress(step_id, msg="Update host %s" % resource.ext_id)
            except:
                task.progress(step_id, msg="Host %s does not exist anymore" % resource.ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def host_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check whether host exists
                conn.host.get(resource.ext_id)
                # delete host
                conn.host.delete(resource.ext_id)
                task.progress(step_id, msg="Delete host %s" % resource.ext_id)
            except:
                task.progress(step_id, msg="Host %s does not exist anymore" % resource.ext_id)

        return oid, params


task_manager.tasks.register(ZabbixHostTask())
