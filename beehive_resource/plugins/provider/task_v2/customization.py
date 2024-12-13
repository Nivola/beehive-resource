# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.customization import (
    ComputeCustomization,
    Customization,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.awx.entity.awx_project import AwxProject


class ComputeCustomizationTask(AbstractProviderResourceTask):
    """ComputeCustomization task"""

    name = "compute_customization_task"
    entity_class = ComputeCustomization

    @staticmethod
    @task_step()
    def create_zone_customization_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone customization.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # create zone customization
        customization_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone customization %s" % params.get("desc"),
            "parent": availability_zone_id,
            "awx_project": params.get("awx_project"),
            "orchestrator_tag": params.get("orchestrator_tag"),
            "attribute": {
                "type": params.get("type"),
                "orchestrator_tag": params.get("orchestrator_tag"),
            },
        }

        # from beehive_resource.container import ResourceContainer
        # provider: ResourceContainer

        try:
            prepared_task, code = provider.resource_factory(Customization, **customization_params)
        except Exception as e:
            task.progress(
                step_id, "Will not create customization in availability zone %s: %s" % (availability_zone_id, str(e))
            )
            return True, params

        customization_id = prepared_task["uuid"]

        # link customization to compute customization
        task.get_session(reopen=True)
        compute_customization = task.get_simple_resource(oid)
        compute_customization.add_link(
            "%s-customization-link" % customization_id,
            "relation.%s" % site_id,
            customization_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link customization %s to compute_customization %s" % (customization_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create customization %s in availability_zone %s" % (customization_id, availability_zone_id),
        )

        return True, params


class CustomizationTask(AbstractProviderResourceTask):
    """Customization task"""

    name = "customization_task"
    entity_class = Customization

    @staticmethod
    @task_step()
    def create_awx_project_step(task, step_id, params, *args, **kvargs):
        """Create awx project resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        name = params.get("name")
        awx_project = params.get("awx_project")
        orchestrator = params.get("orchestrator")

        # get container from orchestrator
        awx_container = task.get_container(orchestrator["id"])

        # create awx_project
        name = "%s-%s-%s" % (name, orchestrator["id"], id_gen())
        awx_project_params = {
            "name": name,
            "desc": "Awx Project %s" % name,
            "scm_url": awx_project.get("scm_url"),
            "scm_branch": awx_project.get("scm_branch", "master"),
            "organization": orchestrator["config"].get("organization"),
            "scm_creds_name": orchestrator["config"].get("scm_creds"),
            "attribute": {},
        }
        prepared_task, code = awx_container.resource_factory(AwxProject, **awx_project_params)
        project_id = prepared_task["uuid"]

        # link awx_project to customization
        task.get_session(reopen=True)
        customization = task.get_simple_resource(oid)
        customization.add_link("%s-awx_project-link" % project_id, "relation", project_id, attributes={})
        task.progress(step_id, msg="Link awx_project %s to customization %s" % (project_id, oid))

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create awx_project %s" % project_id)

        return True, params
