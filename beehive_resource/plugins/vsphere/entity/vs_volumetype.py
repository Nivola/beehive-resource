# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import truncate
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import VsphereResource


class VsphereVolumeType(VsphereResource):
    objdef = 'Vsphere.DataCenter.VolumeType'
    objuri = 'volumetypes'
    objname = 'volumetype'
    objdesc = 'Vsphere volumetypes'

    default_tags = ['vsphere', 'volumetype']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.vs_volumetype.VolumeTypeTask.'

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
        :raise ApiManagerError:
        """
        # add new item to final list
        res = []
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
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
            'resource_class': resclass,
            'objid': objid,
            'name': name,
            'ext_id': ext_id,
            'active': True,
            'desc': resclass.objdesc,
            'attrib': {},
            'parent': parent_id,
            'tags': resclass.default_tags
        }
        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

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
        :param kvargs.disk_iops: disk iops
        :return: kvargs
        :raise ApiManagerError:
        """
        # get datacenter
        from .vs_datacenter import VsphereDatacenter

        parent = controller.get_simple_resource(kvargs.get('parent'), entity_class=VsphereDatacenter)
        kvargs['parent'] = parent.oid
        kvargs['attribute'] = {
            'disk_iops': kvargs.pop('disk_iops')
        }

        steps = [
            VsphereVolumeType.task_path + 'create_resource_pre_step',
            VsphereVolumeType.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    #
    # info
    #
    def info(self):
        """Get infos.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        info = VsphereResource.info(self)
        info['details'] = self.get_attribs()
        return info

    def detail(self):
        """Get details.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = VsphereResource.detail(self)
        info['details'] = self.get_attribs()
        return info

    def add_datastore(self, datastore, tag):
        """Add datastore to volumetype

        :param datastore: datastore id, uuid or name
        :param tag: datastore tag
        :return: True
        :raise ApiManagerError:
        """
        # get datastore
        datastore = self.controller.get_simple_resource(datastore)

        # check datastore already linked
        links, tot = self.controller.get_links(end_resource=datastore.oid, start_resource=self.oid)
        if tot > 0:
            raise ApiManagerError('Datastore %s already linked to volumetype %s' % (datastore.uuid, self.uuid))

        # link datastore
        self.add_link('%s-%s-ds-link' % (self.oid, datastore.oid), 'datastore.%s' % tag, datastore.oid,
                      attributes={})

        self.logger.debug('Add datastore %s to volumetype %s with tag %s' % (datastore.uuid, self.uuid, tag))

        return True

    def del_datastore(self, datastore):
        """Del datastore from volumetype

        :param datastore: datastore id, uuid or name
        :return: True
        :raise ApiManagerError:
        """
        # get datastore
        datastore = self.controller.get_simple_resource(datastore)

        # check datastore already linked
        links, tot = self.controller.get_links(end_resource=datastore.oid, start_resource=self.oid)
        if tot == 0:
            raise ApiManagerError('Datastore %s is not linked to volumetype %s' % (datastore.uuid, self.uuid))

        # delete link
        links[0].expunge()

        self.logger.debug('Remove datastore %s from volumetype %s' % (datastore.uuid, self.uuid))

        return True

    def get_datastores(self, tag=None):
        """Get datastores linked to a volumetype

        :param tag: datastore tag [optional]
        :return: True
        :raise ApiManagerError:
        """
        res = []

        link_type = 'datastore.'
        if tag is not None:
            link_type += tag
        else:
            link_type += '%'

        # get links
        links, tot = self.controller.get_links(start_resource=self.oid, type=link_type, size=-1)

        for link in links:
            ds = link.get_end_resource()
            ds.post_get()
            ds_tag = link.type.split('.')[1]
            res.append((ds, ds_tag))

        self.logger.debug('Get datastores for volumetype %s: %s' % (self.uuid, truncate(res)))

        return res

    def has_datastore(self, datastore):
        """Check if volume type ha datastore conencted

        :param datastore: datastore name
        :return: True
        :raise ApiManagerError:
        """
        link_type = 'datastore.%'

        # get links
        links, tot = self.controller.get_links(start_resource=self.oid, type=link_type, size=-1)

        for link in links:
            ds = link.get_end_resource()
            if ds.name == datastore:
                self.logger.debug('Volume type %s has datastore %s' % (self.uuid, datastore))
                return True

        self.logger.debug('Volume type %s has not datastore %s' % (self.uuid, datastore))
        return False

    def get_best_datastore(self, size, tag=None):
        """Get best datastore to use

        :param tag: datastore tag [optional]
        :param size: available size required in the datastore
        :return: True
        :raise ApiManagerError:
        """
        res = []

        link_type = 'datastore.'
        if tag is not None:
            link_type += tag
        else:
            link_type += '%'

        # get links
        links, tot = self.controller.get_links(start_resource=self.oid, type=link_type, size=-1)

        best_datastore = None
        for link in links:
            datastore = link.get_end_resource()
            datastore.post_get()
            if datastore.get_free_space() > size:
                best_datastore = datastore
                break

        if best_datastore is None:
            raise ApiManagerError('No available datastore was found for requested size of %s' % size)

        self.logger.debug('Get best datastores: %s' % best_datastore.uuid)

        return best_datastore
