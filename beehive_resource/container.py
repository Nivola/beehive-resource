# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from datetime import datetime

import ujson as json
from beecell.db import QueryError, TransactionError
from beecell.simple import (
    import_class,
    id_gen,
    truncate,
    dict_get,
    dict_set,
    dict_unset,
)
from beecell.types.type_string import str2bool
from beehive.common.task_v2 import prepare_or_run_task, run_async
from beehive.common.task_v2.canvas import signature
from beehive.common.apimanager import ApiObject, ApiManagerError
from beehive_resource.model import (
    ContainerState,
    ResourceDbManager,
    ResourceState,
    ResourceWithLink,
)
from beehive.common.data import trace, operation
from beehive.common.apiclient import BeehiveApiClientError
from beehive_resource.model import Resource as ModelResource
from beecell.simple import jsonDumps

from logging import getLogger

from beehive_resource.util import expunge_resource

logger = getLogger(__name__)

# container connection
try:
    import gevent.local

    active_container = gevent.local.local()
except:
    import threading

    active_container = threading.local()

active_container.conn = None


def get_task(task_name):
    return "%s.tasks.%s" % (__name__.replace(".container", ""), task_name)


class ResourceContainer(ApiObject):
    """Resource Container"""

    module = "ResourceModule"
    objtype = "container"
    objdef = "Container"
    objuri = "containers"
    objdesc = "Abstract resource container"
    category = "abstract"
    version = "v1.0"

    expunge_task = None
    synchronize_task = "beehive_resource.task_v2.container.resource_container_task"

    def __init__(self, *args, **kvargs):
        ApiObject.__init__(self, *args, **kvargs)

        self.update_object = self.manager.update_container
        self.expunge_object = self.manager.purge  # self.manager.expunge_container

        self.connection = None
        self.conn_params = None
        self.shared_conn = None

        self.container_ping = None

        # roles
        self._admin_role_prefix = "container-admin"
        self._viewer_role_prefix = "container-viewer"

        # discover
        self._discover_service = "discover_%s_%s" % (self.objdef, self.oid)

        self.child_classes = []

        self.set_connection()

    @property
    def conn(self):
        return self.shared_conn

    @conn.setter
    def conn(self, conn):
        self.shared_conn = conn

    @property
    def manager(self):
        return self.controller.manager

    @property
    def job_manager(self):
        return self.controller.job_manager

    def get_base_state(self):
        """Get container state.

        :return: State can be:

            * PENDING = 0
            * BUILDING =1
            * ACTIVE = 2
            * UPDATING = 3
            * ERROR = 4
            * DELETING = 5
            * DELETED = 6
            * EXPUNGING = 7
            * EXPUNGED = 8
            * SYNCHRONIZE = 9
            * DISABLED = 10
        """
        state = ContainerState.state[self.model.state]
        if self.container_ping is False:
            state = ContainerState.state[10]
        return state

    def set_connection(self):
        """ """
        if self.model is not None:
            self.connection = self.model.connection
            self.conn_params = json.loads(self.connection)

    def get_connection(self, *args, **kvargs):
        """ """
        self.logger.info("Get connection for container %s" % self.name)

    def ping(self):
        """Ping orchestrator.

        Extend for every specific container implmentation.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return True

    def get_resource_classes(self):
        child_classes = [item.objdef for item in self.child_classes]
        for item in self.child_classes:
            child_classes.extend(item(self.controller).get_resource_classes())
        return child_classes

    #
    # info
    #
    def small_info(self):
        """Get resource small infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = ApiObject.small_info(self)
        res["category"] = self.category
        res["state"] = self.get_base_state()
        return res

    def info(self):
        """Get system capabilities.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # ping = self.ping()
        ping = None

        res = ApiObject.info(self)
        count = self.manager.count_resource(container=self.model)
        res.update(
            {
                "category": self.category,
                "state": self.get_base_state(),
                "conn": json.loads(self.model.connection),
                "resources": count,
                "ping": ping,
            }
        )
        return res

    def detail(self):
        """Get system details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = self.info()
        return info

    def query_job(self, job_id, *args, **argv):
        """Query remote container async job."""
        raise NotImplementedError()

    def init_object(self):
        """Register object types, objects and permissions related to module.
        Call this function when initialize system first time.

        :param args:
        """
        ApiObject.init_object(self)

        # call only once during db initialization
        try:
            # create container types
            class_name = self.__class__.__module__ + "." + self.__class__.__name__
            self.manager.add_container_type(self.category, self.objdef, class_name)
        except TransactionError as ex:
            self.logger.warning(ex)

        # register custom resource
        CustomResource(self.controller, self).init_object()

    def authorization(self, objid=None, *args, **kvargs):
        """Get container authorizations

        :param objid: resource objid
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: [(perm, roles), ...]
        :raises ApiManagerError: if query empty return error.
        """
        try:
            # resource permissions
            if objid == None:
                objid = self.objid
            perms, total = self.api_client.get_permissions(
                "container,resource", self.objdef, objid, cascade=True, **kvargs
            )

            return perms, total
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)

    def update_state(self, state):
        """Update container state

        :param state: new state
        :raises ApiManagerError: if query empty return error.
        """
        try:
            # change resource state
            self.manager.update_container_state(self.oid, state)
            self.logger.info("Set container %s state to: %s" % (self.oid, state))
        except QueryError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    #
    # expunge
    #
    @trace(op="delete")
    def expunge(self, **params):
        """Expunge container using the synchronous function expunge_internal.

        :param force: if True force removal [optional]
        :return: {'uuid': ..}
        :raises ApiManagerError: if query empty return error.
        """
        # verify permissions
        self.verify_permisssions("delete")

        # change resource state
        self.update_state(ContainerState.EXPUNGING)

        force = params.get("force", False)

        # verify resource has no childs
        params["child_num"] = self.manager.count_resource(container=self.model)

        # run an optional pre delete function
        params = self.pre_delete(**params)
        self.logger.debug("params after pre expunge: %s" % params)

        if force is False and params["child_num"] > 0:
            raise ApiManagerError(
                "Container %s has %s childs. It can not be expunged" % (self.oid, params["child_num"])
            )

        self.expunge_internal(force)
        return {"uuid": self.uuid}, 200

    @trace(op="delete")
    def expunge_internal(self, force=False):
        """Hard delete resource"""
        try:
            # remove childs
            if force is True:
                childs, tot = self.get_resources(size=-1, with_perm_tag=False)
                childs2, tot = self.get_resources(size=-1, with_perm_tag=False, show_expired=True)
                childs.extend(childs2)

                for child in childs:
                    child.expunge_internal()

            # remove container
            self.manager.expunge_container(oid=self.oid)

            # remove object and permissions
            self.deregister_object(self.objid.split("//"))
            self.logger.debug("Remove container %s permissions" % self.oid)

            self.logger.info("Expunge container %s: %s" % (self.objdef, self.oid))
            return None
        except TransactionError as ex:
            self.update_state(ResourceState.ERROR)
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    #
    # authorization roles
    #
    def set_role_admin_permissions(self, role, args):
        """ """
        # set  main permissions
        self.set_admin_permissions(role, args)

        # set  child resources permissions
        for child_class in self.child_classes:
            child_class(self.controller, self).set_role_admin_permissions(role, args)

    def set_role_viewer_permissions(self, role, args):
        """ """
        # set  main permissions
        self.set_viewer_permissions(role, args)

        # set  child resources permissions
        for child_class in self.child_classes:
            child_class(self.controller, self).set_role_viewer_permissions(role, args)

    def get_admin_role(self):
        """Get admin role with all the required permissions.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # get role
        try:
            role_name = "%s_%s" % (self.name, self._admin_role_prefix)
            res = self.api_client.get_role(role_name)
            return res
        except:
            self.logger.warning("Role %s was not found" % (role_name), exc_info=False)
            return []

    def add_admin_role(self):
        """Add admin role with all the required permissions.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # add role
        role_name = "%s_%s" % (self.name, self._admin_role_prefix)
        self.api_client.add_role(role_name, self.desc + " role")

        # set admin permissions to role
        self.set_role_admin_permissions(role_name, self.objid.split("//"))

    def remove_admin_role(self):
        """Remove admin role with all the required permissions.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # remove role
        name = "%s_%s" % (self.name, self._admin_role_prefix)
        try:
            self.api_client.remove_role(name)
        except:
            self.logger.warning("Role %s does not exist" % name)

    def get_viewer_role(self):
        """Get viewer role with all the required permissions.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        try:
            # get role
            role_name = "%s_%s" % (self.name, self._viewer_role_prefix)
            res = self.api_client.get_role(role_name)
            return res
        except:
            self.logger.warning("Role %s was not found" % (role_name), exc_info=False)
            return []

    def add_viewer_role(self):
        """Add viewer role with all the required permissions.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # add role
        role_name = "%s_%s" % (self.name, self._viewer_role_prefix)
        self.api_client.add_role(role_name, self.desc + " role")

        # set viewer permissions to role
        self.set_role_viewer_permissions(role_name, self.objid.split("//"))

    def remove_viewer_role(self):
        """Remove viewer role with all the required permissions.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # remove role
        name = "%s_%s" % (self.name, self._viewer_role_prefix)
        try:
            self.api_client.remove_role(name)
        except:
            self.logger.warning("Role %s does not exist" % name)

    def get_roles(self):
        """Get all roles.

        :return: True if role added correctly
        :rtype: bool
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        roles = []
        roles.append(self.get_admin_role())
        roles.append(self.get_viewer_role())
        return roles

    #
    # resources
    #
    def count_all_resources(self):
        """Get all resources count"""
        return self.manager.count_resource(container=self.model)

    def update_resource_state(self, resource, state):
        """Update resource state

        :param resource: resource id
        :param state: new state
        :raises ApiManagerError: if query empty return error.
        """
        # clean cache
        self.get_simple_resource(resource).clean_cache()

        try:
            # change resource state
            self.manager.update_resource_state(resource, state)
            self.logger.info("Set resource %s state to: %s" % (resource, state))
        except QueryError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    def activate_resource(self, resource):
        """Set resource active to True

        :param resource: resource id
        :raises ApiManagerError: if query empty return error.
        """
        try:
            # change resource state
            self.manager.update_resource(oid=resource, active=True)
            self.logger.info("Activate resource %s" % resource)
        except QueryError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    def __add_resource(
        self,
        objid=None,
        name=None,
        resource_class=None,
        ext_id=None,
        active=True,
        desc="",
        attrib={},
        parent=None,
        *args,
        **kwargs,
    ):
        """Add resource. This function is used by add_resource.

        :param objid: resource object id.
        :param name: resource name.
        :param resource_class: resource class.
        :param container: container id
        :param ext_id: physical resource id [default='']
        :param active: Status. If True is active [default=True]
        :param desc: description
        :param attrib: attribute
        :param tags: tags to assign [default=[]]
        :param parent: parent id or uuid
        :return: resource uuid
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # create resource reference
        try:
            rtype = self.manager.get_resource_types(value=resource_class.objdef)[0]
        except QueryError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=404)

        try:
            if isinstance(attrib, dict) or isinstance(attrib, list):
                attrib = json.dumps(attrib)

            model = self.manager.add_resource(
                objid=objid,
                name=name,
                rtype=rtype,
                container=self.oid,
                ext_id=ext_id,
                active=active,
                desc=desc,
                attribute=attrib,
                parent_id=parent,
            )
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        # create object and permission
        resource_class(self.controller, oid=model.id).register_object(model.objid.split("//"), desc=desc)

        self.logger.info("Add resource %s with uuid %s" % (name, model.uuid))
        return model

    def add_resource2(self, resource_class, params, *args, **kwargs):
        """Add resource. This function is used by helper and factory.

        :param resource_class: resource class.
        :param params.objid: resource object id.
        :param params.name: resource name.
        :param params.container: container id
        :param params.ext_id: physical resource id [default='']
        :param params.active: Status. If True is active [default=True]
        :param params.desc: description
        :param params.attribute: attribute
        :param params.tags: tags to assign [default=[]]
        :param params.parent: parent id or uuid
        :return: resource uuid
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        model = self.__add_resource(
            objid=params["objid"],
            name=params["name"],
            resource_class=resource_class,
            ext_id=params["ext_id"],
            active=params["active"],
            desc=params["desc"],
            attrib=params["attribute"],
            parent=params.get("parent", None),
        )
        params.update({"id": model.id, "uuid": model.uuid})
        resource = resource_class(
            self.controller,
            oid=model.id,
            objid=params["objid"],
            name=params["name"],
            desc=params["desc"],
            active=params["active"],
            model=model,
        )
        return resource

    def add_resource(
        self,
        objid=None,
        name=None,
        resource_class=None,
        ext_id=None,
        active=True,
        desc="",
        attrib={},
        parent=None,
        tags=[],
    ):
        """Add resource. This function is used by resource_factory.

        :param objid: resource object id.
        :param name: resource name.
        :param resource_class: resource class.
        :param container: container id
        :param ext_id: physical resource id [default='']
        :param active: Status. If True is active [default=True]
        :param desc: description
        :param attrib: attribute
        :param tags: tags to assign [default=[]]
        :param parent: parent id or uuid
        :return: resource uuid
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # create resource reference
        try:
            rtype = self.manager.get_resource_types(value=resource_class.objdef)[0]
        except QueryError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=404)

        try:
            if isinstance(attrib, dict) or isinstance(attrib, list):
                attrib = jsonDumps(attrib)

            model = self.manager.add_resource(
                objid=objid,
                name=name,
                rtype=rtype,
                container=self.oid,
                ext_id=ext_id,
                active=active,
                desc=desc,
                attribute=attrib,
                parent_id=parent,
            )

            # for tag in tags:
            #     tag, total = self.manager.get_tags(value=tag)
            #     self.manager.add_resource_tag(model, tag[0])
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        # create object and permission
        resource_class(self.controller, oid=model.id).register_object(model.objid.split("//"), desc=desc)

        self.logger.info("Add resource %s with uuid %s" % (name, model.uuid))
        return model

    def update_resource(self, resource, **params):
        """Update resource

        :param resource: resource id
        :param params: update params
        :raises ApiManagerError: if query empty return error.
        """
        # clean cache
        self.get_simple_resource(resource).clean_cache()

        try:
            # change resource state
            self.manager.update_resource(oid=resource, **params)
            self.logger.info("Update resource %s with params %s" % (resource, params))
        except QueryError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    def __pre_create_resource(
        self,
        resource_class,
        name=None,
        desc="",
        ext_id=None,
        active=False,
        attribute={},
        parent=None,
        tags="",
        has_quotas=True,
        **params,
    ):
        """pre create resource.

        :param resource_class: resource class
        :param name: resource name
        :param desc: resource description
        :param ext_id: resource physical id
        :param active: resource active
        :param attribute: resource attribute
        :param parent: resource parent
        :param tags: resource tags
        :param has_quotas: enable or disable quota and metric
        :param params: resource custom params
        :return:
        """
        if parent is not None:
            params["objid"] = "%s//%s" % (parent.objid, id_gen())
            params["parent"] = parent.oid
        else:
            params["objid"] = "%s//%s" % (self.objid, id_gen())
            params["parent"] = None

        # get class
        if isinstance(resource_class, str):
            resource_class = import_class(resource_class)

        if tags is None:
            tags = ""
        other_params = {
            "alias": "%s.create" % resource_class.__name__,
            "cid": self.oid,
            "name": name,
            "desc": desc,
            "ext_id": ext_id,
            "active": active,
            "attribute": attribute,
            "tags": tags,
        }
        params.update(other_params)

        # pre create function
        self.logger.debug("Initial params: %s" % params)
        params = resource_class.pre_create(self.controller, self, **params)
        # sync = params.pop('sync', False)
        params["attribute"]["has_quotas"] = has_quotas
        self.logger.debug("Pre create after params: %s" % params)

        # verify permissions
        parent_objid = "//".join(params["objid"].split("//")[:-1])
        self.logger.debug("Parent objid: %s" % parent_objid)
        if operation.authorize is True:
            self.controller.check_authorization(resource_class.objtype, resource_class.objdef, parent_objid, "insert")

        # create resource in PENDING state
        resource = self.add_resource2(resource_class, params)

        self.logger.debug("create resource: %s" % resource)
        return resource, params

    def create_resource(
        self,
        resource_class,
        name=None,
        desc="",
        ext_id=None,
        active=False,
        attribute={},
        parent=None,
        tags="",
        has_quotas=True,
        sync=False,
        **params,
    ):
        """Factory used to create new resource.

        :param resource_class: class of resource to create or string representation
        :param name: resource name
        :param desc: resource desc
        :param ext_id: ext_id [default=None]
        :param active: active [default=True],
        :param attribute: attribute [default={}],
        :param parent: parent id [default=None]
        :param tags: comma separated resource tags to assign [default='']
        :param has_quotas: if True resource has quotas and metric associated [default=True]
        :param sync: if True run sync task, if False run async task
        :param params: custom params required by task or function
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
                 for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource creation")
        else:
            self.logger.debug("run async resource creation")

        # create basic resource
        resource, params = self.__pre_create_resource(
            resource_class,
            name,
            desc,
            ext_id,
            active,
            attribute,
            parent,
            tags,
            has_quotas,
            **params,
        )

        # run resource method that launch task or exec operation sync
        res = resource.do_create(params, sync=sync)

        # run final create is method is sync
        if sync is True:
            # resource.finalize_create(**params)
            res = {"uuid": resource.uuid}, 201
        else:
            res[0]["uuid"] = resource.uuid

        self.logger.debug("end resource creation with result: %s" % res[0])
        return res

    @trace(op="insert")
    def resource_factory(
        self,
        resource_class,
        name=None,
        desc="",
        ext_id=None,
        active=False,
        attribute={},
        parent=None,
        tags="",
        has_quotas=True,
        **params,
    ):
        """Factory used to create new resource.

        :param resource_class: class of resource to create or string representation
        :param name: resource name
        :param desc: resource desc
        :param ext_id: ext_id [default=None]
        :param active: active [default=True],
        :param attribute: attribute [default={}],
        :param parent: parent id [default=None]
        :param tags: comma separated resource tags to assign [default='']
        :param has_quotas: if True resource has quotas and metric associated [default=True]
        :param params: custom params required by task or function
        :param params.sync: if True run sync task, if False run async task
        :param params.set_as_sync: if True it is used to break task behaviour
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if parent is not None:
            parent = self.get_simple_resource(parent)
            params["objid"] = "%s//%s" % (parent.objid, id_gen())
            params["parent"] = parent.oid
        else:
            params["objid"] = "%s//%s" % (self.objid, id_gen())
            params["parent"] = None

        # get class
        if isinstance(resource_class, str):
            resource_class = import_class(resource_class)

        if tags is None:
            tags = ""
        other_params = {
            "alias": "%s.create" % resource_class.__name__,
            "cid": self.oid,
            "name": name,
            "desc": desc,
            "ext_id": ext_id,
            "active": active,
            "attribute": attribute,
            "tags": tags,
        }
        params.update(other_params)

        # pre create function
        self.logger.debug("Initial params: %s" % params)
        params = resource_class.pre_create(self.controller, self, **params)
        sync = params.pop("sync", False)
        set_as_sync = params.pop("set_as_sync", False)
        params["attribute"]["has_quotas"] = has_quotas
        self.logger.debug("Pre create after params: %s" % params)

        # verify permissions
        parent_objid = "//".join(params["objid"].split("//")[:-1])
        self.logger.debug("Parent objid: %s" % parent_objid)
        if operation.authorize is True:
            self.controller.check_authorization(resource_class.objtype, resource_class.objdef, parent_objid, "insert")

        # create resource in PENDING state
        resource = self.add_resource2(resource_class, params)
        model = resource.model

        # try:
        #     model = self.add_resource(objid=params['objid'], name=params['name'], resource_class=resource_class,
        #                               ext_id=params['ext_id'], active=params['active'], desc=params['desc'],
        #                               attrib=params['attribute'], parent=params.get('parent', None))
        #     params.update({'id': model.id, 'uuid': model.uuid})
        #     resource = resource_class(self.controller, oid=model.id, objid=params['objid'], name=params['name'],
        #                               desc=params['desc'], active=params['active'], model=model)
        # except ApiManagerError as ex:
        #     self.logger.error(ex, exc_info=False)
        #     raise

        # post create resource using async celery task
        if set_as_sync is False and resource_class.create_task is not None:
            params.update(self.get_user())
            res = prepare_or_run_task(resource, resource_class.create_task, params, sync=sync)
            resource.logger.info("run create task: %s" % res[0])
            return res

        # post create resource using sync method
        else:
            self.update_resource_state(model.id, ResourceState.BUILDING)

            resource.set_container(self)

            import_func = getattr(resource, "do_create", None)
            if import_func is not None:
                import_func(**params)

            # post create function
            resource_class.post_create(self.controller, self, **params)

            # add tags
            if tags is not None and tags != "":
                resource = self.get_resource(model.id)
                for tag in tags.split(","):
                    try:
                        self.controller.add_tag(value=tag)
                    except ApiManagerError as ex:
                        self.logger.warning(ex)
                    try:
                        resource.add_tag(tag)
                    except ApiManagerError as ex:
                        self.logger.warning(ex)

            self.update_resource_state(model.id, ResourceState.ACTIVE)
            self.activate_resource(model.id)

        return {"uuid": model.uuid}, 201

    def __pre_import_resource(
        self,
        resource_class,
        name=None,
        desc="",
        ext_id=None,
        active=False,
        attribute={},
        parent=None,
        tags="",
        has_quotas=True,
        **params,
    ):
        """pre import resource.

        :param resource_class: resource class
        :param name: resource name
        :param desc: resource description
        :param ext_id: resource physical id
        :param active: resource active
        :param attribute: resource attribute
        :param parent: resource parent id
        :param tags: resource tags
        :param has_quotas: enable or disable quota and metric
        :param params: resource custom params
        :return:
        """
        if parent is not None:
            # parent = self.get_simple_resource(parent)
            params["objid"] = "%s//%s" % (parent.objid, id_gen())
            params["parent"] = parent.oid
        else:
            params["objid"] = "%s//%s" % (self.objid, id_gen())
            params["parent"] = None

        # get class
        if isinstance(resource_class, str):
            resource_class = import_class(resource_class)

        if tags is None:
            tags = ""
        other_params = {
            "alias": "%s.import" % resource_class.__name__,
            "cid": self.oid,
            "name": name,
            "desc": desc,
            "ext_id": ext_id,
            "active": active,
            "attribute": attribute,
            "tags": tags,
        }
        params.update(other_params)

        # pre import function
        self.logger.debug("Initial params: %s" % params)
        params = resource_class.pre_import(self.controller, self, **params)
        sync = params.pop("sync", False)
        params["attribute"]["has_quotas"] = has_quotas
        self.logger.debug("Pre import after params: %s" % params)

        # verify permissions
        parent_objid = "//".join(params["objid"].split("//")[:-1])
        self.logger.debug("Parent objid: %s" % parent_objid)
        if operation.authorize is True:
            self.controller.check_authorization(resource_class.objtype, resource_class.objdef, parent_objid, "insert")

        # import resource in PENDING state
        resource = self.add_resource2(resource_class, params)
        # try:
        #     model = self.add_resource(objid=params['objid'], name=params['name'], resource_class=resource_class,
        #                               ext_id=params['ext_id'], active=params['active'], desc=params['desc'],
        #                               attrib=params['attribute'], parent=params.get('parent', None))
        #     params.update({'id': model.id, 'uuid': model.uuid})
        #     resource = resource_class(self.controller, oid=model.id, objid=params['objid'], name=params['name'],
        #                               desc=params['desc'], active=params['active'], model=model)
        #     resource.set_container(self)
        # except ApiManagerError as ex:
        #     self.logger.error(ex, exc_info=False)
        #     raise

        self.logger.debug("import resource: %s" % resource)
        return resource, params

    def import_resource(
        self,
        resource_class,
        name=None,
        desc="",
        ext_id=None,
        active=False,
        attribute={},
        parent=None,
        tags="",
        has_quotas=True,
        sync=False,
        **params,
    ):
        """Factory used to import new resource.

        :param resource_class: class of resource to import or string representation
        :param name: resource name
        :param desc: resource desc
        :param ext_id: ext_id [default=None]
        :param active: active [default=True],
        :param attribute: attribute [default={}],
        :param parent: parent id [default=None]
        :param tags: comma separated resource tags to assign [default='']
        :param has_quotas: if True resource has quotas and metric associated [default=True]
        :param sync: if True run sync task, if False run async task
        :param params: custom params required by task or function
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
                 for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource creation")
        else:
            self.logger.debug("run async resource creation")

        # import basic resource
        resource, params = self.__pre_import_resource(
            resource_class,
            name,
            desc,
            ext_id,
            active,
            attribute,
            parent,
            tags,
            has_quotas,
            **params,
        )

        # run resource method that launch task or exec operation sync
        res = resource.do_import(params, sync=sync)

        # run final import is method is sync
        if sync is True:
            # resource.finalize_import(**params)
            res = {"uuid": resource.uuid}, 201
        else:
            res[0]["uuid"] = resource.uuid

        self.logger.debug("end resource import with result: %s" % res[0])
        return res

    @trace(op="insert")
    def resource_import_factory(
        self,
        resource_class,
        name=None,
        desc="",
        ext_id=None,
        active=False,
        attribute={},
        parent=None,
        tags="",
        **params,
    ):
        """Factory used to import resource from an existing.

        :param resource_class: class of resource to create or string representation
        :param name: resource name
        :param desc: resource desc
        :param ext_id: resource id to import[default=None]
        :param active: [default=True],
        :param attribute: [default={}]
        :param tags: comma separated resource tags to assign [default='']
        :param parent: parent id [default=None]
        :param params: custom params required by task or function
        :param params.sync: if True run sync task, if False run async task
        :param params.set_as_sync: if True it is used to break task behaviour
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        # get parent
        if parent is not None:
            parent = self.get_resource(parent, run_customize=False)
            params["objid"] = "%s//%s" % (parent.objid, id_gen())
            params["parent"] = parent.oid

        # get class
        # if isinstance(resource_class, str) or isinstance(resource_class, unicode):
        if isinstance(resource_class, str):
            resource_class_name = resource_class
            try:
                resource_class = import_class(resource_class_name)
            except:
                raise ApiManagerError("Resource class %s does not exist" % resource_class_name)

        if tags is None:
            tags = ""
        other_params = {
            "alias": "%s.import" % resource_class.__name__,
            "cid": self.oid,
            "name": name,
            "desc": desc,
            "ext_id": ext_id,
            "active": active,
            "attribute": attribute,
            "tags": tags,
        }
        params.update(other_params)

        # pre import function
        self.logger.debug("Initial params: %s" % params)
        params = resource_class.pre_import(self.controller, self, **params)
        sync = params.pop("sync", False)
        set_as_sync = params.pop("set_as_sync", False)
        self.logger.debug("Pre import after params: %s" % params)

        # verify permissions
        parent_objid = "//".join(params["objid"].split("//")[:-1])
        self.logger.debug("Parent objid: %s" % parent_objid)
        if operation.authorize is True:
            self.controller.check_authorization(resource_class.objtype, resource_class.objdef, parent_objid, "insert")

        # create resource in PENDING state
        resource = self.add_resource2(resource_class, params)
        model = resource.model
        # try:
        #     model = self.add_resource(objid=params['objid'], name=params['name'], resource_class=resource_class,
        #                               ext_id=params['ext_id'], active=params['active'], desc=params['desc'],
        #                               attrib=params['attribute'], parent=params.get('parent', None))
        #     params.update({'id': model.id, 'uuid': model.uuid})
        #     resource = resource_class(self.controller, oid=model.id, objid=params['objid'], name=params['name'],
        #                               desc=params['desc'], active=params['active'], model=model)
        # except ApiManagerError as ex:
        #     self.logger.error(ex, exc_info=False)
        #     raise

        # post import resource using async celery task
        if set_as_sync is False and resource_class.import_task is not None:
            params.update(self.get_user())
            res = prepare_or_run_task(resource, resource_class.import_task, params, sync=sync)
            resource.logger.info("run import task: %s" % res[0])
            return res

        # post import resource using sync method
        else:
            self.update_resource_state(model.id, ResourceState.BUILDING)
            # resource = self.get_simple_resource(model.id)
            resource.set_container(self)

            import_func = getattr(resource, "do_import", None)
            if import_func is not None:
                import_func(**params)

            # post import function
            resource_class.post_import(self.controller, self, **params)

            # add tags
            if tags is not None and tags != "":
                # resource = self.get_resource(model.id)
                for tag in tags.split(","):
                    try:
                        self.controller.add_tag(value=tag)
                    except ApiManagerError as ex:
                        self.logger.warning(ex)
                    try:
                        resource.add_tag(tag)
                    except ApiManagerError as ex:
                        self.logger.warning(ex)

            self.update_resource_state(model.id, ResourceState.ACTIVE)
            self.activate_resource(model.id)

        return {"uuid": model.uuid}, 201

    def __pre_clone_resource(
        self,
        resource_to_clone,
        name=None,
        desc="",
        parent=None,
        has_quotas=True,
        **params,
    ):
        """pre clone resource. TODO:

        :param resource_to_clone: resource to clone
        :param name: resource name
        :param desc: resource description
        :param parent: resource parent
        :param has_quotas: enable or disable quota and metric
        :param params: resource custom params
        :return:
        """
        resource_class = resource_to_clone.__class__

        if parent is not None:
            # parent = self.get_simple_resource(parent)
            params["objid"] = "%s//%s" % (parent.objid, id_gen())
            params["parent"] = parent.oid
        else:
            params["objid"] = "%s//%s" % (self.objid, id_gen())
            params["parent"] = None

        # get class
        if isinstance(resource_class, str):
            resource_class = import_class(resource_class)

        # if tags is None:
        #     tags = ''
        other_params = {
            "cid": self.oid,
            "name": name,
            "desc": desc,
            "ext_id": resource_to_clone.ext_id,
            "active": False,
            "attribute": resource_to_clone.get_attribs(),
            # 'tags': tags
        }
        params.update(other_params)

        # pre clone function
        self.logger.debug("Initial params: %s" % params)
        params = resource_class.pre_clone(self.controller, self, **params)
        # sync = params.pop('sync', False)
        params["attribute"]["has_quotas"] = has_quotas
        self.logger.debug("Pre clone after params: %s" % params)

        # verify permissions
        parent_objid = "//".join(params["objid"].split("//")[:-1])
        self.logger.debug("Parent objid: %s" % parent_objid)
        if operation.authorize is True:
            self.controller.check_authorization(resource_class.objtype, resource_class.objdef, parent_objid, "insert")

        # clone resource in PENDING state
        resource = self.add_resource2(resource_class, params)
        # try:
        #     model = self.add_resource(objid=params['objid'], name=params['name'], resource_class=resource_class,
        #                               ext_id=params['ext_id'], active=params['active'], desc=params['desc'],
        #                               attrib=params['attribute'], parent=params.get('parent', None))
        #     params.update({'id': model.id, 'uuid': model.uuid})
        #     resource = resource_class(self.controller, oid=model.id, objid=params['objid'], name=params['name'],
        #                               desc=params['desc'], active=params['active'], model=model)
        #     resource.set_container(self)
        # except ApiManagerError as ex:
        #     self.logger.error(ex, exc_info=False)
        #     raise

        self.logger.debug("clone resource: %s" % resource)
        return resource, params

    def clone_resource(
        self,
        resource_class,
        name=None,
        desc="",
        resource_id=None,
        attribute={},
        parent=None,
        tags="",
        has_quotas=True,
        sync=False,
        **params,
    ):
        """Factory used to clone new resource. TODO

        :param resource_class: class of resource to clone or string representation
        :param name: resource name
        :param desc: resource desc
        :param ext_id: ext_id [default=None]
        :param active: active [default=True],
        :param attribute: attribute [default={}],
        :param parent: parent id [default=None]
        :param tags: comma separated resource tags to assign [default='']
        :param has_quotas: if True resource has quotas and metric associated [default=True]
        :param sync: if True run sync task, if False run async task
        :param params: custom params required by task or function
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
                 for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource creation")
        else:
            self.logger.debug("run async resource creation")

        # clone basic resource
        resource, params = self.__pre_clone_resource(
            resource_to_clone,
            name=None,
            desc="",
            parent=None,
            has_quotas=True,
            **params,
        )

        # run resource method that launch task or exec operation sync
        res = resource.do_clone(params, sync=sync)

        # run final clone is method is sync
        if sync is True:
            # resource.finalize_clone(**params)
            res = {"uuid": resource.uuid}, 201
        else:
            res[0]["uuid"] = resource.uuid

        self.logger.debug("end resource clone with result: %s" % res[0])
        return res

    # @trace(op='insert')
    # def resource_clone_factory(self, resource_class, name=None, desc='', ext_id=None, active=False,
    #                            attribute={}, parent=None, tags='', has_quotas=True, **params):
    #     """Factory used to clone resource from an existing.
    #
    #     :param resource_class: class of resource to create or string representation
    #     :param name: resource name
    #     :param desc: resource desc
    #     :param ext_id: ext_id [default=None]
    #     :param active: active [default=True],
    #     :param attribute: attribute [default={}],
    #     :param parent: parent id [default=None]
    #     :param tags: comma separated resource tags to assign [default='']
    #     :param has_quotas: if True resource has quotas and metric associated [default=True]
    #     :param params: custom params required by task or function
    #     :param params.clone_resource: id of the resource to clone
    #     :param params.sync: if True run sync task, if False run async task
    #     :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
    #         for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
    #         for sync resource {'uuid': resource uuid}
    #     :raises ApiManagerError: if query empty return error.
    #     """
    #     if parent is not None:
    #         parent = self.get_simple_resource(parent)
    #         params['objid'] = '%s//%s' % (parent.objid, id_gen())
    #         params['parent'] = parent.oid
    #     else:
    #         params['objid'] = '%s//%s' % (self.objid, id_gen())
    #         params['parent'] = None
    #
    #     # get class
    #     if isinstance(resource_class, str):
    #         resource_class = import_class(resource_class)
    #
    #     if tags is None:
    #         tags = ''
    #     other_params = {
    #         'alias': '%s.create' % resource_class.__name__,
    #         'cid': self.oid,
    #         'name': name,
    #         'desc': desc,
    #         'ext_id': ext_id,
    #         'active': active,
    #         'attribute': attribute,
    #         'tags': tags
    #     }
    #     params.update(other_params)
    #
    #     # pre create function
    #     self.logger.debug('Initial params: %s' % params)
    #     params = resource_class.pre_clone(self.controller, self, **params)
    #     sync = params.pop('sync', False)
    #     params['attribute']['has_quotas'] = has_quotas
    #     self.logger.debug('Pre clone after params: %s' % params)
    #
    #     # verify permissions
    #     parent_objid = '//'.join(params['objid'].split('//')[:-1])
    #     self.logger.debug('Parent objid: %s' % parent_objid)
    #     if operation.authorize is True:
    #         self.controller.check_authorization(resource_class.objtype, resource_class.objdef, parent_objid, 'insert')
    #
    #     # create resource in PENDING state
    #     try:
    #         model = self.add_resource(objid=params['objid'], name=params['name'], resource_class=resource_class,
    #                                   ext_id=params['ext_id'], active=params['active'], desc=params['desc'],
    #                                   attrib=params['attribute'], parent=params.get('parent', None))
    #         params.update({'id': model.id, 'uuid': model.uuid})
    #         resource = resource_class(self.controller, oid=model.id, objid=params['objid'], name=params['name'],
    #                                   desc=params['desc'], active=params['active'], model=model)
    #     except ApiManagerError as ex:
    #         self.logger.error(ex, exc_info=False)
    #         raise
    #
    #         # post create resource using async celery task
    #     if resource_class.clone_task is not None:
    #         params.update(self.get_user())
    #         res = prepare_or_run_task(resource, resource_class.create_task, params, sync=sync)
    #         resource.logger.info('run create task: %s' % res[0])
    #         return res
    #
    #     # post create resource using sync method
    #     else:
    #         self.update_resource_state(model.id, ResourceState.BUILDING)
    #         # post create function
    #         resource_class.post_clone(self.controller, self, **params)
    #
    #         # add tags
    #         if tags is not None and tags != '':
    #             resource = self.get_resource(model.id)
    #             for tag in tags.split(','):
    #                 try:
    #                     self.controller.add_tag(value=tag)
    #                 except ApiManagerError as ex:
    #                     self.logger.warning(ex)
    #                 try:
    #                     resource.add_tag(tag)
    #                 except ApiManagerError as ex:
    #                     self.logger.warning(ex)
    #
    #         self.update_resource_state(model.id, ResourceState.ACTIVE)
    #         self.activate_resource(model.id)
    #
    #     return {'uuid': model.uuid}, 201

    @trace(op="view")
    def get_resources(self, *args, **kvargs):
        """Get resources.

        :param authorize: if False disable authorization check
        :param resourcetags: list of tags comma separated. All tags in the list must be met [optional]
        :param objid: resource objid [optional]
        :param name: resource name [optional]
        :param ids: list of resource oid [optional]
        :param uuids: comma separated list of resource uuid [optional]
        :param ext_id: id of resource in the remote container [optional]
        :param ext_ids: list of id of resource in the remote container [optional]
        :param type: comma separated resource type. Use complete syntax or %<type1>% for eachtype. Set with objdef to
            limit permtags [optional]
        :param container: resource container id [optional]
        :param attribute: resource attribute [optional]
        :param parent: parent id [optional]
        :param parent_list: comma separated parent id list [optional]
        :param active: active [optional]
        :param state: state [optional]
        :param creation_date: creation_date [optional]
        :param modification_date: modification_date [optional]
        :param show_expired: if True show expired resources [default=False]
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param objdef: object definition. Use to limit pertag to only used for objdef [optional]
        :param entity_class: entity_class you expect to receive [optional]
        :param run_connect: if True run connect for each container [default=True]
        :param run_customize: if True run customize [default=True]
        :return: :py:class:`list` of :class:`Resource`
        :raise ApiManagerError:
        """
        from beehive_resource.controller import ResourceController

        resourceController: ResourceController = self.controller
        return resourceController.get_resources(container=self.oid, *args, **kvargs)

    def get_resource(self, oid, entity_class=None, *args, **kvargs):
        """Get single resource.

        :param entity_class: Controller ApiObject Extension class. Specify when you want to verify match between
            objdef of the required resource and find resource. [optional]
        :param oid: entity model id or uuid
        :param run_customize: if True run customize [default=True]
        :return: Resource instance
        :raise ApiManagerError:
        """

        def customize(entity, *args, **kvargs):
            # set physical entity
            entity.set_physical_entity(entity=None)

            # # set parent
            # if entity.parent_id is not None:
            #     parent = self.manager.get_entity(ModelResource, entity.parent_id)
            #     entity.set_parent({'id': parent.id, 'uuid': parent.uuid, 'name': parent.name})
            #     self.logger.debug('Set parent %s' % parent.uuid)

            # set container
            entity.set_container(self)
            self.logger.debug("Set container %s" % self)

            # execute custom post_get
            entity.post_get()
            self.logger.debug("Do post get")

            return entity

        res = self.controller.get_entity_v2(
            ModelResource,
            oid,
            entity_class=entity_class,
            customize=customize,
            container_id=self.oid,
            **kvargs,
        )

        # set error reason
        if res.model.state == 4:
            res.reason = res.get_errors()

        return res

    def get_simple_resource(self, oid, entity_class=None, **kvargs):
        """Get single resource without details

        :param entity_class: Controller ApiObject Extension class. Specify when you want to verify match between
            objdef of the required resource and find resource. [optional]
        :param oid: entity model id or uuid
        :return: Resource instance
        :raise ApiManagerError:
        """
        return self.get_resource(oid, entity_class=entity_class, run_customize=False, **kvargs)

    def index_resources_by_extid(self, entity_class=None):
        """Get resources indexed by remote platform id

        :param entity_class: parent resource class [optional]
        :return: list of Resource instances
        :raise ApiManagerError:
        """
        return self.controller.index_resources_by_extid(entity_class=entity_class, container=self.oid)

    def get_resource_by_extid(self, ext_id):
        """Get resource by remote platform id

        :param ext_id: remote platform entity id
        :return: Resource instance
        :raise ApiManagerError:
        """
        if ext_id is None:
            return None
        try:
            entity = self.manager.get_resource_by_extid(ext_id, container=self.oid)
            entity_class = import_class(entity.type.objclass)
            res = entity_class(
                self.controller,
                oid=entity.id,
                objid=entity.objid,
                name=entity.name,
                active=entity.active,
                desc=entity.desc,
                model=entity,
            )
            res.container = self
            self.logger.info("Get resource by ext_id %s : %s" % (ext_id, res))
            return res
        except QueryError as ex:
            self.logger.warning(ex)
            return None

    #
    # link
    #
    def add_link(
        self,
        name=None,
        type=None,
        start_resource=None,
        end_resource=None,
        attributes={},
        *args,
        **kvargs,
    ):
        """Add new link.

        :param name: link name
        :param type: link type
        :param start_resource: start resource reference id, uuid
        :param end_resource: end resource reference id, uuid
        :param attributes: link attributes [default={}]
        :return: link uuid
        :raise ApiManagerError:
        """
        return self.controller.add_link(name, type, start_resource, end_resource, attributes)

    #
    # tags
    #
    @trace(op="tag-assign.update")
    def add_tag(self, value, *args, **kvargs):
        """Add tag

        :param value str: tag value
        :return: True if operation is successful
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        # check authorization
        self.verify_permisssions("update")

        # get tag
        tag = self.controller.get_tag(value)

        try:
            res = self.manager.add_container_tag(self.model, tag.model)
            self.logger.info("Add tag %s to container %s: %s" % (value, self.name, res))
            return res
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="tag-deassign.update")
    def remove_tag(self, value, *args, **kvargs):
        """Remove tag

        :param value str: tag value
        :return: True if operation is successful
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        # check authorization
        self.verify_permisssions("update")

        # get tag
        tag = self.controller.get_tag(value)

        try:
            res = self.manager.remove_container_tag(self.model, tag.model)
            self.logger.info("Remove tag %s from container %s: %s" % (value, self.name, res))
            return res
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    #
    # discover
    #
    @trace(op="use")
    def discover_new_entities(self, restype, ext_id=None):
        """Get resources not registered in beehive.

        :param restype: container resource objdef
        :param ext_id: remote entity id [optional]
        :return:

            {
                'new':[
                    'resclass':..,
                    'id':..,
                    'parent':..,
                    'type':..,
                    'name':..
                ],
                'died':[],
                'changed':[]
            }

        :raise ApiManagerError:
        """
        resources = []
        self.logger.debug("Resource type: %s" % restype)

        try:
            resources = self.manager.get_resources_by_type(type=restype, container=self.oid)
        except QueryError as ex:
            self.logger.warning(ex, exc_info=False)

        try:
            res = []

            # get external ids from beehive resources list
            res_ext_ids = [r.ext_id for r in resources if r.ext_id is not None]

            # call resource discover_new internal method
            restype = self.manager.get_resource_types(value=restype)[0]
            resclass = import_class(restype.objclass)

            self.logger.debug("------- discover new %s -------" % restype)
            res.extend(resclass.discover_new(self, ext_id, res_ext_ids))
            self.logger.debug("------- discover new %s -------" % restype)

            self.logger.info("Discover new %s entities: %s" % (resclass.__name__, truncate(res)))
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="use")
    def discover_died_entities(self, restype, died=True, changed=True):
        """Get resources registered in beehive and not already present in remote platform.

        :param restype: container resource objdef
        :param old: if True remove orphaned resources
        :param changed: if True update changed resources
        :return:

            {
                'new':[],
                'died':[
                    'resclass':..,
                    'id':..,
                    'parent':..,
                    'type':..,
                    'name':..
                ],
                'changed':[
                    'resclass':..,
                    'id':..,
                    'parent':..,
                    'type':..,
                    'name':..
                ]
            }

        :raise ApiManagerError:
        """
        self.logger.debug("Registered resource type: %s" % restype)

        resources = []
        try:
            resources = self.manager.get_resources_by_type(type=restype, container=self.oid)
        except QueryError as ex:
            self.logger.warning(ex, exc_info=False)

        try:
            res = {"died": [], "changed": []}
            items = []

            restype = self.manager.get_resource_types(value=restype)[0]
            resclass = import_class(restype.objclass)
            self.logger.debug("------- discover died %s -------" % restype)
            items = resclass.discover_died(self)
            self.logger.debug("------- discover died %s -------" % restype)

            itemidx = {i["id"]: i for i in items}
            for r in resources:
                if r.ext_id is None or r.ext_id == "":
                    continue

                # append died resources
                if died is True and r.ext_id not in itemidx.keys():
                    resource_class = import_class(r.type.objclass)
                    obj = resource_class(
                        self.controller,
                        oid=r.id,
                        objid=r.objid,
                        name=r.name,
                        desc=r.desc,
                        active=r.active,
                        model=r,
                    )
                    obj.container = self
                    obj.ext_id = r.ext_id
                    res["died"].append(obj)
                    self.logger.debug("Resource %s does not exist anymore. It can be deleted." % r.name)

                # append changed resources
                elif changed is True:
                    if r.name != itemidx[r.ext_id]["name"]:
                        item = itemidx[r.ext_id]
                        resource_class = import_class(r.type.objclass)
                        obj = resource_class(
                            self.controller,
                            oid=r.id,
                            objid=r.objid,
                            name=item["name"],
                            desc=r.desc,
                            active=r.active,
                            model=r,
                        )
                        obj.container = self
                        obj.ext_id = r.ext_id
                        res["changed"].append(obj)
                        self.logger.debug("Resource %s is changed." % r.name)

            return res
        except (ApiManagerError, Exception) as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="use")
    def discover(self, restype, ext_id=None):
        """Discover remote platform entities

        :param restype: container resource objdef
        :param ext_id: remote entity id [optional]
        :return:

            {
                'new':[
                    'resclass':..,
                    'id':..,
                    'parent':..,
                    'type':..,
                    'name':..
                ],
                'died':[],
                'changed':[]
            }

        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("use")

        try:
            res = {"new": [], "died": [], "changed": []}
            entities = self.discover_new_entities(restype, ext_id=ext_id)

            for r in entities:
                data = {
                    "resclass": "%s.%s" % (r[0].__module__, r[0].__name__),
                    "id": r[1],
                    "parent": r[2],
                    "type": r[3],
                    "name": r[4],
                }
                res["new"].append(data)

            entities = self.discover_died_entities(restype)
            for r in entities["died"]:
                data = {
                    "resclass": "%s.%s" % (r.__class__.__module__, r.__class__.__name__),
                    "id": r.oid,
                    "parent": r.parent_id,
                    "type": r.objdef,
                    "name": r.name,
                }
                res["died"].append(data)

            for r in entities["changed"]:
                data = {
                    "resclass": "%s.%s" % (r.__class__.__module__, r.__class__.__name__),
                    "id": r.oid,
                    "parent": r.parent_id,
                    "type": r.objdef,
                    "name": r.name,
                }
                res["changed"].append(data)

            self.logger.info("Discover container %s entities: %s" % (self.oid, truncate(res)))
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    #
    # discover task
    #
    @trace(op="update")
    def synchronize_resources(self, params):
        """Synchronize remote platform entities

        :param params: Params required
        :param params.types: List of resource objef comma separated. If empty use all the available objdef.
        :param params.new: if True discover new entity
        :param params.died: if True remove orphaned resources
        :param params.changed: if True update changed resources
        :param params.ext_id: physical entity id [optional]
        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # self.logger.info('+++++ self %s' % (type(self)))
        from beehive_resource.plugins.grafana.controller import GrafanaContainer
        from beehive_resource.plugins.elk.controller import ElkContainer

        if isinstance(self, GrafanaContainer):
            if self.conn_grafana is None:
                raise ApiManagerError(
                    "Synchronize not implemented for container %s - check connection grafana" % self.oid,
                    code=405,
                )

        elif isinstance(self, ElkContainer):
            if self.conn_kibana is None:
                raise ApiManagerError(
                    "Synchronize not implemented for container %s - check connection kibana" % self.oid,
                    code=405,
                )
            if self.conn_elastic is None:
                raise ApiManagerError(
                    "Synchronize not implemented for container %s - check connection elastic" % self.oid,
                    code=405,
                )

        elif self.conn is None:
            raise ApiManagerError("Synchronize not implemented for container %s" % self.oid, code=405)

        resource_types = params.get("types", None)

        params.update(self.get_user())
        params["objid"] = str(self.uuid)
        params["cid"] = self.oid
        params["alias"] = "SynchronizeResources"
        if resource_types is not None and resource_types.find(",") == -1:
            params["alias"] = "SynchronizeResources.%s" % resource_types
        task = signature(
            self.synchronize_task,
            [params],
            app=self.task_manager,
            queue=self.celery_broker_queue,
        )
        job = task.apply_async()

        self.logger.info("Start resource synchronization over container %s with job %s" % (self.oid, job))
        return job.id

    @trace(op="discover-get.use")
    def get_discover_scheduler(self):
        """Get discover scheduler for the container

        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("use")

        try:
            name = self._discover_service
            uri = "/v1.0/scheduler/entry/%s/" % name
            res = self.api_client.admin_request("resource", uri, "GET", "")
            self.logger.info("Get discover scheduler for container %s: %s" % (self.name, res))
            return res
        except BeehiveApiClientError as ex:
            self.logger.warning(ex, exc_info=False)
            return None

    @trace(op="discover-set.update")
    def add_discover_scheduler(self, minutes):
        """Add discover scheduler for the container

        :param minutes: schedule delta time after new discover in minutes
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        data = {
            "name": self._discover_service,
            "task": "tasks.discover_%s" % self.objdef,
            "args": [self.oid],
            "schedule": {"type": "timedelta", "minutes": minutes},
            "options": {"expires": 86400},
        }
        res = self.api_client.admin_request("resource", "/v1.0/nrs/scheduler/entries", "POST", data)
        self.logger.info("Add discover scheduler for container %s: %s" % (self.name, res))
        return res

    @trace(op="discover-unset.update")
    def remove_discover_scheduler(self):
        """Remove discover scheduler for container

        :param minutes: schedule delta time after new discover in minutes
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        data = {"name": self._discover_service}
        res = self.api_client.admin_request("resource", "/v1.0/nrs/scheduler/entries", "DELETE", data)
        self.logger.info("Remove discover scheduler for container %s: %s" % (self.name, res))
        return res


class Provider(ResourceContainer):
    """Infrastructure provider"""

    objdesc = "Provider"
    category = "provider"


class Orchestrator(ResourceContainer):
    """Infrastructure orchestrator"""

    objdesc = "Orchestrator"
    category = "orchestrator"


class Resource(ApiObject):
    """Basic resource"""

    module = "ResourceModule"
    objtype = "resource"
    objdef = "Container.Resource"
    objuri = "nrs"
    objname = "resource"
    objdesc = "Abstract resource"
    objtask_version = None

    # cache key
    cache_key = "resource.get"

    # set this to define default tags to apply to resource
    default_tags = []

    # set this to manage resource using aysnc celery task
    create_task = None
    import_task = None
    update_task = None
    patch_task = None
    delete_task = None
    expunge_task = None
    action_task = None

    def __init__(self, *args, **kvargs):
        ApiObject.__init__(self, *args, **kvargs)
        self.container: ResourceContainer = None
        self.ext_id = None
        self.ext_obj = None
        self.parent = None
        self.parent_id = None
        self.attribs = None
        self.child_classes = []

        # # roles
        # self._admin_role_prefix = 'admin'
        # self._viewer_role_prefix = 'viewer'

        # uuid and tag name
        self.tag_name = self.uuid

        self.reuse = False

        # status reason. Use when resource in error
        self.reason = None

        # configure
        self.set_attribs()
        self.state = ResourceState.state[9]  # unknown
        if self.model is not None:
            self.parent_id = self.model.parent_id
            self.container_id = self.model.container_id
            self.ext_id = self.model.ext_id
            self.state = self.model.state
            self.active = self.model.active  # aaa nel model in desc c'è la tripletta

    def get_resource_classes(self):
        child_classes = [item.objdef for item in self.child_classes]
        for item in self.child_classes:
            child_classes.extend(item(self.controller).get_resource_classes())
        return child_classes

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(platform_client, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param platform_client: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: ist of tuple (resource class, ext_id, parent_id, resource class objdef, name, level)
        :raise ApiManagerError:
        """
        return []

    @staticmethod
    def discover_died(platform_client):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param client platform_client: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        return []

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        level = entity[5]

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent_id,
            "tags": resclass.default_tags,
        }
        return res

    #
    # init object
    #
    def init_object(self):
        """Register object types, objects and permissions related to module.
        Call this function when initialize system first time.

        :param args:
        """
        ApiObject.init_object(self)

        # call only once during db initialization
        try:
            # create resource type
            class_name = self.__class__.__module__ + "." + self.__class__.__name__
            self.manager.add_resource_type(self.objdef, class_name)
        except TransactionError as ex:
            self.logger.warning(ex)

    def set_parent(self, parent):
        """Set parent resource uuid, id, name

        :param attributes: attributes
        """
        self.parent = parent

    def get_parent(self):
        """Get parent"""
        return self.controller.get_simple_resource(self.parent_id)

    def count_child_resources(self):
        """count child resources

        :return: child resources count
        """
        return self.manager.count_resource(parent_id=self.oid)

    def set_container(self, container):
        """Set container

        :param attributes: attributes
        """
        self.container = container

    def set_physical_entity(self, entity=None):
        """Set physical entity

        :param entity: entity object
        """
        self.ext_obj = entity

    def is_ext_id_valid(self):
        """Check if physical entity id is valid

        :return: True or False
        """
        if self.ext_id is not None and self.ext_id != "":
            return True
        return False

    def set_attribs(self):
        """Set attributes

        :param attributes: attributes
        """
        self.attribs = {}
        if self.model is not None and self.model.attribute is not None:
            try:
                self.attribs = json.loads(self.model.attribute)
            except Exception as ex:
                self.attribs = {}

    def get_attribs(self, key=None, default=None):
        """Get attributes

        :param key: key to search in attributes dict [optional]
        :param default: default value [default=None]
        :return: attributes value
        """
        res = self.attribs
        if key is not None:
            res = dict_get(res, key, default=default)
        return res

    def set_configs(self, key: str = None, value: str = None):
        """Set attributes

        :param key: key
        :param value: value
        :raises ApiManagerError: if return error.
        """
        try:
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            self.attribs = dict_set(self.attribs, key, value, separator=".")
            self.update_internal(attribute=self.attribs)
        except TransactionError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=400)

    def unset_configs(self, key=None):
        """Unset attributes

        :param key: key
        :raises ApiManagerError: if return error.
        """
        try:
            self.attribs = dict_unset(self.attribs, key, separator=".")
            self.update_internal(attribute=self.attribs)
        except TransactionError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=400)

    def update_state(self, state, error=""):
        """Update resource state

        :param state: new state
        :raises ApiManagerError: if query empty return error.
        """
        # clean cache
        self.clean_cache()

        try:
            # change resource state
            self.manager.update_resource_state(self.oid, state, last_error=error)
            self.logger.info("Set resource %s state to: %s" % (self.oid, state))
        except QueryError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    def get_base_state(self):
        """Get resource base state.

        :return: State can be:

            * PENDING = 0
            * BUILDING = 1
            * ACTIVE = 2
            * UPDATING = 3
            * ERROR = 4
            * DELETING = 5
            * DELETED = 6
            * EXPUNGING = 7
            * EXPUNGED = 8
            * UNKNOWN = 9
            * DISABLED = 10
        """
        res = ResourceState.state[self.state]
        return res

    def get_extended_state(self):
        """Get resource extended state.

        :return: state
        """
        res = self.get_base_state()
        # todo improve check of state. is too slow
        # if self.state == 2 and self.check() is False:
        #    res = ResourceState.state[9]
        return res

    def get_runstate(self):
        """Get resource running state if exixst.

        :return: None if runstate does not exist
        """
        return None

    def is_active(self):
        """Check resource state is ACTIVE

        :return: True if it is Active, False otherwise
        """
        self.logger.warn(self.state)
        self.logger.warn(self.active)
        if self.state == 2 and self.active == 1:
            res = True
            self.logger.info("Resource %s is active: %s" % (self.oid, res))
        elif self.state == 4 and self.active == 1:
            res = True
            self.logger.warning("Resource %s is in error but active: %s" % (self.oid, res))
        else:
            res = False
            # self.logger.error('+++++ TRYFIX is_active - oid: %s - state: %s - active: %s' % (self.oid, self.state, self.active))
            self.logger.warning("Resource %s is not active: %s - state: %s" % (self.oid, res, self.state))
        return res

    def check_active(self):
        """Check resource state is ACTIVE

        :return: True if it is active, False otherwise
        """
        if self.is_active() is False:
            raise ApiManagerError("Resource %s is not active" % self.oid)

    def get_errors(self):
        """Get resource errors.

        :return: List of resource errors
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        res = [self.model.last_error]
        return res

    #
    # info
    #
    def get_cache(self):
        """Get cache items"""
        res = ApiObject.get_cache(self)
        res.extend(self.cache.get_by_pattern("*.%s" % self.ext_id))
        return res

    def clean_cache(self):
        """Clean cache"""
        # logger.debug("+++++ clean_cache - Resource %s" % self.ext_id)
        ApiObject.clean_cache(self)
        self.cache.delete_by_pattern("*.%s" % self.ext_id)

    def set_cache(self):
        """Cache object required infos.

        :return: Dictionary with object info.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        ApiObject.set_cache(self)

    def small_info(self):
        """Get resource small infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = ApiObject.small_info(self)
        res["state"] = self.get_base_state()
        return res

    def info(self):
        """Get system capabilities.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = ApiObject.info(self)
        res["base_state"] = self.get_base_state()
        res["state"] = self.get_extended_state()
        res["runstate"] = self.get_runstate()
        res["parent"] = self.parent_id
        # if self.parent is not None:
        #     res['parent'] = {'id': self.parent_id,
        #                      'uuid': self.parent.get('uuid', None),
        #                      'name': self.parent.get('name', None)}
        # else:
        #     res['parent'] = {'id': self.parent_id,
        #                      'uuid': self.parent_id,
        #                      'name': self.parent_id}
        res["details"] = {}
        res["attributes"] = self.attribs
        res["ext_id"] = self.ext_id
        res["reuse"] = self.reuse
        res["reason"] = self.reason
        res["container"] = self.model.container_id
        # try:
        #     res['container'] = self.container.small_info()
        # except:
        #     res['container'] = {'id': self.model.container_id}
        return res

    def detail(self):
        """Get system details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = ApiObject.detail(self)
        res["base_state"] = self.get_base_state()
        res["state"] = self.get_extended_state()
        res["runstate"] = self.get_runstate()
        res["parent"] = self.parent_id
        res["details"] = {}
        res["attributes"] = self.attribs
        res["ext_id"] = self.ext_id
        res["reuse"] = self.reuse
        res["reason"] = self.reason
        res["childs"] = self.count_child_resources()
        res["container"] = self.model.container_id
        return res

    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = {"check": True, "msg": None}
        return res

    def has_quotas(self):
        """Check resource has quotas that must be count

        :return: True or False
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = self.get_attribs(key="has_quotas", default=True)
        return res

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {}
        self.logger.debug2("Get resource %s quotas: %s" % (self.oid, quotas))
        return quotas

    def enable_quotas(self):
        """Enable resource quotas discover

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = self.set_configs(key="has_quotas", value=True)
        return res

    def disable_quotas(self):
        """Disable resource quotas discover

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = self.set_configs(key="has_quotas", value=False)
        return res

    def tree(self, parent=True, link=True):
        """
        TODO: verify
        """
        from networkx import DiGraph
        from networkx.readwrite import json_graph

        maxdepth = 3

        class Tree(object):
            def __init__(self, name, depth, resource):
                self.logger = getLogger("beehive_resource.tree")

                self.graph = DiGraph(name=name + "-tree")
                self.depth = depth
                self.edges = []
                self.resource = resource

            def add_node(self, node, link_id=None, relation=None, reuse=None):
                self.graph.add_node(
                    node.oid,
                    id=node.oid,
                    uuid=node.uuid,
                    ext_id=node.ext_id,
                    name=node.name,
                    label=node.name,
                    type=node.objdef,
                    uri=node.objuri,
                    state=node.get_base_state(),
                    container=node.container.oid,
                    container_name=node.container.name,
                    attributes=node.attribs,
                    link=link_id,
                    reuse="reuse=%s" % reuse,
                    relation=relation,
                )

            def make_parent_tree(self, resource, depth):
                if depth >= maxdepth:
                    return

                childs, total = resource.get_resources()
                for child in childs:
                    # add graph link
                    self.edges.append((resource.oid, child.oid))

                    # add graph node
                    self.add_node(child)

                    # get childs
                    self.make_parent_tree(child, depth)

                    # get linked resource
                    if link is True:
                        self.make_link_tree(child, depth, parent=resource)

            def make_link_tree(self, resource: Resource, depth, parent=None):
                if depth >= maxdepth:
                    return

                self.logger.info("resourceLink resource: %s - name: %s" % (resource.oid, resource.name))
                links, total = resource.get_out_links(type="relation%")
                for link in links:
                    resourceLink: ResourceLink = link
                    self.logger.info("resourceLink link - name: %s" % (resourceLink.name))

                    start = resource
                    end = resourceLink.get_end_resource()
                    node = end

                    # if parent is None or node.oid != parent.oid:
                    # add graph link
                    self.edges.append((start.oid, end.oid))

                    # add graph node
                    self.add_node(node, link.oid, link.type, link.get_reuse())

                    # get links for child
                    # if self.depth > 0:
                    self.make_link_tree(node, depth, parent=resource)

            def make_graph(self):
                self.add_node(self.resource)
                # if parent is True:
                #    self.make_parent_tree(self.resource, 0)
                if link is True:
                    self.make_link_tree(self.resource, 0)
                # add all links
                self.graph.add_edges_from(self.edges)

            def get_tree_data(self):
                return json_graph.tree_data(self.graph, root=self.resource.oid)

        # get all links with recursive function
        self.logger.warning("Start resource %s tree creation" % self.oid)
        treeobj = Tree(self.name, 10, self)
        treeobj.make_graph()
        resp = treeobj.get_tree_data()
        self.logger.warning("Stop resource %s tree creation" % self.oid)

        return resp

    @staticmethod
    def get_entities_filter(controller, container_id, *args, **kvargs):
        """Create a list of ext_id to use as resource filter. Use when you
        want to filter resources with a subset of remote physical id.

        :param controller: controller instance
        :param container_id: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return None

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return entities

    #
    # create
    #
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """check input params before resource creation."""
        return kvargs

    def do_create(self, **params):
        """method to execute to make custom resource operations useful to complete create

        :param params: custom params required by task
        :return:
        """
        pass

    def finalize_create(self, **params):
        self.update_state(ResourceState.BUILDING)

        # post create function
        self.post_create(self.controller, **params)

        # # add tags
        # if tags is not None and tags != '':
        #     resource = self.get_resource(resource.oid)
        #     for tag in tags.split(','):
        #         try:
        #             self.controller.add_tag(value=tag)
        #         except ApiManagerError as ex:
        #             self.logger.warning(ex)
        #         try:
        #             resource.add_tag(tag)
        #         except ApiManagerError as ex:
        #             self.logger.warning(ex)

        self.update_state(ResourceState.ACTIVE)

        # change resource state
        self.manager.update_resource(oid=self.oid, active=True)
        self.logger.info("finalize resource %s creation" % self.oid)

    #
    # import
    #
    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """check input params before resource import."""
        return kvargs

    def do_import(self, **params):
        """method to execute to make custom resource operations useful to complete import

        :param params: custom params required by task
        :return:
        """
        pass

    def finalize_import(self, **params):
        self.update_state(ResourceState.BUILDING)

        # post create function
        self.post_import(self.controller, **params)
        self.update_state(ResourceState.ACTIVE)

        # change resource state
        self.manager.update_resource(oid=self.oid, active=True)
        self.logger.info("finalize resource %s import" % self.oid)

    #
    # clone
    #
    @staticmethod
    def pre_clone(controller, container, *args, **kvargs):
        """check input params before resource clone."""
        return kvargs

    def do_clone(self, **params):
        """method to execute to make custom resource operations useful to complete clone

        :param params: custom params required by task
        :return:
        """
        pass

    def finalize_clone(self, **params):
        self.update_state(ResourceState.BUILDING)

        # post create function
        self.post_clone(self.controller, **params)
        self.update_state(ResourceState.ACTIVE)

        # change resource state
        self.manager.update_resource(oid=self.oid, active=True)
        self.logger.info("finalize resource %s clone" % self.oid)

    #
    # update
    #
    def update_tags(self, params):
        # update tags
        tags = params.pop("tags", None)
        if tags is not None:
            cmd = tags.get("cmd")
            values = tags.get("values")
            # add tag
            if cmd == "add":
                for value in values:
                    self.add_tag(value)
            elif cmd == "remove":
                for value in values:
                    self.remove_tag(value)
        return params

    def update_quotas(self, params):
        # update quotas get status
        if params.pop("enable_quotas", True) is True:
            self.enable_quotas()
        elif params.pop("disable_quotas", True) is True:
            self.disable_quotas()
        return params

    def pre_update(self, *args, **kvargs):
        """pre update function. This function is used in update method."""
        return kvargs

    def do_update(self, **params):
        """method to execute to make custom resource operations useful to complete update

        :param params: custom params required by task
        :return:
        """
        pass

    def update2(self, params, sync=False):
        """update resource using a celery job or the synchronous function.

        :param params: custom params required by task
        :param sync: if True run sync task, if False run async task [default=False]
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
                 for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource patch")
        else:
            self.logger.debug("run async resource patch")

        # verify permissions
        self.verify_permisssions("update")

        # clean cache
        self.clean_cache()

        # verify resource status
        if self.get_base_state() not in ["ACTIVE", "ERROR", "UNKNOWN"]:
            raise ApiManagerError(
                "resource %s %s is not in a valid state" % (self.objname, self.oid),
                code=400,
            )

        # run an optional pre patch function
        params = self.pre_update(**params)
        self.logger.debug("params after pre patch: %s" % params)

        # change resource state
        self.update_state(ResourceState.UPDATING)

        # update tags ans quotas
        params = self.update_tags(params)
        params = self.update_quotas(params)

        # update resource main params
        self.update_internal(**params)

        # run resource method that launch task or exec operation sync
        res = self.do_update(params, sync=sync)

        # run final delete is method is sync
        if sync is True:
            res = {"uuid": self.uuid}, 201
        else:
            res[0]["uuid"] = self.uuid

        self.logger.debug("end resource update with result: %s" % res[0])

        return res

    def update(self, **params):
        """Update resource using a celery job or the synchronous function update_resource.

        :param params: custom params required by task
        :param params.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        sync = params.pop("sync", False)
        # verify permissions
        self.verify_permisssions("update")

        # change resource state
        self.update_state(ResourceState.UPDATING)

        # force update with internal update
        force = params.pop("force", False)
        self.logger.debug("Force update: %s" % force)

        # run an optional pre update function
        if force is False:
            params = self.pre_update(**params)
            self.logger.debug("params after pre_update: %s" % params)

        # clean cache
        self.clean_cache()

        # update resource using async celery task
        if self.update_task is not None and force is False:
            base_params = {
                # 'alias': '%s.update' % self.name,
                "alias": "%s.update" % self.__class__.__name__,
                "cid": self.container.oid,
                "id": self.oid,
                "uuid": self.uuid,
                "objid": self.objid,
                "ext_id": self.ext_id,
            }
            base_params.update(params)
            params = base_params
            params.update(self.get_user())
            res = prepare_or_run_task(self, self.update_task, params, sync=sync)
            self.logger.info("Update resource using task %s" % res[0])
            return res

        # update resource using sync method
        else:
            params.pop("tasks", None)

            # update tags ans quotas
            params = self.update_tags(params)
            params = self.update_quotas(params)

            self.update_internal(**params)

            if "state" not in params:
                self.update_state(ResourceState.ACTIVE)
            return {"uuid": self.uuid}, 200

    def update_internal(self, **kvargs):
        """Update resource

        :param kvargs: Params required by update
        :raises ApiManagerError: if query empty return error.
        """
        # clean cache
        self.clean_cache()

        try:
            kvargs["oid"] = self.oid

            # self.logger.debug('+++++ TRYFIX - self.manager: %s' % type(self.manager))
            self.manager: ResourceDbManager
            self.manager.update_resource(**kvargs)
            self.logger.debug("Update %s %s with data %s" % (self.objdef, self.oid, kvargs))

            # session = self.manager.get_session().hash_key
            # if self.objdef == 'Elk.Space':
            #     self.logger.debug('+++++ TRYFIX - session: %s - update_internal - fisica - %s %s with data %s' % (session, self.objdef, self.oid, kvargs))
            # if self.objdef == 'Provider.Region.Site.AvailabilityZone.LoggingSpace':
            #     self.logger.debug('+++++ TRYFIX - session: %s - update_internal - logica - %s %s with data %s' % (session, self.objdef, self.oid, kvargs))
            # if self.objdef == 'Provider.ComputeZone.ComputeLoggingSpace':
            #     self.logger.debug('+++++ TRYFIX - session: %s - update_internal - aggregata - %s %s with data %s' % (session, self.objdef, self.oid, kvargs))
        except TransactionError as ex:
            self.update_state(ResourceState.ERROR, error=str(ex))
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

        # clean cache
        self.clean_cache()
        return self.uuid

    @trace(op="update")
    def set_state(self, state):
        """Set resource state

        :param state: resource state. Valid value are ACTIVE and ERROR
        :return: True
        """
        # verify permissions
        self.verify_permisssions("update")

        if state == "ACTIVE":
            state = ResourceState.ACTIVE
        elif state == "ERROR":
            state = ResourceState.ERROR
        elif state == "DISABLED":
            state = ResourceState.DISABLED
        self.update_internal(state=state)

        self.logger.info("Set resource %s state to %s" % (self.oid, state))
        return True

    #
    # patch
    #
    def pre_patch(self, *args, **kvargs):
        """check input params before resource patch."""
        return kvargs

    def do_patch(self, **params):
        """method to execute to make custom resource operations useful to complete patch

        :param params: custom params required by task
        :return:
        """
        pass

    def patch2(self, params, sync=False):
        """patch resource using a celery job or the synchronous function.

        :param params: custom params required by task
        :param sync: if True run sync task, if False run async task [default=False]
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
                 for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource patch")
        else:
            self.logger.debug("run async resource patch")

        # verify permissions
        self.verify_permisssions("patch")

        # clean cache
        self.clean_cache()

        # verify resource status
        if self.get_base_state() not in ["ACTIVE", "ERROR", "UNKNOWN"]:
            raise ApiManagerError(
                "resource %s %s is not in a valid state" % (self.objname, self.oid),
                code=400,
            )

        # run an optional pre patch function
        params = self.pre_patch(**params)
        self.logger.debug("params after pre patch: %s" % params)

        # change resource state
        self.update_state(ResourceState.UPDATING)

        # run resource method that launch task or exec operation sync
        res = self.do_patch(params, sync=sync)

        # run final delete is method is sync
        if sync is True:
            res = {"uuid": self.uuid}, 201
        else:
            res[0]["uuid"] = self.uuid

        self.logger.debug("end resource patch with result: %s" % res[0])

        return res

    @trace(op="patch")
    def patch(self, **params):
        """Patch resource using a celery job or the synchronous function patch_resource.

        :param params: custom params required by task
        :param params.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        sync = params.pop("sync", False)
        # verify permissions
        self.verify_permisssions("patch")

        # change resource state
        self.update_state(ResourceState.UPDATING)

        # run an optional pre patch function
        params = self.pre_patch(**params)
        self.logger.debug("params after pre udpate: %s" % params)

        # clean cache
        self.clean_cache()

        # force patch with internal patch
        force = params.pop("force", False)
        self.logger.debug("Force patch: %s" % force)

        # patch resource using async celery task
        if self.patch_task is not None and force is False:
            base_params = {
                # 'alias': '%s.patch' % self.name,
                "alias": "%s.patch" % self.__class__.__name__,
                "cid": self.container.oid,
                "id": self.oid,
                "uuid": self.uuid,
                "objid": self.objid,
                "ext_id": self.ext_id,
                "name": self.name,
            }
            base_params.update(params)
            params = base_params
            params.update(self.get_user())
            res = prepare_or_run_task(self, self.patch_task, params, sync=sync)
            self.logger.info("Patch resource using task %s" % res[0])
            return res

        # patch resource using sync method
        else:
            params.pop("tasks", None)
            self.patch_internal(**params)
            if "state" not in params:
                self.update_state(ResourceState.ACTIVE)
            return {"uuid": self.uuid}, 200

    @trace(op="patch")
    def patch_internal(self, **kvargs):
        """Patch resource

        :param kvargs: Params required by patch
        :raises ApiManagerError: if query empty return error.
        """
        # clean cache
        self.clean_cache()

        try:
            self.logger.debug("Patch %s %s with data %s" % (self.objdef, self.oid, kvargs))
            return self.uuid
        except TransactionError as ex:
            self.update_state(ResourceState.ERROR, error=str(ex))
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    #
    # delete
    #
    def pre_delete(self, *args, **kvargs):
        """check input params before resource delete."""
        return kvargs

    def do_delete(self, **params):
        """method to execute to make custom resource operations useful to complete delete

        :param params: custom params required by task
        :return:
        """
        pass

    def delete2(self, params, sync=False):
        """delete resource using a celery job or the synchronous function.

        :param params: custom params required by task
        :param sync: if True run sync task, if False run async task [default=False]
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource delete")
        else:
            self.logger.debug("run async resource delete")

        # verify permissions
        self.verify_permisssions("delete")

        # clean cache
        self.clean_cache()

        # verify resource status
        if self.get_base_state() not in ["ACTIVE", "ERROR", "UNKNOWN"]:
            raise ApiManagerError(
                "resource %s %s is not in a valid state" % (self.objname, self.oid),
                code=400,
            )

        # verify resource has no childs
        params["child_num"] = self.manager.count_resource(parent_id=self.oid)
        if params["child_num"] > 0:
            raise ApiManagerError("Resource %s has %s childs. It can not be deleted" % (self.oid, params["child_num"]))

        # run an optional pre delete function
        params = self.pre_delete(**params)
        self.logger.debug("params after pre delete: %s" % params)

        # change resource state
        self.update_state(ResourceState.EXPUNGING)

        # run resource method that launch task or exec operation sync
        res = self.do_delete(params, sync=sync)

        # run final delete is method is sync
        if sync is True:
            res = {"uuid": self.uuid}, 201
        else:
            res[0]["uuid"] = self.uuid

        self.logger.debug("end resource delete with result: %s" % res[0])

        return res

    @trace(op="delete")
    def delete(self, **params):
        """Delete resource using a celery job or the synchronous function delete_resource.

        :param params: custom params required by task
        :param params.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        sync = params.pop("sync", False)
        # verify permissions
        self.verify_permisssions("delete")

        # verify resource has no childs
        params["child_num"] = self.manager.count_resource(parent_id=self.oid)

        # run an optional pre delete function
        params = self.pre_delete(**params)
        self.logger.debug("params after pre delete: %s" % params)

        # clean cache
        self.clean_cache()

        # change resource state
        self.update_state(ResourceState.EXPUNGING)

        if params["child_num"] > 0:
            raise ApiManagerError("Resource %s has %s childs. It can not be deleted" % (self.oid, params["child_num"]))

        # delete resource using async celery task
        if self.delete_task is not None:
            # setup task params
            ext_id = self.ext_id
            if ext_id == "":
                ext_id = None
            params.update(
                {
                    # 'alias': '%s.delete' % self.name,
                    "alias": "%s.delete" % self.__class__.__name__,
                    "cid": self.container.oid,
                    "id": self.oid,
                    "uuid": self.uuid,
                    "objid": self.objid,
                    "ext_id": ext_id,
                }
            )
            params.update(self.get_user())
            res = prepare_or_run_task(self, self.delete_task, params, sync=sync)
            self.logger.info("Delete resource using task %s" % res[0])
            return res

        # delete resource using sync method
        else:
            params.pop("tasks", None)
            self.delete_internal()

            # run an optional post delete function
            self.post_delete(**params)

            return {"uuid": self.uuid}, 200

    @trace(op="delete")
    def delete_internal(self):
        """Soft delete resource"""
        # clean cache
        self.clean_cache()

        try:
            # delete resource
            name = "%s-%s-DELETED" % (self.name, id_gen())
            self.manager.delete_resource(oid=self.oid, name=name)

            self.logger.debug("Delete resource %s: %s" % (self.objdef, self.oid))
            return None
        except TransactionError as ex:
            self.update_state(ResourceState.ERROR, error=str(ex))
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    #
    # expunge
    #
    def pre_expunge(self, *args, **kvargs):
        """check input params before resource expunge."""
        return kvargs

    def do_expunge(self, **params):
        """method to execute to make custom resource operations useful to complete expunge

        :param params: custom params required by task
        :return:
        """
        pass

    def expunge2(self, params, sync=False):
        """expunge resource using a celery job or the synchronous function.

        :param params: custom params required by task
        :param sync: if True run sync task, if False run async task [default=False]
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if sync is True:
            self.logger.debug("run sync resource expunge")
        else:
            self.logger.debug("run async resource expunge")

        # verify permissions
        self.verify_permisssions("delete")

        # clean cache
        self.clean_cache()

        # verify resource status
        if str2bool(params.get("force")) is False and self.get_base_state() not in [
            "ACTIVE",
            "ERROR",
            "UNKNOWN",
        ]:
            raise ApiManagerError(
                "resource %s %s is not in a valid state" % (self.objname, self.oid),
                code=400,
            )

        # verify resource has no childs
        params["child_num"] = self.manager.count_resource(parent_id=self.oid)
        if params["child_num"] > 0:
            raise ApiManagerError("Resource %s has %s childs. It can not be expunged" % (self.oid, params["child_num"]))

        # run an optional pre expunge function
        params = self.pre_expunge(**params)
        self.logger.debug("params after pre expunge: %s" % params)

        # change resource state
        self.update_state(ResourceState.EXPUNGING)

        # run resource method that launch task or exec operation sync
        # res = self.do_expunge(params, sync=sync)
        res = self.do_expunge(**params)

        # run final expunge is method is sync
        if sync is True:
            res = {"uuid": self.uuid}, 201
        else:
            res[0]["uuid"] = self.uuid

        self.logger.debug("end resource expunge with result: %s" % res[0])

        return res

    @trace(op="delete")
    def expunge(self, **params):
        """Expunge resource using a celery job or the synchronous function expunge_internal.

        :param params: custom params required by task
        :param params.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        sync = params.pop("sync", False)
        # verify permissions
        self.verify_permisssions("delete")

        # verify resource has no childs
        params["child_num"] = self.manager.count_resource(parent_id=self.oid)

        # run an optional pre delete function
        params = self.pre_delete(**params)
        self.logger.debug("params after pre expunge: %s" % params)

        # clean cache
        self.clean_cache()

        # change resource state
        self.update_state(ResourceState.EXPUNGING)

        if params["child_num"] > 0:
            raise ApiManagerError("Resource %s has %s childs. It can not be expunged" % (self.oid, params["child_num"]))

        # delete resource using async celery task
        if self.expunge_task is not None:
            # setup task params
            ext_id = self.ext_id
            if ext_id == "":
                ext_id = None
            params.update(
                {
                    # 'alias': '%s.expunge' % self.name,
                    "alias": "%s.expunge" % self.__class__.__name__,
                    "cid": self.container.oid,
                    "id": self.oid,
                    "uuid": self.uuid,
                    "objid": self.objid,
                    "ext_id": ext_id,
                }
            )
            params.update(self.get_user())
            res = prepare_or_run_task(self, self.expunge_task, params, sync=sync)
            self.logger.info("Expunge resource using task %s" % res[0])
            return res

        # delete resource using sync method
        else:
            params.pop("tasks", None)
            self.expunge_internal()

            # run an optional post delete function
            self.post_delete(**params)

            return {"uuid": self.uuid}, 200

    @trace(op="delete")
    def expunge_internal(self):
        """Hard delete resource"""
        # clean cache
        self.clean_cache()

        # get links
        try:
            links = self.manager.get_resource_links_internal(self.oid)
        except QueryError as ex:
            self.logger.warning("No links found for resource %s" % self.oid)
            links = []

        # remove links
        for link in links:
            # prepare resource
            obj: ResourceLink = ResourceLink(
                self.controller,
                oid=link.id,
                objid=link.objid,
                name=link.name,
                model=link,
            )

            obj.expunge()
        self.logger.debug("Remove resource %s links: %s" % (self.name, links))

        try:
            # remove resource
            self.manager.expunge_resource(oid=self.oid)

            if self.register is True:
                # remove object and permissions
                self.deregister_object(self.objid.split("//"))
                self.logger.debug("Remove resource %s permissions" % self.oid)

            self.logger.debug("Expunge resource %s: %s" % (self.objdef, self.oid))
            return None
        except TransactionError as ex:
            self.update_state(ResourceState.ERROR, error=str(ex))
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)

    #
    # actions
    #
    def action(self, name, steps, log="Run action", check=None, *args, **kvargs):
        """Execute an action

        :param name: action name
        :param steps: list of steps to execute. Step can be a string with step name or a dict like
            {'step':<step name>, 'args':..}
        :param log: message to log [default='Run action']
        :param check: function used to check input params [optional]
        :param args: custom positional args
        :param kvargs: custom key value args
        :param kvargs.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        sync = kvargs.pop("sync", False)
        self.logger.debug("action - name: %s - sync: %s" % (name, sync))  # aaa

        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        # move in action_resource_pre_step
        # TRYFIX self.check_active()

        if check is not None:
            kvargs = check(*args, **kvargs)

        # clean cache
        self.clean_cache()

        # steps list
        run_steps = ["beehive_resource.task_v2.core.AbstractResourceTask.action_resource_pre_step"]
        run_steps.extend(steps)
        run_steps.append("beehive_resource.task_v2.core.AbstractResourceTask.action_resource_post_step")

        # manage params
        kvargs.update(
            {
                # 'alias': '%s.%s' % (self.name, name),
                "alias": "%s.%s" % (self.__class__.__name__, name),
                "cid": self.container.oid,
                "id": self.oid,
                "objid": self.objid,
                "name": self.name,
                "ext_id": self.ext_id,
                "parent": self.parent_id,
                "action_name": name,
                "steps": run_steps,
            }
        )
        kvargs.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, kvargs, sync=sync)
        self.logger.info("%s %s using task %s" % (log, self.oid, res[0]))
        return res

    #
    # child resources
    #
    @trace(op="view")
    def get_resources(self, *args, **kvargs):
        """Get child resources.

        :param resourcetags: list of tags comma separated. All tags in the list must be met [optional]
        :param objid: resource objid [optional]
        :param name: resource name [optional]
        :param ids: list of resource oid [optional]
        :param uuids: comma separated list of resource uuid [optional]
        :param ext_id: id of resource in the remote container [optional]
        :param ext_ids: list of id of resource in the remote container [optional]
        :param type: comma separated resource type. Use complete syntax or %<type1>% for eachtype [optional]
        :param container: resource container id [optional]
        :param attribute: resource attribute [optional]
        :param parent: parent id [optional]
        :param parent_list: comma separated parent id list [optional]
        :param parents: dict with {'parent_id':{'id':.., 'name':.., 'uuid':..}} [default=None]
        :param active: active [optional]
        :param state: state [optional]
        :param creation_date: creation_date [optional]
        :param modification_date: modification_date [optional]
        :param show_expired: if True show expired resources [default=False]
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param objdef: object definition. Use to limit pertag to only used for objdef [optional]
        :param entity_class: entity_class you expect to receive [optional]
        :param details: if True execute customize_list()
        :param run_connect: if True run connect for each container [default=True]
        :param run_customize: if True run customize [default=True]
        :return: :py:class:`list` of :class:`Resource`
        :raise ApiManagerError:
        """
        parents = {self.oid: {"id": self.oid, "name": self.name, "uuid": self.uuid}}
        res, total = self.container.get_resources(parent=self.oid, parents=parents, *args, **kvargs)

        return res, total

    def resource_factory(
        self,
        resource_class,
        name,
        desc="",
        ext_id=None,
        active=True,
        attribute={},
        tags="",
        **params,
    ):
        """Factory used to create new resource.

        :param resource_class: class of resource to create or string representation
        :param name: resource name
        :param desc: resource desc
        :param ext_id: [default=None]
        :param active: [default=True],
        :param attribute: [default={}],
        :param parent: [default=None]
        :param tags: comma separated resource tags to assign [default='']
        :param params: custom params required by task or function
        :return: {'jobid': celery task instance id, 'uuid': resource uuid} or {'uuid': resource uuid}
        :rtype: Task or str
        :raises ApiManagerError: if query empty return error.
        :raises ApiManagerError: if query empty return error.
        """
        return self.container.resource_factory(
            resource_class,
            name,
            desc,
            ext_id,
            active,
            attribute,
            self.oid,
            tags,
            **params,
        )

    #
    # tags
    #
    def add_tag(self, value, *args, **kvargs):
        """Add tag

        :param value: tag value
        :return: True if operation is successful
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        # check authorization
        self.verify_permisssions("update")

        # get tag
        tag = self.controller.get_tag(value)

        try:
            res = self.manager.add_resource_tag(self.model, tag.model)
            self.logger.info("Add tag %s to resource %s: %s" % (value, self.name, res))
            return res
        except TransactionError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=400)

    def remove_tag(self, value, *args, **kvargs):
        """Remove tag

        :param value str: tag value
        :return: True if operation is successful
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        # check authorization
        self.verify_permisssions("update")

        # get tag
        tag = self.controller.get_tag(value)

        try:
            res = self.manager.remove_resource_tag(self.model, tag.model)
            self.logger.info("Remove tag %s from resource %s: %s" % (value, self.name, res))
            return res
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    #
    # links
    #
    def is_linked(self, resource_id):
        """Verify if resource is linked with it

        :param resource_id: resource id
        :return: True if is linked
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        try:
            res1 = self.manager.is_linked(self.oid, resource_id)
            res2 = self.manager.is_linked(resource_id, self.oid)
            res = res1 or res2
            self.logger.info("Check resource %s is linked to resource %s: %s" % (self.oid, resource_id, res))
            return res
        except QueryError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="view")
    def get_links(self, *args, **kvargs):
        """Get links.

        :param type: link type [optional]
        :param resourcetags: list of tags. All tags in the list must be met [optional]
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """
        return self.controller.get_links(resource=self.oid, *args, **kvargs)

    @trace(op="view")
    def get_out_links(self, *args, **kvargs):
        """Get links from resource.

        :param start_resource: start resource id or uuid [optional]
        :param end_resource: end resource id or uuid [optional]
        :param resource: resource id or uuid [optional]
        :param type: link type [optional]
        :param resourcetags: list of tags. All tags in the list must be met [optional]
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """
        return self.controller.get_links(start_resource=self.oid, *args, **kvargs)

    @trace(op="view")
    def get_links_with_cache(self, link_type=None, *args, **kvargs):
        """Get resource links using also cache info. Permissions are not verified. Use this method for internal usage

        :param link_type: link type [optional]
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """
        res = []
        links = self.manager.get_links_with_cache(self.oid, link_type=link_type)
        for link in links:
            if link_type is not None and link.type != link_type:
                continue
            obj = ResourceLink(
                self.controller,
                oid=link.id,
                objid=link.objid,
                name=link.name,
                active=link.active,
                desc=link.desc,
                model=link,
            )
            res.append(obj)

        self.logger.info("Get resource %s links with cache: %s" % (self.oid, truncate(res)))
        return res

    @trace(op="view")
    def get_linked_resources(
        self,
        link_type=None,
        link_type_filter=None,
        container=None,
        type=None,
        *args,
        **kvargs,
    ):
        """Get linked resources

        :param type: resource type [optional]
        :param container: container id, name or uuid [optional]
        :param link_type: link type [optional]
        :param link_type_filter: link type filter
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param objdef: object definition. Use to limit pertag to only used for objdef [optional]
        :param entity_class: entity_class you expect to receive [optional]
        :param run_customize: if True run customize [default=True]
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs):
            # get filter field
            # container = kvargs.pop('container', None)

            container_id = None
            if container is not None:
                container_id = self.controller.get_container(container).oid
            if type is not None:
                types = self.manager.get_resource_types(filter=type)
                kvargs["types"] = [t.id for t in types]

            res, total = self.manager.get_linked_resources(
                resource=self.oid,
                link_type=link_type,
                link_type_filter=link_type_filter,
                container_id=container_id,
                *args,
                **kvargs,
            )

            return res, total

        def customize(entities, *args, **kvargs):
            return self.controller.customize_resource(entities, *args, **kvargs)

        res, total = self.controller.get_paginated_entities(
            "resource", get_entities, customize=customize, *args, **kvargs
        )
        self.logger.info("Get linked resources: %s" % res)
        return res, total

    @trace(op="view")
    def get_linked_resources_with_cache(self, link_type=None, *args, **kvargs):
        """Get linked resources using also cache info. Permissions are not verified. Use this method for internal
        usage

        :param link_type: link type
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """
        res = []
        entities = self.manager.get_linked_resources_with_cache(ResourceWithLink, self.oid, link_type=link_type)
        for entity in entities:
            objclass = import_class(entity.type.objclass)
            obj = objclass(
                self.controller,
                oid=entity.id,
                objid=entity.objid,
                name=entity.name,
                active=entity.active,
                desc=entity.desc,
                model=entity,
            )
            obj.link_attr = entity.link_attr
            obj.link_type = entity.link_type
            obj.link_creation = entity.link_creation
            res.append(obj)

        self.logger.info("Get resource %s linked resources: %s" % (self.oid, truncate(res)))
        return res

    @trace(op="insert")
    def add_link(self, name=None, type=None, end_resource=None, attributes=None):
        """Add resource links

        :param name: link name
        :param type: link type
        :param end_resource: end resource reference id, uuid
        :param attributes: link attributes [optional]
        :return: link uuid
        :raise ApiManagerError:
        """
        if attributes is None:
            attributes = {}

        # get resource
        end_resource_id = self.controller.get_simple_resource(end_resource).oid

        try:
            objid = id_gen()
            attributes = json.dumps(attributes)
            link = self.manager.add_link(objid, name, type, self.oid, end_resource_id, attributes=attributes)

            # add object and permission
            ResourceLink(self.controller, oid=link.id).register_object([objid], desc=name)

            self.logger.info("Add new link %s to resource %s" % (name, self.oid))
            return link.uuid
        except TransactionError as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=ex.code)
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise ApiManagerError(ex, code=400)

    @trace(op="delete")
    def del_link(self, end_resource):
        """Delete a link that terminate on the end_resource

        :param end_resource: end resource name or id
        :return: link id
        """
        links, tot = self.controller.get_links(start_resource=self.oid, end_resource=end_resource)
        for link in links:
            link.expunge()
        return True

    def resource(self, method, uri, data=""):
        """Interact with resource using api exposed by resource module

        :param method: http method
        :param data: http POST, PUT data
        """
        if data != "":
            data = json.dumps(data)
        res = self.api_client.admin_request("resource", uri, method, data)
        return res

    #
    # internal resource tagging
    #
    def create_default_tag(self):
        """Create default cloud domain tag"""
        # create tag
        self.container.controller.add_tag(self.tag_name)
        # assign tag to itself
        self.add_tag(self.tag_name)

    def remove_default_tag(self):
        """Remove default cloud domain tag"""
        try:
            # deassign tag from itself
            self.remove_tag(self.tag_name)
            # get tag
            tag = self.container.controller.get_tag(self.tag_name)
            # remove tag
            tag.remove()
        except:
            self.logger.warning(exc_info=False)
            self.logger.warning("Resource tag %s does not exist" % self.tag_name)

    def assign_tag_to_resources(self, resources):
        """Assign internal tag to child resources

        :param resources: list of resource id
        """
        self.logger.info("Assign tag %s to resources %s" % (self.tag_name, resources))
        for item in resources:
            resource = self.controller.get_simple_resource(int(item))
            resource.add_tag(self.tag_name)

    def remove_tag_from_resources(self, resources):
        """Deassign internal tag to child resources

        :param resources: list of resource id
        """
        self.logger.info("Deassign tag %s from resources %s" % (self.tag_name, resources))
        for item in resources:
            resource = self.controller.get_simple_resource(int(item))
            resource.remove_tag(self.tag_name)

    def get_tagged_child_resources(self, restype=None):
        """Get a list of child resources

        TODO

        :param restype: resource type [optional]
        :return: List of resource instance
        :rtype: list
        :raises ApiManagerError: if query empty return error.
        """
        try:
            tags = [self.tag_name]
            if restype is not None:
                tags.append(restype)
            resources = self.controller.get_resources(tags=tags)
        except:
            self.logger.warning(exc_info=False)
            resources = []

        self.logger.info("Get %s %s child resources: %s" % (self.objdef, self.oid, truncate(resources)))
        return resources

    #
    # metrics
    #
    def get_metrics(self):
        """Get resource metrics

        :return: list of metrics
        """
        return {}


