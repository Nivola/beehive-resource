# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger
from beecell.types.type_class import import_class
from beecell.types.type_dict import dict_get
from beecell.types.type_string import truncate
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import operation, trace
from beehive_resource.controller import AbstractResourceController
from beehive_resource.container import ResourceLink, ResourceTag, ResourceContainer, Resource

logger = getLogger(__name__)


class ResourceController(AbstractResourceController):
    """Resource Module controller based on mongo db

    :param ApiModule module: beehive module instance
    """
    version = 'v2.0'  #: version

    def __init__(self, module):
        super().__init__(module)

        #: db manager reference
        self.manager = self.api_manager.db_manager

    #
    # count
    #
    def count_all_containers(self):
        """Get all containers count"""
        return self.manager.container.count_documents({})

    def count_all_resources(self):
        """Get all resources count"""
        return self.manager.entity.count_documents({})

    def count_all_tags(self):
        """Get all resource tags count"""
        return self.manager.entity_tag.count_documents({})

    def count_all_links(self):
        """Get all resource links count"""
        return self.manager.entity_link.count_documents({})

    #
    # helper model for entities
    #
    def get_apiobject_instance(self, model, entity_class, *args, **kwargs):
        inst = super().get_apiobject_instance(model, entity_class, *args, **kwargs)

        post_get = getattr(inst, 'post_get', None)
        if post_get is not None:
            post_get()

        # # customize entity
        # run_customize = kwargs.pop('run_customize', True)
        # customize = kwargs.pop('customize', None)
        # if run_customize is True and customize is not None:
        #     # inst = customize(inst, *args, **kwargs)
        #     inst = customize(inst)

        return inst

    def get_entity_for_task(self, entity_class, oid, *args, **kwargs):
        """get single entity usable bya a celery task.

        :param entity_class: Controller ApiObject Extension class
        :param oid: entity id
        :return: entity instance
        :raise ApiManagerError`:
        """
        model = None
        if entity_class == Resource or issubclass(entity_class, Resource) is True:
            entity = self.manager.entity.find_one({'oid': oid})
            if entity is None:
                raise ApiManagerError('no entity %s found' % oid)
            model = 'entity'
        elif entity_class == ResourceContainer or issubclass(entity_class, ResourceContainer) is True:
            entity = self.manager.container.find_one({'oid': oid})
            if entity is None:
                raise ApiManagerError('no container %s found' % oid)
            model = 'container'

        # import class
        int_entity_class = import_class(dict_get(entity, 'type.objclass'))
        inst = int_entity_class(self, oid=entity.get('id'), objid=entity.get('objid'), name=entity.get('name'),
                                active=entity.get('active'), desc=entity.get('desc'), model=entity)

        # if it is a resource subclass set container and run post_get
        if model == 'entity':
            container = self.get_container(entity.get('container_id'))
            inst.set_container(container)
            inst.post_get()

        self.logger.info('get %s : %s' % (int_entity_class.__name__, inst))
        return inst

    def get_entity_v2(self, collection_name, oid, entity_class=None, customize=None, run_customize=True,
                      *args, **kwargs):
        """get single entity by oid (id, uuid, name) if exists

        :param collection_name: mongodb collection to use
        :param oid: entity model id or name or uuid
        :param entity_class: Controller ApiObject Extension class. Specify when you want to verify match between
            objdef of the required resource and find resource. [optional]
        :param kwargs: custom params
        :param kwargs.customize: function used to customize entities. [optional]
            Signature def customize(entities, *args, **kwargs)
        :param kwargs.run_customize: if True run customize [default=True]
        :return: entity instance
        :raise ApiManagerError`:
        """
        collection = getattr(self.manager, collection_name)
        model = collection.find_one({'oid': oid})
        if model is None:
            raise ApiManagerError('no %s %s found' % (collection_name, oid), code=404)

        if entity_class is not None:
            int_entity_class = entity_class
        else:
            int_entity_class = import_class(self.get_model_attribute(model, 'type.objclass'))

        # check objdef match with required
        if entity_class is not None and dict_get(model, 'type.objdef') != entity_class.objdef:
            raise ApiManagerError('%s %s %s not found' % (collection_name, entity_class.objname, oid), code=404)

        # check authorization
        if operation.authorize is True:
            self.check_authorization(int_entity_class.objtype, int_entity_class.objdef,
                                     self.get_model_attribute(model, 'objid'), 'view')

        inst = self.get_apiobject_instance(model, entity_class, *args, **kwargs)
        self.logger.info('get %s : %s' % (entity_class.__name__, inst))
        return inst

    def get_entities_v2(self, objtype, get_entities, page=0, size=10, order='DESC', field='id', *args, **kwargs):
        """get entities with pagination

        :param objtype: objtype to use. Example container, resource
        :param get_entities: model get_entities function. Return (entities, total)
        :param page: objects list page to show [default=0]
        :param size: number of objects to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        #####:param objdef: obj definition to use. Example vsphere.datacenter.folder [optional]
        :param args: custom params
        :param kwargs: custom params
        :param kwargs.entity_class: entity_class you expect to receive [optional]
        :param kwargs.customize: function used to customize entities. [optional]
            Signature def customize(entities, *args, **kwargs)
        :param kwargs.run_customize: if True run customize [default=True]
        :param kwargs.authorize: if False disable authorization check
        :param kwargs.name: name like [optional]
        :param kwargs.active: active [optional]
        :param kwargs.creation_date: creation_date [optional]
        :param kwargs.modification_date: modification_date [optional]
        :return: (list of entity instances, total)
        :raise ApiManagerError:
        """
        res = []
        permtags = []
        filters = {}

        entity_class = kwargs.pop('entity_class', None)
        if entity_class is not None:
            objdef = entity_class.objdef
            filters['type.objdef'] = objdef

        # if entity_class is not None and objdef is not None and entity_class.objdef != objdef:
        #     raise ApiManagerError('entity_class objdef and objdef mismatch')

        if operation.authorize is False or kwargs.get('authorize', True) is False:
            self.logger.debug('Authorization disabled for command')
        elif operation.authorize is True:
            # verify permissions
            objs = self.can('view', objtype=objtype, definition=objdef)

            # create permission tags
            for entity_def, ps in objs.items():
                for p in ps:
                    permtags.append(self.hash_from_permission(entity_def, p))
            filters['permtags'] = {'$in': permtags}
            # self.logger.debug('Permission tags to apply: %s' % truncate(tags))

        try:
            # customize_args = {
            #     'run_customize': kwargs.pop('run_customize', True),
            #     'customize': kwargs.pop('customize', None)
            # }
            models, total = get_entities(order=order, field=field, filters=filters,
                                         *args, **kwargs).limit(size).skip(page*size)

            for model in models:
                # if entity_class is None:
                #     objclass = import_class(self.get_model_attribute(model, 'type.objclass'))
                # else:
                #     objclass = entity_class
                #
                # # bypass object that does not match objdef
                # if objdef is not None and objclass.objdef != objdef:
                #     continue

                objclass = import_class(self.get_model_attribute(model, 'type.objclass'))

                # inst = self.get_apiobject_instance(model, entity_class, **customize_args)
                inst = self.get_apiobject_instance(model, objclass)
                res.append(inst)

            self.logger.info('get %s (total:%s): %s' % (objtype, total, truncate(res)))
            return res, total
        except Exception as ex:
            self.logger.warning(ex, exc_info=True)
            return [], 0

    #
    # resource
    #
    @trace(entity='Resource', op='view')
    def get_resources(self, page=0, size=10, order='DESC', field='id', *args, **kwargs):
        """Get resources.

        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param kwargs.objid: resource objid [optional]
        :param kwargs.name: resource name [optional]
        :param kwargs.ids: list of resource oid [optional]
        :param kwargs.uuids: comma separated list of resource uuid [optional]
        :param kwargs.ext_ids: list of id of resource in the remote container [optional]
        :param kwargs.parent_ids: comma separated parent resource ids [optional]
        :param kwargs.tags: list of tags comma separated. All tags in the list must be met [optional]
        :param kwargs.types: comma separated resource type. Use complete syntax or %<type1>% for each type.
        :param ext_obj: subfileds contained in ext_obj [optional]
        :param kwargs.container: resource container id [optional]
        :param kwargs.attribute: resource attribute [optional]
        :param kwargs.active: resource active [optional]
        :param kwargs.state: resource state [optional]
        :param kwargs.creation_date: resource creation date [optional]
        :param kwargs.modification_date: resource modification date [optional]
        :param kwargs.show_expired: if True show expired resources [default=False]
        :return: :py:class:`list` of :class:`Resource`
        :raise ApiManagerError:        
        """
        def get_entities(*args, **kwargs):
            filters = kwargs.pop('filters', {})

            def add_filter(param_name, transform=None):
                # do nothing
                if transform is None:
                    transform = lambda x: x

                param_value = kwargs.pop(param_name, None)
                filters[param_name] = transform(param_value)

            params = {
                'objid': None,
                'name': None,
                'ids': lambda x: x.split(','),
                'uuids': lambda x: x.split(','),
                'ext_ids': lambda x: x.split(','),
                'parent_ids': lambda pl: [self.get_simple_resource(p).oid for p in pl.split(',')],
                'tags': None,
                'types': lambda ts: [self.get_resource_types(t).oid for t in ts.split(',')],
                'cotainer': lambda x: self.get_container(x).oid,
                'attribute': None,
                'active': None,
                'state': None,
                'creation_date': None,
                'modification_date': None,
                'show_expired': None
            }

            for param, transform in params.items():
                add_filter(param, transform)

            # get resource extended class specific filter
            if len(params['ts'] == 1):
                entity_class = import_class(params['ts'][0].objclass)
                kwargs['entity_class'] = entity_class
                filters = entity_class.add_query_filter(filters, *args, **kwargs)

            total = self.manager.entity.count_documents(filters)
            models = self.manager.entity.find(filters)

            return models, total

        res, total = self.get_entities_v2('resource', get_entities, page=page, size=size, order=order, field=field,
                                          *args, **kwargs)
        return res, total
