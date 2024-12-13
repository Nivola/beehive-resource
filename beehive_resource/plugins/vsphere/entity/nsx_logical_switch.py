# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.vsphere.entity import NsxResource
from beehive_resource.plugins.vsphere.entity import get_task


class NsxLogicalSwitch(NsxResource):
    objdef = "Vsphere.Nsx.NsxLogicalSwitch"
    objuri = "nsx_logical_switchs"
    objname = "nsx_logical_switch"
    objdesc = "Vsphere Nsx logical_switch"

    default_tags = ["vsphere", "network"]
    task_path = "beehive_resource.plugins.vsphere.task_v2.nsx_logical_switch.NsxLogicalSwitchTask."

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

        nsx_manager_id = container.conn.system.nsx.summary_info()["hostName"]
        logical_switchs = container.conn.network.nsx.lg.list()
        for logical_switch in logical_switchs:
            items.append(
                (
                    logical_switch["objectId"],
                    logical_switch["name"],
                    nsx_manager_id,
                    None,
                )
            )

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = NsxLogicalSwitch
                res.append(
                    (
                        resclass,
                        item[0],
                        parent_id,
                        resclass.objdef,
                        item[1],
                        parent_class,
                    )
                )

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
        logical_switchs = container.conn.network.nsx.lg.get()
        for logical_switch in logical_switchs:
            items.append({"id": logical_switch["objectId"], "name": logical_switch["name"]})

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
        parent_id = parent.oid
        objid = "%s//%s" % (parent.objid, id_gen())

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
        remote_entities = container.conn.network.nsx.lg.list()

        # create index of remote objs
        remote_entities_index = {i["objectId"]: i for i in remote_entities}

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
            ext_obj = self.container.conn.network.nsx.lg.get(self.ext_id)
            self.set_physical_entity(ext_obj)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)

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
        :return: kvargs
        :raises ApiManagerError:
        """
        # get parent manager
        manager = container.get_nsx_manager()
        objid = "%s//%s" % (manager.objid, id_gen())

        kvargs.update({"objid": objid, "parent": manager.oid})

        steps = [
            NsxLogicalSwitch.task_path + "create_resource_pre_step",
            NsxLogicalSwitch.task_path + "nsx_logical_switch_create_step",
            NsxLogicalSwitch.task_path + "create_resource_post_step",
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
            NsxLogicalSwitch.task_path + "update_resource_pre_step",
            NsxLogicalSwitch.task_path + "update_resource_post_step",
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
            NsxLogicalSwitch.task_path + "expunge_resource_pre_step",
            NsxLogicalSwitch.task_path + "nsx_logical_switch_delete_step",
            NsxLogicalSwitch.task_path + "expunge_resource_post_step",
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
        info = NsxResource.info(self)
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
                details = info["details"]
                details.update(self.container.conn.network.nsx.lg.info(self.ext_obj))
                for item in details["switch"]:
                    switch = item["switch"]
                    obj = self.container.get_distributed_virtual_switches(ext_id=switch["objectId"])[0]
                    item["switch"] = obj.small_info()
                    portgroup = item["portgroup"]
                    obj = self.container.get_networks(ext_id=portgroup["objectId"])[0]
                    item["portgroup"] = obj.small_info()
        except Exception as ex:
            self.logger.warn(ex)

        return info

    def get_vlan(self):
        vlan = None
        if self.ext_obj is not None:
            vlan = self.ext_obj.get("vdnId", None)
        return vlan

    def get_private_subnet(self):
        """Get subnet for private network

        :return:
        :raise ApiManagerError:
        """
        cidr = None
        if self.container is not None:
            ippool_id = self.get_attribs(key="subnet")
            if ippool_id is not None:
                ippool = self.container.conn.network.nsx.ippool.get(ippool_id)
                prefix_ength = ippool.get("prefixLength")
                gateway = ippool.get("gateway").split(".")
                gateway[-1] = 0
                gateway = ".".join(map(str, gateway))
                cidr = "%s/%s" % (gateway, prefix_ength)
        return cidr

    def get_gateway(self):
        """Get gateway for private network

        :return:
        :raise ApiManagerError:
        """
        gateway = None
        if self.container is not None:
            ippool_id = self.get_attribs(key="subnet")
            if ippool_id is not None:
                ippool = self.container.conn.network.nsx.ippool.get(ippool_id)
                gateway = ippool.get("gateway")
        return gateway

    def get_allocation_pool(self):
        """Get allocation pool for private network

        :return:
        :raise ApiManagerError:
        """
        pool = None
        if self.container is not None:
            ippool_id = self.get_attribs(key="subnet")
            if ippool_id is not None:
                ippool = self.container.conn.network.nsx.ippool.get(ippool_id)
                range = ippool.get("ipRanges", {}).get("ipRangeDto", {})
                pool = [{"start": range.get("startAddress"), "end": range.get("endAddress")}]
        return pool

    def get_parent_dvss(self):
        """Get parent distributed virtual switches"""
        dvss = []
        if self.ext_obj is not None:
            backings = self.ext_obj.get("vdsContextWithBacking", {})
            for backing in backings:
                context = backing.get("switch")
                dvss.append(context.get("objectId"))

        self.logger.debug("get logical switch %s parent dvs: %s" % (self.oid, dvss))
        return dvss

    def get_associated_dvpg(self, dvs):
        """Get associated distributed virtual port group

        :param dvs: dvs mor_id
        """
        dvpg = None
        # self.logger.debug("get logical switch %s - ext_obj: %s - dvs: %s" % (self.oid, self.ext_obj, dvs))
        if self.ext_obj is not None:
            backings = self.ext_obj.get("vdsContextWithBacking", [])
            for backing in backings:
                # self.logger.debug("get logical switch %s - backing: %s" % (self.oid, backing))
                context = backing.get("switch", {}).get("objectId", None)
                if context == dvs:
                    dvpg = backing.get("backingValue")
                    dvpg = self.controller.get_resource_by_extid(dvpg)

        self.logger.debug("get logical switch %s parent dvpg: %s" % (self.oid, dvpg))
        return dvpg
