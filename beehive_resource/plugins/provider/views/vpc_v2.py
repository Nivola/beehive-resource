# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte
from marshmallow.validate import OneOf

from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.vpc_v2 import (
    Vpc,
    SiteNetwork,
    PrivateNetwork,
)
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)


class ProviderVpc(LocalProviderApiView):
    resclass = Vpc
    parentclass = ComputeZone


class ListVpcsRequestSchema(ListResourcesRequestSchema):
    super_zone = fields.String(context="query", description="super zone id, uuid")


class ListVpcsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVpcsResponseSchema(PaginatedResponseSchema):
    vpcs = fields.Nested(ListVpcsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListVpcs(ProviderVpc):
    summary = "List Vpc"
    description = "List Vpc"
    definitions = {
        "ListVpcsResponseSchema": ListVpcsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVpcsRequestSchema)
    parameters_schema = ListVpcsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVpcsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        zone_id = data.get("super_zone", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "SuperZone")
        return self.get_resources(controller, **data)


class GetVpcParamsResponseSchema(ResourceResponseSchema):
    networks = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetVpcResponseSchema(Schema):
    vpc = fields.Nested(GetVpcParamsResponseSchema, required=True, allow_none=True)


class GetVpc(ProviderVpc):
    summary = "Get Vpc"
    description = "Get Vpc"
    definitions = {
        "GetVpcResponseSchema": GetVpcResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVpcResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateVpcParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id")
    # orchestrator_select_types = fields.List(
    #     fields.String(example="vsphere"),
    #     required=False,
    #     allow_none=True,
    #     context="query",
    #     description="orchestrator select types",
    # )
    cidr = fields.String(
        required=True,
        example="192.168.200.0/21",
        description="vpc cidr. Ex. 192.168.200.0/21",
    )
    type = fields.String(
        required=False,
        example="private",
        default="private",
        missing="private",
        description="vpc type. Can be shared or private",
        validate=OneOf(["shared", "private"]),
    )


class CreateVpcRequestSchema(Schema):
    vpc = fields.Nested(CreateVpcParamRequestSchema)


class CreateVpcBodyRequestSchema(Schema):
    body = fields.Nested(CreateVpcRequestSchema, context="body")


class CreateVpc(ProviderVpc):
    summary = "Create vpc"
    description = "Create vpc"
    definitions = {
        "CreateVpcRequestSchema": CreateVpcRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVpcBodyRequestSchema)
    parameters_schema = CreateVpcRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateVpcParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateVpcRequestSchema(Schema):
    vpc = fields.Nested(UpdateVpcParamRequestSchema)


class UpdateVpcBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVpcRequestSchema, context="body")


class UpdateVpc(ProviderVpc):
    summary = "Update Vpc"
    description = "Update Vpc"
    definitions = {
        "UpdateVpcRequestSchema": UpdateVpcRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateVpcBodyRequestSchema)
    parameters_schema = UpdateVpcRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteVpc(ProviderVpc):
    summary = "Delete Vpc"
    description = "Delete Vpc"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class ProviderSiteNetwork(LocalProviderApiView):
    resclass = SiteNetwork
    parentclass = Site


class ListSiteNetworksRequestSchema(ListResourcesRequestSchema):
    pass


class ListSiteNetworksParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSiteNetworksResponseSchema(PaginatedResponseSchema):
    site_networks = fields.Nested(ListSiteNetworksParamsResponseSchema, many=True, required=True, allow_none=True)


class ListSiteNetworks(ProviderSiteNetwork):
    summary = "List site networks"
    description = "List site networks"
    definitions = {
        "ListSiteNetworksResponseSchema": ListSiteNetworksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSiteNetworksRequestSchema)
    parameters_schema = ListSiteNetworksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListSiteNetworksResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        vpc_id = data.get("vpc", None)
        site_id = data.get("site", None)
        instance_id = data.get("instance", None)
        if vpc_id is not None:
            return self.get_linked_resources(controller, vpc_id, "SiteNetwork", "relation%")
        elif instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "ComputeInstance", "network")
        elif site_id is not None:
            return self.get_resources_by_parent(controller, site_id, "Site")

        return self.get_resources(controller, **data)


