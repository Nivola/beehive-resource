# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from .controller import VsphereContainer
from beehive_resource.plugins.vsphere.views.vs_datacenter import VsphereDatacenterAPI
from beehive_resource.plugins.vsphere.views.vs_cluster import VsphereClusterAPI
from beehive_resource.plugins.vsphere.views.vs_host import VsphereHostAPI
from beehive_resource.plugins.vsphere.views.vs_resource_pool import VsphereResourcePoolAPI
from beehive_resource.plugins.vsphere.views.vs_datastore import VsphereDatastoreAPI
from beehive_resource.plugins.vsphere.views.vs_dvpg import VsphereDvpgAPI
from beehive_resource.plugins.vsphere.views.vs_server import VsphereServerAPI
from beehive_resource.plugins.vsphere.views.vs_dvs import VsphereDvsAPI
from beehive_resource.plugins.vsphere.views.nsx_manager import VsphereNsxManagerAPI
from beehive_resource.plugins.vsphere.views.nsx_dlr import VsphereNsxDlrAPI
from beehive_resource.plugins.vsphere.views.nsx_edge import VsphereNsxEdgeAPI
from beehive_resource.plugins.vsphere.views.nsx_logical_switch import VsphereNsxLogicalSwitchAPI
from beehive_resource.plugins.vsphere.views.nsx_security_group import VsphereNsxSecurityGroupAPI
from beehive_resource.plugins.vsphere.views.nsx_ipset import VsphereNsxIpSetAPI
from beehive_resource.plugins.vsphere.views.nsx_dfw import VsphereNsxDfwAPI
from beehive_resource.plugins.vsphere.views.vs_pg import VspherePgAPI
from beehive_resource.plugins.vsphere.views.vs_folder import VsphereFolderAPI
# from beehive_resource.plugins.vsphere.views.vs_stack import VsphereStackAPI
from beehive_resource.plugins.vsphere.views.vs_flavor import VsphereFlavorAPI
from beehive_resource.plugins.vsphere.views.vs_volumetype import VsphereVolumeTypeAPI
from beehive_resource.plugins.vsphere.views.vs_volume import VsphereVolumeAPI


class VspherePlugin(object):
    def __init__(self, module):
        self.module = module
    
    def init(self):
        service = VsphereContainer(self.module.get_controller())
        service.init_object()
    
    def register(self):
        apis = [
            VsphereDatacenterAPI,
            VsphereClusterAPI,
            VsphereDatastoreAPI,
            VsphereHostAPI,
            VsphereResourcePoolAPI,
            VsphereDvpgAPI,
            VspherePgAPI,
            VsphereDvsAPI,
            VsphereFolderAPI,
            VsphereServerAPI,
            # VsphereStackAPI,
            VsphereFlavorAPI,
            VsphereVolumeTypeAPI,
            VsphereVolumeAPI,
            VsphereNsxDfwAPI,
            VsphereNsxManagerAPI,
            VsphereNsxDlrAPI,
            VsphereNsxEdgeAPI,
            VsphereNsxIpSetAPI,
            VsphereNsxLogicalSwitchAPI,
            VsphereNsxSecurityGroupAPI
        ]
        self.module.set_apis(apis)
        
        self.module.add_container(VsphereContainer.objdef, VsphereContainer)
