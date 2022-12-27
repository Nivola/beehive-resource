# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
from marshmallow.validate import OneOf

from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema,\
    ResourceResponseSchema, ResourceSmallResponseSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView,\
    GetApiObjectRequestSchema, CrudApiObjectJobResponseSchema
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import ProviderAPI,\
    LocalProviderApiView, CreateProviderResourceRequestSchema,\
    UpdateProviderResourceRequestSchema

from beehive_resource.plugins.provider.entity.ssh_gateway_wrapper import SshGatewayWrapper

class ProviderSshGateway(LocalProviderApiView):
    resclass = SshGatewayWrapper
    parentclass = ComputeZone

class SshGatewayProviderAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            #('%s/ssh_gateway' % base, 'GET', ListSshGateway, {}),
            #('%s/ssh_gateway/<oid>' % base, 'GET', GetSshGateway, {}),

        ]
        kwargs['version'] = 'v2.0'
        ProviderAPI.register_api(module, rules, **kwargs)