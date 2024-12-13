# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import copy
import ujson as json
from celery.utils.log import get_task_logger
from beecell.simple import import_class, get_value, id_gen, dict_set, str2bool
from base64 import b64encode, b64decode

from beehive.common.apimanager import ApiManagerError
from beehive.common.task.job import JobError, JobInvokeApiError
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
from beehive_resource.plugins.provider.entity.vpc import SiteNetwork, PrivateNetwork

logger = get_task_logger(__name__)


class ProviderOpenstack(object):
    QUOTAS = {
        "compute.instances": {"type": "compute", "quota": "instances", "factor": 1},
        # 'compute.images': {'type': 'compute', 'quota': 'instances', 'factor': 1},
        "compute.volumes": {
            "type": "blcreate_ruleock",
            "quota": "volumes",
            "factor": 1,
        },
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

    @staticmethod
    def create_zone_childs(task, orchestrator, resource, site, quotas=None):
        """Create availability zone childs.

        :param task: task reference
        :param orchestrator: orchestrator
        :param resource: parent resource
        :param site: site where is orchestrator
        :param quotas: list of quotas to set
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        rcid = orchestrator.get("id")
        domain = orchestrator["config"]["domain"]
        parent_project = site.get_physical_resource_from_container(rcid, OpenstackProject.objdef)
        project_id = ProviderOpenstack.create_project(task, rcid, resource, domain, parent_project)
        task.get_session(reopen=True)
        ProviderOpenstack.set_quotas(task, rcid, resource, quotas)
        return project_id

    @staticmethod
    def set_quotas(task, cid, resource, quotas):
        """Set openstack project quotas.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: resource
        :param quotas: list of quotas to set
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        # get project
        # project = task.get_resource(resource.parent_id)

        project = resource.get_physical_resource_from_container(cid, OpenstackProject.objdef)
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

        project.set_quotas(ops_quotas.values())
        task.progress("Set project %s quotas: %s" % (project.uuid, ops_quotas))
        return True

    @staticmethod
    def create_project(task, cid, resource, domain, parent_project):
        """Create openstack project.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: tenant resoruce
        :parma domain: domain id
        :param parent_project: parent project
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        # create project
        name = "%s-%s-project" % (resource.name, cid)
        project_id = None
        if parent_project is not None:
            project_id = parent_project.oid

        container = task.get_container(cid)
        res = container.resource_factory(
            OpenstackProject,
            name=name,
            desc=resource.desc,
            active=False,
            attribute={},
            parent=None,
            tags="",
            is_domain=False,
            enabled=True,
            domain_id=domain,
            project_id=project_id,
        )
        jobid = res[0]["jobid"]
        task.progress("Start project creation with job: %s" % jobid)
        task.release_session()

        # set up resource link
        task.get_session(reopen=True)
        project = task.get_resource(res[0]["uuid"])
        resource.add_link("%s-link" % project.oid, "relation", project.oid, attributes={})
        task.progress("Setup link to project %s" % project.oid)

        # wait job complete
        task.wait_for_job_complete(jobid)
        task.progress("Stop project creation with job: %s" % jobid)

        # get default security group
        task.release_session()
        task.get_session(reopen=True)
        security_groups, tot = project.get_security_groups()

        # reset default security group
        res = security_groups[0].reset_rule()
        task.wait_for_job_complete(res[0]["jobid"])
        task.progress("Reset project %s default security group" % project.oid)

        return project.oid

    @staticmethod
    def create_security_group(task, cid, resource, parent):
        """Create openstack security group.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: tenant resoruce
        :parma domain: domain id
        :param parent: parent
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        try:
            name = "%s-%s-sg" % (resource.name, cid)
            parent_project = parent.get_physical_resource_from_container(cid, orchestrator_mapping("openstack", 0))

            container = task.get_container(cid)
            res = container.resource_factory(
                OpenstackSecurityGroup,
                name=name,
                desc=resource.desc,
                active=False,
                attribute={},
                parent=parent_project.oid,
                tags="",
            )
            jobid = res[0]["jobid"]
            task.progress("Start security group creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            sg = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % sg.oid, "relation", sg.oid, attributes={})

            # wait job complete
            task.wait_for_job_complete(jobid)
            task.progress("Create security group: %s" % name)

            # reset security group
            task.get_session(reopen=True)
            sg = task.get_resource(res[0]["uuid"], details=True)
            res = sg.reset_rule()
            jobid = res[0]["jobid"]
            task.wait_for_job_complete(jobid)
            task.progress("Reset security group %s rules in project %s" % (sg.oid, parent_project.oid))

            return sg.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_network(
        task,
        cid,
        resource,
        network_type,
        name,
        vlan,
        external,
        private,
        physical_network=None,
        public_network=None,
    ):
        """Create openstack network.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param network_type: network type like flat, vlan, vxlan
        :param name: network name
        :param vlan: network vlan. Use with flat and vlan type
        :param external: True if network is used as external
        :param private: True if network is private
        :param physical_network: [optional] id of the openVswitch trunk
        :param public_network: [optional] id of the openVswitch public
        :return: entity instance
        :raise JobError: :class:`JobError`
        """
        try:
            name = "%s-%s-network" % (resource.name, cid)

            parent = task.get_resource(resource.parent_id)
            project = parent.get_physical_resource_from_container(cid, OpenstackProject.objdef)
            container = task.get_container(cid)

            # Use the network if it already exists.
            task.progress("Verify vlan %s is already assigned" % vlan)
            networks, tot = container.get_resources(
                objdef=OpenstackNetwork.objdef,
                type=OpenstackNetwork.objdef,
                segmentation_id=vlan,
            )
            if tot > 0:
                network_id = networks[0].oid
                name = networks[0].name
                task.progress("Network %s already exists" % network_id)
                task.progress("Get network: %s" % network_id)

                # create link
                attrib = {"reuse": True}
                resource.add_link(
                    "%s.%s-link" % (resource.oid, network_id),
                    "relation",
                    network_id,
                    attributes=attrib,
                )
                task.progress("Link openstack network %s" % network_id)

            # create new openstack network
            else:
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
                res = container.resource_factory(OpenstackNetwork, **config)
                jobid = res[0]["jobid"]
                task.progress("Start network creation with job: %s" % jobid)
                task.release_session()

                # set up resource link
                task.get_session(reopen=True)
                net = task.get_resource(res[0]["uuid"])
                network_id = net.oid
                attrib = {"reuse": False}
                resource.add_link(
                    "%s.%s-link" % (resource.oid, network_id),
                    "relation",
                    network_id,
                    attributes=attrib,
                )

                # wait job complete
                task.wait_for_job_complete(jobid)
                task.progress("Create network: %s" % name)

            # # get network subnets
            # net_subnets, tot = container.get_resources(objdef=OpenstackSubnet.objdef, type=OpenstackSubnet.objdef,
            #                                            parent=network_id)
            # net_subnets_idx = {i.get_cidr() for i in net_subnets}
            #
            # # create subnet if they don't already exist
            # # create openstack subnet - don't set gateway. Leave openstack to autoassign one from allocation
            # for subnet in subnets:
            #     cidr = subnet.get('cidr')
            #
            #     # subnet exists
            #     if cidr in net_subnets_idx:
            #         continue
            #
            #     service_types = None
            #     if subnet.get('allocable') is False:
            #         service_types = 'compute:twin'
            #     subnet_name = '%s-subnet-%s' % (name, id_gen())
            #     config = {
            #         'name': subnet_name,
            #         'desc': 'Subnet %s' % subnet_name,
            #         'project': project.oid,
            #         'parent': network_id,
            #         'gateway_ip': subnet.get('gateway', None),
            #         'cidr': cidr,
            #         'allocation_pools': subnet.get('allocation_pools'),
            #         'enable_dhcp': subnet.get('enable_dhcp'),
            #         'dns_nameservers': subnet.get('dns_nameservers', None),
            #         'service_types': service_types
            #     }
            #     if subnet.get('routes', None) is not None:
            #         config['host_routes'] = subnet.get('routes')
            #     task.logger.warn(config)
            #     res = container.resource_factory(OpenstackSubnet, **config)
            #     jobid = res[0]['jobid']
            #     task.progress('Start subnet creation with job: %s' % jobid)
            #
            #     # wait job complete
            #     task.wait_for_job_complete(jobid)
            #     task.progress('Create subnet: %s' % res[0]['uuid'])

            return network_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def append_network(task, resource, network_type, net_id):
        """Append openstack network.

        :param task: task reference
        :param resource: parent resource
        :param network_type: network type like flat, vlan, vxlan
        :param net_id: dvpg id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # create normal dvp
            if network_type in ["flat", "vlan"]:
                # get openstack network
                network = task.get_resource(net_id)
                network_id = network["id"]

            # create logical switch
            elif network_type == "vxlan":
                pass
                # TODO:
            else:
                raise JobError("Network type %s is not supported" % network_type)

            # task.progress('Create network %s' % network_id)

            # create link
            task.get_session(reopen=True)
            attrib = {"reuse": True}
            resource.add_link(
                "%s.%s-link" % (resource.oid, network_id),
                "relation",
                network_id,
                attributes=attrib,
            )
            task.progress("Link openstack network %s" % network_id)
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_subnet(
        task,
        cid,
        resource,
        cidr,
        gateway,
        routes,
        allocation_pools,
        enable_dhcp,
        dns_nameservers,
    ):
        """Create openstack subnet if it does not already exist.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent network
        :param gateway: gateway ip
        :param cidr: subnet cidr
        :param routes: subnet routes [defautl=None]
        :param allocation_pools: pools of continous ip in the subnet.
            Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
        :param enable_dhcp: if True enable dhcp
        :param dns_nameservers: list of dns. default=['8.8.8.8', '8.8.8.4']
        :return: entity instance
        :raise JobError: :class:`JobError`
        """
        try:
            container = task.get_container(cid)
            parent = task.get_resource(resource.parent_id)
            project = parent.get_physical_resource_from_container(cid, OpenstackProject.objdef)
            network = resource.get_physical_resource_from_container(cid, OpenstackNetwork.objdef)
            subnet_name = "%s-%s-%s-subnet" % (resource.name, cid, id_gen())

            # get network subnets
            net_subnets, tot = container.get_resources(
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

            res = container.resource_factory(OpenstackSubnet, **config)
            jobid = res[0]["jobid"]
            task.progress("Start subnet creation with job: %s" % jobid)

            # wait job complete
            task.wait_for_job_complete(jobid)
            task.progress("Create subnet: %s" % subnet_name)

            return res[0]["uuid"]
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def delete_subnet(task, cid, resource, subnet_id):
        """Delete openstack subnet.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent network
        :param subnet_id: id of the subnet
        :return: entity instance
        :raise JobError: :class:`JobError`
        """
        if subnet_id is None:
            task.progress("Subnet not present in openstack")
            return None

        try:
            container = task.get_container(cid)
            try:
                subnet = container.get_resource(subnet_id)
                task.progress("Get openstack subnet: %s" % subnet_id)
            except:
                task.progress("Openstack subnet %s is not already present" % subnet_id)
                return None

            # delete subnet
            res = subnet.expunge()
            jobid = res[0]["jobid"]
            task.wait_for_job_complete(jobid)
            task.progress("Delete openstack network subnet: %s" % subnet_id)

            return subnet_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_gateway(task, cid, resource, name, networks, parent_project):
        """Create openstack router.

        :param task: task reference
        :param cid: orchestrator id
        :param name: gateway name
        :param resource: tenant resoruce
        :param networks: openstack networks
            {'external':{'id':.., 'subnet':..}, 'internal':[subnet_obj1, subnet_obj2]}
        :param parent_project: parent project
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        try:
            name = "%s-%s-gateway" % (resource.name, cid)
            container = task.get_container(cid)

            config = {
                "name": name,
                "desc": name,
                "parent": parent_project.oid,
                "external_gateway_info": {
                    "external_fixed_ips": [{"subnet_id": networks["external"]["subnet"]}],
                    "network_id": networks["external"]["id"],
                },
            }
            res = container.resource_factory(OpenstackSubnet, **config)
            jobid = res[0]["jobid"]
            task.progress("Start router creation with job: %s" % jobid)
            task.release_session()

            # set up resource link
            task.get_session(reopen=True)
            router = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % router.oid, "relation", router.oid, attributes={})

            # wait job complete
            task.wait_for_job_complete(jobid)
            router_id = router.oid
            task.progress("Create router: %s" % name)

            # attach internal network to gateway
            for internal_subnet in networks["internal"]:
                # net_id = internal_net.oid
                subnet_id = internal_subnet.oid
                router.create_port({"subnet_id": subnet_id})
                task.progress("Append internal network to router %s" % router_id)

            return router_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_rule(task, cid, zone, resource, source, destination, service):
        """Create openstack rule.

        :param task: task reference
        :param cid: orchestrator id
        :param zone: availability zone
        :param resource: parent resource
        :param source: source
        :param destination: destination
        :param service: service.
            Ex. {'port':'*', 'protocol':'*'} -> *:*
                {'port':'*', 'protocol':6} -> tcp:*
                {'port':80, 'protocol':6} -> tcp:80
                {'port':80, 'protocol':17} -> udp:80
                {'protocol':1, 'subprotocol':8} -> icmp:echo request
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        try:
            uuid = resource.uuid

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
                    if service["subprotocol"] == "*":
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
                res = task.get_resource(source["value"])
                sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                res = task.get_resource(destination["value"])
                sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid
                # get source cidr
                cidr = source["value"]
                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                res = task.get_resource(source["value"])
                sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid
                # get destination cidr
                cidr = destination["value"]
                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                res = task.get_resource(source["value"])
                source_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid
                # get destination security group id
                res = task.get_resource(destination["value"])
                dest_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                res = task.get_resource(source["value"])
                source_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                # get destination server id
                server_id = destination["value"]
                # get destination security group id where is the server
                server = task.get_resource(server_id)
                res = task.get_resource(server.parent_id)
                dest_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                server = task.get_resource(server_id)
                res = task.get_resource(server.parent_id)
                source_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                # get destination security group id
                res = task.get_resource(destination["value"])
                dest_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                server = task.controller.get_resource(source_server_id)
                res = task.get_resource(server.parent_id)
                source_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                # get destination server id
                dest_server_id = destination["value"]
                # get destination security group id where is the server
                server = task.controller.get_resource(dest_server_id)
                res = task.get_resource(dest_server_id.parent_id)
                dest_sg_id = res.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef).oid

                policies.append(
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
                    ProviderOpenstack.create_openstack_rule(
                        task,
                        resource,
                        cid,
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
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_openstack_rule(
        task,
        resource,
        cid,
        sg_id,
        direction,
        port_range_min,
        port_range_max,
        protocol,
        group=None,
        cidr=None,
    ):
        """Create openstack security group rule

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param direction: ingress or egress
        :param port_range_min: min port range
        :param port_range_max: max port range
        :param protocol: protocol tcp, udp, icmp or None
        :param group: security group id [default=None]
        :param cidr: cidr [default=None]
        """
        task.get_session(reopen=True)

        rule = {"direction": direction, "ethertype": "IPV4", "protocol": protocol}
        if port_range_min is not None:
            rule["port_range_min"] = port_range_min
        if port_range_max is not None:
            rule["port_range_max"] = port_range_max
        if group is not None:
            rule["remote_group_id"] = str(group)
        if cidr is not None:
            rule["remote_ip_prefix"] = cidr

        task.progress("Configure openstack rule: %s" % rule)

        # get security group
        sg = task.get_resource(sg_id, details=True)

        # create rule
        res = sg.create_rule(rule)
        jobid = res[0]["jobid"]
        task.progress("Start rule creation with job: %s" % jobid)
        task.release_session()

        # wait job complete
        task.get_session(reopen=True)
        task_obj = task.wait_for_job_complete(jobid)
        rule_id = task_obj.get("result")
        task.progress("Create openstack rule %s.%s" % (sg_id, rule_id))

        # create custom resource
        orchestrator = task.get_container(cid)
        objid = "%s//%s" % (orchestrator.objid, id_gen())
        name = "openstack_rule_%s" % rule_id
        desc = name
        attribs = {
            "security_group": sg_id,
            "id": rule_id,
            "type": "openstack",
            "sub_type": OpenstackSecurityGroupRule.objdef,
        }
        resource_model = orchestrator.add_resource(
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
        resource_id = resource_model.id
        orchestrator.update_resource_state(resource_id, 2)
        orchestrator.activate_resource(resource_id)
        task.release_session()
        task.progress("Create resource: %s" % resource_id)

        task.get_session(reopen=True)
        resource.add_link("%s-link" % resource_id, "relation", resource_id, attributes={})
        task.release_session()
        task.progress("Setup link to resource to %s" % resource_id)

        return rule_id

    @staticmethod
    def user_data(
        gateway=None,
        hostname=None,
        domain=None,
        dns=None,
        pwd=None,
        sshkey=None,
        users=[],
        cmds=[],
        routes=[],
    ):
        """Setup user data

        :param users: list of dict like {'name':.., 'pwd':[optional], 'sshkeys':[..], 'uid':[optional]}
        :param gateway: network gateway
        :param hostname: server hostname
        :param domain: server domain
        :param dns: server dns
        :param pwd: server root pwd
        :param sshkey: server root sshkey
        :param cmds: list of custom command to execute
        :param route: list of ip route
        :return: entity instance
        """
        user_data = ["#cloud-config", "bootcmd:", "disable_root: false"]
        if gateway:
            user_data.append("  - [ ip, route, change, default, via, %s ]" % gateway)
        if routes:
            for route in routes:
                user_data.append("  - [ %s ]" % route)
        if hostname:
            user_data.append("hostname: %s" % hostname)
            if domain:
                fqdn = "%s.%s" % (hostname, domain)
                # hostname = hostname + ' ' + fqdn
                user_data.append("fqdn: %s" % fqdn)
                user_data.append("hostname: %s" % fqdn)
                user_data.append("manage_etc_hosts: true")
                user_data.append("manage-resolv-conf: true")
            # user_data.append('echo `hostname -I` %s >> /etc/hosts' % hostname)
        if dns and domain:
            user_data.append("resolv_conf:")
            user_data.append("  nameservers: %s" % dns)
            user_data.append("  searchdomains:")
            user_data.append("    - %s" % domain)
            user_data.append("  domain: %s" % domain)
        if cmds:
            user_data.append("runcmd:")
            for cmd in cmds:
                user_data.append("  - %s" % cmd)
        if users:
            user_data.append("users:")
            user_data.append("  - default")
            for user in users:
                user_data.append("  - name: %s" % user["name"])
                user_data.append("    ssh-authorized-keys:")
                for sshkey in user["sshkeys"]:
                    user_data.append("      - %s" % sshkey)
                pwd = user.get("pwd", None)
                if pwd is not None:
                    user_data.append("    lock_passwd: false")
                    user_data.append("    passwd: %s" % pwd)
                uid = user.get("uid", None)
                if uid is not None:
                    user_data.append("    uid: %s" % uid)
        if pwd:
            user_data.append("ssh_pwauth: yes")
            # user_data.append('password: %s' % pwd)
            user_data.append("chpasswd:")
            user_data.append("  list: |")
            user_data.append("    root:%s" % pwd)
            user_data.append("  expire: False")
        if sshkey:
            user_data.append("ssh_authorized_keys:")
            user_data.append("  - %s" % sshkey)

        return b64encode("\n".join(user_data))

    @staticmethod
    def import_server(task, orchestrator, resource, params):
        """Import openstack server.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param params: configuration params
        :return: resource id
        :raiseJobError: If task fails
        """
        try:
            networks = params.get("networks")

            # get server
            server = task.get_resource_with_detail(params.get("physical_server_id"))

            # set up resource link
            resource.add_link("%s-link" % server.oid, "relation", server.oid, attributes={})
            task.progress("Setup link to %s" % server.oid)

            # get server networks
            server_nets = server.detail()["details"]["networks"]
            server_net_idx = {str(n["net_id"]): n["fixed_ips"][0]["ip_address"] for n in server_nets}
            logger.warn(server_net_idx)
            logger.warn(networks)

            # assign ip to network conf
            for network_conf in networks:
                physical_net_id = network_conf.get("physical_net_id")
                fixed_ip = network_conf.get("fixed_ip", None)
                if fixed_ip is not None:
                    network_conf["fixed_ip"] = {"ip": server_net_idx[str(physical_net_id)]}

            params["networks"] = networks
            task.set_shared_data(params)
            task.progress("Update shared data with network: %s" % params["networks"])
            return server.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_server(task, orchestrator, resource, project, params):
        """Create openstack server.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param project: parent openstack project
        :param params: configuration params
        :return: resource id
        :raise JobError:
        """
        try:
            task.get_session(reopen=True)

            flavor_id = params.get("flavor")
            # image_id = params.get('image')
            environments = params.get("security_groups")
            admin_pass = params.get("admin_pass")
            # key_name = params.get('key_name', None)
            networks = params.get("networks")
            # storage = params.get('storage')
            zone_boot_volume = params.get("zone_boot_volume")
            zone_other_volumes = params.get("zone_other_volumes")
            metadata = params.get("metadata")
            user_data = params.get("user_data")
            personality = params.get("personality")
            if metadata is None:
                metadata = {}
            if personality is None:
                personality = []

            uuid = resource.uuid
            cid = orchestrator["id"]
            container = task.get_container(cid)
            name = "%s-%s-server" % (resource.name, cid)
            orchestrator_type = "openstack"
            availability_zone = orchestrator["config"]["availability_zone"]

            server_conf = {
                # 'container': str(cid),
                # 'project': str(project.oid),
                "parent": project.oid,
                "name": name,
                "desc": resource.desc,
                "flavorRef": None,
                # 'imageRef': None,
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
            flavor = task.get_resource(flavor_id, run_customize=False)
            remote_flavor = flavor.get_physical_resource_from_container(cid, OpenstackFlavor.objdef)
            server_conf["flavorRef"] = remote_flavor.uuid

            # get security_groups from environments
            for environment_id in environments:
                env = task.get_resource(environment_id, run_customize=False)
                objdef = orchestrator_mapping(orchestrator_type, 1)
                sg = env.get_physical_resource_from_container(cid, objdef)
                server_conf["security_groups"].append(sg.uuid)

            # set networks
            net = 0
            for network_conf in networks:
                uuid = network_conf.get("id")
                subnet = network_conf.get("subnet")
                # other_subnets = network_conf.get('other_subnets')
                subnet_cidr = network_conf.get("subnet").get("cidr")
                fixed_ip = network_conf.get("fixed_ip", {})
                network = task.get_resource(uuid)

                # get remote network
                if isinstance(network, SiteNetwork):
                    objdef = orchestrator_mapping(orchestrator_type, 2)
                elif isinstance(network, PrivateNetwork):
                    objdef = orchestrator_mapping(orchestrator_type, 3)
                remote_net = network.get_physical_resource_from_container(cid, objdef)

                # get network subnets
                net_subnets, tot = container.get_resources(
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
                server_conf["networks"].append(config)

                # set user data - exec only for net card 0
                if net == 0:
                    try:
                        sshkey = metadata.get("pubkey")
                    except:
                        sshkey = None
                    users = None  # TODO gestione user e sshkey
                    routes = []

                    user_data = ProviderOpenstack.user_data(
                        gateway=subnet["gateway"],
                        users=users,
                        pwd=admin_pass,
                        sshkey=sshkey,
                        domain=fixed_ip.get("dns_search", "nivolalocal"),
                        hostname=fixed_ip.get("hostname"),
                        routes=routes,
                    )
                    server_conf["user_data"] = user_data
                net += 1

            # configure boot volume
            volume = task.get_resource(zone_boot_volume, run_customize=False)
            remote_volume = volume.get_physical_resource_from_container(cid, OpenstackVolume.objdef)
            conf = {
                "boot_index": 0,
                "source_type": "volume",
                "uuid": remote_volume.uuid,
                "destination_type": "volume",
            }
            server_conf["block_device_mapping_v2"].append(conf)

            # create remote server
            container = task.get_container(cid)
            res = container.resource_factory(OpenstackServer, **server_conf)
            jobid = res[0]["jobid"]
            task.progress("Start server creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            server = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % server.oid, "relation", server.oid, attributes={})
            task.progress("Setup link to %s" % server.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack server %s" % server.uuid)

            # get final server
            task.get_session(reopen=True)
            server = task.get_resource(res[0]["uuid"], details=True)

            # get server networks
            server_nets = server.detail()["details"]["networks"]
            server_net_idx = {str(n["net_id"]): n["fixed_ips"][0]["ip_address"] for n in server_nets}

            # assign dhcp ip to network conf
            for network_conf in networks:
                uuid = network_conf.get("id")
                fixed_ip = network_conf.get("fixed_ip", None)
                if fixed_ip is not None:
                    # get remote network
                    network = task.get_resource(uuid)

                    if isinstance(network, SiteNetwork):
                        objdef = orchestrator_mapping(orchestrator_type, 2)
                    elif isinstance(network, PrivateNetwork):
                        objdef = orchestrator_mapping(orchestrator_type, 3)

                    remote_net = network.get_physical_resource_from_container(cid, objdef)

                    network_conf["fixed_ip"] = {"ip": server_net_idx[str(remote_net.uuid)]}

            params["networks"] = networks
            task.set_shared_data(params)
            task.progress("Update shared data with network: %s" % params["networks"])

            # attach other volumes to server
            for zone_other_volume in zone_other_volumes:
                volume = task.get_resource(zone_other_volume, run_customize=False)
                remote_volume = volume.get_physical_resource_from_container(cid, OpenstackVolume.objdef)
                server.add_volume(volume=remote_volume.uuid)
                task.progress("Attach volume %s to server" % zone_other_volume)

            return server.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_share(task, orchestrator, resource, project, params, compute_share):
        """Create openstack share.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param project: parent openstack project
        :param params: configuration params
        :param compute_share: compute_share resource
        :return: resource id
        :raise JobError: If task fails
        """
        try:
            cid = orchestrator["id"]
            name = "%s-%s-share" % (resource.name, cid)
            availability_zone = orchestrator["config"]["availability_zone"]

            # get orchestrator
            container = task.get_container(cid)
            # prefix = container.get_manila_share_type_prefix()
            share_proto = params.get("share_proto").lower()
            vlan = params.get("network").get("vlan")
            subprefix = share_proto
            if share_proto == "cifs":
                subprefix = "smb"

            # get share type name
            share_type = None
            for stype in container.get_manila_share_type_list():
                stypename = stype.get("name")
                if stypename.find("%s-%s" % (subprefix, vlan)) > 0:
                    share_type = stypename
                    break
            if share_type is None:
                raise ApiManagerError("No suitable share type found")

            # share_type = '%s-%s-%s' % (prefix, subprefix, vlan)

            share_conf = {
                "name": name,
                "desc": resource.desc,
                "parent": project.oid,
                "tags": params.get("tags", ""),
                "share_proto": share_proto.upper(),
                "size": params.get("size", 0),
                "share_type": share_type,
                # 'snapshot_id' ''
                # 'share_group_id' : '',
                "metadata": params.get("metadata", {}),
                "availability_zone": availability_zone,
            }

            # create remote share
            res = container.resource_factory(OpenstackShare, **share_conf)
            jobid = res[0]["jobid"]
            task.progress("Start share creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            share = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % share.oid, "relation", share.oid, attributes={})
            task.progress("Setup link to %s" % share.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack share %s" % share.uuid)

            # update compute_zone attributes
            task.get_session(reopen=True)
            share_detail = task.get_resource(res[0]["uuid"], details=True).detail().get("details")
            attribs = compute_share.get_attribs()
            attribs["exports"] = share_detail.get("export_locations", [])
            attribs["host"] = share_detail.get("host", None)
            compute_share.update_internal(attribute=attribs)
            return share.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_share(task, resource, share_id):
        """Import openstack share.

        :param task: task reference
        :param resource: parent resource
        :param  share_id:  share_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, share_id),
                "relation",
                share_id,
                attributes={"reuse": False},
            )
            task.progress("Setup link to %s" % share_id)

            return share_id
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_stack(task, orchestrator, resource, project, params, compute_stack_jobid):
        """Create openstack server.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param project: parent openstack project
        :param params: configuration params
        :param compute_stack_jobid: compute stack jobid
        :return: resource id
        :raise JobError:
        """
        try:
            template_uri = params.get("template_uri")
            environment = params.get("environment")
            parameters = params.get("parameters")
            files = params.get("files")
            provider_id = resource.container.oid

            # uuid = resource.uuid
            cid = orchestrator["id"]
            name = "%s-%s-stack" % (resource.name, cid)
            # orchestrator_type = 'openstack'

            stack_conf = {
                "parent": project.oid,
                "name": name,
                "desc": resource.desc,
                "template_uri": template_uri,
                "environment": environment,
                "parameters": parameters,
                "files": files,
                "owner": "admin",
            }

            # create remote stack
            container = task.get_container(cid)
            res = container.resource_factory(OpenstackHeatStack, **stack_conf)
            jobid = res[0]["jobid"]
            task.progress("Start stack creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            stack = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % stack.oid, "relation", stack.oid, attributes={})
            task.progress("Setup link to %s" % stack.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack stack %s" % stack.uuid)

            # get final stack
            task.get_session(reopen=True)
            stack = task.get_resource(res[0]["uuid"], details=True)

            # get stack resources list
            resources, total = stack.get_stack_resources(details=False)

            # get only servers
            servers = []
            for resource in resources:
                if isinstance(resource, OpenstackServer):
                    servers.append(resource)

            # get servers network configuration
            server_confs = []
            for server in servers:
                server_details = task.get_resource(server.oid, details=True).detail().get("details")

                # get networks
                server_nets = server_details["networks"]
                server_net = server_nets[0]

                # check network has a parent provider network
                provider_nets = task.get_linked_resources(
                    server_net["net_id"],
                    link_type="relation",
                    container_id=None,
                    objdef=None,
                )
                # provider_net = provider_nets[0]
                provider_vpc = task.get_linked_resources(
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
                    rg = task.get_linked_resources(
                        server_sgs["id"],
                        link_type="relation",
                        container_id=None,
                        objdef=None,
                    )
                    if len(rg) > 0:
                        sg = task.get_linked_resources(
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
                    server_subnet = task.get_resource(fixed_ip["subnet_id"], details=True).info()["details"]

                    server_confs.append(
                        {
                            "name": server_details.get("name"),
                            "key_name": parameters.get("key_name"),
                            "vpc": provider_vpc[0].id,
                            # 'network': provider_net.id,
                            "subnet_cidr": server_subnet["cidr"],
                            "ip_address": {"ip": fixed_ip["ip_address"]},
                            "security_groups": provider_sgss,
                        }
                    )

            params["server_confs"] = server_confs
            task.set_shared_data(params)
            task.progress("Update shared data with server confs: %s" % params["server_confs"])

            # set shared data in parent compute stack job
            rparams = task.get_shared_data(job=compute_stack_jobid)
            rparams["server_confs"] = server_confs
            task.set_shared_data(rparams, job=compute_stack_jobid)
            task.progress(
                "Update compute stack job %s shared data with server confs: %s"
                % (compute_stack_jobid, rparams["server_confs"])
            )
            return stack.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_port(task, cid, resource, network_id, subnet_cidr, fixed_ip, rule_groups):
        """Create openstack port.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param name: name
        :param network_id: network id
        :param subnet_cidr: network subnet cidr
        :param fixed_ip: fixed_ip network config
        :param rule_groups: rule group ids
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            name = "%s-%s-port" % (resource.name, cid)

            # get network
            network = task.get_resource(network_id)
            remote_net = network.get_physical_resource_from_container(cid, OpenstackNetwork.objdef)

            # get subnet
            res, total = container.get_resources(type=OpenstackSubnet.objdef, parent=remote_net.oid, cidr=subnet_cidr)
            if total > 0:
                subnet = res[0]
            else:
                raise Exception("No valid subnet found")

            # get project
            parent = task.get_resource(resource.parent_id)
            project = parent.get_physical_resource_from_container(cid, OpenstackProject.objdef)

            # get security groups
            remote_sgs = []
            for rule_group_id in rule_groups:
                sg = task.get_resource(rule_group_id)
                remote_sg = sg.get_physical_resource_from_container(cid, OpenstackSecurityGroup.objdef)
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
            res = container.resource_factory(OpenstackPort, **port_conf)
            jobid = res[0]["jobid"]
            task.progress("Start port creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            port = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % port.oid, "relation", port.oid, attributes={})
            task.progress("Setup link to %s" % port.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack port %s" % port.uuid)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_flavor(task, cid, resource):
        """Create openstack flavor.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            name = "%s-%s-flavor" % (resource.name, cid)
            configs = resource.get_attribs("configs")

            # create openstack flavor
            flavor_conf = {
                "name": name,
                "parent": None,
                "desc": resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            res = container.resource_factory(OpenstackFlavor, **flavor_conf)
            jobid = res[0]["jobid"]
            task.progress("Start flavor creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            flavor = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % flavor.oid, "relation", flavor.oid, attributes={})
            task.progress("Setup link to %s" % flavor.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack flavor %s" % flavor.uuid)

            return flavor.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_flavor(task, cid, resource, flavor_id):
        """Import openstack flavor.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param flavor_id: flavor_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, flavor_id),
                "relation",
                flavor_id,
                attributes={"reuse": True},
            )
            task.progress("Setup link to %s" % flavor_id)

            return flavor_id
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_volumetype(task, cid, resource):
        """Create openstack volumetype.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            name = "%s-%s-volumetype" % (resource.name, cid)
            configs = resource.get_attribs("configs")

            # create openstack volumetype
            volumetype_conf = {
                "name": name,
                "parent": None,
                "desc": resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            res = container.resource_factory(OpenstackVolumeType, **volumetype_conf)
            jobid = res[0]["jobid"]
            task.progress("Start volumetype creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            volumetype = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % volumetype.oid, "relation", volumetype.oid, attributes={})
            task.progress("Setup link to %s" % volumetype.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack volumetype %s" % volumetype.uuid)

            return volumetype.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_volumetype(task, cid, resource, volumetype_id):
        """Import openstack volumetype.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param  volumetype_id:  volumetype_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, volumetype_id),
                "relation",
                volumetype_id,
                attributes={"reuse": True},
            )
            task.progress("Setup link to %s" % volumetype_id)

            return volumetype_id
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_volume(task, orchestrator, compute_volume, resource, project, params):
        """Create openstack volume.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param compute_volume: compute volume id
        :param resource: parent resource
        :param project: parent openstack project
        :param params: configuration params
        :return: resource id
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)

            cid = orchestrator["id"]
            name = "%s-%s-volume" % (resource.name, cid)
            availability_zone = orchestrator["config"]["availability_zone"]
            container = task.get_container(cid)

            volume_type = params.get("flavor")
            volume = params.get("volume")
            snapshot = params.get("snapshot")
            image = params.get("image")

            # create openstack volume
            volume_conf = {
                "name": name,
                "parent": project.oid,
                "desc": resource.desc,
                "availability_zone": availability_zone,
                "size": params.get("size"),
            }

            # set volume type
            volume_type = task.get_resource(volume_type, run_customize=False)
            remote_volume_type = volume_type.get_physical_resource_from_container(cid, OpenstackVolumeType.objdef)
            volume_conf["volume_type"] = remote_volume_type.uuid

            # set image
            if image is not None:
                image = task.get_resource(image, run_customize=False)
                remote_image = image.get_physical_resource_from_container(cid, OpenstackImage.objdef)
                volume_conf["imageRef"] = remote_image.uuid

            # set volume
            elif volume is not None:
                volume = task.get_resource(volume, run_customize=False)
                remote_volume = volume.get_physical_resource_from_container(cid, OpenstackVolume.objdef)
                volume_conf["source_volid"] = remote_volume.uuid

            # create remote volume
            res = container.resource_factory(OpenstackVolume, **volume_conf)
            jobid = res[0]["jobid"]
            task.progress("Start volume creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            volume = task.get_resource(res[0]["uuid"], run_customize=False)
            resource.add_link(
                "%s.%s-link" % (resource.oid, volume.oid),
                "relation",
                volume.oid,
                attributes={},
            )
            task.progress("Setup link to %s" % volume.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create openstack volume %s" % volume.uuid)

            # update compute_volume attributes
            task.get_session(reopen=True)
            volume = task.get_resource(res[0]["uuid"], run_customize=True, details=True)
            compute_volume = task.get_resource(compute_volume, details=False)
            volume_detail = volume.detail().get("details")
            attribs = compute_volume.get_attribs()
            dict_set(attribs, "configs.bootable", str2bool(volume_detail.get("bootable")))
            dict_set(attribs, "configs.encrypted", volume_detail.get("encrypted"))
            compute_volume.update_internal(attribute=attribs)

            return volume.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_volume(task, resource, volume_id):
        """Import openstack volume.

        :param task: task reference
        :param resource: parent resource
        :param  volume_id:  volume_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, volume_id),
                "relation",
                volume_id,
                attributes={"reuse": False},
            )
            task.progress("Setup link to %s" % volume_id)

            return volume_id
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_image(task, cid, resource, image_id, *args):
        """Create openstack image.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param image_id: image_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, image_id),
                "relation",
                image_id,
                attributes={"reuse": True},
            )
            task.progress("Setup link to %s" % image_id)

            return image_id
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def server_action(task, cid, resource, action, params):
        """Send action to openstack server.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: availability zone instance
        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise JobError:
        """
        try:
            task.get_session(reopen=True)

            # get physical server
            remote_server = resource.get_physical_resource_from_container(cid, OpenstackServer.objdef)
            remote_server.post_get()
            action_func = getattr(remote_server, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for openstack server" % action)

            # run custom check function
            check = getattr(ProviderOpenstack, "server_action_%s" % action, None)
            if check is not None:
                params = check(task, cid, **params)

            res = action_func(**params)
            jobid = res[0]["jobid"]
            task.progress("Start run action %s over server %s with job: %s" % (action, remote_server.uuid, jobid))

            task.wait_for_job_complete(jobid)
            task.progress("Run action %s over server %s" % (action, remote_server.uuid))
            return res
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def server_action_set_flavor(task, cid, flavor=None):
        """Set flavor check function

        :param task: task reference
        :param cid: orchestrator id
        :param flavor: zone flavor id
        :return: kvargs
        """
        resource = task.get_resource(flavor)
        remote_flavor = resource.get_physical_resource_from_container(cid, OpenstackFlavor.objdef)
        return {"flavor": remote_flavor.oid}

    @staticmethod
    def server_action_add_volume(task, cid, volume=None):
        """Add volume check function

        :param task: task reference
        :param cid: orchestrator id
        :param volume: zone volume id
        :return: kvargs
        """
        resource = task.get_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(cid, OpenstackVolume.objdef)
        return {"volume": remote_volume.oid}

    @staticmethod
    def server_action_del_volume(task, cid, volume=None):
        """Del volume check function

        :param task: task reference
        :param cid: orchestrator id
        :param volume: zone volume id
        :return: kvargs
        """
        resource = task.get_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(cid, OpenstackVolume.objdef)
        return {"volume": remote_volume.oid}

    @staticmethod
    def remove_resource(task, provider, cid, childs):
        """Delete openstack resources.

        :param task: task reference
        :param provider: provider container
        :param cid: remote orchestrator id
        :parma childs: orchestrator childs
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            # get all child resources
            resources = []
            task.progress("Start removing childs %s" % childs)
            for child in childs:
                definition = child.objdef
                child_id = child.id
                attribs = json.loads(child.attribute)
                link_attr = json.loads(child.link_attr)
                reuse = link_attr.get("reuse", False)

                # get child resource
                entity_class = import_class(child.objclass)
                child = entity_class(
                    container.controller,
                    oid=child.id,
                    objid=child.objid,
                    name=child.name,
                    active=child.active,
                    desc=child.desc,
                    model=child,
                )
                child.container = container

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
                        res = child.expunge()
                        jobid = res[0]["jobid"]
                        task.wait_for_job_complete(jobid)

                    elif definition == OpenstackNetwork.objdef:
                        subnets, total = container.get_resources(parent=child_id)
                        task.progress("Get openstack network %s subnets" % child_id)

                        # delete subnets
                        for subnet in subnets:
                            res = subnet.expunge()
                            jobid = res[0]["jobid"]
                            task.wait_for_job_complete(jobid)
                            task.progress("Delete openstack network subnet %s" % subnet["id"])

                        res = child.expunge()
                        jobid = res[0]["jobid"]
                        task.wait_for_job_complete(jobid)

                    elif definition == CustomResource.objdef:
                        sub_type = attribs["sub_type"]

                        # remove openstack rule
                        if sub_type == OpenstackSecurityGroupRule.objdef:
                            try:
                                sg = task.get_resource(attribs["security_group"])

                                # delete rule
                                sg.delete_rule({"rule_id": attribs["id"]})

                                # delete resource
                                child.expunge()

                            except ApiManagerError as ex:
                                if ex.code == 404:
                                    logger.warn(ex)
                                else:
                                    raise

                    resources.append(child_id)
                    task.progress("Delete child %s" % child_id)
                except:
                    logger.error("Can not delete openstack child %s" % child_id, exc_info=1)
                    task.progress("Can not delete openstack child %s" % child_id)
                    raise

            task.progress("Stop removing childs %s" % childs)
            return resources
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)
