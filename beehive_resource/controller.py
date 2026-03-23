# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from inspect import getfile, isclass
from logging import getLogger
from os import path
from typing import Tuple, List, Callable, Dict, Any, Optional, TYPE_CHECKING
import ujson as json
from beecell.db import QueryError, TransactionError
from beecell.simple import import_class, jsonDumps
from beecell.types.type_date import format_date
from beecell.types.type_id import id_gen
from beecell.types.type_string import compat
from beehive.common.apimanager import ApiController, ApiManagerError
from beehive.common.data import trace, operation, cache

from beehive_resource.container import (
    ResourceLink,
    ResourceTag,
    ResourceContainer,
    Resource,
)
from beehive_resource.model import (
    ResourceDbManager,
    Resource as ModelResource,
    ResourceTag as ModelResourceTag,
    ResourceLink as ModelResourceLink,
    Container as ModelContainer,
    ContainerState,
)
if TYPE_CHECKING:
    from beehive_resource.plugins.awx.entity.awx_project import AwxProject
    from beehive_resource.typing_extras.common.sqlalchemy_row_queries import (
        ResourceDbManager_DirectedLinkedResourcesInternal_Return
    )

logger = getLogger(__name__)


class ResourceController(ApiController):
    """Resource Module controller.

    :param ApiModule module: beehive module instance
    """

    version = "v1.0"  #: version
    manager: 'ResourceDbManager'

    def __init__(self, module):
        ApiController.__init__(self, module)

        #: db manager reference
        self.manager = ResourceDbManager(cache_manager=self.module.api_manager.cache_manager)
        #: container class list
        self.container_classes = {}
        #: child class list
        self.child_classes = [ResourceContainer, Resource, ResourceTag, ResourceLink]
        #: container list
        self.containers = {}

        # init static resources and templates
        clspath = path.dirname(getfile(ResourceController))
        app = module.api_manager.app
        if app is not None:
            app.template_folder = f"{clspath}/templates"
            # app.static_folder = '%s/static' % clspath
            # app.static_url_path = '/console/static'

    def add_container_class(self, name, container_class):
        self.container_classes[name] = container_class

    def get_container_class(self, name):
        return self.container_classes[name]

    def init_object(self):
        """Register object types, objects and permissions related to module.
        Call this function when initialize system first time.
        """
        # register containers
        for container_class in self.container_classes.values():
            container_class(self).init_object()

        ApiController.init_object(self)

    def register_async_methods(self):
        super().register_async_methods()
        for container_class in self.container_classes.values():
            container_class(self).register_async_methods()

    def convert_timestamp(self, timestamp):
        """ """
        timestamp = datetime.fromtimestamp(timestamp)
        return format_date(timestamp)

    def check_authorization(self, objtype, objdef, objid, action):
        """Method override to check user is SuperAdmin"""
        try:
            from beehive.common.audit import localAudit
            from beehive.common.apimanager import ApiMethod
            force = objdef != ApiMethod.objdef
            localAudit().set_objid(objid=objid, objdef=objdef, force=force)
        except Exception as ex:
            logger.error(ex)

        if operation.authorize is False:
            return True

        if not self.is_admin_resource():
            raise ApiManagerError("You are not SuperAdmin", code=403)

        self.logger.debug2("Check authorization OK")
        return True # TODO check

    #
    # count
    #
    def count_all_containers(self):
        """Get all containers count"""
        return self.manager.count_container()

    def count_all_resources(self):
        """Get all resources count"""
        return self.manager.count_resource()

    def count_all_tags(self):
        """Get all resource tags count"""
        return self.manager.count_tags()

    def count_all_links(self):
        """Get all resource links count"""
        return self.manager.count_links()

    #
    # class selector
    #
    def is_class_task_version_v2(self, entity_class):
        """check if class implements task version 2 or 1

        :param entity_class: entity class or entity_class full name
        :return: True or False
        """
        # entity class is the full name
        if isclass(entity_class) is False:
            entity_class = import_class(entity_class)
        if entity_class.objtask_version == "v2" or entity_class.objtask_version is None:
            return True
        return False

    def is_class_task_version_v3(self, entity_class):
        """check if class implements task version 3

        :param entity_class: entity class or entity_class full name
        :return: True or False
        """
        # entity class is the full name
        if isclass(entity_class) is False:
            entity_class = import_class(entity_class)
        if entity_class.objtask_version == "v3":
            return True
        return False

    def is_monitoring_enabled(self, filter_name):
        return self.manager.is_monitoring_enabled(filter_name)

    def get_entity_for_task(self, entity_class, oid, *args, **kvargs):
        """Get single entity usable bya a celery task

        :param entity_class: Controller ApiObject Extension class
        :param oid: entity id
        :return: entity instance
        :raise ApiManagerError`:
        """
        model = None
        if entity_class == Resource:
            model = ModelResource
        elif issubclass(entity_class, Resource) is True:
            model = ModelResource
        elif entity_class == ResourceContainer:
            model = ModelContainer
        elif issubclass(entity_class, ResourceContainer) is True:
            model = ModelContainer
        entity = self.manager.get_entity(model, oid, *args, **kvargs)
        int_entity_class = import_class(entity.type.objclass)
        res = int_entity_class(
            self,
            oid=entity.id,
            objid=entity.objid,
            name=entity.name,
            active=entity.active,
            desc=entity.desc,
            model=entity,
        )

        # if it is a resource subclass set container and run post_get
        if model == ModelResource:
            container = self.get_container(entity.container_id)
            res.set_container(container)
            res.post_get()

        self.logger.debug("get %s : %s", int_entity_class.__name__, res)
        return res

    def get_entity_v2(
        self,
        model_class,
        oid,
        entity_class=None,
        customize: Optional[ Callable[[ 'Resource', Tuple[Any, ...], Dict[str, Any]], 'Resource'] ]=None,
        run_customize=True,
        *args,
        **kvargs,
    ) -> 'Resource':
        """Get single entity by oid (id, uuid, name) if exists

        :param entity_class: Controller ApiObject Extension class. Specify when you want to verify match between
            objdef of the required resource and find resource. [optional]
        :param model_class: Model ApiObject Extension class
        :param oid: entity model id or name or uuid
        :param customize: function used to customize entity. Signature def customize(entity, *args, **kvargs)
        :param run_customize: if True run customize [default=True]
        :param kvargs: additional filters [optional]
        :param kvargs.cache: if True use cache [default=True]
        :return: entity instance
        :raise ApiManagerError`:
        """
        l_cache = kvargs.pop("cache", True)
        self.logger.debug("+++++ cache: %s", l_cache)

        entity = None
        if l_cache:
            entity = self.manager.get_entity_with_cache(model_class, oid, *args, **kvargs)

        # If no cache or cache fail
        if entity is None:
            try:
                entity = self.manager.get_entity(model_class, oid, *args, **kvargs)
                if entity is None:
                    self.logger.error("Resource %s not found", oid)
                    raise ApiManagerError(f"Resource {oid} not found", code=404)
                if entity_class is not None:
                    int_entity_class = entity_class
                else:
                    int_entity_class = import_class(entity.type.objclass)
            except QueryError as ex:
                raise ApiManagerError(f"Resource {oid} not found", code=404) from ex

        if entity_class is not None:
            int_entity_class = entity_class
        else:
            int_entity_class = import_class(entity.type.objclass)

        # check objdef match with required
        if entity_class is not None and entity.type.value != entity_class.objdef:
            raise ApiManagerError(f"Resource {entity_class.objname} {oid} not found", code=404)

        res = int_entity_class(
            self,
            oid=entity.id,
            objid=entity.objid,
            name=entity.name,
            active=entity.active,
            desc=entity.desc,
            model=entity,
        )

        # customize entity
        if run_customize is True and customize is not None:
            res = customize(res, *args, **kvargs)

        self.logger.debug("Get %s : %s", int_entity_class.__name__, res)
        return res

    def get_paginated_entities(
        self,
        objtype,
        get_entities: Callable[[Tuple['Any', ...], Dict[str, Any]],Tuple[List['ModelResource'],int]],
        page=0,
        size=10,
        order="DESC",
        field="id",
        customize: Optional[ Callable[[ List['Resource'], Tuple[Any, ...], Dict[str, Any] ], List['Resource']] ]=None,
        run_customize=True,
        objdef=None,
        entity_class=None,
        *args,
        **kvargs,
    ) -> Tuple[List['Resource'],int]:
        """ Method override to check user is SuperAdmin
        Get entities with pagination

        :param authorize: if False disable authorization check
        :param objtype: objtype to use. Example container, resource
        :param objdef: obj definition to use. Example vsphere.datacenter.folder [optional]
        :param get_entities: model get_entities function. Return (entities, total)
        :param name: name like [optional]
        :param active: active [optional]
        :param creation_date: creation_date [optional]
        :param modification_date: modification_date [optional]
        :param page: objects list page to show [default=0]
        :param size: number of objects to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param customize: function used to customize entities. Signature def customize(entities, *args, **kvargs)
        :param run_customize: if True run customize [default=True]
        :param entity_class: entity_class you expect to receive [optional]
        :param args: custom params
        :param kvargs: custom params
        :return: (list of entity instances, total)
        :raise ApiManagerError:
        """
        res = []
        tags = []

        if entity_class is not None and objdef is not None and entity_class.objdef != objdef:
            raise ApiManagerError("entity_class objdef and objdef mismatch")

        if operation.authorize is False or kvargs.get("authorize", True) is False:
            kvargs["with_perm_tag"] = False
            self.logger.debug("Authorization disabled for command")
        elif operation.authorize is True:
            # verify permissions
            if not self.is_admin_resource():
                raise ApiManagerError("You are not SuperAdmin", code=403)

        if not get_entities:
            raise Exception("get_entities missing. function must be specified")

        try:
            entities: List['ModelResource'] = []
            total: int = 0
            entities, total = get_entities(
                tags=tags,
                page=page,
                size=size,
                order=order,
                field=field,
                *args,
                **kvargs,
            )

            # total = 0
            for entity in entities:
                if entity_class is None:
                    objclass = import_class(entity.type.objclass)
                else:
                    objclass = entity_class

                if objclass is None:
                    self.logger.debug("+++++ entity_class %s", entity_class)
                    self.logger.debug("+++++ entity.type %s", entity.type)
                    self.logger.debug("+++++ entity.type.objclass %s", entity.type.objclass)

                # bypass object that does not match objdef
                if objdef is not None and objclass.objdef != objdef:
                    total -= 1
                    continue

                obj = objclass(
                    self,
                    oid=entity.id,
                    objid=entity.objid,
                    name=entity.name,
                    active=entity.active,
                    desc=entity.desc,
                    model=entity,
                )
                res.append(obj)
                # total += 1
            # customize entities
            if run_customize is True and customize is not None:
                res = customize(res, tags=tags, *args, **kvargs)

            self.logger.debug("Get %s (total:%s): %s", objtype, total, res)
            return res, total
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return [], 0

    #
    # container
    #
    def get_container_types(self):
        """Get container types"""
        objs = self.manager.get_container_type()
        res = [{"id": t.id, "category": t.category, "type": t.value} for t in objs]

        return res

    @staticmethod
    @cache("container.get", ttl=86400)
    def get_container_data(controller, container_id, *args, **kvargs):
        res = {
            "id": container_id,
            "uuid": None,
            "name": None,
            "desc": None,
            "objid": None,
            "active": None,
            "connection": None,
        }
        if container_id is None:
            return res
        try:
            entity = controller.manager.get_entity(ModelContainer, container_id)
            res = {
                "id": entity.id,
                "uuid": entity.uuid,
                "name": entity.name,
                "desc": entity.desc,
                "objid": entity.objid,
                "active": entity.active,
                "connection": json.loads(entity.connection),
            }
            return res
        except:
            logger.warning("", exc_info=True)
            return res

    @trace(entity="ResourceContainer", op="view")
    def get_container(self, oid, cache=True, connect=True, **kvargs) -> 'ResourceContainer':
        """Get single container.

        :param oid: entity model id, name or uuid
        :param bool cache: if True use the last containers list cached
        :param bool connect: if True setup remote platform connection
        :param kvargs: additional params
        :return: container instance
        :raise ApiManagerError:
        """
        if cache is True:
            try:
                entity = self.manager.get_entity(ModelContainer, oid)
                if entity is None:
                    raise QueryError(f"Container {oid} not found")
                entity_class = import_class(entity.type.objclass)

                # check authorization
                if operation.authorize is True:
                    self.check_authorization(entity_class.objtype, entity_class.objdef, entity.objid, "view")

                if entity.id not in self.containers:
                    container: 'ResourceContainer' = entity_class(
                        self,
                        oid=entity.id,
                        name=entity.name,
                        objid=entity.objid,
                        desc=entity.desc,
                        active=entity.active,
                        model=entity,
                    )
                    self.containers[entity.id] = container
                    self.logger.debug("Cache container %s", oid)
                else:
                    self.containers[entity.id].model = entity
                    self.logger.debug("Get container %s from cache", oid)

                container = self.containers[entity.id]
                # get connection
                if connect is True:
                    container.get_connection(**kvargs)
                return container
            except QueryError as ex:
                raise ApiManagerError(f"Container {oid} not found", code=404) from ex
        else:
            entity = self.manager.get_entity(ModelContainer, oid)
            entity_class = import_class(entity.type.objclass)

            # check authorization
            if operation.authorize is True:
                self.check_authorization(entity_class.objtype, entity_class.objdef, entity.objid, "view")

            container = entity_class(
                self,
                oid=entity.id,
                name=entity.name,
                objid=entity.objid,
                desc=entity.desc,
                active=entity.active,
                model=entity,
            )
            self.containers[entity.id] = container
            self.logger.debug("Get container %s", oid)

            # get connection
            if connect is True:
                container.get_connection(**kvargs)
            return container

    @trace(entity="ResourceContainer", op="view")
    def get_containers(self, *args, **kvargs):
        """Get containers.

        :param container_type: container type [optional]
        :param state: container state [optional]
        :param desc: container desc [optional]
        :param resourcetags: list of tags comma separated. All tags in the list must be met [optional]
        :param creation_date: creation_date [optional]
        :param modification_date: modification_date [optional]
        :param page users list page to show [default=0]
        :param size number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list or Container
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs):
            if "container_type" in kvargs:  # orchestrator, provider, ...
                kvargs["type_id"] = self.manager.get_container_type(category=kvargs.get("container_type"))[0].id
            elif "container_type_name" in kvargs:  # value column in container_type
                kvargs["type_id"] = self.manager.get_container_type(value=kvargs.get("container_type_name"))[0].id
            containers, total = self.manager.get_containers(*args, **kvargs)

            return containers, total

        def customize(res, *args, **kvargs):
            return res

        res, total = self.get_paginated_entities("container", get_entities, customize=customize, *args, **kvargs)
        return res, total

    @trace(entity="ResourceContainer", op="insert")
    def add_container(self, type=None, name=None, desc=None, conn=None):
        """Add new container

        :param type: container type
        :param name: container name
        :param desc: container desc
        :param conn: container connection
        :return: container uuid
        :raise ApiManagerError:
        """
        conn = conn or {}

        container_class = self.get_container_class(type)
        self.logger.debug("Get container_class %s", container_class)

        # check authorization
        self.check_authorization(container_class.objtype, container_class.objdef, None, "insert")

        if self.manager.exist_entity(ModelContainer, name) is True:
            raise ApiManagerError(f"Container {name} already exists")

        # call pre create
        kvargs = container_class.pre_create(controller=self, type=type, name=name, desc=desc, active=False, conn=conn)
        name = kvargs.get("name")
        desc = kvargs.get("desc")
        active = kvargs.get("active")
        conn = jsonDumps(kvargs.get("conn", {}))
        objid = id_gen()

        try:
            # create container reference
            ctype = self.manager.get_container_type(value=container_class.objdef, category=container_class.category)[0]
        except QueryError as exc:
            raise ApiManagerError(f"Container type {container_class.__name__} does not exist", code=404) from exc

        try:
            res = self.manager.add_container(objid, name, ctype, conn, desc, active)
            self.manager.update_container_state(res.id, ContainerState.BUILDING)
        except TransactionError as exc:
            raise ApiManagerError(f"Container {name} already exists", code=409) from exc

        # create object and permission
        container = container_class(
            self,
            oid=res.id,
            objid=id_gen(),
            name=name,
            desc=desc,
            active=active,
            model=res,
        )
        container.register_object([objid], desc=container.desc)

        # call post create
        container_class.post_create(controller=self, container=container)

        try:
            self.manager.update_container(oid=res.id, state=ContainerState.ACTIVE, active=True)
        except TransactionError as exc:
            self.manager.update_container_state(res.id, ContainerState.ERROR)
            raise ApiManagerError(exc, code=400) from exc

        self.logger.debug("Add container %s %s", container_class.__name__, name)
        return res.uuid

    #
    # resource
    #
    @trace(entity="Resource", op="view")
    def index_resources_by_id(self, entity_class=None):
        """Get indexed resources. This method does not verify authorization. Use only for internal assignment.

        :param entity_class: parent resource class [optional]
        :return: dictionary {'parent_id':{'id':.., 'uuid':.., 'name':..}}
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        try:
            if entity_class is not None:
                l_type = entity_class.objdef
            else:
                l_type = None
            entities = self.manager.get_resources_by_type(type=l_type)
            resp = {}
            for entity in entities:
                entity_class = import_class(entity.type.objclass)
                res = entity_class(
                    self,
                    oid=entity.id,
                    objid=entity.objid,
                    name=entity.name,
                    active=entity.active,
                    desc=entity.desc,
                    model=entity,
                )
                resp[entity.id] = res
                resp[entity.uuid] = res
            self.logger.debug("Index resources by id: %s", resp)
            return resp
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return None

    @trace(entity="Resource", op="view")
    def index_resources_by_extid(self, entity_class=None, container=None):
        """Get resources indexed by remote platform id

        :param container: container id. [optional]
        :param entity_class: parent resource class [optional]
        :return: list of Resource instances
        :raise ApiManagerError:
        """
        try:
            if entity_class is not None:
                types = [entity_class.objdef]
            else:
                types = None
            entities = self.manager.get_resources_by_type(types=types, container=container)
            resp = {}
            for entity in entities:
                entity_class = import_class(entity.type.objclass)
                res = entity_class(
                    self,
                    oid=entity.id,
                    objid=entity.objid,
                    name=entity.name,
                    active=entity.active,
                    desc=entity.desc,
                    model=entity,
                )
                resp[entity.ext_id] = res
            self.logger.debug("Index resources by ext_id: %s", resp)
            return resp
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return None

    @trace(entity="Resource", op="types.view")
    def get_resource_types(self, oid=None, value=None, rfilter=None):
        """Get resource type.

        :param oid: resource type id.
        :param value: resource type value. String like org or vm
        :param rfilter: resource type partial value
        :rtype: list of :class:`ResourceType`
        :raises QueryError: raise :class:`QueryError`
        """
        try:
            res = self.manager.get_resource_types(oid=oid, value=value, filter=rfilter)
            self.logger.debug("Get resource types: %s", res)
            return [{"id": i.id, "type": i.value, "resclass": i.objclass} for i in res]
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return []

    @trace(entity="Resource", op="view")
    def get_resource(self, oid, entity_class=None, **kvargs):
        """Get single resource.

        :param entity_class: Controller ApiObject Extension class. Specify when you want to verify match between
            objdef of the required resource and find resource. [optional]
        :param oid: entity model id or uuid
        :param run_customize: if True run customize [default=True]
        :return: Resource instance
        :raise ApiManagerError:
        """

        def customize(entity: 'Resource', *args, **kvargs) -> 'Resource':
            # set physical entity
            entity.set_physical_entity(entity=None)

            # set container
            container = self.get_container(entity.container_id, connect=True)
            entity.set_container(container)
            self.logger.debug("Set container %s", container)

            # execute custom post_get
            entity.post_get()
            self.logger.debug("Do post get")

            return entity

        res = self.get_entity_v2(ModelResource, oid, entity_class=entity_class, customize=customize, **kvargs)

        # set error reason
        if res.model.state == 4:
            res.reason = res.get_errors()

        return res

    def get_simple_resource(self, oid, entity_class=None, **kvargs) -> 'Resource':
        """Get single resource without details

        :param entity_class: Controller ApiObject Extension class. Specify when you want to verify match between
            objdef of the required resource and find resource. [optional]
        :param oid: entity model id or uuid
        :return: Resource instance
        :raise ApiManagerError:
        """
        return self.get_resource(oid, entity_class=entity_class, run_customize=False, **kvargs)

    @trace(entity="Resource", op="view")
    def get_resource_by_extid(self, ext_id, container_oid=None) -> 'Resource':
        """Get resource by remote platform id

        :param ext_id: remote platform entity id
        :return: Resource instance
        :raise ApiManagerError:
        """
        if ext_id is None:
            return None
        try:
            entity = self.manager.get_resource_by_extid(ext_id, container_oid)
            entity_class = import_class(entity.type.objclass)
            res = entity_class(
                self,
                oid=entity.id,
                objid=entity.objid,
                name=entity.name,
                active=entity.active,
                desc=entity.desc,
                model=entity,
            )
            self.logger.debug("Get resource by ext_id %s : %s", ext_id, res)
            return res
        except QueryError as ex:
            self.logger.warning(ex, exc_info=False)
            return None

    @trace(entity="Resource", op="view")
    def customize_resource(self, entities: List['Resource'], *args, **kvargs):
        from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor

        kvargs.pop("container", None)
        # get parents
        parents = kvargs.get("parents", None)
        # get containers
        container_idx = {}
        class_idx = {}
        flavor_idx = self.index_resources_by_id(entity_class=ComputeFlavor)

        entity_ids = [e.model.id for e in entities]
        all_links, _ = self.get_links(start_resource_ids=entity_ids, type="flavor")

        flavor_link_idx = defaultdict(list)
        for link in all_links:
            flavor_link_idx[link.model.start_resource_id].append(link)

        for entity in entities:
            index = f"{entity.objdef}-{entity.model.container_id}"
            cid = entity.model.container_id

            if index in class_idx:
                class_idx[index]["entities"].append(entity)
            else:
                # get connection
                if cid not in container_idx:
                    container_idx[cid] = self.get_container(cid, connect=True)
                class_idx[index] = {
                    "class": entity.__class__,
                    "container": container_idx[cid],
                    "entities": [entity],
                }

            links = flavor_link_idx.get(entity.model.id, [])
            if links:
                entity.flavor = flavor_idx.get(links[0].model.end_resource_id)

            entity.set_physical_entity(entity=None)
            # set container
            entity.set_container(container_idx[cid])
            # set parent
            if parents is not None and entity.model.parent_id is not None:
                entity.set_parent(parents.get(entity.model.parent_id, {}))
            # set error reason
            entity.reason = entity.get_errors()

        # execute custom post_list
        for item in class_idx.values():
            item["class"].customize_list(self, item["entities"], container=item["container"], *args, **kvargs)

        return entities

    @trace(entity="Resource", op="view")
    def get_resources(self, *args, **kvargs) -> Tuple[List['Resource'],int]:
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
        :param run_customize: if True run customize [default=True]
        :return: :py:class:`list` of :class:`Resource`
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs) -> Tuple[List['ModelResource'],int]:
            # get filter field
            uuids = kvargs.pop("uuids", None)
            container = kvargs.pop("container", None)
            parent = kvargs.pop("parent", None)
            parent_list = kvargs.pop("parent_list", None)
            l_type = kvargs.pop("type", None)

            if uuids is not None:
                kvargs["uuids"] = uuids.split(",")
            if container is not None:
                kvargs["container_id"] = self.get_container(container).oid

            if parent is not None:
                parent_id = parent
                if not isinstance(parent, int):
                    parent_id = self.get_simple_resource(parent).oid
                kvargs["parent_id"] = parent_id
            elif parent_list is not None:
                kvargs["parent_ids"] = []
                if isinstance(parent_list, str):
                    parent_list = parent_list.split(",")
                for parent_item in parent_list:
                    try:
                        if isinstance(parent, int):
                            kvargs["parent_ids"].append(parent_item)
                        else:
                            kvargs["parent_ids"].append(self.get_simple_resource(parent_item).oid)
                    except:
                        self.logger.warning("resource %s does not exist", parent_item)

            if l_type is not None:
                kvargs["types"] = []
                types = l_type.split(",")
                for item in types:
                    res_types = self.manager.get_resource_types(filter=item)
                    kvargs["types"].extend([t.id for t in res_types])

                # filter entities by ext_id if only one type is expressed
                if len(types) == 1 and container is not None:
                    entity_class = import_class(res_types[0].objclass)
                    kvargs["ext_ids"] = entity_class.get_entities_filter(self, **kvargs)
                    self.logger.debug("Get ext_ids filter: %s", kvargs["ext_ids"])

            # get all resources
            ext_ids = kvargs.get("ext_ids", None)
            if ext_ids is None or len(ext_ids) > 0:
                resources, total = self.manager.get_resources(*args, **kvargs)
            else:
                resources, total = [], 0

            return resources, total

        def customize(entities: List['Resource'], *args, **kvargs) -> List['Resource']:
            if kvargs.get("run_customize", True) is True:
                return self.customize_resource(entities, *args, **kvargs)
            return entities

        res, total = self.get_paginated_entities("resource", get_entities, customize=customize, *args, **kvargs)
        return res, total

    @trace(entity="Resource", op="view")
    def get_directed_linked_resources(
        self,
        resources=None,
        link_type=None,
        link_type_filter=None,
        container=None,
        type=None,
        *args,
        **kvargs,
    ):
        """Get resources direct linked to a list of resources.

        :param resources resource ids list
        :param type: resource type [optional]
        :param container: container id, name or uuid [optional]
        :param link_type: link type [optional]
        :param link_type_filter: link type filter
        :param page users list page to show [default=0]
        :param size number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param run_customize: if True run customize [default=True]
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs) -> Tuple[List['ModelResource'],int]:
            # get filter field
            # container = kvargs.pop('container', None)

            container_id = None
            if container is not None:
                container_id = self.get_container(container).oid
            if type is not None:
                types = self.manager.get_resource_types(filter=type)
                kvargs["types"] = [t.id for t in types]

            res, total = self.manager.get_directed_linked_resources(
                resources=resources,
                link_type=link_type,
                link_type_filter=link_type_filter,
                container_id=container_id,
                *args,
                **kvargs,
            )

            return res, total

        def customize(entities: List['Resource'], *args, **kvargs) -> List['Resource']:
            return self.customize_resource(entities, *args, **kvargs)

        res, total = self.get_paginated_entities("resource", get_entities, customize=customize, *args, **kvargs)
        self.logger.debug("Get linked resources: %s", res)
        return res, total

    def __get_linked_resources_internal(
        self,
        query_method: Callable[...,List['ResourceDbManager_DirectedLinkedResourcesInternal_Return']],
        resources: List[int],
        *args, **kwargs
    ) -> Dict[int,List[Resource]]:
        """Get direct linked resources. Use this method for internal query without authorization.

        :param query_method: query_method to use
        :param resources: resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :param run_customize: if True run customize [default=True]
        :param customize_func: customize function to run [default=customize_list]
        :return: dict like {<resource_id>: [<list o linked resource ids>]}
        """
        link_type = kwargs.get("link_type", None)
        container_id = kwargs.get("container_id", None)
        objdef = kwargs.get("objdef", None)
        objdefs = kwargs.get("objdefs", None)
        run_customize = kwargs.get("run_customize", False)
        customize_func = kwargs.get("customize_func", "customize_list")
        if not resources:
            return {}

        try:
            models = query_method(resources, link_type, container_id, objdef, objdefs)
        except Exception as e:
            self.logger.error("Linked resources query failed: %s", e)
            raise

        resp = defaultdict(list)

        # Local caches to avoid redundant imports/lookups in loop
        _class_cache = {}
        _container_cache = {}

        # Group entities by (class, container) for batch customization
        customization_groups = defaultdict(lambda: {"class": None, "entities": []})

        for model in models:
            if model.objclass not in _class_cache:
                _class_cache[model.objclass] = import_class(model.objclass)

            entity_class = _class_cache[model.objclass]

            entity = entity_class(
                self,
                oid=model.id,
                objid=model.objid,
                name=model.name,
                active=model.active,
                desc=model.desc,
                model=model,
            )

            entity.link_attr = model.link_attr
            entity.link_type = model.link_type
            entity.link_creation = model.link_creation

            resp[model.resource].append(entity)

            if run_customize:
                cid = model.container_id

                # Lazy load container
                if cid not in _container_cache:
                    _container_cache[cid] = self.get_container(cid)

                entity.set_container(_container_cache[cid])
                entity.set_physical_entity(entity=None)

                # Group by class and container to execute customize in bulk later
                group_key = (model.objclass, cid)
                group = customization_groups[group_key]
                if group["class"] is None:
                    group["class"] = entity_class
                group["entities"].append(entity)

        # Execute custom post_list in batch
        if run_customize:
            for (objclass_name, cid), group in customization_groups.items():
                klass = group["class"]
                customizer = getattr(klass, customize_func, None)
                if customizer:
                    customizer(
                        self,
                        group["entities"],
                        container = _container_cache[cid]
                    )
                else:
                    self.logger.warning("Missing %s on %s", customize_func, klass)

        self.logger.debug("Get direct linked resources: %s", resp)
        return resp

    @trace(entity="Resource", op="view")
    def get_directed_linked_resources_internal(
        self,
        resources: List[int],
        *args,
        **kwargs
    ) -> Dict[int, List['Resource']]:
        """Get direct linked resources. Use this method for internal query without authorization.

        :param resources: start resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :param run_customize: if True run customize [default=True]
        :param customize_func: customize function to run [default=customize_list]
        :return: dict like {<resource_id>: [<list of linked resource ids>]}
        """
        return self.__get_linked_resources_internal(
            self.manager.get_directed_linked_resources_internal,
            resources,
            *args,
            **kwargs,
        )

    @trace(entity="Resource", op="view")
    def get_indirected_linked_resources_internal(self, resources, *args, **kwargs) -> Dict[int,List['Resource']]:
        """Get indirect linked resources. Use this method for internal query without authorization.

        :param resources: end resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :param run_customize: if True run customize [default=True]
        :param customize_func: customize function to run [default=customize_list]
        :return: dict like {<resource_id>: [<list of linked resource ids>]}
        """
        return self.__get_linked_resources_internal(
            self.manager.get_indirected_linked_resources_internal,
            resources,
            *args,
            **kwargs,
        )

    @trace(entity="Resource", op="view")
    def get_aggregated_resource_from_physical_resource(self, resource_id, parent_id=None):
        """Get aggregate resource from physical. Use this method for internal query without authorization.

        :param resource_id: resource id list
        :param parent_id: parent id
        :return: dict like {<resource_id>: [<list o linked resource ids>]}
        """
        entity = self.manager.get_aggregated_resource_from_physical_resource(resource_id, parent_id=parent_id)
        if entity is None:
            return None
        entity_class = import_class(entity.type.objclass)
        res = entity_class(
            self,
            oid=entity.id,
            objid=entity.objid,
            name=entity.name,
            active=entity.active,
            desc=entity.desc,
            model=entity,
        )
        return res

    @trace(entity="Resource", op="view")
    def get_main_zone_instance(self, oid):
        """
        Get main availability zone instance

        :param oid: id
        :return:
        """
        entity = self.manager.get_main_zone_instance(oid)
        if entity is None:
            return None
        entity_class = import_class(entity.type.objclass)
        res = entity_class(
            self,
            oid=entity.id,
            objid=entity.objid,
            name=entity.name,
            active=entity.active,
            desc=entity.desc,
            model=entity,
        )
        return res

    #
    # tags
    #
    @trace(entity="ResourceTag", op="view")
    def get_tag(self, oid, *args, **kvargs):
        """Get single tag.

        :param oid: entity model id or name or uuid
        :return: ResourceTag
        :raise ApiManagerError:
        """
        return ApiController.get_entity(self, ResourceTag, ModelResourceTag, oid)

    @trace(entity="ResourceTag", op="view")
    def get_tags(self, *args, **kvargs):
        """Get tags.

        :param value: tag value [optional]
        :param container: container id, uuid or name [optional]
        :param resource: resource id, uuid [optional]
        :param link: link id, uuid or name [optional]
        :param page users list page to show [default=0]
        :param size number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: :py:class:`list` of :py:class:`ResourceTag`
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs):
            # get filter field
            container = kvargs.get("container", None)
            resource = kvargs.get("resource", None)
            link = kvargs.get("link", None)

            # search tags by container
            if container is not None:
                # TODO
                pass
                kvargs["container"] = self.get_container(container).oid
                tags, total = self.manager.get_container_tags(*args, **kvargs)

            # search tags by resource
            elif resource is not None:
                kvargs["resource"] = self.get_simple_resource(resource).oid
                tags, total = self.manager.get_resource_tags(*args, **kvargs)

            # search tags by link
            elif link is not None:
                kvargs["link"] = self.get_link(link).oid
                tags, total = self.manager.get_link_tags(*args, **kvargs)

            # get all tags
            else:
                tags, total = self.manager.get_tags(*args, **kvargs)

            return tags, total

        if self.is_admin_resource():
            kvargs["authorize"] = False
        res, total = ApiController.get_paginated_entities(self, ResourceTag, get_entities, *args, **kvargs)
        return res, total

    @trace(entity="ResourceTag", op="view")
    def get_tags_occurrences(self, *args, **kvargs):
        """Get tags occurrences

        :param page users list page to show [default=0]
        :param size number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: :py:class:`list` of :py:class:`ResourceTagOccurrences`
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs):
            tags, total = self.manager.get_tags(*args, **kvargs)
            return tags, total

        def customize(res, *args, **kvargs):
            for item in res:
                item.resources = item.model.resources
                item.containers = item.model.containers
                item.links = item.model.links
            return res

        if self.is_admin_resource():
            kvargs["authorize"] = False
        res, total = ApiController.get_paginated_entities(
            self, ResourceTag, get_entities, customize=customize, *args, **kvargs
        )
        return res, total

    @trace(entity="ResourceTag", op="insert")
    def add_tag(self, value=None, *args, **kvargs):
        """Add new tag.

        :param value: tag value
        :return: tag uuid
        :raise ApiManagerError:
        """
        # check authorization
        if operation.authorize is True:
            self.check_authorization(ResourceTag.objtype, ResourceTag.objdef, None, "insert")

        try:
            objid = id_gen()
            tag = self.manager.add_tag(value, objid)

            # add object and permission
            ResourceTag(self, oid=tag.id).register_object([objid], desc=value)

            self.logger.debug("Add new tag: %s", value)
            return tag.uuid
        except TransactionError as exc:
            raise ApiManagerError(exc, code=exc.code) from exc
        except Exception as exc:
            raise ApiManagerError(exc, code=400) from exc

    #
    # links
    #
    @trace(entity="ResourceLink", op="view")
    def get_link(self, oid, *args, **kvargs):
        """Get single link.

        :param oid: entity model id or name or uuid
        :return: ResourceLink
        :raise ApiManagerError:
        """
        return ApiController.get_entity(self, ResourceLink, ModelResourceLink, oid)

    @trace(entity="ResourceLink", op="view")
    def get_links(self, *args, **kvargs) -> Tuple[List[ResourceLink], int]:
        """Get links.

        :param start_resource: start resource id or uuid [optional]
        :param end_resource: end resource id or uuid [optional]
        :param resource: resource id or uuid [optional]
        :param type: link type [optional]
        :param resourcetags: list of tags. All tags in the list must be met [optional]
        :param page users list page to show [default=0]
        :param size number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: :py:class:`list` of :py:class:`ResourceLink`
        :raise ApiManagerError:
        """

        def get_entities(*args, **kvargs):
            # get filter field
            start_resource = kvargs.pop("start_resource", None)
            end_resource = kvargs.pop("end_resource", None)
            resource = kvargs.pop("resource", None)

            # get all links
            if end_resource is not None:
                kvargs["end_resource"] = self.get_simple_resource(end_resource).oid
            if start_resource is not None:
                kvargs["start_resource"] = self.get_simple_resource(start_resource).oid
            if resource is not None:
                kvargs["resource"] = self.get_simple_resource(resource).oid

            resource_db_manager: ResourceDbManager = self.manager
            links, total = resource_db_manager.get_links(*args, **kvargs)

            return links, total

        if self.is_admin_resource():
            kvargs["authorize"] = False
        res, total = ApiController.get_paginated_entities(self, ResourceLink, get_entities, *args, **kvargs)
        return res, total

    @trace(entity="ResourceLink", op="insert")
    def add_link(
        self,
        name=None,
        type=None,
        start_resource=None,
        end_resource=None,
        attributes=None,
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
        attributes = attributes or {}

        # check authorization
        if operation.authorize is True:
            self.check_authorization(ResourceLink.objtype, ResourceLink.objdef, None, "insert")

        # get resources
        start_resource_id = self.get_simple_resource(start_resource).oid
        end_resource_id = self.get_simple_resource(end_resource).oid

        try:
            objid = id_gen()
            attributes = jsonDumps(attributes)
            link = self.manager.add_link(
                objid,
                name,
                type,
                start_resource_id,
                end_resource_id,
                attributes=attributes,
            )

            # add object and permission
            ResourceLink(self, oid=link.id).register_object([objid], desc=name)

            self.logger.debug("Add new link: %s", name)
            return link.uuid
        except TransactionError as exc:
            raise ApiManagerError(exc, code=exc.code) from exc
        except Exception as exc:
            raise ApiManagerError(exc, code=400) from exc

    #
    # jobs
    #
    def __get_task(self, task_id):
        from beehive.common.task_v2.manager import get_task_manager
        task_manager = get_task_manager()
        try:
            redis_manager = self.redis_taskmanager
            task = redis_manager.get(task_manager.conf.CELERY_REDIS_RESULT_KEY_PREFIX + task_id)
            task = json.loads(task)
        except:
            task = {}
        return task

    @trace(entity="Resource", op="use")
    def add_job(self, job_id, job_name, params):
        self.manager.add_job(job_id, job_name, params=compat(params))

    @trace(entity="Resource", op="use")
    def get_jobs(
        self,
        jobstatus=None,
        job=None,
        name=None,
        container=None,
        resources=None,
        from_date=None,
        size=10,
    ):
        """Get resource jobs.

        :param jobstatus: jobstatus [optional]
        :param job: job id. [optional]
        :param name: job name. [optional]
        :param resources: resource ids. [optional]
        :param container: container id. [optional]
        :param from_date: filter start date > from_date [optional]
        :param size: max number of jobs [default=10]
        :return: List of jobs
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        # check authorization
        if operation.authorize is True:
            self.check_authorization("task", "Manager", "*", "view")

        jobs, count = self.manager.get_jobs(
            job=job,
            name=name,
            resource=None,
            container=container,
            resources=resources,
            from_date=from_date,
            size=size,
        )

        res = []
        for j in jobs:
            task = self.__get_task(j.job)
            status = task.get("status", None)
            if jobstatus is None or status == jobstatus:
                start_time = format_date(j.creation_date)
                stop_time = task.get("stop_time", None)
                if stop_time is not None:
                    stop_time = self.convert_timestamp(stop_time)
                res.append(
                    {
                        "id": j.job,
                        "name": j.name,
                        "resource": j.resource_id,
                        "container": j.container_id,
                        "params": json.loads(j.params),
                        "start_time": start_time,
                        "stop_time": stop_time,
                        "status": status,
                        "worker": task.get("worker", None),
                        # 'tasks': len(childrens),
                        # 'jobs': len(children_jobs),
                        "elapsed": task.get("stop_time", 0) - task.get("start_time", 0),
                    }
                )

        self.logger.debug("Get jobs: %s", res)

        return res, count

    def get_awx_project(
        self,
        customization_base_name: str,
        site_id: int,
        awx_orchestrator_tag: str=None,
        raise_on_error=True
    ) -> AwxProject:
        """get awx project by customization, zone, and awx tag

        :param customization_base_name: the base name e.g. staas
        :type customization_base_name: str
        :param site_id: site id e.g. 706
        :type site_id: int
        :param awx_orchestrator_tag: optional tag. used to determine
        compute customization actual name together with base name. defaults to None
        :type awx_orchestrator_tag: str, optional
        :param raise_on_error: if true raises on error, otherwise return None.
        defaults to True
        :type raise_on_error: bool, optional
        :raises Exception: if any resource (compute customization, customization, awx project)
        not found
        :return: the awx project, if any
        :rtype: AwxProject
        """
        if awx_orchestrator_tag:
            customization_name = f"{customization_base_name}-{awx_orchestrator_tag}"
        else:
            customization_name = customization_base_name

        # get compute customization
        from beehive_resource.plugins.provider.entity.customization import ComputeCustomization, Customization
        from beehive_resource.plugins.awx.entity.awx_project import AwxProject

        try:
            compute_customization: ComputeCustomization = self.get_resource(
                entity_class=ComputeCustomization,
                oid=customization_name,
                run_customize=False,
                cache=False
            )
        except Exception as exc:
            if raise_on_error:
                raise Exception(f"ComputeCustomization {customization_name} not found") from exc
            return None

        # get customization
        try:
            customization: Customization = compute_customization.get_local_resource(site_id)
        except Exception as exc:
            c_oid = compute_customization.oid
            self.logger.error("ComputeCustomization %s has no child in zone %s", c_oid, site_id)
            if raise_on_error:
                raise Exception(f"ComputeCustomization {c_oid} has no child in zone {site_id}") from exc

        # get project
        try:
            awx_project: AwxProject = customization.get_physical_resource_from_container(None, AwxProject.objdef)
            # same as above, but also gets container and executes resource post_get
            # awx_project2 = customization.get_physical_resource(AwxProject.objdef)
        except Exception as ex:
            self.logger.error("Error while determining awx project: %s", str(ex))
            if raise_on_error:
                raise Exception(f"Error while determining awx project: {ex!s}") from ex

        return awx_project
