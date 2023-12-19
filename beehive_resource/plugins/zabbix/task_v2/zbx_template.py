# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from logging import getLogger

from beehive.common.task_v2.manager import task_manager
from beehive_resource.task_v2 import AbstractResourceTask
from beehive_resource.plugins.zabbix.entity.zbx_template import ZabbixTemplate
from beehive.common.task_v2 import task_step

logger = getLogger(__name__)


class ZabbixTemplateTask(AbstractResourceTask):
    """Template task"""

    name = "zbx_template_task"
    entity_class = ZabbixTemplate

    @staticmethod
    @task_step()
    def template_create_physical_step(task, step_id, params, *args, **kvargs):
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
        groups = params.get("groups")
        task.progress(step_id, msg="Get configuration params")

        # create template
        container = task.get_container(cid)
        conn = container.conn
        inst = conn.template.create(name, groups, description=description)  # ex. of response: {'templateids':['10086']}
        inst_id = inst["templateids"][0]
        task.progress(step_id, msg="Create template %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def template_delete_physical_step(task, step_id, params, *args, **kvargs):
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
                # check whether template exists
                conn.template.get(resource.ext_id)
                # delete template
                conn.template.delete(resource.ext_id)
                task.progress(step_id, msg="Delete template %s" % resource.ext_id)
            except:
                task.progress(step_id, msg="Template %s does not exist anymore" % resource.ext_id)

        return oid, params


task_manager.tasks.register(ZabbixTemplateTask())
