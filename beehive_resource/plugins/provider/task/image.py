# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive_resource.plugins.provider.entity.image import Image
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_zone_image(self, options, site_id, templates):
    """Create compute_image image.

    :param options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param site_id: site id
    :param templates: list of templates
    :param sharedarea: shared area params
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    availability_zone_id = templates[0].get("availability_zone_id")
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    self.update("PROGRESS", msg="Get provider %s" % cid)

    # create image
    image_params = {
        "name": "%s-avz%s" % (params.get("name"), site_id),
        "desc": "Zone Image %s" % params.get("desc"),
        "parent": availability_zone_id,
        "orchestrator_tag": params.get("orchestrator_tag"),
        "templates": templates,
        "attribute": {"configs": {"os": params.get("os"), "os_ver": params.get("os_ver")}},
    }
    res = provider.resource_factory(Image, **image_params)
    job_id = res[0]["jobid"]
    image_id = res[0]["uuid"]
    self.update(
        "PROGRESS",
        msg="Create image in availability zone %s - start job %s" % (availability_zone_id, job_id),
    )

    # link image to compute image
    self.release_session()
    self.get_session()
    compute_image = self.get_resource(oid)
    compute_image.add_link("%s-image-link" % image_id, "relation.%s" % site_id, image_id, attributes={})
    self.update("PROGRESS", msg="Link image %s to compute image %s" % (image_id, oid))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update("PROGRESS", msg="Create image in availability zone %s" % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_image_import_orchestrator_resource(self, options, orchestrator):
    """Create provider physical image.

    :param options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")
    template = orchestrator.get("template")
    self.update("PROGRESS", msg="Get configuration params")

    # get image resource
    self.get_session()
    resource = self.get_resource(oid)
    self.update("PROGRESS", msg="Get image %s" % oid)
    if template is not None:
        image_id = ProviderOrchestrator.get(orchestrator.get("type")).create_image(
            self,
            orchestrator["id"],
            resource,
            template["id"],
            template["template_pwd"],
            template["guest_id"],
        )
        return image_id
    return None


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_zone_template(self, options, site_id, templates):
    """Update compute_template template.

    :param sharedarea.options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea.site_id: site id
    :param sharedarea.templates: list of
    :param sharedarea.site_id:
    :param sharedarea.availability_zone_id:
    :param sharedarea.orchestrator_id: orchestrator id
    :param sharedarea.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
    :param sharedarea.template_id:
    :param sharedarea.sharedarea:
    :param sharedarea.cid: container id
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    availability_zone_id = templates[0].get("availability_zone_id")
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    self.update("PROGRESS", msg="Get provider %s" % cid)

    # check zone template already exists
    zone_templates = self.get_orm_linked_resources(oid, link_type="relation.%s" % site_id, container_id=cid)
    if len(zone_templates) > 0:
        zone_template = provider.get_resource(zone_templates[0].id)
        self.update(
            "PROGRESS",
            msg="Site %s already linked to compute image %s" % (site_id, oid),
        )

        # update template
        template_params = {
            "orchestrator_tag": params.get("orchestrator_tag"),
            "templates": templates,
        }
        res = zone_template.update(**template_params)
        job_id = res[0]["jobid"]
        self.update(
            "PROGRESS",
            msg="Update image in availability zone %s - start job %s" % (availability_zone_id, job_id),
        )

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
        res = provider.resource_factory(Image, **template_params)
        job_id = res[0]["jobid"]
        template_id = res[0]["uuid"]
        self.update(
            "PROGRESS",
            msg="Create image in availability zone %s - start job %s" % (availability_zone_id, job_id),
        )

        # link template to compute template
        self.release_session()
        self.get_session()
        compute_template = self.get_resource(oid)
        compute_template.add_link(
            "%s-image-link" % template_id,
            "relation.%s" % site_id,
            template_id,
            attributes={},
        )
        self.update("PROGRESS", msg="Link image %s to compute template %s" % (template_id, oid))

        # wait job complete
        res = self.wait_for_job_complete(job_id)
        self.update(
            "PROGRESS",
            msg="Create image in availability zone %s" % availability_zone_id,
        )

    return True
