# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from abc import abstractmethod
from logging import getLogger


class AbstractProviderNetworkApplianceHelper(object):
    def __init__(self, controller=None, orchestrator=None, compute_zone=None):
        """Create a provider helper

        :param controller: resource controller
        :param orchestrator: resource orchestrator
        :param compute_zone: resource compute_zone
        """
        self.logger = getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)

        self.controller = controller
        self.cid = orchestrator.get('id', None)
        self.orchestrator = orchestrator
        self.container = self.controller.get_container(self.cid)
        self.compute_zone = compute_zone

    @abstractmethod
    def select_network_appliance(self, *args, **kvargs):
        raise NotImplementedError('Subclasses should implement this method')

    @abstractmethod
    def reserve_ip_address(self, *args, **kvargs):
        raise NotImplementedError('Subclasses should implement this method')

    @abstractmethod
    def create_load_balancer(self, *args, **kvargs):
        raise NotImplementedError('Subclasses should implement this method')
