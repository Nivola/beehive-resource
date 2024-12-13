# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from ipaddress import IPv4Network, ip_network
from logging import getLogger

from beedrones.openstack.client import OpenstackError
from beehive.common.task_v2 import task_step, run_sync_task, TaskError
from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.plugins.provider.entity.gateway import ComputeGateway, Gateway
from beehive_resource.plugins.provider.task_v2 import (
    AbstractProviderResourceTask,
    dict_get,
)
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg

logger = getLogger(__name__)


class GatewayTask(AbstractProviderResourceTask):
    """Gateway task"""

    name = "gateway_task"
    entity_class = ComputeGateway

    @staticmethod
    @task_step()
    def link_gateway_step(task, step_id, params, *args, **kvargs):
        """Create main links

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        volume_flavor_id = params.get("volume_flavor")
        uplink_vpc_id = params.get("uplink_vpc")
        transport_vpc_id = params.get("transport_vpc")
        # transport_subnet = params.get('transport_subnet')

        from beehive_resource.container import Resource

        resource: Resource = task.get_simple_resource(oid)
        transport_vpc: Resource = task.get_simple_resource(transport_vpc_id)
        task.progress(step_id, msg="get resource %s" % oid)

        # get transport vpc allocable subnet /28
        allocable_subnets = ip_network(transport_vpc.get_cidr()).subnets(new_prefix=28)
        allocated_subnets = []

        links, tot = transport_vpc.get_links(type="transport", size=-1)
        for link in links:
            allocated_subnets.append(ip_network(link.get_attribs(key="subnet")))

        transport_subnets = set(allocable_subnets).difference(set(allocated_subnets))
        if len(transport_subnets) == 0:
            raise TaskError("no available transport subnet exist")

        transport_subnets = list(transport_subnets)
        transport_subnets.sort()
        transport_subnet = str(transport_subnets[0])

        # link transport vpc to gateway
        resource.add_link(
            "%s-%s-transport-link" % (oid, transport_vpc_id),
            "transport",
            transport_vpc_id,
            attributes={"subnet": transport_subnet},
        )
        task.progress(step_id, msg="Link transport vpc %s to gateway %s" % (transport_vpc_id, oid))

        # link volume flavor to gateway
        resource.add_link(
            "%s-volumeflavor-link" % oid,
            "volumeflavor",
            volume_flavor_id,
            attributes={},
        )
        task.progress(step_id, msg="Link volume flavor %s to gateway %s" % (volume_flavor_id, oid))

        # link uplink vpc to gateway
        resource.add_link(
            "%s-%s-uplink-link" % (oid, uplink_vpc_id),
            "uplink",
            uplink_vpc_id,
            attributes={},
        )
        task.progress(step_id, msg="Link uplink vpc %s to gateway %s" % (uplink_vpc_id, oid))

        # generate available subnet ip
        ip_list = list(IPv4Network(transport_subnet).hosts())
        ip_list = [str(ip) for ip in ip_list[2:-2]]
        task.progress(step_id, msg="use transport subnet %s" % transport_subnet)

        task.set_shared_data(ip_list)
        # logger.debug('ip_list: %s' % ip_list)

        return oid, params

    @staticmethod
    @task_step()
    def create_zone_gateway_step(
        task,
        step_id,
        params,
        availability_zone_id,
        role,
        uplink_network_id,
        transport_network_id,
        volume_flavor_id,
        uplink_vpc_subnet,
        ip_address,
        *args,
        **kvargs,
    ):
        """Create compute_gateway gateway.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :param role: role: primary, secondary, backup
        :param uplink_network_id: uplink network id
        :param transport_network_id: transport network id
        :param volume_flavor_id: volume flavor id
        :param uplink_vpc_subnet: uplink subnet
        :param ip_address: uplink ip address
        :return: True, params
        """
        task.progress(
            step_id,
            msg="Creating gateway in availability zone %s ..." % availability_zone_id,
        )

        cid = params.get("cid")
        oid = params.get("id")
        # uplink_network_id = params.get('uplink_network_id')
        # uplink_vpc_subnet = params.get('uplink_subnet')

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # get uplink site network
        from beehive_resource.plugins.provider.entity.vpc_v2 import SiteNetwork
        from beehive_resource.plugins.provider.entity.vpc_v2 import PrivateNetwork

        uplink_network: SiteNetwork = task.get_simple_resource(uplink_network_id)
        logger.debug("create_zone_gateway_step - uplink_network: %s" % (type(uplink_network)))
        uplink_subnet = None  # da attributes della Site.Network
        if uplink_vpc_subnet is not None:  # cidr
            uplink_subnet = uplink_network.get_allocable_subnet(uplink_vpc_subnet)

        # create gateway
        gateway_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone gateway %s" % params.get("desc"),
            "parent": availability_zone_id,
            "role": role,
            "uplink_network": uplink_network_id,
            "uplink_subnet": uplink_subnet,
            "transport_network": transport_network_id,
            "transport_main_subnet": params.get("transport_main_subnet"),
            "admin_pwd": params.get("admin_pwd"),
            "dns": params.get("dns"),
            "dns_search": params.get("dns_search"),
            "host_group": params.get("host_group"),
            "flavor": params.get("flavor"),
            "volume_flavor": volume_flavor_id,
            "orchestrator_tag": params.get("orchestrator_tag"),
            # "orchestrator_select_types": params.get("orchestrator_select_types"),
            "type": params.get("type"),
            "ip_address": ip_address,
            "attribute": {"role": role},
        }
        prepared_task, code = provider.resource_factory(Gateway, **gateway_params)
        gateway_id = prepared_task["uuid"]

        # link gateway to compute gateway
        task.get_session(reopen=True)

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        compute_gateway.add_link(
            "%s-gateway-link" % gateway_id,
            "relation.%s" % site_id,
            gateway_id,
            attributes={},
        )
        task.progress(step_id, msg="Link gateway %s to compute gateway %s" % (gateway_id, oid))

        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create gateway in availability zone %s" % availability_zone_id)

        return True, params

    @staticmethod
    @task_step()
    def import_zone_gateway_step(task, step_id, params, site_id, gateways, *args, **kvargs):
        """Import compute gateway gateway.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param site_id: site id
        :param gateways: list of
        :param gateways.x.site_id:
        :param gateways.x.availability_zone_id:
        :param gateways.x.orchestrator_id: orchestrator id
        :param gateways.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param gateways.x.gateway_id:
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        return True, params

    @staticmethod
    @task_step()
    def update_zone_gateway_step(task, step_id, params, site_id, gateways, *args, **kvargs):
        """Update compute_gateway gateway.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param sharedarea.site_id: site id
        :param sharedarea.gateways: list of
        :param sharedarea.site_id:
        :param sharedarea.availability_zone_id:
        :param sharedarea.orchestrator_id: orchestrator id
        :param sharedarea.orchestrator_type Orchestrator type. Ex. vsphere, openstack
        :param sharedarea.gateway_id:
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        return True, params

    @staticmethod
    @task_step()
    def gateway_create_physical_resource_step(
        task, step_id, params, orchestrator, physical_role, uplink_ip, *args, **kvargs
    ):
        """Create gateway physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :param physical_role: physical role
        :param uplink_ip: uplink ip
        :return: gateway_id, params
        """
        oid = params.get("id")
        resource = task.get_resource(oid)
        task.progress(step_id, msg="Get gateway %s" % oid)

        # get transport ip
        ip_list = task.get_shared_data()
        logger.debug("gateway_create_physical_resource_step - ip_list: %s" % ip_list)
        transport_ip = ip_list.pop()
        task.set_shared_data(ip_list)

        from beehive_resource.plugins.provider.task_v2.openstack import (
            ProviderOpenstack,
        )
        from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere

        helper: ProviderOpenstack = task.get_orchestrator(
            orchestrator.get("type"), task, step_id, orchestrator, resource
        )
        gateway_id = helper.create_gateway(physical_role, uplink_ip, transport_ip, params)
        task.progress(step_id, msg="Create gateway %s" % orchestrator.get("type"))

        return gateway_id, params

    @staticmethod
    @task_step()
    def gateway_import_physical_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Import gateway physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :return: gateway_id, params
        """
        oid = params.get("id")
        gateway_conf = orchestrator.get("gateway", None)

        resource = task.get_resource(oid)
        task.progress(step_id, msg="Get gateway %s" % oid)

        gateway_id = None
        if gateway_conf is not None:
            helper = task.get_orchestrator(orchestrator.get("type"), task, step_id, orchestrator, resource)
            gateway_id = helper.import_gateway(gateway_conf["id"])
            task.progress(step_id, msg="Import gateway %s" % gateway_conf["id"])

        return gateway_id, params

    @staticmethod
    def get_vpc_network_route_info(task, compute_gateway, vpc, transport_vpc):
        gateways, tot = compute_gateway.get_linked_resources(
            link_type_filter="relation.%", objdef=Gateway.objdef, run_customize=False
        )

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
            host_group = compute_gateway.get_hostgroup()
            orchestrators_tag = compute_gateway.get_hypervisor_tag()
            orchestrators = site.get_orchestrators_by_tag(orchestrators_tag, index_field="type")

            ###### nsx edge ######
            orchestrator = orchestrators.get("vsphere")
            clusters = dict_get(orchestrator, "config.clusters")
            host_group_config = clusters.get(host_group, None)

            # - get distributed virtual switch
            dvs_id = host_group_config.get("dvs", None)
            dvs = task.get_simple_resource(dvs_id)

            # - get logical switch
            logical_switch = network.get_vsphere_network()
            portgroup = logical_switch.ext_id
            ip_address = logical_switch.get_gateway()
            cidr = logical_switch.get_private_subnet()

            # - get transport portgroup
            transport_portgroup = transport_network.get_vsphere_network(dvs=dvs.oid).oid

            # - get edge
            edge = gateway.get_nsx_edge()

            # - get edge trasport vnic
            vnics = edge.get_vnics(portgroup=transport_portgroup)
            if len(vnics) != 1:
                raise TaskError("transport network has no vnic for portgroup %s" % transport_portgroup)
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

            # - get transport network
            transport_ops_network = transport_network.get_openstack_network().oid

            # - get router trasport port
            ports = [p for p in router.get_ports() if p.network.oid == transport_ops_network]

            if len(ports) != 1:
                raise TaskError("transport network has no port in openstack router %s" % router)
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

        task.progress(msg="routes: %s" % routes)
        return routes

    @staticmethod
    @task_step()
    def add_gateway_internal_vpc(task, step_id, params, *args, **kvargs):
        """add gateway internal vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        vpc_id = params.get("vpc")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        # get vpc cidr
        vpc_cidr = task.get_simple_resource(vpc_id).get_cidr()

        # get routes info
        routes = compute_gateway.get_vpc_route_info(vpc_id)

        # link uplink vpc to gateway
        compute_gateway.add_link("%s-%s-internal-link" % (oid, vpc_id), "internal-vpc", vpc_id, attributes={})
        task.progress(step_id, msg="link internal vpc %s to gateway %s" % (vpc_id, oid))

        for route in routes:
            router = route["router"]
            gateway = route["gateway"]
            network = route["network"]

            if isinstance(router, NsxEdge):
                # create edge vnic (Virtual Network Interface Card)
                index = router.get_vnic_available_index()
                vnic_type = "Internal"
                router.add_vnic(index, vnic_type, network, gateway)
                task.progress(
                    step_id,
                    msg="add nsx edge %s vnic %s on logical switch %s" % (router.oid, index, network),
                )

                # create all the routes
                # ex.
                # per 192.168.201.0/24 via 192.168.96.3     # router openstack
                # per 192.168.202.0/24 via 192.168.96.4
                # per 192.168.203.0/24 via 192.168.96.5     # router openstack
                static_routes = []
                for route1 in routes:
                    router1 = route1["router"]

                    # bypass itself
                    if router == router1:
                        continue

                    static_routes.append(
                        {
                            "destination": route1["cidr"],
                            "nexthop": route1["transport_gateway"],
                        }
                    )

                # create route
                router.add_routes(static_routes)
                task.progress(
                    step_id,
                    msg="add nsx edge %s routes %s" % (router.oid, static_routes),
                )

                # create internet snat
                translated_address = dict_get(
                    router.get_vnics(index="0"),
                    "0.addressGroups.addressGroup.primaryAddress",
                )
                desc = "snat-from-%s-by-%s-vnic0" % (vpc_cidr, translated_address)
                router.add_nat_rule(
                    desc,
                    "snat",
                    vpc_cidr,
                    translated_address,
                    enabled=True,
                    logged=True,
                    original_port=None,
                    translated_port=None,
                    protocol=None,
                    vnic="0",
                )
                task.progress(
                    step_id,
                    msg="add nsx edge %s snat %s by %s" % (router.oid, vpc_cidr, translated_address),
                )

            if isinstance(router, OpenstackRouter):
                # create router port
                ops_params = {
                    "subnet_id": network[1],
                    "ip_address": gateway,
                    "network_id": network[0],
                }
                prepared_task, code = router.create_port(ops_params, sync=True)
                run_sync_task(prepared_task, task, step_id)
                task.progress(
                    step_id,
                    msg="add openstack router %s port on network %s" % (router.oid, network[0]),
                )

                # create all the routes
                # ex.
                # per 192.168.200.0/24 via 192.168.96.2
                # per 192.168.202.0/24 via 192.168.96.4
                # per 192.168.203.0/24 via 192.168.96.5
                static_routes = []
                for route1 in routes:
                    router1 = route1["router"]

                    # bypass itself
                    if router == router1:
                        continue

                    static_routes.append(
                        {
                            "destination": route1["cidr"],
                            "nexthop": route1["transport_gateway"],
                        }
                    )

                # create route
                router.add_routes(static_routes)
                # refresh cache
                task.get_resource(router.oid)
                task.progress(
                    step_id,
                    msg="add openstack router %s routes %s" % (router.oid, static_routes),
                )

            # create internet route
            # compute_gateway.set_default_internet_route(role='primary')

            # create firewall rules

        task.progress(step_id, msg="add internal vpc %s to gateway %s" % (vpc_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def del_gateway_internal_vpc(task, step_id, params, *args, **kvargs):
        """remove gateway internal vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        vpc_id = params.get("vpc")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        # get vpc cidr
        vpc_cidr = task.get_simple_resource(vpc_id).get_cidr()

        # get routes info
        routes = compute_gateway.get_vpc_route_info(vpc_id)

        for route in routes:
            router = route["router"]
            network = route["network"]

            if isinstance(router, NsxEdge):
                # delete all the routes
                # ex.
                # per 192.168.201.0/24 via 192.168.96.3
                # per 192.168.202.0/24 via 192.168.96.4
                # per 192.168.203.0/24 via 192.168.96.5
                static_routes = []
                for route1 in routes:
                    router1 = route1["router"]

                    # bypass itself
                    if router == router1:
                        continue

                    static_routes.append(
                        {
                            "destination": route1["cidr"],
                            "nexthop": route1["transport_gateway"],
                        }
                    )

                # create route
                router.del_routes(static_routes)
                task.progress(
                    step_id,
                    msg="delete nsx edge %s routes %s" % (router.oid, static_routes),
                )

                # delete internet snat
                translated_address = dict_get(
                    router.get_vnics(index="0"),
                    "0.addressGroups.addressGroup.primaryAddress",
                )
                desc = "snat-from-%s-by-%s-vnic0" % (vpc_cidr, translated_address)
                nat_rule_id = router.get_nat_rule(desc=desc)
                if nat_rule_id is not None:
                    router.del_nat_rule(nat_rule_id)
                    task.progress(
                        step_id,
                        msg="delete nsx edge %s snat %s by %s" % (router.oid, vpc_cidr, translated_address),
                    )

                # delete edge vnic
                vnics = router.get_vnics(portgroup=network)
                if len(vnics) == 1:
                    index = vnics[0]["index"]
                    router.del_vnic(index)
                    task.progress(
                        step_id,
                        msg="delete nsx edge %s vnic %s on logical switch %s" % (router.oid, index, network),
                    )

            if isinstance(router, OpenstackRouter):
                # delete all the routes
                # ex.
                # per 192.168.200.0/24 via 192.168.96.2
                # per 192.168.202.0/24 via 192.168.96.4
                # per 192.168.203.0/24 via 192.168.96.5
                static_routes = []
                for route1 in routes:
                    router1 = route1["router"]

                    # bypass itself
                    if router == router1:
                        continue

                    static_routes.append(
                        {
                            "destination": route1["cidr"],
                            "nexthop": route1["transport_gateway"],
                        }
                    )

                # delete routes
                router.del_routes(static_routes)
                # refresh cache
                task.get_resource(router.oid)
                task.progress(
                    step_id,
                    msg="delete openstack router %s route %s" % (router.oid, static_routes),
                )

                # delete router port
                ports = router.get_ports(network=network[0])
                if len(ports) == 1:
                    ops_params = {
                        "subnet_id": network[1],
                    }
                    prepared_task, code = router.delete_port(ops_params, sync=True)  # aaa
                    run_sync_task(prepared_task, task, step_id)
                    task.progress(
                        step_id,
                        msg="delete openstack router %s port on network %s" % (router.oid, network[0]),
                    )

        # delete link
        links, tot = compute_gateway.get_links(end_resource=vpc_id)
        links[0].expunge()

        task.progress(step_id, msg="remove internal vpc %s from gateway %s" % (vpc_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def set_gateway_default_route(task, step_id, params, *args, **kvargs):
        """set default gateway route

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        role = params.get("role")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        compute_gateway.unset_default_internet_route(role=compute_gateway.get_default_role())
        compute_gateway.set_default_internet_route(role=role)
        task.progress(step_id, msg="set default gateway %s route for role %s" % (oid, role))

        return oid, params

    @staticmethod
    @task_step()
    def reset_gateway_routes(task, step_id, params, *args, **kvargs):
        """unset default gateway route

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        role = params.get("role")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        compute_gateway.reset_routes()
        task.progress(step_id, msg="reset gateway %s routes" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def add_gateway_firewall_rule(task, step_id, params, *args, **kvargs):
        """Create firewall rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        role = params.get("role")
        action = params.get("action")
        enabled = params.get("enabled")
        logged = params.get("logged")
        direction = params.get("direction")
        source = params.get("source")
        dest = params.get("dest")
        appl = params.get("appl")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        compute_gateway.add_firewall_rule(
            action=action,
            enabled=enabled,
            logged=logged,
            direction=direction,
            source=source,
            dest=dest,
            appl=appl,
            role=role,
        )
        task.progress(step_id, msg="create gateway %s firewall rule" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def del_gateway_firewall_rule(task, step_id, params, *args, **kvargs):
        """Delete firewall rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        role = params.get("role")
        action = params.get("action")
        direction = params.get("direction")
        source = params.get("source")
        dest = params.get("dest")
        appl = params.get("appl")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        compute_gateway.del_firewall_rule(
            action=action,
            direction=direction,
            source=source,
            dest=dest,
            appl=appl,
            role=role,
        )
        task.progress(step_id, msg="delete gateway %s firewall rule" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def add_gateway_nat_rule(task, step_id, params, *args, **kvargs):
        """Create nat rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        role = params.get("role")
        action = params.get("action")
        original_address = params.get("original_address")
        translated_address = params.get("translated_address")
        enabled = params.get("enabled")
        logged = params.get("logged")
        original_port = params.get("original_port")
        translated_port = params.get("translated_port")
        protocol = params.get("protocol")
        vnic = params.get("vnic")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        compute_gateway.add_nat_rule(
            action=action,
            original_address=original_address,
            translated_address=translated_address,
            enabled=enabled,
            logged=logged,
            original_port=original_port,
            translated_port=translated_port,
            protocol=protocol,
            vnic=vnic,
            role=role,
        )
        task.progress(step_id, msg="create gateway %s nat rule" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def del_gateway_nat_rule(task, step_id, params, *args, **kvargs):
        """Delete nat rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        role = params.get("role")
        action = params.get("action")
        original_address = params.get("original_address")
        translated_address = params.get("translated_address")
        original_port = params.get("original_port")
        translated_port = params.get("translated_port")
        protocol = params.get("protocol")
        vnic = params.get("vnic")

        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = task.get_simple_resource(oid)
        task.progress(step_id, msg="get compute_gateway %s" % oid)

        compute_gateway.del_nat_rule(
            action=action,
            original_address=original_address,
            translated_address=translated_address,
            original_port=original_port,
            translated_port=translated_port,
            protocol=protocol,
            vnic=vnic,
            role=role,
        )
        task.progress(step_id, msg="delete gateway %s nat rule" % oid)

        return oid, params
