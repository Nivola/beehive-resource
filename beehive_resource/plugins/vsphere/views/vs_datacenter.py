# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class VsphereDatacenterApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereDatacenter
    parentclass = None


class ListDatacentersRequestSchema(ListResourcesRequestSchema):
    pass


class ListDatacentersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListDatacentersResponseSchema(PaginatedResponseSchema):
    datacenters = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListDatacenters(VsphereDatacenterApiView):
    definitions = {
        "ListDatacentersResponseSchema": ListDatacentersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListDatacentersRequestSchema)
    parameters_schema = ListDatacentersRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListDatacentersResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List datacenter
        List datacenter
        """
        return self.get_resources(controller, **data)


class GetDatacenterResponseSchema(Schema):
    datacenter = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetDatacenter(VsphereDatacenterApiView):
    definitions = {
        "GetDatacenterResponseSchema": GetDatacenterResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDatacenterResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get datacenter
        Get datacenter
        """
        return self.get_resource(controller, oid)


class VsphereDatacenterAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ("%s/datacenters" % base, "GET", ListDatacenters, {}),
            ("%s/datacenters/<oid>" % base, "GET", GetDatacenter, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
