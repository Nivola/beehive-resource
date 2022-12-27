# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_resource_pool import VsphereResourcePool
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster


class VsphereResourcePoolApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VsphereResourcePool
    parentclass = VsphereCluster


class ListResourcePoolsRequestSchema(ListResourcesRequestSchema):
    cluster = fields.String(context='query')


class ListResourcePoolsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListResourcePoolsResponseSchema(PaginatedResponseSchema):
    resource_pools = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListResourcePools(VsphereResourcePoolApiView):
    definitions = {
        'ListResourcePoolsResponseSchema': ListResourcePoolsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListResourcePoolsRequestSchema)
    parameters_schema = ListResourcePoolsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListResourcePoolsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List resource_pool
        List resource_pool
        """
        cluster = data.get('cluster', None)
        if cluster is not None:
            resp, total = self.controller.get_resources(
                parent=cluster, type=VsphereResourcePool.objdef)
            return self.format_paginated_response(
                resp, self.resclass.objname+'s', total, **data)
        else:
            return self.get_resources(controller, **data)

## get
class GetResourcePoolResponseSchema(Schema):
    resource_pool = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)

class GetResourcePool(VsphereResourcePoolApiView):
    definitions = {
        'GetResourcePoolResponseSchema': GetResourcePoolResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetResourcePoolResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get resource_pool
        Get resource_pool
        """
        return self.get_resource(controller, oid)


class CreateResourcePoolParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test')
    cluster = fields.String(required=True, example='989')
    cpu = fields.Integer(required=True, example=4000)
    memory = fields.Integer(required=True, example=10240)
    shares = fields.String(required=True, example='normal', validate=OneOf(['high', 'low', 'normal']))


class CreateResourcePoolRequestSchema(Schema):
    resource_pool = fields.Nested(CreateResourcePoolParamRequestSchema, required=True)


class CreateResourcePoolBodyRequestSchema(Schema):
    body = fields.Nested(CreateResourcePoolRequestSchema, context='body')


class CreateResourcePool(VsphereResourcePoolApiView):
    definitions = {
        'CreateResourcePoolRequestSchema': CreateResourcePoolRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateResourcePoolBodyRequestSchema)
    parameters_schema = CreateResourcePoolRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create resource_pool
        Create resource_pool
        """
        return self.create_resource(controller, data)


class UpdateResourcePoolParamRequestSchema(Schema):
    name = fields.String(example='test')
    desc = fields.String(example='test')
    enabled = fields.Boolean(example=True)


class UpdateResourcePoolRequestSchema(Schema):
    resource_pool = fields.Nested(UpdateResourcePoolParamRequestSchema)


class UpdateResourcePoolBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateResourcePoolRequestSchema, context='body')


class UpdateResourcePool(VsphereResourcePoolApiView):
    definitions = {
        'UpdateResourcePoolRequestSchema':UpdateResourcePoolRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateResourcePoolBodyRequestSchema)
    parameters_schema = UpdateResourcePoolRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update resource_pool
        Update resource_pool
        """
        return self.update_resource(controller, data)


class DeleteResourcePool(VsphereResourcePoolApiView):
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
        Delete resource_pool
        Delete resource_pool
        """
        return self.expunge_resource(controller, oid)


class GetRespoolRuntimeResponseSchema(Schema):
    resource_pool_runtime = fields.Dict(required=True)


class GetRespoolRuntime(VsphereResourcePoolApiView):
    definitions = {
        'GetRespoolRuntimeResponseSchema': GetRespoolRuntimeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetRespoolRuntimeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_runtime()
        return {'resource_pool_runtime':resp}


class GetRespoolStatsResponseSchema(Schema):
    resource_pool_stats = fields.Dict(required=True)


class GetRespoolStats(VsphereResourcePoolApiView):
    definitions = {
        'GetRespoolStatsResponseSchema': GetRespoolStatsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetRespoolStatsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_usage()
        return {'resource_pool_stats':resp}



'''
class GetRespoolServers(VsphereResourcePoolApiView):
    def get(self, controller, data, oid, oid, *args, **kwargs):
        container = self.get_container(controller, oid, authorize=False)
        obj = self.get_resource_pool(container, oid)
        data = obj.get_servers()
        resp = [d.info() for d in data]
        return resp
'''


class VsphereResourcePoolAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ('%s/resource_pools' % base, 'GET', ListResourcePools, {}),
            ('%s/resource_pools/<oid>' % base, 'GET', GetResourcePool, {}),
            ('%s/resource_pools' % base, 'POST', CreateResourcePool, {}),
            ('%s/resource_pools/<oid>' % base, 'PUT', UpdateResourcePool, {}),
            ('%s/resource_pools/<oid>' % base, 'DELETE', DeleteResourcePool, {}),
            ('%s/resource_pools/<oid>/runtime' % base, 'GET', GetRespoolRuntime, {}),
            ('%s/resource_pools/<oid>/stats' % base, 'GET', GetRespoolStats, {}),
            #('%s/respools/<oid>/servers' % base, 'GET', GetRespoolServers, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
