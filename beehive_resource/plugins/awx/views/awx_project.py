# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    ApiView,
)
from beehive_resource.plugins.awx.entity.awx_project import AwxProject
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
from beehive_resource.plugins.awx.views import AwxAPI, AwxApiView


class AwxProjectView(AwxApiView):
    tags = ["awx"]
    resclass = AwxProject
    parentclass = None


class ListAwxProjectsRequestSchema(ListResourcesRequestSchema):
    pass


class ListAwxProjectsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListAwxProjectsResponseSchema(PaginatedResponseSchema):
    projects = fields.Nested(ListAwxProjectsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListAwxProjects(AwxProjectView):
    summary = "List projects"
    description = "List projects"
    definitions = {
        "ListAwxProjectsResponseSchema": ListAwxProjectsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListAwxProjectsRequestSchema)
    parameters_schema = ListAwxProjectsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListAwxProjectsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """List AWX projects"""
        return self.get_resources(controller, **data)


class GetAwxProjectParamsResponseSchema(ResourceResponseSchema):
    projects = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetAwxProjectResponseSchema(Schema):
    project = fields.Nested(GetAwxProjectParamsResponseSchema, required=True, allow_none=True)


class GetAwxProject(AwxProjectView):
    summary = "Get project"
    description = "Get project"
    definitions = {
        "GetAwxProjectResponseSchema": GetAwxProjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetAwxProjectResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get AWX project"""
        return self.get_resource(controller, oid)


class CreateAwxProjectParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test-project", default="", description="Project name")
    desc = fields.String(example="test-project", default="", description="Project description")
    organization = fields.String(required=True, example="1", default="Default", description="Organization name")
    scm_type = fields.String(
        required=True,
        example="git",
        default="git",
        description="The source control system used to store the project",
    )
    scm_url = fields.String(
        required=True,
        example="https://github.com/awx_projects/nginx",
        default="",
        description="The location where the project is stored",
    )
    scm_branch = fields.String(
        example="1.6.0",
        default="master",
        description="Specific branch, tag or commit to checkout",
    )
    scm_update_on_launch = fields.Boolean(
        default="False",
        description="Update the project when a job using the project is launched",
    )
    scm_creds_name = fields.String(required=True, example="git-test-creds", description="SCM credentials name")


class CreateAwxProjectRequestSchema(Schema):
    project = fields.Nested(CreateAwxProjectParamRequestSchema)


class CreateAwxProjectBodyRequestSchema(Schema):
    body = fields.Nested(CreateAwxProjectRequestSchema, context="body")


class CreateAwxProject(AwxProjectView):
    summary = "Create project"
    description = "Create project"
    definitions = {
        "CreateAwxProjectRequestSchema": CreateAwxProjectRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateAwxProjectBodyRequestSchema)
    parameters_schema = CreateAwxProjectRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new project to AWX"""
        return self.create_resource(controller, data)


class UpdateAwxProjectTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="test-project", default="", description="Project name")
    desc = fields.String(example="test-project", default="", description="Project description")


class UpdateAwxProjectParamRequestSchema(UpdateProviderResourceRequestSchema):
    projects = fields.Nested(
        UpdateAwxProjectTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator projects to link",
        allow_none=True,
    )


class UpdateAwxProjectRequestSchema(Schema):
    project = fields.Nested(UpdateAwxProjectParamRequestSchema)


class UpdateAwxProjectBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateAwxProjectRequestSchema, context="body")


class UpdateAwxProject(AwxProjectView):
    summary = "Update project"
    description = "Update project"
    definitions = {
        "UpdateAwxProjectRequestSchema": UpdateAwxProjectRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateAwxProjectBodyRequestSchema)
    parameters_schema = UpdateAwxProjectRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update AWX project"""
        return self.update_resource(controller, oid, data)


class DeleteAwxProject(AwxProjectView):
    summary = "Delete project"
    description = "Delete project"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete AWX project"""
        return self.expunge_resource(controller, oid)


class AwxProjectAPI(AwxAPI):
    """AWX project api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = AwxAPI.base
        rules = [
            ("%s/projects" % base, "GET", ListAwxProjects, {}),
            ("%s/projects/<oid>" % base, "GET", GetAwxProject, {}),
            ("%s/projects" % base, "POST", CreateAwxProject, {}),
            # ('%s/projects/import' % base, 'POST', ImportAwxProject, {}),
            ("%s/projects/<oid>" % base, "PUT", UpdateAwxProject, {}),
            ("%s/projects/<oid>" % base, "DELETE", DeleteAwxProject, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
