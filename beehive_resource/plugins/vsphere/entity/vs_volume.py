# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType
from beecell.simple import str2bool
from beehive.common.data import trace


class VsphereVolume(VsphereResource):
    objdef = 'Vsphere.DataCenter.Folder.volume'
    objuri = 'volumes'
    objname = 'volume'
    objdesc = 'Vsphere volumes'

    default_tags = ['vsphere', 'volume']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.vs_volume.VolumeTask.'

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
        :param kvargs.size: disk size
        :param kvargs.source_volid: The UUID of the source volume. The API creates a new volume with the same size as
            the source volume. [optional]
        :param kvargs.multiattach: To enable this volume to attach to more than one server, set this value to true.
            Default is false. [optional] [todo]
        :param kvargs.snapshot_id: To create a volume from an existing snapshot, specify the UUID of the volume
            snapshot. The volume is created in same availability zone and with same size as the snapshot. [optional]
        :param kvargs.imageRef: The UUID of the image from which you want to create the volume. Required to create a
            bootable volume. [optional]
        :param kvargs.volume_type: disk volume_type
        :param kvargs.metadata: disk metadata
        :return: kvargs
        :raise ApiManagerError:
        """
        from .vs_server import VsphereServer

        volume_type = container.get_simple_resource(kvargs.get('volume_type'), entity_class=VsphereVolumeType)
        bootable = False

        # get image
        if kvargs.get('imageRef', None) is not None:
            obj = container.get_simple_resource(kvargs.get('imageRef'), entity_class=VsphereServer)
            kvargs['image'] = obj.uuid
            bootable = True

        # get source_volid
        if kvargs.get('source_volid', None) is not None:
            obj = container.get_simple_resource(kvargs.get('source_volid'), entity_class=VsphereVolume)
            kvargs['volume'] = obj.uuid
            bootable = obj.is_bootable()

        kvargs['attribute'] = {
            'size': kvargs.pop('size'),
            'volume_type': volume_type.uuid,
            'metadata': kvargs.pop('metadata', {}),
            'source_volume': kvargs.pop('volume', None),
            'source_image': kvargs.pop('image', None),
            'bootable': bootable,
            'encrypted': False
        }

        steps = [
            VsphereVolume.task_path + 'create_resource_pre_step',
            VsphereVolume.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs = VsphereResource.pre_update(self, *args, **kvargs)

        kvargs['attribute'] = {
            'size': kvargs.pop('size', None),
            'metadata': kvargs.pop('metadata', None),
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
        """
        info = VsphereResource.info(self)
        info['details'] = self.get_attribs()
        info['details']['status'] = 'available'
        if self.ext_id is not None and self.ext_id != '':
            info['details']['status'] = 'in-use'
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = VsphereResource.detail(self)
        info['details'] = self.get_attribs()
        info['details']['status'] = 'available'
        if self.ext_id is not None and self.ext_id != '':
            info['details']['status'] = 'in-use'
        return info

    def get_size(self):
        """Get size

        :return: volume size
        """
        return int(self.get_attribs('size'))

    def is_bootable(self):
        """Get bootable attribute

        :return: volume bootable
        """
        return str2bool(self.get_attribs('bootable'))

    def get_disk_index(self):
        """Get disk index

        :return: disk index
        """
        return self.name.split('-')[-1]

    def is_encrypted(self):
        """Get encrypted attribute

        :return: volume encrypted
        """
        return str2bool(self.get_attribs('encrypted'))

    def get_volume_type(self):
        """Get volume type

        :return: volume type
        """
        return self.container.get_resource(self.get_attribs('volume_type'))

    #
    # snapshot
    #
    @trace(op='use')
    def exist_snapshot(self, snapshot_id):
        """Check volume snapshot exists

        :param snapshot_id: The uuid of the snapshot.
        :return: True
        :raise ApiManagerError:
        """
        return False

    @trace(op='use')
    def list_snapshots(self):
        """List volume snapshots

        :return: snapshot
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        res = []

        self.logger.debug('Get vsphere volume %s snapshot: %s' % (self.uuid, res))
        return res
