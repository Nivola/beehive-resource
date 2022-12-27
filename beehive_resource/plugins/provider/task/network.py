# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from celery.utils.log import get_task_logger
from beehive_resource.tasks import ResourceJobTask, ResourceJob
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, Job
from beehive_resource.tasks import create_resource_pre, create_resource_post, update_resource_pre, \
    update_resource_post, expunge_resource_pre, expunge_resource_post
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.provider.task import group_remove_task, ProviderOrchestrator
from beehive_resource.plugins.provider.task.openstack import ProviderOpenstack
from beehive_resource.plugins.provider.task.vsphere import ProviderVsphere

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_site_network(self, options, orchestrator):
    """Create site network

    :param options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator
    :param sharedarea: shared area params
    :return:
    """
    params = self.get_shared_data()

    self.get_session()
    oid = params.get('id')
    resource = self.get_resource(oid)
    self.update('PROGRESS', msg='Get resource %s' % resource)

    # get params
    name = params.get('name')
    network_type = params.get('network_type')
    vlan = params.get('vlan')
    orchestrator_id = orchestrator['id']
    orchestrator_config = orchestrator.get('config', {})
    physical_network = orchestrator_config.get('physical_network', None)
    # subnets = params.get('subnets')
    external = params.get('external', None)
    private = params.get('private', None)
    public_network = orchestrator_config.get('public_network', None)
    self.update('PROGRESS', msg='Get configuration params')

    # create network
    if orchestrator['type'] == 'vsphere':
        network_id = ProviderVsphere.create_network(self, orchestrator_id, resource, network_type, name, vlan,
                                                    external, private, physical_network=physical_network,
                                                    public_network=public_network)
    elif orchestrator['type'] == 'openstack':

        network_id = ProviderOpenstack.create_network(self, orchestrator_id, resource, network_type, name, vlan,
                                                      external, private, physical_network=physical_network,
                                                      public_network=public_network)
        # network_id = ProviderOpenstack.create_network(self, orchestrator_id, resource, network_type, name, vlan,
        #                                               subnets, external, private, physical_network=physical_network,
        #                                               public_network=public_network)
    else:
        network_id = None

    return network_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_site_network_add_subnet(self, options, orchestrators, subnet):
    """Add subnet to site network

    :param options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrators: list of orchestrators
    :param subnet: subnet to add
    :param sharedarea: shared area params
    :return:
    """
    # validate input params
    params = self.get_shared_data()
    self.get_session()
    oid = params.get('id')
    resource = self.get_resource(oid)
    self.update('PROGRESS', msg='Get resource %s' % resource)

    # append subnet
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
        orchestrator_id = orchestrator['id']

        if orchestrator['type'] == 'vsphere':
            allocation_pool = allocation_pools.get('vsphere', None)
            if allocation_pool is not None:
                sid = ProviderVsphere.create_subnet(self, orchestrator_id, resource, cidr, gateway, routes,
                                                    allocation_pool, enable_dhcp, dns_nameservers)
                subnet['vsphere_id'] = sid
        elif orchestrator['type'] == 'openstack':
            allocation_pool = allocation_pools.get('openstack', None)
            if allocation_pool is not None:
                sid = ProviderOpenstack.create_subnet(self, orchestrator_id, resource, cidr, gateway, routes,
                                                      allocation_pool, enable_dhcp, dns_nameservers)
                subnet['openstack_id'] = sid

        # update subnet with orchestrator subnet id
        resource.update_subnet_in_configs(subnet)
        res.append(sid)

    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_site_network_del_subnet(self, options, orchestrators, subnet):
    """Delete subnet from site network

    :param options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrators: list of orchestrators
    :param subnet: subnet to remove
    :param sharedarea: shared area params
    :return:
    """
    # validate input params
    params = self.get_shared_data()
    self.get_session()
    oid = params.get('id')
    resource = self.get_resource(oid)
    self.update('PROGRESS', msg='Get resource %s' % resource)

    res = []
    for orchestrator in orchestrators:
        orchestrator_id = orchestrator['id']
        if orchestrator['type'] == 'vsphere':
            subnet_id = subnet.get('vsphere_id', None)
            sid = ProviderVsphere.delete_subnet(self, orchestrator_id, resource, subnet_id)
            subnet['vsphere_id'] = None
        elif orchestrator['type'] == 'openstack':
            subnet_id = subnet.get('openstack_id', None)
            sid = ProviderOpenstack.delete_subnet(self, orchestrator_id, resource, subnet_id)
            subnet['openstack_id'] = None

        resource.update_subnet_in_configs(subnet)
        res.append(sid)

    resource.delete_subnet_in_configs(subnet)

    return res


