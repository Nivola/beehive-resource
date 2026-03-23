# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    CrudApiObjectResponseSchema,
)

from beehive_resource.view import (
    ResourceResponseSchema,
    ListResourcesRequestSchema,
    ResourceSmallResponseSchema,
)

from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter


class VsphereFlavorApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereFlavor
    parentclass = VsphereDatacenter


class ListFlavorsRequestSchema(ListResourcesRequestSchema):
    pass


class ListFlavorsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListFlavorsResponseSchema(PaginatedResponseSchema):
    flavors = fields.Nested(
        ListFlavorsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListFlavors(VsphereFlavorApiView):
    definitions = {"ListFlavorsResponseSchema": ListFlavorsResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListFlavorsRequestSchema)
    parameters_schema = ListFlavorsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListFlavorsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List flavor
        """
        return self.get_resources(controller, **data)


class GetFlavorResponseSchema(Schema):
    flavor = fields.Nested(
        ResourceResponseSchema,
        required=True,
        allow_none=True,
    )


class GetFlavor(VsphereFlavorApiView):
    definitions = {"GetFlavorResponseSchema": GetFlavorResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetFlavorResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get flavor
        """
        return self.get_resource(controller, oid)


class CreateFlavorParamRequestSchema(Schema):
    container = fields.String(
        required=True,
        metadata={
            "example": '12',
            "description": 'container id, uuid or name',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'name',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'name',
        },
    )

    datacenter = fields.String(
        required=True,
        metadata={
            "example": '23',
            "description": 'datacenter id, uuid or name',
        },
    )

    tags = fields.String(
        metadata={
            "example": 'prova',
            "description": 'comma separated list of tags',
        },
    )

    core_x_socket = fields.Integer(
        load_default=1,
        metadata={
            "example": 1,
            "description": 'core per socket',
        },
    )

    vcpus = fields.Integer(
        required=True,
        metadata={
            "example": 2,
            "description": 'socket number',
        },
    )

    guest_id = fields.String(
        load_default="centos64Guest",
        metadata={
            "example": 'centos64Guest',
            "description": 'vsphere guest id',
        },
    )

    ram = fields.Integer(
        required=True,
        metadata={
            "example": 1024,
            "description": 'memory',
        },
    )

    version = fields.String(
        load_default="vmx-11",
        metadata={
            "example": 'vmx-11',
            "description": 'virtual machine version',
        },
    )

    disk = fields.Integer(
        required=True,
        metadata={
            "example": 40,
            "description": 'size of main disk in GB',
        },
    )


class CreateFlavorRequestSchema(Schema):
    flavor = fields.Nested(CreateFlavorParamRequestSchema)


class CreateFlavorBodyRequestSchema(Schema):
    body = fields.Nested(CreateFlavorRequestSchema, context="body")


class CreateFlavor(VsphereFlavorApiView):
    definitions = {
        "CreateFlavorRequestSchema": CreateFlavorRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateFlavorBodyRequestSchema)
    parameters_schema = CreateFlavorRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create flavor
        """
        return self.create_resource(controller, data)


class UpdateFlavorParamRequestSchema(Schema):
    name = fields.String(
        metadata={
            "example": 'test',
        },
    )

    desc = fields.String(
        metadata={
            "example": 'test',
        },
    )

    enabled = fields.Boolean(
        metadata={
            "example": True,
        },
    )


class UpdateFlavorRequestSchema(Schema):
    flavor = fields.Nested(UpdateFlavorParamRequestSchema)


class UpdateFlavorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateFlavorRequestSchema, context="body")


class UpdateFlavor(VsphereFlavorApiView):
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
        """
        return self.update_resource(controller, oid, data)


class DeleteFlavor(VsphereFlavorApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class VsphereFlavorAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ("%s/flavors" % base, "GET", ListFlavors, {}),
            ("%s/flavors/<oid>" % base, "GET", GetFlavor, {}),
            ("%s/flavors" % base, "POST", CreateFlavor, {}),
            ("%s/flavors/<oid>" % base, "PUT", UpdateFlavor, {}),
            ("%s/flavors/<oid>" % base, "DELETE", DeleteFlavor, {}),
            # ('%s/flavors/<oid>/datastores' % base, 'GET', GetFlavorDatastores, {}),
            # ('%s/flavors/<oid>/datastores' % base, 'POST', AddFlavorDatastores, {}),
            # ('%s/flavors/<oid>/datastores' % base, 'DELETE', DeleteFlavorDatastores, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
