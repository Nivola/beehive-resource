# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import ujson as json
from logging import getLogger
from datetime import datetime
from beecell.types.type_string import compat, truncate
from beecell.types.type_date import format_date
from beecell.types.type_id import id_gen
from beecell.simple import import_class
from beehive.common.apimanager import ApiController, ApiManagerError
from beehive.common.task.manager import task_manager
from beehive_resource.container import ResourceLink, ResourceTag, ResourceContainer, Resource
from beecell.db import QueryError, TransactionError
from beehive_resource.model import ResourceDbManager, Resource as ModelResource, ResourceTag as ModelResourceTag, \
    ResourceLink as ModelResourceLink, Container as ModelContainer, ContainerState
from beehive.common.data import trace, operation, cache
from beecell.simple import jsonDumps
from os import path
from inspect import getfile, isclass

logger = getLogger(__name__)


class ResourceController(ApiController):
    """Resource Module controller.
    
    :param ApiModule module: beehive module instance
    """    
    version = 'v1.0' #: version
    
    def __init__(self, module):
        ApiController.__init__(self, module)
        
        #: db manager reference
        self.manager = ResourceDbManager(cache_manager=self.module.api_manager.cache_manager)
        #: container class list
        self.container_classes = {}
        #: child class list
        self.child_classes = [
            ResourceContainer,
            Resource,
            ResourceTag, 
            ResourceLink]
        #: container list
        self.containers = {}

        # init static resources and templates
        clspath = path.dirname(getfile(ResourceController))
        app = module.api_manager.app
        if app is not None:
            app.template_folder = '%s/templates' % clspath
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
        """
        """
        timestamp = datetime.fromtimestamp(timestamp)
        return format_date(timestamp)

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
        if entity_class.objtask_version == 'v2' or entity_class.objtask_version is None:
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
        if entity_class.objtask_version == 'v3':
            return True
        return False

    #
    # helper model for entities
    #
    # def get_entity(self, model_class, oid, entity_class=None, details=True, run_customize=True, *args, **kvargs):
    #     """Get single entity by oid (id, uuid, name) if exists
    #     
    #     :param entity_class: Controller ApiObject Extension class. Specify when you want to verif match between
    #         objdef of the required resource and find resource. [optional]
    #     :param model_class: Model ApiObject Extension class
    #     :param oid: entity model id or name or uuid
    #     :param details: if True call custom method post_get()
    #     :param run_customize: if True run customize [default=True]
    #     :param kvargs: additional filters [optional]
    #     :return: entity instance
    #     :raise ApiManagerError`:
    #     """
    #     try:
    #         entity = self.manager.get_entity(model_class, oid, *args, **kvargs)
    #         if entity_class is not None:
    #             int_entity_class = entity_class
    #         else:
    #             int_entity_class = import_class(entity.type.objclass)
    #     except QueryError as ex:         
    #         self.logger.error(ex)
    #         raise ApiManagerError('Resource %s not found' % (oid), code=404)
    #     
    #     # check objdef match with required
    #     if entity_class is not None and entity.type.value != entity_class.objdef:
    #         raise ApiManagerError('Resource %s %s not found' % (entity_class.objname, oid), code=404)
    #         
    #     # check authorization
    #     if operation.authorize is True:
    #         self.check_authorization(int_entity_class.objtype, int_entity_class.objdef, entity.objid, 'view')
    #     
    #     res = int_entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
    #                            desc=entity.desc, model=entity)
    # 
    #     if run_customize is True:
    #         # set physical entity
    #         res.set_physical_entity(entity=None)
    # 
    #         # set parent
    #         if entity.parent_id is not None:
    #             parent = self.manager.get_entity(ModelResource, entity.parent_id)
    #             res.set_parent({'id': parent.id, 'uuid': parent.uuid, 'name': parent.name})
    #             self.logger.debug('Set parent %s' % parent.uuid)
    # 
    #         # set container
    #         container = self.get_container(entity.container_id)
    #         res.set_container(container)
    #         self.logger.debug('Set container %s' % container)
    # 
    #         # execute custom post_get
    #         if details is True:
    #             res.post_get()
    #             self.logger.debug('Do post get')
    #     
    #     self.logger.info('Get %s : %s' % (int_entity_class.__name__, res))
    #     return res

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
        res = int_entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                               desc=entity.desc, model=entity)

        # if it is a resource subclass set container and run post_get
        if model == ModelResource:
            container = self.get_container(entity.container_id)
            res.set_container(container)
            res.post_get()

        self.logger.info('get %s : %s' % (int_entity_class.__name__, res))
        return res

    def get_entity_v2(self, model_class, oid, entity_class=None, customize=None, run_customize=True, *args, **kvargs):
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
        if kvargs.pop('cache', True) is True:
            entity = self.manager.get_entity_with_cache(model_class, oid, *args, **kvargs)
        else:
            try:
                entity = self.manager.get_entity(model_class, oid, *args, **kvargs)
                if entity is None:
                    self.logger.error('Resource %s not found' % oid)
                    raise ApiManagerError('Resource %s not found' % oid, code=404)
                if entity_class is not None:
                    int_entity_class = entity_class
                else:
                    int_entity_class = import_class(entity.type.objclass)
            except QueryError as ex:
                self.logger.error(ex)
                raise ApiManagerError('Resource %s not found' % oid, code=404)

        # cached_entity = model_class.get_entity_with_cache(self, oid, *args, **kvargs)
        # entity = model_class.dict_to_model(cached_entity)

        if entity_class is not None:
            int_entity_class = entity_class
        else:
            int_entity_class = import_class(entity.type.objclass)

        # check objdef match with required
        if entity_class is not None and entity.type.value != entity_class.objdef:
            raise ApiManagerError('Resource %s %s not found' % (entity_class.objname, oid), code=404)

        # check authorization
        if operation.authorize is True:
            self.check_authorization(int_entity_class.objtype, int_entity_class.objdef, entity.objid, 'view')

        res = int_entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                               desc=entity.desc, model=entity)

        # customize entity
        if run_customize is True and customize is not None:
            res = customize(res, *args, **kvargs)

        self.logger.info('Get %s : %s' % (int_entity_class.__name__, res))
        return res

    def get_paginated_entities(self, objtype, get_entities, page=0, size=10, order='DESC', field='id', customize=None,
                               run_customize=True, objdef=None, entity_class=None, *args, **kvargs):
        """Get entities with pagination

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
            raise ApiManagerError('entity_class objdef and objdef mismatch')

        if operation.authorize is False or kvargs.get('authorize', True) is False:
            kvargs['with_perm_tag'] = False
            self.logger.debug('Authorization disabled for command')
        elif operation.authorize is True:
            # verify permissions
            objs = self.can('view', objtype=objtype, definition=objdef)
            self.logger.warn('Permission tags to apply: %s' % objs)

            # create permission tags
            for entity_def, ps in objs.items():
                for p in ps:
                    tags.append(self.manager.hash_from_permission(entity_def.lower(), p))
            self.logger.warn('Permission tags to apply: %s' % tags)

        try:
            entities, total = get_entities(tags=tags, page=page, size=size, order=order, field=field, *args, **kvargs)

            # total = 0
            for entity in entities:
                if entity_class is None:
                    objclass = import_class(entity.type.objclass)
                else:
                    objclass = entity_class

                # bypass object that does not match objdef
                if objdef is not None and objclass.objdef != objdef:
                    continue

                obj = objclass(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                               desc=entity.desc, model=entity)
                res.append(obj)
                # total += 1
            # customize entities
            if run_customize is True and customize is not None:
                res = customize(res, tags=tags, *args, **kvargs)
            
            self.logger.info('Get %s (total:%s): %s' % (objtype, total, truncate(res)))
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
        res = [{
            'id': t.id,
            'category': t.category,
            'type': t.value
        } for t in objs]
        
        return res

    @staticmethod
    @cache('container.get', ttl=86400)
    def get_container_data(controller, container_id, *args, **kvargs):
        res = {
            'id': container_id,
            'uuid': None,
            'name': None,
            'desc': None,
            'objid': None,
            'active': None,
            'connection': None
        }
        if container_id is None:
            return res
        try:
            entity = controller.manager.get_entity(ModelContainer, container_id)
            res = {
                'id': entity.id,
                'uuid': entity.uuid,
                'name': entity.name,
                'desc': entity.desc,
                'objid': entity.objid,
                'active': entity.active,
                'connection': json.loads(entity.connection)
            }
            return res
        except:
            logger.warning('', exc_info=True)
            return res

    @trace(entity='ResourceContainer', op='view')
    def get_container(self, oid, cache=True, connect=True, **kvargs):
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
                    raise QueryError('Container %s not found' % oid)
                entity_class = import_class(entity.type.objclass)
                
                # check authorization
                if operation.authorize is True:
                    self.check_authorization(entity_class.objtype, entity_class.objdef, entity.objid, 'view')

                if entity.id not in self.containers:
                    container = entity_class(self, oid=entity.id, name=entity.name, objid=entity.objid,
                                             desc=entity.desc, active=entity.active, model=entity)
                    self.containers[entity.id] = container
                    self.logger.info('Cache container %s' % oid)
                else:
                    self.containers[entity.id].model = entity
                    self.logger.info('Get container %s from cache' % oid)
                
                container = self.containers[entity.id]
                # get connection
                if connect is True:
                    container.get_connection(**kvargs)
                return container
            except QueryError as ex:         
                self.logger.error(ex, exc_info=True)
                raise ApiManagerError('Container %s not found' % oid, code=404)
        else:
            entity = self.manager.get_entity(ModelContainer, oid)
            entity_class = import_class(entity.type.objclass)

            # check authorization
            if operation.authorize is True:
                self.check_authorization(entity_class.objtype, entity_class.objdef, entity.objid, 'view')

            container = entity_class(self, oid=entity.id, name=entity.name, objid=entity.objid,
                                     desc=entity.desc, active=entity.active, model=entity)
            self.containers[entity.id] = container
            self.logger.info('Get container %s' % oid)

            # get connection
            if connect is True:
                container.get_connection(**kvargs)
            return container

    @trace(entity='ResourceContainer', op='view')
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
            if 'container_type' in kvargs:
                kvargs['type_id'] = self.manager.get_container_type(category=kvargs.get('container_type'))[0].id
            containers, total = self.manager.get_containers(*args, **kvargs)
            
            return containers, total
        
        def customize(res, *args, **kvargs):
            return res
            
        res, total = self.get_paginated_entities('container', get_entities, customize=customize, *args, **kvargs)
        return res, total
    
    @trace(entity='ResourceContainer', op='view')
    def index_containers_by_id(self, entity_class=None):
        """Get indexed containers. This method does not verify authorization. Use only for internal assignment.
    
        :param entity_class: container class [optional]            
        :return: index of Container by id            
        :raise ApiManagerError:
        """    
        try:
            if entity_class is not None:
                type = entity_class.objdef
            else:
                type = None            
            entities = self.manager.get_containers_by_type(type=type) 
            resp = {}
            for entity in entities:
                entity_class = import_class(entity.type.objclass)
                res = entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                                   desc=entity.desc, model=entity)
                resp[entity.id] = res
            self.logger.debug('Index containers by id')
            return resp
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return None
    
    @trace(entity='ResourceContainer', op='insert')
    def add_container(self, type=None, name=None, desc=None, conn={}):
        """Add new container
        
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param conn: container connection            
        :return: container uuid            
        :raise ApiManagerError:
        """
        container_class = self.get_container_class(type)
        self.logger.debug('Get container_class %s' % container_class)

        # check authorization
        self.check_authorization(container_class.objtype, container_class.objdef, None, 'insert')

        if self.manager.exist_entity(ModelContainer, name) is True:
            raise ApiManagerError('Container %s already exists' % name)

        # call pre create
        kvargs = container_class.pre_create(controller=self, type=type, name=name, desc=desc, active=False, conn=conn)
        name = kvargs.get('name')
        desc = kvargs.get('desc')
        active = kvargs.get('active')
        conn = jsonDumps(kvargs.get('conn', {}))
        objid=id_gen()
        
        try:
            # create container reference
            ctype = self.manager.get_container_type(value=container_class.objdef, category=container_class.category)[0]
        except QueryError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError('Container type %s does not exist' % container_class.__name__, code=404)
        
        try:                               
            res = self.manager.add_container(objid, name, ctype, conn, desc, active)
            self.manager.update_container_state(res.id, ContainerState.BUILDING)
        except TransactionError as ex:
            # self.manager.update_container_state(res.id, ContainerState.ERROR)
            self.logger.error(ex)
            raise ApiManagerError('Container %s already exists' % name, code=409)

        # create object and permission
        container = container_class(self, oid=res.id, objid=id_gen(), name=name, desc=desc, active=active, model=res)        
        container.register_object([objid], desc=container.desc)
        
        # call post create
        container_class.post_create(controller=self, container=container)          
        
        try:
            self.manager.update_container(oid=res.id, state=ContainerState.ACTIVE, active=True)
            self.manager.update_container(oid=res.id, state=ContainerState.ACTIVE, active=True)
        except TransactionError as ex:
            self.manager.update_container_state(res.id, ContainerState.ERROR)
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)        
        
        self.logger.info('Add container %s %s' % (container_class.__name__, name))
        return res.uuid

    #
    # resource
    #
    @trace(entity='Resource', op='view')
    def index_resources_by_id(self, entity_class=None):
        """Get indexed resources. This method does not verify authorization. Use only for internal assignment.

        :param entity_class: parent resource class [optional]
        :return: dictionary {'parent_id':{'id':.., 'uuid':.., 'name':..}}
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        try:
            if entity_class is not None:
                type = entity_class.objdef
            else:
                type = None
            entities = self.manager.get_resources_by_type(type=type)
            resp = {}
            for entity in entities:
                entity_class = import_class(entity.type.objclass)
                res = entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                                   desc=entity.desc, model=entity)
                resp[entity.id] = res
                resp[entity.uuid] = res
            self.logger.info('Index resources by id: %s' % truncate(resp))
            return resp
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return None

    @trace(entity='Resource', op='view')
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
                res = entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                                   desc=entity.desc, model=entity)
                resp[entity.ext_id] = res
            self.logger.info('Index resources by ext_id: %s' % truncate(resp))
            return resp
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return None
        
    @trace(entity='Resource', op='types.view')
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
            self.logger.info('Get resource types: %s' % truncate(res))        
            return [{'id': i.id, 'type': i.value, 'resclass': i.objclass} for i in res]
        except QueryError as ex:
            self.logger.warning(ex, exc_info=True)
            return []

    @trace(entity='Resource', op='view')
    def get_resource(self, oid, entity_class=None, **kvargs):
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
            container = self.get_container(entity.container_id, connect=True)
            entity.set_container(container)
            self.logger.debug('Set container %s' % container)

            # execute custom post_get
            entity.post_get()
            self.logger.debug('Do post get')

            return entity

        res = self.get_entity_v2(ModelResource, oid, entity_class=entity_class, customize=customize, **kvargs)

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

    @trace(entity='Resource', op='view')
    def get_resource_by_extid(self, ext_id):
        """Get resource by remote platform id

        :param ext_id: remote platform entity id
        :return: Resource instance
        :raise ApiManagerError:
        """
        if ext_id is None:
            return None
        try:
            entity = self.manager.get_resource_by_extid(ext_id)
            entity_class = import_class(entity.type.objclass)
            res = entity_class(self, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                               desc=entity.desc, model=entity)
            self.logger.info('Get resource by ext_id %s : %s' % (ext_id, res))
            return res
        except QueryError as ex:
            self.logger.warning(ex, exc_info=False)
            return None

    @trace(entity='Resource', op='view')
    def customize_resource(self, entities, *args, **kvargs):
        kvargs.pop('container', None)

        # get parents
        parents = kvargs.get('parents', None)

        # get containers
        container_idx = {}
        class_idx = {}

        # set parent
        for entity in entities:
            index = '%s-%s' % (entity.objdef, entity.model.container_id)
            cid = entity.model.container_id
            if index in class_idx:
                class_idx[index]['entities'].append(entity)
            else:
                # get connection
                if cid not in container_idx.keys():
                    container_idx[cid] = self.get_container(cid, connect=True)
                class_idx[index] = {
                    'class': entity.__class__,
                    'container': container_idx[cid],
                    'entities': [entity]
                }
                # self.logger.debug('Append new entity type: %s' % entity.objdef)

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
            item['class'].customize_list(self, item['entities'], container=item['container'], *args, **kvargs)

        return entities

    @trace(entity='Resource', op='view')
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
        def get_entities(*args, **kvargs):
            # get filter field
            uuids = kvargs.pop('uuids', None)
            container = kvargs.pop('container', None)
            parent = kvargs.pop('parent', None)
            parent_list = kvargs.pop('parent_list', None)
            type = kvargs.pop('type', None)

            if uuids is not None:
                kvargs['uuids'] = uuids.split(',')
            if container is not None:
                kvargs['container_id'] = self.get_container(container).oid
            if parent is not None:
                parent_id = parent
                if not isinstance(parent, int):
                    parent_id = self.get_simple_resource(parent).oid
                kvargs['parent_id'] = parent_id
            elif parent_list is not None:
                kvargs['parent_ids'] = []
                if isinstance(parent_list, str):
                    parent_list = parent_list.split(',')
                for parent_item in parent_list:
                    try:
                        if isinstance(parent, int):
                            kvargs['parent_ids'].append(parent_item)
                        else:
                            kvargs['parent_ids'].append(self.get_simple_resource(parent_item).oid)
                    except:
                        self.logger.warning('resource %s does not exist' % parent_item)
            if type is not None:
                kvargs['types'] = []
                types = type.split(',')
                for item in types:
                    res_types = self.manager.get_resource_types(filter=item)
                    kvargs['types'].extend([t.id for t in res_types])
                
                # filter entities by ext_id if only one type is expressed
                if len(types) == 1 and container is not None:
                    entity_class = import_class(res_types[0].objclass)
                    kvargs['ext_ids'] = entity_class.get_entities_filter(self, **kvargs)
                    self.logger.debug('Get ext_ids filter: %s' % kvargs['ext_ids'])

            # get all resources
            ext_ids = kvargs.get('ext_ids', None)
            if ext_ids is None or len(ext_ids) > 0:
                resources, total = self.manager.get_resources(*args, **kvargs)
            else:
                resources, total = [], 0
            
            return resources, total
        
        def customize(entities, *args, **kvargs):
            if kvargs.get('run_customize', True) is True:
                return self.customize_resource(entities, *args, **kvargs)
            return entities
        
        res, total = self.get_paginated_entities('resource', get_entities, customize=customize, *args, **kvargs)
        return res, total

    @trace(entity='Resource', op='view')
    def get_directed_linked_resources(self, resources=None, link_type=None, link_type_filter=None, container=None,
                                      type=None, *args, **kvargs):
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
        def get_entities(*args, **kvargs):
            # get filter field
            # container = kvargs.pop('container', None)

            container_id = None
            if container is not None:
                container_id = self.get_container(container).oid
            if type is not None:
                types = self.manager.get_resource_types(filter=type)
                kvargs['types'] = [t.id for t in types]

            res, total = self.manager.get_directed_linked_resources(resources=resources, link_type=link_type,
                                                                    link_type_filter=link_type_filter,
                                                                    container_id=container_id, *args, **kvargs)

            return res, total

        def customize(entities, *args, **kvargs):
            return self.customize_resource(entities, *args, **kvargs)

        res, total = self.get_paginated_entities('resource', get_entities, customize=customize, *args, **kvargs)
        self.logger.info('Get linked resources: %s' % truncate(res))
        return res, total

    def __get_linked_resources_internal(self, query_method, resources, *args, **kwargs):
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
        link_type = kwargs.get('link_type', None)
        container_id = kwargs.get('container_id', None)
        objdef = kwargs.get('objdef', None)
        objdefs = kwargs.get('objdefs', None)
        run_customize = kwargs.get('run_customize', False)
        customize_func = kwargs.get('customize_func', 'customize_list')
        
        try:
            if len(resources) == 0:
                models = []
            else:
                models = query_method(resources, link_type, container_id, objdef, objdefs)
            resp = {}
            container_idx = {}
            class_idx = {}

            for model in models:
                entity_class = import_class(model.objclass)
                entity = entity_class(self, oid=model.id, objid=model.objid, name=model.name, active=model.active,
                                      desc=model.desc, model=model)
                entity.link_attr = model.link_attr
                entity.link_type = model.link_type
                entity.link_creation = model.link_creation
                try:
                    resp[model.resource].append(entity)
                except:
                    resp[model.resource] = [entity]

                if run_customize is True:
                    index = '%s-%s' % (model.objdef, model.container_id)
                    cid = model.container_id
                    if index in class_idx:
                        class_idx[index]['entities'].append(entity)
                    else:
                        # get connection
                        if cid not in container_idx.keys():
                            container_idx[cid] = self.get_container(cid)
                        class_idx[index] = {
                            'class': entity.__class__,
                            'container': container_idx[cid],
                            'entities': [entity]
                        }
                        self.logger.debug('Append new entity type: %s' % model.objdef)

                    entity.set_physical_entity(entity=None)
                    # set container
                    entity.set_container(container_idx[cid])

            # execute custom post_list
            if run_customize is True:
                for item in class_idx.values():
                    func = getattr(item['class'], customize_func)
                    func(self, item['entities'], container=item['container'])

            self.logger.info('Get direct linked resources: %s' % truncate(resp))

            return resp
        except:
            self.logger.warning('', exc_info=True)
            return {}

    @trace(entity='Resource', op='view')
    def get_directed_linked_resources_internal(self, resources, *args, **kwargs):
        """Get direct linked resources. Use this method for internal query without authorization.

        :param resources: start resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :param run_customize: if True run customize [default=True]
        :param customize_func: customize function to run [default=customize_list]
        :return: dict like {<resource_id>: [<list o linked resource ids>]}
        """
        return self.__get_linked_resources_internal(self.manager.get_directed_linked_resources_internal, resources,
                                                    *args, **kwargs)

    @trace(entity='Resource', op='view')
    def get_indirected_linked_resources_internal(self, resources, *args, **kwargs):
        """Get indirect linked resources. Use this method for internal query without authorization.

        :param resources: end resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :param run_customize: if True run customize [default=True]
        :param customize_func: customize function to run [default=customize_list]
        :return: dict like {<resource_id>: [<list o linked resource ids>]}
        """
        return self.__get_linked_resources_internal(self.manager.get_indirected_linked_resources_internal, resources,
                                                    *args, **kwargs)

    # @trace(entity='ResourceLink', op='view')
    # def get_directed_links_internal(self, resources, link_type=None, *args, **kvargs):
    #     """Get links that start from resources select from an input list.
    # 
    #     :param resources: list of start resource id
    #     :param link_type: link type [optional]
    #     :return: :py:class:`list` of :py:class:`ResourceLink`
    #     :raise ApiManagerError:
    #     """
    #     resp = {}
    #     models, total = self.manager.get_links(start_resources=resources, type=link_type)
    #     for model in models:
    #         entity_class = import_class(model.objclass)
    #         entity = entity_class(self, oid=model.id, objid=model.objid, name=model.name, active=model.active,
    #                               desc=model.desc, model=model)
    #         entity.link_attr = model.link_attr
    #         try:
    #             resp[model.start].append(entity)
    #         except:
    #             resp[model.start] = [entity]
    # 
    #     res, total = ApiController.get_paginated_entities(self, ResourceLink, get_entities, *args, **kvargs)
    #     return res, total

    #
    # tags
    #
    @trace(entity='ResourceTag', op='view')
    def get_tag(self, oid, *args, **kvargs):
        """Get single tag.

        :param oid: entity model id or name or uuid
        :return: ResourceTag
        :raise ApiManagerError:
        """
        return ApiController.get_entity(self, ResourceTag, ModelResourceTag, oid)
    
    @trace(entity='ResourceTag', op='view')
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
            container = kvargs.get('container', None)
            resource = kvargs.get('resource', None)
            link = kvargs.get('link', None)             
            
            # search tags by container
            if container is not None:
                # TODO
                pass
                kvargs['container'] = self.get_container(container).oid
                tags, total = self.manager.get_container_tags(*args, **kvargs)
            
            # search tags by resource
            elif resource is not None:
                kvargs['resource'] = self.get_simple_resource(resource).oid
                tags, total = self.manager.get_resource_tags(*args, **kvargs)
    
            # search tags by link
            elif link is not None:
                kvargs['link'] = self.get_link(link).oid
                tags, total = self.manager.get_link_tags(*args, **kvargs)  
            
            # get all tags
            else:
                tags, total = self.manager.get_tags(*args, **kvargs)
            
            return tags, total
        
        res, total = ApiController.get_paginated_entities(self, ResourceTag, get_entities, *args, **kvargs)
        return res, total
    
    @trace(entity='ResourceTag', op='view')
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
        
        res, total = ApiController.get_paginated_entities(self, ResourceTag, get_entities, customize=customize,
                                                          *args, **kvargs)
        return res, total
    
    @trace(entity='ResourceTag', op='insert')
    def add_tag(self, value=None, *args, **kvargs):
        """Add new tag.
    
        :param value: tag value            
        :return: tag uuid            
        :raise ApiManagerError:
        """
        # check authorization
        if operation.authorize is True:
            self.check_authorization(ResourceTag.objtype, ResourceTag.objdef, None, 'insert')
    
        try:
            objid = id_gen()
            tag = self.manager.add_tag(value, objid)
            
            # add object and permission
            ResourceTag(self, oid=tag.id).register_object([objid], desc=value)
    
            self.logger.info('Add new tag: %s' % value)
            return tag.uuid
        except TransactionError as ex:       
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)
    
    #
    # links
    #
    @trace(entity='ResourceLink', op='view')
    def get_link(self, oid, *args, **kvargs):
        """Get single link.

        :param oid: entity model id or name or uuid
        :return: ResourceLink
        :raise ApiManagerError:
        """
        return ApiController.get_entity(self, ResourceLink, ModelResourceLink, oid)
    
    @trace(entity='ResourceLink', op='view')
    def get_links(self, *args, **kvargs):
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
            start_resource = kvargs.pop('start_resource', None)
            end_resource = kvargs.pop('end_resource', None)
            resource = kvargs.pop('resource', None)
            
            # get all links
            if end_resource is not None:
                kvargs['end_resource'] = self.get_simple_resource(end_resource).oid
            if start_resource is not None:
                kvargs['start_resource'] = self.get_simple_resource(start_resource).oid
            if resource is not None:
                kvargs['resource'] = self.get_simple_resource(resource).oid
            links, total = self.manager.get_links(*args, **kvargs)
            
            return links, total
        
        res, total = ApiController.get_paginated_entities(self, ResourceLink, get_entities, *args, **kvargs)
        return res, total
    
    @trace(entity='ResourceLink', op='insert')
    def add_link(self, name=None, type=None, start_resource=None, end_resource=None, attributes={}, *args, **kvargs):
        """Add new link.
    
        :param name: link name
        :param type: link type
        :param start_resource: start resource reference id, uuid
        :param end_resource: end resource reference id, uuid
        :param attributes: link attributes [default={}]            
        :return: link uuid            
        :raise ApiManagerError:
        """
        # check authorization
        if operation.authorize is True:
            self.check_authorization(ResourceLink.objtype, ResourceLink.objdef, None, 'insert')
        
        # get resources
        start_resource_id = self.get_simple_resource(start_resource).oid
        end_resource_id = self.get_simple_resource(end_resource).oid
    
        try:
            objid = id_gen()
            attributes = jsonDumps(attributes)
            link = self.manager.add_link(objid, name, type, start_resource_id, end_resource_id, attributes=attributes)
            
            # add object and permission
            ResourceLink(self, oid=link.id).register_object([objid], desc=name)
    
            self.logger.info('Add new link: %s' % name)
            return link.uuid
        except TransactionError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    #
    # jobs
    #
    def __get_task(self, task_id):
        try:
            redis_manager = self.redis_taskmanager
            task = redis_manager.get(task_manager.conf.CELERY_REDIS_RESULT_KEY_PREFIX + task_id)
            task = json.loads(task)
        except:
            task = {}
        return task

    @trace(entity='Resource', op='use')
    def add_job(self, job_id, job_name, params):
        self.manager.add_job(job_id, job_name, params=compat(params))

    @trace(entity='Resource', op='use')
    def get_jobs(self, jobstatus=None, job=None, name=None, container=None, resources=None, from_date=None, size=10):
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
            self.check_authorization('task', 'Manager', '*', 'view')

        jobs, count = self.manager.get_jobs(job=job, name=name, resource=None, container=container, resources=resources,
                                            from_date=from_date, size=size)

        res = []
        for j in jobs:
            task = self.__get_task(j.job)
            status = task.get('status', None)

            # childs = t.get('children', [])
            # if childs is not None:
            #     for child in childs:
            #         jobs = child.get('jobs', [])
            #         res[info(child)] = OD()
            #         for job in jobs:
            #             res[info(child)][info(job)] = explore(job)

            # childrens = []
            # children_jobs = []
            # main_task = task.get('children', [])
            # if len(main_task) > 0:
            #     main_task = self.__get_task(main_task[0])
            #     childrens = main_task.get('children', [])
            #     for children in childrens:
            #         children = self.__get_task(children)
            #         children_jobs.extend(children.get('jobs', []))
            if jobstatus is None or status == jobstatus:
                start_time = format_date(j.creation_date)
                stop_time = task.get('stop_time', None)
                if stop_time is not None:
                    stop_time = self.convert_timestamp(stop_time)
                res.append({
                    'id': j.job,
                    'name': j.name,
                    'resource': j.resource_id,
                    'container': j.container_id,
                    'params': json.loads(j.params),
                    'start_time': start_time,
                    'stop_time': stop_time,
                    'status': status,
                    'worker': task.get('worker', None),
                    # 'tasks': len(childrens),
                    # 'jobs': len(children_jobs),
                    'elapsed': task.get('stop_time', 0) - task.get('start_time', 0)
                })

        self.logger.info('Get jobs: %s' % truncate(res))

        return res, count