# @task_manager.task(bind=True, base=ResourceJobTask)
# @job_task()
# def provider_create_vsphere_network(self, options, orchestrator):
#     """Create provider vsphere network
#
#
#
#         * **options** (tupla): Tupla with some useful options.
#             (class_name, objid, job, job id, start time,
#              time before new query, user)
#         * **sharedarea** (dict):
#
#             * **cid** (int): container id
#             * **site_id** (int): site id
#             * **external**: True if network is external
#             * **vlan**: vlan id
#             * **subnets**: list of network subnet
#                 * **cidr**: subnet cidr. Ex. 194.116.110.0/24
#                 * **gateway**: gateway ip. Ex. 194.116.110.1
#                 * **routes**: network routes [optional]
#                 * **allocation_pools**: pools of continous ip in the subnet.
#                     Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
#                 * **enable_dhcp**: if True enable dhcp [optional]
#                 * **dns_nameservers**: list of dns. default=['8.8.8.8', '8.8.8.4']
#                     [optional]
#
#     :return:
#     """
#     params = self.get_shared_data()
#
#     # validate input params
#     oid = params.get('id')
#     name = params.get('name')
#     network_type = params.get('network_type')
#     vlan = params.get('vlan')
#     orchestrator_id = orchestrator['id']
#     self.update('PROGRESS', msg='Get configuration params')
#
#     # get parent cloud domain
#     self.get_session()
#     resource = self.get_resource(oid)
#     self.release_session()
#     self.update('PROGRESS', msg='Get resource %s' % resource)
#
#     # create network
#     self.get_session()
#     physical_network = orchestrator['config']['physical_network']
#     network_id = ProviderVsphere.create_network(self, orchestrator_id, resource, network_type, name, vlan,
#                                                 physical_network)
#
#     return network_id
#
#
# @task_manager.task(bind=True, base=ResourceJobTask)
# @job_task()
# def provider_create_openstack_network(self, options, orchestrator):
#     """Create provider openstack network.
#
#
#
#         * **options** (tupla): Tupla with some useful options.
#             (class_name, objid, job, job id, start time,
#              time before new query, user)
#         * **orchestrator**: orchestrator reference
#         * **sharedarea** (dict):
#
#             * **cid** (int): container id
#             * **site_id** (int): site id
#             * **external**: True if network is external
#             * **vlan**: vlan id
#             * **subnets**: list of network subnet
#                 * **cidr**: subnet cidr. Ex. 194.116.110.0/24
#                 * **gateway**: gateway ip. Ex. 194.116.110.1
#                 * **routes**: network routes [optional]
#                 * **allocation_pools**: pools of continous ip in the subnet.
#                     Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
#                 * **enable_dhcp**: if True enable dhcp [optional]
#                 * **dns_nameservers**: list of dns. default=['8.8.8.8', '8.8.8.4']
#                     [optional]
#
#     :return:
#     """
#     params = self.get_shared_data()
#
#     # validate input params
#     oid = params.get('id')
#     name = params.get('name')
#     subnets = params.get('subnets')
#     network_type = params.get('network_type')
#     vlan = params.get('vlan')
#     external = params.get('external', None)
#     private = params.get('private', None)
#     orchestrator_id = orchestrator['id']
#     self.update('PROGRESS', msg='Get configuration params')
#
#     # get parent cloud domain
#     self.get_session()
#     resource = self.get_resource(oid)
#     self.release_session()
#     self.update('PROGRESS', msg='Get resource %s' % resource)
#
#     # create network
#     self.get_session()
#     public_network = orchestrator['config']['public_network']
#     physical_network = orchestrator['config']['physical_network']
#     network_id = ProviderOpenstack.create_network(self, orchestrator_id, resource, network_type, name, vlan, subnets,
#                                                   external, private, physical_network=physical_network,
#                                                   public_network=public_network)
#
#     return network_id


