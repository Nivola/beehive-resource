# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from datetime import datetime
from beecell.simple import format_date, truncate, dict_set, dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Resource
from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc
from beehive_resource.plugins.provider.entity.zone import (
    AvailabilityZoneChildResource,
    ComputeZone,
)
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge


class ComputeGateway(ComputeProviderResource):
    """Compute gateway"""

    objdef = "Provider.ComputeZone.ComputeGateway"
    objuri = "%s/gateways/%s"
    objname = "gateway"
    objdesc = "Provider ComputeGateway"
    task_path = "beehive_resource.plugins.provider.task_v2.gateway.GatewayTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.actions = [
            # 'start',
            # 'stop',
            # 'reboot',
            # 'pause',
            # 'unpause',
            # 'migrate',
            # # 'setup_network': self.setup_network,
            # # 'reset_state': self.reset_state,
            # 'add_volume',
            # 'del_volume',
            # 'set_flavor',
        ]

    def get_hypervisor(self):
        hypervisor = self.get_attribs(key="type")
        return hypervisor

    def get_hypervisor_tag(self):
        hypervisor = self.get_attribs(key="orchestrator_tag", default="default")
        return hypervisor

    def get_hostgroup(self):
        host_group = self.get_attribs(key="host_group", default="default")
        return host_group

    def get_default_role(self):
        role = self.get_attribs(key="default_role", default="")
        return role

    def set_default_role(self, role):
        self.set_configs(key="default_role", value=role)

    def get_transport_vpc(self):
        links, tot = self.get_links(type="transport")
        if tot == 1:
            link = links[0]
            vpc = link.get_end_simple_resource()
            dict_set(vpc.attribs, "configs.cidr", link.get_attribs(key="subnet"))
            return vpc
        else:
            return None

    def get_uplink_vpcs(self):
        objs, tot = self.get_linked_resources(link_type="uplink", objdef=Vpc.objdef, run_customize=False)
        return objs

    def get_internal_vpcs(self):
        objs, tot = self.get_linked_resources(link_type="internal-vpc", objdef=Vpc.objdef, run_customize=False)
        return objs

    def get_internal_router(self):
        res = []
        objs, tot = self.get_linked_resources(link_type_filter="relation.%", objdef=Gateway.objdef, run_customize=False)
        for obj in objs:
            edge = obj.get_nsx_edge()
            router = obj.get_openstack_router()
            if edge is not None:
                res.append(edge)
            if router is not None:
                res.append(router)
        self.logger.debug("gateway %s internal router: %s" % (self.oid, res))
        return res

    def get_external_ip_address(self):
        res = {}
        objs, tot = self.get_linked_resources(link_type_filter="relation.%", objdef=Gateway.objdef, run_customize=False)
        for obj in objs:
            edge = obj.get_nsx_edge()
            if edge is not None:
                edge_info = edge.info()
                uplink_vnics = [
                    v
                    for v in edge.get_vnics()
                    if dict_get(v, "isConnected") == "true" and dict_get(v, "type") == "uplink"
                ]
                if len(uplink_vnics) > 0:
                    res[obj.get_role()] = dict_get(uplink_vnics[0], "addressGroups.addressGroup.primaryAddress")
        return res

    def get_internal_router_info(self):
        res = []
        objs, tot = self.get_linked_resources(link_type_filter="relation.%", objdef=Gateway.objdef, run_customize=False)
        for obj in objs:
            edge = obj.get_nsx_edge()
            router = obj.get_openstack_router()
            if edge is not None:
                edge_info = edge.info()
                edge_info["role"] = obj.get_role()
                routes = []
                for r in edge.get_routes():
                    if r.get("type") == "static":
                        routes.append({"network": r.get("network"), "next_hop": r.get("nextHop")})
                    elif r.get("type") == "default":
                        routes.append({"network": "0.0.0.0/0", "next_hop": r.get("gateway")})
                edge_info["attributes"].update(
                    {
                        "vnics": [
                            {
                                "index": dict_get(v, "index"),
                                "name": dict_get(v, "name"),
                                "primary_address": dict_get(v, "addressGroups.addressGroup.primaryAddress"),
                                "type": dict_get(v, "type"),
                                "mtu": dict_get(v, "mtu"),
                            }
                            for v in edge.get_vnics()
                            if dict_get(v, "isConnected") == "true"
                        ],
                        "routes": routes,
                    }
                )
                res.append(edge_info)
            if router is not None:
                router_info = router.info()
                router_info["role"] = obj.get_role()
                ports = [p for p in router.get_ports() if p.name.find("internal-port") >= 0]
                routes = []
                for r in router.get_routes():
                    routes.append({"network": r.get("destination"), "next_hop": r.get("nexthop")})
                router_info["attributes"].update(
                    {
                        "vnics": [
                            {
                                "index": p.oid,
                                "name": p.name,
                                "primary_address": p.get_main_ip_address(),
                                "type": "internal",
                                "mtu": "",
                            }
                            for p in ports
                        ],
                        "routes": routes,
                    }
                )
                res.append(router_info)
        return res

    def get_vpc_route_info(self, vpc_id):
        """Get vpc route info to use in task when add, remove vpc.

        :param vpc_id: vpc id
        :return: list of route info
            {'role':.., 'router':.., 'gateway':.., 'network':.., 'cidr':.., 'transport_gateway':..}
        """
        gateways, tot = self.get_linked_resources(
            link_type_filter="relation.%", objdef=Gateway.objdef, run_customize=False
        )

        # get transport vpc
        transport_vpc = self.get_transport_vpc()

        # get vpc
        vpc = self.controller.get_simple_resource(vpc_id)

        # routes list
        routes = []

        for gateway in gateways:
            role = gateway.get_role()
            site = gateway.get_site()
            site_id = site.oid

            # get private network from vpc
            network = vpc.get_network_by_site(site_id)

            # get site network from transport vpc
            transport_network = transport_vpc.get_network_by_site(site_id)

            # get orchestrators
            host_group = self.get_hostgroup()
            orchestrators_tag = self.get_hypervisor_tag()
            orchestrators = site.get_orchestrators_by_tag(orchestrators_tag, index_field="type")

            ###### nsx edge ######
            orchestrator = orchestrators.get("vsphere")
            clusters = dict_get(orchestrator, "config.clusters")
            host_group_config = clusters.get(host_group, None)

            # - get distributed virtual switch
            dvs_id = host_group_config.get("dvs", None)
            dvs = self.controller.get_simple_resource(dvs_id)

            # - get logical switch
            logical_switch = network.get_vsphere_network()
            # portgroup = logical_switch.ext_id
            ip_address = logical_switch.get_gateway()
            cidr = logical_switch.get_private_subnet()

            # - get transport portgroup
            transport_portgroup = transport_network.get_vsphere_network(dvs=dvs.oid).oid

            # - get edge
            edge = gateway.get_nsx_edge()
            if edge is None:
                continue

            # - get edge transport vnic
            vnics = edge.get_vnics(portgroup=transport_portgroup)
            if len(vnics) != 1:
                raise ApiManagerError("transport network has no vnic for portgroup %s" % transport_portgroup)
            trasport_ip_address = dict_get(vnics[0], "addressGroups.addressGroup.primaryAddress")

            # - add edge route
            routes.append(
                {
                    "role": role,
                    "router": edge,
                    "gateway": ip_address,
                    "network": logical_switch.oid,
                    "cidr": cidr,
                    "transport_gateway": trasport_ip_address,
                }
            )

            ###### openstack router ######
            # - get openstack network
            ops_network = network.get_openstack_network()

            # - get subnet and gateway
            subnet_id = ops_network.get_private_subnet_entity().oid
            ip_address = ops_network.get_gateway()
            cidr = ops_network.get_private_subnet()
            network_id = ops_network.oid

            # - get router reference
            router = gateway.get_openstack_router()
            if router is None:
                continue

            # - get transport network
            transport_ops_network = transport_network.get_openstack_network().oid

            # - get router trasport port
            ports = [p for p in router.get_ports() if p.network.oid == transport_ops_network]

            if len(ports) != 1:
                raise ApiManagerError("transport network has no port in openstack router %s" % router)
            trasport_ip_address = ports[0].get_main_ip_address()

            # - add openstack router route
            routes.append(
                {
                    "role": role,
                    "router": router,
                    "gateway": ip_address,
                    "network": (network_id, subnet_id),
                    "cidr": cidr,
                    "transport_gateway": trasport_ip_address,
                }
            )

        self.logger.debug("vpc %s routes: %s" % (vpc, routes))
        return routes

    def get_bastion(self, parent=None):
        """get gateway bastion host

        :param parent: parent instance
        :return: bastion host
        """
        computeZone: ComputeZone = parent
        if computeZone is None:
            computeZone = self.get_parent()
        bastion = computeZone.get_bastion_host()
        return bastion

    def has_bastion(self, parent):
        """check gateway has bastion host

        :return: True if bastion host exists
        """
        if self.get_bastion(parent) is not None:
            return True
        return False

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        parent = self.get_parent()
        info["parent_desc"] = parent.desc
        try:
            info["hypervisor"] = self.get_hypervisor()
            transport = self.get_transport_vpc()
            if transport is not None:
                transport = transport.info()
            info["vpc"] = {
                "uplinks": [v.info() for v in self.get_uplink_vpcs()],
                "transport": transport,
                "internals": [v.info() for v in self.get_internal_vpcs()],
            }
            info["default_role"] = self.get_default_role()
            info["external_ip_address"] = self.get_external_ip_address()
            info["bastion"] = self.has_bastion(parent)
        except:
            self.logger.warn("", exc_info=True)

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        parent = self.get_parent()
        info["parent_desc"] = parent.desc
        try:
            info["hypervisor"] = self.get_hypervisor()
            transport = self.get_transport_vpc()
            if transport is not None:
                transport = transport.info()
            info["vpc"] = {
                "uplinks": [v.info() for v in self.get_uplink_vpcs()],
                "transport": transport,
                "internals": [v.info() for v in self.get_internal_vpcs()],
            }
            info["default_role"] = self.get_default_role()
            info["external_ip_address"] = self.get_external_ip_address()

            # get internal_router
            info["details"] = {"internal_router": self.get_internal_router_info()}

            info["bastion"] = self.has_bastion(parent)
        except:
            self.logger.warn("", exc_info=True)
        return info

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {}

        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return kvargs

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        # # get main zone instance
        # res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type='relation%')
        # res = res.get(self.oid)
        # objdefs = [Gateway.objdef]
        # for zone_gw in res:
        #     linked = self.controller.get_directed_linked_resources_internal(resources=[self.oid], objdefs=objdefs)
        # self.logger.debug2('Get compute instance main zone instance: %s' % self.main_zone_instance)
        #
        # # set physical_server
        # if self.main_zone_instance is not None:
        #     self.physical_server = self.main_zone_instance.get_physical_server()
        #     if self.physical_server is not None:
        #         self.physical_server_status = self.physical_server.get_status()
        # self.logger.debug2('Get physical server: %s' % self.physical_server)
        #
        # # get other linked entities
        #
        # self.logger.debug2('Get compute instance linked entities: %s' % linked)

        pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.flavor: gateway flavor [default=compact]
        :param kvargs.volume_flavor: volume flavor
        :param kvargs.uplink_vpc:
        :param kvargs.primary_subnet:
        :param kvargs.secondary_subnet:
        :param kvargs.transport_vpc:
        :param kvargs.primary_zone:
        :param kvargs.secondary_zone:
        :param kvargs.primary_ip_address:
        :param kvargs.secondary_ip_address:
        :param kvargs.admin_pwd: admin password
        :param kvargs.dns:
        :param kvargs.dns_search:
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.orchestrator_tag: orchestrators tag [default=default]
        :param kvargs.type: orchestrator type. Ex. vsphere|pfsense
        :return: dict
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get("type", "vsphere")
        orchestrator_tag = kvargs.get("orchestrator_tag")
        host_group = kvargs.get("host_group", "default")
        compute_zone_id = kvargs.get("parent")
        flavor = kvargs.get("flavor")
        primary_zone_id = kvargs.get("primary_zone")
        secondary_zone_id = kvargs.get("secondary_zone", None)
        primary_ip_address = kvargs.get("primary_ip_address", None)
        secondary_ip_address = kvargs.get("secondary_ip_address", None)
        volume_flavor_id = kvargs.get("volume_flavor")
        uplink_vpc_id = kvargs.get("uplink_vpc")
        primary_subnet = kvargs.get("primary_subnet")
        secondary_subnet = kvargs.get("secondary_subnet", None)
        transport_vpc_id = kvargs.get("transport_vpc")
        admin_pwd = kvargs.get("admin_pwd")

        # get compute zone
        compute_zone = controller.get_simple_resource(compute_zone_id)
        compute_zone.set_container(container)

        active_availability_zones = []

        # get primary availability zone
        primary_site = controller.get_simple_resource(primary_zone_id, entity_class=Site)
        zone_id = ComputeProviderResource.get_active_availability_zone(compute_zone, primary_site)
        active_availability_zones.append(zone_id)

        # get secondary availability zone
        secondary_site = None
        if secondary_zone_id is not None:
            secondary_site = controller.get_simple_resource(secondary_zone_id, entity_class=Site)
            zone_id = ComputeProviderResource.get_active_availability_zone(compute_zone, secondary_site)
            active_availability_zones.append(zone_id)

        # get all the availability zones
        # availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, True)
        availability_zones = active_availability_zones

        # get vpcs
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

        uplink_vpc: Vpc = controller.get_simple_resource(uplink_vpc_id)
        transport_vpc = controller.get_simple_resource(transport_vpc_id)

        # # get transport vpc allocable subnet /28
        # allocable_subnets = ip_network(transport_vpc.get_cidr()).subnets(new_prefix=28)
        # allocated_subnets = []
        # links, tot = transport_vpc.get_links(type='transport', size=-1)
        # for link in links:
        #     allocated_subnets.append(ip_network(link.get_attribs(key='subnet')))
        #
        # transport_subnets = set(allocable_subnets).difference(set(allocated_subnets))
        # if len(transport_subnets) == 0:
        #     raise ApiManagerError('no available transport subnet exist')
        #
        # transport_subnets = (list(transport_subnets))
        # transport_subnets.sort()
        # transport_subnet = str(transport_subnets[0])

        # get volume flavor
        compute_volume_flavor = container.get_simple_resource(volume_flavor_id, entity_class=ComputeVolumeFlavor)

        params = {
            "volume_flavor": compute_volume_flavor.oid,
            "uplink_vpc": uplink_vpc.oid,
            "transport_vpc": transport_vpc.oid,
            "transport_main_subnet": transport_vpc.get_cidr(),
            # 'transport_subnet': transport_subnet,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "host_group": host_group,
                "flavor": flavor,
                # 'primary_ip_address': primary_ip_address,
                # 'secondary_ip_address': secondary_ip_address,
                "admin_pwd": controller.encrypt_data(admin_pwd),
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeGateway.task_path + "create_resource_pre_step",
            ComputeGateway.task_path + "link_gateway_step",
        ]
        for availability_zone_id in availability_zones:
            availability_zone = controller.get_simple_resource(availability_zone_id)
            site_id = availability_zone.parent_id
            # cerca link "relation. + id site"
            uplink_network_id = uplink_vpc.get_network_by_site(site_id).oid
            transport_network_id = transport_vpc.get_network_by_site(site_id).oid
            volume_flavor_id = compute_volume_flavor.get_flavor_by_site(site_id).oid
            if site_id == primary_site.oid:
                role = "primary"
                ip_address = primary_ip_address
                uplink_subnet = primary_subnet
            elif secondary_site is not None and site_id == secondary_site.oid:
                role = "secondary"
                ip_address = secondary_ip_address
                uplink_subnet = secondary_subnet
            else:
                role = "backup"
                ip_address = None
                uplink_subnet = None
            step = {
                "step": ComputeGateway.task_path + "create_zone_gateway_step",
                "args": [
                    availability_zone_id,
                    role,
                    uplink_network_id,
                    transport_network_id,
                    volume_flavor_id,
                    uplink_subnet,
                    ip_address,
                ],
            }
            steps.append(step)
        steps.append(ComputeGateway.task_path + "create_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # get instances
        instances, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [p.oid for p in instances]

        # create task workflow
        steps = [
            ComputeGateway.task_path + "expunge_resource_pre_step",
            ComputeGateway.task_path + "reset_gateway_routes",
        ]
        # remove childs
        for child in childs:
            steps.append(
                {
                    "step": ComputeGateway.task_path + "remove_child_step",
                    "args": [child],
                }
            )
        # post expunge
        steps.append(ComputeGateway.task_path + "expunge_resource_post_step")

        kvargs["steps"] = steps
        return kvargs

    def get_credentials(self):
        self.verify_permisssions("*")

        admin_pwd = self.get_attribs(key="admin_pwd", default="")
        admin_pwd = self.controller.decrypt_data(admin_pwd)
        return {"user": "admin", "password": admin_pwd}

    #
    # metrics
    #
    def get_metrics(self):
        """Get resource metrics

        :return: a dict like this

            {
                "id": "1",
                "uuid": "vm1",
                "metrics": [
                    {
                        "key": "ram",
                        "value: 10,
                        "type": 1,
                        "unit": "GB"
                    }],
                "extraction_date": "2018-03-04 12:00:34 200",
                "resource_uuid": "12u956-2425234-23654573467-567876"
            }
        """
        metrics = []
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get compute instance %s metrics: %s" % (self.uuid, res))
        return res

    #
    # actions
    #
    def add_internal_vpc(self, *args, **kvargs):
        """Add internal vpc to gateway

        :param vpc: vpc id [optional]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        vpc = kvargs.pop("vpc", None)
        vpc = self.container.get_simple_resource(vpc)

        if self.is_linked(vpc.oid) is True:
            raise ApiManagerError("vpc %s is already linked" % vpc.oid)

        vpc.check_active()
        kvargs["vpc"] = vpc.oid
        steps = [self.task_path + "add_gateway_internal_vpc"]
        res = self.action("add_internal_vpc", steps, log="Add vpc to gateway", check=None, **kvargs)
        return res

    def del_internal_vpc(self, *args, **kvargs):
        """Remove internal vpc to gateway

        :param vpc: vpc id [optional]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        vpc = kvargs.pop("vpc", None)
        vpc = self.container.get_simple_resource(vpc)

        if self.is_linked(vpc.oid) is False:
            raise ApiManagerError("vpc %s is not linked" % vpc.oid)

        vpc.check_active()
        kvargs["vpc"] = vpc.oid
        steps = [self.task_path + "del_gateway_internal_vpc"]
        res = self.action("del_internal_vpc", steps, log="Add vpc to gateway", check=None, **kvargs)
        return res

    #
    # routing
    #
    def __get_vsphere_transport_ip_address(self, gateway):
        trasport_ip_address = None

        edge = gateway.get_nsx_edge()
        site = gateway.get_site()

        # get orchestrators
        host_group = self.get_hostgroup()
        orchestrators_tag = self.get_hypervisor_tag()
        orchestrators = site.get_orchestrators_by_tag(orchestrators_tag, index_field="type")
        orchestrator = orchestrators.get("vsphere")
        clusters = dict_get(orchestrator, "config.clusters")
        host_group_config = clusters.get(host_group, None)

        # - get distributed virtual switch
        dvs_id = host_group_config.get("dvs", None)
        dvs = self.controller.get_simple_resource(dvs_id)

        # - get transport portgroup
        transport_vpc = self.get_transport_vpc()
        transport_network = transport_vpc.get_network_by_site(site.oid)
        transport_portgroup = transport_network.get_vsphere_network(dvs=dvs.oid).oid

        # - get edge transport vnic
        vnics = edge.get_vnics(portgroup=transport_portgroup)
        if len(vnics) != 1:
            raise ApiManagerError("transport network has no vnic for portgroup %s" % transport_portgroup)
        trasport_ip_address = dict_get(vnics[0], "addressGroups.addressGroup.primaryAddress")

        return trasport_ip_address

    def set_default_internet_route(self, role="default"):
        """Create default internet route

        :param role: role to select router. Can be default, primary, secondary  [default=default]
        """
        # create default internet route by primary router
        # ex.
        # per 0.0.0.0/0 via 192.168.96.2
        if self.get_hypervisor() == "vsphere" and role != "":
            self.set_default_role(role)

            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            gateway_from_role = None
            if role in ["primary", "secondary"]:
                # get main edge
                for gateway in gateways:
                    if gateway.get_role() == role:
                        gateway_from_role = gateway

            # add internet ruote to openstack router
            for gateway in gateways:
                if role == "default":
                    gateway_from_role = gateway

                # get transport ip address to use in route
                trasport_ip_address = self.__get_vsphere_transport_ip_address(gateway_from_role)

                # create route
                router = gateway.get_openstack_router()
                static_route = [{"destination": "0.0.0.0/0", "nexthop": trasport_ip_address}]
                router.add_routes(static_route)

                # refresh cache
                self.controller.get_resource(router.oid)
                self.logger.debug("add openstack router %s default internet route %s" % (router.oid, static_route))

            self.logger.info("set gateway %s default internet route for role %s" % (self.oid, role))

    def unset_default_internet_route(self, role="default"):
        """Remove default internet route

        :param role: role to select router. Can be default, primary, secondary  [default=default]
        """
        # create default internet route by primary router
        # ex.
        # per 0.0.0.0/0 via 192.168.96.2
        if self.get_hypervisor() == "vsphere" and role != "":
            self.set_default_role("")

            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            gateway_from_role = None
            if role in ["primary", "secondary"]:
                # get main edge
                for gateway in gateways:
                    if gateway.get_role() == role:
                        gateway_from_role = gateway

            # add internet ruote to openstack router
            for gateway in gateways:
                if role == "default":
                    gateway_from_role = gateway

                # get transport ip address to use in route
                trasport_ip_address = self.__get_vsphere_transport_ip_address(gateway_from_role)

                router = gateway.get_openstack_router()
                static_route = [{"destination": "0.0.0.0/0", "nexthop": trasport_ip_address}]
                router.del_routes(static_route)

                # refresh cache
                self.controller.get_resource(router.oid)
                self.logger.debug("delete openstack router %s default internet route %s" % (router.oid, static_route))

            self.logger.info("unset gateway %s default internet route for role %s" % (self.oid, role))

    def reset_routes(self):
        """Remove default internet route"""
        # get zone gateway
        gateways, tot = self.get_linked_resources(
            link_type_filter="relation.%", objdef=Gateway.objdef, run_customize=False
        )

        # add internet ruote to openstack router
        for gateway in gateways:
            router: OpenstackRouter = gateway.get_openstack_router()
            if router is None:
                continue

            router.reset_routes()

            # refresh cache
            self.controller.get_resource(router.oid)
            self.logger.debug("delete all openstack router %s routes" % router.oid)

    def set_default_route(self, *args, **kvargs):
        """set default gateway route

        :param role: role to select router. Can be default, primary, secondary  [default=default]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        # role = kvargs.pop('role', None)
        # self.logger.warn(kvargs)
        steps = [self.task_path + "set_gateway_default_route"]
        res = self.action("set_default_route", steps, log="set default route", check=None, **kvargs)
        return res

    #
    # nat
    #
    def __get_nat_rule_desc(
        self,
        action=None,
        original_address=None,
        translated_address=None,
        original_port=None,
        translated_port=None,
        protocol=None,
        vnic=None,
    ):
        desc = "%s-oa:%s-ta:%s" % (action, original_address, translated_address)
        if original_port is not None:
            desc = "%s-op:%s" % (desc, original_port)
        if translated_port is not None:
            desc = "%s-tp:%s" % (desc, original_port)
        if protocol is not None:
            desc = "%s-pr:%s" % (desc, protocol)
        if vnic is not None:
            desc = "%s-vn:%s" % (desc, vnic)

        return desc

    def get_nat_rules(self):
        """Get nat rules"""
        nat_rules = []
        if self.get_hypervisor() == "vsphere":
            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            for gateway in gateways:
                role = gateway.get_role()

                # create nat rule
                edge = gateway.get_nsx_edge()
                if edge is None:
                    continue

                rules = edge.get_nat_config()
                for rule in rules:
                    rule["role"] = role
                nat_rules.extend(rules)
                self.logger.debug("get edge %s nat rules %s" % (edge.oid, truncate(rules)))

        return nat_rules

    def add_nat_rule(
        self,
        action=None,
        original_address=None,
        translated_address=None,
        enabled=True,
        logged=False,
        original_port=None,
        translated_port=None,
        protocol=None,
        vnic=None,
        role="default",
    ):
        """Create nat rule

        :param action: can be dnat, snat
        :param enabled: rule status [default=True]
        :param logged: rule logged [default=False]
        :param original_address: original address
        :param translated_address: translated address
        :param original_port: original port [optional]
        :param translated_port: translated port [optional]
        :param protocol: protocol [optional]
        :param vnic: vnic [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        """
        if self.get_hypervisor() == "vsphere":
            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            for gateway in gateways:
                # bypass edge with different role
                if role in ["primary", "secondary"] and gateway.get_role() != role:
                    continue

                # create nat rule
                edge = gateway.get_nsx_edge()
                desc = self.__get_nat_rule_desc(
                    action,
                    original_address,
                    translated_address,
                    original_port,
                    translated_port,
                    protocol,
                    vnic,
                )
                rule = edge.get_nat_rule(desc=desc)
                if rule is not None:
                    self.logger.warning("rule %s already exists" % desc)
                    continue

                edge.add_nat_rule(
                    desc,
                    action,
                    original_address,
                    translated_address,
                    enabled=enabled,
                    logged=logged,
                    original_port=original_port,
                    translated_port=translated_port,
                    protocol=protocol,
                    vnic=vnic,
                )

                # refresh cache
                self.controller.get_resource(edge.oid)
                self.logger.debug("add edge %s nat rule %s" % (edge.oid, desc))

    def del_nat_rule(
        self,
        action=None,
        original_address=None,
        translated_address=None,
        original_port=None,
        translated_port=None,
        protocol=None,
        vnic=None,
        role="default",
    ):
        """Delete nat rule

        :param action: can be dnat, snat
        :param original_address: original address
        :param translated_address: translated address
        :param original_port: original port [optional]
        :param translated_port: translated port [optional]
        :param protocol: protocol [optional]
        :param vnic: vnic [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        """
        if self.get_hypervisor() == "vsphere":
            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            for gateway in gateways:
                # bypass edge with different role
                if role in ["primary", "secondary"] and gateway.get_role() != role:
                    continue

                # create nat rule
                edge = gateway.get_nsx_edge()
                desc = self.__get_nat_rule_desc(
                    action,
                    original_address,
                    translated_address,
                    original_port,
                    translated_port,
                    protocol,
                    vnic,
                )
                rule = edge.get_nat_rule(desc=desc)
                if rule is None:
                    self.logger.warning("rule %s does not exist" % desc)
                    continue

                edge.del_nat_rule(rule)

                # refresh cache
                self.controller.get_resource(edge.oid)
                self.logger.debug("delete edge %s nat rule %s" % (edge.oid, desc))

    def add_nat_rule_action(self, *args, **kvargs):
        """Create nat rule

        :param action: can be dnat, snat
        :param enabled: rule status [default=True]
        :param logged: rule logged [default=False]
        :param original_address: original address
        :param translated_address: translated address
        :param original_port: original port [optional]
        :param translated_port: translated port [optional]
        :param protocol: protocol [optional]
        :param vnic: vnic [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [self.task_path + "add_gateway_nat_rule"]
        res = self.action("add_nat_rule", steps, log="add nat rule", check=None, **kvargs)
        return res

    def del_nat_rule_action(self, *args, **kvargs):
        """Delete nat rule

        :param action: can be dnat, snat
        :param original_address: original address
        :param translated_address: translated address
        :param original_port: original port [optional]
        :param translated_port: translated port [optional]
        :param protocol: protocol [optional]
        :param vnic: vnic [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [self.task_path + "del_gateway_nat_rule"]
        res = self.action("del_nat_rule", steps, log="del nat rule", check=None, **kvargs)
        return res

    #
    # firewall
    #
    @staticmethod
    def get_firewall_rule_name(action, direction, source, destination, application):
        name = "%s" % action
        if direction is not None:
            name = "%s-dir:%s" % (name, direction)
        else:
            name = "%s-dir:any" % name
        if source is not None:
            name = "%s-src:%s" % (name, source)
        else:
            name = "%s-src:any" % name
        if destination is not None:
            name = "%s-dst:%s" % (name, destination)
        else:
            name = "%s-dst:any" % name
        if application is not None:
            name = "%s-appl:%s" % (name, application)
        else:
            name = "%s-appl:any" % name
        return name

    def get_firewall_rules(self):
        """Get firewall rules"""
        firewall_rules = []
        if self.get_hypervisor() == "vsphere":
            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            for gateway in gateways:
                role = gateway.get_role()

                # create firewall rule
                edge = gateway.get_nsx_edge()
                if edge is None:
                    continue

                rules = edge.get_firewall_rules()
                for rule in rules:
                    rule["role"] = role
                firewall_rules.extend(rules)
                self.logger.debug("get edge %s firewall rules %s" % (edge.oid, truncate(rules)))

        return firewall_rules

    def add_firewall_rule(
        self,
        action="accept",
        enabled=True,
        logged=False,
        direction=None,
        source=None,
        dest=None,
        appl=None,
        role="default",
    ):
        """Create firewall rule

        :param action: rule action. Can be: accept, deny [default=accept]
        :param enabled: rule status [default=True]
        :param logged: rule logged [default=False]
        :param direction: rule direction. Can be: in, out, inout [default=inout]
        :param source: rule source. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param dest: rule destination. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param appl: rule application. list of comma separated item like: app:<applicationId>,
            ser:proto+port+source_port [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        """
        if self.get_hypervisor() == "vsphere":
            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            for gateway in gateways:
                # bypass edge with different role
                if role in ["primary", "secondary"] and gateway.get_role() != role:
                    continue

                # create firewall rule
                edge = gateway.get_nsx_edge()
                name = self.get_firewall_rule_name(action, direction, source, dest, appl)
                rule = edge.get_firewall_rule(name=name)
                if rule is not None:
                    self.logger.warning("firewall rule %s already exists" % name)
                    continue

                edge.add_firewall_rule(
                    name,
                    action=action,
                    enabled=enabled,
                    logged=logged,
                    direction=direction,
                    source=source,
                    dest=dest,
                    appl=appl,
                )

                # refresh cache
                self.controller.get_resource(edge.oid)
                self.logger.debug("add edge %s firewall rule %s" % (edge.oid, name))

    def del_firewall_rule(
        self,
        action=None,
        direction=None,
        source=None,
        dest=None,
        appl=None,
        role="default",
    ):
        """Delete firewall rule

        :param action: rule action. Can be: accept, deny [optional]
        :param direction: rule direction. Can be: in, out, inout [optional]
        :param source: rule source. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param dest: rule destination. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param appl: rule application. list of comma separated item like: app:<applicationId>,
            ser:proto+port+source_port [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        """
        if self.get_hypervisor() == "vsphere":
            # get zone gateway
            gateways, tot = self.get_linked_resources(
                link_type_filter="relation.%",
                objdef=Gateway.objdef,
                run_customize=False,
            )

            for gateway in gateways:
                # bypass edge with different role
                if role in ["primary", "secondary"] and gateway.get_role() != role:
                    continue

                # create firewall rule
                edge = gateway.get_nsx_edge()
                if edge is None:
                    continue

                name = self.get_firewall_rule_name(action, direction, source, dest, appl)
                rule = edge.get_firewall_rule(name=name)
                if rule is None:
                    self.logger.warning("firewall rule %s was not found" % name)
                    continue

                edge.del_firewall_rule(rule)

                # refresh cache
                self.controller.get_resource(edge.oid)
                self.logger.debug("delete edge %s firewall rule %s" % (edge.oid, name))

    def add_firewall_rule_action(self, *args, **kvargs):
        """Create firewall rule

        :param action: rule action. Can be: accept, deny [default=accept]
        :param enabled: rule status [default=True]
        :param logged: rule logged [default=False]
        :param direction: rule direction. Can be: in, out, inout [default=inout]
        :param source: rule source. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param dest: rule destination. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param appl: rule application. list of comma separated item like: app:<applicationId>,
            ser:proto+port+source_port [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [self.task_path + "add_gateway_firewall_rule"]
        res = self.action("add_firewall_rule", steps, log="add firewall rule", check=None, **kvargs)
        return res

    def del_firewall_rule_action(self, *args, **kvargs):
        """Delete firewall rule

        :param action: rule action. Can be: accept, deny [optional]
        :param direction: rule direction. Can be: in, out, inout [optional]
        :param source: rule source. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param dest: rule destination. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param appl: rule application. list of comma separated item like: app:<applicationId>,
            ser:proto+port+source_port [optional]
        :param role: role to select router. Can be default, primary, secondary  [default=default]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [self.task_path + "del_gateway_firewall_rule"]
        res = self.action("del_firewall_rule", steps, log="del firewall rule", check=None, **kvargs)
        return res

    #
    # vpn
    #
    # def get_sslvpn_config(self):
    #     """Get ssl vpn configuration
    #     """
    #     config = []
    #     if self.get_hypervisor() == 'vsphere':
    #         # get zone gateway
    #         gateways, tot = self.get_linked_resources(link_type_filter='relation.%', objdef=Gateway.objdef,
    #                                                   run_customize=False)
    #
    #         for gateway in gateways:
    #             role = gateway.get_role()
    #
    #             # create firewall rule
    #             edge = gateway.get_nsx_edge()
    #             if edge is None:
    #                 continue
    #
    #             rules = edge.get_firewall_rules()
    #             for rule in rules:
    #                 rule['role'] = role
    #             firewall_rules.extend(rules)
    #             self.logger.debug('get edge %s firewall rules %s' % (edge.oid, truncate(rules)))
    #
    #     return config


class Gateway(AvailabilityZoneChildResource):
    """Availability Zone Instance"""

    objdef = "Provider.Region.Site.AvailabilityZone.Gateway"
    objuri = "%s/gateways/%s"
    objname = "gateway"
    objdesc = "Provider Availability Zone Gateway"
    task_path = "beehive_resource.plugins.provider.task_v2.gateway.GatewayTask."

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
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.role: gateway role. Can be: primary, secondary or backup
        :param kvargs.uplink_network: uplink network
        :param kvargs.uplink_subnet: uplink subnet
        :param kvargs.transport_network: transport network
        :param kvargs.transport_subnet: transport subnet
        :param kvargs.admin_pwd: admin password
        :param kvargs.dns: dns list
        :param kvargs.dns_search: dns zone
        :param kvargs.host_group: Define the optional host group where put the gateway [optional]
        :param kvargs.flavor: server flavor
        :param kvargs.volume_flavor: volume flavor
        :param kvargs.orchestrator_tag: orchestrator tag [default=default]
        :param kvargs.type: orchestrator type. Can be: vsphere, pfsense
        :param kvargs.ip_address: uplink ip address [optional]
        :return: kvargs
        :raise ApiManagerError:
        """
        controller.logger.info("Gateway - pre_create - kvargs: %s" % kvargs)

        orchestrator_tag = kvargs.get("orchestrator_tag")
        gateway_type = kvargs.get("type")
        role = kvargs.get("role")
        # host_group = kvargs.get('host_group')
        # transport_subnet = kvargs.get('transport_subnet')
        uplink_ip_address = kvargs.get("ip_address")

        # get availability_zone
        availability_zone = container.get_simple_resource(kvargs.get("parent"))
        # site_id = availability_zone.parent_id

        # select remote orchestrators
        orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag)

        # create task workflow
        steps = [
            Gateway.task_path + "create_resource_pre_step",
        ]

        for k, orchestrator in orchestrator_idx.items():
            orchestrator_type = orchestrator["type"]
            physical_role = None
            ip_address = None
            if orchestrator_type == gateway_type:
                physical_role = role
                ip_address = uplink_ip_address
                controller.logger.info("Gateway - pre_create - physical_role: %s" % physical_role)
                controller.logger.info("Gateway - pre_create - ip_address: %s" % ip_address)

            step = {
                "step": Gateway.task_path + "gateway_create_physical_resource_step",
                "args": [orchestrator, physical_role, ip_address],
            }
            steps.append(step)

        steps.extend(
            [
                Gateway.task_path + "create_resource_post_step",
            ]
        )
        kvargs["steps"] = steps
        kvargs["sync"] = True

        return kvargs

    def get_role(self):
        return self.get_attribs("role")

    def get_nsx_edge(self):
        res, tot = self.get_linked_resources(link_type="relation", objdef=NsxEdge.objdef, run_customize=False)
        if len(res) > 0:
            edge = res[0]
            edge.set_container(self.controller.get_container(edge.container_id))
            edge.post_get()
            return edge
        return None

    def get_openstack_router(self):
        res, tot = self.get_linked_resources(link_type="relation", objdef=OpenstackRouter.objdef, run_customize=True)
        if len(res) > 0:
            return res[0]
        return None
