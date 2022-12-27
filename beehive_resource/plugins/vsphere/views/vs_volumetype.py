# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema, CrudApiObjectResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema, ResourceSmallResponseSchema
from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter


class VsphereVolumeTypeApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VsphereVolumeType
    parentclass = VsphereDatacenter


class ListVolumeTypesRequestSchema(ListResourcesRequestSchema):
    pass


class ListVolumeTypesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVolumeTypesResponseSchema(PaginatedResponseSchema):
    volumetypes = fields.Nested(ListVolumeTypesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListVolumeTypes(VsphereVolumeTypeApiView):
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


class GetVolumeType(VsphereVolumeTypeApiView):
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


class CreateVolumeTypeParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='name')
    desc = fields.String(required=True, example='test', description='name')
    datacenter = fields.String(required=True, example='23', description='datacenter id, uuid or name')
    tags = fields.String(example='prova', default='', description='comma separated list of tags')
    disk_iops = fields.Integer(example=1, missing=-1, description='disk iops')


class CreateVolumeTypeRequestSchema(Schema):
    volumetype = fields.Nested(CreateVolumeTypeParamRequestSchema)


class CreateVolumeTypeBodyRequestSchema(Schema):
    body = fields.Nested(CreateVolumeTypeRequestSchema, context='body')


class CreateVolumeType(VsphereVolumeTypeApiView):
    definitions = {
        'CreateVolumeTypeRequestSchema': CreateVolumeTypeRequestSchema,
        'CrudApiObjectResponseSchema': CrudApiObjectResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateVolumeTypeBodyRequestSchema)
    parameters_schema = CreateVolumeTypeRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create volumetype
        Create volumetype
        """
        return self.create_resource(controller, data)


class UpdateVolumeTypeParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    disk_iops = fields.Integer(example=1, missing=1, description='disk iops')


class UpdateVolumeTypeRequestSchema(Schema):
    volumetype = fields.Nested(UpdateVolumeTypeParamRequestSchema)


class UpdateVolumeTypeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeTypeRequestSchema, context='body')


class UpdateVolumeType(VsphereVolumeTypeApiView):
    definitions = {
        'UpdateVolumeTypeRequestSchema': UpdateVolumeTypeRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateVolumeTypeBodyRequestSchema)
    parameters_schema = UpdateVolumeTypeRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update volumetype
        Update volumetype
        """
        return self.update_resource(controller, oid, data)


class DeleteVolumeType(VsphereVolumeTypeApiView):
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


class GetVolumeTypeDatastoresResponseSchema(Schema):
    volumetype = fields.Nested(ResourceSmallResponseSchema, required=True, allow_none=True)


class GetVolumeTypeDatastores(VsphereVolumeTypeApiView):
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
        Get volumetype datastores
        Get volumetype datastores
        """
        res = []
        resource = self.get_resource_reference(controller, oid)
        datastore = resource.get_datastores()
        for d in datastore:
            ds = d[0].small_info()
            ds['tag'] = d[1]
            res.append(ds)
        return {'datastores': res, 'count': len(res)}


class AddVolumeTypeDatastoresParamRequestSchema(Schema):
    uuid = fields.String(example='4cdf0ea4-159a-45aa-96f2-708e461130e1', required=True, description='Datastore uuid')
    tag = fields.String(example='default', required=True, description='Datastore tag')


class AddVolumeTypeDatastoresRequestSchema(Schema):
    datastore = fields.Nested(AddVolumeTypeDatastoresParamRequestSchema)


class AddVolumeTypeDatastoresBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddVolumeTypeDatastoresRequestSchema, context='body')


class AddVolumeTypeDatastores(VsphereVolumeTypeApiView):
    definitions = {
        'AddVolumeTypeDatastoresRequestSchema': AddVolumeTypeDatastoresRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(AddVolumeTypeDatastoresBodyRequestSchema)
    parameters_schema = AddVolumeTypeDatastoresRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Add volumetype datastore
        Add volumetype datastore
        """
        resource = self.get_resource_reference(controller, oid)
        data = data.get('datastore')
        resource.add_datastore(data.get('uuid'), data.get('tag'))
        return {'uuid': data.get('uuid')}


class DeleteVolumeTypeDatastoresParamRequestSchema(Schema):
    uuid = fields.String(example='4cdf0ea4-159a-45aa-96f2-708e461130e1', required=True, description='Datastore uuid')


class DeleteVolumeTypeDatastoresRequestSchema(Schema):
    datastore = fields.Nested(DeleteVolumeTypeDatastoresParamRequestSchema)


class DeleteVolumeTypeDatastoresBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteVolumeTypeDatastoresRequestSchema, context='body')


class DeleteVolumeTypeDatastores(VsphereVolumeTypeApiView):
    definitions = {
        'DeleteVolumeTypeDatastoresRequestSchema': DeleteVolumeTypeDatastoresRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteVolumeTypeDatastoresBodyRequestSchema)
    parameters_schema = DeleteVolumeTypeDatastoresRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Remove volumetype datastore
        Remove volumetype datastore
        """
        resource = self.get_resource_reference(controller, oid)
        data = data.get('datastore')
        resource.del_datastore(data.get('uuid'))
        return {'uuid': data.get('uuid')}


class VsphereVolumeTypeAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ('%s/volumetypes' % base, 'GET', ListVolumeTypes, {}),
            ('%s/volumetypes/<oid>' % base, 'GET', GetVolumeType, {}),
            ('%s/volumetypes' % base, 'POST', CreateVolumeType, {}),
            ('%s/volumetypes/<oid>' % base, 'PUT', UpdateVolumeType, {}),
            ('%s/volumetypes/<oid>' % base, 'DELETE', DeleteVolumeType, {}),

            ('%s/volumetypes/<oid>/datastores' % base, 'GET', GetVolumeTypeDatastores, {}),
            ('%s/volumetypes/<oid>/datastores' % base, 'POST', AddVolumeTypeDatastores, {}),
            ('%s/volumetypes/<oid>/datastores' % base, 'DELETE', DeleteVolumeTypeDatastores, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)