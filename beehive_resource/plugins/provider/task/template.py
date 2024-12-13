# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.template import Template
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_template(self, options, avz_id):
    """Create compute_template instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int avz_id: availability zone id
    :param bool main: if True this is the main zone
    :param dict templatearea: input params
    :param templatearea.cid: container id
    :param templatearea.id: resource id
    :param templatearea.objid: resource objid
    :param templatearea.parent: resource parent id [default=None]
    :param templatearea.cid: container id
    :param templatearea.name: resource name
    :param templatearea.desc: resource desc
    :param templatearea.ext_id: resource ext_id [default=None]
    :param templatearea.active: resource active [default=False]
    :param dict templatearea.attribute: attributes [default={}]
    :param templatearea.tags: comma separated resource tags to assign [default='']
    :param templatearea.size: template size, in GBs
    :param templatearea.network: network
    :param templatearea.network.vpc: vpc id
    :param templatearea.network.vlan: network vlan
    :param templatearea.orchestrator_tag: orchestrators tag
    :param templatearea.orchestrator_type: orchestrator type. Ex. vsphere|openstack
    :param templatearea.compute_zone: parent compute_zone
    :return: resource id
    """
    params = self.get_shared_data()

    logger.warn("Create ComputeTemplate: %s" % params)
    # input params
    cid = params.get("cid")
    oid = params.get("id")
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    # availability_zone = self.get_resource(avz_id)
    self.update("PROGRESS", msg="Get resources")

    # create zone instance params
    instance_params = {
        "type": params.get("type"),
        "name": "zone-template-%s" % params.get("name"),
        "desc": "Zone template %s" % params.get("desc"),
        "parent": avz_id,
        "compute_template": oid,
        "tags": params.get("tags"),
        "metadata": params.get("metadata"),
        "attribute": params.get("configs", {}),
    }

    res = provider.resource_factory(Template, **instance_params)
    job_id = res[0]["jobid"]
    template_id = res[0]["uuid"]
    self.update(
        "PROGRESS",
        msg="Create template in availability zone %s - start job %s" % (avz_id, job_id),
    )

    # wait job complete
    self.wait_for_job_complete(job_id)
    self.update(
        "PROGRESS",
        msg="Create template %s in availability zone %s" % (template_id, avz_id),
    )

    return template_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_zone_template(self, options, zone_template_id):
    """Update compute_template instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int zone_template_id: availability zone template id
    :param bool main: if True this is the main zone
    :param dict templatearea: input params
    :param int templatearea.cid: container id
    :param int templatearea.id: resource id
    :param uuid templatearea.uuid: resource uuid
    :param str templatearea.objid: resource objid
    :param str templatearea.ext_id: resource remote id
    :param dict templatearea.attribute: resource attribute
    :param templatearea.attribute.type: resource attribute type
    :param templatearea.attribute.orchestrator_tag: resource attribute orchestrator_tag
    :param templatearea.attribute.availability_zone: resource attribute availability_zone
    :param templatearea.attribute.size: resource attribute size
    :param templatearea.attribute.proto: resource attribute proto
    :param templatearea.size: template size in gb
    :param templatearea.grant: grant configuration
    :param templatearea.grant.access_level: The access level to the template: ro, rw
    :param templatearea.grant.access_type: The access rule type: ip, cert, user
    :param templatearea.grant.access_to: The value that defines the access.
        - ip. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0.
        - cert. A valid value is any string up to 64 characters long in the common name (CN) of the certificate.
        - user. A valid value is an alphanumeric string that can contain some special characters and is from 4 to 32
          characters long
    :param int templatearea.grant.access_id: The UUID of the access rule to which access is granted.
    :param str templatearea.grant.action: Set grant action: add or del
    :return: resource id
    """
    params = self.get_template_data()

    # input params
    oid = params.get("id")
    size = params.get("size", None)
    grant = params.get("grant", None)
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    compute_template = self.get_resource(oid)
    zone_template = self.get_resource(zone_template_id)
    avz_id = zone_template.parent_id
    self.update("PROGRESS", msg="Get resources")

    # update size
    if size is not None:
        old_size = params.get("attribute").get("size")
        res = zone_template.update_size(old_size, size)
        job_id = res[0]["jobid"]
        self.update(
            "PROGRESS",
            msg="Update template size in availability zone %s - start job %s" % (oid, job_id),
        )

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.update(
            "PROGRESS",
            msg="Update template %s size in availability zone %s" % (oid, avz_id),
        )

        # update attributes
        attribs = compute_template.get_attribs()
        attribs["size"] = size
        params["attribute"] = attribs
        self.set_template_data(params)

    # set grant
    if grant is not None:
        res = zone_template.grant_set(grant)
        job_id = res[0]["jobid"]
        self.update(
            "PROGRESS",
            msg="Update template grant in availability zone %s - start job %s" % (oid, job_id),
        )

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.update(
            "PROGRESS",
            msg="Update template %s grant in availability zone %s" % (oid, avz_id),
        )

    return zone_template_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_template(self, options):
    """Create template

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict templatearea: input params
    :templatearea:
        * **objid**: resource objid
        * **parent**: resource parent id [default=None]
        * **cid**: container id
        * **name**: resource name
        * **desc**: resource desc
        * **ext_id**: resource ext_id [default=None]
        * **active**: resource active [default=False]
        * **attribute** (:py:class:`dict`): attributes [default={}]
        * **attribute.main** (:py:class:`dict`): if True set this as main zone template
        * **tags**: comma separated resource tags to assign [default='']
        * **size**: template size, in GBs
        * **compute_template**: parent compute template
    :return: resource id
    """
    params = self.get_template_data()
    logger.warn("Create Template: %s" % params)

    main = params.get("main", False)
    oid = params.get("id")
    availability_zone_id = params.get("parent")
    compute_template_id = params.get("compute_template")
    self.update("PROGRESS", msg="Get configuration params")

    # get resources
    self.get_session()
    availability_zone = self.get_resource(availability_zone_id)
    compute_template = self.get_resource(compute_template_id)
    template = self.get_resource(oid)
    self.update("PROGRESS", msg="Get resource %s" % oid)

    # create template
    template_id = None
    if main is True:
        # get main orchestrator
        main_orchestrator_id = params.get("main_orchestrator")
        orchestrator = params.get("orchestrators").get(main_orchestrator_id)

        # get remote parent for server
        objdef = orchestrator_mapping(orchestrator["type"], 0)
        parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

        template_id = ProviderOrchestrator.get(orchestrator.get("type")).create_template(
            self, orchestrator, template, parent, params, compute_template
        )

        self.update("PROGRESS", msg="Create template: %s" % template_id)

    return template_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_template(self, options):
    """Link zone template to compute template

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    compute_template_id = params.get("compute_template")
    availability_zone_id = params.get("parent")
    oid = params.get("id")
    self.update("PROGRESS", msg="Get configuration params")

    # link template to compute template
    self.get_session()
    compute_template = self.get_resource(compute_template_id, run_customize=False)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    compute_template.add_link("%s-template-link" % oid, "relation.%s" % site_id, oid, attributes={})
    self.update(
        "PROGRESS",
        msg="Link template %s to compute template %s" % (oid, compute_template_id),
    )

    return oid
