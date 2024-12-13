# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.views.logging_role import ComputeLoggingRoleAPI
from beehive_resource.plugins.provider.views.logging_role_mapping import (
    ComputeLoggingRoleMappingAPI,
)
from beehive_resource.plugins.provider.views.monitoring_folder import (
    ComputeMonitoringFolderAPI,
)
from beehive_resource.plugins.provider.views.monitoring_team import (
    ComputeMonitoringTeamAPI,
)
from beehive_resource.plugins.provider.views.monitoring_alert import (
    ComputeMonitoringAlertAPI,
)
from beehive_resource.plugins.provider.views.monitoring_threshold import ComputeMonitoringThresholdAPI
from .controller import LocalProvider
from .views.bastion import BastionProviderAPI
from .views.site import SiteProviderAPI
from .views.region import RegionProviderAPI
from .views.compute_zone import ComputeZoneAPI
from .views.image import ComputeImageAPI
from .views.flavor import ComputeFlavorAPI
from .views.vpc_v2 import VpcProviderAPI
from .views.security_group import SecurityGroupProviderAPI
from .views.security_group_acl import SecurityGroupAclProviderAPI
from .views.rule import RuleProviderAPI
from .views.instance import InstanceProviderAPI
from .views.stack import StackProviderAPI
from .views.stacks.sql import SqlStackProviderAPI
from .views.share import ShareProviderAPI
from .views.share_v2 import ShareV2ProviderAPI
from .views.volume import VolumeProviderAPI
from .views.stacks.app_engine import AppStackProviderAPI
from .views.volumeflavor import VolumeFlavorAPI
from .views.stack_v2 import StackV2ProviderAPI
from .views.customization import ComputeCustomizationAPI
from .views.gateway import GatewayProviderAPI
from .views.load_balancer import LoadBalancerProviderAPI
from .views.stacks_v2.sql import SqlStackV2ProviderAPI
from .views.logging_space import ComputeLoggingSpaceAPI
from .views.ssh_gateway_wrapper import SshGatewayProviderAPI


class LocalProviderPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = LocalProvider(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            RegionProviderAPI,
            SiteProviderAPI,
            ComputeZoneAPI,
            ComputeImageAPI,
            ComputeFlavorAPI,
            VpcProviderAPI,
            GatewayProviderAPI,
            LoadBalancerProviderAPI,
            SecurityGroupProviderAPI,
            SecurityGroupAclProviderAPI,
            RuleProviderAPI,
            InstanceProviderAPI,
            BastionProviderAPI,
            VolumeProviderAPI,
            VolumeFlavorAPI,
            StackV2ProviderAPI,
            StackProviderAPI,
            SqlStackProviderAPI,
            SqlStackV2ProviderAPI,
            AppStackProviderAPI,
            ShareProviderAPI,
            ShareV2ProviderAPI,
            ComputeCustomizationAPI,
            ComputeLoggingSpaceAPI,
            ComputeLoggingRoleAPI,
            ComputeLoggingRoleMappingAPI,
            ComputeMonitoringFolderAPI,
            ComputeMonitoringTeamAPI,
            ComputeMonitoringAlertAPI,
            ComputeMonitoringThresholdAPI,
            SshGatewayProviderAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(LocalProvider.objdef, LocalProvider)
