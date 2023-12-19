# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from time import sleep

from beecell.simple import random_password
from beehive_resource.plugins.provider.entity.bastion import ComputeBastion
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.rule import ComputeRule
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.task_v2 import (
    AbstractProviderResourceTask,
    dict_get,
)

logger = getLogger(__name__)


class ComputeBastionTask(AbstractProviderResourceTask):
    """ComputeBastionTask task"""

    name = "compute_bastion_task"
    entity_class = ComputeBastion

    def __init__(self, *args, **kwargs):
        super(ComputeBastionTask, self).__init__(*args, **kwargs)

    @staticmethod
    @task_step()
    def link_compute_bastion_step(task, step_id, params, *args, **kvargs):
        """Create main links

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        compute_zone_id = params.get("parent")

        compute_zone = task.get_simple_resource(compute_zone_id)
        task.progress(step_id, msg="get compute zone %s" % oid)

        # link bastion to compute zone
        compute_zone.add_link("%s-bastion-link" % oid, "bastion", oid, attributes={})
        task.progress(step_id, msg="Link bastion %s to compute zone %s" % (oid, compute_zone_id))
        #         beehive3 res links add 517661-551542-bastion-link bastion 517661 551542 -attributes \{
        #         \"host\":\"84.1.2.3\",\"port\":\"1\"\} -e podto1

        return oid, params

    @staticmethod
    @task_step()
    def create_bastion_security_group_step(task, step_id, params, *args, **kvargs):
        """Create bastion security group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")
        name = params.get("name")
        compute_zone_id = params.get("parent")
        acls = params.get("acl", [])

        provider = task.get_container(cid)
        compute_zone = task.get_simple_resource(compute_zone_id)
        compute_zone.set_container(provider)
        vpc = compute_zone.get_default_vpc()
        task.progress(step_id, msg="get resource %s" % oid)

        # create security group
        sg_params = {
            "parent": vpc.oid,
            "name": "SG-%s" % name,
            "desc": "Availability Zone volume %s" % params.get("desc"),
            "compute_zone": params.get("parent"),
            "sync": True,
        }
        prepared_task, code = provider.resource_factory(SecurityGroup, has_quotas=False, **sg_params)
        sg_id = prepared_task["uuid"]

        # add SgBastionHost01 to bastion security group
        params["security_groups"].append(sg_id)

        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create security group %s" % sg_id)

        # create rule in security group
        index = 0
        for acl in acls:
            rule_params = {
                "parent": compute_zone_id,
                "name": "RuleBastionHost0%s" % index,
                "desc": "Availability Zone volume %s" % params.get("desc"),
                "compute_zone": params.get("parent"),
                "source": {"type": "Cidr", "value": acl.get("subnet")},
                "destination": {"type": "SecurityGroup", "value": sg_id},
                "service": {"protocol": "tcp", "port": "22"},
                "reserved": True,
                "sync": True,
            }
            prepared_task, code = provider.resource_factory(ComputeRule, has_quotas=False, **rule_params)
            index += 1
            rule_id = prepared_task["uuid"]

            # wait task complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg="Create security rule %s" % rule_id)

        return oid, params

    @staticmethod
    @task_step()
    def create_gateway_nat_step(task, step_id, params, *args, **kvargs):
        """Create create gateway nat and firewall rules

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")
        compute_zone_id = params.get("parent")
        nat_data = dict_get(params, "attribute.nat")
        acls = params.get("acl", [])

        resource = task.get_simple_resource(oid)
        provider = task.get_container(cid)
        compute_zone = task.get_simple_resource(compute_zone_id)
        compute_zone.set_container(provider)
        task.progress(step_id, msg="get resource %s" % oid)

        # get nat ipaddress and port
        gw = compute_zone.get_default_gateway()
        nat_ip_address = nat_data.get("ip_address")
        nat_port = nat_data.get("port")

        # add nat rule
        gw.add_nat_rule(
            action="dnat",
            original_address=nat_ip_address,
            translated_address=resource.get_ip_address(),
            original_port=nat_port,
            translated_port=22,
            protocol="tcp",
            vnic=0,
            role="default",
            enabled=True,
            logged=False,
        )
        task.progress(step_id, msg="create nat rule for bastion")

        # add firewall rule
        source = ",".join(["ip:%s" % acl.get("subnet") for acl in acls])
        appl = "ser:tcp+11100+any"
        gw.add_firewall_rule(
            action="accept",
            enabled=True,
            logged=False,
            direction=None,
            source=source,
            dest=None,
            appl=appl,
            role="default",
        )
        task.progress(step_id, msg="create firewall rule for bastion from %s" % source)

        return oid, params

    @staticmethod
    @task_step()
    def install_zabbix_proxy_step(task, step_id, params, *args, **kvargs):
        """install zabbix proxy

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        resource = task.get_resource(oid)
        task.progress(step_id, msg="get resource %s" % oid)

        prepared_task, code = resource.action("install_zabbix_proxy", sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="install zabbix proxy on gateway %s" % oid)

        return oid, params

    # @staticmethod
    # @task_step()
    # def install_zabbix_proxy_step(task, step_id, params, *args, **kvargs):
    #     """install zabbix proxy
    #
    #     :param task: parent celery task
    #     :param str step_id: step id
    #     :param dict params: step params
    #     :return: oid, params
    #     """
    #     oid = params.get('id')
    #     resource = task.get_resource(oid)
    #     task.progress(step_id, msg='get resource %s' % oid)
    #
    #     prepared_task, code = resource.action('install_zabbix_proxy', sync=True)
    #     run_sync_task(prepared_task, task, step_id)
    #     task.progress(step_id, msg='install zabbix proxy on gateway %s' % oid)
    #
    #     return oid, params

    @staticmethod
    @task_step()
    def enable_monitoring_step(task, step_id, params, *args, **kvargs):
        """enable monitoring

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        resource = task.get_resource(oid)
        task.progress(step_id, msg="get resource %s" % oid)

        prepared_task, code = resource.action("enable_monitoring", sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="enable monitoring on gateway %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def disable_monitoring_step(task, step_id, params, *args, **kvargs):
        """disable monitoring

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        resource = task.get_resource(oid)
        task.progress(step_id, msg="get resource %s" % oid)

        prepared_task, code = resource.action("disable_monitoring", sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="disable monitoring on gateway %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def create_user_gateway_step(task, step_id, params, *args, **kvargs):
        """Create create user gateway

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        key_name = params.get("key_name", None)

        from beehive_resource.plugins.provider.entity.instance import ComputeInstance

        resource: ComputeInstance = task.get_resource(oid)
        task.progress(step_id, msg="get resource %s" % oid)

        # logger.debug('+++++ create_user_gateway_step - sleep')
        # sleep(30) # 30, altrimenti il task "wait_ssh_is_up non parte!"

        # add_user è un action di ComputeInstance (parent di ComputeBastion)
        prepared_task, code = resource.action(
            "add_user",
            user_name="gateway",
            user_pwd=random_password(length=20),
            user_ssh_key=key_name,
            sync=True,
        )
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="create bastion %s user gateway" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def delete_bastion_security_group_step(task, step_id, params, *args, **kvargs):
        """Delete bastion security group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")

        resource = task.get_resource(oid)
        provider = task.get_container(cid)
        task.progress(step_id, msg="get resource %s" % oid)

        sg_bastion = resource.get_bastion_security_group()
        rules = sg_bastion.get_rules()

        # remove rules
        for rule in rules:
            rule.set_container(provider)
            prepared_task, code = rule.delete(sync=True)
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg="remove bastion security group rule %s" % rule.oid)

        # remove bastion security groups link
        links, total = resource.get_links(type="security-group", size=-1)
        for link in links:
            link.expunge()
            task.progress(step_id, msg="remove bastion security group link %s" % link.oid)

        # remove security group
        sg_bastion.set_container(provider)
        prepared_task, code = sg_bastion.delete(sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="remove bastion security group %s" % sg_bastion.oid)

        return oid, params

    @task_step()
    def delete_gateway_nat_step(task, step_id, params, *args, **kvargs):
        """delete create_gateway_nat

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")
        acls = params.get("acl", [])

        resource = task.get_simple_resource(oid)
        provider = task.get_container(cid)
        compute_zone = resource.get_parent()
        compute_zone.set_container(provider)
        task.progress(step_id, msg="get resource %s" % oid)

        # get nat ipaddress and port
        nat_data = resource.get_attribs(key="nat")
        gw = compute_zone.get_default_gateway()
        nat_ip_address = nat_data.get("ip_address")
        nat_port = nat_data.get("port")

        # add nat rule
        gw.del_nat_rule(
            action="dnat",
            original_address=nat_ip_address,
            translated_address=resource.get_ip_address(),
            original_port=nat_port,
            translated_port=22,
            protocol="tcp",
            vnic=0,
            role="default",
        )
        task.progress(step_id, msg="delete nat rule for bastion")

        # add firewall rule
        for acl in acls:
            source = "ip:%s" % acl.get("subnet")
            gw.del_firewall_rule(
                action="accept",
                enabled=True,
                logged=False,
                direction=None,
                source=source,
                dest=None,
                appl=None,
                role="default",
            )
            task.progress(step_id, msg="delete firewall rule for bastion from %s" % source)

        return oid, params
