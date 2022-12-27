# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_pg import VspherePg
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder


class VspherePgApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VspherePg
    parentclass = VsphereFolder


class ListPgsRequestSchema(ListResourcesRequestSchema):
    pass


class ListPgsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListPgsResponseSchema(PaginatedResponseSchema):
    pgs = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListPgs(VspherePgApiView):
    definitions = {
        'ListPgsResponseSchema': ListPgsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListPgsRequestSchema)
    parameters_schema = ListPgsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListPgsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List pg
        List pg
        """
        return self.get_resources(controller, **data)

## get
class GetPgResponseSchema(Schema):
    pg = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)

class GetPg(VspherePgApiView):
    definitions = {
        'GetPgResponseSchema': GetPgResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetPgResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get pg
        Get pg
        """
        return self.get_resource(controller, oid)

## create
class CreatePgParamRequestSchema(Schema):
    container = fields.String(required=True, example='12',
                              description='container id, uuid or name')
    name = fields.String(required=True, default='test')
    desc = fields.String(required=True, default='test')
    domain_id = fields.String(required=True, default='default')
    enabled = fields.Boolean(default=True)
    is_domain = fields.Boolean(default=False)
    parent = fields.String(default='')
    tags = fields.String(default='')

class CreatePgRequestSchema(Schema):
    pg = fields.Nested(CreatePgParamRequestSchema)

class CreatePgBodyRequestSchema(Schema):
    body = fields.Nested(CreatePgRequestSchema, context='body')

class CreatePg(VspherePgApiView):
    definitions = {
        'CreatePgRequestSchema': CreatePgRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreatePgBodyRequestSchema)
    parameters_schema = CreatePgRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Create pg
        Create pg
        """
        return self.create_resource(controller, oid, data)

## update
class UpdatePgParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)

class UpdatePgRequestSchema(Schema):
    pg = fields.Nested(UpdatePgParamRequestSchema)

class UpdatePgBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdatePgRequestSchema, context='body')

class UpdatePg(VspherePgApiView):
    definitions = {
        'UpdatePgRequestSchema': UpdatePgRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdatePgBodyRequestSchema)
    parameters_schema = UpdatePgRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update pg
        Update pg
        """
        return self.update_resource(controller, data)

## delete
class DeletePg(VspherePgApiView):
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

class VspherePgAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + '/network'
        rules = [
            ('%s/pgs' % base, 'GET', ListPgs, {}),
            ('%s/pgs/<oid>' % base, 'GET', GetPg, {}),
            ('%s/pgs' % base, 'POST', CreatePg, {}),
            ('%s/pgs/<oid>' % base, 'PUT', UpdatePg, {}),
            ('%s/pgs/<oid>' % base, 'DELETE', DeletePg, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
