# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from time import sleep
from beedrones.vsphere.client import VsphereError
from beehive.common.task_v2 import task_step, TaskError
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge
from beehive_resource.task_v2 import AbstractResourceTask


class NsxEdgeTask(AbstractResourceTask):
    """NsxEdgeTask"""

    name = "nsx_edge_task"
    entity_class = NsxEdge

    def __init__(self, *args, **kwargs):
        super(NsxEdgeTask, self).__init__(*args, **kwargs)

    @staticmethod
    def __wait_from_edge_job(task, step_id, conn, nsx_jobid, edge, operation):
        # task.progress(step_id, msg='wait for edge job: %s' % nsx_jobid)
        res = conn.network.nsx.edge.get_job(nsx_jobid)
        status = res["status"]
        elapsed = 0
        while status not in ["COMPLETED", "FAILED", "ROLLBACK", "TIMEOUT"]:
            task.progress(step_id, msg="wait for edge job: %s" % nsx_jobid)
            sleep(5)
            res = conn.network.nsx.edge.get_job(nsx_jobid)
            status = res["status"]
            elapsed += 5
            if elapsed > 600:
                status = "TIMEOUT"
        task.progress(step_id, msg="%s edge %s %s" % (operation, edge, status))

    @staticmethod
    @task_step()
    def nsx_edge_create_step(task, step_id, params, *args, **kvargs):
        """Create nsx edge

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        datacenter = params.get("datacenter")
        cluster_id = params.get("cluster")
        datastore = params.get("datastore")
        uplink_dvpg = params.get("uplink_dvpg", None)
        uplink_subnet_pool = params.get("uplink_subnet_pool", None)
        uplink_ipaddress = params.get("uplink_ipaddress", None)
        uplink_gateway = params.get("uplink_gateway", None)
        uplink_prefix = params.get("uplink_prefix", None)
        pwd = params.get("pwd")
        dns = params.get("dns", "").split(" ")
        domain = params.get("domain", None)
        size = params.get("size")

        container = task.get_container(cid)
        conn = container.conn

        # get resource pool
        cluster = conn.cluster.get(cluster_id)
        respools = conn.cluster.resource_pool.list(cluster._moId)
        respool = respools[0].get("obj")._moId

        if uplink_subnet_pool is not None:
            ip_allocated = conn.network.nsx.ippool.allocations(uplink_subnet_pool)
            if uplink_ipaddress is not None and uplink_ipaddress in ip_allocated:
                raise TaskError("uplink ip %s is already allocated" % uplink_ipaddress)

            new_ip = conn.network.nsx.ippool.allocate(uplink_subnet_pool, static_ip=uplink_ipaddress)
            dns = [new_ip.get("dnsServer1"), new_ip.get("dnsServer2")]
            domain = new_ip.get("dnsSuffix")
            uplink_ipaddress = new_ip.get("ipAddress")
            uplink_prefix = new_ip.get("prefixLength")
            uplink_gateway = new_ip.get("gateway")

        # create nsx edge
        data = {
            "name": name,
            "datacenterMoid": datacenter,
            "tenant": "prova",
            "fqdn": name,
            "applianceSize": size,
            "appliances": [{"resourcePoolId": respool, "datastoreId": datastore}],
            "password": pwd,
            "primaryDns": dns[0],
            "domainName": domain,
        }
        if uplink_dvpg is not None:
            data["vnics"] = [
                {
                    "type": "Uplink",
                    "portgroupId": uplink_dvpg,
                    "addressGroups": [
                        {
                            "primaryAddress": uplink_ipaddress,
                            "subnetPrefixLength": uplink_prefix,
                        }
                    ],
                }
            ]
        if len(dns) > 1:
            data["secondaryDns"] = dns[1]
        res = conn.network.nsx.edge.add(data)
        job = conn.network.nsx.edge.get_job(res)
        edgeid = job["result"][0]["value"]
        NsxEdgeTask.__wait_from_edge_job(task, step_id, conn, res, edgeid, "create")

        # set gateway
        conn.network.nsx.edge.route_default_add(edgeid, uplink_gateway, mtu=1500, vnic=0)

        params["ext_id"] = edgeid
        params["attrib"] = {"gateway": uplink_gateway}

        return oid, params

    @staticmethod
    @task_step()
    def nsx_edge_delete_step(task, step_id, params, *args, **kvargs):
        """Delete nsx edge

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

        # delete vsphere edge
        if resource.is_ext_id_valid() is True:
            try:
                conn.network.nsx.edge.get(ext_id)
            except VsphereError:
                task.progress(step_id, msg="edge %s does not already exist" % ext_id)
                return oid, params

            # get primary address from uplink vnics
            primary_addresses = []
            vnics = resource.get_vnics()
            for vnic in vnics:
                if vnic.get("type") == "uplink":
                    address_groups = vnic.get("addressGroups")

                    if isinstance(address_groups, dict) is True:
                        address_groups = [address_groups]
                    if len(address_groups) > 0:
                        primary_address = address_groups[0].get("addressGroup", {}).get("primaryAddress", None)
                        primary_addresses.append(primary_address)

            # delete edge
            res = conn.network.nsx.edge.delete(ext_id)
            conn.network.nsx.edge.get_job(res)
            NsxEdgeTask.__wait_from_edge_job(task, step_id, conn, res, ext_id, "delete")

            # deallocate ip address from pool
            for primary_address in primary_addresses:
                pools = conn.network.nsx.ippool.list(pool_range=[primary_address, primary_address])
                pool_id = pools[0]["objectId"]
                conn.network.nsx.ippool.release(pool_id, primary_address)
                task.progress(
                    step_id,
                    msg="release ip %s from subnet pool %s" % (primary_address, pool_id),
                )

        return oid, params
