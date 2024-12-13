# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beehive.common.data import cache
from beehive_resource.container import Resource, AsyncResource

logger = logging.getLogger(__name__)


class AwxResource(AsyncResource):
    objdef = "Awx.Resource"
    objdesc = "Awx resources"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

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

    @staticmethod
    @cache("awx.project.get", ttl=86400)
    def get_remote_project(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.project.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("awx.template.get", ttl=86400)
    def get_remote_template(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.job_template.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("awx.ad_hoc_command.get", ttl=86400)
    def get_remote_ad_hoc_command(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.ad_hoc_command.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}
