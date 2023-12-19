# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from beehive_resource.plugins.grafana.controller import GrafanaContainer
from beehive.common.apimanager import ApiView


class GrafanaApiView(ResourceApiView):
    containerclass = GrafanaContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class GrafanaAPI(ApiView):
    """ """

    base = "nrs/grafana"
