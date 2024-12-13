# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class DomainTask(AbstractResourceTask):
    """Domain task"""

    name = "domain_task"
    entity_class = OpenstackDomain


task_manager.tasks.register(DomainTask())
