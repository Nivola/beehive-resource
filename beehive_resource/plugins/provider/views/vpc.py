# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.entity.vpc import Vpc
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)


class ProviderVpc(LocalProviderApiView):
    resclass = Vpc
    parentclass = ComputeZone


class ListVpcsRequestSchema(ListResourcesRequestSchema):
    super_zone = fields.String(context="query", description="super zone id, uuid")


class ListVpcsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVpcsResponseSchema(PaginatedResponseSchema):
    vpcs = fields.Nested(ListVpcsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListVpcs(ProviderVpc):
    definitions = {
        "ListVpcsResponseSchema": ListVpcsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVpcsRequestSchema)
    parameters_schema = ListVpcsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVpcsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List vpcs
        List vpcs

        # - filter by: tags
        # - filter by: super_zone

        "attributes": {

        }
        """
        zone_id = data.get("super_zone", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "SuperZone")
        return self.get_resources(controller, **data)


class GetVpcParamsResponseSchema(ResourceResponseSchema):
    networks = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetVpcResponseSchema(Schema):
    vpc = fields.Nested(GetVpcParamsResponseSchema, required=True, allow_none=True)


class GetVpc(ProviderVpc):
    definitions = {
        "GetVpcResponseSchema": GetVpcResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVpcResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get vpc
        Get vpc

        "attributes": {

        }
        """
        return self.get_resource(controller, oid)


class CreateVpcParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    multi_avz = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if instance must be deployed to work in all the availability zones",
    )
    networks = fields.List(
        fields.Str(example="2887"),
        required=True,
        description="list of site_network or private_network id or uuid",
    )


class CreateVpcRequestSchema(Schema):
    vpc = fields.Nested(CreateVpcParamRequestSchema)


class CreateVpcBodyRequestSchema(Schema):
    body = fields.Nested(CreateVpcRequestSchema, context="body")


class CreateVpc(ProviderVpc):
    summary = "Create vpc"
    description = "Create vpc"
    definitions = {
        "CreateVpcRequestSchema": CreateVpcRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVpcBodyRequestSchema)
    parameters_schema = CreateVpcRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateVpcParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateVpcRequestSchema(Schema):
    vpc = fields.Nested(UpdateVpcParamRequestSchema)


class UpdateVpcBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVpcRequestSchema, context="body")


class UpdateVpc(ProviderVpc):
    summary = "Update Vpc"
    description = "Update Vpc"
    definitions = {
        "UpdateVpcRequestSchema": UpdateVpcRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateVpcBodyRequestSchema)
    parameters_schema = UpdateVpcRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteVpc(ProviderVpc):
    summary = "Delete Vpc"
    description = "Delete Vpc"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class VpcProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/vpcs" % base, "GET", ListVpcs, {}),
            ("%s/vpcs/<oid>" % base, "GET", GetVpc, {}),
            ("%s/vpcs" % base, "POST", CreateVpc, {}),
            ("%s/vpcs/<oid>" % base, "PUT", UpdateVpc, {}),
            ("%s/vpcs/<oid>" % base, "DELETE", DeleteVpc, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
