# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from copy import deepcopy
from beecell.simple import id_gen
from beehive.common.task import BaseTask
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace, LoggingSpace
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
from logging import getLogger

logger = getLogger(__name__)


class ComputeLoggingSpaceTask(AbstractProviderResourceTask):
    """ComputeLoggingSpace task
    """
    name = 'compute_logging_space_task'
    entity_class = ComputeLoggingSpace

    @staticmethod
    @task_step()
    def create_zone_logging_space_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone logging space.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get('cid') # container id
        oid = params.get('id') # id della risorsa
        logger.debug('create_zone_logging_space_step - oid %s' % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg='Get resources')

        # create zone logging_space
        # fv - modifica il nome della risorsa
        logging_space_params = {
            # 'name': '%s-avz%s' % (params.get('name'), site_id),
            # name rimane uguale
            'name': '%s' % (params.get('name')),
            'desc': 'logging_space %s' % params.get('desc'),
            'parent': availability_zone_id,
            'norescreate': params.get('norescreate'),
            'elk_space': params.get('elk_space'),
            'attribute': {
                'type': params.get('type'),
                'orchestrator_tag': params.get('orchestrator_tag'),
            }
        }
        logger.debug('create_zone_logging_space_step - logging_space_params {} '.format(logging_space_params))
        prepared_task, code = provider.resource_factory(LoggingSpace, **logging_space_params)
        logging_space_id = prepared_task['uuid']

        # link logging_space to compute logging_space
        task.get_session(reopen=True)
        compute_logging_space = task.get_simple_resource(oid)
        compute_logging_space.add_link('%s-logging_space-link' % logging_space_id, 'relation.%s' % site_id,
                                       logging_space_id, attributes={})
        task.progress(step_id, msg='Link logging_space %s to compute_logging_space %s' % (logging_space_id, oid))

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create logging space %s in availability_zone %s'
                                   % (logging_space_id, availability_zone_id))

        return True, params

    @staticmethod
    @task_step()
    def send_action_to_logging_space_step(task, step_id, params, logging_space_id, *args, **kvargs):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        logger.debug('send_action_to_logging_space_step - params {}'.format(params))

        cid = params.get('cid')
        oid = params.get('id')
        action = params.get('action_name')
        logger.debug('send_action_to_logging_space_step - action_name %s' % (action))

        configs = deepcopy(params)
        configs['id'] = logging_space_id
        # hypervisor = params.get('hypervisor')
        # hypervisor_tag = params.get('hypervisor_tag')

        resource = task.get_simple_resource(oid)
        logging_space: LoggingSpace
        logging_space = task.get_resource(logging_space_id)
        task.progress(step_id, msg='Get resources')

        # send action
        logger.debug('send_action_to_logging_space_step - configs {}'.format(configs))
        prepared_task, code = logging_space.action(action, configs)
        task.progress(step_id, msg='Send action to logging space %s' % logging_space_id)
        res = run_sync_task(prepared_task, task, step_id)

        return res, params


class LoggingSpaceTask(AbstractProviderResourceTask):
    """LoggingSpace task
    """
    name = 'logging_space_task'
    entity_class = LoggingSpace

    @staticmethod
    @task_step()
    def create_elk_space_step(task: BaseTask, step_id, params, *args, **kvargs):
        """Create elk space resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get('id')
        name = params.get('name')
        elk_space = params.get('elk_space')
        orchestrator = params.get('orchestrator')
        norescreate = params.get('norescreate')

        # get container from orchestrator
        from beehive_resource.plugins.elk.controller import ElkContainer
        elk_container: ElkContainer
        elk_container = task.get_container(orchestrator['id'])

        elk_space_temp: ElkSpace
        elk_space_name = elk_space.get('name')
        try:
            logger.debug('create_elk_space_step - cerco space per name: %s' % elk_space_name)
            elk_space_temp = elk_container.get_simple_resource(elk_space_name)
            space_id = elk_space_temp.oid
            logger.debug('create_elk_space_step - space trovato - aggiungo link: %s' % space_id)

            # reuse in cancellazione non cancella la risorsa fisica
            logging_space: LoggingSpace
            logging_space = task.get_simple_resource(oid)
            logging_space.add_link('%s-elk_space-link' % space_id, 'relation', space_id, attributes={'reuse': True})
            logger.debug('create_elk_space_step - link creato')

            task.progress(step_id, msg='Link elk_space %s' % space_id)

        except:
            logger.error('create_elk_space_step - norescreate: %s' % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error('create_elk_space_step - space NON trovato - name: %s' % elk_space_name)
                logger.error('create_elk_space_step - link non creato - LoggingSpace - oid: %s' % oid)
                raise Exception('space NON trovato - name: %s' % elk_space_name)
            else:
                logger.debug('create_elk_space_step - space NON trovato - name: %s' % elk_space_name)
                # risorsa non trovata -> la creo
                # create elk_space
                # name = '%s-%s-%s' % (name, orchestrator['id'], id_gen())
                # name rimane uguale

                elk_space_params = {
                    'name': elk_space_name,
                    'desc': elk_space.get('desc'),
                    'space_id': elk_space.get('space_id'),
                    'color': elk_space.get('color'),
                    'attribute': {},
                    'sync': True
                }
                logger.debug('create_elk_space_step - elk_container %s' % type(elk_container).__name__)
                prepared_task, code = elk_container.resource_factory(ElkSpace, **elk_space_params)
            
                # id of the physical resource
                space_id = prepared_task['uuid']

                # link elk_space to logging_space
                task.get_session(reopen=True)
                logging_space: LoggingSpace
                logging_space = task.get_simple_resource(oid)
                logging_space.add_link('%s-elk_space-link' % space_id, 'relation', space_id, attributes={})
                task.progress(step_id, msg='Link elk_space %s to logging_space %s' % (space_id, oid))

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg='Create elk_space %s' % space_id)

        return True, params

    @staticmethod
    @task_step()
    # def instance_action_step(task, step_id, params, orchestrator, *args, **kvargs):
    def logging_space_action_step(task, step_id, params, *args, **kvargs):
        """Send action to physical server.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug('logging_space_action_step - params {}'.format(params))
        logger.debug('logging_space_action_step - args {}'.format(args))
        
        oid = params.get('id')
        cid = params.get('cid')
        space_id = params.get('space_id')
        action = params.get('action_name')

        elk_space: ElkSpace
        elk_space = task.get_simple_resource(space_id)

        # cid è l'id di Podto1Elk (non più ResourceProvider01)
        container = task.get_container(cid)
        elk_space.set_container(container)

        space_id_from = params.get('space_id_from')
        dashboard = params.get('dashboard')
        index_pattern = params.get('index_pattern')
        # space_name = params.get('space_name')
        space_id_to = elk_space.ext_id

        res, str = elk_space.add_dashboard(space_id_from, dashboard, space_id_to, index_pattern, params)
        logger.debug('logging_space_action_step - str: %s' % str)

        return True, params
    