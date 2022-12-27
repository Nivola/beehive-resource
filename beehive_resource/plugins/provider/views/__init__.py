# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive_resource.view import CreateResourceBaseRequestSchema,\
    ResourceApiView, ResourceResponseSchema
from beehive_resource.views.entity import ResourceApiView as ResourceApiViewV2
from flasgger import fields, Schema
from beehive.common.apimanager import ApiView
from beehive_resource.plugins.provider.controller import LocalProvider


class LocalProviderApiView(ResourceApiView):
    tags = ['provider']
    containerclass = LocalProvider

    def get_resource(self, controller, oid, alternative_name=None):
        """
        """
        containers, tot = controller.get_containers(container_type='Provider')
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        print_name = self.resclass.objname
        if alternative_name is not None:
            print_name = alternative_name
        resp = {print_name: res.detail()}
        return resp

    def update_resource(self, controller, oid, data):
        """
        """
        containers, tot = controller.get_containers(container_type='Provider')
        container = containers[0]
        obj = container.get_resource(oid, entity_class=self.resclass)
        data = data.get(self.resclass.objname)
        res = obj.update(**data)
        return res


class LocalProviderApiViewV2(ResourceApiViewV2):
    tags = ['provider']
    containerclass = LocalProvider

    def get_resource(self, controller, oid, alternative_name=None):
        """
        """
        containers, tot = controller.get_containers(container_type='Provider')
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        print_name = self.resclass.objname
        if alternative_name is not None:
            print_name = alternative_name
        resp = {print_name: res.detail()}
        return resp

    # def update_resource(self, controller, oid, data):
    #     """
    #     """
    #     containers, tot = controller.get_containers(container_type='Provider')
    #     container = containers[0]
    #     obj = container.get_resource(oid, entity_class=self.resclass)
    #     data = data.get(self.resclass.objname)
    #     res = obj.update(**data)
    #     return res


class ProviderAPI(ApiView):
    """
    """
    base = 'nrs/provider'


class CreateProviderResourceRequestSchema(CreateResourceBaseRequestSchema):
    desc = fields.String(required=True, example='test', description='The resource description')
    orchestrator_tag = fields.String(required=False, missing='default',
                                     description='orchestrator tag. Use to select a subset of orchestrators where '
                                                 'security group must be created.')


class UpdateProviderResourceRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(required=False, example='test', description='The resource description')
    orchestrator_tag = fields.String(required=False, missing='default',
                                     description='orchestrator tag. Use to select a subset of orchestrators where '
                                                 'security group must be created.')
