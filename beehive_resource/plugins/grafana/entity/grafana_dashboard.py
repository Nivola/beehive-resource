# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beecell.simple import id_gen
from beecell.types.type_dict import dict_get
from beehive_resource.plugins.grafana.entity import GrafanaResource
from beehive.common.data import trace, operation
from beecell.simple import jsonDumps

logger = logging.getLogger(__name__)


class GrafanaDashboard(GrafanaResource):
    objdef = "Grafana.Dashboard"
    objuri = "dashboards"
    objname = "dashboard"
    objdesc = "Grafana Dashboard"

    default_tags = ["grafana"]
    task_base_path = "beehive_resource.plugins.grafana.task_v2.grafana_dashboard.GrafanaDashboardTask."

    def __init__(self, *args, **kvargs):
        """ """
        GrafanaResource.__init__(self, *args, **kvargs)

        # object uri
        # self.objuri = '/%s/%s/%s' % (self.container.version, self.container.objuri, GrafanaDashboard.objuri)

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
        # get from grafana
        remote_entities = []

        from beehive_resource.plugins.grafana.controller import GrafanaContainer

        grafanaContainer: GrafanaContainer = container

        if ext_id is not None:
            remote_entity = grafanaContainer.conn_grafana.dashboard.get(ext_id)
            remote_entities.append(remote_entity)
        # else:
        #     remote_entities = grafanaContainer.conn_grafana.dashboard.list()

        # add new item to final list
        res = []
        for item in remote_entities:
            dashboard = item["dashboard"]

            # ext_id set null to avoid resource can be deleted in container Grafana synchronization (died resource)
            # ext_id = dashboard["uid"]
            ext_id = None

            # if ext_id not in res_ext_ids:
            name = dashboard["title"]
            parent_id = None
            str_dashboard = jsonDumps(item)
            res.append(
                (
                    GrafanaDashboard,
                    ext_id,
                    parent_id,
                    GrafanaDashboard.objdef,
                    name,
                    str_dashboard,
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
        # get from grafana
        items = []

        # from beehive_resource.plugins.grafana.controller import GrafanaContainer
        # grafanaContainer: GrafanaContainer = container
        # remote_entities = grafanaContainer.conn_grafana.dashboard.list()
        # dashboards = remote_entities["dashboards"]

        # resources = grafanaContainer.get_resources(type="Grafana.Dashboard")
        # logger.debug("+++++ discover_died - resources: %s" % len(resources))
        # for item in resources:
        #     items.append({"id": item["ext_id"], "name": item["name"]})

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
        item_json = entity[5]

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            # "attrib": {},
            "attrib": item_json,
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
        # get from grafana
        from beehive_resource.plugins.grafana.controller import GrafanaContainer

        grafanaContainer: GrafanaContainer = container
        remote_entities = grafanaContainer.conn_grafana.dashboard.list()
        dashboards = remote_entities["dashboards"]

        # create index of remote objs
        remote_entities_index = {i["uid"]: i for i in dashboards}

        entity: GrafanaDashboard
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
        pass
        # ext_obj = self.get_remote_dashboard(self.controller, self.ext_id, self.container, self.ext_id)
        # self.set_physical_entity(ext_obj)

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
            GrafanaDashboard.task_base_path + "create_resource_pre_step",
            GrafanaDashboard.task_base_path + "grafana_dashboard_create_physical_step",
            GrafanaDashboard.task_base_path + "create_resource_post_step",
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
            GrafanaDashboard.task_base_path + "update_resource_pre_step",
            GrafanaDashboard.task_base_path + "grafana_dashboard_update_physical_step",
            GrafanaDashboard.task_base_path + "update_resource_post_step",
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
            GrafanaDashboard.task_base_path + "expunge_resource_pre_step",
            GrafanaDashboard.task_base_path + "grafana_dashboard_delete_physical_step",
            GrafanaDashboard.task_base_path + "expunge_resource_post_step",
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
        info = GrafanaResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = GrafanaResource.detail(self)
        return info
