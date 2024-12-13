# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beecell.simple import id_gen
from beecell.types.type_dict import dict_get
from beehive_resource.plugins.veeam.entity import VeeamResource
from beehive.common.data import trace, operation

logger = logging.getLogger(__name__)


class VeeamJob(VeeamResource):
    objdef = "Veeam.Job"
    objuri = "jobs"
    objname = "job"
    objdesc = "Veeam.Job"

    default_tags = ["veeam"]
    task_base_path = "beehive_resource.plugins.veeam.task_v2.veeam_job.VeeamJobTask."

    def __init__(self, *args, **kvargs):
        """ """
        VeeamResource.__init__(self, *args, **kvargs)

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, VeeamJob.objuri)

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
        logger.debug("+++++ discover_new - res_ext_ids {}".format(res_ext_ids))

        # get from veeam
        logger.debug("+++++ discover_new - ext_id {}".format(ext_id))
        if ext_id is not None:
            items = container.conn_veeam.job.get(ext_id)
        else:
            items = container.conn_veeam.job.list()

        # add new item to final list
        res = []
        for item in items:
            item_id = str(item["id"])
            logger.debug("+++++ discover_new - item_id {}".format(item_id))
            if item_id not in res_ext_ids:
                level = None
                name = item["name"]
                # status = item['status']
                parent_id = None
                logger.debug("+++++ discover_new - append item_id {}".format(item_id))
                res.append((VeeamJob, item_id, parent_id, VeeamJob.objdef, name, level))  # , status))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """

        # get from veeam
        items = []
        remote_entities = container.conn_veeam.job.list()
        for item in remote_entities:
            logger.debug("+++++ discover_died - id {}".format(item["id"]))
            items.append({"id": str(item["id"]), "name": item["name"]})

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
        # get from veeam
        remote_entities = container.conn_veeam.job.list()

        # create index of remote objs
        remote_entities_index = {i["id"]: i for i in remote_entities}

        entity: VeeamJob
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
                entity.get_veeam_user()
            except:
                container.logger.warn("", exc_info=1)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_job(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)
        self.get_veeam_user()

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
        steps = [
            VeeamJob.task_base_path + "create_resource_pre_step",
            VeeamJob.task_base_path + "veeam_job_create_physical_step",
            VeeamJob.task_base_path + "create_resource_post_step",
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
            VeeamJob.task_base_path + "update_resource_pre_step",
            VeeamJob.task_base_path + "veeam_job_update_physical_step",
            VeeamJob.task_base_path + "update_resource_post_step",
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
            VeeamJob.task_base_path + "expunge_resource_pre_step",
            VeeamJob.task_base_path + "veeam_job_delete_physical_step",
            VeeamJob.task_base_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
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
        info = VeeamResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = VeeamResource.detail(self)
        return info
