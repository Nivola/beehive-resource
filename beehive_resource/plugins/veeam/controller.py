# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import json
from time import sleep
from datetime import datetime
from beedrones.veeam.client_veeam import VeeamManager, VeeamError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator

from beehive_resource.plugins.veeam.entity.veeam_job import VeeamJob


def get_task(task_name):
    return "%s.task.%s" % (__name__.rstrip(".controller"), task_name)


class VeeamContainer(Orchestrator):
    """Veeam container

    :param connection: veeam connection

        {
            "uri": "http://cmpto2-veeam01.site02.nivolapiemonte.it/api/v2/",
            "user": "admin",
            "pwd": ...,
            "timeout": ...
        }
    """

    objdef = "Veeam"
    objdesc = "Veeam container"
    objuri = "nrs/veeam"
    version = "v1.0"

    conn_veeam: VeeamManager = None

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [VeeamJob]

        self.conn_veeam = None
        self.prefix = "veeam-token-"

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self.get_connection()
            res = self.conn_veeam.ping()
            self.logger.debug("+++++ ping veeam %s" % (res))
        except:
            self.logger.warning("+++++ ping veeam ko", exc_info=True)
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
        # logger = logging.getLogger(__name__)
        # logger.debug('+++++ pre_create - conn: %s ' % (conn))
        # encrypt pwd for configurate "connection" in container table
        from beehive_resource.controller import ResourceController

        resourceController: ResourceController = controller
        conn["pwd"] = resourceController.encrypt_data(conn["pwd"])

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
        """Get veeam connection with existing token"""
        try:
            conn_params = self.conn_params

            veeam_host = conn_params.get("host")
            veeam_port = conn_params.get("port")
            veeam_protocol = conn_params.get("proto")
            veeam_path = conn_params.get("path")
            uri = "%s://%s:%s%s" % (veeam_protocol, veeam_host, veeam_port, veeam_path)

            self.conn_veeam = VeeamManager(uri=uri)
            self.conn_veeam.authorize(token=token)
            self.logger.debug("Get veeam connection %s with token %s" % (self.conn, token))
        except VeeamError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def __new_connection(self, cache_key):
        """Get veeam connection with new token"""
        try:
            conn_params = self.conn_params
            self.logger.debug("+++++ __new_connection - conn_params: %s " % (conn_params))

            veeam_host = conn_params.get("host")
            veeam_port = conn_params.get("port")
            veeam_protocol = conn_params.get("proto")
            veeam_path = conn_params.get("path")
            uri = "%s://%s:%s%s" % (veeam_protocol, veeam_host, veeam_port, veeam_path)
            self.conn_veeam = VeeamManager(uri=uri)

            veeam_user = conn_params.get("user")
            veeam_pwd = conn_params.get("pwd")
            # decrypt password
            veeam_pwd = self.decrypt_data(veeam_pwd)
            # self.logger.debug('+++++ __new_connection - veeam_pwd: %s ' % (veeam_pwd))
            self.conn_veeam.authorize(user=veeam_user, pwd=veeam_pwd)
            token = self.conn_veeam.get_token()
            expires = token.get("expires")

            # cache token
            self.logger.debug(
                "+++++ Create veeam connection - cache set cache_key %s, token %s, expires %s"
                % (cache_key, token, expires)
            )
            self.cache.set(cache_key, token, ttl=expires)
            self.logger.debug("Create veeam connection %s with token %s" % (self.conn, token["token"]))
            self.logger.debug("Create veeam connection %s " % (self.conn_veeam))

        # except VeeamError as ex:
        except VeeamError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get veeam connection"""
        # get user
        user = self.conn_params.get("user")
        # build key
        cache_key = self.prefix + str(self.oid) + "-" + user
        self.logger.debug("+++++ get_connection - cache_key: %s" % cache_key)
        # get from cache
        res = self.cache.get(cache_key)
        self.logger.debug("+++++ get_connection - res: %s" % res)

        if res is None:
            self.__new_connection(cache_key)
        else:
            try:
                # extract token from response
                token = res.get("token")
                # check token expire
                # expires_at = data.get('expires', '')
                # a = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                # b = datetime.utcnow()
                # is_valid = (a >= b)
                # if is_valid is True:
                self.logger.debug("+++++ Token %s is valid" % token)
                self.__get_connection(token)
                # else:
                #     self.logger.debug('____Token %s is expired' % token)
                #     self.__new_connection()
            except:
                self.__new_connection(cache_key)

        Orchestrator.get_connection(self)

    def close_connection(self):
        """ """
        if self.conn_veeam is None:
            pass

    def wait_for_veeam_job(self, job_query_func, job_id, maxtime=600, delta=1, job_error_func=None):
        job = job_query_func(job_id)
        status = job["status"]
        elapsed = 0
        while status not in ["successful", "failed", "error", "canceled"]:
            self.logger.debug("wait for veeam job %s" % job_id)
            job = job_query_func(job_id)
            status = job["status"]
            sleep(delta)
            elapsed += delta
            if elapsed >= maxtime:
                raise TimeoutError("veeam job %s query timeout" % job_id)
        if status in ["failed", "error"]:
            self.logger.error(job["result_traceback"])
            err = ""
            if job_error_func is not None:
                err = job_error_func()
            raise ApiManagerError("veeam job %s error: %s" % (job_id, err))
        elif status == "cancelled":
            self.logger.error(job["veeam job %s cancelled" % job_id])
            raise ApiManagerError("veeam job %s cancelled" % job_id)
        else:
            self.logger.info("veeam job %s successful" % job_id)