# @task_manager.task(bind=True, base=ResourceJobTask)
# @job_task()
# def provider_update_openstack_network(self, options, orchestrator):
#     """Update provider openstack network.
#
#
#
#         * **options** (tupla): Tupla with some useful options.
#             (class_name, objid, job, job id, start time,
#              time before new query, user)
#         * **sharedarea** (dict):
#
#             * **cid** (int): container id
#             * **subnets**: list of network subnet to add
#                 * **cidr**: subnet cidr. Ex. 194.116.110.0/24
#                 * **gateway**: gateway ip. Ex. 194.116.110.1
#                 * **routes**: network routes [optional]
#                 * **allocation_pools**: pools of continous ip in the subnet.
#                     Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
#                 * **enable_dhcp**: if True enable dhcp [optional]
#                 * **dns_nameservers**: list of dns. default=['8.8.8.8', '8.8.8.4']
#                     [optional]
#
#     :return:
#     """
#     params = self.get_shared_data()
#
#     # validate input params
#     oid = params.get('id')
#     name = params.get('name')
#     subnets = params.get('subnets')
#     orchestrator_id = orchestrator['id']
#     self.update('PROGRESS', msg='Get configuration params')
#
#     # get parent cloud domain
#     self.get_session()
#     resource = self.get_resource(oid)
#     self.release_session()
#     self.update('PROGRESS', msg='Get resource %s' % resource)
#
#     # create network
#     self.get_session()
#     res = []
#     for s in subnets:
#         sid = ProviderOpenstack.create_subnet(self, orchestrator_id, resource, s['cidr'], s['gateway'],
#                                               s.get('routes', None), s.get('allocation_pools', None),
#                                               s['enable_dhcp'], s.get('dns_nameservers', None))
#         res.append(sid)
#
#     return res


# @task_manager.task(bind=True, base=ResourceJobTask)
# @job_task()
# def update_network_attribute(self, options):
#     """Update network attribute.
#
#
#
#         * **options** (tupla): Tupla with some useful options.
#             (class_name, objid, job, job id, start time,
#              time before new query, user)
#         * **sharedarea** (dict):
#
#             * **cid** (int): container id
#             * **subnets**: list of network subnet to add
#                 * **cidr**: subnet cidr. Ex. 194.116.110.0/24
#                 * **gateway**: gateway ip. Ex. 194.116.110.1
#                 * **routes**: network routes [optional]
#                 * **allocation_pools**: pools of continous ip in the subnet.
#                     Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
#                 * **enable_dhcp**: if True enable dhcp [optional]
#                 * **dns_nameservers**: list of dns. default=['8.8.8.8', '8.8.8.4']
#                     [optional]
#
#     :return:
#     """
#     params = self.get_shared_data()
#
#     # validate input params
#     oid = params.get('id')
#
#     # get parent cloud domain
#     self.get_session()
#     resource = self.get_resource(oid)
#     self.release_session()
#     self.update('PROGRESS', msg='Get resource %s' % resource)
#
#     # update network subnets
#     new_subnets = params.get('subnets')
#     attribs = resource.attribs
#     attribs['configs']['subnets'].extend(new_subnets)
#     params['attribute'] = attribs
#
#     self.set_shared_data(params)
#     self.update('PROGRESS', msg='Update shared data')
#     return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_site_network_append_physical_network(self, options):
    """Append vsphere or openstack network to provider site network

    :param options: Config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator
    :param sharedarea: shared area params
    :return:
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')
    network_type = params.get('network_type')
    net_id = params.get('network_id')
    orchestrator_type = params.get('orchestrator_type')
    self.update('PROGRESS', msg='Get configuration params')

    # get parent cloud domain
    self.get_session()
    resource = self.get_resource(oid)
    self.release_session()
    self.update('PROGRESS', msg='Get resource %s' % resource)

    # create network
    self.get_session()
    network_id = ProviderOrchestrator.get(orchestrator_type).append_network(self, resource, network_type, net_id)

    return network_id


# #
# # base function
# #
# def job_network_create(task, objid, params):
#     """Create provider network.
#
#
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **objid**: resource objid
#             * **parent**: resource parent id
#             * **cid**: container id
#             * **name**: resource name
#             * **desc**: resource desc
#             * **ext_id**: resource ext_id
#             * **active**: resource active
#             * **attribute** (:py:class:`dict`): attributes
#             * **tags**: comma separated resource tags to assign [default='']
#
#             * **orchestrators**: orchestrators index
#             * **site_id**: parent site id
#             * **external**: True if network is external
#             * **vlan**: vlan id
#             * **subnets**: list of network subnet
#                 * **cidr**: subnet cidr. Ex. 194.116.110.0/24
#                 * **gateway**: gateway ip. Ex. 194.116.110.1
#                 * **routes**: network routes [optional]
#                 * **allocation_pools**: pools of continous ip in the subnet.
#                     Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
#                 * **enable_dhcp**: if True enable dhcp [optional]
#                 * **dns_nameservers**: list of dns. default=['8.8.8.8', '8.8.8.4']
#                     [optional]
#     """
#     task.set_shared_data(params)
#     ops = task.get_options()
#
#     # remote orchestrators network
#     g_network = []
#     for orchestrator in params['orchestrators'].values():
#         if orchestrator['type'] == 'vsphere':
#             g_network.append(provider_create_vsphere_network.signature((ops, orchestrator),
#                                                                        immutable=True,
#                                                                        queue=task_manager.conf.TASK_DEFAULT_QUEUE))
#         elif orchestrator['type'] == 'openstack':
#             g_network.append(provider_create_openstack_network.signature((ops, orchestrator),
#                                                                          immutable=True,
#                                                                          queue=task_manager.conf.TASK_DEFAULT_QUEUE))
#
#     Job.create([
#         end_task,
#         create_resource_post,
#         g_network,
#         create_resource_pre,
#         start_task
#     ], ops).delay()
#     return True


