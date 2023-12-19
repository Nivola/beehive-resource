# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    ApiView,
)
from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup
from beehive_resource.plugins.provider.views import (
    ResourceApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.zabbix.views import ZabbixAPI, ZabbixApiView


class ZabbixUsergroupView(ZabbixApiView):
    tags = ["zabbix"]
    resclass = ZabbixUsergroup
    parentclass = None


class ListZabbixUsergroupsRequestSchema(ListResourcesRequestSchema):
    pass


class ListZabbixUsergroupsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListZabbixUsergroupsResponseSchema(PaginatedResponseSchema):
    usergroups = fields.Nested(ListZabbixUsergroupsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListZabbixUsergroups(ZabbixUsergroupView):
    summary = "List usergroups"
    description = "List usergroups"
    definitions = {
        "ListZabbixUsergroupsResponseSchema": ListZabbixUsergroupsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListZabbixUsergroupsRequestSchema)
    parameters_schema = ListZabbixUsergroupsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListZabbixUsergroupsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """List Zabbix usergroups"""
        return self.get_resources(controller, **data)


class GetZabbixUsergroupParamsResponseSchema(ResourceResponseSchema):
    usergroups = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetZabbixUsergroupResponseSchema(Schema):
    usergroup = fields.Nested(GetZabbixUsergroupParamsResponseSchema, required=True, allow_none=True)


class GetZabbixUsergroup(ZabbixUsergroupView):
    summary = "Get usergroup"
    description = "Get usergroup"
    definitions = {
        "GetZabbixUsergroupResponseSchema": GetZabbixUsergroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetZabbixUsergroupResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Zabbix usergroup"""
        return self.get_resource(controller, oid)


class CreateZabbixUsergroupParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test-name-usergroup", default="", description="Usergroup name")
    desc = fields.String(
        required=False,
        allow_none=True,
        default="Zabbix usergroup",
        description="The resource description - redefined required False",
    )
    hostgroup_id = fields.Integer(
        required=True,
        allow_none=False,
        description="Hostgroup id",
    )


class CreateZabbixUsergroupRequestSchema(Schema):
    usergroup = fields.Nested(CreateZabbixUsergroupParamRequestSchema)


class CreateZabbixUsergroupBodyRequestSchema(Schema):
    body = fields.Nested(CreateZabbixUsergroupRequestSchema, context="body")


class CreateZabbixUsergroup(ZabbixUsergroupView):
    summary = "Create usergroup"
    description = "Create usergroup"
    definitions = {
        "CreateZabbixUsergroupRequestSchema": CreateZabbixUsergroupRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateZabbixUsergroupBodyRequestSchema)
    parameters_schema = CreateZabbixUsergroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new usergroup to Zabbix"""
        return self.create_resource(controller, data)


class UpdateZabbixUsergroupTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="Test usergroup", default="", description="Usergroup name")
    desc = fields.String(
        required=False,
        example="This is the test usergroup",
        default="",
        description="Usergroup description",
    )


class UpdateZabbixUsergroupParamRequestSchema(UpdateProviderResourceRequestSchema):
    usergroups = fields.Nested(
        UpdateZabbixUsergroupTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator usergroups to link",
        allow_none=True,
    )


class UpdateZabbixUsergroupRequestSchema(Schema):
    usergroup = fields.Nested(UpdateZabbixUsergroupParamRequestSchema)


class UpdateZabbixUsergroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateZabbixUsergroupRequestSchema, context="body")


class UpdateZabbixUsergroup(ZabbixUsergroupView):
    summary = "Update usergroup"
    description = "Update usergroup"
    definitions = {
        "UpdateZabbixUsergroupRequestSchema": UpdateZabbixUsergroupRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateZabbixUsergroupBodyRequestSchema)
    parameters_schema = UpdateZabbixUsergroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Zabbix usergroup"""
        return self.update_resource(controller, oid, data)


class DeleteZabbixUsergroup(ZabbixUsergroupView):
    summary = "Delete usergroup"
    description = "Delete usergroup"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Zabbix usergroup"""
        return self.expunge_resource(controller, oid)


class ZabbixUsergroupAPI(ZabbixAPI):
    """Zabbix usergroup api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = ZabbixAPI.base
        rules = [
            ("%s/usergroups" % base, "GET", ListZabbixUsergroups, {}),
            ("%s/usergroups/<oid>" % base, "GET", GetZabbixUsergroup, {}),
            ("%s/usergroups" % base, "POST", CreateZabbixUsergroup, {}),
            ("%s/usergroups/<oid>" % base, "PUT", UpdateZabbixUsergroup, {}),
            ("%s/usergroups/<oid>" % base, "DELETE", DeleteZabbixUsergroup, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
