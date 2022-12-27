# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from ipaddress import ip_network
from beecell.types.type_string import truncate
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import SiteChildResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from logging import getLogger
from typing import Any, Dict

logger = getLogger(__name__)

class SshGatewayWrapper(ComputeProviderResource):
    """SshGatewayWrapper
    """
    objdef = 'Provider.ComputeZone.SshGatewayWrapper'
    objuri = '%s/sshgw/%s'
    objname = 'vpc'
    objdesc = 'Provider Ssh Gateway'
    task_path = 'beehive_resource.plugins.provider.task_v2.sshgw.TODOTask.'

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)
