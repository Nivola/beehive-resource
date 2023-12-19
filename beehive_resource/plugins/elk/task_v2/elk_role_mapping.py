# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.elk.entity.elk_role_mapping import ElkRoleMapping
from beehive_resource.plugins.elk.controller import ElkContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager


class ElkRoleMappingTask(AbstractResourceTask):
    """ElkRoleMapping task"""

    name = "elk_role_mapping_task"
    entity_class = ElkRoleMapping

    @staticmethod
    @task_step()
    def elk_role_mapping_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger = logging.getLogger(__name__)
        logger.debug("+++++ elk_role_mapping_create_physical_step")

        cid = params.get("cid")  # container id
        oid = params.get("id")
        logger.debug("+++++ cid: %s: " % cid)
        logger.debug("+++++ oid: %s: " % oid)

        name = params.get("name")
        desc = params.get("desc")
        role_mapping_name = name
        role_name = params.get("role_name")
        users_email = params.get("users_email")
        realm_name = params.get("realm_name")

        logger.debug("+++++ role_name: %s: " % role_name)
        logger.debug("+++++ users_email: %s: " % users_email)
        logger.debug("+++++ realm_name: %s: " % realm_name)

        users_email_array = users_email.split(",")

        task.progress(step_id, msg="Get configuration params")

        container: ElkContainer
        container = task.get_container(cid)
        conn_elastic = container.conn_elastic

        inst_id = role_mapping_name
        try:
            # controllare se esiste l'oggetto prima di crearlo
            remote_entity = conn_elastic.role_mapping.get(role_mapping_name)
            task.progress(
                step_id,
                msg="+++++ Elk role mapping %s already exist " % role_mapping_name,
            )
        except:
            task.progress(
                step_id,
                msg="+++++ Elk role mapping %s does not exist yet" % role_mapping_name,
            )
            inst = conn_elastic.role_mapping.add(
                role_mapping_name,
                role_name,
                users_email=users_email_array,
                realm_name=realm_name,
            )
            # inst_id = inst['id']
            task.progress(step_id, msg="+++++ Elk role mapping created %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def elk_role_mapping_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def elk_role_mapping_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container: ElkContainer
        container = task.get_container(cid)
        conn_elastic = container.conn_elastic
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check if role_mapping exists
                conn_elastic.role_mapping.get(resource.ext_id)
                # delete role_mapping
                conn_elastic.role_mapping.delete(resource.ext_id)
                task.progress(step_id, msg="+++++ Elk role_mapping deleted %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg="+++++ Elk role_mapping %s does not exist anymore" % resource.ext_id,
                )

        return oid, params


task_manager.tasks.register(ElkRoleMappingTask())
