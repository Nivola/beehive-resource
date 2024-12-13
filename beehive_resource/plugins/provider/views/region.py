# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.entity.region import Region
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    DeleteResourceRequestSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)


class ProviderRegion(LocalProviderApiView):
    resclass = Region
    parentclass = None


class ListRegionsRequestSchema(ListResourcesRequestSchema):
    pass


class ListRegionsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListRegionsResponseSchema(PaginatedResponseSchema):
    regions = fields.Nested(ListRegionsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListRegions(ProviderRegion):
    summary = "List regions"
    description = "List regions"
    definitions = {
        "ListRegionsResponseSchema": ListRegionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListRegionsRequestSchema)
    parameters_schema = ListRegionsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListRegionsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetRegionParamsResponseSchema(ResourceResponseSchema):
    pass


class GetRegionResponseSchema(Schema):
    region = fields.Nested(GetRegionParamsResponseSchema, required=True, allow_none=True)


class GetRegion(ProviderRegion):
    summary = "Get region"
    description = "Get region"
    definitions = {
        "GetRegionResponseSchema": GetRegionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetRegionResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateRegionParamRequestSchema(CreateProviderResourceRequestSchema):
    geo_area = fields.String(required=True, example="Italy", description="geographic area: Italy, Europe")
    coords = fields.String(
        required=True,
        example="45.514046, 13.007813",
        description="geographic coordinates",
    )


class CreateRegionRequestSchema(Schema):
    region = fields.Nested(CreateRegionParamRequestSchema)


class CreateRegionBodyRequestSchema(Schema):
    body = fields.Nested(CreateRegionRequestSchema, context="body")


class CreateRegion(ProviderRegion):
    summary = "Create region"
    description = "Create region"
    definitions = {
        "CreateRegionRequestSchema": CreateRegionRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateRegionBodyRequestSchema)
    parameters_schema = CreateRegionRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateRegionParamRequestSchema(UpdateProviderResourceRequestSchema):
    geo_area = fields.String(example="Italy", description="geographic area: Italy, Europe")
    coords = fields.String(example="45.514046, 13.007813", description="geographic coordinates")


class UpdateRegionRequestSchema(Schema):
    region = fields.Nested(UpdateRegionParamRequestSchema)


class UpdateRegionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateRegionRequestSchema, context="body")


class UpdateRegion(ProviderRegion):
    summary = "Update region"
    description = "Update region"
    definitions = {
        "UpdateRegionRequestSchema": UpdateRegionRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateRegionBodyRequestSchema)
    parameters_schema = UpdateRegionRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteRegion(ProviderRegion):
    summary = "Delete region"
    description = "Delete region"
    definitions = {"CrudApiObjectResponseSchema": CrudApiObjectResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class RegionProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            ("%s/regions" % base, "GET", ListRegions, {}),
            ("%s/regions/<oid>" % base, "GET", GetRegion, {}),
            ("%s/regions" % base, "POST", CreateRegion, {}),
            ("%s/regions/<oid>" % base, "PUT", UpdateRegion, {}),
            ("%s/regions/<oid>" % base, "DELETE", DeleteRegion, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
