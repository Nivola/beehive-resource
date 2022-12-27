# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from gitlab import Gitlab
from beehive_resource.container import Orchestrator
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.gitlab.entity.group import GitlabGroup
from beehive_resource.plugins.gitlab.entity.project import GitlabProject


def get_task(task_name):
    return '%s.task.%s' % (__name__, task_name)


class GitlabContainer(Orchestrator):
    """Gitlab orchestrator

    **connection syntax**:

        {
            'uri': 'https://gitlab.csi.it/',
            'token': 'dsmerifmucer',
            'timeout': 5,
            'ssl_verify': False
        }
    """
    objdef = 'Gitlab'
    objdesc = 'Gitlab container'
    version = 'v1.0'

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            GitlabProject,
            GitlabGroup
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
            res = True
            # res = self.conn.ping()
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
        info = super().detail()
        return info

    def detail(self):
        """Get container detail.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = super().detail()
        return info

    def __new_connection(self, timeout=5):
        """Get zabbix connection with new token
        """
        try:
            uri = self.conn_params.get('uri')
            token = self.conn_params.get('token')
            ssl_verify = self.conn_params.get('ssl_verify', False)

            # decrypt token
            token = self.decrypt_data(token)

            # get gitlab manager connection
            gl_auth = {
                'private_token': token,
                'ssl_verify': ssl_verify,
                'timeout': timeout
            }
            self.conn = Gitlab(url=uri, **gl_auth)
            self.conn.auth()
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    # def __get_connection(self, token):
    #     """Get zabbix connection with existing token
    #     """
    #     try:
    #         conn_params = self.conn_params['api']
    #         uri = conn_params['uri']
    #
    #         self.conn = GitlabManager(uri=uri)
    #         self.conn.authorize(token=token)
    #         self.logger.debug('Get zabbix connection %s with token: %s' % (self.conn, token))
    #     except GitlabError as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise ApiManagerError(ex, code=400)

    def get_connection(self):
        """Get zabbix connection
        """
        self.__new_connection()

        Orchestrator.get_connection(self)

    def close_connection(self, token):
        pass
        # if self.conn is not None:
        #     try:
        #         self.conn.logout(token)
        #         self.conn = None
        #         self.logger.debug('Close zabbix connection: %s' % self.conn)
        #     except GitlabError as ex:
        #         self.logger.error(ex, exc_info=True)
        #         raise ApiManagerError(ex, code=400)

    @staticmethod
    def pre_create(controller=None, type=None, name=None, desc=None, active=None, conn=None, **kvargs):
        """Check input params

        :param ResourceController controller: resource controller instance
        :param str type: container type
        :param str name: container name
        :param str desc: container desc
        :param bool active: container active
        :param dict conn: container connection
        :param str conn.uri: connection uri (ex. https://gitlab.csi.it/)
        :param str conn.token: connection token
        :param int conn.timeout: connection timeout (ex. 5s)
        :param bool conn.ssl_verify: if True check ssl certificate
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # encrypt password
        conn['token']= controller.encrypt_data(conn['token'])

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
