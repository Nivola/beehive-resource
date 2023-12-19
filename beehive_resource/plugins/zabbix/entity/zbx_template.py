# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.zabbix.entity import ZabbixResource
from beehive_resource.plugins.zabbix.entity.zbx_hostgroup import ZabbixHostgroup

import logging

logger = logging.getLogger(__name__)


class ZabbixTemplate(ZabbixResource):
    objdef = "Zabbix.Template"
    objuri = "template"
    objname = "template"
    objdesc = "Zabbix template"

    default_tags = ["zabbix", "monitoring"]
    task_base_path = "beehive_resource.plugins.zabbix.task_v2.zbx_template.ZabbixTemplateTask."

    def __init__(self, *args, **kvargs):
        """ """
        ZabbixResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []
        # hosts that are linked to the template
        self.hosts = []
        # hostgroups that the template belongs to
        self.groups = []

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
            items = container.conn.template.get(ext_id)
        else:
            items = container.conn.template.list()

        # add new items to final list
        res = []
        for item in items:
            item_id = item["templateid"]
            if item_id not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = None
                res.append(
                    (
                        ZabbixTemplate,
                        item_id,
                        parent_id,
                        ZabbixTemplate.objdef,
                        name,
                        level,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to communicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        items = []
        templates = container.conn.template.list()
        for template in templates:
            items.append({"id": template["templateid"], "name": template["name"]})
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

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent_id,
            "tags": resclass.default_tags,
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
        remote_entities = container.conn.template.list()

        # create index of remote objs
        remote_entities_index = {i["templateid"]: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn("", exc_info=1)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.template.get(self.ext_id)
            self.set_physical_entity(ext_obj)

            # retrieve hosts that are linked to the template
            ext_hosts = self.container.conn.template.hosts(ext_obj["templateid"]).get("hosts", [])
            for item in ext_hosts:
                host = self.controller.get_resource_by_extid(item["hostid"])
                self.hosts.append(host)

            # retrieve hostgroups the template belongs to
            ext_groups = self.container.conn.template.groups(ext_obj["templateid"]).get("groups", [])
            for item in ext_groups:
                group = self.controller.get_resource_by_extid(item["groupid"])
                self.groups.append(group)
        except:
            # pass
            logger.warning("", exc_info=True)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method."""
        name = kvargs.get("name")
        groups = kvargs.get("groups")

        # check whether a template named 'name' already exists on zabbix
        found = False
        templates = container.conn.template.list()
        for item in templates:
            if item["name"] == name:
                # template already exists, do not proceed with creation
                found = True
                break

        if not found:
            # retrieve ext_ids for given hostgroups
            ext_ids = []
            for item in groups:
                group = container.get_resource(item, entity_class=ZabbixHostgroup)
                ext_ids.append(group.ext_id)
            kvargs["groups"] = ext_ids

            steps = [
                ZabbixTemplate.task_base_path + "create_resource_pre_step",
                ZabbixTemplate.task_base_path + "template_create_physical_step",
                ZabbixTemplate.task_base_path + "create_resource_post_step",
            ]
            kvargs["steps"] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method."""
        steps = [
            ZabbixTemplate.task_base_path + "update_resource_pre_step",
            # ZabbixTemplate.task_base_path + 'template_update_physical_step',
            ZabbixTemplate.task_base_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method."""
        steps = [
            ZabbixTemplate.task_base_path + "expunge_resource_pre_step",
            ZabbixTemplate.task_base_path + "template_delete_physical_step",
            ZabbixTemplate.task_base_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps

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

        hostgroups = [{"id": item.oid, "objid": item.objid, "name": item.name} for item in self.groups]
        hosts = [{"id": item.oid, "objid": item.objid, "name": item.name} for item in self.hosts]
        data = {
            "groups": hostgroups,
            "hosts": hosts,
        }
        info["details"].update(data)

        return info
