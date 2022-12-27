# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema,  CrudApiJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject


class OpenstackRouterApiView(OpenstackApiView):
    tags = ['openstack']
    resclass = OpenstackRouter
    parentclass = OpenstackProject


class ListRoutersRequestSchema(ListResourcesRequestSchema):
    pass


class ListRoutersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListRoutersResponseSchema(PaginatedResponseSchema):
    routers = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListRouters(OpenstackRouterApiView):
    definitions = {
        'ListRoutersResponseSchema': ListRoutersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListRoutersRequestSchema)
    parameters_schema = ListRoutersRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListRoutersResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List router
        List router
        """
        return self.get_resources(controller, **data)


class GetRouterResponseSchema(Schema):
    router = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetRouter(OpenstackRouterApiView):
    definitions = {
        'GetRouterResponseSchema': GetRouterResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetRouterResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get router
        Get router
        """
        return self.get_resource(controller, oid)


class CreateRouterRouteRequestSchema(Schema):
    destination = fields.String(example='0.0.0.0/0', required=True, description='destination')
    nexthop = fields.String(example='123.45.67.89', required=True, description='nexthop')


class CreateRouterExtNetIpRequestSchema(Schema):
    subnet_id = fields.String(required=True, example='12', description='subnet id or uuid')
    ip = fields.String(required=False, example='10.102.34.8', description='ip address')


class CreateRouterExtNetRequestSchema(Schema):
    network_id = fields.String(required=True, example='12', description='External network id or uuid')
    external_fixed_ips = fields.Nested(CreateRouterExtNetIpRequestSchema, many=True, description='router external_ips',
                                       allow_none=True)


class CreateRouterParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='router name')
    desc = fields.String(example='test', description='router description')
    project = fields.String(required=True, example='1639', description='parent tenant/project id or uuid')
    tags = fields.String(default='', example='tag1,tag2', description='Comma separated list of tags')
    external_gateway_info = fields.Nested(CreateRouterExtNetRequestSchema, required=True,
                                          description='External network refernce', allow_none=True)
    routes = fields.Nested(CreateRouterRouteRequestSchema, required=False, many=True, allow_none=True,
                           description='A list of host route dictionaries for the router')


class CreateRouterRequestSchema(Schema):
    router = fields.Nested(CreateRouterParamRequestSchema)


class CreateRouterBodyRequestSchema(Schema):
    body = fields.Nested(CreateRouterRequestSchema, context='body')


class CreateRouter(OpenstackRouterApiView):
    tags = ['openstack']
    definitions = {
        'CreateRouterRequestSchema': CreateRouterRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateRouterBodyRequestSchema)
    parameters_schema = CreateRouterRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create router
        Create router
        """
        return self.create_resource(controller, data)


class UpdateRouterRoutesRequestSchema(Schema):
    nexthop = fields.String(required=True, example='10.109.78.2', description='nexthop')
    destination = fields.String(required=True, example='102.109.178.23/24', description='destination')


class UpdateRouterParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)
    routes = fields.Nested(UpdateRouterRoutesRequestSchema, many=True,
                           required=False, description='List of custom routes', allow_none=True)


class UpdateRouterRequestSchema(Schema):
    router = fields.Nested(UpdateRouterParamRequestSchema)


class UpdateRouterBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateRouterRequestSchema, context='body')


class UpdateRouter(OpenstackRouterApiView):
    definitions = {
        'UpdateRouterRequestSchema': UpdateRouterRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateRouterBodyRequestSchema)
    parameters_schema = UpdateRouterRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update router
        Update router
        """
        return self.update_resource(controller, oid, data)


class DeleteRouter(OpenstackRouterApiView):
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


class ListRouterPortsResponseSchema(Schema):
    router_ports = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class ListRouterPorts(OpenstackRouterApiView):
    definitions = {
        'ListRouterPortsResponseSchema': ListRouterPortsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListRouterPortsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get router ports list
        Get router ports list
        """
        obj = self.get_resource_reference(controller, oid)
        data = obj.get_ports()
        res = [d.info() for d in data]
        resp = {'router_ports':res,
                'count':len(res)}
        return resp


class CreateRouterPortParamRequestSchema(Schema):
    subnet_id = fields.String(required=True, example='123', description='subnet id, uuid')


class CreateRouterPortRequestSchema(Schema):
    router_port = fields.Nested(CreateRouterPortParamRequestSchema)


class CreateRouterPortBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CreateRouterPortRequestSchema, context='body')


class CreateRouterPort(OpenstackRouterApiView):
    definitions = {
        'CreateRouterPortRequestSchema': CreateRouterPortRequestSchema,
        'CrudApiJobResponseSchema': CrudApiJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateRouterPortBodyRequestSchema)
    parameters_schema = CreateRouterPortRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Add router port
        Add router port
        """
        router = self.get_resource_reference(controller, oid)
        task = router.create_port(data.get('router_port'))
        return task


class DeleteRouterPortParamRequestSchema(Schema):
    subnet_id = fields.String(required=True, example='123', description='subnet id, uuid')


class DeleteRouterPortRequestSchema(Schema):
    router_port = fields.Nested(DeleteRouterPortParamRequestSchema)


class DeleteRouterPortBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteRouterPortRequestSchema, context='body')


class DeleteRouterPort(OpenstackRouterApiView):
    definitions = {
        'DeleteRouterPortRequestSchema': DeleteRouterPortRequestSchema,
        'CrudApiJobResponseSchema': CrudApiJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteRouterPortBodyRequestSchema)
    parameters_schema = DeleteRouterPortRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete router port
        Delete router port
        """
        router = self.get_resource_reference(controller, oid)
        task = router.delete_port(data.get('router_port'))
        return task


class OpenstackRouterAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/routers' % base, 'GET', ListRouters, {}),
            ('%s/routers/<oid>' % base, 'GET', GetRouter, {}),
            ('%s/routers' % base, 'POST', CreateRouter, {}),
            ('%s/routers/<oid>' % base, 'PUT', UpdateRouter, {}),
            ('%s/routers/<oid>' % base, 'DELETE', DeleteRouter, {}),
            ('%s/routers/<oid>/ports' % base, 'GET', ListRouterPorts, {}),
            ('%s/routers/<oid>/ports' % base, 'POST', CreateRouterPort, {}),
            ('%s/routers/<oid>/ports' % base, 'DELETE', DeleteRouterPort, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