class GetSiteNetworkParamsResponseSchema(ResourceResponseSchema):
    availability_zones = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetSiteNetworkResponseSchema(Schema):
    site_network = fields.Nested(GetSiteNetworkParamsResponseSchema, required=True, allow_none=True)


class GetSiteNetwork(ProviderSiteNetwork):
    summary = "Get site networks"
    description = "Get site networks"
    definitions = {
        "GetSiteNetworkResponseSchema": GetSiteNetworkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetSiteNetworkResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateSiteNetworkSubnetPoolResponseSchema(Schema):
    start = fields.String(
        required=True,
        example="10.138.200.20",
        default="10.138.200.20",
        description="start pool ip address",
    )
    end = fields.String(
        required=True,
        example="10.138.200.255",
        default="10.138.200.255",
        description="end pool ip address",
    )


class CreateSiteNetworkSubnetPoolsResponseSchema(Schema):
    vsphere = fields.Nested(
        CreateSiteNetworkSubnetPoolResponseSchema,
        required=False,
        many=True,
        description="vsphere pool",
    )
    openstack = fields.Nested(
        CreateSiteNetworkSubnetPoolResponseSchema,
        required=False,
        many=True,
        description="openstack pool",
    )


class CreateSiteNetworkSubnetRequestSchema(Schema):
    gateway = fields.String(
        required=False,
        example="10.102.189.1",
        description="subnet gateway. Ex. 10.102.189.1",
    )
    cidr = fields.String(
        required=True,
        example="10.102.189.0/25",
        description="subnet cidr. Ex. 10.102.189.0/25",
    )
    routes = fields.List(fields.String, required=False, description="subnet additional routes")
    allocation_pools = fields.Nested(
        CreateSiteNetworkSubnetPoolsResponseSchema,
        required=True,
        description="hypervisor pools",
    )
    enable_dhcp = fields.Boolean(
        required=True,
        example=False,
        description="true if dhcp is enabled for the network",
    )
    dns_nameservers = fields.List(
        fields.String(example="8.8.8.8"),
        required=False,
        description='dns nameservers list. Ex. ["8.8.8.8", "8.8.8.4"]',
    )
    allocable = fields.Boolean(
        required=False,
        missing=True,
        description="if False subnet can not be used to allocate ip in the newtwork",
    )


class CreateSiteNetworkParamRequestSchema(CreateProviderResourceRequestSchema):
    site = fields.String(
        required=True,
        example="12",
        description="parent site id, uuid where create network",
    )
    external = fields.Boolean(required=True, example=False, description="true if network is external")
    vlan = fields.Integer(required=True, example=567, description="network segmentation value. Ex. 567")
    dns_search = fields.String(
        required=True,
        example="site03.nivolapiemonte.it",
        description="network dns zone",
    )
    proxy = fields.String(required=False, example="http://10.102.9.9:3128", description="http(s) proxy")
    zabbix_proxy = fields.String(required=False, example="10.102.9.9", description="zabbix proxy")


class CreateSiteNetworkRequestSchema(Schema):
    site_network = fields.Nested(CreateSiteNetworkParamRequestSchema)


class CreateSiteNetworkBodyRequestSchema(Schema):
    body = fields.Nested(CreateSiteNetworkRequestSchema, context="body")


class CreateSiteNetwork(ProviderSiteNetwork):
    summary = "Create site networks"
    description = "Create site networks"
    definitions = {
        "CreateSiteNetworkRequestSchema": CreateSiteNetworkRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateSiteNetworkBodyRequestSchema)
    parameters_schema = CreateSiteNetworkRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateSiteNetworkParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateSiteNetworkRequestSchema(Schema):
    site_network = fields.Nested(UpdateSiteNetworkParamRequestSchema)


class UpdateSiteNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSiteNetworkRequestSchema, context="body")


