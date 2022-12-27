# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from beehive_resource.container import Resource, AsyncResourceV3


def get_task(task_name):
    return '%s.%s' % (__name__.replace('entity', 'task'), task_name)


class GitlabResource(AsyncResourceV3):
    objdef = 'Gitlab.Resource'
    objdesc = 'Gitlab resources'

    def __init__(self, *args, **kvargs):
        """ """
        AsyncResourceV3.__init__(self, *args, **kvargs)

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
        return info
