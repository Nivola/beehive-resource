# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.zabbix.controller import ZabbixContainer
from beehive.common.apimanager import ApiView
from beehive_resource.views import ResourceApiView


class ZabbixApiView(ResourceApiView):
    containerclass = ZabbixContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class ZabbixAPI(ApiView):
    """ """

    base = "nrs/zabbix"
