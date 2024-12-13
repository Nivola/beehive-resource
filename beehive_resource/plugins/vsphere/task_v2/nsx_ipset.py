# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte
from beedrones.vsphere.client import VsphereNotFound
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet
from beehive_resource.task_v2 import AbstractResourceTask


class NsxIpsetTask(AbstractResourceTask):
    """NsxIpsetTask"""

    name = "nsx_ipset_task"
    entity_class = NsxIpSet

    @staticmethod
    @task_step()
    def nsx_ipset_create_step(task, step_id, params, *args, **kvargs):
        """Create nsx ipset.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        name = params.get("name")
        desc = params.get("desc")
        cidr = params.get("cidr")

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # create nsx ipset
        inst_id = conn.network.nsx.ipset.create(name, desc, cidr)
        task.progress(step_id, msg="Create nsx ip set %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {"cidr": cidr}
        return inst_id, params

    @staticmethod
    @task_step()
    def nsx_ipset_delete_step(task, step_id, params, *args, **kvargs):
        """Delete nsx ipset.

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

        # delete vsphere ipset
        if resource.is_ext_id_valid() is True:
            try:
                conn.network.nsx.ipset.delete(ext_id)
                task.progress(step_id, msg="Delete nsx ip set %s" % ext_id)
            except VsphereNotFound:
                task.progress(step_id, msg="Nsx ip set %s does not exist anymore" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def ipset_add_security_group_step(task, step_id, params, *args, **kvargs):
        """Attach security group to ipset

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        security_group = params.get("security_group")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        if resource.has_security_group(security_group) is False:
            conn.network.nsx.sg.add_member(security_group, ext_id)
            task.progress(
                step_id,
                msg="Add security group %s to ipset %s" % (security_group, ext_id),
            )
        else:
            task.progress(
                step_id,
                msg="Security group %s is already attached to ipset %s" % (security_group, oid),
            )

        return oid, params

    @staticmethod
    @task_step()
    def ipset_del_security_group_step(task, step_id, params, *args, **kvargs):
        """Detach security group from ipset

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        security_group = params.get("security_group")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        if resource.has_security_group(security_group) is True:
            conn.network.nsx.sg.delete_member(security_group, ext_id)
            task.progress(
                step_id,
                msg="Remove security group %s from ipset %s" % (security_group, ext_id),
            )
        else:
            task.progress(
                step_id,
                msg="Security group %s is already attached to ipset %s" % (security_group, oid),
            )

        return oid, params
