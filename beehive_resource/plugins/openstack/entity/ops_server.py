# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte
from datetime import datetime

from time import sleep

from beecell.simple import truncate, get_value, id_gen, dict_get
from beedrones.openstack.client import OpenstackError
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace, cache, operation
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task
from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet
from beehive_resource.plugins.openstack.entity.ops_security_group import (
    OpenstackSecurityGroup,
)
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.openstack.entity.ops_volume_type import (
    OpenstackVolumeType,
)


class OpenstackServer(OpenstackResource):
    objdef = "Openstack.Domain.Project.Server"
    objuri = "servers"
    objname = "server"
    objdesc = "Openstack servers"

    default_tags = ["openstack", "server"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_server.ServerTask."

    def __init__(self, *args, **kvargs):
        """
        Possible state are: ACTIVE, BUILDING, DELETED, ERROR, HARD_REBOOT,
        PASSWORD, PAUSED, REBOOT, REBUILD, RESCUED, RESIZED, REVERT_RESIZE,
        SHUTOFF, SOFT_DELETED, STOPPED, SUSPENDED, UNKNOWN, or VERIFY_RESIZE
        """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.flavor_idx = None
        self.volume_idx = None
        self.image_idx = None

        self.actions = {
            "start": self.start,
            "stop": self.stop,
            "reboot": self.reboot,
            "pause": self.pause,
            "unpause": self.unpause,
            "migrate": self.migrate,
            # 'setup_network': self.setup_network,
            # 'reset_state': self.reset_state,
            "add_snapshot": self.add_snapshot,
            "del_snapshot": self.del_snapshot,
            "revert_snapshot": self.revert_snapshot,
            "add_security_group": self.add_security_group,
            "del_security_group": self.del_security_group,
            "add_volume": self.add_volume,
            "del_volume": self.del_volume,
            "extend_volume": self.extend_volume,
            "set_flavor": self.set_flavor,
            # 'add_backup_restore_point': self.add_backup_restore_point,
            # 'del_backup_restore_point': self.del_backup_restore_point,
            "restore_from_backup": self.restore_from_backup,
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
        # get from openstack
        if ext_id is not None:
            items = [container.conn.server.get(oid=ext_id)]
        else:
            # items = container.conn.server.list(all_tenants=True, detail=True)
            items = OpenstackResource.list_remote_server(container.controller, "all", container, "all")

        # volume_idx = {v['id']: v for v in OpenstackResource.list_remote_volume(
        #    container.controller, 'all', container, 'all')}

        # volume_idx = {v['id']: v for v in container.conn.volume_v3.list_all(detail=True, limit=250)}

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                container.logger.warn(item)
                try:
                    level = None
                    name = item["name"]
                    parent_id = item["tenant_id"]
                    volumes = item["os-extended-volumes:volumes_attached"]
                    volume_id = None
                    for volume in volumes:
                        vol = container.conn.volume_v3.get(oid=volume["id"])
                        # vol = volume_idx.get(volume['id'])
                        if vol["bootable"] == "true":
                            volume_id = volume["id"]

                    res.append(
                        (
                            OpenstackServer,
                            item["id"],
                            parent_id,
                            OpenstackServer.objdef,
                            name,
                            volume_id,
                        )
                    )
                except:
                    container.logger.warn("", exc_info=True)

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param kvargs.container.conn: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        return OpenstackResource.list_remote_server(container.controller, "all", container, "all")
        # return container.conn.server.list(all_tenants=True, detail=True)

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
        volume_id = entity[5]

        # get parent project
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            if parent is not None:
                objid = "%s//%s" % (parent.objid, id_gen())
                parent_id = parent.oid
            else:
                objid = "%s//none//none//%s" % (container.objid, id_gen())
                parent_id = None
        else:
            objid = "%s//none//none//%s" % (container.objid, id_gen())
            parent_id = None

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {"volume": {"boot": volume_id}},
            "parent": parent_id,
            "tags": resclass.default_tags,
        }
        return res

    def __get_volume_type(self, volume):
        volume_type_name = volume.get("volume_type")
        res = self.container.get_simple_resource(volume_type_name, entity_class=OpenstackVolumeType)
        return res

    #
    # patch
    #
    def __create_volume(
        self,
        volume_name,
        volume_type,
        volume_size,
        source_type,
        disk_object_id=None,
        boot=False,
        image_id=None,
        availability_zone=None,
        volume_resource_uuid=None,
    ):
        factory_params = {
            "name": volume_name,
            "desc": volume_name,
            "parent": self.parent_id,
            "ext_id": disk_object_id,
            "size": volume_size,
            "volume_type": volume_type,
            "sync": True,
            "source_volid": volume_resource_uuid,
            "snapshot_id": None,
            "imageRef": image_id,
            "availability_zone": availability_zone,
            "set_as_sync": True,
        }

        # create new volume
        volume, code = self.container.resource_factory(OpenstackVolume, **factory_params)
        volume_resource_uuid = volume.get("uuid")
        self.logger.debug("create volume resource %s" % volume_resource_uuid)

        # set bootable
        volume_resource = self.container.get_simple_resource(volume_resource_uuid)
        volume_resource.set_configs("bootable", boot)

        # link volume id to server
        self.add_link(
            "%s-%s-volume-link" % (self.oid, volume_resource.oid),
            "volume",
            volume_resource.oid,
            attributes={"boot": boot},
        )
        self.logger.debug("setup volume link from volume %s to server %s" % (volume_resource.oid, self.oid))

        return volume_resource_uuid

    def __name_index(self, physical_volume):
        attachment = next(a for a in physical_volume.get("attachments", []) if a["server_id"] == self.ext_id)
        if attachment is None:
            return None
        # Map /dev/vda in 0 /dev/vdb in 1 ...
        return ord(attachment["device"][-1]) - 97

    def __patch_missing_volume(self, physical_volume, exist=False, resource_volume=None):
        name_index = self.__name_index(physical_volume)
        if name_index is None:
            self.logger.warn("Volume %s is not attached to server %s" % (volume_id, server_name))
            return

        volume_id = physical_volume.get("id")
        server_name = self.name
        server_ext_id = self.ext_id
        volume_name = "%s-%s" % (server_name.replace("-server", "-volume"), name_index)
        volume_bootable = physical_volume.get("bootable")
        volume_type = self.__get_volume_type(physical_volume).oid

        if volume_bootable == "true":
            boot = True
        else:
            boot = False

        if exist is True:
            resource_volume.update_internal(name=volume_name, ext_id=volume_id)
        else:
            source_type = None
            volume_size = physical_volume.get("size")
            self.__create_volume(
                volume_name,
                volume_type,
                volume_size,
                source_type,
                disk_object_id=volume_id,
                boot=boot,
                image_id=None,
                volume_resource_uuid=None,
                availability_zone=physical_volume.get("availability_zone"),
            )

    def do_patch(self, **params):
        """method to execute to make custom resource operations useful to complete patch

        :param params: custom params required by task
        """
        # get already linked volume
        linked_volumes, tot = self.get_linked_resources(link_type="volume", size=-1)
        linked_volumes_idx = {str(v.ext_id): v for v in linked_volumes}
        self.logger.debug("do_patch - linked_volumes_idx: %s" % linked_volumes_idx)

        # get ops server disks
        l_volumes = self.container.conn.server.get_volumes(self.ext_id)
        conn_volume = self.container.conn.volume
        logger = self.logger
        for l_volume in l_volumes:
            vol_id = l_volume.get("id")
            vol_name = l_volume.get("name")
            self.logger.debug("do_patch - physical_volume - name: %s, id: %s" % (vol_name, vol_id))
            physical_volume = conn_volume.get(vol_id)
            linked_volume = linked_volumes_idx.get(vol_id)
            if linked_volume is None:
                logger.debug("physical_volume %s %s is not linked" % (vol_name, vol_id))
                self.__patch_missing_volume(physical_volume, exist=False)
            else:
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
            OpenstackServer.task_path + "patch_resource_pre_step",
            OpenstackServer.task_path + "patch_server_step",
            OpenstackServer.task_path + "patch_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

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
        for entity in entities:
            try:
                ext_obj = OpenstackServer.get_remote_server(controller, entity.ext_id, container, entity.ext_id)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn("", exc_info=1)

        return entities

    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param kvargs.controller: controller instance
        :param kvargs.entities: list of entities
        :param kvargs.container: container instance
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        # create index of related objs
        flavor_idx = {
            flavor["id"]: flavor for flavor in OpenstackServer.list_remote_flavor(controller, container.oid, container)
        }
        image_idx = {
            image["id"]: image for image in OpenstackServer.list_remote_image(controller, container.oid, container)
        }
        # volume_idx = {volume['id']: volume
        #               for volume in OpenstackServer.list_remote_volume(controller, container.oid, container)}

        for entity in entities:
            ext_obj = OpenstackServer.get_remote_server(controller, entity.ext_id, container, entity.ext_id)
            entity.set_physical_entity(ext_obj)
            entity.flavor_idx = flavor_idx
            entity.image_idx = image_idx
            # entity.volume_idx = volume_idx

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method. Extend this function to extend description
        info returned after query.

        :raise ApiManagerError:
        """
        ext_obj = self.get_remote_server(self.controller, self.ext_id, self.container, self.ext_id)
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
        :param kvargs.accessIPv4: IPv4 address that should be used to access this server. [optional] [TODO]
        :param kvargs.accessIPv6: IPv6 address that should be used to access this server. [optional] [TODO]
        :param kvargs.flavorRef: server cpu, ram and operating system
        :param kvargs.adminPass: The administrative password of the server. [TODO]
        :param kvargs.availability_zone: Specify the availability zone
        :param kvargs.metadata: server metadata
        :param kvargs.metadata.admin_pwd: root admin password used for guest customization
        :param kvargs.security_groups: One or more security groups.
        :param kvargs.networks: A networks object. Required parameter when there are multiple networks defined for the
            tenant. When you do not specify the networks parameter, the server attaches to the only network created
            for the current tenant. Optionally, you can create one or more NICs on the server. To provision the
            server instance with a NIC for a network, specify the UUID of the network in the uuid attribute in a
            networks object. [TODO: support for multiple network]
        :param kvargs.networks.uuid: is the id a tenant network.
        :param kvargs.networks.x.subnet_uuid: is the id a tenant network subnet.
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
        :param kvargs.block_device_mapping_v2.x.device_name: A path to the device for the volume that you want to use to
            boot the server. [TODO]
        :param kvargs.block_device_mapping_v2.x.source_type: The source type of the volume. A valid value is:
            snapshot - creates a volume backed by the given volume snapshot referenced via the
                       block_device_mapping_v2.uuid parameter and attaches it to the server
            volume: uses the existing persistent volume referenced via the block_device_mapping_v2.uuid parameter
                    and attaches it to the server
            image: creates an image-backed volume in the block storage service and attaches it to the server
        :param kvargs.block_device_mapping_v2.x.volume_size: size of volume in GB
        :param kvargs.block_device_mapping_v2.x.uuid: This is the uuid of source resource. The uuid points to different
            resources based on the source_type.
            If source_type is image, the block device is created based on the specified image which is retrieved
            from the image service.
            If source_type is snapshot then the uuid refers to a volume snapshot in the block storage service.
            If source_type is volume then the uuid refers to a volume in the block storage service.
        :param kvargs.block_device_mapping_v2.x.volume_type: The device volume_type. This can be used to specify the
            type of volume which the compute service will create and attach to the server. If not specified, the block
            storage service will provide a default volume type. It is only supported with source_type of image or
            snapshot.
        :param kvargs.block_device_mapping_v2.x.destination_type: Defines where the volume comes from. A valid value is
            local or volume. [default=volume]
        :param kvargs.block_device_mapping_v2.x.delete_on_termination: To delete the boot volume when the server is
            destroyed, specify true. Otherwise, specify false. [TODO]
        :param kvargs.block_device_mapping_v2.x.guest_format: Specifies the guest server disk file system format, such
            as ephemeral or swap. [TODO]
        :param kvargs.block_device_mapping_v2.x.boot_index: Defines the order in which a hypervisor tries devices when
            it attempts to boot the guest from storage. Give each device a unique boot index starting from 0. To
            disable a device from booting, set the boot index to a negative value or use the default boot index
            value, which is None. The simplest usage is, set the boot index of the boot device to 0 and use the
            default boot index value, None, for any other devices. Some hypervisors might not support booting from
            multiple devices; these hypervisors consider only the device with a boot index of 0. Some hypervisors
            support booting from multiple devices but only if the devices are of different types. For example, a
            disk and CD-ROM. [TODO]
        :param kvargs.block_device_mapping_v2.x.tag: An arbitrary tag. [TODO]
        :param kvargs.block_device_mapping_v2.x.clone: If True clone volume set using uuid
        :param kvargs.config_drive: enable inject of metadata using config drive
        :return: kvargs
        :raise ApiManagerError:
        """
        """
        :param kvargs.clone_server: [optional] if param exist contains master server used to clone volumes. When you
            set this param block_device_mapping_v2 is not used
        :param kvargs.clone_server_volume_type: [optional] The device volume_type. This is used to specify the type
            of volume which the compute service will create and attach to the cloned server volumes.        
        """

        # get project
        parent = kvargs.get("parent")
        parent = container.get_resource(parent, run_customize=False)
        kvargs["project_extid"] = parent.ext_id

        # get flavor
        flavor = container.get_resource(kvargs.get("flavorRef"), entity_class=OpenstackFlavor)
        flavor_ref = flavor.info().get("details")
        kvargs["flavor"] = flavor.ext_id

        # get availability_zone
        availability_zone = get_value(kvargs, "availability_zone", None)
        zones = {z["zoneName"] for z in container.system.get_compute_zones()}
        if availability_zone not in zones:
            raise ApiManagerError(
                "Openstack availability_zone %s does not exist" % availability_zone,
                code=404,
            )
        kvargs["availability_zone"] = availability_zone

        # get networks
        networks = kvargs.get("networks")
        for network in networks:
            obj = container.get_resource(network.get("uuid"), entity_class=OpenstackNetwork)
            network["uuid"] = obj.ext_id
            network["resource_id"] = obj.oid
            subnet_uuid = network.get("subnet_uuid", None)
            if subnet_uuid is not None:
                obj = container.get_resource(subnet_uuid, entity_class=OpenstackSubnet)
                network["subnet_uuid"] = obj.ext_id

        # get security_groups
        security_groups = kvargs.get("security_groups")
        sgs = []
        sgs_ext_id = []
        for security_group in security_groups:
            obj = container.get_resource(security_group, entity_class=OpenstackSecurityGroup)
            sgs.append(obj.name)
            sgs_ext_id.append(obj.ext_id)
        kvargs["security_groups"] = sgs
        kvargs["security_groups_ext_id"] = sgs_ext_id

        # set desc
        kvargs["desc"] = kvargs.get("desc", "Server %s" % kvargs["name"])

        # # get clone server
        # clone_server = kvargs.get('clone_server', None)
        #
        # # new server is a clone of another
        # if clone_server is not None:
        #     steps = [
        #         OpenstackServer.task_path + 'create_resource_pre_step',
        #         OpenstackServer.task_path + 'server_clone_physical_step',
        #         OpenstackServer.task_path + 'create_resource_post_step'
        #     ]
        #     kvargs['steps'] = steps
        #
        # # new server from scratch
        # else:
        # set main volume
        main_volume = {
            "boot_index": 0,
            "tags": None,
            "source_type": "image",
            "volume_size": flavor_ref["disk"],
            "destination_type": "volume",
        }
        volumes = [main_volume]

        # get volumes
        block_devices = kvargs.get("block_device_mapping_v2")
        for block_device in block_devices:
            boot_index = block_device.get("boot_index", None)
            source_type = block_device.get("source_type")

            if source_type == "image":
                obj = container.get_simple_resource(block_device["uuid"], entity_class=OpenstackImage)
                block_device["uuid"] = obj.ext_id
                min_disk_size = obj.get_min_disk()

                obj = container.get_simple_resource(block_device.get("volume_type"), entity_class=OpenstackVolumeType)
                block_device["volume_type"] = obj.oid

                if boot_index == 0:
                    if min_disk_size > 0 and block_device.get("volume_size") < min_disk_size:
                        block_device["volume_size"] = min_disk_size
                else:
                    raise ApiManagerError("Source type image is supported only for boot volume")

            elif source_type == "volume":
                obj = controller.get_simple_resource(block_device["uuid"], entity_class=OpenstackVolume)
                # if obj.parent_id != parent.oid:
                #     raise ApiManagerError('Volume project is different from server project')
                block_device["uuid"] = obj.oid

                # if original volume is in another container check voluem type
                if block_device.get("clone", False) is True:
                    obj = container.get_simple_resource(
                        block_device.get("volume_type"),
                        entity_class=OpenstackVolumeType,
                    )
                    block_device["volume_type"] = obj.oid

            # reconfigure main disk
            if boot_index == 0:
                volumes[0].update(block_device)

            # add new disk
            else:
                volumes.append(block_device)
        kvargs["block_device_mapping_v2"] = volumes

        steps = [
            OpenstackServer.task_path + "create_resource_pre_step",
            OpenstackServer.task_path + "server_create_physical_step",
            OpenstackServer.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackServer.task_path + "update_resource_pre_step",
            # OpenstackServer.task_path + 'server_update_physical_step',
            OpenstackServer.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.all: If True delete all the server attached volumes. If False delete only boot volume
        :return: kvargs
        :raise ApiManagerError:
        """
        # get parent
        kvargs["parent_id"] = self.parent_id
        steps = [
            OpenstackServer.task_path + "expunge_resource_pre_step",
            OpenstackServer.task_path + "server_expunge_physical_step",
            OpenstackServer.task_path + "server_expunge_ports_physical_step",
            OpenstackServer.task_path + "server_expunge_volumes_physical_step",
            OpenstackServer.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    #
    # info
    #
    def set_cache(self):
        """Cache object required infos.

        :return: Dictionary with object info.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        OpenstackResource.set_cache(self)

        operation.cache = False
        ext_obj = self.get_remote_server(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)
        operation.cache = True

    def info(self):
        """Get infos.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            self.volume_idx = {}
            remote_volumes = self.ext_obj.get("os-extended-volumes:volumes_attached", [])
            for remote_volume in remote_volumes:
                volume_extid = remote_volume["id"]
                self.volume_idx[volume_extid] = self.get_remote_volume(
                    self.controller, volume_extid, self.container, volume_extid
                )
            flavor = None
            if self.ext_obj.get("flavor", None) is not None and self.ext_obj["flavor"] != "":
                flavor_extid = self.ext_obj["flavor"]["id"]
                flavor = self.get_remote_flavor(self.controller, flavor_extid, self.container, flavor_extid)
            image = None
            if self.ext_obj.get("image", None) is not None and self.ext_obj["image"] != "":
                image_extid = self.ext_obj["image"]["id"]
                image = self.get_remote_image(self.controller, image_extid, self.container, image_extid)
            data = self.container.conn.server.info(self.ext_obj, volume_idx=self.volume_idx, flavor=flavor, image=image)

            info["details"] = data

        return info

    def __physical_detail(self):
        """Get physical server detail

        :return: dict like

            {'date': {'created': '2016-10-19T12:26:30Z',
                       'launched': '2016-10-19T12:26:39.000000',
                       'terminated': None,
                       'updated': '2016-10-19T12:26:39Z'},
             'flavor': {'cpu': 1, 'id': '2', 'memory': 2048},
             'metadata': {},
             'networks': [{'name':None,
                            'fixed_ips': [{'ip_address': '172.25.5.156',
                                            'subnet_id': '54fea9ab-9ba4-4c99-a729-f7ce52cae8fd'}],
                            'mac_addr': 'fa:16:3e:17:4d:87',
                            'net_id': 'dc8771c3-f76e-4da6-bb59-e25e67ebb8bb',
                            'port_id': '033e6918-13fc-4af1-818d-1bd65e0d3800',
                            'port_state': 'ACTIVE'}],
             'opsck:build_progress': 0,
             'opsck:config_drive': '',
             'opsck:disk_config': 'MANUAL',
             'opsck:image': '',
             'opsck:internal_name': 'instance-00000a44',
             'opsck:key_name': None,
             'opsck:opsck_user_id': '730cd1699f144275811400d41afa7645',
             'os': 'CentOS 7',
             'state': 'poweredOn',
             'volumes': [{'bootable': 'true',
                           'format': 'qcow2',
                           'id': '83935084-f323-4e31-9a2c-478f2826b46f',
                           'mode': 'rw',
                           'name': 'server-49405-root-volume',
                           'size': 20,
                           'storage': 'cinder-liberty.nuvolacsi.it#RBD',
                           'type': None}]}
        """
        server = self.ext_obj
        if server == {}:
            return {}

        meta = None

        # get flavor info
        flavor_ext_id = server["flavor"]["id"]
        flavor = self.get_remote_flavor(self.controller, flavor_ext_id, self.container, flavor_ext_id)
        # flavor = self.manager.flavor.get(oid=flavor_id)
        memory = flavor["ram"] or None
        cpu = flavor["vcpus"] or None

        # get volume info
        volumes_ids = server["os-extended-volumes:volumes_attached"]
        volumes = []
        boot_volume = None
        for volumes_id in volumes_ids:
            try:
                volume_extid = volumes_id["id"]
                vol = self.get_remote_volume(self.controller, volume_extid, self.container, volume_extid)
                volumes.append(vol)
                if vol["bootable"] == "true":
                    boot_volume = vol
            except:
                self.logger.warn("Server %s has not boot volume" % server["name"])

        # get image from boot volume
        if server["image"] is None or server["image"] == "" and boot_volume is not None:
            meta = boot_volume.get("volume_image_metadata", {})

        # get image
        elif server["image"] is not None and server["image"] != "":
            image_ext_id = server["image"]["id"]
            image = self.get_remote_image(self.controller, image_ext_id, self.container, image_ext_id)
            # image = self.manager.image.get(oid=server['image']['id'])
            meta = image.get("metadata", None)

        os = ""
        if meta is not None:
            try:
                os_distro = meta["os_distro"]
                os_version = meta["os_version"]
                os = "%s %s" % (os_distro, os_version)
            except:
                os = ""

        # networks
        networks = self.get_remote_server_port_interfaces(self.controller, self.ext_id, self.container, self.ext_id)

        # volumes
        server_volumes = []
        for volume in volumes:
            server_volumes.append(
                {
                    "id": volume["id"],
                    "type": volume["volume_type"],
                    "bootable": volume["bootable"],
                    "name": volume["name"],
                    "size": volume["size"],
                    "format": volume.get("volume_image_metadata", {}).get("disk_format", None),
                    "mode": volume.get("metadata").get("attached_mode", None),
                    "storage": volume.get("os-vol-host-attr:host", None),
                }
            )

        data = {
            "os": os,
            "state": self.container.conn.server.get_state(server["status"]),
            "flavor": {
                "id": flavor["id"],
                "memory": memory,
                "cpu": cpu,
            },
            "networks": networks,
            "volumes": server_volumes,
            "date": {
                "created": server["created"],
                "updated": server["updated"],
                "launched": server["OS-SRV-USG:launched_at"],
                "terminated": server["OS-SRV-USG:terminated_at"],
            },
            "metadata": server["metadata"],
            "opsck:internal_name": server["OS-EXT-SRV-ATTR:instance_name"],
            "opsck:opsck_user_id": server["user_id"],
            "opsck:key_name": server["key_name"],
            "opsck:build_progress": get_value(server, "progress", None),
            "opsck:image": server["image"],
            "opsck:disk_config": server["OS-DCF:diskConfig"],
            "opsck:config_drive": server["config_drive"],
            "security_groups": server.get("security_groups", []),
        }

        return data

    def detail(self):
        """Get details.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            # data = self.container.conn.server.detail(self.ext_obj)
            data = self.__physical_detail()

            # get networks
            for item in data.get("networks", []):
                obj = self.container.get_resource_by_extid(item["net_id"])
                item["net_id"] = getattr(obj, "uuid", None)
                obj = self.controller.get_resource_by_extid(item["port_id"])
                item["port_id"] = getattr(obj, "uuid", None)
                for fixed_ip in item["fixed_ips"]:
                    obj = self.container.get_resource_by_extid(fixed_ip["subnet_id"])
                    fixed_ip["subnet_id"] = getattr(obj, "uuid", None)

            # get volumes
            for item in data.get("volumes", []):
                obj = self.container.get_resource_by_extid(item["id"])
                item["id"] = getattr(obj, "uuid", None)

            # get flavor
            item = data.get("flavor", None)
            if item is not None:
                obj = self.container.get_resource_by_extid(item["id"])
                item["id"] = getattr(obj, "uuid", None)
                item["name"] = getattr(obj, "name", None)

            # ge security group
            for item in data.get("security_groups", []):
                obj = self.container.get_resource(item["name"], parent_id=self.parent_id)
                # obj, total = self.container.get_resources(parent=self.parent_id, name=item['name'])
                item.update(obj.small_info())

            info["details"].update(data)
        return info

    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        operation.cache = False
        self.container = self.controller.get_container(self.container_id)
        self.post_get()
        if self.ext_obj != {}:
            res = {"check": True, "msg": None}
        else:
            res = {"check": False, "msg": "no remote server found"}
        self.logger.debug2("Check resource %s: %s" % (self.uuid, res))
        return res

    #
    # additional info
    #
    def is_running(self):
        """True if server is running"""
        status = self.get_status()
        if status is not None and status == "poweredOn":
            return True
        else:
            return False

    @trace(op="view")
    def get_main_ip_address(self):
        """Get main ip address"""
        ip_address = None
        self.logger.warn(self.ext_obj)
        if self.ext_obj is not None:
            fixed_ips = list(self.ext_obj.get("addresses", {}).values())[0]
            if len(fixed_ips) > 0:
                ip_address = fixed_ips[0].get("addr")
        return ip_address

    @trace(op="view")
    def get_flavor_resource(self):
        """Get server flavor resource"""
        flavor = None
        if self.ext_obj is not None:
            if "flavor" in self.ext_obj:
                flavor_ext_id = self.ext_obj["flavor"]["id"]
                flavor = self.container.get_resource_by_extid(flavor_ext_id)

            self.logger.debug("Get openstack server %s flavor: %s" % (self.uuid, truncate(flavor)))
        return flavor

    @trace(op="view")
    def get_flavor(self):
        """Get server flavor"""
        flavor = {}
        if self.ext_obj is not None:
            flavor = self.__physical_detail().get("flavor", {})

        self.logger.debug("Get openstack server %s flavor: %s" % (self.uuid, truncate(flavor)))
        return flavor

    @trace(op="view")
    def get_volumes(self):
        """Get server volumes"""
        volumes = []
        if self.ext_obj is not None:
            volumes = self.container.conn.server.detail(self.ext_obj).get("volumes", [])

            for item in volumes:
                obj = self.container.get_resource_by_extid(item["id"])
                item["uuid"] = getattr(obj, "uuid", None)

        self.logger.debug("Get openstack server %s volumes: %s" % (self.uuid, truncate(volumes)))
        return volumes

    @trace(op="view")
    def get_volume_resources(self):
        """Get server volume resources"""
        volumes = []
        if self.ext_obj is not None:
            remote_volumes = self.container.conn.server.detail(self.ext_obj).get("volumes", [])

            for item in remote_volumes:
                obj = self.container.get_resource_by_extid(item["id"])
                obj.ext_obj = obj
                volumes.append(obj)

        self.logger.debug("Get openstack server %s volumes: %s" % (self.uuid, truncate(volumes)))
        return volumes

    def has_volume(self, volume_id):
        """check if server ha volume

        :param volume_id: volume resource id
        :return: True is volume is attached
        """
        volumes = [v["uuid"] for v in self.get_volumes()]
        if volume_id in volumes:
            return True
        return False

    @trace(op="view")
    def get_ports(self):
        """Get server ports"""
        ports = []
        if self.ext_id is not None and self.ext_id != "":
            ports = self.container.conn.server.get_port_interfaces(self.ext_id)

            for item in ports:
                obj = self.container.get_resource_by_extid(item["port_id"])
                item["uuid"] = getattr(obj, "uuid", None)

                # obj = self.container.get_resource_by_extid(item['net_id'])
                # item['net_id'] = getattr(obj, 'uuid', None)
                # obj = self.controller.get_resource_by_extid(item['port_id'])
                # item['uuid'] = getattr(obj, 'uuid', None)
                # for fixed_ip in item['fixed_ips']:
                #     obj = self.container.get_resource_by_extid(fixed_ip['subnet_id'])
                #     fixed_ip['subnet_id'] = getattr(obj, 'uuid', None)

        self.logger.debug("Get openstack server %s ports: %s" % (self.uuid, truncate(ports)))
        return ports

    @trace(op="view")
    def get_host(self):
        if self.ext_obj is not None:
            return self.ext_obj.get("OS-EXT-SRV-ATTR:host", None)
        return None

    def get_host_group(self):
        host_idx = {}
        aggregates = self.list_remote_aggregate(self.controller, self.container.oid, self.container)
        for aggregate in aggregates:
            hosts = aggregate.get("hosts", [])
            for host in hosts:
                host_idx[host] = aggregate.get("name")
        self.logger.warn(host_idx)
        host = self.get_host()
        host_group = None
        if host is not None:
            host_group = host_idx.get(host, "default")
        return host_group

    @trace(op="use")
    def get_hardware(self):
        """Get hardware info

        :return:
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")
        return {}

    @trace(op="use")
    def get_vnc_console(self, *args, **kwargs):
        """Get vnc console.

        :return: {'type': 'novnc', 'url': 'http://ctrl-liberty.nuvolacsi.it:6080/vnc_auto....' }
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        try:
            res = self.container.conn.server.get_vnc_console(self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s vnc console: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_guest_info(self):
        """Get guest info.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions("use")
        return {}

    @trace(op="use")
    def get_networks(self):
        """Get network info.

        :return: [<net small_info>,..]
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        res = []
        try:
            nets = self.container.conn.server.get_port_interfaces(self.ext_id)
            for item in nets:
                obj = self.container.get_resource_by_extid(item["net_id"])
                res.append(obj.small_info())
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s network info: %s" % (self.uuid, res))
        return res

    @trace(op="use")
    def get_storage(self):
        """Get storage info.

        :return: [{'device': '/dev/vda', 'uuid': 3165, 'serverId': 3166, 'volumeId': 3165}]
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        try:
            res = self.container.conn.server.get_volumes(self.ext_id)
            for item in res:
                obj = self.container.get_resource_by_extid(item["id"])
                item["uuid"] = obj.uuid
                obj = self.container.get_resource_by_extid(item["volumeId"])
                item["volumeId"] = obj.uuid
                item["serverId"] = self.uuid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s volumes: %s" % (self.uuid, res))
        return res

    def get_status(self):
        """Gets the status info for the server.

        :return: status info
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        res = None
        try:
            if self.ext_obj is not None:
                res = self.container.conn.server.get_state(self.ext_obj.get("status", None))
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)
        return res

    @trace(op="use")
    def get_runtime(self):
        """Gets the runtime info for the server.

        :return:

            {
                'availability_zone': {'name': 'nova'},
                'boot_time': '2016-10-19T12:26:39.000000',
                'host': {'id': '0b6fd70fc49154b1a640a201717c959efb97ad449fd2cea2c6420988',
                         'name': 'comp-liberty2-kvm.nuvolacsi.it'},
                'server_state': 'active',
                'task': None
            }

        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        try:
            res = self.container.conn.server.runtime(self.ext_obj)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s runtime: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_stats(self):
        """Gets the usage data for the server.

        :return:

            {
                'cpu0_time': 326410000000L,
                'memory': 2097152,
                'memory-actual': 2097152,
                'memory-available': 2049108,
                'memory-major_fault': 542,
                'memory-minor_fault': 5574260,
                'memory-rss': 667896,
                'memory-swap_in': 0,
                'memory-swap_out': 0,
                'memory-unused': 1665356,
                'tap033e6918-13_rx': 40355211,
                'tap033e6918-13_rx_drop': 0,
                'tap033e6918-13_rx_errors': 0,
                'tap033e6918-13_rx_packets': 627185,
                'tap033e6918-13_tx': 4006494,
                'tap033e6918-13_tx_drop': 0,
                'tap033e6918-13_tx_errors': 0,
                'tap033e6918-13_tx_packets': 11721,
                'vda_errors': -1,
                'vda_read': 163897856,
                'vda_read_req': 11610,
                'vda_write': 296491008,
                'vda_write_req': 45558
            }

        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        try:
            res = self.container.conn.server.diagnostics(self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s stats: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_metadata(self):
        """Lists the metadata for a specified server instance.

        :return: metatdata list
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        try:
            res = self.container.conn.server.get_metadata(self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s metadata: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_actions(self, action_id=None):
        """Get actions.

        :return:

            [
                {
                    'action': 'create',
                    'events': [{'event': 'compute__do_build_and_run_instance',
                                 'finish_time': '2016-10-19T12:26:39.000000',
                                 'result': 'Success',
                                 'start_time': '2016-10-19T12:26:31.000000',
                                 'traceback': None}],
                    'instance_uuid': 3166,
                    'message': None,
                    'project_id': 3137,
                    'request_id': 'req-cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0',
                    'start_time': '2016-10-19T12:26:30.000000',
                    'user_id': '730cd1699f144275811400d41afa7645'
                }
            ]

        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        try:
            res = self.container.conn.server.get_actions(self.ext_id, action_id=action_id)
            if not isinstance(res, list):
                res = [res]
            obj = self.container.get_resource_by_extid(res[0]["project_id"])
            for item in res:
                item["project_id"] = obj.uuid
                item["instance_uuid"] = self.uuid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack server %s actions: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_snapshots(self, snapshot_ext_id=None):
        """
        Get snapshots.

        :param snapshot_ext_id: snapshot id, it is the nova image id
        :return: List of dictionary with resp_fields
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")
        resp = []
        resp_fields = ["id", "name", "created_at", "status"]
        snapshot_ext_ids = None
        if snapshot_ext_id is not None:
            snapshot_ext_ids = [snapshot_ext_id]
        else:
            snapshot_ext_ids = self.get_attribs("snapshot_ext_ids")
        if snapshot_ext_ids is None:
            return resp
        for snapshot_ext_id in snapshot_ext_ids:
            try:
                r = self.container.conn.image.get(oid=snapshot_ext_id)
                res = {a: r[a] for a in resp_fields}
                resp.append(res)
            except OpenstackError as ex:
                raise ApiManagerError(ex.value)
        self.logger.debug("Get openstack server %s snapshots: %s" % (self.name, resp))
        return resp

    @trace(op="use")
    def delete_snapshots(self):
        """
        Delete snapshots
        NOTE: use this method in task

        :param conn: openstack connection to use
        """
        snapshot_ext_ids = self.get_attribs("snapshot_ext_ids", [])
        for snapshot_ext_id in snapshot_ext_ids:
            self.container.conn.image.delete(oid=snapshot_ext_id)
        self.set_configs("snapshot_ext_ids", [])

    def add_snapshot_ext_id(self, snapshot_ext_id):
        """
        Add snapshot_ext_id to server params
        :param snapshot_ext_id: snapshot_ext_id to be added, it is the nova image id
        """
        snapshot_ext_ids = self.get_attribs("snapshot_ext_ids", [])
        snapshot_ext_ids.append(snapshot_ext_id)
        self.set_configs("snapshot_ext_ids", snapshot_ext_ids)

    def del_snapshot_ext_id(self, snapshot_ext_id):
        """
        Del snapshot_ext_id from server params
        :param snapshot_ext_id: snapshot_ext_id to be removed, it is the nova image id
        """
        snapshot_ext_ids = self.get_attribs("snapshot_ext_ids", [])
        if snapshot_ext_id not in snapshot_ext_ids:
            self.logger.warn("snapshot_ext_ids %s not found in server attribs" % snapshot_ext_id)
        snapshot_ext_ids.remove(snapshot_ext_id)
        self.set_configs("snapshot_ext_ids", snapshot_ext_ids)

    def __check_volume_is_active(self, volume_extid):
        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackVolume.get_remote_volume(self.controller, volume_extid, self.container, volume_extid)
            status = inst["status"]
            if status == "available":
                break
            elif status == "error":
                raise Exception("Can not detach openstack volume %s" % volume_extid)
            sleep(2)

    def __detach_all_server_volumes(self, conn):
        """
        Detach all server volumes

        :param conn: openstack connection to use
        """
        attachments = conn.volume_v3.attachment.list(instance_id=self.ext_id)
        for attachment in attachments:
            volume_id = attachment["volume_id"]
            # get mountpoint
            volume = conn.volume_v3.get(volume_id)
            attachment["mountpoint"] = dict_get(volume, "attachments.0.device")
            # detach volume
            conn.volume_v3.detach_volume_from_server(volume_id, attachment["id"])
            self.logger.warn("detach volume %s" % volume_id)
        return attachments

    def __attach_all_server_volumes(self, conn, attachments):
        """
        Attach all server volumes

        :param conn: openstack connection to use
        """
        attachments = conn.volume_v3.attachment.list(instance_id=self.ext_id)
        for attachment in attachments:
            volume_id = attachment["volume_id"]
            conn.volume_v3.attach_volume_to_server(volume_id, self.ext_id, attachment["mountpoint"])
            self.logger.warn("attach volume %s" % volume_id)
        return attachments

    def __apply_volume_snapshot(self, conn, volume_snapshot_id):
        """
        Apply volume snapshot id to the associated volume

        :param volume_snapshot_id: cinder volume snapshot id
        """
        res = conn.volume_v3.snapshot.get(volume_snapshot_id)
        volume_id = res["volume_id"]
        # Apply the revert of volume_snapshot_id on volume_id
        conn.volume_v3.snapshot.revert_to(volume_id, volume_snapshot_id)
        self.__check_volume_is_active(volume_id)
        self.logger.warn("revert volume %s to snapshot %s" % (volume_id, volume_snapshot_id))

    def revert_to_snapshot(self, conn, snapshot_ext_id):
        """
        Revert server to a specific snapshot_ext_id.
        It is a nova image id.
        In this implementation we find the cinder volume snapshots and revert them.

        NOTE: use this method in task

        :param conn: openstack connection to use
        :param snapshot_ext_id: snapshot_ext_id it is the nova image id
        """
        try:
            image_res = conn.image.get(oid=snapshot_ext_id)
            import json

            block_device_mapping = json.loads(image_res["block_device_mapping"])
            # Get the cinder volumes snapshot associated to the nova image
            volume_snapshot_ids = [a["snapshot_id"] for a in block_device_mapping]
            # detach volumes
            attachments = self.__detach_all_server_volumes(conn)

            # Loop through snapshot
            # If a server volume not in cinder snapshot it remains in the same state
            for volume_snapshot_id in volume_snapshot_ids:
                self.__apply_volume_snapshot(conn, volume_snapshot_id)

            # reattach volumes
            self.__attach_all_server_volumes(conn, attachments)

        except OpenstackError as ex:
            raise ApiManagerError(ex.value)

    @trace(op="use")
    def get_security_groups(self):
        """Get security groups.

        :return: security group list
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("use")

        resp = []
        try:
            res = self.container.conn.server.security_groups(self.ext_id)
        except OpenstackError as ex:
            raise ApiManagerError(ex.value)
        for item in res:
            sg = self.controller.get_resource_by_extid(item["id"])
            sg.container = self.container
            resp.append(sg)

        self.logger.debug("Get openstack server %s security groups: %s" % (self.name, resp))
        return resp

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

    @trace(op="update")
    def start(self, *args, **kvargs):
        """Start server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        if self.is_running() is True:
            raise ApiManagerError("Server %s is already running" % self.uuid)

        steps = [OpenstackServer.task_path + "server_start_step"]
        res = self.action("start", steps, log="Start server", **kvargs)
        return res

    @trace(op="update")
    def stop(self, *args, **kvargs):
        """Stop server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        if self.is_running() is False:
            raise ApiManagerError("Server %s is not running" % self.uuid)

        steps = [OpenstackServer.task_path + "server_stop_step"]
        res = self.action("stop", steps, log="Stop server", **kvargs)
        return res

    @trace(op="update")
    def reboot(self, *args, **kvargs):
        """Rebbot server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [OpenstackServer.task_path + "server_reboot_step"]
        res = self.action("reboot", steps, log="Reboot server", **kvargs)
        return res

    @trace(op="update")
    def pause(self, *args, **kvargs):
        """Pause server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [OpenstackServer.task_path + "server_pause_step"]
        res = self.action("pause", steps, log="Pause server", **kvargs)
        return res

    @trace(op="update")
    def unpause(self, *args, **kvargs):
        """Unpause server.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [OpenstackServer.task_path + "server_unpause_step"]
        res = self.action("unpause", steps, log="Unpause server", **kvargs)
        return res

    @trace(op="update")
    def migrate(self, *args, **kvargs):
        """Migrate server.

        :param live: if True run live migration
        :param host: physical server where migrate [optional]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [OpenstackServer.task_path + "server_migrate_step"]
        res = self.action("migrate", steps, log="Migrate server", *args, **kvargs)
        return res

    @trace(op="update")
    def reset_state(self, state=None, *args, **kvargs):
        """Reset server state

        :param state: server state
        :return: {'taskid':..}, 202
        :raise ApiManagerError:

        state:
            * ACTIVE. The server is active.
            * BUILDING. The server has not finished the original build process.
            * DELETED. The server is permanently deleted.
            * ERROR. The server is in error.
            * HARD_REBOOT. The server is hard rebooting. This is equivalent to pulling the power plug on a physical
                server, plugging it back in, and rebooting it.
            * MIGRATING. The server is being migrated to a new host.
            * PASSWORD. The password is being reset on the server.
            * PAUSED. In a paused state, the state of the server is stored in RAM. A paused server continues to run in
              frozen state.
            * REBOOT. The server is in a soft reboot state. A reboot command was passed to the operating system.
            * REBUILD. The server is currently being rebuilt from an image.
            * RESCUED. The server is in rescue mode. A rescue image is running with the original server image attached.
            * RESIZED. Server is performing the differential copy of data that changed during its initial copy. Server
                is down for this stage.
            * REVERT_RESIZE. The resize or migration of a server failed for some reason. The destination server is being
              cleaned up and the original source server is restarting.
            * SOFT_DELETED. The server is marked as deleted but the disk images are still available to restore.
            * STOPPED. The server is powered off and the disk image still persists.
            * SUSPENDED. The server is suspended, either by request or necessity. This status appears for only the
              XenServer/XCP, KVM, and ESXi hypervisors. Administrative users can suspend an instance if it is
              infrequently used or to perform system maintenance. When you suspend an instance, its VM state is stored
              on disk, all memory is written to disk, and the virtual machine is stopped. Suspending an instance is
              similar to placing a device in hibernation; memory and vCPUs become available to create other instances.
            * UNKNOWN. The state of the server is unknown. Contact your cloud provider.
            * VERIFY_RESIZE. System is awaiting confirmation that the server is operational after a move or resize.
        """
        steps = [OpenstackServer.task_path + "server_reset_state_step"]
        res = self.action("reset_state", steps, log="Reset state to server", state=None, **kvargs)
        return res

    @trace(op="update")
    def add_snapshot(self, *args, **kvargs):
        """
        Add server snapshot

        :param name: snapshot name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            return kvargs
            # security_group = self.container.get_simple_resource(kvargs['security_group'],
            #                                                     entity_class=OpenstackSecurityGroup)
            # if self.has_security_group(security_group.oid) is False:
            #     security_group.check_active()
            #     kvargs['security_group'] = security_group.oid
            #     return kvargs
            # else:
            #     raise ApiManagerError('security group %s is already attached to server %s' %
            #                           (security_group.oid, self.oid))

        steps = ["beehive_resource.plugins.openstack.task_v2.ops_server.ServerTask.server_add_snapshot_step"]
        res = self.action("add_snapshot", steps, log="Add server snapshot", check=check, **kvargs)
        return res

    def check_snapshot(self, snapshot_ext_id):
        """
        Check that the snapshot_ext_id belong to the server
        :param snapshot_ext_id: snapshot_ext_id to be removed, it is the nova image ìd
        :return bool
        """
        snapshot_ext_ids = self.get_attribs("snapshot_ext_ids")
        return snapshot_ext_id in snapshot_ext_ids

    @trace(op="update")
    def del_snapshot(self, *args, **kvargs):
        """
        Remove server snapshot

        :param snapshot: snapshot id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            if self.check_snapshot(kvargs.get("snapshot")) is False:
                raise ApiManagerError("snapshot %s does not exist" % kvargs.get("snapshot"))
            return kvargs

        steps = ["beehive_resource.plugins.openstack.task_v2.ops_server.ServerTask.server_del_snapshot_step"]
        res = self.action("del_snapshot", steps, log="Remove server snapshot", check=check, **kvargs)
        return res

    @trace(op="update")
    def revert_snapshot(self, *args, **kvargs):
        """Revert server to snapshot

        :param snapshot: snapshot id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            if self.check_snapshot(kvargs.get("snapshot")) is False:
                raise ApiManagerError("snapshot %s does not exist" % kvargs.get("snapshot"))
            return kvargs

        steps = ["beehive_resource.plugins.openstack.task_v2.ops_server.ServerTask.server_revert_snapshot_step"]
        res = self.action(
            "revert_snapshot",
            steps,
            log="Revert server to snapshot",
            check=check,
            **kvargs,
        )
        return res

    @trace(op="update")
    def add_security_group(self, *args, **kvargs):
        """Add security group to server

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(
                kvargs["security_group"], entity_class=OpenstackSecurityGroup
            )
            if self.has_security_group(security_group.oid) is False:
                security_group.check_active()
                kvargs["security_group"] = security_group.oid
                return kvargs
            else:
                raise ApiManagerError(
                    "security group %s is already attached to server %s" % (security_group.oid, self.oid)
                )

        steps = ["beehive_resource.plugins.openstack.task_v2.ops_server.ServerTask.server_add_security_group_step"]
        res = self.action(
            "add_security_group",
            steps,
            log="Add security group to server",
            check=check,
            **kvargs,
        )
        return res

    @trace(op="update")
    def del_security_group(self, *args, **kvargs):
        """Remove security group from server

        :param security_group: security_group uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            security_group = self.container.get_simple_resource(
                kvargs["security_group"], entity_class=OpenstackSecurityGroup
            )
            if self.has_security_group(security_group.oid) is True:
                kvargs["security_group"] = security_group.oid
                return kvargs
            else:
                raise ApiManagerError("security group %s is not attached to server %s" % (security_group.oid, self.oid))

        steps = ["beehive_resource.plugins.openstack.task_v2.ops_server.ServerTask.server_del_security_group_step"]
        res = self.action(
            "del_security_group",
            steps,
            log="Remove security group from server",
            check=check,
            **kvargs,
        )
        return res

    @trace(op="update")
    def add_volume(self, *args, **kvargs):
        """Add volume to server

        :param volume: volume uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            volume = self.container.get_simple_resource(kvargs["volume"], entity_class=OpenstackVolume)
            if self.has_volume(volume.uuid) is False:
                # if self.is_linked(volume.oid) is False:
                kvargs["volume"] = volume.oid
                kvargs["volume_extid"] = volume.ext_id
                return kvargs
            else:
                raise ApiManagerError("volume %s is already attached to server %s" % (volume.oid, self.oid))

        steps = [OpenstackServer.task_path + "server_add_volume_step"]
        res = self.action("add_volume", steps, log="Add volume to server", check=check, **kvargs)
        return res

    @trace(op="update")
    def del_volume(self, *args, **kvargs):
        """Remove volume from server

        :param volume: volume uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            volume = self.container.get_simple_resource(kvargs["volume"], entity_class=OpenstackVolume)
            if self.has_volume(volume.uuid) is True:
                kvargs["volume"] = volume.oid
                kvargs["volume_extid"] = volume.ext_id
                return kvargs
            else:
                raise ApiManagerError("volume %s is not attached to server %s" % (volume.oid, self.oid))

        steps = [OpenstackServer.task_path + "server_del_volume_step"]
        res = self.action("del_volume", steps, log="Remove volume from server", check=check, **kvargs)
        return res

    @trace(op="update")
    def extend_volume(self, *args, **kvargs):
        """Extend volume of server

        :param volume: volume uuid or name
        :param volume_size: volume size
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            volume = self.container.get_simple_resource(kvargs["volume"], entity_class=OpenstackVolume)
            if self.has_volume(volume.uuid) is True:
                kvargs["volume"] = volume.oid
                kvargs["volume_extid"] = volume.ext_id
                return kvargs
            else:
                raise ApiManagerError("volume %s is not attached to server %s" % (volume.oid, self.oid))

        steps = [OpenstackServer.task_path + "server_extend_volume_step"]
        res = self.action("extend_volume", steps, log="Extend volume of server", check=check, **kvargs)
        return res

    @trace(op="update")
    def set_flavor(self, *args, **kvargs):
        """Set flavor to server.

        :param flavor: flavor uuid or name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            flavor = self.container.get_simple_resource(kvargs["flavor"], entity_class=OpenstackFlavor)
            kvargs["flavor"] = flavor.ext_id
            if self.get_flavor_resource().oid == flavor.oid:
                raise ApiManagerError("flavor %s already assigned to server %s" % (flavor.oid, self.oid))

            return kvargs

        steps = [OpenstackServer.task_path + "server_set_flavor_step"]
        res = self.action("set_flavor", steps, log="Set flavor to server", check=check, **kvargs)
        return res

    #
    # trilio backup
    #
    @trace(op="view")
    def get_trilio_backup(self):
        """Get trilio backup info

        :return: (workload_name, workload_id)
        """
        workload_name, workload_id = None, None
        if self.ext_obj is not None:
            workload_name = dict_get(self.ext_obj, "metadata.workload_name")
            workload_id = dict_get(self.ext_obj, "metadata.workload_id")

        self.logger.debug("Get openstack server %s trilio backup info: %s" % (self.oid, (workload_name, workload_id)))
        return workload_name, workload_id

    def has_backup(self):
        """check if server has backup job associated

        :return: True if server has backup workload associated
        """
        if self.get_trilio_backup() != (None, None):
            return True
        return False

    def has_backup_restore_point(self, restore_point):
        """check if server has backup restore point

        :param restore_point: restore point id
        :return: True if server has backup workload associated
        """
        job = self.get_backup_job()
        if job == {}:
            return False

        workload_id = job["id"]

        trilio_conn = self.get_trilio_manager()
        restore_points = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        restore_points = [s for s in restore_points if s.get("id") == restore_point]
        if len(restore_points) > 0:
            return True
        return False

    def get_backup_job(self):
        """get info of physical backup job associated

        :return: workload info
        """
        workload_name, workload_id = self.get_trilio_backup()
        if workload_id is None:
            self.logger.warning("no backup job found info for server %s" % self.oid)
            return {}

        trilio_conn = self.get_trilio_manager()
        workload = trilio_conn.workload.get(workload_id)
        self.logger.debug("get backup job info for server %s: %s" % (self.oid, workload))
        res = {
            "id": workload.get("id"),
            "name": workload.get("name"),
            "created": workload.get("created_at"),
            "updated": workload.get("updated_at"),
            "error": workload.get("error_msg"),
            "usage": dict_get(workload, "storage_usage.usage"),
            "schedule": dict_get(workload, "jobschedule"),
            # 'storage_usage': workload.get('storage_usage'),
            "status": workload.get("status"),
            "type": workload.get("workload_type_id"),
        }
        return res

    def get_backup_restore_points(self, job):
        """get backup restore points

        :param job: job id
        :return: snapshots list
        """
        if job == {}:
            self.logger.warning("no backup job found info for server %s" % self.oid)
            return []

        # snapshot_number = dict_get(job, 'schedule.retention_policy_value')
        # snapshot_number = 30
        # now = datetime.today()
        # date_from = '%s-%s-%sT' % (now.year, now.month, now.day - snapshot_number)
        # date_to = '%s-%s-%sT' % (now.year, now.month, now.day)

        workload_id = job
        trilio_conn = self.get_trilio_manager()
        snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)

        # check if server is in snapshot
        server_snapshots = []
        for snapshot in snapshots:
            snapshot = trilio_conn.snapshot.get(snapshot["id"])
            snapshot_instances = [i["id"] for i in snapshot.get("instances", [])]
            if self.ext_id in snapshot_instances:
                server_snapshots.append(snapshot)

        # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id, date_from=date_from, date_to=date_to)
        self.logger.debug(
            "get backup job %s restore points for server %s: %s" % (workload_id, self.oid, server_snapshots)
        )
        res = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "desc": s.get("description"),
                "created": s.get("created_at"),
                "type": s.get("snapshot_type"),
                "status": s.get("status"),
            }
            for s in server_snapshots
        ]
        return res

    def get_backup_restore_status(self, restore_point):
        """get status of restore

        :param restore_point: restore point id
        :return: restore list
        """
        workload_name, workload_id = self.get_trilio_backup()
        if workload_id is None:
            self.logger.warning("no backup restore status for server %s" % self.oid)
            return []

        self.container.get_connection(projectid=self.parent_id)
        trilio_conn = self.get_trilio_manager()

        # get workload
        workload = trilio_conn.workload.get(workload_id)
        self.logger.debug("get openstack trilio workload info for server %s: %s" % (self.oid, workload))

        # get snapshots
        # snapshot_number = dict_get(workload, 'jobschedule.retention_policy_value')
        # snapshot_number = 30
        # now = datetime.today()
        # date_from = '%s-%s-%sT' % (now.year, now.month, now.day - snapshot_number)
        # date_to = '%s-%s-%sT' % (now.year, now.month, now.day)
        # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id, date_from=date_from, date_to=date_to)
        snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
        snapshots = [s for s in snapshots if s.get("id") == restore_point]

        if len(snapshots) == 0:
            self.logger.warning("no backup restore point %s found for server %s" % (restore_point, self.oid))
            return []

        # get restores
        restores = trilio_conn.restore.list(snapshot_id=restore_point)
        self.logger.debug(
            "get backup restore point %s restores for server %s: %s" % (restore_point, self.oid, restores)
        )

        res = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "desc": s.get("description"),
                "time_taken": s.get("time_taken"),
                "size": s.get("size"),
                "uploaded_size": s.get("uploaded_size"),
                "status": s.get("status"),
                "progress_percent": s.get("progress_percent"),
                "created": s.get("created_at"),
                "updated": s.get("updated_at"),
                "finished": s.get("finished_at"),
                "msg": {
                    "warning": s.get("warning_msg"),
                    "progress": s.get("progress_msg"),
                    "error": s.get("error_msg"),
                },
            }
            for s in restores
        ]
        self.logger.debug("get backup restore status for server %s: %s" % (self.oid, res))
        return res

    # @trace(op='update')
    # def add_backup_restore_point(self, *args, **kvargs):
    #     """add physical backup restore point
    #
    #     :param full: if True make a full restore point. If False make an incremental restore point [default=True]
    #     :return: {'taskid':..}, 202
    #     :raise ApiManagerError:
    #     """
    #     def check(*args, **kvargs):
    #         if self.has_backup() is False:
    #             raise ApiManagerError('server %s has no backup job associated' % self.oid)
    #         return kvargs
    #
    #     steps = [OpenstackServer.task_path + 'server_add_backup_restore_point']
    #     res = self.action('add_backup_restore_point', steps, log='Add backup restore point to server', check=check,
    #                       **kvargs)
    #     return res

    # @trace(op='update')
    # def del_backup_restore_point(self, *args, **kvargs):
    #     """delete physical backup restore point
    #
    #     :param restore_point: restore point id
    #     :return: {'taskid':..}, 202
    #     :raise ApiManagerError:
    #     """
    #     def check(*args, **kvargs):
    #         job = self.get_backup_job()
    #         if job == {}:
    #             raise ApiManagerError('server %s has no backup job associated' % self.oid)
    #
    #         workload_id = job['id']
    #         restore_point = kvargs['restore_point']
    #         trilio_conn = self.container.get_trilio_connection()
    #         snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
    #         snapshots = [s for s in snapshots if s.get('id') == restore_point]
    #
    #         if len(snapshots) == 0:
    #             raise ApiManagerError('no backup restore point %s found for server %s' % (restore_point, self.oid))
    #
    #         return kvargs
    #
    #     steps = [OpenstackServer.task_path + 'server_del_backup_restore_point']
    #     res = self.action('del_backup_restore_point', steps, log='Delete backup restore point to server', check=check,
    #                       **kvargs)
    #     return res

    @trace(op="update")
    def restore_from_backup(self, *args, **kvargs):
        """restore server from backup

        :param restore_point: restore point id
        :param server_name: restored server name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            job = self.get_backup_job()
            if job == {}:
                raise ApiManagerError("server %s has no backup job associated" % self.oid)

            workload_id = job["id"]
            restore_point = kvargs["restore_point"]
            trilio_conn = self.get_trilio_manager()
            snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id)
            snapshots = [s for s in snapshots if s.get("id") == restore_point]

            if len(snapshots) == 0:
                raise ApiManagerError("no backup restore point %s found for server %s" % (restore_point, self.oid))

            return kvargs

        steps = [OpenstackServer.task_path + "server_restore_from_backup"]
        res = self.action(
            "restore_from_backup",
            steps,
            log="Restore server from backup",
            check=check,
            **kvargs,
        )
        return res
