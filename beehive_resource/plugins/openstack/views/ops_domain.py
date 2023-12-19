# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView


class OpenstackDomainApiView(OpenstackApiView):
    resclass = OpenstackDomain
    parentclass = None


class ListDomainsRequestSchema(ListResourcesRequestSchema):
    pass


class ListDomainsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListDomainsResponseSchema(PaginatedResponseSchema):
    domains = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListDomains(OpenstackDomainApiView):
    tags = ["openstack"]
    definitions = {
        "ListDomainsResponseSchema": ListDomainsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListDomainsRequestSchema)
    parameters_schema = ListDomainsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListDomainsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List domain
        List domain
        """
        return self.get_resources(controller, **data)


class GetDomainResponseSchema(Schema):
    domain = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetDomain(OpenstackDomainApiView):
    tags = ["openstack"]
    definitions = {
        "GetDomainResponseSchema": GetDomainResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDomainResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get domain
        Get domain
        """
        return self.get_resource(controller, oid)


class OpenstackDomainAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/domains" % base, "GET", ListDomains, {}),
            ("%s/domains/<oid>" % base, "GET", GetDomain, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
