# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beedrones.vsphere.client import VsphereError
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup
from beehive_resource.task_v2 import AbstractResourceTask, truncate


class NsxSecurityGroupTask(AbstractResourceTask):
    """NsxSecurityGroupTask"""

    name = "nsx_security_group_task"
    entity_class = NsxSecurityGroup

    def __init__(self, *args, **kwargs):
        super(NsxSecurityGroupTask, self).__init__(*args, **kwargs)

    @staticmethod
    @task_step()
    def nsx_security_group_create_step(task, step_id, params, *args, **kvargs):
        """Create nsx security_group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")

        container = task.get_container(cid)
        conn = container.conn

        # create nsx security_group
        sgid = conn.network.nsx.sg.create(name)
        params["ext_id"] = sgid
        params["attrib"] = {}
        task.progress(step_id, msg="Create security group: %s" % sgid)

        return oid, params

    @staticmethod
    @task_step()
    def nsx_security_group_delete_step(task, step_id, params, *args, **kvargs):
        """Delete nsx security_group

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        # delete vsphere security_group
        if resource.is_ext_id_valid() is True:
            try:
                conn.network.nsx.sg.get(ext_id)
            except VsphereError:
                task.progress(step_id, msg="Security group %s does not already exist" % ext_id)
                return None

            # search if security group is used in dfw rules
            rules = conn.network.nsx.dfw.filter_rules(security_groups=[ext_id])
            task.progress(
                step_id,
                msg="Security group %s is used by rules: %s" % (ext_id, [r.get("id") for r in rules]),
            )
            for rule in rules:
                sectionid = rule.get("sectionId")
                ruleid = rule.get("id")

                # check rule exists
                try:
                    rule = conn.network.nsx.dfw.get_rule(sectionid, ruleid)
                except VsphereError:
                    rule = {}
                if rule == {}:
                    task.progress(step_id, msg="Rule %s:%s does not exist" % (sectionid, ruleid))
                else:
                    # delete nsx dfw rule
                    conn.network.nsx.dfw.delete_rule(sectionid, ruleid)
                    task.progress(step_id, msg="Delete nsx dfw rule %s:%s" % (sectionid, ruleid))

            conn.network.nsx.sg.delete(ext_id)
            # update task
            task.progress(step_id, msg="Delete security group: %s" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def nsx_security_group_add_member_step(task, step_id, params, *args, **kvargs):
        """Add nsx security_group member

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        member_ext_id = params.get("member")
        sg_ext_id = params.get("security_group")

        container = task.get_container(cid)
        conn = container.conn

        # create nsx security_group
        conn.network.nsx.sg.add_member(sg_ext_id, member_ext_id)

        return True, params

    @staticmethod
    @task_step()
    def nsx_security_group_delete_member_step(task, step_id, params, *args, **kvargs):
        """Delete nsx security_group member

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        member_ext_id = params.get("member")
        sg_ext_id = params.get("security_group")

        container = task.get_container(cid)
        conn = container.conn

        # create nsx security_group
        conn.network.nsx.sg.delete_member(sg_ext_id, member_ext_id)

        return True, params
