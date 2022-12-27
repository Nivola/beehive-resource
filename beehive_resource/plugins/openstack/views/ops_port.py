# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork


class OpenstackPortApiView(OpenstackApiView):
    resclass = OpenstackPort
    parentclass = OpenstackNetwork


class ListPortsRequestSchema(ListResourcesRequestSchema):
    pass


class ListPortsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListPortsResponseSchema(PaginatedResponseSchema):
    ports = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListPorts(OpenstackPortApiView):
    tags = ['openstack']
    definitions = {
        'ListPortsResponseSchema': ListPortsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListPortsRequestSchema)
    parameters_schema = ListPortsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListPortsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List port
        List port
        """
        return self.get_resources(controller, **data)


class GetPortResponseSchema(Schema):
    port = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetPort(OpenstackPortApiView):
    tags = ['openstack']
    definitions = {
        'GetPortResponseSchema': GetPortResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetPortResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get port
        Get port
        """
        return self.get_resource(controller, oid)


class CreatePortFixedIpRequestSchema(Schema):
    subnet_id = fields.String(default='', required=True, example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                              description='The id or uuid of the subnet')
    ip_address = fields.String(default='', required=False, example='10.0.0.2', description='The ip address')


class CreatePortBindingRequestSchema(Schema):
    host_id = fields.String(default='', example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='The ID of the host where the port is allocated. In some cases, different '
                                        'implementations can run on different hosts.')
    profile = fields.String(default='', example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='A dictionary that enables the application running on the host to pass and '
                                        'receive virtual network interface (VIF) port-specific information to the '
                                        'plug-in.')
    vnic_type = fields.String(default='', example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                              description='The virtual network interface card (vNIC) type that is bound to the '
                                          'neutron port. A valid value is normal, direct, or macvtap.')


class CreatePortParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='Name')
    desc = fields.String(required=False, example='test', default='', description='Description')
    tags = fields.String(default='', example='tag1,tag2', description='Comma separated list of tags')
    project = fields.String(default='', required=True, example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='Project id or uuid')
    network = fields.String(default='', required=True, example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                            description='Network id or uuid')
    fixed_ips = fields.Nested(CreatePortFixedIpRequestSchema, required=True, many=True, default=[],
                              description='Specify the subnet', allow_none=True)
    binding = fields.Nested(CreatePortBindingRequestSchema, default={}, allow_none=True)
    device_owner = fields.String(default='', example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                                 description='The uuid of the entity that uses this port. For example, a DHCP agent.')
    device_id = fields.String(default='', example='a0304c3a-4f08-4c43-88af-d796509c97d2',
                              description='The id or uuid of the device that uses this port. For example, a virtual '
                                          'server.')
    security_groups = fields.List(fields.String(example='a0304c3a-4f08-4c43-88af-d796509c97d2'), default=[],
                                  description='list of security group id or uuid')
    mac_address = fields.String(default='', example='3c:97:0e:11:39:72', description='Mac Address')


class CreatePortRequestSchema(Schema):
    port = fields.Nested(CreatePortParamRequestSchema)


class CreatePortBodyRequestSchema(Schema):
    body = fields.Nested(CreatePortRequestSchema, context='body')


class CreatePort(OpenstackPortApiView):
    tags = ['openstack']
    definitions = {
        'CreatePortRequestSchema': CreatePortRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreatePortBodyRequestSchema)
    parameters_schema = CreatePortRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create port
        Create port
        """
        return self.create_resource(controller, data)


class UpdatePortParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdatePortRequestSchema(Schema):
    port = fields.Nested(UpdatePortParamRequestSchema)


class UpdatePortBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdatePortRequestSchema, context='body')


class UpdatePort(OpenstackPortApiView):
    tags = ['openstack']
    definitions = {
        'UpdatePortRequestSchema':UpdatePortRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdatePortBodyRequestSchema)
    parameters_schema = UpdatePortRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update port
        Update port
        """
        return self.update_resource(controller, oid, data)


class DeletePort(OpenstackPortApiView):
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


class OpenstackPortAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/ports' % base, 'GET', ListPorts, {}),
            ('%s/ports/<oid>' % base, 'GET', GetPort, {}),
            ('%s/ports' % base, 'POST', CreatePort, {}),
            ('%s/ports/<oid>' % base, 'PUT', UpdatePort, {}),
            ('%s/ports/<oid>' % base, 'DELETE', DeletePort, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
