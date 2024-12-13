# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from beehive_resource.plugins.vsphere.controller import VsphereContainer
from beehive.common.apimanager import ApiView


class VsphereApiView(ResourceApiView):
    tags = ["vsphere"]
    containerclass = VsphereContainer

    def get_container(self, controller, oid):
        c = ResourceApiView.get_container(self, controller, oid)
        return c


class VsphereAPI(ApiView):
    """ """

    base = "nrs/vsphere"
