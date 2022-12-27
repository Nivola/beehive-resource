# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.simple import id_gen, bool2str
from beehive_resource.plugins.provider.entity.stack import ComputeStack
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, \
    ResourceResponseSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, \
    GetApiObjectRequestSchema, CrudApiObjectResponseSchema, \
    CrudApiObjectJobResponseSchema, ApiManagerError
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import ProviderAPI, \
    LocalProviderApiView, UpdateProviderResourceRequestSchema, \
    CreateProviderResourceRequestSchema
from marshmallow.validate import OneOf
from re import search


class ProviderLoadBalancer(LocalProviderApiView):
    resclass = ComputeStack
    parentclass = ComputeZone


class ListLoadBalancersRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context='query', description='comma separated list of compute zone id or uuid')


class ListLoadBalancersResponseSchema(PaginatedResponseSchema):
    stacks = fields.Nested(ResourceResponseSchema, many=True, required=True)


class ListLoadBalancers(ProviderLoadBalancer):
    definitions = {
        'ListLoadBalancersResponseSchema': ListLoadBalancersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListLoadBalancersRequestSchema)
    parameters_schema = ListLoadBalancersRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListLoadBalancersResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List load_balancers
        List load_balancers

        # - filter by: tags
        # - filter by: compute_zone
        """
        compute_zones = data.pop('compute_zones', None)
        if compute_zones is not None:
            data['parent_list'] = compute_zones.split(',')

        data['attribute'] = '%"stack_type":"load_balancer"%'
        resources, total = self.get_resources_reference(controller, **data)

        resp = []
        ids = [r.oid for r in resources]
        avz_insts = controller.get_directed_linked_resources_internal(ids, link_type='relation%')
        vpcs_all = controller.get_directed_linked_resources_internal(ids, link_type='vpc')
        sgs_all = controller.get_directed_linked_resources_internal(ids, link_type='security-group')

        for resource in resources:
            info = resource.info()

            zone_stacks = avz_insts.get(resource.oid)
            vpcs = vpcs_all.get(resource.oid)
            sgs = sgs_all.get(resource.oid)

            info['vpcs'] = [vpc.small_info() for vpc in vpcs]
            info['security_groups'] = [sg.small_info() for sg in sgs]

            is_public = resource.get_attribs().get('is_public', False)
            public_hots_key = 'IPServerlb'
            if is_public is True:
                public_hots_key = 'IPServerlb_public'

            info['stacks'] = []
            for zone_stack in zone_stacks:
                zone_stack.post_get()
                uri = ''
                for outputs in zone_stack.outputs():
                    if outputs.get('ManagemtnUri') in [public_hots_key]:
                        uri = outputs.get('output_value')
                zone = {'availability_zone': zone_stack.get_site().name,
                        'status_reason': zone_stack.status_reason(),
                        'uri': uri}
                info['stacks'].append(zone)

            resp.append(info)

        return self.format_paginated_response(resp, 'load_balancers', total, **data)


class GetLoadBalancerResponseSchema(Schema):
    load_balancer = fields.Nested(ResourceResponseSchema, required=True)


class GetLoadBalancer(ProviderLoadBalancer):
    definitions = {
        'GetLoadBalancerResponseSchema': GetLoadBalancerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetLoadBalancerResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get load_balancer
        Get load_balancer
        """
        containers, tot = controller.get_containers(container_type='Provider')
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)

        # get zone stacks
        zone_stacks, total = res.get_linked_resources(link_type_filter='relation%')
        vpcs, total = res.get_linked_resources(link_type_filter='vpc')
        sgs, total = res.get_linked_resources(link_type_filter='security-group')
        info = res.info()

        info['vpcs'] = [vpc.small_info() for vpc in vpcs]
        info['security_groups'] = [sg.small_info() for sg in sgs]

        is_public = res.get_attribs().get('is_public', False)
        public_hots_key = 'IPServerlb'
        if is_public is True:
            public_hots_key = 'IPServerlb_public'

        info['stacks'] = []
        for zone_stack in zone_stacks:
            zone_stack.post_get()
            uri = ''
            for outputs in zone_stack.outputs():
                if outputs.get('ManagemtnUri') in [public_hots_key]:
                    uri = outputs.get('output_value')
            zone = {'availability_zone': zone_stack.get_site().name,
                    'status_reason': zone_stack.status_reason(),
                    'uri': uri}
            info['stacks'].append(zone)

        return {'load_balancer': info}


class GetLoadBalancerResourcesResponseSchema(Schema):
    load_balancer_resources = fields.List(fields.Dict(), required=True)


