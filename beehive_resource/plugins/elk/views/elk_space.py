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
from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
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


class ElkSpaceView(ElkApiView):
    tags = ["elk"]
    resclass = ElkSpace
    parentclass = None


class ListElkSpacesRequestSchema(ListResourcesRequestSchema):
    pass


class ListElkSpacesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListElkSpacesResponseSchema(PaginatedResponseSchema):
    spaces = fields.Nested(ListElkSpacesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListElkSpaces(ElkSpaceView):
    summary = "List spaces"
    description = "List spaces"
    definitions = {
        "ListElkSpacesResponseSchema": ListElkSpacesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListElkSpacesRequestSchema)
    parameters_schema = ListElkSpacesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListElkSpacesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """List Elk spaces"""
        return self.get_resources(controller, **data)


class GetElkSpaceParamsResponseSchema(ResourceResponseSchema):
    spaces = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetElkSpaceResponseSchema(Schema):
    space = fields.Nested(GetElkSpaceParamsResponseSchema, required=True, allow_none=True)


class GetElkSpace(ElkSpaceView):
    summary = "Get space"
    description = "Get space"
    definitions = {
        "GetElkSpaceResponseSchema": GetElkSpaceResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetElkSpaceResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Elk space"""
        return self.get_resource(controller, oid)


class CreateElkSpaceParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    space_id = fields.String(required=True, example="test-space", default="", description="Space id")
    name = fields.String(required=True, example="Test space", default="", description="Space name")
    desc = fields.String(example="This is the test space", default="", description="Space description")
    color = fields.String(example="Color test", default="", description="Space color")
    initials = fields.String(example="Initials test", default="", description="Space initials")


class CreateElkSpaceRequestSchema(Schema):
    space = fields.Nested(CreateElkSpaceParamRequestSchema)


class CreateElkSpaceBodyRequestSchema(Schema):
    body = fields.Nested(CreateElkSpaceRequestSchema, context="body")


class CreateElkSpace(ElkSpaceView):
    summary = "Create space"
    description = "Create space"
    definitions = {
        "CreateElkSpaceRequestSchema": CreateElkSpaceRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateElkSpaceBodyRequestSchema)
    parameters_schema = CreateElkSpaceRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new space to Elk"""
        return self.create_resource(controller, data)


class UpdateElkSpaceTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="Test space", default="", description="Space name")
    desc = fields.String(example="This is the test space", default="", description="Space description")


class UpdateElkSpaceParamRequestSchema(UpdateProviderResourceRequestSchema):
    spaces = fields.Nested(
        UpdateElkSpaceTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator spaces to link",
        allow_none=True,
    )


class UpdateElkSpaceRequestSchema(Schema):
    space = fields.Nested(UpdateElkSpaceParamRequestSchema)


class UpdateElkSpaceBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateElkSpaceRequestSchema, context="body")


class UpdateElkSpace(ElkSpaceView):
    summary = "Update space"
    description = "Update space"
    definitions = {
        "UpdateElkSpaceRequestSchema": UpdateElkSpaceRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateElkSpaceBodyRequestSchema)
    parameters_schema = UpdateElkSpaceRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Elk space"""
        return self.update_resource(controller, oid, data)


class DeleteElkSpace(ElkSpaceView):
    summary = "Delete space"
    description = "Delete space"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Elk space"""
        return self.expunge_resource(controller, oid)


class ElkSpaceAPI(ElkAPI):
    """Elk space api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = ElkAPI.base
        rules = [
            ("%s/spaces" % base, "GET", ListElkSpaces, {}),
            ("%s/spaces/<oid>" % base, "GET", GetElkSpace, {}),
            ("%s/spaces" % base, "POST", CreateElkSpace, {}),
            ("%s/spaces/<oid>" % base, "PUT", UpdateElkSpace, {}),
            ("%s/spaces/<oid>" % base, "DELETE", DeleteElkSpace, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
