# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from ipaddress import ip_network
from beecell.types.type_string import truncate
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import SiteChildResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg


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

    def get_cidr(self):
        return self.get_attribs("configs.cidr", "")

    def get_type(self):
        return self.get_attribs("configs.type", "shared")

    def is_private(self):
        if self.get_type() == "private":
            return True
        return False

    def is_shared(self):
        if self.get_type() == "shared":
            return True
        return False

    def __render_pool(self, pool):
        if pool is not None:
            return ",".join(["%s-%s" % (p.get("start", ""), p.get("end", "")) for p in pool])
        return ""

    def get_subnets(self):
        nets, total = self.get_linked_resources(link_type_filter="relation%")
        res = []
        for net in nets:
            info = net.info()
            if isinstance(net, PrivateNetwork):
                subnet = {"cidr": net.get_cidr(), "hypervisor": [], "allocable": True}
                physical_nets, total = net.get_linked_resources(link_type_filter="relation")
                for physical_net in physical_nets:
                    if isinstance(physical_net, OpenstackNetwork):
                        hypervisor = "openstack"
                    elif isinstance(physical_net, NsxLogicalSwitch):
                        hypervisor = "vsphere"
                    subnet["hypervisor"].append(
                        {
                            "type": hypervisor,
                            "vxlan": physical_net.get_vlan(),
                            "cidr": physical_net.get_private_subnet(),
                            "gateway": physical_net.get_gateway(),
                            "pool": self.__render_pool(physical_net.get_allocation_pool()),
                        }
                    )
                info["attributes"]["configs"]["subnets"] = [subnet]
            elif isinstance(net, SiteNetwork):
                subnets = []
                for net_subnet in info["attributes"]["configs"]["subnets"]:
                    pool = net_subnet.get("allocation_pools")
                    subnet = {
                        "cidr": net_subnet.get("cidr"),
                        "allocable": net_subnet.get("allocable", True),
                        "hypervisor": [
                            {
                                "type": "openstack",
                                "vxlan": None,
                                "cidr": None,
                                "gateway": net_subnet.get("gateway"),
                                "pool": self.__render_pool(pool.get("openstack", None)),
                            },
                            {
                                "type": "vsphere",
                                "vxlan": None,
                                "cidr": None,
                                "gateway": net_subnet.get("gateway"),
                                "pool": self.__render_pool(pool.get("vsphere", None)),
                            },
                        ],
                    }
                    subnets.append(subnet)
                info["attributes"]["configs"]["subnets"] = subnets
            res.append(info)
        return res

    def get_proxies(self, site_id):
        """Get all proxies from vpc instance

        :param site_id: local site id
        :return: dict with proxies info
        """
        res = {"zabbix": None, "http": "", "socks": ""}

        if self.is_shared() is True:
            # get vpc zone network
            vpc_nets, total = self.get_linked_resources(
                link_type="relation.%s" % site_id,
                objdef=SiteNetwork.objdef,
                authorize=False,
                run_customize=False,
            )
            vpc_net = vpc_nets[0]

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

        self.logger.debug("Get all proxies for vpc %s: %s" % (self.oid, res))
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
        compute_zone_id = kvargs.get("parent")
        compute_zone = container.get_resource(compute_zone_id)

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
        sgs, total = self.get_linked_resources(link_type="sg")
        if len(sgs) > 0:
            raise ApiManagerError("Vpc has security groups associated")

        # get networks
        networks = self.get_networks()
        if len(networks) > 0:
            raise ApiManagerError("vpc %s has active networks and can not be deleted" % self.oid)

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
                    raise ApiManagerError("network cidr %s is not a subnet of vpc cidr %s" % (cidr, self.get_cidr()))
                if int(network_cidr.prefixlen) != net_prefixlen:
                    raise ApiManagerError("network cidr prefixlen must be vpc cidr prefixlen -2: %s" % net_prefixlen)
                if network_cidr.is_private is False:
                    raise ApiManagerError("network cidr %s is not private" % cidr)

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
                    raise ApiManagerError("vpc %s does not have a network with cidr %s" % (self.oid, cidr))
                steps.append(
                    {
                        "step": self.task_path + "vpc_del_network_step",
                        "args": [network.oid],
                    }
                )

        res = self.action("del_network", steps, log="Delete network from vpc", check=None, **kvargs)
        return res


