# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Provider
from beehive_resource.plugins.provider.entity.region import Region
from beehive_resource.plugins.provider.entity.zone import ComputeZone


class LocalProvider(Provider):
    """Local provider

    :param controller: resource controller.

    """

    objdef = "Provider"
    objuri = "provider"
    objdesc = "Local Provider"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Provider.__init__(self, *args, **kvargs)
        self.child_classes = [
            Region,
            ComputeZone,
        ]

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return True

    def get_availability_zone_from_physical_resource(self, resource_id):
        """Get availability zone from physical resource

        :param resource_id: physical resource id
        :return:
        """

        get_linked = self.controller.get_indirected_linked_resources_internal

        # check resource has a parent provider zone resource
        zone_ress = get_linked([resource_id], link_type="relation").get(resource_id, [])

        if len(zone_ress) > 0:
            avz = zone_ress[0]
            self.logger.debug("Get availability zone from physical resource %s: %s" % (resource_id, avz))
            return avz

        raise ApiManagerError("No availability zone found for physical resource %s" % resource_id)

    def get_zone_resource_from_physical_resource(self, resource_id):
        """Get zone resource from physical resource

        :param resource_id: physical resource id
        :return:
        """
        get_linked = self.controller.get_indirected_linked_resources_internal

        # check resource has a parent provider zone resource
        zone_ress = get_linked([resource_id], link_type="relation").get(resource_id, [])

        # check provider zone has a parent provider aggregated resource
        if len(zone_ress) > 0:
            zone_res = zone_ress[0]
            self.logger.debug("Get zone resource from physical resource %s: %s" % (resource_id, zone_res))
            return zone_res

        raise ApiManagerError("No zone resource found for physical resource %s" % resource_id)

    def get_aggregated_resource_from_physical_resource(self, resource_id, parent_id=None):
        """
        Get aggregated resource from physical resource

        :param resource_id: physical resource id
        :param parent_id: aggregated resource parent. Set when physical resource is linked to more then one
            aggregated resource. [optional]
        :return:
        """
        aggr_res = self.controller.get_aggregated_resource_from_physical_resource(resource_id, parent_id=parent_id)
        if aggr_res is None:
            raise ApiManagerError(f"No aggregated resource found for physical resource {resource_id}")
        msg = f"Get aggregated resource from physical resource {resource_id}: {aggr_res}"
        if parent_id is not None:
            msg += f" for parent {parent_id}"
        self.logger.debug(msg)
        return aggr_res
