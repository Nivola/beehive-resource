# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beecell.simple import id_gen
from beecell.types.type_dict import dict_get
from beehive_resource.plugins.zabbix.entity import ZabbixResource
from beehive.common.data import trace, operation
from beehive.common.data import cache

logger = logging.getLogger(__name__)


class ZabbixAction(ZabbixResource):
    objdef = "Zabbix.Action"
    objuri = "actions"
    objname = "action"
    objdesc = "Zabbix Action"

    default_tags = ["zabbix"]
    task_base_path = "beehive_resource.plugins.zabbix.task_v2.zbx_action.ZabbixActionTask."

    severity = None

    def __init__(self, *args, **kvargs):
        """ """
        ZabbixResource.__init__(self, *args, **kvargs)

        # self.zabbix_users = []

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, ZabbixAction.objuri)

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
        logger.debug("+++++ discover_new - res_ext_ids {}".format(res_ext_ids))

        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = container
        zabbixManager: ZabbixManager = zabbixContainer.conn

        # get from zabbix
        logger.debug("+++++ discover_new - ext_id {}".format(ext_id))
        if ext_id is not None:
            items = []
            items.append(zabbixManager.action.get(ext_id))
        else:
            items = zabbixManager.action.list()

        # add new item to final list
        res = []
        for item in items:
            item_id = str(item["actionid"])
            logger.debug("+++++ discover_new - item_id {}".format(item_id))
            if item_id not in res_ext_ids:
                name = item["name"]
                eventsource = item["eventsource"]
                parent_id = None
                logger.debug("+++++ discover_new - append item_id {}".format(item_id))
                res.append((ZabbixAction, item_id, parent_id, ZabbixAction.objdef, name, eventsource))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = container
        zabbixManager: ZabbixManager = zabbixContainer.conn

        # get from zabbix
        items = []
        remote_entities = zabbixManager.action.list()
        for item in remote_entities:
            logger.debug("+++++ discover_died - id {}".format(item["actionid"]))
            item_name = item["name"]
            items.append({"id": str(item["actionid"]), "name": item_name})

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
        # logger.debug("+++++ synchronize - entity: ".format(entity))
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        eventsource = entity[5]

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {"eventsource": eventsource},
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
        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = container
        zabbixManager: ZabbixManager = zabbixContainer.conn

        # get from zabbix
        remote_entities = zabbixManager.action.list()

        # create index of remote objs
        remote_entities_index = {i["actionid"]: i for i in remote_entities}

        entity: ZabbixAction
        for entity in entities:
            try:
                if entity.ext_id is not None:
                    ext_obj = remote_entities_index.get(entity.ext_id, None)
                    print("customize_list - ext_obj: %s" % ext_obj)
                    entity.set_physical_entity(ext_obj)
                    entity.get_severity(ext_obj)
            except:
                container.logger.warn("", exc_info=1)

        return entities

    def get_severity(self, ext_obj):
        filter = ext_obj["filter"]
        conditions = filter["conditions"]
        for condition in conditions:
            # severity higher or equal to XX
            conditiontype = condition["conditiontype"]
            if conditiontype == "4":
                value = condition["value"]
                print("post_get - value: %s" % value)
                print("post_get - type value: %s" % type(value))
                from beedrones.zabbix.action import ZabbixAction as BeedronesZabbixAction

                value_int = int(value)
                if value_int == BeedronesZabbixAction.SEVERITY_INFORMATION:
                    self.severity = "Information"
                elif value_int == BeedronesZabbixAction.SEVERITY_WARNING:
                    self.severity = "Warning"
                elif value_int == BeedronesZabbixAction.SEVERITY_AVERAGE:
                    self.severity = "Average"
                elif value_int == BeedronesZabbixAction.SEVERITY_HIGH:
                    self.severity = "High"
                elif value_int == BeedronesZabbixAction.SEVERITY_DISASTER:
                    self.severity = "Disaster"
                else:
                    self.severity = "-"

        print("get_severity - severity: %s" % self.severity)

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_action(self.controller, self.ext_id, self.container, self.ext_id)
        if ext_obj is not None:
            self.set_physical_entity(ext_obj)
            self.get_severity(ext_obj)

    @staticmethod
    @cache("zabbix.action.get", ttl=3600)
    def get_remote_action(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            from beehive_resource.plugins.zabbix.controller import ZabbixContainer
            from beehive_resource.plugins.zabbix.controller import ZabbixManager

            zabbixContainer: ZabbixContainer = container
            zabbixManager: ZabbixManager = zabbixContainer.conn

            remote_entity = zabbixManager.action.get(ext_id)
            return remote_entity
        except Exception as ex:
            logger.error(ex, exc_info=True)
            return None

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
            ZabbixAction.task_base_path + "create_resource_pre_step",
            ZabbixAction.task_base_path + "zabbix_action_create_physical_step",
            ZabbixAction.task_base_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            ZabbixAction.task_base_path + "update_resource_pre_step",
            ZabbixAction.task_base_path + "zabbix_action_update_physical_step",
            ZabbixAction.task_base_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            ZabbixAction.task_base_path + "expunge_resource_pre_step",
            ZabbixAction.task_base_path + "zabbix_action_delete_physical_step",
            ZabbixAction.task_base_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
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
        info = ZabbixResource.info(self)
        info["severity"] = self.severity
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ZabbixResource.detail(self)
        info["severity"] = self.severity
        return info

    @trace(op="update")
    def update_severity(self, severity: str, hostgroup_id=None, *args, **kvargs):
        """Update severity

        :param severity: user severity
        :param hostgroup_id: hostgroup_id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            # add check user exists
            return kvargs

        kvargs.update(
            {
                "severity": severity,
                "hostgroup_id": hostgroup_id,
            }
        )
        logger.debug("update_severity - after update kvargs {}".format(kvargs))

        steps = ["beehive_resource.plugins.zabbix.task_v2.zbx_action.ZabbixActionTask.update_severity_step"]
        res = self.action("update_severity", steps, log="Update_severity", check=check, **kvargs)
        return res, "called"
