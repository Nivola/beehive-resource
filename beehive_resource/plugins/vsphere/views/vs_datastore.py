# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_datastore import VsphereDatastore
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter


class VsphereDatastoreApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereDatastore
    parentclass = VsphereDatacenter


class ListDatastoresRequestSchema(ListResourcesRequestSchema):
    pass


class ListDatastoresParamsResponseSchema(ResourceResponseSchema):
    pass


class ListDatastoresResponseSchema(PaginatedResponseSchema):
    datastores = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListDatastores(VsphereDatastoreApiView):
    definitions = {
        "ListDatastoresResponseSchema": ListDatastoresResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListDatastoresRequestSchema)
    parameters_schema = ListDatastoresRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListDatastoresResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List datastore
        List datastore
        """
        return self.get_resources(controller, **data)


## get
class GetDatastoreResponseSchema(Schema):
    datastore = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetDatastore(VsphereDatastoreApiView):
    definitions = {
        "GetDatastoreResponseSchema": GetDatastoreResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDatastoreResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get datastore
        Get datastore
        """
        return self.get_resource(controller, oid)


class VsphereDatastoreAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ("%s/datastores" % base, "GET", ListDatastores, {}),
            ("%s/datastores/<oid>" % base, "GET", GetDatastore, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
