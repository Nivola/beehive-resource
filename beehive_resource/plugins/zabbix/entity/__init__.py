# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.container import Resource, AsyncResource
from beehive.common.data import cache


def get_task(task_name):
    return "%s.%s" % (__name__.replace("entity", "task"), task_name)


class ZabbixResource(AsyncResource):
    objdef = "Zabbix.Resource"
    objdesc = "Zabbix resources"

    def __init__(self, *args, **kvargs):
        """ """
        AsyncResource.__init__(self, *args, **kvargs)

    def info(self):
        """Get infos.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)

        # TODO: add details
        # if self.ext_obj is not None:
        #     info['details'] = {
        #         'key_one': self.ext_obj.get('key_one', None),
        #         'key_two': self.ext_obj.get('key_two', None)
        #     }

        return info

    # #
    # # zabbix query
    # #
    # @staticmethod
    # @cache('zabbix.host.list', ttl=86400)
    # def list_hosts(controller, postfix, container, *args, **kvargs):
    #     hosts = container.conn.host.list(detail=True)
    #     return hosts
    #
    # @staticmethod
    # @cache('zabbix.host.get', ttl=86400)
    # def get_host(controller, postfix, container, ext_id, *args, **kvargs):
    #     host = container.conn.host.get(ext_id)
    #     return host
