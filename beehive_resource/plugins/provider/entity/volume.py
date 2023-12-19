# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from random import randint
from datetime import datetime
from beecell.simple import format_date, id_gen, truncate
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import operation
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.container import Resource
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.provider.entity.aggregate import (
    ComputeProviderResource,
    get_task,
)
from beehive_resource.plugins.provider.entity.image import ComputeImage
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.volumeflavor import (
    ComputeVolumeFlavor,
    VolumeFlavor,
)
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume


class ComputeVolume(ComputeProviderResource):
    """Compute volume"""

    objdef = "Provider.ComputeZone.ComputeVolume"
    objuri = "%s/volumes/%s"
    objname = "volume"
    objdesc = "Provider ComputeVolume"
    task_path = "beehive_resource.plugins.provider.task_v2.volume.VolumeTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.main_zone_volume = None
        self.availability_zone = None
        self.flavor = None
        self.physical_volume = None
        self.instance = None

        try:
            self.availability_zone_id = self.get_attribs(key="availability_zone")
        except:
            self.availability_zone_id = None

        self.actions = [
            "set_flavor",
        ]

    def get_hypervisor(self):
        hypervisor = self.get_attribs(key="type")
        return hypervisor

    def get_hypervisor_tag(self):
        hypervisor = self.get_attribs(key="orchestrator_tag", default="default")
        return hypervisor

    def is_bootable(self):
        return self.get_attribs("configs.bootable")

    def is_encrypted(self):
        return self.get_attribs("configs.encrypted")

    def get_size(self):
        return self.get_attribs("configs.size")

    def __get_instance(self):
        if self.instance is not None:
            return self.instance.small_info()
        return None

    def __get_availability_zone_info(self, info):
        if self.availability_zone is not None:
            info["availability_zone"] = self.availability_zone.small_info()
        else:
            info["availability_zone"] = {}
        return info

    def __get_attachment_date(self):
        if self.instance is not None:
            return format_date(self.instance.link_creation)
        return None

    def __get_flavor_info(self):
        if self.flavor is not None:
            return self.flavor.small_info()
        return None

    def get_flavor(self):
        try:
            physical_flavor = self.physical_volume.get_volume_type()
            self.flavor = self.container.get_aggregated_resource_from_physical_resource(physical_flavor.oid)
        except:
            self.logger.warn("", exc_info=True)
            self.flavor = None
        return self.flavor

    def get_main_zone_volume(self):
        site = self.get_attribs().get("availability_zone", None)
        if site is None:
            return None
        site = self.controller.get_simple_resource(site).oid
        volumes, total = self.get_linked_resources(link_type_filter="relation.%s" % site, with_perm_tag=False)
        res = None
        if total == 1:
            res = volumes[0]
        return res

    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        operation.cache = False
        try:
            physical_volume = self.get_physical_volume()
        except ApiManagerError as ex:
            physical_volume = None
            check = False
            msg = ex.value

        if physical_volume is None:
            check = False
            msg = "physical volume does not exist"
        elif not (isinstance(physical_volume, OpenstackVolume) or isinstance(physical_volume, VsphereVolume)):
            check = False
            msg = "physical volume type is wrong"
        else:
            check = True
            msg = None
            pcheck = physical_volume.check().get("check")
            if pcheck is False:
                check = False
                msg = "no remote volume found"
        res = {"check": check, "msg": msg}
        self.logger.debug2("Check resource %s: %s" % (self.uuid, res))
        return res

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        try:
            info["hypervisor"] = self.get_hypervisor()
            info = self.__get_availability_zone_info(info)
            info["size"] = self.get_size()
            info["bootable"] = self.is_bootable()
            info["encrypted"] = self.is_encrypted()
            info["flavor"] = self.__get_flavor_info()
            info["instance"] = self.__get_instance()
            info["used"] = self.is_allocated()
            info["attachment"] = self.__get_attachment_date()
        except:
            self.logger.warn("", exc_info=True)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)

        try:
            info["hypervisor"] = self.get_hypervisor()
            info = self.__get_availability_zone_info(info)
            info["size"] = self.get_size()
            info["bootable"] = self.is_bootable()
            info["encrypted"] = self.is_encrypted()
            info["flavor"] = self.__get_flavor_info()
            info["instance"] = self.__get_instance()
            info["used"] = self.is_allocated()
        except:
            pass
        return info

    def is_allocated(self):
        if self.instance is None:
            return False
        return True

    def get_physical_volume(self):
        # get main zone instance
        zone_volume = None
        res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    zone_volume = zone_inst
        if zone_volume is not None:
            physical_volume = self.controller.get_directed_linked_resources_internal(
                resources=[zone_volume.oid], link_type="relation"
            ).get(zone_volume.oid, [])
            if len(physical_volume) > 1:
                raise ApiManagerError("too much physical volume are linked")
            elif len(physical_volume) > 0:
                physical_volume = physical_volume[0]
            else:
                physical_volume = None
            self.logger.debug("Get compute volume %s physical volume: %s" % (self.uuid, physical_volume))
            return physical_volume
        return None

    def get_quotas(self):
        """Get resource quotas

        :return: list of resoruce quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        list_snapshots = 0
        # rilevazione forse commentata in quanto lenta
        # if self.physical_volume is not None:
        #     list_snapshots = len(self.physical_volume.list_snapshots())

        quotas = {
            "compute.volumes": 1,
            "compute.snapshots": list_snapshots,
            "compute.blocks": self.get_attribs("configs.size"),
        }

        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param kvargs.controller: controller instance
        :param kvargs.entities: list of entities
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        from beehive_resource.plugins.provider.entity.instance import ComputeInstance

        resource_idx = {}
        resource_ids = []
        for e in entities:
            resource_idx[e.oid] = e
            resource_ids.append(e.oid)

        # get main availability zones
        zone_idx = controller.index_resources_by_id(entity_class=Site)

        for entity in entities:
            if entity.availability_zone_id is not None:
                entity.availability_zone = zone_idx.get(entity.availability_zone_id)
        controller.logger.debug2("Get compute instance availability zones")

        # get main zone instance
        res = controller.get_directed_linked_resources_internal(
            resources=resource_ids, link_type="relation%", run_customize=False
        )
        controller.logger.debug2("Get compute instance main zone instance")

        # get physical servers list
        zone_insts_ids = []
        for items in res.values():
            zone_insts_ids.extend([item.oid for item in items])

        controller.logger.debug2("Get zone volume physical volume")
        objdefs = [VsphereVolume.objdef, OpenstackVolume.objdef]
        remote_volumes = controller.get_directed_linked_resources_internal(
            resources=zone_insts_ids,
            link_type="relation",
            objdefs=objdefs,
            run_customize=True,
            customize_func="customize_list",
        )
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    physical_volumes = remote_volumes.get(zone_inst.oid, [])
                    resource_idx[resource].main_zone_instance = zone_inst
                    if len(physical_volumes) > 0 and physical_volumes[0] is not None:
                        resource_idx[resource].physical_volume = physical_volumes[0]

        # get flavor
        for entity in entities:
            entity.get_flavor()

        # # get other linked entitites
        # linked = controller.get_directed_linked_resources_internal(resources=resource_ids, link_type='flavor')
        # controller.logger.debug2('Get compute volume direct linked entities: %s' % truncate(linked))
        #
        # for resource, enitities in linked.items():
        #     res = resource_idx[resource]
        #     for entity in enitities:
        #         if isinstance(entity, ComputeVolumeFlavor):
        #             res.flavor = entity

        # get linked instances
        linked2 = controller.get_indirected_linked_resources_internal(resources=resource_ids)
        controller.logger.debug2("Get compute volume indirect linked entities: %s" % truncate(linked2))

        for resource, enitities in linked2.items():
            res = resource_idx[resource]
            for entity in enitities:
                if isinstance(entity, ComputeInstance):
                    res.instance = entity

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        from beehive_resource.plugins.provider.entity.instance import ComputeInstance

        # get main availability zones
        if self.availability_zone_id is not None:
            self.availability_zone = self.controller.get_simple_resource(self.availability_zone_id)
        self.logger.debug2("Get compute volume availability zones: %s" % self.availability_zone)

        # get main zone instance
        res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    self.main_zone_volume = zone_inst
                    self.logger.debug2("Get compute volume main zone instance: %s" % self.main_zone_volume)
                    self.physical_volume = self.main_zone_volume.get_physical_volume()
                    self.logger.debug2("Get compute volume physical volume: %s" % self.physical_volume)

        self.logger.warn(self.main_zone_volume)
        self.logger.warn(self.physical_volume)

        # # get other linked entitites
        # linked = self.controller.get_directed_linked_resources_internal(resources=[self.oid])
        # self.logger.debug2('Get compute volume direct linked entities: %s' % linked)
        #
        # for entity in linked.get(self.oid, []):
        #     if isinstance(entity, ComputeVolumeFlavor):
        #         self.flavor = entity

        # get flavor
        self.get_flavor()

        # get other linked entitites
        linked2 = self.controller.get_indirected_linked_resources_internal(resources=[self.oid])
        self.logger.debug2("Get compute volume indirect linked entities: %s" % linked2)

        for entity in linked2.get(self.oid, []):
            if isinstance(entity, ComputeInstance):
                self.instance = entity

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.
        If orchestrator_id and volume_id are specified volume is created from an existing physical volume.
        If storage, type and orchestrator_tag are specified volume is created as new in the selected orchestraators.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: site id or uuid
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones [default=False]
        :param kvargs.orchestrator_tag: orchestrators tag [optional]
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack [optional]
        :param kvargs.flavor: volume flavor
        :param kvargs.metadata: custom metadata. To create vsphere server in a non default cluster specify the key
            cluster=cluster_name and dvs=dvs_name. Ex. {'My Server Name' : 'Apache1'} [optional]
        :param kvargs.volume: The id or name of the source volume. The API creates a new volume with the same size as
            the source volume [optional]
        :param kvargs.snapshot: To create a volume from an existing snapshot, specify the id or name of the volume
            snapshot. The volume is created in same availability zone and with same size as the snapshot [optional]
        :param kvargs.image: The id or name of the image from which you want to create the volume [optional]
        :param kvargs.size: volume size in GB
        :return: extended kvargs
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get("type", None)
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        compute_zone_id = kvargs.get("parent")
        site_id = kvargs.get("availability_zone")
        multi_avz = kvargs.get("multi_avz")
        flavor = kvargs.get("flavor", None)
        volume = kvargs.get("volume", None)
        snapshot = kvargs.get("snapshot", None)
        image = kvargs.get("image", None)
        size = kvargs.get("size", None)
        metadata = kvargs.get("metadata", {})

        # get compute zone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)

        # get compute zone
        site = container.get_simple_resource(site_id)

        # get main availability zone
        main_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        # get availability zones ACTIVE
        availability_zones = []
        if multi_avz is True:
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
            availability_zones.remove(main_availability_zone)

        # get image
        if image is not None:
            image_obj = container.get_simple_resource(image, entity_class=ComputeImage)
            image_obj.check_active()
            image_volume_size = image_obj.get_attribs(key="configs.min_disk_size")
            kvargs["image"] = image_obj.oid

            if image_volume_size > size:
                size = image_volume_size
                container.logger.debug("Force volume size to image size to %s GB" % size)

            # get volume type
            flavor = container.get_simple_resource(flavor, entity_class=ComputeVolumeFlavor)
            flavor.check_active()
            kvargs["flavor"] = flavor.oid

        # get volume
        if volume is not None:
            volume_obj = container.get_simple_resource(volume, entity_class=ComputeVolume)
            volume_obj.check_active()
            kvargs["volume"] = volume_obj.oid

            # get volume type
            flavor = container.get_simple_resource(flavor, entity_class=ComputeVolumeFlavor)
            flavor.check_active()
            kvargs["flavor"] = flavor.oid

        # get snapshot
        # todo:

        # check datastore free space todo

        # set params
        params = {
            "orchestrator_tag": orchestrator_tag,
            "compute_zone": compute_zone.oid,
            "main_availability_zone": main_availability_zone,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.uuid,
                "configs": {"size": size, "bootable": None, "encrypted": None},
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeVolume.task_path + "create_resource_pre_step",
            ComputeVolume.task_path + "link_compute_volume_step",
            {
                "step": ComputeVolume.task_path + "create_zone_volume_step",
                "args": [main_availability_zone],
            },
        ]
        for zone_id in availability_zones:
            steps.append(
                {
                    "step": ComputeVolume.task_path + "create_zone_volume_step",
                    "args": [zone_id],
                }
            )
        steps.append(ComputeVolume.task_path + "create_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used in container resource_import_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource id to import [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :return: extended kvargs
        :raise ApiManagerError:
        """
        physical_id = kvargs.get("physical_id")
        params = kvargs.get("configs", {})

        # check share type from ext_id
        volume = controller.get_resource(physical_id)
        if isinstance(volume, OpenstackVolume) is True:
            orchestrator_type = "openstack"
        elif isinstance(volume, VsphereVolume) is True:
            orchestrator_type = "vsphere"
        else:
            raise ApiManagerError("Volume orchestrator type is not supported")

        # check parent compute zone match volume parent
        parent_id = volume.parent_id
        parent = container.get_aggregated_resource_from_physical_resource(parent_id)
        parent.set_container(container)
        kvargs["objid"] = "%s//%s" % (parent.objid, id_gen())
        kvargs["parent"] = parent.oid
        compute_zone = parent

        # get resource to import
        resource = controller.get_resource(physical_id)
        size = resource.get_size()
        metadata = {}
        orchestrator_tag = None

        # get main availability zone
        main_availability_zone = container.get_availability_zone_from_physical_resource(parent_id)
        mainsite = main_availability_zone.get_parent()
        main_availability_zone = main_availability_zone.oid
        multi_avz = params.get("multi_avz", True)

        # get volume flavor
        volume_type = resource.get_volume_type()
        volume_flavors, tot = volume_type.get_linked_resources(
            link_type="relation",
            entity_class=VolumeFlavor,
            objdef=VolumeFlavor.objdef,
            run_customize=False,
        )
        compute_volume_flavors, tot = volume_flavors[0].get_linked_resources(
            link_type="relation.%s" % mainsite.oid,
            entity_class=ComputeVolumeFlavor,
            objdef=ComputeVolumeFlavor.objdef,
            run_customize=False,
        )
        flavor = compute_volume_flavors[0].oid

        # # check quotas are not exceed for new volumes
        # new_quotas = {
        #     'compute.volumes': 1,
        #     'compute.blocks': int(size)
        # }
        # compute_zone.check_quotas(new_quotas)

        # set params
        params = {
            "orchestrator_tag": orchestrator_tag,
            "compute_zone": compute_zone.oid,
            "main_availability_zone": main_availability_zone,
            "flavor": flavor,
            "metadata": metadata,
            "multi_avz": multi_avz,
            "type": orchestrator_type,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": mainsite.uuid,
                "metadata": metadata,
                "configs": {
                    "size": size,
                    "bootable": resource.is_bootable(),
                    "encrypted": resource.is_encrypted(),
                },
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeVolume.task_path + "create_resource_pre_step",
            ComputeVolume.task_path + "link_compute_volume_step",
            {
                "step": ComputeVolume.task_path + "import_zone_volume_step",
                "args": [main_availability_zone],
            },
            ComputeVolume.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def do_import(self, *args, **kvargs):
        """sync import method.

        :param args: custom params
        :param kvargs: custom params
        :return: extended kvargs
        :raise ApiManagerError:
        """
        self.logger.warn(args)
        self.logger.warn(kvargs)

        # create_resource_pre_step No

        ##### link_compute_volume_step #####
        oid = kvargs.get("id")
        image_id = kvargs.get("image")
        volume_id = kvargs.get("volume")
        flavor_id = kvargs.get("flavor")
        physical_id = kvargs.get("physical_id")
        availability_zone_id = kvargs.get("main_availability_zone")

        # resource = self.container.get_simple_resource(oid)

        # link image to volume
        if image_id is not None:
            self.add_link(
                "%s-%s-image-link" % (self.oid, image_id),
                "image",
                image_id,
                attributes={},
            )
            self.logger.debug("Link image %s to volume %s" % (image_id, self.oid))

        elif volume_id is not None:
            orig_volume = self.container.get_simple_resource(volume_id)
            images, tot = orig_volume.get_linked_resources(link_type="image")
            # volume is root volume
            if len(images) > 0:
                image_id = images[0].oid
                self.add_link(
                    "%s-%s-image-link" % (self.oid, image_id),
                    "image",
                    image_id,
                    attributes={},
                )
                self.logger.debug("Link image %s to volume %s" % (image_id, self.oid))

        # link flavor to volume
        self.add_link(
            "%s-%s-flavor-link" % (self.oid, flavor_id),
            "flavor",
            flavor_id,
            attributes={},
        )
        self.logger.debug("Link flavor %s to volume %s" % (flavor_id, self.oid))
        ##### link_compute_volume_step #####

        ##### import_zone_volume_step args': [main_availability_zone]} #####
        # cid = params.get('cid')
        # oid = params.get('id')
        # flavor_id = params.get('flavor')
        # resource_id = params.get('physical_id')
        #
        # provider = task.get_container(cid)
        availability_zone = self.controller.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id

        # get availability zone flavor
        zone_flavor = self.container.get_simple_resource(flavor_id).get_active_availability_zone_child(site_id)
        # flavor = task.get_orm_linked_resources(flavor_id, link_type='relation.%s' % site_id)[0]
        # flavor_id = flavor.id

        # create zone volume params
        volume_params = {
            "type": kvargs.get("type"),
            "name": "%s-avz%s" % (kvargs.get("name"), site_id),
            "desc": "Availability Zone volume %s" % kvargs.get("desc"),
            "parent": availability_zone_id,
            "compute_volume": oid,
            "flavor": zone_flavor.oid,
            "size": kvargs.get("size"),
            "metadata": kvargs.get("metadata"),
            "main": True,
            "physical_id": physical_id,
            "attribute": {"main": True, "type": kvargs.get("type"), "configs": {}},
            "set_as_sync": True,
        }
        res, code = self.container.resource_import_factory(Volume, **volume_params)
        # volume_id = prepared_task['uuid']
        # run_sync_task(prepared_task, task, step_id)
        # self.logger.debug('Create volume %s in availability zone %s' % (volume_id, availability_zone_id))

        ##### import_zone_volume_step args': [main_availability_zone]} #####

        # create_resource_post_step NO

        return kvargs

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in update method. Extend this function to manipulate and
        validate patch input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            ComputeVolume.task_path + "patch_resource_pre_step",
            ComputeVolume.task_path + "patch_compute_volume_step",
            ComputeVolume.task_path + "patch_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        self.post_get()

        if self.is_allocated() is True:
            raise ApiManagerError("Volume %s is allocated and can not be deleted" % self.uuid)

        # get instances
        volumes, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [p.oid for p in volumes]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs

    #
    # snapshot
    #
    def exist_snapshot(self, snapshot_id):
        """Check volume snapshot exists

        :param snapshot_id: The uuid of the snapshot.
        :return: True
        :raise ApiManagerError:
        """
        try:
            res = self.physical_volume.get_snapshot(snapshot_id)
        except Exception as ex:
            err = "Volume %s snapshot does not exist: %s" % (self.uuid, snapshot_id)
            self.logger.error(err)
            raise ApiManagerError(err)

        return True

    # def list_snapshots(self):
    #     """List volume snapshots
    #
    #     :return: snapshot
    #     :raise ApiManagerError:
    #     """
    #     # verify permissions
    #     self.verify_permisssions('use')
    #
    #     try:
    #         res = self.physical_volume.list_snapshots()
    #         for item in res:
    #             item.pop('volume_id')
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)
    #
    #     self.logger.debug('Get volume %s snapshots: %s' % (self.uuid, res))
    #     return res
    #
    # def get_snapshot(self, snapshot_id):
    #     """Get volume snapshot
    #
    #     :param snapshot_id: snapshot id
    #     :return: snapshot
    #     :raise ApiManagerError:
    #     """
    #     # verify permissions
    #     self.verify_permisssions('use')
    #
    #     try:
    #         res = self.physical_volume.get_snapshot(snapshot_id)
    #         res.pop('volume_id')
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)
    #
    #     self.logger.debug('Get volume %s snapshot: %s' % (self.uuid, res))
    #     return res
    #
    # def add_snapshot(self, name):
    #     """Add volume snapshot
    #
    #     :param name: snapshot name
    #     :return: snapshot
    #     :raise ApiManagerError:
    #     """
    #     # verify permissions
    #     self.verify_permisssions('use')
    #
    #     try:
    #         res = self.physical_volume.add_snapshot(name)
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)
    #
    #     self.logger.debug('Add volume %s snapshot: %s' % (self.uuid, res))
    #     return res
    #
    # def delete_snapshot(self, snapshot_id):
    #     """Delete volume snapshot
    #
    #     :param snapshot_id: The uuid of the snapshot.
    #     :return: snapshot
    #     :raise ApiManagerError:
    #     """
    #     # verify permissions
    #     self.verify_permisssions('use')
    #
    #     self.exist_snapshot(snapshot_id)
    #
    #     try:
    #         res = self.physical_volume.delete_snapshot(snapshot_id)
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)
    #
    #     self.logger.debug('Delete volume %s snapshot: %s' % (self.uuid, snapshot_id))
    #     return res
    #
    # def revert_snapshot(self, snapshot_id):
    #     """Revert volume to snapshot
    #
    #     :param snapshot_id: The uuid of the snapshot.
    #     :return: snapshot
    #     :raise ApiManagerError:
    #     """
    #     # verify permissions
    #     self.verify_permisssions('use')
    #
    #     self.exist_snapshot(snapshot_id)
    #
    #     try:
    #         res = self.physical_volume.revert_snapshot(snapshot_id)
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)
    #
    #     self.logger.debug('Revert volume %s to snapshot: %s' % (self.uuid, snapshot_id))
    #     return res

    #
    # metrics
    #
    def get_metrics(self):
        """Get resource metrics

        :return: a dict like this

        {
            "id": "1",
            "uuid": "vm1",
            "metrics": [
                {
                    "key": "ram",
                    "value: 10,
                    "type": 1,
                    "unit": "GB"
                }],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"

        }
        """
        if self.has_quotas() is False:
            self.logger.warning("Compute volume %s has metric disabled" % self.oid)
            return {
                "id": self.oid,
                "uuid": self.uuid,
                "resource_uuid": self.uuid,
                "type": self.objdef,
                "metrics": [],
                "extraction_date": format_date(datetime.today()),
            }

        # base metric units
        metric_units = {"gbdisk_hi": "GB", "gbdisk_low": "GB"}

        # base metric label
        metric_labels = {}

        # get hypervisor specific metric label
        hypervisor = self.get_hypervisor()
        if hypervisor == "openstack":
            metric_labels.update({"gbdisk_hi": "vm_gbdisk_hi_os", "gbdisk_low": "vm_gbdisk_low_os"})
        elif hypervisor == "vsphere":
            metric_labels.update({"gbdisk_hi": "vm_gbdisk_hi_com", "gbdisk_low": "vm_gbdisk_low_com"})

        # if hypervisor == 'openstack' or (hypervisor == 'vsphere' and self.is_allocated() is True):
        if hypervisor == "openstack" or hypervisor == "vsphere":
            metrics = {
                metric_labels.get("gbdisk_low"): self.get_size(),
                metric_labels.get("gbdisk_hi"): 0,
            }
        else:
            metrics = {
                metric_labels.get("gbdisk_low"): 0,
                metric_labels.get("gbdisk_hi"): 0,
            }

        metric_units = {metric_labels.get(k): v for k, v in metric_units.items()}

        metrics = [{"key": k, "value": v, "type": 1, "unit": metric_units.get(k)} for k, v in metrics.items()]
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get compute volume %s metrics: %s" % (self.uuid, res))
        return res

    #
    # scheduled actions
    #
    def scheduled_action(self, action, schedule=None, params=None):
        """Create scheduled action

        :param action: action name
        :param schedule: schedule [optional]
        :param params: action params [optional]
        :return: schedule name
        :raises ApiManagerError if query empty return error.
        """
        self.verify_permisssions("update")

        if schedule is None:
            schedule = {"type": "timedelta", "minutes": 1}
        params = {
            "id": self.oid,
            "action": action,
            "action_params": params,
            "steps": [
                # self.task_path + 'remove_schedule_step',
                self.task_path
                + "run_scheduled_action_step"
            ],
        }
        schedule_name = super().scheduled_action(
            "%s.%s" % (action, self.oid),
            schedule,
            params=params,
            task_path="beehive_resource.plugins.provider.task_v2.",
            task_name="provider_resource_scheduled_action_task",
        )

        return schedule_name

    #
    # actions
    #
    def action(self, name, sync=False, *args, **kvargs):
        """Execute an action

        :param name: action name
        :param sync: if True run sync task, if False run async task
        :param args: custom positional args
        :param kvargs: custom key value args
        :param kvargs.internal_steps: custom action internal steps
        :param kvargs.hypervisor: custom action hypervisor
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        zone_volume = self.get_main_zone_volume()

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            kvargs = check(**kvargs)

        # clean cache
        self.clean_cache()

        # get custom action params
        internal_step = {
            "step": ComputeVolume.task_path + "send_action_to_zone_volume_step",
            "args": [zone_volume.oid],
        }
        internal_steps = kvargs.pop("internal_steps", [internal_step])
        hypervisor = kvargs.get("hypervisor", self.get_hypervisor())

        # create internal steps
        run_steps = [ComputeVolume.task_path + "action_resource_pre_step"]
        run_steps.extend(internal_steps)
        run_steps.append(ComputeVolume.task_path + "action_resource_post_step")

        # manage params
        params = {
            "cid": self.container.oid,
            "id": self.oid,
            "objid": self.objid,
            "ext_id": self.ext_id,
            "action_name": name,
            "hypervisor": hypervisor,
            "hypervisor_tag": self.get_hypervisor_tag(),
            "steps": run_steps,
            "alias": "%s.%s" % (self.__class__.__name__, name),
            # 'sync': True
        }
        params.update(kvargs)
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, params, sync=sync)
        self.logger.info("%s compute volume %s using task" % (name, self.uuid))
        return res

    def set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: compute flavor uuid or name
        :return: kvargs
        """
        res = self.container.get_resource(flavor, entity_class=ComputeVolumeFlavor, run_customize=False)

        # check hypervisor
        hypervisor = self.get_hypervisor()
        if hypervisor not in ["openstack"]:
            raise ApiManagerError("set flavor is not already supported for hypervisor %s" % hypervisor)

        # check flavor not already linked
        links, total = self.get_linked_resources(link_type="flavor")
        if links[0].oid == res.oid:
            raise ApiManagerError("Flavor %s already assigned to the volume %s" % (res.uuid, self.uuid))

        return {"flavor": res.oid}


