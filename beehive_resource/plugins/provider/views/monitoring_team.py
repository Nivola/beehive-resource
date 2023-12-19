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
from beehive_resource.plugins.provider.entity.monitoring_folder import (
    ComputeMonitoringFolder,
)
from beehive_resource.plugins.provider.entity.monitoring_team import (
    ComputeMonitoringTeam,
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
# MonitoringTeam
#
class ProviderMonitoringTeam(LocalProviderApiView):
    resclass = ComputeMonitoringTeam
    # parentclass = ComputeZone
    parentclass = ComputeMonitoringFolder


class ListMonitoringTeamsRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context="query", description="instance id, uuid or name")
    parent = fields.String(required=False, default="", description="il padre Team id", allow_none=True)


class ListMonitoringTeamsResponseSchema(PaginatedResponseSchema):
    monitoring_teams = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListMonitoringTeams(ProviderMonitoringTeam):
    summary = "List monitoring teams"
    description = "List monitoring teams"
    definitions = {
        "ListMonitoringTeamsResponseSchema": ListMonitoringTeamsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListMonitoringTeamsRequestSchema)
    parameters_schema = ListMonitoringTeamsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListMonitoringTeamsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "monitoring_team")
        return self.get_resources(controller, **data)


class GetMonitoringTeamParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetMonitoringTeamResponseSchema(Schema):
    monitoring_team = fields.Nested(GetMonitoringTeamParamsResponseSchema, required=True, allow_none=True)


class GetMonitoringTeam(ProviderMonitoringTeam):
    summary = "Get monitoring team"
    description = "Get monitoring team"
    definitions = {
        "GetMonitoringTeamResponseSchema": GetMonitoringTeamResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetMonitoringTeamResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateMonitoringTeamGrafanaTeamRequestSchema(Schema):
    name = fields.String(required=True, example="Test team", default="", description="Team name")
    desc = fields.String(
        required=True,
        example="This is the test team",
        default="",
        description="Team description",
    )


class CreateMonitoringTeamParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example="test", description="monitoring_team name")
    desc = fields.String(required=True, example="test", description="monitoring_team description")
    # compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    monitoring_folder = fields.String(required=True, example="1", description="parent compute folder id or uuid")
    norescreate = fields.Boolean(required=False, allow_none=True, description="don't create physical resource")
    grafana_team = fields.Nested(
        CreateMonitoringTeamGrafanaTeamRequestSchema,
        required=True,
        description="grafana team parameters",
    )


class CreateMonitoringTeamRequestSchema(Schema):
    monitoring_team = fields.Nested(CreateMonitoringTeamParamRequestSchema)


class CreateMonitoringTeamBodyRequestSchema(Schema):
    body = fields.Nested(CreateMonitoringTeamRequestSchema, context="body")


class CreateMonitoringTeam(ProviderMonitoringTeam):
    summary = "Create monitoring team"
    description = "Create monitoring team"
    definitions = {
        "CreateMonitoringTeamRequestSchema": CreateMonitoringTeamRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateMonitoringTeamBodyRequestSchema)
    parameters_schema = CreateMonitoringTeamRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteMonitoringTeam(ProviderMonitoringTeam):
    summary = "Delete monitoring team"
    description = "Delete monitoring team"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class SendMonitoringTeamActionParamsUserRequestSchema(Schema):
    users_email = fields.String(
        required=True,
        example="aaa@bbb.it,ccc@ddd.it",
        description="users email to search",
    )


class SendMonitoringTeamActionParamsRequestSchema(Schema):
    add_user = fields.Nested(
        SendMonitoringTeamActionParamsUserRequestSchema,
        required=False,
        allow_none=True,
        description="add user to team",
    )


class SendMonitoringTeamActionRequestSchema(Schema):
    action = fields.Nested(SendMonitoringTeamActionParamsRequestSchema, required=True)
    schedule = fields.Dict(
        required=False,
        missing=None,
        description="schedule to use when you want to run a scheduled action",
    )


class SendMonitoringTeamActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendMonitoringTeamActionRequestSchema, context="body")


class SendMonitoringTeamAction(ProviderMonitoringTeam):
    summary = "Send server action"
    description = "Send server action"
    definitions = {
        "SendMonitoringTeamActionRequestSchema": SendMonitoringTeamActionRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendMonitoringTeamActionBodyRequestSchema)
    parameters_schema = SendMonitoringTeamActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        instance: ComputeMonitoringTeam
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


class ComputeMonitoringTeamAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/monitoring_teams" % base, "GET", ListMonitoringTeams, {}),
            ("%s/monitoring_teams/<oid>" % base, "GET", GetMonitoringTeam, {}),
            ("%s/monitoring_teams" % base, "POST", CreateMonitoringTeam, {}),
            ("%s/monitoring_teams/<oid>" % base, "DELETE", DeleteMonitoringTeam, {}),
            (
                "%s/monitoring_teams/<oid>/actions" % base,
                "PUT",
                SendMonitoringTeamAction,
                {},
            ),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
