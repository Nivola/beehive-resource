# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import truncate, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import NsxResource
from beecell.db import QueryError
from beehive.common.data import trace
from networkx.classes.digraph import DiGraph
from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfw
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet
from beehive_resource.plugins.vsphere.entity.nsx_dlr import NsxDlr
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer


class NsxManager(NsxResource):
    objdef = 'Vsphere.Nsx'
    objuri = 'nsxs'
    objname = 'nsx'
    objdesc = 'Vsphere nsx manager'
    
    default_tags = ['vsphere', 'network']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.nsx_manager.NsxManager.'
    
    def __init__(self, *args, **kvargs):
        """ """
        NsxResource.__init__(self, *args, **kvargs)
        
        # child classes
        self.child_classes = [
            NsxDfw,
            NsxLogicalSwitch,
            NsxSecurityGroup,
            NsxIpSet,
            NsxDlr,
            NsxEdge        
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
        items = []
        
        nsx_manager = container.conn.system.nsx.summary_info()
        items.append((nsx_manager['hostName'], nsx_manager['applianceName'], None, None))
        
        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = NsxManager
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
        nsx_manager = container.conn.system.nsx.summary_info()
        items = [{
            'id':nsx_manager['hostName'],
            'name':nsx_manager['applianceName'],
        }]  
        
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
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]
        
        objid = '%s//%s' % (container.objid, id_gen())
        
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
        for entity in entities:
            entity.set_physical_entity('nsx')
        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:            
        :raises ApiManagerError:
        """
        self.set_physical_entity('nsx')

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
        if self.ext_obj is not None and self.container is not None:
            entities = self.container.conn.system.nsx.global_info()
            info['details'] = entities

        return info

    def detail(self):
        """Get details.
        
        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = NsxResource.detail(self)
        details = info['details']
        if self.container is not None:
            data = self.container.conn.system.nsx.summary_info()
            details.update(data)
        
        try:
            ipaddress = data['ipv4Address']
            server = self.container.get_servers(ipaddress=ipaddress)[0]
            details['server'] = server.small_info()
        except Exception as ex:
            self.logger.warning(ex)
        
        return info
    
    #
    # transport zones
    #
    @trace(op='use')
    def get_transport_zones(self):
        """Get transport zones.
        
        :return: List of instance
        :rtype: list
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.verify_permisssions('use')
        
        try:
            res = []
            
            # get child servers from vsphere
            items = self.container.conn.network.nsx.list_transport_zones()
            if isinstance(items, dict):
                items = [items]
            
            for item in items:
                oid = item.pop('objectId')
                obj = {'id': oid,
                       'ext_id': oid,
                       'name': item.pop('name')}
                
                clusters = item.pop('clusters')['cluster']
                obj['clusters'] = []
                if isinstance(clusters, list):
                    for cluster in clusters:
                        obj['clusters'].append(cluster['cluster'])
                else:
                    obj['clusters'].append(clusters['cluster'])
                    
                obj['details'] = item
                
                res.append(obj)
                    
            self.logger.debug('Get nsx %s transport zones: %s' % (self.name, truncate(items)))
            return res
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []

    #
    # components
    #
    @trace(op='use')
    def get_manager_components(self):
        """Get nsx manager components.
        
        :return: List of components
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.verify_permisssions('use')        
        
        try:
            res = []
            items = self.container.conn.system.nsx.query_appliance_components()
            for item in items:
                res.append(item)
            self.logger.debug('Get nsx manager %s components: %s' % (self.name, truncate(items)))
            return res
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []

    #
    # audits and events
    #
    @trace(op='use')
    def get_system_events(self, start_index=0, page_size=10):
        """Get nsx manager events.
        
        :param start_index: start index is an optional parameter which specifies the starting point for retrieving the 
            logs. If this parameter is not specified, logs are retrieved from the beginning.
        :param page_size: page size is an optional parameter that limits the maximum number of entries returned by the 
            API. The default value for this parameter is 256 and the valid range is 1-1024.        
        :return: List of events
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.verify_permisssions('use')        
        
        try:
            items = self.container.conn.system.nsx.get_system_events(start_index, page_size)
            self.logger.debug('Get nsx manager %s events: %s' % (self.name, truncate(items)))
            return items
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []
    
    @trace(op='use')
    def get_system_audit_logs(self, start_index=0, page_size=10):
        """Get nsx manager audit logs.
        
        :param start_index: start index is an optional parameter which specifies the starting point for retrieving the
            logs. If this parameter is not specified, logs are retrieved from the beginning.
        :param page_size: page size is an optional parameter that limits the maximum number of entries returned by the
            API. The default value for this parameter is 256 and the valid range is 1-1024.
        :return: List of audit logs
        :rtype: list
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.verify_permisssions('use')        
        
        try:
            items = self.container.conn.system.nsx.get_system_audit_logs(start_index, page_size)
            self.logger.debug('Get nsx manager %s audit logs: %s' % (self.name, truncate(items)))
            return items
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []
        
    #
    # controllers
    #
    @trace(op='use')
    def get_controllers(self):
        """Retrieves details and runtime status for controller. untime status can be one of the following:
        
        - Deploying: controller is being deployed and the procedure has not completed yet.
        - Removing: controller is being removed and the procedure has not completed yet.
        - Running: controller has been deployed and can respond to API invocation.
        - Unknown: controller has been deployed but fails to respond to API invocation.
           
        :return: List of controllers
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.verify_permisssions('use')        
        
        try:
            res = []
            
            items = self.container.conn.system.nsx.list_controllers()
            for item in items:
                ext_id = item['virtualMachineInfo']['objectId']
                try:
                    server = self.controller.get_resources(ext_id=ext_id, objdef=VsphereServer.objdef, details=False)[0]
                    item['virtualMachineInfo']['id'] = server.oid
                    item['virtualMachineInfo']['uri'] = server.objuri
                except: pass
                res.append(item)
                    
            self.logger.debug('Get nsx manager %s controllers: %s' % (self.name, truncate(items)))
            return res
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []

    #
    # security group custom function
    #
    @trace(op='use')
    def get_security_groups_graph(self, oid=None, ext_id=None):
        """Get security groups graph
        
        :param oid: unique id  [optional]
        :param ext_id: id [optional]
        :return: List of instance
        :rtype: list
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.controller.check_authorization(NsxSecurityGroup.objtype, NsxSecurityGroup.objdef, self.objid+'//*', 'view')
        
        try:  
            try:
                if oid is not None:
                    # get resources
                    resource = self.container.get_resource(oid)                
                    morid = resource.ext_id
                    items = [self.container.conn.network.nsx.sg.get(morid)]
                if ext_id is not None:
                    items = [self.container.conn.network.nsx.sg.get(ext_id)]
                else:
                    items = self.container.conn.network.nsx.sg.list()
                    # get resources
                    resources, total = self.container.get_resources(
                        type=NsxSecurityGroup.objdef)
            except:
                self.logger.warninging('No security groups found')         
                return [] 

            # index resources
            res_index = {}
            for i in resources:
                res_index[i.ext_id] = i

            for item in items:
                # bypass non registered resources
                try:
                    res_index[item['objectId']].ext_obj = item
                except:
                    pass
            
            objs = res_index.values()
            graph = DiGraph(name=self.name+'-graph')
            edges = []
            for obj in objs:
                # add graph node
                graph.add_node(obj.oid, 
                               id=obj.oid,
                               name=obj.name,
                               label=obj.desc, 
                               type=obj.objdef,
                               uri=obj.objuri,
                               container=obj.container.oid,
                               attributes='')
                                
                members = obj.ext_obj.pop('member', [])
                if isinstance(members, list) is False:
                    members = [members]
                for member in members:
                    try:
                        child = self.container.get_resources(ext_id=member['objectId'])[0]
                        # add graph node
                        graph.add_node(child.oid, 
                                       id=child.oid,
                                       name=child.name,  
                                       label=child.desc,
                                       type=child.objdef,
                                       uri=child.objuri,
                                       container=child.container.oid,
                                       attributes='')
                        # add graph link
                        edges.append((obj.oid, child.oid))
                    except:
                        pass
            
            # add all links
            graph.add_edges_from(edges)
            res = graph

            self.logger.debug('Get security groups graph: %s' % truncate(res))    
            return res
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []
    
    @trace(op='use')
    def get_security_groups_tree(self, oid=None, ext_id=None):
        """Get security groups tree
        
        :param oid: unique id  [optional]
        :param ext_id: id [optional]
        :return: List of instance
        :rtype: list
        :raises ApiManagerError if query empty return error.
        """
        # check authorization
        self.controller.check_authorization(NsxSecurityGroup.objtype, NsxSecurityGroup.objdef, self.objid+'//*', 'view')
        
        try:  
            try:
                if oid is not None:
                    # get resources
                    resource = self.container.get_resource(oid)                
                    morid = resource.ext_id
                    items = [self.container.conn.network.nsx.sg.get(morid)]
                if ext_id is not None:
                    items = [self.container.conn.network.nsx.sg.get(ext_id)]
                else:
                    items = self.container.conn.network.nsx.sg.list()
                    # get resources
                    resources, total = self.container.get_resources(type=NsxSecurityGroup.objdef)
            except:
                self.logger.warninging('No security groups found')         
                return [] 

            # index resources
            res_index = {}
            for i in resources:
                res_index[i.ext_id] = i

            for item in items:
                # bypass non registered resources
                try:
                    res_index[item['objectId']].ext_obj = item
                except:
                    pass
            
            objs = res_index.values()
            graph = DiGraph(name=self.name+'-tree')
            
            # add tree root node
            graph.add_node(0, 
                           id=0,
                           name='root',
                           label='root', 
                           type='',
                           uri='',
                           size=1,
                           container='',
                           attributes='')
            
            edges = {}
            for obj in objs:
                # add graph node
                graph.add_node(obj.oid, 
                               id=obj.oid,
                               name=obj.name,
                               label=obj.desc, 
                               type=obj.objdef,
                               uri=obj.objuri,
                               size=1,
                               container=obj.container.oid,
                               attributes='')
                
                # add link to root node
                edges[obj.oid] = (0, obj.oid)
            
            for obj in objs:
                members = obj.ext_obj.pop('member', [])
                if isinstance(members, list) is False:
                    members = [members]
                for member in members:
                    try:
                        child = self.container.get_resources(ext_id=member['objectId'])[0]
                        # add graph node
                        graph.add_node(child.oid, 
                                       id=child.oid,
                                       name=child.name,  
                                       label=child.desc,
                                       type=child.objdef,
                                       uri=child.objuri,
                                       container=child.container.oid,
                                       size=1,
                                       attributes='')
                        
                        # remove link to root node - this is a level>1 security group
                        if child.objdef == 'vsphere.nsx.security_group':
                            edges.pop(child.oid, None)             
                        
                        # add graph link
                        edges[child.oid] = (obj.oid, child.oid)
                    except:
                        pass
            
            # add all links
            graph.add_edges_from(edges.values())
            res = graph

            self.logger.debug('Get security groups tree: %s' % truncate(res))    
            return res
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return []    

    #
    # ip pools
    #
    def get_ippools(self, pool_id=None, pool_range=None):
        """Get a list of ippools

        :param pool_id: id of a pool [optional]
        :param pool_range: tupla with start_ip and end_ip [optional]
        """
        res = self.container.conn.network.nsx.ippool.list(pool_id=pool_id, pool_range=pool_range)
        self.logger.debug('Get ippools: %s' % truncate(res))

        return res

    def add_ippool(self, name, prefix=None, gateway=None, dnssuffix=None, dns1=None, dns2=None, startip=None,
                  stopip=None):
        """Add an ippool

        :param name: pool name
        :param prefix: pool prefix. Ex. /24
        :param gateway: pool gateway. Ex. 10.102.34.1
        :param dnssuffix: pool dns suffix. Ex. localdomain.local
        :param dns1: pool dns1 ip address
        :param dns2: pool dns2 ip address
        :param startip: start pool ip address
        :param stopip: end pool ip address
        :return: ippool id
        """
        res = self.container.conn.network.nsx.ippool.create(name, prefix=prefix, gateway=gateway, dnssuffix=dnssuffix,
                                                            dns1=dns1, dns2=dns2, startip=startip, stopip=stopip)
        self.logger.debug('Add ippool: %s' % res)
        return res

    def del_ippool(self, pool_id):
        """Delete an ippool

        :param pool_id: id of a pool
        :return:
        """
        pool = self.container.conn.network.nsx.ippool.get(pool_id)
        if int(pool.get('usedAddressCount')) > 0:
            raise ApiManagerError('Ippool %s has ip address allocated. It can not be deleted' % pool_id)

        try:
            self.container.conn.network.nsx.ippool.delete(pool_id)
            self.logger.debug('Delete ippool: %s' % pool_id)
            return pool_id
        except:
            raise ApiManagerError('Ippool %s does not exists' % pool_id)
