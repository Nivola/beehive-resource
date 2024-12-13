# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.rule import ComputeRule, Rule
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


def convert_source(task, zone_id, source):
    """Convert source and destination type from SecurityGroup in Environment of certain zone

    :param task: celery task reference
    :param zone_id: availability zone id
    :param source: dict like {'type':.., 'value':..}
    :return: {'type':'environment', 'value':..} or None
    """
    source_type = source["type"]
    source_value = source["value"]
    if source_type == "SecurityGroup":
        resource = task.get_resource(source_value)
        rgs = task.get_orm_linked_resources(resource.oid, link_type="relation.%s" % zone_id)
        return {"type": "RuleGroup", "value": rgs[0].id}
    return {"type": source_type, "value": source_value}


class RuleTask(AbstractProviderResourceTask):
    """Rule task"""

    name = "rule_task"
    entity_class = ComputeRule

    @staticmethod
    @task_step()
    def link_rule_step(task, step_id, params, *args, **kvargs):
        """Link zone rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        source = params.get("source")
        dest = params.get("destination")

        # if source or dest are SecurityGroup link super rule
        sg_id = None
        if source["type"] == "SecurityGroup":
            task.get_session(reopen=True)
            sg_id = source["value"]
            sg = task.get_simple_resource(sg_id)
            sg.add_link("%s-%s-rule-link" % (sg.oid, oid), "rule", oid, attributes={})
            task.progress(step_id, msg="Link rule %s to security group %s" % (oid, sg_id))
        if dest["type"] == "SecurityGroup" and dest["value"] != sg_id:
            task.get_session(reopen=True)
            sg_id = dest["value"]
            sg = task.get_simple_resource(sg_id)
            sg.add_link("%s-%s-rule-link" % (sg.oid, oid), "rule", oid, attributes={})
            task.progress(step_id, msg="Link rule %s to security group %s" % (oid, sg_id))

        return oid, params

    @staticmethod
    @task_step()
    def create_zone_rule_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Link zone rule

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
        site_id = availability_zone.parent_id
        task.progress(step_id, msg="Get provider %s" % cid)

        task.progress(step_id, msg="Convert source: %s" % params.get("source"))
        source = convert_source(task, site_id, params.get("source"))
        task.progress(step_id, msg="Convert destination: %s" % params.get("destination"))
        destination = convert_source(task, site_id, params.get("destination"))

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
            "reserved": params.get("reserved"),
            "rule_orchestrator_types": params.get("rule_orchestrator_types"),
        }
        prepared_task, code = provider.resource_factory(Rule, **rule_params)
        group_id = prepared_task["uuid"]

        # link rule to compute rule
        task.get_session(reopen=True)
        compute_rule = task.get_simple_resource(oid)
        compute_rule.add_link("%s-rule-link" % group_id, "relation.%s" % site_id, group_id, attributes={})
        task.progress(step_id, msg="Link rule %s to compute rule %s" % (group_id, oid))

        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create rule %s in availability zone %s" % (group_id, availability_zone_id),
        )

        return True, params

    @staticmethod
    @task_step()
    def patch_zone_rule_step(task, step_id, params, *args, **kvargs):
        """Patch zone rule.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        compute_rule = task.get_simple_resource(oid)
        task.progress(step_id, msg="Get compute rule %s" % compute_rule)

        # get zone rules
        zone_rules, tot = compute_rule.get_orm_linked_resources(link_type_filter="relation%")

        # invoke zone_rule patch
        for zone_rule in zone_rules:
            prepared_task, code = zone_rule.patch()
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg="Patch zone rule %s" % zone_rule)

        task.progress(step_id, msg="Patch compute rule %s" % oid)

        return True, params

    @staticmethod
    @task_step()
    def rule_create_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create orchestrator rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        source = params.get("source")
        destination = params.get("destination")
        service = params.get("service")
        zone_id = params.get("parent")
        reserved = params.get("reserved")
        rule_orchestrator_types = params.get("rule_orchestrator_types")

        resource = task.get_resource(oid)
        zone = task.get_resource(zone_id)
        task.progress(step_id, msg="Get rule %s" % oid)

        orchestrator_type = orchestrator.get("type")
        helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)
        if reserved:
            if rule_orchestrator_types is not None and orchestrator_type in rule_orchestrator_types:
                helper.create_rule(zone, source, destination, service, reserved)
        else:
            helper.create_rule(zone, source, destination, service, reserved)
        return True, params
