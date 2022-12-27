# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema,\
    ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from beehive_resource.plugins.vsphere.entity.nsx_dlr import NsxDlr


class VsphereNsxDlrApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = NsxDlr
    parentclass = NsxManager


class ListNsxDlrsRequestSchema(ListResourcesRequestSchema):
    pass


class ListNsxDlrsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNsxDlrsResponseSchema(PaginatedResponseSchema):
    nsx_dlrs = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNsxDlrs(VsphereNsxDlrApiView):
    definitions = {
        'ListNsxDlrsResponseSchema': ListNsxDlrsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxDlrsRequestSchema)
    parameters_schema = ListNsxDlrsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListNsxDlrsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List nsx_dlr
        List nsx_dlr
        """
        return self.get_resources(controller, **data)


class GetNsxDlrResponseSchema(Schema):
    nsx_dlr = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetNsxDlr(VsphereNsxDlrApiView):
    definitions = {
        'GetNsxDlrResponseSchema': GetNsxDlrResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetNsxDlrResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx_dlr
        Get nsx_dlr
        """
        return self.get_resource(controller, oid)


class CreateNsxDlrParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test')
    desc = fields.String(required=True, example='test')
    cidr = fields.String(required=True, example='10.102.34.90/32', description='ip set cidr')


class CreateNsxDlrRequestSchema(Schema):
    nsx_dlr = fields.Nested(CreateNsxDlrParamRequestSchema)


class CreateNsxDlrBodyRequestSchema(Schema):
    body = fields.Nested(CreateNsxDlrRequestSchema, context='body')


class CreateNsxDlr(VsphereNsxDlrApiView):
    definitions = {
        'CreateNsxDlrRequestSchema': CreateNsxDlrRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateNsxDlrBodyRequestSchema)
    parameters_schema = CreateNsxDlrRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Create nsx_dlr
        Create nsx_dlr
        """
        return self.create_resource(controller, oid, data)


class UpdateNsxDlrParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateNsxDlrRequestSchema(Schema):
    nsx_dlr = fields.Nested(UpdateNsxDlrParamRequestSchema)


class UpdateNsxDlrBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateNsxDlrRequestSchema, context='body')


class UpdateNsxDlr(VsphereNsxDlrApiView):
    definitions = {
        'UpdateNsxDlrRequestSchema': UpdateNsxDlrRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateNsxDlrBodyRequestSchema)
    parameters_schema = UpdateNsxDlrRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update nsx_dlr
        Update nsx_dlr
        """
        return self.update_resource(controller, data)


class DeleteNsxDlr(VsphereNsxDlrApiView):
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
        Delete nsx_dlr
        Delete nsx_dlr
        """
        return self.expunge_resource(controller, oid)


class VsphereNsxDlrAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + '/network'
        rules = [
            ('%s/nsx_dlrs' % base, 'GET', ListNsxDlrs, {}),
            ('%s/nsx_dlrs/<oid>' % base, 'GET', GetNsxDlr, {}),
            ('%s/nsx_dlrs' % base, 'POST', CreateNsxDlr, {}),
            ('%s/nsx_dlrs/<oid>' % base, 'PUT', UpdateNsxDlr, {}),
            ('%s/nsx_dlrs/<oid>' % base, 'DELETE', DeleteNsxDlr, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
