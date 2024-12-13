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
from beehive_resource.plugins.provider.entity.image import ComputeImage
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


class ProviderImage(LocalProviderApiView):
    resclass = ComputeImage
    parentclass = ComputeZone


## list
class ListImagesRequestSchema(ListResourcesRequestSchema):
    pass


class ListImagesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListImagesResponseSchema(PaginatedResponseSchema):
    images = fields.Nested(ListImagesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListImages(ProviderImage):
    definitions = {
        "ListImagesResponseSchema": ListImagesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListImagesRequestSchema)
    parameters_schema = ListImagesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListImagesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List images
        List images

        # - filter by: tags
        # - filter by: super_zone, instance

        "attributes": {
          "configs": {
            "os-ver": "7.1",
            "os": "Centos"
          }
        }
        """
        zone_id = data.get("super_zone", None)
        instance_id = data.get("instance", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "ComputeZone")
        elif instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "image")
        return self.get_resources(controller, **data)


class GetImageParamsResponseSchema(ResourceResponseSchema):
    images = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetImageResponseSchema(Schema):
    image = fields.Nested(GetImageParamsResponseSchema, required=True, allow_none=True)


class GetImage(ProviderImage):
    definitions = {
        "GetImageResponseSchema": GetImageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetImageResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get image
        Get image

        "attributes": {
          "configs": {
            "os-ver": "7.1",
            "os": "Centos"
          }
        }
        """
        return self.get_resource(controller, oid)


class ImportImageTemplateRequestSchema(Schema):
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where is located the orchestrator",
    )
    orchestrator = fields.String(required=True, example="16", description="id, uuid of the orchestrator")
    template_id = fields.String(
        required=True,
        example="3328",
        description="id, uuid of the template. Openstack Image or Vsphere Server template",
    )
    template_pwd = fields.String(
        required=False,
        example="xxxx",
        description="template password [only for vsphere]",
    )
    guest_id = fields.String(required=False, example="centos64Guest", description="vsphere guest id")
    orchestrator_type = fields.String(
        required=True,
        example="openstack",
        description="Orchestrator type. Can be " "openstack or vsphere",
        validate=OneOf(["openstack", "vsphere"]),
    )
    customization_spec_name = fields.String(
        required=False, example="NUVOLAWEB WS2k16", description="vsphere customization"
    )


class ImportImageParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    os = fields.String(required=True, example="Centos", description="operating system name")
    os_ver = fields.String(required=True, example="Centos", description="operating system version")
    templates = fields.Nested(
        ImportImageTemplateRequestSchema,
        required=True,
        many=True,
        description="list of orchestrator templates to link.",
        allow_none=True,
    )
    min_disk_size = fields.Integer(
        required=False,
        example=20,
        missing=20,
        description="Minimum disk size required to run this image",
    )
    min_ram_size = fields.Integer(
        required=False,
        example=2,
        missing=2,
        description="Minimum ram size required to run this image",
    )


class ImportImageRequestSchema(Schema):
    image = fields.Nested(ImportImageParamRequestSchema)


class ImportImageBodyRequestSchema(Schema):
    body = fields.Nested(ImportImageRequestSchema, context="body")


class ImportImage(ProviderImage):
    definitions = {
        "ImportImageRequestSchema": ImportImageRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ImportImageBodyRequestSchema)
    parameters_schema = ImportImageRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create image
        Create image

        **templates**: list of remote orchestrator template reference
            Ex. for openstack {'zone_id':.., 'cid':.., 'template_id':..}
            Ex. for vsphere {'zone_id':.., 'cid':.., 'template_id':.., 'admin_pwd':..}
        """
        return self.create_resource(controller, data)


class UpdateImageTemplateRequestSchema(Schema):
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where " "is located the orchestrator",
    )
    orchestrator = fields.String(required=True, example="16", description="id, uuid of the orchestrator")
    template_id = fields.String(
        required=True,
        example="3328",
        description="id, uuid of the template. Openstack " "Image or Vsphere Server template",
    )
    template_pwd = fields.String(
        required=False,
        example="xxxx",
        description="template password [only for vsphere]",
    )
    guest_id = fields.String(required=False, example="centos64Guest", description="vsphere guest id")
    orchestrator_type = fields.String(
        required=True,
        example="openstack",
        description="Orchestrator type. Can be openstack or vsphere",
        validate=OneOf(["openstack", "vsphere"]),
    )
    customization_spec_name = fields.String(
        required=False,
        example="NUVOLAWEB WS2k16",
        description="Optional vsphere customization",
    )


class UpdateImageParamRequestSchema(UpdateProviderResourceRequestSchema):
    templates = fields.Nested(
        UpdateImageTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator templates to link",
        allow_none=True,
    )


class UpdateImageRequestSchema(Schema):
    image = fields.Nested(UpdateImageParamRequestSchema)


class UpdateImageBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateImageRequestSchema, context="body")


class UpdateImage(ProviderImage):
    definitions = {
        "UpdateImageRequestSchema": UpdateImageRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateImageBodyRequestSchema)
    parameters_schema = UpdateImageRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update image
        Update image
        """
        return self.update_resource(controller, oid, data)


class DeleteImage(ProviderImage):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete image
        Delete image
        """
        return self.expunge_resource(controller, oid)


class ComputeImageAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: super_zone, instance
            ("%s/images" % base, "GET", ListImages, {}),
            ("%s/images/<oid>" % base, "GET", GetImage, {}),
            ("%s/images/import" % base, "POST", ImportImage, {}),
            ("%s/images/<oid>" % base, "PUT", UpdateImage, {}),
            ("%s/images/<oid>" % base, "DELETE", DeleteImage, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
