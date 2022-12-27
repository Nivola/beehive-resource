# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from beehive_resource.plugins.awx.controller import AwxContainer
from beehive.common.apimanager import ApiView


class AwxApiView(ResourceApiView):
    containerclass = AwxContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class AwxAPI(ApiView):
    """
    """
    base = 'nrs/awx'