class UpdateSiteNetwork(ProviderSiteNetwork):
    summary = "Update site networks"
    description = "Update site networks"
    definitions = {
        "UpdateSiteNetworkRequestSchema": UpdateSiteNetworkRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateSiteNetworkBodyRequestSchema)
    parameters_schema = UpdateSiteNetworkRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteSiteNetwork(ProviderSiteNetwork):
    summary = "Delete site networks"
    description = "Delete site networks"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GetSiteNetworkSubnetPoolResponseSchema(Schema):
    start = fields.String(
        required=True,
        example="10.138.200.20",
        default="10.138.200.20",
        description="start pool ip address",
    )
    end = fields.String(
        required=True,
        example="10.138.200.255",
        default="10.138.200.255",
        description="end pool ip address",
    )


class GetSiteNetworkSubnetResponseSchema(Schema):
    enable_dhcp = fields.Boolean(required=True, example=True, default=True, description="enable dhcp on subnet")
    dns_nameservers = fields.List(
        fields.String,
        required=False,
        example=["10.103.48.1", "10.103.48.2"],
        default=["10.103.48.1", "10.103.48.2"],
        description="dns list",
    )
    allocable = fields.Boolean(
        required=True,
        example=True,
        default=True,
        description="tell if subnet is allocable",
    )
    allocation_pools = fields.Nested(
        GetSiteNetworkSubnetPoolResponseSchema,
        required=True,
        many=True,
        description="openstack pool",
    )
    allocation_pools_vs = fields.String(
        required=False,
        example="ipaddresspool-5",
        default="ipaddresspool-5",
        description="vsphere allocation pool id",
    )
    router = fields.String(
        required=False,
        example="10.138.200.2",
        default="10.138.200.2",
        description="subnet internal openstack router ip address",
    )
    cidr = fields.String(
        required=True,
        example="10.138.200.0/21",
        default="10.138.200.0/21",
        description="subnet cidr",
    )
    gateway = fields.String(
        required=False,
        example="10.138.200.1",
        default="10.138.200.1",
        description="subnet gateway",
    )


class GetSiteNetworkSubnetsResponseSchema(Schema):
    subnets = fields.Nested(GetSiteNetworkSubnetResponseSchema, required=True, allow_none=True)


