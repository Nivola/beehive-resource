# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import json
import logging
from time import sleep
from datetime import datetime
from beedrones.grafana.client_grafana import GrafanaManager, GrafanaError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator
from beehive_resource.plugins.grafana.entity.grafana_alert_notification import (
    GrafanaAlertNotification,
)
from beehive_resource.plugins.grafana.entity.grafana_folder import GrafanaFolder
from beehive_resource.plugins.grafana.entity.grafana_team import GrafanaTeam
from beehive_resource.plugins.grafana.entity.grafana_dashboard import GrafanaDashboard


def get_task(task_name):
    return "%s.task.%s" % (__name__.rstrip(".controller"), task_name)


class GrafanaContainer(Orchestrator):
    """Grafana container

    :param connection: grafana connection

        {
            "uri": "http://cmpto2-grafana01.site02.nivolapiemonte.it/api/v2/",
            "user": "admin",
            "pwd": ...,
            "timeout": ...
        }
    """

    objdef = "Grafana"
    objdesc = "Grafana container"
    objuri = "nrs/grafana"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            GrafanaFolder,
            GrafanaTeam,
            GrafanaAlertNotification,
            GrafanaDashboard,
        ]

        self.conn_grafana = None
        self.prefix = "grafana-token-"

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self.get_connection()
            res = self.conn_grafana.ping()
            self.logger.debug("+++++ ping grafana %s" % (res))
        except:
            self.logger.warning("+++++ ping grafana ko", exc_info=True)
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

    def __new_connection(self):
        """Get grafana connection with new token"""
        try:
            conn_params = self.conn_params
            self.logger.debug("+++++ __new_connection - conn_params: %s " % (conn_params))

            # grafana = conn_params.get('grafana')

            grafana_host = conn_params.get("host")
            grafana_hosts = conn_params.get("hosts")
            grafana_port = conn_params.get("port")
            grafana_user = conn_params.get("user")
            grafana_pwd = conn_params.get("pwd")
            grafana_protocol = conn_params.get("proto")

            # decrypt password
            grafana_pwd = self.decrypt_data(grafana_pwd)
            # self.logger.debug('+++++ __new_connection - grafana_pwd: %s ' % (grafana_pwd))

            self.conn_grafana = GrafanaManager(
                host=grafana_host,
                hosts=grafana_hosts,
                port=grafana_port,
                protocol=grafana_protocol,
                username=grafana_user,
                pwd=grafana_pwd,
            )

            # self.conn.authorize(user=user, pwd=pwd)
            # token = self.conn.get_token()

            # build key
            # key = self.prefix + str(self.oid) + '-' + user
            # cache token
            # self.cache.set(key, token, ttl=86400)
            # self.logger.debug('Create grafana connection %s with token %s' % (self.conn, token['token']))
            self.logger.debug("Create grafana connection %s " % (self.conn_grafana))

        # except GrafanaError as ex:
        except GrafanaError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get grafana connection"""
        # get user
        # user = self.conn_params.get('user')
        # build key
        # key = self.prefix + str(self.oid) + '-' + user
        # get from cache
        # res = self.cache.get_by_pattern(key)

        # if res is None or len(res) == 0:
        self.__new_connection()
        # else:
        #     try:
        #         # extract token from response
        #         res = res[0]
        #         value = res.get('value')
        #         value = json.loads(value)
        #         data = value.get('data')
        #         token = data.get('token')
        #         # check token expire
        #         expires_at = data.get('expires', '1970-01-01T00:00:00.000000Z')
        #         a = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M:%S.%fZ')
        #         b = datetime.utcnow()
        #         is_valid = (a >= b)
        #         if is_valid is True:
        #             # self.logger.debug('____Token %s is valid' % token)
        #             self.__get_connection(token)
        #         else:
        #             # self.logger.debug('____Token %s is expired' % token)
        #             self.__new_connection()
        #     except:
        #         self.__new_connection()

        Orchestrator.get_connection(self)

    def close_connection(self):
        """ """
        if self.conn_grafana is None:
            pass

    def wait_for_grafana_job(self, job_query_func, job_id, maxtime=600, delta=1, job_error_func=None):
        job = job_query_func(job_id)
        status = job["status"]
        elapsed = 0
        while status not in ["successful", "failed", "error", "canceled"]:
            self.logger.debug("wait for grafana job %s" % job_id)
            job = job_query_func(job_id)
            status = job["status"]
            sleep(delta)
            elapsed += delta
            if elapsed >= maxtime:
                raise TimeoutError("grafana job %s query timeout" % job_id)
        if status in ["failed", "error"]:
            self.logger.error(job["result_traceback"])
            err = ""
            if job_error_func is not None:
                err = job_error_func()
            raise ApiManagerError("grafana job %s error: %s" % (job_id, err))
        elif status == "cancelled":
            self.logger.error(job["grafana job %s cancelled" % job_id])
            raise ApiManagerError("grafana job %s cancelled" % job_id)
        else:
            self.logger.info("grafana job %s successful" % job_id)
