# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class VolumeTask(AbstractResourceTask):
    """Volume task"""

    name = "volume_task"
    entity_class = VsphereVolume
