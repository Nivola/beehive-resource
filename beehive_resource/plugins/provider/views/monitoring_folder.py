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
# MonitoringFolder
#
class ProviderMonitoringFolder(LocalProviderApiView):
    resclass = ComputeMonitoringFolder
    parentclass = ComputeZone


class ListMonitoringFoldersRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context="query", description="instance id, uuid or name")


class ListMonitoringFoldersResponseSchema(PaginatedResponseSchema):
    monitoring_folders = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListMonitoringFolders(ProviderMonitoringFolder):
    summary = "List monitoring folders"
    description = "List monitoring folders"
    definitions = {
        "ListMonitoringFoldersResponseSchema": ListMonitoringFoldersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListMonitoringFoldersRequestSchema)
    parameters_schema = ListMonitoringFoldersRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListMonitoringFoldersResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get("instance", None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "monitoring_folder")
        return self.get_resources(controller, **data)


class GetMonitoringFolderParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetMonitoringFolderResponseSchema(Schema):
    monitoring_folder = fields.Nested(GetMonitoringFolderParamsResponseSchema, required=True, allow_none=True)


class GetMonitoringFolder(ProviderMonitoringFolder):
    summary = "Get monitoring folder"
    description = "Get monitoring folder"
    definitions = {
        "GetMonitoringFolderResponseSchema": GetMonitoringFolderResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetMonitoringFolderResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateMonitoringFolderGrafanaFolderRequestSchema(Schema):
    # container = fields.String(required=True, example='12', description='Container id, uuid or name')
    # folder_id = fields.String(required=True, example='test-folder', default='', description='Folder id')
    name = fields.String(required=True, example="Test folder", default="", description="Folder name")
    desc = fields.String(
        required=True,
        example="This is the test folder",
        default="",
        description="Folder description",
    )


class CreateMonitoringFolderParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example="test", description="monitoring_folder name")
    desc = fields.String(required=True, example="test", description="monitoring_folder description")
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    norescreate = fields.Boolean(required=False, allow_none=True, description="don't create physical resource")
    grafana_folder = fields.Nested(
        CreateMonitoringFolderGrafanaFolderRequestSchema,
        required=True,
        description="grafana folder parameters",
    )


class CreateMonitoringFolderRequestSchema(Schema):
    monitoring_folder = fields.Nested(CreateMonitoringFolderParamRequestSchema)


class CreateMonitoringFolderBodyRequestSchema(Schema):
    body = fields.Nested(CreateMonitoringFolderRequestSchema, context="body")


class CreateMonitoringFolder(ProviderMonitoringFolder):
    summary = "Create monitoring folder"
    description = "Create monitoring folder"
    definitions = {
        "CreateMonitoringFolderRequestSchema": CreateMonitoringFolderRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateMonitoringFolderBodyRequestSchema)
    parameters_schema = CreateMonitoringFolderRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteMonitoringFolder(ProviderMonitoringFolder):
    summary = "Delete monitoring folder"
    description = "Delete monitoring folder"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class SendMonitoringFolderActionParamsDashboardRequestSchema(Schema):
    dashboard_folder_from = fields.String(
        required=False,
        allow_none=True,
        example="default",
        description="folder from copy dashboard",
    )
    dashboard_to_search = fields.String(
        required=True,
        example="dashboard-to-search",
        description="dashboard name to add",
    )
    dash_tag = fields.String(required=False, allow_none=True, example="abc,def", description="tags dashboard")
    organization = fields.String(
        required=False,
        example="organization",
        description="organization to replace in dashboard",
    )
    division = fields.String(
        required=False,
        example="division",
        description="division to replace in dashboard",
    )
    account = fields.String(required=False, example="account", description="account to replace in dashboard")


class SendMonitoringFolderActionParamsPermissionRequestSchema(Schema):
    # folder_id_from = fields.String(required=False, allow_none=True, example='default', description='folder from copy dashboard')
    team_viewer = fields.String(
        required=True,
        example="team_01",
        description="team viewer name to add permission",
    )
    team_editor = fields.String(
        required=False,
        allow_none=True,
        example="team_02",
        description="team editor name to add permission",
    )


class SendMonitoringFolderActionParamsRequestSchema(Schema):
    add_dashboard = fields.Nested(
        SendMonitoringFolderActionParamsDashboardRequestSchema,
        required=False,
        allow_none=True,
        description="add dashboard to folder",
    )
    add_permission = fields.Nested(
        SendMonitoringFolderActionParamsPermissionRequestSchema,
        required=False,
        allow_none=True,
        description="add permission to folder",
    )


class SendMonitoringFolderActionRequestSchema(Schema):
    action = fields.Nested(SendMonitoringFolderActionParamsRequestSchema, required=True)
    schedule = fields.Dict(
        required=False,
        missing=None,
        description="schedule to use when you want to run a scheduled action",
    )


class SendMonitoringFolderActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendMonitoringFolderActionRequestSchema, context="body")


class SendMonitoringFolderAction(ProviderMonitoringFolder):
    summary = "Send server action"
    description = "Send server action"
    definitions = {
        "SendMonitoringFolderActionRequestSchema": SendMonitoringFolderActionRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendMonitoringFolderActionBodyRequestSchema)
    parameters_schema = SendMonitoringFolderActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        instance: ComputeMonitoringFolder
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


class ComputeMonitoringFolderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/monitoring_folders" % base, "GET", ListMonitoringFolders, {}),
            ("%s/monitoring_folders/<oid>" % base, "GET", GetMonitoringFolder, {}),
            ("%s/monitoring_folders" % base, "POST", CreateMonitoringFolder, {}),
            (
                "%s/monitoring_folders/<oid>" % base,
                "DELETE",
                DeleteMonitoringFolder,
                {},
            ),
            (
                "%s/monitoring_folders/<oid>/actions" % base,
                "PUT",
                SendMonitoringFolderAction,
                {},
            ),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
