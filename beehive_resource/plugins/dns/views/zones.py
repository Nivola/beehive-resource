# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from marshmallow import Schema, fields

from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectSimpleResponseSchema,
)
from beehive_resource.plugins.dns.controller import DnsZone
from beehive_resource.plugins.dns.views import DnsAPI, DnsApiView
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema


class DnsZoneApiView(DnsApiView):
    resclass = DnsZone
    parentclass = None


class ListZoneRequestSchema(ListResourcesRequestSchema):
    pass


class ListZoneParamsResponseSchema(ResourceResponseSchema):
    pass


class ListZoneResponseSchema(PaginatedResponseSchema):
    zones = fields.Nested(ListZoneParamsResponseSchema, many=True, required=True, allow_none=True)


class ListZone(DnsZoneApiView):
    definitions = {
        "ListZoneResponseSchema": ListZoneResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListZoneRequestSchema)
    parameters_schema = ListZoneRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListZoneResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List zone
        List zone
        """
        return self.get_resources(controller, **data)


class GetZoneResponseSchema(Schema):
    zone = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetZone(DnsZoneApiView):
    definitions = {
        "GetZoneResponseSchema": GetZoneResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetZoneResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get zone
        Get zone
        """
        return self.get_resource(controller, oid)


class CreateZoneParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="site.prova.com", description="dns zone name")


class CreateZoneRequestSchema(Schema):
    zone = fields.Nested(CreateZoneParamRequestSchema)


class CreateZoneBodyRequestSchema(Schema):
    body = fields.Nested(CreateZoneRequestSchema, context="body")


class CreateZone(DnsZoneApiView):
    definitions = {
        "CreateZoneRequestSchema": CreateZoneRequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateZoneBodyRequestSchema)
    parameters_schema = CreateZoneRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """
        Create zone
        Create zone
        """
        return self.create_resource(controller, data)


class UpdateZoneParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="prova", description="dns zone name")


class UpdateZoneRequestSchema(Schema):
    zone = fields.Nested(UpdateZoneParamRequestSchema)


class UpdateZoneBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateZoneRequestSchema, context="body")


class UpdateZone(DnsZoneApiView):
    definitions = {
        "UpdateZoneRequestSchema": UpdateZoneRequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateZoneBodyRequestSchema)
    parameters_schema = UpdateZoneRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update zone
        Update zone
        """
        data.get("zone").pop("container")
        return self.update_resource(controller, oid, data)


class ImportZoneRecordParamRequestSchema(Schema):
    name = fields.String(required=True, example="prova", description="record host-name or alias")
    type = fields.String(required=True, example="prova", description="record type like A or CNAME")
    value = fields.String(
        required=True,
        example="prova",
        description="record value like ip address or host-name",
    )


class ImportZoneRecordRequestSchema(Schema):
    records = fields.Nested(ImportZoneRecordParamRequestSchema, many=True)


class ImportZoneRecordBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ImportZoneRecordRequestSchema, context="body")


class ImportZoneRecordResponseSchema(GetApiObjectRequestSchema):
    records = fields.Dict(required=True)


class ImportZoneRecord(DnsZoneApiView):
    definitions = {
        "ImportZoneRecordRequestSchema": ImportZoneRecordRequestSchema,
        "ImportZoneRecordResponseSchema": ImportZoneRecordResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ImportZoneRecordBodyRequestSchema)
    parameters_schema = ImportZoneRecordRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ImportZoneRecordResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Import zone record
        Import zone record
        """
        resource = self.get_resource_reference(controller, oid)
        res = resource.import_record(data.get("records"))
        return {"records": res}


class DeleteZoneRequestSchema(Schema):
    expunge = fields.Boolean(
        required=False,
        context="query",
        missing=False,
        description="If true expunge zone",
    )


class DeleteZoneRequest2Schema(GetApiObjectRequestSchema, DeleteZoneRequestSchema):
    pass


class DeleteZone(DnsZoneApiView):
    definitions = {
        "DeleteZoneRequestSchema": DeleteZoneRequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteZoneRequest2Schema)
    parameters_schema = DeleteZoneRequestSchema
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


class GetZoneNameserversRequestSchema(GetApiObjectRequestSchema):
    # container = fields.String(required=True, context='query', description='dns container id, uuid or name')
    pass


class GetZoneNameserverResponseSchema(Schema):
    start_nameserver = fields.String(required=True, example="prova", description="nameserver queried")
    ip_addr = fields.String(required=True, example="prova", description="ip of the nameserver returned")
    fqdn = fields.String(required=True, example="prova", description="fqdn of the nameserver returned")


class GetZoneNameserversResponseSchema(Schema):
    nameservers = fields.Nested(GetZoneNameserverResponseSchema, required=True, allow_none=True)


