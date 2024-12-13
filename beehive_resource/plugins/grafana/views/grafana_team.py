# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    ApiView,
)
from beehive_resource.plugins.grafana.entity.grafana_team import GrafanaTeam
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
from beehive_resource.plugins.grafana.views import GrafanaAPI, GrafanaApiView


class GrafanaTeamView(GrafanaApiView):
    tags = ["grafana"]
    resclass = GrafanaTeam
    parentclass = None


class ListGrafanaTeamsRequestSchema(ListResourcesRequestSchema):
    pass


class ListGrafanaTeamsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListGrafanaTeamsResponseSchema(PaginatedResponseSchema):
    teams = fields.Nested(ListGrafanaTeamsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListGrafanaTeams(GrafanaTeamView):
    summary = "List teams"
    description = "List teams"
    definitions = {
        "ListGrafanaTeamsResponseSchema": ListGrafanaTeamsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListGrafanaTeamsRequestSchema)
    parameters_schema = ListGrafanaTeamsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListGrafanaTeamsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """List Grafana teams"""
        return self.get_resources(controller, **data)


class GetGrafanaTeamParamsResponseSchema(ResourceResponseSchema):
    teams = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetGrafanaTeamResponseSchema(Schema):
    team = fields.Nested(GetGrafanaTeamParamsResponseSchema, required=True, allow_none=True)


class GetGrafanaTeam(GrafanaTeamView):
    summary = "Get team"
    description = "Get team"
    definitions = {
        "GetGrafanaTeamResponseSchema": GetGrafanaTeamResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetGrafanaTeamResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Grafana team"""
        return self.get_resource(controller, oid)


class CreateGrafanaTeamParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test-name-team", default="", description="Team name")
    desc = fields.String(
        required=False,
        allow_none=True,
        example="test-desc-team",
        description="The resource description",
    )


class CreateGrafanaTeamRequestSchema(Schema):
    team = fields.Nested(CreateGrafanaTeamParamRequestSchema)


class CreateGrafanaTeamBodyRequestSchema(Schema):
    body = fields.Nested(CreateGrafanaTeamRequestSchema, context="body")


class CreateGrafanaTeam(GrafanaTeamView):
    summary = "Create team"
    description = "Create team"
    definitions = {
        "CreateGrafanaTeamRequestSchema": CreateGrafanaTeamRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateGrafanaTeamBodyRequestSchema)
    parameters_schema = CreateGrafanaTeamRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new team to Grafana"""
        return self.create_resource(controller, data)


class UpdateGrafanaTeamTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="Test team", default="", description="Team name")
    desc = fields.String(
        required=False,
        example="This is the test team",
        default="",
        description="Team description",
    )


class UpdateGrafanaTeamParamRequestSchema(UpdateProviderResourceRequestSchema):
    teams = fields.Nested(
        UpdateGrafanaTeamTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator teams to link",
        allow_none=True,
    )


class UpdateGrafanaTeamRequestSchema(Schema):
    team = fields.Nested(UpdateGrafanaTeamParamRequestSchema)


class UpdateGrafanaTeamBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateGrafanaTeamRequestSchema, context="body")


class UpdateGrafanaTeam(GrafanaTeamView):
    summary = "Update team"
    description = "Update team"
    definitions = {
        "UpdateGrafanaTeamRequestSchema": UpdateGrafanaTeamRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateGrafanaTeamBodyRequestSchema)
    parameters_schema = UpdateGrafanaTeamRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Grafana team"""
        return self.update_resource(controller, oid, data)


class DeleteGrafanaTeam(GrafanaTeamView):
    summary = "Delete team"
    description = "Delete team"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Grafana team"""
        return self.expunge_resource(controller, oid)


class GrafanaTeamAPI(GrafanaAPI):
    """Grafana team api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = GrafanaAPI.base
        rules = [
            ("%s/teams" % base, "GET", ListGrafanaTeams, {}),
            ("%s/teams/<oid>" % base, "GET", GetGrafanaTeam, {}),
            ("%s/teams" % base, "POST", CreateGrafanaTeam, {}),
            ("%s/teams/<oid>" % base, "PUT", UpdateGrafanaTeam, {}),
            ("%s/teams/<oid>" % base, "DELETE", DeleteGrafanaTeam, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
