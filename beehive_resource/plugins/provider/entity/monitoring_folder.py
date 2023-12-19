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
from beehive.common.task_v2 import prepare_or_run_task
from logging import getLogger
from beecell.simple import format_date
from beecell.simple import dict_get
from datetime import datetime
from beehive_resource.plugins.provider.entity.monitoring_team import (
    ComputeMonitoringTeam,
    MonitoringTeam,
)
from beehive_resource.plugins.provider.entity.monitoring_alert import (
    ComputeMonitoringAlert,
    MonitoringAlert,
)

logger = getLogger(__name__)


class ComputeMonitoringFolder(ComputeProviderResource):
    """Compute monitoring folder"""

    objdef = "Provider.ComputeZone.ComputeMonitoringFolder"
    objuri = "%s/monitoring_folders/%s"
    objname = "monitoring_folder"
    objdesc = "Provider ComputeMonitoringFolder"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_folder.ComputeMonitoringFolderTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder

        self.physical_folder = GrafanaFolder
        self.physical_folder = None

        self.child_classes = [
            ComputeMonitoringTeam,
            ComputeMonitoringAlert,
        ]

        self.actions = ["add_dashboard", "add_permission"]

    def get_physical_folder(self):
        """Get physical folder"""
        if self.physical_folder is None:
            # get main zone folder
            zone_instance = None
            res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
            zone_folders = res.get(self.oid)

            zone_folder: MonitoringFolder
            zone_folder = None
            if zone_folders is not None and len(zone_folders) > 0:
                zone_folder = zone_folders[0]
            self.logger.info("zone_folder: %s" % zone_folder)

            if zone_folder is not None:
                self.physical_folder = zone_folder.get_physical_folder()

        self.logger.debug("Get compute folder %s physical folder: %s" % (self.uuid, self.physical_folder))
        return self.physical_folder

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # self.logger.debug('+++++ info -')
        info = Resource.info(self)

        from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder

        physical_folder: GrafanaFolder
        physical_folder = self.get_physical_folder()
        # self.logger.debug('+++++ info - physical_folder: %s' % (physical_folder))
        if physical_folder is not None:
            info["dashboards"] = physical_folder.dashboards
            info["permissions"] = physical_folder.permissions

            # self.logger.debug('+++++ info - physical_folder.ext_id: %s' % (physical_folder.ext_id))
            info["physical_ext_id"] = physical_folder.ext_id
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # self.logger.debug('+++++ detail -')
        info = Resource.detail(self)

        from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder

        physical_folder: GrafanaFolder
        physical_folder = self.get_physical_folder()
        # self.logger.debug('+++++ detail - physical_folder: %s' % (physical_folder))
        if physical_folder is not None:
            info["dashboards"] = physical_folder.dashboards
            info["permissions"] = physical_folder.permissions

            # self.logger.debug('+++++ detail - physical_folder.ext_id: %s' % (physical_folder.ext_id))
            info["physical_ext_id"] = physical_folder.ext_id
        return info

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "monitoring.folders": 1,
        }
        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

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
        Use create when you want to create new grafana folder and connect to monitoring_folder.

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
        compute_zone: ComputeZone
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
            ComputeMonitoringFolder.task_base_path + "create_resource_pre_step",
        ]
        for availability_zone in availability_zones:
            logger.debug("folder - create in availability_zone: %s" % (availability_zone))
            step = {
                "step": ComputeMonitoringFolder.task_base_path + "create_zone_monitoring_folder_step",
                "args": [availability_zone],
            }
            steps.append(step)
        steps.append(ComputeMonitoringFolder.task_path + "create_resource_post_step")
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

        # get monitoring_folders
        customs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in customs]
        self.logger.debug("+++++ pre_delete - childs: %s" % (childs))

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs

    def add_dashboard(
        self,
        dashboard_folder_from,
        dashboard_to_search,
        organization,
        division,
        account,
        dash_tag,
        *args,
        **kvargs,
    ):
        """Add dashboard check function

        :param dashboard: dashboard name
        :return: kvargs
        """
        self.logger.debug(
            "add_dashboard - ComputeMonitoringFolder - dashboard_folder_from: %s" % (dashboard_folder_from)
        )
        self.logger.debug("add_dashboard - ComputeMonitoringFolder - dashboard_to_search: %s" % (dashboard_to_search))
        # self.logger.debug('add_dashboard - ComputeMonitoringFolder - folder_id_to: %s' % (folder_id_to))
        self.logger.debug("add_dashboard - ComputeMonitoringFolder - dash_tag: %s" % (dash_tag))
        self.logger.debug("add_dashboard - ComputeMonitoringFolder - organization: %s" % (organization))
        self.logger.debug("add_dashboard - ComputeMonitoringFolder - division: %s" % (division))
        self.logger.debug("add_dashboard - ComputeMonitoringFolder - account: %s" % (account))
        return {
            "dashboard_folder_from": dashboard_folder_from,
            "dashboard_to_search": dashboard_to_search,
            # 'folder_id_to': folder_id_to,
            "dash_tag": dash_tag,
            "organization": organization,
            "division": division,
            "account": account,
        }

    def add_permission(self, team_viewer, team_editor, *args, **kvargs):
        """Add dashboard check function

        :param team_viewer: team viewer
        :param team_editor: team editor
        :return: kvargs
        """
        self.logger.debug("add_permission - ComputeMonitoringFolder - team_viewer: %s" % (team_viewer))
        self.logger.debug("add_permission - ComputeMonitoringFolder - team_editor: %s" % (team_editor))
        return {
            "team_viewer": team_viewer,
            "team_editor": team_editor,
        }

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
        self.logger.debug("action - ComputeMonitoringFolder - action name: %s" % (name))

        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        monitoring_folder: MonitoringFolder
        monitoring_folder = self.get_monitoring_folder_instance()
        # self.logger.debug('action - monitoring_folder type: %s' % (type(monitoring_folder)))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug("action - ComputeMonitoringFolder - pre check - kvargs: {}".format(kvargs))
            kvargs = check(**kvargs)
            self.logger.debug("action - ComputeMonitoringFolder - after check - kvargs: {}".format(kvargs))

        # clean cache
        self.clean_cache()

        # get custom action params
        internal_step = {
            "step": ComputeMonitoringFolder.task_base_path + "send_action_to_monitoring_folder_step",
            "args": [monitoring_folder.oid],
        }
        internal_steps = kvargs.pop("internal_steps", [internal_step])
        # hypervisor = kvargs.get('hypervisor', self.get_hypervisor())

        # create internal steps
        run_steps = [ComputeMonitoringFolder.task_base_path + "action_resource_pre_step"]
        run_steps.extend(internal_steps)
        run_steps.append(ComputeMonitoringFolder.task_base_path + "action_resource_post_step")

        # manage params
        params = {
            "cid": self.container.oid,
            "id": self.oid,
            "objid": self.objid,
            "ext_id": self.ext_id,
            "action_name": name,
            "steps": run_steps,
            "alias": "%s.%s" % (self.__class__.__name__, name),
            # 'sync': True
        }
        params.update(kvargs)
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, params, sync=sync)
        self.logger.debug("action - %s compute monitoring folder %s using task" % (name, self.uuid))
        return res

    def get_monitoring_folder_instance(self):
        instances, total = self.get_linked_resources(link_type_filter="relation%")
        self.logger.debug("get_monitoring_folder_instance - total: %s " % total)

        res = None
        if total > 0:
            res = instances[0]
        return res


