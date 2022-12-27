# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

# from elasticsearch.client import logger
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.logging_role_mapping import ComputeLoggingRoleMapping, LoggingRoleMapping
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.elk.entity.elk_role_mapping import ElkRoleMapping
from logging import getLogger

logger = getLogger(__name__)

class ComputeLoggingRoleMappingTask(AbstractProviderResourceTask):
    """ComputeLoggingRoleMapping task
    """
    name = 'compute_logging_role_mapping_task'
    entity_class = ComputeLoggingRoleMapping

    @staticmethod
    @task_step()
    def create_zone_logging_role_mapping_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone logging role mapping.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        logger.debug('+++++ create_zone_logging_role_mapping_step - oid %s' % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg='Get resources')

        # create zone logging_role_mapping
        # fv - modifica il nome della risorsa
        logging_role_mapping_params = {
            # 'name': '%s-avz%s' % (params.get('name'), site_id),
            # name rimane uguale
            'name': '%s' % (params.get('name')),
            'desc': 'Logica - logging_role_mapping %s' % params.get('desc'),
            'parent': availability_zone_id,
            'norescreate': params.get('norescreate'),
            'elk_role_mapping': params.get('elk_role_mapping'),
            'attribute': {
                'type': params.get('type'),
                'orchestrator_tag': params.get('orchestrator_tag'),
            }
        }
        logger.debug('+++++ create_zone_logging_role_mapping_step - logging_role_mapping_params {} '.format(logging_role_mapping_params))
        prepared_task, code = provider.resource_factory(LoggingRoleMapping, **logging_role_mapping_params)
        logging_role_mapping_id = prepared_task['uuid']

        # link logging_role_mapping to compute logging_role_mapping
        task.get_session(reopen=True)
        compute_logging_role_mapping = task.get_simple_resource(oid)
        compute_logging_role_mapping.add_link('%s-logging_role_mapping-link' % logging_role_mapping_id, 'relation.%s' % site_id,
                                       logging_role_mapping_id, attributes={})
        task.progress(step_id, msg='Link logging_role_mapping %s to compute_logging_role_mapping %s' % (logging_role_mapping_id, oid))

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create logging role mapping %s in availability_zone %s'
                                   % (logging_role_mapping_id, availability_zone_id))

        return True, params


class LoggingRoleMappingTask(AbstractProviderResourceTask):
    """LoggingRoleMapping task
    """
    name = 'logging_role_mapping_task'
    entity_class = LoggingRoleMapping

    @staticmethod
    @task_step()
    def create_elk_role_mapping_step(task, step_id, params, *args, **kvargs):
        """Create elk role mapping resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get('id')
        name = params.get('name')
        elk_role_mapping = params.get('elk_role_mapping')
        orchestrator = params.get('orchestrator')
        norescreate = params.get('norescreate')

        # get container from orchestrator
        from beehive_resource.plugins.elk.controller import ElkContainer
        elk_container: ElkContainer
        elk_container = task.get_container(orchestrator['id'])

        elk_role_mapping_temp: ElkRoleMapping
        elk_role_mapping_name = name
        try:
            logger.debug('+++++ create_elk_role_mapping_step - cerco role_mapping per name: %s' % elk_role_mapping_name)
            elk_role_mapping_temp = elk_container.get_simple_resource(elk_role_mapping_name)
            role_mapping_id = elk_role_mapping_temp.oid
            logger.debug('+++++ create_elk_role_mapping_step - role_mapping trovato - aggiungo link: %s' % role_mapping_id)

            # reuse in cancellazione non cancella la risorsa fisica
            logging_role_mapping: LoggingRoleMapping
            logging_role_mapping = task.get_simple_resource(oid)
            logging_role_mapping.add_link('%s-elk_role_mapping-link' % role_mapping_id, 'relation', role_mapping_id, attributes={ 'reuse': True })
            logger.debug('+++++ create_elk_role_mapping_step - link creato')

            task.progress(step_id, msg='Link elk_role_mapping %s' % role_mapping_id)

        except:
            logger.error('create_elk_role_mapping_step - norescreate: %s' % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error('create_elk_role_mapping_step - role_mapping NON trovato - name: %s' % elk_role_mapping_name)
                logger.error('create_elk_role_mapping_step - link non creato - LoggingRoleMapping - oid: %s' % oid)
                raise Exception('role_mapping NON trovato - name: %s' % elk_role_mapping_name)
            else:
                logger.debug('create_elk_role_mapping_step - role_mapping NON trovato - name: %s' % elk_role_mapping_name)
                # risorsa non trovata -> la creo
                # create elk_role_mapping
                # name = '%s-%s-%s' % (name, orchestrator['id'], id_gen())
                # name rimane uguale

                elk_role_mapping_params = {
                    'name': elk_role_mapping_name,
                    'desc': 'Fisica - Elk RoleMapping %s' % elk_role_mapping_name,
                    'role_name': elk_role_mapping.get('role_name'),
                    'users_email': elk_role_mapping.get('users_email'),
                    'realm_name': elk_role_mapping.get('realm_name'),
                    #'organization': orchestrator['config'].get('organization'),
                    'attribute': {},
                    'sync': True
                }
                logger.debug('+++++ create_elk_role_mapping_step - elk_container %s' % type(elk_container).__name__)
                prepared_task, code = elk_container.resource_factory(ElkRoleMapping, **elk_role_mapping_params)
                
                role_mapping_id = prepared_task['uuid']

                # link elk_role_mapping to logging_role_mapping
                task.get_session(reopen=True)
                logging_role_mapping: ElkRoleMapping
                logging_role_mapping = task.get_simple_resource(oid)
                logging_role_mapping.add_link('%s-elk_role_mapping-link' % role_mapping_id, 'relation', role_mapping_id, attributes={})
                task.progress(step_id, msg='Link elk_role_mapping %s to logging_role_mapping %s' % (role_mapping_id, oid))

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg='Create elk_role_mapping %s' % role_mapping_id)

        return True, params
