# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.security_group import (
    RuleGroup,
    SecurityGroup,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class SecurityGroupTask(AbstractProviderResourceTask):
    """SecurityGroup task"""

    name = "securit_group_task"
    entity_class = SecurityGroup

    @staticmethod
    @task_step()
    def link_security_group_step(task, step_id, params, *args, **kvargs):
        """link rule group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        oid = params.get("id")
        compute_zone_id = params.get("compute_zone_id")

        compute_zone = task.get_simple_resource(compute_zone_id)
        task.progress(step_id, msg="Get compute_zone %s" % compute_zone_id)

        compute_zone.add_link("%s-sg-link" % oid, "sg", oid, attributes={})
        task.progress(step_id, msg="Link security group %s to zone %s" % (oid, compute_zone.oid))

        return oid, params

    @staticmethod
    @task_step()
    def create_rule_group_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """create rule group

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

        # create flavor
        group_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone security group %s" % params.get("desc"),
            "parent": availability_zone.oid,
            "orchestrator_tag": params.get("orchestrator_tag"),
            # "orchestrator_select_types": params.get("orchestrator_select_types"),
            # 'rules': rules,
            "attribute": {"configs": {}},
        }
        prepared_task, code = provider.resource_factory(RuleGroup, **group_params)
        group_id = prepared_task["uuid"]

        # link flavor to compute flavor
        task.get_session(reopen=True)
        sg = task.get_simple_resource(oid)
        sg.add_link(
            "%s-rulegroup-link" % group_id,
            "relation.%s" % site_id,
            group_id,
            attributes={},
        )
        task.progress(step_id, msg="Link rule group %s to security group %s" % (group_id, oid))

        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create rule group %s in availability zone %s" % (group_id, availability_zone_id),
        )

        return True, params

    @staticmethod
    @task_step()
    def rulegroup_create_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create security_group physical resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :return: sg_id, params
        """
        oid = params.get("id")
        availability_zone_id = params.get("parent")

        resource = task.get_resource(oid)
        availability_zone = task.get_resource(availability_zone_id)
        task.progress(step_id, msg="Get rule group %s" % oid)

        from beehive_resource.plugins.provider.task_v2.openstack import ProviderOpenstack
        from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere

        helper: ProviderVsphere = task.get_orchestrator(orchestrator.get("type"), task, step_id, orchestrator, resource)
        sg_id = helper.create_security_group(availability_zone)
        return sg_id, params
