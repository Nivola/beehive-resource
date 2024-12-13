# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from typing import TypeVar
from base64 import b64decode
from six import ensure_binary, ensure_text
from beehive_resource.container import Orchestrator
from beehive.common.apimanager import ApiManagerError
from beedrones.ssh_gateway.client import SshGwManager, SshGwError

T_SSHGWCONT = TypeVar("T_SSHGWCONT", bound="SshGatewayContainer")


class SshGatewayContainer(Orchestrator):
    """Ssh gateway container
    :param connection: json string like {}
    """

    objdef = "SshGateway"
    objdesc = "Ssh Gateway Container"
    objuri = "nrs/sshgateway"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)
        self.conn: SshGwManager = None

    def _get_connection(self):
        """
        Obtain SshGwManager Object
        """
        if self.conn is None:
            try:
                pwd = self.conn_params.get("pwd")
                pwd = self.decrypt_data(pwd)
                user = self.conn_params.get("user")
                port = self.conn_params.get("port")
                hosts = self.conn_params.get("hosts")

                self.conn = SshGwManager(
                    gw_hosts=hosts,
                    gw_port=port,
                    gw_user=user,
                    gw_pwd=pwd,
                    redis_manager=self.controller.redis_identity_manager,
                    redis_uri=None,
                )
            except SshGwError as ex:
                raise ApiManagerError(ex) from ex

        return self.conn

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res_redis = False
        res_hosts = False

        res_redis = self._get_connection().ping_db()
        if not res_redis:
            self.logger.warning("ssh gw redis db ping ko")

        res_hosts = self._get_connection().ping_hosts()
        if not res_hosts:
            self.logger.warning("ssh gw hosts ping ko")

        if res_hosts and res_redis:
            self.container_ping = True
        else:
            self.container_ping = False
        return self.container_ping

    @staticmethod
    def pre_create(controller=None, type=None, name=None, desc=None, active=None, conn=None, **kvargs):
        """Check input params

        :param ResourceController controller: resource controller instance
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param active: container active
        :param conn: container connection
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
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
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs

    def pre_clean(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs

    def activate_for_user(self, user, fqdn, port):
        """
        activate ssh gw connection
        :param user: e.g. abcd@def.gh
        :param fqdn: destination fqdn
        :param port: port number
        :return: private key
        :
        """
        try:
            private_key_b64 = self._get_connection().redis_update_ssh_gw_entry(user=user, host=fqdn, port=port)
            private_key = ensure_text(b64decode(ensure_binary(private_key_b64)))
        except SshGwError as ex:
            raise ApiManagerError(ex) from ex

        command_example = (
            "ssh -L <local_port>:"
            + fqdn
            + ":"
            + str(port)
            + " "
            + user
            + "@"
            + self.conn_params.get("hosts")[0]
            + " -i <keyfile>"
        )
        return private_key, command_example
