# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task


class OpenstackSubnet(OpenstackResource):
    objdef = 'Openstack.Domain.Project.Network.Subnet'
    objuri = 'subnets'
    objname = 'subnet'
    objdesc = 'Openstack network subnets'
    
    default_tags = ['openstack', 'network']
    task_path = 'beehive_resource.plugins.openstack.task_v2.ops_subnet.SubnetTask.'   
    
    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.network = None
        self.project = None
    
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
        # get from openstack
        if ext_id is not None:
            items = container.conn.network.subnet.get(oid=ext_id)
        else:
            items = container.conn.network.subnet.list()

        # add new item to final list
        res = []
        for item in items:
            if item['id'] not in res_ext_ids:
                level = None
                parent_id = None
                name = item['name']
                parent_id = item['network_id']
                if str(parent_id) == '':
                    parent_id = None                
                    
                res.append((OpenstackSubnet, item['id'], parent_id, OpenstackSubnet.objdef, name, level))
        
        return res    
    
    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        return container.conn.network.subnet.list()
    
    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        level = entity[5]     
        
        # get parent project
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            objid = '%s//%s' % (parent.objid, id_gen())
            parent_id = parent.oid
        else:
            objid = '%s//none//none//none//%s' % (container.objid, id_gen())
            parent_id = None
        
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
    def get_entities_filter(controller, container_id, *args, **kvargs):
        """Create a list of ext_id to use as resource filter. Use when you
        want to filter resources with a subset of remote physical id.

        :param controller: controller instance
        :param container_id: list of entities
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cidr: subnet cidr like 10.102.19.0/24 [optional]
        :param kvargs.network: subnet network [optional]
        :param kvargs.gateway_ip: subnet gateway_ip like 10.102.19.1[optional]
        :return: list of ext_id
        :raise ApiManagerError:
        """
        from .ops_network import OpenstackNetwork

        # get container
        container = controller.get_container(container_id)

        network = kvargs.get('network', None)
        network_extid = None
        if network is not None:
            net_resource = controller.get_resource(network, entity_class=OpenstackNetwork)
            network_extid = net_resource.ext_id
        cidr = kvargs.get('cidr', None)
        gateway_ip = kvargs.get('gateway_ip', None)
        remote_entities = container.conn.network.subnet.list(cidr=cidr, network=network_extid, gateway_ip=gateway_ip)

        # create index of remote objs
        ext_ids = [i['id'] for i in remote_entities]

        return ext_ids

    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.
        
        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.network: network ext_id
        :return: None
        :raise ApiManagerError:
        """
        network = kvargs.get('network', None)
        remote_entities = container.conn.network.subnet.list(network=network)
        
        # create index of related objs
        from ..entity.ops_network import OpenstackNetwork
        net_index = controller.index_resources_by_extid(OpenstackNetwork)        
        
        # create index of remote objs
        remote_entities_index = {i['id']: i for i in remote_entities}
        
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                if ext_obj is not None:
                    entity.set_physical_entity(ext_obj)
                    entity.network = net_index[ext_obj['network_id']]
            except:
                container.logger.warn('', exc_info=1)
        return entities    
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:            
        :raises ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.network.subnet.get(oid=self.ext_id)
            self.set_physical_entity(ext_obj)
            self.network = self.controller.get_resource_by_extid(ext_obj['network_id'])
        except:
            pass
    
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used 
        in container resource_factory method.

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
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.tenant: id or uuid of the tenant
        :param kvargs.network: id or uuid of the network
        :param kvargs.gateway_ip: ip of the gateway
        :param kvargs.cidr: network cidr
        :param kvargs.allocation_pools: list of start and end ip of a pool
        :param kvargs.enable_dhcp: [default=True] Set to true if DHCP is enabled and false if DHCP is disabled.
        :param kvargs.dns_nameservers: [default=['8.8.8.7', '8.8.8.8'] A list of DNS name servers for the subnet. 
            Specify each name server as an IP  address and separate multiple entries with a space.
        :param kvargs.ervice_types: The service types associated with the subnet. Ex. ['compute:nova'], ['compute:foo']
        :param kvargs.host_routes:  A list of host route dictionaries for the subnet.
            Ex. [{"destination":"0.0.0.0/0", "nexthop":"123.45.67.89" }, .. ]            
        :return: kvargs
        :raise ApiManagerError:
        """
        project = kvargs.pop('project')
        network = kvargs.pop('parent')

        # get parent tenant
        project = controller.get_resource(project)
        
        # get parent network
        network = container.get_resource(network)

        # get service types
        service_types = kvargs.pop('service_types', None)
        if service_types is not None:
            service_types = service_types.split(',')

        data = {
            # 'objid':objid,
            # 'desc':'Network Subnet %s' % kvargs['name'],
            'network_ext_id': network.ext_id,
            'parent': network.oid,
            'project_ext_id': network.ext_id,
            'subnet_ext_id': project.ext_id,
            'service_types': service_types
        }
        kvargs.update(data)
        
        steps = [
            OpenstackSubnet.task_path + 'create_resource_pre_step',
            OpenstackSubnet.task_path + 'subnet_create_physical_step',
            OpenstackSubnet.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """ 
        steps = [
            OpenstackSubnet.task_path + 'update_resource_pre_step',
            OpenstackSubnet.task_path + 'subnet_update_physical_step',
            OpenstackSubnet.task_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs
    
    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackSubnet.task_path + 'expunge_resource_pre_step',
            OpenstackSubnet.task_path + 'subnet_expunge_physical_step',
            OpenstackSubnet.task_path + 'expunge_resource_post_step'
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
        # verify permissions
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            # get network
            network = self.network.small_info()      
            
            data = {}
            data['cidr'] = self.ext_obj.get('cidr', None)
            data['ip_version'] = self.ext_obj.get('ip_version', None)
            data['status'] = self.ext_obj.get('status', None)
            data['gateway_ip'] = self.ext_obj.get('gateway_ip', None)
            allocation_pools = ['%s-%s' % (a['start'], a['end'])
                                for a in self.ext_obj.get('allocation_pools', [])]
            data['allocation_pools'] = allocation_pools
            data['network'] = network
            data['enable_dhcp'] = self.ext_obj.get('enable_dhcp', None)
            data['subnet_types'] = self.ext_obj.get('service_types', None)
            
            try:
                data['project'] = self.project.small_info()
            except:
                data['project'] = None
            
            info['details'].update(data)
            
        return info
    
    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.detail(self)
        
        from .ops_security_group import OpenstackSecurityGroup
        
        if self.ext_obj is not None:
            # get network
            network = self.network.small_info()
            
            data = {}
            data['date'] = {'created': self.ext_obj.get('created_at', None),
                             'updated': self.ext_obj.get('updated_at', None)}
            data['gateway_ip'] = self.ext_obj.get('gateway_ip', None)
            data['ip_version'] = self.ext_obj.get('ip_version', None)
            data['cidr'] = self.ext_obj.get('cidr', None)
            data['dns_nameservers'] = self.ext_obj.get('dns_nameservers', None)
            data['status'] = self.ext_obj.get('status', None)
            data['network'] = network
            allocation_pools = ['%s-%s' % (a['start'], a['end'])
                                for a in self.ext_obj.get('allocation_pools', [])]
            data['allocation_pools'] = allocation_pools
            data['host_routes'] = self.ext_obj.get('host_routes', None)
            data['enable_dhcp'] = self.ext_obj.get('enable_dhcp', None)
            data['ipv6_ra_mode'] = self.ext_obj.get('ipv6_ra_mode', None)
            data['ipv6_address_mode'] = self.ext_obj.get('ipv6_address_mode', None)
            data['subnet_types'] = self.ext_obj.get('service_types', None)
            
            try:
                data['project'] = self.project.small_info()
            except:
                data['project'] = None            
            
            info['details'].update(data)

        return info

    def get_cidr(self):
        if self.ext_obj is not None:
            return self.ext_obj.get('cidr', None)
        else:
            return None

    def get_gateway(self):
        if self.ext_obj is not None:
            return self.ext_obj.get('gateway_ip', None)
        else:
            return None

    def get_allocation_pool(self):
        if self.ext_obj is not None:
            return self.ext_obj.get('allocation_pools', None)
        else:
            return None
