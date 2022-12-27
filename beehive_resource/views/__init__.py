# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.types.type_class import import_class
from beecell.types.type_string import str2bool
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Resource
from beehive_resource.view import ResourceApiView as ResourceApiViewV1


class ResourceApiView(ResourceApiViewV1):
    resclass = Resource
    parentclass = Resource
    containerclass = None

    def __get_resource_class(self):
        resclass = None
        if self.resclass != Resource:
            resclass = self.resclass
        return resclass

    def __get_parent_resource_class(self):
        resclass = None
        if self.parentclass != Resource:
            resclass = self.parentclass
        return resclass

    def __get_resource_class_for_create(self, data):
        if self.resclass == Resource:
            resclass_name = data.get(self.resclass.objname, {}).get('resclass')
            resclass = import_class(resclass_name)
        else:
            resclass = self.resclass
        return resclass

    def __get_resource(self, controller, oid):
        return controller.get_resource(oid, entity_class=self.__get_resource_class(), cache=False)

    def __get_parent_resource(self, controller, oid):
        return controller.get_resource(oid, entity_class=self.__get_parent_resource_class(), cache=False)

    def __exist_resource(self, controller, data, check_name=True):
        """check if already exists

        :param controller:
        :param data:
        :param check_name:
        :return:
        """
        container = self.get_container(controller, data.pop('container', None))

        if check_name is True:
            try:
                obj = controller.get_simple_resource(data.get('name'), entity_class=self.__get_resource_class(),
                                                     container_id=container.oid)
            except:
                obj = None

            if obj is not None:
                raise ApiManagerError('%s %s already exists' % (self.resclass.objname, data.get('name')), code=409)
        return container

    def __set_parent(self, controller, data):
        """set parent

        :param controller:
        :param data:
        :return:
        """
        if self.parentclass == Resource:
            key = 'parent'
        else:
            key = self.parentclass.objname
        parent_id = data.pop(key, None)
        if parent_id is not None:
            self.logger.debug('Parent id: %s' % parent_id)
            parent = self.__get_parent_resource(controller, parent_id)
            data['parent'] = parent # parent.oid
        else:
            self.logger.warning('Parent id was not specified')
            data['parent'] = None
        return data

    def create_resource(self, controller, data, check_name=True):
        """create resource

        :param controller:
        :param data:
        :param check_name:
        :return:
        """
        resclass = self.__get_resource_class_for_create(data)
        if controller.is_class_task_version_v2(resclass):
            res = super().create_resource(controller, data, check_name=check_name)
        elif controller.is_class_task_version_v3(resclass):
            data = data.get(self.resclass.objname, {})
            container = self.__exist_resource(controller, data, check_name=check_name)
            data = self.__set_parent(controller, data)
            sync = data.pop('sync', False)
            res = container.create_resource(resclass, sync=sync, **data)
        return res

    def clone_resource(self, controller, oid, data, check_name=True):
        """
        """
        resclass = self.__get_resource_class_for_create(data)
        res = None, 400
        if controller.is_class_task_version_v3(resclass):
            data = data.get(self.resclass.objname, {})
            # get resource to clone
            resource_class = data.get('resclass')
            resource_id = data.get('resource_id')
            resource_to_clone = controller.get_resource(resource_id, entity_class=resource_class)

            # set container
            container_id = data.get('container', None)
            if container_id is None:
                data['container'] = resource_to_clone.container_id
            container = self.__exist_resource(controller, data, check_name=check_name)

            # set parent
            parent_id = data.pop(self.parentclass.objname, None)
            if parent_id is None:
                data[self.parentclass.objname] = resource_to_clone.parent_id
            data = self.__set_parent(controller, data)

            sync = data.pop('sync', False)
            res = container.clone_resource(resclass, sync=sync, **data)
        return res

    def import_resource(self, controller, data, check_name=True):
        """
        """
        resclass = self.__get_resource_class_for_create(data)
        if controller.is_class_task_version_v2(resclass):
            res = super().import_resource(controller, data)
        elif controller.is_class_task_version_v3(resclass):
            data = data.get(self.resclass.objname, {})
            container = self.__exist_resource(controller, data, check_name=check_name)
            data = self.__set_parent(controller, data)
            sync = data.pop('sync', False)
            res = container.import_resource(resclass, sync=sync, **data)
        return res

    def patch_resource(self, controller, oid, data):
        """
        """
        obj = self.__get_resource(controller, oid)
        if controller.is_class_task_version_v2(obj.__class__):
            data = data.get(self.resclass.objname)
            res = super().patch2(controller, oid, data)
        elif controller.is_class_task_version_v3(obj.__class__):
            data = data.get(self.resclass.objname)
            sync = data.pop('sync', False)
            res = obj.patch2(data, sync=sync)
        return res

    def update_resource(self, controller, oid, data):
        """
        """
        obj = self.__get_resource(controller, oid)

        # old update for sync and task v2
        if controller.is_class_task_version_v2(obj.__class__):
            data = data.get(self.resclass.objname)
            res = obj.update(**data)

        # update for task v3
        elif controller.is_class_task_version_v3(obj.__class__):
            data = data.get(self.resclass.objname)
            sync = data.pop('sync', False)
            res = obj.update2(data, sync=sync)
        return res

    def delete_resource(self, controller, oid, **kvargs):
        """
        """
        obj = self.__get_resource(controller, oid)
        if controller.is_class_task_version_v2(obj.__class__):
            res = super().delete(controller, oid, **kvargs)
        elif controller.is_class_task_version_v3(obj.__class__):
            res = obj.delete2(kvargs, sync=kvargs.pop('sync', False))
        return res

    def expunge_resource(self, controller, oid, **kvargs):
        """
        """
        obj = self.__get_resource(controller, oid)
        if controller.is_class_task_version_v2(obj.__class__):
            # resource = controller.get_resource(oid)
            if str2bool(kvargs.get('deep')) is False:
                res = obj.expunge_internal()
            elif str2bool(kvargs.get('force')) is True or \
                    obj.get_base_state() in ['ACTIVE', 'ERROR', 'UNKNOWN', 'EXPUNGING']:
                res = obj.expunge()
            else:
                raise ApiManagerError('Resource %s is not in a valid state' % oid, code=400)
        elif controller.is_class_task_version_v3(obj.__class__):
            res = obj.expunge2(kvargs, sync=kvargs.pop('sync', False))
        return res