class AsyncResource(Resource):
    """Basic async resource"""

    objtask_version = "v2"

    task_path = "beehive_resource.task_v2.core.AbstractResourceTask."

    create_task = "beehive_resource.task_v2.core.resource_add_task"
    # clone_task = 'beehive_resource.task_v2.core.resource_clone_task'
    import_task = "beehive_resource.task_v2.core.resource_import_task"
    update_task = "beehive_resource.task_v2.core.resource_update_task"
    patch_task = "beehive_resource.task_v2.core.resource_patch_task"
    delete_task = "beehive_resource.task_v2.core.resource_delete_task"
    expunge_task = "beehive_resource.task_v2.core.resource_expunge_task"
    action_task = "beehive_resource.task_v2.core.resource_action_task"

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used  in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            AsyncResource.task_path + "create_resource_pre_step",
            AsyncResource.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            self.task_path + "update_resource_pre_step",
            self.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            self.task_path + "expunge_resource_pre_step",
            self.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs


class AsyncResourceV3(Resource):
    """Basic async resource with async internal methods"""

    objtask_version = "v3"


class CustomResource(Resource):
    """Custom resource"""

    objdef = "Container.CustomResource"
    objuri = "custom-resources"
    objname = "costomresources"
    objdesc = "Custom resource"


