# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive.common.apimanager import ApiManagerError


class ComputeTemplate(ComputeProviderResource):
    """Compute template AWX"""

    objdef = "Provider.ComputeZone.ComputeTemplate"
    objuri = "%s/templates/%s"
    objname = "template"
    objdesc = "Provider ComputeTemplate"
    task_path = "beehive_resource.plugins.provider.task_v2.template.TemplateTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.availability_zones = []
        self.template_id = None

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        info["availability_zones"] = self.availability_zones
        return info

    def get_template_id(self):
        return self.get_attribs("template_id")

    @staticmethod
    def check_template(controller, compute_zone, *args, **kvargs):
        # check template
        template_id = kvargs.get("template_id")

        if compute_zone.is_managed():
            awxclient = controller.awx_client
        else:
            # recuperare il Client AWX Private
            awxclient = None

        # check if template exist
        res = awxclient.job_templates_get(id=template_id)

        if res is None or len(res.get("results")) == 0:
            raise ApiManagerError("Template %s not exist")

        template = controller.get_resource_by_template_id(template_id)
        if template is not None:
            raise ApiManagerError("The Template resource associate with id %s already exist")

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info["availability_zones"] = self.availability_zones
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

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.compute_zone: compute zone id
        :param kvargs.template_id: awx template id reference

        :return: (:py:class:`dict`)

        :raise ApiManagerError:
        """
        compute_zone_id = kvargs.get("parent")
        template_id = kvargs.get("template_id")
        parameters = kvargs.get("parameters", {})

        # get compute zone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)

        if compute_zone is None:
            raise ApiManagerError("ComputeZone Parent not found")

        # get availability zones ACTIVE
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone)

        # check template_id
        #         ComputeTemplate.check_template(controller, compute_zone, *args, **kvargs)

        # set params
        params = {
            "compute_zone": compute_zone.oid,
            "attribute": {"awx_template": template_id, "parameters": parameters},
        }
        kvargs.update(params)

        g_zones = []
        for zone_id in availability_zones:
            subtask = {
                "task": ComputeTemplate.task_base_path + "task_create_zone_template",
                "args": [zone_id],
            }
            g_zones.append(subtask)

        tasks = [
            "beehive_resource.tasks.create_resource_pre",
            g_zones,
            "beehive_resource.tasks.create_resource_post",
        ]
        kvargs["tasks"] = tasks

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
        :param kvargs.template_id: id of template reference

        :return: (:py:class:`dict`)

        :raise ApiManagerError:
        """
        # get zone
        compute_zone = self.controller.get_resource(kvargs.get("parent"))
        if kvargs.get("uuid") is None:
            raise ApiManagerError("Resource to update not specified")

        template = self.controller.get_resource(kvargs.get("uuid"))
        if template is not None:
            raise ApiManagerError("Template %s not found" % (kvargs.get("uuid")))

        # check template_id
        #         ComputeTemplate.check_template(self.controller, compute_zone, *args, **kvargs)

        if kvargs.get("parameters", None) is not None:
            new_parameters = kvargs.get("parameters", None)
        else:
            new_parameters = template.get("params").get("parameters")

        params = {
            "template_id": kvargs.get("template_id"),
            "parameters": new_parameters,
        }
        kvargs["params"] = params

        return kvargs


class Template(AvailabilityZoneChildResource):
    """Availability Zone Template AWX"""

    objdef = "Provider.Region.Site.AvailabilityZone.Template"
    objuri = "%s/templates/%s"
    objname = "template"
    objdesc = "Provider Availability Zone Template"

    task_base_path = "beehive_resource.plugins.provider.task.template."
    create_task = "beehive_resource.tasks.job_resource_create"
    update_task = "beehive_resource.tasks.job_resource_update"
    expunge_task = "beehive_resource.tasks.job_resource_expunge"

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input kvargs before resource creation. This function is used
        in container resource_factory method.

        :param controller** (:py:class:`ResourceController`): resource controller instance
        :param container** (:py:class:`DummyContainer`): container instance
        :param args: custom kvargs
        :param kvargs: custom kvargs
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.configs:


        :return: {...}
        :raise ApiManagerError:
        """
        # get zone
        #         availability_zone = container.get_resource(kvargs.get('parent'))

        tasks = [
            "beehive_resource.tasks.create_resource_pre",
            ComputeTemplate.task_base_path + "task_link_template",
            "beehive_resource.tasks.create_resource_post",
        ]
        kvargs["tasks"] = tasks

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
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.custom_params: list of template params custom
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs
