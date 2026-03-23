# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class VsphereDvpgApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereDvpg
    parentclass = None


class ListDvpgsRequestSchema(ListResourcesRequestSchema):
    pass


class ListDvpgsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListDvpgsResponseSchema(PaginatedResponseSchema):
    dvpgs = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListDvpgs(VsphereDvpgApiView):
    definitions = {"ListDvpgsResponseSchema": ListDvpgsResponseSchema,}
    parameters = SwaggerHelper().get_parameters(ListDvpgsRequestSchema)
    parameters_schema = ListDvpgsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListDvpgsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List dvpg
        """
        return self.get_resources(controller, **data)


## get
class GetDvpgResponseSchema(Schema):
    dvpg = fields.Nested(
        ResourceResponseSchema,
        required=True,
        allow_none=True,
    )


class GetDvpg(VsphereDvpgApiView):
    definitions = {"GetDvpgResponseSchema": GetDvpgResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDvpgResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get dvpg
        """
        return self.get_resource(controller, oid)


## create
class CreateDvpgParamRequestSchema(Schema):
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
            "example": 'test-dvpg',
        },
    )

    physical_network = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'dvs id, uuid or name',
        },
    )

    network_type = fields.String(
        required=False,
        metadata={
            "example": 'vlan',
            "description": 'Only vlan is supported',
        },
    )

    segmentation_id = fields.Integer(
        required=True,
        metadata={
            "example": 567,
            "description": 'Netwrok vlan id',
        },
    )

    numports = fields.Integer(
        required=False,
        metadata={
            "example": 24,
            "description": 'port group intial ports number',
        },
    )


class CreateDvpgRequestSchema(Schema):
    dvpg = fields.Nested(
        CreateDvpgParamRequestSchema,
        required=True,
    )


class CreateDvpgBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateDvpgRequestSchema,
        context="body",
    )


class CreateDvpg(VsphereDvpgApiView):
    definitions = {
        "CreateDvpgRequestSchema": CreateDvpgRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateDvpgBodyRequestSchema)
    parameters_schema = CreateDvpgRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create dvpg
        <p>**segmentation_id**: An isolated segment on he physical network. The
        network_type attribute defines the segmentation model. For example,
        if the network_type value is vlan, this ID is a vlan identifier.
        If the network_type value is gre, this ID is a gre key.</p>
        """
        return self.create_resource(controller, data)


## delete
class DeleteDvpg(VsphereDvpgApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class VsphereDvpgAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + "/network"
        rules = [
            ("%s/dvpgs" % base, "GET", ListDvpgs, {}),
            ("%s/dvpgs/<oid>" % base, "GET", GetDvpg, {}),
            ("%s/dvpgs" % base, "POST", CreateDvpg, {}),
            # ('%s/dvpgs/<oid>' % base, 'PUT', UpdateDvpg, {}),
            ("%s/dvpgs/<oid>" % base, "DELETE", DeleteDvpg, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
