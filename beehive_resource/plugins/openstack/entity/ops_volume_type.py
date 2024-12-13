# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beecell.simple import truncate, get_value, id_gen, dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task


class OpenstackVolumeType(OpenstackResource):
    objdef = "Openstack.VolumeType"
    objuri = "volumetypes"
    objname = "volumetype"
    objdesc = "Openstack volumetypes"

    default_tags = ["openstack", "volumetype"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_volumetype.VolumeTypeTask."

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
        # get volumetypes from openstack
        if ext_id is not None:
            items = container.conn.volume_v3.type.get(ext_id)
        else:
            items = container.conn.volume_v3.type.list()

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                parent_id = None
                name = item["name"]
                res.append(
                    (
                        OpenstackVolumeType,
                        item["id"],
                        parent_id,
                        OpenstackVolumeType.objdef,
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
        :raise ApiManagerError:
        """
        return container.conn.volume_v3.type.list()

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
        parent_id = None

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
        remote_entities = container.conn.volume_v3.type.list()

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
        try:
            ext_obj = self.container.conn.volume_v3.type.get(self.ext_id)
            self.set_physical_entity(ext_obj)
        except:
            pass

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data["qos_specs_id"] = self.ext_obj.get("qos_specs_id")
            data["extra_specs"] = self.ext_obj.get("extra_specs")
            data["is_public"] = self.ext_obj.get("is_public")
            info["details"] = data

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            data["qos_specs_id"] = self.ext_obj.get("qos_specs_id")
            data["extra_specs"] = self.ext_obj.get("extra_specs")
            data["is_public"] = self.ext_obj.get("is_public")
            info["details"] = data

        return info

    def get_backend(self):
        """get storage backend"""
        backend = {}
        if self.ext_obj is not None:
            backend_name = dict_get(self.ext_obj, "extra_specs.volume_backend_name")
            backend = self.container.conn.volume_v3.get_backend_storage_pools(backend_name=backend_name)[0]
        self.logger.debug("get volume type %s backend: %s" % (self.oid, backend))
        return backend
