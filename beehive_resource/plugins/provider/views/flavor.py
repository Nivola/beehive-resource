# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper


class ProviderFlavor(LocalProviderApiView):
    resclass = ComputeFlavor
    parentclass = ComputeZone


class ListFlavorsRequestSchema(ListResourcesRequestSchema):
    pass


class ListFlavorsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListFlavorsResponseSchema(PaginatedResponseSchema):
    flavors = fields.Nested(ListFlavorsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListFlavors(ProviderFlavor):
    definitions = {
        "ListFlavorsResponseSchema": ListFlavorsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListFlavorsRequestSchema)
    parameters_schema = ListFlavorsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListFlavorsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List flavors
        List flavors

        # - filter by: tags
        # - filter by: super_zone, instance

        "attributes": {
          "configs": {
            "vcpus": 1,
            "disk": 10,
            "bandwidth": 1000,
            "memory": 2048
          }
        }
        """
        zone_id = data.get("super_zone", None)
        instance_id = data.get("instance", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "SuperZone")
        elif instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "flavor")
        return self.get_resources(controller, **data)


class GetFlavorParamsResponseSchema(ResourceResponseSchema):
    flavors = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetFlavorResponseSchema(Schema):
    flavor = fields.Nested(GetFlavorParamsResponseSchema, required=True, allow_none=True)


class GetFlavor(ProviderFlavor):
    definitions = {
        "GetFlavorResponseSchema": GetFlavorResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetFlavorResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get flavor
        Get flavor

        "attributes": {
          "configs": {
            "vcpus": 1,
            "disk": 10,
            "bandwidth": 1000,
            "memory": 2048
          }
        }
        """
        return self.get_resource(controller, oid)


class CreateFlavorParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    memory = fields.Integer(required=True, example=2048, description="size of ram in MB")
    disk = fields.Integer(required=True, example="Centos", description="size of root disk in GB")
    disk_iops = fields.Integer(required=True, example=100, description="root disk max iops")
    vcpus = fields.Integer(required=True, example=2, description="number of virtual cpus")
    bandwidth = fields.Integer(required=True, example=1000, description="network bandwidth")
    multi_avz = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if flavor must be deployed to work in all the availability zones",
    )


class CreateFlavorRequestSchema(Schema):
    flavor = fields.Nested(CreateFlavorParamRequestSchema)


class CreateFlavorBodyRequestSchema(Schema):
    body = fields.Nested(CreateFlavorRequestSchema, context="body")


class CreateFlavor(ProviderFlavor):
    definitions = {
        "CreateFlavorRequestSchema": CreateFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateFlavorBodyRequestSchema)
    parameters_schema = CreateFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create flavor
        Create flavor
        """
        return self.create_resource(controller, data)


class ImportFlavorTemplateRequestSchema(Schema):
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where is located the orchestrator",
    )
    orchestrator = fields.String(required=True, example="16", description="id, uuid of the orchestrator")
    orchestrator_type = fields.String(
        required=True,
        example="openstack",
        description="Orchestrator type. Can be openstack or vsphere",
        validate=OneOf(["openstack", "vsphere"]),
    )
    flavor_id = fields.String(
        required=False,
        example="3328",
        description="id of the flavor [only for openstack]",
    )


class ImportFlavorParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    memory = fields.Integer(required=True, example=2048, description="size of ram in MB")
    disk = fields.Integer(required=True, example="Centos", description="size of root disk in GB")
    disk_iops = fields.Integer(required=True, example=100, description="root disk max iops")
    vcpus = fields.Integer(required=True, example=2, description="number of virtual cpus")
    bandwidth = fields.Integer(required=True, example=1000, description="network bandwidth")
    flavors = fields.Nested(
        ImportFlavorTemplateRequestSchema,
        required=True,
        many=True,
        description="list of orchestrator flavors to link",
        allow_none=True,
    )


class ImportFlavorRequestSchema(Schema):
    flavor = fields.Nested(ImportFlavorParamRequestSchema)


class ImportFlavorBodyRequestSchema(Schema):
    body = fields.Nested(ImportFlavorRequestSchema, context="body")


class ImportFlavor(ProviderFlavor):
    definitions = {
        "ImportFlavorRequestSchema": ImportFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ImportFlavorBodyRequestSchema)
    parameters_schema = ImportFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Import flavor
        Import flavor
        """
        return self.create_resource(controller, data)


class UpdateFlavorTemplateRequestSchema(Schema):
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where is located the orchestrator",
    )
    orchestrator = fields.String(required=True, example="16", description="id, uuid of the orchestrator")
    orchestrator_type = fields.String(
        required=True,
        example="openstack",
        description="Orchestrator type. Can be openstack or vsphere",
        validate=OneOf(["openstack", "vsphere"]),
    )
    flavor_id = fields.String(
        required=False,
        example="3328",
        description="id of the flavor [only for openstack]",
    )


class UpdateFlavorParamRequestSchema(UpdateProviderResourceRequestSchema):
    flavors = fields.Nested(
        UpdateFlavorTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator flavors to link",
        allow_none=True,
    )


class UpdateFlavorRequestSchema(Schema):
    flavor = fields.Nested(UpdateFlavorParamRequestSchema)


class UpdateFlavorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateFlavorRequestSchema, context="body")


class UpdateFlavor(ProviderFlavor):
    definitions = {
        "UpdateFlavorRequestSchema": UpdateFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateFlavorBodyRequestSchema)
    parameters_schema = UpdateFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update flavor
        Update flavor
        """
        return self.update_resource(controller, oid, data)


class DeleteFlavor(ProviderFlavor):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete flavor
        Delete flavor
        """
        return self.expunge_resource(controller, oid)


class ComputeFlavorAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: super_zone, instance
            ("%s/flavors" % base, "GET", ListFlavors, {}),
            ("%s/flavors/<oid>" % base, "GET", GetFlavor, {}),
            # ('%s/flavors' % base, 'POST', CreateFlavor, {}),
            ("%s/flavors/import" % base, "POST", ImportFlavor, {}),
            ("%s/flavors/<oid>" % base, "PUT", UpdateFlavor, {}),
            ("%s/flavors/<oid>" % base, "DELETE", DeleteFlavor, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