class GetSiteNetworkSubnets(ProviderSiteNetwork):
    summary = "Get site network subnets"
    description = "Get site network subnets"
    definitions = {
        "GetSiteNetworkResponseSchema": GetSiteNetworkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetSiteNetworkResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        container = controller.get_containers(container_type="Provider")[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        res = resource.get_subnets()
        return {"subnets": res}


class AddSiteNetworkSubnetPoolResponseSchema(Schema):
    start = fields.String(
        required=True,
        example="10.138.200.20",
        default="10.138.200.20",
        description="start pool ip address",
    )
    end = fields.String(
        required=True,
        example="10.138.200.255",
        default="10.138.200.255",
        description="end pool ip address",
    )


class AddSiteNetworkSubnetPoolsResponseSchema(Schema):
    vsphere = fields.Nested(
        AddSiteNetworkSubnetPoolResponseSchema,
        required=False,
        many=True,
        description="vsphere pools. For the moment only one is supported",
    )
    openstack = fields.Nested(
        AddSiteNetworkSubnetPoolResponseSchema,
        required=False,
        many=True,
        description="openstack pools. For the moment only one is supported",
    )


class AddSiteNetworkRouteResponseSchema(Schema):
    destination = fields.String(
        required=True,
        example="192.168.0.0/24",
        default="192.168.0.0/24",
        description="route destination",
    )
    nexthop = fields.String(
        required=True,
        example="192.168.0.1",
        default="192.168.0.1",
        description="route next op",
    )


class AddSiteNetworkSubnetResponseSchema(Schema):
    enable_dhcp = fields.Boolean(required=True, example=True, default=True, description="enable dhcp on subnet")
    dns_nameservers = fields.List(
        fields.String,
        required=False,
        example=["10.103.48.1", "10.103.48.2"],
        default=["10.103.48.1", "10.103.48.2"],
        description="dns list",
    )
    allocable = fields.Boolean(
        required=False,
        example=True,
        default=True,
        missing=True,
        description="tell if subnet is allocable",
    )
    allocation_pools = fields.Nested(
        AddSiteNetworkSubnetPoolsResponseSchema,
        required=True,
        description="hypervisor pools",
    )
    routes = fields.Nested(
        AddSiteNetworkRouteResponseSchema,
        required=False,
        many=True,
        description="list of additional routes",
    )
    cidr = fields.String(
        required=True,
        example="10.138.200.0/21",
        default="10.138.200.0/21",
        description="subnet cidr",
    )
    gateway = fields.String(
        required=False,
        example="10.138.200.1",
        default="10.138.200.1",
        description="subnet gateway",
    )


class AddSiteNetworkSubnetsResponseSchema(Schema):
    subnets = fields.Nested(AddSiteNetworkSubnetResponseSchema, required=True, allow_none=True, many=True)
    orchestrator_tag = fields.String(
        required=False,
        missing="default",
        description="orchestrator tag. Use to select a subset of orchestrators where " "entity must be created.",
    )


class AddSiteNetworkSubnetsBodyResponseSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddSiteNetworkSubnetsResponseSchema, context="body")


class AddSiteNetworkSubnets(ProviderSiteNetwork):
    summary = "Add site network subnet"
    description = "Add site network subnet"
    definitions = {
        "AddSiteNetworkSubnetsResponseSchema": AddSiteNetworkSubnetsResponseSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddSiteNetworkSubnetsBodyResponseSchema)
    parameters_schema = AddSiteNetworkSubnetsResponseSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, oid, *args, **kwargs):
        container = controller.get_containers(container_type="Provider")[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        return resource.add_subnets(data)


class DelSiteNetworkSubnetResponseSchema(Schema):
    cidr = fields.String(
        required=True,
        example="10.138.200.0/21",
        default="10.138.200.0/21",
        description="subnet cidr",
    )


class DelSiteNetworkSubnetsResponseSchema(Schema):
    subnets = fields.Nested(DelSiteNetworkSubnetResponseSchema, required=True, allow_none=True, many=True)
    orchestrator_tag = fields.String(
        required=False,
        missing="default",
        description="orchestrator tag. Use to select a " "subset of orchestrators where entity must be created.",
    )


class DelSiteNetworkSubnetsBodyResponseSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DelSiteNetworkSubnetsResponseSchema, context="body")


