# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_volume_type import OpenstackVolumeType
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class OpenstackVolumeTypeApiView(OpenstackApiView):
    resclass = OpenstackVolumeType
    parentclass = None


class ListVolumeTypesRequestSchema(ListResourcesRequestSchema):
    pass


class ListVolumeTypesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVolumeTypesResponseSchema(PaginatedResponseSchema):
    volumetypes = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListVolumeTypes(OpenstackVolumeTypeApiView):
    tags = ['openstack']
    definitions = {
        'ListVolumeTypesResponseSchema': ListVolumeTypesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVolumeTypesRequestSchema)
    parameters_schema = ListVolumeTypesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListVolumeTypesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List volumetype
        List volumetype
        """
        return self.get_resources(controller, **data)


class GetVolumeTypeResponseSchema(Schema):
    volumetype = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetVolumeType(OpenstackVolumeTypeApiView):
    tags = ['openstack']
    definitions = {
        'GetVolumeTypeResponseSchema': GetVolumeTypeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVolumeTypeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get volumetype
        Get volumetype
        """
        return self.get_resource(controller, oid)


class OpenstackVolumeTypeAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/volumetypes' % base, 'GET', ListVolumeTypes, {}),
            ('%s/volumetypes/<oid>' % base, 'GET', GetVolumeType, {})
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
