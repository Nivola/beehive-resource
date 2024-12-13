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
from beehive_resource.plugins.grafana.entity.grafana_dashboard import GrafanaDashboard
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


class GrafanaDashboardView(GrafanaApiView):
    tags = ["grafana"]
    resclass = GrafanaDashboard
    parentclass = None


class ListGrafanaDashboardsRequestSchema(ListResourcesRequestSchema):
    pass


class ListGrafanaDashboardsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListGrafanaDashboardsResponseSchema(PaginatedResponseSchema):
    dashboards = fields.Nested(
        ListGrafanaDashboardsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListGrafanaDashboards(GrafanaDashboardView):
    summary = "List dashboards"
    description = "List dashboards"
    definitions = {
        "ListGrafanaDashboardsResponseSchema": ListGrafanaDashboardsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListGrafanaDashboardsRequestSchema)
    parameters_schema = ListGrafanaDashboardsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListGrafanaDashboardsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """List Grafana dashboards"""
        return self.get_resources(controller, **data)


class GetGrafanaDashboardParamsResponseSchema(ResourceResponseSchema):
    dashboards = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetGrafanaDashboardResponseSchema(Schema):
    dashboard = fields.Nested(GetGrafanaDashboardParamsResponseSchema, required=True, allow_none=True)


class GetGrafanaDashboard(GrafanaDashboardView):
    summary = "Get dashboard"
    description = "Get dashboard"
    definitions = {
        "GetGrafanaDashboardResponseSchema": GetGrafanaDashboardResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetGrafanaDashboardResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Grafana dashboard"""
        return self.get_resource(controller, oid)


class CreateGrafanaDashboardParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test-name-dashboard", default="", description="Dashboard name")
    desc = fields.String(
        required=False,
        example="test-desc-dashboard",
        description="The resource description",
    )


class CreateGrafanaDashboardRequestSchema(Schema):
    dashboard = fields.Nested(CreateGrafanaDashboardParamRequestSchema)


class CreateGrafanaDashboardBodyRequestSchema(Schema):
    body = fields.Nested(CreateGrafanaDashboardRequestSchema, context="body")


class CreateGrafanaDashboard(GrafanaDashboardView):
    summary = "Create dashboard"
    description = "Create dashboard"
    definitions = {
        "CreateGrafanaDashboardRequestSchema": CreateGrafanaDashboardRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateGrafanaDashboardBodyRequestSchema)
    parameters_schema = CreateGrafanaDashboardRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new dashboard to Grafana"""
        return self.create_resource(controller, data)


class UpdateGrafanaDashboardTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="Test dashboard", default="", description="Dashboard name")
    desc = fields.String(
        required=False,
        example="This is the test dashboard",
        default="",
        description="Dashboard description",
    )


class UpdateGrafanaDashboardParamRequestSchema(UpdateProviderResourceRequestSchema):
    dashboards = fields.Nested(
        UpdateGrafanaDashboardTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator dashboards to link",
        allow_none=True,
    )


class UpdateGrafanaDashboardRequestSchema(Schema):
    dashboard = fields.Nested(UpdateGrafanaDashboardParamRequestSchema)


class UpdateGrafanaDashboardBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateGrafanaDashboardRequestSchema, context="body")


class UpdateGrafanaDashboard(GrafanaDashboardView):
    summary = "Update dashboard"
    description = "Update dashboard"
    definitions = {
        "UpdateGrafanaDashboardRequestSchema": UpdateGrafanaDashboardRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateGrafanaDashboardBodyRequestSchema)
    parameters_schema = UpdateGrafanaDashboardRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Grafana dashboard"""
        return self.update_resource(controller, oid, data)


class DeleteGrafanaDashboard(GrafanaDashboardView):
    summary = "Delete dashboard"
    description = "Delete dashboard"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Grafana dashboard"""
        return self.expunge_resource(controller, oid)


class GrafanaDashboardAPI(GrafanaAPI):
    """Grafana dashboard api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = GrafanaAPI.base
        rules = [
            ("%s/dashboards" % base, "GET", ListGrafanaDashboards, {}),
            ("%s/dashboards/<oid>" % base, "GET", GetGrafanaDashboard, {}),
            ("%s/dashboards" % base, "POST", CreateGrafanaDashboard, {}),
            ("%s/dashboards/<oid>" % base, "PUT", UpdateGrafanaDashboard, {}),
            ("%s/dashboards/<oid>" % base, "DELETE", DeleteGrafanaDashboard, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
