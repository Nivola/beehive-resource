# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.provider.entity.region import Region
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    DeleteResourceRequestSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiTaskResponseSchema,
    CrudApiObjectTaskResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)
from marshmallow.validate import OneOf


class ProviderSite(LocalProviderApiView):
    resclass = Site
    parentclass = Region


class ListSitesRequestSchema(ListResourcesRequestSchema):
    pass


class ListSitesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSitesResponseSchema(PaginatedResponseSchema):
    sites = fields.Nested(ListSitesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListSites(ProviderSite):
    summary = "List sites"
    description = "List sites"
    definitions = {
        "ListSitesResponseSchema": ListSitesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSitesRequestSchema)
    parameters_schema = ListSitesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListSitesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        region_id = data.get("region", None)
        if region_id is not None:
            return self.get_resources_by_parent(controller, region_id, "Site")
        return self.get_resources(controller, **data)


class GetSiteParamsResponseSchema(ResourceResponseSchema):
    pass


class GetSiteResponseSchema(Schema):
    site = fields.Nested(GetSiteParamsResponseSchema, required=True, allow_none=True)


class GetSite(ProviderSite):
    summary = "Get site"
    description = "Get site"
    definitions = {
        "GetSiteResponseSchema": GetSiteResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetSiteResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateSiteParamRequestSchema(CreateProviderResourceRequestSchema):
    region = fields.String(required=True, example="region1", description="parent region")
    geo_area = fields.String(required=True, example="Italy", description="geographic area: Italy, Europe")
    coords = fields.String(
        required=True,
        example="45.514046, 13.007813",
        description="geographic coordinates",
    )
    limits = fields.Dict(
        required=True,
        example={},
        description="max limits. Use to set up infrastructure limits",
    )
    repo = fields.String(required=True, example="10.138.208.15", description="rpm repo ip address")
    zone = fields.String(required=True, example="localhost.localdomain", description="dns zone")


class CreateSiteRequestSchema(Schema):
    site = fields.Nested(CreateSiteParamRequestSchema)


class CreateSiteBodyRequestSchema(Schema):
    body = fields.Nested(CreateSiteRequestSchema, context="body")


class CreateSite(ProviderSite):
    summary = "Create site"
    description = "Create site"
    definitions = {
        "CreateSiteRequestSchema": CreateSiteRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateSiteBodyRequestSchema)
    parameters_schema = CreateSiteRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateSiteParamRequestSchema(UpdateProviderResourceRequestSchema):
    geo_area = fields.String(example="Italy", description="geographic area: Italy, Europe")
    coords = fields.String(example="45.514046, 13.007813", description="geographic coordinates")


class UpdateSiteRequestSchema(Schema):
    site = fields.Nested(UpdateSiteParamRequestSchema)


class UpdateSiteBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSiteRequestSchema, context="body")


class UpdateSite(ProviderSite):
    summary = "Update site"
    description = "Update site"
    definitions = {
        "UpdateSiteRequestSchema": UpdateSiteRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateSiteBodyRequestSchema)
    parameters_schema = UpdateSiteRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteSite(ProviderSite):
    summary = "Delete site"
    description = "Delete site"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class AddSiteOrchestratorParamRequestSchema(UpdateProviderResourceRequestSchema):
    type = fields.String(
        required=True,
        example="openstack",
        description="Orchestrator type. Ex. vsphere, openstack",
        validate=OneOf(
            [
                "vsphere",
                "openstack",
                "awx",
                "zabbix",
                "elk",
                "ontap",
                "grafana",
                "veeam",
            ]
        ),
    )
    id = fields.String(required=True, example="12", description="Orchestrator id, uuid or name")
    tag = fields.String(example="default", default="default", description="Orchestrator tag")
    config = fields.Dict(required=True, example={}, description="Orchestrator configuration")


class AddSiteOrchestratorRequestSchema(Schema):
    orchestrator = fields.Nested(AddSiteOrchestratorParamRequestSchema)


class AddSiteOrchestratorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddSiteOrchestratorRequestSchema, context="body")


class AddSiteOrchestrator(ProviderSite):
    summary = "Add site orchestrator"
    description = "Add site orchestrator"
    definitions = {
        "AddSiteOrchestratorRequestSchema": AddSiteOrchestratorRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddSiteOrchestratorBodyRequestSchema)
    parameters_schema = AddSiteOrchestratorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Vsphere orchestrator:

        {
            "type":"vsphere",
            "id":16,
            "tag":"default",
            "config":{
                "datacenter":4,
                "resource_pool":{"default":298},
                "physical_network": 346
            }
        }

        Openstack orchestrator:

        {
            "type":"openstack",
            "id":22,
            "tag":"default",
            "config":{
                "domain":1459,
                "availability_zone":{"default":"nova"},
                "physical_network":"datacentre",
                "public_network":"internet"
            }
        }
        """
        obj = self.get_resource_reference(controller, oid)
        return obj.add_orchestrator(**data.get("orchestrator"))


class DeleteSiteOrchestratorParamRequestSchema(Schema):
    id = fields.String(required=True, example="12", description="Orchestrator id, uuid or name")


class DeleteSiteOrchestratorRequestSchema(Schema):
    orchestrator = fields.Nested(DeleteSiteOrchestratorParamRequestSchema)


class DeleteSiteOrchestratorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteSiteOrchestratorRequestSchema, context="body")


class DeleteSiteOrchestrator(ProviderSite):
    summary = "Delete site orchestrator"
    description = "Delete site orchestrator"
    definitions = {
        "DeleteSiteOrchestratorRequestSchema": DeleteSiteOrchestratorRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteSiteOrchestratorBodyRequestSchema)
    parameters_schema = DeleteSiteOrchestratorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        return obj.delete_orchestrator(**data.get("orchestrator"))


class SiteProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # sites
            # - filter by: tags
            # - filter by: region
            ("%s/sites" % base, "GET", ListSites, {}),
            ("%s/sites/<oid>" % base, "GET", GetSite, {}),
            ("%s/sites" % base, "POST", CreateSite, {}),
            ("%s/sites/<oid>" % base, "PUT", UpdateSite, {}),
            ("%s/sites/<oid>" % base, "DELETE", DeleteSite, {}),
            ("%s/sites/<oid>/orchestrators" % base, "POST", AddSiteOrchestrator, {}),
            (
                "%s/sites/<oid>/orchestrators" % base,
                "DELETE",
                DeleteSiteOrchestrator,
                {},
            ),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
