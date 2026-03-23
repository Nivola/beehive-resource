# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from logging import getLogger

from beehive_resource.plugins.openstack.entity.ops_volume_type import (
    OpenstackVolumeType,
)
from beehive_resource.task_v2 import AbstractResourceTask
from beehive.common.task_v2.manager import get_task_manager

logger = getLogger(__name__)


class VolumeTypeTask(AbstractResourceTask):
    """VolumeType task"""

    name = "volumetype_task"
    entity_class = OpenstackVolumeType


get_task_manager().register_task(VolumeTypeTask())
