# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity import VsphereResource


class VsphereFlavor(VsphereResource):
    objdef = "Vsphere.DataCenter.Flavor"
    objuri = "flavors"
    objname = "flavor"
    objdesc = "Vsphere flavors"

    default_tags = ["vsphere", "flavor"]
    task_path = "beehive_resource.plugins.vsphere.task_v2.vs_flavor.FlavorTask"
    create_task = None
    import_task = None
    update_task = None
    patch_task = None
    delete_task = None
    expunge_task = None
    action_task = None

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
        # add new item to final list
        res = []
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        items = []
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

        objid = None

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
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
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
        :param kvargs.core_x_socket: core per socket [default=1]
        :param kvargs.vcpus: socket number
        :param kvargs.guest_id: vsphere guest id [default=centos64Guest]
        :param kvargs.ram: ram size in GB
        :param kvargs.disk: main disk size in GB
        :param kvargs.version: virtual machine version [default=vmx-11]
        :return: kvargs
        :raises ApiManagerError:
        """
        kvargs = VsphereResource.pre_create(controller, container, *args, **kvargs)

        # get datacenter
        from .vs_datacenter import VsphereDatacenter

        parent = controller.get_simple_resource(kvargs.get("parent"), entity_class=VsphereDatacenter)
        kvargs["parent"] = parent.oid
        kvargs["attribute"] = {
            "core_x_socket": kvargs.pop("core_x_socket"),
            "vcpus": kvargs.pop("vcpus"),
            "guest_id": kvargs.pop("guest_id"),
            "ram": kvargs.pop("ram"),
            "disk": kvargs.pop("disk"),
            "version": kvargs.pop("version"),
        }
        return kvargs

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`

        details: {
            'core_x_socket': 1,
            'vcpus': 2,
            'guest_id': 'centos64Guest',
            'ram': 1024,
            'version': 'vmx-11',
            'disk': 10
        }
        """
        info = VsphereResource.info(self)
        info["details"] = self.get_attribs()
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`

        details: {
            'core_x_socket': 1,
            'vcpus': 2,
            'guest_id': 'centos64Guest',
            'ram': 1024,
            'version': 'vmx-11',
            'disk': 10
        }
        """
        # verify permissions
        info = VsphereResource.detail(self)
        info["details"] = self.get_attribs()
        return info

    # def add_datastore(self, datastore, tag):
    #     """Add datastore to flavor
    #
    #     **Parameters:**
    #
    #         * **datastore** (:py:class:`str`): datastore id, uuid or name
    #         * **tag** (:py:class:`str`): datastore tag
    #
    #     **Returns:**
    #
    #         True
    #
    #     :raises ApiManagerError: raise :class:`.ApiManagerError`
    #     """
    #     # get datastore
    #     datastore = self.controller.get_resource(datastore)
    #
    #     # check datastore already linked
    #     links, tot = self.controller.get_links(end_resource=datastore.oid, start_resource=self.oid)
    #     if tot > 0:
    #         raise ApiManagerError('Datastore %s already linked to flavor %s' % (datastore.uuid, self.uuid))
    #
    #     # link datastore
    #     self.add_link('%s-%s-ds-link' % (self.oid, datastore.oid), 'datastore.%s' % tag, datastore.oid,
    #                   attributes={})
    #
    #     self.logger.debug('Add datastore %s to flavor %s with tag %s' % (datastore.uuid, self.uuid, tag))
    #
    #     return True
    #
    # def del_datastore(self, datastore):
    #     """Del datastore from flavor
    #
    #     **Parameters:**
    #
    #         * **datastore** (:py:class:`str`): datastore id, uuid or name
    #
    #     **Returns:**
    #
    #         True
    #
    #     :raises ApiManagerError: raise :class:`.ApiManagerError`
    #     """
    #     # get datastore
    #     datastore = self.controller.get_resource(datastore)
    #
    #     # check datastore already linked
    #     links, tot = self.controller.get_links(end_resource=datastore.oid, start_resource=self.oid)
    #     if tot == 0:
    #         raise ApiManagerError('Datastore %s is not linked to flavor %s' % (datastore.uuid, self.uuid))
    #
    #     # delete link
    #     links[0].delete()
    #
    #     self.logger.debug('Remove datastore %s from flavor %s' % (datastore.uuid, self.uuid))
    #
    #     return True
    #
    # def get_datastores(self, tag=None):
    #     """Get datastores linked to a flavor
    #
    #     **Parameters:**
    #
    #         * **tag** (:py:class:`str`): datastore tag [optional]
    #
    #     **Returns:**
    #
    #         True
    #
    #     :raises ApiManagerError: raise :class:`.ApiManagerError`
    #     """
    #     res = []
    #
    #     link_type = 'datastore.'
    #     if tag is not None:
    #         link_type += tag
    #     else:
    #         link_type += '%'
    #
    #     # get links
    #     links, tot = self.controller.get_links(start_resource=self.oid, type=link_type)
    #
    #     for link in links:
    #         ds = link.get_end_resource()
    #         ds_tag = link.type.split('.')[1]
    #         res.append((ds, ds_tag))
    #
    #     self.logger.debug('Get datastores for flavor %s: %s' % (self.uuid, truncate(res)))
    #
    #     return res
