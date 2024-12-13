# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.plugins.vsphere.entity import NsxResource
from beehive_resource.plugins.vsphere.entity import get_task
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup


class NsxIpSet(NsxResource):
    objdef = "Vsphere.Nsx.IpSet"
    objuri = "nsx_ipsets"
    objname = "nsx_ipset"
    objdesc = "Vsphere Nsx ipset"

    default_tags = ["vsphere", "network"]
    task_path = "beehive_resource.plugins.vsphere.task_v2.nsx_ipset.NsxIpsetTask."

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
        ipsets = container.conn.network.nsx.ipset.list()
        for ipset in ipsets:
            items.append((ipset["objectId"], ipset["name"], nsx_manager_id, None))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = NsxIpSet
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
        ipsets = container.conn.network.nsx.ipset.list()
        for ipset in ipsets:
            items.append(
                {
                    "id": ipset["objectId"],
                    "name": ipset["name"],
                }
            )

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
        remote_entities = container.conn.network.nsx.ipset.list()

        # create index of remote objs
        remote_entities_index = {i["objectId"]: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn("", exc_info=True)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.network.nsx.ipset.get(self.ext_id)
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
        objid = "%s//%s" % (manager.objid, id_gen())

        kvargs.update(
            {
                "objid": objid,
                "parent": manager.oid,
            }
        )

        steps = [
            NsxIpSet.task_path + "create_resource_pre_step",
            NsxIpSet.task_path + "nsx_ipset_create_step",
            NsxIpSet.task_path + "create_resource_post_step",
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
            NsxIpSet.task_path + "update_resource_pre_step",
            NsxIpSet.task_path + "update_resource_post_step",
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
            NsxIpSet.task_path + "expunge_resource_pre_step",
            NsxIpSet.task_path + "nsx_ipset_delete_step",
            NsxIpSet.task_path + "expunge_resource_post_step",
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
        try:
            if self.ext_obj is not None:
                info["details"] = {"cidr": self.ext_obj.get("value", "")}
        except Exception as ex:
            self.logger.warning(ex, exc_info=True)
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
                details = {
                    "scope": {
                        "id": self.ext_obj["scope"]["id"],
                        "name": self.ext_obj["scope"]["name"],
                        "type": self.ext_obj["scope"]["objectTypeName"],
                    },
                    "revision": self.ext_obj["revision"],
                    "client_handle": self.ext_obj["clientHandle"],
                    "extended_attributes": self.ext_obj["extendedAttributes"],
                    "is_universal": self.ext_obj["isUniversal"],
                    "universal_revision": self.ext_obj["universalRevision"],
                    "inheritance_allowed": self.ext_obj["inheritanceAllowed"],
                    "cidr": self.ext_obj.get("value", ""),
                }
                info["details"] = details
        except Exception as ex:
            self.logger.warn(ex, exc_info=True)

        return info

    def has_security_group(self, security_group_id):
        """Check security group is attached to ipset

        :param security_group_id: security group id to check
        :return: True
        :raise ApiManagerError:
        """
        ext_obj = self.container.conn.network.nsx.sg.get(security_group_id)
        data = self.container.conn.network.nsx.sg.info(ext_obj)
        members = data.pop("member", [])
        if isinstance(members, dict):
            members = [members]

        for member in members:
            if self.ext_id == member["objectId"]:
                return True
        return False

    @trace(op="update")
    def add_security_group(self, *args, **kvargs):
        """Add security group to nsx ipset

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(kvargs["security_group"], entity_class=NsxSecurityGroup)
            kvargs["security_group"] = security_group.ext_id
            return kvargs

            # if self.has_security_group(security_group.oid) is False:
            #     # security_group.check_active()
            #     kvargs['security_group'] = security_group.oid
            #     return kvargs
            # else:
            #     raise ApiManagerError('security group %s is already attached to port %s' %
            #                           (security_group.oid, self.oid))

        steps = ["beehive_resource.plugins.vsphere.task_v2.nsx_ipset.NsxIpsetTask.ipset_add_security_group_step"]
        res = self.action(
            "add_security_group",
            steps,
            log="Add security group to nsx ipset",
            check=check,
            **kvargs,
        )
        return res

    @trace(op="update")
    def del_security_group(self, *args, **kvargs):
        """Remove security group from nsx ipset

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(kvargs["security_group"], entity_class=NsxSecurityGroup)
            kvargs["security_group"] = security_group.ext_id
            return kvargs
            # if self.has_security_group(security_group.oid) is True:
            #     kvargs['security_group'] = security_group.oid
            #     return kvargs
            # else:
            #     raise ApiManagerError('security group %s is not attached to port %s' % (security_group.oid, self.oid))

        steps = ["beehive_resource.plugins.vsphere.task_v2.nsx_ipset.NsxIpsetTask.ipset_del_security_group_step"]
        res = self.action(
            "del_security_group",
            steps,
            log="Remove security group from nsx ipset",
            check=check,
            **kvargs,
        )
        return res
