# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from .controller import OpenstackContainer
from beehive_resource.plugins.openstack.views.ops_system import OpenstackSystemAPI
from beehive_resource.plugins.openstack.views.ops_project import OpenstackProjectAPI
from beehive_resource.plugins.openstack.views.ops_domain import OpenstackDomainAPI
from beehive_resource.plugins.openstack.views.ops_keystone import OpenstackKeystoneAPI
from beehive_resource.plugins.openstack.views.ops_flavor import OpenstackFlavorAPI
from beehive_resource.plugins.openstack.views.ops_image import OpenstackImageAPI
from beehive_resource.plugins.openstack.views.ops_server import OpenstackServerAPI
from beehive_resource.plugins.openstack.views.ops_network import OpenstackNetworkAPI
from beehive_resource.plugins.openstack.views.ops_port import OpenstackPortAPI
from beehive_resource.plugins.openstack.views.ops_subnet import OpenstackSubnetAPI
from beehive_resource.plugins.openstack.views.ops_volume import OpenstackVolumeAPI
from beehive_resource.plugins.openstack.views.ops_security_group import (
    OpenstackSecurityGroupAPI,
)
from beehive_resource.plugins.openstack.views.ops_router import OpenstackRouterAPI
from beehive_resource.plugins.openstack.views.ops_stack import OpenstackStackAPI
from beehive_resource.plugins.openstack.views.ops_stack_template import (
    OpenstackStackTemplateAPI,
)
from beehive_resource.plugins.openstack.views.ops_share import OpenstackShareAPI
from beehive_resource.plugins.openstack.views.ops_volume_type import (
    OpenstackVolumeTypeAPI,
)


class OpenstackPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = OpenstackContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            OpenstackSystemAPI,
            OpenstackKeystoneAPI,
            OpenstackDomainAPI,
            OpenstackProjectAPI,
            OpenstackFlavorAPI,
            OpenstackImageAPI,
            OpenstackServerAPI,
            OpenstackNetworkAPI,
            OpenstackPortAPI,
            OpenstackSubnetAPI,
            OpenstackSecurityGroupAPI,
            OpenstackRouterAPI,
            OpenstackVolumeAPI,
            OpenstackStackAPI,
            OpenstackStackTemplateAPI,
            OpenstackShareAPI,
            OpenstackVolumeTypeAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(OpenstackContainer.objdef, OpenstackContainer)
