# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive.common.apimanager import PaginatedResponseSchema, \
    SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectJobResponseSchema
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet
from beehive_resource.plugins.openstack.views import OpenstackAPI, \
    OpenstackApiView
from beehive_resource.view import ResourceResponseSchema, \
    ListResourcesRequestSchema
from flasgger import fields, Schema
from marshmallow.decorators import validates_schema
from marshmallow.exceptions import ValidationError

from beecell.swagger import SwaggerHelper


class OpenstackSubnetApiView(OpenstackApiView):
    resclass = OpenstackSubnet
    parentclass = OpenstackNetwork


class ListSubnetsRequestSchema(ListResourcesRequestSchema):
    cidr = fields.String(required=False, context='query', example='10.102.10.0/24', description='subnet cidr')
    network = fields.String(required=False, example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='Network id or uuid')
    gateway_ip = fields.String(required=False, example='10.102.10.1', description='ip of the gateway')

    @validates_schema
    def validate_subnets(self, data, *args, **kvargs):
        keys = data.keys()
        if 'cidr' in keys or\
           'network' in keys or\
           'gateway_ip' in keys:
            if 'container' not in keys:
                raise ValidationError('container is required when cidr, network or gateway_ip are used as filter')


class ListSubnetsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSubnetsResponseSchema(PaginatedResponseSchema):
    subnets = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListSubnets(OpenstackSubnetApiView):
    tags = ['openstack']
    definitions = {
        'ListSubnetsResponseSchema': ListSubnetsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSubnetsRequestSchema)
    parameters_schema = ListSubnetsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSubnetsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List subnet
        List subnet
        """
        return self.get_resources(controller, **data)


class GetSubnetResponseSchema(Schema):
    subnet = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetSubnet(OpenstackSubnetApiView):
    tags = ['openstack']
    definitions = {
        'GetSubnetResponseSchema': GetSubnetResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetSubnetResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get subnet
        Get subnet
        """
        return self.get_resource(controller, oid)


class CreateSubnetAllocationPoolRequestSchema(Schema):
    start = fields.String(example='10.102.10.2', required=True, description='start ip')
    end = fields.String(example='10.102.10.13', required=True, description='end ip')


class CreateSubnetRouteRequestSchema(Schema):
    destination = fields.String(example='0.0.0.0/0', required=True, description='destination')
    nexthop = fields.String(example='123.45.67.89', required=True, description='nexthop')


class CreateSubnetParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, default='test')
    desc = fields.String(required=True, default='test')
    tags = fields.String(default='')
    project = fields.String(default='', required=True, example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='Project id or uuid')
    network = fields.String(default='', required=True, example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='Network id or uuid')
    gateway_ip = fields.String(example='10.102.10.1', required=False, allow_none=True,
                               description='ip of the gateway')
    cidr = fields.String(default='', required=True, example='10.102.10.0/24', description='network cidr')
    allocation_pools = fields.Nested(CreateSubnetAllocationPoolRequestSchema, required=False, many=True,
                                     allow_none=True, description='list of start and end ip of a pool')
    enable_dhcp = fields.Boolean(required=True, example=True, description='Set to true if DHCP is enabled and false '\
                                 'if DHCP is disabled.')
    host_routes = fields.Nested(CreateSubnetRouteRequestSchema, required=False, many=True, allow_none=True,
                                description='A list of host route dictionaries for the subnet.')
    dns_nameservers = fields.List(fields.String(example='8.8.8.8'), required=False, allow_none=True,
                                  description='A list of DNS name servers for the subnet. Specify each name server '\
                                              'as an IP address and separate multiple entries with a space.')
    service_types = fields.String(missing=None, required=False, example='compute:foo',
                                  description='The service types associated with the subnet. Ex. '
                                              '"compute:nova", "compute:foo,compute:foo2"')


class CreateSubnetRequestSchema(Schema):
    subnet = fields.Nested(CreateSubnetParamRequestSchema)


class CreateSubnetBodyRequestSchema(Schema):
    body = fields.Nested(CreateSubnetRequestSchema, context='body')


class CreateSubnet(OpenstackSubnetApiView):
    tags = ['openstack']
    definitions = {
        'CreateSubnetRequestSchema': CreateSubnetRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateSubnetBodyRequestSchema)
    parameters_schema = CreateSubnetRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create subnet
        Create subnet
        """
        return self.create_resource(controller, data)


class UpdateSubnetParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateSubnetRequestSchema(Schema):
    subnet = fields.Nested(UpdateSubnetParamRequestSchema)


class UpdateSubnetBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSubnetRequestSchema, context='body')


class UpdateSubnet(OpenstackSubnetApiView):
    tags = ['openstack']
    definitions = {
        'UpdateSubnetRequestSchema': UpdateSubnetRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateSubnetBodyRequestSchema)
    parameters_schema = UpdateSubnetRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update subnet
        Update subnet
        """
        return self.update_resource(controller, oid, data)


class DeleteSubnet(OpenstackSubnetApiView):
    tags = ['openstack']
    definitions = {
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class OpenstackSubnetAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/subnets' % base, 'GET', ListSubnets, {}),
            ('%s/subnets/<oid>' % base, 'GET', GetSubnet, {}),
            ('%s/subnets' % base, 'POST', CreateSubnet, {}),
            ('%s/subnets/<oid>' % base, 'PUT', UpdateSubnet, {}),
            ('%s/subnets/<oid>' % base, 'DELETE', DeleteSubnet, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
