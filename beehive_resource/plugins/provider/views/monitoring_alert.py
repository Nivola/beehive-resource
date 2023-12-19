# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)
from beehive_resource.plugins.provider.entity.monitoring_alert import (
    ComputeMonitoringAlert,
)
from beehive_resource.plugins.provider.entity.monitoring_folder import (
    ComputeMonitoringFolder,
)
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
# MonitoringAlert
#
class ProviderMonitoringAlert(LocalProviderApiView):
    resclass = ComputeMonitoringAlert
    # parentclass = ComputeZone
    parentclass = ComputeMonitoringFolder


class ListMonitoringAlertsRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context="query", description="instance id, uuid or name")
    parent = fields.String(required=False, default="", description="il padre Folder id", allow_none=True)


class ListMonitoringAlertsResponseSchema(PaginatedResponseSchema):
    monitoring_alerts = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListMonitoringAlerts(ProviderMonitoringAlert):
    summary = "List monitoring alerts"
    description = "List monitoring alerts"
    definitions = {
        "ListMonitoringAlertsResponseSchema": ListMonitoringAlertsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListMonitoringAlertsRequestSchema)
    parameters_schema = ListMonitoringAlertsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListMonitoringAlertsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "monitoring_alert")
        return self.get_resources(controller, **data)


class GetMonitoringAlertParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetMonitoringAlertResponseSchema(Schema):
    monitoring_alert = fields.Nested(GetMonitoringAlertParamsResponseSchema, required=True, allow_none=True)


class GetMonitoringAlert(ProviderMonitoringAlert):
    summary = "Get monitoring alert"
    description = "Get monitoring alert"
    definitions = {
        "GetMonitoringAlertResponseSchema": GetMonitoringAlertResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetMonitoringAlertResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateMonitoringAlertGrafanaAlertRequestSchema(Schema):
    name = fields.String(required=True, example="Test alert", default="", description="Alert name")
    desc = fields.String(
        required=True,
        example="This is the test alert",
        default="",
        description="Alert description",
    )
    email = fields.String(
        required=True,
        example="test_email@aaa.it",
        default="",
        description="Alert email",
    )


class CreateMonitoringAlertParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example="test", description="monitoring_alert name")
    desc = fields.String(required=True, example="test", description="monitoring_alert description")
    # compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    monitoring_folder = fields.String(required=True, example="1", description="parent compute folder id or uuid")
    norescreate = fields.Boolean(required=False, allow_none=True, description="don't create physical resource")
    grafana_alert = fields.Nested(
        CreateMonitoringAlertGrafanaAlertRequestSchema,
        required=True,
        description="grafana alert parameters",
    )


class CreateMonitoringAlertRequestSchema(Schema):
    monitoring_alert = fields.Nested(CreateMonitoringAlertParamRequestSchema)


class CreateMonitoringAlertBodyRequestSchema(Schema):
    body = fields.Nested(CreateMonitoringAlertRequestSchema, context="body")


class CreateMonitoringAlert(ProviderMonitoringAlert):
    summary = "Create monitoring alert"
    description = "Create monitoring alert"
    definitions = {
        "CreateMonitoringAlertRequestSchema": CreateMonitoringAlertRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateMonitoringAlertBodyRequestSchema)
    parameters_schema = CreateMonitoringAlertRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteMonitoringAlert(ProviderMonitoringAlert):
    summary = "Delete monitoring alert"
    description = "Delete monitoring alert"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GetAppliedMonitoringAlertsResponseSchema(PaginatedResponseSchema):
    applied_monitoring_alerts = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ComputeMonitoringAlertAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/monitoring_alerts" % base, "GET", ListMonitoringAlerts, {}),
            ("%s/monitoring_alerts/<oid>" % base, "GET", GetMonitoringAlert, {}),
            ("%s/monitoring_alerts" % base, "POST", CreateMonitoringAlert, {}),
            ("%s/monitoring_alerts/<oid>" % base, "DELETE", DeleteMonitoringAlert, {}),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
