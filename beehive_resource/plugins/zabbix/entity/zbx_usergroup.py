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


class ZabbixUsergroup(ZabbixResource):
    objdef = "Zabbix.Usergroup"
    objuri = "usergroups"
    objname = "usergroup"
    objdesc = "Zabbix Usergroup"

    default_tags = ["zabbix"]
    task_base_path = "beehive_resource.plugins.zabbix.task_v2.zbx_usergroup.ZabbixUsergroupTask."

    users_email = []
    user_severities = []

    def __init__(self, *args, **kvargs):
        """ """
        ZabbixResource.__init__(self, *args, **kvargs)

        # self.zabbix_users = []

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, ZabbixUsergroup.objuri)

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
            items = zabbixManager.usergroup.get(ext_id)
        else:
            items = zabbixManager.usergroup.list()

        # add new item to final list
        res = []
        for item in items:
            item_id = str(item["usrgrpid"])
            logger.debug("+++++ discover_new - item_id {}".format(item_id))
            if item_id not in res_ext_ids:
                level = None
                name = item["name"]
                # status = item['status']
                parent_id = None
                logger.debug("+++++ discover_new - append item_id {}".format(item_id))
                res.append((ZabbixUsergroup, item_id, parent_id, ZabbixUsergroup.objdef, name, level))  # , status))

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
        remote_entities = zabbixManager.usergroup.list()
        for item in remote_entities:
            logger.debug("+++++ discover_died - id {}".format(item["usrgrpid"]))
            items.append({"id": str(item["usrgrpid"]), "name": item["name"]})

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
        from beehive_resource.plugins.zabbix.controller import ZabbixContainer
        from beehive_resource.plugins.zabbix.controller import ZabbixManager

        zabbixContainer: ZabbixContainer = container
        zabbixManager: ZabbixManager = zabbixContainer.conn

        # get from zabbix
        remote_entities = zabbixManager.usergroup.list()

        # create index of remote objs
        remote_entities_index = {i["usrgrpid"]: i for i in remote_entities}

        entity: ZabbixUsergroup
        for entity in entities:
            try:
                if entity.ext_id is not None:
                    ext_obj = remote_entities_index.get(entity.ext_id, None)
                    entity.set_physical_entity(ext_obj)
                    entity.get_user_info(ext_obj)
            except:
                container.logger.warn("", exc_info=1)

        return entities

    def get_user_info(self, ext_obj):
        self.users_email = []
        self.user_severities = []
        severity_temp: int = 0
        users = ext_obj["users"]

        # one user for email media
        for user in users:
            userid = user["userid"]
            alias: str = user["alias"]

            # username = "Gruppo %s" % params.get("triplet")
            if alias.startswith("Gruppo"):
                from beehive_resource.plugins.zabbix.controller import ZabbixContainer
                from beehive_resource.plugins.zabbix.controller import ZabbixManager

                zabbixContainer: ZabbixContainer = self.container
                zabbixManager: ZabbixManager = zabbixContainer.conn

                remote_user = zabbixManager.user.get(userid)
                medias = remote_user["medias"]
                for media in medias:
                    severity = media["severity"]
                    sendto = media["sendto"]
                    mediatypeid = media["mediatypeid"]
                    if mediatypeid == "1":  # email
                        for email in sendto:
                            self.users_email.append(email)

                        severity_temp = int(severity)

        # split severity level
        from beedrones.zabbix.user import ZabbixUser as BeedronesZabbixUser
        from beehive_resource.plugins.zabbix import ZabbixPlugin

        if severity_temp >= BeedronesZabbixUser.SEVERITY_DISASTER:
            self.user_severities.append(ZabbixPlugin.SEVERITY_DESC_DISASTER)
            severity_temp -= BeedronesZabbixUser.SEVERITY_DISASTER

        if severity_temp >= BeedronesZabbixUser.SEVERITY_HIGH:
            self.user_severities.append(ZabbixPlugin.SEVERITY_DESC_HIGH)
            severity_temp -= BeedronesZabbixUser.SEVERITY_HIGH

        if severity_temp >= BeedronesZabbixUser.SEVERITY_AVERAGE:
            self.user_severities.append(ZabbixPlugin.SEVERITY_DESC_AVERAGE)
            severity_temp -= BeedronesZabbixUser.SEVERITY_AVERAGE

        if severity_temp >= BeedronesZabbixUser.SEVERITY_WARNING:
            self.user_severities.append(ZabbixPlugin.SEVERITY_DESC_WARNING)
            severity_temp -= BeedronesZabbixUser.SEVERITY_WARNING

        if severity_temp >= BeedronesZabbixUser.SEVERITY_INFORMATION:
            self.user_severities.append(ZabbixPlugin.SEVERITY_DESC_INFORMATION)
            severity_temp -= BeedronesZabbixUser.SEVERITY_INFORMATION

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_usergroup(self.controller, self.ext_id, self.container, self.ext_id)
        if ext_obj is not None:
            self.set_physical_entity(ext_obj)
            self.get_user_info(ext_obj)

    @staticmethod
    @cache("zabbix.usergroup.get", ttl=3600)
    def get_remote_usergroup(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            from beehive_resource.plugins.zabbix.controller import ZabbixContainer
            from beehive_resource.plugins.zabbix.controller import ZabbixManager

            zabbixContainer: ZabbixContainer = container
            zabbixManager: ZabbixManager = zabbixContainer.conn

            remote_entity = zabbixManager.usergroup.get(ext_id)
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
            ZabbixUsergroup.task_base_path + "create_resource_pre_step",
            ZabbixUsergroup.task_base_path + "zabbix_usergroup_create_physical_step",
            ZabbixUsergroup.task_base_path + "create_resource_post_step",
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
            ZabbixUsergroup.task_base_path + "update_resource_pre_step",
            ZabbixUsergroup.task_base_path + "zabbix_usergroup_update_physical_step",
            ZabbixUsergroup.task_base_path + "update_resource_post_step",
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
            ZabbixUsergroup.task_base_path + "expunge_resource_pre_step",
            ZabbixUsergroup.task_base_path + "zabbix_usergroup_delete_physical_step",
            ZabbixUsergroup.task_base_path + "expunge_resource_post_step",
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
        info["users_email"] = self.users_email
        info["user_severities"] = self.user_severities
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ZabbixResource.detail(self)
        info["users_email"] = self.users_email
        info["user_severities"] = self.user_severities
        return info

    @trace(op="update")
    def add_user(self, username, users_email: str, severity: str, usergroup_id_to, *args, **kvargs):
        """Add user

        :param users_email: user email
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            # add check user exists
            return kvargs

        kvargs.update(
            {
                "username": username,
                "users_email": users_email,
                "severity": severity,
                "usergroup_id_to": usergroup_id_to,
            }
        )
        logger.debug("add_user - after update kvargs {}".format(kvargs))

        steps = ["beehive_resource.plugins.zabbix.task_v2.zbx_usergroup.ZabbixUsergroupTask.add_user_step"]
        res = self.action("add_user", steps, log="Add user", check=check, **kvargs)
        return res, "called"
