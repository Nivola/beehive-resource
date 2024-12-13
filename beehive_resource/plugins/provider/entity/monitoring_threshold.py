# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.model import BaseEntity
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.zone import (
    AvailabilityZoneChildResource,
    ComputeZone,
)
from logging import getLogger

logger = getLogger(__name__)


class ComputeMonitoringThreshold(ComputeProviderResource):
    """Compute monitoring threshold"""

    objdef = "Provider.ComputeZone.ComputeMonitoringThreshold"
    objuri = "%s/monitoring_thresholds/%s"
    objname = "monitoring_threshold"
    objdesc = "Provider ComputeMonitoringThreshold"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_threshold.ComputeMonitoringThresholdTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup

        self.physical_usergroup = ZabbixUsergroup
        self.physical_usergroup = None

        self.child_classes = []

        self.actions = [
            "add_user",
            "modify_user",
        ]

    def get_physical_usergroup(self):
        """Get physical usergroup"""
        if self.physical_usergroup is None:
            # get main zone usergroup
            zone_instance = None
            res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
            zone_thresholds = res.get(self.oid)

            zone_threshold: MonitoringThreshold = None
            if zone_thresholds is not None and len(zone_thresholds) > 0:
                zone_threshold = zone_thresholds[0]
            self.logger.info("zone_threshold: %s" % zone_threshold)

            if zone_threshold is not None:
                self.physical_usergroup = zone_threshold.get_physical_usergroup()

        self.logger.debug("Get compute threshold %s physical usergroup: %s" % (self.uuid, self.physical_usergroup))
        return self.physical_usergroup

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)

        from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup

        physical_usergroup: ZabbixUsergroup
        physical_usergroup = self.get_physical_usergroup()
        # self.logger.debug('+++++ info - physical_folder: %s' % (physical_folder))
        if physical_usergroup is not None:
            info["users_email"] = physical_usergroup.users_email
            info["user_severities"] = physical_usergroup.user_severities

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)

        from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup

        physical_usergroup: ZabbixUsergroup
        physical_usergroup = self.get_physical_usergroup()
        # self.logger.debug('+++++ info - physical_folder: %s' % (physical_folder))
        if physical_usergroup is not None:
            info["users_email"] = physical_usergroup.users_email
            info["user_severities"] = physical_usergroup.user_severities

        return info

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "monitoring.alerts": 1,
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
        Use create when you want to create new zabbix threshold and connect to monitoring_threshold.

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
        controller.logger.debug("pre_create - kvargs %s" % (kvargs))
        orchestrator_type = kvargs.get("type")
        orchestrator_tag = kvargs.get("orchestrator_tag")
        compute_zone_id = kvargs.get("parent")
        availability_zone = kvargs.get("availability_zone")
        controller.logger.debug("pre_create - availability_zone: %s" % (availability_zone))

        # get compute zone
        compute_zone: ComputeZone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        multi_avz = True

        if compute_zone is None:
            raise ApiManagerError("ComputeZone Parent not found")

        # get availability zones ACTIVE
        # availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
        site = container.get_simple_resource(availability_zone)
        controller.logger.debug("pre_create - site: %s" % (site))
        availability_zone_id = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        # set params
        params = {
            "compute_zone": compute_zone.oid,
            "attribute": {
                "type": orchestrator_type,
                # 'type': 'zabbix',
                "orchestrator_tag": orchestrator_tag,
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeMonitoringThreshold.task_base_path + "create_resource_pre_step",
        ]
        # for availability_zone in availability_zones:
        # logger.debug("pre_create - threshold - create in availability_zone: %s" % (availability_zone))
        step = {
            "step": ComputeMonitoringThreshold.task_base_path + "create_zone_monitoring_threshold_step",
            # "args": [availability_zone],
            "args": [availability_zone_id],
        }
        steps.append(step)

        steps.append(ComputeMonitoringThreshold.task_path + "create_resource_post_step")
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

        # get monitoring_thresholds
        customs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in customs]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs

    def add_user(self, triplet, users_email, severity, *args, **kvargs):
        """Add user check function

        :param users_email: user email
        :param severity: severity
        :return: kvargs
        """
        self.logger.debug("add_user - ComputeMonitoringThreshold - triplet: %s" % (triplet))
        self.logger.debug("add_user - ComputeMonitoringThreshold - users_email: %s" % (users_email))
        self.logger.debug("add_user - ComputeMonitoringThreshold - severity: %s" % (severity))
        return {
            "triplet": triplet,
            "users_email": users_email,
            "severity": severity,
        }

    def modify_user(self, triplet, users_email, severity, *args, **kvargs):
        """Modify user check function

        :param users_email: user email
        :param severity: severity
        :return: kvargs
        """
        self.logger.debug("modify_user - ComputeMonitoringThreshold - triplet: %s" % (triplet))
        self.logger.debug("modify_user - ComputeMonitoringThreshold - users_email: %s" % (users_email))
        self.logger.debug("modify_user - ComputeMonitoringThreshold - severity: %s" % (severity))

        severity_array = severity.split(",")
        for severity_item in severity_array:
            from beedrones.zabbix.action import ZabbixAction as BeedronesZabbixAction
            from beehive_resource.plugins.zabbix import ZabbixPlugin

            if severity_item == ZabbixPlugin.SEVERITY_DESC_DISASTER:
                pass
            elif severity_item == ZabbixPlugin.SEVERITY_DESC_HIGH:
                pass
            elif severity_item == ZabbixPlugin.SEVERITY_DESC_AVERAGE:
                pass
            elif severity_item == ZabbixPlugin.SEVERITY_DESC_WARNING:
                pass
            elif severity_item == ZabbixPlugin.SEVERITY_DESC_INFORMATION:
                pass
            else:
                raise ApiManagerError("Unknown severity %s" % severity_item)
        return {
            "triplet": triplet,
            "users_email": users_email,
            "severity": severity,
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
        self.logger.debug("action - ComputeMonitoringThreshold - action name: %s" % (name))

        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        monitoring_threshold: MonitoringThreshold
        monitoring_threshold = self.get_monitoring_threshold_instance()
        # self.logger.debug('action - monitoring_threshold type: %s' % (type(monitoring_threshold)))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug("action - ComputeMonitoringThreshold - pre check - kvargs: {}".format(kvargs))
            kvargs = check(**kvargs)
            self.logger.debug("action - ComputeMonitoringThreshold - after check - kvargs: {}".format(kvargs))

        # clean cache
        self.clean_cache()

        # get custom action params
        internal_step = {
            "step": ComputeMonitoringThreshold.task_base_path + "send_action_to_monitoring_threshold_step",
            "args": [monitoring_threshold.oid],
        }
        internal_steps = kvargs.pop("internal_steps", [internal_step])
        # hypervisor = kvargs.get('hypervisor', self.get_hypervisor())

        # create internal steps
        run_steps = [ComputeMonitoringThreshold.task_base_path + "action_resource_pre_step"]
        run_steps.extend(internal_steps)
        run_steps.append(ComputeMonitoringThreshold.task_base_path + "action_resource_post_step")

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
        self.logger.debug("action - %s compute monitoring threshold %s using task" % (name, self.uuid))
        return res

    def get_monitoring_threshold_instance(self):
        instances, total = self.get_linked_resources(link_type_filter="relation%")
        self.logger.debug("get_monitoring_threshold_instance - total: %s " % total)

        res = None
        if total > 0:
            res = instances[0]
        return res


class MonitoringThreshold(AvailabilityZoneChildResource):
    """Availability Zone MonitoringThreshold"""

    objdef = "Provider.Region.Site.AvailabilityZone.MonitoringThreshold"
    objuri = "%s/monitoring_thresholds/%s"
    objname = "monitoring_threshold"
    objdesc = "Provider Availability Zone MonitoringThreshold"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_threshold.MonitoringThresholdTask."

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
        # orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        orchestrator_tag = kvargs.get("orchestrator_tag", "tenant")

        # get availability_zone
        avz = container.get_simple_resource(avz_id)

        # select remote orchestrator
        orchestrator = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=["zabbix"])

        # set container
        params = {"orchestrator": list(orchestrator.values())[0]}
        kvargs.update(params)

        # create task workflow
        steps = [
            MonitoringThreshold.task_base_path + "create_resource_pre_step",
            MonitoringThreshold.task_base_path + "create_zabbix_threshold_step",
            MonitoringThreshold.task_base_path + "create_resource_post_step",
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
        # orchestrator_idx = self.get_orchestrators(select_types=["zabbix"])

        # orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        orchestrator_tag = kvargs.get("orchestrator_tag", "tenant")
        orchestrator_idx = self.get_orchestrators_by_tag(orchestrator_tag, select_types=["zabbix"])

        kvargs["steps"] = self.group_remove_step(orchestrator_idx)
        kvargs["sync"] = True

        return kvargs

    def get_zabbix_usergroup(self):
        """get zabbix usergroup resource

        :return: zabbix usergroup resource
        """
        from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup

        usergroups, total = self.get_linked_resources(link_type_filter="relation", objdef=ZabbixUsergroup.objdef)
        if total > 0:
            usergroup = usergroups[0]
            self.logger.debug("get zone monitoring_threshold %s zabbix usergroup: %s" % (self.oid, usergroup))
            return usergroup
        else:
            # raise ApiManagerError("no zabbix usergroup in zone monitoring_threshold %s" % self.oid)
            self.logger.warning("no zabbix usergroup in zone monitoring_threshold %s" % self.oid)

    def get_physical_usergroup(self):
        return self.get_zabbix_usergroup()

    def add_user(self, triplet, users_email, severity, *args, **kvargs):
        """Add user check function

        :param users_email: user email
        :return: kvargs
        """
        self.logger.debug("add_user - MonitoringThreshold - triplet: %s" % (triplet))
        self.logger.debug("add_user - MonitoringThreshold - users_email: %s" % (users_email))
        self.logger.debug("add_user - MonitoringThreshold - severity: %s" % (severity))
        return {
            "triplet": triplet,
            "users_email": users_email,
            "severity": severity,
        }

    def modify_user(self, triplet, users_email, severity, *args, **kvargs):
        """Modify user check function

        :param users_email: user email
        :return: kvargs
        """
        self.logger.debug("modify_user - MonitoringThreshold - triplet: %s" % (triplet))
        self.logger.debug("modify_user - MonitoringThreshold - users_email: %s" % (users_email))
        self.logger.debug("modify_user - MonitoringThreshold - severity: %s" % (severity))
        return {
            "triplet": triplet,
            "users_email": users_email,
            "severity": severity,
        }

    def action(self, name, params):
        """Execute an action

        :param name: action name
        :param params: action params
        :param params.internal_step: custom internal_step [default=monitoring_threshold_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        self.logger.debug("action - monitoring threshold - action name: %s" % (name))

        # get usergroup
        from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup

        usergroups, total_usergroups = self.get_linked_resources(
            link_type_filter="relation", objdef=ZabbixUsergroup.objdef
        )
        self.logger.debug("action - monitoring threshold - total_usergroups: %s" % (total_usergroups))

        usergroup: ZabbixUsergroup
        usergroup = usergroups[0]
        self.logger.debug("action - monitoring threshold id: %s - zabbix usergroup: %s" % (self.oid, usergroup))
        self.logger.debug("action - usergroup container: %s" % (usergroup.container.oid))

        # get action
        from beehive_resource.plugins.zabbix.entity.zbx_action import ZabbixAction

        actions, total_actions = self.get_linked_resources(link_type_filter="relation", objdef=ZabbixAction.objdef)
        self.logger.debug("action - monitoring threshold - total_actions: %s" % (total_actions))

        action: ZabbixAction
        action = actions[0]
        self.logger.debug("action - monitoring threshold id: %s - zabbix action: %s" % (self.oid, action))
        self.logger.debug("action - action container: %s" % (action.container.oid))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug("action - monitoring threshold - pre check - params {}".format(params))
            params = check(**params)
            self.logger.debug("action - monitoring threshold - after check - params {}".format(params))

        # get custom internal step
        internal_step = params.pop("internal_step", "monitoring_threshold_action_step")

        # clean cache
        self.clean_cache()

        # create internal steps
        run_steps = [MonitoringThreshold.task_base_path + "action_resource_pre_step"]
        # for orchestrator in orchestrators:
        # step = {'step': MonitoringThreshold.task_path + internal_step, 'args': [orchestrator]}
        step = {"step": MonitoringThreshold.task_base_path + internal_step, "args": []}
        run_steps.append(step)

        run_steps.append(MonitoringThreshold.task_base_path + "action_resource_post_step")

        # manage params
        params.update(
            {
                # 'cid': self.container.oid, # id del provider
                "cid": usergroup.container.oid,  # id di Podto1Zabbix
                "id": self.oid,
                "objid": self.objid,
                "ext_id": self.ext_id,
                "action_name": name,
                "steps": run_steps,
                "alias": "%s.%s" % (self.__class__.__name__, name),
                # 'alias': '%s.%s' % (self.name, name)
                "usergroup_id": usergroup.oid,
                "action_id": action.oid,
            }
        )
        params.update(self.get_user())
        self.logger.debug("action - monitoring threshold - post update - params {}".format(params))

        res = prepare_or_run_task(self, self.action_task, params, sync=True)
        self.logger.info("action - monitoring threshold - %s monitoring threshold %s using task" % (name, self.uuid))
        return res
