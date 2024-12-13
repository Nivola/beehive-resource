# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import truncate, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive.common.data import trace


class VsphereDvs(VsphereResource):
    objdef = "Vsphere.DataCenter.Folder.Dvs"
    objuri = "dvss"
    objname = "dvs"
    objdesc = "Vsphere distributed virtual switches"

    default_tags = ["vsphere", "network"]
    task_path = "beehive_resource.plugins.vsphere.task_v2.vs_dvs.DvsTask."

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
        items = []
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        for datacenter in datacenters:
            for node in datacenter.networkFolder.childEntity:
                obj_type = type(node).__name__
                if obj_type == "vim.dvs.VmwareDistributedVirtualSwitch":
                    items.append((node._moId, node.name, node.parent._moId, None))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereDvs
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
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []

        for datacenter in datacenters:
            for node in datacenter.networkFolder.childEntity:
                obj_type = type(node).__name__
                if obj_type == "vim.dvs.VmwareDistributedVirtualSwitch":
                    items.append({"id": node._moId, "name": node.name})

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
        remote_entities = container.conn.network.list_distributed_virtual_switches()

        # create index of remote objs
        remote_entities_index = {i["obj"]._moId: i for i in remote_entities}

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
            ext_obj = self.container.conn.network.get_distributed_virtual_switch(self.ext_id)
            self.set_physical_entity(ext_obj)
        except:
            pass
        self.logger.warn(self.ext_obj)

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

        details: {
            "configVersion": "8",
            "date": {"created": "16-02-16 07:25:56"},
            "desc": None,
            "extensionKey": None,
            "maxPorts": 2147483647,
            "networkResourceManagementEnabled": False,
            "numPorts": 28,
            "numStandalonePorts": 0,
            "overall_status": "green",
            "switchIpAddress": None,
            "targetInfo": None,
            "uplinkPortgroup": ["dvportgroup-122"],
            "uuid": "07 ff 26 50 3d 3e c5 a9-9b b9 03 51 63 bc 65 d8"
        }
        """
        # verify permissions
        info = VsphereResource.detail(self)
        if self.ext_obj is not None:
            details = info["details"]
            data = self.container.conn.network.detail_distributed_virtual_switch(self.ext_obj)
            details.update(data)
        return info

    #
    # other info
    #
    @trace(op="runtime.use")
    def get_runtime(self):
        """Get runtime.

        :return:

            [
                {
                    "detail": None,
                    "host": {
                        "id": 1036,
                        "name": "esx6-r610-n01.nuvolacsi.it"
                    },
                    "status": "up"
                },..
            ]

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("use")

        try:
            res = []
            datas = self.ext_obj.runtime.hostMemberRuntime
            for data in datas:
                info = {"status": data.status, "detail": data.statusDetail}

                host = data.host
                try:
                    hid = self.container.get_hosts(ext_id=host._moId)[0].oid
                except:
                    hid = None

                info["host"] = {"name": host.name, "id": hid}
                res.append(info)

            self.logger.debug("Get distributed virtual switch %s runtime: %s..." % (self.oid, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    @trace(op="portgroups.use")
    def get_portgroups(self):
        """Get portgroup.

        :return:

            [
                {
                    "autoExpand": True,
                    "configVersion": "0",
                    "description": None,
                    "ext_id": "dvportgroup-123",
                    "id": 979,
                    "name": "CARBON_dvpg-510_Vmotion",
                    "numPorts": 8,
                    "portKeys": ["2", "3", "4", "5", "6", "7", "8", "9"],
                    "type": "earlyBinding",
                    "vlan": 510
                },..
            ]

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("use")

        try:
            res = []
            ports = self.ext_obj.portgroup
            for port in ports:
                try:
                    pid = self.container.get_networks(ext_id=port.key)[0].oid
                except:
                    pid = None

                info = {
                    "id": pid,
                    "ext_id": port.key,
                    "name": port.config.name,
                    "portKeys": port.portKeys,
                    "autoExpand": port.config.autoExpand,
                    "configVersion": port.config.configVersion,
                    "description": port.config.description,
                    "numPorts": port.config.numPorts,
                    "type": port.config.type,
                    "vlan": port.config.defaultPortConfig.vlan.vlanId,
                }

                res.append(info)

            self.logger.debug("Get distributed virtual switch %s portgroup: %s..." % (self.oid, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)