class Volume(AvailabilityZoneChildResource):
    """Availability Zone Volume"""

    objdef = "Provider.Region.Site.AvailabilityZone.Volume"
    objuri = "%s/volumes/%s"
    objname = "volume"
    objdesc = "Provider Availability Zone Volume"
    task_path = "beehive_resource.plugins.provider.task_v2.volume.VolumeTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    def get_physical_volume(self):
        """Get remote physical volume from orchestrator

        :return:
        """
        inst_type = self.get_attribs().get("type")
        if inst_type == "openstack":
            objdef = OpenstackVolume.objdef
        elif inst_type == "vsphere":
            objdef = VsphereVolume.objdef
        try:
            volume = self.get_physical_resource(objdef)
        except:
            volume = None
        return volume

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller volume
        :param container: container volume
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.main: if True this is the main volume [optional]
        :param kvargs.compute_volume: compute volume id
        :param kvargs.orchestrator_id: orchestrators id [optional]
        :param kvargs.orchestrator_tag: orchestrators tag [optional]
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack [optional]
        :param kvargs.flavor: volume flavor
        :param kvargs.metadata: custom metadata. To create vsphere server in a non default cluster specify the key
            cluster=cluster_name and dvs=dvs_name. Ex. {'My Server Name' : 'Apache1'} [optional]
        :param kvargs.volume: The id or name of the source volume. The API creates a new volume with the same size as
            the source volume [optional]
        :param kvargs.snapshot: To create a volume from an existing snapshot, specify the id or name of the volume
            snapshot. The volume is created in same availability zone and with same size as the snapshot [optional]
        :param kvargs.image: The id or name of the image from which you want to create the volume [optional]
        :param kvargs.size: volume size in GB
        :return: extended kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag", None)
        orchestrator_type = kvargs.pop("type", None)
        orchestrator_id = kvargs.pop("orchestrator_id", None)
        main = kvargs.get("main")

        # get availability_zone
        availability_zone = controller.get_resource(kvargs.get("parent"))

        if orchestrator_id is not None:
            # main orchestrator is where volume will be created
            main_orchestrator = str(orchestrator_id)
            orchestrator_idx = availability_zone.get_orchestrators()
        else:
            # select remote orchestrators
            orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag)

            # select main available orchestrators
            available_main_orchestrators = []
            for k, v in orchestrator_idx.items():
                if orchestrator_type == v["type"]:
                    available_main_orchestrators.append(v)

            # main orchestrator is where volume will be created
            main_orchestrator = None
            if main is True:
                if len(available_main_orchestrators) > 0:
                    index = randint(0, len(available_main_orchestrators) - 1)
                    main_orchestrator = str(available_main_orchestrators[index]["id"])
                else:
                    raise ApiManagerError("No available orchestrator exist where create volume", code=404)

        # set container
        params = {
            "main_orchestrator": main_orchestrator,
            "orchestrators": orchestrator_idx,
        }
        kvargs.update(params)

        # create job workflow
        steps = [
            Volume.task_path + "create_resource_pre_step",
            Volume.task_path + "link_volume_step",
            Volume.task_path + "create_main_volume_step",
            Volume.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True
        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used
        in container resource_import_factory method.

        :param controller: resource controller volume
        :param container: container volume
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource id to import [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :param kvargs.main: if True this is the main volume [optional]
        :param kvargs.compute_volume: compute volume id
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack [optional]
        :param kvargs.flavor: volume flavor
        :param kvargs.metadata: custom metadata. To create vsphere server in a non default cluster specify the key
            cluster=cluster_name and dvs=dvs_name. Ex. {'My Server Name' : 'Apache1'} [optional]
        :param kvargs.size: volume size in GB
        :return: extended kvargs
        :raise ApiManagerError:
        """
        # create job workflow
        steps = [
            Volume.task_path + "create_resource_pre_step",
            Volume.task_path + "link_volume_step",
            Volume.task_path + "import_main_volume_step",
            Volume.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True
        return kvargs

    def do_import(self, *args, **kvargs):
        """sync import method.

        :param args: custom params
        :param kvargs: custom params
        :return: extended kvargs
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get("type")
        physical_id = kvargs.get("physical_id")

        # create_resource_pre_step - No

        # link_volume_step
        compute_volume_id = kvargs.get("compute_volume")
        compute_volume = self.container.get_simple_resource(compute_volume_id)
        availability_zone = self.get_parent()
        site_id = availability_zone.parent_id
        compute_volume.add_link(
            "%s-volume-link" % self.oid,
            "relation.%s" % site_id,
            self.oid,
            attributes={},
        )
        self.logger.debug("Link volume %s to compute volume %s" % (self.oid, compute_volume.oid))

        # import_main_volume_step
        physical_volume = self.controller.get_simple_resource(physical_id)
        helper = self.get_orchestrator_helper(orchestrator_type, {"id": None}, self)
        volume_id = helper.import_volume(physical_volume.oid)
        self.logger.debug("import volume: %s" % volume_id)

        # create_resource_post_step - No

        return kvargs

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in update method. Extend this function to manipulate and
        validate patch input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            Volume.task_path + "patch_resource_pre_step",
            Volume.task_path + "patch_zone_volume_step",
            Volume.task_path + "patch_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    #
    # actions
    #
    def action(self, name, params, hypervisor, hypervisor_tag):
        """Execute an action

        :param name: action name
        :param params: action params
        :param params.internal_step: custom internal_step [default=volume_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        orchestrator_idx = self.get_orchestrators_by_tag(hypervisor_tag, index_field="type")
        # if hypervisor is None return all the orchestrator else return only main orchestrator
        if hypervisor is not None:
            orchestrators = [orchestrator_idx[hypervisor]]
        else:
            orchestrators = list(orchestrator_idx.values())

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            params = check(**params)

        # get custom internal step
        internal_step = params.pop("internal_step", "volume_action_step")

        # clean cache
        self.clean_cache()

        # create internal steps
        run_steps = [Volume.task_path + "action_resource_pre_step"]
        for orchestrator in orchestrators:
            step = {"step": Volume.task_path + internal_step, "args": [orchestrator]}
            run_steps.append(step)
        run_steps.append(Volume.task_path + "action_resource_post_step")

        # manage params
        params.update(
            {
                "cid": self.container.oid,
                "id": self.oid,
                "objid": self.objid,
                "ext_id": self.ext_id,
                "action_name": name,
                "steps": run_steps,
                "alias": "%s.%s" % (self.__class__.__name__, name),
                # 'alias': '%s.%s' % (self.name, name)
            }
        )
        params.update(self.get_user())

        res = prepare_or_run_task(self, self.action_task, params, sync=True)
        self.logger.info("%s zone volume %s using task" % (name, self.uuid))
        return res

    def set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: compute flavor id
        :return: kvargs
        """
        site = self.get_site()
        compute_flavor = self.container.get_resource(flavor)
        flavors, total = compute_flavor.get_linked_resources(link_type_filter="relation.%s" % site.oid)
        return {"flavor": flavors[0].oid}
