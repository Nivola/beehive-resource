# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatTemplate
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import SwaggerApiView
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject


class OpenstackStackTemplateApiView(OpenstackApiView):
    tags = ["openstack"]
    resclass = OpenstackHeatTemplate
    parentclass = OpenstackProject


class GetOpsStackTemplateVersionsRequestSchema(Schema):
    container = fields.String(
        required=True,
        context="query",
        description="resource container id, uuid or name",
    )


class GetOpsStackTemplateVersionsResponseSchema(Schema):
    template_versions = fields.List(fields.String, required=True)


class GetOpsStackTemplateVersions(OpenstackStackTemplateApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackTemplateVersionsRequestSchema": GetOpsStackTemplateVersionsRequestSchema,
        "GetOpsStackTemplateVersionsResponseSchema": GetOpsStackTemplateVersionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetOpsStackTemplateVersionsRequestSchema)
    parameters_schema = GetOpsStackTemplateVersionsRequestSchema
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetOpsStackTemplateVersionsResponseSchema,
            }
        }
    )

    def get(self, controller, data, *args, **kwargs):
        """
        Get heat template versions
        Get heat template versions
        """
        container_id = data.get("container")
        orchestrator = self.get_container(controller, container_id)
        heat = orchestrator.get_heat_resource()
        res = heat.get_template_versions()
        return res


class GetOpsStackTemplateFunctionsRequestSchema(Schema):
    container = fields.String(
        required=True,
        context="query",
        description="resource container id, uuid or name",
    )
    template = fields.String(required=True, context="query", description="template reference from versions")


class GetOpsStackTemplateFunctionsResponseSchema(Schema):
    template_functions = fields.List(fields.Dict, required=True)


class GetOpsStackTemplateFunctions(OpenstackStackTemplateApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackTemplateFunctionsRequestSchema": GetOpsStackTemplateFunctionsRequestSchema,
        "GetOpsStackTemplateFunctionsResponseSchema": GetOpsStackTemplateFunctionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetOpsStackTemplateFunctionsRequestSchema)
    parameters_schema = GetOpsStackTemplateFunctionsRequestSchema
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetOpsStackTemplateFunctionsResponseSchema,
            }
        }
    )

    def get(self, controller, data, *args, **kwargs):
        """
        Get heat template functions
        Get heat template functions
        """
        container_id = data.get("container")
        template = data.get("template")
        orchestrator = self.get_container(controller, container_id)
        heat = orchestrator.get_heat_resource()
        res = heat.get_template_functions(template)
        return res


class ValidateTemplateParamsRequestSchema(Schema):
    container = fields.String(required=True, description="resource container id, uuid or name")
    template_uri = fields.String(required=True, description="template remote http uri")


class ValidateTemplateRequestSchema(Schema):
    stack_template = fields.Nested(ValidateTemplateParamsRequestSchema)


class ValidateTemplateBodyRequestSchema(Schema):
    body = fields.Nested(ValidateTemplateRequestSchema, context="body")


class ValidateTemplateResponseSchema(Schema):
    validate = fields.Boolean(required=True, example=True)


class ValidateTemplate(OpenstackStackTemplateApiView):
    tags = ["openstack"]
    definitions = {
        "ValidateTemplateRequestSchema": ValidateTemplateRequestSchema,
        "ValidateTemplateResponseSchema": ValidateTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ValidateTemplateBodyRequestSchema)
    parameters_schema = ValidateTemplateRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ValidateTemplateResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Get heat template functions
        Get heat template functions
        """
        data = data.get("stack_template")
        container_id = data.get("container")
        template_uri = data.get("template_uri")
        orchestrator = self.get_container(controller, container_id)
        heat = orchestrator.get_heat_resource()
        heat.validate_template(template_uri)
        return {"validate": True}


class OpenstackStackTemplateAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/stack-templates" % base, "GET", GetOpsStackTemplateVersions, {}),
            (
                "%s/stack-template-functions" % base,
                "GET",
                GetOpsStackTemplateFunctions,
                {},
            ),
            ("%s/stack-template-validate" % base, "POST", ValidateTemplate, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
