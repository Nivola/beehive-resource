# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster
from beehive_resource.plugins.vsphere.entity.vs_datastore import VsphereDatastore
from beehive_resource.plugins.vsphere.entity.vs_dvs import VsphereDvs
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.plugins.vsphere.entity.vs_pg import VspherePg
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType


class VsphereDatacenter(VsphereResource):
    objdef = "Vsphere.DataCenter"
    objuri = "datacenters"
    objname = "datacenter"
    objdesc = "Vsphere datacenters"

    default_tags = ["vsphere"]

    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = [
            VsphereFolder,
            VsphereCluster,
            VsphereDatastore,
            VspherePg,
            VsphereDvs,
            VsphereDvpg,
            VsphereFlavor,
            VsphereVolumeType,
        ]

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
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []
        for datacenter in datacenters:
            items.append((datacenter._moId, datacenter.name, None, None))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereDatacenter
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
            items.append(
                {
                    "id": datacenter._moId,
                    "name": datacenter.name,
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

        # get parent folder
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            parent_id = parent.oid
            objid = parent.objid + "." + id_gen()
        else:
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
        remote_entities = container.conn.datacenter.list()

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
            ext_obj = self.container.conn.datacenter.get(self.ext_id)
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
        info = VsphereResource.info(self)

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = VsphereResource.detail(self)
        details = info["details"]
        if self.ext_obj is not None:
            details.update(self.container.conn.datacenter.info(self.ext_obj))

        return info
