# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from beehive_resource.plugins.veeam.controller import VeeamContainer
from beehive.common.apimanager import ApiView


class VeeamApiView(ResourceApiView):
    containerclass = VeeamContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class VeeamAPI(ApiView):
    """ """

    base = "nrs/veeam"
