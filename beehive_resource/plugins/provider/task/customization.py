# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte
from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.customization import Customization
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_customization(self, options, avz_id, main):
    """Create compute_customization instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int avz_id: availability zone id
    :param bool main: if True this is the main zone
    :param dict customizationarea: input params
    :param customizationarea.cid: container id
    :param customizationarea.id: resource id
    :param customizationarea.objid: resource objid
    :param customizationarea.parent: resource parent id [default=None]
    :param customizationarea.cid: container id
    :param customizationarea.name: resource name
    :param customizationarea.desc: resource desc
    :param customizationarea.ext_id: resource ext_id [default=None]
    :param customizationarea.active: resource active [default=False]
    :param dict customizationarea.attribute: attributes [default={}]
    :param customizationarea.tags: comma separated resource tags to assign [default='']
    :param customizationarea.size: customization size, in GBs
    :param customizationarea.network: network
    :param customizationarea.network.vpc: vpc id
    :param customizationarea.network.vlan: network vlan
    :param customizationarea.orchestrator_tag: orchestrators tag
    :param customizationarea.orchestrator_type: orchestrator type. Ex. vsphere|openstack
    :param customizationarea.compute_zone: parent compute_zone
    :return: resource id
    """
    params = self.get_shared_data()

    logger.warn("Create ComputeTemplate: %s" % params)
    # input params
    cid = params.get("cid")
    oid = params.get("id")
    # customization_type = params.get('customization_type')
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    # availability_zone = self.get_resource(avz_id)
    self.update("PROGRESS", msg="Get resources")

    # create zone instance params
    instance_params = {
        "type": params.get("type"),
        "name": "zone-customization-%s" % params.get("name"),
        "desc": "Zone customization %s" % params.get("desc"),
        "parent": avz_id,
        "compute_customization": oid,
        "tags": params.get("tags"),
        "metadata": params.get("metadata"),
        "main": main,
        "attribute": {"main": main, "type": params.get("type")},
    }

    res = provider.resource_factory(Customization, **instance_params)
    job_id = res[0]["jobid"]
    customization_id = res[0]["uuid"]
    self.update(
        "PROGRESS",
        msg="Create customization in availability zone %s - start job %s" % (avz_id, job_id),
    )

    # wait job complete
    self.wait_for_job_complete(job_id)
    self.update(
        "PROGRESS",
        msg="Create customization %s in availability zone %s" % (customization_id, avz_id),
    )

    return customization_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_zone_customization(self, options, zone_customization_id, main):
    """Update compute_customization instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int zone_customization_id: availability zone customization id
    :param bool main: if True this is the main zone
    :param dict customizationarea: input params
    :param int customizationarea.cid: container id
    :param int customizationarea.id: resource id
    :param uuid customizationarea.uuid: resource uuid
    :param str customizationarea.objid: resource objid
    :param str customizationarea.ext_id: resource remote id
    :param dict customizationarea.attribute: resource attribute
    :param customizationarea.attribute.type: resource attribute type
    :param customizationarea.attribute.orchestrator_tag: resource attribute orchestrator_tag
    :param customizationarea.attribute.availability_zone: resource attribute availability_zone
    :param customizationarea.attribute.size: resource attribute size
    :param customizationarea.attribute.proto: resource attribute proto
    :param customizationarea.size: customization size in gb
    :param customizationarea.grant: grant configuration
    :param customizationarea.grant.access_level: The access level to the customization: ro, rw
    :param customizationarea.grant.access_type: The access rule type: ip, cert, user
    :param customizationarea.grant.access_to: The value that defines the access.
        - ip. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0.
        - cert. A valid value is any string up to 64 characters long in the common name (CN) of the certificate.
        - user. A valid value is an alphanumeric string that can contain some special characters and is from 4 to 32
          characters long
    :param int customizationarea.grant.access_id: The UUID of the access rule to which access is granted.
    :param str customizationarea.grant.action: Set grant action: add or del
    :return: resource id
    """
    params = self.get_customization_data()

    # input params
    oid = params.get("id")
    size = params.get("size", None)
    grant = params.get("grant", None)
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    compute_customization = self.get_resource(oid)
    zone_customization = self.get_resource(zone_customization_id)
    avz_id = zone_customization.parent_id
    self.update("PROGRESS", msg="Get resources")

    # update size
    if size is not None:
        old_size = params.get("attribute").get("size")
        res = zone_customization.update_size(old_size, size)
        job_id = res[0]["jobid"]
        self.update(
            "PROGRESS",
            msg="Update customization size in availability zone %s - start job %s" % (oid, job_id),
        )

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.update(
            "PROGRESS",
            msg="Update customization %s size in availability zone %s" % (oid, avz_id),
        )

        # update attributes
        attribs = compute_customization.get_attribs()
        attribs["size"] = size
        params["attribute"] = attribs
        self.set_customization_data(params)

    # set grant
    if grant is not None:
        res = zone_customization.grant_set(grant)
        job_id = res[0]["jobid"]
        self.update(
            "PROGRESS",
            msg="Update customization grant in availability zone %s - start job %s" % (oid, job_id),
        )

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.update(
            "PROGRESS",
            msg="Update customization %s grant in availability zone %s" % (oid, avz_id),
        )

    return zone_customization_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_customization(self, options):
    """Create customization

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict customizationarea: input params
    :customizationarea:
        * **objid**: resource objid
        * **parent**: resource parent id [default=None]
        * **cid**: container id
        * **name**: resource name
        * **desc**: resource desc
        * **ext_id**: resource ext_id [default=None]
        * **active**: resource active [default=False]
        * **attribute** (:py:class:`dict`): attributes [default={}]
        * **attribute.main** (:py:class:`dict`): if True set this as main zone customization
        * **tags**: comma separated resource tags to assign [default='']
        * **size**: customization size, in GBs
        * **compute_customization**: parent compute customization
    :return: resource id
    """
    params = self.get_customization_data()
    logger.warn("Create Template: %s" % params)

    main = params.get("main")
    oid = params.get("id")
    availability_zone_id = params.get("parent")
    compute_customization_id = params.get("compute_customization")
    self.update("PROGRESS", msg="Get configuration params")

    # get resources
    self.get_session()
    availability_zone = self.get_resource(availability_zone_id)
    compute_customization = self.get_resource(compute_customization_id)
    customization = self.get_resource(oid)
    self.update("PROGRESS", msg="Get resource %s" % oid)

    # create customization
    customization_id = None
    if main is True:
        # get main orchestrator
        main_orchestrator_id = params.get("main_orchestrator")
        orchestrator = params.get("orchestrators").get(main_orchestrator_id)

        # get remote parent for server
        objdef = orchestrator_mapping(orchestrator["type"], 0)
        parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

        customization_id = ProviderOrchestrator.get(orchestrator.get("type")).create_customization(
            self, orchestrator, customization, parent, params, compute_customization
        )

        self.update("PROGRESS", msg="Create customization: %s" % customization_id)

    return customization_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_customization(self, options, template_id):
    """Link zone customization to compute customization

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    compute_customization_id = params.get("compute_customization")
    availability_zone_id = params.get("parent")
    oid = params.get("id")
    self.update("PROGRESS", msg="Get configuration params")

    # link customization to compute customization
    self.get_session()
    compute_customization = self.get_resource(compute_customization_id, run_customize=False)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    compute_customization.add_link("%s-customization-link" % oid, "relation.%s" % site_id, oid, attributes={})
    self.update(
        "PROGRESS",
        msg="Link customization %s to compute customization %s" % (oid, compute_customization_id),
    )

    return oid
