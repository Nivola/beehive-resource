# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from flasgger import fields, Schema
from beehive_resource.plugins.ontap.controller import OntapNetappContainer
from beehive.common.apimanager import ApiView

class OntapNetappApiView(ResourceApiView):
    containerclass = OntapNetappContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class OntapNetappAPI(ApiView):
    """ """

    base = "nrs/ontap"
