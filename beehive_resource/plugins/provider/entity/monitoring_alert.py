# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from beehive.common.model import BaseEntity
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.zone import (
    AvailabilityZoneChildResource,
    ComputeZone,
)

# from beehive_resource.plugins.provider.entity.monitoring_folder import ComputeMonitoringFolder
from logging import getLogger

logger = getLogger(__name__)


# nome abbreviato per problema colonna DB
class ComputeMonitoringAlert(ComputeProviderResource):
    """Compute monitoring alert"""

    objdef = "Provider.ComputeZone.ComputeMonitoringFolder.ComputeMonitoringAlert"  # abbreviato per problema colonna DB
    objuri = "%s/monitoring_alerts/%s"
    objname = "monitoring_alert"
    objdesc = "Provider ComputeMonitoringAlert"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_alert.ComputeMonitoringAlertTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.child_classes = []

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
        # TODO metodo verificare se da implementare
        # info['applied'] = [a.small_info() for a in self.get_applied_monitoring_alert()]
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
        pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.
        Use create when you want to create new grafana alert and connect to monitoring_alert.

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
        # compute_zone_id = kvargs.get('compute_zone')
        folder_id = kvargs.get("parent")

        # get compute monitoring folder
        from beehive_resource.plugins.provider.entity.monitoring_folder import (
            ComputeMonitoringFolder,
        )

        compute_monitoring_folder: ComputeMonitoringFolder
        compute_monitoring_folder = container.get_simple_resource(folder_id)
        compute_monitoring_folder.check_active()
        compute_monitoring_folder.set_container(container)
        compute_zone = compute_monitoring_folder.get_parent()
        # compute_zone.oid - id della zone

        if compute_monitoring_folder is None:
            raise ApiManagerError("ComputeMonitoringFolder Parent not found")

        # get compute zone
        # compute_zone: ComputeZone
        # compute_zone = container.get_simple_resource(compute_zone_id)
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
                # 'type': 'grafana',
                "orchestrator_tag": orchestrator_tag,
            },
        }
        kvargs.update(params)

        compute_zone_model: BaseEntity
        compute_zone_model = compute_zone.model
        controller.logger.debug2("compute_zone_model.desc %s" % (compute_zone_model.desc))

        # create task workflow
        steps = [
            ComputeMonitoringAlert.task_base_path + "create_resource_pre_step",
        ]
        for availability_zone in availability_zones:
            logger.debug(": alert - create in availability_zone: %s" % (availability_zone))
            step = {
                "step": ComputeMonitoringAlert.task_base_path + "create_zone_monitoring_alert_step",
                "args": [availability_zone],
            }
            steps.append(step)
        steps.append(ComputeMonitoringAlert.task_path + "create_resource_post_step")
        kvargs["steps"] = steps
        # fv - forzatura
        kvargs["sync"] = False

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

        # get monitoring_alerts
        customs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in customs]
        self.logger.debug("+++++ pre_delete - childs: %s" % (childs))

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs


class MonitoringAlert(AvailabilityZoneChildResource):
    """Availability Zone MonitoringAlert"""

    objdef = "Provider.Region.Site.AvailabilityZone.MonitoringAlert"
    objuri = "%s/monitoring_alerts/%s"
    objname = "monitoring_alert"
    objdesc = "Provider Availability Zone MonitoringAlert"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_alert.MonitoringAlertTask."

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
        orchestrator = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=["grafana"])

        # set container
        params = {"orchestrator": list(orchestrator.values())[0]}
        kvargs.update(params)

        # create task workflow
        steps = [
            MonitoringAlert.task_base_path + "create_resource_pre_step",
            MonitoringAlert.task_base_path + "create_grafana_alert_step",
            MonitoringAlert.task_base_path + "create_resource_post_step",
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
        orchestrator_idx = self.get_orchestrators(select_types=["grafana"])
        self.logger.debug("+++++ pre_delete - orchestrator_idx: %s" % (orchestrator_idx))

        kvargs["steps"] = self.group_remove_step(orchestrator_idx)
        kvargs["sync"] = True

        return kvargs

    def get_grafana_alert(self):
        """get grafana alert resource

        :return: grafana alert resource
        """
        alerts, total = self.get_linked_resources(link_type_filter="relation")
        if total > 0:
            alert = alerts[0]
            self.logger.debug("get zone monitoring_alert %s grafana alert: %s" % (self.oid, alert))
            return alert
        else:
            raise ApiManagerError("no grafana alert in zone monitoring_alert %s" % self.oid)
