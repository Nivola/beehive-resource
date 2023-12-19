# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.task_v2 import task_step, run_sync_task, TaskError
from beehive_resource.plugins.provider.entity.load_balancer import (
    ComputeLoadBalancer,
    LoadBalancer,
)
from beehive_resource.plugins.provider.entity.rule import ComputeRule
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beecell.simple import dict_get, import_class

from logging import getLogger

logger = getLogger(__name__)


class LoadBalancerTask(AbstractProviderResourceTask):
    """Load Balancer task"""

    name = "load_balancer_task"
    entity_class = ComputeLoadBalancer

    @staticmethod
    @task_step()
    def create_zone_load_balancer_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create compute load balancer

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

        # create load balancer
        load_balancer_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone load balancer %s" % params.get("name"),
            "parent": availability_zone_id,
            "orchestrator_tag": params.get("orchestrator_tag"),
            "orchestrator_type": dict_get(params, "attribute.orchestrator_type"),
            "lb_configs": params.get("lb_configs"),
            "helper_class": dict_get(params, "attribute.helper_class"),
            "attribute": {},
        }
        prepared_task, code = provider.resource_factory(LoadBalancer, **load_balancer_params)
        load_balancer_id = prepared_task["uuid"]

        # add link between load balancer and compute load balancer
        task.get_session(reopen=True)
        compute_load_balancer = task.get_simple_resource(oid)
        compute_load_balancer.add_link(
            "%s-lb-link" % load_balancer_id,
            "relation.%s" % site_id,
            load_balancer_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link load balancer %s to compute load balancer %s" % (load_balancer_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create load balancer in availability zone %s" % availability_zone_id,
        )

        return True, params

    @staticmethod
    @task_step()
    def create_load_balancer_physical_resource_step(task, step_id, params, orchestrator_type, *args, **kvargs):
        """Create load balancer physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator_type: orchestrator type
        :return: gateway_id, params
        """
        oid = params.get("id")

        # get orchestrator
        avz_id = params.get("parent")
        avz = task.controller.get_simple_resource(avz_id)
        orchestrator_idx = avz.get_orchestrators(select_types=[orchestrator_type])
        orchestrator = list(orchestrator_idx.values())[0]

        # create helper
        helper_class_path = params.get("helper_class")
        helper_class = import_class(helper_class_path)
        helper = helper_class(task.controller, orchestrator, None)

        # create physical resource
        lb_configs = params.get("lb_configs")
        res = helper.create_load_balancer(**lb_configs)
        task.progress(
            step_id,
            msg="Create load balancer %s on %s" % (lb_configs.get("name"), helper.orchestrator.get("type")),
        )

        # get zone resource
        load_balancer: LoadBalancer = task.get_simple_resource(oid)

        # update zone resource attributes
        net_appl_id = lb_configs.get("network_appliance")
        load_balancer.set_configs(key="network_appliance", value=net_appl_id)
        ip_pool = dict_get(lb_configs, "vip.ip_pool")
        load_balancer.set_configs(key="ip_pool", value=ip_pool)
        for k, v in res.items():
            load_balancer.set_configs(key=k, value=v)

        return True, params

    @staticmethod
    @task_step()
    def update_load_balancer_step(task, step_id, params, site_id, balanced_targets, *args, **kvargs):
        """

        :param task:
        :param step_id:
        :param params:
        :param site_id:
        :param balanced_targets:
        :param args:
        :param kvargs:
        :return:
        """
        oid = params.get("id")

        helper, zone_resource = LoadBalancerTask.__commons(task, params)
        zone_resource: LoadBalancer
        zn_attribs = zone_resource.get_attribs()

        # update load balancer
        lb_configs = params.get("lb_configs")
        res = helper.update_load_balancer(lb_configs, zn_attribs)
        task.progress(
            step_id,
            msg="Update load balancer %s in availability zone %s" % (oid, site_id),
        )

        # update zone resource attributes
        if res.get("fw_rules") is not None:
            fw_rule = dict_get(res, "fw_rules.edge2backend")
            if fw_rule is None:  # so called edge2backend fw rule was deleted
                fw_rules = zone_resource.get_attribs(key="fw_rules")
                del fw_rules["edge2backend"]
                zone_resource.set_configs(key="fw_rules", value=fw_rules)
            else:  # so called edge2backend fw rule was updated
                zone_resource.set_configs(key="fw_rules.edge2backend", value=fw_rule)

            # TODO: add check on interpod fw rule

        # update compute resource attributes
        compute_resource: ComputeLoadBalancer = task.get_simple_resource(oid)
        compute_resource.set_configs(key="balanced_targets", value=balanced_targets)

        return True, params

    @staticmethod
    @task_step()
    def update_zone_load_balancer_step(task, step_id, params, *args, **kvargs):
        """

        :param step_id:
        :param params:
        :param site_id:
        :param balanced_targets:
        :param args:
        :param kvargs:
        :return:
        """
        oid = params.get("id")
        attribute = params.get("attribute")
        # update zone resource attributes
        zone_resource: LoadBalancer = task.get_simple_resource(oid)
        zone_resource.update_internal(attribute=attribute)

        return True, params

    @staticmethod
    @task_step()
    def delete_load_balancer_step(task, step_id, params, resource_id, *args, **kvargs):
        """Delete load balancer

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param resource_id: id of the resource to delete
        :return: True, params
        """
        helper, resource = LoadBalancerTask.__commons(task, params)
        resource: LoadBalancer
        attribs = resource.get_attribs()

        # delete physical load balancer
        res = helper.delete_load_balancer(**attribs)
        task.progress(step_id, msg="Delete load balancer")

        # release allocated ip address
        ip_pool = attribs.get("ip_pool")
        ip_addr = dict_get(attribs, "vnic.uplink.secondary_ip")
        res = helper.release_ip_address(ip_pool, ip_addr)
        task.progress(step_id, msg="Release ip address: %s" % ip_addr)

        # delete zone load balancer
        prepared_task, code = resource.expunge(sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Remove child %s" % resource_id)

        return True, params

    @staticmethod
    @task_step()
    def import_zone_load_balancer_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Import load balancer zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: physical resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        lb_config = dict_get(params, "configs")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id

        # create zone instance params
        lb_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Availability zone load balancer %s" % params.get("desc"),
            "parent": availability_zone_id,
            "compute_load_balancer": oid,
            "attribute": {},
            "configs": lb_config,
        }
        prepared_task, code = provider.resource_import_factory(LoadBalancer, **lb_params)
        lb_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Import load balancer %s in availability zone %s" % (lb_id, availability_zone_id))
        return lb_id, params

    @staticmethod
    @task_step()
    def import_physical_load_balancer_step(task, step_id, params, *args, **kvargs):
        """

        :param task:
        :param step_id:
        :param params:
        :param args:
        :param kvargs:
        :return:
        """
        oid = params.get("id")

        # get compute load balancer
        compute_resource_id = params.get("compute_load_balancer")
        compute_resource: ComputeLoadBalancer = task.get_simple_resource(compute_resource_id)

        helper_class_path = dict_get(params, "configs.helper_class")
        helper_class = import_class(helper_class_path)

        orchestrator_type = compute_resource.get_attribs(key="orchestrator_type")

        # get zone load balancer
        resource: LoadBalancer = task.get_simple_resource(oid)

        # get orchestrator
        avz_id = resource.parent_id
        avz = task.get_simple_resource(avz_id)
        site_id = avz.parent_id
        orchestrator_idx = avz.get_orchestrators(select_types=[orchestrator_type])
        orchestrator = list(orchestrator_idx.values())[0]

        # create helper
        helper = helper_class(
            controller=compute_resource.controller,
            orchestrator=orchestrator,
            compute_zone=compute_resource.get_parent(),
        )

        # import zone load balancer
        res = helper.import_load_balancer(**params)

        # update zone load balancer attributes
        resource.set_configs(key="has_quotas", value=True)
        for k, v in res.items():
            resource.set_configs(key=k, value=v)

        # add link between compute load balancer and zone load balancer
        compute_resource.add_link("%s-lb-link" % oid, "relation.%s" % site_id, oid, attributes={})
        task.progress(step_id, msg="Link instance %s to compute instance %s" % (oid, compute_resource_id))

        return oid, params

    @staticmethod
    @task_step()
    def run_action_step(task, step_id, params, *args, **kvargs):
        """

        :param task:
        :param step_id:
        :param params:
        :param args:
        :param kvargs:
        :return:
        """
        helper, resource = LoadBalancerTask.__commons(task, params)
        resource: LoadBalancer
        attribs = resource.get_attribs()

        action = params.get("action_name")

        # run action
        check = getattr(helper, action, None)
        if check is not None:
            check(**attribs)

        return True, params

    @staticmethod
    def __commons(task, params):
        """

        :param task:
        :param params:
        :return:
        """
        oid = params.get("id")

        # get compute load balancer
        compute_resource: ComputeLoadBalancer = task.get_simple_resource(oid)

        orchestrator_type = compute_resource.get_attribs(key="orchestrator_type")
        site = compute_resource.get_attribs(key="site")
        helper_class_path = compute_resource.get_attribs(key="helper_class")

        # get zone load balancer
        resources, tot = compute_resource.get_linked_resources(
            link_type_filter="relation.%s" % site,
            objdef=LoadBalancer.objdef,
            with_perm_tag=False,
        )
        if tot != 1:
            raise TaskError("Load balancer resource on site %s not found or is not unique" % site)
        resource = resources[0]

        # get orchestrator
        avz_id = resource.parent_id
        avz = task.get_simple_resource(avz_id)
        orchestrator_idx = avz.get_orchestrators(select_types=[orchestrator_type])
        orchestrator = list(orchestrator_idx.values())[0]

        # instantiate helper
        helper_class = import_class(helper_class_path)
        helper = helper_class(
            controller=compute_resource.controller,
            orchestrator=orchestrator,
            compute_zone=compute_resource.get_parent(),
        )

        return helper, resource
