# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    CrudApiObjectResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class VsphereVolumeApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereVolume
    parentclass = VsphereFolder


class ListVolumesRequestSchema(ListResourcesRequestSchema):
    pass


class ListVolumesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVolumesResponseSchema(PaginatedResponseSchema):
    volumes = fields.Nested(ListVolumesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListVolumes(VsphereVolumeApiView):
    definitions = {
        "ListVolumesResponseSchema": ListVolumesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVolumesRequestSchema)
    parameters_schema = ListVolumesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVolumesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List volume
        List volume
        """
        return self.get_resources(controller, **data)


class GetVolumeResponseSchema(Schema):
    volume = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetVolume(VsphereVolumeApiView):
    definitions = {
        "GetVolumeResponseSchema": GetVolumeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVolumeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get volume
        Get volume
        """
        return self.get_resource(controller, oid)


class CreateVolumeParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test", description="name")
    desc = fields.String(required=True, example="test", description="name")
    folder = fields.String(required=True, example="23", description="folder id, uuid or name")
    tags = fields.String(example="prova", default="", description="comma separated list of tags")
    size = fields.Int(required=True, default=20, description="volume size in GB")
    source_volid = fields.String(
        required=False,
        missing=None,
        description="The UUID of the source volume. The API "
        "creates a new volume with the same size as the source volume.",
    )
    snapshot_id = fields.String(
        required=False,
        missing=None,
        description="To create a volume from an existing "
        "snapshot, specify the UUID of the volume snapshot. The volume is created in same "
        "availability zone and with same size as the snapshot.",
    )
    imageRef = fields.String(
        required=False,
        missing=None,
        description="The UUID of the image from which you want to "
        "create the volume. Required to create a bootable volume.",
    )
    volume_type = fields.String(
        required=False,
        missing=None,
        description="The volume type. To create an environment "
        "with multiple-storage back ends, you must specify a volume type.",
    )
    metadata = fields.Dict(
        required=False,
        missing={},
        description="One or more metadata key and value pairs that " "are associated with the volume",
    )


class CreateVolumeRequestSchema(Schema):
    volume = fields.Nested(CreateVolumeParamRequestSchema)


class CreateVolumeBodyRequestSchema(Schema):
    body = fields.Nested(CreateVolumeRequestSchema, context="body")


class CreateVolume(VsphereVolumeApiView):
    definitions = {
        "CreateVolumeRequestSchema": CreateVolumeRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVolumeBodyRequestSchema)
    parameters_schema = CreateVolumeRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create volume
        Create volume
        """
        return self.create_resource(controller, data)


class UpdateVolumeParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    size = fields.Int(required=False, default=20, description="volume size in GB")
    metadata = fields.Dict(
        required=False,
        missing={},
        description="One or more metadata key and value pairs that " "are associated with the volume",
    )


class UpdateVolumeRequestSchema(Schema):
    volume = fields.Nested(UpdateVolumeParamRequestSchema)


class UpdateVolumeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeRequestSchema, context="body")


class UpdateVolume(VsphereVolumeApiView):
    definitions = {
        "UpdateVolumeRequestSchema": UpdateVolumeRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateVolumeBodyRequestSchema)
    parameters_schema = UpdateVolumeRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update volume
        Update volume
        """
        return self.update_resource(controller, oid, data)


class DeleteVolume(VsphereVolumeApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class VsphereVolumeAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ("%s/volumes" % base, "GET", ListVolumes, {}),
            ("%s/volumes/<oid>" % base, "GET", GetVolume, {}),
            ("%s/volumes" % base, "POST", CreateVolume, {}),
            ("%s/volumes/<oid>" % base, "PUT", UpdateVolume, {}),
            ("%s/volumes/<oid>" % base, "DELETE", DeleteVolume, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
