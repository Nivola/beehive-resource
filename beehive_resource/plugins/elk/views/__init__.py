# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from beehive_resource.plugins.elk.controller import ElkContainer
from beehive.common.apimanager import ApiView


class ElkApiView(ResourceApiView):
    containerclass = ElkContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class ElkAPI(ApiView):
    """ """

    base = "nrs/elk"
