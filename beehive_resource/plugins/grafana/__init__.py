# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.grafana.controller import GrafanaContainer
from beehive_resource.plugins.grafana.views.grafana_alert_notification import (
    GrafanaAlertNotificationAPI,
)
from beehive_resource.plugins.grafana.views.grafana_folder import GrafanaFolderAPI
from beehive_resource.plugins.grafana.views.grafana_team import GrafanaTeamAPI
from beehive_resource.plugins.grafana.views.grafana_dashboard import GrafanaDashboardAPI


class GrafanaPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = GrafanaContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            GrafanaFolderAPI,
            GrafanaTeamAPI,
            GrafanaAlertNotificationAPI,
            GrafanaDashboardAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(GrafanaContainer.objdef, GrafanaContainer)
