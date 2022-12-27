# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc, SiteNetwork, PrivateNetwork
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class VpcTask(AbstractProviderResourceTask):
    """Vpc task
    """
    name = 'vpc_task'
    entity_class = Vpc

    @staticmethod
    @task_step()
    def vpc_assign_network_step(task, step_id, params, network_id, *args, **kvargs):
        """Assign site network to vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param network_id: network id
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        resource = task.get_resource(oid)
        network = task.get_resource(network_id)

        site_id = network.parent_id
        attributes = {'reuse': True}
        resource.add_link('%s-%s-network-link' % (oid, network_id), 'relation.%s' % site_id, network_id,
                          attributes=attributes)
        task.progress(step_id, msg='Link network %s to vpc %s' % (network_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def vpc_deassign_network_step(task, step_id, params, network_id, *args, **kvargs):
        """Deassign site network to vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param network_id: network id
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        resource = task.get_resource(oid)

        resource.del_link(network_id)
        task.progress(step_id, msg='unlink network %s from vpc %s' % (network_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def vpc_add_network_step(task, step_id, params, network, *args, **kvargs):
        """Add private network to vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param network: network configuration
        :param vpc_cidr: vpccidr
        :param network.cidr: private network cidr
        :param network.dns_search: network dns zone
        :param network.zabbix_proxy: zabbix proxy
        :param network.dns_nameservers: dns nameservers list. Ex. ["8.8.8.8", "8.8.8.4"]
        :param network.availability_zone: private network site
        :param network.orchestrator_tag: orchestartor tag [optional]
        :return: network_id, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        name = params.get('name')
        vpc_cidr = params.get('vpc_cidr')
        cidr = network.get('cidr')
        dns_search = network.get('dns_search')
        dns_nameservers = network.get('dns_nameservers')
        zabbix_proxy = network.get('zabbix_proxy')
        site_id = network.get('availability_zone')
        orchestrator_tag = network.get('orchestrator_tag')

        resource = task.get_resource(oid)
        compute_zone = resource.get_parent()
        site = task.get_simple_resource(site_id)
        availability_zone = compute_zone.get_availability_zone(site.oid)

        site_id = availability_zone.parent_id
        provider = task.get_container(cid)
        task.progress(step_id, msg='Get provider %s' % cid)

        # create private network
        task_params = {
            'name': '%s-%s' % (name, cidr.replace('.', '-').replace('/', '-')),
            'desc': 'private network %s' % cidr,
            'parent': availability_zone.oid,
            'active': False,
            'orchestrator_tag': orchestrator_tag,
            'cidr': cidr,
            'vpc_cidr': vpc_cidr,
            'dns_search': dns_search,
            'dns_nameservers': dns_nameservers,
            'zabbix_proxy': zabbix_proxy
        }
        prepared_task, code = provider.resource_factory(PrivateNetwork, **task_params)
        network_id = prepared_task['uuid']

        # link network to vpc
        task.get_session(reopen=True)
        resource.add_link('%s-%s-network-link' % (oid, network_id), 'relation.%s' % site_id, network_id,
                          attributes={'reuse': False})
        task.progress(step_id, msg='Link private network %s to vpc %s' % (network_id, oid))

        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create private network %s in availability zone %s' %
                                   (network_id, availability_zone.oid))

        return network_id, params

    @staticmethod
    @task_step()
    def vpc_del_network_step(task, step_id, params, network_id, *args, **kvargs):
        """Delete private network from vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param network_id: private network id
        :return: oid, params
        """
        oid = params.get('id')
        network = task.get_resource(network_id)

        prepared_task, code = network.expunge(sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='remove private network %s from vpc' % network_id)
        return oid, params

    @staticmethod
    @task_step()
    def create_site_network_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create site network

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator
        :return: oid, params
        """
        oid = params.get('id')
        resource = task.get_simple_resource(oid)

        network_type = params.get('network_type')
        vlan = params.get('vlan')
        orchestrator_config = orchestrator.get('config', {})
        physical_network = orchestrator_config.get('physical_network', None)
        external = params.get('external', False)
        private = params.get('private', False)
        public_network = orchestrator_config.get('public_network', None)
        task.progress(step_id, msg='Get configuration params')

        helper = task.get_orchestrator(orchestrator.get('type'), task, step_id, orchestrator, resource)
        network_id = helper.create_network(network_type, vlan, external, private, physical_network=physical_network,
                                           public_network=public_network)
        return network_id, params

    @staticmethod
    @task_step()
    def create_private_network_step(task, step_id, params, orchestrator, cidr, other_cidrs, gateway, pool,
                                    *args, **kvargs):
        """Create private network

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator
        :param cidr: cidr
        :param other_cidrs: other cidrs
        :param gateway: gateway
        :param pool: allocation pool
        :return: oid, params
        """
        oid = params.get('id')
        dns_nameservers = params.get('dns_nameservers')
        resource = task.get_simple_resource(oid)

        orchestrator_type = orchestrator.get('type')
        # orchestrator_config = orchestrator.get('config', {})
        # physical_network = orchestrator_config.get('physical_network', None)
        # public_network = orchestrator_config.get('public_network', None)
        task.progress(step_id, msg='Get configuration params')

        helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)

        # create network
        network_id = helper.create_network('vxlan', None, False, False, physical_network=None, public_network=None)
        network = task.get_simple_resource(network_id)
        network.set_configs(key='subnet', value=None)

        # create subnet
        enable_dhcp = True
        routes = []
        for other_cidr in other_cidrs:
            routes.append({'destination': other_cidr, 'nexthop': gateway})

        sid = helper.create_subnet(cidr, gateway, routes, pool, enable_dhcp, dns_nameservers, overlap=True)
        network.set_configs(key='subnet', value=sid)

        # create other cidr
        sids = []
        network.set_configs(key='other_subnets', value=[])
        for cidr in other_cidrs:
            sid = helper.create_subnet(cidr, None, None, [], False, [])
            sids.append(sid)
        network.set_configs(key='other_subnets', value=sids)

        return network_id, params

    @staticmethod
    @task_step()
    def delete_private_network_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Delete subnet from private network

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator
        :return: True, params
        """
        oid = params.get('id')
        resource = task.get_resource(oid)

        orchestrator_type = orchestrator['type']
        orchestrator_id = orchestrator['id']

        networks = task.get_orm_linked_resources(resource.oid, link_type='relation', container_id=orchestrator_id)
        helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)

        for network in networks:
            network_id = network[0]
            network = task.get_simple_resource(network_id)
            subnet_id = network.get_attribs(key='subnet', default=None)
            if subnet_id is not None:
                helper.delete_subnet(subnet_id)
                network.set_configs(key='subnet', value=None)

            other_subnets = network.get_attribs(key='other_subnets', default=[])
            for subnet_id in other_subnets:
                helper.delete_subnet(subnet_id)
            network.set_configs(key='other_subnets', value=[])

        return True, params

    @staticmethod
    @task_step()
    def site_network_add_subnet_step(task, step_id, params, orchestrators, subnet, *args, **kvargs):
        """Assign site network to vpc

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrators: list of orchestrators
        :param subnet: subnet to add
        :return: True, params
        """
        oid = params.get('id')
        resource = task.get_resource(oid)

        res = []
        cidr = subnet['cidr']
        gateway = subnet.get('gateway', None)
        routes = subnet.get('routes', None)
        allocation_pools = subnet.get('allocation_pools', None)
        enable_dhcp = subnet['enable_dhcp']
        dns_nameservers = subnet.get('dns_nameservers', None)

        # insert empty subnet
        subnet['vsphere_id'] = None
        subnet['openstack_id'] = None
        resource.update_subnet_in_configs(subnet)

        for orchestrator in orchestrators:
            orchestrator_type = orchestrator['type']
            allocation_pool = allocation_pools.get(orchestrator_type, None)
            if allocation_pool is None:
                continue

            helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)

            if allocation_pool is not None:
                sid = helper.create_subnet(cidr, gateway, routes, allocation_pool, enable_dhcp, dns_nameservers)
                subnet['%s_id' % orchestrator_type] = sid

            # update subnet with orchestrator subnet id
            resource.update_subnet_in_configs(subnet)
            res.append(sid)

        return True, params

    @staticmethod
    @task_step()
    def site_network_del_subnet_step(task, step_id, params, orchestrators, subnet, *args, **kvargs):
        """Delete subnet from site network

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrators: list of orchestrators
        :param subnet: subnet to remove
        :return: oid, params
        """
        oid = params.get('id')
        resource = task.get_resource(oid)

        res = []
        for orchestrator in orchestrators:
            orchestrator_type = orchestrator['type']
            subnet_id = subnet.get('%s_id' % orchestrator_type, None)
            helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)
            sid = helper.delete_subnet(subnet_id)
            subnet['%s_id' % orchestrator_type] = None
            resource.update_subnet_in_configs(subnet)
            res.append(sid)

        resource.delete_subnet_in_configs(subnet)

        return True, params
