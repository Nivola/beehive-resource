# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_dvs import VsphereDvs
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder


class VsphereDvsApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereDvs
    parentclass = VsphereFolder


class ListDvssRequestSchema(ListResourcesRequestSchema):
    pass


class ListDvssParamsResponseSchema(ResourceResponseSchema):
    pass


class ListDvssResponseSchema(PaginatedResponseSchema):
    dvss = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListDvss(VsphereDvsApiView):
    definitions = {
        "ListDvssResponseSchema": ListDvssResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListDvssRequestSchema)
    parameters_schema = ListDvssRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListDvssResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List dvs
        List dvs
        """
        return self.get_resources(controller, **data)


## get
class GetDvsResponseSchema(Schema):
    dvs = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetDvs(VsphereDvsApiView):
    definitions = {
        "GetDvsResponseSchema": GetDvsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDvsResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get dvs
        Get dvs
        """
        return self.get_resource(controller, oid)


## runtime
class GetDvsRuntimeItemResponseSchema(Schema):
    detail = fields.Raw(required=True, example=None)
    host = fields.Dict(required=True, example={"id": 1, "name": "esxi1"})
    status = fields.String(required=True, example="up")


class GetDvsRuntimeResponseSchema(Schema):
    dvs_runtime = fields.Nested(GetDvsRuntimeItemResponseSchema, required=True, allow_none=True)


class GetDvsRuntime(VsphereApiView):
    definitions = {
        "GetDvsRuntimeResponseSchema": GetDvsRuntimeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDvsRuntimeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get dvs runtime
        Get dvs runtime
        """
        obj = self.get_resource(controller, oid)
        resp = obj.get_runtime()
        return resp


## portgroup
class GetDvsPortgroupItemResponseSchema(Schema):
    autoExpand = fields.Boolean(required=True, example=True)
    configVersion = fields.String(required=True, example="0")
    description = fields.String(required=True, example=None)
    ext_id = fields.String(required=True, example="dvportgroup-123")
    id = fields.Integer(required=True, example=979)
    name = fields.String(required=True, example="CARBON_dvpg-510_Vmotion")
    numPorts = fields.Integer(required=True, example=8)
    portKeys = fields.List(fields.String, required=True, example=["2", "3", "4", "5", "6", "7", "8", "9"])
    type = fields.String(required=True, example="earlyBinding")
    vlan = fields.Integer(required=True, example=510)


class GetDvsPortgroupResponseSchema(Schema):
    dvs = fields.Nested(GetDvsPortgroupItemResponseSchema, required=True, allow_none=True)


class GetDvsPortgroup(VsphereApiView):
    definitions = {
        "GetDvsPortgroupResponseSchema": GetDvsPortgroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDvsPortgroupResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get dvs portgroups
        Get dvs portgroups
        """
        obj = self.get_resource(controller, oid)
        resp = obj.get_portgroups()
        return resp


class VsphereDvsAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + "/network"
        rules = [
            ("%s/dvss" % base, "GET", ListDvss, {}),
            ("%s/dvss/<oid>" % base, "GET", GetDvs, {}),
            ("%s/dvss/<oid>/runtime" % base, "GET", GetDvsRuntime, {}),
            ("%s/dvss/<oid>/portgroup" % base, "GET", GetDvsPortgroup, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
