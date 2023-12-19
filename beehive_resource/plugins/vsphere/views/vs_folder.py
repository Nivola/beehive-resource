# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder


class VsphereFolderApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereFolder
    parentclass = None


class ListFoldersRequestSchema(ListResourcesRequestSchema):
    pass


class ListFoldersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListFoldersResponseSchema(PaginatedResponseSchema):
    folders = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListFolders(VsphereFolderApiView):
    definitions = {
        "ListFoldersResponseSchema": ListFoldersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListFoldersRequestSchema)
    parameters_schema = ListFoldersRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListFoldersResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List folder
        List folder
        """
        return self.get_resources(controller, **data)


class GetFolderResponseSchema(Schema):
    folder = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetFolder(VsphereFolderApiView):
    definitions = {
        "GetFolderResponseSchema": GetFolderResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetFolderResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get folder
        Get folder
        """
        return self.get_resource(controller, oid)


class CreateFolderParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test")
    desc = fields.String(required=True, example="test")
    folder_type = fields.String(
        required=False,
        example="vm",
        default="vm",
        description="folder type. Can be: host, network, storage, vm",
        validate=OneOf(["host", "network", "storage", "vm"]),
    )
    folder = fields.String(example=1, description="parent folder id or uuid")
    datacenter = fields.String(example=1, description="parent datacenter id or uuid")
    tags = fields.String(default="", description="comma separated resource tags to assign")


class CreateFolderRequestSchema(Schema):
    folder = fields.Nested(CreateFolderParamRequestSchema, required=True)


class CreateFolderBodyRequestSchema(Schema):
    body = fields.Nested(CreateFolderRequestSchema, context="body")


class CreateFolder(VsphereFolderApiView):
    definitions = {
        "CreateFolderRequestSchema": CreateFolderRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateFolderBodyRequestSchema)
    parameters_schema = CreateFolderRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create folder
        Create folder
        """
        return self.create_resource(controller, data)


## update
class UpdateFolderParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    enabled = fields.Boolean(default=True)


class UpdateFolderRequestSchema(Schema):
    folder = fields.Nested(UpdateFolderParamRequestSchema)


class UpdateFolderBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateFolderRequestSchema, context="body")


class UpdateFolder(VsphereFolderApiView):
    definitions = {
        "UpdateFolderRequestSchema": UpdateFolderRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateFolderBodyRequestSchema)
    parameters_schema = UpdateFolderRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update folder
        Update folder
        """
        return self.update_resource(controller, data)


## delete
class DeleteFolder(VsphereFolderApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class VsphereFolderAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ("%s/folders" % base, "GET", ListFolders, {}),
            ("%s/folders/<oid>" % base, "GET", GetFolder, {}),
            ("%s/folders" % base, "POST", CreateFolder, {}),
            ("%s/folders/<oid>" % base, "PUT", UpdateFolder, {}),
            ("%s/folders/<oid>" % base, "DELETE", DeleteFolder, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
