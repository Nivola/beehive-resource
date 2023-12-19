# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject


class OpenstackOpsStackApiView(OpenstackApiView):
    tags = ["openstack"]
    resclass = OpenstackHeatStack
    parentclass = OpenstackProject


class ListOpsStackRequestSchema(ListResourcesRequestSchema):
    pass


class ListOpsStackParamsResponseSchema(ResourceResponseSchema):
    pass


class ListOpsStackResponseSchema(PaginatedResponseSchema):
    stacks = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListOpsStack(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "ListOpsStackResponseSchema": ListOpsStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListOpsStackRequestSchema)
    parameters_schema = ListOpsStackRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListOpsStackResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List Stack
        List Stack
        """
        return self.get_resources(controller, **data)


class GetOpsStackResponseSchema(Schema):
    stack = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetOpsStack(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackResponseSchema": GetOpsStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetOpsStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack
        Get Stack
        """
        return self.get_resource(controller, oid)


class GetOpsStackTemplateResponseSchema(Schema):
    stack_template = fields.List(fields.Dict, required=True)


class GetOpsStackTemplate(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackTemplateResponseSchema": GetOpsStackTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetOpsStackTemplateResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack template
        Get Stack template
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_template()
        return {"stack_template": res}


class GetOpsStackEnvironmentResponseSchema(Schema):
    stack_environment = fields.List(fields.Dict, required=True)


class GetOpsStackEnvironment(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackEnvironmentResponseSchema": GetOpsStackEnvironmentResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetOpsStackEnvironmentResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack environment
        Get Stack environment
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_environment()
        return {"stack_environment": res}


class GetOpsStackFilesResponseSchema(Schema):
    stack_files = fields.List(fields.Dict, required=True)


class GetOpsStackFiles(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackFilesResponseSchema": GetOpsStackFilesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetOpsStackFilesResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack files
        Get Stack files
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_files()
        return {"stack_files": res}


class GetOpsStackOutputsResponseSchema(Schema):
    stack_outputs = fields.List(fields.Dict, required=True)


class GetOpsStackOutputs(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackOutputsResponseSchema": GetOpsStackOutputsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetOpsStackOutputsResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack outputs
        Get Stack outputs
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_outputs()
        return {"stack_ouputs": res}


class GetOpsStackResourcesResponseSchema(Schema):
    stack_resources = fields.List(fields.Dict, required=True)


class GetOpsStackResources(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackResourcesResponseSchema": GetOpsStackResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetOpsStackResourcesResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack resources
        Get Stack resources
        """
        stack = self.get_resource_reference(controller, oid)
        res, total = stack.get_stack_resources(*args, **kwargs)
        resp = [i.info() for i in res if i is not None]
        return self.format_paginated_response(resp, "resources", total, **kwargs)


class GetOpsStackInternalResourcesResponseSchema(Schema):
    stack_resources = fields.List(fields.Dict, required=True)


class GetOpsStackInternalResources(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackInternalResourcesResponseSchema": GetOpsStackInternalResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetOpsStackInternalResourcesResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack resources
        Get Stack resources
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_stack_internal_resources()
        return {"stack_resources": res}


class GetOpsStackEventsResponseSchema(Schema):
    stack_events = fields.List(fields.Dict, required=True)


class GetOpsStackEvents(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "GetOpsStackEventsResponseSchema": GetOpsStackEventsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetOpsStackEventsResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack events
        Get Stack events
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_events()
        return {"stack_events": res}


class CreateOpsStackParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test", description="name")
    desc = fields.String(required=True, example="test", description="name")
    project = fields.String(required=True, example="23", description="project id, uuid or name")
    tags = fields.String(
        example="test_api,tag_test_api",
        default="",
        description="comma separated list of tags",
    )
    template_uri = fields.String(
        required=True,
        example="",
        default="",
        description="A URI to the location containing the stack template on which to "
        "perform the operation. See the description of the template parameter "
        "for information about the expected template content located at the URI.",
    )
    environment = fields.Dict(
        example={},
        default={},
        description="A JSON environment for the stack.",
        allow_none=True,
    )
    parameters = fields.Dict(
        example={"key_name": "opstkcsi"},
        default={"key_name": "opstkcsi"},
        allow_none=True,
        description="Supplies arguments for parameters defined in the stack template.",
    )
    files = fields.Dict(
        example={"myfile": '#!\/bin\/bash\necho "Hello world" > \/root\/testfile.txt'},
        default={"myfile": '#!\/bin\/bash\necho "Hello world" > \/root\/testfile.txt'},
        description="Supplies the contents of files referenced in the template or the environment.",
        allow_none=True,
    )
    owner = fields.String(required=True, example="admin", default="admin", description="stack owner name")


class CreateOpsStackRequestSchema(Schema):
    stack = fields.Nested(CreateOpsStackParamRequestSchema)


class CreateOpsStackBodyRequestSchema(Schema):
    body = fields.Nested(CreateOpsStackRequestSchema, context="body")


class CreateOpsStack(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "CreateOpsStackRequestSchema": CreateOpsStackRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateOpsStackBodyRequestSchema)
    parameters_schema = CreateOpsStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create Stack
        Create Stack
        """
        return self.create_resource(controller, data)


class UpdateOpsStackParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")


class UpdateOpsStackRequestSchema(Schema):
    stack = fields.Nested(UpdateOpsStackParamRequestSchema)


class UpdateOpsStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateOpsStackRequestSchema, context="body")


class UpdateOpsStack(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {
        "UpdateOpsStackRequestSchema": UpdateOpsStackRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateOpsStackBodyRequestSchema)
    parameters_schema = UpdateOpsStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update Stack
        Update Stack
        """
        return self.update_resource(controller, oid, data)


class DeleteOpsStack(OpenstackOpsStackApiView):
    tags = ["openstack"]
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class OpenstackStackAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/stacks" % base, "GET", ListOpsStack, {}),
            ("%s/stacks/<oid>" % base, "GET", GetOpsStack, {}),
            ("%s/stacks/<oid>/template" % base, "GET", GetOpsStackTemplate, {}),
            ("%s/stacks/<oid>/environment" % base, "GET", GetOpsStackEnvironment, {}),
            ("%s/stacks/<oid>/files" % base, "GET", GetOpsStackFiles, {}),
            ("%s/stacks/<oid>/outputs" % base, "GET", GetOpsStackOutputs, {}),
            ("%s/stacks/<oid>/resources" % base, "GET", GetOpsStackResources, {}),
            (
                "%s/stacks/<oid>/internal_resources" % base,
                "GET",
                GetOpsStackInternalResources,
                {},
            ),
            ("%s/stacks/<oid>/events" % base, "GET", GetOpsStackEvents, {}),
            ("%s/stacks" % base, "POST", CreateOpsStack, {}),
            ("%s/stacks/<oid>" % base, "PUT", UpdateOpsStack, {}),
            ("%s/stacks/<oid>" % base, "DELETE", DeleteOpsStack, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
