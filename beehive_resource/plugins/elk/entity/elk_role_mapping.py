# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beecell.simple import id_gen
from beehive_resource.plugins.elk.entity import ElkResource

# from beehive_resource.plugins.elk.controller import ElkContainer

logger = logging.getLogger(__name__)


class ElkRoleMapping(ElkResource):
    objdef = "Elk.RoleMapping"
    objuri = "role_mappings"
    objname = "role_mapping"
    objdesc = "Elk RoleMapping"

    default_tags = ["elk"]
    task_base_path = "beehive_resource.plugins.elk.task_v2.elk_role_mapping.ElkRoleMappingTask."

    def __init__(self, *args, **kvargs):
        """ """
        ElkResource.__init__(self, *args, **kvargs)

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, ElkRoleMapping.objuri)

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to communicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)
        :raises ApiManagerError:
        """
        # get from elk
        # container: ElkContainer
        if ext_id is not None:
            remote_entities = container.conn_elastic.role_mapping.get(ext_id)
        else:
            remote_entities = container.conn_elastic.role_mapping.list()

        # add new item to final list
        res = []
        for item in remote_entities:
            logger.debug("discover_new - item: {}".format(item))
            item_id = item  # item[0]
            if item_id not in res_ext_ids:
                level = None
                name = item_id
                parent_id = None
                res.append(
                    (
                        ElkRoleMapping,
                        item_id,
                        parent_id,
                        ElkRoleMapping.objdef,
                        name,
                        level,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # get from elk
        items = []
        remote_entities = container.conn_elastic.role_mapping.list()
        for item in remote_entities:
            logger.debug("discover_died - item: {}".format(item))
            item_id = item  # item[0]
            items.append({"id": item_id, "name": item_id})

        return items

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

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "resource_class": resclass,
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
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        # get from elk
        # container: ElkContainer
        remote_entities = container.conn_elastic.role_mapping.list()

        # create index of remote objs
        remote_entities_index = {i[0]: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn("", exc_info=1)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_role_mapping(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.vcpus: vcpus
        :param kvargs.ram: ram
        :param kvargs.disk: disk
        :return: kvargs
        :raise ApiManagerError:
        """
        # def get_organization_id(name):
        #     res = container.conn.organization.list(name=name)
        #     if len(res) > 1:
        #         msg = 'More than an organization with the same name'
        #         logger.error(msg)
        #         raise Exception(msg)
        #     return res[0].get('id')

        # def get_credentials_id(name):
        #     res = container.conn.credential.list(name=name)
        #     if len(res) > 1:
        #         msg = 'More than a credential with the same name'
        #         logger.error(msg)
        #         raise Exception(msg)
        #     return res[0].get('id')

        # org_name = kvargs.pop('organization')
        # scm_creds = kvargs.pop('scm_creds_name')

        # try:
        #     org_ext_id = get_organization_id(org_name)
        #     scm_creds_ext_id = get_credentials_id(scm_creds)
        # except Exception as ex:
        #     logger.error(ex, exc_info=True)
        #     raise Exception(ex)

        # kvargs['scm_creds'] = scm_creds_ext_id
        # kvargs['org_ext_id'] = org_ext_id

        steps = [
            ElkRoleMapping.task_base_path + "create_resource_pre_step",
            ElkRoleMapping.task_base_path + "elk_role_mapping_create_physical_step",
            ElkRoleMapping.task_base_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        # kvargs['sync'] = True # non fa partire i task

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            ElkRoleMapping.task_base_path + "update_resource_pre_step",
            ElkRoleMapping.task_base_path + "elk_role_mapping_update_physical_step",
            ElkRoleMapping.task_base_path + "update_resource_post_step",
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
            ElkRoleMapping.task_base_path + "expunge_resource_pre_step",
            ElkRoleMapping.task_base_path + "elk_role_mapping_delete_physical_step",
            ElkRoleMapping.task_base_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
        # kvargs['sync'] = True # non fa partire i task

        return kvargs

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return ElkResource.info(self)

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ElkResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            info["details"].update(data)

        return info
