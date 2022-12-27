# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.zabbix.entity import ZabbixResource
from beehive_resource.plugins.zabbix.entity.zbx_hostgroup import ZabbixHostgroup
from beehive_resource.plugins.zabbix.entity.zbx_template import ZabbixTemplate

import logging
logger = logging.getLogger(__name__)


class ZabbixHost(ZabbixResource):
    objdef = 'Zabbix.Host'
    objuri = 'host'
    objname = 'host'
    objdesc = 'Zabbix host'

    default_tags = ['zabbix', 'monitoring']
    task_base_path = 'beehive_resource.plugins.zabbix.task_v2.zbx_host.ZabbixHostTask.'

    def __init__(self, *args, **kvargs):
        """ """
        ZabbixResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []
        # hostgroups the host belongs to
        self.groups = []
        # templates linked to the host
        self.templates = []
        # interfaces used by the host
        self.ext_interfaces = []

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
            items = container.conn.host.get(ext_id)
        else:
            items = container.conn.host.list()

        # add new items to final list
        res = []
        for item in items:
            item_id = item['hostid']
            if item_id not in res_ext_ids:
                level = None
                name = item['name']
                status = item['status']
                parent_id = None
                res.append((ZabbixHost, item_id, parent_id, ZabbixHost.objdef, name, level, status))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to communicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # query zabbix
        items = []
        hosts = container.conn.host.list()
        for host in hosts:
            items.append({
                'id': host['hostid'],
                'name': host['name']
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
        status = entity[6]

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
        # query zabbix
        remote_entities = container.conn.host.list()

        # create index of remote objs
        remote_entities_index = {i['hostid']: i for i in remote_entities}

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
            ext_obj = self.container.conn.host.get(self.ext_id)
            self.set_physical_entity(ext_obj)

            # retrieve hostgroups the host belongs to
            ext_groups = self.container.conn.host.groups(ext_obj['hostid']).get('groups', [])
            for item in ext_groups:
                group = self.controller.get_resource_by_extid(item['groupid'])
                self.groups.append(group)

            # retrieve templates linked to the host
            ext_templates = self.container.conn.host.templates(ext_obj['hostid']).get('parentTemplates', [])
            for item in ext_templates:
                template = self.controller.get_resource_by_extid(item['templateid'])
                self.templates.append(template)

            # retrieve interfaces used by the host
            self.ext_interfaces = self.container.conn.host.interfaces(ext_obj['hostid']).get('interfaces', [])
        except:
            # pass
            logger.warning('', exc_info=True)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.
        """
        groups = kvargs.pop('groups')
        templates = kvargs.pop('templates')

        # retrieve external ids for given hostgroups and templates
        group_ext_ids = []
        template_ext_ids = []
        try:
            for item in groups:
                obj = container.get_resource(item, entity_class=ZabbixHostgroup)
                if obj.is_ext_id_valid() is True:
                    # check whether hostgroup exists on the platform
                    res = container.conn.group.get(obj.ext_id)
                    # if exists, add it to list of ext_ids
                    group_ext_ids.append(obj.ext_id)

            for item in templates:
                obj = container.get_resource(item, entity_class=ZabbixTemplate)
                if obj.is_ext_id_valid() is True:
                    # check whether template exists on the platform
                    res = container.conn.template.get(obj.ext_id)
                    # if exists, add it to list of ext_ids
                    template_ext_ids.append(obj.ext_id)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise Exception(ex)

        kvargs['groups'] = group_ext_ids
        kvargs['templates'] = template_ext_ids

        steps = [
            ZabbixHost.task_base_path + 'create_resource_pre_step',
            ZabbixHost.task_base_path + 'host_create_physical_step',
            ZabbixHost.task_base_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.
        """
        steps = [
            ZabbixHost.task_base_path + 'update_resource_pre_step',
            ZabbixHost.task_base_path + 'host_update_physical_step',
            ZabbixHost.task_base_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.
        """
        steps = [
            ZabbixHost.task_base_path + 'expunge_resource_pre_step',
            ZabbixHost.task_base_path + 'host_delete_physical_step',
            ZabbixHost.task_base_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    def do_expunge(self, **params):
        """method to execute to make custom resource operations useful to complete delete

        :param params: custom params required by task
        """
        if self.is_ext_id_valid() is False:
            self.logger.warn('resource %s ext_id is not valid. Do nothing' % self.oid)

        try:
            # check whether host exists
            self.container.conn.host.get(self.ext_id)
            # delete host
            self.container.conn.host.delete(self.ext_id)
            self.logger.debug('delete zabbix host %s' % self.ext_id)
        except:
            self.logger.warning('zabbix host %s does not exist anymore' % self.ext_id)

    #
    # info
    #
    def info(self):
        """Get info.

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

        hostgroups = [{'id': item.oid, 'objid': item.objid, 'name': item.name} for item in self.groups]
        templates = [{'id': item.oid, 'objid': item.objid, 'name': item.name} for item in self.templates]
        ext_interfaces = [
            {
                'id': item['interfaceid'],
                'ip': item['ip'],
                'port': item['port'],
                'type': item['type'],
                'main': item['main']
            } for item in self.ext_interfaces
        ]
        data = {
            'groups': hostgroups,
            'templates': templates,
            'ext_interfaces:': ext_interfaces,
        }
        info['details'].update(data)

        return info
