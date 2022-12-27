# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import truncate, id_gen, dict_get
from beecell.types.type_id import token_gen
from json import dumps
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import run_async
from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive.common.data import trace, operation
from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster
from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType


class VsphereServer(VsphereResource):
    objdef = 'Vsphere.DataCenter.Folder.Server'
    objuri = 'servers'
    objname = 'server'
    objdesc = 'Vsphere servers'

    # html console prefix
    console_prefix = 'html5_console.'
    console_expire_time = 3600

    default_tags = ['vsphere', 'server']
    task_path = 'beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.'

    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)
        
        # child classes
        self.child_classes = []

        self.actions = {
            'start': self.start,
            'stop': self.stop,
            'reboot': self.reboot,
            # 'pause': self.pause,
            # 'unpause': self.unpause,
            # 'migrate': self.migrate,
            # 'setup_network': self.setup_network,
            # 'reset_state': self.reset_state,
            'add_snapshot': self.add_snapshot,
            'del_snapshot': self.del_snapshot,
            'revert_snapshot': self.revert_snapshot,
            'add_security_group': self.add_security_group,
            'del_security_group': self.del_security_group,
            'add_volume': self.add_volume,
            'del_volume': self.del_volume,
            'set_flavor': self.set_flavor,
        }

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
        from .vs_folder import VsphereServer
        from .vs_datacenter import VsphereDatacenter
        
        items = []

        def append_node(node, parent, parent_class):
            obj_type = type(node).__name__
            if obj_type == 'vim.Folder':
                # get childs
                if hasattr(node, 'childEntity'):
                    childs = node.childEntity
                    for c in childs:
                        append_node(c, node._moId, VsphereServer)
                        
            if obj_type == 'vim.VirtualMachine':
                # if ext_id is not None and ext_id != node._moId:
                #     pass
                if ext_id is None or (ext_id is not None and ext_id == node._moId):
                    items.append((node._moId, node.name, parent, parent_class))
        
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity        
        for datacenter in datacenters:
            append_node(datacenter.vmFolder, datacenter._moId, VsphereDatacenter)
        
        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereServer
                res.append((resclass, item[0], parent_id, resclass.objdef, item[1], parent_class))
        
        return res    

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.
        
        :param container: client used to comunicate with remote platform
        :return: list of remote entities            
        :raise ApiManagerError:
        """
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []
        
        def append_node(node):
            obj_type = type(node).__name__
            if obj_type == 'vim.Folder':
                # get childs
                if hasattr(node, 'childEntity'):
                    childs = node.childEntity
                    for c in childs:
                        append_node(c)
                        
            if obj_type == 'vim.VirtualMachine':
                items.append({
                    'id': node._moId,
                    'name': node.name,
                })
        
        for datacenter in datacenters:
            append_node(datacenter.vmFolder)
        
        return items
    
    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.
        
        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: {'resclass':, 'objid':, 'name':, 'ext_id':, 'active':, 'desc':, 'attrib':, 'parent':, 'tags':}
        :raise ApiManagerError:
        """
        from .vs_folder import VsphereServer
        
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]

        parent = container.get_resource_by_extid(parent_id)
        parent_id = parent.oid
        
        # get parent folder
        if parent_class == VsphereServer:
            objid = '%s//%s' % (parent.objid, id_gen())
        # get parent datacenter
        else:
            objid = '%s//none//%s' % (parent.objid, id_gen()) 
        
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
    def customize_list_status_info(controller, entities, container, *args, **kvargs):
        """Post list status function.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        remote_entities = container.conn.server.list()

        # create index of remote objs
        remote_entities_index = {i['obj']._moId: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn('', exc_info=1)
        return entities

    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None            
        :raise ApiManagerError:
        """
        remote_entities = container.conn.server.list()
        
        # create index of remote objs
        remote_entities_index = {i['obj']._moId: i for i in remote_entities}
        
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn('', exc_info=1)
        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        try:
            self.ext_obj = self.container.conn.server.get_by_morid(self.ext_id)
        except Exception as ex:
            self.logger.warn(ex)
        
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
        :param kvargs.accessIPv4: IPv4 address that should be used to access this server. [optional] [TODO]
        :param kvargs.accessIPv6: IPv6 address that should be used to access this server. [optional] [TODO]
        :param kvargs.imageRef: id or uuid of an image
        :param kvargs.flavorRef: server cpu, ram and operating system
        :param kvargs.adminPass: The administrative password of the server. [TODO]
        :param kvargs.availability_zone: Specify the availability zone
        :param kvargs.metadata: server metadata
        :param kvargs.metadata.template_pwd: root admin password used for guest customization
        :param kvargs.security_groups: One or more security groups.
        :param kvargs.networks: A networks object. Required parameter when there are multiple networks defined for the
            tenant. When you do not specify the networks parameter, the server attaches to the only network created
            for the current tenant. Optionally, you can create one or more NICs on the server. To provision the
            server instance with a NIC for a network, specify the UUID of the network in the uuid attribute in a
            networks object. [TODO: support for multiple network]
        :param kvargs.networks.x.uuid: is the id a tenant network.
        :param kvargs.networks.x.subnet_pool: is the id a tenant network subnet.
        :param kvargs.networks.x.fixed_ip: the network configuration. For static ip pass some fields
        :param kvargs.networks.x.fixed_ip.ip:
        :param kvargs.networks.x.fixed_ip.gw:
        :param kvargs.networks.x.fixed_ip.hostname:
        :param kvargs.networks.x.fixed_ip.dns:
        :param kvargs.networks.x.fixed_ip.dnsname:
        :param kvargs.user_data:  Configuration information or scripts to use upon launch. Must be Base64 encoded.
            [optional] Pass ssh_key using base64.b64decode({'pubkey':..})
        :param kvargs.personality: The file path and contents, text only, to inject into the server at launch.
            The maximum size of the file path data is 255 bytes. The maximum limit is The number of allowed bytes in the
            decoded, rather than encoded, data. [optional] [TODO]
        :param kvargs.block_device_mapping_v2: Enables fine grained control of the block device mapping for an instance.
        :param kvargs.block_device_mapping_v2.device_name: A path to the device for the volume that you want to use to
            boot the server. [TODO]
        :param kvargs.block_device_mapping_v2.source_type: The source type of the volume. A valid value is:
            snapshot - creates a volume backed by the given volume snapshot referenced via the
                       block_device_mapping_v2.uuid parameter and attaches it to the server
            volume: uses the existing persistent volume referenced via the block_device_mapping_v2.uuid parameter
                    and attaches it to the server
            image: creates an image-backed volume in the block storage service and attaches it to the server
        :param kvargs.block_device_mapping_v2.volume_size: size of volume in GB
        :param kvargs.block_device_mapping_v2.uuid: This is the uuid of source resource. The uuid points to different
            resources based on the source_type.
            If source_type is image, the block device is created based on the specified image which is retrieved
            from the image service.
            If source_type is snapshot then the uuid refers to a volume snapshot in the block storage service.
            If source_type is volume then the uuid refers to a volume in the block storage service.
        :param kvargs.block_device_mapping_v2.volume_type: The device volume_type. This can be used to specify the type
            of volume which the compute service will create and attach to the server. If not specified, the block
            storage service will provide a default volume type. It is only supported with source_type of image or
            snapshot.
        :param kvargs.block_device_mapping_v2.destination_type: Defines where the volume comes from. A valid value is
            local or volume. [default=volume]
        :param kvargs.block_device_mapping_v2.delete_on_termination: To delete the boot volume when the server is
            destroyed, specify true. Otherwise, specify false. [TODO]
        :param kvargs.block_device_mapping_v2.guest_format: Specifies the guest server disk file system format, such as
            ephemeral or swap. [TODO]
        :param kvargs.block_device_mapping_v2.boot_index: Defines the order in which a hypervisor tries devices when it
            attempts to boot the guest from storage. Give each device a unique boot index starting from 0. To
            disable a device from booting, set the boot index to a negative value or use the default boot index
            value, which is None. The simplest usage is, set the boot index of the boot device to 0 and use the
            default boot index value, None, for any other devices. Some hypervisors might not support booting from
            multiple devices; these hypervisors consider only the device with a boot index of 0. Some hypervisors
            support booting from multiple devices but only if the devices are of different types. For example, a
            disk and CD-ROM. [TODO]
        :param kvargs.block_device_mapping_v2.tag: An arbitrary tag. [TODO]
        :param kvargs.customization_spec_name: vsphere customization spec name to apply [default=WS201x PRVCLOUD
            custom OS sysprep]
        :return: kvargs
        :raise ApiManagerError:
        """
        # get folder
        parent = container.get_simple_resource(kvargs.get('parent'))

        # get flavor
        flavor = container.get_simple_resource(kvargs.get('flavorRef'), entity_class=VsphereFlavor)
        flavor_ref = flavor.get_attribs()
        kvargs['flavorRef'] = flavor_ref

        # get resource pool
        obj = container.get_simple_resource(kvargs.get('availability_zone'), entity_class=VsphereCluster)
        kvargs['availability_zone'] = obj.oid

        # set main volume
        # main_datastore = flavor.get_datastores(tag='default')
        main_volume = {
            'boot_index': 0,
            'tag': None,
            'source_type': 'image',
            'volume_size': flavor_ref['disk'],
            'destination_type': 'volume',
        }
        volumes = [main_volume]

        # get volumes
        block_devices = kvargs.get('block_device_mapping_v2')
        for block_device in block_devices:
            boot_index = block_device.get('boot_index', None)
            source_type = block_device.get('source_type')

            if source_type == 'image':
                obj = container.get_simple_resource(block_device['uuid'], entity_class=VsphereServer)
                block_device['uuid'] = obj.oid
                min_disk_size = obj.get_min_disk()

                obj = container.get_simple_resource(block_device.get('volume_type'), entity_class=VsphereVolumeType)
                block_device['volume_type'] = obj.oid

                if boot_index == 0:
                    if min_disk_size > 0 and block_device.get('volume_size') < min_disk_size:
                        block_device['volume_size'] = min_disk_size
                else:
                    raise ApiManagerError('Source type image is supported only for boot volume')

            elif source_type == 'volume':
                obj = container.get_simple_resource(block_device['uuid'], entity_class=VsphereVolume)
                if obj.parent_id != parent.oid:
                    raise ApiManagerError('Volume folder is different from server folder')
                if boot_index == 0 and obj.is_bootable() is False:
                    raise ApiManagerError('Volume is not bootable')
                block_device['uuid'] = obj.oid

            # reconfigure main disk
            if boot_index == 0:
                volumes[0].update(block_device)

            # add new disk
            else:
                volumes.append(block_device)
        kvargs['block_device_mapping_v2'] = volumes
        
        # get networks
        networks = kvargs.get('networks')
        for network in networks:
            obj = container.get_simple_resource(network.get('uuid'), entity_class=VsphereDvpg)
            network['uuid'] = obj.oid
            
        # get security_groups
        sgs = []
        security_groups = kvargs.get('security_groups')
        for security_group in security_groups:
            obj = container.get_simple_resource(security_group, entity_class=NsxSecurityGroup)
            sgs.append(obj.oid)
        kvargs['security_groups'] = sgs

        # set desc
        kvargs['desc'] = kvargs.get('desc', 'Server %s' % kvargs['name'])

        customization_spec_name = kvargs.get('customization_spec_name', 'WS201x PRVCLOUD custom OS sysprep')
        if customization_spec_name is None:
            customization_spec_name = 'WS201x PRVCLOUD custom OS sysprep'
        kvargs['customization_spec_name'] = customization_spec_name

        steps = [
            VsphereServer.task_path + 'create_resource_pre_step',
            VsphereServer.task_path + 'create_server_step',
            VsphereServer.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    #
    # patch
    #
    def __create_volume(self, volume_name, volume_type, volume_size, source_type, disk_object_id=None, boot=False,
                        image_id=None, volume_resource_uuid=None):
        factory_params = {
            'name': volume_name,
            'desc': volume_name,
            'parent': self.parent_id,
            'ext_id': disk_object_id,
            'size': volume_size,
            'volume_type': volume_type,
            'sync': True,
            'source_volid': volume_resource_uuid,
            'snapshot_id': None,
            'imageRef': image_id,
            'set_as_sync': True
        }

        # create volume from image
        if source_type == 'image':
            volume, code = self.container.resource_factory(VsphereVolume, **factory_params)
            volume_resource_uuid = volume.get('uuid')
            self.logger.debug('create volume resource %s' % volume_resource_uuid)

        # get existing volume
        elif source_type in ['volume']:
            self.logger.debug('get existing volume resource %s' % volume_resource_uuid)

        # create new volume
        elif source_type is None:
            volume, code = self.container.resource_factory(VsphereVolume, **factory_params)
            volume_resource_uuid = volume.get('uuid')
            self.logger.debug('create volume resource %s' % volume_resource_uuid)

        # set bootable
        volume_resource = self.container.get_simple_resource(volume_resource_uuid)
        volume_resource.set_configs('bootable', boot)

        # link volume id to server
        self.add_link('%s-%s-volume-link' % (self.oid, volume_resource.oid), 'volume', volume_resource.oid,
                      attributes={'boot': boot})
        self.logger.debug('setup volume link from volume %s to server %s' % (volume_resource.oid, self.oid))

        return volume_resource_uuid

    def __get_volume_type(self, volume):
        volume_types, tot = self.container.get_resources(type=VsphereVolumeType.objdef)
        volume_type = None

        datastore = volume.get('storage')
        self.logger.debug('get volume type - datastore: %s' % datastore)
        
        for vt in volume_types:
            vsphereVolumeType: VsphereVolumeType = vt
            self.logger.debug('get volume type - vsphereVolumeType: %s' % vsphereVolumeType)
            
            if vsphereVolumeType.has_datastore(datastore) is True:
                volume_type = vsphereVolumeType
                break
        
        if volume_type is None:
            raise ApiManagerError('no volume type found for volume %s' % volume.get('id'))
        self.logger.debug('get volume type: %s' % volume_type)
        return volume_type

    def __patch_missing_volume(self, physical_volume, exist=False, resource_volume=None):
        index = str(physical_volume.get('unit_number'))
        disk_object_id = str(physical_volume.get('disk_object_id'))
        name = physical_volume.get('name')
        name_index = name.replace('Hard disk ', '')
        volume_name = '%s-%s' % (self.name.replace('-server', '-volume'), name_index)
        volume_type = self.__get_volume_type(physical_volume).oid

        if index == '0' and name == 'Hard disk 1':
            boot = True
        else:
            boot = False

        self.logger.warn('%s - %s' % (volume_name, boot))

        if exist is True:
            resource_volume.update_internal(name=volume_name, ext_id=disk_object_id)
            # if physical_volume.is_linked(resource_volume.oid) is False:
            #     # link volume id to server
            #     self.add_link('%s-%s-volume-link' % (self.oid, resource_volume.oid), 'volume', resource_volume.oid,
            #                   attributes={'boot': boot})
            #     self.logger.debug('setup volume link from volume %s to server %s' % (resource_volume.oid, self.oid))
        else:
            source_type = None
            volume_size = physical_volume.get('size')
            self.__create_volume(volume_name, volume_type, volume_size, source_type, disk_object_id=disk_object_id,
                                 boot=boot, image_id=None, volume_resource_uuid=None)

    def do_patch(self, **params):
        """method to execute to make custom resource operations useful to complete patch

        :param params: custom params required by task
        """
        # get already linked volume
        linked_volumes, tot = self.get_linked_resources(link_type='volume', size=-1)
        linked_volumes_idx = {str(v.ext_id): v for v in linked_volumes}
        self.logger.debug('do_patch - linked_volumes_idx: ' % (linked_volumes_idx))

        # get vsphere server disks
        physical_volumes = self.container.conn.server.volumes(self.ext_obj)
        for physical_volume in physical_volumes:
            name = physical_volume.get('name')
            unit_number = str(physical_volume.get('unit_number'))
            disk_object_id = str(physical_volume.get('disk_object_id'))
            self.logger.debug('do_patch - physical_volume - name: ' % (name))
            self.logger.debug('do_patch - physical_volume - unit_number: ' % (unit_number))
            self.logger.debug('do_patch - physical_volume - disk_object_id: ' % (disk_object_id))
            
            linked_volume_by_unit_number = linked_volumes_idx.get(unit_number, None)
            linked_volume_by_disk_object_id = linked_volumes_idx.get(disk_object_id, None)
            linked_volume = linked_volume_by_unit_number if linked_volume_by_unit_number is not None \
                else linked_volume_by_disk_object_id
            if linked_volume is None:
                self.logger.warning('physical_volume %s %s is not linked' % (name, disk_object_id))
                self.__patch_missing_volume(physical_volume, exist=False)
            else:
                self.logger.debug('physical_volume %s %s is already linked' % (name, disk_object_id))
                self.__patch_missing_volume(physical_volume, exist=True, resource_volume=linked_volume)

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in update method. Extend this function to manipulate and
        validate patch input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.volume_type:: volume_type
        :param kvargs.image_id:: image_id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            VsphereServer.task_path + 'patch_resource_pre_step',
            VsphereServer.task_path + 'patch_server_step',
            VsphereServer.task_path + 'patch_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params            
        :return: kvargs            
        :raises ApiManagerError:
        """
        steps = [
            VsphereServer.task_path + 'update_resource_pre_step',
            VsphereServer.task_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params            
        :return: kvargs            
        :raises ApiManagerError:
        """
        net_links, tot = self.get_links(type='network')
        if len(net_links) > 0:
            net_link = net_links[0]
            kvargs['networks'] = [net_link.attribs]
        
        steps = [
            VsphereServer.task_path + 'expunge_resource_pre_step',
            VsphereServer.task_path + 'delete_server_step',
            VsphereServer.task_path + 'delete_volumes_step',
            VsphereServer.task_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs
    
    #
    # info
    #    
    def info(self):
        """Get infos.
        
        :return: like :class:`Resource`

            details: {
                'cpu': 1,
                'disk': None,
                'hostname': 'env-server-83200',
                'ip_address': ['172.25.5.154'],
                'memory': 1024,
                'os': 'CentOS 4/5/6/7 (64-bit)',
                'state': 'poweredOn',
                'template': False
            }

        :raise ApiManagerError: 
        """
        info = VsphereResource.info(self)
        details = info['details']
        if self.ext_obj is not None:
            details.update(self.container.conn.server.info(self.ext_obj))
        return info

    def detail(self):
        """Get details.
        
        :return: ike :class:`Resource`
        
            details: {
                'date': {
                    'created': None, 
                    'launched': '2016-10-03T07:32:15', 
                    'terminated': None, 
                    'updated': None
                },
                'flavor': {
                    'cpu': 1,
                    'id': None, 
                    'memory': 1024
                },
                'metadata': None,
                'networks': [
                {
                    'fixed_ips': None, 
                    'mac_addr': '00:50:56:a6:05:bf', 
                    'name': 'Network adapter 1', 
                    'net_id': 2800, 
                    'port_state': True
                },..],
                'os': 'CentOS 4/5/6/7 (64-bit)',
                'overall_status': 'green',
                'state': 'poweredOn',
                'volumes': [
                {    
                    'bootable': None,
                    'format': None,
                    'id': '[DatastoreNFS] tst-vm2/tst-vm2.vmdk',
                    'mode': 'persistent',
                    'name': 'Hard disk 1',
                    'size': 8.0,
                    'storage': 'DatastoreNFS',
                    'type': None
                },..],
                'vsphere:firmware': 'bios',
                'vsphere:linked': {'linked': False, 'parent': None},
                'vsphere:managed': None,
                'vsphere:notes': '',
                'vsphere:template': False,
                'vsphere:tools': {
                    'status': 'guestToolsRunning', 
                    'version': '2147483647'
                },
                'vsphere:uuid': '5026dc4d-5d04-9c4b-04ad-7680bb0ae7ee',
                'vsphere:vapp': None,
                'vsphere:version': 'vmx-11'
            }
        
        :raise ApiManagerError: 
        """
        # verify permissions
        info = VsphereResource.detail(self)

        details = info['details']
        if self.ext_obj is not None:
            data = self.container.conn.server.detail(self.ext_obj)
            for item in data['networks']:
                obj = self.container.get_resource_by_extid(item['net_id'])
                net_link, tot = self.get_links(type='network')
                item['net_id'] = None
                if obj is not None:
                    item['net_id'] = obj.uuid
                if len(net_link) > 0:
                    item['fixed_ips'] = net_link[0].attribs.get('ip')
            details.update(data)

            # get security group
            sgs = [s.small_info() for s in self.get_security_groups() if s is not None]
            details.update({'security_groups': sgs})

            # get linked volumes
            volumes, tot = self.get_linked_resources(link_type_filter='volume', entity_class=VsphereVolume,
                                                     objdef=VsphereVolume.objdef, run_customize=False, size=-1)
            volume_idx = {str(v.ext_id): v for v in volumes}
            for volume in data['volumes']:
                volume['vsphere:name'] = volume['name']
                volume['name'] = None

                # get id as diskObjectId
                v = volume_idx.get(str(volume.get('disk_object_id')), None)
                if v is not None:
                    volume['name'] = v.name
                    volume['uuid'] = v.uuid
                    volume['bootable'] = v.is_bootable()
                    volume['ext_id'] = v.ext_id

                # get id as unit number
                v = volume_idx.get(str(volume.get('unit_number')), None)
                if v is not None:
                    volume['name'] = v.name
                    volume['uuid'] = v.uuid
                    volume['bootable'] = v.is_bootable()
                    volume['uuid'] = v.uuid
                    volume['ext_id'] = v.ext_id

            # get flavor
            flavor = self.get_flavor_resource()
            details['flavor']['id'] = flavor.oid
            details['flavor']['name'] = flavor.name

        return info

    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        operation.cache = False
        self.container = self.controller.get_container(self.container_id)
        self.post_get()

        volumes = dict_get(self.detail(), 'details.volumes')

        if self.ext_obj is None:
            res = {'check': False, 'msg': 'no remote server found'}
        elif volumes is not None and len(volumes) != len([v for v in volumes if v.get('uuid', None) is not None]):
            res = {'check': False, 'msg': 'wrong volume assignment'}
        else:
            res = {'check': True, 'msg': None}
        self.logger.debug2('Check resource %s: %s' % (self.uuid, res))
        return res

    #
    # additional info
    #
    def is_running(self):
        """True if server is running"""
        status = self.get_status()
        if status is not None and status == 'poweredOn':
            return True
        else:
            return False

    def get_network_config(self):
        networks = None
        if self.ext_obj is not None:
            data = self.container.conn.server.detail(self.ext_obj)
            networks = data['networks']
            for item in networks:
                net_id = item['net_id']
                obj = self.container.get_resource_by_extid(net_id)

                # check if dvpg has a logical switch associated
                lg = self.container.conn.network.nsx.lg.get_by_dvpg(net_id)
                if lg is not None:
                    net_id = lg.get('objectId')
                    obj = self.container.get_resource_by_extid(net_id)

                net_link, tot = self.get_links(type='network')
                item['net_id'] = None
                if obj is not None:
                    item['net_id'] = obj.uuid
                if len(net_link) > 0:
                    item['fixed_ips'] = net_link[0].attribs.get('ip')
        return networks

    @trace(op='view')
    def get_main_ip_address(self):
        """Get main ip address"""
        ip_address = None
        net_link, tot = self.get_links(type='network')
        if len(net_link) > 0:
            ip_config = net_link[0].attribs
            ip_address = ip_config.get('ip', None)
        return ip_address

    def get_ip_address_config(self):
        """Get server main ip address with ippool

        :return:
        """
        ip = None
        net_link, tot = self.get_links(type='network')
        if len(net_link) > 0:
            ip = net_link[0].attribs
        return ip

    def get_min_disk(self):
        """Get minimum disk size

        :return: minimum disk size
        """
        if self.ext_obj is not None:
            volumes = self.container.conn.server.detail(self.ext_obj).get('volumes')
            return int(volumes[0].get('size', 0))
        else:
            return 0

    def get_template_disks(self, exclude_main=True):
        """Get disk list from a server template

        :param exclude_main: if True exclude main boot disk
        :return: list of template disks
        """
        if self.ext_obj is not None:
            volumes = self.container.conn.server.detail(self.ext_obj).get('volumes')
            if exclude_main is True:
                volumes = [v for v in volumes if v['unit_number'] != 0]
            return volumes
        else:
            return []

    def get_status(self):
        """Gets the status info for the server.

        :return: status info
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')

        res = None
        try:
            if self.ext_obj is not None:
                info = self.container.conn.server.info(self.ext_obj)
                res = info.get('state', '')
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)
        return res

    @trace(op='view')
    def get_flavor_resource(self):
        """Get server flavor resource"""
        flavor = None

        if self.ext_obj is not None:
            data = self.container.conn.server.detail(self.ext_obj)
            ram = dict_get(data, 'flavor.memory')
            cpu = dict_get(data, 'flavor.cpu')
            json_attribute_contain = [{'field': 'ram', 'value': ram}, {'field': 'vcpus', 'value': cpu}]
            ress, tot = self.container.get_resources(json_attribute_contain=json_attribute_contain, size=-1,
                                                     with_perm_tag=False, active=1)
            # filter = '{"ram":' + str(ram) + ',%,"vcpus":' + str(cpu) + '%}'
            # ress, tot = self.container.get_resources(attribute=filter, size=-1)
            for res in ress:
                self.logger.warn(res)
            if tot > 0:
                flavor = ress[0]

            self.logger.debug('Get vsphere server %s flavor: %s' % (self.uuid, truncate(flavor)))
        return flavor

    @trace(op='view')
    def get_flavor(self):
        """Get server flavor
        todo:
        """
        pass

    @trace(op='view')
    def get_volumes(self):
        """Get server platform volumes"""
        volumes = []
        try:
            if self.ext_obj is not None:
                info = self.container.conn.server.detail(self.ext_obj)
                volumes = info.get('volumes', [])
                linkvols, tot = self.get_linked_resources(link_type_filter='volume', entity_class=VsphereVolume,
                                                          objdef=VsphereVolume.objdef, run_customize=False, size=-1)
                volume_idx = {str(v.ext_id): v for v in linkvols}
                for volume in volumes:
                    v = volume_idx.get(str(volume.get('unit_number')), None)
                    if v is not None:
                        volume['uuid'] = v.uuid
                        volume['bootable'] = v.is_bootable()
                    v = volume_idx.get(str(volume.get('disk_object_id')), None)
                    if v is not None:
                        volume['uuid'] = v.uuid
                        volume['bootable'] = v.is_bootable()
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug('Get vsphere server %s platform volumes: %s' % (self.uuid, truncate(volumes)))
        return volumes

    @trace(op='view')
    def get_volume_resources(self):
        """Get server volumes"""
        volumes = []
        volumes, tot = self.get_linked_resources(link_type_filter='volume', entity_class=VsphereVolume,
                                                 objdef=VsphereVolume.objdef, run_customize=False, size=-1)

        self.logger.debug('Get vsphere server %s volumes: %s' % (self.uuid, truncate(volumes)))
        return volumes

    @trace(op='view')
    def get_ports(self):
        """Get server ports"""
        ports = []
        data = self.container.conn.server.detail(self.ext_obj)
        ports = data.get('networks', [])
        for item in ports:
            obj = self.container.get_resource_by_extid(item['net_id'])
            net_link, tot = self.get_links(type='network')
            item['net_id'] = None
            if obj is not None:
                item['net_id'] = obj.uuid
            if len(net_link) > 0:
                item['fixed_ips'] = net_link[0].attribs.get('ip')

        self.logger.debug('Get vsphere server %s ports: %s' % (self.uuid, truncate(ports)))
        return ports

    @trace(op='view')
    def get_host(self):
        # if self.ext_obj is not None:
        #     return self.ext_obj.get('OS-EXT-SRV-ATTR:host', None)
        return None

    def get_host_group(self):
        # if self.ext_obj is not None:
        #     return self.ext_obj.get('OS-EXT-SRV-ATTR:host', None)
        return None

    @trace(op='use')
    def get_hardware(self):
        """Get hardware info
        
        :return:
        
            {
                'bios_uuid': '42261175-77b9-ba63-f959-9bd290c329d5',
                'boot': {
                    'boot_delay': 0, 
                    'enter_bios_setup': False, 
                    'network_protocol': 'ipv4', 
                    'order': [], 
                    'retry_delay': 10000, 
                    'retry_enabled': False
                },
                'cdrom': {
                    'backing': 'vim.vm.device.VirtualCdrom.IsoBackingInfo', 
                    'key': 3002, 
                    'name': 'CD/DVD drive 1', 
                    'type': 'vim.vm.device.VirtualCdrom'
                },
                'cpu': {
                    'core': 1, 
                    'hardware_utilization': None, 
                    'limit': 'unlimited', 
                    'num': 1, 
                    'performance_counters': None, 
                    'reservation': '0 MHz', 
                    'shares': '1000 (normal)'
                },
                'file_layout': {
                    'files': [
                    {    
                        'accessible': True, 
                        'key': 0, 
                        'name': '[DatastoreNFS] tst-vm2/tst-vm2.vmx', 
                        'size': 2905, 
                        'type': 'config', 
                        'uniqueSize': 2905
                    },..,
                    {
                        'accessible': True,
                        'key': 4,
                        'name': '[DatastoreNFS] tst-vm2/tst-vm2-flat.vmdk',
                        'size': 1125253632,
                        'type': 'diskExtent',
                        'uniqueSize': 1125253632
                    },..],
                    'logDirectory': '[DatastoreNFS] tst-vm2/',
                    'snapshotDirectory': '[DatastoreNFS] tst-vm2/',
                    'suspendDirectory': '[DatastoreNFS] tst-vm2/',
                    'vmPathName': '[DatastoreNFS] tst-vm2/tst-vm2.vmx'},
                'firmware': 'bios',
                'floppy': {
                    'key': 8000, 
                    'name': 'Floppy drive 1', 
                    'type': 'vim.vm.device.VirtualFloppy'
                },
                'memory': {
                    'limit': 'unlimited', 
                    'reservation': '0 MB', 
                    'shares': '10240 (normal)', 
                    'total': 1024, 'vm_overhead_consumed': None
                },
                'network': [
                {    
                    'backing': 'vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo',
                    'connected': True,
                    'direct_path_io': None,
                    'key': 4000,
                    'limit': None,
                    'macaddress': '00:50:56:a6:05:bf',
                    'name': 'Network adapter 1',
                    'network': {'dvs': 'dvs-124', 'id': 'dvportgroup-1120',
                                 'name': '229c88e4-04a0-4f5f-ac59-086568ffe31e-14-net-backend', 'vlan': 307},
                    'reservation': None,
                    'shares': None,
                    'type': 'vim.vm.device.VirtualVmxnet3',
                    'unit_number': 7
                },..],
                'other': {
                    'controllers': [
                        {'key': 200, 'name': 'IDE 0', 'type': 'vim.vm.device.VirtualIDEController'},
                        {'key': 201, 'name': 'IDE 1', 'type': 'vim.vm.device.VirtualIDEController'},
                        {'key': 300, 'name': 'PS2 controller 0', 'type': 'vim.vm.device.VirtualPS2Controller'},
                        {'key': 100, 'name': 'PCI controller 0', 'type': 'vim.vm.device.VirtualPCIController'},
                        {'key': 400, 'name': 'SIO controller 0', 'type': 'vim.vm.device.VirtualSIOController'},
                        {'key': 1000, 'name': 'SCSI controller 0',
                         'type': 'vim.vm.device.VirtualLsiLogicController'}
                    ],
                    'input_devices': [
                        {'key': 600, 'name': 'Keyboard ', 'type': 'vim.vm.device.VirtualKeyboard'},
                        {'backing': 'vim.vm.device.VirtualPointingDevice.DeviceBackingInfo',
                         'key': 700,
                         'name': 'Pointing device',
                         'type': 'vim.vm.device.VirtualPointingDevice'}
                    ],
                    'other': [],
                    'pci': [{'key': 12000, 'name': 'VMCI device', 'type': 'vim.vm.device.VirtualVMCIDevice'}],
                    'scsi_adapters': []},
                'storage': [
                {
                    'backing': 'vim.vm.device.VirtualDisk.FlatVer2BackingInfo',
                    'datastore': {'delta_disk_format': None,
                                   'delta_disk_format_variant': None,
                                   'delta_grain_size': None,
                                   'digest_enabled': False,
                                   'disk_mode': 'persistent',
                                   'file_name': '[DatastoreNFS] tst-vm2/tst-vm2.vmdk',
                                   'id': 'datastore-10',
                                   'name': 'DatastoreNFS',
                                   'parent': None,
                                   'sharing': 'sharingNone',
                                   'split': False,
                                   'thin_provisioned': True,
                                   'write_through': False},
                    'flashcache': None,
                    'name': 'Hard disk 1',
                    'size': 8192,
                    'type': 'vim.vm.device.VirtualDisk'
                }],
                'swap_placement': 'inherit',
                'version': 'vmx-11',
                'video': {
                    'key': 500, 
                    'name': 'Video card ', 
                    'type': 'vim.vm.device.VirtualVideoCard'
                }
            }
            
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')
        
        try:
            res = self.container.conn.server.hardware.info(self.ext_obj)
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)  
        return res

    @trace(op='use')
    def get_vnc_console(self, endpoint):
        """Get vnc console.
        
        :return: {'type': 'novnc', 'url': 'http://ctrl-liberty.nuvolacsi.it:6080/vnc_auto....' }
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')
        
        try:
            token_data = self.container.conn.server.get_console_esxi_uri(self.ext_obj)
            token_data['staticuri'] = endpoint
            json_token_data = dumps(token_data)
            token = token_gen()
            # self.controller.redis_manager.setex(self.console_prefix + token, self.console_expire_time, json_token_data)
            self.controller.redis_identity_manager.setex(self.console_prefix + token,
                                                         self.console_expire_time,
                                                         json_token_data)

            resp = {
                'url': '%s/v1.0/console/vnc_auto.html?token=%s' % (self.api_manager.cluster_app_uri, token),
                'type': 'novnc',
                'protocol': 'vnc'
            }
            self.logger.debug('Get vsphere server %s vnc console: %s' % (self.oid, resp))
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)  
        return resp

    @trace(op='use')
    def get_guest_info(self):
        """Get guest info.
        
        :return:
        
            {
                'disk': [{'capacity': '6858MB', 'diskPath': '/', 'free_space': '5622MB'},
                          {'capacity': '496MB', 'diskPath': '/boot', 'free_space': '349MB'},
                          {'capacity': '6858MB', 'diskPath': '/tmp', 'free_space': '5622MB'},
                          {'capacity': '6858MB', 'diskPath': '/var/tmp', 'free_space': '5622MB'}],
                'guest': {'app_heartbeat_status': 'appStatusGray',
                           'app_state': 'none',
                           'family': 'linuxGuest',
                           'fullname': 'CentOS 4/5/6/7 (64-bit)',
                           'generation_info': [],
                           'guest_kernel_crashed': None,
                           'id': 'centos64Guest',
                           'interactive_operations_ready': False,
                           'operations_ready': True,
                           'state': 'running',
                           'state_change_supported': True},
                'hostname': 'tst-vm2',
                'ip_address': '172.25.5.151',
                'ip_stack': [{'dhcpConfig': None,
                               'dns_config': {'dhcp': False, 'domainname': '', 'hostname': 'tst-vm2',
                                               'ip_address': ['127.0.0.1', '172.25.5.100'], 'search_domain': ['']},
                               'ipStackConfig': [],
                               'ip_route_config': [{'gateway': '172.25.5.18', 'network': '0.0.0.0/0'},
                                                    {'gateway': '172.25.5.1', 'network': '10.102.160.0/24'},
                                                    {'gateway': '172.25.5.1', 'network': '158.102.160.0/24'},
                                                    {'gateway': None, 'network': '169.254.0.0/16'},
                                                    {'gateway': None, 'network': '172.25.5.0/24'},
                                                    {'gateway': None, 'network': 'fe80::/64'},
                                                    {'gateway': None, 'network': 'ff02::1/128'},
                                                    {'gateway': None, 'network': 'ff00::/8'}]}],
                'nics': [{'connected': True,
                           'device_config_id': 4000,
                           'dnsConfig': None,
                           'ip_config': {'dhcp': None, 'ip_address': ['172.25.5.151/24',
                                                                         'fe80::250:56ff:fea6:5bf/64']},
                           'mac_address': '00:50:56:a6:05:bf',
                           'netbios_config': None,
                           'network': '229c88e4-04a0-4f5f-ac59-086568ffe31e-14-net-backend'}],
                'screen': {'height': 768, 'width': 1280},
                'tools': {'running_status': 'guestToolsRunning',
                           'status': 'toolsOk',
                           'version': '2147483647',
                           'version_status': 'guestToolsUnmanaged',
                           'version_status2': 'guestToolsUnmanaged'}
            }
            
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')
        try:
            res = self.container.conn.server.guest_info(self.ext_obj)
            self.logger.debug('Get server %s guest info: %s' % (self.oid, res))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    @trace(op='use')
    def get_networks(self):
        """Get network info.
        
        :return: list of vsphere network info
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')
        try:
            if self.ext_obj is not None:
                res = []
                # get dvpg list
                nets = self.container.conn.server.network(self.ext_obj)
                for item in nets:
                    net_id = item['id']

                    # check if dvpg has a logical switch associated
                    lg = self.container.conn.network.nsx.lg.get_by_dvpg(net_id)
                    if lg is not None:
                        net_id = lg.get('objectId')

                    try:
                        net = self.container.get_resource_by_extid(net_id)
                        res.append(net.small_info())
                    except:
                        pass

                self.logger.debug('Get server %s network info: %s' % (self.name, truncate(res)))
                return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    @trace(op='use')
    def get_storage(self):
        """Get storage info.
        
        :return:
        
            [
                {
                    'committed': 1.0,
                    'datastore': <small_info>,
                    'uncommitted': 6.0,
                    'unshared': 1.0,
                    'url': '/vmfs/volumes/01ce0616-7bc9f86e'
                }
            ]
            
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')
        try:
            vm = self.ext_obj

            # storage info
            res = []
            storeurls = {i.name: i for i in vm.config.datastoreUrl}
            
            for item in vm.storage.perDatastoreUsage:
                # datastore
                obj = self.controller.get_resource_by_extid(item.datastore._moId)
                
                storage = {'committed': round(item.committed/1073741824, 2),
                           'uncommitted': round(item.uncommitted/1073741824, 2),
                           'unshared': round(item.unshared/1073741824, 2),
                           'url': storeurls[item.datastore.name].url,
                           'datastore': obj.small_info()}
                res.append(storage)

            self.logger.debug('Get server %s storage info: %s' % (self.name, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    @trace(op='use')
    def get_runtime(self):
        """Get runtime.
        
        :return:
        
            {
                'boot_time': 1475479935,
                'host': <small_info>,
                'resource_pool': <small_info>
            }
            
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')        
        
        try:
            res = self.container.conn.server.runtime(self.ext_obj)
            self.logger.warn(res)

            # host
            host = self.controller.get_resource_by_extid(res['host']['id'])
            if host is not None:
                res['host'] = host.small_info()
            
            # resource pool
            resource_pool = self.controller.get_resource_by_extid(res['resource_pool']['id'])
            if resource_pool is not None:
                res['resource_pool'] = host.small_info()

            self.logger.debug('Get server %s runtime: %s' % (self.name, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    @trace(op='use')
    def get_stats(self):
        """Get statistics.

        :return:
        
            {
                'balloonedMemory': 0,
                'compressedMemory': 0,
                'consumedOverheadMemory': 38,
                'distributedCpuEntitlement': 0,
                'distributedMemoryEntitlement': 390,
                'dynamicProperty': [],
                'dynamicType': None,
                'ftLatencyStatus': 'gray',
                'ftLogBandwidth': -1,
                'ftSecondaryLatency': -1,
                'guestHeartbeatStatus': 'green',
                'guestMemoryUsage': 30,
                'hostMemoryUsage': 337,
                'overallCpuDemand': 0,
                'overallCpuUsage': 0,
                'privateMemory': 300,
                'sharedMemory': 0,
                'ssdSwappedMemory': 0,
                'staticCpuEntitlement': 2260,
                'staticMemoryEntitlement': 1092,
                'swappedMemory': 0,
                'uptimeSeconds': 1824053
            }
            
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')        
        
        try:
            res = self.container.conn.server.usage(self.ext_obj)

            self.logger.debug('Get server %s statistics: %s' % (self.name, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)  
        
    @trace(op='use')
    def get_metadata(self):
        """Get metadata.

        :return: List            
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')
        raise ApiManagerError('Method is not supported', code=405)
    
    @trace(op='use')
    def get_actions(self, action_id=None):
        """Get actions.

        :param action_id: action id            
        :return: List            
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')
        raise ApiManagerError('Method is not supported', code=405)    
        
    @trace(op='use')
    def get_snapshots(self, snapshot_id=None):
        """Get snapshots.
        
        :param snapshot_id: snapshot id            
        :return: True            
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')
        
        try:
            res = self.container.conn.server.snapshot.list(self.ext_obj)
        except VsphereServer as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

        resp = [{'id': r['id'], 'name': r['name'], 'created_at': r['creation_date'], 'status': r['state']}
                for r in res]
        self.logger.debug('Get vsphere server %s snapshots: %s' % (self.name, resp))
        return resp
        
    @trace(op='use')
    def get_current_snapshot(self):
        """Get current snapshot.

        :return:
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions('use')        
        
        try:
            res = self.container.conn.server.snapshot.get_current(self.ext_obj)

            self.logger.debug('Get server %s current snapshot: %s' % (self.oid, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)           

    @trace(op='use')
    def get_security_groups(self):
        """Get security groups.
        
        :param security_group: security_group id to assign            
        :return: True            
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')
        try:
            sgs = self.container.conn.server.security_groups(self.ext_obj)
            if isinstance(sgs, dict):
                sgs = [sgs]
            res = []

            for sg in sgs:
                res.append(self.container.get_resource_by_extid(sg['objectId']))

            self.logger.debug('Get server %s security groups: %s' % (self.oid, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    def has_security_group(self, security_group_id):
        """Check security group is attached to server

        :param security_group_id: security_group id to check
        :return: True
        :raise ApiManagerError:
        """
        sgs = self.get_security_groups()
        for sg in sgs:
            if sg.oid == security_group_id:
                return True
        return False

    #
    # action
    #
    @trace(op='update')
    def start(self, *args, **kvargs):
        """Start server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        if self.is_running() is True:
            raise ApiManagerError('Server %s is already running' % self.uuid)

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_start_step']
        res = self.action('start', steps, log='Start server', **kvargs)
        return res

    @trace(op='update')
    def stop(self, *args, **kvargs):
        """Stop server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        if self.is_running() is False:
            raise ApiManagerError('Server %s is not running' % self.uuid)

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_stop_step']
        res = self.action('stop', steps, log='Stop server', **kvargs)
        return res

    @trace(op='update')
    def reboot(self, *args, **kvargs):
        """Rebbot server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_reboot_step']
        res = self.action('reboot', steps, log='Reboot server', **kvargs)
        return res

    @trace(op='update')
    def pause(self, *args, **kvargs):
        """Pause server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_pause_step']
        res = self.action('pause', steps, log='Pause server', **kvargs)
        return res

    @trace(op='update')
    def unpause(self, *args, **kvargs):
        """Unpause server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_unpause_step']
        res = self.action('unpause', steps, log='Unpause server', **kvargs)
        return res

    @trace(op='update')
    def migrate(self, *args, **kvargs):
        """Migrate server.

        :param live: if True run live migration
        :param host: physical server where migrate [optional]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_migrate_step']
        res = self.action('migrate', steps, log='Migrate server', *args, **kvargs)
        return res

    @trace(op='update')
    def add_snapshot(self, *args, **kvargs):
        """Remove server snapshot

        :param snapshot: snapshot name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            # add check snapshot exists
            return kvargs

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_add_snapshot_step']
        res = self.action('add_snapshot', steps, log='Add server snapshot', check=check, **kvargs)
        return res

    @trace(op='update')
    def del_snapshot(self, *args, **kvargs):
        """Remove server snapshot

        :param snapshot: snapshot id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            # add check snapshot exists
            return kvargs

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_del_snapshot_step']
        res = self.action('del_snapshot', steps, log='Remove server snapshot', check=check, **kvargs)
        return res

    @trace(op='update')
    def revert_snapshot(self, *args, **kvargs):
        """Revert server to snapshot

        :param snapshot: snapshot id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            # add check snapshot exists
            return kvargs

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_revert_snapshot_step']
        res = self.action('revert_snapshot', steps, log='Revert server to snapshot', check=check, **kvargs)
        return res

    @trace(op='update')
    def add_security_group(self, *args, **kvargs):
        """Add security group to server

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(kvargs['security_group'], entity_class=NsxSecurityGroup)
            if self.has_security_group(security_group.oid) is False:
                security_group.check_active()
                kvargs['security_group'] = security_group.oid
                return kvargs
            else:
                raise ApiManagerError('security group %s is already attached to server %s' %
                                      (security_group.oid, self.oid))

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_add_security_group_step']
        res = self.action('add_security_group', steps, log='Add security group to server', check=check, **kvargs)
        return res

    @trace(op='update')
    def del_security_group(self, *args, **kvargs):
        """Remove security group from server

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(kvargs['security_group'], entity_class=NsxSecurityGroup)
            if self.has_security_group(security_group.oid) is True:
                kvargs['security_group'] = security_group.oid
                return kvargs
            else:
                raise ApiManagerError('security group %s is not attached to server %s' % (security_group.oid, self.oid))

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_del_security_group_step']
        res = self.action('del_security_group', steps, log='Remove security group from server', check=check, **kvargs)
        return res

    @trace(op='update')
    def add_volume(self, *args, **kvargs):
        """Add volume to server

        :param volume: volume uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            volume = self.container.get_simple_resource(kvargs['volume'], entity_class=VsphereVolume)
            volume.check_active()
            if self.is_linked(volume.oid) is False:
                kvargs['volume'] = volume.oid
                return kvargs
            else:
                raise ApiManagerError('volume %s is already linked to server %s' % (volume.oid, self.oid))

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_add_volume_step']
        res = self.action('add_volume', steps, log='Add volume to server', check=check, **kvargs)
        return res

    @trace(op='update')
    def del_volume(self, *args, **kvargs):
        """Remove volume from server

        :param volume: volume uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            volume = self.container.get_simple_resource(kvargs['volume'], entity_class=VsphereVolume)
            volume.check_active()
            if self.is_linked(volume.oid) is True:
                kvargs['volume'] = volume.oid
                return kvargs
            else:
                raise ApiManagerError('volume %s is not linked to server %s' % (volume.oid, self.oid))

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_del_volume_step']
        res = self.action('del_volume', steps, log='Remove volume from server', check=check, **kvargs)
        return res

    @trace(op='update')
    def set_flavor(self, *args, **kvargs):
        """Set flavor to server.

        :param flavor: flavor uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        def check(*args, **kvargs):
            flavor = self.container.get_simple_resource(kvargs['flavor'], entity_class=VsphereFlavor)
            kvargs['flavor'] = flavor.oid
            return kvargs

        steps = ['beehive_resource.plugins.vsphere.task_v2.vs_server.ServerTask.server_set_flavor_step']
        res = self.action('set_flavor', steps, log='Set flavor to server', check=check, **kvargs)
        return res

    #
    # veeam backup
    #
    @trace(op='view')
    def get_veeam_backup(self):
        """Get veeam backup info

        :return: (workload_name, workload_id)
        """
        return None, None
        # workload_name, workload_id = None, None
        # if self.ext_obj is not None:
        #     workload_name = dict_get(self.ext_obj, 'metadata.workload_name')
        #     workload_id = dict_get(self.ext_obj, 'metadata.workload_id')
        # 
        # self.logger.debug('Get openstack server %s trilio backup info: %s' % (self.oid, (workload_name, workload_id)))
        # return workload_name, workload_id
    
    def has_backup(self):
        """check if server has backup workload associated

        :return: True if server has backup workload associated
        """
        return False

    def has_backup_restore_point(self, restore_point):
        """check if server has backup restore point

        :param restore_point: restore point id
        :return: True if server has backup workload associated
        """
        job = self.get_backup_job()
        if job == {}:
            return False

        workload_id = job['id']
        trilio_conn = self.container.get_veeam_connection()
        restore_points = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        restore_points = [s for s in restore_points if s.get('id') == restore_point]
        if len(restore_points) > 0:
            return True
        return False

    def get_backup_job(self):
        """get info of physical backup job associated

        :return: workload info
        """
        workload_name, workload_id = self.get_veeam_backup()
        if workload_id is None:
            self.logger.warning('no backup job found info for server %s' % self.oid)
            return {}

        trilio_conn = self.container.get_veeam_connection()
        workload = trilio_conn.workload.get(workload_id)
        self.logger.debug('get backup job info for server %s: %s' % (self.oid, workload))
        res = {
            'id':  workload.get('id'),
            'name': workload.get('name'),
            'created': workload.get('created_at'),
            'updated': workload.get('updated_at'),
            'error': workload.get('error_msg'),
            # 'usage': dict_get(workload, 'storage_usage.usage'),
            'schedule': dict_get(workload, 'jobschedule'),
            # 'storage_usage': workload.get('storage_usage'),
            'status': workload.get('status'),
            'type': workload.get('workload_type_id')
        }
        return res

    def get_backup_restore_points(self, job):
        """get backup restore points

        :param job: job info
        :return: snapshots list
        """
        return []
        # if job == {}:
        #     self.logger.warning('no backup job found info for server %s' % self.oid)
        #     return []
        # 
        # # if job.get('status'):
        # #     return []
        # 
        # # snapshot_number = dict_get(job, 'schedule.retention_policy_value')
        # # snapshot_number = 30
        # # now = datetime.today()
        # # date_from = '%s-%s-%sT' % (now.year, now.month, now.day - snapshot_number)
        # # date_to = '%s-%s-%sT' % (now.year, now.month, now.day)
        # 
        # workload_id = job['id']
        # trilio_conn = self.container.get_veeam_connection()
        # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        # # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id, date_from=date_from, date_to=date_to)
        # self.logger.debug('get backup job %s restore points for server %s: %s' %
        #                   (workload_id, self.oid, snapshots))
        # res = [{
        #     'id': s.get('id'),
        #     'name': s.get('name'),
        #     'desc': s.get('description'),
        #     'created': s.get('created_at'),
        #     'type': s.get('snapshot_type'),
        #     'status': s.get('status'),
        # } for s in snapshots]
        # return res

    def get_backup_restore_status(self, restore_point):
        """get status of restore

        :param restore_point: restore point id
        :return: restore list
        """
        return []
        # workload_name, workload_id = self.get_veeam_backup()
        # if workload_id is None:
        #     self.logger.warning('no backup restore status for server %s' % self.oid)
        #     return []
        # 
        # self.container.get_connection(projectid=self.parent_id)
        # trilio_conn = self.container.get_veeam_connection()
        # 
        # # get workload
        # workload = trilio_conn.workload.get(workload_id)
        # self.logger.debug('get openstack trilio workload info for server %s: %s' % (self.oid, workload))
        # 
        # # get snapshots
        # # snapshot_number = dict_get(workload, 'jobschedule.retention_policy_value')
        # # snapshot_number = 30
        # # now = datetime.today()
        # # date_from = '%s-%s-%sT' % (now.year, now.month, now.day - snapshot_number)
        # # date_to = '%s-%s-%sT' % (now.year, now.month, now.day)
        # # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id, date_from=date_from, date_to=date_to)
        # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        # snapshots = [s for s in snapshots if s.get('id') == restore_point]
        # 
        # if len(snapshots) == 0:
        #     self.logger.warning('no backup restore point %s found for server %s' % (restore_point, self.oid))
        #     return []
        # 
        # # get restores
        # restores = trilio_conn.restore.list(snapshot_id=restore_point)
        # self.logger.debug('get backup restore point %s restores for server %s: %s' %
        #                   (restore_point, self.oid, restores))
        # 
        # res = [{
        #     'id': s.get('id'),
        #     'name': s.get('name'),
        #     'desc': s.get('description'),
        #     'time_taken': s.get('time_taken'),
        #     'size': s.get('size'),
        #     'uploaded_size': s.get('uploaded_size'),
        #     'status': s.get('status'),
        #     'progress_percent': s.get('progress_percent'),
        #     'created': s.get('created_at'),
        #     'updated': s.get('updated_at'),
        #     'finished': s.get('finished_at'),
        #     'msg': {
        #         'warning': s.get('warning_msg'),
        #         'progress': s.get('progress_msg'),
        #         'error': s.get('error_msg'),
        #     }
        # } for s in restores]
        # self.logger.debug('get backup restore status for server %s: %s' % (self.oid, res))
        # return res

    @trace(op='update')
    def add_backup_restore_point(self, *args, **kvargs):
        """add physical backup restore point

        :param full: if True make a full restore point. If False make an incremental restore point [default=True]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        pass
        # def check(*args, **kvargs):
        #     if self.has_backup() is False:
        #         raise ApiManagerError('server %s has no backup job associated' % self.oid)
        #     return kvargs
        # 
        # steps = [OpenstackServer.task_path + 'server_add_backup_restore_point']
        # res = self.action('add_backup_restore_point', steps, log='Add backup restore point to server', check=check,
        #                   **kvargs)
        # return res

    @trace(op='update')
    def del_backup_restore_point(self, *args, **kvargs):
        """delete physical backup restore point

        :param restore_point: restore point id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        pass
        # def check(*args, **kvargs):
        #     job = self.get_backup_job()
        #     if job == {}:
        #         raise ApiManagerError('server %s has no backup job associated' % self.oid)
        # 
        #     workload_id = job['id']
        #     restore_point = kvargs['restore_point']
        #     trilio_conn = self.container.get_veeam_connection()
        #     snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        #     snapshots = [s for s in snapshots if s.get('id') == restore_point]
        # 
        #     if len(snapshots) == 0:
        #         raise ApiManagerError('no backup restore point %s found for server %s' % (restore_point, self.oid))
        # 
        #     return kvargs
        # 
        # steps = [OpenstackServer.task_path + 'server_del_backup_restore_point']
        # res = self.action('del_backup_restore_point', steps, log='Delete backup restore point to server', check=check,
        #                   **kvargs)
        # return res

    @trace(op='update')
    def restore_from_backup(self, *args, **kvargs):
        """restore server from backup

        :param restore_point: restore point id
        :param server_name: restored server name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        pass
        # def check(*args, **kvargs):
        #     job = self.get_backup_job()
        #     if job == {}:
        #         raise ApiManagerError('server %s has no backup job associated' % self.oid)
        # 
        #     workload_id = job['id']
        #     restore_point = kvargs['restore_point']
        #     trilio_conn = self.container.get_veeam_connection()
        #     snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        #     snapshots = [s for s in snapshots if s.get('id') == restore_point]
        # 
        #     if len(snapshots) == 0:
        #         raise ApiManagerError('no backup restore point %s found for server %s' % (restore_point, self.oid))
        # 
        #     return kvargs
        # 
        # steps = [OpenstackServer.task_path + 'server_restore_from_backup']
        # res = self.action('restore_from_backup', steps, log='Restore server from backup', check=check,
        #                   **kvargs)
        # return res

