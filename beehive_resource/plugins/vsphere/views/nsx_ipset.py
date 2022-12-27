# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet


class VsphereNsxIpSetApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = NsxIpSet
    parentclass = NsxManager


class ListNsxIpSetsRequestSchema(ListResourcesRequestSchema):
    pass


class ListNsxIpSetsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNsxIpSetsResponseSchema(PaginatedResponseSchema):
    nsx_ipsets = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNsxIpSets(VsphereNsxIpSetApiView):
    definitions = {
        'ListNsxIpSetsResponseSchema': ListNsxIpSetsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxIpSetsRequestSchema)
    parameters_schema = ListNsxIpSetsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListNsxIpSetsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List nsx_ipset
        List nsx_ipset
        """
        return self.get_resources(controller, **data)

## get
class GetNsxIpSetResponseSchema(Schema):
    nsx_ipset = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)

class GetNsxIpSet(VsphereNsxIpSetApiView):
    definitions = {
        'GetNsxIpSetResponseSchema': GetNsxIpSetResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetNsxIpSetResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx_ipset
        Get nsx_ipset
        """
        return self.get_resource(controller, oid)


class CreateNsxIpSetParamRequestSchema(Schema):
    container = fields.String(required=True, example='12',
                              description='container id, uuid or name')
    name = fields.String(required=True, example='test')
    desc = fields.String(required=True, example='test')
    cidr = fields.String(required=True, example='10.102.34.90/32',
                         description='ip set cidr')


class CreateNsxIpSetRequestSchema(Schema):
    nsx_ipset = fields.Nested(CreateNsxIpSetParamRequestSchema, required=True)


class CreateNsxIpSetBodyRequestSchema(Schema):
    body = fields.Nested(CreateNsxIpSetRequestSchema, context='body')


class CreateNsxIpSet(VsphereNsxIpSetApiView):
    definitions = {
        'CreateNsxIpSetRequestSchema': CreateNsxIpSetRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateNsxIpSetBodyRequestSchema)
    parameters_schema = CreateNsxIpSetRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create nsx_ipset
        Create nsx_ipset
        """
        return self.create_resource(controller, data)


class UpdateNsxIpSetParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)

class UpdateNsxIpSetRequestSchema(Schema):
    nsx_ipset = fields.Nested(UpdateNsxIpSetParamRequestSchema)

class UpdateNsxIpSetBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateNsxIpSetRequestSchema, context='body')

class UpdateNsxIpSet(VsphereNsxIpSetApiView):
    definitions = {
        'UpdateNsxIpSetRequestSchema': UpdateNsxIpSetRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateNsxIpSetBodyRequestSchema)
    parameters_schema = UpdateNsxIpSetRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update nsx_ipset
        Update nsx_ipset
        """
        return self.update_resource(controller, data)

## delete
class DeleteNsxIpSet(VsphereNsxIpSetApiView):
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
        """
        Delete nsx_ipset
        Delete nsx_ipset
        """
        return self.expunge_resource(controller, oid)

class VsphereNsxIpSetAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + '/network'
        rules = [
            ('%s/nsx_ipsets' % base, 'GET', ListNsxIpSets, {}),
            ('%s/nsx_ipsets/<oid>' % base, 'GET', GetNsxIpSet, {}),
            ('%s/nsx_ipsets' % base, 'POST', CreateNsxIpSet, {}),
            ('%s/nsx_ipsets/<oid>' % base, 'PUT', UpdateNsxIpSet, {}),
            ('%s/nsx_ipsets/<oid>' % base, 'DELETE', DeleteNsxIpSet, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
