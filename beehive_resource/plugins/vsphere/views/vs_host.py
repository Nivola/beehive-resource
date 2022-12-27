# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_host import VsphereHost
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster


class VsphereHostApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VsphereHost
    parentclass = VsphereCluster


class ListHostsRequestSchema(ListResourcesRequestSchema):
    cluster = fields.String(context='query')


class ListHostsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListHostsResponseSchema(PaginatedResponseSchema):
    hosts = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListHosts(VsphereHostApiView):
    definitions = {
        'ListHostsResponseSchema': ListHostsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListHostsRequestSchema)
    parameters_schema = ListHostsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListHostsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List host
        List host
        """
        cluster = data.get('cluster', None)
        if cluster is not None:
            resp, total = self.controller.get_resources(
                parent=cluster, type=VsphereHost.objdef)
            return self.format_paginated_response(
                resp, self.resclass.objname+'s', total, **data)
        else:
            return self.get_resources(controller, **data)

## get TODO: gestire dettaglio risposta
class GetHostResponseSchema(Schema):
    host = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)

class GetHost(VsphereHostApiView):
    definitions = {
        'GetHostResponseSchema': GetHostResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get host
        Get host
        """
        return self.get_resource(controller, oid)

## hardware TODO: gestire dettaglio risposta
class GetHostHardwareResponseSchema(Schema):
    host_hardware = fields.Dict(required=True)

class GetHostHardware(VsphereHostApiView):
    definitions = {
        'GetHostHardwareResponseSchema': GetHostHardwareResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostHardwareResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_hardware()
        return {'host_hardware':resp}

## runtime TODO: gestire dettaglio risposta
class GetHostRuntimeResponseSchema(Schema):
    host_runtime = fields.Dict(required=True)

class GetHostRuntime(VsphereHostApiView):
    definitions = {
        'GetHostRuntimeResponseSchema': GetHostRuntimeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostRuntimeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_runtime()
        return {'host_runtime':resp}

## config TODO: gestire dettaglio risposta
class GetHostConfigResponseSchema(Schema):
    host_config = fields.Dict(required=True)

class GetHostConfig(VsphereHostApiView):
    definitions = {
        'GetHostConfigResponseSchema': GetHostConfigResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostConfigResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_configuration()
        return {'host_config':resp}

## stats TODO: gestire dettaglio risposta
class GetHostStatsResponseSchema(Schema):
    host_stats = fields.Dict(required=True)

class GetHostStats(VsphereHostApiView):
    definitions = {
        'GetHostStatsResponseSchema': GetHostStatsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostStatsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_usage()
        return {'host_stats':resp}

## services TODO: gestire dettaglio risposta
class GetHostServicesResponseSchema(Schema):
    host_services = fields.Dict(required=True)

class GetHostServices(VsphereHostApiView):
    definitions = {
        'GetHostServicesResponseSchema': GetHostServicesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostServicesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_services()
        return {'host_services':resp}

'''
## servers
class GetHostServers(VsphereApiView):
    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource(controller, oid)
        data = obj.get_servers()
        resp = [d.info() for d in data]
        return resp
'''

class VsphereHostAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ('%s/hosts' % base, 'GET', ListHosts, {}),
            ('%s/hosts/<oid>' % base, 'GET', GetHost, {}),
            ('%s/hosts/<oid>/hardware' % base, 'GET', GetHostHardware, {}),
            ('%s/hosts/<oid>/runtime' % base, 'GET', GetHostRuntime, {}),
            ('%s/hosts/<oid>/config' % base, 'GET', GetHostConfig, {}),
            ('%s/hosts/<oid>/stats' % base, 'GET', GetHostStats, {}),
            ('%s/hosts/<oid>/services' % base, 'GET', GetHostServices, {}),
            #('%s/hosts/<oid>/servers' % base, 'GET', GetHostServers, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
