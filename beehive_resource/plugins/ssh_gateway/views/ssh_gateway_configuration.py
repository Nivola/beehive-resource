# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import ApiView, PaginatedRequestQuerySchema,PaginatedResponseSchema,SwaggerApiView,GetApiObjectRequestSchema,CrudApiObjectResponseSchema
from beehive_resource.plugins.ssh_gateway.views import SshGatewayResourceApiViewBase,SshGatewayAPIBase
#from beehive_resource.views.entity import ListResourcesRequestSchema
#from beehive_resource.view import ListResourcesRequestSchema
from marshmallow import fields, Schema
from marshmallow.validate import OneOf, Range

from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema, CreateResourceRequestSchema,CreateResourceParamRequestSchema
from beehive_resource.plugins.ssh_gateway.entity.ssh_gateway_configuration import SshGatewayConfiguration

class SshGatewayConfigurationApiView(SshGatewayResourceApiViewBase):
    tags = ['sshgateway']
    resclass = SshGatewayConfiguration
    parentclass = None

# create


class CreateSshGwConfigurationResponseSchema(CrudApiObjectResponseSchema):
    pass


class CreateSshGatewayConfigurationNestedRequestSchema(Schema):
    name = fields.String(required=True, default='ssh gateway')
    desc = fields.String(required=False, default='ssh gateway')
    attribute = fields.Dict(default={}, allow_none=True)
    container = fields.String(required=True, allow_none=False)
    gw_type = fields.String(validate=OneOf(['gw_dbaas','gw_vm','gw_ext'], error='invalid gw_type'),
                            description='type of ssh gateway',required=True)
    res_id = fields.String(default='', allow_none=True)


class CreateSshGatewayConfigurationRequestSchema(Schema):
    configuration = fields.Nested(CreateSshGatewayConfigurationNestedRequestSchema)


class CreateSshGwConfigurationBodyRequestSchema(Schema):
    body = fields.Nested(CreateSshGatewayConfigurationRequestSchema, context='body')


class CreateSshGwConfiguration(SshGatewayConfigurationApiView):
    summary = 'Create ssh gateway configuration'
    description = 'Create ssh gateway configuration'
    definitions = {
        'CreateSshGatewayConfigurationRequestSchema': CreateSshGatewayConfigurationRequestSchema,
        'CreateSshGwConfigurationResponseSchema': CreateSshGwConfigurationResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateSshGwConfigurationBodyRequestSchema)
    parameters_schema = CreateSshGatewayConfigurationRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description':'success',
            'schema': CreateSshGwConfigurationResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """ create ssh gateway configuration """
        return self.create_resource(controller,data)
# get


class GetSshGwConfigurationRequestSchema(GetApiObjectRequestSchema):
    pass

class GetSshGwConfigurationResponseSchema(ResourceResponseSchema):
    pass


class GetSshGwConfiguration(SshGatewayConfigurationApiView):
    summary = 'Get ssh gateway configuration'
    description = 'Get ssh gateway configuration'
    definitions = {
        'GetSshGwConfigurationResponseSchema':GetSshGwConfigurationResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetSshGwConfigurationRequestSchema)
    reponses = SwaggerApiView.setResponses({
        200: {
            'description':'success',
            'schema': GetSshGwConfigurationResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)

# list


class ListSshGwConfigurationsRequestSchema(ListResourcesRequestSchema):
    pass


class ListSshGwConfigurationsResponseSchema(PaginatedResponseSchema):
    configurations = fields.Nested(GetSshGwConfigurationResponseSchema, many=True, required=True, allow_none=True)


class ListSshGwConfigurations(SshGatewayConfigurationApiView):
    summary = 'List ssh gateway configurations'
    description = 'List ssh gateway configurations'
    definitions = {
        'ListSshGwConfigurationsResponseSchema':ListSshGwConfigurationsResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(ListSshGwConfigurationsRequestSchema)
    parameters_schema = ListSshGwConfigurationsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSshGwConfigurationsResponseSchema
        }
    })
    response_schema = ListSshGwConfigurationsResponseSchema

    def get(self, controller, data, *args, **kwargs):
        """List ssh gateway configurations
        """
        return self.get_resources(controller, **data)

# end list

class SshGatewayConfigurationAPI(SshGatewayAPIBase):
    @staticmethod
    def register_api(module, **kwargs):
        base = SshGatewayAPIBase.base
        rules = [
            ('%s/configuration' % base, 'GET', ListSshGwConfigurations, {}),
            ('%s/configuration/<oid>' % base, 'GET', GetSshGwConfiguration, {}),
            ('%s/configuration' % base, 'POST', CreateSshGwConfiguration, {}),
            #('%s/configuration/<oid>' % base, 'PUT', UpdateSshGwConfiguration, {}),
            #('%s/configuration/<oid>' % base, 'DELETE', DeleteSshGwConfiguration, {})
        ]
        kwargs['version'] = 'v1.0'
        ApiView.register_api(module, rules, **kwargs)
