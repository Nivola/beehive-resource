# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.vsphere.entity import NsxResource
from beehive.common.data import trace


class NsxSecurityGroup(NsxResource):
    objdef = 'Vsphere.Nsx.NsxSecurityGroup'
    objuri = 'nsx_security_groups'
    objname = 'nsx_security_group'
    objdesc = 'Vsphere Nsx security_group'
    
    default_tags = ['vsphere', 'security_group']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.nsx_security_group.NsxSecurityGroupTask.'
    
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
        security_groups = container.conn.network.nsx.sg.list()
        for security_group in security_groups:
            items.append((security_group['objectId'], security_group['name'], nsx_manager_id, None))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = NsxSecurityGroup
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
        sgs = container.conn.network.nsx.sg.list()
        for sg in sgs:
            items.append({
                'id':sg['objectId'],
                'name':sg['name'],
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
        remote_entities = container.conn.network.nsx.sg.list()
        
        # create index of remote objs
        remote_entities_index = {i['objectId']: i for i in remote_entities}      
        
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
            ext_obj = self.container.conn.network.nsx.sg.get(self.ext_id)
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
        :param kvargs.datacenter: parent datacenter id or uuid
        :param kvargs.folder: parent folder id or uuid
        :param kvargs.folder_type: folder type. Can be: host, network, storage, vm             
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
        
        steps = [
            NsxSecurityGroup.task_path + 'create_resource_pre_step',
            NsxSecurityGroup.task_path + 'nsx_security_group_create_step',
            NsxSecurityGroup.task_path + 'create_resource_post_step'
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
            NsxSecurityGroup.task_path + 'update_resource_pre_step',
            NsxSecurityGroup.task_path + 'update_resource_post_step'
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
            NsxSecurityGroup.task_path + 'expunge_resource_pre_step',
            NsxSecurityGroup.task_path + 'nsx_security_group_delete_step',
            NsxSecurityGroup.task_path + 'expunge_resource_post_step'
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
        try:
            if self.ext_obj is not None:
                info['details'] = {}
                details = info['details']
                data = self.container.conn.network.nsx.sg.info(self.ext_obj)
                data.pop('member', None)
                data.pop('dynamicMemberDefinition', None)
                data.pop('type', None)
                data.pop('objectId', None)
                
                details.update(data)
        except Exception as ex:
            self.logger.warning(ex, exc_info=1)        
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
                data = self.container.conn.network.nsx.sg.info(self.ext_obj)
                data.pop('dynamicMemberDefinition', None)
                data.pop('type', None)
                data.pop('objectId', None)

                members = data.pop('member', [])
                if isinstance(members, list) is False:
                    members = [members]
                data['members'] = []
                for item in members:
                    m_type = item['objectTypeName']
                    if m_type == 'VirtualMachine':
                        member = self.container.get_resources(ext_id=item['objectId'])[0]
                    elif m_type == 'IPSet':
                        member = self.parent().get_ipsets(ext_id=item['objectId'])[0]                  
                    data['members'].append(member.info())
                
                details.update(data)
        except Exception as ex:
            self.logger.warning(ex, exc_info=1)
        return info

    def is_member(self, member):
        data = self.container.conn.network.nsx.sg.info(self.ext_obj)
        members = data.pop('member', [])
        if isinstance(members, dict):
            members = [members]
        members = [m.get('objectId') for m in members]
        self.logger.warn(members)
        if member.ext_id in members:
            return True
        return False

    @trace(op='update')
    def add_member(self, params):
        """Add member

        :param args: custom positional args
        :param kvargs: custom key value args
        :param kvargs.member: The securitygroup member to add
        :param kvargs.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        name = 'add_member'
        steps = [self.task_path + 'nsx_security_group_add_member_step']
        member = self.container.get_simple_resource(params.get('member'))
        params.update({
            'cid': self.container.oid,
            'security_group': self.ext_id,
            'member': member.ext_id
        })
        res = self.action(name, steps, log='Add security group member', check=None, **params)
        return res

    @trace(op='update')
    def delete_member(self, params):
        """Delete member 

        :param args: custom positional args
        :param kvargs: custom key value args
        :param kvargs.member: The securitygroup member to remove
        :param kvargs.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        name = 'del_member'
        steps = [self.task_path + 'nsx_security_group_delete_member_step']
        member = self.container.get_simple_resource(params.get('member'))
        params.update({
            'cid': self.container.oid,
            'security_group': self.ext_id,
            'member': member.ext_id
        })
        res = self.action(name, steps, log='Remove security group member', check=None, **params)
        return res
