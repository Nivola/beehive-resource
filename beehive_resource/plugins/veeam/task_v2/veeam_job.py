# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beecell.types.type_dict import dict_get
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.veeam.entity.veeam_job import VeeamJob
from beehive_resource.plugins.veeam.controller import VeeamContainer
from beehive_resource.task_v2 import AbstractResourceTask, task_manager
import string
import os, random

logger = logging.getLogger(__name__)


class VeeamJobTask(AbstractResourceTask):
    """VeeamJob task"""

    name = "veeam_job_task"
    entity_class = VeeamJob

    @staticmethod
    @task_step()
    def veeam_job_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("+++++ veeam_job_create_physical_step")

        cid = params.get("cid")  # container id
        oid = params.get("id")
        logger.debug("+++++ cid: %s" % cid)
        logger.debug("+++++ oid: %s" % oid)

        # job_id = params.get('job_id')
        name = params.get("name")
        desc = params.get("desc")

        # logger.debug('job_id: %s: ' % job_id)
        logger.debug("+++++ name: %s" % name)
        logger.debug("+++++ desc: %s" % desc)

        task.progress(step_id, msg="Get configuration params")

        container: VeeamContainer
        container = task.get_container(cid)
        conn_veeam = container.conn_veeam

        inst_id = None
        try:
            # controllare se esiste l'oggetto prima di crearlo
            remote_entities = conn_veeam.job.get_by_name(name)
            remote_entity = remote_entities[0]
            inst_id = remote_entity["id"]
            task.progress(
                step_id,
                msg=" Veeam job %s already exist - inst_id: %s" % (name, inst_id),
            )
        except:
            task.progress(step_id, msg=" Veeam job %s does not exist yet" % name)
            inst = conn_veeam.job.add(job_name=name)
            logger.debug("+++++ inst: %s" % inst)
            inst_id = inst["jobId"]
            task.progress(step_id, msg=" Veeam job created: %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def veeam_job_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def veeam_job_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("+++++ veeam_job_delete_physical_step")

        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("+++++ cid %s: " % cid)
        logger.debug("+++++ oid %s: " % oid)

        container: VeeamContainer
        container = task.get_container(cid)
        conn_veeam = container.conn_veeam
        resource = container.get_simple_resource(oid)
        logger.debug("+++++ resource.ext_id: %s: " % resource.ext_id)

        if resource.is_ext_id_valid() is True:
            try:
                # check if job exists
                conn_veeam.job.get(job_id=resource.ext_id)
                # delete job
                conn_veeam.job.delete(job_id=resource.ext_id)
                task.progress(step_id, msg=" Veeam job deleted %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg=" Veeam job %s does not exist anymore" % resource.ext_id,
                )

        return oid, params

    @staticmethod
    @task_step()
    def add_user_step(task, step_id, params, *args, **kvargs):
        """Add server user

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """

        def add_user_action(conn, cid, oid, ext_id, params):
            logger.debug("add_user_step - add_user_action - params={}".format(params))

            container: VeeamContainer
            container = task.get_container(cid)
            conn_veeam = container.conn_veeam

            users_email: str = params["users_email"]
            job_id_to = params["job_id_to"]

            # cancello tutti gli utenti del job
            remote_users = conn_veeam.job.get_users(job_id_to)
            for user in remote_users:
                user_id = user["userId"]
                logger.debug("add_user_step - removing user_id: %s" % (user_id))
                del_message = conn_veeam.job.del_user(job_id_to, user_id)
                logger.debug("add_user_step - user_id: %s - del_message: %s" % (user_id, del_message))

            # inserisco gli utenti del job
            users_email_array = users_email.split(",")
            for user_email in users_email_array:
                try:
                    res_user = conn_veeam.user.get_by_login_or_email(user_email)
                    user_id = res_user["id"]
                    if user_id is not None:
                        try:
                            add_message = conn_veeam.job.add_user(job_id=job_id_to, user_id=user_id)
                            logger.debug("add_user_step - user_email: %s - add_message: %s" % (user_email, add_message))
                        except:
                            logger.warning("add_user_step - user not added to job - user_email: %s" % (user_email))
                except:
                    logger.warning("add_user_step - user not found - user_email: %s" % (user_email))
                    try:
                        if user_email.endswith("csi.it"):
                            password = password_generator()
                            res = conn_veeam.user.add(
                                name=user_email,
                                email=user_email,
                                login=user_email,
                                password=password,
                            )
                            if res is not None and "id" in res:
                                user_id = res["id"]
                                if user_id is not None:
                                    try:
                                        add_message = conn_veeam.job.add_user(job_id=job_id_to, user_id=user_id)
                                        logger.debug(
                                            "add_user_step - new user: %s - add_message: %s" % (user_email, add_message)
                                        )
                                    except:
                                        logger.warning(
                                            "add_user_step - new user not added - user_email: %s" % (user_email)
                                        )
                    except:
                        logger.warning("add_user_step - user not created - user_email: %s" % (user_email))

        def password_generator(length=10):
            """Generate random string to use as password

            :param length: length of password to generate
            return : random string
            """

            chars = string.ascii_letters + string.digits
            random.seed = os.urandom(1024)
            return "".join(random.choice(chars) for i in range(length))

        logger.debug("add_user_step - params={}".format(params))
        res = VeeamJobTask.job_action(task, step_id, add_user_action, "Add user", "Error adding user", params)
        return res, params

    #
    # action
    #
    @staticmethod
    def job_action(task, step_id, action, success, error, params):
        """Execute a server action

        :param task: celery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param params: input params
        :return: ext_id
        :raise:
        """
        logger.debug("job_action")
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


task_manager.tasks.register(VeeamJobTask())
