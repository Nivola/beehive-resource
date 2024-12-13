# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beecell.simple import id_gen
from beehive_resource.plugins.openstack.entity import OpenstackResource
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject

logger = getLogger(__name__)


class OpenstackDomain(OpenstackResource):
    objdef = "Openstack.Domain"
    objuri = "domains"
    objname = "domain"
    objdesc = "Openstack domains"
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_domain.DomainTask."

    default_tags = ["openstack"]

    create_task = None
    update_task = None
    expunge_task = None

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = [OpenstackProject]

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)

        :raises ApiManagerError:
        """
        # get from openstack
        if ext_id is not None:
            items = container.conn.domain.get(oid=ext_id)
        else:
            items = container.conn.domain.list()

        # add new item to final list
        res = []
        for item in items:
            itemid = "%s-%s" % (container.oid, item["id"])
            if itemid not in res_ext_ids:
                level = None
                parent_id = None
                name = item["name"]

                res.append(
                    (
                        OpenstackDomain,
                        itemid,
                        parent_id,
                        OpenstackDomain.objdef,
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
        items = container.conn.domain.list()
        for item in items:
            item["id"] = "%s-%s" % (container.oid, item["id"])

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
        level = entity[5]

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
        remote_entities = container.conn.domain.list()

        # create index of remote objs
        remote_entities_index = {"%s-%s" % (container.oid, i["id"]): i for i in remote_entities}

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
        try:
            ext_id = self.ext_id.split("-")[1]
            ext_obj = self.container.conn.domain.get(oid=ext_id)
            self.set_physical_entity(ext_obj)
        except:
            pass
