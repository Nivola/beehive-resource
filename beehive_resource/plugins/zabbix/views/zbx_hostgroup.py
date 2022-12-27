# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.zabbix.entity.zbx_hostgroup import ZabbixHostgroup
from beehive_resource.plugins.zabbix.views import ZabbixAPI, ZabbixApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema


class ZabbixHostgroupApiView(ZabbixApiView):
    tags = ['zabbix']
    resclass = ZabbixHostgroup
    parentclass = None


class ListHostgroupsRequestSchema(ListResourcesRequestSchema):
    pass


class ListHostgroupsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListHostgroupsResponseSchema(PaginatedResponseSchema):
    # hostgroups = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)
    hostgroups = fields.List(fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True))


class ListHostgroups(ZabbixHostgroupApiView):
    definitions = {
        'ListHostgroupsResponseSchema': ListHostgroupsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListHostgroupsRequestSchema)
    parameters_schema = ListHostgroupsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListHostgroupsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """List hostgroups
        """
        return self.get_resources(controller, **data)


class GetHostgroupResponseSchema(Schema):
    hostgroup = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetHostgroup(ZabbixHostgroupApiView):
    definitions = {
        'GetHostgroupResponseSchema': GetHostgroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetHostgroupResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """Get hostgroup
        """
        return self.get_resource(controller, oid)


class CreateHostgroupParamRequestSchema(Schema):
    container = fields.String(required=True, example='1234', description='container id, uuid or name')
    name = fields.String(required=True, default='linux servers')
    desc = fields.String(required=True, default='linux servers')


class CreateHostgroupRequestSchema(Schema):
    hostgroup = fields.Nested(CreateHostgroupParamRequestSchema)


class CreateHostgroupBodyRequestSchema(Schema):
    body = fields.Nested(CreateHostgroupRequestSchema, context='body')


class CreateHostgroup(ZabbixHostgroupApiView):
    definitions = {
        'CreateHostgroupRequestSchema': CreateHostgroupRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateHostgroupBodyRequestSchema)
    parameters_schema = CreateHostgroupRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """Create hostgroup
        """
        return self.create_resource(controller, data)


class UpdateHostgroupParamRequestSchema(Schema):
    name = fields.String(default='')
    desc = fields.String(default='')


class UpdateHostgroupRequestSchema(Schema):
    hostgroup = fields.Nested(UpdateHostgroupParamRequestSchema)


class UpdateHostgroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateHostgroupRequestSchema, context='body')


class UpdateHostgroup(ZabbixHostgroupApiView):
    definitions = {
        'UpdateHostgroupRequestSchema': UpdateHostgroupRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateHostgroupBodyRequestSchema)
    parameters_schema = UpdateHostgroupRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """Update hostgroup
        """
        return self.update_resource(controller, oid, data)


class DeleteHostgroup(ZabbixHostgroupApiView):
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
        """Delete hostgroup
        """
        return self.expunge_resource(controller, oid)


class ZabbixHostgroupAPI(ZabbixAPI):
    """Zabbix base platform api routes
    """
    @staticmethod
    def register_api(module, *args, **kwargs):
        base = ZabbixAPI.base
        rules = [
            ('%s/hostgroups' % base, 'GET', ListHostgroups, {}),
            ('%s/hostgroups/<oid>' % base, 'GET', GetHostgroup, {}),
            ('%s/hostgroups' % base, 'POST', CreateHostgroup, {}),
            ('%s/hostgroups/<oid>' % base, 'PUT', UpdateHostgroup, {}),
            ('%s/hostgroups/<oid>' % base, 'DELETE', DeleteHostgroup, {}),
        ]

        ZabbixAPI.register_api(module, rules, **kwargs)
