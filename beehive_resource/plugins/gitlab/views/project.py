# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.gitlab.entity.project import GitlabProject
from beehive_resource.plugins.gitlab.views import GitlabAPI, GitlabApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)


class GitlabProjectApiView(GitlabApiView):
    tags = ["gitlab"]
    resclass = GitlabProject
    parentclass = None


class ListProjectsRequestSchema(ListResourcesRequestSchema):
    pass


class ListProjectsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListProjectsResponseSchema(PaginatedResponseSchema):
    # projects = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)
    projects = fields.List(fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True))


class ListProjects(GitlabProjectApiView):
    summary = "List projects"
    description = "List projects"
    definitions = {
        "ListProjectsResponseSchema": ListProjectsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListProjectsRequestSchema)
    parameters_schema = ListProjectsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListProjectsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetProjectResponseSchema(Schema):
    project = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetProject(GitlabProjectApiView):
    summary = "Get project"
    description = "Get project"
    definitions = {
        "GetProjectResponseSchema": GetProjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetProjectResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class ProjectInterfaceRequestSchema(Schema):
    ip_addr = fields.String(required=True, example="192.168.3.1", default="127.0.0.1")
    port = fields.String(required=True, example="10050", default="10050")


class CreateProjectParamRequestSchema(Schema):
    container = fields.String(required=True, example="1234", description="container id, uuid or name")
    name = fields.String(required=True, example="linux server")
    desc = fields.String(required=False, example="project description")
    status = fields.Integer(
        required=False,
        default=0,
        description="0 - (default) monitored project; 1 - unmonitored project",
        validate=OneOf([0, 1]),
    )
    interfaces = fields.Nested(
        ProjectInterfaceRequestSchema,
        required=True,
        many=True,
        allow_none=True,
        description="interfaces to be created for the project",
    )
    projects = fields.List(
        fields.String(
            required=True,
            example="['50', '62']",
            many=True,
            allow_none=True,
            description="ids of project to add the project to",
        )
    )
    templates = fields.List(
        fields.String(
            required=False,
            example="['20045']",
            many=True,
            allow_none=True,
            description="ids of templates to be linked to the project",
        )
    )


class CreateProjectRequestSchema(Schema):
    project = fields.Nested(CreateProjectParamRequestSchema)


class CreateProjectBodyRequestSchema(Schema):
    body = fields.Nested(CreateProjectRequestSchema, context="body")


class CreateProject(GitlabProjectApiView):
    summary = "Create project"
    description = "Create project"
    definitions = {
        "CreateProjectRequestSchema": CreateProjectRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateProjectBodyRequestSchema)
    parameters_schema = CreateProjectRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateProjectParamRequestSchema(Schema):
    name = fields.String(default="")
    desc = fields.String(default="")
    status = fields.Integer(default=0)


class UpdateProjectRequestSchema(Schema):
    project = fields.Nested(UpdateProjectParamRequestSchema)


class UpdateProjectBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateProjectRequestSchema, context="body")


class UpdateProject(GitlabProjectApiView):
    summary = "Update project"
    description = "Update project"
    definitions = {
        "UpdateProjectRequestSchema": UpdateProjectRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateProjectBodyRequestSchema)
    parameters_schema = UpdateProjectRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteProject(GitlabProjectApiView):
    summary = "Delete project"
    description = "Delete project"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GitlabProjectAPI(GitlabAPI):
    """Gitlab base platform api routes"""

    @staticmethod
    def register_api(module, *args, **kwargs):
        base = GitlabAPI.base
        rules = [
            ("%s/projects" % base, "GET", ListProjects, {}),
            ("%s/projects/<oid>" % base, "GET", GetProject, {}),
            ("%s/projects" % base, "POST", CreateProject, {}),
            ("%s/projects/<oid>" % base, "PUT", UpdateProject, {}),
            ("%s/projects/<oid>" % base, "DELETE", DeleteProject, {}),
        ]

        GitlabAPI.register_api(module, rules, **kwargs)
