# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
from beehive_resource.plugins.elk.controller import ElkContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager

logger = logging.getLogger(__name__)


class ElkSpaceTask(AbstractResourceTask):
    """ElkSpace task"""

    name = "elk_space_task"
    entity_class = ElkSpace

    @staticmethod
    @task_step()
    def elk_space_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("elk_space_create_physical_step")

        cid = params.get("cid")  # container id
        oid = params.get("id")
        logger.debug("cid: %s: " % cid)
        logger.debug("oid: %s: " % oid)

        space_id = params.get("space_id")
        name = params.get("name")
        desc = params.get("desc")
        color = params.get("color")
        initials = params.get("initials")

        logger.debug("space_id: %s: " % space_id)
        logger.debug("name: %s: " % name)

        task.progress(step_id, msg="Get configuration params")

        container: ElkContainer
        container = task.get_container(cid)
        conn_kibana = container.conn_kibana

        inst_id = space_id
        try:
            # controllare se esiste l'oggetto prima di crearlo
            remote_entity = conn_kibana.space.get(space_id)
            task.progress(step_id, msg=" Elk space %s already exist " % space_id)
        except:
            task.progress(step_id, msg=" Elk space %s does not exist yet" % space_id)
            inst = conn_kibana.space.add(space_id, name, description=desc, color=color, initials=initials)
            # inst_id = inst['id']
            task.progress(step_id, msg=" Elk space created: %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def elk_space_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def elk_space_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("elk_space_delete_physical_step")

        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("cid %s: " % cid)
        logger.debug("oid %s: " % oid)

        container: ElkContainer
        container = task.get_container(cid)
        conn_kibana = container.conn_kibana
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check if space exists
                conn_kibana.space.get(resource.ext_id)
                # delete space
                conn_kibana.space.delete(resource.ext_id)
                task.progress(step_id, msg=" Elk space deleted %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg=" Elk space %s does not exist anymore" % resource.ext_id,
                )

        return oid, params

    @staticmethod
    @task_step()
    def add_dashboard_step(task, step_id, params, *args, **kvargs):
        """Add server dashboard

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def add_dashboard_action(conn, cid, oid, ext_id, params):
            logger.debug("add_dashboard_action - params={}".format(params))

            container: ElkContainer
            container = task.get_container(cid)
            conn_kibana = container.conn_kibana
            conn_kibana.space.add_dashboard(
                params["space_id_from"],
                params["dashboard"],
                params["space_id_to"],
                params["index_pattern"],
            )

            # server = conn.server.get_by_morid(ext_id)
            # vs_task = conn.server.dashboard.create(server, params['dashboard'])
            # return vs_task

        logger.debug("add_dashboard_step - params={}".format(params))
        res = ElkSpaceTask.space_action(
            task,
            step_id,
            add_dashboard_action,
            "Add dashboard",
            "Error adding dashboard",
            params,
        )
        return res, params

    #
    # action
    #
    @staticmethod
    def space_action(task, step_id, action, success, error, params):
        """Execute a server action

        :param task: celery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param params: input params
        :return: ext_id
        :raise:
        """
        logger.debug("space_action")
        task.progress(step_id, msg="start action %s" % action.__name__)
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # execute action
        vs_task = action(conn, cid, oid, ext_id, params)
        if vs_task is not None:
            container.query_remote_task(task, step_id, vs_task, error=error)

        # update cache
        server_obj = task.get_resource(oid)
        server_obj.set_cache()

        task.progress(step_id, msg=success)
        task.progress(step_id, msg="stop action %s" % action.__name__)
        return True


task_manager.tasks.register(ElkSpaceTask())
