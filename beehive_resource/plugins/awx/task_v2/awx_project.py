# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.awx.entity.awx_project import AwxProject
from beehive_resource.task_v2 import AbstractResourceTask


class AwxProjectTask(AbstractResourceTask):
    """AwxProject task"""

    name = "awx_project_task"
    entity_class = AwxProject

    @staticmethod
    @task_step()
    def awx_project_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        desc = params.get("desc")
        org_id = params.get("org_ext_id")
        scm_type = params.get("scm_type", "git")
        scm_url = params.get("scm_url")
        scm_branch = params.get("scm_branch", "master")
        scm_update_on_launch = params.get("scm_update_on_launch", False)
        scm_creds = params.get("scm_creds")
        # default_environment = params.get("default_environment", None)
        task.progress(step_id, msg="Get configuration params")

        from beedrones.awx.client import AwxManager

        container = task.get_container(cid)
        conn: AwxManager = container.conn
        inst = conn.project.add(
            name,
            description=desc,
            organization=org_id,
            scm_type=scm_type,
            scm_url=scm_url,
            scm_branch=scm_branch,
            scm_update_on_launch=scm_update_on_launch,
            credential=scm_creds,
            # default_environment=default_environment
        )
        inst_id = inst["id"]
        task.progress(step_id, msg="Create awx project %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def awx_project_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def awx_project_delete_physical_step(task, step_id, params, *args, **kvargs):
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
                # check if project exists
                conn.project.get(resource.ext_id)
                # delete project
                conn.project.delete(resource.ext_id)
                task.progress(step_id, msg="Delete awx project %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg="Awx project %s does not exist anymore" % resource.ext_id,
                )

        return oid, params


task_manager.tasks.register(AwxProjectTask())
