# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.container import Orchestrator
from beedrones.ontapp.client import OntapManager, OntapError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume


def get_task(task_name):
    return '%s.task.%s' % (__name__, task_name)


class OntapNetappContainer(Orchestrator):
    """Ontap Netapp orchestrator

    **connection syntax**:

        {
            "host": ..,
            "port": ..,
            "proto": ..,
            "user": ..,
            "pwd": ..,
            "timeout": 5.0,
        }
    """
    objdef = 'OntapNetapp'
    objdesc = 'OntapNetapp container'
    version = 'v1.0'

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            OntapNetappSvm,
            OntapNetappVolume
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
            self.__new_connection(timeout=1)
            res = self.conn.ping()
        except:
            self.logger.warning('ping ko', exc_info=True)
            res = False
        self.container_ping = res
        return res

    def info(self):
        """Get container info.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Orchestrator.info(self)
        return info

    def detail(self):
        """Get container detail.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Orchestrator.info(self)

        res = info
        res['details'] = {
            'cluster': self.get_cluster_info()
            # 'version': self.conn.version()
        }

        return res

    def __new_connection(self, timeout=5):
        """Get zabbix connection with new token
        """
        try:
            host = self.conn_params.get('host')
            port = self.conn_params.get('port', 80)
            proto = self.conn_params.get('proto', 'http')
            user = self.conn_params.get('user')
            pwd = self.conn_params.get('pwd')

            # decrypt password
            pwd = self.decrypt_data(pwd)
            self.conn = OntapManager(host, user, pwd, port=port, proto=proto, timeout=5.0)
            self.conn.authorize()
        except OntapError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get ontap netapp connection
        """
        if self.conn is None:
            self.__new_connection()
        else:
            if self.conn.ping() is False:
                self.__new_connection()

        Orchestrator.get_connection(self)

    def close_connection(self, token):
        if self.conn is not None:
            pass

    @staticmethod
    def pre_create(controller=None, type=None, name=None, desc=None, active=None, conn=None, **kvargs):
        """Check input params

        :param controller: (:py:class:`ResourceController`): resource controller instance
        :param type: (:py:class:`str`): container type
        :param name: (:py:class:`str`): container name
        :param desc: (:py:class:`str`): container desc
        :param active: (:py:class:`str`): container active
        :param conn: (:py:class:`dict`): container connection
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # encrypt password
        conn['pwd'] = controller.encrypt_data(conn['pwd'])

        kvargs = {
            'type': type,
            'name': name,
            'desc': desc,
            'active': active,
            'conn': conn,
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

    def get_cluster_info(self):
        """Get ontap netapp cluster info"""
        res = self.conn.cluster.get()
        return res
