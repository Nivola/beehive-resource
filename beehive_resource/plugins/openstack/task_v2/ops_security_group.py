# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beedrones.openstack.client import OpenstackNotFound, OpenstackError
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_security_group import (
    OpenstackSecurityGroup,
)
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class SecurityGroupTask(AbstractResourceTask):
    """SecurityGroup task"""

    name = "securitygroup_task"
    entity_class = OpenstackSecurityGroup

    @staticmethod
    @task_step()
    def security_group_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create openstack security group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        desc = params.get("desc")
        parent = params.get("parent")

        container = task.get_container(cid)
        conn = container.conn
        parent = container.get_simple_resource(parent)

        # create openstack security group
        inst = conn.network.security_group.create(name, desc, parent.ext_id)
        inst_id = inst["id"]
        OpenstackSecurityGroup.get_remote_securitygroup(container.controller, inst_id, container, inst_id)
        task.progress(step_id, msg="Create security group %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id

        return oid, params

    @staticmethod
    @task_step()
    def security_group_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update openstack security group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        name = params.get("name")
        desc = params.get("desc")

        container = task.get_container(cid)
        resource = container.get_simple_resource(oid)

        # update openstack security group
        if resource.is_ext_id_valid() is True:
            conn = container.conn
            conn.network.security_group.update(ext_id, name, desc)
            OpenstackSecurityGroup.get_remote_securitygroup(container.controller, ext_id, container, ext_id)
            task.progress(step_id, msg="Update security group %s" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def security_group_expunge_physical_step(task, step_id, params, *args, **kvargs):
        """Delete openstack security group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        container = task.get_container(cid)
        resource = container.get_simple_resource(oid)

        # update openstack security group
        if resource.is_ext_id_valid() is True:
            try:
                container.conn.network.security_group.get(ext_id)
            except:
                task.progress(step_id, msg="Security group %s does not already exist" % ext_id)
                return None

            # delete openstack security group
            container.conn.network.security_group.delete(ext_id)
            OpenstackSecurityGroup.get_remote_securitygroup(container.controller, ext_id, container, ext_id)
            task.progress(step_id, msg="Delete security group %s" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def security_group_rule_create_step(task, step_id, params, *args, **kvargs):
        """Create openstack security group rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: rule oid, params
        """
        cid = params.get("cid")
        ext_id = params.get("ext_id")
        direction = params.get("direction")
        ethertype = params.get("ethertype")
        port_range_min = params.get("port_range_min")
        port_range_max = params.get("port_range_max")
        protocol = params.get("protocol")
        remote_group_ext_id = params.get("remote_group_extid")
        remote_ip_prefix = params.get("remote_ip_prefix")

        container = task.get_container(cid)
        conn = container.conn
        rule = conn.network.security_group.create_rule(
            ext_id,
            direction,
            ethertype=ethertype,
            port_range_min=port_range_min,
            port_range_max=port_range_max,
            protocol=protocol,
            remote_group_id=remote_group_ext_id,
            remote_ip_prefix=remote_ip_prefix,
        )
        task.progress(step_id, msg="Create new security group %s rule %s" % (ext_id, rule["id"]))

        # set resource id in shared data
        params["result"] = rule["id"]
        task.set_shared_data(params)

        return rule["id"], params

    @staticmethod
    @task_step()
    def security_group_rule_delete_step(task, step_id, params, *args, **kvargs):
        """Create openstack security group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: rule oid, params
        """
        cid = params.get("cid")
        ext_id = params.get("ext_id")
        rule_id = params.get("rule_id")

        container = task.get_container(cid)
        conn = container.conn
        try:
            conn.network.security_group.delete_rule(rule_id)
        except OpenstackNotFound as ex:
            logger.warning(ex)
        except OpenstackError as ex:
            if ex.code == 404:
                logger.warning(ex)
            else:
                raise
        except Exception:
            raise
        task.progress(step_id, msg="Remove security group %s rule %s" % (ext_id, rule_id))

        # set resource id in shared data
        params["result"] = rule_id

        return rule_id, params

    @staticmethod
    @task_step()
    def security_group_rule_reset_step(task, step_id, params, *args, **kvargs):
        """Delete all rules of a security group.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        ext_id = params.get("ext_id")

        container = task.get_container(cid)
        conn = container.conn
        grp = conn.network.security_group.get(ext_id)
        rules = []
        for rule in grp["security_group_rules"]:
            conn.network.security_group.delete_rule(rule["id"])
            rules.append(rule["id"])
            task.progress(step_id, msg="remove security group %s rule %s" % (ext_id, rule))

        return True, params


task_manager.tasks.register(SecurityGroupTask())
