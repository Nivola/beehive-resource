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
from beehive_resource.plugins.elk.entity.elk_role_mapping import ElkRoleMapping
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
from beehive_resource.plugins.elk.views import ElkAPI, ElkApiView


class ElkRoleMappingView(ElkApiView):
    tags = ["elk"]
    resclass = ElkRoleMapping
    parentclass = None


class ListElkRoleMappingsRequestSchema(ListResourcesRequestSchema):
    pass


class ListElkRoleMappingsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListElkRoleMappingsResponseSchema(PaginatedResponseSchema):
    role_mappings = fields.Nested(
        ListElkRoleMappingsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListElkRoleMappings(ElkRoleMappingView):
    summary = "List role mappings"
    description = "List role mappings"
    definitions = {
        "ListElkRoleMappingsResponseSchema": ListElkRoleMappingsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListElkRoleMappingsRequestSchema)
    parameters_schema = ListElkRoleMappingsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListElkRoleMappingsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """List Elk role mappings"""
        return self.get_resources(controller, **data)


class GetElkRoleMappingParamsResponseSchema(ResourceResponseSchema):
    role_mappings = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetElkRoleMappingResponseSchema(Schema):
    role_mapping = fields.Nested(GetElkRoleMappingParamsResponseSchema, required=True, allow_none=True)


class GetElkRoleMapping(ElkRoleMappingView):
    summary = "Get role mapping"
    description = "Get role mapping"
    definitions = {
        "GetElkRoleMappingResponseSchema": GetElkRoleMappingResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetElkRoleMappingResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Elk role mapping"""
        return self.get_resource(controller, oid)


class CreateElkRoleMappingParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    # role_mapping_id = fields.String(required=True, example='test-role_mapping', default='', description='RoleMapping id')
    name = fields.String(
        required=True,
        example="Test role_mapping",
        default="",
        description="RoleMapping name",
    )
    desc = fields.String(
        example="This is the test role_mapping",
        default="",
        description="RoleMapping description",
    )
    role_name = fields.String(required=True, example="test-role", default="", description="Role name")
    users_email = fields.String(required=True, example="test-users email", default="", description="Users email")
    realm_name = fields.String(required=True, example="test-realm name", default="", description="Realm name")


class CreateElkRoleMappingRequestSchema(Schema):
    role_mapping = fields.Nested(CreateElkRoleMappingParamRequestSchema)


class CreateElkRoleMappingBodyRequestSchema(Schema):
    body = fields.Nested(CreateElkRoleMappingRequestSchema, context="body")


class CreateElkRoleMapping(ElkRoleMappingView):
    summary = "Create role mapping"
    description = "Create role mapping"
    definitions = {
        "CreateElkRoleMappingRequestSchema": CreateElkRoleMappingRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateElkRoleMappingBodyRequestSchema)
    parameters_schema = CreateElkRoleMappingRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new role mapping to Elk"""
        return self.create_resource(controller, data)


class UpdateElkRoleMappingTemplateRequestSchema(Schema):
    name = fields.String(
        required=True,
        example="Test role_mapping",
        default="",
        description="RoleMapping name",
    )
    desc = fields.String(
        example="This is the test role_mapping",
        default="",
        description="RoleMapping description",
    )


class UpdateElkRoleMappingParamRequestSchema(UpdateProviderResourceRequestSchema):
    role_mappings = fields.Nested(
        UpdateElkRoleMappingTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator role_mappings to link",
        allow_none=True,
    )


class UpdateElkRoleMappingRequestSchema(Schema):
    role_mapping = fields.Nested(UpdateElkRoleMappingParamRequestSchema)


class UpdateElkRoleMappingBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateElkRoleMappingRequestSchema, context="body")


class UpdateElkRoleMapping(ElkRoleMappingView):
    summary = "Update role mapping"
    description = "Update role mapping"
    definitions = {
        "UpdateElkRoleMappingRequestSchema": UpdateElkRoleMappingRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateElkRoleMappingBodyRequestSchema)
    parameters_schema = UpdateElkRoleMappingRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Elk role mapping"""
        return self.update_resource(controller, oid, data)


class DeleteElkRoleMapping(ElkRoleMappingView):
    summary = "Delete role mapping"
    description = "Delete role mapping"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Elk role mapping"""
        return self.expunge_resource(controller, oid)


class ElkRoleMappingAPI(ElkAPI):
    """Elk role mapping api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = ElkAPI.base
        rules = [
            ("%s/role_mappings" % base, "GET", ListElkRoleMappings, {}),
            ("%s/role_mappings/<oid>" % base, "GET", GetElkRoleMapping, {}),
            ("%s/role_mappings" % base, "POST", CreateElkRoleMapping, {}),
            ("%s/role_mappings/<oid>" % base, "PUT", UpdateElkRoleMapping, {}),
            ("%s/role_mappings/<oid>" % base, "DELETE", DeleteElkRoleMapping, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
