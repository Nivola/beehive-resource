# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class SiteTask(AbstractProviderResourceTask):
    """Site task"""

    name = "site_task"
    entity_class = Site

    @staticmethod
    @task_step()
    def add_orchestrator_step(task, step_id, params, *args, **kvargs):
        """Add orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: orchestrator_id, params
        """
        site_id = params.get("site_id")
        orchestrator_id = params.get("orchestrator_id")
        orchestrator_type = params.get("orchestrator_type")
        orchestrator_tag = params.get("orchestrator_tag")
        orchestrator_config = params.get("orchestrator_config")
        task.progress(step_id, msg="Get configuration params")

        resource = task.get_simple_resource(site_id)

        # base orchestrator
        data = {
            "type": orchestrator_type,
            "id": orchestrator_id,
            "tag": orchestrator_tag,
            "config": orchestrator_config,
        }

        # create project/folder
        orchestrator = {"id": orchestrator_id}
        if orchestrator_type == "vsphere":
            helper = task.get_orchestrator("vsphere", task, step_id, orchestrator, resource)
            datacenter = orchestrator_config["datacenter"]
            folder_id = helper.create_folder(datacenter, None)
            data["config"]["folder"] = folder_id

        elif orchestrator_type == "openstack":
            helper = task.get_orchestrator("openstack", task, step_id, orchestrator, resource)
            domain = orchestrator_config["domain"]
            project_id = helper.create_project(domain, None)
            data["config"]["project"] = project_id

        # update resource
        attribute = resource.get_attribs()
        attribute["orchestrators"].append(data)
        resource.update_internal(attribute=attribute)
        task.progress(step_id, msg="Update resource %s" % site_id)

        return orchestrator_id, params

    @staticmethod
    @task_step()
    def del_orchestrator_step(task, step_id, params, *args, **kvargs):
        """Delete orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: orchestrator_id, params
        """
        cid = params.get("cid")
        site_id = params.get("site_id")
        orchestrator_id = params.get("orchestrator_id")
        orchestrator_type = params.get("orchestrator_type")
        task.progress(step_id, msg="Get configuration params")

        # container = task.get_container(cid)
        resource = task.get_simple_resource(site_id)

        # get all child resources
        childs = task.get_orm_linked_resources(site_id, link_type="relation", container_id=orchestrator_id)

        # delete all childs
        helper = task.get_orchestrator(orchestrator_type, task, step_id, {"id": orchestrator_id}, resource)
        helper.remove_resource(childs)
        # if orchestrator_type == 'vsphere':
        #     helper.remove_resource(childs)
        # elif orchestrator_type == 'openstack':
        #     helper.remove_resource(childs)

        # update resource
        orchestrators = resource.get_orchestrators(select_types=Site.available_orchestrator_types)
        orchestrators.pop(orchestrator_id)
        attribute = resource.get_attribs()
        attribute["orchestrators"] = list(orchestrators.values())
        resource.update_internal(attribute=attribute)
        task.progress(
            step_id,
            msg="Delete orchestrator %s from site %s" % (orchestrator_id, site_id),
        )

        return orchestrator_id, params
