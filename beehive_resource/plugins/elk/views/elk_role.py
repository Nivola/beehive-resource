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
from beehive_resource.plugins.elk.entity.elk_role import ElkRole
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


class ElkRoleView(ElkApiView):
    tags = ["elk"]
    resclass = ElkRole
    parentclass = None


class ListElkRolesRequestSchema(ListResourcesRequestSchema):
    pass


class ListElkRolesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListElkRolesResponseSchema(PaginatedResponseSchema):
    roles = fields.Nested(ListElkRolesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListElkRoles(ElkRoleView):
    summary = "List roles"
    description = "List roles"
    definitions = {
        "ListElkRolesResponseSchema": ListElkRolesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListElkRolesRequestSchema)
    parameters_schema = ListElkRolesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListElkRolesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """List Elk roles"""
        return self.get_resources(controller, **data)


class GetElkRoleParamsResponseSchema(ResourceResponseSchema):
    roles = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetElkRoleResponseSchema(Schema):
    role = fields.Nested(GetElkRoleParamsResponseSchema, required=True, allow_none=True)


class GetElkRole(ElkRoleView):
    summary = "Get role"
    description = "Get role"
    definitions = {
        "GetElkRoleResponseSchema": GetElkRoleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetElkRoleResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Elk role"""
        return self.get_resource(controller, oid)


class CreateElkRoleParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="Test role", default="", description="Role name")
    indice = fields.String(required=True, example="test-indice-*", default="", description="Index pattern")
    space_id = fields.String(required=True, example="test-space", default="", description="Space id")


class CreateElkRoleRequestSchema(Schema):
    role = fields.Nested(CreateElkRoleParamRequestSchema)


class CreateElkRoleBodyRequestSchema(Schema):
    body = fields.Nested(CreateElkRoleRequestSchema, context="body")


class CreateElkRole(ElkRoleView):
    summary = "Create role"
    description = "Create role"
    definitions = {
        "CreateElkRoleRequestSchema": CreateElkRoleRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateElkRoleBodyRequestSchema)
    parameters_schema = CreateElkRoleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new role to Elk"""
        return self.create_resource(controller, data)


class UpdateElkRoleTemplateRequestSchema(Schema):
    name = (fields.String(required=True, example="Test role", default="", description="Role name"),)
    indice = (
        fields.String(
            required=True,
            example="test-indice-*",
            default="",
            description="Index pattern",
        ),
    )
    space_id = fields.String(required=True, example="test-space", default="", description="Space id")


class UpdateElkRoleParamRequestSchema(UpdateProviderResourceRequestSchema):
    roles = fields.Nested(
        UpdateElkRoleTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator roles to link",
        allow_none=True,
    )


class UpdateElkRoleRequestSchema(Schema):
    role = fields.Nested(UpdateElkRoleParamRequestSchema)


class UpdateElkRoleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateElkRoleRequestSchema, context="body")


class UpdateElkRole(ElkRoleView):
    summary = "Update role"
    description = "Update role"
    definitions = {
        "UpdateElkRoleRequestSchema": UpdateElkRoleRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateElkRoleBodyRequestSchema)
    parameters_schema = UpdateElkRoleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Elk role"""
        return self.update_resource(controller, oid, data)


class DeleteElkRole(ElkRoleView):
    summary = "Delete role"
    description = "Delete role"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Elk role"""
        return self.expunge_resource(controller, oid)


class ElkRoleAPI(ElkAPI):
    """Elk role api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = ElkAPI.base
        rules = [
            ("%s/roles" % base, "GET", ListElkRoles, {}),
            ("%s/roles/<oid>" % base, "GET", GetElkRole, {}),
            ("%s/roles" % base, "POST", CreateElkRole, {}),
            ("%s/roles/<oid>" % base, "PUT", UpdateElkRole, {}),
            ("%s/roles/<oid>" % base, "DELETE", DeleteElkRole, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
