# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_orchestrator import VsphereStack
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder


class VsphereVsphereStackApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VsphereStack
    parentclass = VsphereFolder


class ListVsphereStackRequestSchema(ListResourcesRequestSchema):
    pass


class ListVsphereStackParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVsphereStackResponseSchema(PaginatedResponseSchema):
    stacks = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListVsphereStack(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'ListResourcesResponseSchema': ListVsphereStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVsphereStackRequestSchema)
    parameters_schema = ListVsphereStackRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListVsphereStackResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List Stack
        List Stack
        """
        return self.get_resources(controller, **data)


class GetVsphereStackResponseSchema(Schema):
    stack = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetVsphereStack(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetResourceResponseSchema': GetVsphereStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack
        Get Stack
        """
        return self.get_resource(controller, oid)


class GetVsphereStackTemplateResponseSchema(Schema):
    stack_template = fields.List(fields.Dict, required=True)


class GetVsphereStackTemplate(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackTemplateResponseSchema': GetVsphereStackTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackTemplateResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack template
        Get Stack template
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_template()
        return {'stack_template': res}


class GetVsphereStackEnvironmentResponseSchema(Schema):
    stack_environment = fields.List(fields.Dict, required=True)


class GetVsphereStackEnvironment(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackEnvironmentResponseSchema': GetVsphereStackEnvironmentResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackEnvironmentResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack environment
        Get Stack environment
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_environment()
        return {'stack_environment': res}


class GetVsphereStackFilesResponseSchema(Schema):
    stack_files = fields.List(fields.Dict, required=True)


class GetVsphereStackFiles(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackFilesResponseSchema': GetVsphereStackFilesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackFilesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack files
        Get Stack files
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_files()
        return {'stack_files': res}


class GetVsphereStackOutputsResponseSchema(Schema):
    stack_outputs = fields.List(fields.Dict, required=True)


class GetVsphereStackOutputs(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackOutputsResponseSchema': GetVsphereStackOutputsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackOutputsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack outputs
        Get Stack outputs
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_outputs()
        return {'stack_ouputs': res}


class GetVsphereStackResourcesResponseSchema(Schema):
    stack_resources = fields.List(fields.Dict, required=True)


class GetVsphereStackResources(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackResourcesResponseSchema': GetVsphereStackResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackResourcesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack resources
        Get Stack resources
        """
        stack = self.get_resource_reference(controller, oid)
        res, total = stack.get_stack_resources(*args, **kwargs)
        resp = [i.info() for i in res]
        return self.format_paginated_response(resp, 'resources', total, **kwargs)


class GetVsphereStackInternalResourcesResponseSchema(Schema):
    stack_resources = fields.List(fields.Dict, required=True)


class GetVsphereStackInternalResources(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackInternalResourcesResponseSchema': GetVsphereStackInternalResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackInternalResourcesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack resources
        Get Stack resources
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_stack_internal_resources()
        return {'stack_resources': res}


class GetVsphereStackEventsResponseSchema(Schema):
    stack_events = fields.List(fields.Dict, required=True)


class GetVsphereStackEvents(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'GetVsphereStackEventsResponseSchema': GetVsphereStackEventsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetVsphereStackEventsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Stack events
        Get Stack events
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.get_events()
        return {'stack_events': res}


class CreateVsphereStackParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='name')
    desc = fields.String(required=True, example='test', description='name')
    folder = fields.String(required=True, example='23', description='folder id, uuid or name')
    tags = fields.String(example='test_api,tag_test_api', default='', description='comma separated list of tags')
    template_uri = fields.String(required=True, example='', default='',
                                 description='A URI to the location containing the stack template on which to '
                                             'perform the operation. See the description of the template parameter '
                                             'for information about the expected template content located at the URI.')
    environment = fields.Dict(example={}, default={}, description='A JSON environment for the stack.', allow_none=True)
    parameters = fields.Dict(example={'key_name': 'opstkcsi'}, default={'key_name': 'opstkcsi'}, allow_none=True,
                             description='Supplies arguments for parameters defined in the stack template.')
    files = fields.Dict(example={'myfile': '#!\/bin\/bash\necho \"Hello world\" > \/root\/testfile.txt'},
                        default={'myfile': '#!\/bin\/bash\necho \"Hello world\" > \/root\/testfile.txt'},
                        description='Supplies the contents of files referenced in the template or the environment.',
                        allow_none=True)
    owner = fields.String(required=True, example='admin', missing='admin', description='stack owner name')


class CreateVsphereStackRequestSchema(Schema):
    stack = fields.Nested(CreateVsphereStackParamRequestSchema)


class CreateVsphereStackBodyRequestSchema(Schema):
    body = fields.Nested(CreateVsphereStackRequestSchema, context='body')


class CreateVsphereStack(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'CreateVsphereStackRequestSchema': CreateVsphereStackRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateVsphereStackBodyRequestSchema)
    parameters_schema = CreateVsphereStackRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create Stack
        Create Stack
        """
        return self.create_resource(controller, data)


class UpdateVsphereStackParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')


class UpdateVsphereStackRequestSchema(Schema):
    stack = fields.Nested(UpdateVsphereStackParamRequestSchema)


class UpdateVsphereStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVsphereStackRequestSchema, context='body')


class UpdateVsphereStack(VsphereVsphereStackApiView):
    tags = ['vsphere']
    definitions = {
        'UpdateResourceRequestSchema': UpdateVsphereStackRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateVsphereStackBodyRequestSchema)
    parameters_schema = UpdateVsphereStackRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update Stack
        Update Stack
        """
        return self.update_resource(controller, oid, data)


class DeleteVsphereStack(VsphereVsphereStackApiView):
    tags = ['vsphere']
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


class VsphereStackAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ('%s/stacks' % base, 'GET', ListVsphereStack, {}),
            ('%s/stacks/<oid>' % base, 'GET', GetVsphereStack, {}),
            ('%s/stacks/<oid>/template' % base, 'GET', GetVsphereStackTemplate, {}),
            ('%s/stacks/<oid>/environment' % base, 'GET', GetVsphereStackEnvironment, {}),
            ('%s/stacks/<oid>/files' % base, 'GET', GetVsphereStackFiles, {}),
            ('%s/stacks/<oid>/outputs' % base, 'GET', GetVsphereStackOutputs, {}),
            ('%s/stacks/<oid>/resources' % base, 'GET', GetVsphereStackResources, {}),
            ('%s/stacks/<oid>/ineternal_resources' % base, 'GET', GetVsphereStackInternalResources, {}),
            ('%s/stacks/<oid>/events' % base, 'GET', GetVsphereStackEvents, {}),
            ('%s/stacks' % base, 'POST', CreateVsphereStack, {}),
            ('%s/stacks/<oid>' % base, 'PUT', UpdateVsphereStack, {}),
            ('%s/stacks/<oid>' % base, 'DELETE', DeleteVsphereStack, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
