# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger
from beecell.simple import truncate, get_value, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive.common.data import trace
from beehive_resource.plugins.vsphere.entity import get_task


class VsphereResourcePool(VsphereResource):
    objdef = 'Vsphere.DataCenter.Cluster.ResourcePool'
    objuri = 'resource_pools'
    objname = 'resource_pool'
    objdesc = 'Vsphere resource_pools'
    
    default_tags = ['vsphere']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.vs_resource_pool.ResourcePoolTask.'
    
    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)
        
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
        from .vs_cluster import VsphereCluster
        
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []
        for datacenter in datacenters:
            for node in datacenter.hostFolder.childEntity:
                obj_type = type(node).__name__
                if obj_type == 'vim.ClusterComputeResource':
                    rs = node.resourcePool
                    items.append((rs._moId, node.name+'ResourcePool', node._moId, VsphereCluster))
                    if len(node.resourcePool.resourcePool) > 0:     
                        for rs in node.resourcePool.resourcePool:                                
                            items.append((rs._moId, rs.name, rs.parent._moId, VsphereResourcePool))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereResourcePool
                res.append((resclass, item[0], parent_id, resclass.objdef, item[1], parent_class))
        
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []
               
        for datacenter in datacenters:
            for node in datacenter.hostFolder.childEntity:
                obj_type = type(node).__name__
                if obj_type == 'vim.ClusterComputeResource':
                    rs = node.resourcePool
                    items.append({
                        'id': rs._moId,
                        'name': rs.name,
                    })           
                    if len(node.resourcePool.resourcePool) > 0:      
                        for rs in node.resourcePool.resourcePool:
                            items.append({
                                'id': rs._moId,
                                'name': rs.name,
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
        from .vs_cluster import VsphereCluster
        
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]
        
        parent = container.get_resource_by_extid(parent_id)
        parent_id = parent.oid

        if parent_class == VsphereCluster:
            objid = '%s//%s' % (parent.objid, id_gen())
        # get parent datacenter
        else:
            objid = '%s.%s' % (parent.objid, id_gen())
        
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
        remote_entities = container.conn.cluster.resource_pool.list()
        
        # create index of remote objs
        remote_entities_index = {i['obj']._moId: i for i in remote_entities}      
        
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
        :raises ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.cluster.resource_pool.get(self.ext_id)
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
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.cluster: cluster id or uuid
        :param kvargs.cpu: cpu limit in MHz
        :param kvargs.memory: memory limit in MB
        :param kvargs.shares: 
            high
              For CPU: Shares = 2000 * number of virtual CPUs
              For Memory: Shares = 20 * virtual machine memory size in megabytes
              For Disk: Shares = 2000
              For Network: Shares = networkResourcePoolHighShareValue 
            low    
              For CPU: Shares = 500 * number of virtual CPUs
              For Memory: Shares = 5 * virtual machine memory size in megabytes
              For Disk: Shares = 500
              For Network: Shares = 0.25 * networkResourcePoolHighShareValue 
            normal    
              For CPU: Shares = 1000 * number of virtual CPUs
              For Memory: Shares = 10 * virtual machine memory size in megabytes
              For Disk: Shares = 1000
              For Network: Shares = 0.5 * networkResourcePoolHighShareValue    
            [default=normal]
        :return: kvargs            
        :raises ApiManagerError:
        """
        cluster = kvargs.pop('parent', None)
        
        # check cluster
        from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster
        cluster = container.get_resource(cluster, entity_class=VsphereCluster)
        
        kvargs.update({
            'objid': '%s//%s' % (cluster.objid, id_gen()),
            'parent': cluster.oid,
            'desc': 'Resource Pool %s' % kvargs['name'],
            'cluster_ext_id': cluster.ext_id
        })
        
        steps = [
            VsphereResourcePool.task_path + 'create_resource_pre_step',
            VsphereResourcePool.task_path + 'resource_pool_create_physical_step',
            VsphereResourcePool.task_path + 'create_resource_post_step'
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
            VsphereResourcePool.task_path + 'update_resource_pre_step',
            VsphereResourcePool.task_path + 'resource_pool_update_physical_step',
            VsphereResourcePool.task_path + 'update_resource_post_step'
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
            VsphereResourcePool.task_path + 'expunge_resource_pre_step',
            VsphereResourcePool.task_path + 'resource_pool_delete_physical_step',
            VsphereResourcePool.task_path + 'expunge_resource_post_step'
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
        info = VsphereResource.info(self)

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.

            details: {
                "config": {
                    "cpu_allocation": {
                        "expandableReservation": True, 
                        "limit": 62934, 
                        "reservation": 62934, 
                        "shares": {"level": "normal", "shares": 4000}
                    },
                    "memory_allocation": {
                        "expandableReservation": True, 
                        "limit": 132860, 
                        "reservation": 132860, 
                        "shares": {"level": "normal", "shares": 163840}
                    },
                    "version": None
                },
                "date": {"modified": None},
                "overall_status": "green"
            }
        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = VsphereResource.detail(self)
        if self.ext_obj is not None:
            details = info['details']
            data = self.container.conn.cluster.resource_pool.detail(self.ext_obj)
            details.update(data)
        
        return info
    
    #
    # custom info
    #
    @trace(op='use')
    def get_runtime(self):
        """Get runtime.
        
        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        
          {"cp": {"dynamicProperty": [],
                    "dynamicType": None,
                    "maxUsage": 62934,
                    "overallUsage": 1235,
                    "reservationUsed": 0,
                    "reservationUsedForVm": 0,
                    "unreservedForPool": 62934,
                    "unreservedForVm": 62934},
           "dynamicProperty": [],
           "dynamicType": None,
           "memory": {"dynamicProperty": [],
                       "dynamicType": None,
                       "maxUsage": 139314855936L,
                       "overallUsage": 41266708480L,
                       "reservationUsed": 24240979968L,
                       "reservationUsedForVm": 24240979968L,
                       "unreservedForPool": 115073875968L,
                       "unreservedForVm": 115073875968L},
           "overallStatus": "green"}        
        """
        self.verify_permisssions('use')
        
        try:
            data = {}
            if self.ext_obj is not None:
                data = self.container.conn.cluster.resource_pool.runtime(self.ext_obj)
            
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)

    @trace(op='use')
    def get_usage(self):
        """Get usage.
        
        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        
          {"balloonedMemory": 0,
           "compressedMemory": 0,
           "consumedOverheadMemory": 319,
           "distributedCpuEntitlement": 1649,
           "distributedMemoryEntitlement": 14829,
           "dynamicProperty": [],
           "dynamicType": None,
           "guestMemoryUsage": 4624,
           "hostMemoryUsage": 39355,
           "overallCpuDemand": 1831,
           "overallCpuUsage": 1678,
           "overheadMemory": 497,
           "privateMemory": 39034,
           "sharedMemory": 176,
           "staticCpuEntitlement": 62934,
           "staticMemoryEntitlement": 45646,
           "swappedMemory": 0}        
        """
        self.verify_permisssions('use')
        
        try:
            data = {}
            if self.ext_obj is not None:
                data = self.container.conn.cluster.resource_pool.usage(self.ext_obj)
            
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)   
