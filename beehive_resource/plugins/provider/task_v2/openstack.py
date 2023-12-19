# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import copy
from logging import getLogger
import ujson as json

from beecell.db import ModelError
from beecell.simple import import_class, id_gen, dict_set, str2bool
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import TaskError
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.openstack.entity.ops_volume_type import (
    OpenstackVolumeType,
)
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.entity.ops_security_group import (
    OpenstackSecurityGroup,
    OpenstackSecurityGroupRule,
)
from beehive_resource.container import CustomResource
from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.plugins.provider.entity.vpc_v2 import SiteNetwork, PrivateNetwork
from beehive_resource.plugins.provider.task_v2 import AbstractProviderHelper

logger = getLogger(__name__)


class ProviderOpenstack(AbstractProviderHelper):
    QUOTAS = {
        "compute.instances": {"type": "compute", "quota": "instances", "factor": 1},
        # 'compute.images': {'type': 'compute', 'quota': 'instances', 'factor': 1},
        "compute.volumes": {"type": "block", "quota": "volumes", "factor": 1},
        "compute.snapshots": {"type": "block", "quota": "snapshots", "factor": 1},
        "compute.blocks": {"type": "block", "quota": "gigabytes", "factor": 1024},
        "compute.ram": {"type": "compute", "quota": "ram", "factor": 1024},
        "compute.cores": {"type": "compute", "quota": "cores", "factor": 1},
        "compute.networks": {"type": "network", "quota": "network", "factor": 1},
        "compute.floatingips": {"type": "network", "quota": "floatingip", "factor": 1},
        "compute.security_groups": {
            "type": "network",
            "quota": "security_group",
            "factor": 1,
        },
        "compute.security_group_rules": {
            "type": "network",
            "quota": "security_group_rule",
            "factor": 1,
        },
        "compute.keypairs": {"type": "compute", "quota": "key_pairs", "factor": 1},
        "database.instances": {"type": "compute", "quota": "instances", "factor": 2},
        "database.ram": {"type": "compute", "quota": "ram", "factor": 1024},
        "database.cores": {"type": "compute", "quota": "cores", "factor": 1},
        "database.volumes": {"type": "block", "quota": "volumes", "factor": 1},
        "database.snapshots": {"type": "block", "quota": "snapshots", "factor": 1},
        "database.blocks": {"type": "block", "quota": "gigabytes", "factor": 1024},
        # 'share.instances': {'default': 10, 'unit': '#'},
        "share.blocks": {"type": "share", "quota": "gigabytes", "factor": 1024},
        "appengine.instances": {"type": "compute", "quota": "instances", "factor": 5},
        "appengine.ram": {"type": "compute", "quota": "ram", "factor": 1024},
        "appengine.cores": {"type": "compute", "quota": "cores", "factor": 1},
        "appengine.volumes": {"type": "block", "quota": "volumes", "factor": 1},
        "appengine.snapshots": {"type": "block", "quota": "snapshots", "factor": 1},
        "appengine.blocks": {"type": "block", "quota": "gigabytes", "factor": 1024},
    }

    def create_zone_childs(self, site, quotas=None):
        """Create availability zone childs

        :param site: site where is orchestrator
        :param quotas: list of quotas to set
        :return: resource id
        :rtype: int
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        domain = self.orchestrator["config"]["domain"]
        parent_project = site.get_physical_resource_from_container(self.cid, OpenstackProject.objdef)
        project_id = self.create_project(domain, parent_project)
        self.get_session(reopen=True)
        self.set_quotas(quotas)
        return project_id

    def set_quotas(self, quotas):
        """Set openstack project quotas.

        :param quotas: list of quotas to set
        :return: list
        :rtype: resource list
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        project = self.resource.get_physical_resource_from_container(self.cid, OpenstackProject.objdef)
        ops_quotas = {}
        for k, v in quotas.items():
            base_quota = copy.deepcopy(ProviderOpenstack.QUOTAS)
            data = base_quota.get(k, None)

            if data is not None:
                data["value"] = int(v) * data.pop("factor", 1)

                key = "%s.%s" % (data["type"], data["quota"])
                if key in ops_quotas:
                    ops_quotas[key]["value"] += data["value"]
                else:
                    ops_quotas[key] = data

        project.set_quotas(list(ops_quotas.values()))
        self.progress("Set project %s quotas: %s" % (project.uuid, ops_quotas))
        return True

    def create_project(self, domain, parent_project):
        """Create openstack project.

        :parma domain: domain id
        :param parent_project: parent project
        :return: resource oid
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        # create project
        name = "%s-%s-project" % (self.resource.name, self.cid)
        project_id = None
        if parent_project is not None:
            project_id = parent_project.oid

        prepared_task = self.create_resource(
            OpenstackProject,
            name=name,
            desc=self.resource.desc,
            active=False,
            attribute={},
            parent=None,
            tags="",
            is_domain=False,
            enabled=True,
            domain_id=domain,
            project_id=project_id,
        )
        project = self.add_link(prepared_task)
        self.run_sync_task(prepared_task, msg="stop project creation")

        # reset default security group
        self.get_session(reopen=True)
        project = self.get_resource(project.oid)
        security_groups, tot = project.get_security_groups()
        prepared_task, code = security_groups[0].reset_rule(sync=True)
        self.run_sync_task(prepared_task, msg="reset project %s default security group" % project.oid)

        return project.oid

    def create_security_group(self, parent):
        """Create openstack security group.

        :param parent: parent
        :return: resource oid
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        name = "%s-%s-sg" % (self.resource.name, self.cid)
        parent_project = parent.get_physical_resource_from_container(self.cid, orchestrator_mapping("openstack", 0))

        prepared_task = self.create_resource(
            OpenstackSecurityGroup,
            name=name,
            desc=self.resource.desc,
            active=False,
            attribute={},
            parent=parent_project.oid,
            tags="",
        )
        sg = self.add_link(prepared_task)
        self.run_sync_task(prepared_task, msg="stop security group %s creation" % sg.oid)

        # reset security group
        self.get_session(reopen=True)
        sg = self.get_resource(prepared_task["uuid"])
        prepared_task, code = sg.reset_rule(sync=True)
        self.run_sync_task(prepared_task, msg="reset security group %s" % sg.oid)

        return sg.oid

    def create_network(
        self,
        network_type,
        vlan,
        external,
        private,
        physical_network=None,
        public_network=None,
    ):
        """Create openstack network.

        :param network_type: network type like flat, vlan, vxlan
        :param vlan: network vlan. Use with flat and vlan type
        :param external: True if network is used as external
        :param private: True if network is private
        :param physical_network: [optional] id of the openVswitch trunk
        :param public_network: [optional] id of the openVswitch public
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        name = "%s-%s-network" % (self.resource.name, self.cid)

        parent = self.get_resource(self.resource.parent_id)
        project = parent.get_physical_resource_from_container(self.cid, OpenstackProject.objdef)

        if vlan is not None:
            # Use the network if it already exists.
            self.progress("Verify vlan %s is already assigned" % vlan)
            networks, tot = self.container.get_resources(
                objdef=OpenstackNetwork.objdef,
                type=OpenstackNetwork.objdef,
                segmentation_id=vlan,
            )
            if tot > 0:
                network_id = networks[0].oid
                # name = networks[0].name
                self.progress("Network %s already exists" % network_id)
                self.progress("Get network: %s" % network_id)

                # create link
                self.add_link(resource_to_link=networks[0], attrib={"reuse": True})
                return network_id

        # create new openstack network
        shared = False
        if external is False and private is False:
            shared = True
        if network_type == "flat":
            physical_network = public_network

        config = {
            "name": name,
            "desc": name,
            "physical_network": physical_network,
            "network_type": network_type,
            "segmentation_id": vlan,
            "shared": shared,
            "parent": project.oid,
            "external": external,
            # 'qos_rule_id':.., TODO
            # 'segments':.., TODO
        }
        prepared_task = self.create_resource(OpenstackNetwork, **config)
        network = self.add_link(prepared_task, attrib={"reuse": False})
        self.run_sync_task(prepared_task, msg="stop network creation")

        return network.oid

    # def append_network(self, network_type, net_id):
    #     """Append openstack network.
    #
    #     :param network_type: network type like flat, vlan, vxlan
    #     :param net_id: dvpg id
    #     :return: resource id
    #     :rtype: int
    #     :raise TaskError: If task fails
    #     :raise ApiManagerError: :class:`ApiManagerError`
    #     """
    #     # create normal dvp
    #     if network_type in ['flat', 'vlan']:
    #         # get openstack network
    #         network = self.get_resource(net_id)
    #         network_id = network['id']
    #
    #     # create logical switch
    #     elif network_type == 'vxlan':
    #         pass
    #         # TODO:
    #     else:
    #         raise TaskError('Network type %s is not supported' % network_type)
    #
    #     # self.progress('Create network %s' % network_id)
    #
    #     # create link
    #     self.get_session(reopen=True)
    #     attrib = {'reuse': True}
    #     resource.add_link('%s.%s-link' % (resource.oid, network_id), 'relation', network_id, attributes=attrib)
    #     self.progress('Link openstack network %s' % network_id)

    def create_subnet(
        self,
        cidr,
        gateway,
        routes,
        allocation_pools,
        enable_dhcp,
        dns_nameservers,
        overlap=False,
    ):
        """Create openstack subnet if it does not already exist.

        :param resource: parent network
        :param gateway: gateway ip
        :param cidr: subnet cidr
        :param routes: subnet routes [defautl=None]
        :param allocation_pools: pools of continous ip in the subnet.
            Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
        :param enable_dhcp: if True enable dhcp
        :param dns_nameservers: list of dns. default=['8.8.8.8', '8.8.8.4']
        :return: subnet uuid
        :param overlap: if True permit subnet overlapping
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        parent = self.get_resource(self.resource.parent_id)
        project = parent.get_physical_resource_from_container(self.cid, OpenstackProject.objdef)
        network = self.resource.get_physical_resource_from_container(self.cid, OpenstackNetwork.objdef)
        subnet_name = "%s-%s-%s-subnet" % (self.resource.name, self.cid, id_gen())

        # get network subnets
        net_subnets, tot = self.container.get_resources(
            objdef=OpenstackSubnet.objdef,
            type=OpenstackSubnet.objdef,
            parent=network.oid,
            cidr=cidr,
        )

        # subnet already exists
        if tot > 0:
            return net_subnets[0].uuid

        # create openstack subnet - don't set gateway. Leave openstack to autoassign one from allocation
        config = {
            "name": subnet_name,
            "desc": "Subnet %s" % subnet_name,
            "project": project.oid,
            "parent": network.oid,
            "gateway_ip": gateway,
            "cidr": cidr,
            "allocation_pools": allocation_pools,
            "enable_dhcp": enable_dhcp,
            "dns_nameservers": dns_nameservers,
        }
        if routes is not None:
            config["host_routes"] = routes

        if enable_dhcp is False:
            config["service_types"] = "compute:twin"

        prepared_task = self.create_resource(OpenstackSubnet, **config)
        # subnet = self.add_link(prepared_task)
        self.run_sync_task(prepared_task, msg="stop subnet creation")

        return prepared_task.get("uuid")

    def delete_subnet(self, subnet_id):
        """Delete openstack subnet.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent network
        :param subnet_id: id of the subnet
        :return: subnet id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        if subnet_id is None:
            self.progress("subnet is not present in openstack")
            return None

        subnet = self.container.get_resource(subnet_id)
        prepared_task, code = subnet.expunge(sync=True)
        self.run_sync_task(prepared_task, msg="delete openstack network subnet: %s" % subnet_id)

        return subnet_id

    def create_gateway(self, role, uplink_ip_address, transport_ip_address, params):
        """Create openstack router.

        :return: list
        :rtype: resource list
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        name = "%s-%s-router" % (self.resource.name, self.cid)
        zone = self.resource.get_parent()
        project = zone.get_physical_resource_from_container(self.cid, OpenstackProject.objdef)
        transport_network = params.get("transport_network")
        transport_subnet = params.get("transport_main_subnet")

        config = {
            "name": name,
            "desc": name,
            "parent": project.oid,
        }
        prepared_task = self.create_resource(OpenstackRouter, **config)
        router = self.add_link(prepared_task)
        router_id = router.oid
        self.run_sync_task(prepared_task, msg="stop router creation")
        self.progress("create openstack router: %s" % router_id)

        # append transport network
        # - get transport network
        transport_network = self.get_simple_resource(transport_network)
        transport_network = transport_network.get_physical_resource_from_container(self.cid, OpenstackNetwork.objdef)

        # - get network subnets
        net_subnets, tot = self.container.get_resources(
            objdef=OpenstackSubnet.objdef,
            type=OpenstackSubnet.objdef,
            parent=transport_network.oid,
            cidr=transport_subnet,
        )
        if tot > 0:
            transport_subnet = net_subnets[0].oid
        else:
            self.progress("ERROR - create openstack router: %s" % router_id)
            raise TaskError(
                "no transport network with cidr %s exists in transport network %s"
                % (transport_subnet, transport_network.oid)
            )

        port_params = {
            "ip_address": transport_ip_address,
            "network_id": transport_network.oid,
            "subnet_id": transport_subnet,
        }
        # dati test - create_gateway - port_params: {'ip_address': '192.168.97.187', 'network_id': 28520, 'subnet_id': 170673}
        self.logger.debug("create_gateway - port_params: %s" % port_params)

        openstackRouter: OpenstackRouter = self.get_resource(router_id)
        prepared_task, code = openstackRouter.create_port(port_params, sync=True)
        self.run_sync_task(prepared_task, msg="stop router transport port creation")
        self.progress("add transport network with ip: %s" % transport_ip_address)

        return router_id

    def create_rule(self, zone, source, destination, service):
        """Create openstack rule.

        :param zone: availability zone
        :param source: source
        :param destination: destination
        :param service: service.
            Ex. {'port':'*', 'protocol':'*'} -> *:*
                {'port':'*', 'protocol':6} -> tcp:*
                {'port':80, 'protocol':6} -> tcp:80
                {'port':80, 'protocol':17} -> udp:80
                {'protocol':1, 'subprotocol':8} -> icmp:echo request
        :return: list
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            policies = []

            # get protocol
            protocol = service.get("protocol", None)
            port = service.get("port", None)

            # parse service
            if protocol == "*" and port == "*":
                proto = None
                port_range_min = None
                port_range_max = None
            else:
                if protocol == "1":
                    # for a complete list of icmp type http://www.nthelp.com/icmp.html
                    proto = "icmp"
                    self.logger.warn(service)
                    if service["subprotocol"] == "-1":
                        port_range_min = port_range_max = None
                    else:
                        port_range_min = port_range_max = service["subprotocol"]  # contains icmp type
                elif protocol == "6":
                    proto = "tcp"
                    if port == "*":
                        port_range_min = port_range_max = None
                    else:
                        if port.find("-") > 0:
                            port_range_min, port_range_max = port.split("-")
                        else:
                            port_range_min = port_range_max = port
                elif protocol == "17":
                    proto = "udp"
                    if port == "*":
                        port_range_min = port_range_max = None
                    else:
                        if port.find("-") > 0:
                            port_range_min, port_range_max = port.split("-")
                        else:
                            port_range_min = port_range_max = port
                else:
                    raise Exception("Procotol %s is not supported" % protocol)

            # sgrule1 -> sgrule1
            if source["type"] == destination["type"] and source["value"] == destination["value"]:
                # get source security group id
                res = self.get_resource(source["value"])
                sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    self.create_openstack_rule(
                        sg_id,
                        "egress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=sg_id,
                        cidr=None,
                    )
                )
                policies.append(
                    self.create_openstack_rule(
                        sg_id,
                        "ingress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=sg_id,
                        cidr=None,
                    )
                )

            # cidr -> sgrule
            elif source["type"] == "Cidr" and destination["type"] in ["RuleGroup"]:
                # get destination security group id
                res = self.get_resource(destination["value"])
                sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid
                # get source cidr
                cidr = source["value"]
                policies.append(
                    self.create_openstack_rule(
                        sg_id,
                        "ingress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=None,
                        cidr=cidr,
                    )
                )

            # sgrule -> cidr
            elif destination["type"] == "Cidr" and source["type"] in ["RuleGroup"]:
                # get source security group id
                res = self.get_resource(source["value"])
                sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid
                # get destination cidr
                cidr = destination["value"]
                policies.append(
                    self.create_openstack_rule(
                        sg_id,
                        "egress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=None,
                        cidr=cidr,
                    )
                )

            # sgrule1 -> sgrule2
            elif source["type"] in ["RuleGroup"] and destination["type"] in ["RuleGroup"]:
                # get source security group id
                res = self.get_resource(source["value"])
                source_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid
                # get destination security group id
                res = self.get_resource(destination["value"])
                dest_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    self.create_openstack_rule(
                        source_sg_id,
                        "egress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=dest_sg_id,
                        cidr=None,
                    )
                )
                policies.append(
                    self.create_openstack_rule(
                        dest_sg_id,
                        "ingress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=source_sg_id,
                        cidr=None,
                    )
                )

            # sgrule -> server
            elif source["type"] in ["RuleGroup"] and destination["type"] in ["Server"]:
                # get source security group id
                res = self.get_resource(source["value"])
                source_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                # get destination server id
                server_id = destination["value"]
                # get destination security group id where is the server
                server = self.get_resource(server_id)
                res = self.get_resource(server.parent_id)
                dest_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    self.create_openstack_rule(
                        source_sg_id,
                        "egress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=None,
                        cidr=server_id,
                    )
                )
                policies.append(
                    self.create_openstack_rule(
                        dest_sg_id,
                        "ingress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=source_sg_id,
                        cidr=None,
                    )
                )

            # server -> sgrule
            elif destination["type"] in ["Environment"] and source["type"] in ["Server"]:
                # get source server id
                server_id = source["value"]
                # get source security group id where is the server
                server = self.get_resource(server_id)
                res = self.get_resource(server.parent_id)
                source_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                # get destination security group id
                res = self.get_resource(destination["value"])
                dest_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    self.create_openstack_rule(
                        source_sg_id,
                        "egress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=dest_sg_id,
                        cidr=None,
                    )
                )
                policies.append(
                    self.create_openstack_rule(
                        dest_sg_id,
                        "ingress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=None,
                        cidr=server_id,
                    )
                )

            # server -> server
            elif source["type"] in ["Server"] and destination["type"] in ["Server"]:
                # get source server id
                source_server_id = source["value"]
                # get source security group id where is the server
                server = self.get_resource(source_server_id)
                res = self.get_resource(server.parent_id)
                source_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                # get destination server id
                dest_server_id = destination["value"]
                # get destination security group id where is the server
                server = self.get_resource(dest_server_id)
                res = self.get_resource(dest_server_id.parent_id)
                dest_sg_id = res.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    self.create_openstack_rule(
                        source_sg_id,
                        "egress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=None,
                        cidr=dest_server_id,
                    )
                )
                policies.append(
                    self.create_openstack_rule(
                        dest_sg_id,
                        "ingress",
                        port_range_min,
                        port_range_max,
                        proto,
                        group=None,
                        cidr=source_server_id,
                    )
                )

            return policies
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_openstack_rule(
        self,
        sg_id,
        direction,
        port_range_min,
        port_range_max,
        protocol,
        group=None,
        cidr=None,
    ):
        """Create openstack security group rule

        :param direction: ingress or egress
        :param port_range_min: min port range
        :param port_range_max: max port range
        :param protocol: protocol tcp, udp, icmp or None
        :param group: security group id [default=None]
        :param cidr: cidr [default=None]
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        rule = {"direction": direction, "ethertype": "IPV4", "protocol": protocol}
        if port_range_min is not None:
            rule["port_range_min"] = port_range_min
        if port_range_max is not None:
            rule["port_range_max"] = port_range_max
        if group is not None:
            rule["remote_group_id"] = str(group)
        if cidr is not None:
            rule["remote_ip_prefix"] = cidr

        self.progress("Configure openstack rule: %s" % rule)

        # get security group
        sg = self.get_resource(sg_id)

        # create rule
        prepared_task, code = sg.create_rule(rule, sync=True)
        rule_id = self.run_sync_task(prepared_task, msg="stop rule creation")
        self.progress("Create openstack rule %s.%s" % (sg_id, rule_id))

        # create custom resource
        objid = "%s//%s" % (self.container.objid, id_gen())
        name = "openstack_rule_%s" % rule_id
        desc = name
        attribs = {
            "security_group": sg_id,
            "id": rule_id,
            "type": "openstack",
            "sub_type": OpenstackSecurityGroupRule.objdef,
        }
        resource_model = self.container.add_resource(
            objid=objid,
            name=name,
            resource_class=CustomResource,
            ext_id=None,
            active=True,
            desc=desc,
            attrib=attribs,
            parent=None,
            tags=["openstack"],
        )
        rule_resource_id = resource_model.id
        self.container.update_resource_state(rule_resource_id, 2)
        self.container.activate_resource(rule_resource_id)
        self.add_link({"uuid": rule_resource_id})
        self.progress("create rule resource: %s" % rule_resource_id)

        return rule_id

    def import_server(self, params):
        """Import openstack server.

        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            networks = params.get("networks")

            # get server
            server = self.get_resource(params.get("physical_server_id"))

            # set up resource link
            self.add_link(resource_to_link=server)

            # get server networks
            server_nets = server.detail()["details"]["networks"]
            server_net_idx = {str(n["net_id"]): n["fixed_ips"][0]["ip_address"] for n in server_nets}

            # assign ip to network conf
            for network_conf in networks:
                physical_net_id = network_conf.get("physical_net_id")
                fixed_ip = network_conf.get("fixed_ip", None)
                if fixed_ip is not None:
                    network_conf["fixed_ip"] = {"ip": server_net_idx[str(physical_net_id)]}

            params["networks"] = networks
            return server.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    # def clone_server(self, project, params):
    #     """Create openstack server.
    #
    #     :param project: parent openstack project
    #     :param params: configuration params
    #     :return: resource id
    #     :raise TaskError: :class:`TaskError`
    #     :raise ApiManagerError: :class:`ApiManagerError`
    #     """
    #     from beedrones.openstack.server import OpenstackServer as OS
    #
    #     try:
    #         flavor_id = params.get('flavor')
    #         environments = params.get('security_groups')
    #         admin_pass = params.get('admin_pass')
    #         networks = params.get('networks')
    #         clone_server = params.get('clone_server')
    #         clone_server_volume_type = params.get('clone_server_volume_type')
    #         metadata = params.get('metadata')
    #         user_data = params.get('user_data')
    #         personality = params.get('personality')
    #         if metadata is None:
    #             metadata = {}
    #         if personality is None:
    #             personality = []
    #
    #         name = '%s-%s-server' % (self.resource.name, self.cid)
    #         orchestrator_type = 'openstack'
    #         availability_zone = self.orchestrator['config']['availability_zone']
    #
    #         server_conf = {
    #             'parent': project.oid,
    #             'name': name,
    #             'desc': self.resource.desc,
    #             'flavorRef': None,
    #             'availability_zone': availability_zone,
    #             'adminPass': admin_pass,
    #             'networks': [],
    #             'security_groups': [],
    #             'user_data': user_data,
    #             'metadata': metadata,
    #             'personality': personality,
    #             'clone_server': clone_server.oid,
    #             'clone_server_volume_type': clone_server_volume_type.oid,
    #             'config_drive': True
    #         }
    #
    #         # set flavor
    #         flavor = self.get_simple_resource(flavor_id)
    #         remote_flavor = flavor.get_physical_resource_from_container(self.cid, OpenstackFlavor.objdef)
    #         server_conf['flavorRef'] = remote_flavor.uuid
    #
    #         # get security_groups from environments
    #         for environment_id in environments:
    #             env = self.get_simple_resource(environment_id)
    #             objdef = orchestrator_mapping(orchestrator_type, 1)
    #             sg = env.get_physical_resource_from_container(self.cid, objdef)
    #             server_conf['security_groups'].append(sg.uuid)
    #
    #         # set networks
    #         net = 0
    #         for network_conf in networks:
    #             uuid = network_conf.get('id')
    #             subnet = network_conf.get('subnet')
    #             subnet_cidr = network_conf.get('subnet').get('cidr')
    #             fixed_ip = network_conf.get('fixed_ip', {})
    #             network = self.get_resource(uuid)
    #             remote_net = self.__get_physical_network(network)
    #
    #             noproxy = False
    #             if isinstance(network, PrivateNetwork):
    #                 noproxy = True
    #
    #             # get network subnets
    #             net_subnets, tot = self.container.get_resources(objdef=OpenstackSubnet.objdef,
    #                                                             type=OpenstackSubnet.objdef,
    #                                                             parent=remote_net.oid, cidr=subnet_cidr)
    #             if tot > 0:
    #                 remote_subnet = net_subnets[0].uuid
    #             else:
    #                 raise Exception('No valid subnet found for network %s and cidr %s' % (remote_net.oid, subnet_cidr))
    #
    #             # set network config
    #             config = {
    #                 'uuid': remote_net.uuid,
    #                 'subnet_uuid': remote_subnet
    #             }
    #             server_conf['networks'].append(config)
    #
    #             # set user data - exec only for net card 0
    #             if net == 0:
    #                 try:
    #                     sshkey = metadata.get('pubkey')
    #                 except:
    #                     sshkey = None
    #                 users = None  # TODO gestione user e sshkey
    #                 routes = []
    #
    #                 user_data = OS.user_data(gateway=subnet['gateway'], users=users, pwd=admin_pass, sshkey=sshkey,
    #                                          domain=fixed_ip.get('dns_search', 'nivolalocal'), noproxy=noproxy,
    #                                          hostname=fixed_ip.get('hostname'), routes=routes)
    #                 server_conf['user_data'] = user_data
    #             net += 1
    #
    #         # # configure boot volume
    #         # volume = self.get_simple_resource(zone_boot_volume)
    #         # remote_volume = volume.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
    #         # conf = {
    #         #     'boot_index': 0,
    #         #     'source_type': 'volume',
    #         #     'uuid': remote_volume.uuid,
    #         #     'destination_type': 'volume',
    #         # }
    #         # server_conf['block_device_mapping_v2'].append(conf)
    #
    #         # create remote server
    #         prepared_task = self.create_resource(OpenstackServer, **server_conf)
    #         server = self.add_link(prepared_task)
    #         self.run_sync_task(prepared_task, msg='stop project creation')
    #
    #         # get final server
    #         self.get_session(reopen=True)
    #         server = self.get_resource(server.uuid)
    #
    #         # get server networks
    #         server_nets = server.detail()['details']['networks']
    #         server_net_idx = {str(n['net_id']): n['fixed_ips'][0]['ip_address'] for n in server_nets}
    #
    #         # assign dhcp ip to network conf
    #         for network_conf in networks:
    #             uuid = network_conf.get('id')
    #             fixed_ip = network_conf.get('fixed_ip', None)
    #             if fixed_ip is not None:
    #                 # get remote network
    #                 network = self.get_resource(uuid)
    #                 remote_net = self.__get_physical_network(network)
    #
    #                 network_conf['fixed_ip'] = {'ip': server_net_idx[str(remote_net.uuid)]}
    #
    #         params['networks'] = networks
    #         self.progress('Update shared data with network: %s' % params['networks'])
    #
    #         # # attach other volumes to server
    #         # for zone_other_volume in zone_other_volumes:
    #         #     volume = self.get_simple_resource(zone_other_volume)
    #         #     remote_volume = volume.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
    #         #     prepared_task, code = server.add_volume(volume=remote_volume.uuid, sync=True)
    #         #     self.run_sync_task(prepared_task, msg='attach volume %s to server' % zone_other_volume)
    #         #     self.progress('Attach volume %s to server' % zone_other_volume)
    #
    #         return server.oid
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise TaskError(ex)

    def __get_physical_network(self, network):
        """get physical network

        :param network: network
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        orchestrator_type = "openstack"
        if isinstance(network, SiteNetwork):
            objdef = orchestrator_mapping(orchestrator_type, 2)
        elif isinstance(network, PrivateNetwork):
            objdef = orchestrator_mapping(orchestrator_type, 3)
        remote_net = network.get_physical_resource_from_container(self.cid, objdef)
        return remote_net

    def create_server(self, project, params):
        """Create openstack server.

        :param project: parent openstack project
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        from beedrones.openstack.server import OpenstackServer as OS

        try:
            flavor_id = params.get("flavor")
            environments = params.get("security_groups")
            admin_pass = params.get("admin_pass")
            networks = params.get("networks")
            zone_boot_volume = params.get("zone_boot_volume")
            zone_other_volumes = params.get("zone_other_volumes")
            metadata = params.get("metadata")
            user_data = params.get("user_data")
            personality = params.get("personality")
            if metadata is None:
                metadata = {}
            if personality is None:
                personality = []

            name = "%s-%s-server" % (self.resource.name, self.cid)
            orchestrator_type = "openstack"
            availability_zone = self.orchestrator["config"]["availability_zone"]

            server_conf = {
                "parent": project.oid,
                "name": name,
                "desc": self.resource.desc,
                "flavorRef": None,
                "availability_zone": availability_zone,
                "adminPass": admin_pass,
                "networks": [],
                "security_groups": [],
                "user_data": user_data,
                "metadata": metadata,
                "personality": personality,
                "block_device_mapping_v2": [],
                "config_drive": True,
            }

            # set flavor
            flavor = self.get_simple_resource(flavor_id)
            remote_flavor = flavor.get_physical_resource_from_container(self.cid, OpenstackFlavor.objdef)
            server_conf["flavorRef"] = remote_flavor.uuid

            # get security_groups from environments
            for environment_id in environments:
                env = self.get_simple_resource(environment_id)
                objdef = orchestrator_mapping(orchestrator_type, 1)
                sg = env.get_physical_resource_from_container(self.cid, objdef)
                server_conf["security_groups"].append(sg.uuid)

            # set networks
            net = 0
            for network_conf in networks:
                uuid = network_conf.get("id")
                subnet = network_conf.get("subnet")
                subnet_cidr = network_conf.get("subnet").get("cidr")
                fixed_ip = network_conf.get("fixed_ip", {})
                network = self.get_resource(uuid)
                remote_net = self.__get_physical_network(network)

                noproxy = False
                if isinstance(network, PrivateNetwork):
                    noproxy = True

                # get network subnets
                net_subnets, tot = self.container.get_resources(
                    objdef=OpenstackSubnet.objdef,
                    type=OpenstackSubnet.objdef,
                    parent=remote_net.oid,
                    cidr=subnet_cidr,
                )
                if tot > 0:
                    remote_subnet = net_subnets[0].uuid
                else:
                    raise Exception("No valid subnet found for network %s and cidr %s" % (remote_net.oid, subnet_cidr))

                # set network config
                config = {"uuid": remote_net.uuid, "subnet_uuid": remote_subnet}
                if fixed_ip is not None and fixed_ip != {}:
                    config["fixed_ip"] = fixed_ip
                server_conf["networks"].append(config)

                # set user data - exec only for net card 0
                if net == 0:
                    try:
                        sshkey = metadata.get("pubkey")
                    except:
                        sshkey = None
                    users = None  # TODO gestione user e sshkey
                    routes = []

                    user_data = OS.user_data(
                        gateway=subnet["gateway"],
                        users=users,
                        pwd=admin_pass,
                        sshkey=sshkey,
                        domain=fixed_ip.get("dns_search", "nivolalocal"),
                        noproxy=noproxy,
                        hostname=fixed_ip.get("hostname"),
                        routes=routes,
                    )
                    server_conf["user_data"] = user_data
                net += 1

            # configure boot volume
            volume = self.get_simple_resource(zone_boot_volume)
            remote_volume = volume.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
            conf = {
                "boot_index": 0,
                "source_type": "volume",
                "uuid": remote_volume.uuid,
                "destination_type": "volume",
            }
            server_conf["block_device_mapping_v2"].append(conf)

            # create remote server
            prepared_task = self.create_resource(OpenstackServer, **server_conf)
            server = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop project creation")

            # get final server
            self.get_session(reopen=True)
            server = self.get_resource(server.uuid)

            # get server networks
            server_nets = server.detail()["details"]["networks"]
            server_net_idx = {str(n["net_id"]): n["fixed_ips"][0]["ip_address"] for n in server_nets}

            # assign dhcp ip to network conf
            for network_conf in networks:
                uuid = network_conf.get("id")
                fixed_ip = network_conf.get("fixed_ip", None)
                if fixed_ip is not None:
                    # get remote network
                    network = self.get_resource(uuid)
                    remote_net = self.__get_physical_network(network)

                    network_conf["fixed_ip"] = {"ip": server_net_idx[str(remote_net.uuid)]}

            params["networks"] = networks
            self.progress("Update shared data with network: %s" % params["networks"])

            # attach other volumes to server
            for zone_other_volume in zone_other_volumes:
                volume = self.get_simple_resource(zone_other_volume)
                remote_volume = volume.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
                prepared_task, code = server.add_volume(volume=remote_volume.uuid, sync=True)
                self.run_sync_task(prepared_task, msg="attach volume %s to server" % zone_other_volume)
                self.progress("Attach volume %s to server" % zone_other_volume)

            return server.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_share(self, project, params, compute_share):
        """Create openstack share.

        :param project: parent openstack project
        :param params: configuration params
        :param compute_share: compute_share resource
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-share" % (self.resource.name, self.cid)
            availability_zone = self.orchestrator["config"]["availability_zone"]

            # get share proto
            share_proto = params.get("share_proto").lower()
            network_config = params.get("network")
            vlan = network_config.get("vlan")
            label = network_config.get("label", None)
            proto = share_proto
            if share_proto == "cifs":
                proto = "smb"

            # get share network and subnet
            subnet_cidr = network_config.get("subnet", None)

            # if subnet is defined use to create share network
            # TODO STAAS PRIVATE Nuovo  deve ricondursi al  caso enti
            if subnet_cidr is not None:
                share_type = "local"

                # get network from vpc
                vpc = self.get_simple_resource(network_config["vpc"])
                if vpc.is_private() is True:
                    network = vpc.get_private_network_by_cidr(subnet_cidr)
                elif vpc.is_shared() is True:
                    network = vpc.get_site_network_by_cidr(subnet_cidr)

                # get openstack network
                ops_network = network.get_openstack_network()
                # get openstack subnet
                ops_subnet = network.get_allocable_subnet(subnet_cidr, orchestrator_type="openstack")

                ops_network_id = ops_network.oid
                ops_subnet_id = ops_subnet.get("openstack_id")

            else:
                # get share type name
                # share_type = None
                ops_network_id = None
                ops_subnet_id = None

                # create share type name filter
                # vlan=1120,protocol=nfs
                # stype_search_name = '%s-%s' % (proto, vlan)
                stype_search_name = "vlan=%s,protocol=%s" % (vlan, proto)
                if label is not None:
                    # vlan=1189,protocol=nfs,label=ComuneVercelli.ComuneVercelli.apk
                    # stype_search_name = '%s-%s-%s' % (proto, vlan, label)
                    stype_search_name = "vlan=%s,protocol=%s,label=%s" % (
                        vlan,
                        proto,
                        label,
                    )

                share_type = self.container.get_manila_share_type(stype_search_name)
                if isinstance(share_type, dict):
                    share_type = share_type.get("name")

                # for stype in self.container.get_manila_share_type_list():
                #     stype_name = '-'.join(stype.get('name').split('-')[1:])
                #     # if stype_name.find(stype_search_name) > 0:
                #     if stype_name == stype_search_name:
                #         share_type = stype.get('name')
                #         break
                # if share_type is None:
                #     raise ApiManagerError('No suitable share type found')

            share_conf = {
                "name": name,
                "desc": self.resource.desc,
                "parent": project.oid,
                "tags": params.get("tags", ""),
                "share_proto": share_proto.upper(),
                "size": params.get("size", 0),
                "share_type": share_type,
                # 'snapshot_id' ''
                # 'share_group_id' : '',
                "network": ops_network_id,
                "subnet": ops_subnet_id,
                "metadata": params.get("metadata", {}),
                "availability_zone": availability_zone,
            }

            # create remote share
            prepared_task = self.create_resource(OpenstackShare, **share_conf)
            share = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop project creation")

            # update compute_zone attributes
            self.get_session(reopen=True)
            share_detail = self.get_resource(share.oid).detail().get("details")
            attribs = compute_share.get_attribs()
            export_locations = share_detail.get("export_locations", [])
            export_locations = [e.get("path") for e in export_locations]
            attribs["exports"] = export_locations
            attribs["host"] = share_detail.get("host", None)
            compute_share.update_internal(attribute=attribs)
            return share.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_share(self, share_id):
        """Import openstack share.

        :param  share_id:  share_id
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": share_id}, attrib={"reuse": False})
        return share_id

    def create_stack(self, project, params):
        """Create openstack stack.

        :param project: parent openstack project
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            template_uri = params.get("template_uri")
            environment = params.get("environment")
            parameters = params.get("parameters")
            files = params.get("files")

            name = "%s-%s-stack" % (self.resource.name, self.cid)

            stack_conf = {
                "parent": project.oid,
                "name": name,
                "desc": self.resource.desc,
                "template_uri": template_uri,
                "environment": environment,
                "parameters": parameters,
                "files": files,
                "owner": "admin",
            }

            # create remote stack
            prepared_task = self.create_resource(OpenstackHeatStack, **stack_conf)
            stack = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop project creation")

            # get final stack
            self.get_session(reopen=True)
            stack = self.get_resource(stack.uuid)

            # get stack resources list
            resources, total = stack.get_stack_resources()

            # get only servers
            servers = []
            for resource in resources:
                if isinstance(resource, OpenstackServer):
                    servers.append(resource)

            # get servers network configuration
            server_confs = []
            for server in servers:
                server_details = self.get_resource(server.oid).detail().get("details")

                # get networks
                server_nets = server_details["networks"]
                server_net = server_nets[0]

                # check network has a parent provider network
                provider_nets = self.task.get_orm_linked_resources(
                    server_net["net_id"],
                    link_type="relation",
                    container_id=None,
                    objdef=None,
                )
                provider_vpc = self.task.get_orm_linked_resources(
                    provider_nets[0].id,
                    link_type="relation.%",
                    container_id=None,
                    objdef=None,
                )

                # get security groups
                server_sgss = server_details["security_groups"]

                # check each security groups has a parent provider rule group
                provider_sgss = []
                for server_sgs in server_sgss:
                    rg = self.task.get_orm_linked_resources(
                        server_sgs["id"],
                        link_type="relation",
                        container_id=None,
                        objdef=None,
                    )
                    if len(rg) > 0:
                        sg = self.task.get_orm_linked_resources(
                            rg[0].id,
                            link_type="relation.%",
                            container_id=None,
                            objdef=None,
                        )

                        provider_sgss.append(sg[0].id)

                # create server config to use with twins only if exist a linked provider network
                if len(provider_nets) > 0 and len(provider_sgss) > 0:
                    # get subnet
                    fixed_ip = server_net["fixed_ips"][0]
                    server_subnet = self.get_resource(fixed_ip["subnet_id"]).info()["details"]

                    server_confs.append(
                        {
                            "name": server_details.get("name"),
                            "key_name": parameters.get("key_name"),
                            "vpc": provider_vpc[0].id,
                            "subnet_cidr": server_subnet["cidr"],
                            "ip_address": {"ip": fixed_ip["ip_address"]},
                            "security_groups": provider_sgss,
                        }
                    )

            params["server_confs"] = server_confs

            # # set shared data in parent compute stack job
            # rparams = task.get_shared_data(job=compute_stack_jobid)
            # rparams['server_confs'] = server_confs
            # task.set_shared_data(rparams, job=compute_stack_jobid)
            # self.progress('Update compute stack job %s shared data with server confs: %s' %
            #                              (compute_stack_jobid, rparams['server_confs']))
            return stack.oid, params
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_port(self, network_id, subnet_cidr, fixed_ip, rule_groups):
        """Create openstack port.

        :param network_id: network id
        :param subnet_cidr: network subnet cidr
        :param fixed_ip: fixed_ip network config
        :param rule_groups: rule group ids
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-port" % (self.resource.name, self.cid)

            # get network
            network = self.get_resource(network_id)
            remote_net = network.get_physical_resource_from_container(self.cid, OpenstackNetwork.objdef)

            # get subnet
            res, total = self.container.get_resources(
                type=OpenstackSubnet.objdef, parent=remote_net.oid, cidr=subnet_cidr
            )
            if total > 0:
                subnet = res[0]
            else:
                raise Exception("No valid subnet found")

            # get project
            parent = self.get_simple_resource(self.resource.parent_id)
            project = parent.get_physical_resource_from_container(self.cid, OpenstackProject.objdef)

            # get security groups
            remote_sgs = []
            for rule_group_id in rule_groups:
                sg = self.get_simple_resource(rule_group_id)
                remote_sg = sg.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef)
                remote_sgs.append(str(remote_sg.oid))

            # get network configuration
            if fixed_ip is not None:
                ip = fixed_ip.get("ip")
            else:
                # TODO: get ip from dhcp setting
                ip = "127.0.0.1"

            # create openstack port
            port_conf = {
                # 'container': cid,
                "name": name,
                "parent": remote_net.oid,
                "project": project.oid,
                "fixed_ips": [
                    {
                        "subnet_id": subnet.oid,
                        "ip_address": ip,
                    }
                ],
                "security_groups": remote_sgs,
                "vnic_type": "normal",
                "device_owner": "compute:twin"
                # 'device_id': None
            }

            # create remote port
            prepared_task = self.create_resource(OpenstackPort, **port_conf)
            port = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="create openstack port %s" % port.uuid)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_flavor(self):
        """Create openstack flavor.

        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-flavor" % (self.resource.name, self.cid)
            configs = self.resource.get_attribs("configs")

            # create openstack flavor
            flavor_conf = {
                "name": name,
                "parent": None,
                "desc": self.resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            prepared_task = self.create_resource(OpenstackFlavor, **flavor_conf)
            flavor = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="Create openstack flavor %s" % flavor.uuid)

            return flavor.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_flavor(self, flavor_id):
        """Import openstack flavor.

        :param flavor_id: flavor_id
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": flavor_id}, attrib={"reuse": True})
        return flavor_id

    def create_volumetype(self):
        """Create openstack volumetype.

        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-volumetype" % (self.resource.name, self.cid)
            configs = self.resource.get_attribs("configs")

            # create openstack volumetype
            volumetype_conf = {
                "name": name,
                "parent": None,
                "desc": self.resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            prepared_task = self.create_resource(OpenstackVolumeType, **volumetype_conf)
            volumetype = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="create openstack volumetype %s" % volumetype.uuid)

            return volumetype.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_volumetype(self, volumetype_id):
        """Import openstack volumetype.

        :param volumetype_id: volumetype_id
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": volumetype_id}, attrib={"reuse": True})
        return volumetype_id

    def create_volume(self, compute_volume, project, params):
        """Create openstack volume.

        :param compute_volume: compute volume id
        :param project: parent openstack project
        :param params: configuration params
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-volume" % (self.resource.name, self.cid)
            availability_zone = self.orchestrator["config"]["availability_zone"]

            volume_type = params.get("flavor")
            volume = params.get("volume")
            snapshot = params.get("snapshot")
            image = params.get("image")

            # create openstack volume
            volume_conf = {
                "name": name,
                "parent": project.oid,
                "desc": self.resource.desc,
                "availability_zone": availability_zone,
                "size": params.get("size"),
            }

            # set volume type
            volume_type = self.get_simple_resource(volume_type)
            remote_volume_type = volume_type.get_physical_resource_from_container(self.cid, OpenstackVolumeType.objdef)
            volume_conf["volume_type"] = remote_volume_type.uuid

            # set image
            if image is not None:
                image = self.get_simple_resource(image)
                remote_image = image.get_physical_resource_from_container(self.cid, OpenstackImage.objdef)
                volume_conf["imageRef"] = remote_image.uuid

            # set snapshot
            elif snapshot is not None:
                raise TaskError("snapshot is not already supported")

            # set volume
            elif volume is not None:
                volume = self.get_simple_resource(volume)
                remote_volumes, tot = volume.get_linked_resources(
                    link_type_filter="relation",
                    run_customize=False,
                    with_permtags=False,
                )

                remote_volume = remote_volumes[0]
                volume_conf["source_volid"] = remote_volume.uuid

            # create remote volume
            prepared_task = self.create_resource(OpenstackVolume, **volume_conf)
            volume = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="create openstack volume %s" % volume.uuid)

            # update compute_volume attributes
            self.get_session(reopen=True)
            volume = self.get_resource(volume.uuid)
            compute_volume = self.get_resource(compute_volume)
            volume_detail = volume.detail().get("details")
            attribs = compute_volume.get_attribs()
            dict_set(attribs, "configs.bootable", str2bool(volume_detail.get("bootable")))
            dict_set(attribs, "configs.encrypted", volume_detail.get("encrypted"))
            compute_volume.update_internal(attribute=attribs)

            return volume.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_volume(self, volume_id):
        """Import openstack volume.

        :param  volume_id:  volume_id
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": volume_id}, attrib={"reuse": False})
        return volume_id

    def create_image(self, image_id, *args):
        """Create openstack image.

        :param image_id: image_id
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": image_id}, attrib={"reuse": True})
        return image_id

    def remote_action(self, remote_object, action, params):
        """Send action to a remote entity based to entity class

        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        if isinstance(remote_object, OpenstackServer):
            return self.server_action(action, params)
        elif isinstance(remote_object, OpenstackPort):
            return self.port_action(action, params)

    def server_action(self, action, params):
        """Send action to openstack server.

        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            self.get_session(reopen=True)

            # get physical server
            remote_server = self.resource.get_physical_resource_from_container(self.cid, OpenstackServer.objdef)
            remote_server.post_get()
            action_func = getattr(remote_server, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for openstack server" % action)

            # run custom check function
            check = getattr(self, "server_action_%s" % action, None)
            if check is not None:
                params = check(**params)
            params["sync"] = True

            prepared_task, code = action_func(**params)
            res = self.run_sync_task(
                prepared_task,
                msg="Run action %s over server %s" % (action, remote_server.uuid),
            )
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise TaskError(ex)

    def server_action_extend_volume(self, volume=None, volume_size=None, *args, **kvargs):
        """Extend volume check function

        :param volume: zone volume id
        :return: kvargs
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_resource(volume)
        remote_volume = resource.get_physical_volume()
        return {"volume": remote_volume.oid, "volume_size": volume_size}

    def port_action(self, action, params):
        """Send action to openstack port.

        :param action: port action
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            self.get_session(reopen=True)

            # get physical server
            remote_port = self.resource.get_physical_resource_from_container(self.cid, OpenstackPort.objdef)
            remote_port.post_get()
            action_func = getattr(remote_port, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for openstack port" % action)

            # run custom check function
            check = getattr(self, "port_action_%s" % action, None)
            if check is not None:
                params = check(**params)
            params["sync"] = True

            prepared_task, code = action_func(**params)
            res = self.run_sync_task(
                prepared_task,
                msg="Run action %s over port %s" % (action, remote_port.uuid),
            )
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise TaskError(ex)

    def volume_action(self, action, params):
        """Send action to openstack volume.

        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            self.get_session(reopen=True)

            # get physical server
            remote_volume = self.resource.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
            remote_volume.post_get()
            action_func = getattr(remote_volume, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for openstack volume" % action)

            # run custom check function
            check = getattr(self, "volume_action_%s" % action, None)
            if check is not None:
                params = check(**params)
            params["sync"] = True

            prepared_task, code = action_func(**params)
            res = self.run_sync_task(
                prepared_task,
                msg="Run action %s over volume %s" % (action, remote_volume.uuid),
            )
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise TaskError(ex)

    def server_action_set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: zone flavor id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(flavor)
        remote_flavor = resource.get_physical_resource_from_container(self.cid, OpenstackFlavor.objdef)
        return {"flavor": remote_flavor.oid}

    def server_action_add_volume(self, volume=None, *args, **kvargs):
        """Add volume check function

        :param volume: zone volume id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
        return {"volume": remote_volume.oid}

    def server_action_del_volume(self, volume=None, *args, **kvargs):
        """Del volume check function

        :param volume: zone volume id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(self.cid, OpenstackVolume.objdef)
        return {"volume": remote_volume.oid}

    def server_action_add_security_group(self, security_group=None, *args, **kvargs):
        """Add security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def server_action_del_security_group(self, security_group=None, *args, **kvargs):
        """Del security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def volume_action_set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: zone flavor id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(flavor)
        remote_flavor = resource.get_physical_resource_from_container(self.cid, OpenstackVolumeType.objdef)
        return {"flavor": remote_flavor.oid}

    def port_action_add_security_group(self, security_group=None, *args, **kvargs):
        """Add security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def port_action_del_security_group(self, security_group=None, *args, **kvargs):
        """Del security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, OpenstackSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def remove_resource(self, childs):
        """delete openstack resources.

        :param childs: orchestrator childs
        :return: list
        :rtype: resource list
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            # get all child resources
            resources = []
            self.progress("Start removing openstack childs: %s" % childs)
            for child in childs:
                definition = child.objdef
                child_id = child.id
                attribs = json.loads(child.attribute)
                link_attr = json.loads(child.link_attr)
                reuse = link_attr.get("reuse", False)

                # get child resource
                entity_class = import_class(child.objclass)
                child = entity_class(
                    self.controller,
                    oid=child.id,
                    objid=child.objid,
                    name=child.name,
                    active=child.active,
                    desc=child.desc,
                    model=child,
                )
                child.container = self.container

                if reuse is True:
                    continue

                try:
                    if definition in [
                        OpenstackProject.objdef,
                        OpenstackSecurityGroup.objdef,
                        OpenstackRouter.objdef,
                        OpenstackServer.objdef,
                        OpenstackHeatStack.objdef,
                        OpenstackPort.objdef,
                        OpenstackShare.objdef,
                        OpenstackVolume.objdef,
                    ]:
                        prepared_task, code = child.expunge(sync=True)
                        self.run_sync_task(prepared_task, msg="remove child %s" % child.oid)

                    elif definition == OpenstackNetwork.objdef:
                        subnets, total = self.container.get_resources(parent=child_id)
                        self.progress("Get openstack network %s subnets" % child_id)

                        # delete subnets
                        for subnet in subnets:
                            prepared_task, code = subnet.expunge(sync=True)
                            self.run_sync_task(
                                prepared_task,
                                msg="delete openstack network subnet %s" % subnet["id"],
                            )

                        prepared_task, code = child.expunge(sync=True)
                        self.run_sync_task(prepared_task, msg="remove child %s" % child.oid)

                    elif definition == CustomResource.objdef:
                        sub_type = attribs["sub_type"]

                        # remove openstack rule
                        if sub_type == OpenstackSecurityGroupRule.objdef:
                            try:
                                sg = self.get_resource(attribs["security_group"])

                                # delete rule
                                prepared_task, code = sg.delete_rule({"rule_id": attribs["id"]}, sync=True)
                                self.run_sync_task(
                                    prepared_task,
                                    msg="remove openstack rule %s" % attribs["id"],
                                )

                                # delete resource
                                child.expunge(sync=True)

                            except (ModelError, ApiManagerError) as ex:
                                if ex.code == 404:
                                    self.logger.warn(ex)
                                else:
                                    raise

                    resources.append(child_id)
                    self.progress("Delete child %s" % child_id)
                except:
                    self.logger.error("Can not delete openstack child %s" % child_id, exc_info=True)
                    self.progress("Can not delete openstack child %s" % child_id)
                    raise

            self.progress("Stop removing openstack childs: %s" % childs)
            return resources
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)
