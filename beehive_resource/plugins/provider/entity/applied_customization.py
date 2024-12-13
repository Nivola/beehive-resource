# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource

from logging import getLogger

logger = getLogger(__name__)


class AppliedComputeCustomization(ComputeProviderResource):
    """Applied compute customization"""

    objdef = "Provider.ComputeZone.ComputeCustomization.AppliedComputeCustomization"
    objuri = "%s/customizations/%s/applied/%s"
    objname = "applied_customization"
    objdesc = "Provider AppliedComputeCustomization"
    task_base_path = "beehive_resource.plugins.provider.task_v2.applied_customization.AppliedComputeCustomizationTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.physical_job_template = None

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # TODO: verify permissions

        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        if self.physical_job_template is not None:
            job_template = self.physical_job_template.info()
            job_template["last_job"] = self.physical_job_template.get_last_job()
            info["job_template"] = job_template

        return info

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

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

        :raise ApiManagerError:
        """
        # # get main availability zones
        # if self.availability_zone_id is not None:
        #     self.availability_zone = self.controller.get_simple_resource(self.availability_zone_id)
        # self.logger.debug2('Get compute instance availability zones: %s' % self.availability_zone)

        # get main zone applied costomization
        res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
        zone_insts = res.get(self.oid, None)
        zone_inst = None
        if zone_insts is not None and len(zone_insts) > 0:
            zone_inst = zone_insts[0]

        # get job template
        if zone_inst is not None:
            job_templates, tot = zone_inst.get_linked_resources(link_type="relation")
            if tot > 0:
                self.physical_job_template = job_templates[0]
                self.physical_job_template.post_get()

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.
        Use create when you want to create new awx project and connect to customization.

        :param kvargs.controller: resource controller instance
        :param kvargs.container: container instance
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
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
        :return: kvargs
        :raise ApiManagerError:
        """
        compute_customization_id = kvargs.get("parent")
        compute_zone_id = kvargs.get("compute_zone")
        instances = kvargs.pop("instances")

        # get compute customization
        from beehive_resource.plugins.provider.entity.customization import (
            ComputeCustomization,
        )

        compute_customization = controller.get_simple_resource(
            compute_customization_id, entity_class=ComputeCustomization
        )

        # get compute zone
        compute_zone = controller.get_simple_resource(compute_zone_id)
        compute_zone.set_container(container)
        multi_avz = True

        # get availability zones ACTIVE
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

        # get instances
        instance_sites = []
        for instance in instances:
            obj = controller.get_simple_resource(instance.get("id"))
            # obj = controller.get_simple_resource(instance.get('id'), entity_class=ComputeInstance)
            obj.check_active()
            instance["id"] = obj.oid
            site_id = obj.get_attribs().get("availability_zone", None)
            if site_id not in instance_sites:
                instance_sites.append(site_id)

        params = {
            "orchestrator_tag": kvargs.get("orchestrator_tag", "default"),
            "compute_customization_id": compute_customization_id,
            "compute_zone_id": compute_zone.oid,
            "availability_zones": [avz for avz in availability_zones],
            "instances": instances,
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            AppliedComputeCustomization.task_base_path + "create_resource_pre_step",
        ]
        for availability_zone in availability_zones:
            # get project
            site_id = controller.get_simple_resource(availability_zone).parent_id
            # bypass availability zone if it does not contain instances to customize
            if site_id not in instance_sites:
                continue

            zone_customization = compute_customization.get_active_availability_zone_child(site_id)
            project = zone_customization.get_awx_project().name

            step = {
                "step": AppliedComputeCustomization.task_base_path + "create_zone_customization_step",
                "args": [availability_zone, project],
            }
            steps.append(step)

        steps.append(AppliedComputeCustomization.task_base_path + "create_resource_post_step")
        kvargs["steps"] = steps
        logger.debug("+++++ AppliedComputeCustomization - pre_create - kvargs: %s" % kvargs)

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.preserve: if True preserve resource when stack is removed
        :return: kvargs
        :raise ApiManagerError:
        """
        # check related objects
        # TODO

        # get applied customizations
        applied_customs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in applied_customs]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs


class AppliedCustomization(AvailabilityZoneChildResource):
    """Availability Zone Applied Customization"""

    objdef = "Provider.Region.Site.AvailabilityZone.AppliedCustomization"
    objuri = "%s/customizations/%s/applied/%s"
    objname = "applied_customization"
    objdesc = "Provider Availability Zone AppliedCustomization"
    task_base_path = "beehive_resource.plugins.provider.task_v2.applied_customization.AppliedCustomizationTask."

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
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrator tag [default=default]
        # TODO add missing params
        :return: kvargs
        :raise ApiManagerError:
        """
        avz_id = kvargs.get("parent")
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        # get availability_zone
        from beehive_resource.plugins.provider.entity.site import Site

        avz: Site = container.get_simple_resource(avz_id)

        # select remote orchestrator
        orchestrator = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=["awx"])

        # set container
        params = {"orchestrator": list(orchestrator.values())[0]}
        kvargs.update(params)

        # create task workflow
        steps = [
            AppliedCustomization.task_base_path + "create_resource_pre_step",
            AppliedCustomization.task_base_path + "create_awx_job_template_step",
            AppliedCustomization.task_base_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource physical id
        :return: kvargs
        :raise ApiManagerError:
        """
        # select physical orchestrator
        orchestrator_idx = self.get_orchestrators(select_types=["awx"])
        kvargs["steps"] = self.group_remove_step(orchestrator_idx)
        kvargs["sync"] = True

        return kvargs
