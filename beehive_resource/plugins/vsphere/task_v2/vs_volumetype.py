# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class VolumeTypeTask(AbstractResourceTask):
    """VolumeType task"""

    name = "volumetype_task"
    entity_class = VsphereVolumeType
