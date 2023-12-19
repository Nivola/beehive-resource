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
from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate
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


class AwxJobTemplateView(AwxApiView):
    tags = ["awx"]
    resclass = AwxJobTemplate
    parentclass = None


class ListAwxJobTemplatesRequestSchema(ListResourcesRequestSchema):
    pass


class ListAwxJobTemplatesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListAwxJobTemplatesResponseSchema(PaginatedResponseSchema):
    job_templates = fields.Nested(
        ListAwxJobTemplatesParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListAwxJobTemplates(AwxJobTemplateView):
    summary = "List job_templates"
    description = "List job_templates"
    definitions = {
        "ListAwxJobTemplatesResponseSchema": ListAwxJobTemplatesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListAwxJobTemplatesRequestSchema)
    parameters_schema = ListAwxJobTemplatesRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListAwxJobTemplatesResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """List job_templates"""
        return self.get_resources(controller, **data)


class GetAwxJobTemplateParamsResponseSchema(ResourceResponseSchema):
    job_templates = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetAwxJobTemplateResponseSchema(Schema):
    job_template = fields.Nested(GetAwxJobTemplateParamsResponseSchema, required=True, allow_none=True)


class GetAwxJobTemplate(AwxJobTemplateView):
    summary = "Get job_template"
    description = "Get job_template"
    definitions = {
        "GetAwxJobTemplateResponseSchema": GetAwxJobTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetAwxJobTemplateResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """Get job_template"""
        return self.get_resource(controller, oid)


class AwxJobTemplateHostRequestSchema(Schema):
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


class AwxJobTemplateHostSshCredsRequestSchema(Schema):
    username = fields.String(required=True, example="test", description="Username")
    password = fields.String(required=True, example="test1234", description="Password")


class CreateAwxJobTemplateAddParamRequestSchema(Schema):
    organization = fields.String(required=True, example="1", default="", description="Organization id")
    hosts = fields.Nested(
        AwxJobTemplateHostRequestSchema,
        required=False,
        many=True,
        allow_none=True,
        description="Hosts to add to inventory",
    )
    project = fields.String(
        required=True,
        example="test-project",
        default="",
        description="Awx project name",
    )
    playbook = fields.String(required=True, example="main.yml", default="", description="Playbook")
    verbosity = fields.Integer(
        example=1,
        default=0,
        description="Verbosity: 0 (Normal) (default), 1 (Verbose), "
        "2 (More Verbose), 3 (Debug), 4 (Connection Debug), 5 (WinRM Debug)",
    )
    inventory = fields.String(required=False, example="12", default="", description="inventory id")


class CreateAwxJobTemplateLaunchParamRequestSchema(Schema):
    ssh_creds = fields.Nested(
        AwxJobTemplateHostSshCredsRequestSchema,
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


class CreateAwxJobTemplateParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(
        required=True,
        example="test-job-template",
        default="",
        description="Job template name",
    )
    desc = fields.String(example="test-job-template", default="", description="Job template description")
    add = fields.Nested(
        CreateAwxJobTemplateAddParamRequestSchema,
        required=True,
        description="List of parameters to create an awx job template",
    )
    launch = fields.Nested(
        CreateAwxJobTemplateLaunchParamRequestSchema,
        required=True,
        description="List of parameters to run an awx job template",
    )


class CreateAwxJobTemplateRequestSchema(Schema):
    job_template = fields.Nested(CreateAwxJobTemplateParamRequestSchema)


class CreateAwxJobTemplateBodyRequestSchema(Schema):
    body = fields.Nested(CreateAwxJobTemplateRequestSchema, context="body")


class CreateAwxJobTemplate(AwxJobTemplateView):
    summary = "Create job_template"
    description = "Create job_template"
    definitions = {
        "CreateAwxJobTemplateRequestSchema": CreateAwxJobTemplateRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateAwxJobTemplateBodyRequestSchema)
    parameters_schema = CreateAwxJobTemplateRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Create AWX job_template"""
        return self.create_resource(controller, data)


class UpdateAwxJobTemplateTemplateRequestSchema(Schema):
    name = fields.String(
        required=True,
        example="test-job_template",
        default="",
        description="Job_template name",
    )
    desc = fields.String(example="test-job_template", default="", description="Job_template description")


class UpdateAwxJobTemplateParamRequestSchema(UpdateProviderResourceRequestSchema):
    job_templates = fields.Nested(
        UpdateAwxJobTemplateTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator job_templates to link",
        allow_none=True,
    )


class UpdateAwxJobTemplateRequestSchema(Schema):
    job_template = fields.Nested(UpdateAwxJobTemplateParamRequestSchema)


class UpdateAwxJobTemplateBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateAwxJobTemplateRequestSchema, context="body")


class UpdateAwxJobTemplate(AwxJobTemplateView):
    summary = "Update job_template"
    description = "Update job_template"
    definitions = {
        "UpdateAwxJobTemplateRequestSchema": UpdateAwxJobTemplateRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateAwxJobTemplateBodyRequestSchema)
    parameters_schema = UpdateAwxJobTemplateRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update AWX job_template"""
        return self.update_resource(controller, oid, data)


class DeleteAwxJobTemplate(AwxJobTemplateView):
    summary = "Delete job_template"
    description = "Delete job_template"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class AwxJobTemplateAPI(AwxAPI):
    """AWX job template api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = AwxAPI.base
        rules = [
            ("%s/job_templates" % base, "GET", ListAwxJobTemplates, {}),
            ("%s/job_templates/<oid>" % base, "GET", GetAwxJobTemplate, {}),
            ("%s/job_templates" % base, "POST", CreateAwxJobTemplate, {}),
            ("%s/job_templates/<oid>" % base, "PUT", UpdateAwxJobTemplate, {}),
            ("%s/job_templates/<oid>" % base, "DELETE", DeleteAwxJobTemplate, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
