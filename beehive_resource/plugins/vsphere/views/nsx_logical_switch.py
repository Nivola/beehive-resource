# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

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
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch


class VsphereNsxLogicalSwitchApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = NsxLogicalSwitch
    parentclass = NsxManager


class ListNsxLogicalSwitchsRequestSchema(ListResourcesRequestSchema):
    pass


class ListNsxLogicalSwitchsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNsxLogicalSwitchsResponseSchema(PaginatedResponseSchema):
    nsx_logical_switchs = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNsxLogicalSwitchs(VsphereNsxLogicalSwitchApiView):
    definitions = {
        "ListNsxLogicalSwitchsResponseSchema": ListNsxLogicalSwitchsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxLogicalSwitchsRequestSchema)
    parameters_schema = ListNsxLogicalSwitchsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListNsxLogicalSwitchsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """
        List nsx_logical_switch
        List nsx_logical_switch
        """
        return self.get_resources(controller, **data)


class GetNsxLogicalSwitchResponseSchema(Schema):
    nsx_logical_switch = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetNsxLogicalSwitch(VsphereNsxLogicalSwitchApiView):
    definitions = {
        "GetNsxLogicalSwitchResponseSchema": GetNsxLogicalSwitchResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetNsxLogicalSwitchResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx_logical_switch
        Get nsx_logical_switch
        """
        return self.get_resource(controller, oid)


class CreateNsxLogicalSwitchParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test")
    desc = fields.String(required=True, example="test")
    tenant = fields.String(
        required=False,
        example="virtual wire tenant",
        missing="virtual wire tenant",
        description="tenant",
    )
    guest_allowed = fields.Boolean(required=True, example=True, default=True)
    transport_zone = fields.String(required=True, example="12", description="id of the trasport zone")


class CreateNsxLogicalSwitchRequestSchema(Schema):
    nsx_logical_switch = fields.Nested(CreateNsxLogicalSwitchParamRequestSchema, required=True)


class CreateNsxLogicalSwitchBodyRequestSchema(Schema):
    body = fields.Nested(CreateNsxLogicalSwitchRequestSchema, context="body")


class CreateNsxLogicalSwitch(VsphereNsxLogicalSwitchApiView):
    definitions = {
        "CreateNsxLogicalSwitchRequestSchema": CreateNsxLogicalSwitchRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateNsxLogicalSwitchBodyRequestSchema)
    parameters_schema = CreateNsxLogicalSwitchRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create nsx_logical_switch
        Create nsx_logical_switch
        """
        return self.create_resource(controller, data)


class UpdateNsxLogicalSwitchParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    enabled = fields.Boolean(default=True)


class UpdateNsxLogicalSwitchRequestSchema(Schema):
    nsx_logical_switch = fields.Nested(UpdateNsxLogicalSwitchParamRequestSchema)


class UpdateNsxLogicalSwitchBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateNsxLogicalSwitchRequestSchema, context="body")


class UpdateNsxLogicalSwitch(VsphereNsxLogicalSwitchApiView):
    definitions = {
        "UpdateNsxLogicalSwitchRequestSchema": UpdateNsxLogicalSwitchRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateNsxLogicalSwitchBodyRequestSchema)
    parameters_schema = UpdateNsxLogicalSwitchRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update nsx_logical_switch
        Update nsx_logical_switch
        """
        return self.update_resource(controller, data)


## delete
class DeleteNsxLogicalSwitch(VsphereNsxLogicalSwitchApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete nsx_logical_switch
        Delete nsx_logical_switch
        """
        return self.expunge_resource(controller, oid)


class VsphereNsxLogicalSwitchAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + "/network"
        rules = [
            ("%s/nsx_logical_switchs" % base, "GET", ListNsxLogicalSwitchs, {}),
            ("%s/nsx_logical_switchs/<oid>" % base, "GET", GetNsxLogicalSwitch, {}),
            ("%s/nsx_logical_switchs" % base, "POST", CreateNsxLogicalSwitch, {}),
            ("%s/nsx_logical_switchs/<oid>" % base, "PUT", UpdateNsxLogicalSwitch, {}),
            (
                "%s/nsx_logical_switchs/<oid>" % base,
                "DELETE",
                DeleteNsxLogicalSwitch,
                {},
            ),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