class MonitoringFolder(AvailabilityZoneChildResource):
    """Availability Zone MonitoringFolder"""

    objdef = "Provider.Region.Site.AvailabilityZone.MonitoringFolder"
    objuri = "%s/monitoring_folders/%s"
    objname = "monitoring_folder"
    objdesc = "Provider Availability Zone MonitoringFolder"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_folder.MonitoringFolderTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

        self.child_classes = [MonitoringTeam, MonitoringAlert]

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
            MonitoringFolder.task_base_path + "create_resource_pre_step",
            MonitoringFolder.task_base_path + "create_grafana_folder_step",
            MonitoringFolder.task_base_path + "create_resource_post_step",
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

    def get_grafana_folder(self):
        """get grafana folder resource

        :return: grafana folder resource
        """
        folders, total = self.get_linked_resources(link_type_filter="relation")
        if total > 0:
            from beehive_resource.plugins.grafana.entity.grafana_folder import (
                GrafanaFolder,
            )

            folder: GrafanaFolder
            folder = folders[0]
            self.logger.debug("get zone monitoring_folder %s grafana folder: %s" % (self.oid, folder))
            return folder
        else:
            # raise ApiManagerError('no grafana folder in zone monitoring_folder %s' % self.oid)
            self.logger.error("no grafana folder in zone monitoring_folder %s" % self.oid)

    def get_physical_folder(self):
        return self.get_grafana_folder()

    def add_dashboard(
        self,
        dashboard_folder_from,
        dashboard_to_search,
        organization,
        division,
        account,
        dash_tag,
        *args,
        **kvargs,
    ):
        """Add dashboard check function

        :param dashboard_to_search: dashboard name to search
        :return: kvargs
        """
        self.logger.debug("add_dashboard - MonitoringFolder - dashboard_folder_from: %s" % (dashboard_folder_from))
        self.logger.debug("add_dashboard - MonitoringFolder - dashboard_to_search: %s" % (dashboard_to_search))
        self.logger.debug("add_dashboard - MonitoringFolder - dash_tag: %s" % (dash_tag))
        self.logger.debug("add_dashboard - MonitoringFolder - organization: %s" % (organization))
        self.logger.debug("add_dashboard - MonitoringFolder - division: %s" % (division))
        self.logger.debug("add_dashboard - MonitoringFolder - account: %s" % (account))
        return {
            "dashboard_folder_from": dashboard_folder_from,
            "dashboard_to_search": dashboard_to_search,
            "dash_tag": dash_tag,
            "organization": organization,
            "division": division,
            "account": account,
        }

    def add_permission(self, team_viewer, team_editor: None, *args, **kvargs):
        """Add dashboard check function

        :param team_viewer: team viewer
        :param team_editor: team editor
        :return: kvargs
        """
        self.logger.debug("add_permission - MonitoringFolder - team_viewer: %s" % (team_viewer))
        self.logger.debug("add_permission - MonitoringFolder - team_editor: %s" % (team_editor))
        return {
            "team_viewer": team_viewer,
            "team_editor": team_editor,
        }

    def action(self, name, params):
        """Execute an action

        :param name: action name
        :param params: action params
        :param params.internal_step: custom internal_step [default=monitoring_folder_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        self.logger.debug("action - monitoring folder - action name: %s" % (name))

        folders, total = self.get_linked_resources(link_type_filter="relation")

        if total == 0:
            self.logger.error("action - monitoring folder - total: %s" % (total))
            return

        elif total > 0:
            self.logger.debug("action - monitoring folder - total: %s" % (total))
            from beehive_resource.plugins.grafana.entity.grafana_folder import (
                GrafanaFolder,
            )

            folder: GrafanaFolder
            folder = folders[0]
            self.logger.debug("action - monitoring folder id: %s - grafana folder: %s" % (self.oid, folder))
            self.logger.debug("action - folder container: %s" % (folder.container.oid))

            # run custom check function
            check = getattr(self, name, None)
            if check is not None:
                self.logger.debug("action - MonitoringFolder - pre check - params {}".format(params))
                params = check(**params)
                self.logger.debug("action - MonitoringFolder - after check - params {}".format(params))

            # get custom internal step
            internal_step = params.pop("internal_step", "monitoring_folder_action_step")

            # clean cache
            self.clean_cache()

            # create internal steps
            run_steps = [MonitoringFolder.task_base_path + "action_resource_pre_step"]
            # for orchestrator in orchestrators:
            # step = {'step': MonitoringFolder.task_path + internal_step, 'args': [orchestrator]}
            step = {"step": MonitoringFolder.task_base_path + internal_step, "args": []}
            run_steps.append(step)

            run_steps.append(MonitoringFolder.task_base_path + "action_resource_post_step")

            # manage params
            params.update(
                {
                    # 'cid': self.container.oid, # id del provider
                    "cid": folder.container.oid,  # id di Podto1Grafana
                    "id": self.oid,
                    "objid": self.objid,
                    "ext_id": self.ext_id,
                    "action_name": name,
                    "steps": run_steps,
                    "alias": "%s.%s" % (self.__class__.__name__, name),
                    # 'alias': '%s.%s' % (self.name, name)
                    "folder_id": folder.oid,
                }
            )
            params.update(self.get_user())
            self.logger.debug("action - post update - params {}".format(params))

            res = prepare_or_run_task(self, self.action_task, params, sync=True)
            self.logger.info("%s monitoring folder %s using task" % (name, self.uuid))
            return res
