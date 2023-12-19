# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from beehive.common.apimanager import (
    ApiManagerError,
    CrudApiTaskResponseSchema,
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)
from beehive_resource.plugins.provider.entity.monitoring_threshold import (
    ComputeMonitoringThreshold,
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
from beehive_resource.plugins.provider.entity.zone import ComputeZone


#
# MonitoringThreshold
#
class ProviderMonitoringThreshold(LocalProviderApiView):
    resclass = ComputeMonitoringThreshold
    parentclass = ComputeZone


class ListMonitoringThresholdsRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context="query", description="instance id, uuid or name")
    parent = fields.String(required=False, default="", description="il padre Threshold id", allow_none=True)


class ListMonitoringThresholdsResponseSchema(PaginatedResponseSchema):
    monitoring_thresholds = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListMonitoringThresholds(ProviderMonitoringThreshold):
    summary = "List monitoring thresholds"
    description = "List monitoring thresholds"
    definitions = {
        "ListMonitoringThresholdsResponseSchema": ListMonitoringThresholdsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListMonitoringThresholdsRequestSchema)
    parameters_schema = ListMonitoringThresholdsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListMonitoringThresholdsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "monitoring_threshold")
        return self.get_resources(controller, **data)


class GetMonitoringThresholdParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetMonitoringThresholdResponseSchema(Schema):
    monitoring_threshold = fields.Nested(GetMonitoringThresholdParamsResponseSchema, required=True, allow_none=True)


class GetMonitoringThreshold(ProviderMonitoringThreshold):
    summary = "Get monitoring threshold"
    description = "Get monitoring threshold"
    definitions = {
        "GetMonitoringThresholdResponseSchema": GetMonitoringThresholdResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetMonitoringThresholdResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateMonitoringThresholdZabbixThresholdRequestSchema(Schema):
    name = fields.String(required=True, example="Test threshold", default="", description="Threshold name")
    desc = fields.String(
        required=True,
        example="This is the test threshold",
        default="",
        description="Threshold description",
    )
    triplet = fields.String(required=True, example="Test threshold", default="", description="Triplet account")
    str_users = fields.String(required=True, example="test@email.com,aaa@bbb.it", default="", description="Users email")


class CreateMonitoringThresholdParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example="test", description="monitoring_threshold name")
    desc = fields.String(required=True, example="test", description="monitoring_threshold description")
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    availability_zone = fields.String(required=True, example="1", description="availability_zone")
    norescreate = fields.Boolean(required=False, allow_none=True, description="don't create physical resource")
    zabbix_threshold = fields.Nested(
        CreateMonitoringThresholdZabbixThresholdRequestSchema,
        required=True,
        description="zabbix threshold parameters",
    )


class CreateMonitoringThresholdRequestSchema(Schema):
    monitoring_threshold = fields.Nested(CreateMonitoringThresholdParamRequestSchema)


class CreateMonitoringThresholdBodyRequestSchema(Schema):
    body = fields.Nested(CreateMonitoringThresholdRequestSchema, context="body")


class CreateMonitoringThreshold(ProviderMonitoringThreshold):
    summary = "Create monitoring threshold"
    description = "Create monitoring threshold"
    definitions = {
        "CreateMonitoringThresholdRequestSchema": CreateMonitoringThresholdRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateMonitoringThresholdBodyRequestSchema)
    parameters_schema = CreateMonitoringThresholdRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteMonitoringThreshold(ProviderMonitoringThreshold):
    summary = "Delete monitoring threshold"
    description = "Delete monitoring threshold"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class SendMonitoringThresholdActionParamsAddUserRequestSchema(Schema):
    triplet = fields.String(required=True, description="triplet of account")
    users_email = fields.String(
        required=True,
        example="aaa@bbb.it,ccc@ddd.it",
        description="users email to search",
    )
    severity = fields.String(
        required=True,
        example="48",
        description="severity of alert received",
    )


class SendMonitoringThresholdActionParamsModifyUserRequestSchema(Schema):
    triplet = fields.String(required=True, description="triplet of account")
    users_email = fields.String(
        required=True,
        example="aaa@bbb.it,ccc@ddd.it",
        description="users email to search",
    )
    severity = fields.String(
        required=True,
        example="48",
        description="severity of alert received",
    )


class SendMonitoringThresholdActionParamsRequestSchema(Schema):
    add_user = fields.Nested(
        SendMonitoringThresholdActionParamsAddUserRequestSchema,
        required=False,
        allow_none=True,
        description="add user to threshold",
    )
    modify_user = fields.Nested(
        SendMonitoringThresholdActionParamsModifyUserRequestSchema,
        required=False,
        allow_none=True,
        description="add user to threshold",
    )


class SendMonitoringThresholdActionRequestSchema(Schema):
    action = fields.Nested(SendMonitoringThresholdActionParamsRequestSchema, required=True)
    schedule = fields.Dict(
        required=False,
        missing=None,
        description="schedule to use when you want to run a scheduled action",
    )


class SendMonitoringThresholdActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendMonitoringThresholdActionRequestSchema, context="body")


class SendMonitoringThresholdAction(ProviderMonitoringThreshold):
    summary = "Send server action"
    description = "Send server action"
    definitions = {
        "SendMonitoringThresholdActionRequestSchema": SendMonitoringThresholdActionRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendMonitoringThresholdActionBodyRequestSchema)
    parameters_schema = SendMonitoringThresholdActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        instance: ComputeMonitoringThreshold
        instance = self.get_resource_reference(controller, oid)

        actions = data.get("action")
        schedule = data.get("schedule")
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {"param": params}

        instance.check_active()
        if action in instance.actions:
            if schedule is not None:
                task = instance.scheduled_action(action, schedule=schedule, params=params)
            else:
                task = instance.action(action, **params)
        else:
            raise ApiManagerError("Action %s not supported for instance" % action)

        return task


class GetMonitoringUserSeverityResponseSchema(Schema):
    user_severities = fields.List(fields.String(), required=True, description="List of severity")


class GetMonitoringUserSeverity(ProviderMonitoringThreshold):
    summary = "Get monitoring user severity"
    description = "Get monitoring user severity"
    definitions = {
        "GetMonitoringUserSeverityResponseSchema": GetMonitoringUserSeverityResponseSchema,
    }
    # parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    parameters = None
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetMonitoringUserSeverityResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        from beehive_resource.plugins.zabbix import ZabbixPlugin

        user_severities = []
        user_severities.append(ZabbixPlugin.SEVERITY_DESC_INFORMATION)
        user_severities.append(ZabbixPlugin.SEVERITY_DESC_WARNING)
        user_severities.append(ZabbixPlugin.SEVERITY_DESC_AVERAGE)
        user_severities.append(ZabbixPlugin.SEVERITY_DESC_HIGH)
        user_severities.append(ZabbixPlugin.SEVERITY_DESC_DISASTER)

        return {"user_severities": user_severities}


class ComputeMonitoringThresholdAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/monitoring_thresholds" % base, "GET", ListMonitoringThresholds, {}),
            ("%s/monitoring_thresholds/<oid>" % base, "GET", GetMonitoringThreshold, {}),
            ("%s/monitoring_thresholds" % base, "POST", CreateMonitoringThreshold, {}),
            ("%s/monitoring_thresholds/<oid>" % base, "DELETE", DeleteMonitoringThreshold, {}),
            (
                "%s/monitoring_thresholds/<oid>/actions" % base,
                "PUT",
                SendMonitoringThresholdAction,
                {},
            ),
            ("%s/monitoring_thresholds/user/severities" % base, "GET", GetMonitoringUserSeverity, {}),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
