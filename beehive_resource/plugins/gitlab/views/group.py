# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.gitlab.entity.group import GitlabGroup
from beehive_resource.plugins.gitlab.views import GitlabAPI, GitlabApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiTaskResponseSchema,
)


class GitlabGroupApiView(GitlabApiView):
    tags = ["gitlab"]
    resclass = GitlabGroup
    parentclass = None


class ListGroupsRequestSchema(ListResourcesRequestSchema):
    pass


class ListGroupsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListGroupsResponseSchema(PaginatedResponseSchema):
    # groups = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)
    groups = fields.List(fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True))


class ListGroups(GitlabGroupApiView):
    summary = "List groups"
    description = "List groups"
    definitions = {
        "ListGroupsResponseSchema": ListGroupsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListGroupsRequestSchema)
    parameters_schema = ListGroupsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListGroupsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetGroupResponseSchema(Schema):
    group = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetGroup(GitlabGroupApiView):
    summary = "Get group"
    description = "Get group"
    definitions = {
        "GetGroupResponseSchema": GetGroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetGroupResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class GroupInterfaceRequestSchema(Schema):
    ip_addr = fields.String(required=True, example="192.168.3.1", default="127.0.0.1")
    port = fields.String(required=True, example="10050", default="10050")


class CreateGroupParamRequestSchema(Schema):
    container = fields.String(required=True, example="1234", description="container id, uuid or name")
    name = fields.String(required=True, example="linux server")
    desc = fields.String(required=False, example="group description")
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


class CreateGroupRequestSchema(Schema):
    group = fields.Nested(CreateGroupParamRequestSchema)


class CreateGroupBodyRequestSchema(Schema):
    body = fields.Nested(CreateGroupRequestSchema, context="body")


class CreateGroup(GitlabGroupApiView):
    summary = "Create group"
    description = "Create group"
    definitions = {
        "CreateGroupRequestSchema": CreateGroupRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateGroupBodyRequestSchema)
    parameters_schema = CreateGroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateGroupParamRequestSchema(Schema):
    name = fields.String(default="")
    desc = fields.String(default="")
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


class UpdateGroupRequestSchema(Schema):
    group = fields.Nested(UpdateGroupParamRequestSchema)


class UpdateGroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateGroupRequestSchema, context="body")


class UpdateGroup(GitlabGroupApiView):
    summary = "Update group"
    description = "Update group"
    definitions = {
        "UpdateGroupRequestSchema": UpdateGroupRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateGroupBodyRequestSchema)
    parameters_schema = UpdateGroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteGroupParamRequestSchema(Schema):
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


class DeleteGroupRequestSchema(Schema):
    group = fields.Nested(DeleteGroupParamRequestSchema)


class DeleteGroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteGroupRequestSchema, context="body")


class DeleteGroup(GitlabGroupApiView):
    summary = "Delete group"
    description = "Delete group"
    definitions = {
        "DeleteGroupRequestSchema": DeleteGroupRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateGroupBodyRequestSchema)
    parameters_schema = DeleteGroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid, **data.get("group"))


class GitlabGroupAPI(GitlabAPI):
    """Gitlab base platform api routes"""

    @staticmethod
    def register_api(module, *args, **kwargs):
        base = GitlabAPI.base
        rules = [
            ("%s/groups" % base, "GET", ListGroups, {}),
            ("%s/groups/<oid>" % base, "GET", GetGroup, {}),
            ("%s/groups" % base, "POST", CreateGroup, {}),
            ("%s/groups/<oid>" % base, "PUT", UpdateGroup, {}),
            ("%s/groups/<oid>" % base, "DELETE", DeleteGroup, {}),
        ]

        GitlabAPI.register_api(module, rules, **kwargs)
