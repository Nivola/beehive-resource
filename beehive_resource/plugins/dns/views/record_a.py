# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from marshmallow import Schema, fields
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    CrudApiObjectSimpleResponseSchema,
    GetApiObjectRequestSchema,
    SwaggerApiView,
    PaginatedResponseSchema,
    ApiManagerError,
    PaginatedRequestQuerySchema,
)
from beehive_resource.plugins.dns.controller import DnsZone, DnsRecordA
from beehive_resource.plugins.dns.views import DnsAPI, DnsApiView
from beehive_resource.view import ResourceResponseSchema


class DnsRecordAApiView(DnsApiView):
    resclass = DnsRecordA
    parentclass = DnsZone


class ListRecordARequestSchema(PaginatedRequestQuerySchema):
    uuids = fields.String(context="query", description="comma separated list of uuid")
    tags = fields.String(context="query", description="comma separated list of tags")
    name = fields.String(context="query", description="recorda name")
    ip_addr = fields.String(context="query", description="recorda ip address")
    container = fields.String(context="query", description="resource container id, uuid or name")
    parent = fields.String(context="query", description="resource parent")
    state = fields.String(
        context="query",
        description="resource state like PENDING, BUILDING, ACTIVE, UPDATING, "
        "ERROR, DELETING, DELETED, EXPUNGING, EXPUNGED, UNKNOWN",
    )
    show_expired = fields.Boolean(
        context="query",
        required=False,
        example=True,
        missing=False,
        description="If True show expired resources",
    )


class ListRecordAParamsResponseSchema(ResourceResponseSchema):
    pass


class ListRecordAResponseSchema(PaginatedResponseSchema):
    recordas = fields.Nested(ListRecordAParamsResponseSchema, many=True, required=True, allow_none=True)


class ListRecordA(DnsRecordAApiView):
    definitions = {
        "ListRecordAResponseSchema": ListRecordAResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListRecordARequestSchema)
    parameters_schema = ListRecordARequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListRecordAResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List recorda
        List recorda
        """
        if "name" in data:
            name = data.pop("name")
            data["attribute"] = '%"host_name":"' + name + '"%'
        if "ip_addr" in data:
            ip_addr = data.pop("ip_addr")
            data["attribute"] = '%"ip_address":"' + ip_addr + '"%'

        return self.get_resources(controller, **data)


class GetRecordAResponseSchema(Schema):
    recorda = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetRecordA(DnsRecordAApiView):
    definitions = {
        "GetRecordAResponseSchema": GetRecordAResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetRecordAResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get recorda
        Get recorda
        """
        return self.get_resource(controller, oid)


class CreateRecordAParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    ip_addr = fields.String(required=True, example="10.102.189.89", description="ip address to associate")
    name = fields.String(required=True, example="test", description="host name")
    zone = fields.String(required=True, example="site.prova.com", description="dns zone")
    ttl = fields.Integer(required=False, example=600, missing=30, description="record time to live")
    force = fields.Boolean(
        required=False,
        example=True,
        missing=True,
        description="If True force registration of record in dns",
    )


class CreateRecordARequestSchema(Schema):
    recorda = fields.Nested(CreateRecordAParamRequestSchema)


class CreateRecordABodyRequestSchema(Schema):
    body = fields.Nested(CreateRecordARequestSchema, context="body")


class CreateRecordA(DnsRecordAApiView):
    definitions = {
        "CreateRecordARequestSchema": CreateRecordARequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateRecordABodyRequestSchema)
    parameters_schema = CreateRecordARequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """
        Create recorda
        Create recorda
        """
        return self.create_resource(controller, data, check_name=False)


class UpdateRecordAParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test", description="host name")
    ip_addr = fields.String(required=True, example="10.102.189.89", description="ip address to associate")
    zone = fields.String(required=True, example="site.prova.com", description="dns zone")
    ttl = fields.Integer(required=False, example=600, missing=30, description="record time to live")


class UpdateRecordARequestSchema(Schema):
    recorda = fields.Nested(UpdateRecordAParamRequestSchema)


class UpdateRecordABodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateRecordARequestSchema, context="body")


class UpdateRecordA(DnsRecordAApiView):
    definitions = {
        "UpdateRecordARequestSchema": UpdateRecordARequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateRecordABodyRequestSchema)
    parameters_schema = UpdateRecordARequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update recorda
        Update recorda
        """
        data = data.get("recorda")

        # get existing record
        record = self.get_resource_reference(controller, oid)
        zone = record.get_parent()
        self.logger.warn(zone.name)
        self.logger.warn(data.get("zone"))
        if data.get("zone") != zone.name:
            raise ApiManagerError("Recorda %s does not exist in zone %s" % (oid, zone.name))

        # soft delete existing record
        self.delete_resource(controller, oid)

        # create new record
        data["name"] = record.name
        res = self.create_resource(controller, {"recorda": data})

        return res


class DeleteRecordARequestSchema(Schema):
    expunge = fields.Boolean(
        required=False,
        context="query",
        missing=False,
        description="If true expunge record a",
    )


class DeleteRecordARequest2Schema(GetApiObjectRequestSchema, DeleteRecordARequestSchema):
    pass


class DeleteRecordA(DnsRecordAApiView):
    definitions = {
        "DeleteRecordARequestSchema": DeleteRecordARequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteRecordARequest2Schema)
    parameters_schema = DeleteRecordARequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        expunge = data.get("expunge")
        if expunge is True:
            res = self.expunge_resource(controller, oid)
        else:
            res = self.delete_resource(controller, oid)
        return res


class DnsRecordAAPI(DnsAPI):
    """Dns base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = DnsAPI.base
        rules = [
            ("%s/recordas" % base, "GET", ListRecordA, {}),
            ("%s/recordas/<oid>" % base, "GET", GetRecordA, {}),
            ("%s/recordas" % base, "POST", CreateRecordA, {}),
            ("%s/recordas/<oid>" % base, "PUT", UpdateRecordA, {}),
            ("%s/recordas/<oid>" % base, "DELETE", DeleteRecordA, {}),
        ]

        DnsAPI.register_api(module, rules, **kwargs)
