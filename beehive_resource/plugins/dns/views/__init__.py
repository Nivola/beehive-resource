# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from beehive.common.apimanager import ApiView
from beehive_resource.plugins.dns import DnsContainer
from beehive_resource.view import ResourceApiView


class DnsApiView(ResourceApiView):
    tags = ["dns"]
    containerclass = DnsContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class DnsAPI(ApiView):
    """ """

    base = "nrs/dns"
