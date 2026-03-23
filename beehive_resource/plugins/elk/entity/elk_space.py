# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

import logging
from time import sleep
from beecell.simple import id_gen
from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.controller import ResourceController
from beehive_resource.plugins.elk.entity import ElkResource
from beehive.common.data import trace, operation

logger = logging.getLogger(__name__)


class ElkSpace(ElkResource):
    objdef = "Elk.Space"
    objuri = "spaces"
    objname = "space"
    objdesc = "Elk Space"

    default_tags = ["elk"]
    task_base_path = "beehive_resource.plugins.elk.task_v2.elk_space.ElkSpaceTask."

    def __init__(self, *args, **kvargs):
        """ """
        ElkResource.__init__(self, *args, **kvargs)

        self.dashboards = []

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, ElkSpace.objuri)

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
        if ext_id is not None:
            remote_entities = [container.conn_kibana.space.get(ext_id)]
        else:
            remote_entities = container.conn_kibana.space.list()

        # add new item to final list
        res = []
        for item in remote_entities:
            if item["id"] not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = None
                res.append((ElkSpace, item["id"], parent_id, ElkSpace.objdef, name, level))

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
        remote_entities = container.conn_kibana.space.list()
        for item in remote_entities:
            items.append({"id": item["id"], "name": item["name"]})

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
        remote_entities = container.conn_kibana.space.list()

        # create index of remote objs
        remote_entities_index = {i["id"]: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
                entity.get_dashboard()
            except:
                container.logger.warn("", exc_info=1)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_space(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)
        self.get_dashboard()

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
            ElkSpace.task_base_path + "create_resource_pre_step",
            ElkSpace.task_base_path + "elk_space_create_physical_step",
            ElkSpace.task_base_path + "create_resource_post_step",
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
            ElkSpace.task_base_path + "update_resource_pre_step",
            ElkSpace.task_base_path + "elk_space_update_physical_step",
            ElkSpace.task_base_path + "update_resource_post_step",
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
            ElkSpace.task_base_path + "expunge_resource_pre_step",
            ElkSpace.task_base_path + "elk_space_delete_physical_step",
            ElkSpace.task_base_path + "expunge_resource_post_step",
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
        info = ElkResource.info(self)
        info["dashboards"] = self.dashboards
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = ElkResource.detail(self)
        info["dashboards"] = self.dashboards
        return info

    def get_dashboard(self):
        """get space dashboard"""
        dashboards = self.get_remote_space_dashboards(self.controller, self.ext_id, self.container, self.ext_id)
        self.dashboards = [
            {
                "id": dict_get(d, "id"),
                "desc": dict_get(d, "attributes.title"),
                "version": dict_get(d, "version"),
                "namespaces": dict_get(d, "namespaces"),
                "score": dict_get(d, "score"),
                "updated_at": dict_get(d, "updated_at"),
            }
            for d in dashboards
        ]

    @trace(op="update")
    def add_dashboard(self, space_id_from, dashboard, space_id_to, index_pattern, *args, **kvargs):
        """Add dashboard

        :param dashboard: dashboard name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            # add check dashboard exists
            return kvargs

        kvargs.update(
            {
                "space_id_from": space_id_from,
                "dashboard": dashboard,
                "space_id_to": space_id_to,
                "index_pattern": index_pattern,
            }
        )
        logger.debug("add_dashboard - after update kvargs {}".format(kvargs))

        steps = ["beehive_resource.plugins.elk.task_v2.elk_space.ElkSpaceTask.add_dashboard_step"]
        res = self.action("add_dashboard", steps, log="Add dashboard", check=check, **kvargs)
        logger.debug("add_dashboard - res {}".format(res))

        if "taskid" in res[0]:
            taskid = res[0]["taskid"]
            logger.debug("add_dashboard - taskid: %s" % taskid)
            status = self.wait_task(taskid)
            if status == 'FAILURE':
                raise ApiManagerError("Error in add_dashboard")
            
        return res, "called"
    
    @trace(op="update")
    def delete_dashboard(
        self,
        dashboard_to_search,
        space_id,
        *args,
        **kvargs,
    ):
        """Delete dashboard

        :param dashboard: dashboard name
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            # add check dashboard exists
            return kvargs

        kvargs.update(
            {
                "dashboard_to_search": dashboard_to_search,
                "space_id": space_id,
                # "sync": True, # if sync no taskid in res
            }
        )
        logger.debug("delete_dashboard - after update kvargs {}".format(kvargs))

        steps = ["beehive_resource.plugins.elk.task_v2.elk_space.ElkSpaceTask.delete_dashboard_step"]
        res = self.action("delete_dashboard", steps, log="Delete dashboard", check=check, **kvargs)
        logger.debug("+++++ delete_dashboard - res {}".format(res))

        if "taskid" in res[0]:
            taskid = res[0]["taskid"]
            logger.debug("delete_dashboard - taskid: %s" % taskid)
            status = self.wait_task(taskid)
            if status == 'FAILURE':
                raise ApiManagerError("Error in delete_dashboard")
            
        return res, "called"

    def wait_task(self, taskid, maxtime=180, delta=1):
        elapsed = 0
        status = "SUPERUNKNOWN"
        while status not in ["SUCCESS", "FAILURE", "TIMEOUT"]:
            sleep(delta)
            status = self.get_status(taskid)  
            elapsed += delta
            if elapsed > maxtime:
                status = "TIMEOUT"
        
        return status
    
    def get_status(self, taskid):
        status = "SUPERUNKNOWN"
        from beehive.module.scheduler_v2.model import SchedulerDbManager
        schedulerDbManager = SchedulerDbManager()
        tasks, tot = schedulerDbManager.get_tasks(task_id=taskid, with_perm_tag=False)
        logger.debug("get_status - tot: %s" % tot)
        if tot == 1:
            task = tasks[0]
            status = task.status
            logger.debug("get_status - status: %s" % status)

        return status