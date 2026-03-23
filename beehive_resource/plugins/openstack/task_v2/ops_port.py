# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from logging import getLogger
from beedrones.openstack.client import OpenstackError, OpenstackManager
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import get_task_manager
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class PortTask(AbstractResourceTask):
    """Port task"""

    name = "port_task"
    entity_class = OpenstackPort

    @staticmethod
    @task_step()
    def port_create_physical_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
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
    def port_delete_physical_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container = task.get_container(cid)
        conn: OpenstackManager = container.conn
        resource = container.get_simple_resource(oid)

        port_uuid = resource.ext_id
        if resource.is_ext_id_valid() is True:
            port_exists = False
            try:
                # check port exists
                task.progress(step_id, msg="Check port exists %s" % port_uuid)
                conn.network.port.get(port_uuid)
                port_exists = True
            except OpenstackError as ose:
                task.logger.error(ose, exc_info=True)
                if ose.code == 404:
                    task.progress(step_id, msg="Port doesn't exist %s" % port_uuid)
                    port_exists = False
                else:
                    raise ApiManagerError(ose, code=ose.code)
            except Exception as ex:
                task.progress(step_id, msg="Error checking port %s - %s" % (port_uuid, ex))
                task.logger.error(ex, exc_info=True)
                raise ApiManagerError(ex, code=getattr(ex, "code", 500))

            try:
                if port_exists:
                    # delete openport port
                    conn.network.port.delete(port_uuid)
                    task.progress(step_id, msg="Delete port %s" % port_uuid)
            except Exception as ex:
                task.progress(step_id, msg="Error deleting port %s - %s" % (port_uuid, ex))
                task.logger.error(ex, exc_info=True)
                raise ApiManagerError(ex, code=getattr(ex, "code", 500))
        else:
            task.progress(step_id, msg="Port uuid not valid %s" % (port_uuid))

        return oid, params

    @staticmethod
    @task_step()
    def port_add_security_group_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
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
    def port_del_security_group_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
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


get_task_manager().register_task(PortTask())
