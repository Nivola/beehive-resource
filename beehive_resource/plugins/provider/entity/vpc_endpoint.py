# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.entity.aggregate import (
    ComputeProviderResource,
    get_task,
)
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource


class ComputeVpcEndpoint(ComputeProviderResource):
    """Compute vpcendpoint type"""

    objdef = "Provider.ComputeZone.ComputeVpcEndpoint"
    objuri = "%s/vpcendpoints/%s"
    objname = "vpcendpoint"
    objdesc = "Provider ComputeVpcEndpoint"
    task_path = "beehive_resource.plugins.provider.task_v2.vpcendpoint.VpcEndpointTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)


class VpcEndpoint(AvailabilityZoneChildResource):
    """Availability Zone VpcEndpoint"""

    objdef = "Provider.Region.Site.AvailabilityZone.VpcEndpoint"
    objuri = "%s/vpcendpoints/%s"
    objname = "vpcendpoint"
    objdesc = "Provider Availability Zone VpcEndpoint"
    task_path = "beehive_resource.plugins.provider.task_v2.vpcendpoint.VpcEndpointTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)
