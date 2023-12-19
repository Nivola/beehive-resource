# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

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

    def discover_new_entities(self, step_id, container, params, objdef):
        """Register new entity in remote platform.

        :param str step_id: step id
        :param container: container object
        :param objdef: resource objdef
        :param dict params: step params
        :param params.cid: container id
        :param params.new: if True discover new entity
        :param params.died: if True remove orphaned resources
        :param params.changed: if True update changed resources
        :param params.ext_id: physical entity id [optional]
        :return: list of tuple (resource uuid, resource class)
        """
        self.progress(step_id, msg="Get resource objdef %s" % objdef)

        ext_id = params.get("ext_id", None)

        items = container.discover_new_entities(objdef, ext_id=ext_id)
        self.progress(step_id, msg="Discover new entities: %s" % len(items))

        res = []

        for item in items:
            resclass = item[0]
            ext_id = item[1]
            name = item[4]

            resource = resclass.synchronize(container, item)
            self.progress(step_id, msg="Call resource %s synchronize method" % resclass.objdef)

            # add resource reference in db
            model = container.add_resource(**resource)
            container.update_resource_state(model.id, ResourceState.ACTIVE)
            container.activate_resource(model.id)
            res.append((model.id, resclass.objdef))
            self.progress(step_id, msg="Add new resource: (%s, %s)" % (name, ext_id))
        return res

    def discover_died_entities(self, step_id, container, params, objdef):
        """Discover died/changed entities

        :param str step_id: step id
        :param container: container object
        :param objdef: resource objdef
        :param dict params: step params
        :param params.cid: container id
        :param params.new: if True discover new entity
        :param params.died: if True remove orphaned resources
        :param params.changed: if True update changed resources
        :return: list of tuple (resource uuid, resource class)
        """
        self.progress(step_id, msg="Get resource objdef %s" % objdef)
        died = params.get("died", True)
        changed = params.get("changed", True)

        res = {"died": [], "changed": []}

        # get resources
        from typing import List
        from beehive_resource.container import Resource

        resources: List[Resource] = container.discover_died_entities(objdef)

        # remove died resources
        if died is True:
            self.progress(step_id, msg="Get died entities: %s" % truncate(resources["died"]))
            for r in resources["died"]:
                # remove from beehive
                resource: Resource = r
                resource.expunge_internal()

                obj = {"id": resource.oid, "name": resource.name, "extid": resource.ext_id}
                res["died"].append(obj)
                logger.debug("Resource %s will be deleted." % obj)

                self.progress(step_id, msg="Delete resource %s" % obj)

        # update changed resources
        if changed is True:
            self.progress(step_id, msg="Get changed entities: %s" % truncate(resources["changed"]))
            for r in resources["changed"]:
                resource: Resource = r
                resource.update_state(ResourceState.UPDATING)
                params = {"name": resource.name, "desc": resource.desc}
                resource.update_internal(**params)

                obj = {"id": resource.oid, "name": resource.name, "extid": resource.ext_id}
                res["changed"].append(obj)
                resource.update_state(ResourceState.ACTIVE)
                logger.debug("Resource %s will be changed." % obj)

                self.progress(step_id, msg="Update resource %s" % obj)

        return res

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
        :param params.ext_id: physical entity id [optional]
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
            # todo: this is wrong
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
