# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.simple import dict_get
from beehive.common.task_v2 import run_async
from beehive_resource.util import create_resource
from beehive_resource.container import Resource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.provider.entity.instance import ComputeInstance, Instance
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet

from logging import getLogger
logger = getLogger(__name__)


class ComputeLoadBalancer(ComputeProviderResource):
    """Compute load balancer
    """
    objdef = 'Provider.ComputeZone.ComputeLoadBalancer'
    objuri = '%s/loadbalancers/%s'
    objname = 'load_balancer'
    objdesc = 'Provider ComputeLoadBalancer'
    task_path = 'beehive_resource.plugins.provider.task_v2.load_balancer.LoadBalancerTask.'

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)
        self.actions = []

    def get_hypervisor(self):
        hypervisor = self.get_attribs(key='type')
        return hypervisor

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        return info

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return kvargs

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        pass

    @staticmethod
    def __target_type_mapping(target_type):
        mapping = {
            'vm': ComputeInstance,
        }
        return mapping.get(target_type)

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
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag [default=default]
        :param kvargs.type: orchestrator type. Ex. vsphere|pfsense
        :return: dict
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get('type', 'vsphere')
        orchestrator_tag = kvargs.get('orchestrator_tag', 'default')
        compute_zone_id = kvargs.get('parent')
        site_id = kvargs.get('availability_zone')
        multi_avz = kvargs.get('multi_avz', False)
        vpc_id = kvargs.get('vpc')
        lb_configs = kvargs.get('lb_configs')
        target_type = dict_get(lb_configs, 'target_group.target_type')
        targets = dict_get(lb_configs, 'target_group.targets')
        static_ip = dict_get(lb_configs, 'static_ip')
        net_appl_tag = dict_get(lb_configs, 'net_appl_tag')
        net_appl_selection_criteria = kvargs.get('net_appl_select_criteria')

        lb_configs['name'] = kvargs.get('name')
        lb_configs['desc'] = kvargs.get('desc')

        # get compute zone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)

        # get site
        site = container.get_resource(site_id)

        # get availability zone
        main_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        # update targets
        entity_class = ComputeLoadBalancer.__target_type_mapping(target_type)
        for target in targets:
            # get compute resource
            compute_resource = controller.get_resource(target.get('resource_uuid'), entity_class=entity_class)

            # get ip address and fqdn
            ip_addr = compute_resource.get_ip_address()
            fqdn = compute_resource.get_fqdn()

            # get hypervisor on which the resource is located
            hypervisor = compute_resource.get_hypervisor()
            if hypervisor not in ['vsphere', 'openstack']:
                raise ApiManagerError('Unknown hypervisor: %s' % hypervisor)

            # get logical resource in main zone
            zone_resource = compute_resource.get_main_zone_instance()

            # get physical resource depending on hypervisor
            if hypervisor == 'vsphere':
                physical_resource = zone_resource.get_physical_resource(VsphereServer.objdef)
            else:  # hypervisor == 'openstack'
                physical_resource = zone_resource.get_physical_resource(NsxIpSet.objdef)

            # get physical resource id a.k.a. ext_id
            ext_id = physical_resource.ext_id

            # update target
            target.update({
                'ip_addr': ip_addr,
                'fqdn': fqdn,
                'ext_id': ext_id
            })

        # get helper
        helper = compute_zone.get_network_appliance_helper(orchestrator_type, controller, site)

        # select network appliance
        net_appl = helper.select_network_appliance(vpc_id, site.oid, net_appl_tag=net_appl_tag,
                                                   selection_criteria=net_appl_selection_criteria)
        logger.info('Selected network appliance: %s' % net_appl.uuid)
        kvargs['lb_configs'].update({'net_appl': net_appl.uuid})

        # get uplink network interface primary ip
        primary_ip = helper.get_uplink_vnic_primary_ip(net_appl.uuid)
        logger.info('Network appliance %s uplink vnic primary ip: %s' % (net_appl.uuid, primary_ip))

        # look for an unallocated ip address to reserve to load balancer
        reserved_ip = helper.reserve_ip_address(vpc_id, site.oid, static_ip)
        logger.info('Reserved ip address for load balancer frontend: %s' % reserved_ip)
        kvargs['lb_configs'].update({'vip': reserved_ip})

        params = {
            'orchestrator_tag': orchestrator_tag,
            'compute_zone': compute_zone.oid,
            'availability_zone': main_availability_zone,
            'multi_avz': multi_avz,
            'helper_class': helper.__class__.__module__ + '.' + helper.__class__.__name__,
            'attribute': {
                'type': orchestrator_type,
                'site': site.oid,
                'vip': reserved_ip.get('ip'),
                'is_static': reserved_ip.get('is_static'),
                'configs': {}

            }
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeLoadBalancer.task_path + 'create_resource_pre_step',
            {
                'step': ComputeLoadBalancer.task_path + 'create_zone_load_balancer_step',
                'args': [main_availability_zone]
            }
        ]
        for target in targets:
            step = {
                'step': ComputeLoadBalancer.task_path + 'add_rule_to_target_security_group_step',
                'args': [target.get('resource_uuid'), primary_ip]
            }
            steps.append(step)
        steps.append(ComputeLoadBalancer.task_path + 'create_resource_post_step')
        kvargs['steps'] = steps

        return kvargs

    @run_async(action='insert', alias='create_resource')
    @create_resource()
    def do_create(self, **params):
        """Method to execute to make custom resource operations useful to complete create

        :param params: custom params required by task
        :return:
        """
        self.logger.warning('____$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warning('____compute.do_create')
        self.logger.warning('____$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')

        return True, params

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # get related entities
        entities, total = self.get_linked_resources(link_type_filter='relation%')
        childs = [e.oid for e in entities]

        # create task workflow
        steps = [
            ComputeLoadBalancer.task_path + 'expunge_resource_pre_step'
        ]
        # remove childs
        for child in childs:
            steps.append({
                'step': ComputeLoadBalancer.task_path + 'delete_load_balancer_step',
                'args': [child]
            })
        steps.append(ComputeLoadBalancer.task_path + 'expunge_resource_post_step')
        kvargs['steps'] = steps

        return kvargs


class LoadBalancer(AvailabilityZoneChildResource):
    """Availability Zone Instance
    """
    objdef = 'Provider.Region.Site.AvailabilityZone.LoadBalancer'
    objuri = '%s/loadlalancers/%s'
    objname = 'load_balancer'
    objdesc = 'Provider Availability Zone Load Balancer'
    task_path = 'beehive_resource.plugins.provider.task_v2.load_balancer.LoadBalancerTask.'

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.role: gateway role. Can be: primary, secondary or backup
        :param kvargs.uplink_network: uplink network
        :param kvargs.uplink_subnet: uplink subnet
        :param kvargs.transport_network: transport network
        :param kvargs.transport_subnet: transport subnet
        :param kvargs.admin_pwd: admin password
        :param kvargs.dns: dns list
        :param kvargs.dns_search: dns zone
        :param kvargs.flavor: server flavor
        :param kvargs.volume_flavor: volume flavor
        :param kvargs.orchestrator_tag: orchestrator tag [default=default]
        :param kvargs.type: orchestrator type. Can be: vsphere, pfsense
        :param kvargs.ip_address: uplink ip address [optional]
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get('orchestrator_type')

        # create task workflow
        steps = [
            LoadBalancer.task_path + 'create_resource_pre_step',
            {
                'step': LoadBalancer.task_path + 'create_load_balancer_physical_resource_step',
                'args': [orchestrator_type]
            },
            LoadBalancer.task_path + 'create_resource_post_step',
        ]

        kvargs['steps'] = steps
        kvargs['sync'] = True
        return kvargs

    @run_async(action='insert', alias='create_resource')
    @create_resource()
    def do_create(self, **params):
        """Method to execute to make custom resource operations useful to complete create

        :param params: custom params required by task
        :return:
        """
        self.logger.warning('____$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warning('____zone.do_create')
        self.logger.warning('____$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')

        return True, params
