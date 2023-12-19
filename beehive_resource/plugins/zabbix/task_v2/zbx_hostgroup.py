# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.zabbix.entity.zbx_hostgroup import ZabbixHostgroup
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class ZabbixHostgroupTask(AbstractResourceTask):
    """Hostgroup task"""

    name = "zbx_hostgroup_task"
    entity_class = ZabbixHostgroup

    @staticmethod
    @task_step()
    def hostgroup_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        task.progress(step_id, msg="Get configuration params")

        # create hostgroup
        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn
        inst = zabbixManager.hostgroup.add(name)  # example of response: inst = {'groupids': ['42']}
        inst_id = inst["groupids"][0]
        task.progress(step_id, msg="Create hostgroup %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def hostgroup_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        task.progress(step_id, msg="Get configuration params")

        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn
        resource = zabbixContainer.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check whether hostgroup exists
                zabbixManager.hostgroup.get(resource.ext_id)
                # update hostgroup
                zabbixManager.hostgroup.update(resource.ext_id, name)
                task.progress(step_id, msg="Update hostgroup %s" % resource.ext_id)
            except:
                task.progress(step_id, msg="Hostgroup %s does not exist anymore" % resource.ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def hostgroup_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn
        resource = zabbixContainer.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check if hostgroup exists
                zabbixManager.hostgroup.get(resource.ext_id)
                # delete hostgroup
                zabbixManager.hostgroup.delete(resource.ext_id)
                task.progress(step_id, msg="Delete hostgroup %s" % resource.ext_id)
                # reset ext_id
                resource.update_internal(ext_id=None)
            except:
                task.progress(step_id, msg="Hostgroup %s does not exist anymore" % resource.ext_id)

        return oid, params


task_manager.tasks.register(ZabbixHostgroupTask())
