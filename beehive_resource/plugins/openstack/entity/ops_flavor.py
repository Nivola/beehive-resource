# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task


class OpenstackFlavor(OpenstackResource):
    objdef = "Openstack.Flavor"
    objuri = "flavors"
    objname = "flavor"
    objdesc = "Openstack flavors"

    default_tags = ["openstack"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_flavor.FlavorTask."

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

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
        # get from openstack
        if ext_id is not None:
            items = container.conn.flavor.get(oid=ext_id)
        else:
            items = container.conn.flavor.list()

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = None

                res.append(
                    (
                        OpenstackFlavor,
                        item["id"],
                        parent_id,
                        OpenstackFlavor.objdef,
                        name,
                        level,
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
        items = container.conn.flavor.list()

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
        remote_entities = container.conn.flavor.list(detail=True)

        # create index of remote objs
        remote_entities_index = {i["id"]: i for i in remote_entities}

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
        ext_obj = self.get_remote_flavor(self.controller, self.ext_id, self.container, self.ext_id)
        # ext_obj = self.container.conn.server.get(oid=self.ext_id)
        self.set_physical_entity(ext_obj)

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
            OpenstackFlavor.task_path + "create_resource_pre_step",
            OpenstackFlavor.task_path + "flavor_create_physical_step",
            OpenstackFlavor.task_path + "create_resource_post_step",
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
            OpenstackFlavor.task_path + "update_resource_pre_step",
            OpenstackFlavor.task_path + "flavor_update_physical_step",
            OpenstackFlavor.task_path + "update_resource_post_step",
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
            OpenstackFlavor.task_path + "expunge_resource_pre_step",
            OpenstackFlavor.task_path + "flavor_delete_physical_step",
            OpenstackFlavor.task_path + "expunge_resource_post_step",
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
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data["is_public"] = self.ext_obj.get("os-flavor-access:is_public", None)
            data["ram"] = self.ext_obj.get("ram", None)
            data["vcpus"] = self.ext_obj.get("vcpus", None)
            data["swap"] = self.ext_obj.get("swap", None)
            data["disk"] = self.ext_obj.get("disk", None)
            data["rxtx_factor"] = self.ext_obj.get("rxtx_factor", None)

            info["details"] = data

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            data["is_public"] = self.ext_obj.get("os-flavor-access:is_public", None)
            data["ram"] = self.ext_obj.get("ram", None)
            data["vcpus"] = self.ext_obj.get("vcpus", None)
            data["swap"] = self.ext_obj.get("swap", None)
            data["disk"] = self.ext_obj.get("disk", None)
            data["rxtx_factor"] = self.ext_obj.get("rxtx_factor", None)

            info["details"].update(data)

        return info
