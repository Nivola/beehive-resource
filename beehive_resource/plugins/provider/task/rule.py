# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive_resource.plugins.provider.entity.rule import Rule
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


def convert_source(task, zone_id, source):
    """Convert source and destination type from SecurityGroup in Environment
    of certain zone

    **Parameters:**

        * **task** (): celery task reference
        * **zone_id** (str): availability zone id
        * **source** (dict): dict like {'type':.., 'value':..}

    **Return:**

        {'type':'environment', 'value':..} or None
    """
    source_type = source["type"]
    source_value = source["value"]
    if source_type == "SecurityGroup":
        resource = task.get_resource(source_value)
        rgs = task.get_linked_resources(resource.oid, link_type="relation.%s" % zone_id)
        return {"type": "RuleGroup", "value": rgs[0].id}
    return {"type": source_type, "value": source_value}


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_rule(self, options):
    """Create super_rule resource - pre task

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

            * **cid**: container id
            * **orchestrator_tag**: orchestrator tag
            * **name**: rule name
            * **super_zone**: super zone id
            * **source**: source SecurityGroup, Instance, Cidr
            * **destination**: destination SecurityGroup, Instance, Cidr
            * **service**: service configuration [optional]

    **Return:**

    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")
    source = params.get("source")
    dest = params.get("destination")
    self.update("PROGRESS", msg="Get configuration params")

    # if source or dest are SecurityGroup link super rule
    sg_id = None
    self.get_session()
    if source["type"] == "SecurityGroup":
        self.get_session()
        sg_id = source["value"]
        sg = self.get_resource(sg_id)
        sg.add_link("%s-%s-rule-link" % (sg.oid, oid), "rule", oid, attributes={})
        self.update("PROGRESS", msg="Link rule %s to security group %s" % (oid, sg_id))
        self.release_session()
    if dest["type"] == "SecurityGroup" and dest["value"] != sg_id:
        self.get_session()
        sg_id = dest["value"]
        sg = self.get_resource(sg_id)
        sg.add_link("%s-%s-rule-link" % (sg.oid, oid), "rule", oid, attributes={})
        self.update("PROGRESS", msg="Link rule %s to security group %s" % (oid, sg_id))
        self.release_session()

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_rule(self, options, availability_zone_id):
    """Create zone rule.

    :param options: Tupla with some useful options.
        (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability_zone_id
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.site_id: site id
    :param sharedarea.orchestrator_id: orchestrator id
    :param sharedarea.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
    :param sharedarea.name: rule name
    :param sharedarea.super_zone: super zone id
    :param sharedarea.source: source SecurityGroup, Instance, Cidr
    :param sharedarea.destination: destination SecurityGroup, Instance, Cidr
    :param sharedarea.service: service configuration [optional]
    """
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    # rules = params.get('rules')
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id)
    site_id = availability_zone.parent_id
    self.update("PROGRESS", msg="Get provider %s" % cid)

    self.update("PROGRESS", msg="Convert source: %s" % params.get("source"))
    source = convert_source(self, site_id, params.get("source"))
    self.update("PROGRESS", msg="Convert destination: %s" % params.get("destination"))
    destination = convert_source(self, site_id, params.get("destination"))

    # create rule
    rule_params = {
        "name": "%s-avz%s" % (params.get("name"), site_id),
        "desc": "Zone rule %s" % params.get("desc"),
        "parent": availability_zone_id,
        "orchestrator_tag": params.get("orchestrator_tag"),
        "attribute": {
            "configs": {
                "source": source,
                "destination": destination,
                "service": params.get("service"),
            }
        },
        "source": source,
        "destination": destination,
        "service": params.get("service"),
    }
    res = provider.resource_factory(Rule, **rule_params)
    job_id = res[0]["jobid"]
    group_id = res[0]["uuid"]
    self.update(
        "PROGRESS",
        msg="Create rule group in availability zone %s - start job %s" % (availability_zone_id, job_id),
    )

    # link flavor to compute flavor
    self.release_session()
    self.get_session()
    compute_flavor = self.get_resource(oid)
    compute_flavor.add_link("%s-rule-link" % group_id, "relation.%s" % site_id, group_id, attributes={})
    self.update("PROGRESS", msg="Link rule %s to compute rule %s" % (group_id, oid))

    # wait job complete
    self.wait_for_job_complete(job_id)
    self.update(
        "PROGRESS",
        msg="Create rule %s in availability zone %s" % (group_id, availability_zone_id),
    )

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_patch_zone_rule(self, options):
    """Patch zone rule.

    :param options: Tupla with some useful options.
        (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: compute rule id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    # rules = params.get('rules')
    self.update("PROGRESS", msg="Get configuration params")

    # get provider
    self.get_session()
    compute_rule = self.get_resource(oid)
    self.update("PROGRESS", msg="Get compute rule %s" % compute_rule)

    # get zone rules
    zone_rules, tot = compute_rule.get_linked_resources(link_type_filter="relation%")

    # invoke zone_rule patch
    for zone_rule in zone_rules:
        res = zone_rule.patch()
        job_id = res[0]["jobid"]

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.update("PROGRESS", msg="Patch zone rule %s" % zone_rule)

    self.update("PROGRESS", msg="Patch compute rule %s" % oid)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_rule_create_orchestrator_resource(self, options, orchestrator):
    """Create provider physical rule.

    :param options: Tupla with some useful options.
            (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    source = params.get("source")
    destination = params.get("destination")
    service = params.get("service")
    zone_id = params.get("parent")
    self.update("PROGRESS", msg="Get configuration params")

    # get rule resource
    self.get_session()
    resource = self.get_resource(oid)
    zone = self.get_resource(zone_id)
    self.update("PROGRESS", msg="Get rule %s" % oid)

    rules = ProviderOrchestrator.get(orchestrator.get("type")).create_rule(
        self, orchestrator["id"], zone, resource, source, destination, service
    )
    return rules
