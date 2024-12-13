# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import json
from time import sleep
from datetime import datetime
from beedrones.elk.client_elastic import ElasticManager
from beedrones.elk.client_kibana import KibanaManager, KibanaError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator
from beehive_resource.plugins.elk.entity.elk_space import ElkSpace
from beehive_resource.plugins.elk.entity.elk_role import ElkRole
from beehive_resource.plugins.elk.entity.elk_role_mapping import ElkRoleMapping


def get_task(task_name):
    return "%s.task.%s" % (__name__.rstrip(".controller"), task_name)


class ElkContainer(Orchestrator):
    """Elk container

    :param connection: elk connection

        {
            "uri": "http://cmpto2-elk01.site02.nivolapiemonte.it/api/v2/",
            "user": "admin",
            "pwd": ...,
            "timeout": ...
        }
    """

    objdef = "Elk"
    objdesc = "Elk container"
    objuri = "nrs/elk"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [ElkSpace, ElkRole, ElkRoleMapping]

        self.conn_kibana = None
        self.conn_elastic = None
        self.prefix = "elk-token-"

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self.get_connection()
            res = self.conn_kibana.ping()
            self.logger.debug("+++++ ping kibana %s" % (res))
        except:
            self.logger.warning("+++++ ping kibana ko", exc_info=True)
            res = False

        try:
            self.get_connection()
            res = self.conn_elastic.ping()
            self.logger.debug("+++++ ping elastic %s" % (res))
        except:
            self.logger.warning("+++++ ping elastic ko", exc_info=True)
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
        # encrypt pwd for configurate "connection" in container table
        # conn['pwd'] = controller.encrypt_data(conn['pwd'])

        conn_elastic = conn["elastic"]
        conn_elastic["pwd"] = controller.encrypt_data(conn_elastic["pwd"])
        conn["elastic"] = conn_elastic

        conn_kibana = conn["kibana"]
        conn_kibana["pwd"] = controller.encrypt_data(conn_kibana["pwd"])
        conn["kibana"] = conn_kibana

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

    # def __get_connection(self, token):
    #     """Get elk connection with existing token
    #     """
    #     try:
    #         conn_params = self.conn_params
    #         uri = conn_params.get('uri')
    #         user = conn_params.get('user')
    #         pwd = conn_params.get('pwd')

    #         # decrypt password
    #         pwd = self.decrypt_data(pwd)

    #         # self.conn = ElkManager(uri=uri)
    #         self.conn_kibana = KibanaManager(uri=uri, user=user, passwd=pwd)
    #         self.conn_elastic = ElasticManager(host=host, uri=uri, user=user, passwd=pwd)

    #         # self.conn.authorize(token=token)
    #         # self.logger.debug('Get elk connection %s with token %s' % (self.conn, token))
    #         self.logger.debug('Get elk connection %s' % (self.conn))

    #     # except ElkError as ex:
    #     except KibanaError as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)

    def __new_connection(self):
        """Get elk connection with new token"""
        try:
            conn_params = self.conn_params

            elastic = conn_params.get("elastic")
            elastic_host = elastic.get("host")
            elastic_hosts = elastic.get("hosts")
            elastic_user = elastic.get("user")
            elastic_pwd = elastic.get("pwd")

            kibana = conn_params.get("kibana")
            kibana_uri = kibana.get("uri")
            kibana_user = kibana.get("user")
            kibana_pwd = kibana.get("pwd")

            # decrypt password
            elastic_pwd = self.decrypt_data(elastic_pwd)
            kibana_pwd = self.decrypt_data(kibana_pwd)

            from six import b, ensure_text

            elastic_pwd = ensure_text(elastic_pwd)
            kibana_pwd = ensure_text(kibana_pwd)

            # self.conn_elastic = ElkManager(uri=uri)
            # self.conn_kibana: KibanaManager
            self.conn_elastic = ElasticManager(
                host=elastic_host,
                hosts=elastic_hosts,
                user=elastic_user,
                pwd=elastic_pwd,
            )
            self.conn_kibana = KibanaManager(uri=kibana_uri, user=kibana_user, passwd=kibana_pwd)

            # self.conn.authorize(user=user, pwd=pwd)
            # token = self.conn.get_token()

            # build key
            # key = self.prefix + str(self.oid) + '-' + user
            # cache token
            # self.cache.set(key, token, ttl=86400)
            # self.logger.debug('Create elk connection %s with token %s' % (self.conn, token['token']))
            self.logger.debug("Create elk connection elastic %s " % (self.conn_elastic))
            self.logger.debug("Create elk connection kibana %s " % (self.conn_kibana))

        # except ElkError as ex:
        except KibanaError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get elk connection"""
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
        if self.conn_kibana is None:
            pass

    def wait_for_elk_job(self, job_query_func, job_id, maxtime=600, delta=1, job_error_func=None):
        job = job_query_func(job_id)
        status = job["status"]
        elapsed = 0
        while status not in ["successful", "failed", "error", "canceled"]:
            self.logger.debug("wait for elk job %s" % job_id)
            job = job_query_func(job_id)
            status = job["status"]
            sleep(delta)
            elapsed += delta
            if elapsed >= maxtime:
                raise TimeoutError("elk job %s query timeout" % job_id)
        if status in ["failed", "error"]:
            self.logger.error(job["result_traceback"])
            err = ""
            if job_error_func is not None:
                err = job_error_func()
            raise ApiManagerError("elk job %s error: %s" % (job_id, err))
        elif status == "cancelled":
            self.logger.error(job["elk job %s cancelled" % job_id])
            raise ApiManagerError("elk job %s cancelled" % job_id)
        else:
            self.logger.info("elk job %s successful" % job_id)
