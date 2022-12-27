# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.model import BaseEntity
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.logging_role import ComputeLoggingRole, LoggingRole
from beehive_resource.plugins.provider.entity.logging_role_mapping import ComputeLoggingRoleMapping, LoggingRoleMapping
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource, ComputeZone
from beehive.common.task_v2 import prepare_or_run_task
from logging import getLogger
from beecell.simple import format_date
from beecell.simple import dict_get
from datetime import datetime

logger = getLogger(__name__)


class ComputeLoggingSpace(ComputeProviderResource):
    """Compute logging space
    """
    objdef = 'Provider.ComputeZone.ComputeLoggingSpace'
    objuri = '%s/logging_spaces/%s'
    objname = 'logging_space'
    objdesc = 'Provider ComputeLoggingSpace'
    task_base_path = 'beehive_resource.plugins.provider.task_v2.logging_space.ComputeLoggingSpaceTask.'

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.physical_space = None

        self.child_classes = [
            ComputeLoggingRole,
            ComputeLoggingRoleMapping
        ]

        self.actions = [
            'add_dashboard'
        ]

    def get_physical_space(self):
        """Get physical space"""
        if self.physical_space is None:
            # get main zone space
            zone_instance = None
            res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type='relation%')
            zone_spaces = res.get(self.oid)
            zone_space = None
            if len(zone_spaces) > 0:
                zone_space = zone_spaces[0]
            self.logger.warn(zone_space)

            if zone_space is not None:
                self.physical_space = zone_space.get_physical_space()

        self.logger.debug('Get compute space %s physical space: %s' % (self.uuid, self.physical_space))
        return self.physical_space

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)

        from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
        physical_space: ElkSpace
        physical_space = self.get_physical_space()
        # self.logger.debug('+++++ info - physical_folder: %s' % (physical_folder))
        if physical_space is not None:
            info['dashboards'] = physical_space.dashboards

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        
        from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
        physical_space: ElkSpace
        physical_space = self.get_physical_space()
        # self.logger.debug('+++++ info - physical_folder: %s' % (physical_folder))
        if physical_space is not None:
            info['dashboards'] = physical_space.dashboards
            
        return info

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            'logging.spaces': 1,
        }
        self.logger.debug2('Get resource %s quotas: %s' % (self.uuid, quotas))
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
        Use create when you want to create new elk space and connect to logging_space.
        
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
        orchestrator_type = kvargs.get('type')
        orchestrator_tag = kvargs.get('orchestrator_tag')
        compute_zone_id = kvargs.get('parent')

        # get compute zone
        compute_zone: ComputeZone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        multi_avz = True
        
        if compute_zone is None:
            raise ApiManagerError('ComputeZone Parent not found')

        # get availability zones ACTIVE
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

        # set params
        params = {
            'compute_zone': compute_zone.oid,
            'attribute': {
                'type': orchestrator_type,
                # 'type': 'elk',
                'orchestrator_tag': orchestrator_tag,
            }
        }
        kvargs.update(params)

        # TODO fv capire se in desc c'è la tripletta
        compute_zone_model: BaseEntity
        compute_zone_model = compute_zone.model
        controller.logger.debug2('compute_zone_model.desc %s' % (compute_zone_model.desc))

        # create task workflow
        steps = [
            ComputeLoggingSpace.task_base_path + 'create_resource_pre_step',
        ]
        for availability_zone in availability_zones:
            logger.debug('space - create in availability_zone: %s' % (availability_zone))
            step = {
                'step': ComputeLoggingSpace.task_base_path + 'create_zone_logging_space_step',
                'args': [availability_zone]
            }
            steps.append(step)
        steps.append(ComputeLoggingSpace.task_path + 'create_resource_post_step')
        kvargs['steps'] = steps
        # fv - forzatura
        kvargs['sync'] = False

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
        # TODO - fv verificare non ci siano role, role_mapping associati
        # applied_customs, total = self.get_linked_resources(link_type='applied_customs')
        # if len(applied_customs) > 0:
        #     raise ApiManagerError('ComputeLoggingSpace %s has applied logging_spaces associated and cannot be '
        #                           'deleted' % self.oid)

        # get logging_spaces
        customs, total = self.get_linked_resources(link_type_filter='relation%')
        childs = [e.oid for e in customs]

        # create task workflow
        kvargs['steps'] = self.group_remove_step(childs)

        return kvargs

    def add_dashboard(self, space_id_from=None, dashboard=None, index_pattern=None, *args, **kvargs):
        """Add dashboard check function

        :param dashboard: dashboard name
        :return: kvargs
        """
        self.logger.debug('add_dashboard - ComputeLoggingSpace - space_id_from: %s' % (space_id_from))
        self.logger.debug('add_dashboard - ComputeLoggingSpace - dashboard: %s' % (dashboard))
        self.logger.debug('add_dashboard - LoggingSpace - index_pattern: %s' % (index_pattern))
        return {
            'space_id_from': space_id_from,
            'dashboard': dashboard,
            'index_pattern': index_pattern
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
        self.logger.debug('action - ComputeLoggingSpace - action name: %s' % (name))

        # verify permissions
        self.verify_permisssions('update')

        # check state is ACTIVE
        self.check_active()

        logging_space: LoggingSpace
        logging_space = self.get_logging_space_instance()
        # self.logger.debug('action - logging_space type: %s' % (type(logging_space)))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug('action - ComputeLoggingSpace - pre check - kvargs: {}'.format(kvargs))
            kvargs = check(**kvargs)
            self.logger.debug('action - ComputeLoggingSpace - after check - kvargs: {}'.format(kvargs))

        # clean cache
        self.clean_cache()

        # get custom action params
        internal_step = {
            'step': ComputeLoggingSpace.task_base_path + 'send_action_to_logging_space_step',
            'args': [logging_space.oid]
        }
        internal_steps = kvargs.pop('internal_steps', [internal_step])
        # hypervisor = kvargs.get('hypervisor', self.get_hypervisor())

        # create internal steps
        run_steps = [ComputeLoggingSpace.task_base_path + 'action_resource_pre_step']
        run_steps.extend(internal_steps)
        run_steps.append(ComputeLoggingSpace.task_base_path + 'action_resource_post_step')

        # manage params
        params = {
            'cid': self.container.oid,
            'id': self.oid,
            'objid': self.objid,
            'ext_id': self.ext_id,
            'action_name': name,
            'steps': run_steps,
            'alias': '%s.%s' % (self.__class__.__name__, name),
            # 'sync': True
        }
        params.update(kvargs)
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, params, sync=sync)
        self.logger.debug('action - %s compute logging space %s using task' % (name, self.uuid))
        return res

    def get_logging_space_instance(self):
        instances, total = self.get_linked_resources(link_type_filter='relation%')
        self.logger.debug('get_logging_space_instance - total: %s ' % total)

        res = None
        if total > 0:
            res = instances[0]
        return res

    # def get_size(self):
    #     info = Resource.detail(self)
    #     # self.logger.debug('+++++ get_size - info: {}'.format(info))

    #     loggingSpace: LoggingSpace = self.get_logging_space_instance()
    #     # self.logger.debug('+++++ get_size - loggingSpace: {}'.format(loggingSpace))

    #     from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
    #     elkSpace: ElkSpace = loggingSpace.get_physical_space()
    #     # self.logger.debug('+++++ get_size - elkSpace: {}'.format(elkSpace))
    #     triplet = elkSpace.name
    #     self.logger.debug('+++++ get_size - triplet: {}'.format(triplet))

    #     from beehive_resource.plugins.elk.controller import ElkContainer
    #     elkContainer: ElkContainer = elkSpace.container
    #     # self.logger.debug('+++++ get_size - elkContainer: {}'.format(elkContainer))
    #     from elasticsearch import Elasticsearch
    #     es: Elasticsearch = elkContainer.conn_elastic.es
       
    #     indice = '*-%s' % triplet
    #     indice = indice.lower()

    #     pattern = indice
    #     self.logger.debug('+++++ get_size - pattern: {}'.format(pattern))
    #     # pattern = '*cmp_nivola_test*'     # pattern per prova su elastic di test
    #     sizeTotal = 0
    #     res = list(es.indices.get(pattern).values())
    #     # self.logger.debug("+++++ index_get - res: %s" % res)
        
    #     res2 = es.indices.stats(pattern).get('indices', {})
    #     for item in res:
    #         # self.logger.debug("+++++ get_size - provided_name: %s" % dict_get(item, 'settings.index.provided_name'))
    #         item['stats'] = res2.get(dict_get(item, 'settings.index.provided_name'))
    #         # self.logger.debug("+++++ index_get - item['stats']: %s" % item['stats'])
    #         size_in_bytes = dict_get(item['stats'], 'total.store.size_in_bytes')
    #         # self.logger.debug("+++++ get_size - size_in_bytes: %s" % size_in_bytes)

    #         size = round(float(size_in_bytes), 2)
    #         sizeTotal += size

    #     sizeTotal = round(sizeTotal/1024.0/1024.0/1024.0, 2)
    #     self.logger.debug("+++++ get_size - sizeTotal: %s" % sizeTotal)
    #     return sizeTotal

    # NOTA: metrica acquisita con batch/acquire_metric_elastic
    # def get_metrics(self):
    #     """Get resource metrics

    #     :return: a dict like this

    #         {
    #             "id": "1",
    #             "uuid": "vm1",
    #             "metrics": [
    #                 {
    #                     "key": "log_gb",
    #                     "value: 10,
    #                     "type": 1,
    #                     "unit": "GB"
    #                 }],
    #             "extraction_date": "2018-03-04 12:00:34 200",
    #             "resource_uuid": "12u956-2425234-23654573467-567876"
    #         }
    #     """
    #     self.logger.debug('+++++ get_metrics')
    #     metrics = [{
    #         'key': 'log_gb', 
    #         'value': self.get_size(), 
    #         'type': 1, 
    #         'unit': 'GB'
    #     }]
    #     res = {
    #         'id': self.oid,
    #         'uuid': self.uuid,
    #         'resource_uuid': self.uuid,
    #         'type': self.objdef,
    #         'metrics': metrics,
    #         'extraction_date': format_date(datetime.today())
    #     }

    #     self.logger.debug('+++++ get_metrics - get logging space %s metrics: %s' % (self.uuid, res))
    #     return res


