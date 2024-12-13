# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    CrudApiObjectResponseSchema,
)
from beehive_resource.plugins.provider.entity.template import ComputeTemplate
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper


class ProviderTemplate(LocalProviderApiView):
    resclass = ComputeTemplate
    parentclass = ComputeZone


## list
class ListTemplatesRequestSchema(ListResourcesRequestSchema):
    pass


class ListTemplatesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListTemplatesResponseSchema(PaginatedResponseSchema):
    templates = fields.Nested(ListTemplatesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListTemplates(ProviderTemplate):
    definitions = {
        "ListTemplatesResponseSchema": ListTemplatesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListTemplatesRequestSchema)
    parameters_schema = ListTemplatesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListTemplatesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List templates
        List templates

        # - filter by: tags
        # - filter by: super_zone, instance

        "attributes": {
          "configs": ...
          }
        }
        """
        zone_id = data.get("super_zone", None)
        instance_id = data.get("instance", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "ComputeZone")
        elif instance_id is not None:
            return self.get_linked_resources(controller, instance_id, "Instance", "template")
        return self.get_resources(controller, **data)


class GetTemplateParamsResponseSchema(ResourceResponseSchema):
    pass


class GetTemplateResponseSchema(Schema):
    templates = fields.Nested(GetTemplateParamsResponseSchema, required=True, allow_none=True)


class GetTemplate(ProviderTemplate):
    definitions = {
        "GetTemplateResponseSchema": GetTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetTemplateResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get job_template awx
        Get job_template awx

        "attributes": {
          "configs": {
            "os-ver": "7.1",
            "os": "Centos"
          }
        }
        """
        return self.get_resource(controller, oid)


class UpdateTemplateTemplateRequestSchema(UpdateProviderResourceRequestSchema):
    template_id = fields.String(required=False, example="3328", description="id, uuid of the job_template awx")
    parameters = fields.Dict(
        required=False,
        missing={},
        example={"param1": "xxxx"},
        description="job_template awx input parameters",
    )


class UpdateTemplateRequestSchema(Schema):
    template = fields.Nested(UpdateTemplateTemplateRequestSchema)


class UpdateTemplateBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateTemplateRequestSchema, context="body")


class UpdateTemplate(ProviderTemplate):
    definitions = {
        "UpdateTemplateRequestSchema": UpdateTemplateRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateTemplateBodyRequestSchema)
    parameters_schema = UpdateTemplateRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update job_template
        Update job_template
        """
        return self.update_resource(controller, oid, data)


class DeleteTemplate(ProviderTemplate):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete job_template
        Delete job_template
        """

        return self.expunge_resource(controller, oid)


class CreateTemplateParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    template_id = fields.String(required=True, example="3328", description="id, uuid of the job_template awx")
    parameters = fields.Dict(
        required=True,
        missing={},
        example={"image_id": "centos7-guestagent"},
        description="job_template awx input parameters",
    )


class CreateTemplateRequestSchema(Schema):
    template = fields.Nested(CreateTemplateParamRequestSchema)


class CreateTemplateBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CreateTemplateRequestSchema, context="body")


class CreateTemplateResponseSchema(CrudApiObjectResponseSchema):
    pass


class CreateTemplate(ProviderTemplate):
    definitions = {
        "CreateTemplateRequestSchema": CreateTemplateRequestSchema,
        "CreateTemplateResponseSchema": CreateTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateTemplateBodyRequestSchema)
    parameters_schema = CreateTemplateRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create awx template
        Create awx template
        """

        return self.create_resource(controller, data)


class ComputeTemplateAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/templates" % base, "GET", ListTemplates, {}),
            ("%s/templates/<oid>" % base, "GET", GetTemplate, {}),
            ("%s/templates" % base, "POST", CreateTemplate, {}),
            ("%s/templates/<oid>" % base, "PUT", UpdateTemplate, {}),
            ("%s/templates/<oid>" % base, "DELETE", DeleteTemplate, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
