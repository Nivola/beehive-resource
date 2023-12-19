# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
    CrudApiObjectSimpleResponseSchema,
    ApiManagerError,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)
from marshmallow.validate import OneOf


class ProviderStackV2(LocalProviderApiView):
    resclass = ComputeStackV2
    parentclass = ComputeZone


class ListStackV2sRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone id or uuid")


class ListStackV2sResponseSchema(PaginatedResponseSchema):
    stacks = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListStackV2s(ProviderStackV2):
    summary = "List stacks"
    description = "List stacks"
    definitions = {
        "ListStackV2sResponseSchema": ListStackV2sResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListStackV2sRequestSchema)
    parameters_schema = ListStackV2sRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListStackV2sResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        return self.get_resources(controller, **data)


class GetStackV2ItemResponseSchema(ResourceResponseSchema):
    actions = fields.Nested(ResourceResponseSchema, required=False, many=False, allow_none=True)
    resources = fields.Nested(ResourceSmallResponseSchema, required=False, many=False, allow_none=True)


class GetStackV2ResponseSchema(Schema):
    stack = fields.Nested(GetStackV2ItemResponseSchema, required=True, allow_none=True)


class GetStackV2(ProviderStackV2):
    summary = "Get stack"
    description = "Get stack"
    definitions = {
        "GetStackV2ResponseSchema": GetStackV2ResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackV2ResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateStackV2InputRequestSchema(Schema):
    name = fields.String(required=True, example="test", description="input name")
    desc = fields.String(required=True, example="test", description="input description")
    value = fields.String(required=True, example="test", description="input value")


class CreateStackV2OutputRequestSchema(Schema):
    name = fields.String(required=True, example="test", description="output name")
    desc = fields.String(required=True, example="test", description="output description")
    value = fields.String(required=True, example="test", description="output value")


class CreateStackV2ActionResourceRequestSchema(Schema):
    type = fields.String(required=False, example="ComputeInstance", description="action resource type")
    oid = fields.String(required=False, example="123", description="action resource id")
    operation = fields.String(
        required=True,
        example="test",
        description="action resource operation to execute",
    )
    preserve = fields.Bool(
        required=False,
        example=True,
        missing=False,
        description="if True preserve resource when action is removed",
    )


class CreateStackV2ActionRequestSchema(Schema):
    name = fields.String(required=True, example="test", description="action name")
    desc = fields.String(required=True, example="test", description="action description")
    resource = fields.Nested(
        CreateStackV2ActionResourceRequestSchema,
        many=False,
        required=True,
        description="stack action resource",
    )
    params = fields.Dict(required=False, example='{"k1": "v1"}', description="action params")


class CreateStackV2ParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    inputs = fields.Nested(
        CreateStackV2InputRequestSchema,
        many=True,
        required=False,
        description="list of stack inputs",
    )
    outputs = fields.Nested(
        CreateStackV2OutputRequestSchema,
        many=True,
        required=True,
        description="list of stack outputs",
    )
    actions = fields.Nested(
        CreateStackV2ActionRequestSchema,
        many=True,
        required=True,
        description="list of stack actions",
    )


class CreateStackV2RequestSchema(Schema):
    stack = fields.Nested(CreateStackV2ParamRequestSchema)


class CreateStackV2BodyRequestSchema(Schema):
    body = fields.Nested(CreateStackV2RequestSchema, context="body")


class CreateStackV2(ProviderStackV2):
    summary = "Create stack"
    description = "Create stack"
    definitions = {
        "CreateStackV2RequestSchema": CreateStackV2RequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateStackV2BodyRequestSchema)
    parameters_schema = CreateStackV2RequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateStackV2ParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateStackV2RequestSchema(Schema):
    stack = fields.Nested(UpdateStackV2ParamRequestSchema)


class UpdateStackV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateStackV2RequestSchema, context="body")


class UpdateStackV2(ProviderStackV2):
    summary = "Update stack"
    description = "Update stack"
    definitions = {
        "UpdateStackV2RequestSchema": UpdateStackV2RequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateStackV2BodyRequestSchema)
    parameters_schema = UpdateStackV2RequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteStackV2RequestSchema(Schema):
    preserve = fields.Bool(
        required=False,
        example=True,
        missing=False,
        description="if True preserve resource when stack is removed",
    )


class DeleteStackV2(ProviderStackV2):
    summary = "Delete stack"
    description = "Delete stack"
    definitions = {
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
        "DeleteStackV2RequestSchema": DeleteStackV2RequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    parameters_schema = DeleteStackV2RequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid, **data)


class StackV2ProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/stacks" % base, "GET", ListStackV2s, {}),
            ("%s/stacks/<oid>" % base, "GET", GetStackV2, {}),
            ("%s/stacks" % base, "POST", CreateStackV2, {}),
            ("%s/stacks/<oid>" % base, "PUT", UpdateStackV2, {}),
            ("%s/stacks/<oid>" % base, "DELETE", DeleteStackV2, {}),
        ]
        kwargs["version"] = "v2.0"
        ProviderAPI.register_api(module, rules, **kwargs)
