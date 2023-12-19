# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beecell.types.type_dict import dict_get
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup
from beehive_resource.plugins.zabbix.controller import ZabbixContainer, ZabbixManager
from beehive_resource.task_v2 import AbstractResourceTask, task_manager
import string
import os, random

logger = logging.getLogger(__name__)


class ZabbixUsergroupTask(AbstractResourceTask):
    """ZabbixUsergroup task"""

    name = "zabbix_usergroup_task"
    entity_class = ZabbixUsergroup

    @staticmethod
    @task_step()
    def zabbix_usergroup_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("+++++ zabbix_usergroup_create_physical_step")

        cid = params.get("cid")  # container id
        oid = params.get("id")
        logger.debug("+++++ cid: %s" % cid)
        logger.debug("+++++ oid: %s" % oid)

        # usergroup_id = params.get('usergroup_id')
        name = params.get("name")
        hostgroup_id = params.get("hostgroup_id")

        # logger.debug('usergroup_id: %s: ' % usergroup_id)
        logger.debug("+++++ name: %s" % name)
        logger.debug("+++++ hostgroup_id: %s" % hostgroup_id)

        task.progress(step_id, msg="Get configuration params")

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn

        task.progress(step_id, msg="Zabbix usergroup %s does not exist yet" % name)
        inst = zabbixManager.usergroup.add(name=name, hostgroup_id=hostgroup_id)
        logger.debug("+++++ inst: %s" % inst)
        inst_id = inst["usrgrpids"][0]
        task.progress(step_id, msg="Zabbix usergroup created: %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def zabbix_usergroup_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def zabbix_usergroup_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        logger.debug("+++++ zabbix_usergroup_delete_physical_step")

        cid = params.get("cid")
        oid = params.get("id")
        logger.debug("+++++ cid %s: " % cid)
        logger.debug("+++++ oid %s: " % oid)

        zabbixContainer: ZabbixContainer = task.get_container(cid)
        zabbixManager: ZabbixManager = zabbixContainer.conn
        resource = zabbixContainer.get_simple_resource(oid)
        logger.debug("+++++ resource.ext_id: %s: " % resource.ext_id)

        if resource.is_ext_id_valid() is True:
            try:
                # check if usergroup exists
                zabbixManager.usergroup.get(usergroup_id=resource.ext_id)

                # delete user of usergroup
                remote_users = zabbixManager.user.list(usrgrpids=resource.ext_id)
                for user in remote_users:
                    userid = user["userid"]
                    zabbixManager.user.delete(userid)

                # delete usergroup
                zabbixManager.usergroup.delete(usergroup_id=resource.ext_id)
                task.progress(step_id, msg=" Zabbix usergroup deleted %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg=" Zabbix usergroup %s does not exist anymore" % resource.ext_id,
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

            zabbixContainer: ZabbixContainer = task.get_container(cid)
            zabbixManager: ZabbixManager = zabbixContainer.conn

            username: str = params["username"]
            users_email: str = params["users_email"]
            severity: str = params["severity"]
            usergroup_id_to = params["usergroup_id_to"]

            # cerco gli utenti del usergroup
            user_found = None
            remote_users = zabbixManager.user.list(usrgrpids=usergroup_id_to)
            for user in remote_users:
                alias = user["alias"]
                logger.debug("add_user_step - alias: %s" % (alias))
                if alias == username:
                    user_found = user

            email_array = users_email.split(",")

            # convert array severity literal in integer severity
            severity_sum = 0
            severity_array = severity.split(",")
            for severity_item in severity_array:
                from beedrones.zabbix.user import ZabbixUser as BeedronesZabbixUser
                from beehive_resource.plugins.zabbix import ZabbixPlugin

                if severity_item == ZabbixPlugin.SEVERITY_DESC_DISASTER:
                    severity_sum += BeedronesZabbixUser.SEVERITY_DISASTER

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_HIGH:
                    severity_sum += BeedronesZabbixUser.SEVERITY_HIGH

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_AVERAGE:
                    severity_sum += BeedronesZabbixUser.SEVERITY_AVERAGE

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_WARNING:
                    severity_sum += BeedronesZabbixUser.SEVERITY_WARNING

                elif severity_item == ZabbixPlugin.SEVERITY_DESC_INFORMATION:
                    severity_sum += BeedronesZabbixUser.SEVERITY_INFORMATION

            if user_found is None:
                password = password_generator()
                res = zabbixManager.user.add(
                    username=username, passwd=password, usrgrpid=usergroup_id_to, email=email_array
                )
            else:
                userid = user_found["userid"]
                res = zabbixManager.user.update(userid, email=email_array, severity=severity_sum)

        def password_generator(length=10):
            """Generate random string to use as password

            :param length: length of password to generate
            return : random string
            """

            chars = string.ascii_letters + string.digits
            random.seed = os.urandom(1024)
            return "".join(random.choice(chars) for i in range(length))

        logger.debug("add_user_step - params={}".format(params))
        res = ZabbixUsergroupTask.usergroup_action(
            task, step_id, add_user_action, "Add user", "Error adding user", params
        )
        return res, params

    #
    # action
    #
    @staticmethod
    def usergroup_action(task, step_id, action, success, error, params):
        """Execute a server action

        :param task: celery task instance
        :param action: action to execute
        :param success: success message
        :param error: error message
        :param params: input params
        :return: ext_id
        :raise:
        """
        logger.debug("usergroup_action")
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


task_manager.tasks.register(ZabbixUsergroupTask())
