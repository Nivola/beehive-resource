# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, \
    GetApiObjectRequestSchema, CrudApiObjectJobResponseSchema, ApiView
from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder
from beehive_resource.plugins.provider.views import \
    ResourceApiView, CreateProviderResourceRequestSchema, \
    UpdateProviderResourceRequestSchema
from beehive_resource.view import ListResourcesRequestSchema, \
    ResourceResponseSchema, ResourceSmallResponseSchema
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.grafana.views import GrafanaAPI, GrafanaApiView


class GrafanaFolderView(GrafanaApiView):
    tags = ['grafana']
    resclass = GrafanaFolder
    parentclass = None


class ListGrafanaFoldersRequestSchema(ListResourcesRequestSchema):
    pass


class ListGrafanaFoldersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListGrafanaFoldersResponseSchema(PaginatedResponseSchema):
    folders = fields.Nested(ListGrafanaFoldersParamsResponseSchema, many=True, required=True, allow_none=True)


class ListGrafanaFolders(GrafanaFolderView):
    summary = 'List folders'
    description = 'List folders'
    definitions = {
        'ListGrafanaFoldersResponseSchema': ListGrafanaFoldersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListGrafanaFoldersRequestSchema)
    parameters_schema = ListGrafanaFoldersRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListGrafanaFoldersResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """List Grafana folders
        """
        return self.get_resources(controller, **data)


class GetGrafanaFolderParamsResponseSchema(ResourceResponseSchema):
    folders = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetGrafanaFolderResponseSchema(Schema):
    folder = fields.Nested(GetGrafanaFolderParamsResponseSchema, required=True, allow_none=True)


class GetGrafanaFolder(GrafanaFolderView):
    summary = 'Get folder'
    description = 'Get folder'
    definitions = {
        'GetGrafanaFolderResponseSchema': GetGrafanaFolderResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetGrafanaFolderResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Grafana folder
        """
        return self.get_resource(controller, oid)


class CreateGrafanaFolderParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example='12', description='Container id, uuid or name')
    name = fields.String(required=True, example='test-name-folder', default='', description='Folder name')
    desc = fields.String(required=False, example='test-desc-folder', description='The resource description')

class CreateGrafanaFolderRequestSchema(Schema):
    folder = fields.Nested(CreateGrafanaFolderParamRequestSchema)


class CreateGrafanaFolderBodyRequestSchema(Schema):
    body = fields.Nested(CreateGrafanaFolderRequestSchema, context='body')


class CreateGrafanaFolder(GrafanaFolderView):
    summary = 'Create folder'
    description = 'Create folder'
    definitions = {
        'CreateGrafanaFolderRequestSchema': CreateGrafanaFolderRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateGrafanaFolderBodyRequestSchema)
    parameters_schema = CreateGrafanaFolderRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """Add new folder to Grafana
        """
        return self.create_resource(controller, data)


class UpdateGrafanaFolderTemplateRequestSchema(Schema):
    name = fields.String(required=True, example='Test folder', default='', description='Folder name')
    desc = fields.String(required=False, example='This is the test folder', default='', description='Folder description')


class UpdateGrafanaFolderParamRequestSchema(UpdateProviderResourceRequestSchema):
    folders = fields.Nested(UpdateGrafanaFolderTemplateRequestSchema, required=False, many=True,
                             description='list of orchestrator folders to link', allow_none=True)


class UpdateGrafanaFolderRequestSchema(Schema):
    folder = fields.Nested(UpdateGrafanaFolderParamRequestSchema)


class UpdateGrafanaFolderBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateGrafanaFolderRequestSchema, context='body')


class UpdateGrafanaFolder(GrafanaFolderView):
    summary = 'Update folder'
    description = 'Update folder'
    definitions = {
        'UpdateGrafanaFolderRequestSchema': UpdateGrafanaFolderRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateGrafanaFolderBodyRequestSchema)
    parameters_schema = UpdateGrafanaFolderRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Grafana folder
        """
        return self.update_resource(controller, oid, data)


class DeleteGrafanaFolder(GrafanaFolderView):
    summary = 'Delete folder'
    description = 'Delete folder'
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
        """Delete Grafana folder
        """
        return self.expunge_resource(controller, oid)


class GrafanaFolderAPI(GrafanaAPI):
    """Grafana folder api routes
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = GrafanaAPI.base
        rules = [
            ('%s/folders' % base, 'GET', ListGrafanaFolders, {}),
            ('%s/folders/<oid>' % base, 'GET', GetGrafanaFolder, {}),
            ('%s/folders' % base, 'POST', CreateGrafanaFolder, {}),
            ('%s/folders/<oid>' % base, 'PUT', UpdateGrafanaFolder, {}),
            ('%s/folders/<oid>' % base, 'DELETE', DeleteGrafanaFolder, {})
        ]

        kwargs['version'] = 'v1.0'
        ApiView.register_api(module, rules, **kwargs)
