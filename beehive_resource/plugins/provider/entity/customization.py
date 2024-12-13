# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.container import Resource
from beehive_resource.controller import ResourceController
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.zone import AvailabilityZone, AvailabilityZoneChildResource
from beehive_resource.plugins.provider.entity.applied_customization import (
    AppliedComputeCustomization,
)


class ComputeCustomization(ComputeProviderResource):
    """Compute customization"""

    objdef = "Provider.ComputeZone.ComputeCustomization"
    objuri = "%s/customizations/%s"
    objname = "customization"
    objdesc = "Provider ComputeCustomization"
    task_base_path = "beehive_resource.plugins.provider.task_v2.customization.ComputeCustomizationTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.child_classes = [AppliedComputeCustomization]

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
        # TODO: verify permissions

        info = Resource.detail(self)
        info["applied"] = [a.small_info() for a in self.get_applied_customization()]
        return info

    def get_applied_customization(self, oid=None):
        """Get applied customizations

        :param oid: applied customization id
        :return: resources list
        :raise ApiManagerError:
        """
        if oid is None:
            applied_customs, tot = self.controller.get_resources(
                parent=self.oid,
                run_customize=True,
                objdef=AppliedComputeCustomization.objdef,
            )
        else:
            applied_customs, tot = self.controller.get_resources(
                parent=self.oid,
                oid=oid,
                run_customize=True,
                objdef=AppliedComputeCustomization.objdef,
            )
            applied_customs = applied_customs[0]

        return applied_customs

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
        pass

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
        orchestrator_type = kvargs.get("type")
        orchestrator_tag = kvargs.get("orchestrator_tag")
        compute_zone_id = kvargs.get("parent")

        # get compute zone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        multi_avz = True

        if compute_zone is None:
            raise ApiManagerError("ComputeZone Parent not found")

        # get availability zones ACTIVE
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

        # set params
        params = {
            "compute_zone": compute_zone.oid,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeCustomization.task_base_path + "create_resource_pre_step",
        ]
        for availability_zone in availability_zones:
            step = {
                "step": ComputeCustomization.task_base_path + "create_zone_customization_step",
                "args": [availability_zone],
            }
            steps.append(step)
        steps.append(ComputeCustomization.task_path + "create_resource_post_step")
        kvargs["steps"] = steps

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
        :param kvargs.awx_project: remote orchestrator project reference
        :param kvargs.awx_project.scm_type: the source control system used to store the project
        :param kvargs.awx_project.scm_url: the location where the project is stored
        :param kvargs.awx_project.scm_branch: specific branch to checkout
        :return: kvargs
        :raise ApiManagerError:

        Ex.
            {
                ...
                'awx_project':{
                    'scm_type': ...
                    'scm_url': ..,
                    'scm_branch': ..,
                }
            }
        """
        # get zone
        compute_zone = self.get_parent()
        multi_avz = True

        # get availability zones
        avz_ids = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

        new_avz_ids = []
        for avz_id in avz_ids:
            self.controller: ResourceController
            avz = self.controller.get_resource(avz_id, entity_class=AvailabilityZone)
            site_id = avz.get_parent().oid
            zone_customizations, tot_zone_customizations = self.get_linked_resources(
                link_type="relation.%s" % site_id, authorize=False, run_customize=False
            )
            if tot_zone_customizations == 0:
                new_avz_ids.append(avz_id)

        # create task workflow
        steps = [ComputeCustomization.task_path + "update_resource_pre_step"]
        for availability_zone in new_avz_ids:
            step = {
                "step": ComputeCustomization.task_base_path + "create_zone_customization_step",
                "args": [availability_zone],
            }
            steps.append(step)
        steps.append(ComputeCustomization.task_path + "update_resource_post_step")
        kvargs["steps"] = steps
        kvargs["name"] = self.name

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
        applied_customs, total = self.get_linked_resources(link_type="applied_customs")
        if len(applied_customs) > 0:
            raise ApiManagerError(
                "ComputeCustomization %s has applied customizations associated and cannot be " "deleted" % self.oid
            )

        # get customizations
        customs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in customs]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs


class Customization(AvailabilityZoneChildResource):
    """Availability Zone Customization"""

    objdef = "Provider.Region.Site.AvailabilityZone.Customization"
    objuri = "%s/customizations/%s"
    objname = "customization"
    objdesc = "Provider Availability Zone Customization"
    task_base_path = "beehive_resource.plugins.provider.task_v2.customization.CustomizationTask."

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
        avz = container.get_simple_resource(avz_id)

        # select remote orchestrator
        # try:
        orchestrator = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=["awx"])
        # except Exception as e:
        #    controller.logger.error(str(e))
        #    steps = []
        #    kvargs["steps"] = steps
        #    kvargs["sync"] = True
        #    return kvargs
        # set container
        params = {"orchestrator": list(orchestrator.values())[0]}
        kvargs.update(params)

        # create task workflow
        steps = [
            Customization.task_base_path + "create_resource_pre_step",
            Customization.task_base_path + "create_awx_project_step",
            Customization.task_base_path + "create_resource_post_step",
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

    def get_awx_project(self):
        """get awx project resource

        :return: awx project resource
        """
        projects, total = self.get_linked_resources(link_type_filter="relation")
        if total > 0:
            project = projects[0]
            self.logger.debug("get zone customization %s awx project: %s" % (self.oid, project))
            return project
        else:
            raise ApiManagerError("no awx project in zone customization %s" % self.oid)
