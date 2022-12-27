# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task


class OpenstackNetwork(OpenstackResource):
    objdef = 'Openstack.Domain.Project.Network'
    objuri = 'networks'
    objname = 'network'
    objdesc = 'Openstack networks'
    
    default_tags = ['openstack', 'network']
    task_path = 'beehive_resource.plugins.openstack.task_v2.ops_network.NetworkTask.'
    
    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = [
            OpenstackSubnet,
            OpenstackPort    
        ]
        
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
            items = container.conn.network.get(oid=ext_id)
        else:
            items = container.conn.network.list()

        # add new item to final list
        res = []
        for item in items:
            if item['id'] not in res_ext_ids:
                level = None        
                name = item['name']
                parent_id = item['tenant_id']
                if str(parent_id) == '':
                    parent_id = None
                    
                res.append((OpenstackNetwork, item['id'], parent_id, OpenstackNetwork.objdef, name, level))
        
        return res    
    
    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        return container.conn.network.list()
    
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
            objid = '%s//none//none//%s' % (container.objid, id_gen())
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

        :param kvargs.segmentation_id: An isolated segment on the physical 
                    network. The network_type attribute defines the segmentation 
                    model. For example, if the network_type value is vlan, this 
                    ID is a vlan identifier. If the network_type value is gre, 
                    this ID is a gre key. [optional]
        :param kvargs.network_type: The type of physical network that maps to 
                    this network resource. For example, flat, vlan, vxlan,  or 
                    gre. [optional]
        :param kvargs.external: Indicates whether this network can provide 
                    floating IPs via a router. [optional]
        :param kvargs.shared: Indicates whether this network is shared 
                    across all projects. [optional]
        :param kvargs.physical_network: The physical network where this network 
                    object is implemented. The Networking API v2.0 does not 
                    provide a way to list available physical networks. For 
                    example, the Open vSwitch plug-in configuration file defines 
                    a symbolic name that maps to specific bridges on each 
                    Compute host.                          
        :return: list of ext_id            
        :raise ApiManagerError:
        """
        # get container
        container = controller.get_container(container_id)
        
        tenant = None
        limit = kvargs.get('limit', None)
        marker = kvargs.get('marker', None)
        shared = kvargs.get('shared', None)
        segmentation_id = kvargs.get('segmentation_id', None)
        network_type = kvargs.get('network_type', None)
        external = kvargs.get('external', None)
        physical_network = kvargs.get('physical_network', None)
        remote_entities = container.conn.network.list(
            tenant=tenant, limit=limit, marker=marker, shared=shared,
            segmentation_id=segmentation_id, network_type=network_type, 
            external=external, physical_network=physical_network)
        
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
        :param kvargs.tenant: tenant id [optional]
        :param kvargs.limit:  Requests a page size of items. Returns a number of items 
                       up to a limit value. Use the limit parameter to make an 
                       initial limited request and use the ID of the last-seen 
                       item from the response as the marker parameter value in 
                       a subsequent limited request. [optional]
        :param kvargs.marker: The ID of the last-seen item. Use the limit parameter 
                       to make an initial limited request and use the ID of the 
                       last-seen item from the response as the marker parameter 
                       value in a subsequent limited request. [optional]
        :param kvargs.segmentation_id: An isolated segment on the physical network. 
                                The network_type attribute defines the 
                                segmentation model. For example, if the 
                                network_type value is vlan, this ID is a vlan 
                                identifier. If the network_type value is gre, 
                                this ID is a gre key. [optional]
        :param kvargs.network_type: The type of physical network that maps to this 
                             network resource. For example, flat, vlan, vxlan, 
                             or gre. [optional]
        :param kvargs.external: Indicates whether this network can provide floating IPs 
                         via a router. [optional]
        :param kvargs.shared: Indicates whether this network is shared 
                       across all projects. [optional]
        :param kvargs.physical_network: The physical network where this network object 
                                 is implemented. The Networking API v2.0 does 
                                 not provide a way to list available physical 
                                 networks. For example, the Open vSwitch plug-in 
                                 configuration file defines a symbolic name 
                                 that maps to specific bridges on each Compute host.
        :return: None
        :raise ApiManagerError:
        """
        tenant = None
        limit = kvargs.get('limit', None)
        marker = kvargs.get('marker', None)
        shared = kvargs.get('shared', None)
        segmentation_id = kvargs.get('segmentation_id', None)
        network_type = kvargs.get('network_type', None)
        external = kvargs.get('external', None)
        physical_network = kvargs.get('physical_network', None)
        remote_entities = container.conn.network.list(
            tenant=tenant, limit=limit, marker=marker, shared=shared,
            segmentation_id=segmentation_id, network_type=network_type, 
            external=external, physical_network=physical_network)
        
        # create index of remote objs
        remote_entities_index = {i['id']: i for i in remote_entities}
        
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn('', exc_info=1)
        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.
        
        :return:            
        :raise ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.network.get(oid=self.ext_id)
            self.set_physical_entity(ext_obj)
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
        :param kvargs.shared: Indicates whether this network is shared across 
                    all tenants. By default, only administrative users can 
                    change this value
        :param kvargs.external: Indicates whether this network is externally 
                    accessible
        :param kvargs.parent: The id or uuid of the tenant that owns the network')
        :param kvargs.qos_policy_id: The openstack UUID of the QoS policy 
                    associated with this network. The policy will need to have 
                    been created before the network to associate it with
        :param kvargs.segments: A list of provider segment objects
        :param kvargs.physical_network: [optional] The physical network where 
                    this network object is implemented. The Networking API v2.0 
                    does not provide a way to list available physical networks. 
                    For example, the Open vSwitch plug-in configuration file 
                    defines a symbolic name that maps to specific bridges on 
                    each Compute host
        :param kvargs.network_type: [default=vlan] The type of physical 
                    network that maps to this network resource. For example, 
                    flat, vlan, vxlan, or gre
        :param kvargs.segmentation_id: [optional] An isolated segment on the 
                    physical network. The network_type attribute defines the 
                    segmentation model. For example, if the network_type value 
                    is vlan, this ID is a vlan identifier. If the network_type 
                    value is gre, this ID is a gre key            
        :return: kvargs            
        :raise ApiManagerError:
        """
        parent = kvargs['parent']
        
        # get parent project
        project = controller.get_resource(parent)
        
        # set additional params
        params = {
            'parent_ext_id': project.ext_id,
            'desc': 'Network %s' % kvargs['name'],
        }
        kvargs.update(params)        
        
        steps = [
            OpenstackNetwork.task_path + 'create_resource_pre_step',
            OpenstackNetwork.task_path + 'network_create_physical_step',
            OpenstackNetwork.task_path + 'create_resource_post_step'
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
            OpenstackNetwork.task_path + 'update_resource_pre_step',
            OpenstackNetwork.task_path + 'network_update_physical_step',
            OpenstackNetwork.task_path + 'update_resource_post_step'
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
            OpenstackNetwork.task_path + 'expunge_resource_pre_step',
            OpenstackNetwork.task_path + 'network_delete_physical_step',
            OpenstackNetwork.task_path + 'expunge_resource_post_step'
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
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data['provider_network_type'] = self.ext_obj.get('provider:network_type', None)
            data['shared'] = self.ext_obj.get('shared', None)
            data['external'] = self.ext_obj.get('router:external', None)
            data['status'] = self.ext_obj.get('status', None)
            data['segmentation_id'] = self.ext_obj.get('provider:segmentation_id', None)
            info['details'].update(data)
            
        return info
    
    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OpenstackResource.detail(self)
        
        if self.ext_obj is not None:
            # get allocated ports
            ports, total = self.controller.get_resources(parent=self.oid, type=OpenstackPort.objdef, details=False)
            
            data = {}
            data['provider_network_type'] = self.ext_obj.get('provider:network_type', None)
            data['physical_network'] = self.ext_obj.get('provider:physical_network', None)
            data['segmentation_id'] = self.ext_obj.get('provider:segmentation_id', None)
            data['shared'] = self.ext_obj.get('shared', None)
            data['external'] = self.ext_obj.get('router:external', None)
            data['status'] = self.ext_obj.get('status', None)
            data['mt'] = self.ext_obj.get('mt', None)
            data['port_security_enabled'] = self.ext_obj.get('port_security_enabled', None)
            data['physical_network'] = self.ext_obj.get('provider:physical_network', None)            
            data['ports_allocated'] = total            
            info['details'].update(data)

        return info

    def get_vlan(self):
        vlan = None
        if self.ext_obj is not None:
            vlan = self.ext_obj.get('provider:segmentation_id', None)
        return vlan

    def get_private_subnet_entity(self):
        """Get subnet for private network

        :return:
        :raise ApiManagerError:
        """
        private_subnet = None
        subnet = self.get_attribs(key='subnet')
        if subnet is not None:
            private_subnet = self.container.get_resource(subnet)
        return private_subnet

    def get_private_subnet(self):
        """Get subnet cidr for private network

        :return:
        :raise ApiManagerError:
        """
        cidr = None
        subnet = self.get_attribs(key='subnet')
        if subnet is not None:
            private_subnet = self.container.get_resource(subnet)
            cidr = private_subnet.get_cidr()
        return cidr

    def get_gateway(self):
        """Get subnet for private network

        :return:
        :raise ApiManagerError:
        """
        gateway = None
        subnet = self.get_attribs(key='subnet')
        if subnet is not None:
            private_subnet = self.container.get_resource(subnet)
            gateway = private_subnet.get_gateway()
        return gateway

    def get_allocation_pool(self):
        """Get allocable pool for private network

        :return:
        :raise ApiManagerError:
        """
        pool = None
        subnet = self.get_attribs(key='subnet')
        if subnet is not None:
            private_subnet = self.container.get_resource(subnet)
            pool = private_subnet.get_allocation_pool()
        return pool