class GetLoadBalancerResources(ProviderLoadBalancer):
    definitions = {
        'GetLoadBalancerResourcesResponseSchema': GetLoadBalancerResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetLoadBalancerResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get load_balancer resources
        Get load_balancer resources
        """
        resource = self.get_resource_reference(controller, oid)
        resources = resource.resources()
        return {'load_balancer_resources': resources, 'count': len(resources)}


class CreateLoadBalancerParamConfigRequestSchema(Schema):
    pass


class CreateLoadBalancerParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    availability_zone = fields.String(required=True, example='2995',
                                      description='id, uuid or name of the site where create sql')
    flavor = fields.String(required=True, example='2995', description='id, uuid or name of the flavor')
    image = fields.String(required=True, example='2995', description='id, uuid or name of the image')
    vpc = fields.String(required=True, example='2995', description='id, uuid or name of the private vpc')
    vpc_public = fields.String(required=False, example='2995', missing='',
                               description='id, uuid or name of the public vpc')
    is_public = fields.Boolean(required=False, missing=False, description='if True load balancer is on public network')
    security_group = fields.String(required=True, example='2995',
                                   description='id, uuid or name of the private security group')
    routes = fields.List(fields.String(), required=False, example='6.5', description='List of routes')
    key_name = fields.String(required=False, example='opstkcsi', default='opstkcsi',
                             description='Openstack public key name')
    version = fields.String(required=True, example='6.5', description='App engine version')
    engine = fields.String(required=True, example='mysql', description='App engine', validate=OneOf(['haproxy']))
    engine_configs = fields.Nested(CreateLoadBalancerParamConfigRequestSchema, required=True,
                                   description='App engine specific params')
    admin_password = fields.String(required=True, example='prova', description='Console admin password')
    resolve = fields.Boolean(example=False, missing=True, required=False,
                             description='Define if stack instances must registered on the availability_zone dns zone')


class CreateLoadBalancerRequestSchema(Schema):
    load_balancer = fields.Nested(CreateLoadBalancerParamRequestSchema, context='body')


class CreateLoadBalancerBodyRequestSchema(Schema):
    body = fields.Nested(CreateLoadBalancerRequestSchema, context='body')


class CreateLoadBalancer(ProviderLoadBalancer):
    definitions = {
        'CreateLoadBalancerRequestSchema': CreateLoadBalancerRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateLoadBalancerBodyRequestSchema)
    parameters_schema = CreateLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create load_balancer
        Create load_balancer
        """
        input = data.get('load_balancer')

        orchestrator_tag = input.get('orchestrator_tag', 'default')

        # get availability_zone
        site = controller.get_resource(input.pop('availability_zone'))
        orchestrator_idx = site.get_orchestrators_by_tag(orchestrator_tag, index_field='type')
        orchestrator = orchestrator_idx.get('openstack', None)
        if orchestrator is None:
            raise ApiManagerError('No valid orchestrator found', code=404)

        filter = {'container_id': site.container.oid}

        # get flavor
        flavor = controller.get_resource(input.pop('flavor'), **filter)
        zone_flavor, tot = flavor.get_linked_resources(link_type_filter='relation.%s' % site.oid)
        ops_flavor, tot = zone_flavor[0].get_linked_resources(link_type='relation', container=orchestrator['id'])
        ops_flavor = ops_flavor[0]

        # get image
        image = controller.get_resource(input.pop('image'), **filter)
        zone_image, tot = image.get_linked_resources(link_type_filter='relation.%s' % site.oid)
        ops_image = zone_image[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get private vpc
        vpc = controller.get_resource(input.pop('vpc'), **filter)
        zone_vpc, tot = vpc.get_linked_resources(link_type_filter='relation.%s' % site.oid)
        ops_vpc = zone_vpc[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get private network vlan
        configs = zone_vpc[0].get_attribs().get('configs')
        vlan = configs.get('vlan')
        # get default gw and router ip
        subnets = configs.get('subnets')
        for subnet in subnets:
            if subnet.get('allocable', False) is True:
                break

        # check load balancer has public ip
        is_public = input.pop('is_public')
        gw = subnet.get('gateway', '')
        router = gw
        static_routes = ''
        if is_public is True:
            router = subnet.get('router', '')
            static_routes = ','.join(input.pop('routes', []))

            vpc_public = controller.get_resource(input.pop('vpc_public'), **filter)
            zone_vpc_public, tot = vpc_public.get_linked_resources(link_type_filter='relation.%s' % site.oid)
            ops_vpc_public = zone_vpc_public[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get private security_group
        security_group = controller.get_resource(input.pop('security_group'), **filter)
        zone_security_group, tot = security_group.get_linked_resources(link_type_filter='relation.%s' % site.oid)
        ops_security_group = zone_security_group[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get public security_group
        # security_group_public = controller.get_resource(input.pop('security_group_public'), **filter)
        # zone_security_group_public, tot = security_group_public.get_linked_resources(link_type_filter='relation.%s' % site.oid)
        # ops_security_group_public = zone_security_group_public[0].get_physical_resource_from_container(orchestrator['id'], None)

        # engine
        engine = input.pop('engine', None)
        version = input.pop('version', None)
        engine_configs = input.pop('engine_configs', {})

        if engine == 'haproxy':
            template_uri = '%s/network/load-balancer.yaml' % (controller.api_manager.stacks_uri)

            # pattern = r"(http[s]*:\/\/\d+.\d+.\d+.\d+:\d+)(\/([\d\w-]+)\/([\d\w-]+)\/raw\/([\d\w-]+)\/([\d\w-]+))"
            # match = search(pattern, str(controller.api_manager.stacks_uri))
            # git_roles_uri = match.group(0)
            # git_roles_branch = match.group(4)
            # git_roles_path = '%s/roles' % match.group(1)
            git_roles_uri = controller.api_manager.git.get('uri')
            git_roles_branch = controller.api_manager.git.get('branch')

            orchestrator_type = 'openstack'

            input['templates'] = [
                {
                    'availability_zone': site.oid,
                    'orchestrator_type': orchestrator_type,
                    'template_uri': template_uri,
                    'environment': {},
                    'parameters': {
                        'name': input.get('name'),
                        'key_name': input.pop('key_name', 'opstkcsi'),
                        'instance_type': ops_flavor.ext_id,
                        'proxy_server': controller.api_manager.http_proxy,
                        'image_id': ops_image.ext_id,
                        'volume1_size': ops_flavor.ext_obj.get('disk', 20),
                        'private_network': ops_vpc.ext_id,
                        'is_public': bool2str(is_public),
                        'public_network': ops_vpc_public.ext_id,
                        'security_groups': ops_security_group.ext_id,
                        'lb_gateway_default': router,
                        'lb_gateway_orig': gw,
                        'static_routes': static_routes,
                        'admin_password': input.pop('admin_password'),

                        'git_roles_uri': git_roles_uri,
                        'git_roles_branch': git_roles_branch
                    },
                    'owner': 'admin',
                    'files': None
                }
            ]
            input['parameters'] = {}

            input['attribute'] = {
                'stack_type': 'load_balancer',
                'availability_zone': site.oid,
                'engine': engine,
                'version': version,
                'engine_configs': engine_configs,
                'is_public': is_public
            }

        # return {'msg': None}
        res = self.create_resource(controller, {'stack': input})
        uuid = res[0].get('uuid')

        # create some links
        resource = controller.get_resource(uuid)
        link_params = [
            ('security-group', security_group),
            ('vpc', vpc),
            ('image', image),
            ('flavor', flavor),
        ]
        for item in link_params:
            resource.add_link(name='%s-%s-%s-%s-link' % (resource.oid, item[1].oid, item[0], id_gen()), type=item[0],
                              end_resource=item[1].oid, attributes={})

        return res


class UpdateLoadBalancerParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateLoadBalancerRequestSchema(Schema):
    load_balancer = fields.Nested(UpdateLoadBalancerParamRequestSchema)


class UpdateLoadBalancerBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateLoadBalancerRequestSchema, context='body')


class UpdateLoadBalancer(ProviderLoadBalancer):
    definitions = {
        'UpdateLoadBalancerRequestSchema': UpdateLoadBalancerRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateLoadBalancerBodyRequestSchema)
    parameters_schema = UpdateLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update load_balancer
        Update load_balancer
        """
        return self.update_resource(controller, oid, data)


class DeleteLoadBalancer(ProviderLoadBalancer):
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
        """
        Delete load_balancer
        Delete load_balancer
        """
        return self.expunge_resource(controller, oid)


class LoadBalancerProviderAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: compute_zone
            ('%s/load_balancers' % base, 'GET', ListLoadBalancers, {}),
            ('%s/load_balancers/<oid>' % base, 'GET', GetLoadBalancer, {}),
            ('%s/load_balancers/<oid>/resources' % base, 'GET', GetLoadBalancerResources, {}),
            ('%s/load_balancers' % base, 'POST', CreateLoadBalancer, {}),
            ('%s/load_balancers/<oid>' % base, 'PUT', UpdateLoadBalancer, {}),
            ('%s/load_balancers/<oid>' % base, 'DELETE', DeleteLoadBalancer, {})
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
