# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import json
from time import sleep
from datetime import datetime
from beedrones.awx.client import AwxManager, AwxError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator
from beehive_resource.plugins.awx.entity.awx_ad_hoc_command import AwxAdHocCommand
from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate
from beehive_resource.plugins.awx.entity.awx_project import AwxProject


def get_task(task_name):
    return "%s.task.%s" % (__name__.rstrip(".controller"), task_name)


class AwxContainer(Orchestrator):
    """Awx container

    :param connection: awx connection

        {
            "uri": "http://cmpto2-awx01.site02.nivolapiemonte.it/api/v2/",
            "user": "admin",
            "pwd": ...,
            "timeout": ...
        }
    """

    objdef = "Awx"
    objdesc = "Awx container"
    objuri = "nrs/awx"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            AwxProject,
            AwxJobTemplate,
            AwxAdHocCommand,
        ]

        self.conn = None
        self.prefix = "awx-token-"

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self.get_connection()
            res = self.conn.ping()
        except:
            self.logger.warning("ping ko", exc_info=True)
            res = False
        self.container_ping = res
        return res
        # res = self.conn.ping()
        # return res

    @staticmethod
    def pre_create(
        controller=None,
        type=None,
        name=None,
        desc=None,
        active=None,
        conn=None,
        **kvargs,
    ):
        """Check input params

        :param controller: resource controller instance
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param active: container active
        :param conn: container connection
        :return: kvargs
        :raise ApiManagerError:
        """
        # encrypt pwd
        conn["pwd"] = controller.encrypt_data(conn["pwd"])

        kvargs = {
            "type": type,
            "name": name,
            "desc": desc,
            "active": active,
            "conn": conn,
        }
        return kvargs

    def pre_change(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def pre_clean(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def __get_connection(self, token):
        """Get awx connection with existing token"""
        try:
            conn_params = self.conn_params
            uri = conn_params.get("uri")

            self.conn = AwxManager(uri=uri)
            self.conn.authorize(token=token)
            self.logger.debug("Get awx connection %s with token %s" % (self.conn, token))
        except AwxError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def __new_connection(self):
        """Get awx connection with new token"""
        try:
            conn_params = self.conn_params
            uri = conn_params.get("uri")
            user = conn_params.get("user")
            pwd = conn_params.get("pwd")

            # decrypt password
            pwd = self.decrypt_data(pwd)

            self.conn = AwxManager(uri=uri)
            self.conn.authorize(user=user, pwd=pwd)
            token = self.conn.get_token()
            # build key
            key = self.prefix + str(self.oid) + "-" + user
            # cache token
            self.cache.set(key, token, ttl=86400)
            self.logger.debug("Create awx connection %s with token %s" % (self.conn, token["token"]))
        except AwxError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get awx connection"""
        # get user
        user = self.conn_params.get("user")
        # build key
        key = self.prefix + str(self.oid) + "-" + user
        # get from cache
        res = self.cache.get_by_pattern(key)

        if res is None or len(res) == 0:
            self.__new_connection()
        else:
            try:
                # extract token from response
                res = res[0]
                value = res.get("value")
                value = json.loads(value)
                data = value.get("data")
                token = data.get("token")
                # check token expire
                expires_at = data.get("expires", "1970-01-01T00:00:00.000000Z")
                a = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                b = datetime.utcnow()
                is_valid = a >= b
                if is_valid is True:
                    # self.logger.debug('____Token %s is valid' % token)
                    self.__get_connection(token)
                else:
                    # self.logger.debug('____Token %s is expired' % token)
                    self.__new_connection()
            except:
                self.__new_connection()

        Orchestrator.get_connection(self)

    def close_connection(self):
        """ """
        if self.conn is None:
            pass

    def wait_for_awx_job(
        self, job_query_func, job_id, maxtime=3600, delta=1, job_error_func=None, job_success_func=None
    ):
        job = job_query_func(job_id)  # job-get
        status = job["status"]
        self.logger.debug("wait for awx job %s - status %s" % (job_id, status))
        elapsed = 0

        while status not in ["successful", "failed", "error", "canceled"]:
            job = job_query_func(job_id)
            status = job["status"]
            self.logger.debug("wait for awx job %s - status %s" % (job_id, status))
            sleep(delta)
            elapsed += delta
            if elapsed >= maxtime:
                raise TimeoutError("awx job %s query timeout" % job_id)

        if status in ["failed", "error"]:
            self.logger.error(job["result_traceback"])
            err = ""
            if job_error_func is not None:
                err = job_error_func()
            raise ApiManagerError("awx job %s error: %s" % (job_id, err))

        elif status == "cancelled":
            self.logger.error(job["awx job %s cancelled" % job_id])
            raise ApiManagerError("awx job %s cancelled" % job_id)

        else:
            self.logger.info("awx job %s successful" % job_id)
            if job_success_func is not None:
                stdout = job_success_func()
                return stdout