class ResourceTag(ApiObject):
    """Resource tag"""

    objtype = "resource"
    objdef = "ResourceTag"
    objuri = "resourcetags"
    objdesc = "Resource tag"

    def __init__(self, *args, **kvargs):
        ApiObject.__init__(self, *args, **kvargs)

        self.update_object = self.manager.update_tag
        self.expunge_object = self.manager.purge  # self.manager.delete_tag

        if self.model is not None:
            self.resources = self.model.__dict__.get("resources", None)
            self.containers = self.model.__dict__.get("containers", None)
            self.links = self.model.__dict__.get("links", None)

    def info(self):
        """Get tag info

        :return: Dictionary with tag info.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ApiObject.info(self)
        if self.resources is not None:
            info.update(
                {
                    "resources": self.resources,
                    "containers": self.containers,
                    "links": self.links,
                }
            )
        return info

    def detail(self):
        """Get resource details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = []
        cont = []

        info = ApiObject.info(self)
        info["resources"] = res
        info["containers"] = cont
        return info


class ResourceLink(ApiObject):
    """ """

    objtype = "resource"
    objdef = "ResourceLink"
    objuri = "resourcelinks"
    objdesc = "Resource link"

    def __init__(self, *args, **kvargs):
        ApiObject.__init__(self, *args, **kvargs)

        self.start_node = None
        self.end_node = None
        self.type = None
        self.attribs = None
        if self.model is not None:
            self.type = self.model.type

        self.set_attribs()

        self.update_object = self.manager.update_link
        self.expunge_object = self.manager.purge

    def set_attribs(self):
        """Set attributes

        :param attributes: attributes
        """
        if self.model is not None:
            self.attribs = {}
            if self.model is not None and self.model.attributes is not None:
                try:
                    self.attribs = json.loads(self.model.attributes)
                except Exception:
                    pass

    def get_attribs(self, key=None, default=None):
        """Get attributes

        :param key: key to search in attributes dict [optional]
        :param default: default value [default=None]
        :return: attributes value
        """
        res = self.attribs
        if key is not None:
            res = dict_get(res, key, default=default)
        return res

    def get_reuse(self):
        """Get resource reuse value"""
        return self.attribs.get("reuse", False)

    def small_info(self):
        """Get resource small infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ApiObject.small_info(self)
        return info

    def info(self):
        """Get resource link infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ApiObject.info(self)

        # get start and end resources
        # start_resource = self.controller.get_simple_resource(self.model.start_resource_id)
        # end_resource = self.controller.get_simple_resource(self.model.end_resource_id)

        info["details"] = {
            "attributes": self.attribs,
            "type": self.model.type,
            "start_resource": self.model.start_resource_id,
            "end_resource": self.model.end_resource_id
            # 'start_resource': start_resource.small_info(),
            # 'end_resource': end_resource.small_info()
        }

        return info

    def detail(self):
        """Get resource link details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ApiObject.info(self)

        # get start and end resources
        start_resource = self.controller.get_simple_resource(self.model.start_resource_id)
        end_resource = self.controller.get_simple_resource(self.model.end_resource_id)

        info["details"] = {
            "attributes": self.attribs,
            "type": self.model.type,
            "start_resource": start_resource.small_info(),
            "end_resource": end_resource.small_info(),
        }

        return info

    def get_start_resource(self):
        """Get start resource

        :param details: if True get details
        :return: resource instance
        """
        return self.controller.get_resource(self.model.start_resource_id)

    def get_start_simple_resource(self):
        """Get start resource without customization

        :param details: if True get details
        :return: resource instance
        """
        return self.controller.get_simple_resource(self.model.start_resource_id)

    def get_end_resource(self):
        """Get end resource

        :param details: if True get details
        :return: resource instance
        """
        return self.controller.get_resource(self.model.end_resource_id)

    def get_end_simple_resource(self):
        """Get end resource without customization

        :param details: if True get details
        :return: resource instance
        """
        return self.controller.get_simple_resource(self.model.end_resource_id)

    def pre_update(self, **kvargs):
        """Pre change function. Extend this function to manipulate and validate input params.

        :param name: link name
        :param ltype: link type
        :param start_resource: start resource reference id, uuid
        :param end_resource: end resource reference id, uuid
        :param attributes: link attributes [default={}]
        :return: kvargs
        :raise ApiManagerError:
        """
        # get resources
        start_resource = kvargs.pop("start_resource", None)
        if start_resource is not None:
            kvargs["start_resource_id"] = self.controller.get_simple_resource(start_resource).oid
        end_resource = kvargs.pop("end_resource", None)
        if end_resource is not None:
            kvargs["end_resource_id"] = self.controller.get_simple_resource(end_resource).oid
        attributes = kvargs.pop("attributes", None)
        if attributes is not None:
            kvargs["attributes"] = json.dumps(attributes)

        return kvargs

    #
    # tags
    #
    @trace(op="tag-assign.update")
    def add_tag(self, value, *rags, **kvargs):
        """Add tag

        :param value str: tag value
        :return: True if operation is successful
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        # check authorization
        self.verify_permisssions("update")

        # get tag
        tag = self.controller.get_tag(value)

        try:
            res = self.manager.add_link_tag(self.model, tag.model)
            self.logger.info("Add tag %s to link %s: %s" % (value, self.name, res))
            return res
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="tag-deassign.update")
    def remove_tag(self, value, *rags, **kvargs):
        """Remove tag

        :param value str: tag value
        :return: True if operation is successful
        :rtype: bool
        :raises ApiManagerError: if query empty return error.
        """
        # check authorization
        self.verify_permisssions("update")

        # get tag
        tag = self.controller.get_tag(value)

        try:
            res = self.manager.remove_link_tag(self.model, tag.model)
            self.logger.info("Remove tag %s from link %s: %s" % (value, self.name, res))
            return res
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)
