# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from celery.utils.log import get_task_logger
from beecell.simple import truncate
from beehive.common.data import operation
from beehive.common.task_v2 import BaseTask, task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.container import ResourceContainer
from beehive_resource.model import ResourceState

logger = get_task_logger(__name__)


class ResourceContainerTask(BaseTask):
    """ResourceContainer task"""

    name = "resource_container_task"
    entity_class = ResourceContainer

    def __init__(self, *args, **kwargs):
        super(ResourceContainerTask, self).__init__(*args, **kwargs)

        self.steps = [ResourceContainerTask.synchronize_container_step]

    def get_container(self, container_oid, projectid=None):
        """Get resource container instance.

        :param container_oid: container oid
        :param projectid: projectid. Used only for container openstack
        :return: container instance
        :raise ApiManagerError:
        """
        operation.cache = False
        local_container = self.controller.get_container(container_oid, connect=False, cache=False)
        if local_container.objdef == "Openstack":
            # local_container.conn = self.__get_openstack_connection(local_container, projectid=projectid)
            local_container.get_connection(projectid=projectid)
        else:
            local_container.get_connection()
        self.logger.debug("Get container %s of type %s" % (local_container, local_container.objdef))
        return local_container

    @staticmethod
    @task_step()
    def synchronize_container_step(task, step_id, params, *args, **kvargs):
        """Synchronize remote platform entities

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.types: List of resource objdef. If empty use all the available objdef.
        :param params.new: if True discover new entity
        :param params.died: if True remove orphaned resources
        :param params.changed: if True update changed resources
        :return: True, params
        """
        cid = params.get("cid")
        container = task.get_container(cid)

        # get resource classes
        resource_types = params.get("types", None)
        new = params.get("new", True)
        died = params.get("died", True)
        changed = params.get("changed", True)

        resource_objdefs = []
        if resource_types is None:
            for resource_class in container.child_classes:
                resource_objdefs.append(resource_class.objdef)
        else:
            types = resource_types.split(",")
            for t in types:
                resource_objdefs.append(t)

        for objdef in resource_objdefs:
            if new is True:
                task.discover_new_entities(step_id, container, params, objdef)
            if died is True or changed is True:
                task.discover_died_entities(step_id, container, params, objdef)

        return True, params


task_manager.tasks.register(ResourceContainerTask())
