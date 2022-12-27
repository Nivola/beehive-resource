# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from marshmallow import Schema, fields
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import CrudApiObjectSimpleResponseSchema, GetApiObjectRequestSchema, SwaggerApiView, \
    PaginatedResponseSchema, ApiManagerError, PaginatedRequestQuerySchema
from beehive_resource.plugins.dns.controller import DnsZone, DnsRecordCname
from beehive_resource.plugins.dns.views import DnsAPI, DnsApiView
from beehive_resource.view import ResourceResponseSchema


class DnsRecordCnameApiView(DnsApiView):
    resclass = DnsRecordCname
    parentclass = DnsZone


class ListRecordCnameRequestSchema(PaginatedRequestQuerySchema):
    uuids = fields.String(context='query', description='comma separated list of uuid')
    tags = fields.String(context='query', description='comma separated list of tags')
    name = fields.String(context='query', example='host2', description='alias to associate')
    host_name = fields.String(context='query', example='host1', description='original host name')
    container = fields.String(context='query', description='resource container id, uuid or name')
    parent = fields.String(context='query', description='resource parent')
    state = fields.String(context='query', description='resource state like PENDING, BUILDING, ACTIVE, UPDATING, '
                                                        'ERROR, DELETING, DELETED, EXPUNGING, EXPUNGED, UNKNOWN')
    show_expired = fields.Boolean(context='query', required=False, example=True, missing=False,
                                  description='If True show expired resources')


class ListRecordCnameParamsResponseSchema(ResourceResponseSchema):
    pass


class ListRecordCnameResponseSchema(PaginatedResponseSchema):
    record_cnames = fields.Nested(ListRecordCnameParamsResponseSchema, many=True, required=True, allow_none=True)


class ListRecordCname(DnsRecordCnameApiView):
    definitions = {
        'ListRecordCnameResponseSchema': ListRecordCnameResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListRecordCnameRequestSchema)
    parameters_schema = ListRecordCnameRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListRecordCnameResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List record_cname
        List record_cname
        """
        if 'name' in data:
            name = data.pop('name')
            data['attribute'] = '%"host_name":"' + name + '"%'
        if 'ip_addr' in data:
            ip_addr = data.pop('ip_addr')
            data['attribute'] = '%"ip_address":"' + ip_addr + '"%'

        return self.get_resources(controller, **data)


class GetRecordCnameResponseSchema(Schema):
    record_cname = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetRecordCname(DnsRecordCnameApiView):
    definitions = {
        'GetRecordCnameResponseSchema': GetRecordCnameResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetRecordCnameResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get record_cname
        Get record_cname
        """
        return self.get_resource(controller, oid)


class CreateRecordCnameParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='host2', description='alias to associate')
    host_name = fields.String(required=True, example='host1', description='original host name')
    zone = fields.String(required=True, example='site.prova.com', description='dns zone')
    ttl = fields.Integer(required=False, example=600, missing=30, description='record time to live')
    force = fields.Boolean(required=False, example=True, missing=True,
                           description='If True force registration of record in dns')


class CreateRecordCnameRequestSchema(Schema):
    record_cname = fields.Nested(CreateRecordCnameParamRequestSchema)


class CreateRecordCnameBodyRequestSchema(Schema):
    body = fields.Nested(CreateRecordCnameRequestSchema, context='body')


class CreateRecordCname(DnsRecordCnameApiView):
    definitions = {
        'CreateRecordCnameRequestSchema': CreateRecordCnameRequestSchema,
        'CrudApiObjectSimpleResponseSchema': CrudApiObjectSimpleResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateRecordCnameBodyRequestSchema)
    parameters_schema = CreateRecordCnameRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectSimpleResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create record_cname
        Create record_cname
        """
        return self.create_resource(controller, data, check_name=False)


class UpdateRecordCnameParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='host2', description='alias to associate')
    host_name = fields.String(required=True, example='host1', description='original host name')
    zone = fields.String(required=True, example='site.prova.com', description='dns zone')
    ttl = fields.Integer(required=False, example=600, missing=30, description='record time to live')


class UpdateRecordCnameRequestSchema(Schema):
    record_cname = fields.Nested(UpdateRecordCnameParamRequestSchema)


class UpdateRecordCnameBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateRecordCnameRequestSchema, context='body')


class UpdateRecordCname(DnsRecordCnameApiView):
    definitions = {
        'UpdateRecordCnameRequestSchema': UpdateRecordCnameRequestSchema,
        'CrudApiObjectSimpleResponseSchema': CrudApiObjectSimpleResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateRecordCnameBodyRequestSchema)
    parameters_schema = UpdateRecordCnameRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectSimpleResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update record_cname
        Update record_cname
        """
        data = data.get('record_cname')

        # get existing record
        record = self.get_resource_reference(controller, oid)
        zone = record.get_parent()
        self.logger.warn(zone.name)
        self.logger.warn(data.get('zone'))
        if data.get('zone') != zone.name:
            raise ApiManagerError('Recorda %s does not exist in zone %s' % (oid, zone.name))

        # soft delete existing record
        self.delete_resource(controller, oid)

        # create new record
        data['name'] = record.name
        res = self.create_resource(controller, {'record_cname': data})

        return res


class DeleteRecordCnameRequestSchema(Schema):
    expunge = fields.Boolean(required=False, context='query', missing=False, description='If true expunge record a')


class DeleteRecordCnameRequest2Schema(GetApiObjectRequestSchema, DeleteRecordCnameRequestSchema):
    pass


class DeleteRecordCname(DnsRecordCnameApiView):
    definitions = {
        'DeleteRecordCnameRequestSchema': DeleteRecordCnameRequestSchema,
        'CrudApiObjectSimpleResponseSchema': CrudApiObjectSimpleResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteRecordCnameRequest2Schema)
    parameters_schema = DeleteRecordCnameRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectSimpleResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        expunge = data.get('expunge')
        if expunge is True:
            res = self.expunge_resource(controller, oid)
        else:
            res = self.delete_resource(controller, oid)
        return res


class DnsRecordCnameAPI(DnsAPI):
    """Dns base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = DnsAPI.base
        rules = [
            ('%s/record_cnames' % base, 'GET', ListRecordCname, {}),
            ('%s/record_cnames/<oid>' % base, 'GET', GetRecordCname, {}),
            ('%s/record_cnames' % base, 'POST', CreateRecordCname, {}),
            ('%s/record_cnames/<oid>' % base, 'PUT', UpdateRecordCname, {}),
            ('%s/record_cnames/<oid>' % base, 'DELETE', DeleteRecordCname, {}),
        ]

        DnsAPI.register_api(module, rules, **kwargs)
