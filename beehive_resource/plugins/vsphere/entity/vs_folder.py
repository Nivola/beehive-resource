# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume


class VsphereFolder(VsphereResource):
    objdef = 'Vsphere.DataCenter.Folder'
    objuri = 'folders'
    objname = 'folder'
    objdesc = 'Vsphere folders'
    
    default_tags = ['vsphere']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.vs_folder.FolderTask.'

    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)
        
        # child classes
        self.child_classes = [
            VsphereServer,
            VsphereVolume
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
        from .vs_datacenter import VsphereDatacenter
        
        items = []

        def append_node(node, parent, parent_class):
            obj_type = type(node).__name__
            if obj_type == 'vim.Folder': 
                items.append((node._moId, node.name, parent, parent_class))
                
                # get childs
                if hasattr(node, 'childEntity'):
                    childs = node.childEntity
                    for c in childs:
                        append_node(c, node._moId, VsphereFolder)
        
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        for datacenter in datacenters:
            append_node(datacenter.vmFolder, datacenter._moId, VsphereDatacenter)
            append_node(datacenter.hostFolder, datacenter._moId, VsphereDatacenter)
            append_node(datacenter.datastoreFolder, datacenter._moId, VsphereDatacenter)
            append_node(datacenter.networkFolder, datacenter._moId, VsphereDatacenter)

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereFolder
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
                items.append({
                    'id':  node._moId,
                    'name':  node.name,
                })
                
                # get childs
                if hasattr(node, 'childEntity'):
                    childs = node.childEntity
                    for c in childs:
                        append_node(c)
        
        for datacenter in datacenters:
            append_node(datacenter.vmFolder)
            append_node(datacenter.hostFolder)
            append_node(datacenter.datastoreFolder)
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
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]
        parent = container.get_resource_by_extid(parent_id)        
        
        # get parent folder
        if parent_class == VsphereFolder:
            objid = parent.objid + '.' + id_gen()
        # get parent datacenter
        else:
            objid = '%s//%s' % (parent.objid, id_gen())
        
        res = {
            'resource_class': resclass,
            'objid': objid, 
            'name': name, 
            'ext_id': ext_id, 
            'active': True, 
            'desc': resclass.objdesc, 
            'attrib': {}, 
            'parent': parent.oid,
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
        remote_entities = container.conn.folder.list()
        
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
            ext_obj = self.container.conn.folder.get(self.ext_id)
            self.set_physical_entity(ext_obj)
        except Exception as ex:
            self.logger.warn(ex)
        
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
        :param kvargs.datacenter: parent datacenter id or uuid
        :param kvargs.folder: parent folder id or uuid
        :param kvargs.folder_type: folder type. Can be: host, network, storage, vm             
        :return: kvargs            
        :raises ApiManagerError:
        """
        from .vs_datacenter import VsphereDatacenter

        # check parent
        datacenter = kvargs.pop('datacenter', None)
        folder = kvargs.pop('folder', None)
        
        kvargs['datacenter'] = None
        kvargs['folder'] = None
        
        # get parent folder
        if folder is not None:
            folder = container.get_resource(folder, entity_class=VsphereFolder)
            objid = '%s.%s' % (folder.objid, id_gen())
            kvargs['folder'] = folder.ext_id
            kvargs['parent'] = folder.oid
        elif datacenter is not None:
            datacenter = container.get_resource(datacenter, entity_class=VsphereDatacenter)
            objid = '%s//%s' % (datacenter.objid, id_gen())
            kvargs['datacenter'] = datacenter.ext_id
            kvargs['parent'] = datacenter.oid

        kvargs['objid'] = objid

        steps = [
            VsphereFolder.task_path + 'create_resource_pre_step',
            VsphereFolder.task_path + 'folder_create_physical_step',
            VsphereFolder.task_path + 'create_resource_post_step'
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
            VsphereFolder.task_path + 'update_resource_pre_step',
            VsphereFolder.task_path + 'folder_update_physical_step',
            VsphereFolder.task_path + 'update_resource_post_step'
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
            VsphereFolder.task_path + 'expunge_resource_pre_step',
            VsphereFolder.task_path + 'folder_delete_physical_step',
            VsphereFolder.task_path + 'expunge_resource_post_step'
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
        details = info['details']
        if self.ext_obj is not None:
            details.update(self.container.conn.folder.info(self.ext_obj))

        return info

    def detail(self):
        """Get details.
        
        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = VsphereResource.detail(self)
        details = info['details']
        if self.ext_obj is not None:
            details.update(self.container.conn.folder.detail(self.ext_obj))
        
        return info
