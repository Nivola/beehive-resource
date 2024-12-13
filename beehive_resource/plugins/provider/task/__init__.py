# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.task.vsphere import ProviderVsphere
from beehive_resource.plugins.provider.task.openstack import ProviderOpenstack


#
# orchestrator helper
#
class ProviderOrchestrator(object):
    @staticmethod
    def get(orchestrator_type):
        """Return orchestrator helper

        :param orchestrator_type: type of orchestrator like vsphere or openstack
        :return: orchestrator helper
        """
        helpers = {"vsphere": ProviderVsphere, "openstack": ProviderOpenstack}
        res = helpers.get(orchestrator_type, None)
        if res is None:
            raise JobError("Helper for orchestrator %s does not exist" % orchestrator_type)

        return res


#
# remove task and facility method
#
def group_remove_task(ops, orchestrators):
    """ """
    tasks = []
    for item in orchestrators.values():
        orchestrator_id = str(item["id"])
        # tasks.append(remove_remote_resource.si(ops, orchestrator_id, item['type']))
        tasks.append(
            remove_remote_resource.signature(
                (ops, orchestrator_id, item["type"]),
                immutable=True,
                queue=task_manager.conf.TASK_DEFAULT_QUEUE,
            )
        )
    return tasks


from .util import *
from .flavor import *
from .image import *
from .instance import *
from .rule import *
from .security_group import *
from .share import *
from .site import *
from .network import *
from .stack import *
from .vpc import *
from .zone import *
from .volumeflavor import *
from .volume import *
from .template import *
