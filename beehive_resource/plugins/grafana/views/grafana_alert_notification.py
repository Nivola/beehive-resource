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
from beehive_resource.plugins.grafana.entity.grafana_alert_notification import (
    GrafanaAlertNotification,
)
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


class GrafanaAlertNotificationView(GrafanaApiView):
    tags = ["grafana"]
    resclass = GrafanaAlertNotification
    parentclass = None


class ListGrafanaAlertNotificationsRequestSchema(ListResourcesRequestSchema):
    pass


class ListGrafanaAlertNotificationsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListGrafanaAlertNotificationsResponseSchema(PaginatedResponseSchema):
    alert_notifications = fields.Nested(
        ListGrafanaAlertNotificationsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListGrafanaAlertNotifications(GrafanaAlertNotificationView):
    summary = "List alert_notifications"
    description = "List alert_notifications"
    definitions = {
        "ListGrafanaAlertNotificationsResponseSchema": ListGrafanaAlertNotificationsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListGrafanaAlertNotificationsRequestSchema)
    parameters_schema = ListGrafanaAlertNotificationsRequestSchema
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": ListGrafanaAlertNotificationsResponseSchema,
            }
        }
    )

    def get(self, controller, data, *args, **kwargs):
        """List Grafana alert_notifications"""
        return self.get_resources(controller, **data)


class GetGrafanaAlertNotificationParamsResponseSchema(ResourceResponseSchema):
    alert_notifications = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetGrafanaAlertNotificationResponseSchema(Schema):
    alert_notification = fields.Nested(GetGrafanaAlertNotificationParamsResponseSchema, required=True, allow_none=True)


class GetGrafanaAlertNotification(GrafanaAlertNotificationView):
    summary = "Get alert_notification"
    description = "Get alert_notification"
    definitions = {
        "GetGrafanaAlertNotificationResponseSchema": GetGrafanaAlertNotificationResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetGrafanaAlertNotificationResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Grafana alert_notification"""
        return self.get_resource(controller, oid)


class CreateGrafanaAlertNotificationParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(
        required=True,
        example="test-name-alert_notification",
        default="",
        description="AlertNotification name",
    )
    desc = fields.String(
        required=False,
        allow_none=True,
        example="test-desc-alert_notification",
        description="The resource description",
    )
    email = fields.String(required=True, example="test-email-alert_notification", description="The email")


class CreateGrafanaAlertNotificationRequestSchema(Schema):
    alert_notification = fields.Nested(CreateGrafanaAlertNotificationParamRequestSchema)


class CreateGrafanaAlertNotificationBodyRequestSchema(Schema):
    body = fields.Nested(CreateGrafanaAlertNotificationRequestSchema, context="body")


class CreateGrafanaAlertNotification(GrafanaAlertNotificationView):
    summary = "Create alert_notification"
    description = "Create alert_notification"
    definitions = {
        "CreateGrafanaAlertNotificationRequestSchema": CreateGrafanaAlertNotificationRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateGrafanaAlertNotificationBodyRequestSchema)
    parameters_schema = CreateGrafanaAlertNotificationRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new alert_notification to Grafana"""
        return self.create_resource(controller, data)


class UpdateGrafanaAlertNotificationTemplateRequestSchema(Schema):
    name = fields.String(
        required=True,
        example="Test alert_notification",
        default="",
        description="AlertNotification name",
    )
    desc = fields.String(
        required=False,
        example="This is the test alert_notification",
        default="",
        description="AlertNotification description",
    )


class UpdateGrafanaAlertNotificationParamRequestSchema(UpdateProviderResourceRequestSchema):
    alert_notifications = fields.Nested(
        UpdateGrafanaAlertNotificationTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator alert_notifications to link",
        allow_none=True,
    )


class UpdateGrafanaAlertNotificationRequestSchema(Schema):
    alert_notification = fields.Nested(UpdateGrafanaAlertNotificationParamRequestSchema)


class UpdateGrafanaAlertNotificationBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateGrafanaAlertNotificationRequestSchema, context="body")


class UpdateGrafanaAlertNotification(GrafanaAlertNotificationView):
    summary = "Update alert_notification"
    description = "Update alert_notification"
    definitions = {
        "UpdateGrafanaAlertNotificationRequestSchema": UpdateGrafanaAlertNotificationRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateGrafanaAlertNotificationBodyRequestSchema)
    parameters_schema = UpdateGrafanaAlertNotificationRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Grafana alert_notification"""
        return self.update_resource(controller, oid, data)


class DeleteGrafanaAlertNotification(GrafanaAlertNotificationView):
    summary = "Delete alert_notification"
    description = "Delete alert_notification"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Grafana alert_notification"""
        return self.expunge_resource(controller, oid)


class GrafanaAlertNotificationAPI(GrafanaAPI):
    """Grafana alert_notification api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = GrafanaAPI.base
        rules = [
            ("%s/alert_notifications" % base, "GET", ListGrafanaAlertNotifications, {}),
            (
                "%s/alert_notifications/<oid>" % base,
                "GET",
                GetGrafanaAlertNotification,
                {},
            ),
            (
                "%s/alert_notifications" % base,
                "POST",
                CreateGrafanaAlertNotification,
                {},
            ),
            (
                "%s/alert_notifications/<oid>" % base,
                "PUT",
                UpdateGrafanaAlertNotification,
                {},
            ),
            (
                "%s/alert_notifications/<oid>" % base,
                "DELETE",
                DeleteGrafanaAlertNotification,
                {},
            ),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
