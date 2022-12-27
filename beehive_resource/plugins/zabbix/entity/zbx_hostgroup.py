# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.zabbix.entity import ZabbixResource

import logging
logger = logging.getLogger(__name__)


class ZabbixHostgroup(ZabbixResource):
    objdef = 'Zabbix.Hostgroup'
    objuri = 'hostgroup'
    objname = 'hostgroup'
    objdesc = 'Zabbix hostgroup'

    default_tags = ['zabbix', 'monitoring']
    task_base_path = 'beehive_resource.plugins.zabbix.task_v2.zbx_hostgroup.ZabbixHostgroupTask.'

    def __init__(self, *args, **kvargs):
        """ """
        ZabbixResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []
        # hosts that belong to the hostgroup
        self.hosts = []
        # templates that belong to the hostgroup
        self.templates = []

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
        # query zabbix
        if ext_id is not None:
            items = container.conn.group.get(ext_id)
        else:
            items = container.conn.group.list()

        # add new items to final list
        res = []
        for item in items:
            item_id = item['groupid']
            if item_id not in res_ext_ids:
                level = None
                name = item['name']
                internal = item['internal']
                parent_id = None
                res.append((ZabbixHostgroup, item_id, parent_id, ZabbixHostgroup.objdef, name, level, internal))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to communicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        items = []
        groups = container.conn.group.list()
        for group in groups:
            items.append({
                'id': group['groupid'],
                'name': group['name']
            })
        return items

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data:

            {
                'resclass': ..,
                'objid': ..,
                'name': ..,
                'ext_id': ..,
                'active': ..,
                'desc': ..,
                'attrib': ..,
                'parent': ..,
                'tags': ..
            }

        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        level = entity[5]
        internal = entity[6]

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
        remote_entities = container.conn.group.list()

        # create index of remote objs
        remote_entities_index = {i['groupid']: i for i in remote_entities}

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
            ext_obj = self.container.conn.group.get(self.ext_id)
            self.set_physical_entity(ext_obj)

            # retrieve hosts that belong to the hostgroup
            ext_hosts = self.container.conn.group.hosts(self.ext_id).get('hosts', [])
            for item in ext_hosts:
                host = self.controller.get_resource_by_extid(item['hostid'])
                self.hosts.append(host)

            # retrieve templates that belong to the hostgroup
            ext_templates = self.container.conn.group.templates(self.ext_id).get('templates', [])
            for item in ext_templates:
                template = self.controller.get_resource_by_extid(item['templateid'])
                self.templates.append(template)
        except:
            # pass
            logger.warning('', exc_info=True)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.
        """
        # get hostgroup name from input params
        name = kvargs.get('name')

        # check whether a hostgroup named 'name' already exists on zabbix
        found = False
        hostgroups = container.conn.group.list()
        for item in hostgroups:
            if item['name'] == name:
                # hostgroup already exists, do not proceed with creation
                found = True
                break

        if not found:
            steps = [
                ZabbixHostgroup.task_base_path + 'create_resource_pre_step',
                ZabbixHostgroup.task_base_path + 'hostgroup_create_physical_step',
                ZabbixHostgroup.task_base_path + 'create_resource_post_step'
            ]
            kvargs['steps'] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.
        """
        steps = [
            ZabbixHostgroup.task_base_path + 'update_resource_pre_step',
            ZabbixHostgroup.task_base_path + 'hostgroup_update_physical_step',
            ZabbixHostgroup.task_base_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.
        """

        # From Zabbix docs:
        # https://www.zabbix.com/documentation/current/manual/api/reference/hostgroup/delete
        #
        # A host group can not be deleted if:
        # - it is marked as internal
        # - it contains hosts that belong to this group only
        # - it contains templates that belong to this group only
        # (- it is used by a host prototype)
        # (- it is used in a global script)
        # (- it is used in a correlation condition)

        can_delete = True

        ext_obj = self.container.conn.group.get(self.ext_id)
        if ext_obj.get('internal') == 1:
            can_delete = False

        self.post_get()

        for host in self.hosts:
            groups = self.container.conn.host.groups(host.ext_id).get('groups', [])
            if len(groups) <= 1:
                can_delete = False

        for template in self.templates:
            groups = self.container.conn.template.groups(template.ext_id).get('groups', [])
            if len(groups) <= 1:
                can_delete = False

        if can_delete:
            steps = [
                ZabbixHostgroup.task_base_path + 'expunge_resource_pre_step',
                ZabbixHostgroup.task_base_path + 'hostgroup_delete_physical_step',
                ZabbixHostgroup.task_base_path + 'expunge_resource_post_step'
            ]
            kvargs['steps'] = steps

        return kvargs

    #
    # info
    #
    def info(self):
        """Get infos.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return ZabbixResource.info(self)

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ZabbixResource.detail(self)

        hosts = [{'id': item.oid, 'objid': item.objid, 'name': item.name} for item in self.hosts]
        templates = [{'id': item.oid, 'objid': item.objid, 'name': item.name} for item in self.templates]
        data = {
            'hosts': hosts,
            'templates': templates,
        }
        info['details'].update(data)

        return info