class LoggingSpace(AvailabilityZoneChildResource):
    """Availability Zone LoggingSpace
    """
    objdef = 'Provider.Region.Site.AvailabilityZone.LoggingSpace'
    objuri = '%s/logging_spaces/%s'
    objname = 'logging_space'
    objdesc = 'Provider Availability Zone LoggingSpace'
    task_base_path = 'beehive_resource.plugins.provider.task_v2.logging_space.LoggingSpaceTask.'

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)
        
        self.child_classes = [
            LoggingRole,
            LoggingRoleMapping
        ]

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
        avz_id = kvargs.get('parent')
        orchestrator_tag = kvargs.get('orchestrator_tag', 'default')

        # get availability_zone
        avz = container.get_simple_resource(avz_id)

        # select remote orchestrator
        orchestrator = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=['elk'])

        # set container
        params = {
            'orchestrator': list(orchestrator.values())[0]
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            LoggingSpace.task_base_path + 'create_resource_pre_step',
            LoggingSpace.task_base_path + 'create_elk_space_step',
            LoggingSpace.task_base_path + 'create_resource_post_step',
        ]
        kvargs['steps'] = steps
        kvargs['sync'] = True

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
        orchestrator_idx = self.get_orchestrators(select_types=['elk'])
        kvargs['steps'] = self.group_remove_step(orchestrator_idx)
        kvargs['sync'] = True

        return kvargs

    def get_elk_space(self):
        """get elk space resource

        :return: elk space resource
        """
        spaces, total = self.get_linked_resources(link_type_filter='relation')
        if total > 0:
            space = spaces[0]
            self.logger.debug('get zone logging_space %s elk space: %s' % (self.oid, space))
            return space
        else:
            # raise ApiManagerError('no elk space in zone logging_space %s' % self.oid)
            self.logger.error('no elk space in zone logging_space %s' % self.oid)

    def get_physical_space(self):
        return self.get_elk_space()

    def add_dashboard(self, space_id_from=None, dashboard=None, index_pattern=None, *args, **kvargs):
        """Add dashboard check function

        :param dashboard: dashboard name
        :return: kvargs
        """
        self.logger.debug('add_dashboard - LoggingSpace - space_id_from: %s' % (space_id_from))
        self.logger.debug('add_dashboard - LoggingSpace - dashboard: %s' % (dashboard))
        self.logger.debug('add_dashboard - LoggingSpace - index_pattern: %s' % (index_pattern))
        return {
            'space_id_from': space_id_from,
            'dashboard': dashboard,
            'index_pattern': index_pattern
        }

    def action(self, name, params):
        """Execute an action

        :param name: action name
        :param params: action params
        :param params.internal_step: custom internal_step [default=logging_space_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        self.logger.debug('action - logging space - action name: %s' % (name))

        spaces, total = self.get_linked_resources(link_type_filter='relation')
        self.logger.debug('action - logging space - total: %s' % (total))
        # if total > 0:
        from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
        space: ElkSpace
        space = spaces[0]
        self.logger.debug('action - logging space id: %s - elk space: %s' % (self.oid, space))
        self.logger.debug('action - space container: %s' % (space.container.oid))

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            self.logger.debug('action - LoggingSpace - pre check - params {}'.format(params))
            params = check(**params)
            self.logger.debug('action - LoggingSpace - after check - params {}'.format(params))

        # get custom internal step
        internal_step = params.pop('internal_step', 'logging_space_action_step')

        # clean cache
        self.clean_cache()

        # create internal steps
        run_steps = [LoggingSpace.task_base_path + 'action_resource_pre_step']
        # for orchestrator in orchestrators:
        # step = {'step': LoggingSpace.task_path + internal_step, 'args': [orchestrator]}
        step = {'step': LoggingSpace.task_base_path + internal_step, 'args': []}
        run_steps.append(step)
        
        run_steps.append(LoggingSpace.task_base_path + 'action_resource_post_step')

        # manage params
        params.update({
            # 'cid': self.container.oid, # id del provider
            'cid': space.container.oid, # id di Podto1Elk
            'id': self.oid,
            'objid': self.objid,
            'ext_id': self.ext_id,
            'action_name': name,
            'steps': run_steps,
            'alias': '%s.%s' % (self.__class__.__name__, name),
            # 'alias': '%s.%s' % (self.name, name)
            'space_id': space.oid
        })
        params.update(self.get_user())
        self.logger.debug('action - post update - params {}'.format(params))

        res = prepare_or_run_task(self, self.action_task, params, sync=True)
        self.logger.info('%s logging space %s using task' % (name, self.uuid))
        return res
