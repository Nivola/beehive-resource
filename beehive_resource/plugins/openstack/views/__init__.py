# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.view import ResourceApiView
from beehive_resource.plugins.openstack.controller import OpenstackContainer
from beehive.common.apimanager import ApiView


class OpenstackApiView(ResourceApiView):
    containerclass = OpenstackContainer

    def get_container(self, controller, oid, projectid=None):
        c = ResourceApiView.get_container(self, controller, oid, projectid=projectid)
        return c


class OpenstackAPI(ApiView):
    """ """

    base = "nrs/openstack"
