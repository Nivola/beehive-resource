# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)
from beehive_resource.plugins.provider.entity.logging_role_mapping import (
    ComputeLoggingRoleMapping,
)
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
# LoggingRoleMapping
#
class ProviderLoggingRoleMapping(LocalProviderApiView):
    resclass = ComputeLoggingRoleMapping
    # parentclass = ComputeZone
    parentclass = ComputeLoggingSpace


class ListLoggingRoleMappingsRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context="query", description="instance id, uuid or name")
    parent = fields.String(required=False, default="", description="il padre Space id", allow_none=True)


class ListLoggingRoleMappingsResponseSchema(PaginatedResponseSchema):
    logging_role_mappings = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListLoggingRoleMappings(ProviderLoggingRoleMapping):
    summary = "List logging role mappings"
    description = "List logging role mappings"
    definitions = {
        "ListLoggingRoleMappingsResponseSchema": ListLoggingRoleMappingsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListLoggingRoleMappingsRequestSchema)
    parameters_schema = ListLoggingRoleMappingsRequestSchema
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": ListLoggingRoleMappingsResponseSchema,
            }
        }
    )

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "logging_role_mapping")
        return self.get_resources(controller, **data)


class GetLoggingRoleMappingParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetLoggingRoleMappingResponseSchema(Schema):
    logging_role_mapping = fields.Nested(GetLoggingRoleMappingParamsResponseSchema, required=True, allow_none=True)


class GetLoggingRoleMapping(ProviderLoggingRoleMapping):
    summary = "Get logging role mapping"
    description = "Get logging role mapping"
    definitions = {
        "GetLoggingRoleMappingResponseSchema": GetLoggingRoleMappingResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetLoggingRoleMappingResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateLoggingRoleMappingElkRoleMappingRequestSchema(Schema):
    name = fields.String(
        required=True,
        example="Test role_mapping",
        default="",
        description="RoleMapping name",
    )
    desc = fields.String(
        required=True,
        example="This is the test role_mapping",
        default="",
        description="RoleMapping description",
    )
    role_name = fields.String(required=True, example="test-role", default="", description="Role name")
    users_email = fields.String(required=True, example="test-users email", default="", description="Users email")
    realm_name = fields.String(required=True, example="test-realm name", default="", description="Realm name")


class CreateLoggingRoleMappingParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example="test", description="logging_role_mapping name")
    desc = fields.String(required=True, example="test", description="logging_role_mapping description")
    # compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    logging_space = fields.String(required=True, example="1", description="parent compute space id or uuid")
    norescreate = fields.Boolean(required=False, allow_none=True, description="don't create physical resource")
    elk_role_mapping = fields.Nested(
        CreateLoggingRoleMappingElkRoleMappingRequestSchema,
        required=True,
        description="elk role_mapping parameters",
    )


class CreateLoggingRoleMappingRequestSchema(Schema):
    logging_role_mapping = fields.Nested(CreateLoggingRoleMappingParamRequestSchema)


class CreateLoggingRoleMappingBodyRequestSchema(Schema):
    body = fields.Nested(CreateLoggingRoleMappingRequestSchema, context="body")


class CreateLoggingRoleMapping(ProviderLoggingRoleMapping):
    summary = "Create logging role mapping"
    description = "Create logging role mapping"
    definitions = {
        "CreateLoggingRoleMappingRequestSchema": CreateLoggingRoleMappingRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateLoggingRoleMappingBodyRequestSchema)
    parameters_schema = CreateLoggingRoleMappingRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteLoggingRoleMapping(ProviderLoggingRoleMapping):
    summary = "Delete logging role mapping"
    description = "Delete logging role mapping"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GetAppliedLoggingRoleMappingsResponseSchema(PaginatedResponseSchema):
    applied_logging_role_mappings = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ComputeLoggingRoleMappingAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/logging_role_mappings" % base, "GET", ListLoggingRoleMappings, {}),
            ("%s/logging_role_mappings/<oid>" % base, "GET", GetLoggingRoleMapping, {}),
            ("%s/logging_role_mappings" % base, "POST", CreateLoggingRoleMapping, {}),
            (
                "%s/logging_role_mappings/<oid>" % base,
                "DELETE",
                DeleteLoggingRoleMapping,
                {},
            ),
        ]

        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
