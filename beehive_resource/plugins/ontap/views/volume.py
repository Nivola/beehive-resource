# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectTaskResponseSchema
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.ontap.views import OntapNetappApiView, OntapNetappAPI
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class OntapNetappVolumeApiView(OntapNetappApiView):
    resclass = OntapNetappVolume
    parentclass = None


class ListVolumesRequestSchema(ListResourcesRequestSchema):
    pass


class ListVolumesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVolumesResponseSchema(PaginatedResponseSchema):
    volumes = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListVolumes(OntapNetappVolumeApiView):
    summary = 'List volumes'
    description = 'List volumes'
    tags = ['ontap_netapp']
    definitions = {
        'ListVolumesResponseSchema': ListVolumesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVolumesRequestSchema)
    parameters_schema = ListVolumesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListVolumesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetVolumeResponseSchema(Schema):
    volume = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetVolume(OntapNetappVolumeApiView):
    summary = 'Get volume'
    description = 'Get volume'
    tags = ['ontap_netapp']
    definitions = {
        'GetVolumeResponseSchema': GetVolumeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVolumeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateVolumeParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='name')
    desc = fields.String(required=False, example='test', description='name')
    ontap_volume_id = fields.String(required=True, example='23',
                                    description='physical id of volume in ontap netapp platform')


class CreateVolumeRequestSchema(Schema):
    volume = fields.Nested(CreateVolumeParamRequestSchema)


class CreateVolumeBodyRequestSchema(Schema):
    body = fields.Nested(CreateVolumeRequestSchema, context='body')


class CreateVolume(OntapNetappVolumeApiView):
    summary = 'Create volume'
    description = 'Create volume'
    tags = ['ontap_netapp']
    definitions = {
        'CreateVolumeRequestSchema': CreateVolumeRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateVolumeBodyRequestSchema)
    parameters_schema = CreateVolumeRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateVolumeParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateVolumeRequestSchema(Schema):
    volume = fields.Nested(UpdateVolumeParamRequestSchema)


class UpdateVolumeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeRequestSchema, context='body')


class UpdateVolume(OntapNetappVolumeApiView):
    summary = 'Update volume'
    description = 'Update volume'
    tags = ['ontap_netapp']
    definitions = {
        'UpdateVolumeRequestSchema': UpdateVolumeRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateVolumeBodyRequestSchema)
    parameters_schema = UpdateVolumeRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteVolume(OntapNetappVolumeApiView):
    summary = 'Delete volume'
    description = 'Delete volume'
    tags = ['ontap_netapp']
    definitions = {
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class OntapNetappVolumeAPI(OntapNetappAPI):
    """OntapNetapp base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OntapNetappAPI.base
        rules = [
            ('%s/volumes' % base, 'GET', ListVolumes, {}),
            ('%s/volumes/<oid>' % base, 'GET', GetVolume, {}),
            ('%s/volumes' % base, 'POST', CreateVolume, {}),
            ('%s/volumes/<oid>' % base, 'PUT', UpdateVolume, {}),
            ('%s/volumes/<oid>' % base, 'DELETE', DeleteVolume, {}),
        ]

        OntapNetappAPI.register_api(module, rules, **kwargs)
