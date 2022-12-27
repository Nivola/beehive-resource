# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.simple import id_gen, bool2str
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack
from beehive_resource.plugins.provider.entity.stack import ComputeStack


class AppComputeStack(ComputeStack):
    """App compute stack
    """
    objuri = '%s/app_stacks/%s'
    objname = 'app_stack'
    task_path = 'beehive_resource.plugins.provider.task_v2.stack.StackTask.'

    engine = {
        'apache-php': ['7'],
    }

    def __init__(self, *args, **kvargs):
        ComputeStack.__init__(self, *args, **kvargs)

    def is_public(self):
        """Return True if app engine is public"""
        is_public = self.get_attribs().get('is_public', False)
        return is_public

    def get_engine(self):
        """Return appengine engine"""
        engine = self.get_attribs().get('engine', None)
        return engine

    def info(self):
        """Get infos.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeStack.info(self)

        public_hots_key = 'IPServerlb'
        if self.is_public() is True:
            public_hots_key = 'IPServerlb_public'

        info['vpcs'] = [vpc.small_info() for vpc in self.vpcs]
        info['security_groups'] = [sg.small_info() for sg in self.sgs]

        info['stacks'] = []
        for zone_stack in self.zone_stacks:
            servers = []
            uris = []

            if self.get_engine() == 'apache-php':
                try:
                    servers.append({'ip': zone_stack.output('IPServer1'), 'desc': 'Web server 01'})
                    servers.append({'ip': zone_stack.output('IPServer2'), 'desc': 'Web server 02'})
                    servers.append({'ip': zone_stack.output(public_hots_key), 'desc': 'Load balancer'})
                except:
                    servers = []

                try:
                    uris = [
                        'https://%s:443' % zone_stack.output(public_hots_key),
                        'http://%s:80' % zone_stack.output(public_hots_key)
                    ]
                except:
                    uris = []

            if zone_stack.has_remote_stack() is True:
                zone = {'availability_zone': zone_stack.get_site().name,
                        'status_reason': zone_stack.status_reason(),
                        'uris': uris,
                        'servers': servers}
                info['stacks'].append(zone)

        return info

    def detail(self):
        """Get details.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = self.info()
        return info

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        resource_ids = [e.oid for e in entities]
        vpcs_all = controller.get_directed_linked_resources_internal(resource_ids, link_type='vpc', run_customize=False)
        sgs_all = controller.get_directed_linked_resources_internal(resource_ids, link_type='security-group',
                                                                    run_customize=False)
        zone_stacks_all = controller.get_directed_linked_resources_internal(resource_ids, link_type='relation%',
                                                                            run_customize=False)

        # index zone stacks
        zone_stacks_all_idx = {}
        for zs in zone_stacks_all.values():
            zone_stacks_all_idx.update({z.oid: z for z in zs})

        # get all the physical stacks related to zone stacks
        physical_stacks = controller.get_directed_linked_resources_internal(zone_stacks_all_idx.keys(),
                                                                            link_type='relation',
                                                                            run_customize=True,
                                                                            objdef=OpenstackHeatStack.objdef)
        for zone_id, zone_stack in zone_stacks_all_idx.items():
            physical_stack = physical_stacks.get(zone_id, None)
            if physical_stack is not None:
                zone_stack.set_remote_stack(physical_stack[0])

        for e in entities:
            e.zone_stacks = zone_stacks_all.get(e.oid, [])
            e.vpcs = vpcs_all.get(e.oid, [])
            e.sgs = sgs_all.get(e.oid, [])

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        get_resources = self.controller.get_directed_linked_resources_internal

        resource_ids = [self.oid]
        vpcs_all = get_resources(resource_ids, link_type='vpc', run_customize=False)
        sgs_all = get_resources(resource_ids, link_type='security-group', run_customize=False)
        zone_stacks_all = get_resources(resource_ids, link_type='relation%', run_customize=False)

        self.zone_stacks = zone_stacks_all.get(self.oid, [])
        self.vpcs = vpcs_all.get(self.oid, [])
        self.sgs = sgs_all.get(self.oid, [])

        for zone_stack in self.zone_stacks:
            zone_stack.get_remote_stack()

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param dict kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: id, uuid or name of the site where create sql
        :param kvargs.flavor: id, uuid or name of the flavor
        :param kvargs.image: id, uuid or name of the image
        :param kvargs.vpc: id, uuid or name of the vpc
        :param kvargs.subnet: subnet reference
        :param kvargs.security_group: id, uuid or name of the security group
        :param kvargs.db_name: First app database name
        :param kvargs.db_appuser_name: First app user name
        :param kvargs.db_appuser_password: First app user password
        :param kvargs.db_root_name: The database admin account username
        :param kvargs.db_root_password: The database admin password
        :param kvargs.key_name: public key name
        :param kvargs.version: Database engine version
        :param kvargs.engine: Database engine
        :param kvargs.root_disk_size: root disk size [default=40GB]
        :param kvargs.data_disk_size: data disk size [default=30GB]
        :param kvargs.geo_extension: if True enable geographic extension [default=False]
        :return: dict
        :raise ApiManagerError:
        """
        from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet

        orchestrator_tag = kvargs.get('orchestrator_tag', 'default')

        # get super zone
        compute_zone = controller.get_simple_resource(kvargs.get('parent'))

        # check quotas are not exceed
        new_quotas = {
            'appengine.instances': 1,
        }
        compute_zone.check_quotas(new_quotas)

        # get availability_zone
        site = controller.get_simple_resource(kvargs.pop('availability_zone'))
        ip_repository = site.get_attribs().get('repo')
        dns_zone = site.get_dns_zone()

        orchestrator_idx = site.get_orchestrators_by_tag(orchestrator_tag, index_field='type')
        orchestrator = orchestrator_idx.get('openstack', None)
        if orchestrator is None:
            raise ApiManagerError('No valid orchestrator found', code=404)

        filter = {'container_id': site.container.oid}

        # get flavor
        flavor = controller.get_simple_resource(kvargs.pop('flavor'), **filter)
        zone_flavor, tot = flavor.get_linked_resources(link_type_filter='relation.%s' % site.oid, run_customize=False)
        ops_flavor, tot = zone_flavor[0].get_linked_resources(link_type='relation', container=orchestrator['id'])
        ops_flavor = ops_flavor[0]

        # get image
        image = controller.get_simple_resource(kvargs.pop('image'), **filter)
        zone_image, tot = image.get_linked_resources(link_type_filter='relation.%s' % site.oid, run_customize=False)
        ops_image = zone_image[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get vpc
        vpc = controller.get_simple_resource(kvargs.pop('vpc'), **filter)
        vpc_net, tot = vpc.get_linked_resources(link_type_filter='relation.%s' % site.oid, run_customize=False)
        ops_net = vpc_net[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get private network vlan
        configs = vpc_net[0].get_attribs(key='configs')
        vlan = configs.get('vlan')
        proxy = configs.get('proxy')

        # check subnet
        subnet = kvargs.pop('subnet')
        allocable_subnet = vpc_net[0].get_allocable_subnet(subnet)

        ops_subnet = controller.get_simple_resource(allocable_subnet.get('openstack_id'), entity_class=OpenstackSubnet)

        # check load balancer has public ip
        is_public = kvargs.pop('is_public')
        gw = allocable_subnet.get('gateway', '')
        router = gw
        static_routes = ''
        ops_vpc_public_ext_id = None
        if is_public is True:
            router = allocable_subnet.get('router', '')
            static_routes = ','.join(kvargs.pop('routes', []))

            vpc_public = controller.get_simple_resource(kvargs.pop('vpc_public'), **filter)
            vpc_net_public, tot = vpc_public.get_linked_resources(link_type_filter='relation.%s' % site.oid)
            ops_vpc_public = vpc_net_public[0].get_physical_resource_from_container(orchestrator['id'], None)
            ops_vpc_public_ext_id = ops_vpc_public.ext_id

        # get private security_group
        security_group = controller.get_simple_resource(kvargs.pop('security_group'), **filter)
        zone_security_groups, tot = security_group.get_linked_resources(link_type_filter='relation.%s' % site.oid)
        ops_security_group = zone_security_groups[0].get_physical_resource_from_container(orchestrator['id'], None)

        # get key
        key = compute_zone.get_ssh_keys(oid=kvargs.get('key_name'))[0]
        openstack_key_name = key.get('attributes', {}).get('openstack_name', None)
        if openstack_key_name is not None:
            key_name = openstack_key_name
        else:
            raise ApiManagerError('Ssh key is not configured to be used in stack creation')

        # engine
        engine = kvargs.pop('engine', 'php')
        version = kvargs.pop('version', '7')
        engine_configs = kvargs.pop('engine_configs', {})

        # disk
        root_disk_size = kvargs.pop('disk', 40)
        share_size = kvargs.pop('share_dimension', 10)
        share_cfg_size = kvargs.pop('share_cfg_dimension', 2)

        orchestrator_type = None
        template_uri1 = None
        if engine == 'apache-php':
            template_uri1 = '%s/appengine/apache-php-floating.yaml' % (controller.api_manager.stacks_uri)
            orchestrator_type = 'openstack'
            additional_params = {}
        else:
            raise ApiManagerError('Engine %s is not supported' % engine)

        # get share type name
        share_type = None
        ops_container = controller.get_container(orchestrator['id'], connect=True)
        for stype in ops_container.get_manila_share_type_list():
            stypename = stype.get('name')
            if stypename.find('nfs-%s' % vlan) > 0:
                share_type = stypename
                break
        if share_type is None:
            raise ApiManagerError('No suitable share type found')

        template = {
            'availability_zone': site.oid,
            'orchestrator_type': orchestrator_type,
            'template_uri': template_uri1,
            'environment': {},
            'parameters': {
                'dns_zone': dns_zone,
                'key_name': key_name,
                'instance_type': ops_flavor.ext_id,
                'private_network': ops_net.ext_id,
                'private_network_subnet': ops_subnet.ext_id,
                'is_public': bool2str(is_public),
                'public_network': ops_vpc_public_ext_id,
                'proxy_server': proxy,
                'security_groups': ops_security_group.ext_id,
                # 'public_security_groups': ops_security_group_public.ext_id,
                'lb_gateway_default': router,
                'lb_gateway_orig': gw,
                'static_routes': static_routes,
                'image_id': ops_image.ext_id,
                'share_type': share_type,
                'volume1_size': root_disk_size,
                'document_root': engine_configs.get('document_root', '/var/www'),
                'ftp_server': engine_configs.get('ftp_server', True),
                'smb_server': engine_configs.get('smb_server', False),
                'share_dimension': share_size,
                'share_cfg_dimension': share_cfg_size,
                'app_port': engine_configs.get('app_port', 80),
                'farm_name': engine_configs.get('farm_name', 'tst-portali')
            },
            'owner': 'admin',
            'files': None
        }
        kvargs['templates'] = [template]
        kvargs['parameters'] = {}
        kvargs['attribute'] = {
            'stack_type': 'app_stack',
            'availability_zone': site.oid,
            'engine': engine,
            'version': version,
            'engine_configs': engine_configs,
            'is_public': is_public
        }
        # extend parameters with engine specific parameters
        template['parameters'].update(additional_params)

        # setup link params
        link_params = [
            ('security-group', security_group.oid),
            ('vpc', vpc.oid),
            ('image', image.oid),
            ('flavor', flavor.oid),
        ]
        kvargs['link_params'] = link_params

        return ComputeStack.pre_create(controller, container, *args, **kvargs)

    @staticmethod
    def post_create(controller, *args, **kvargs):
        """Post create function. This function is used in object_factory method. Used only for synchronous creation.
        Extend this function to execute some operation after entity was created.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # create some links
        resource = controller.get_simple_resource(kvargs['uuid'])
        link_params = kvargs['link_params']
        for item in link_params:
            resource.add_link(name='%s-%s-%s-%s-link' % (resource.oid, item[1], item[0], id_gen()), type=item[0],
                              end_resource=item[1], attributes={})

        return None
