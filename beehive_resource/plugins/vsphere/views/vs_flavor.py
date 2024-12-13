# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
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
from beehive_resource.view import (
    ResourceResponseSchema,
    ListResourcesRequestSchema,
    ResourceSmallResponseSchema,
)
from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter


class VsphereFlavorApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = VsphereFlavor
    parentclass = VsphereDatacenter


class ListFlavorsRequestSchema(ListResourcesRequestSchema):
    pass


class ListFlavorsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListFlavorsResponseSchema(PaginatedResponseSchema):
    flavors = fields.Nested(ListFlavorsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListFlavors(VsphereFlavorApiView):
    definitions = {
        "ListFlavorsResponseSchema": ListFlavorsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListFlavorsRequestSchema)
    parameters_schema = ListFlavorsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListFlavorsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List flavor
        List flavor
        """
        return self.get_resources(controller, **data)


class GetFlavorResponseSchema(Schema):
    flavor = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetFlavor(VsphereFlavorApiView):
    definitions = {
        "GetFlavorResponseSchema": GetFlavorResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetFlavorResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get flavor
        Get flavor
        """
        return self.get_resource(controller, oid)


class CreateFlavorParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test", description="name")
    desc = fields.String(required=True, example="test", description="name")
    datacenter = fields.String(required=True, example="23", description="datacenter id, uuid or name")
    tags = fields.String(example="prova", default="", description="comma separated list of tags")
    core_x_socket = fields.Integer(example=1, missing=1, description="core per socket")
    vcpus = fields.Integer(example=2, default=2, required=True, description="socket number")
    guest_id = fields.String(example="centos64Guest", missing="centos64Guest", description="vsphere guest id")
    ram = fields.Integer(example=1024, default=1024, required=True, description="memory")
    version = fields.String(example="vmx-11", missing="vmx-11", description="virtual machine version")
    disk = fields.Integer(example=40, default=40, required=True, description="size of main disk in GB")


class CreateFlavorRequestSchema(Schema):
    flavor = fields.Nested(CreateFlavorParamRequestSchema)


class CreateFlavorBodyRequestSchema(Schema):
    body = fields.Nested(CreateFlavorRequestSchema, context="body")


class CreateFlavor(VsphereFlavorApiView):
    definitions = {
        "CreateFlavorRequestSchema": CreateFlavorRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateFlavorBodyRequestSchema)
    parameters_schema = CreateFlavorRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create flavor
        Create flavor
        """
        return self.create_resource(controller, data)


class UpdateFlavorParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    enabled = fields.Boolean(default=True)


class UpdateFlavorRequestSchema(Schema):
    flavor = fields.Nested(UpdateFlavorParamRequestSchema)


class UpdateFlavorBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateFlavorRequestSchema, context="body")


class UpdateFlavor(VsphereFlavorApiView):
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


class DeleteFlavor(VsphereFlavorApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


# class GetFlavorDatastoresResponseSchema(Schema):
#     flavor = fields.Nested(ResourceSmallResponseSchema, required=True, allow_none=True)
#
#
# class GetFlavorDatastores(VsphereFlavorApiView):
#     definitions = {
#         'GetResourceResponseSchema': GetFlavorResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': GetFlavorResponseSchema
#         }
#     })
#
#     def get(self, controller, data, oid, *args, **kwargs):
#         """
#         Get flavor datastores
#         Get flavor datastores
#         """
#         res = []
#         resource = self.get_resource_reference(controller, oid)
#         datastore = resource.get_datastores()
#         for d in datastore:
#             ds = d[0].small_info()
#             ds['tag'] = d[1]
#             res.append(ds)
#         return {'datastores': res, 'count': len(res)}
#
#
# class AddFlavorDatastoresParamRequestSchema(Schema):
#     uuid = fields.String(example='4cdf0ea4-159a-45aa-96f2-708e461130e1', required=True, description='Datastore uuid')
#     tag = fields.String(example='default', missing='default', required=True, description='Datastore tag')
#
#
# class AddFlavorDatastoresRequestSchema(Schema):
#     datastore = fields.Nested(AddFlavorDatastoresParamRequestSchema)
#
#
# class AddFlavorDatastoresBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(AddFlavorDatastoresRequestSchema, context='body')
#
#
# class AddFlavorDatastores(VsphereFlavorApiView):
#     definitions = {
#         'UpdateResourceRequestSchema': AddFlavorDatastoresRequestSchema,
#         'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(AddFlavorDatastoresBodyRequestSchema)
#     parameters_schema = AddFlavorDatastoresRequestSchema
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectResponseSchema
#         }
#     })
#
#     def post(self, controller, data, oid, *args, **kwargs):
#         """
#         Add flavor datastore
#         Add flavor datastore
#         """
#         resource = self.get_resource_reference(controller, oid)
#         data = data.get('datastore')
#         resource.add_datastore(data.get('uuid'), data.get('tag'))
#         return {'uuid': data.get('uuid')}
#
#
# class DeleteFlavorDatastoresParamRequestSchema(Schema):
#     uuid = fields.String(example='4cdf0ea4-159a-45aa-96f2-708e461130e1', required=True, description='Datastore uuid')
#
#
# class DeleteFlavorDatastoresRequestSchema(Schema):
#     datastore = fields.Nested(DeleteFlavorDatastoresParamRequestSchema)
#
#
# class DeleteFlavorDatastoresBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(DeleteFlavorDatastoresRequestSchema, context='body')
#
#
# class DeleteFlavorDatastores(VsphereFlavorApiView):
#     definitions = {
#         'UpdateResourceRequestSchema': DeleteFlavorDatastoresRequestSchema,
#         'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(DeleteFlavorDatastoresBodyRequestSchema)
#     parameters_schema = DeleteFlavorDatastoresRequestSchema
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectResponseSchema
#         }
#     })
#
#     def delete(self, controller, data, oid, *args, **kwargs):
#         """
#         Remove flavor datastore
#         Remove flavor datastore
#         """
#         resource = self.get_resource_reference(controller, oid)
#         data = data.get('datastore')
#         resource.del_datastore(data.get('uuid'))
#         return {'uuid': data.get('uuid')}


class VsphereFlavorAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ("%s/flavors" % base, "GET", ListFlavors, {}),
            ("%s/flavors/<oid>" % base, "GET", GetFlavor, {}),
            ("%s/flavors" % base, "POST", CreateFlavor, {}),
            ("%s/flavors/<oid>" % base, "PUT", UpdateFlavor, {}),
            ("%s/flavors/<oid>" % base, "DELETE", DeleteFlavor, {}),
            # ('%s/flavors/<oid>/datastores' % base, 'GET', GetFlavorDatastores, {}),
            # ('%s/flavors/<oid>/datastores' % base, 'POST', AddFlavorDatastores, {}),
            # ('%s/flavors/<oid>/datastores' % base, 'DELETE', DeleteFlavorDatastores, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
