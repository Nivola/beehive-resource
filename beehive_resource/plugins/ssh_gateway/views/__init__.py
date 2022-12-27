# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.apimanager import ApiView
from beehive_resource.plugins.ssh_gateway.controller import SshGatewayContainer
from beehive_resource.view import ResourceApiView

# per swagger
class SshGatewayResourceApiViewBase(ResourceApiView):
    containerclass = SshGatewayContainer

    def get_container(self, controller, oid, connect=True, cache=True, *args, **kvargs):
        return ResourceApiView.get_container(self,controller,oid,connect,cache,args,kvargs)


class SshGatewayAPIBase(ApiView):
    """
    """
    base = 'nrs/sshgateway'