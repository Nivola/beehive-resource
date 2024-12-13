# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class SubnetTask(AbstractResourceTask):
    """Subnet task"""

    name = "subnet_task"
    entity_class = OpenstackSubnet

    @staticmethod
    @task_step()
    def subnet_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")
        name = params.get("name")
        parent_ext_id = params.get("project_ext_id")
        network_ext_id = params.get("network_ext_id")
        gateway_ip = params.get("gateway_ip")
        cidr = params.get("cidr")
        allocation_pools = params.get("allocation_pools")
        enable_dhcp = params.get("enable_dhcp")
        host_routes = params.get("host_routes")
        dns_nameservers = params.get("dns_nameservers")
        service_types = params.get("service_types")

        container = task.get_container(cid)
        conn = container.conn
        inst = conn.network.subnet.create(
            name,
            network_ext_id,
            parent_ext_id,
            gateway_ip,
            cidr,
            allocation_pools,
            enable_dhcp,
            host_routes,
            dns_nameservers,
            service_types,
        )
        inst_id = inst["id"]
        task.progress(step_id, msg="Create subnet %s" % inst_id)

        # set resource id in shared data
        params["ext_id"] = inst_id
        params["result"] = inst_id

        return oid, params

    @staticmethod
    @task_step()
    def subnet_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        ext_id = params.get("ext_id")
        cid = params.get("cid")
        name = params.get("name")
        gateway_ip = params.get("gateway_ip")
        allocation_pools = params.get("allocation_pools")
        enable_dhcp = params.get("enable_dhcp")
        host_routes = params.get("host_routes")
        dns_nameservers = params.get("dns_nameservers")

        container = task.get_container(cid)
        conn = container.conn
        inst = conn.network.subnet.update(
            ext_id,
            name,
            None,
            None,
            gateway_ip,
            None,
            allocation_pools,
            enable_dhcp,
            host_routes,
            dns_nameservers,
        )
        inst_id = inst["id"]
        task.progress(step_id, msg="Update subnet %s" % inst_id)

        # set resource id in shared data
        params["result"] = inst_id

        return oid, params

    @staticmethod
    @task_step()
    def subnet_expunge_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        cid = params.get("cid")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        # delete vsphere folder
        if resource.is_ext_id_valid() is True:
            try:
                # check subnet exists
                conn.subnet.get(resource.ext_id)

                # delete subnet
                conn.network.subnet.delete(resource.ext_id)
                task.progress(step_id, msg="Delete subnet %s" % resource.ext_id)
            except:
                pass

        return oid, params


task_manager.tasks.register(SubnetTask())
