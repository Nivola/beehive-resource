# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beedrones.grafana.client_grafana import GrafanaManager
from beehive.common.data import cache
from beehive_resource.container import Resource, AsyncResource

logger = logging.getLogger(__name__)


class GrafanaResource(AsyncResource):
    objdef = "Grafana.Resource"
    objdesc = "Grafana resources"

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
    @cache("grafana.folder.get", ttl=86400)
    def get_remote_folder(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn_grafana.folder.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("grafana.folder-dashboards.get", ttl=86400)
    def get_remote_folder_dashboards(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            conn_grafana: GrafanaManager = container.conn_grafana
            # remote_entity = container.conn_grafana.folder.get_dashboard(folder_uid=ext_id, size=100).get('dashboards')
            remote_entity_folder = conn_grafana.folder.get(folder_uid=ext_id)
            folder_id = remote_entity_folder["id"]
            remote_entity = conn_grafana.dashboard.list(folder_id=folder_id, size=100).get("dashboards")
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("grafana.folder-permissions.get", ttl=86400)
    def get_remote_folder_permissions(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            conn_grafana: GrafanaManager = container.conn_grafana
            remote_entity = conn_grafana.folder.get_permissions(folder_uid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("grafana.team.get", ttl=86400)
    def get_remote_team(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn_grafana.team.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("grafana.team-users.get", ttl=86400)
    def get_remote_team_users(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            conn_grafana: GrafanaManager = container.conn_grafana
            remote_entity = conn_grafana.team.get_users(team_id=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("grafana.alert.get", ttl=86400)
    def get_remote_alert_notification(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn_grafana.alert_notification.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}
