# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from beehive.common.apimanager import (
    ApiManagerError,
    CrudApiTaskResponseSchema,
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)

from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
from beehive_resource.plugins.provider.entity.zone import ComputeZone

from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
)

from beehive_resource.plugins.provider.views.instance import ProviderInstance

from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)

from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper


#
# LoggingSpace
#
class ProviderLoggingSpace(LocalProviderApiView):
    resclass = ComputeLoggingSpace
    parentclass = ComputeZone


class ListLoggingSpacesRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(
        context="query",
        metadata={
            "description": 'instance id, uuid or name',
        },
    )


class ListLoggingSpacesResponseSchema(PaginatedResponseSchema):
    logging_spaces = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListLoggingSpaces(ProviderLoggingSpace):
    summary = "List logging spaces"
    description = "List logging spaces"
    definitions = {"ListLoggingSpacesResponseSchema": ListLoggingSpacesResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListLoggingSpacesRequestSchema)
    parameters_schema = ListLoggingSpacesRequestSchema

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListLoggingSpacesResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "logging_space")
        return self.get_resources(controller, **data)


class GetLoggingSpaceParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetLoggingSpaceResponseSchema(Schema):
    logging_space = fields.Nested(GetLoggingSpaceParamsResponseSchema, required=True, allow_none=True)


class GetLoggingSpace(ProviderLoggingSpace):
    summary = "Get logging space"
    description = "Get logging space"
    definitions = {"GetLoggingSpaceResponseSchema": GetLoggingSpaceResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetLoggingSpaceResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateLoggingSpaceElkSpaceRequestSchema(Schema):
    space_id = fields.String(
        required=True,
        metadata={
            "example": 'test-space',
            "description": 'Space id',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'Test space',
            "description": 'Space name',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'This is the test space',
            "description": 'Space description',
        },
    )

    color = fields.String(
        metadata={
            "example": 'Color test',
            "description": 'Space color',
        },
    )

    initials = fields.String(
        metadata={
            "example": 'Initials test',
            "description": 'Space initials',
        },
    )


class CreateLoggingSpaceParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'logging_space name',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'logging_space description',
        },
    )

    compute_zone = fields.String(
        required=True,
        metadata={
            "example": '1',
            "description": 'parent compute zone id or uuid',
        },
    )

    norescreate = fields.Boolean(
        required=False,
        allow_none=True,
        metadata={
            "description": "don't create physical resource",
        },
    )

    elk_space = fields.Nested(
        CreateLoggingSpaceElkSpaceRequestSchema,
        required=True,
        metadata={
            "description": 'elk space parameters',
        },
    )


class CreateLoggingSpaceRequestSchema(Schema):
    logging_space = fields.Nested(CreateLoggingSpaceParamRequestSchema)


class CreateLoggingSpaceBodyRequestSchema(Schema):
    body = fields.Nested(CreateLoggingSpaceRequestSchema, context="body")


class CreateLoggingSpace(ProviderLoggingSpace):
    summary = "Create logging space"
    description = "Create logging space"

    definitions = {
        "CreateLoggingSpaceRequestSchema": CreateLoggingSpaceRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateLoggingSpaceBodyRequestSchema)
    parameters_schema = CreateLoggingSpaceRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteLoggingSpace(ProviderLoggingSpace):
    summary = "Delete logging space"
    description = "Delete logging space"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class SendLoggingSpaceActionParamsDashboardRequestSchema(Schema):
    space_id_from = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'default',
            "description": 'space from copy dashboard',
        },
    )

    dashboard = fields.String(
        required=True,
        metadata={
            "example": 'dashboard apache',
            "description": 'dashboard name to add',
        },
    )

    index_pattern = fields.String(
        required=False,
        metadata={
            "example": 'index_pattern',
            "description": 'index_pattern to replace in dashboard',
        },
    )


class SendLoggingSpaceActionParamsDeleteDashboardRequestSchema(Schema):
    dashboard_to_search = fields.String(
        required=True,
        metadata={
            "example": 'dashboard-to-search',
            "description": 'dashboard name to delete',
        },
    )


class SendLoggingSpaceActionParamsRequestSchema(Schema):
    add_dashboard = fields.Nested(
        SendLoggingSpaceActionParamsDashboardRequestSchema,
        metadata={
            "description": 'add dashboard to space',
        },
    )

    delete_dashboard = fields.Nested(
        SendLoggingSpaceActionParamsDeleteDashboardRequestSchema,
        required=False,
        allow_none=True,
        metadata={
            "description": 'delete dashboard to space',
        },
    )


class SendLoggingSpaceActionRequestSchema(Schema):
    action = fields.Nested(SendLoggingSpaceActionParamsRequestSchema, required=True)
    schedule = fields.Dict(
        required=False,
        load_default=None,
        metadata={
            "description": 'schedule to use when you want to run a scheduled action',
        },
    )


class SendLoggingSpaceActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        SendLoggingSpaceActionRequestSchema,
        context="body",
    )


class SendLoggingSpaceAction(ProviderLoggingSpace):
    summary = "Send server action"
    description = "Send server action"

    definitions = {
        "SendLoggingSpaceActionRequestSchema": SendLoggingSpaceActionRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(SendLoggingSpaceActionBodyRequestSchema)
    parameters_schema = SendLoggingSpaceActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        instance: ComputeLoggingSpace
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


class ComputeLoggingSpaceAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/logging_spaces" % base, "GET", ListLoggingSpaces, {}),
            ("%s/logging_spaces/<oid>" % base, "GET", GetLoggingSpace, {}),
            ("%s/logging_spaces" % base, "POST", CreateLoggingSpace, {}),
            ("%s/logging_spaces/<oid>" % base, "DELETE", DeleteLoggingSpace, {}),
            (
                "%s/logging_spaces/<oid>/actions" % base,
                "PUT",
                SendLoggingSpaceAction,
                {},
            ),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
