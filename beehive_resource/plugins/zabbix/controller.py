# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from urllib.parse import urlparse

from beehive_resource.container import Orchestrator
from beehive_resource.plugins.zabbix.entity.zbx_host import ZabbixHost
from beehive_resource.plugins.zabbix.entity.zbx_hostgroup import ZabbixHostgroup
from beehive_resource.plugins.zabbix.entity.zbx_template import ZabbixTemplate
from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup
from beehive_resource.plugins.zabbix.entity.zbx_action import ZabbixAction
from beedrones.zabbix.client import ZabbixManager, ZabbixError
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace


def get_task(task_name):
    return "%s.task.%s" % (__name__, task_name)


class ZabbixContainer(Orchestrator):
    """Zabbix orchestrator

    **connection syntax**:

        {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                "user": "...",
                "password": "..."
            },
            "id": 1
        }
    """

    objdef = "Zabbix"
    objdesc = "Zabbix container"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            ZabbixHost,
            ZabbixHostgroup,
            ZabbixTemplate,
            ZabbixUsergroup,
            ZabbixAction,
        ]

        self.conn = None
        self.token = None

    def ping(self):
        """Ping orchestrator.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self.__new_connection(timeout=30)
            res = self.conn.ping()
        except:
            self.logger.warning("ping ko", exc_info=True)
            res = False
        self.container_ping = res
        return res
        # res = self.conn.ping()
        # return res

    def info(self):
        """Get container info.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # TODO: verify permissions

        info = Orchestrator.info(self)
        return info

    def detail(self):
        """Get container detail.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # TODO: verify permissions

        info = Orchestrator.info(self)

        res = info
        res["details"] = {"version": self.conn.version()}

        return res

    def __new_connection(self, timeout=30):
        """Get zabbix connection with new token"""
        try:
            conn_params = self.conn_params["api"]
            uri = conn_params["uri"]
            user = conn_params["user"]
            pwd = conn_params["pwd"]

            # decrypt password
            pwd = self.decrypt_data(pwd)

            # get zabbix manager connection
            self.conn = ZabbixManager(uri=uri)
            self.conn.authorize(user=user, pwd=pwd)
            self.token = self.conn.token
        except ZabbixError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def __get_connection(self, token):
        """Get zabbix connection with existing token"""
        try:
            conn_params = self.conn_params["api"]
            uri = conn_params["uri"]

            self.conn = ZabbixManager(uri=uri)
            self.conn.authorize(token=token)
            self.logger.debug("Get zabbix connection %s with token: %s" % (self.conn, token))
        except ZabbixError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get zabbix connection"""
        token = self.token
        self.logger.debug("Use connection token: %s" % token)

        # create new token
        if token is None:
            self.logger.info("Active token is null, ask for new one")
            self.__new_connection()
        else:
            self.__get_connection(token)

        Orchestrator.get_connection(self)

    def close_connection(self, token):
        if self.conn is not None:
            try:
                self.conn.logout(token)
                self.conn = None
                self.logger.debug("Close zabbix connection: %s" % self.conn)
            except ZabbixError as ex:
                self.logger.error(ex, exc_info=True)
                raise ApiManagerError(ex, code=400)

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

        :param controller: (:py:class:`ResourceController`): resource controller instance
        :param type: (:py:class:`str`): container type
        :param name: (:py:class:`str`): container name
        :param desc: (:py:class:`str`): container desc
        :param active: (:py:class:`str`): container active
        :param conn: (:py:class:`dict`): container connection

                {
                    "api": {
                        "uri": "http://10.102.184.38:80/zabbix/api_jsonrpc.php",
                        "user": "Admin",
                        "pwd": "..."
                    }
                }

        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # encrypt password
        conn["api"]["pwd"] = controller.encrypt_data(conn["api"]["pwd"])

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

    def get_ip_address(self):
        """Get zabbix server ip address"""
        conn_params = self.conn_params["api"]
        uri = conn_params["uri"]
        parsed_uri = urlparse(uri)
        ip_address, port = parsed_uri.netloc.split(":")
        # http://cmpvc1-zabbix01.site03.nivolapiemonte.it:80/zabbix/api_jsonrpc.php
        return ip_address
