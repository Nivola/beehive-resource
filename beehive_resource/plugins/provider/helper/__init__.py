# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from abc import ABC
from logging import getLogger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController
    from beehive_resource.plugins.provider.entity.zone import ComputeZone

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class AbstractBaseProviderHelper(ABC):
    def __init__(self,
                 controller: 'ResourceController' = None,
                 compute_zone: 'ComputeZone' = None
    ):
        """Provider helper base class

        :param controller: resource controller
        :param compute_zone: resource compute_zone
        """
        self.logger = getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

        self.controller = controller
        self.compute_zone = compute_zone
