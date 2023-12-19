# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class PortTask(AbstractResourceTask):
    """Port task"""

    name = "port_task"
    entity_class = OpenstackPort

    @staticmethod
    @task_step()
    def port_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        # validate input params
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        network = params.get("network")
        fixed_ips = params.get("fixed_ips")
        host_id = params.get("host_id")
        profile = params.get("profile")
        vnic_type = params.get("vnic_type")
        device_owner = params.get("device_owner")
        device_id = params.get("device_id")
        sgs = params.get("security_groups")
        mac_address = params.get("mac_address")
        project_ext_id = params.get("project_ext_id")

        container = task.get_container(cid)

        # create openstack network port
        conn = container.conn
        inst = conn.network.port.create(
            name,
            network,
            fixed_ips,
            host_id,
            profile,
            vnic_type,
            device_owner,
            device_id,
            sgs,
            mac_address,
            project_ext_id,
        )
        inst_id = inst["id"]
        task.progress(step_id, msg="Create port %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def port_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def port_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check port exists
                conn.network.port.get(resource.ext_id)

                # delete openport port
                conn.network.port.delete(resource.ext_id)
                task.progress(step_id, msg="Delete port %s" % resource.ext_id)
            except:
                pass

        return oid, params

    @staticmethod
    @task_step()
    def port_add_security_group_step(task, step_id, params, *args, **kvargs):
        """Attach security group to port

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
        # resource = container.get_simple_resource(oid)

        conn.network.port.add_security_group(ext_id, security_group)
        task.progress(step_id, msg="Add security group %s to port %s" % (security_group, ext_id))

        return oid, params

    @staticmethod
    @task_step()
    def port_del_security_group_step(task, step_id, params, *args, **kvargs):
        """Detach security group from port

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
        # resource = container.get_simple_resource(oid)

        conn.network.port.remove_security_group(ext_id, security_group)
        task.progress(
            step_id,
            msg="Remove security group %s from port %s" % (security_group, ext_id),
        )

        return oid, params


task_manager.tasks.register(PortTask())
