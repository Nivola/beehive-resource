# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte
import ipaddress
from marshmallow import validates, ValidationError

from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectTaskResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge


class VsphereNsxEdgeApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = NsxEdge
    parentclass = NsxManager


class ListNsxEdgesRequestSchema(ListResourcesRequestSchema):
    pass


class ListNsxEdgesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNsxEdgesResponseSchema(PaginatedResponseSchema):
    nsx_edges = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNsxEdges(VsphereNsxEdgeApiView):
    summary = 'List nsx_edge'
    description = 'List nsx_edge'
    definitions = {
        'ListNsxEdgesResponseSchema': ListNsxEdgesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxEdgesRequestSchema)
    parameters_schema = ListNsxEdgesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListNsxEdgesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetNsxEdgeResponseSchema(Schema):
    nsx_edge = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetNsxEdge(VsphereNsxEdgeApiView):
    summary = 'Get nsx_edge'
    description = 'Get nsx_edge'
    definitions = {
        'GetNsxEdgeResponseSchema': GetNsxEdgeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetNsxEdgeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateNsxEdgeParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='edge name')
    desc = fields.String(required=True, example='test', description='edge description')
    datacenter = fields.String(required=True, example='123', description='datacenter id')
    cluster = fields.String(required=True, example='123', description='cluster id')
    datastore = fields.String(required=True, example='123', description='datastore id')
    uplink_dvpg = fields.String(required=True, example='123', description='uplink dvpg id')
    uplink_subnet_pool = fields.String(required=False, example='123', description='uplink ip pool mor id')
    uplink_ipaddress = fields.String(required=False, example='10.102.34.90', description='uplink address')
    uplink_gateway = fields.String(required=False, example='10.102.34.1', description='uplink gateway')
    uplink_prefix = fields.String(required=False, example='24', missing='24', description='uplink prefix')
    pwd = fields.String(required=True, example='test', description='admin user password')
    dns = fields.String(required=False, example='8.8.8.8 8.8.4.4', description='dns name server list')
    domain = fields.String(required=False, example='site01.nivolapiemonte.it', description='dns zone')
    size = fields.String(required=False, example='compact', missing='compact', description='appliance size')

    @validates("uplink_ipaddress")
    def validate_uplink_ipaddress(self, value):
        try:
            ipaddress.ip_address(value)
        except ValueError as ex:
            raise ValidationError(ex)

    @validates("uplink_gateway")
    def validate_uplink_gateway(self, value):
        try:
            ipaddress.ip_address(value)
        except ValueError as ex:
            raise ValidationError(ex)

    @validates("dns")
    def validate_dns(self, value):
        values = value.split(' ')
        try:
            [ipaddress.ip_address(v) for v in values]
        except ValueError as ex:
            raise ValidationError(ex)


class CreateNsxEdgeRequestSchema(Schema):
    nsx_edge = fields.Nested(CreateNsxEdgeParamRequestSchema)


class CreateNsxEdgeBodyRequestSchema(Schema):
    body = fields.Nested(CreateNsxEdgeRequestSchema, context='body')


class CreateNsxEdge(VsphereNsxEdgeApiView):
    summary = 'Create nsx_edge'
    description = 'Create nsx_edge'
    definitions = {
        'CreateNsxEdgeRequestSchema': CreateNsxEdgeRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateNsxEdgeBodyRequestSchema)
    parameters_schema = CreateNsxEdgeRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateNsxEdgeParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateNsxEdgeRequestSchema(Schema):
    nsx_edge = fields.Nested(UpdateNsxEdgeParamRequestSchema)


class UpdateNsxEdgeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateNsxEdgeRequestSchema, context='body')


class UpdateNsxEdge(VsphereNsxEdgeApiView):
    summary = 'Update nsx_edge'
    description = 'Update nsx_edge'
    definitions = {
        'UpdateNsxEdgeRequestSchema': UpdateNsxEdgeRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateNsxEdgeBodyRequestSchema)
    parameters_schema = UpdateNsxEdgeRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, data)


class DeleteNsxEdge(VsphereNsxEdgeApiView):
    summary = 'Delete nsx_edge'
    description = 'Delete nsx_edge'
    definitions = {
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class VsphereNsxEdgeAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + '/network'
        rules = [
            ('%s/nsx_edges' % base, 'GET', ListNsxEdges, {}),
            ('%s/nsx_edges/<oid>' % base, 'GET', GetNsxEdge, {}),
            ('%s/nsx_edges' % base, 'POST', CreateNsxEdge, {}),
            ('%s/nsx_edges/<oid>' % base, 'PUT', UpdateNsxEdge, {}),
            ('%s/nsx_edges/<oid>' % base, 'DELETE', DeleteNsxEdge, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
