# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.container import Resource
from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor


class ComputeFlavor(ComputeProviderResource):
    """Compute flavor"""

    objdef = "Provider.ComputeZone.ComputeFlavor"
    objuri = "%s/flavors/%s"
    objname = "flavor"
    objdesc = "Provider ComputeFlavor"
    task_path = "beehive_resource.plugins.provider.task_v2.flavor.FlavorTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

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
        :param kvargs.memory: available ram
        :param kvargs.disk: root disk size
        :param kvargs.disk_iops: disk iops
        :param kvargs.vcpus: number of virtual cpus
        :param kvargs.bandwidth: network bandwidth [optional]
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones
        :param kvargs.flavors: list of remote orchestrator flavor reference.
        :param kvargs.flavors.x.orchestrator_type: orchestrator type. Ex. openstack, vsphere
        :param kvargs.flavors.x.availability_zone: availability zone
        :param kvargs.flavors.x.orchestrator: orchestrator
        :param kvargs.flavors.x.flavor_id: flavor id
        :return: kvargs
        :raise ApiManagerError:

        Ex.

            {
                ...
                'flavors':{
                    <site_id>: {
                        'orchestrator_type':..,
                        'site_id':..,
                        'availability_zone_id':..,
                        'orchestrator_id':..,
                        ['flavor_id':..]
                    }
                }
            }
        """
        # get zone
        compute_zone = container.get_simple_resource(kvargs.get("parent"))

        # set attributes
        attrib = {
            "configs": {
                "memory": kvargs.get("memory"),
                "disk": kvargs.get("disk"),
                "disk_iops": kvargs.get("disk_iops"),
                "vcpus": kvargs.get("vcpus"),
                "bandwidth": kvargs.get("bandwidth"),
            }
        }
        kvargs["attribute"] = attrib
        kvargs["orchestrator_tag"] = kvargs.get("orchestrator_tag", "default")

        # import existing flavors
        if "flavors" in kvargs:
            # check flavors to import
            flavors = {}
            for flavor in kvargs.get("flavors"):
                orchestrator = controller.get_container(flavor.pop("orchestrator"))
                flavor["orchestrator_id"] = orchestrator.oid
                site_id = controller.get_simple_resource(flavor.pop("availability_zone"), entity_class=Site).oid
                flavor["site_id"] = site_id
                zones, tot = compute_zone.get_linked_resources(
                    link_type="relation.%s" % site_id,
                    run_customize=False,
                    with_perm_tag=False,
                )
                flavor["availability_zone_id"] = zones[0].oid
                flavor_id = flavor["flavor_id"]
                if flavor["orchestrator_type"] == "vsphere":
                    flavor["flavor_id"] = orchestrator.get_simple_resource(flavor_id, entity_class=VsphereFlavor).oid
                elif flavor["orchestrator_type"] == "openstack":
                    flavor["flavor_id"] = orchestrator.get_simple_resource(flavor_id, entity_class=OpenstackFlavor).oid
                try:
                    flavors[site_id].append(flavor)
                except:
                    flavors[site_id] = [flavor]

            # create import task workflow
            steps = []
            for site_id, flavors in flavors.items():
                substep = {
                    "step": ComputeFlavor.task_path + "import_zone_flavor_step",
                    "args": [site_id, flavors],
                }
                steps.append(substep)
            kvargs["steps"] = ComputeProviderResource.group_create_step(steps)

        # create new flavors
        else:
            # get availability zones ACTIVE
            multi_avz = kvargs.get("multi_avz")
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

            # create task workflow
            steps = []
            for availability_zone in availability_zones:
                substep = {
                    "step": ComputeFlavor.task_path + "create_zone_flavor_step",
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
        :param kvargs.flavors: list of remote orchestrator flavor reference.
        :param kvargs.flavors.x.orchestrator_type: orchestrator type. Ex. openstack, vsphere
        :param kvargs.flavors.x.availability_zone: availability zone
        :param kvargs.flavors.x.orchestrator: orchestrator
        :param kvargs.flavors.x.flavor_id: flavor id
        :return: kvargs
        :raise ApiManagerError:

        Ex.

            {
                ...
                'templates':{
                    <site_id>:{
                        'orchestrator_type':..,
                        'site_id':..,
                        'availability_zone_id':..,
                        'orchestrator_id':..,
                        ['flavor_id':..]
                    }
                }
            }
        """
        compute_zone = self.get_parent()

        # check flavor
        flavors = {}
        for flavor in kvargs.get("flavors", []):
            # pass ComputeFlavor name in order have prefix while generating Avalability.Flavor name
            flavor["name"] = self.name
            orchestrator = self.controller.get_container(flavor.pop("orchestrator"))
            flavor["orchestrator_id"] = orchestrator.oid
            site_id = self.controller.get_simple_resource(flavor.pop("availability_zone"), entity_class=Site).oid
            flavor["site_id"] = site_id
            zones, tot = compute_zone.get_linked_resources(link_type="relation.%s" % site_id, run_customize=False)
            zone_flavors, tot_zone_flavors = self.get_linked_resources(
                link_type="relation.%s" % site_id, run_customize=False
            )
            flavor["availability_zone_id"] = zones[0].oid
            flavor_id = flavor["flavor_id"]
            if flavor["orchestrator_type"] == "vsphere":
                flavor["flavor_id"] = orchestrator.get_simple_resource(flavor_id, entity_class=VsphereFlavor).oid
            elif flavor["orchestrator_type"] == "openstack":
                flavor["flavor_id"] = orchestrator.get_simple_resource(flavor_id, entity_class=OpenstackFlavor).oid

            # check flavor already linked
            if tot_zone_flavors == 0:
                try:
                    flavors[site_id].append(flavor)
                except:
                    flavors[site_id] = [flavor]

        self.logger.debug("Append new flavors: %s" % kvargs.get("flavors", []))

        # create task workflow
        steps = []
        for site_id, flavors in flavors.items():
            substep = {
                "step": ComputeFlavor.task_path + "update_zone_flavor_step",
                "args": [site_id, flavors],
            }
            steps.append(substep)
        kvargs["steps"] = self.group_update_step(steps)

        return kvargs


