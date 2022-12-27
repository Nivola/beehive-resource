# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectTaskResponseSchema
from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
from beehive_resource.plugins.provider.entity.applied_customization import AppliedComputeCustomization
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.plugins.provider.views import ProviderAPI, LocalProviderApiView, \
    CreateProviderResourceRequestSchema
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema, ResourceSmallResponseSchema
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper


#
# Customization
#
class ProviderCustomization(LocalProviderApiView):
    resclass = ComputeCustomization
    parentclass = ComputeZone


class ListCustomizationsRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context='query', description='instance id, uuid or name')


class ListCustomizationsResponseSchema(PaginatedResponseSchema):
    customizations = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListCustomizations(ProviderCustomization):
    summary = 'List customizations'
    description = 'List customizations'
    definitions = {
        'ListCustomizationsResponseSchema': ListCustomizationsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListCustomizationsRequestSchema)
    parameters_schema = ListCustomizationsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListCustomizationsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get('instance', None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, 'Instance', 'customization')
        return self.get_resources(controller, **data)


class GetCustomizationParamsResponseSchema(ResourceResponseSchema):
    applied = fields.Nested(ResourceSmallResponseSchema, required=True, many=False, allow_none=True)


class GetCustomizationResponseSchema(Schema):
    customization = fields.Nested(GetCustomizationParamsResponseSchema, required=True, allow_none=True)


class GetCustomization(ProviderCustomization):
    summary = 'Get customization'
    description = 'Get customization'
    definitions = {
        'GetCustomizationResponseSchema': GetCustomizationResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetCustomizationResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateCustomizationAwxProjectRequestSchema(Schema):
    # container = fields.String(required=True, example='12', description='Container id, uuid or name')
    # name = fields.String(required=True, example='test-project', default='', description='awx project name')
    # desc = fields.String(example='test-project', default='', description='awx project description')
    scm_type = fields.String(required=True, example='git', default='git',
                             description='The source control system used to store the project')
    scm_url = fields.String(required=True, example='https://github.com/awx_projects/nginx', default='',
                            description='The location where the project is stored')


class CreateCustomizationParamRequestSchema(CreateProviderResourceRequestSchema):
    name = fields.String(required=True, example='test', description='customization name')
    desc = fields.String(required=True, example='test', description='customization description')
    compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    awx_project = fields.Nested(CreateCustomizationAwxProjectRequestSchema, required=True,
                                description='awx project parameters')


class CreateCustomizationRequestSchema(Schema):
    customization = fields.Nested(CreateCustomizationParamRequestSchema)


class CreateCustomizationBodyRequestSchema(Schema):
    body = fields.Nested(CreateCustomizationRequestSchema, context='body')


class CreateCustomization(ProviderCustomization):
    summary = 'Create customization'
    description = 'Create customization'
    definitions = {
        'CreateCustomizationRequestSchema': CreateCustomizationRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateCustomizationBodyRequestSchema)
    parameters_schema = CreateCustomizationRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteCustomization(ProviderCustomization):
    summary = 'Delete customization'
    description = 'Delete customization'
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


#
# Applied Customization
#
class ProviderAppliedCustomization(LocalProviderApiView):
    resclass = AppliedComputeCustomization
    parentclass = ComputeCustomization


class GetAppliedCustomizationsRequestSchema(ListResourcesRequestSchema):
    instance = fields.String(context='query', description='instance id, uuid or name')
    oid = fields.String(description='customization id')
    acid = fields.String(context='query', description='applied customization id', missing=None)


class GetAppliedCustomizationsResponseSchema(PaginatedResponseSchema):
    applied_customizations = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class GetAppliedCustomizations(ProviderAppliedCustomization):
    summary = 'Get applied customizations'
    description = 'Get applied customizations'
    definitions = {
        'GetCustomizationResponseSchema': GetCustomizationResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetAppliedCustomizationsRequestSchema)
    parameters_schema = GetAppliedCustomizationsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetCustomizationResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        instance_id = data.get('instance', None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, 'Instance', 'customization')
        data.update({'parent': oid})
        return self.get_resources(controller, **data)


class GetAppliedCustomizationParamsResponseSchema(ResourceResponseSchema):
    pass


class GetAppliedCustomizationResponseSchema(Schema):
    applied_customization = fields.Nested(GetAppliedCustomizationParamsResponseSchema, required=True, allow_none=True)


class GetAppliedCustomizationRequestSchema(GetApiObjectRequestSchema):
    acid = fields.String(required=True, description='applied customization id, uuid or name', context='path')


class GetAppliedCustomization(ProviderAppliedCustomization):
    summary = 'Get applied customization'
    description = 'Get applied customization'
    definitions = {
        'GetAppliedCustomizationResponseSchema': GetAppliedCustomizationResponseSchema,
        'GetAppliedCustomizationRequestSchema': GetAppliedCustomizationRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetAppliedCustomizationRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetAppliedCustomizationResponseSchema
        }
    })

    def get(self, controller, data, oid, acid, *args, **kwargs):
        return self.get_resource(controller, acid)


class AwxJobTemplateHostRequestSchema(Schema):
    id = fields.String(required=True, example='123', default='', description='instance id or uuid')
    extra_vars = fields.Dict(example='{"ansible_user":"root", "ansible_connection":"ssh"}', missing={},
                             description='host variables. Ex: {"ansible_user":"root"}')


class CreateAppliedCustomizationParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    name = fields.String(required=True, example='test', description='applied customization name')
    desc = fields.String(required=True, example='test', description='applied customization description')
    customization = fields.String(required=True, example='test', description='id of the parent customization')
    instances = fields.Nested(AwxJobTemplateHostRequestSchema, required=True, many=True, allow_none=True,
                              description='compute instances where run customization')
    extra_vars = fields.Dict(description='Variables used when applying customization. Ex: {"k1":"v1", "k2":"v2"}',
                             missing=None, example='{"host_groups2:["awx_group_prova", "awx_group_test"],'
                             '"host_templates":"[Template OS Linux]", "zabbix_server":"10.138.218.292,'
                             '"zabbix_server_proxy":"10.138.200.15"')
    playbook = fields.String(required=False, example='main.yml', missing='main.yml', description='Playbook')
    verbosity = fields.Integer(example=1, missing=0, description='Verbosity: 0 (Normal) (default), 1 (Verbose), '
                               '2 (More Verbose), 3 (Debug), 4 (Connection Debug), 5 (WinRM Debug)')


class CreateAppliedCustomizationRequestSchema(Schema):
    applied_customization = fields.Nested(CreateAppliedCustomizationParamRequestSchema)


class CreateAppliedCustomizationBodyRequestSchema(Schema):
    body = fields.Nested(CreateAppliedCustomizationRequestSchema, context='body')


class CreateAppliedCustomization(ProviderAppliedCustomization):
    summary = 'Create applied customization'
    description = 'Create applied customization'
    definitions = {
        'CreateAppliedCustomizationRequestSchema': CreateAppliedCustomizationRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateAppliedCustomizationBodyRequestSchema)
    parameters_schema = CreateAppliedCustomizationRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteAppliedCustomization(ProviderAppliedCustomization):
    summary = 'Delete applied customization'
    description = 'Delete applied customization'
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


#
# Applied Customization2
#
class GetAppliedCustomizations2RequestSchema(Schema):
    instance = fields.String(context='query', example='b0f55ace-0c02-4852-b9e8-384cd857603f',
                             description='instance id, uuid or name')
    customization = fields.String(context='query', example='b0f55ace-0c02-4852-b9e8-384cd857603f',
                                  description='customization id')
    uuids = fields.String(context='query', description='comma separated list of applied customization uuid')
    compute_zones = fields.String(context='query', description='comma separated list of compute zone uuid')


class GetAppliedCustomizations2ResponseSchema(PaginatedResponseSchema):
    applied_customizations = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class GetAppliedCustomizations2(ProviderAppliedCustomization):
    summary = 'Get applied customizations'
    description = 'Get applied customizations'
    definitions = {
        'GetCustomizationResponseSchema': GetCustomizationResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetAppliedCustomizationsRequestSchema)
    parameters_schema = GetAppliedCustomizationsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetCustomizationResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        instance_id = data.get('instance', None)
        customization_id = data.get('customization', None)
        if instance_id is not None:
            return self.get_linked_resources(controller, instance_id, 'Instance', 'customization')
        if customization_id is not None:
            data.update({'parent': customization_id})

        return self.get_resources(controller, **data)


class GetAppliedCustomization2(ProviderAppliedCustomization):
    summary = 'Get applied customization'
    description = 'Get applied customization'
    definitions = {
        'GetAppliedCustomizationResponseSchema': GetAppliedCustomizationResponseSchema,
        'GetAppliedCustomizationRequestSchema': GetAppliedCustomizationRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetAppliedCustomizationRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetAppliedCustomizationResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateAppliedCustomization2(ProviderAppliedCustomization):
    summary = 'Create applied customization'
    description = 'Create applied customization'
    definitions = {
        'CreateAppliedCustomizationRequestSchema': CreateAppliedCustomizationRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateAppliedCustomizationBodyRequestSchema)
    parameters_schema = CreateAppliedCustomizationRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteAppliedCustomization2(ProviderAppliedCustomization):
    summary = 'Delete applied customization'
    description = 'Delete applied customization'
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


class ComputeCustomizationAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ('%s/customizations' % base, 'GET', ListCustomizations, {}),
            ('%s/customizations/<oid>' % base, 'GET', GetCustomization, {}),
            ('%s/customizations' % base, 'POST', CreateCustomization, {}),
            ('%s/customizations/<oid>' % base, 'DELETE', DeleteCustomization, {}),

            ('%s/customizations/<oid>/applied' % base, 'GET', GetAppliedCustomizations, {}),
            ('%s/customizations/<oid>/applied/<acid>' % base, 'GET', GetAppliedCustomization, {}),
            ('%s/customizations/<oid>/applied' % base, 'POST', CreateAppliedCustomization, {}),
            ('%s/customizations/<oid>/applied' % base, 'DELETE', DeleteAppliedCustomization, {}),

            ('%s/applied_customizations' % base, 'GET', GetAppliedCustomizations2, {}),
            ('%s/applied_customizations/<oid>' % base, 'GET', GetAppliedCustomization2, {}),
            ('%s/applied_customizations' % base, 'POST', CreateAppliedCustomization2, {}),
            ('%s/applied_customizations/<oid>' % base, 'DELETE', DeleteAppliedCustomization2, {}),
        ]

        kwargs['version'] = 'v1.0'
        ProviderAPI.register_api(module, rules, **kwargs)
