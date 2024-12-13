# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beehive.common.data import cache
from beehive_resource.container import Resource, AsyncResource

# from beehive_resource.plugins.elk.controller import ElkContainer

logger = logging.getLogger(__name__)


class ElkResource(AsyncResource):
    objdef = "Elk.Resource"
    objdesc = "Elk resources"

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
    @cache("elk.space.get", ttl=86400)
    def get_remote_space(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn_kibana.space.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("elk.space-dashboards.get", ttl=86400)
    def get_remote_space_dashboards(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            from beedrones.elk.client_kibana import KibanaManager

            conn_kibana: KibanaManager
            conn_kibana = container.conn_kibana
            remote_entity = conn_kibana.space.get_dashboard(ext_id, "*", size=100).get("dashboards")
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("elk.role.get", ttl=86400)
    def get_remote_role(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn_kibana.role.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("elk.role_mapping.get", ttl=86400, pickling=True)
    def get_remote_role_mapping(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn_elastic.role_mapping.get(ext_id)
            # logger.info('+++++ remote_entity type %s' % (type(remote_entity)))
            # logger.info('+++++ remote_entity %s' % (remote_entity))
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}