class GetZoneNameservers(DnsZoneApiView):
    definitions = {
        "GetZoneNameserversRequestSchema": GetZoneNameserversRequestSchema,
        "GetZoneNameserversResponseSchema": GetZoneNameserversResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetZoneNameserversRequestSchema)
    parameters_schema = GetZoneNameserversRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetZoneNameserversResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get zone nameservers
        Get zone nameservers
        """
        resource = self.get_resource_reference(controller, oid)
        # cid = data.get('container')
        # container = self.get_container(controller, cid)
        return {"nameservers": resource.get_nameservers()}


class GetZoneAuthorityRequestSchema(GetApiObjectRequestSchema):
    # container = fields.String(required=True, context='query', description='dns container id, uuid or name')
    pass


class GetZoneAuthorityResponseSchema(Schema):
    start_nameserver = fields.String(required=True, example="prova", description="nameserver queried")
    mname = fields.String(
        required=True,
        example="prova",
        description="The <domain-name> of the name server that was "
        "the original or primary source of data for this zone.",
    )
    rname = fields.String(
        required=True,
        example="prova",
        description="A <domain-name> which specifies the mailbox " "of the person responsible for this zone.",
    )
    serial = fields.String(
        required=True,
        example="prova",
        description="The unsigned 32 bit version number of the "
        "original copy of the zone. Zone transfers preserve this value. This value wraps and "
        "should be compared using sequence space arithmetic.",
    )
    refresh = fields.String(
        required=True,
        example="prova",
        description="A 32 bit time interval before the zone " "should be refreshed.",
    )
    retry = fields.String(
        required=True,
        example="prova",
        description="A 32 bit time interval that should elapse " "before a failed refresh should be retried.",
    )
    expire = fields.String(
        required=True,
        example="prova",
        description="A 32 bit time value that specifies the upper "
        "limit on the time interval that can elapse before the zone is no longer authoritative.",
    )
    minimum = fields.String(
        required=True,
        example="prova",
        description="The unsigned 32 bit minimum TTL field that " "should be exported with any RR from this zone.",
    )


class GetZoneAuthorityResponseSchema(Schema):
    authority = fields.Nested(GetZoneAuthorityResponseSchema, required=True, allow_none=True)


class GetZoneAuthority(DnsZoneApiView):
    definitions = {
        "GetZoneAuthorityRequestSchema": GetZoneAuthorityRequestSchema,
        "GetZoneAuthorityResponseSchema": GetZoneAuthorityResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetZoneAuthorityRequestSchema)
    parameters_schema = GetZoneAuthorityRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetZoneAuthorityResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get zone authority
        Get zone authority
        """
        # cid = data.get('container')
        # container = self.get_container(controller, cid)
        resource = self.get_resource_reference(controller, oid)
        return {"authority": resource.get_authority()}


class QueryZoneRequestSchema(GetApiObjectRequestSchema):
    name = fields.String(required=True, context="query", description="name of the host to resolve")
    # container = fields.String(required=True, context='query', description='dns container id, uuid or name')


class QueryZoneResponseSchema(Schema):
    start_nameserver = fields.String(required=True, example="prova", description="nameserver queried")
    ip_address = fields.String(
        required=False,
        example="prova",
        description="The ip address related to the fqdn",
    )
    base_fqdn = fields.String(required=False, example="prova", description="The base fqdn related to the fqdn")


class QueryZoneResponseSchema(Schema):
    records = fields.Nested(QueryZoneResponseSchema, required=True, allow_none=True)


class QueryZone(DnsZoneApiView):
    definitions = {
        "QueryZoneRequestSchema": QueryZoneRequestSchema,
        "QueryZoneResponseSchema": QueryZoneResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(QueryZoneRequestSchema)
    parameters_schema = QueryZoneRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": QueryZoneResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Query zone to get ip address or alias related to a fqdn
        Query zone to get ip address or alias related to a fqdn
        """
        # cid = data.get('container')
        name = data.get("name")
        # container = self.get_container(controller, cid)
        resource = self.get_resource_reference(controller, oid)
        return {"records": resource.query_remote_record(name)}


class DnsZoneAPI(DnsAPI):
    """Dns base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = DnsAPI.base
        rules = [
            ("%s/zones" % base, "GET", ListZone, {}),
            ("%s/zones/<oid>" % base, "GET", GetZone, {}),
            ("%s/zones" % base, "POST", CreateZone, {}),
            ("%s/zones/<oid>" % base, "PUT", UpdateZone, {}),
            ("%s/zones/<oid>/import" % base, "PUT", ImportZoneRecord, {}),
            ("%s/zones/<oid>" % base, "DELETE", DeleteZone, {}),
            ("%s/zones/<oid>/nameservers" % base, "GET", GetZoneNameservers, {}),
            ("%s/zones/<oid>/authority" % base, "GET", GetZoneAuthority, {}),
            ("%s/zones/<oid>/query" % base, "GET", QueryZone, {}),
        ]

        DnsAPI.register_api(module, rules, **kwargs)
