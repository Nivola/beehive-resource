# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.gateway import ComputeGateway
from beehive_resource.plugins.provider.helper.network_appliance import AbstractProviderNetworkApplianceHelper
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge


class VsphereNsxEdgeFirewallRule(object):
    rules = {
        'any2lb': {
            'action': 'accept',
            'direction': 'in',
            'source': 'ip:any',
            'dest': 'xxxxxxxxxx',
            'appl': 'ser:tcp+80+any'
        },
        'edge2backend': {
            'action': 'accept',
            'direction': 'in',
            'source': 'xxxxxxxxxx',
            'dest': 'xxxxxxxxxx',
            'appl': 'ser:tcp+80+any'
        }
    }


class ProviderVsphereHelper(AbstractProviderNetworkApplianceHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.edge = None

    def select_network_appliance(self, vpc_id, site_id, *args, **kvargs):
        """Select the network appliance where configuring the load balancer. In vSphere world, the network appliance
        corresponds with the nsx network edge.

        :param vpc_id: vpc id
        :param site_id: site id
        :param kvargs.net_appl_tag: list of tags the network appliance to select have attached
        :param kvargs.selection_criteria: criteria to select the network appliance where configuring the load balancer
        :return: network edge object if exists, None otherwise
        """
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc, SiteNetwork
        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway, Gateway
        from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge

        # get vpc
        vpc: Vpc = self.controller.get_simple_resource(vpc_id)
        # - shared
        if vpc.is_shared():
            # get network
            network: SiteNetwork = vpc.get_network_by_site(site_id)

            # get tag
            edge_tag = kvargs.get('net_appl_tag')
            if edge_tag is None:
                edge_tag = network.get_attribs(key='configs.network_appliance.tag')
            self.logger.debug('Vsphere nsx edge tag: %s' % edge_tag)

            # get criteria to choose the proper network appliance
            selection_criteria = kvargs.get('selection_criteria')
            if selection_criteria is None:
                selection_criteria = network.get_attribs(key='configs.network_appliance.selection_criteria')
            orchestrator = self.orchestrator.get('type')
            max_virtual_server = dict_get(selection_criteria, orchestrator + '.by_components.max_virtual_server')
            cpu_max_usage = dict_get(selection_criteria, orchestrator + '.by_performance.max_cpu')
            memory_max_usage = dict_get(selection_criteria, orchestrator + '.by_performance.max_memory')
            disk_max_usage = dict_get(selection_criteria, orchestrator + '.by_performance.max_disk')
            self.logger.debug('Nsx edge selection criteria: max_virtual_server: %d' % max_virtual_server)
            self.logger.debug('Nsx edge selection criteria: cpu_max_usage: %d, memory_max_usage: %d, disk_max_usage: %d'
                              % (cpu_max_usage, memory_max_usage, disk_max_usage))

            # get nsx edges
            edges: NsxEdge = self.container.get_nsx_edges(resourcetags=edge_tag)

            # select edge if exists
            final_edge = None
            for edge in edges:
                # get virtual servers
                virt_servers = edge.get_lb_virt_servers()
                # apply selection criteria
                if len(virt_servers) < max_virtual_server:
                    final_edge = edge
                    break
            if final_edge is None:
                raise ApiManagerError('No suitable edge found where configuring load balancer')
            return final_edge
        # - private
        elif vpc.is_private():
            # get gateway
            compute_gateway: ComputeGateway = self.compute_zone.get_default_gateway()

            # get zone gateway
            gateways, tot = compute_gateway.get_linked_resources(link_type_filter='relation.%', objdef=Gateway.objdef,
                                                                 run_customize=False)
            if tot == 0:
                raise ApiManagerError('No gateway found in compute zone %s' % self.compute_zone.uuid)
            gateway = gateways[0]

            # get nsx edge
            edge: NsxEdge = gateway.get_nsx_edge()

            # get virtual servers
            virt_servers = edge.get_lb_virt_servers()

            # apply selection criteria
            if len(virt_servers) >= 20:
                raise ApiManagerError('No suitable edge found where configuring load balancer')
            return edge

    def get_network_appliance(self, edge_id):
        """Get network appliance

        :param edge_id: network appliance id
        """
        self.edge: NsxEdge = self.controller.get_simple_resource(edge_id)
        self.edge.set_container(self.controller.get_container(self.edge.container_id))
        self.edge.post_get()

    def reserve_ip_address(self, vpc_id, site_id, static_ip):
        """Allocate an IP address for the load balancer

        :param vpc_id: vpc id
        :param site_id: site id
        :param static_ip: ip address specified by the user
        :return: dict with reserved ip address and other info
        """
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc, SiteNetwork

        # get vpc
        vpc: Vpc = self.controller.get_simple_resource(vpc_id)

        # get network
        network: SiteNetwork = vpc.get_network_by_site(site_id)

        # get network subnets
        subnets = network.get_attribs(key='configs.subnets', default=[])
        subnet = subnets[0]

        # get ippool
        ippool_id = subnet.get('vsphere_id')

        # allocate ip address
        conn = self.container.conn
        allocated_ips = conn.network.nsx.ippool.allocations(ippool_id)
        if static_ip is not None and static_ip in allocated_ips:
            raise ApiManagerError('Ip address %s specified by user is already allocated' % static_ip)
        new_ip = conn.network.nsx.ippool.allocate(ippool_id, static_ip=static_ip)
        self.logger.warning('____real_new_ip={}'.format(new_ip))

        # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
        # Temporary workaround to avoid getting following error:
        # "BAD_REQUEST - Address group IP addresses in EdgeVnic uplink-ext-internet are not in the same subnet."
        # To be removed in real cases.
        fake_ip = '10.102.186.66'
        self.logger.warning('____fake_new_ip={}'.format(fake_ip))
        # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

        return {
            # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
            # 'ip': new_ip.get('ipAddress'),
            'ip': fake_ip,
            # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
            'is_static': True if static_ip is not None else False,
            'ip_pool': ippool_id,
            'gateway': new_ip.get('gateway'),
            'dns': new_ip.get('dnsServer1') + ',' + new_ip.get('dnsServer2'),
            'dns_search': new_ip.get('dnsSuffix'),
            'prefix': new_ip.get('prefixLength'),
        }

    def release_ip_address(self, ip_pool, ip_addr):
        """Release IP address allocated for load balancer

        :return:
        """
        # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
        self.logger.warning('____release_ip_address.ip_pool={}'.format(ip_pool))
        self.logger.warning('____release_ip_address.ip_addr_fake={}'.format(ip_addr))
        real_ip = '10.102.185.84'
        ip_addr = real_ip
        self.logger.warning('____release_ip_address.ip_addr_real={}'.format(ip_addr))
        # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
        self.container.conn.network.nsx.ippool.release(ip_pool, ip_addr)
        self.logger.info('Release ip address %s from ip pool %s' % (ip_addr, ip_pool))

    def create_load_balancer(self, params, *args, **kvargs):
        """Create load balancer

        :param params: load balancer params
        :param args:
        :param kvargs:
        :return:
        """
        # get network edge
        if self.edge is None:
            edge_id = params.get('net_appl')
            self.get_network_appliance(edge_id)

        # add secondary ip to uplink network interface
        vnics = self.edge.get_vnics(vnic_type='uplink')
        if len(vnics) != 1:
            raise ApiManagerError('Uplink vnic not found or is not unique')
        uplink_vnic = vnics[0]
        vnic_ext_id = uplink_vnic.get('index')
        primary_ip = dict_get(uplink_vnic, 'addressGroups.addressGroup.primaryAddress')
        secondary_ip = dict_get(params, 'vip.ip')
        self.__update_vnic(vnic_ext_id, secondary_ip)

        # enable load balancer
        self.edge.enable_lb()
        self.logger.info('Enable lb on network edge %s' % self.edge.name)

        # create/select health monitor
        hm_params = params.get('health_monitor')
        hm_type = hm_params.get('type')
        if hm_type == 'custom':
            hm_ext_id = self.__create_lb_monitor(hm_params)
            if hm_ext_id is None:
                raise ApiManagerError('Cannot create custom lb health monitor on network edge %s' % self.edge.name)
        else:
            hm_ext_id = self.__select_lb_monitor(hm_params)
            if hm_ext_id is None:
                raise ApiManagerError('Unable to find predefined lb health monitor on network edge %s' % self.edge.name)
        params['target_group'].update({'monitor_id': hm_ext_id})

        # create pool
        pool_params = params.get('target_group')
        pool_ext_id = self.__create_lb_pool(pool_params)
        if pool_ext_id is None:
            raise ApiManagerError('Cannot create lb pool on network edge %s' % self.edge.name)
        params.update({'pool_id': pool_ext_id})

        # add members to pool
        members = pool_params.get('targets')
        self.__populate_lb_pool(pool_ext_id, members)

        # create/select application profile
        ap_params = params.get('listener')
        ap_type = ap_params.get('type')
        if ap_type == 'custom':
            ap_ext_id = self.__create_lb_app_profile(ap_params)
            if ap_ext_id is None:
                raise ApiManagerError('Cannot create custom lb application profile on network edge %s' % self.edge.name)
        else:
            ap_ext_id = self.__select_lb_app_profile(ap_params)
            if hm_ext_id is None:
                raise ApiManagerError('Unable to find predefined lb application profile on network edge %s'
                                      % self.edge.name)
        params.update({'app_profile_id': ap_ext_id})

        # create virtual server
        vs_ext_id = self.__create_lb_virt_server(params)
        if vs_ext_id is None:
            raise ApiManagerError('Cannot create lb virtual server on network edge %s' % self.edge.name)

        res = {
            'uplink_vnic': {
                'ext_id': vnic_ext_id,
                'secondary_ip': secondary_ip,
                'is_static': dict_get(params, 'vip.is_static'),
                'ip_pool': dict_get(params, 'vip.ip_pool')
            },
            'health_monitor': {
                'ext_id': hm_ext_id,
                'type': hm_type
            },
            'pool': {
                'ext_id': pool_ext_id
            },
            'application_profile': {
                'ext_id': ap_ext_id,
                'type': ap_type
            },
            'virtual_server': {
                'ext_id': vs_ext_id
            },
            'fw_rules': []
        }

        # create firewall rules
        for k, v in VsphereNsxEdgeFirewallRule.rules.items():
            if k == 'any2lb':
                v['dest'] = 'ip:%s/32' % secondary_ip
            elif k == 'edge2backend':
                v['source'] = 'ip:%s/32' % primary_ip
                v['dest'] = ','.join(['ip:' + member.get('ip_addr') + '/32' for member in members])
            ext_id, name, flag = self.__create_fw_rule(**v)
            if ext_id is None:
                raise ApiManagerError('Cannot create firewall rule %s on network edge %s' % (k, self.edge.name))
            res['fw_rules'].append({'name': name, 'ext_id': ext_id, 'is_shared': flag})

        return res

    def get_uplink_vnic_primary_ip(self, edge_id):
        """Get primary ip of uplink network interface

        :param edge_id: network appliance id
        :return: ip address string, None otherwise
        """
        if self.edge is None:
            self.get_network_appliance(edge_id)

        # get uplink vnic
        vnics = self.edge.get_vnics(vnic_type='uplink')
        if len(vnics) != 1:
            raise ApiManagerError('Uplink vnic not found or is not unique')
        uplink_vnic = vnics[0]
        # get primary ip
        primary_ip = dict_get(uplink_vnic, 'addressGroups.addressGroup.primaryAddress')
        return primary_ip

    def __update_vnic(self, vnic_id, ip_addr):
        self.edge.update_vnic(vnic_id, secondary_ip=ip_addr, action='add')
        self.logger.info('Add secondary ip address %s to vnic %s on network edge %s' % (ip_addr, vnic_id,
                                                                                        self.edge.name))
        return True

    def __create_lb_monitor(self, params):
        res = self.edge.add_lb_monitor(**params)
        ext_id = res.get('ext_id')
        self.logger.info('Create custom lb health monitor %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id

    def __select_lb_monitor(self, params):
        orchestrator = self.orchestrator.get('type')
        monitor_name = dict_get(params, 'physical_resources.' + orchestrator + '.name')
        res = self.edge.get_lb_monitors()
        ext_id = next((item.get('monitorId') for item in res if item.get('name') == monitor_name), None)
        self.logger.info('Select predefined lb health monitor %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id

    def __create_lb_pool(self, params):
        res = self.edge.add_lb_pool(**params)
        ext_id = res.get('ext_id')
        self.logger.info('Create lb pool %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id

    def __populate_lb_pool(self, pool, members):
        res = self.edge.populate_lb_pool(pool, members)
        self.logger.info('Populate lb pool %s with members %s' % (pool, ', '.join(member.get('name')
                                                                                  for member in members)))
        return res

    def __create_lb_app_profile(self, params):
        res = self.edge.add_lb_app_profile(**params)
        ext_id = res.get('ext_id')
        self.logger.info('Create lb application profile %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id

    def __select_lb_app_profile(self, params):
        orchestrator = self.orchestrator.get('type')
        profile_name = dict_get(params, 'physical_resources.' + orchestrator + '.name')
        res = self.edge.get_lb_app_profiles()
        ext_id = next((item.get('applicationProfileId') for item in res if item.get('name') == profile_name), None)
        self.logger.info('Select predefined lb application profile %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id

    def __create_lb_virt_server(self, params):
        res = self.edge.add_lb_virt_server(**params)
        ext_id = res.get('ext_id')
        self.logger.info('Create lb virtual server %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id

    def __create_fw_rule(self, **rule_params):
        """

        :return:
        """
        action = rule_params.get('action')
        direction = rule_params.get('direction')
        source = rule_params.get('source')
        dest = rule_params.get('dest')
        appl = rule_params.get('appl')

        name = ComputeGateway.get_firewall_rule_name(action, direction, source, dest, appl)

        found = False
        rule = self.edge.get_firewall_rule(name=name)
        if rule is not None:
            self.logger.warning('Firewall rule %s already exists' % name)
            ext_id = rule
            found = True
        else:
            res = self.edge.add_firewall_rule(name, action=action, enabled=True, logged=False, direction=direction,
                                              source=source, dest=dest, appl=appl)
            ext_id = res.get('ext_id')
            self.logger.info('Create firewall rule %s on network edge %s' % (ext_id, self.edge.name))
        return ext_id, name, found

    def delete_load_balancer(self, params, *args, **kvargs):
        """Delete load balancer

        :param params:
        :param args:
        :param kvargs:
        :return:
        """
        # get network edge
        edge_id = params.get('net_appl')
        edge: NsxEdge = self.controller.get_simple_resource(edge_id)
        edge.set_container(edge.controller.get_container(edge.container_id))
        edge.post_get()

        # delete virtual server
        vs_ext_id = dict_get(params, 'virtual_server.ext_id')
        try:
            edge.del_lb_virt_server(vs_ext_id)
            self.logger.info('Delete lb virtual server %s on network edge %s' % (vs_ext_id, edge.name))
        except:
            raise ApiManagerError('Cannot delete lb virtual server %s on network edge %s' % (vs_ext_id, edge.name))

        # delete secondary ip address from uplink network interface
        vnic_ext_id = dict_get(params, 'vnic.ext_id')
        secondary_ip = dict_get(params, 'vnic.secondary_ip')
        try:
            edge.update_vnic(vnic_ext_id, secondary_ip=secondary_ip, action='delete')
            self.logger.info('Remove secondary ip address %s from vnic %s on network edge %s' %
                             (secondary_ip, vnic_ext_id, edge.name))
        except:
            raise ApiManagerError('Cannot update vnic %s on network edge %s' % (vnic_ext_id, edge.name))

        # delete application profile
        ap_type = dict_get(params, 'application_profile.type')
        ap_ext_id = dict_get(params, 'application_profile.ext_id')
        if ap_type not in ['predefined', 'custom']:
            raise ApiManagerError('Bad type for lb application profile %s: %s' % (ap_ext_id, ap_type))
        if ap_type == 'predefined':
            self.logger.info('Application profile %s is predefined and cannot be deleted' % ap_ext_id)
        else:
            try:
                edge.del_lb_app_profile(ap_ext_id)
                self.logger.info('Delete custon lb application profile %s on network edge %s' % (ap_ext_id,
                                                                                                 edge.name))
            except:
                raise ApiManagerError('Cannot delete lb application profile %s on network edge %s' % (ap_ext_id,
                                                                                                      edge.name))

        # delete pool
        pool_ext_id = dict_get(params, 'pool.ext_id')
        try:
            edge.del_lb_pool(pool_ext_id)
            self.logger.info('Delete lb pool %s on network edge %s' % (pool_ext_id, edge.name))
        except:
            raise ApiManagerError('Cannot delete lb pool %s on network edge %s' % (pool_ext_id, edge.name))

        # delete custom health monitor only
        hm_type = dict_get(params, 'health_monitor.type')
        hm_ext_id = dict_get(params, 'health_monitor.ext_id')
        if hm_type not in ['predefined', 'custom']:
            raise ApiManagerError('Bad type for lb health monitor %s: %s' % (hm_ext_id, hm_type))
        if hm_type == 'predefined':
            self.logger.info('Health monitor %s is predefined and cannot be deleted' % hm_ext_id)
        else:
            try:
                edge.del_lb_monitor(hm_ext_id)
                self.logger.info('Delete custom lb health monitor %s on network edge %s' % (hm_ext_id, edge.name))
            except:
                raise ApiManagerError('Cannot delete custom lb health monitor %s on network edge %s' % (hm_ext_id,
                                                                                                        edge.name))

        # delete firewall rules
        fw_rules = dict_get(params, 'fw_rules')
        for fw_rule in fw_rules:
            fwr_ext_id = fw_rule.get('ext_id')
            is_shared = fw_rule.get('is_shared')
            if is_shared:
                self.logger.info('Firewall rule %s might be shared with other edge resources and cannot be deleted' %
                                 fwr_ext_id)
                continue
            try:
                edge.del_firewall_rule(fwr_ext_id)
                self.logger.info('Delete firewall rule %s on network edge %s' % (fwr_ext_id, edge.name))
            except:
                raise ApiManagerError('Cannot delete firewall root %s on network edge %s' % (fwr_ext_id, edge.name))

        # disable load balancer
        edge.disable_lb()
        self.logger.info('Disable lb on network edge %s' % edge.name)

        return True


class ProviderOPNsenseHelper(AbstractProviderNetworkApplianceHelper):
    def select_network_appliance(self, *args, **kvargs):
        """Select the network appliance where configuring the load balancer. In OPNsense world, the network appliance
        corresponds with ...

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def get_network_appliance(self, net_appl_id, *args, **kvargs):
        """Get network appliance

        :param net_appl_id: network appliance id
        """
        pass

    def reserve_ip_address(self, *args, **kvargs):
        """Allocate an IP address for the load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def create_load_balancer(self, *args, **kvargs):
        """Create load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def get_uplink_vnic_primary_ip(self, net_appl_id, *args, **kvargs):
        """Get primary ip of uplink network interface

        :param net_appl_id: network appliance id
        :return: ip address string, None otherwise
        """
        pass

    def delete_load_balancer(self, *args, **kvargs):
        """Delete load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass


class ProviderHAproxyHelper(AbstractProviderNetworkApplianceHelper):
    def select_network_appliance(self, *args, **kvargs):
        """Select the network appliance where configuring the load balancer. In HAProxy world, the network appliance
        corresponds with ...

        :return:
        """
        pass

    def get_network_appliance(self, net_appl_id, *args, **kvargs):
        """Get network appliance

        :param net_appl_id: network appliance id
        """
        pass

    def reserve_ip_address(self, *args, **kvargs):
        """Allocate an IP address for the load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def create_load_balancer(self, *args, **kvargs):
        """Create load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def get_uplink_vnic_primary_ip(self, net_appl_id, *args, **kvargs):
        """Get primary ip of uplink network interface

        :param net_appl_id: network appliance id
        :return: ip address string, None otherwise
        """
        pass

    def delete_load_balancer(self, *args, **kvargs):
        """Delete load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass
