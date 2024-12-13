# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.image import ComputeImage, Image
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class ImageTask(AbstractProviderResourceTask):
    """Image task"""

    name = "image_task"
    entity_class = ComputeImage

    @staticmethod
    @task_step()
    def import_zone_image_step(task, step_id, params, site_id, templates, *args, **kvargs):
        """Create compute_image image.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param site_id: site id
        :param templates: list of templates
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        availability_zone_id = templates[0].get("availability_zone_id")

        provider = task.get_container(cid)
        task.progress(step_id, msg="Get provider %s" % cid)

        # create image
        image_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone Image %s" % params.get("desc"),
            "parent": availability_zone_id,
            "orchestrator_tag": params.get("orchestrator_tag"),
            "templates": templates,
            "attribute": {"configs": {"os": params.get("os"), "os_ver": params.get("os_ver")}},
        }
        prepared_task, code = provider.resource_factory(Image, **image_params)
        image_id = prepared_task["uuid"]

        # link flavor to compute flavor
        task.get_session(reopen=True)
        compute_image = task.get_simple_resource(oid)
        compute_image.add_link("%s-image-link" % image_id, "relation.%s" % site_id, image_id, attributes={})
        task.progress(step_id, msg="Link image %s to compute image %s" % (image_id, oid))

        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create image in availability zone %s" % availability_zone_id)

        return True, params

    @staticmethod
    @task_step()
    def image_import_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create provider physical image.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator
        :return: True, params
        """
        oid = params.get("id")
        tmpl = orchestrator.get("template")

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg="Get image %s" % oid)
        if tmpl is not None:
            helper = task.get_orchestrator(orchestrator.get("type"), task, step_id, orchestrator, resource)
            image_id = helper.create_image(
                tmpl["id"],
                tmpl["template_pwd"],
                tmpl["guest_id"],
                tmpl["customization_spec_name"],
            )
            return image_id, params
        return None, params

    @staticmethod
    @task_step()
    def update_zone_template_step(task, step_id, params, site_id, templates, *args, **kvargs):
        """Update compute_template template.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param sharedarea.site_id: site id
        :param sharedarea.templates: list of template config
        :param sharedarea.templates.x.site_id:
        :param sharedarea.templates.x.availability_zone_id:
        :param sharedarea.templates.x.orchestrator_id: orchestrator id
        :param sharedarea.templates.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param sharedarea.templates.x.template_id: template id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        availability_zone_id = templates[0].get("availability_zone_id")

        provider = task.get_container(cid)
        task.progress(step_id, msg="Get provider %s" % cid)

        # check zone template already exists
        zone_templates = task.get_orm_linked_resources(oid, link_type="relation.%s" % site_id, container_id=cid)
        if len(zone_templates) > 0:
            zone_template = provider.get_simple_resource(zone_templates[0].id)
            task.progress(
                step_id,
                msg="Site %s already linked to compute image %s" % (site_id, oid),
            )

            # update template
            template_params = {
                "orchestrator_tag": params.get("orchestrator_tag"),
                "templates": templates,
            }
            prepared_task, code = zone_template.update(**template_params)
            run_sync_task(prepared_task, task, step_id)

        # create zone template
        else:
            template_params = {
                "name": "%s-avz%s" % (params.get("name"), site_id),
                "desc": "Zone template %s" % params.get("desc"),
                "parent": availability_zone_id,
                "orchestrator_tag": params.get("orchestrator_tag"),
                "templates": templates,
                "attribute": {"configs": {"os": params.get("os"), "os_ver": params.get("os_ver")}},
            }
            prepared_task, code = provider.resource_factory(Image, **template_params)
            template_id = prepared_task["uuid"]

            # link template to compute template
            task.get_session(reopen=True)
            compute_template = task.get_simple_resource(oid)
            compute_template.add_link(
                "%s-image-link" % template_id,
                "relation.%s" % site_id,
                template_id,
                attributes={},
            )
            task.progress(step_id, msg="Link image %s to compute template %s" % (template_id, oid))

            # wait task complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(
                step_id,
                msg="Create image in availability zone %s" % availability_zone_id,
            )

        return True, params
