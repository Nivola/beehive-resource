# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class OpenstackFlavorApiView(OpenstackApiView):
    resclass = OpenstackFlavor
    parentclass = OpenstackDomain


class ListFlavorsRequestSchema(ListResourcesRequestSchema):
    pass


class ListFlavorsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListFlavorsResponseSchema(PaginatedResponseSchema):
    flavors = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListFlavors(OpenstackFlavorApiView):
    tags = ["openstack"]
    definitions = {
        "ListFlavorsResponseSchema": ListFlavorsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListFlavorsRequestSchema)
    parameters_schema = ListFlavorsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListFlavorsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List flavor
        List flavor
        """
        return self.get_resources(controller, **data)


class GetFlavorResponseSchema(Schema):
    flavor = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetFlavor(OpenstackFlavorApiView):
    tags = ["openstack"]
    definitions = {
        "GetFlavorResponseSchema": GetFlavorResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetFlavorResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get flavor
        Get flavor
        """
        return self.get_resource(controller, oid)


class CreateFlavorParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, default="test")
    desc = fields.String(required=True, default="test")
    tags = fields.String(default="")
    vcpus = fields.Integer(default="", description="vcpus")
    ram = fields.Integer(default="", description="ram")
    disk = fields.Integer(default="", description="disk")


class CreateFlavorRequestSchema(Schema):
    flavor = fields.Nested(CreateFlavorParamRequestSchema)


class CreateFlavorBodyRequestSchema(Schema):
    body = fields.Nested(CreateFlavorRequestSchema, context="body")


class CreateFlavor(OpenstackFlavorApiView):
    tags = ["openstack"]
    definitions = {
        "CreateFlavorRequestSchema": CreateFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateFlavorBodyRequestSchema)
    parameters_schema = CreateFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create flavor
        Create flavor
        """
        return self.create_resource(controller, data)


class UpdateFlavorParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    enabled = fields.Boolean(default=True)
    extra_specs = fields.Dict(default=False)


class UpdateFlavorRequestSchema(Schema):
    flavor = fields.Nested(UpdateFlavorParamRequestSchema)


class UpdateFlavorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateFlavorRequestSchema, context="body")


class UpdateFlavor(OpenstackFlavorApiView):
    tags = ["openstack"]
    definitions = {
        "UpdateFlavorRequestSchema": UpdateFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateFlavorBodyRequestSchema)
    parameters_schema = UpdateFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update flavor
        Update flavor
        """
        return self.update_resource(controller, oid, data)


class DeleteFlavor(OpenstackFlavorApiView):
    tags = ["openstack"]
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class OpenstackFlavorAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/flavors" % base, "GET", ListFlavors, {}),
            ("%s/flavors/<oid>" % base, "GET", GetFlavor, {}),
            ("%s/flavors" % base, "POST", CreateFlavor, {}),
            ("%s/flavors/<oid>" % base, "PUT", UpdateFlavor, {}),
            ("%s/flavors/<oid>" % base, "DELETE", DeleteFlavor, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
