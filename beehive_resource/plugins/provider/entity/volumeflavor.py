# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.container import Resource
from beehive_resource.plugins.openstack.entity.ops_volume_type import (
    OpenstackVolumeType,
)
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType


class ComputeVolumeFlavor(ComputeProviderResource):
    """Compute volume volumeflavor"""

    objdef = "Provider.ComputeZone.ComputeVolumeFlavor"
    objuri = "%s/volumeflavors/%s"
    objname = "volumeflavor"
    objdesc = "Provider ComputeVolumeFlavor"
    task_path = "beehive_resource.plugins.provider.task_v2.volumeflavor.VolumeFlavorTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

    def get_flavor_by_site(self, site_id):
        """Get flavor by parent site

        :param site_id: site id
        :return: network
        """
        return self.get_active_availability_zone_child(site_id)

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        return info

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.compute_zone: compute zone id
        :param kvargs.disk_iops: disk iops
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones
        :param kvargs.volume_types: list of remote orchestrator volume type reference. [optional]
        :param kvargs.volume_types.x.availability_zone:
        :param kvargs.volume_types.x.orchestrator: orchestrator
        :param kvargs.volume_types.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param kvargs.volume_types.x.volume_type_id: volume type id
        :return: kvargs
        :raise ApiManagerError:
        """
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        # get zone
        compute_zone = container.get_resource(kvargs.get("parent"), run_customize=False)
        # set attributes
        attrib = {
            "configs": {
                "disk_iops": kvargs.get("disk_iops"),
            }
        }
        kvargs["attribute"] = attrib
        kvargs["orchestrator_tag"] = kvargs.get("orchestrator_tag", "default")
        orchestrator_tag = kvargs["orchestrator_tag"]

        # import existing volumeflavors
        if "volume_types" in kvargs:
            # check volumeflavors to import
            volume_types = {}
            for volume_type in kvargs.get("volume_types"):
                orchestrator = controller.get_container(volume_type.pop("orchestrator"), connect=False)
                volume_type["orchestrator_id"] = orchestrator.oid
                volume_type["site_id"] = controller.get_simple_resource(
                    volume_type.pop("availability_zone"),
                    entity_class=Site,
                ).oid
                zones, tot = compute_zone.get_linked_resources(
                    link_type="relation.%s" % volume_type["site_id"],
                    entity_class=AvailabilityZone,
                    objdef=AvailabilityZone.objdef,
                    run_customize=False,
                )
                volume_type["availability_zone_id"] = zones[0].oid
                if volume_type["orchestrator_type"] == "vsphere":
                    volume_type["volume_type_id"] = orchestrator.get_simple_resource(
                        volume_type["volume_type_id"], entity_class=VsphereVolumeType
                    ).oid
                elif volume_type["orchestrator_type"] == "openstack":
                    volume_type["volume_type_id"] = orchestrator.get_simple_resource(
                        volume_type["volume_type_id"], entity_class=OpenstackVolumeType
                    ).oid
                try:
                    volume_types[volume_type["site_id"]].append(volume_type)
                except:
                    volume_types[volume_type["site_id"]] = [volume_type]

            # create import job workflow
            steps = []
            for site_id, volume_types in volume_types.items():
                substep = {
                    "step": ComputeVolumeFlavor.task_path + "import_zone_volumeflavor_step",
                    "args": [site_id, volume_types],
                }
                steps.append(substep)
            kvargs["steps"] = ComputeProviderResource.group_create_step(steps)

        # create new volumeflavors
        else:
            # get availability zones ACTIVE
            multi_avz = kvargs.get("multi_avz")
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

            # create job workflow
            steps = []
            for availability_zone in availability_zones:
                substep = {
                    "step": ComputeVolumeFlavor.task_path + "create_zone_volumeflavor_step",
                    "args": [availability_zone.oid],
                }
                steps.append(substep)
            kvargs["steps"] = ComputeProviderResource.group_create_step(steps)

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method. Extend
        this function to manipulate and validate update input params.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.volume_types: list of remote orchestrator volume type reference.
        :param kvargs.volume_types: list of remote orchestrator volume type reference. [optional]
        :param kvargs.volume_types.x.availability_zone:
        :param kvargs.volume_types.x.orchestrator: orchestrator
        :param kvargs.volume_types.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param kvargs.volume_types.x.volume_type_id: volume type id
        :return: kvargs
        :raise ApiManagerError:
        """
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        # get zone
        compute_zone = self.get_parent()
        # set attributes
        attrib = {
            "configs": {
                "disk_iops": kvargs.get("disk_iops"),
            }
        }
        kvargs["attribute"] = attrib
        kvargs["orchestrator_tag"] = kvargs.get("orchestrator_tag", "default")

        # check volumeflavors to import
        volume_types = {}
        for volume_type in kvargs.get("volume_types"):
            orchestrator = self.controller.get_container(volume_type.pop("orchestrator"), connect=False)
            volume_type["orchestrator_id"] = orchestrator.oid
            volume_type["site_id"] = self.controller.get_simple_resource(
                volume_type.pop("availability_zone"),
                entity_class=Site,
            ).oid
            zones, tot = compute_zone.get_linked_resources(
                link_type="relation.%s" % volume_type["site_id"],
                entity_class=AvailabilityZone,
                objdef=AvailabilityZone.objdef,
                run_customize=False,
            )
            zone_volumeflavors, tot = self.get_linked_resources(
                link_type="relation.%s" % volume_type["site_id"],
                entity_class=VolumeFlavor,
                objdef=VolumeFlavor.objdef,
                run_customize=False,
            )

            # bypass if flavor already linked
            if tot == 0:
                volume_type["availability_zone_id"] = zones[0].oid
                if volume_type["orchestrator_type"] == "vsphere":
                    volume_type["volume_type_id"] = orchestrator.get_simple_resource(
                        volume_type["volume_type_id"], entity_class=VsphereVolumeType
                    ).oid
                elif volume_type["orchestrator_type"] == "openstack":
                    volume_type["volume_type_id"] = orchestrator.get_simple_resource(
                        volume_type["volume_type_id"], entity_class=OpenstackVolumeType
                    ).oid
                try:
                    volume_types[volume_type["site_id"]].append(volume_type)
                except:
                    volume_types[volume_type["site_id"]] = [volume_type]

        # create import job workflow
        steps = []
        for site_id, volume_types in volume_types.items():
            substep = {
                "step": ComputeVolumeFlavor.task_path + "import_zone_volumeflavor_step",
                "args": [site_id, volume_types],
            }
            steps.append(substep)
        kvargs["steps"] = ComputeProviderResource.group_create_step(steps)

        return kvargs


