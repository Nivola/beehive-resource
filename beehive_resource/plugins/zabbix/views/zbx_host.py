# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.zabbix.entity.zbx_host import ZabbixHost
from beehive_resource.plugins.zabbix.views import ZabbixAPI, ZabbixApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema


class ZabbixHostApiView(ZabbixApiView):
    tags = ['zabbix']
    resclass = ZabbixHost
    parentclass = None


class ListHostsRequestSchema(ListResourcesRequestSchema):
    pass


class ListHostsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListHostsResponseSchema(PaginatedResponseSchema):
    # hosts = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)
    hosts = fields.List(fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True))


class ListHosts(ZabbixHostApiView):
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
        """List hosts
        """
        return self.get_resources(controller, **data)


class GetHostResponseSchema(Schema):
    host = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetHost(ZabbixHostApiView):
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
        """Get host
        """
        return self.get_resource(controller, oid)


class HostInterfaceRequestSchema(Schema):
    ip_addr = fields.String(required=True, example='192.168.3.1', default='127.0.0.1')
    port = fields.String(required=True, example='10050', default='10050')


class CreateHostParamRequestSchema(Schema):
    container = fields.String(required=True, example='1234', description='container id, uuid or name')
    name = fields.String(required=True, example='linux server')
    desc = fields.String(required=False, example='host description')
    status = fields.Integer(required=False, default=0,
                            description='0 - (default) monitored host; 1 - unmonitored host',
                            validate=OneOf([0, 1]))
    interfaces = fields.Nested(HostInterfaceRequestSchema, required=True, many=True, allow_none=True,
                               description='interfaces to be created for the host')
    groups = fields.List(fields.String(required=True, example='[\'50\', \'62\']', many=True, allow_none=True,
                                       description='ids of hostgroups to add the host to'))
    templates = fields.List(fields.String(required=False, example='[\'20045\']', many=True, allow_none=True,
                                          description='ids of templates to be linked to the host'))


class CreateHostRequestSchema(Schema):
    host = fields.Nested(CreateHostParamRequestSchema)


class CreateHostBodyRequestSchema(Schema):
    body = fields.Nested(CreateHostRequestSchema, context='body')


class CreateHost(ZabbixHostApiView):
    definitions = {
        'CreateHostRequestSchema': CreateHostRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateHostBodyRequestSchema)
    parameters_schema = CreateHostRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """Create host
        """
        return self.create_resource(controller, data)


class UpdateHostParamRequestSchema(Schema):
    name = fields.String(default='')
    desc = fields.String(default='')
    status = fields.Integer(default=0)


class UpdateHostRequestSchema(Schema):
    host = fields.Nested(UpdateHostParamRequestSchema)


class UpdateHostBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateHostRequestSchema, context='body')


class UpdateHost(ZabbixHostApiView):
    definitions = {
        'UpdateHostRequestSchema': UpdateHostRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateHostBodyRequestSchema)
    parameters_schema = UpdateHostRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """Update host
        """
        return self.update_resource(controller, oid, data)


class DeleteHost(ZabbixHostApiView):
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
        """Delete host
        """
        return self.expunge_resource(controller, oid)


class ZabbixHostAPI(ZabbixAPI):
    """Zabbix base platform api routes
    """
    @staticmethod
    def register_api(module, *args, **kwargs):
        base = ZabbixAPI.base
        rules = [
            ('%s/hosts' % base, 'GET', ListHosts, {}),
            ('%s/hosts/<oid>' % base, 'GET', GetHost, {}),
            ('%s/hosts' % base, 'POST', CreateHost, {}),
            ('%s/hosts/<oid>' % base, 'PUT', UpdateHost, {}),
            ('%s/hosts/<oid>' % base, 'DELETE', DeleteHost, {}),
        ]

        ZabbixAPI.register_api(module, rules, **kwargs)
