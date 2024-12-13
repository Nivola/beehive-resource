# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
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


class ProviderVolumeFlavor(LocalProviderApiView):
    resclass = ComputeVolumeFlavor
    parentclass = ComputeZone


class ListVolumeFlavorsRequestSchema(ListResourcesRequestSchema):
    pass


class ListVolumeFlavorsParamsResponseSchema(ResourceResponseSchema):
    compute_zone = fields.String(context="query", description="compute zone id or name")
    volume_id = fields.String(context="query", description="volume id or name")


class ListVolumeFlavorsResponseSchema(PaginatedResponseSchema):
    volumeflavors = fields.Nested(ListVolumeFlavorsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListVolumeFlavors(ProviderVolumeFlavor):
    definitions = {
        "ListVolumeFlavorsResponseSchema": ListVolumeFlavorsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVolumeFlavorsRequestSchema)
    parameters_schema = ListVolumeFlavorsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListVolumeFlavorsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """
        List volumeflavors
        List volumeflavors
        """
        zone_id = data.get("compute_zone", None)
        volume_id = data.get("volume_id", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "SuperZone")
        elif volume_id is not None:
            return self.get_linked_resources(controller, volume_id, "ComputeVolume", "volumeflavor")
        return self.get_resources(controller, **data)


class GetVolumeFlavorParamsResponseSchema(ResourceResponseSchema):
    volumeflavors = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetVolumeFlavorResponseSchema(Schema):
    volumeflavor = fields.Nested(GetVolumeFlavorParamsResponseSchema, required=True, allow_none=True)


class GetVolumeFlavor(ProviderVolumeFlavor):
    definitions = {
        "GetVolumeFlavorResponseSchema": GetVolumeFlavorResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVolumeFlavorResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get volumeflavor
        Get volumeflavor
        """
        return self.get_resource(controller, oid)


class CreateVolumeFlavorParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    disk_iops = fields.Integer(required=True, example=100, description="root disk max iops")
    multi_avz = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if volumeflavor must be deployed to work in all the " "availability zones",
    )


class CreateVolumeFlavorRequestSchema(Schema):
    volumeflavor = fields.Nested(CreateVolumeFlavorParamRequestSchema)


class CreateVolumeFlavorBodyRequestSchema(Schema):
    body = fields.Nested(CreateVolumeFlavorRequestSchema, context="body")


class CreateVolumeFlavor(ProviderVolumeFlavor):
    definitions = {
        "CreateVolumeFlavorRequestSchema": CreateVolumeFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVolumeFlavorBodyRequestSchema)
    parameters_schema = CreateVolumeFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create volumeflavor
        Create volumeflavor
        """
        return self.create_resource(controller, data)


class ImportVolumeFlavorTemplateRequestSchema(Schema):
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where is located the orchestrator",
    )
    orchestrator = fields.String(required=True, example="16", description="id, uuid of the orchestrator")
    orchestrator_type = fields.String(
        required=True,
        example="openstack",
        validate=OneOf(["openstack", "vsphere"]),
        description="Orchestrator type. Can be openstack or vsphere",
    )
    volume_type_id = fields.String(required=False, example="3328", description="id of the volume type")


class ImportVolumeFlavorParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    disk_iops = fields.Integer(required=False, example=100, missing=0, description="disk max iops")
    volume_types = fields.Nested(
        ImportVolumeFlavorTemplateRequestSchema,
        required=True,
        many=True,
        description="list of orchestrator volume types to link",
        allow_none=True,
    )


class ImportVolumeFlavorRequestSchema(Schema):
    volumeflavor = fields.Nested(ImportVolumeFlavorParamRequestSchema)


class ImportVolumeFlavorBodyRequestSchema(Schema):
    body = fields.Nested(ImportVolumeFlavorRequestSchema, context="body")


class ImportVolumeFlavor(ProviderVolumeFlavor):
    definitions = {
        "ImportVolumeFlavorRequestSchema": ImportVolumeFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ImportVolumeFlavorBodyRequestSchema)
    parameters_schema = ImportVolumeFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Import volumeflavor
        Import volumeflavor
        """
        return self.create_resource(controller, data)


class UpdateVolumeFlavorTemplateRequestSchema(Schema):
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
    volume_type_id = fields.String(required=False, example="3328", description="id of the volume type")


class UpdateVolumeFlavorParamRequestSchema(UpdateProviderResourceRequestSchema):
    volume_types = fields.Nested(
        ImportVolumeFlavorTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator volume types to link",
        allow_none=True,
    )


class UpdateVolumeFlavorRequestSchema(Schema):
    volumeflavor = fields.Nested(UpdateVolumeFlavorParamRequestSchema)


class UpdateVolumeFlavorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeFlavorRequestSchema, context="body")


class UpdateVolumeFlavor(ProviderVolumeFlavor):
    definitions = {
        "UpdateVolumeFlavorRequestSchema": UpdateVolumeFlavorRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateVolumeFlavorBodyRequestSchema)
    parameters_schema = UpdateVolumeFlavorRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update volumeflavor
        Update volumeflavor
        """
        return self.update_resource(controller, oid, data)


class DeleteVolumeFlavor(ProviderVolumeFlavor):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete volumeflavor
        Delete volumeflavor
        """
        return self.expunge_resource(controller, oid)


class VolumeFlavorAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/volumeflavors" % base, "GET", ListVolumeFlavors, {}),
            ("%s/volumeflavors/<oid>" % base, "GET", GetVolumeFlavor, {}),
            # ('%s/volumeflavors' % base, 'POST', CreateVolumeFlavor, {}),
            ("%s/volumeflavors/import" % base, "POST", ImportVolumeFlavor, {}),
            ("%s/volumeflavors/<oid>" % base, "PUT", UpdateVolumeFlavor, {}),
            ("%s/volumeflavors/<oid>" % base, "DELETE", DeleteVolumeFlavor, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
