# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import ujson as json
from celery.utils.log import get_task_logger

from beehive.common.apimanager import ApiManagerError
from beehive.common.data import operation
from beehive.common.task_v2 import BaseTask, task_step, run_sync_task
from beehive.common.task_v2.manager import task_manager
from beehive_resource.container import Resource
from beehive_resource.model import Resource as ModelResource, ResourceState
from beecell.simple import jsonDumps

logger = get_task_logger(__name__)


class ResourceTaskException(Exception):
    pass


class AbstractResourceTask(BaseTask):
    """AbstractResource task"""

    name = "resource_task"
    entity_class = Resource

    def __init__(self, *args, **kwargs):
        super(AbstractResourceTask, self).__init__(*args, **kwargs)

        self.container = None
        self.token = None
        self._data = None

    def set_data(self, key, value):
        """Set local data as opposed to set_shared_data"""
        if self._data is None:
            self._data = {}
        self._data[key] = value

    def get_data(self, key, default_value=None):
        """Get local data as opposed to get_shared_data"""
        if self._data is None:
            return None
        return self._data.get(key, default_value)

    def is_ext_id_valid(self, ext_id):
        """Validate ext_id"""
        if ext_id is not None and ext_id != "":
            return True
        return False

    def renew_container_token(self, *args, **kwargs):
        """Renew container token"""
        container_oid = kwargs.get("container_oid", None)
        projectid = kwargs.get("projectid", None)
        if container_oid:
            self.logger.debug("Renewing Token for container %s and project %s " % (container_oid, projectid))
            container_new = self.get_container(container_oid, projectid)
            if container_new is not None and container_new.conn.get_token() is not None:
                return container_new.conn.get_token().get("token")
        return None

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
            from beehive_resource.plugins.openstack.controller import OpenstackContainer
            from beedrones.openstack.client import OpenstackManager

            openstackContainer: OpenstackContainer = local_container
            openstackManager: OpenstackManager = openstackContainer.get_connection(projectid=projectid)
        else:
            local_container.get_connection()
        self.logger.debug("Get container %s of type %s" % (local_container, local_container.objdef))
        return local_container

    def get_simple_container(self, container_oid):
        """Get resource container instance.

        :param container_oid: container oid
        :param projectid: projectid. Used only for container openstack
        :return: container instance
        :raise ApiManagerError:
        """
        operation.cache = False
        local_container = self.controller.get_container(container_oid, connect=False, cache=False)
        self.logger.debug("Get container %s of type %s" % (local_container, local_container.objdef))
        return local_container

    def __get_resource(self, oid, run_customize=True):
        """Get resource instance.

        :param oid: resource oid
        :param run_customize: if True run customize [default=True]
        :return: resource instance
        :raises ApiManagerError: if query empty return error.
        """
        from beehive_resource.controller import ResourceController

        controller: ResourceController
        controller = self.controller
        return controller.get_resource(oid, run_customize=run_customize, cache=False)

    def get_simple_resource(self, oid):
        """Get resource instance without detail.

        :param oid: resource oid
        :return: resource instance
        :raises ApiManagerError: if query empty return error.
        """
        return self.__get_resource(oid, run_customize=False)

    def get_simple_resource_by_name_and_entity_class(self, name, entity_class):
        """Get resource by name and entity class

        :param name: resource name
        :param entity_class: entity class
        :return: resource instance
        :raises ApiManagerError:
        """
        from beehive_resource.controller import ResourceController

        controller: ResourceController
        controller = self.controller
        return controller.get_entity_v2(ModelResource, name, entity_class=entity_class, customize=None)

    def get_resource(self, oid):
        """Get resource instance with detail.

        :param oid: resource oid
        :return: resource instance
        :raises ApiManagerError: if query empty return error.
        """
        return self.__get_resource(oid, run_customize=True)

    def get_resource_by_extid(self, extid):
        """Get resource instance by external id.

        :param extid: resource extid
        :return: resource instance
        :raise ApiManagerError:
        """
        resource = self.controller.get_resource_by_extid(extid)
        return resource

    def get_link(self, oid):
        """Get link instance.

        :param oid: link oid
        :return: link instance
        :raise ApiManagerError:
        """
        link = self.controller.get_link(oid)
        return link

    def get_tag(self, oid):
        """Get tag instance.

        :param oid: tag oid
        :return: tag instance
        :raise ApiManagerError:
        """
        tag = self.controller.get_tag(oid)
        return tag

    def get_orm_linked_resources(self, resource, link_type=None, container_id=None, objdef=None):
        """Get linked resources from orm.

        :param resource: resource id
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :return: list of records
        :raise ApiManagerError:
        """
        manager = self.controller.manager
        entity = manager.get_entity(ModelResource, resource)
        resources = manager.get_linked_resources_internal(
            entity.id, link_type=link_type, container_id=container_id, objdef=objdef
        )
        return resources

    def get_orm_link_among_resources(self, start, end):
        """Get links of a resource from orm

        :param start: start resource id
        :param end: end resource id
        :return: list of ModelResourceLink
        :raise ApiManagerError:
        """
        manager = self.controller.manager
        link = manager.get_link_among_resources_internal(start, end)
        return link

    def update_orm_link(self, link_id, attributes):
        """Update links of a resource from orm

        :param link_id: link id
        :param attributes: attributes
        :return: list of ModelResourceLink
        :raise ApiManagerError:
        """
        manager = self.controller.manager
        res = manager.update_link(oid=link_id, attributes=attributes)
        return res

    def failure(self, params, error):
        # get resource
        try:
            resource = self.get_simple_resource(params.get("id"))

            # update resource state
            resource.update_state(ResourceState.ERROR, error=error)
        except ApiManagerError as ex:
            if ex.code == 404:
                self.logger.warning(ex)
            else:
                raise

    @staticmethod
    @task_step()
    def create_resource_pre_step(task, step_id, params, *args, **kvargs):
        """Create resource in beehive - pre step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.objid: objid of the resource. Ex. 110//2222//334//*
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.name: resource name
        :param params.desc: resource desc
        :param params.parent: resource parent
        :param params.ext_id: physical id
        :param params.active: active
        :param params.attribute: attribute
        :param params.tags: list of tags to add
        :return: id of the created resource, params
        """
        oid = params.get("id")
        uuid = params.get("uuid")
        tags = params.get("tags")

        resource: Resource = task.get_simple_resource(oid)
        resource.update_state(ResourceState.BUILDING)
        task.progress(
            step_id,
            msg="Update resource %s state to %s" % (oid, ResourceState.BUILDING),
        )

        # add tags
        if tags is not None and tags != "":
            for tag in tags.split(","):
                try:
                    resource.controller.add_tag(value=tag)
                    task.progress(step_id, msg="Add resource tag %s" % tag)
                except ApiManagerError as ex:
                    task.progress(step_id, msg="WARN: %s" % ex)
                    task.logger.warning(ex)
                try:
                    resource.add_tag(tag)
                    task.progress(step_id, msg="Assign resource tag %s" % tag)
                except ApiManagerError as ex:
                    task.progress(step_id, msg="WARN: %s" % ex)
                    task.logger.warning(ex)

            # add tags
            for tag in tags:
                resource.add_tag(tag)
                task.progress(step_id, msg="Add resource tag %s" % tag)

        return oid, params

    @staticmethod
    @task_step()
    def create_resource_post_step(task: "AbstractResourceTask", step_id, params, *args, **kvargs):
        """Create resource in beehive database - post step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.objid: objid of the resource. Ex. 110//2222//334//*
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.name: resource name
        :param params.desc: resource desc
        :param params.parent: resource parent
        :param params.ext_id: physical id
        :param params.active: active
        :param params.attribute: attribute
        :param params.tags: list of tags to add
        :return: id of the created resource, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        uuid = params.get("uuid")
        ext_id = params.get("ext_id", None)
        attribute = params.get("attrib", None)

        task.get_session(reopen=True)

        resource: Resource
        resource = task.get_simple_resource(oid)
        # resource_class = resource.__class__

        # run post create
        # resource_class.post_create(task.controller, **params)

        # update resource
        # task.logger.debug('+++++ TRYFIX create_resource_post_step - reopen=True - oid: %s' % oid)
        resource.update_internal(active=True, attribute=attribute, ext_id=ext_id, state=ResourceState.ACTIVE)
        task.progress(step_id, msg="Update resource %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def update_resource_pre_step(task, step_id, params, *args, **kvargs):
        """Update resource in beehive database - pre step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.name: resource name
        :param params.desc: resource desc
        :param params.parent: resource parent
        :param params.ext_id: physical id
        :param params.active: active
        :param params.attribute: attribute
        :return: id of the updated resource, params
        """
        oid = params.get("id")
        name = params.get("name", None)
        desc = params.get("desc", None)
        active = params.get("active", None)
        attrib = params.get("attribute", None)
        ext_id = params.get("ext_id", None)
        if attrib is not None:
            attrib = jsonDumps(attrib)

        resource = task.get_simple_resource(oid)
        data = {
            "attribute": attrib,
            "name": name,
            "desc": desc,
            "ext_id": ext_id,
            "state": ResourceState.UPDATING,
        }
        if active is not None:
            data["active"] = active
        resource.update_internal(**data)
        return oid, params

    @staticmethod
    @task_step()
    def update_resource_post_step(task, step_id, params, *args, **kvargs):
        """Update resource in beehive database - post step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.name: resource name
        :param params.desc: resource desc
        :param params.parent: resource parent
        :param params.ext_id: physical id
        :param params.active: active
        :param params.attribute: attribute
        :return: id of the updated resource, params
        """
        oid = params.get("id")
        uuid = params.get("uuid")
        attrib = params.get("attribute", None)
        if attrib is not None:
            attrib = jsonDumps(attrib)

        task.get_session(reopen=True)
        resource = task.get_simple_resource(oid)
        resource.update_internal(active=True, attribute=attrib, state=ResourceState.ACTIVE)
        task.progress(step_id, msg="Update resource %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def patch_resource_pre_step(task, step_id, params, *args, **kvargs):
        """Patch resource in beehive database - pre step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.name: resource name
        :param params.desc: resource desc
        :param params.parent: resource parent
        :param params.ext_id: physical id
        :param params.active: active
        :param params.attribute: attribute
        :return: id of the patchd resource, params
        """
        oid = params.get("id")

        resource = task.get_simple_resource(oid)
        resource.update_internal(active=False, state=ResourceState.UPDATING)
        return oid, params

    @staticmethod
    @task_step()
    def patch_resource_post_step(task, step_id, params, *args, **kvargs):
        """Patch resource in beehive database - post step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.name: resource name
        :param params.desc: resource desc
        :param params.parent: resource parent
        :param params.ext_id: physical id
        :param params.active: active
        :param params.attribute: attribute
        :return: id of the patched resource, params
        """
        oid = params.get("id")
        uuid = params.get("uuid")
        task.get_session(reopen=True)

        resource = task.get_simple_resource(oid)
        resource.update_internal(active=True, state=ResourceState.ACTIVE)
        task.progress(step_id, msg="Patch resource %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def expunge_resource_pre_step(task, step_id, params, *args, **kvargs):
        """Hard delete resource from beehive database - pre step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.ext_id: resource physical id
        :return: id of the removed resource, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        resource = task.get_simple_resource(oid)
        resource.update_internal(active=False, state=ResourceState.EXPUNGING)
        # container = task.get_container(cid)
        # container.update_resource_state(oid, state=ResourceState.EXPUNGING)
        task.progress(step_id, msg="Expunging resource %s" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def expunge_resource_post_step(task, step_id, params, *args, **kvargs):
        """Hard delete resource from beehive database - post step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.ext_id: resource physical id
        :return: id of the removed resource, params
        """
        oid = params.get("id")
        task.get_session(reopen=True)
        resource = task.get_simple_resource(oid)

        # delete resource
        resource.expunge_internal()
        task.progress(step_id, msg="Expunge resource %s" % resource.oid)
        return oid, params

    @staticmethod
    @task_step()
    def action_resource_pre_step(task, step_id, params, *args, **kvargs):
        """Run action on a resource - pre step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.ext_id: resource physical id
        :param params.action_name: action name
        :return: id of the removed resource, params
        """
        oid = params.get("id")
        uuid = params.get("uuid")
        action_name = params.get("action_name")

        resource: Resource
        resource = task.get_simple_resource(oid)

        # before updating
        resource.check_active()

        resource.update_internal(state=ResourceState.UPDATING)
        task.progress(step_id, msg="Run action %s on resource %s" % (action_name, oid))
        # task.logger.debug('+++++ TRYFIX - action_resource_pre_step - resource: %s - oid %s - active %s - state %s' % (type(resource), resource.oid, resource.active, resource.state))

        return oid, params

    @staticmethod
    @task_step()
    def action_resource_post_step(task, step_id, params, *args, **kvargs):
        """Run action on a resource - post step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.id: resource id
        :param params.uuid: resource uuid
        :param params.objid: resource objid
        :param params.ext_id: resource physical id
        :param params.action_name: action name
        :return: result, params
        """
        oid = params.get("id")
        task.get_session(reopen=True)
        resource: Resource = task.get_simple_resource(oid)
        resource.update_internal(state=ResourceState.ACTIVE)
        res = params.get("result", oid)
        return res, params

    @staticmethod
    @task_step()
    def delete_resource_list(task, step_id, params, *args, **kvargs):
        """Remove resource list from beehive database.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.ids: resource id list
        :return: id list of the removed resource, params
        """
        oids = params.get("ids")

        for oid in oids:
            resource = task.get_resourece(oid)
            resource.update_state(ResourceState.EXPUNGING)

            # delete resource
            resource.expunge()
            task.progress(step_id, msg="Delete resource %s" % resource.oid)
        return oids, params

    @staticmethod
    @task_step()
    def delete_resourcelink_list(task, step_id, params, *args, **kvargs):
        """Remove resource link list from beehive database.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param params.cid: container id
        :param params.ids: resource link id list
        :return: id list of the removed resource link, params
        """
        oids = params.get("ids")

        for oid in oids:
            link = task.get_link(oid)

            # delete resource
            link.expunge()
            task.progress(step_id, msg="Delete resource link %s" % oid)
        return oids, params

    @staticmethod
    @task_step()
    def remove_child_step(task, step_id, params, resource_id, *args, **kvargs):
        """Remove compute resource childs.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param resource_id: id of the resource to delete
        :return: True, params
        """
        resource = task.get_resource(resource_id)

        # delete child
        prepared_task, code = resource.expunge(sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Remove child %s" % resource_id)

        return True, params


class ResourceAddTask(AbstractResourceTask):
    """ResourceAdd task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param name: resource name
    :param desc: resource desc
    :param parent: resource parent
    :param ext_id: physical id
    :param active: active
    :param attribute: attribute
    :param tags: list of tags to add
    """

    abstract = False
    name = "resource_add_task"
    entity_class = Resource


# class ResourceCloneTask(AbstractResourceTask):
#     """ResourceClone task
#
#     :param cid: container id
#     :param id: resource id
#     :param uuid: return resource id, params
#     :param objid: resource objid
#     :param name: resource name
#     :param desc: resource desc
#     :param parent: resource parent
#     :param ext_id: physical id
#     :param active: active
#     :param attribute: attribute
#     :param tags: list of tags to add
#     """
#     abstract = False
#     name = 'resource_clone_task'
#     entity_class = Resource


class ResourceImportTask(AbstractResourceTask):
    """ResourceImport task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param ext_id: physical id
    """

    abstract = False
    name = "resource_import_task"
    entity_class = Resource


class ResourceUpdateTask(AbstractResourceTask):
    """ResourceUpdate task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param ext_id: physical id
    """

    abstract = False
    name = "resource_update_task"
    entity_class = Resource


class ResourcePatchTask(AbstractResourceTask):
    """ResourcePatch task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param ext_id: physical id
    """

    abstract = False
    name = "resource_patch_task"
    entity_class = Resource


class ResourceDeleteTask(AbstractResourceTask):
    """ResourceDelete task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    """

    abstract = False
    name = "resource_delete_task"
    entity_class = Resource


class ResourceExpungeTask(AbstractResourceTask):
    """ResourceExpunge task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    """

    abstract = False
    name = "resource_expunge_task"
    entity_class = Resource


class ResourceActionTask(AbstractResourceTask):
    """ResourceAction task"""

    abstract = False
    name = "resource_action_task"
    entity_class = Resource


task_manager.tasks.register(ResourceAddTask())
# task_manager.tasks.register(ResourceCloneTask())
task_manager.tasks.register(ResourceImportTask())
task_manager.tasks.register(ResourceUpdateTask())
task_manager.tasks.register(ResourcePatchTask())
task_manager.tasks.register(ResourceDeleteTask())
task_manager.tasks.register(ResourceExpungeTask())
task_manager.tasks.register(ResourceActionTask())
