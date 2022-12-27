# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import logging
from beecell.simple import id_gen
from beecell.types.type_dict import dict_get
from beehive_resource.plugins.grafana.entity import GrafanaResource
from beehive.common.data import trace, operation

logger = logging.getLogger(__name__)


class GrafanaFolder(GrafanaResource):
    objdef = 'Grafana.Folder'
    objuri = 'folders'
    objname = 'folder'
    objdesc = 'Grafana Folder'
    
    default_tags = ['grafana']
    task_base_path = 'beehive_resource.plugins.grafana.task_v2.grafana_folder.GrafanaFolderTask.'
    
    def __init__(self, *args, **kvargs):
        """ """
        GrafanaResource.__init__(self, *args, **kvargs)

        self.dashboards = []
        self.permissions = []

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, GrafanaFolder.objuri)
        
    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to communicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)
        :raises ApiManagerError:
        """
        # get from grafana
        if ext_id is not None:
            remote_entities = container.conn_grafana.folder.get(ext_id)
        else:
            remote_entities = container.conn_grafana.folder.list()

        # add new item to final list
        res = []
        for item in remote_entities:
            if item['uid'] not in res_ext_ids:
                level = None
                name = item['title']
                parent_id = None
                res.append((GrafanaFolder, item['uid'], parent_id, GrafanaFolder.objdef, name, level))
        
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # get from grafana
        items = []
        remote_entities = container.conn_grafana.folder.list()
        for item in remote_entities:
            items.append({
                'id': item['uid'],
                'name': item['title']
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
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        
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
        # get from grafana
        from beehive_resource.plugins.grafana.controller import GrafanaContainer
        grafanaContainer: GrafanaContainer = container
        remote_entities = grafanaContainer.conn_grafana.folder.list()
        
        # create index of remote objs
        remote_entities_index = {i['id']: i for i in remote_entities}
        
        entity: GrafanaFolder
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
                entity.get_dashboard()
                entity.get_permission()
            except:
                container.logger.warn('', exc_info=1)

        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_folder(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)
        self.get_dashboard()
        self.get_permission()
        
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.vcpus: vcpus
        :param kvargs.ram: ram
        :param kvargs.disk: disk
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            GrafanaFolder.task_base_path + 'create_resource_pre_step',
            GrafanaFolder.task_base_path + 'grafana_folder_create_physical_step',
            GrafanaFolder.task_base_path + 'create_resource_post_step',
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
            GrafanaFolder.task_base_path + 'update_resource_pre_step',
            GrafanaFolder.task_base_path + 'grafana_folder_update_physical_step',
            GrafanaFolder.task_base_path + 'update_resource_post_step',
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
            GrafanaFolder.task_base_path + 'expunge_resource_pre_step',
            GrafanaFolder.task_base_path + 'grafana_folder_delete_physical_step',
            GrafanaFolder.task_base_path + 'expunge_resource_post_step',
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
        info = GrafanaResource.info(self)
        info['dashboards'] = self.dashboards
        info['permissions'] = self.permissions
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = GrafanaResource.detail(self)
        info['dashboards'] = self.dashboards
        info['permissions'] = self.permissions
        return info

    def get_dashboard(self):
        """get folder dashboard"""
        dashboards = self.get_remote_folder_dashboards(self.controller, self.ext_id, self.container, self.ext_id)
        self.dashboards = [{
            'id': dict_get(d, 'id'),
            'uid': dict_get(d, 'uid'),
            'desc': dict_get(d, 'title'),
            # 'version': dict_get(d, 'version'),
            'tags': dict_get(d, 'tags'),
            # 'updated_at': dict_get(d, 'meta.updated'),
        } for d in dashboards]

    @trace(op='update')
    def add_dashboard(self, dashboard_to_search, folder_uid_to, organization, division, account, dash_tag, *args, **kvargs):
        """Add dashboard

        :param dashboard: dashboard name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            # add check dashboard exists
            return kvargs

        kvargs.update({
            'dashboard_to_search': dashboard_to_search,
            'folder_uid_to': folder_uid_to,
            'dash_tag': dash_tag,
            'organization': organization,
            'division': division,
            'account': account,
        })
        logger.debug('add_dashboard - after update kvargs {}'.format(kvargs))
        
        steps = ['beehive_resource.plugins.grafana.task_v2.grafana_folder.GrafanaFolderTask.add_dashboard_step']
        res = self.action('add_dashboard', steps, log='Add dashboard', check=check, **kvargs)
        return res, 'called'

    def get_permission(self):
        """get folder permission"""
        permissions = self.get_remote_folder_permissions(self.controller, self.ext_id, self.container, self.ext_id)
        self.permissions = [{
            'teamId': dict_get(d, 'teamId'),
            'team': dict_get(d, 'team'),
            'permissionName': dict_get(d, 'permissionName'),
            'updated': dict_get(d, 'updated'),
        } for d in permissions]

    @trace(op='update')
    def add_permission(self, folder_uid, team_viewer=None, team_editor=None, *args, **kvargs):
        """Add permission

        :param permission: permission name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            # add check permission exists
            return kvargs

        kvargs.update({
            'folder_uid': folder_uid,
            'team_viewer': team_viewer,
            'team_editor': team_editor,
        })
        logger.debug('add_permission - after update kvargs {}'.format(kvargs))
        
        steps = ['beehive_resource.plugins.grafana.task_v2.grafana_folder.GrafanaFolderTask.add_permission_step']
        res = self.action('add_permission', steps, log='Add permission', check=check, **kvargs)
        return res, 'called'