class VolumeFlavor(AvailabilityZoneChildResource):
    """Availability Zone VolumeFlavor"""

    objdef = "Provider.Region.Site.AvailabilityZone.VolumeFlavor"
    objuri = "%s/volumeflavors/%s"
    objname = "volumeflavor"
    objdesc = "Provider Availability Zone VolumeFlavor"
    task_path = "beehive_resource.plugins.provider.task_v2.volumeflavor.VolumeFlavorTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

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
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.volume_types: list of
        :param kvargs.volume_types.x.site_id:
        :param kvargs.volume_types.x.availability_zone_id:
        :param kvargs.volume_types.x.orchestrator_id: orchestrator id
        :param kvargs.volume_types.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param kvargs.volume_types.x.volume_type_id: volumetype id
        :return: kvargs
        :raise ApiManagerError:

        Ex.

            {
                ...
                'orchestrators':{
                    '1':{
                        'volumeflavor':{
                            'id':..,
                        }
                    },
                    ...
                }
            }
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        volume_types = kvargs.get("volume_types", None)

        # get zone
        zone = container.get_resource(kvargs.get("parent"), run_customize=False)

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
        orchestrator_ids = list(orchestrator_idx.keys())

        # assign volumeflavor to orchestrator
        if volume_types is not None:
            for t in volume_types:
                orchestrator_id = t.get("orchestrator_id")
                # remove template if container not in subset selected via tag
                if str(orchestrator_id) in orchestrator_ids:
                    orchestrator_idx[str(orchestrator_id)]["volume_type"] = {"id": t.get("volume_type_id", None)}

            # create job workflow
            steps = []
            for item in orchestrator_idx.values():
                substep = {
                    "step": VolumeFlavor.task_path + "volumetype_import_orchestrator_resource_step",
                    "args": [item],
                }
                steps.append(substep)

            kvargs["steps"] = AvailabilityZoneChildResource.group_create_step(steps)

        kvargs["sync"] = True
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method. Extend
        this function to manipulate and validate update input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :param cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param orchestrator_tag: orchestrators tag
        :param volume_types list of
        :param volume_types.x.site_id:
        :param volume_types.x.availability_zone_id:
        :param volume_types.x.orchestrator_id: orchestrator id
        :param volume_types.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param volume_types.x.volume_type_id: volumeflavor id
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        volume_types = kvargs.get("volume_types")

        # get zone
        zone = self.get_parent()

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
        orchestrator_ids = list(orchestrator_idx.keys())

        # assign volume_types to orchestrator
        for t in volume_types:
            orchestrator_id = t.get("orchestrator_id")
            # remove template if container not in subset selected via tag
            if str(orchestrator_id) in orchestrator_ids:
                orchestrator_idx[str(orchestrator_id)]["volume_type"] = {"id": t.get("volume_type_id", None)}

        # create job workflow
        steps = []
        for item in orchestrator_idx.values():
            substep = {
                "step": VolumeFlavor.task_path + "volumetype_import_orchestrator_resource_step",
                "args": [item],
            }
            steps.append(substep)

        kvargs["steps"] = AvailabilityZoneChildResource.group_update_step(steps)
        kvargs["sync"] = True
        return kvargs