class SiteNetwork(SiteChildResource):
    """Site network. Define external and shared network."""

    objdef = "Provider.Region.Site.Network"
    objuri = "%s/site_networks/%s"
    objname = "site_network"
    objdesc = "site network"
    task_path = "beehive_resource.plugins.provider.task_v2.vpc.VpcTask."

    def __init__(self, *args, **kvargs):
        SiteChildResource.__init__(self, *args, **kvargs)

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
                    "Get network %s allocable subnet - cidr: %s - subnet cidr: %s" % (self.oid, cidr, item.get("cidr"))
                )
                if item.get("cidr") == cidr:
                    if item.get("allocable", True) is True:
                        allocable_subnet = item
                        break
                    else:
                        self.logger.debug(
                            "Get network %s allocable subnet - subnet cidr: %s not allocable"
                            % (self.oid, item.get("cidr"))
                        )

            if allocable_subnet is None:
                raise ApiManagerError("No available subnet found in network %s for cidr %s" % (self.oid, cidr))

            self.logger.debug("Get network %s allocable subnet for cidr %s: %s" % (self.oid, cidr, allocable_subnet))

        else:
            for item in subnets:
                if item.get("allocable", True) is True:
                    allocable_subnet = item
            if allocable_subnet is None:
                raise ApiManagerError("No available subnet found in network %s " % self.oid)

            self.logger.debug("Get network %s allocable subnet: %s" % (self.oid, allocable_subnet))

        return allocable_subnet

    def get_non_allocable_subnets(self):
        """Get network not allocable subnets"""
        subnets = self.get_attribs(key="configs.subnets")
        not_allocable_subnets = []
        for item in subnets:
            if item.get("allocable", False) is False:
                not_allocable_subnets.append(item)

        self.logger.debug("Get network %s not allocable subnets: %s" % (self.uuid, not_allocable_subnets))
        return not_allocable_subnets

    def get_subnets(self):
        """Get network subnets"""
        subnets = self.get_attribs(key="configs.subnets")
        self.logger.debug("Get network %s subnets: %s" % (self.uuid, truncate(subnets)))
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
            raise ApiManagerError("Subnet %s already exist" % cidr)
        subnets.append(subnet)
        self.set_configs(key="configs.subnets", value=subnets)
        self.logger.debug("Add subnet %s in config" % subnet)
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
        self.logger.debug("Add/Update subnet %s in config" % subnet)
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
        self.logger.debug("Delete subnet %s in config" % subnet)
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
            raise ApiManagerError("Network %s has active subnets. it can not be deleted" % self.uuid)

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
        self.logger.debug("Get network %s cidr: %s" % (self.uuid, cidr))
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
            raise ApiManagerError(
                "No zabbix proxy available in attributes of network %s" % self.uuid,
                code=404,
            )
        l = zbx_proxy.split(",", maxsplit=1)
        zbx_proxy_ip = l[0].strip()
        zbx_proxy_name = None
        if len(l) == 2:
            zbx_proxy_name = l[1].strip()
        self.logger.debug("Get network %s zabbix proxy: %s, %s" % (self.uuid, zbx_proxy_ip, zbx_proxy_name))
        return zbx_proxy_ip, zbx_proxy_name

    def get_dns_search(self):
        """Get network dns_search"""
        dns_search = self.get_attribs(key="configs.dns_search")
        self.logger.debug("Get network %s dns search: %s" % (self.uuid, dns_search))
        return dns_search

    def get_dns_nameservers(self):
        """Get network dns_nameservers"""
        dns_nameservers = self.get_attribs(key="configs.dns_nameservers")
        self.logger.debug("Get network %s dns nameservers: %s" % (self.uuid, dns_nameservers))
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
            raise ApiManagerError("There are no subnet to add to network %s" % self.uuid)

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
            log="Add subnets to site network %s" % self.uuid,
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
            raise ApiManagerError("There are no subnet to delete from the network %s" % self.uuid)

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
            log="del subnets from site network %s" % self.uuid,
            **params,
        )
        return res


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
        network_type = "vxlan"
        base_cidr = kvargs.get("cidr", "")
        vpc_cidr = kvargs.get("vpc_cidr", "")
        controller.logger.warn(kvargs)

        # get availability_zone
        availability_zone = container.get_simple_resource(kvargs.get("parent"))
        site = availability_zone.get_parent()

        # select remote orchestrators
        orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag)

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
                raise ApiManagerError(
                    "no available sub cidr found for orchestrator %s in base cidr %s" % (orchestrator["id"], base_cidr)
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
        self.logger.debug("Get network %s cidr: %s" % (self.uuid, cidr))
        return cidr

    def get_zabbix_proxy(self):
        """Get network zabbix proxy

        :return: ip address and hostname of zabbix proxy
        """
        zbx_proxy = self.get_attribs(key="configs.zabbix_proxy")
        if zbx_proxy is None:
            raise ApiManagerError(
                "No zabbix proxy available in attributes of network %s" % self.uuid,
                code=404,
            )
        l = zbx_proxy.split(",", maxsplit=1)
        zbx_proxy_ip = l[0].strip()
        zbx_proxy_name = None
        if len(l) == 2:
            zbx_proxy_name = l[1].strip()
        self.logger.debug("Get network %s zabbix proxy: %s, %s" % (self.uuid, zbx_proxy_ip, zbx_proxy_name))
        return zbx_proxy_ip, zbx_proxy_name

    def get_dns_search(self):
        """Get network dns_search"""
        dns_search = self.get_attribs(key="configs.dns_search")
        self.logger.debug("Get network %s dns search: %s" % (self.uuid, dns_search))
        return dns_search

    def get_dns_nameservers(self):
        """Get network dns_nameservers"""
        dns_nameservers = self.get_attribs(key="configs.dns_nameservers")
        self.logger.debug("Get network %s dns nameservers: %s" % (self.uuid, dns_nameservers))
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

        physical_nets, total = self.get_linked_resources(link_type_filter="relation")
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

        self.logger.debug("Get network %s allocable subnet for cidr %s: %s" % (self.uuid, cidr, allocable_subnet))
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
