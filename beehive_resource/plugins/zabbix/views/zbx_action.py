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
from beehive_resource.plugins.zabbix.entity.zbx_action import ZabbixAction
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


class ZabbixActionView(ZabbixApiView):
    tags = ["zabbix"]
    resclass = ZabbixAction
    parentclass = None


class ListZabbixActionsRequestSchema(ListResourcesRequestSchema):
    pass


class ListZabbixActionsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListZabbixActionsResponseSchema(PaginatedResponseSchema):
    actions = fields.Nested(ListZabbixActionsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListZabbixActions(ZabbixActionView):
    summary = "List actions"
    description = "List actions"
    definitions = {
        "ListZabbixActionsResponseSchema": ListZabbixActionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListZabbixActionsRequestSchema)
    parameters_schema = ListZabbixActionsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListZabbixActionsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """List Zabbix actions"""
        return self.get_resources(controller, **data)


class GetZabbixActionParamsResponseSchema(ResourceResponseSchema):
    actions = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetZabbixActionResponseSchema(Schema):
    action = fields.Nested(GetZabbixActionParamsResponseSchema, required=True, allow_none=True)


class GetZabbixAction(ZabbixActionView):
    summary = "Get action"
    description = "Get action"
    definitions = {
        "GetZabbixActionResponseSchema": GetZabbixActionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetZabbixActionResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Zabbix action"""
        return self.get_resource(controller, oid)


class CreateZabbixActionParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test-name-action", default="", description="Action name")
    desc = fields.String(
        required=False,
        allow_none=True,
        default="Zabbix action",
        description="The resource description - redefined required False",
    )
    usrgrp_id = fields.Integer(
        required=True,
        allow_none=False,
        description="Usergroup id",
    )
    hostgroup_id = fields.Integer(
        required=True,
        allow_none=False,
        description="Hostgroup id",
    )


class CreateZabbixActionRequestSchema(Schema):
    action = fields.Nested(CreateZabbixActionParamRequestSchema)


class CreateZabbixActionBodyRequestSchema(Schema):
    body = fields.Nested(CreateZabbixActionRequestSchema, context="body")


class CreateZabbixAction(ZabbixActionView):
    summary = "Create action"
    description = "Create action"
    definitions = {
        "CreateZabbixActionRequestSchema": CreateZabbixActionRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateZabbixActionBodyRequestSchema)
    parameters_schema = CreateZabbixActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new action to Zabbix"""
        return self.create_resource(controller, data)


class UpdateZabbixActionTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="Test action", default="", description="Action name")
    desc = fields.String(
        required=False,
        example="This is the test action",
        default="",
        description="Action description",
    )


class UpdateZabbixActionParamRequestSchema(UpdateProviderResourceRequestSchema):
    actions = fields.Nested(
        UpdateZabbixActionTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator actions to link",
        allow_none=True,
    )


class UpdateZabbixActionRequestSchema(Schema):
    action = fields.Nested(UpdateZabbixActionParamRequestSchema)


class UpdateZabbixActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateZabbixActionRequestSchema, context="body")


class UpdateZabbixAction(ZabbixActionView):
    summary = "Update action"
    description = "Update action"
    definitions = {
        "UpdateZabbixActionRequestSchema": UpdateZabbixActionRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateZabbixActionBodyRequestSchema)
    parameters_schema = UpdateZabbixActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Zabbix action"""
        return self.update_resource(controller, oid, data)


class DeleteZabbixAction(ZabbixActionView):
    summary = "Delete action"
    description = "Delete action"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Zabbix action"""
        return self.expunge_resource(controller, oid)


class ZabbixActionAPI(ZabbixAPI):
    """Zabbix action api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = ZabbixAPI.base
        rules = [
            ("%s/actions" % base, "GET", ListZabbixActions, {}),
            ("%s/actions/<oid>" % base, "GET", GetZabbixAction, {}),
            ("%s/actions" % base, "POST", CreateZabbixAction, {}),
            ("%s/actions/<oid>" % base, "PUT", UpdateZabbixAction, {}),
            ("%s/actions/<oid>" % base, "DELETE", DeleteZabbixAction, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