# def job_network_update(self, objid, params):
#     """Update provider network.
#
#
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **cid** (int): container id
#             * **id** (int): resource id
#             * **uuid** (uuid): resource uuid
#             * **objid** (str): resource objid
#             * **ext_id** (str): physical id
#             * **orchestrators**: remote orchestrators
#             * **subnets**: list of network subnet to add
#                 * **cidr**: subnet cidr. Ex. 194.116.110.0/24
#                 * **gateway**: gateway ip. Ex. 194.116.110.1
#                 * **routes**: network routes [optional]
#                 * **allocation_pools**: pools of continous ip in the subnet.
#                     Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
#                 * **enable_dhcp**: if True enable dhcp [optional]
#                 * **dns_nameservers**: list of dns. default=['8.8.8.8', '8.8.8.4']
#                     [optional]
#
#     :return:
#
#         True
#     """
#     ops = self.get_options()
#     self.set_shared_data(params)
#
#     # remote orchestrators network
#     g_network = []
#     for orchestrator in params['orchestrators'].values():
#         if orchestrator['type'] == 'vsphere':
#             g_network.append(provider_update_vsphere_network.signature((ops, orchestrator),
#                                                                        immutable=True,
#                                                                        queue=task_manager.conf.TASK_DEFAULT_QUEUE))
#         elif orchestrator['type'] == 'openstack':
#             g_network.append(provider_update_openstack_network.signature((ops, orchestrator),
#                                                                          immutable=True,
#                                                                          queue=task_manager.conf.TASK_DEFAULT_QUEUE))
#
#     Job.create([
#         end_task,
#         update_resource_post,
#         update_network_attribute,
#         g_network,
#         update_resource_pre,
#         start_task
#     ], ops).delay()
#     return True
#
#
# def job_network_delete(task, objid, params):
#     """Delete provider network.
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **cid** (int): container id
#             * **id** (int): resource id
#             * **uuid** (uuid): resource uuid
#             * **objid** (str): resource objid
#             * **ext_id** (str): resource physical id
#             * **orchestrators**: remote orchestrators
#
#     :return: True
#     """
#     task.set_shared_data(params)
#     ops = task.get_options()
#
#     Job.create([
#         end_task,
#         expunge_resource_post,
#         group_remove_task(ops, params['orchestrators']),
#         expunge_resource_pre,
#         start_task
#     ], ops).delay()
#     return True


# def job_network_add_network(task, objid, params):
#     """Add vsphere network to provider network
#
#
#
#         * **objid** (str): objid of the resource. Ex. 110//2222//334//*
#         * **params** (:py:class:`dict`): input params
#
#             * **oid** (int): resource id
#             * **cid** (int): container id
#             * **network_type**: network type. Can be flat, vlan, vxlan
#             * **network_id**: True if network is external
#     """
#     task.set_shared_data(params)
#     ops = task.get_options()
#
#     Job.create([
#         end_task,
#         provider_append_network,
#         start_task
#     ], ops).delay()
#     return True