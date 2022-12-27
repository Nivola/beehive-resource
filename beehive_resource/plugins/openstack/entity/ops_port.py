# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.plugins.openstack.entity.ops_security_group import OpenstackSecurityGroup
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task


class OpenstackPort(OpenstackResource):
    objdef = 'Openstack.Domain.Project.Network.Port'
    objuri = 'ports'
    objname = 'port'
    objdesc = 'Openstack network ports'
    
    default_tags = ['openstack', 'network']
    task_path = 'beehive_resource.plugins.openstack.task_v2.ops_port.PortTask.'
    
    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.network = None
        self.project = None
        self.device = None

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
            items = container.conn.network.port.get(oid=ext_id)
        else:
            items = container.conn.network.port.list()

        # add new item to final list
        res = []
        for item in items:
            if item['id'] not in res_ext_ids:
                level = None
                name = item['name']
                parent_id = item['network_id']
                if str(parent_id) == '':
                    parent_id = None
                    
                res.append((OpenstackPort, item['id'], parent_id, OpenstackPort.objdef, name, level))
        
        return res    
    
    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        return container.conn.network.port.list()
    
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
        network = kvargs.get('network', None)
        remote_entities = container.conn.network.port.list(network=network)
        
        # create index of related objs
        from ..entity.ops_network import OpenstackNetwork
        from ..entity.ops_project import OpenstackProject
        from ..entity.ops_server import OpenstackServer
        from ..entity.ops_router import OpenstackRouter
        net_index = controller.index_resources_by_extid(OpenstackNetwork)        
        prj_index = controller.index_resources_by_extid(OpenstackProject) 
        server_index = controller.index_resources_by_extid(OpenstackServer) 
        router_index = controller.index_resources_by_extid(OpenstackRouter)    
        
        # create index of remote objs
        remote_entities_index = {i['id']: i for i in remote_entities}
        
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)

                # set network
                entity.network = net_index[ext_obj.get('network_id', None)]

                # set tenant
                if ext_obj['tenant_id'] != '':
                    entity.project = prj_index[ext_obj['tenant_id']]

                # set subnet
                def replace_subnet(item):
                    try:
                        subnet = controller.get_resource_by_extid(item['subnet_id'])
                        item['subnet_id'] = subnet.uuid
                    except:
                        item['subnet_id'] = None
                    return item

                for fixed_ip in ext_obj['fixed_ips']:
                    fixed_ip = replace_subnet(fixed_ip)

                # set device
                try:
                    device_id = ext_obj.get('device_id', None)
                    if device_id is not None:
                        server = server_index.get(device_id, None)
                        router = router_index.get(device_id, None)
                        entity.device = server if server is not None else router
                except:
                    pass
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
            ext_obj = self.get_remote_port(self.controller, self.ext_id, self.container, self.ext_id)
            # ext_obj = self.container.conn.network.port.get(oid=self.ext_id)
            self.set_physical_entity(ext_obj)

            # set subnet
            def replace_subnet(item):
                try:
                    subnet = self.controller.get_resource_by_extid(item['subnet_id'])
                    item['subnet_id'] = subnet.uuid
                except:
                    item['subnet_id'] = None
                return item

            for fixed_ip in ext_obj['fixed_ips']:
                fixed_ip = replace_subnet(fixed_ip)

            self.network = self.controller.get_resource_by_extid(ext_obj['network_id'])
            self.project = self.controller.get_resource_by_extid(ext_obj['tenant_id'])

            # set device
            try:
                device_id = ext_obj.get('device_id', None)
                if device_id is not None:
                    device = self.controller.get_resource_by_extid(device_id)
                    self.device = device
            except:
                pass
        except:
            self.ext_id = None
    
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
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.project: id or uuid of the project
        :param kvargs.ixed_ips: specify the subnet. Ex. 
            without ip: [{"subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2"},..]
            with fixed ip: [{"subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2", ip_address": "10.0.0.2"},..]                                    
        :param kvargs.security_groups: [optional] list of security group id or uuid
        :param kvargs.binding:
        :param kvargs.binding.host_id: [optional] The ID of the host where the port is allocated. In some cases, 
            different implementations can run on different hosts.
        :param kvargs.bindingp.rofile: [optional] A dictionary that enables the application running on the host to 
        pass and receive virtual network interface (VIF) port-specific information to the plug-in.
        :param kvargs.binding.vnic_type: [optional] The virtual network interface card (vNIC) type that is bound to the 
            neutron port. A valid value is normal, direct, or macvtap.
        :param kvargs.device_owner: [optional] The UUID of the entity that uses this port. For example, a DHCP agent.
        :param kvargs.device_id: [optional] The id or uuid of the device that uses this port. For example, a virtual 
            server.
        :return: kvargs            
        :raises ApiManagerError:
        """
        project = kvargs.pop('project')
        network = kvargs.pop('parent')
        security_groups = kvargs.pop('security_groups', [])
        fixed_ips = kvargs.pop('fixed_ips', [])
        device_id = kvargs.pop('device_id', None)
        
        # get parent project
        project = controller.get_resource(project)
        
        # get parent network
        network = container.get_resource(network)
        
        # get security_groups
        sgs = []
        for item in security_groups:
            sgs.append(container.get_resource(item).ext_id)
        
        # get fixed_ips
        for item in fixed_ips:
            subnet = item.get('subnet_id')
            subnet = container.get_resource(subnet)
            item['subnet_id'] = subnet.ext_id
        
        # get device_id
        if device_id is not None:
            device_id = controller.get_resource(device_id).ext_id

        params = {
            'network': network.ext_id,
            'parent': network.oid,
            'project_ext_id': project.ext_id,
            'fixed_ips': fixed_ips,
            'security_groups': sgs,
            'device_id': device_id
        }

        kvargs.update(params)
        
        steps = [
            OpenstackPort.task_path + 'create_resource_pre_step',
            OpenstackPort.task_path + 'port_create_physical_step',
            OpenstackPort.task_path + 'create_resource_post_step'
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
            OpenstackPort.task_path + 'update_resource_pre_step',
            OpenstackPort.task_path + 'port_update_physical_step',
            OpenstackPort.task_path + 'update_resource_post_step'
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
            OpenstackPort.task_path + 'expunge_resource_pre_step',
            OpenstackPort.task_path + 'port_delete_physical_step',
            OpenstackPort.task_path + 'expunge_resource_post_step'
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

        data = {}
        if self.ext_obj is not None:
            data['fixed_ips'] = self.ext_obj.get('fixed_ips', None)
            data['device_owner'] = self.ext_obj.get('device_owner', None)
            data['status'] = self.ext_obj.get('status', None)
            data['mac_address'] = self.ext_obj.get('mac_address', None)
        
            try:
                data['network'] = self.network.small_info()
            except:
                data['network'] = {'name': None}
    
            try:
                data['project'] = self.project.small_info()
            except:
                data['project'] = {'name': None}
                
            try:
                data['device'] = self.device.small_info()
            except:
                data['device'] = {'name': None}
            
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

        data = {}
        if self.ext_obj is not None:
            data['fixed_ips'] = self.ext_obj.get('fixed_ips', None)
            data['device_owner'] = self.ext_obj.get('device_owner', None)
            data['status'] = self.ext_obj.get('status', None)
            data['mac_address'] = self.ext_obj.get('mac_address', None)
            data['date'] = {
                'created': self.ext_obj.get('created_at', None),
                'updated': self.ext_obj.get('updated_at', None)
            }
            data['allowed_address_pairs'] = self.ext_obj.get('allowed_address_pairs', None)
            data['ip_address'] = self.ext_obj.get('ip_address', None)
            data['mac_address'] = self.ext_obj.get('mac_address', None)
            data['status'] = self.ext_obj.get('status', None)
            data['dns_assignment'] = self.ext_obj.get('dns_assignment', None)
            data['dns_name'] = self.ext_obj.get('dns_name', None)
            data['device_owner'] = self.ext_obj.get('device_owner', None)
            data['binding'] = {
                'host_id': self.ext_obj.get('binding:host_id', None),
                'vif_details': self.ext_obj.get('binding:vif_details', None),
                'vif_type': self.ext_obj.get('binding:vif_type', None),
                'profile': self.ext_obj.get('binding:profile', None),
                'vnic_type': self.ext_obj.get('binding:vnic_type', None)
            }
            data['port_security_enabled'] = self.ext_obj.get('port_security_enabled', None),
            data['port_filter'] = self.ext_obj.get('port_filter', None),
            data['ovs_hybrid_plug'] = self.ext_obj.get('ovs_hybrid_plug', None)
                
            try:
                data['network'] = self.network.small_info()
            except:
                data['network'] = None
    
            try:
                data['project'] = self.project.small_info()
            except:
                data['project'] = None
                
            try:
                data['device'] = self.device.small_info()
            except:
                data['device'] = {'name': None}
                
            # get security groups
            sgs, tot = self.controller.get_resources(type=OpenstackSecurityGroup.objdef)
            sg_idx = {s.ext_id: s for s in sgs}
            sglist = []
            try:
                for item in self.ext_obj.get('security_groups', []):
                    sglist.append(sg_idx[item].small_info())
            except:
                pass
            data['security_groups'] = sglist      
            
        info['details'].update(data)

        return info

    def get_main_ip_address(self):
        """"""
        if self.ext_obj is not None:
            fixed_ips = self.ext_obj.get('fixed_ips', None)
            if len(fixed_ips) > 0:
                return fixed_ips[0]['ip_address']
        return None

    @trace(op='update')
    def add_security_group(self, *args, **kvargs):
        """Add security group to port

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(kvargs['security_group'],
                                                                entity_class=OpenstackSecurityGroup)
            # project_ext_id = self.ext_obj.get('project_id')
            kvargs['security_group'] = security_group.ext_id
            # kvargs['project'] = self.controller.get_resource_by_extid(project_ext_id).oid
            return kvargs
            # if self.has_security_group(security_group.oid) is False:
            #     security_group.check_active()
            #     kvargs['security_group'] = security_group.oid
            #     return kvargs
            # else:
            #     raise ApiManagerError('security group %s is already attached to port %s' %
            #                           (security_group.oid, self.oid))

        steps = ['beehive_resource.plugins.openstack.task_v2.ops_port.PortTask.port_add_security_group_step']
        res = self.action('add_security_group', steps, log='Add security group to port', check=check, **kvargs)
        return res

    @trace(op='update')
    def del_security_group(self, *args, **kvargs):
        """Remove security group from port

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(kvargs['security_group'],
                                                                entity_class=OpenstackSecurityGroup)
            # project_ext_id = self.ext_obj.get('project_id')
            kvargs['security_group'] = security_group.ext_id
            # kvargs['project'] = self.controller.get_resource_by_extid(project_ext_id).oid
            return kvargs
            # if self.has_security_group(security_group.oid) is True:
            #     kvargs['security_group'] = security_group.oid
            #     return kvargs
            # else:
            #     raise ApiManagerError('security group %s is not attached to port %s' % (security_group.oid, self.oid))

        steps = ['beehive_resource.plugins.openstack.task_v2.ops_port.PortTask.port_del_security_group_step']
        res = self.action('del_security_group', steps, log='Remove security group from port', check=check, **kvargs)
        return res
