# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive_resource.plugins.ssh_gateway.views.ssh_gateway_configuration import SshGatewayConfigurationAPI
from beehive_resource.plugins.ssh_gateway.controller import SshGatewayContainer


class SshGatewayPlugin(object):
    def __init__(self, module):
        self.module = module
    
    def init(self):
        service = SshGatewayContainer(self.module.get_controller())
        service.init_object()
    
    def register(self):
        apis = [
            SshGatewayConfigurationAPI
        ]
        self.module.set_apis(apis)
        
        self.module.add_container(SshGatewayContainer.objdef, SshGatewayContainer)