class Flavor(AvailabilityZoneChildResource):
    """Availability Zone Flavor"""

    objdef = "Provider.Region.Site.AvailabilityZone.Flavor"
    objuri = "%s/flavors/%s"
    objname = "flavor"
    objdesc = "Provider Availability Zone Flavor"
    task_path = "beehive_resource.plugins.provider.task_v2.flavor.FlavorTask."

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
        :param kvargs.flavors: list of
        :param kvargs.flavors.x.site_id:
        :param kvargs.flavors.x.availability_zone_id:
        :param kvargs.flavors.x.orchestrator_id: orchestrator id
        :param kvargs.flavors.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param kvargs.flavors.x.flavor_id: flavor id
        :return: kvargs
        :raise ApiManagerError:

        Ex.

            {
                ...
                'orchestrators':{
                    '1':{
                        'flavor':{
                            'id':..,
                        }
                    },
                    ...
                }
            }
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        flavors = kvargs.get("flavors", None)

        # get zone
        zone = container.get_resource(kvargs.get("parent"))

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
        orchestrator_ids = list(orchestrator_idx.keys())

        # assign flavor to orchestrator
        if flavors is not None:
            for t in flavors:
                orchestrator_id = t.get("orchestrator_id")
                # remove template if container not in subset selected via tag
                if str(orchestrator_id) in orchestrator_ids:
                    orchestrator_idx[str(orchestrator_id)]["flavor"] = {"id": t.get("flavor_id", None)}

            # create task workflow
            steps = []
            for item in orchestrator_idx.values():
                subtask = {
                    "step": Flavor.task_path + "flavor_import_orchestrator_resource_step",
                    "args": [item],
                }
                steps.append(subtask)

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
        :param flavors list of
        :param flavors.x.site_id:
        :param flavors.x.availability_zone_id:
        :param flavors.x.orchestrator_id: orchestrator id
        :param flavors.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param flavors.x.flavor_id: flavor id
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        flavors = kvargs.get("flavors", [])

        # get zone
        zone = self.get_parent()

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
        orchestrator_ids = list(orchestrator_idx.keys())

        # assign flavor to orchestrator
        for t in flavors:
            orchestrator_id = t.get("orchestrator_id")
            # remove template if container not in subset selected via tag
            if str(orchestrator_id) in orchestrator_ids:
                orchestrator_idx[str(orchestrator_id)]["flavor"] = {"id": t.get("flavor_id", None)}

        # create task workflow
        steps = []
        for item in orchestrator_idx.values():
            subtask = {
                "step": Flavor.task_path + "flavor_import_orchestrator_resource_step",
                "args": [item],
            }
            steps.append(subtask)

        kvargs["steps"] = AvailabilityZoneChildResource.group_update_task(steps)
        kvargs["sync"] = True

        return kvargs
