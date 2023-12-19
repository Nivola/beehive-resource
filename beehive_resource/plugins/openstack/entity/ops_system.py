# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import truncate
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity import OpenstackResource


class OpenstackSystem(OpenstackResource):
    """Openstack system info."""

    objdef = "Openstack.System"
    objuri = "system"
    objname = "system"
    objdesc = "Openstack system"

    default_tags = ["openstack"]

    def __init__(self, *args, **kvargs):
        kvargs.pop("model", None)
        OpenstackResource.__init__(self, model=None, *args, **kvargs)

        self.container = None

    def get_services(self):
        """Get services.

        :return: Dictionary with services details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.get_services()
            self.logger.debug("Get openstack %s services: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s services: %s" % (self.container.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_endpoints(self):
        """Get endpoints.

        :return: Dictionary with endpoints details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.get_endpoints()
            self.logger.debug("Get openstack %s endpoints: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s endpoints: %s" % (self.container.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_services(self):
        """Get compute service.

        :return: Dictionary with services details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_services()

            self.logger.debug("Get openstack %s compute services: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s compute services: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_zones(self):
        """Get compute availability zones.

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_zones()
            self.logger.debug("Get openstack %s availability zones: %s" % (self.container.name, len(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s availability zones: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_hosts(self):
        """Get physical hosts.

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_hosts()
            self.logger.debug("Get openstack %s hosts: %s" % (self.container.name, len(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s hosts: %s" % (self.container.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_host_aggregates(self):
        """Get compute host aggregates.
        An aggregate assigns metadata to groups of compute nodes. Aggregates
        are only visible to the cloud provider.

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_host_aggregates()
            self.logger.debug("Get openstack %s aggregates: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s aggregates: %s" % (self.container.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_server_groups(self):
        """Get compute server groups.

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_server_groups()
            self.logger.debug("Get openstack %s server groups: %s" % (self.container.name, len(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s server groups: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_hypervisors(self):
        """Displays extra statistical information from the machine that hosts
        the hypervisor through the API for the hypervisor (XenAPI or KVM/libvirt).

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_hypervisors()
            self.logger.debug("Get openstack %s hypervisors: %s" % (self.container.name, len(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s hypervisors: %s" % (self.container.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_hypervisors_statistics(self):
        """Get compute hypervisors statistics.

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_hypervisors_statistics()
            self.logger.debug("Get openstack %s hypervisors statistics: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s hypervisors statistics: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_compute_agents(self):
        """Get compute agents.

        :return: Dictionary with details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.compute_agents()
            self.logger.debug("Get openstack %s agents: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s agents: %s" % (self.container.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_storage_services(self):
        """Get storage service.

        :return: Dictionary with services details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.storage_services()
            self.logger.debug("Get openstack %s storage services: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s storage services: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_network_agents(self):
        """Get network agents.

        :return: Dictionary with network agents details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.network_agents()
            self.logger.debug("Get openstack %s network agents: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s network agents: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_network_service_providers(self):
        """Get network service providers.

        :return: Dictionary with service providers details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.network_service_providers()
            self.logger.debug("Get openstack %s service providers: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s service providers: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_heat_services(self):
        """Get heat services.

        :return: Dictionary with services details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.system.orchestrator_services()
            self.logger.debug("Get openstack %s orchestrator services: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s network agents: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_usages(self, startdate=None, enddate=None, usage_type=None):
        """Get usage data

        :param enddate: End date range for usage record query. Use yyyy-MM-dd
                        as the date format, e.g. startDate=2009-06-03
        :param startdate: Start date range for usage record query. Use
                          yyyy-MM-dd as the date format, e.g. startDate=2009-06-01.
        :param usage_type: 1:'Running Vm Usage', 2:'Allocated Vm Usage',
                           3:'IP Address Usage', 4:'Network Usage (Bytes Sent)',
                           5:'Network Usage (Bytes Received)', 6:'Volume Usage',
                           7:'Template Usage', 8:'ISO Usage', 9:'Snapshot Usage',
                           10:'Security Group Usage', 11:'Load Balancer Usage',
                           12:'Port Forwarding Usage', 13:'Network Offering Usage',
                           14:'VPN users usage', 15:'VM Disk usage(I/O Read)',
                           16:'VM Disk usage(I/O Write)', 17:'VM Disk usage(Bytes Read)',
                           18:'VM Disk usage(Bytes Write)', 19:'VM Snapshot storage usage'

        :return:
        :rtype:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        self.controller.can("use", self.objtype, definition=self.objdef)

    def get_default_quotas(self):
        """Get default project quotas.

        :return: Dictionary with services details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.project.get_default_quotas()
            self.logger.debug("Get openstack %s default project quotas: %s" % (self.container.name, truncate(res)))
            return res
        except Exception as ex:
            err = "Can not get openstack %s default project quotas: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)
