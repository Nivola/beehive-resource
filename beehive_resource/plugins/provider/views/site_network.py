# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.vpc import SiteNetwork
from beehive_resource.view import ListResourcesRequestSchema,\
    ResourceResponseSchema, ResourceSmallResponseSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView,\
    GetApiObjectRequestSchema, CrudApiObjectJobResponseSchema
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import ProviderAPI,\
    LocalProviderApiView, CreateProviderResourceRequestSchema,\
    UpdateProviderResourceRequestSchema


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
    definitions = {
        'ListSiteNetworksResponseSchema': ListSiteNetworksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSiteNetworksRequestSchema)
    parameters_schema = ListSiteNetworksRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSiteNetworksResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List site_networks
        List site_networks

        # - filter by: tags
        # - filter by: vpc, Site, instance

        "attributes": {
          "configs": {
            "enable-dhcp": false,
            "name": "DCCTP-tst-FE-Rupar",
            "vlan": 568,
            "allocation-pools": [
              {
                "start": "10.102.189.75",
                "end": "10.102.189.100"
              }
            ],
            "private": false,
            "network-type": "vlan",
            "dns_nameservers": [
              "8.8.8.8",
              "8.8.8.4"
            ],
            "routes": [],
            "cidr": "10.102.189.0/25",
            "gateway": "10.102.189.1",
            "external": true
          }
        }
        """
        vpc_id = data.get('vpc', None)
        Site_id = data.get('Site', None)
        instance_id = data.get('instance', None)
        if vpc_id is not None:
            return self.get_linked_resources(controller, vpc_id, 'SiteNetwork', 'relation%')
        elif instance_id is not None:
            return self.get_linked_resources(controller, instance_id, 'SuperInstance', 'network')
        elif Site_id is not None:
            return self.get_resources_by_parent(controller, Site_id, 'Site')

        return self.get_resources(controller, **data)


class GetSiteNetworkParamsResponseSchema(ResourceResponseSchema):
    availability_zones = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetSiteNetworkResponseSchema(Schema):
    site_network = fields.Nested(GetSiteNetworkParamsResponseSchema, required=True, allow_none=True)


class GetSiteNetwork(ProviderSiteNetwork):
    definitions = {
        'GetSiteNetworkResponseSchema': GetSiteNetworkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetSiteNetworkResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get site_network
        Get site_network

        "attributes": {
          "configs": {
            "enable-dhcp": false,
            "name": "DCCTP-tst-FE-Rupar",
            "vlan": 568,
            "allocation-pools": [
              {
                "start": "10.102.189.75",
                "end": "10.102.189.100"
              }
            ],
            "private": false,
            "network-type": "vlan",
            "dns_nameservers": [
              "8.8.8.8",
              "8.8.8.4"
            ],
            "routes": [],
            "cidr": "10.102.189.0/25",
            "gateway": "10.102.189.1",
            "external": true
          }
        }
        """
        return self.get_resource(controller, oid)


class CreateSiteNetworkSubnetPoolResponseSchema(Schema):
    start = fields.String(required=True, example='10.138.200.20', default='10.138.200.20',
                          description='start pool ip address')
    end = fields.String(required=True, example='10.138.200.255', default='10.138.200.255',
                        description='end pool ip address')


class CreateSiteNetworkSubnetPoolsResponseSchema(Schema):
    vsphere = fields.Nested(CreateSiteNetworkSubnetPoolResponseSchema, required=False, many=True,
                            description='vsphere pool')
    openstack = fields.Nested(CreateSiteNetworkSubnetPoolResponseSchema, required=False, many=True,
                              description='openstack pool')


class CreateSiteNetworkSubnetRequestSchema(Schema):
    gateway = fields.String(required=False, example='10.102.189.1', description='subnet gateway. Ex. 10.102.189.1')
    cidr = fields.String(required=True, example='10.102.189.0/25', description='subnet cidr. Ex. 10.102.189.0/25')
    routes = fields.List(fields.String, required=False, description='subnet additional routes')
    allocation_pools = fields.Nested(CreateSiteNetworkSubnetPoolsResponseSchema, required=True,
                                     description='hypervisor pools')
    enable_dhcp = fields.Boolean(required=True, example=False, description='true if dhcp is enabled for the network')
    dns_nameservers = fields.List(fields.String(example='8.8.8.8'), required=False,
                                  description='dns nameservers list. Ex. ["8.8.8.8", "8.8.8.4"]')
    allocable = fields.Boolean(required=False, missing=True,
                               description='if False subnet can not be used to allocate ip in the newtwork')


class CreateSiteNetworkParamRequestSchema(CreateProviderResourceRequestSchema):
    site = fields.String(required=True, example='12', description='parent site id, uuid where create network')
    external = fields.Boolean(required=True, example=False, description='true if network is external')
    vlan = fields.Integer(required=True, example=567, description='network segmentation value. Ex. 567')
    dns_search = fields.String(required=True, example='site03.nivolapiemonte.it', description='network dns zone')
    proxy = fields.String(required=False, example='http://10.102.9.9:3128', description='http(s) proxy')
    zabbix_proxy = fields.String(required=False, example='10.102.9.9', description='zabbix proxy')


