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


class ComputeMonitoringTeam(ComputeProviderResource):
    """Compute monitoring team"""

    objdef = "Provider.ComputeZone.ComputeMonitoringFolder.ComputeMonitoringTeam"
    objuri = "%s/monitoring_teams/%s"
    objname = "monitoring_team"
    objdesc = "Provider ComputeMonitoringTeam"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_team.ComputeMonitoringTeamTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.child_classes = []

        self.actions = [
            "add_user",
        ]

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
        # info['applied'] = [a.small_info() for a in self.get_applied_monitoring_team()]
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
        Use create when you want to create new grafana team and connect to monitoring_team.

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
            ComputeMonitoringTeam.task_base_path + "create_resource_pre_step",
        ]
        for availability_zone in availability_zones:
            logger.debug(": team - create in availability_zone: %s" % (availability_zone))
            step = {
                "step": ComputeMonitoringTeam.task_base_path + "create_zone_monitoring_team_step",
                "args": [availability_zone],
            }
            steps.append(step)
        steps.append(ComputeMonitoringTeam.task_path + "create_resource_post_step")
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

        # get monitoring_teams
        customs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in customs]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs

    def add_user(self, users_email, *args, **kvargs):
        """Add user check function

        :param users_email: user email
        :return: kvargs
        """
        self.logger.debug("add_user - ComputeMonitoringTeam - users_email: %s" % (users_email))
        return {"users_email": users_email}

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
        self.logger.debug("action - ComputeMonitoringTeam - action name: %s" % (name))

        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        monitoring_team: MonitoringTeam
        monitoring_team = self.get_monitoring_team_instance()
        # self.logger.debug('action - monitoring_team type: %s' % (type(monitoring_team)))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug("action - ComputeMonitoringTeam - pre check - kvargs: {}".format(kvargs))
            kvargs = check(**kvargs)
            self.logger.debug("action - ComputeMonitoringTeam - after check - kvargs: {}".format(kvargs))

        # clean cache
        self.clean_cache()

        # get custom action params
        internal_step = {
            "step": ComputeMonitoringTeam.task_base_path + "send_action_to_monitoring_team_step",
            "args": [monitoring_team.oid],
        }
        internal_steps = kvargs.pop("internal_steps", [internal_step])
        # hypervisor = kvargs.get('hypervisor', self.get_hypervisor())

        # create internal steps
        run_steps = [ComputeMonitoringTeam.task_base_path + "action_resource_pre_step"]
        run_steps.extend(internal_steps)
        run_steps.append(ComputeMonitoringTeam.task_base_path + "action_resource_post_step")

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
        self.logger.debug("action - %s compute monitoring team %s using task" % (name, self.uuid))
        return res

    def get_monitoring_team_instance(self):
        instances, total = self.get_linked_resources(link_type_filter="relation%")
        self.logger.debug("get_monitoring_team_instance - total: %s " % total)

        res = None
        if total > 0:
            res = instances[0]
        return res


class MonitoringTeam(AvailabilityZoneChildResource):
    """Availability Zone MonitoringTeam"""

    objdef = "Provider.Region.Site.AvailabilityZone.MonitoringTeam"
    objuri = "%s/monitoring_teams/%s"
    objname = "monitoring_team"
    objdesc = "Provider Availability Zone MonitoringTeam"
    task_base_path = "beehive_resource.plugins.provider.task_v2.monitoring_team.MonitoringTeamTask."

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
            MonitoringTeam.task_base_path + "create_resource_pre_step",
            MonitoringTeam.task_base_path + "create_grafana_team_step",
            MonitoringTeam.task_base_path + "create_resource_post_step",
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
        kvargs["steps"] = self.group_remove_step(orchestrator_idx)
        kvargs["sync"] = True

        return kvargs

    def get_grafana_team(self):
        """get grafana team resource

        :return: grafana team resource
        """
        teams, total = self.get_linked_resources(link_type_filter="relation")
        if total > 0:
            team = teams[0]
            self.logger.debug("get zone monitoring_team %s grafana team: %s" % (self.oid, team))
            return team
        else:
            raise ApiManagerError("no grafana team in zone monitoring_team %s" % self.oid)

    def get_physical_team(self):
        return self.get_grafana_team()

    def add_user(self, users_email, *args, **kvargs):
        """Add user check function

        :param users_email: user email
        :return: kvargs
        """
        self.logger.debug("add_user - MonitoringTeam - users_email: %s" % (users_email))
        return {
            "users_email": users_email,
        }

    def action(self, name, params):
        """Execute an action

        :param name: action name
        :param params: action params
        :param params.internal_step: custom internal_step [default=monitoring_team_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        self.logger.debug("action - monitoring team - action name: %s" % (name))

        teams, total = self.get_linked_resources(link_type_filter="relation")
        self.logger.debug("action - monitoring team - total: %s" % (total))
        # if total > 0:
        from beehive_resource.plugins.grafana.entity.grafana_team import GrafanaTeam

        team: GrafanaTeam
        team = teams[0]
        self.logger.debug("action - monitoring team id: %s - grafana team: %s" % (self.oid, team))
        self.logger.debug("action - team container: %s" % (team.container.oid))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug("action - MonitoringTeam - pre check - params {}".format(params))
            params = check(**params)
            self.logger.debug("action - MonitoringTeam - after check - params {}".format(params))

        # get custom internal step
        internal_step = params.pop("internal_step", "monitoring_team_action_step")

        # clean cache
        self.clean_cache()

        # create internal steps
        run_steps = [MonitoringTeam.task_base_path + "action_resource_pre_step"]
        # for orchestrator in orchestrators:
        # step = {'step': MonitoringTeam.task_path + internal_step, 'args': [orchestrator]}
        step = {"step": MonitoringTeam.task_base_path + internal_step, "args": []}
        run_steps.append(step)

        run_steps.append(MonitoringTeam.task_base_path + "action_resource_post_step")

        # manage params
        params.update(
            {
                # 'cid': self.container.oid, # id del provider
                "cid": team.container.oid,  # id di Podto1Grafana
                "id": self.oid,
                "objid": self.objid,
                "ext_id": self.ext_id,
                "action_name": name,
                "steps": run_steps,
                "alias": "%s.%s" % (self.__class__.__name__, name),
                # 'alias': '%s.%s' % (self.name, name)
                "team_id": team.oid,
            }
        )
        params.update(self.get_user())
        self.logger.debug("action - post update - params {}".format(params))

        res = prepare_or_run_task(self, self.action_task, params, sync=True)
        self.logger.info("%s monitoring team %s using task" % (name, self.uuid))
        return res
