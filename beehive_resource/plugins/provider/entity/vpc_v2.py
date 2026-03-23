# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from ipaddress import ip_network
from typing import Literal, List, TYPE_CHECKING, Optional, TypedDict
from beecell.types.type_string import truncate
from beecell.types.type_ip import subnet_is_internet
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.model import Resource as ModelResource
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import SiteChildResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
if TYPE_CHECKING:
    from beehive_resource.plugins.provider.entity.site import Site
    from beehive_resource.plugins.vsphere.controller import VsphereContainer

class Vpc(ComputeProviderResource):
    """Vpc"""

    objdef = "Provider.ComputeZone.Vpc"
    objuri = "%s/vpcs/%s"
    objname = "vpc"
    objdesc = "Provider Vpc"
    task_path = "beehive_resource.plugins.provider.task_v2.vpc.VpcTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        from beehive_resource.plugins.provider.entity.security_group import (
            SecurityGroup,
        )
        from beehive_resource.plugins.provider.entity.vpc_endpoint import VpcEndpoint

        self.child_classes = [SecurityGroup, VpcEndpoint]
    
    def is_internet(self)->bool:
        """
        Returns:
            bool:True if internet cidr
        """
        return subnet_is_internet(self.get_cidr())
        

    def get_cidr(self):
        """ Get vpc cidr """
        return self.get_attribs("configs.cidr", "")

    def get_type(self):
        """ Get vpc type """
        return self.get_attribs("configs.type", "shared")

    def is_private(self):
        """ Is the vpc private? """
        if self.get_type() == "private":
            return True
        return False

    def is_shared(self):
        """ Is the vpc shared? """
        if self.get_type() == "shared":
            return True
        return False

    def __render_pool(self, pool):
        if pool is not None:
            return ",".join([f"{p.get('start', '')}-{p.get('end', '')}" for p in pool])
        return ""

    class SubnetFilter(TypedDict):
        site_name: str
        orchestrator_type: Literal["vsphere", "openstack"]

    def get_subnets(
            self,
            filters: Optional[List[SubnetFilter]] = None,
            allocable_only: bool = False,
            allocation_pools_details=False
    ):
        """
        Get vpc subnets.
        """
        nets, _ = self.get_linked_resources(link_type_filter="relation%")
        res = []

        def matches_filters(site_name: str, orch_type: str) -> bool:
            """Check if the given site/orchestrator matches at least one filter."""
            if filters is None:
                return True
            for f in filters:
                if f["site_name"] == site_name and f["orchestrator_type"] == orch_type:
                    return True
            return False

        for net in nets:
            info = net.info()
            site = info["availabilty_zone"]["name"]

            if isinstance(net, PrivateNetwork):
                subnet = {"cidr": net.get_cidr(), "hypervisor": [], "allocable": True}
                physical_nets, _ = net.get_linked_resources(link_type_filter="relation")
                for physical_net in physical_nets:
                    hypervisor = None
                    if isinstance(physical_net, OpenstackNetwork):
                        hypervisor = "openstack"
                    elif isinstance(physical_net, NsxLogicalSwitch):
                        hypervisor = "vsphere"

                    if hypervisor and matches_filters(site, hypervisor):
                        item = {
                            "type": hypervisor,
                            "vxlan": physical_net.get_vlan(),
                            "cidr": physical_net.get_private_subnet(),
                            "gateway": physical_net.get_gateway(),
                            "pool": self.__render_pool(physical_net.get_allocation_pool()),
                        }
                        if allocation_pools_details:
                            item[ "available_ips"] = physical_net.get_available_pool_counter()
                        subnet["hypervisor"].append(item)

                info["attributes"]["configs"]["subnets"] = [subnet]
                res.append(info)

            elif isinstance(net, SiteNetwork):
                # net is the SiteNetwork
                subnets = []
                vsphere_pool_ids = []
                openstack_subnet_id_to_allocation_pools = {}

                for net_subnet in info["attributes"]["configs"]["subnets"]:
                    allocable = net_subnet.get("allocable", True)
                    if allocable_only and not allocable:
                        continue
                    pool = net_subnet.get("allocation_pools")
                    cidr = net_subnet.get("cidr")
                    gateway = net_subnet.get("gateway")
                    hypervisors = []
                    if matches_filters(site, "vsphere"):
                        hypervisor_d = {
                            "type": "vsphere",
                            "vxlan": None,
                            "cidr": cidr,
                            "gateway": gateway,
                            "pool": self.__render_pool(pool.get("vsphere")),
                        }
                        if allocation_pools_details and allocable:
                            vsphere_id = net_subnet.get("vsphere_id")
                            if vsphere_id is not None and matches_filters(site, "vsphere"):
                                # vsphere_id contains pool platform id
                                vsphere_pool_ids.append(vsphere_id)
                                hypervisor_d["ext_id"] = vsphere_id
                        hypervisors.append(hypervisor_d)
                    if matches_filters(site, "openstack"):
                        ops_allocation_pools = pool.get("openstack")
                        hypervisor_d = {
                            "type": "openstack",
                            "vxlan": None,
                            "cidr": cidr,
                            "gateway": gateway,
                            "pool": self.__render_pool(ops_allocation_pools),
                        }
                        if allocation_pools_details and allocable:
                            openstack_id = net_subnet.get("openstack_id")
                            if openstack_id is not None and matches_filters(site, "openstack"):
                                subnet_res = self.controller.get_simple_resource(
                                    oid=openstack_id,
                                    entity_class=OpenstackSubnet
                                )
                                openstack_subnet_id = subnet_res.ext_id
                                openstack_subnet_id_to_allocation_pools[openstack_subnet_id] = ops_allocation_pools
                                hypervisor_d["ext_id"] = openstack_subnet_id
                        hypervisors.append(hypervisor_d)

                    subnet = {
                        "cidr": cidr,
                        "allocable": allocable,
                        "hypervisor": hypervisors,
                    }
                    subnets.append(subnet)
                info["attributes"]["configs"]["subnets"] = subnets
                if allocation_pools_details:
                    available_ips_openstack = net.get_openstack_number_of_available_ip_addresses(
                        openstack_subnet_id_to_allocation_pools
                    )
                    available_ips_vsphere = net.get_vsphere_number_of_available_ip_addresses(
                        vsphere_pool_ids
                    )

                    for subnet in subnets:
                        allocable = subnet.get("allocable", True)
                        hypervisors = subnet.get("hypervisor")
                        if not allocable:
                            continue
                        for hypervisor_d in hypervisors:
                            hypervisor_type = hypervisor_d.get("type")
                            ext_id = hypervisor_d.pop("ext_id", None)
                            available_ips = None
                            if ext_id is not None:
                                if hypervisor_type == "vsphere":
                                    available_ips = available_ips_vsphere.get(ext_id)
                                elif hypervisor_type == "openstack":
                                    available_ips = available_ips_openstack.get(ext_id)
                            hypervisor_d["available_ips"] = available_ips

                res.append(info)

        return res

    def get_subnets_ip_availability(self,  filters: Optional[List[SubnetFilter]] = None):
        """
        Returns available IPs per site and per VPC for both vsphere and openstack.
        filters: list of dicts with keys 'site_name' and 'orchestrator_type'
        """
        result = {"available_ips": {}}

        subnets_info = self.get_subnets(filters=filters, allocable_only=True, allocation_pools_details=True)

        for subnet_info in subnets_info:
            site_name = subnet_info["availabilty_zone"]["name"]
            if site_name not in result["available_ips"]:
                result["available_ips"][site_name] = {}
            subnets = subnet_info["attributes"]["configs"]["subnets"]
            for subnet in subnets:
                for hyp_subnet in subnet.get("hypervisor"):
                    available_ips = hyp_subnet.get("available_ips")
                    orchestrator_type = hyp_subnet.get("type")
                    result["available_ips"][site_name][orchestrator_type] = available_ips
        return result

    def get_subnet_ip_availability(
            self,
            site_name: str,
            orchestrator_type: Literal["vsphere", "openstack"]
    ):
        """
        Get subnet ip avalilability
        """
        filters = [{"site_name": site_name, "orchestrator_type": orchestrator_type}]
        result = self.get_subnets_ip_availability(filters)
        return {"available_ips": result.get("available_ips", {}).get(site_name, {}).get("orchestrator_type")}

    def get_proxies(self, site_id):
        """Get all proxies from vpc instance

        :param site_id: local site id
        :return: dict with proxies info
        """
        res = {"zabbix": None, "http": "", "socks": ""}

        if self.is_shared() is True:
            # get vpc zone network
            vpc_nets, _ = self.get_linked_resources(
                link_type=f"relation.{site_id}",
                objdef=SiteNetwork.objdef,
                authorize=False,
                run_customize=False,
            )
            vpc_net: SiteNetwork = vpc_nets[0]

            # get proxy and zabbix proxy
            proxy, set_proxy = vpc_net.get_proxy()
            zbx_proxy_ip, zbx_proxy_name = vpc_net.get_zabbix_proxy()
            res["http"] = (proxy, set_proxy)
            res["zabbix"] = (zbx_proxy_ip, zbx_proxy_name)

        elif self.is_private() is True:
            bastion_host = self.get_parent().get_bastion_host()
            if bastion_host is not None:
                res["http"] = ("", "")
                res["zabbix"] = (
                    bastion_host.get_ip_address(),
                    bastion_host.get_zabbix_proxy_name(),
                )
                # res['socks'] = 'socks5://admin:admin3proxy@%s:1080' % (bastion_host.get_ip_address())

        self.logger.debug("Get all proxies for vpc %s: %s", self.oid, res)
        return res

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info["cidr"] = self.get_cidr()
        info["type"] = self.get_type()
        #info["networks"] = self.get_subnets()
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        info["cidr"] = self.get_cidr()
        info["type"] = self.get_type()
        info["networks"] = self.get_subnets()
        return info

    @staticmethod
    def add_allocation_pools_details(controller, resource):
        vpc = controller.get_entity_v2(ModelResource, resource['id'], entity_class=Vpc)
        resource["networks"] = vpc.get_subnets(allocation_pools_details=True)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param kvargs.controller: resource controller instance
        :param kvargs.container: container instance
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.compute_zone: compute zone id
        :param kvargs.cidr: vpc cidr. Ex. 10.102.189.0/25
        :return: (:py:class:`dict`)
        :raise ApiManagerError:
        """
        # get compute zone
        # compute_zone_id = kvargs.get("parent")
        # compute_zone = container.get_resource(compute_zone_id)
        # check quotas are not exceed
        # new_quotas = {
        #     'compute.networks': 1,
        # }
        # compute_zone.check_quotas(new_quotas)

        # set attributes
        attrib = {"configs": {"cidr": kvargs.get("cidr"), "type": kvargs.get("type")}}
        kvargs["attribute"] = attrib

        # networks = kvargs.get('networks')
        #
        # # check networks
        # params = {'networks': []}
        # for network in networks:
        #     res = container.get_resource(network)
        #     if res.objdef not in [SiteNetwork.objdef, PrivateNetwork.objdef]:
        #         raise ApiManagerError('Network %s is not correct' % network)
        #     params['networks'].append(res.oid)
        #
        # params['attribute'] = {'multi_avz': kvargs.pop('multi_avz')}

        # kvargs.update(params)
        kvargs["orchestrator_tag"] = kvargs.get("orchestrator_tag", "default")
        # kvargs["orchestrator_select_types"] = kvargs.get("orchestrator_select_types", None)

        # # create task workflow
        # g_steps = []
        # for network in params['networks']:
        #     substep = {
        #         'task': Vpc.task_path + 'task_vpc_assign_network',
        #         'args': [network]
        #     }
        #     g_steps.append(substep)
        # kvargs['steps'] = ComputeProviderResource.group_create_step(g_steps)

        steps = [
            Vpc.task_path + "create_resource_pre_step",
            # Vpc.task_path + 'folder_create_physical_step',
            Vpc.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # check related objects
        sgs, _ = self.get_linked_resources(link_type="sg")
        if len(sgs) > 0:
            raise ApiManagerError("Vpc has security groups associated")

        # get networks
        networks = self.get_networks()
        if len(networks) > 0:
            raise ApiManagerError(f"vpc {self.oid} has active networks and can not be deleted")

        steps = [
            Vpc.task_path + "expunge_resource_pre_step",
            Vpc.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def get_network_by_site(self, site_id):
        """Get network by parent site

        :param site_id: site id
        :return: network
        """
        return self.get_active_availability_zone_child(site_id)

    @trace(op="view")
    def get_networks(self, *args, **kvargs):
        """Get vpc networks

        :return: network list
        :raise ApiManagerError:
        """
        objdefs = [SiteNetwork.objdef, PrivateNetwork.objdef]
        networks = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], objdefs=objdefs, run_customize=False
        )
        return networks

    @trace(op="update")
    def get_private_network_by_cidr(self, cidr):
        """Get vpc private network by cidr

        :param cidr: private network cidr
        :return: network instance
        :raise ApiManagerError:
        """
        objdefs = [PrivateNetwork.objdef]
        networks = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], objdefs=objdefs, run_customize=False
        )
        networks = networks.get(self.oid, [])
        for network in networks:
            if network.get_cidr() == cidr:
                return network
        return None

    @trace(op="update")
    def get_site_network_by_cidr(self, cidr):
        """Get vpc site network by cidr

        :param cidr: private network cidr
        :return: network instance
        :raise ApiManagerError:
        """
        objdefs = [SiteNetwork.objdef]
        networks = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], objdefs=objdefs, run_customize=False
        )
        networks = networks.get(self.oid, [])
        for network in networks:
            self.logger.warn(network.get_cidr())
            self.logger.warn(cidr)
            if network.get_cidr() == cidr:
                return network
        return None

    def has_network(self, network, *args, **kvargs):
        """Check vpc has network connected

        :param network: network id
        :return: True if vpc has network assigned
        :raise ApiManagerError:
        """
        objdefs = [Vpc.objdef]
        networks = self.controller.get_indirected_linked_resources_internal(
            resources=[network], objdefs=objdefs, run_customize=False
        )
        vpcs = networks.get(network, [])
        if len(vpcs) > 0:
            for vpc in vpcs:
                if vpc.oid == self.oid:
                    return True
        return False

    @trace(op="update")
    def add_network(self, *args, **kvargs):
        """Add network to vpc or assign a shared network to vpc

        :param site: list of site network id [optional]
        :param site.x.network: site network id
        :param private: list of private network [optional]
        :param private.x.cidr: private network cidr
        :param private.x.dns_search: network dns zone
        :param private.x.zabbix_proxy: zabbix proxy
        :param private.x.dns_nameservers: dns nameservers list. Ex. ["8.8.8.8", "8.8.8.4"]
        :param private.x.availability_zone: private network site
        :param private.x.orchestrator_tag: orchestartor tag [optional]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        site = kvargs.pop("site", None)
        private = kvargs.pop("private", None)
        if site is not None and private is not None:
            raise ApiManagerError("site and private are exclusive parameters. Only one can be used")

        steps = []
        if site is not None:
            for item in site:
                network = item.get("network")
                network_id = self.container.get_simple_resource(network, entity_class=SiteNetwork).oid
                if self.has_network(network_id) is False:
                    steps.append(
                        {
                            "step": self.task_path + "vpc_assign_network_step",
                            "args": [network_id],
                        }
                    )

        elif private is not None:
            for network in private:
                cidr = network.get("cidr")

                # check network cidr is in vpc cidr
                vpc_network_cidr = ip_network(self.get_cidr())
                network_cidr = ip_network(cidr)
                net_prefixlen = int(vpc_network_cidr.prefixlen) + 2
                if network_cidr.subnet_of(vpc_network_cidr) is False:
                    raise ApiManagerError(f"network cidr {cidr} is not a subnet of vpc cidr {self.get_cidr()}")
                if int(network_cidr.prefixlen) != net_prefixlen:
                    raise ApiManagerError(f"network cidr prefixlen must be vpc cidr prefixlen -2: {net_prefixlen}")
                if network_cidr.is_private is False:
                    raise ApiManagerError(f"network cidr {cidr} is not private")


                kvargs["vpc_cidr"] = self.get_cidr()

                if self.get_private_network_by_cidr(cidr) is None:
                    steps.append(
                        {
                            "step": self.task_path + "vpc_add_network_step",
                            "args": [network],
                        }
                    )

        res = self.action("add_network", steps, log="Add network to vpc", check=None, **kvargs)
        return res

    @trace(op="update")
    def del_network(self, *args, **kvargs):
        """Delete network from vpc or deassign a shared network from vpc

        :param site: list of site network id [optional]
        :param site.x.network: site network id
        :param private: list of private network [optional]
        :param private.x.cidr: private network cidr
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        site = kvargs.get("site", None)
        private = kvargs.get("private", None)
        if site is not None and private is not None:
            raise ApiManagerError("site and private are exclusive parameters. Only one can be used")

        steps = []
        if site is not None:
            for item in site:
                network = item.get("network")
                network_id = self.container.get_simple_resource(network, entity_class=SiteNetwork).oid
                if self.has_network(network_id) is True:
                    steps.append(
                        {
                            "step": self.task_path + "vpc_deassign_network_step",
                            "args": [network_id],
                        }
                    )
        elif private is not None:
            for data in private:
                cidr = data.get("cidr")
                network = self.get_private_network_by_cidr(cidr)
                if network is None:
                    raise ApiManagerError(f"vpc {self.oid} does not have a network with cidr {cidr}")
                steps.append(
                    {
                        "step": self.task_path + "vpc_del_network_step",
                        "args": [network.oid],
                    }
                )

        res = self.action("del_network", steps, log="Delete network from vpc", check=None, **kvargs)
        return res

    def get_quotas(self):
        quotas = {
            "compute.networks": 1
        }
        from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
        sgs, total = self.controller.get_resources(
            parent_id=self.oid,
            authorize=False,
            size=-1,
            run_customize=False,
            type=SecurityGroup.objdef,
        )
        quotas["compute.security_groups"] = total
        return quotas


class SiteNetwork(SiteChildResource):
    """Site network. Define external and shared network."""

    objdef = "Provider.Region.Site.Network"
    objuri = "%s/site_networks/%s"
    objname = "site_network"
    objdesc = "site network"
    task_path = "beehive_resource.plugins.provider.task_v2.vpc.VpcTask."

    def __init__(self, *args, **kvargs):
        SiteChildResource.__init__(self, *args, **kvargs)
    
    def is_internet(self)->bool:
        """
        Returns:
            bool: True if is internet
        """
        return  subnet_is_internet(self.get_cidr())
    
    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info["availabilty_zone"] = self.get_parent().small_info()
        return info

    def get_vsphere_number_of_available_ip_addresses(
        self,
        vsphere_pool_ids: [],
        orchestrator_tag: str="default",
        **kwargs
    ) -> {}:
        """
        Return the number of available IP addresses for multiple vSphere IP pools.

        :param vsphere_pool_ids: List of vSphere IP pool IDs to check.
                E.g.
                    [
                        "pool-12345",
                        "pool-67890"
                    ]
        :param orchestrator_tag: Orchestrator tag to filter resources (default: "default").
        :param kwargs: Additional parameters for customization.

        :return: Dict mapping vSphere pool IDs to the number of free/available IP addresses.
                E.g.
                    {
                        "pool-12345": 45,
                        "pool-67890": 128
                    }
        :raises VsphereError: If pool data cannot be retrieved or processed.
        """
        res = {}
        if len(vsphere_pool_ids) == 0:
            return res
        site: 'Site' = self.get_parent()
        vsphere_container: 'VsphereContainer'
        _, vsphere_container = site.get_orchestrator_and_container("vsphere", orchestrator_tag)
        for vsphere_pool_id in vsphere_pool_ids:
            try:
                vsphere_pool = vsphere_container.conn.network.nsx.ippool.get(vsphere_pool_id)
                free_address_count = vsphere_pool.get("freeAddressCount")
                if free_address_count is not None:
                    res[vsphere_pool_id] =  int(free_address_count)
            except:
                self.logger.warning(f"Unable to get number of ip available on vsphere pool {vsphere_pool_id}")
        return res

    def get_openstack_number_of_available_ip_addresses(
        self,
        openstack_subnet_id_to_allocation_pools: {},
        orchestrator_tag: str="default",
        **kwargs
    ) -> {}:
        """
        Return the number of available IP addresses for multiple OpenStack subnets.

        :param openstack_subnet_id_to_allocation_pools: Dict mapping each subnet ID to its allocation pools.
                E.g.
                    {
                        "cb5000b8-cf67-4c63-abad-363b002531ac": [
                            {"start": "10.138.129.2", "end": "10.138.129.254"}
                        ],
                        "de2001a1-1a52-4c73-a7f9-0a5a9c2e823a": [
                            {"start": "192.168.1.10", "end": "192.168.1.50"},
                            {"start": "192.168.1.100", "end": "192.168.1.150"}
                        ]
                    }
        :param orchestrator_tag: Orchestrator tag to filter resources (default: "default").
        :param kwargs: Additional parameters for customization.

        :return: Dict mapping subnet IDs to the number of free/available IP addresses.
                E.g.
                    {
                        "cb5000b8-cf67-4c63-abad-363b002531ac": 236,
                        "de2001a1-1a52-4c73-a7f9-0a5a9c2e823a": 82
                    }
        :raises OpenstackError: If subnet data cannot be retrieved or processed.
        """
        res = {}
        if len(openstack_subnet_id_to_allocation_pools) == 0:
            return res
        site: 'Site' = self.get_parent()
        openstack_container: 'OpenstackContainer'
        _, openstack_container = site.get_orchestrator_and_container("openstack", orchestrator_tag)
        ops_subnets_d = openstack_container.conn.network.subnet.get_subnets_ip_usage_detail(
            openstack_subnet_id_to_allocation_pools
        )
        return  {o:ops_subnets_d[o]['pool_available'] for o in ops_subnets_d}

    def get_allocable_subnet(self, cidr=None, orchestrator_type=None):
        """Get network allocable subnet

        :param cidr: cidr to check if exists and is allocable [optional]
        :param orchestrator_type: orchestrator type like openstack, vsphere [optional]
        """
        subnets = self.get_attribs(key="configs.subnets")
        allocable_subnet = None

        if cidr is not None:
            for item in subnets:
                self.logger.debug(
                    "Get network %s allocable subnet - cidr: %s - subnet cidr: %s", self.oid, cidr, item.get("cidr")
                )
                if item.get("cidr") == cidr:
                    if item.get("allocable", True):
                        allocable_subnet = item
                        break
                    self.logger.debug(
                        "Get network %s allocable subnet - subnet cidr: %s not allocable",
                        self.oid, item.get("cidr")
                    )
            if allocable_subnet is None:
                raise ApiManagerError(f"No available subnet found in network {self.oid} for cidr {cidr}")

            self.logger.debug(
                "Get network %s allocable subnet for cidr %s: %s",
                self.oid,
                cidr,
                allocable_subnet
            )
        else:
            for item in subnets:
                if item.get("allocable", True):
                    allocable_subnet = item
            if allocable_subnet is None:
                raise ApiManagerError(f"No available subnet found in network {self.oid}")
            self.logger.debug(
                "Get network %s allocable subnet: %s",
                self.oid,
                allocable_subnet
            )

        return allocable_subnet

    def get_non_allocable_subnets(self):
        """Get network not allocable subnets"""
        subnets = self.get_attribs(key="configs.subnets")
        not_allocable_subnets = []
        for item in subnets:
            if item.get("allocable", False) is False:
                not_allocable_subnets.append(item)

        self.logger.debug("Get network %s not allocable subnets: %s", self.uuid, not_allocable_subnets)
        return not_allocable_subnets

    def get_subnets(self):
        """Get network subnets"""
        subnets = self.get_attribs(key="configs.subnets")
        self.logger.debug("Get network %s subnets: %s", self.uuid, truncate(subnets))
        return subnets

    def add_subnet_in_configs(self, subnet):
        """Add subnet in entity attribs configs

        :param subnet: subnet to add
        :return: True
        :raise ApiManagerError:
        """
        subnets = self.get_attribs(key="configs.subnets")
        subnets_idx = {s.get("cidr") for s in subnets}
        cidr = subnet.get("cidr")
        if cidr in subnets_idx:
            raise ApiManagerError(f"Subnet {cidr} already exist")
        subnets.append(subnet)
        self.set_configs(key="configs.subnets", value=subnets)
        self.logger.debug("Add subnet %s in config", subnet)
        return True

    def update_subnet_in_configs(self, subnet):
        """Add or update subnet in entity attribs configs

        :param subnet: subnet to update
        :return: True
        :raise ApiManagerError:
        """
        subnets = self.get_attribs(key="configs.subnets")
        subnets_idx = {s.get("cidr"): s for s in subnets}
        cidr = subnet.get("cidr")
        if cidr not in list(subnets_idx.keys()):
            subnets.append(subnet)
        else:
            subnets_idx[cidr] = subnet
            subnets = list(subnets_idx.values())
        self.set_configs(key="configs.subnets", value=subnets)
        self.logger.debug("Add/Update subnet %s in config", subnet)
        return True

    def delete_subnet_in_configs(self, subnet):
        """Delete subnet in entity attribs configs

        :param subnet: subnet to update
        :return: True
        :raise ApiManagerError:
        """
        subnets = self.get_attribs(key="configs.subnets")
        subnets_idx = {s.get("cidr"): s for s in subnets}
        cidr = subnet.get("cidr")
        subnets_idx.pop(cidr)
        subnets = list(subnets_idx.values())
        self.set_configs(key="configs.subnets", value=subnets)
        self.logger.debug("Delete subnet %s in config", subnet)
        return True

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.site: parent site
        :param kvargs.external: True if network is external
        :param kvargs.vlan: vlan id
        :param kvargs.proxy: http proxy
        :param kvargs.zabbix_proxy: zabbix proxy
        :param kvargs.dns_search: network dns zone
        :return:
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag", "default")
        site_id = kvargs.get("parent")
        external = kvargs.get("external")

        # get site
        site = container.get_resource(site_id)

        # select remote orchestrators
        orchestrator_idx = site.get_orchestrators_by_tag(orchestrator_tag)

        network_type = "vlan"
        if external is True:
            network_type = "flat"

        # set params
        params = {
            "site_id": site.oid,
            # 'orchestrators': orchestrator_idx,
            "network_type": network_type,
            "attribute": {
                "configs": {
                    "external": kvargs.get("external"),
                    "vlan": kvargs.get("vlan", None),
                    "proxy": kvargs.get("proxy", ""),
                    "zabbix_proxy": kvargs.get("zabbix_proxy", ""),
                    "dns_search": kvargs.get("dns_search", None),
                    "subnets": kvargs.get("subnets", []),
                }
            },
        }

        kvargs.update(params)

        # create task workflow
        steps = []
        for item in orchestrator_idx.values():
            steps.append(
                {
                    "step": SiteNetwork.task_path + "create_site_network_step",
                    "args": [item],
                }
            )

        kvargs["steps"] = AvailabilityZoneChildResource.group_create_step(steps)
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method. Extend this function to manipulate and
        validate delete input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # check if network has active subnet
        if len(self.get_subnets()) > 0:
            raise ApiManagerError(f"Network {self.uuid} has active subnets. it can not be deleted")

        # select remote orchestrators
        orchestrator_idx = self.get_orchestrators()

        # create task workflow
        kvargs["steps"] = self.group_remove_step(orchestrator_idx)

        return kvargs

    def get_cidr(self):
        """Get network cidr"""
        cidr = None
        subnets = self.get_attribs(key="configs.subnets")
        for subnet in subnets:
            if subnet.get("allocable", False) is True:
                cidr = subnet.get("cidr", None)
        self.logger.debug("Get network %s cidr: %s", self.uuid, cidr)
        return cidr

    def get_proxy(self):
        """Get network proxy"""
        proxy = self.get_attribs(key="configs.proxy")
        if proxy is None or proxy == "":
            set_proxy = False
            proxy = ""
        else:
            set_proxy = True
        return proxy, set_proxy

    def get_zabbix_proxy(self):
        """Get network zabbix proxy

        :return: ip address and hostname of zabbix proxy
        """
        zbx_proxy = self.get_attribs(key="configs.zabbix_proxy")
        if zbx_proxy is None:
            # raise ApiManagerError(
            #     "No zabbix proxy available in attributes of network %s" % self.uuid,
            #     code=404,
            # )
            self.logger.info("No zabbix proxy available in attributes of network %s", self.uuid)
            return "", ""
        l = zbx_proxy.split(",", maxsplit=1)
        zbx_proxy_ip = l[0].strip()
        zbx_proxy_name = None
        if len(l) == 2:
            zbx_proxy_name = l[1].strip()
        self.logger.debug("Get network %s zabbix proxy: %s, %s", self.uuid, zbx_proxy_ip, zbx_proxy_name)
        return zbx_proxy_ip, zbx_proxy_name

    def get_dns_search(self):
        """Get network dns_search"""
        dns_search = self.get_attribs(key="configs.dns_search")
        self.logger.debug("Get network %s dns search: %s", self.uuid, dns_search)
        return dns_search

    def get_dns_nameservers(self):
        """Get network dns_nameservers"""
        dns_nameservers = self.get_attribs(key="configs.dns_nameservers")
        self.logger.debug("Get network %s dns nameservers: %s", self.uuid, dns_nameservers)
        return dns_nameservers

    def get_vsphere_network(self, dvs=None):
        """Get vsphere NsxLogicalSwitch

        :param dvs: parent distributed virtual switch oid [optional]
        """
        res, tot = self.get_linked_resources(link_type_filter="relation", objdef=VsphereDvpg.objdef)
        if tot > 0:
            if dvs is not None:
                res = [r for r in res if r.get_parent_dvs().oid == dvs]
            return res[0]
        return None

    def get_openstack_network(self):
        """Get openstack network"""
        res, tot = self.get_linked_resources(link_type_filter="relation", objdef=OpenstackNetwork.objdef)
        if tot > 0:
            return res[0]
        return None

    def add_subnets(self, params):
        """Add subnets

        :param params.n.enable_dhcp: enable dhcp on subnet
        :param params.n.dns_nameservers: dns list
        :param params.n.routes: list of routes
        :param params.n.routes.m.destination: route destination
        :param params.n.routes.m.nexthop: route nexthop
        :param params.n.allocable: tell if subnet is allocable
        :param params.n.allocation_pools: allocation pools
        :param params.n.allocation_pools.vsphere: allocation pool for vsphere
        :param params.n.allocation_pools.vsphere.start: allocation pool start ip
        :param params.n.allocation_pools.vsphere.end: allocation pool end ip
        :param params.n.allocation_pools.openstack: allocation pool for openstack
        :param params.n.allocation_pools.openstack.start: allocation pool start ip
        :param params.n.allocation_pools.openstack.end: allocation pool end ip
        :param params.n.router: subnet internal openstack router ip address
        :param params.n.cidr: subnet cidr
        :param params.n.gateway: subnet gateway
        :param orchestrator_tag: orchestrator tag. Use to select a subset of orchestrators where security
            group must be created.
        :return: {'jobid':<job id>}, 202
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # select remote orchestrators
        orchestrator_tag = params.pop("orchestrator_tag", "default")
        orchestrator_idx = self.get_orchestrators_by_tag(orchestrator_tag)

        # check subnets
        orig_subnets = self.get_subnets()
        subnet_cidrs = [s["cidr"] for s in orig_subnets]
        new_subnets = []
        for s in params.pop("subnets", []):
            if s["cidr"] not in subnet_cidrs:
                new_subnets.append(s)

        if len(new_subnets) == 0:
            raise ApiManagerError(f"There are no subnet to add to network {self.uuid}")

        # create task workflow
        # steps = [SiteNetwork.task_path + 'update_resource_pre_step']
        steps = []
        for subnet in new_subnets:
            steps.append(
                {
                    "step": SiteNetwork.task_path + "site_network_add_subnet_step",
                    "args": [list(orchestrator_idx.values()), subnet],
                }
            )
        # steps.append(SiteNetwork.task_path + 'update_resource_post_step')
        res = Resource.action(
            self,
            "add_subnet",
            steps,
            log=f"Add subnets to site network {self.uuid}",
            **params,
        )
        return res

    def delete_subnets(self, params):
        """Delete subnets

        :param params.n.cidr: subnet cidr
        :param orchestrator_tag: orchestrator tag. Use to select a subset of orchestrators where security
            group must be created.
        :return: {'jobid':<job id>}, 202
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # select remote orchestrators
        orchestrator_tag = params.pop("orchestrator_tag", "default")
        orchestrator_idx = self.get_orchestrators_by_tag(orchestrator_tag)

        # check subnets
        orig_subnets = self.get_subnets()
        subnet_cidrs = {s["cidr"]: s for s in orig_subnets}
        del_subnets = []
        for s in params.pop("subnets", []):
            subnet = subnet_cidrs.get(s["cidr"], None)
            if subnet is not None:
                del_subnets.append(subnet)

        if len(del_subnets) == 0:
            raise ApiManagerError(f"There are no subnet to delete from the network {self.uuid}")

        # create task workflow
        # steps = [SiteNetwork.task_path + 'update_resource_pre_step']
        steps = []
        for subnet in del_subnets:
            steps.append(
                {
                    "step": SiteNetwork.task_path + "site_network_del_subnet_step",
                    "args": [list(orchestrator_idx.values()), subnet],
                }
            )

        # steps.append(SiteNetwork.task_path + 'update_resource_post_step')

        res = Resource.action(
            self,
            "del_subnet",
            steps,
            log=f"del subnets from site network {self.uuid}",
            **params,
        )
        return res

    @staticmethod
    def enrich_site_network_subnets_with_available_ips(controller, site_network):
        # get the full SiteNetwork entity from controller
        site_net_entity = controller.get_entity_v2(ModelResource, site_network["id"], entity_class=SiteNetwork)

        subnets = site_network.get("attributes", {}).get("configs", {}).get("subnets", [])

        vsphere_pool_ids = []
        openstack_subnet_id_to_allocation_pools = {}

        for s in subnets:
            if not s.get("allocable"):
                continue

            vs_id = s.get("vsphere_id")
            if vs_id and vs_id != "None":
                vsphere_pool_ids.append(vs_id)

            ops_id = s.get("openstack_id")
            if ops_id and ops_id != "None":
                ap = s.get("allocation_pools", {})
                if isinstance(ap, dict):
                    ap = ap.get("openstack", [])
                openstack_subnet_id_to_allocation_pools[ops_id] = ap

        available_ips_openstack = {}
        if openstack_subnet_id_to_allocation_pools:
            available_ips_openstack = site_net_entity.get_openstack_number_of_available_ip_addresses(
                openstack_subnet_id_to_allocation_pools
            )

        available_ips_vsphere = {}
        if vsphere_pool_ids:
            available_ips_vsphere = site_net_entity.get_vsphere_number_of_available_ip_addresses(vsphere_pool_ids)

        for s in subnets:
            ops_id = s.get("openstack_id")
            vs_id = s.get("vsphere_id")

            if ops_id and ops_id != "None":
                val = available_ips_openstack.get(ops_id)
            elif vs_id and vs_id != "None":
                val = available_ips_vsphere.get(vs_id)
            else:
                val = "None"

            s["available_ips"] = val



    @staticmethod
    def enrich_site_networks_subnets_with_available_ips(controller, site_networks_info):
        """
        For each SiteNetwork:
          - collect allocable subnets
          - query available IPs (openstack, vsphere)
          - enrich subnets with 'available_ips'
        """
        site_networks = site_networks_info['site_networks']
        for site_network in site_networks:
            SiteNetwork.enrich_site_network_subnets_with_available_ips(controller, site_network)
        return site_networks_info


class PrivateNetwork(AvailabilityZoneChildResource):
    """Availability zone private network"""

    objdef = "Provider.Region.Site.AvailabilityZone.PrivateNetwork"
    objuri = "%s/private_networks/%s"
    objname = "private_network"
    objdesc = "Provider Availability Zone Private Network"
    task_path = "beehive_resource.plugins.provider.task_v2.vpc.VpcTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info["availabilty_zone"] = self.get_site().small_info()
        return info

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.vpc_cidr: vpc base cidr
        :param kvargs.cidr: private network cidr
        :param kvargs.dns_search: network dns zone
        :param kvargs.zabbix_proxy: zabbix proxy
        :param kvargs.dns_nameservers: dns nameservers list. Ex. ["8.8.8.8", "8.8.8.4"]
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag")
        # orchestrator_select_types = kvargs.pop("orchestrator_select_types")
        network_type = "vxlan"
        base_cidr = kvargs.get("cidr", "")
        vpc_cidr = kvargs.get("vpc_cidr", "")
        controller.logger.warn(kvargs)

        # get availability_zone
        from beehive_resource.plugins.provider.entity.site import Site
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        availability_zone: AvailabilityZone = container.get_simple_resource(kvargs.get("parent"))
        site = availability_zone.get_parent()

        # select remote orchestrators
        # orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag, select_types=orchestrator_select_types)
        orchestrator_idx = availability_zone.get_hypervisors_by_tag(orchestrator_tag)

        # set params
        params = {
            "site_id": site.oid,
            "network_type": network_type,
            "attribute": {
                "configs": {
                    "cidr": base_cidr,
                    "zabbix_proxy": kvargs.get("zabbix_proxy", ""),
                    "dns_search": kvargs.get("dns_search", None),
                    "dns_nameservers": kvargs.get("dns_nameservers", []),
                }
            },
        }
        kvargs.update(params)

        # get sub cidr
        vpc_network_cidr = ip_network(vpc_cidr)
        base_network_cidr = ip_network(base_cidr)
        sub_network_prefixlen = int(base_network_cidr.prefixlen) + 1
        # - all the subnet that could be assigned
        available_subnets = list(vpc_network_cidr.subnets(new_prefix=sub_network_prefixlen))
        # - network subnet that could be assigned
        available_network_subnets = list(base_network_cidr.subnets(new_prefix=sub_network_prefixlen))

        # create task workflow
        steps = []
        index = 0
        for orchestrator in orchestrator_idx.values():
            if index >= len(available_network_subnets):
                orchestrator_id = orchestrator["id"]
                raise ApiManagerError(
                    f"no available sub cidr found for orchestrator {orchestrator_id} in base cidr {base_cidr}"
                )

            # main cidr
            subnet = available_network_subnets[index]
            hosts = list(subnet.hosts())
            cidr = str(subnet)
            gateway = str(hosts[0])
            # exclude from allocation pool .2, .3, .4, .5, .252, .253, .254
            pool = [{"start": str(hosts[5]), "end": str(hosts[-3])}]

            # other cidrs
            other_cidrs = []
            if orchestrator["type"] == "openstack":
                other_cidrs = [str(s) for s in available_subnets]
                other_cidrs.remove(cidr)

            steps.append(
                {
                    "step": PrivateNetwork.task_path + "create_private_network_step",
                    "args": [orchestrator, cidr, other_cidrs, gateway, pool],
                }
            )
            index += 1

        kvargs["steps"] = AvailabilityZoneChildResource.group_create_step(steps)
        kvargs["sync"] = True
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method. Extend this function to manipulate and
        validate delete input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # select remote orchestrators
        orchestrator_idx = self.get_orchestrators()

        run_steps = [PrivateNetwork.task_path + "expunge_resource_pre_step"]
        for item in orchestrator_idx.values():
            substep = {
                "step": PrivateNetwork.task_path + "delete_private_network_step",
                "args": [item],
            }
            run_steps.append(substep)
            substep = {
                "step": PrivateNetwork.task_path + "remove_physical_resource_step",
                "args": [str(item["id"]), item["type"]],
            }
            run_steps.append(substep)
        run_steps.append(PrivateNetwork.task_path + "expunge_resource_post_step")
        kvargs["steps"] = run_steps
        kvargs["sync"] = True

        return kvargs

    def get_cidr(self):
        """Get network cidr"""
        cidr = self.get_attribs(key="configs.cidr")
        self.logger.debug("Get network %s cidr: %s", self.uuid, cidr)
        return cidr

    def get_zabbix_proxy(self):
        """Get network zabbix proxy

        :return: ip address and hostname of zabbix proxy
        """
        zbx_proxy = self.get_attribs(key="configs.zabbix_proxy")
        if zbx_proxy is None:
            raise ApiManagerError(
                f"No zabbix proxy available in attributes of network {self.uuid}",
                code=404,
            )
        l = zbx_proxy.split(",", maxsplit=1)
        zbx_proxy_ip = l[0].strip()
        zbx_proxy_name = None
        if len(l) == 2:
            zbx_proxy_name = l[1].strip()
        self.logger.debug("Get network %s zabbix proxy: %s, %s", self.uuid, zbx_proxy_ip, zbx_proxy_name)
        return zbx_proxy_ip, zbx_proxy_name

    def get_dns_search(self):
        """Get network dns_search"""
        dns_search = self.get_attribs(key="configs.dns_search")
        self.logger.debug("Get network %s dns search: %s", self.uuid, dns_search)
        return dns_search

    def get_dns_nameservers(self):
        """Get network dns_nameservers"""
        dns_nameservers = self.get_attribs(key="configs.dns_nameservers")
        self.logger.debug("Get network %s dns nameservers: %s", self.uuid, dns_nameservers)
        return dns_nameservers

    def get_allocable_subnet(self, cidr, orchestrator_type=None):
        """Get network allocable subnet

        :param cidr: cidr to check if exists and is allocable
        :param orchestrator_type: orchestrator type like openstack, vsphere
        """
        allocable_subnet = {
            "dns_nameservers": self.get_dns_nameservers(),
            "gateway": {},
            "vsphere_id": None,
            "openstack_id": None,
            "cidr": None,
        }

        physical_nets, _ = self.get_linked_resources(link_type_filter="relation")
        for physical_net in physical_nets:
            if isinstance(physical_net, OpenstackNetwork):
                allocable_subnet["openstack_id"] = physical_net.get_attribs(key="subnet")
                if orchestrator_type is not None and orchestrator_type == "openstack":
                    allocable_subnet["gateway"] = physical_net.get_gateway()
                    allocable_subnet["cidr"] = physical_net.get_private_subnet()
            elif isinstance(physical_net, NsxLogicalSwitch):
                allocable_subnet["vsphere_id"] = physical_net.get_attribs(key="subnet")
                if orchestrator_type is not None and orchestrator_type == "vsphere":
                    allocable_subnet["gateway"] = physical_net.get_gateway()
                    allocable_subnet["cidr"] = physical_net.get_private_subnet()

        self.logger.debug("Get network %s allocable subnet for cidr %s: %s", self.uuid, cidr, allocable_subnet)
        return allocable_subnet

    def get_vsphere_network(self):
        """Get vsphere NsxLogicalSwitch"""
        res, tot = self.get_linked_resources(link_type_filter="relation", objdef=NsxLogicalSwitch.objdef)
        if tot > 0:
            return res[0]
        return None

    def get_openstack_network(self):
        """Get openstack network"""
        res, tot = self.get_linked_resources(link_type_filter="relation", objdef=OpenstackNetwork.objdef)
        if tot > 0:
            return res[0]
        return None
