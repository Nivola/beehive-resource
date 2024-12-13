# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)
from beehive_resource.plugins.provider.entity.logging_role import ComputeLoggingRole
from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
)
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper


#
# LoggingRole
#
class ProviderLoggingRole(LocalProviderApiView):
    resclass = ComputeLoggingRole
    # parentclass = ComputeZone
    parentclass = ComputeLoggingSpace


class ListLoggingRolesRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context="query", description="instance id, uuid or name")
    parent = fields.String(required=False, default="", description="il padre Space id", allow_none=True)


class ListLoggingRolesResponseSchema(PaginatedResponseSchema):
    logging_roles = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListLoggingRoles(ProviderLoggingRole):
    summary = "List logging roles"
    description = "List logging roles"
    definitions = {
        "ListLoggingRolesResponseSchema": ListLoggingRolesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListLoggingRolesRequestSchema)
    parameters_schema = ListLoggingRolesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListLoggingRolesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "logging_role")
        return self.get_resources(controller, **data)


class GetLoggingRoleParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetLoggingRoleResponseSchema(Schema):
    logging_role = fields.Nested(GetLoggingRoleParamsResponseSchema, required=True, allow_none=True)


class GetLoggingRole(ProviderLoggingRole):
    summary = "Get logging role"
    description = "Get logging role"
    definitions = {
        "GetLoggingRoleResponseSchema": GetLoggingRoleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetLoggingRoleResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateLoggingRoleElkRoleRequestSchema(Schema):
    name = fields.String(required=True, example="Test role", default="", description="Role name")
    desc = fields.String(
        required=True,
        example="This is the test role",
        default="",
        description="Role description",
    )
    indice = fields.String(required=True, example="test-indice-*", default="", description="Index pattern")
    space_id = fields.String(required=True, example="test-space", default="", description="Space id")


class CreateLoggingRoleParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example="test", description="logging_role name")
    desc = fields.String(required=True, example="test", description="logging_role description")
    # compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    logging_space = fields.String(required=True, example="1", description="parent compute space id or uuid")
    norescreate = fields.Boolean(required=False, allow_none=True, description="don't create physical resource")
    elk_role = fields.Nested(
        CreateLoggingRoleElkRoleRequestSchema,
        required=True,
        description="elk role parameters",
    )


class CreateLoggingRoleRequestSchema(Schema):
    logging_role = fields.Nested(CreateLoggingRoleParamRequestSchema)


class CreateLoggingRoleBodyRequestSchema(Schema):
    body = fields.Nested(CreateLoggingRoleRequestSchema, context="body")


class CreateLoggingRole(ProviderLoggingRole):
    summary = "Create logging role"
    description = "Create logging role"
    definitions = {
        "CreateLoggingRoleRequestSchema": CreateLoggingRoleRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateLoggingRoleBodyRequestSchema)
    parameters_schema = CreateLoggingRoleRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteLoggingRole(ProviderLoggingRole):
    summary = "Delete logging role"
    description = "Delete logging role"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GetAppliedLoggingRolesResponseSchema(PaginatedResponseSchema):
    applied_logging_roles = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ComputeLoggingRoleAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/logging_roles" % base, "GET", ListLoggingRoles, {}),
            ("%s/logging_roles/<oid>" % base, "GET", GetLoggingRole, {}),
            ("%s/logging_roles" % base, "POST", CreateLoggingRole, {}),
            ("%s/logging_roles/<oid>" % base, "DELETE", DeleteLoggingRole, {}),
        ]

        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
