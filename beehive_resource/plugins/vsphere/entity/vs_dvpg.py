# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.vsphere.entity import VsphereResource


class VsphereDvpg(VsphereResource):
    objdef = 'Vsphere.DataCenter.Folder.Dvpg'
    objuri = 'dvpgs'
    objname = 'dvpg'
    objdesc = 'Vsphere dvpgs'
    
    default_tags = ['vsphere', 'network']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.vs_dvpg.DvpgTask.'
    
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
        from .vs_folder import VsphereFolder
        from .vs_datacenter import VsphereDatacenter
        
        items = []

        def append_node(node, parent, parent_class):
            obj_type = type(node).__name__
            if obj_type == 'vim.Folder':
                # get childs
                if hasattr(node, 'childEntity'):
                    childs = node.childEntity
                    for c in childs:
                        append_node(c, node._moId, VsphereFolder)
                        
            if obj_type == 'vim.dvs.VmwareDistributedVirtualSwitch':
                for portgroup in node.portgroup:
                    items.append((portgroup._moId, portgroup.name, parent, parent_class))
        
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity        
        for datacenter in datacenters:
            append_node(datacenter.networkFolder, datacenter._moId, VsphereDatacenter)
        
        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereDvpg
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
        
        def append_node(node):
            obj_type = type(node).__name__
            if obj_type == 'vim.Folder':
                # get childs
                if hasattr(node, 'childEntity'):
                    childs = node.childEntity
                    for c in childs:
                        append_node(c)
                        
            if obj_type == 'vim.dvs.VmwareDistributedVirtualSwitch':
                for portgroup in node.portgroup:
                    items.append({
                        'id': portgroup._moId,
                        'name': portgroup.name,
                    })
        
        for datacenter in datacenters:
            append_node(datacenter.networkFolder)
        
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
        from .vs_folder import VsphereFolder
        
        resclass  = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]
        
        parent = container.get_resource_by_extid(parent_id)
        parent_id = parent.oid
        
        # get parent folder
        if parent_class == VsphereFolder:
            objid = '%s//%s' % (parent.objid, id_gen())
        # get parent datacenter
        else:
            objid = '%s//none//%s' % (parent.objid, id_gen()) 
        
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
        remote_entities = container.conn.network.list_networks()
        
        # create index of remote objs
        remote_entities_index = {i['obj']._moId:i for i in remote_entities}      
        
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
            ext_obj = self.container.conn.network.get_network(self.ext_id)
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
        :param kvargs.physical_network: dvs id, uuid or name
        :param kvargs.network_type: only vlan is supported
        :param kvargs.segmentation_id: An isolated segment on he physical network. 
            The network_type attribute defines the segmentation model. 
            For example, if the network_type value is vlan, this ID is a 
            vlan identifier. If the network_type value is gre, this ID is a gre key.
        :param kvargs.numports: port group intial ports number       
        :return: kvargs            
        :raises ApiManagerError:
        """
        dvs = kvargs.pop('physical_network', None)
        
        # check dvs
        from beehive_resource.plugins.vsphere.entity.vs_dvs import VsphereDvs
        dvs = container.get_resource(dvs, entity_class=VsphereDvs)
        
        # get parent folder
        folder = container.get_resource(dvs.parent_id)
        
        kvargs.update({
            'objid': '%s//%s' % (folder.objid, id_gen()),
            'parent': folder.oid,
            'desc': 'Dvpg %s' % kvargs['name'],
            'dvs_ext_id': dvs.ext_id
        })

        steps = [
            VsphereDvpg.task_path + 'create_resource_pre_step',
            VsphereDvpg.task_path + 'dvpg_create_physical_step',
            VsphereDvpg.task_path + 'create_resource_post_step'
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
            VsphereDvpg.task_path + 'update_resource_pre_step',
            VsphereDvpg.task_path + 'dvpg_update_physical_step',
            VsphereDvpg.task_path + 'update_resource_post_step'
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
            VsphereDvpg.task_path + 'expunge_resource_pre_step',
            VsphereDvpg.task_path + 'dvpg_delete_physical_step',
            VsphereDvpg.task_path + 'expunge_resource_post_step'
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
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = VsphereResource.detail(self)
        if self.ext_obj is not None:
            details = info['details']
            data = self.container.conn.network.detail_network(self.ext_obj)
            data['dvs'] = self.container.get_resource_by_extid(data['dvs']).small_info()
            details.update(data)
        return info

    def get_parent_dvs(self):
        """Get parent distributed virtual switch

        :return: parent dvs
        """
        ext_obj = self.container.conn.network.get_network(self.ext_id)
        data = self.container.conn.network.detail_network(ext_obj)
        dvs = self.container.get_resource_by_extid(data['dvs'])
        return dvs
