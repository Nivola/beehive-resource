# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen, truncate, dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import NsxResource


class NsxEdge(NsxResource):
    objdef = 'Vsphere.Nsx.NsxEdge'
    objuri = 'nsx_edges'
    objname = 'nsx_edge'
    objdesc = 'Vsphere Nsx edge'
    
    default_tags = ['vsphere', 'network']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.nsx_edge.NsxEdgeTask.'

    def __init__(self, *args, **kvargs):
        """ """
        NsxResource.__init__(self, *args, **kvargs)
        
        # child classes
        self.child_classes = []        

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)

        :raises ApiManagerError:
        """
        items = []
        
        nsx_manager_id = container.conn.system.nsx.summary_info()['hostName']
        edges = container.conn.network.nsx.edge.list()
        for edge in edges:
            items.append((edge['objectId'], edge['name'], nsx_manager_id, None))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = NsxEdge
                res.append((resclass, item[0], parent_id, resclass.objdef, item[1], parent_class))
        
        return res 

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # query vsphere nsx
        items = []
        edges = container.conn.network.nsx.edge.list()
        for edge in edges:
            items.append({
                'id': edge['objectId'],
                'name': edge['name'],
            })
        
        return items
    
    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass  = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]
        
        parent = container.get_resource_by_extid(parent_id)
        parent_id = parent.oid
        
        objid = '%s//%s' % (parent.objid, id_gen())
        
        res = {
            'resource_class': resclass,
            'objid': objid,
            'name': name,
            'ext_id': ext_id,
            'active': True,
            'desc': resclass.objdesc,
            'attrib': {},
            'parent': parent_id,
            'tags': resclass.default_tags
        }
        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        remote_entities = container.conn.network.nsx.edge.list()
        
        # create index of remote objs
        remote_entities_index = {i['id']: i for i in remote_entities}
        
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn('', exc_info=True)

        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.network.nsx.edge.get(self.ext_id)
            self.set_physical_entity(ext_obj)
        except:
            pass
    
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used  in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attribute
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.datacenter: datacenter id
        :param kvargs.cluster: cluster id
        :param kvargs.datastore: datastore id
        :param kvargs.uplink_dvpg: uplink dvpg id
        :param kvargs.uplink_ipaddress: uplink ip address
        :param kvargs.uplink_subnet_pool: uplink subnet pool
        :param kvargs.pwd: admin password
        :param kvargs.dns: list of dns
        :param kvargs.domain: dns zone
        :param kvargs.size: appliance size [default=compact]
        :return: kvargs
        :raises ApiManagerError:
        """
        # get parent manager
        manager = container.get_nsx_manager()
        objid = '%s//%s' % (manager.objid, id_gen())

        kvargs.update({
            'objid': objid,
            'parent': manager.oid
        })  

        kvargs['datacenter'] = container.get_simple_resource(kvargs['datacenter']).ext_id
        kvargs['cluster'] = container.get_simple_resource(kvargs['cluster']).ext_id
        kvargs['datastore'] = container.get_simple_resource(kvargs['datastore']).ext_id
        if kvargs.get('uplink_dvpg', None) is not None:
            kvargs['uplink_dvpg'] = container.get_simple_resource(kvargs['uplink_dvpg']).ext_id
        else:
            kvargs['uplink_dvpg'] = None
        kvargs['size'] = kvargs.get('size', 'compact')

        steps = [
            NsxEdge.task_path + 'create_resource_pre_step',
            NsxEdge.task_path + 'nsx_edge_create_step',
            NsxEdge.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps
        
        return kvargs
    
    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            NsxEdge.task_path + 'update_resource_pre_step',
            NsxEdge.task_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs
    
    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            NsxEdge.task_path + 'expunge_resource_pre_step',
            NsxEdge.task_path + 'nsx_edge_delete_step',
            NsxEdge.task_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs
    
    #
    # info
    #    
    def info(self):
        """Get info.
        
        :return: Dictionary with capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = NsxResource.info(self)
        return info

    def detail(self):
        """Get details.
        
        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = NsxResource.detail(self)
        try:
            if self.ext_obj is not None:
                details = info['details']
                details.update(self.container.conn.network.nsx.edge.info(self.ext_obj))
        except Exception as ex:
            self.logger.warn(ex)
        
        return info

    #
    # actions
    #
    def set_password(self, pwd):
        """set edge admin password
        
        :param pwd: admin password
        :return: 
        """
        if self.container is not None:
            self.container.conn.network.nsx.edge.reset_password(self.ext_id, pwd)
            self.logger.info('set edge %s admin password' % self.oid)

    #
    # vnic
    #
    def get_vnic_available_index(self):
        """get vnics

        :param portgroup: portgroup id [optional]
        :return:
        """
        resp = []
        if self.container is not None:
            res = self.container.conn.network.nsx.edge.vnics(self.ext_obj)
            resp = [r for r in res if dict_get(r, 'isConnected') == 'false']
        if len(resp) == 0:
            raise ApiManagerError('no available edge %s vnic index found' % self.oid)

        return resp[0]['index']

    def get_vnics(self, portgroup=None, index=None, vnic_type=None):
        """get vnics

        :param portgroup: portgroup id [optional]
        :param index: vnic index [optional]
        :param vnic_type: vnic type [optional]
        :return:
        """
        resp = []
        if self.container is not None:
            res = self.container.conn.network.nsx.edge.vnics(self.ext_obj)
            resp = res
            if portgroup is not None:
                portgroup = self.container.get_simple_resource(portgroup).ext_id
                resp = [r for r in res if r.get('portgroupId') == portgroup]
            if index is not None:
                resp = [r for r in res if r.get('index') == index]
            if vnic_type is not None:
                resp = [r for r in res if r.get('type') == vnic_type]

        self.logger.info('get edge %s vnics: %s' % (self.oid, truncate(resp)))
        return resp

    def get_vnic_primary_ip(self, vnic_id):
        """Get primary ip address of given vnic

        :param vnic_id: vnic index
        :return: ip address string, None otherwise
        """
        vnic = self.get_vnics(index=vnic_id)[0]
        return dict_get(vnic, 'addressGroups.addressGroup.primaryAddress')

    def add_vnic(self, index, vnic_type, portgroup, ip_address):
        """add vnic

        :param index: vnic index to configure
        :param vnic_type: vnic type. Can be Uplink or Internal
        :param portgroup: portgroup id
        :param ip_address: vnic primary ip address
        :return:
        """
        if self.container is not None:
            portgroup = self.container.get_simple_resource(portgroup).ext_id
            data = {
                'index': index,
                'type': vnic_type,
                'portgroupId': portgroup,
                'addressGroups': [{
                    'primaryAddress': ip_address
                }]
            }
            self.container.conn.network.nsx.edge.vnic_add(self.ext_id, data)
            self.logger.info('add edge %s vnic %s' % (self.oid, index))

    def update_vnic(self, index, **kwargs):
        """update existing vnic

        :param index: vnic index
        :param kwargs:
        :return:
        """
        if self.container is not None:
            self.container.conn.network.nsx.edge.vnic_update(self.ext_id, index, **kwargs)
            self.logger.info('update edge %s vnic %s' % (self.oid, index))

    def del_vnic(self, index):
        """delete vnic

        :param index: vnic index
        :return:
        """
        if self.container is not None:
            self.container.conn.network.nsx.edge.vnic_del(self.ext_id, index)
            self.logger.info('delete edge %s vnic %s' % (self.oid, index))

    #
    # firewall
    #
    def get_firewall_config(self):
        """get edge firewall config

        :return:
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.firewall(self.ext_obj)
            self.logger.info('get edge %s firewall config: %s' % (self.oid, truncate(res)))
        return res

    def get_firewall_rules(self):
        """get edge firewall rules

        :param rule: rule id
        :return:
        """
        res = []
        if self.ext_obj is not None:
            res = self.get_firewall_config().get('rules', [])
        return res

    def get_firewall_rule(self, name=None):
        """get edge firewall rule

        :param name: rule name
        :return:
        """
        rule_id = None
        if self.ext_obj is not None:
            rules = self.container.conn.network.nsx.edge.firewall_rules(self.ext_obj)
            for rule in rules:
                if rule.get('name') == name:
                    rule_id = rule.get('id')
                    self.logger.info('get edge %s firewall rule: %s' % (self.oid, rule_id))

        self.logger.warning('no edge %s firewall rule found' % self.oid)
        return rule_id

    def add_firewall_rule(self, name, desc=None, action='accept', enabled=True, logged=False, direction=None,
                          source=None, dest=None, appl=None):
        """add edge firewall rule

        :param name: rule name
        :param desc: rule description
        :param action: rule action. Can be: accept, deny [default=accept]
        :param enabled: rule status [default=True]
        :param logged: rule logged [default=False]
        :param direction: rule direction. Can be: in, out, inout [default=inout]
        :param source: rule source. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param dest: rule destination. list of comma separated item like: ip:<ipAddress>, grp:<groupingObjectId>,
            vnic:<vnicGroupId> [optional]
        :param appl: rule application. list of comma separated item like: app:<applicationId>,
            ser:proto+port+source_port [optional]
        :return: True or None
        """
        res = None
        if self.ext_obj is not None:
            if desc is None:
                desc = name
            if source:
                source = source.split(',')
            if dest:
                dest = dest.split(',')
            if appl:
                appl = appl.split(',')

            # self.container.conn.network.nsx.edge.get(self.oid)
            res = self.container.conn.network.nsx.edge.firewall_rule_add(self.ext_id, name, action, direction=direction,
                                                                         desc=desc, enabled=enabled, source=source,
                                                                         dest=dest, application=appl, logged=logged)
            self.logger.info('create firewall rule %s' % name)
        return res

    def del_firewall_rule(self, rule):
        """delete edge firewall rule

        :param rule: rule id
        :return:
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.firewall_rule_delete(self.ext_id, rule)
            self.logger.info('delete firewall rule %s' % rule)
        return res

    #
    # nat
    #
    def get_nat_config(self):
        """get edge nat config

        :return:
        """
        res = None
        if self.ext_obj is not None:
            # edge = self.container.conn.network.nsx.edge.get(self.oid)
            res = self.container.conn.network.nsx.edge.nat(self.ext_obj)
            self.logger.info('get edge %s nat config: %s' % (self.oid, truncate(res)))
        return res

    def get_nat_rule(self, desc=None, action=None, original_address=None, translated_address=None, original_port=None,
                     translated_port=None, protocol=None, vnic=None):
        """add edge nat rule

        :param desc: rule description [optional]
        :param action: can be dnat, snat [optional]
        :param original_address: original address [optional]
        :param translated_address: translated address [optional]
        :param original_port: original port [optional]
        :param translated_port: translated port [optional]
        :param protocol: protocol [optional]
        :param vnic: vnic [optional]
        :return: True or None
        """
        rule_id = None
        if self.ext_obj is not None:
            rules = self.container.conn.network.nsx.edge.nat(self.ext_obj)
            for rule in rules:
                if rule.get('description') == desc:
                    rule_id = rule.get('ruleId')
                    self.logger.info('get edge %s nat rule: %s' % (self.oid, rule_id))
        self.logger.warning('no edge %s nat rule found' % self.oid)
        return rule_id

    def add_nat_rule(self, desc, action, original_address, translated_address, enabled=True, logged=True,
                     original_port=None, translated_port=None, protocol=None, vnic=None, dnat_match_source_address=None,
                     dnat_match_source_port=None, snat_match_dest_address=None, snat_match_dest_port=None):
        """add edge nat rule

        :param desc: rule description
        :param action: can be dnat, snat
        :param enabled: rule status [default=True]
        :param logged: rule logged [default=False]
        :param original_address: original address
        :param translated_address: translated address
        :param original_port: original port [optional]
        :param translated_port: translated port [optional]
        :param protocol: protocol [optional]
        :param vnic: vnic [optional]
        :param dnat_match_source_address: dnat match source address [optional]
        :param dnat_match_source_port: dnat match source port [optional]
        :param snat_match_dest_address: snat match destination address [optional]
        :param snat_match_dest_port: snat match destination port [optional]
        :return: True or None
        """
        res = None
        if self.ext_obj is not None:
            self.container.conn.network.nsx.edge.nat_rule_add(self.ext_id, desc, action, original_address,
                                                              translated_address, logged=logged, enabled=enabled,
                                                              protocol=protocol, vnic=vnic,
                                                              translated_port=translated_port,
                                                              original_port=original_port,
                                                              dnat_match_source_address=dnat_match_source_address,
                                                              dnat_match_source_port=dnat_match_source_port,
                                                              snat_match_destination_address=snat_match_dest_address,
                                                              snat_match_destination_port=snat_match_dest_port)
            self.logger.info('create edge %s nat rule %s' % (self.oid, desc))
            res = True
        return res

    def del_nat_rule(self, rule):
        """delete edge nat rule

        :param rule: nat rule id
        :return:
        """
        res = None
        if self.ext_obj is not None:
            # self.container.conn.network.nsx.edge.get(self.oid)
            self.container.conn.network.nsx.edge.nat_rule_delete(self.ext_id, rule)
            self.logger.info('delete edge %s nat rule %s' % (self.oid, rule))
            res = True
        return res

    #
    # route
    #
    def get_router_config(self):
        """get edge routing info

        :return:
        """
        res = None
        if self.ext_obj is not None:
            # edge = self.container.conn.network.nsx.edge.get(self.oid)
            res = self.container.conn.network.nsx.edge.route(self.ext_obj)
            self.logger.info('get edge %s router config: %s' % (self.oid, truncate(res)))
        return res

    def get_router_static_config(self):
        """get edge static routes

        :return:
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.route_static_get(self.ext_id)
            self.logger.info('get edge %s router static config: %s' % (self.oid, truncate(res)))
        return res

    def add_default_route(self, gateway, vnic=0, mtu=1500):
        """add edge default route

        :param gateway: gateway ip address
        :param mtu: mut [default=1500]
        :param vnic: gateway vnic [deafult=0]
        :return:
        """
        res = None
        if self.ext_obj is not None:
            self.container.conn.network.nsx.edge.route_default_add(self.ext_id, gateway, mtu=mtu, vnic=vnic)
            self.logger.info('add edge %s default route' % self.oid)
            res = True
        return res

    def add_static_route(self, desc, network, next_hop, mtu=1500, vnic=0):
        """add edge default route

        :param desc: route description
        :param network: network cidr
        :param next_hop: next_hop address
        :param mtu: mtu [default=1500]
        :param vnic: vnic [default=0]
        :return:
        """
        res = None
        if self.ext_obj is not None:
            self.container.conn.network.nsx.edge.route_static_add(self.ext_id, desc, network, next_hop, mtu=mtu,
                                                                  vnic=vnic)
            self.logger.info('create edge %s static route' % self.oid)
            res = True
        return res

    def del_static_route(self):
        """delete edge static routes

        :return:
        """
        res = None
        if self.ext_obj is not None:
            self.container.conn.network.nsx.edge.route_static_del_all(self.ext_id)
            self.logger.info('delete edge %s static route' % self.oid)
            res = True
        return res

    def get_routes(self):
        """get edge routing info

        :return:
        """
        res = []
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.route_static_get(self.ext_id)
            self.logger.info('get edge %s router static config: %s' % (self.oid, truncate(res)))
        return res

    def add_route(self, route):
        """add route to edge

        :param route: route configuration {'destination':.., 'nexthop':..}
        :return:
        """
        destination = route['destination']
        nexthop = route['nexthop']
        if self.ext_obj is not None:
            desc = 'route-to-%s-by-%s' % (destination, nexthop)
            self.container.conn.network.nsx.edge.route_static_add(self.ext_id, desc, destination, nexthop)
            self.logger.info('create edge %s static route' % self.oid)
            return True
        return False

    def del_route(self, route):
        """delete route from edge

        :param route: route configuration {'destination':.., 'nexthop':..}
        :return:
        """
        destination = route['destination']
        nexthop = route['nexthop']
        if self.ext_obj is not None:
            desc = 'route-to-%s-by-%s' % (destination, nexthop)
            self.container.conn.network.nsx.edge.route_static_del(self.ext_id, destination, nexthop)
            self.logger.info('delete edge %s static route' % self.oid)
            return True
        return False

    def add_routes(self, routes):
        """add routes to edge

        :param routes: routes configuration [{'destination':.., 'nexthop':..}]
        :return:
        """
        if self.ext_obj is not None:
            self.container.conn.network.nsx.edge.route_static_adds(self.ext_id, routes)
            return True
        return False

    def del_routes(self, routes):
        """delete routes from edge

        :param routes: routes configuration [{'destination':.., 'nexthop':..}]
        :return:
        """
        if self.ext_obj is not None:
            self.container.conn.network.nsx.edge.route_static_dels(self.ext_id, routes)
            return True
        return False

    #
    # load balancer
    #
    def enable_lb(self):
        """Enable load balancer functionality on network edge

        :return:
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.config_update(self.ext_id, enabled=True, logging=True,
                                                                        log_level='INFO')
            self.logger.info('enable lb on edge %s' % self.oid)
        return res

    def disable_lb(self):
        """Disable load balancer functionality on network edge

        :return:
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.config_update(self.ext_id, enabled=False, logging=False)
            self.logger.info('disable lb on edge %s' % self.oid)
        return res

    def get_lb_monitors(self):
        """List network edge load balancer health monitors

        :return: list of dict with monitor configurations
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.monitor_list(self.ext_id)
        return res

    def get_lb_monitor(self, monitor):
        """Get network edge load balancer health monitor

        :param monitor: monitor id
        :return: dict with monitor configuration
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.monitor_get(self.ext_obj, monitor)
            self.logger.info('get lb monitor %s' % monitor)
        return res

    def add_lb_monitor(self, **kvargs):
        """Add network edge load balancer monitor

        :param kvargs.name: name of the monitor
        :param kvargs.monitor_type: the protocol the load balancer uses when performing health checks on backend servers
        :param kvargs.interval: interval in seconds in which a server is to be tested
        :param kvargs.timeout: maximum time in seconds within which a response from the server must be received
        :param kvargs.max_retries: maximum number of times the server is tested before it is declared down
        :param kvargs.method: method to send the health check request to the server
        :param kvargs.request_uri: URL to send GET or POST requests
        :param kvargs.expected: expected string, e.g. 200 in case of success
        :param kvargs.send: string to be sent to the backend server after a connection is established
        :param kvargs,receive: string to be received from the backend server for HTTP/HTTPS protocol
        :param kvargs.extension: advanced monitor configuration
        :return: dict {'ext_id': '<ext_id>'} in case of success; None otherwise
        """
        res = None
        if self.ext_obj is not None:
            name = kvargs.get('name')
            monitor_type = kvargs.get('protocol')
            hm_params = {
                'interval': kvargs.get('interval'),
                'timeout': kvargs.get('timeout'),
                'max_retries': kvargs.get('max_retries'),
                'method': kvargs.get('method'),
                'url': kvargs.get('request_uri'),
                'expected': kvargs.get('expected'),
                'send': kvargs.get('send'),
                'receive': kvargs.get('receive'),
                'extension': kvargs.get('extension'),
            }

            # remove keys with None values
            filtered = {k: v for k, v in hm_params.items() if v is not None}
            hm_params.clear()
            hm_params.update(filtered)

            res = self.container.conn.network.nsx.edge.lb.monitor_add(self.ext_id, name, monitor_type, **hm_params)
            self.logger.info('create lb health monitor %s' % res.get('ext_id'))
        return res

    def del_lb_monitor(self, monitor):
        """Delete network edge load balancer health monitor

        :param monitor: monitor id
        :return: True in case of success, None otherwise
        """
        res = False
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.monitor_del(self.ext_id, monitor)
            self.logger.info('delete lb monitor %s' % monitor)
        return res

    def get_lb_pools(self):
        """List network edge load balancer pools

        :return: list of dict with pool configurations
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.pool_list(self.ext_id)
        return res

    def get_lb_pool(self, pool):
        """Get network edge load balancer pool

        :return: dict with pool configuration
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.pool_get(self.ext_id, pool)
            self.logger.info('get lb pool %s' % pool)
        return res

    def add_lb_pool(self, **kvargs):
        """Add network edge load balancer monitor

        :param kvargs.name: pool name
        :param kvargs.balancing_algorithm: the algorithm used to balance backend nodes
        :param kvargs.description: pool description
        :param kvargs.monitor_id: health monitor external id
        :return: dict {'ext_id': '<ext_id>'} in case of success; None otherwise
        """
        res = None
        if self.ext_obj is not None:
            name = kvargs.get('name')
            balancing_algorithm = kvargs.get('balancing_algorithm')
            pool_params = {
                'description': kvargs.get('desc'),
                'monitor_id': kvargs.get('monitor_id'),
            }

            # remove keys with None values
            filtered = {k: v for k, v in pool_params.items() if v is not None}
            pool_params.clear()
            pool_params.update(filtered)

            res = self.container.conn.network.nsx.edge.lb.pool_add(self.ext_id, name, balancing_algorithm,
                                                                   **pool_params)
            self.logger.info('create lb pool %s' % res.get('ext_id'))
        return res

    def populate_lb_pool(self, pool, members):
        """Add members to pool

        :param pool: pool external id
        :param members: list of members to be added
        :return:
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.pool_members_add(self.ext_id, pool, members)
            self.logger.info('populate lb pool with members %s' % ', '.join(member.get('name') for member in members))
        return res

    def del_lb_pool(self, pool):
        """Delete network edge load balancer pool

        :param pool: pool id
        :return: True in case of success, None otherwise
        """
        res = False
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.pool_del(self.ext_id, pool)
            self.logger.info('delete lb pool %s' % pool)
        return res

    def get_lb_app_profiles(self):
        """List network edge load balancer application profiles

        :return: list of dict with application profile configurations
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.app_profile_list(self.ext_id)
        return res

    def get_lb_app_profile(self, profile):
        """Get network edge load balancer application profile

        :return: dict with application profile configuration
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.app_profile_get(self.ext_id, profile)
            self.logger.info('get lb application profile %s' % profile)
        return res

    @staticmethod
    def __traffic_type_mapping(traffic_type: str) -> dict:
        mapper = {
            'http': {
                'template': 'http',
                'ssl_passthrough': None,
                'server_ssl_enabled': None,
            },
            'ssl-passthrough': {
                'template': 'https',
                'ssl_passthrough': True,
                'server_ssl_enabled': False
            },
            'https-offloading': {
                'template': 'https',
                'ssl_passthrough': False,
                'server_ssl_enabled': False,
            },
            'https-end-to-end': {
                'template': 'https',
                'ssl_passthrough': False,
                'server_ssl_enabled': True
            }
        }
        return mapper.get(traffic_type)

    def add_lb_app_profile(self, **kvargs):
        """Add network edge load balancer application profile

        :param kvargs.name: application profile name
        :param kvargs.traffic_type: traffic template used by load balancer to improve incoming traffic management
        :param kvargs:
        :return: dict {'ext_id': '<ext_id>'} in case of success; None otherwise
        """
        res = None
        if self.ext_obj is not None:
            name = kvargs.get('name')
            traffic_type = kvargs.get('traffic_type')
            d = self.__traffic_type_mapping(traffic_type)
            template = d.get('template').upper()
            ap_params = {
                'ssl_passthrough': d.get('ssl_passthrough'),
                'server_ssl_enabled': d.get('server_ssl_enabled'),
                'http_redirect_url': kvargs.get('http_redirect_url'),
                'persistence': kvargs.get('persistence'),
                'expire': kvargs.get('expire'),
                'cookie_name': kvargs.get('cookie_name'),
                'cookie_mode': kvargs.get('cookie_mode'),
                'insert_x_forwarded_for': kvargs.get('insert_x_forwarded_for'),
                'client_ssl_service_certificate': kvargs.get('client_ssl_service_certificate'),
                'client_ssl_ca_certificate': kvargs.get('client_ssl_ca_certificate'),
                'client_ssl_cipher': kvargs.get('client_ssl_cipher'),
                'client_auth': kvargs.get('client_auth'),
                'server_ssl_service_certificate': kvargs.get('server_ssl_service_certificate'),
                'server_ssl_ca_certificate': kvargs.get('server_ssl_ca_certificate'),
                'server_ssl_cipher': kvargs.get('server_ssl_cipher'),
            }

            # remove keys whose value is None
            filtered = {k: v for k, v in ap_params.items() if v is not None}
            ap_params.clear()
            ap_params.update(filtered)

            res = self.container.conn.network.nsx.edge.lb.app_profile_add(self.ext_id, name, template, **ap_params)
            self.logger.info('create lb application profile %s' % res.get('ext_id'))
        return res

    def del_lb_app_profile(self, profile):
        """Delete network edge load balancer application profile

        :param profile: application profile id
        :return: True in case of success, None otherwise
        """
        res = False
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.app_profile_del(self.ext_id, profile)
            self.logger.info('delete lb application profile %s' % profile)
        return res

    def get_lb_virt_servers(self):
        """List network edge load balancer virtual servers

        :return: list of dict with virtual server configurations
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.virt_server_list(self.ext_id)
        return res

    def get_lb_virt_server(self, virt_srv):
        """Get network edge load balancer virtual server

        :return: dict with virtual server configuration
        """
        res = None
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.virt_server_get(self.ext_id, virt_srv)
            self.logger.info('get lb virtual server %s' % virt_srv)
        return res

    def add_lb_virt_server(self, **kvargs):
        """Add network edge load balancer virtual server

        :param kvargs:
        :return: dict {'ext_id': '<ext_id>'} in case of success; None otherwise
        """
        res = None
        if self.ext_obj is not None:
            name = kvargs.get('name')
            ip_address = dict_get(kvargs, 'vip.ip')
            protocol = kvargs.get('protocol')
            port = kvargs.get('port')
            app_profile = kvargs.get('app_profile_id')
            pool = kvargs.get('pool_id')
            vs_params = {
                'desc': kvargs.get('desc'),
                'max_conn': kvargs.get('max_conn'),
                'max_conn_rate': kvargs.get('max_conn_rate'),
                'enable': True,
                'acceleration_enabled': False
            }

            # remove keys whose value is None
            filtered = {k: v for k, v in vs_params.items() if v is not None}
            vs_params.clear()
            vs_params.update(filtered)

            res = self.container.conn.network.nsx.edge.lb.virt_server_add(self.ext_id, name, ip_address, protocol,
                                                                          port, app_profile, pool, **vs_params)
            self.logger.info('create lb virtual server %s' % res.get('ext_id'))
        return res

    def del_lb_virt_server(self, virt_server):
        """Delete network edge load balancer virtual server

        :param virt_server: virtual server id
        :return:
        """
        res = False
        if self.ext_obj is not None:
            res = self.container.conn.network.nsx.edge.lb.virt_server_del(self.ext_id, virt_server)
            self.logger.info('delete lb virtual server %s' % virt_server)
        return res
