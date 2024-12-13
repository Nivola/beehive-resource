# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.types.type_string import truncate
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.container import Resource
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import SiteChildResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg


class Vpc(ComputeProviderResource):
    """Vpc"""

    objdef = "Provider.ComputeZone.Vpc"
    objuri = "%s/vpcs/%s"
    objname = "vpc"
    objdesc = "Provider Vpc"

    task_base_path = "beehive_resource.plugins.provider.task.vpc."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        from beehive_resource.plugins.provider.entity.security_group import (
            SecurityGroup,
        )
        from beehive_resource.plugins.provider.entity.vpc_endpoint import VpcEndpoint

        self.child_classes = [SecurityGroup, VpcEndpoint]

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        # info['details'].update(self.attribs)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        nets, total = self.get_linked_resources(link_type_filter="relation%")
        info["networks"] = [z.info() for z in nets]
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
        :param kvargs.multi_avz: Define if instance must be deployed to work in all the availability zones
        :param kvargs.networks: list of network id or uuid
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

        networks = kvargs.get("networks")

        # check networks
        params = {"networks": []}
        for network in networks:
            res = container.get_resource(network)
            if res.objdef not in [SiteNetwork.objdef, PrivateNetwork.objdef]:
                raise ApiManagerError("Network %s is not correct" % network)
            params["networks"].append(res.oid)

        params["attribute"] = {"multi_avz": kvargs.pop("multi_avz")}

        kvargs.update(params)
        kvargs["orchestrator_tag"] = kvargs.get("orchestrator_tag", "default")

        # create job workflow
        g_tasks = []
        for network in params["networks"]:
            subtask = {
                "task": Vpc.task_base_path + "task_vpc_assign_network",
                "args": [network],
            }
            g_tasks.append(subtask)
        kvargs["tasks"] = ComputeProviderResource.group_create_task(g_tasks)

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
        networks, total = self.get_linked_resources(link_type_filter="relation%")

        # check if network is SiteNetwork
        if len(networks) > 0 and isinstance(networks[0], SiteNetwork):
            networks = []
            # SiteNetwork are shared and must not be deleted

        childs = [p.oid for p in networks]

        # create job workflow
        kvargs["tasks"] = self.group_remove_task(childs)

        return kvargs


class SiteNetwork(SiteChildResource):
    """Site network. Define external and shared network."""

    objdef = "Provider.Region.Site.Network"
    objuri = "%s/site_networks/%s"
    objname = "site_network"
    objdesc = "Site network"

    task_base_path = "beehive_resource.plugins.provider.task.network."
    create_task = "beehive_resource.tasks.job_resource_create"
    update_task = "beehive_resource.tasks.job_resource_update"
    expunge_task = "beehive_resource.tasks.job_resource_expunge"

    # create_task = 'beehive_resource.plugins.provider.task.site.job_site_network_create'
    # update_task = 'beehive_resource.plugins.provider.task.site.job_site_network_update'
    # # expunge_task = 'beehive_resource.plugins.provider.task.site.job_site_network_delete'
    # add_network_task = 'beehive_resource.plugins.provider.task.site.job_site_network_add_network'
    # add_vsphere_network_task = 'beehive_resource.plugins.provider.task.site.job_site_network_add_network'
    # add_openstack_network_task = 'beehive_resource.plugins.provider.task.site.job_site_network_add_network'

    def __init__(self, *args, **kvargs):
        SiteChildResource.__init__(self, *args, **kvargs)

    def get_allocable_subnet(self, cidr):
        """Get network allocable subnet

        :param cidr: cidr to check if exists and is allocable
        """
        subnets = self.get_attribs(key="configs.subnets")
        allocable_subnet = None
        for item in subnets:
            if item.get("cidr") == cidr:
                if item.get("allocable", True) is True:
                    allocable_subnet = item
                    break

        if allocable_subnet is None:
            raise ApiManagerError("No available subnet found in network %s for cidr %s" % (self.uuid, cidr))

        self.logger.debug("Get network %s allocable subnet for cidr %s: %s" % (self.uuid, cidr, allocable_subnet))
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
            subnets = subnets_idx.values()
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
        subnets = subnets_idx.values()
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
        :param kvargs.subnets: list of network subnet
        :param kvargs.subnets.x.cidr: subnet cidr. Ex. 194.116.110.0/24
        :param kvargs.subnets.x.gateway: gateway ip. Ex. 194.116.110.1
        :param kvargs.subnets.x.dns_search: network dns_search
        :param kvargs.subnets.x.routes: network routes [optional]
        :param params.n.allocable: tell if subnet is allocable
        :param params.n.allocation_pools: allocation pools
        :param params.n.allocation_pools.vsphere: allocation pool for vsphere
        :param params.n.allocation_pools.vsphere.start: allocation pool start ip
        :param params.n.allocation_pools.vsphere.end: allocation pool end ip
        :param params.n.allocation_pools.openstack: allocation pool for openstack
        :param params.n.allocation_pools.openstack.start: allocation pool start ip
        :param params.n.allocation_pools.openstack.end: allocation pool end ip
        :param kvargs.subnets.x.dns_nameservers: list of dns. default=['8.8.8.8', '8.8.8.4'] [optional]
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

        # create job workflow
        g_tasks = []
        for item in orchestrator_idx.values():
            subtask = {
                "task": SiteNetwork.task_base_path + "task_create_site_network",
                "args": [item],
            }
            g_tasks.append(subtask)

        kvargs["tasks"] = AvailabilityZoneChildResource.group_create_task(g_tasks)
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
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

        # create job workflow
        kvargs["tasks"] = self.group_remove_task(orchestrator_idx)

        return kvargs

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

        # create job workflow
        tasks = ["beehive_resource.tasks.update_resource_pre"]
        for subnet in new_subnets:
            tasks.append(
                {
                    "task": SiteNetwork.task_base_path + "task_site_network_add_subnet",
                    "args": [orchestrator_idx.values(), subnet],
                }
            )

        tasks.append("beehive_resource.tasks.update_resource_post")
        res = Resource.action(
            self,
            "add_subnet",
            tasks,
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

        # create job workflow
        tasks = ["beehive_resource.tasks.update_resource_pre"]
        for subnet in del_subnets:
            tasks.append(
                {
                    "task": SiteNetwork.task_base_path + "task_site_network_del_subnet",
                    "args": [orchestrator_idx.values(), subnet],
                }
            )

        tasks.append("beehive_resource.tasks.update_resource_post")

        res = Resource.action(
            self,
            "del_subnet",
            tasks,
            log="Delete subnets from site network %s" % self.uuid,
            **params,
        )
        return res

    @trace(op="update")
    def append_network(self, params):
        """Append network

        :param params.network_id: openstack/vsphere network id, name or uuid
        :return: {'jobid':<job id>}, 202
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # check network exists
        network = self.controller.get_resource(params["network_id"], run_customize=False)

        if isinstance(network, VsphereDvpg):
            params["orchestrator_type"] = "vsphere"
        elif isinstance(network, OpenstackNetwork):
            params["orchestrator_type"] = "openstack"

        params["network_type"] = "vlan"
        params["network_id"] = network.oid

        # create job workflow
        tasks = [
            "beehive_resource.tasks.action_resource_pre",
            "beehive_resource.plugins.provider.task.network.task_update_site_network_append_physical_network",
            "beehive_resource.tasks.action_resource_post",
        ]

        res = Resource.action(
            self,
            "append_network",
            tasks,
            log="Append openstack/vsphere to site network %s" % self.uuid,
            **params,
        )
        return res


class PrivateNetwork(AvailabilityZoneChildResource):
    """Availability zone private network

    TODO
    """

    objdef = "Provider.Region.Site.AvailabilityZone.PrivateNetwork"
    objuri = "%s/private_networks/%s"
    objname = "private_network"
    objdesc = "Provider Availability Zone Private Network"

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

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
        :return: {}
        :raise ApiManagerError:
        """
        name = kvargs.get("name")
        desc = kvargs.get("name", "Gateway %s" % name)

        return kvargs