class DelSiteNetworkSubnets(ProviderSiteNetwork):
    summary = "Delete site network subnet"
    description = "Delete site network subnet"
    definitions = {
        "DelSiteNetworkSubnetsResponseSchema": DelSiteNetworkSubnetsResponseSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DelSiteNetworkSubnetsBodyResponseSchema)
    parameters_schema = DelSiteNetworkSubnetsResponseSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        container = controller.get_containers(container_type="Provider")[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        return resource.delete_subnets(data)


class VpcNetworkResponseSchema(ResourceResponseSchema):
    pass


class ListVpcNetworksResponseSchema(PaginatedResponseSchema):
    site = fields.Nested(VpcNetworkResponseSchema, required=False, allow_none=True, many=True)
    private = fields.Nested(VpcNetworkResponseSchema, required=False, allow_none=True, many=True)


class ListVpcNetworks(ProviderVpc):
    summary = "List Vpc"
    description = "List Vpc"
    definitions = {
        "ListVpcNetworksResponseSchema": ListVpcNetworksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVpcNetworksResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        container = controller.get_containers(container_type="Provider")[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        res = {"site": [], "private": []}
        for net in resource.get_networks():
            if isinstance(net, SiteNetwork):
                res["site"].append(net.info())
            elif isinstance(net, PrivateNetwork):
                res["private"].append(net.info())
        return res


class GetVpcTransportNextSubnetResponseSchema(Schema):
    subnet = fields.String(required=True)


class GetVpcTransportNextSubnet(ProviderVpc):
    summary = "Get next transport subnet"
    description = "Get next transport subnet"
    definitions = {
        "GetVpcTransportNextSubnetResponseSchema": GetVpcTransportNextSubnetResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetVpcTransportNextSubnetResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        from beehive_resource.container import ResourceContainer
        from beehive_resource.plugins.provider.controller import LocalProvider

        container: LocalProvider = controller.get_containers(container_type="Provider")[0][0]
        # resource = self.get_resource_reference(controller, oid, container=container.oid)

        transport_vpc_id = oid
        from beehive_resource.container import Resource
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

        transport_vpc: Vpc = container.get_simple_resource(transport_vpc_id)

        # get transport vpc allocable subnet /28
        from ipaddress import ip_network

        allocable_subnets = ip_network(transport_vpc.get_cidr()).subnets(new_prefix=28)
        allocated_subnets = []

        links, tot = transport_vpc.get_links(type="transport", size=-1)
        for link in links:
            allocated_subnets.append(ip_network(link.get_attribs(key="subnet")))

        transport_subnets = set(allocable_subnets).difference(set(allocated_subnets))
        if len(transport_subnets) == 0:
            raise Exception("no available transport subnet exist")

        transport_subnets = list(transport_subnets)
        transport_subnets.sort()
        transport_subnet = str(transport_subnets[0])
        self.logger.debug("transport_subnet: %s" % transport_subnet)

        res = {"subnet": transport_subnet}
        return res


class AddVpcPrivateNetworkRequestSchema(Schema):
    cidr = fields.String(
        required=False,
        example="192.168.200.0/23",
        missing="192.168.200.0/23",
        description="network cidr",
    )
    dns_search = fields.String(
        required=True,
        example="site03.nivolapiemonte.it",
        description="network dns zone",
    )
    zabbix_proxy = fields.String(required=False, example="10.102.9.9", description="zabbix proxy")
    dns_nameservers = fields.List(
        fields.String(example="8.8.8.8"),
        required=False,
        description='dns nameservers list. Ex. ["8.8.8.8", "8.8.8.4"]',
    )
    availability_zone = fields.String(required=True, example="avz1", description="availability zone id")
    orchestrator_tag = fields.String(
        required=False,
        missing="default",
        description="orchestrator tag. Use to select a " "subset of orchestrators where entity must be created.",
    )
    # orchestrator_select_types = fields.List(
    #     fields.String(example="vsphere"),
    #     required=False,
    #     allow_none=True,
    #     context="query",
    #     description="orchestrator select types",
    # )


class AddVpcSiteNetworkRequestSchema(Schema):
    network = fields.String(required=True, example="123", description="site network id")


class AddVpcNetworkRequestSchema(Schema):
    site = fields.Nested(AddVpcSiteNetworkRequestSchema, required=False, allow_none=True, many=True)
    private = fields.Nested(AddVpcPrivateNetworkRequestSchema, required=False, allow_none=True, many=True)


class AddVpcNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddVpcNetworkRequestSchema, context="body")


class AddVpcNetwork(ProviderVpc):
    summary = "Add network to vpc or assign a site network"
    description = "Add network to vpc or assign a site network"
    definitions = {
        "AddVpcNetworkRequestSchema": AddVpcNetworkRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddVpcNetworkBodyRequestSchema)
    parameters_schema = AddVpcNetworkRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, oid, *args, **kwargs):
        container = controller.get_containers(container_type="Provider")[0][0]
        vpc: Vpc = self.get_resource_reference(controller, oid, container=container.oid)
        return vpc.add_network(**data)


class DeleteVpcPrivateNetworkRequestSchema(Schema):
    cidr = fields.String(required=True, example="10.0.0.0/24", description="network cidr")
    availability_zone = fields.String(required=True, example="avz1", description="availability zone id")
    orchestrator_tag = fields.String(
        required=False,
        missing="default",
        description="orchestrator tag. Use to select a " "subset of orchestrators where entity must be created.",
    )


class DeleteVpcSiteNetworkRequestSchema(Schema):
    network = fields.String(required=True, example="123", description="site network id")


class DeleteVpcNetworkRequestSchema(Schema):
    site = fields.Nested(DeleteVpcSiteNetworkRequestSchema, required=False, allow_none=True, many=True)
    private = fields.Nested(DeleteVpcPrivateNetworkRequestSchema, required=False, allow_none=True, many=True)


class DeleteVpcNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteVpcNetworkRequestSchema, context="body")


class DeleteVpcNetwork(ProviderVpc):
    summary = "Delete network from vpc or deassign a site network"
    description = "Delete network from vpc or deassign a site network"
    definitions = {
        "DeleteVpcNetworkRequestSchema": DeleteVpcNetworkRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteVpcNetworkBodyRequestSchema)
    parameters_schema = DeleteVpcNetworkRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        container = controller.get_containers(container_type="Provider")[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        return resource.del_network(**data)


class VpcProviderAPI(ProviderAPI):
    """Vpc api

    private vpc:
    - create vpc
    - add vpc network (avz 1)
    - add vpc network (avz 2)

    shared vpc:
    - create vpc
    - add site network (site 1)
    - add site network (site 2)
    - add (assign) vpc network (avz 1)
    - add (assign) vpc network (avz 2)
    """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/vpcs" % base, "GET", ListVpcs, {}),
            ("%s/vpcs/<oid>" % base, "GET", GetVpc, {}),
            ("%s/vpcs" % base, "POST", CreateVpc, {}),
            ("%s/vpcs/<oid>" % base, "PUT", UpdateVpc, {}),
            ("%s/vpcs/<oid>" % base, "DELETE", DeleteVpc, {}),
            # private vpc - add/delete network
            # shared vpc - (de)assign network
            ("%s/vpcs/<oid>/network" % base, "GET", ListVpcNetworks, {}),
            ("%s/vpcs/<oid>/network" % base, "POST", AddVpcNetwork, {}),
            ("%s/vpcs/<oid>/network" % base, "DELETE", DeleteVpcNetwork, {}),
            ("%s/vpcs/<oid>/subnet/next" % base, "GET", GetVpcTransportNextSubnet, {}),
            # shared vpc network
            ("%s/site_networks" % base, "GET", ListSiteNetworks, {}),
            ("%s/site_networks/<oid>" % base, "GET", GetSiteNetwork, {}),
            ("%s/site_networks" % base, "POST", CreateSiteNetwork, {}),
            ("%s/site_networks/<oid>" % base, "DELETE", DeleteSiteNetwork, {}),
            # ('%s/site_networks/<oid>/network' % base, 'PUT', AppendNetworkToSiteNetwork, {}),
            ("%s/site_networks/<oid>/subnets" % base, "GET", GetSiteNetworkSubnets, {}),
            (
                "%s/site_networks/<oid>/subnets" % base,
                "POST",
                AddSiteNetworkSubnets,
                {},
            ),
            (
                "%s/site_networks/<oid>/subnets" % base,
                "DELETE",
                DelSiteNetworkSubnets,
                {},
            ),
        ]
        kwargs["version"] = "v2.0"
        ProviderAPI.register_api(module, rules, **kwargs)
