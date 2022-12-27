# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class OpenstackImageApiView(OpenstackApiView):
    resclass = OpenstackImage
    parentclass = OpenstackDomain


class ListImagesRequestSchema(ListResourcesRequestSchema):
    pass


class ListImagesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListImagesResponseSchema(PaginatedResponseSchema):
    images = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListImages(OpenstackImageApiView):
    tags = ['openstack']
    definitions = {
        'ListImagesResponseSchema': ListImagesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListImagesRequestSchema)
    parameters_schema = ListImagesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListImagesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List image
        List image
        """
        return self.get_resources(controller, **data)


class GetImageResponseSchema(Schema):
    image = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetImage(OpenstackImageApiView):
    tags = ['openstack']
    definitions = {
        'GetImageResponseSchema': GetImageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetImageResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get image
        Get image
        """
        return self.get_resource(controller, oid)


class CreateImageParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, default='test')
    desc = fields.String(required=True, default='test')
    tags = fields.String(default='')


class CreateImageRequestSchema(Schema):
    image = fields.Nested(CreateImageParamRequestSchema)


class CreateImageBodyRequestSchema(Schema):
    body = fields.Nested(CreateImageRequestSchema, context='body')


class CreateImage(OpenstackImageApiView):
    tags = ['openstack']
    definitions = {
        'CreateImageRequestSchema': CreateImageRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateImageBodyRequestSchema)
    parameters_schema = CreateImageRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create image
        Create image
        """
        return self.create_resource(controller, data)


class UpdateImageParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateImageRequestSchema(Schema):
    image = fields.Nested(UpdateImageParamRequestSchema)


class UpdateImageBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateImageRequestSchema, context='body')


class UpdateImage(OpenstackImageApiView):
    tags = ['openstack']
    definitions = {
        'UpdateImageRequestSchema': UpdateImageRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateImageBodyRequestSchema)
    parameters_schema = UpdateImageRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update image
        Update image
        """
        return self.update_resource(controller, oid, data)


class DeleteImage(OpenstackImageApiView):
    tags = ['openstack']
    definitions = {
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


# class GetImageMetadataResponseSchema(Schema):
#     image_metadata = fields.Dict(required=True)
#
#
# class GetImageMetadata(OpenstackImageApiView):
#     definitions = {
#         'GetImageMetadataResponseSchema': GetImageMetadataResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': GetImageMetadataResponseSchema
#         }
#     })
#
#     def get(self, controller, data, oid, *args, **kwargs):
#         """
#         Get server metadata
#         Get server metadata
#         """
#         obj = self.get_resource_reference(controller, oid)
#         res = obj.get_metadata()
#         resp = {'image_metadata': res, 'count': len(res)}
#         return resp


class OpenstackImageAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/images' % base, 'GET', ListImages, {}),
            ('%s/images/<oid>' % base, 'GET', GetImage, {}),
            ('%s/images' % base, 'POST', CreateImage, {}),
            ('%s/images/<oid>' % base, 'PUT', UpdateImage, {}),
            ('%s/images/<oid>' % base, 'DELETE', DeleteImage, {}),

            # ('%s/images/<oid>/metadata' % base, 'GET', GetImageMetadata, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