class CreateSiteNetworkRequestSchema(Schema):
    site_network = fields.Nested(CreateSiteNetworkParamRequestSchema)


class CreateSiteNetworkBodyRequestSchema(Schema):
    body = fields.Nested(CreateSiteNetworkRequestSchema, context='body')


class CreateSiteNetwork(ProviderSiteNetwork):
    definitions = {
        'CreateSiteNetworkRequestSchema': CreateSiteNetworkRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateSiteNetworkBodyRequestSchema)
    parameters_schema = CreateSiteNetworkRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create site_network
        Create site_network
        """
        return self.create_resource(controller, data)


class UpdateSiteNetworkParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateSiteNetworkRequestSchema(Schema):
    site_network = fields.Nested(UpdateSiteNetworkParamRequestSchema)


class UpdateSiteNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSiteNetworkRequestSchema, context='body')


class UpdateSiteNetwork(ProviderSiteNetwork):
    definitions = {
        'UpdateSiteNetworkRequestSchema': UpdateSiteNetworkRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateSiteNetworkBodyRequestSchema)
    parameters_schema = UpdateSiteNetworkRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update site_network
        Update site_network
        """
        return self.update_resource(controller, oid, data)


class DeleteSiteNetwork(ProviderSiteNetwork):
    definitions = {
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete site_network
        Delete site_network
        """
        return self.expunge_resource(controller, oid)


class AppendNetworkToSiteNetworkParamRequestSchema(UpdateProviderResourceRequestSchema):
    network_id = fields.String(required=True, example='12',
                               description='id, name or uuid of an existing openstack/vsphere network')


class AppendNetworkToSiteNetworkRequestSchema(Schema):
    site_network = fields.Nested(AppendNetworkToSiteNetworkParamRequestSchema)


class AppendNetworkToSiteNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AppendNetworkToSiteNetworkRequestSchema, context='body')


class AppendNetworkToSiteNetwork(ProviderSiteNetwork):
    definitions = {
        'AppendNetworkToSiteNetworkRequestSchema': AppendNetworkToSiteNetworkRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(AppendNetworkToSiteNetworkBodyRequestSchema)
    parameters_schema = AppendNetworkToSiteNetworkRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Append an existing vsphere dvpg or openstack network to site_network
        Append an existing vsphere dvpg or openstack network to site_network
        """
        data = data.get('site_network')
        container = controller.get_containers(container_type='Provider')[0][0]
        net = self.get_resource_reference(controller, oid, container=container.oid)
        return net.append_network(data)


#
# subnets
#
class GetSiteNetworkSubnetPoolResponseSchema(Schema):
    start = fields.String(required=True, example='10.138.200.20', default='10.138.200.20',
                          description='start pool ip address')
    end = fields.String(required=True, example='10.138.200.255', default='10.138.200.255',
                        description='end pool ip address')


class GetSiteNetworkSubnetResponseSchema(Schema):
    enable_dhcp = fields.Boolean(required=True, example=True, default=True, description='enable dhcp on subnet')
    dns_nameservers = fields.List(fields.String, required=False, example=['10.103.48.1', '10.103.48.2'],
                                  default=['10.103.48.1', '10.103.48.2'], description='dns list')
    allocable = fields.Boolean(required=True, example=True, default=True, description='tell if subnet is allocable')
    allocation_pools = fields.Nested(GetSiteNetworkSubnetPoolResponseSchema, required=True, many=True,
                                     description='openstack pool')
    allocation_pools_vs = fields.String(required=False, example='ipaddresspool-5', default='ipaddresspool-5',
                                        description='vsphere allocation pool id')
    router = fields.String(required=False, example='10.138.200.2', default='10.138.200.2',
                           description='subnet internal openstack router ip address')
    cidr = fields.String(required=True, example='10.138.200.0/21', default='10.138.200.0/21',
                         description='subnet cidr')
    gateway = fields.String(required=False, example='10.138.200.1', default='10.138.200.1',
                            description='subnet gateway')


class GetSiteNetworkSubnetsResponseSchema(Schema):
    subnets = fields.Nested(GetSiteNetworkSubnetResponseSchema, required=True, allow_none=True)


class GetSiteNetworkSubnets(ProviderSiteNetwork):
    definitions = {
        'GetSiteNetworkResponseSchema': GetSiteNetworkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetSiteNetworkResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get site_network subnets
        Get site_network subnets
        """
        container = controller.get_containers(container_type='Provider')[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        res = resource.get_subnets()
        return {'subnets': res}


class AddSiteNetworkSubnetPoolResponseSchema(Schema):
    start = fields.String(required=True, example='10.138.200.20', default='10.138.200.20',
                          description='start pool ip address')
    end = fields.String(required=True, example='10.138.200.255', default='10.138.200.255',
                        description='end pool ip address')


class AddSiteNetworkSubnetPoolsResponseSchema(Schema):
    vsphere = fields.Nested(AddSiteNetworkSubnetPoolResponseSchema, required=False, many=True,
                            description='vsphere pools. For the moment only one is supported')
    openstack = fields.Nested(AddSiteNetworkSubnetPoolResponseSchema, required=False, many=True,
                              description='openstack pools. For the moment only one is supported')


class AddSiteNetworkRouteResponseSchema(Schema):
    destination = fields.String(required=True, example='192.168.0.0/24', default='192.168.0.0/24',
                                description='route destination')
    nexthop = fields.String(required=True, example='192.168.0.1', default='192.168.0.1',
                            description='route next op')


class AddSiteNetworkSubnetResponseSchema(Schema):
    enable_dhcp = fields.Boolean(required=True, example=True, default=True, description='enable dhcp on subnet')
    dns_nameservers = fields.List(fields.String, required=False, example=['10.103.48.1', '10.103.48.2'],
                                  default=['10.103.48.1', '10.103.48.2'], description='dns list')
    allocable = fields.Boolean(required=False, example=True, default=True, missing=True,
                               description='tell if subnet is allocable')
    allocation_pools = fields.Nested(AddSiteNetworkSubnetPoolsResponseSchema, required=True,
                                     description='hypervisor pools')
    routes = fields.Nested(AddSiteNetworkRouteResponseSchema, required=False, many=True,
                           description='list of additional routes')
    # allocation_pools_vs = fields.String(required=False, example='ipaddresspool-5', default='ipaddresspool-5',
    #                                     description='vsphere allocation pool id')
    # router = fields.String(required=False, example='10.138.200.2', default='10.138.200.2',
    #                        description='subnet internal openstack router ip address')
    cidr = fields.String(required=True, example='10.138.200.0/21', default='10.138.200.0/21',
                         description='subnet cidr')
    gateway = fields.String(required=False, example='10.138.200.1', default='10.138.200.1',
                            description='subnet gateway')


class AddSiteNetworkSubnetsResponseSchema(Schema):
    subnets = fields.Nested(AddSiteNetworkSubnetResponseSchema, required=True, allow_none=True, many=True)
    orchestrator_tag = fields.String(required=False, missing='default',
                                     description='orchestrator tag. Use to select a subset of orchestrators where '
                                                 'security group must be created.')


class AddSiteNetworkSubnetsBodyResponseSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AppendNetworkToSiteNetworkRequestSchema, context='body')


class AddSiteNetworkSubnets(ProviderSiteNetwork):
    definitions = {
        'AddSiteNetworkSubnetsResponseSchema': AddSiteNetworkSubnetsResponseSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(AddSiteNetworkSubnetsBodyResponseSchema)
    parameters_schema = AddSiteNetworkSubnetsResponseSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Add site_network subnet
        Add site_network subnet
        """
        container = controller.get_containers(container_type='Provider')[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        return resource.add_subnets(data)


class DelSiteNetworkSubnetResponseSchema(Schema):
    cidr = fields.String(required=True, example='10.138.200.0/21', default='10.138.200.0/21',
                         description='subnet cidr')


class DelSiteNetworkSubnetsResponseSchema(Schema):
    subnets = fields.Nested(DelSiteNetworkSubnetResponseSchema, required=True, allow_none=True, many=True)
    orchestrator_tag = fields.String(required=False, missing='default',
                                     description='orchestrator tag. Use to select a subset of orchestrators where '
                                                 'security group must be created.')


class DelSiteNetworkSubnetsBodyResponseSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AppendNetworkToSiteNetworkRequestSchema, context='body')


class DelSiteNetworkSubnets(ProviderSiteNetwork):
    definitions = {
        'DelSiteNetworkSubnetsResponseSchema': DelSiteNetworkSubnetsResponseSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DelSiteNetworkSubnetsBodyResponseSchema)
    parameters_schema = DelSiteNetworkSubnetsResponseSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete site_network subnet
        Delete site_network subnet
        """
        container = controller.get_containers(container_type='Provider')[0][0]
        resource = self.get_resource_reference(controller, oid, container=container.oid)
        return resource.delete_subnets(data)


class SiteNetworkProviderAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # sites
            # - filter by: tags
            # - filter by: region
            ('%s/site_networks' % base, 'GET', ListSiteNetworks, {}),
            ('%s/site_networks/<oid>' % base, 'GET', GetSiteNetwork, {}),
            ('%s/site_networks' % base, 'POST', CreateSiteNetwork, {}),
            ('%s/site_networks/<oid>' % base, 'PUT', UpdateSiteNetwork, {}),
            ('%s/site_networks/<oid>' % base, 'DELETE', DeleteSiteNetwork, {}),

            # platform network
            ('%s/site_networks/<oid>/network' % base, 'PUT', AppendNetworkToSiteNetwork, {}),

            # subnets
            ('%s/site_networks/<oid>/subnets' % base, 'GET', GetSiteNetworkSubnets, {}),
            ('%s/site_networks/<oid>/subnets' % base, 'POST', AddSiteNetworkSubnets, {}),
            ('%s/site_networks/<oid>/subnets' % base, 'DELETE', DelSiteNetworkSubnets, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
