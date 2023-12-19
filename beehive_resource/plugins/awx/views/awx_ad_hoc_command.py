# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    ApiView,
)
from beehive_resource.plugins.awx.entity.awx_ad_hoc_command import AwxAdHocCommand
from beehive_resource.plugins.provider.views import (
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
from beehive_resource.plugins.awx.views import AwxAPI, AwxApiView


class AwxAdHocCommandView(AwxApiView):
    tags = ["awx"]
    resclass = AwxAdHocCommand
    parentclass = None


class ListAwxAdHocCommandsRequestSchema(ListResourcesRequestSchema):
    pass


class ListAwxAdHocCommandsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListAwxAdHocCommandsResponseSchema(PaginatedResponseSchema):
    ad_hoc_command = fields.Nested(
        ListAwxAdHocCommandsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListAwxAdHocCommands(AwxAdHocCommandView):
    summary = "List ad_hoc_command"
    description = "List ad_hoc_command"
    definitions = {
        "ListAwxAdHocCommandsResponseSchema": ListAwxAdHocCommandsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListAwxAdHocCommandsRequestSchema)
    parameters_schema = ListAwxAdHocCommandsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListAwxAdHocCommandsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """List ad_hoc_command"""
        return self.get_resources(controller, **data)


class GetAwxAdHocCommandParamsResponseSchema(ResourceResponseSchema):
    ad_hoc_command = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetAwxAdHocCommandResponseSchema(Schema):
    job_template = fields.Nested(GetAwxAdHocCommandParamsResponseSchema, required=True, allow_none=True)


class GetAwxAdHocCommand(AwxAdHocCommandView):
    summary = "Get job_template"
    description = "Get job_template"
    definitions = {
        "GetAwxAdHocCommandResponseSchema": GetAwxAdHocCommandResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetAwxAdHocCommandResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """Get job_template"""
        return self.get_resource(controller, oid)


class AwxAdHocCommandHostRequestSchema(Schema):
    name = fields.String(
        required=True,
        example="test.nivolapiemonte.it",
        default="",
        description="Host IP or FQDN",
    )
    extra_vars = fields.String(
        description="host variables. Ex: k1:v1;k2:v2",
        default="",
        example="ansible_user:root;ansible_connection:ssh",
    )


class AwxAdHocCommandHostSshCredsRequestSchema(Schema):
    username = fields.String(required=True, example="test", description="Username")
    password = fields.String(required=True, example="test1234", description="Password")


class CreateAwxAdHocCommandParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(
        required=True,
        example="test-job-template",
        default="",
        description="Job template name",
    )
    desc = fields.String(example="test-job-template", default="", description="Job template description")
    ssh_creds = fields.Nested(
        AwxAdHocCommandHostSshCredsRequestSchema,
        required=False,
        description="Ssh credentials",
    )
    ssh_cred_id = fields.String(required=False, description="Ssh credential id")
    extra_vars = fields.String(
        description="Variables used when launching job template. Ex: k1:v1;k2:v2",
        default="",
        example="host_groups:[awx_group_prova, awx_group_test];"
        "host_templates:[Template OS Linux];zabbix_server:10.138.218.29",
    )
    organization = fields.String(required=True, example="1", default="", description="Organization id")
    hosts = fields.Nested(
        AwxAdHocCommandHostRequestSchema,
        required=False,
        many=True,
        allow_none=True,
        description="Hosts to add to inventory",
    )
    verbosity = fields.Integer(
        example=1,
        default=0,
        description="Verbosity: 0 (Normal) (default), 1 (Verbose), "
        "2 (More Verbose), 3 (Debug), 4 (Connection Debug), 5 (WinRM Debug)",
    )
    inventory = fields.String(required=False, example="12", default="", description="inventory id")
    module_name = fields.String(required=False, example="12", missing="shell", description="module name")
    module_args = fields.String(required=False, example="12", default="", description="module args")


class CreateAwxAdHocCommandRequestSchema(Schema):
    job_template = fields.Nested(CreateAwxAdHocCommandParamRequestSchema)


class CreateAwxAdHocCommandBodyRequestSchema(Schema):
    body = fields.Nested(CreateAwxAdHocCommandRequestSchema, context="body")


class CreateAwxAdHocCommand(AwxAdHocCommandView):
    summary = "Create job_template"
    description = "Create job_template"
    definitions = {
        "CreateAwxAdHocCommandRequestSchema": CreateAwxAdHocCommandRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateAwxAdHocCommandBodyRequestSchema)
    parameters_schema = CreateAwxAdHocCommandRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateAwxAdHocCommandTemplateRequestSchema(Schema):
    name = fields.String(
        required=True,
        example="test-job_template",
        default="",
        description="Job_template name",
    )
    desc = fields.String(example="test-job_template", default="", description="Job_template description")


class UpdateAwxAdHocCommandParamRequestSchema(UpdateProviderResourceRequestSchema):
    ad_hoc_command = fields.Nested(
        UpdateAwxAdHocCommandTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator ad_hoc_command to link",
        allow_none=True,
    )


class UpdateAwxAdHocCommandRequestSchema(Schema):
    job_template = fields.Nested(UpdateAwxAdHocCommandParamRequestSchema)


class UpdateAwxAdHocCommandBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateAwxAdHocCommandRequestSchema, context="body")


class UpdateAwxAdHocCommand(AwxAdHocCommandView):
    summary = "Update job_template"
    description = "Update job_template"
    definitions = {
        "UpdateAwxAdHocCommandRequestSchema": UpdateAwxAdHocCommandRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateAwxAdHocCommandBodyRequestSchema)
    parameters_schema = UpdateAwxAdHocCommandRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update AWX job_template"""
        return self.update_resource(controller, oid, data)


class DeleteAwxAdHocCommand(AwxAdHocCommandView):
    summary = "Delete job_template"
    description = "Delete job_template"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class AwxAdHocCommandAPI(AwxAPI):
    """AWX job template api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = AwxAPI.base
        rules = [
            ("%s/ad_hoc_commands" % base, "GET", ListAwxAdHocCommands, {}),
            ("%s/ad_hoc_commands/<oid>" % base, "GET", GetAwxAdHocCommand, {}),
            ("%s/ad_hoc_commands" % base, "POST", CreateAwxAdHocCommand, {}),
            ("%s/ad_hoc_commands/<oid>" % base, "PUT", UpdateAwxAdHocCommand, {}),
            ("%s/ad_hoc_commands/<oid>" % base, "DELETE", DeleteAwxAdHocCommand, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
