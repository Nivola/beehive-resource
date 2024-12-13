# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

# from elasticsearch.client import logger
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.logging_role import (
    ComputeLoggingRole,
    LoggingRole,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.elk.entity.elk_role import ElkRole
from logging import getLogger

logger = getLogger(__name__)


class ComputeLoggingRoleTask(AbstractProviderResourceTask):
    """ComputeLoggingRole task"""

    name = "compute_logging_role_task"
    entity_class = ComputeLoggingRole

    @staticmethod
    @task_step()
    def create_zone_logging_role_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone logging role.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("+++++ create_zone_logging_role_step - oid %s" % oid)

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg="Get resources")

        # create zone logging_role
        # fv - modifica il nome della risorsa
        logging_role_params = {
            # 'name': '%s-avz%s' % (params.get('name'), site_id),
            # name rimane uguale
            "name": "%s" % (params.get("name")),
            "desc": "Logica - logging_role %s" % params.get("desc"),
            "parent": availability_zone_id,
            "norescreate": params.get("norescreate"),
            "elk_role": params.get("elk_role"),
            "attribute": {
                "type": params.get("type"),
                "orchestrator_tag": params.get("orchestrator_tag"),
            },
        }
        logger.debug("+++++ create_zone_logging_role_step - logging_role_params {} ".format(logging_role_params))
        prepared_task, code = provider.resource_factory(LoggingRole, **logging_role_params)
        logging_role_id = prepared_task["uuid"]

        # link logging_role to compute logging_role
        task.get_session(reopen=True)
        compute_logging_role = task.get_simple_resource(oid)
        compute_logging_role.add_link(
            "%s-logging_role-link" % logging_role_id,
            "relation.%s" % site_id,
            logging_role_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link logging_role %s to compute_logging_role %s" % (logging_role_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create logging role %s in availability_zone %s" % (logging_role_id, availability_zone_id),
        )

        return True, params


class LoggingRoleTask(AbstractProviderResourceTask):
    """LoggingRole task"""

    name = "logging_role_task"
    entity_class = LoggingRole

    @staticmethod
    @task_step()
    def create_elk_role_step(task, step_id, params, *args, **kvargs):
        """Create elk role resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        name = params.get("name")
        elk_role = params.get("elk_role")
        orchestrator = params.get("orchestrator")
        norescreate = params.get("norescreate")

        # get container from orchestrator
        from beehive_resource.plugins.elk.controller import ElkContainer

        elk_container: ElkContainer
        elk_container = task.get_container(orchestrator["id"])

        elk_role_temp: ElkRole
        elk_role_name = name  # elk_role.get('name')
        try:
            logger.debug("+++++ create_elk_role_step - cerco role per name: %s" % elk_role_name)
            elk_role_temp = elk_container.get_simple_resource(elk_role_name)
            role_id = elk_role_temp.oid
            logger.debug("+++++ create_elk_role_step - role trovato - aggiungo link: %s" % role_id)

            # reuse in cancellazione non cancella la risorsa fisica
            logging_role: LoggingRole
            logging_role = task.get_simple_resource(oid)
            logging_role.add_link(
                "%s-elk_role-link" % role_id,
                "relation",
                role_id,
                attributes={"reuse": True},
            )
            logger.debug("+++++ create_elk_role_step - link creato")

            task.progress(step_id, msg="Link elk_role %s" % role_id)

        except:
            logger.error("create_elk_role_step - norescreate: %s" % norescreate)
            if norescreate is not None and norescreate == True:
                logger.error("create_elk_role_step - role NON trovato - name: %s" % elk_role_name)
                logger.error("create_elk_role_step - link non creato - LoggingRole - oid: %s" % oid)
                raise Exception("role NON trovato - name: %s" % elk_role_name)
            else:
                logger.debug("create_elk_role_step - role NON trovato - name: %s" % elk_role_name)
                # risorsa non trovata -> la creo
                # create elk_role
                # name = '%s-%s-%s' % (name, orchestrator['id'], id_gen())
                # name rimane uguale

                elk_role_params = {
                    "name": elk_role_name,
                    "desc": "Fisica - Elk Role %s" % elk_role_name,
                    "indice": elk_role.get("indice"),
                    "space_id": elk_role.get("space_id"),
                    #'organization': orchestrator['config'].get('organization'),
                    "attribute": {},
                    "sync": True,
                }
                logger.debug("+++++ create_elk_role_step - elk_container %s" % type(elk_container).__name__)
                prepared_task, code = elk_container.resource_factory(ElkRole, **elk_role_params)

                role_id = prepared_task["uuid"]

                # link elk_role to logging_role
                task.get_session(reopen=True)
                logging_role: ElkRole
                logging_role = task.get_simple_resource(oid)
                logging_role.add_link("%s-elk_role-link" % role_id, "relation", role_id, attributes={})
                task.progress(step_id, msg="Link elk_role %s to logging_role %s" % (role_id, oid))

                # wait for task to complete
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="Create elk_role %s" % role_id)

        return True, params
