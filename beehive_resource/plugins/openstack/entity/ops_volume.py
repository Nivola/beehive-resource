# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from ast import Try
from beecell.simple import truncate, get_value, id_gen, str2bool, dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity import OpenstackResource
from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive.common.data import trace, operation
from beehive_resource.plugins.openstack.entity.ops_volume_type import OpenstackVolumeType


class OpenstackVolume(OpenstackResource):
    objdef = 'Openstack.Domain.Project.Volume'
    objuri = 'volumes'
    objname = 'volume'
    objdesc = 'Openstack volumes'

    default_tags = ['openstack', 'volume']
    task_path = 'beehive_resource.plugins.openstack.task_v2.ops_volume.VolumeTask.'

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.actions = {
            'set_flavor': self.set_flavor,
        }

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param kvargs.container.conn: client used to comunicate with remote platform
        :param kvargs.ext_id: remote platform entity id
        :param kvargs.res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, level)
        :raise ApiManagerError:
        """
        # get volumes from openstack
        if ext_id is not None:
            items = container.conn.volume_v3.get(oid=ext_id)
        else:
            items = container.conn.volume_v3.list_all(detail=True, limit=250)
            # items = container.conn.volume_v3.list(all_tenants=True, detail=True)

        # add new item to final list
        res = []
        for item in items:
            if item['id'] not in res_ext_ids:
                level = None
                parent_id = None
                name = item['name']
                if name is None or name == '':
                    name = item['id']
                parent_id = item['os-vol-tenant-attr:tenant_id']

                res.append((OpenstackVolume, item['id'], parent_id, OpenstackVolume.objdef, name, level))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param kvargs.container.conn: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        items = container.conn.volume_v3.list_all(detail=True, limit=1000)
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
        level = entity[5]

        # get parent project
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            if parent is not None:
                objid = '%s//%s' % (parent.objid, id_gen())
                parent_id = parent.oid
            else:
                objid = '%s//none//none//%s' % (container.objid, id_gen())
                parent_id = None
        else:
            objid = '%s//none//none//%s' % (container.objid, id_gen())
            parent_id = None

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

        :param kvargs.controller: controller instance
        :param kvargs.entities: list of entities
        :param kvargs.container: container instance
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :return: entities
        :raise ApiManagerError:
        """
        # remote_entities = OpenstackVolume.list_volume(controller, container.oid, container)
        remote_volume_types = OpenstackVolume.list_remote_volume_type(controller, container.oid, container)

        # create index of remote objs
        # remote_entities_index = {i['id']: i for i in remote_entities}
        remote_volume_types_index = {i['name']: i for i in remote_volume_types}

        # get volume types
        volume_types_index = container.index_resources_by_extid(entity_class=OpenstackVolumeType)

        for entity in entities:
            ext_obj = OpenstackVolume.get_remote_volume(controller, entity.ext_id, container, entity.ext_id)
            # ext_obj = remote_entities_index.get(entity.ext_id, None)
            entity.set_physical_entity(ext_obj)
            try:
                volume_type_ext_id = remote_volume_types_index.get(ext_obj.get('volume_type'))['id']
                entity.volume_type = volume_types_index.get(volume_type_ext_id)
            except:
                entity.volume_type = None
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        try:
            remote_volume_types = self.container.conn.volume_v3.type.list()
            remote_volume_types_index = {i['name']: i for i in remote_volume_types}

            ext_obj = OpenstackVolume.get_remote_volume(self.controller, self.ext_id, self.container, self.ext_id)
            self.set_physical_entity(ext_obj)
            try:
                volume_type_ext_id = remote_volume_types_index.get(ext_obj.get('volume_type'))['id']
                self.volume_type = self.container.get_resource_by_extid(volume_type_ext_id)
            except:
                self.volume_type = None
        except:
            pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom positional params
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
        :param kvargs.size: The size of the volume, in gibibytes (GiB).
        :param kvargs.availability_zone: The availability zone. [optional]
        :param kvargs.source_volid: The UUID of the source volume. The API creates a new volume with the same size as
            the source volume. [optional]
        :param kvargs.multiattach: To enable this volume to attach to more than one server, set this value to true.
            Default is false. [optional] [todo]
        :param kvargs.snapshot_id: To create a volume from an existing snapshot, specify the UUID of the volume
            snapshot. The volume is created in same availability zone and with same size as the snapshot. [optional]
        :param kvargs.imageRef: The UUID of the image from which you want to create the volume. Required to create a
            bootable volume. [optional]
        :param kvargs.volume_type: The volume type. To create an environment with multiple-storage back ends, you must
            specify a volume type. Block Storage volume back ends are spawned as children to cinder-volume, and they
            are keyed from a unique queue. They are named cinder- volume.HOST.BACKEND. For example,
            cinder-volume.ubuntu.lvmdriver. When a volume is created, the scheduler chooses an appropriate back end
            to handle the request based on the volume type. Default is None. For information about how to use
            volume typesto create multiple-storage back ends, see Configure multiple-storage back ends. [optional]
        :param kvargs.metadata: One or more metadata key and value pairs that are associated with the volume_v3. [optional]
        :param kvargs.source_replica: The UUID of the primary volume to clone. [optional] [todo]
        :param kvargs.consistencygroup_id: The UUID of the consistency group. [optional] [todo]
        :param kvargs.scheduler_hints: The dictionary of data to send to the scheduler. [optional] [todo]
        :return: kvargs
        :raise ApiManagerError:
        """
        # set project
        parent = kvargs.get('parent')
        parent = controller.get_resource(parent)
        kvargs['project_extid'] = parent.ext_id

        obj = container.get_resource(kvargs.get('volume_type'), entity_class=OpenstackVolumeType)
        kvargs['volume_type'] = obj.oid

        # get image
        if kvargs.get('imageRef') is not None:
            obj = container.get_resource(kvargs.get('imageRef'), entity_class=OpenstackImage)
            kvargs['image'] = obj.ext_id

        # get source_volid
        if kvargs.get('source_volid') is not None:
            obj = controller.get_resource(kvargs.get('source_volid'), entity_class=OpenstackVolume)
            kvargs['source_volid'] = obj.oid

        # # get snapshot_id
        # if kvargs.get('snapshot_id') is not None:
        #     obj = container.get_resource(kvargs.get('snapshot_id'), entity_class=OpenstackVolume)
        #     kvargs['snapshot'] = obj.ext_id

        # get availability_zone
        availability_zone = get_value(kvargs, 'availability_zone', None)
        zones = {z['zoneName'] for z in container.system.get_compute_zones()}
        if availability_zone not in zones:
            raise ApiManagerError('Openstack availability_zone %s does not exist' % availability_zone, code=404)
        kvargs['availability_zone'] = availability_zone

        steps = [
            OpenstackVolume.task_path + 'create_resource_pre_step',
            OpenstackVolume.task_path + 'volume_create_physical_step',
            OpenstackVolume.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackVolume.task_path + 'update_resource_pre_step',
            OpenstackVolume.task_path + 'volume_update_physical_step',
            OpenstackVolume.task_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs['parent_id'] = self.parent_id
        steps = [
            OpenstackVolume.task_path + 'expunge_resource_pre_step',
            OpenstackVolume.task_path + 'volume_expunge_physical_step',
            OpenstackVolume.task_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    #
    # info
    #
    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        operation.cache = False
        self.container = self.controller.get_container(self.container_id)
        ext_obj = OpenstackVolume.get_remote_volume(self.controller, self.ext_id, self.container, self.ext_id)
        if ext_obj != {}:
            res = {'check': True, 'msg': None}
        else:
            res = {'check': False, 'msg': 'no remote volume found'}
        self.logger.debug2('Check resource %s: %s' % (self.uuid, res))
        return res

    def info(self):
        """Get infos.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data['volume_type'] = getattr(self.volume_type, 'uuid', None)
            data['attachments'] = self.ext_obj.get('attachments')
            data['bootable'] = self.ext_obj.get('bootable')
            data['encrypted'] = self.ext_obj.get('encrypted')
            data['size'] = self.ext_obj.get('size')
            data['status'] = self.ext_obj.get('status')

            info['details'] = data

        return info

    def detail(self):
        """Get details.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            data['volume_type'] = getattr(self.volume_type, 'uuid', None)
            data['attachments'] = self.ext_obj.get('attachments')
            data['bootable'] = self.ext_obj.get('bootable')
            data['encrypted'] = self.ext_obj.get('encrypted')
            data['size'] = self.ext_obj.get('size')
            data['status'] = self.ext_obj.get('status')

            info['details'].update(data)
        return info

    def get_size(self):
        """Get size

        :return: volume size
        """
        if self.ext_obj is not None:
            ret = self.ext_obj.get('size')
            if isinstance(ret, int):
                return ret
            elif isinstance(ret, float):
                return ret
            elif isinstance(ret, str):
                s: str = ret
                try:
                    ret = int(s)
                    return ret
                except ValueError as ex:
                    try:
                        ret = float(s)
                        return ret
                    except ValueError as ex:
                        return 0
            else:
                return 0
            # return self.ext_obj.get('size')
        else:
            return 0

    def get_volume_type(self):
        """Get volume type

        :return: volume type
        """
        return self.volume_type

    def is_bootable(self):
        """Get bootable attribute

        :return: volume bootable
        """
        if self.ext_obj is not None:
            return str2bool(self.ext_obj.get('bootable'))
        else:
            return False

    def get_disk_index(self):
        """Get disk index

        :return: disk index
        """
        return None

    def is_encrypted(self):
        """Get encrypted attribute

        :return: volume encrypted
        """
        if self.ext_obj is not None:
            return str2bool(self.ext_obj.get('encrypted'))
        else:
            return False

    @trace(op='use')
    def get_metadata(self):
        """Lists the metadata for a specified volume instance.

        :return: metadata list
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        try:
            res = self.container.conn.volume_v3.get_metadata(self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Get openstack volume %s metadata: %s' % (self.uuid, res))
        return res

    @trace(op='use')
    def get_image_metadata(self):
        """Lists the image metadata for a specified volume instance.

        :return: metadata list
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        try:
            res = self.container.conn.volume_v3.show_image_metadata(self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Get openstack volume %s image metadata: %s' % (self.uuid, res))
        return res

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
        try:
            self.container.conn.volume_v3.snapshot.get(snapshot_id)
        except Exception as ex:
            err = 'Openstack volume %s snapshot does not exist: %s' % (self.uuid, snapshot_id)
            self.logger.error(err)
            raise ApiManagerError(err)

        return True

    @trace(op='use')
    def list_snapshots(self):
        """List volume snapshots

        :return: snapshot
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        try:
            all_snapshots = OpenstackVolume.list_remote_volume_snapshots(self.controller, self.container.oid,
                                                                         self.container, None)
            res = []
            for item in all_snapshots:
                if item['volume_id'] == self.ext_id:
                    item['volume_id'] = self.uuid
                    res.append(item)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Get openstack volume %s snapshots: %s' % (self.uuid, truncate(res)))
        return res

    @trace(op='use')
    def get_snapshot(self, snapshot_id):
        """Get volume snapshot

        :param snapshot_id: snapshot id
        :return: snapshot
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        try:
            res = self.container.conn.volume_v3.snapshot.get(snapshot_id)
            res['volume_id'] = self.uuid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Get openstack volume %s snapshot: %s' % (self.uuid, res))
        return res

    @trace(op='use')
    def add_snapshot(self, name):
        """Add volume snapshot

        :param name: snapshot name
        :return: snapshot
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        try:
            res = self.container.conn.volume_v3.snapshot.create(name, force=True, volume_id=self.ext_id)
            res['volume_id'] = self.uuid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Add openstack volume %s snapshot: %s' % (self.uuid, res))
        return res

    @trace(op='use')
    def delete_snapshot(self, snapshot_id):
        """Delete volume snapshot

        :param snapshot_id: The uuid of the snapshot.
        :return: snapshot
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        self.exist_snapshot(snapshot_id)

        try:
            res = self.container.conn.volume_v3.snapshot.delete(snapshot_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Delete openstack volume %s snapshot: %s' % (self.uuid, snapshot_id))
        return res

    @trace(op='use')
    def revert_snapshot(self, snapshot_id):
        """Revert volume to snapshot

        :param snapshot_id: The uuid of the snapshot.
        :return: snapshot
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        self.exist_snapshot(snapshot_id)

        try:
            res = self.container.conn.volume_v3.snapshot.revert_to(self.ext_id, snapshot_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Revert openstack volume %s to snapshot: %s' % (self.uuid, snapshot_id))
        return res

    #
    # clone
    #
    @trace(op='update')
    def clone(self, name, project):
        """Clone volume

        :param name: cloned volume name
        :param project: cloned volume project id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            from .ops_project import OpenstackProject

            parent_project = self.container.get_simple_resource(project, entity_class=OpenstackProject)
            kvargs['cloned_name'] = name
            kvargs['parent_id'] = parent_project.oid
            return kvargs

        steps = [
            OpenstackVolume.task_path + 'volume_clone_step',
        ]
        res = self.action('clone_volume', steps, log='Clone volume', check=check)
        return res

    #
    # actions
    #
    @trace(op='update')
    def set_flavor(self, *args, **kvargs):
        """Set volume type to volume.

        :param flavor: flavor uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            flavor = self.container.get_simple_resource(kvargs['flavor'], entity_class=OpenstackVolumeType)
            kvargs['flavor'] = flavor.ext_id
            if self.volume_type is None:
                raise ApiManagerError('flavor %s is not assigned to volume %s' % self.oid)
            if self.volume_type.oid == flavor.oid:
                raise ApiManagerError('flavor %s already assigned to volume %s' % (flavor.oid, self.oid))

            return kvargs

        steps = [OpenstackVolume.task_path + 'volume_set_flavor_step']
        res = self.action('set_flavor', steps, log='Set volume type to volume', check=check, **kvargs)
        return res
