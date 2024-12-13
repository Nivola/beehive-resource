# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)
from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm
from beehive_resource.plugins.ontap.views import OntapNetappApiView, OntapNetappAPI
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema, DiscoverResponseSchema


class OntapNetappSvmApiView(OntapNetappApiView):
    resclass = OntapNetappSvm
    parentclass = None


class ListSvmsRequestSchema(ListResourcesRequestSchema):
    pass


class ListSvmsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSvmsResponseSchema(PaginatedResponseSchema):
    svms = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListSvms(OntapNetappSvmApiView):
    summary = "List Svms"
    description = "List Svms"
    tags = ["ontap_netapp"]
    definitions = {
        "ListSvmsResponseSchema": ListSvmsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSvmsRequestSchema)
    parameters_schema = ListSvmsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListSvmsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetSvmResponseSchema(Schema):
    svm = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetSvm(OntapNetappSvmApiView):
    summary = "Get svm"
    description = "Get svm"
    tags = ["ontap_netapp"]
    definitions = {
        "GetSvmResponseSchema": GetSvmResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetSvmResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class OntapNetappSvmAPI(OntapNetappAPI):
    """OntapNetapp base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OntapNetappAPI.base
        rules = [
            ("%s/svms" % base, "GET", ListSvms, {}),
            ("%s/svms/<oid>" % base, "GET", GetSvm, {}),
        ]

        OntapNetappAPI.register_api(module, rules, **kwargs)
