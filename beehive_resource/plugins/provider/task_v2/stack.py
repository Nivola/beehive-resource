# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beecell.simple import id_gen
from beehive.common import DNS_TTL
from beehive.common.task_v2 import task_step, run_sync_task, TaskError
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.stack import ComputeStack, Stack
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class StackTask(AbstractProviderResourceTask):
    """Stack task"""

    name = "stack_task"
    entity_class = ComputeStack

    @staticmethod
    @task_step()
    def link_compute_stack_step(task, step_id, params, *args, **kvargs):
        """Create compute stack links

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        compute_stack = task.get_resource(oid)

        link_params = params.get("link_params", [])
        for item in link_params:
            compute_stack.add_link(
                name="%s-%s-%s-%s-link" % (oid, item[1], item[0], id_gen()),
                type=item[0],
                end_resource=item[1],
                attributes={},
            )

        return oid, params

    @staticmethod
    @task_step()
    def create_zone_stack_step(task, step_id, params, template, stack_id, *args, **kvargs):
        """Create zone stack

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param template: template per availability zone
        :param template.site_id: id  of the site
        :param template.availability_zone_id: id  of the availability zone
        :param template.orchestrator_type: Orchestrator type. Can be openstack
        :param template.template_uri: remote template uri
        :param template.environment: additional environment
        :param template.parameters: stack input parameters
        :param template.files: stack input files
        :param stack_id: stack reference id
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        availability_zone_id = template.pop("availability_zone_id")
        site_id = template.pop("site_id")

        provider = task.get_container(cid)
        task.progress(step_id, msg="Get resources")

        # create zone stack
        stack_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone stack %s %s" % (params.get("name"), stack_id),
            "parent": availability_zone_id,
            "compute_stack": oid,
            "orchestrator_tag": params.get("orchestrator_tag"),
            "attribute": {"stack": True, "template_uri": template.get("template_uri")},
            "template": template,
        }
        prepared_task, code = provider.resource_factory(Stack, **stack_params)
        stack_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create stack %s in availability zone %s" % (stack_id, availability_zone_id),
        )

        return oid, params

    @staticmethod
    @task_step()
    def create_zone_stack_twins_step(task, step_id, params, availability_zone_id, stack_id, *args, **kvargs):
        """reate compute_stack stack.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone where create twins
        :param stack_id: stack reference id
        :return: stack_id, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        task.progress(step_id, msg="Get resources")

        # create zone stack
        stack_params = {
            "name": "zone-stack-twin-%s-%s" % (params.get("name"), stack_id),
            "desc": "Zone stack twin %s %s" % (params.get("name"), stack_id),
            "parent": availability_zone_id,
            "compute_stack": oid,
            "orchestrator_tag": params.get("orchestrator_tag"),
            "attribute": {"stack": False, "template_uri": None},
            "template": None,
            "server_confs": params.get("server_confs"),
        }
        prepared_task, code = provider.resource_factory(Stack, **stack_params)
        stack_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create stack twin %s in availability zone %s" % (stack_id, availability_zone_id),
        )

        return oid, params

    @staticmethod
    @task_step()
    def manage_compute_stack_step(task, step_id, params, *args, **kvargs):
        """Register compute stack in ssh module

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        key_name = params.get("key_name", None)

        compute_stack = task.get_resource(oid)

        uuid = None
        if key_name is not None:
            uuid = compute_stack.manage(user="root", key=params.get("key_name"), password="")
            task.progress(step_id, msg="Manage compute stack %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def unmanage_compute_stack_step(task, step_id, params, *args, **kvargs):
        """Deregister compute stack from ssh module

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")

        compute_stack = task.get_resource(oid)

        uuid = None
        if compute_stack.is_managed() is True:
            uuid = compute_stack.unmanage()
            task.progress(step_id, msg="Unmanage stack %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def register_dns_compute_stack_step(task, step_id, params, *args, **kvargs):
        """Register compute stack in dns

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        resolve = params.get("resolve")

        compute_stack = task.get_resource(oid)

        uuids = None
        if resolve is True:
            try:
                uuids = compute_stack.set_dns_recorda(force=True, ttl=DNS_TTL)
                task.progress(
                    step_id,
                    msg="Register stack %s in dns with records %s" % (oid, uuids),
                )
            except Exception as ex:
                task.progress(step_id, msg="Error - Register stack %s in dns: %s" % (oid, ex))
                raise TaskError("Register stack %s in dns: %s" % (oid, ex))

        return oid, params

    @staticmethod
    @task_step()
    def unregister_dns_compute_stack_step(task, step_id, params, *args, **kvargs):
        """Deregister compute stack from dns

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: stack_id, params
        """
        oid = params.get("id")

        compute_stack = task.get_resource(oid)

        uuids = None
        try:
            uuids = compute_stack.unset_dns_recorda()
            task.progress(step_id, msg="Unregister stack %s records %s from dns" % (oid, uuids))
        except Exception as ex:
            task.progress(step_id, msg="Error - Deregister stack %s from dns: %s" % (oid, ex))
            raise TaskError("Deregister stack %s in dns: %s" % (oid, ex))

        return oid, params

    @staticmethod
    @task_step()
    def link_stack_step(task, step_id, params, *args, **kvargs):
        """Link stack to compute stack

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        compute_stack_id = params.get("compute_stack")
        availability_zone_id = params.get("parent")
        oid = params.get("id")

        compute_stack = task.get_simple_resource(compute_stack_id)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        compute_stack.add_link("%s-stack-link" % oid, "relation.%s" % site_id, oid, attributes={})
        task.progress(step_id, msg="Link stack %s to compute stack %s" % (oid, compute_stack_id))

        return oid, params

    @staticmethod
    @task_step()
    def create_stack_step(task, step_id, params, *args, **kvargs):
        """Create main stack

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        availability_zone_id = params.get("parent")
        orchestrators = params.get("orchestrators")
        template = params.get("template")
        task.progress(step_id, msg="Get configuration params")

        if template is None:
            task.progress(step_id, msg="Skip stack creation. This is a twin")
            return None, params

        orchestrator_type = template.get("orchestrator_type")

        availability_zone = task.get_resource(availability_zone_id)
        stack = task.get_resource(oid)
        task.progress(step_id, msg="Get resource %s" % oid)

        # get main orchestrator
        orchestrator = orchestrators.pop(orchestrator_type)

        # get remote parent project for stack
        objdef = orchestrator_mapping(orchestrator["type"], 0)
        parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

        # create stack
        helper = task.get_orchestrator(orchestrator.get("type"), task, step_id, orchestrator, stack)
        stack_id, params2 = helper.create_stack(parent, template)
        task.set_shared_data(params2["server_confs"])
        task.progress(step_id, msg="Create stack: %s" % stack_id)

        return oid, params

    @staticmethod
    @task_step()
    def create_twins_step(task, step_id, params, *args, **kvargs):
        """Create zone stack twin

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: bool, params
        """
        oid = params.get("id")
        orchestrators = params.get("orchestrators")
        availability_zone_id = params.get("parent")
        template = params.get("template")
        server_confs = task.get_shared_data()
        task.progress(step_id, msg="Get configuration params")

        # create twins
        stack = task.get_resource(oid)
        availability_zone = task.get_resource(availability_zone_id)
        site_id = availability_zone.parent_id

        # create twins
        for server_conf in server_confs:
            vpc_id = server_conf["vpc"]
            # get site network
            network_id = task.get_orm_linked_resources(vpc_id, link_type="relation.%s" % site_id)[0].id
            subnet_cidr = server_conf["subnet_cidr"]
            fixed_ip = server_conf["ip_address"]
            security_groups = server_conf["security_groups"]
            rule_groups = []
            for item in security_groups:
                sg = task.get_simple_resource(item)
                rgs = task.get_orm_linked_resources(sg.oid, link_type="relation.%s" % site_id)
                rule_groups.append(rgs[0].id)

            # exec task after stack creation
            if template is not None:
                task.progress(step_id, msg="Create vsphere twin")
                orchestrator = orchestrators.pop("vsphere", None)
                if orchestrator is not None:
                    helper = task.get_orchestrator("vsphere", task, step_id, orchestrator, stack)
                    helper.create_ipset(fixed_ip, rule_groups)
                    task.progress(step_id, msg="Create vsphere twin - ok")
                    return False, params

            # exec task when stack creation skipped
            else:
                task.progress(step_id, msg="Create all the twin")

                orchestrator = orchestrators.pop("vsphere", None)
                if orchestrator is not None:
                    helper = task.get_orchestrator("vsphere", task, step_id, orchestrator, stack)
                    helper.create_ipset(fixed_ip, rule_groups)
                    task.progress(step_id, msg="Create vsphere twin - ok")

                orchestrator = orchestrators.pop("openstack", None)
                if orchestrator is not None:
                    helper = task.get_orchestrator("openstack", task, step_id, orchestrator, stack)
                    helper.create_port(network_id, subnet_cidr, fixed_ip, rule_groups)
                    task.progress(step_id, msg="Create openstack twin - ok")
                return True, params

        return False, params
