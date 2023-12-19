# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import truncate, id_gen
from beecell.db import QueryError
from beehive.common.data import trace
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet


class OpenstackRouter(OpenstackResource):
    objdef = "Openstack.Domain.Project.Router"
    objuri = "routers"
    objname = "router"
    objdesc = "Openstack routers"

    default_tags = ["openstack", "router"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_router.RouterTask."

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.network = None

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
            items = container.conn.network.router.get()
        else:
            items = container.conn.network.router.list()

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = item["tenant_id"]

                res.append(
                    (
                        OpenstackRouter,
                        item["id"],
                        parent_id,
                        OpenstackRouter.objdef,
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
        :raise ApiManagerError:
        """
        return container.conn.network.router.list()

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

        # get parent project
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            objid = "%s//%s" % (parent.objid, id_gen())
            parent_id = parent.oid
        else:
            objid = "%s//none//none//%s" % (container.objid, id_gen())
            parent_id = None

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
        # remote_entities = container.conn.network.router.list()

        # get related object
        from ..entity.ops_network import OpenstackNetwork

        net_index = controller.index_resources_by_extid(OpenstackNetwork)

        # create index of remote objs
        # remote_entities_index = {i['id']: i for i in remote_entities}

        for entity in entities:
            ext_obj = OpenstackRouter.get_remote_router(controller, entity.ext_id, container, entity.ext_id)
            entity.set_physical_entity(ext_obj)
            if ext_obj.get("external_gateway_info", None) is not None:
                net_id = ext_obj["external_gateway_info"]["network_id"]
                entity.network = net_index[net_id]
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_router(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)
        if ext_obj.get("external_gateway_info", None) is not None:
            net_id = ext_obj["external_gateway_info"]["network_id"]
            self.network = self.controller.get_resource_by_extid(net_id)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param routes:
        :param kvargs.external_gateway_info:
        :param kvargs.external_gateway_info.network_id: router external network id
        :param kvargs.external_gateway_info.external_fixed_ips: [optional] router external_ips.
            Ex. [{'subnet_id': '255.255.255.0', 'ip': '192.168.10.1'}]
        :param kvargs.routes: custom routes. Ex. [{"destination": "179.24.1.0/24", "nexthop": "172.24.3.99"}]
        :return: kvargs
        :raise ApiManagerError:
        """
        # get network id
        external_gateway_info = kvargs.get("external_gateway_info", None)
        if external_gateway_info is not None:
            network = container.get_resource(external_gateway_info["network_id"], entity_class=OpenstackNetwork)
            external_gateway_info["network_id"] = network.ext_id

            # get optional external_fixed_ips
            external_fixed_ips = external_gateway_info.get("external_fixed_ips", None)
            if external_fixed_ips is not None:
                for item in external_fixed_ips:
                    subnet = container.get_resource(item["subnet_id"], entity_class=OpenstackSubnet)
                    item["subnet_id"] = subnet.ext_id

        # get parent project
        project = controller.get_resource(kvargs["parent"])

        params = {"desc": "Router %s" % kvargs["name"], "project_extid": project.ext_id}
        kvargs.update(params)

        steps = [
            OpenstackRouter.task_path + "create_resource_pre_step",
            OpenstackRouter.task_path + "router_create_physical_step",
            OpenstackRouter.task_path + "router_create_ports_physical_step",
            OpenstackRouter.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackRouter.task_path + "update_resource_pre_step",
            OpenstackRouter.task_path + "router_update_physical_step",
            OpenstackRouter.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs["ha_tenant_network"] = self.attribs.get("ha_tenant_network", [])

        steps = [
            OpenstackRouter.task_path + "expunge_resource_pre_step",
            OpenstackRouter.task_path + "router_delete_ports_physical_step",
            OpenstackRouter.task_path + "router_delete_network_physical_step",
            OpenstackRouter.task_path + "router_delete_physical_step",
            OpenstackRouter.task_path + "expunge_resource_post_step",
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
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data["status"] = self.ext_obj.get("status")
            try:
                external_gateway_info = self.ext_obj.get("external_gateway_info", {})
                data["external_network"] = self.network.small_info()
                data["external_ips"] = external_gateway_info.get("external_fixed_ips")
                for conf in data["external_ips"]:
                    subnet = self.container.get_resource_by_extid(conf["subnet_id"])
                    conf["subnet_id"] = subnet.uuid
                data["enable_snat"] = external_gateway_info.get("enable_snat")
            except:
                data["external_network"] = None
                data["external_ips"] = None
                data["enable_snat"] = None

            info["details"] = data

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            data["status"] = self.ext_obj.get("status")
            data["routes"] = self.ext_obj.get("routes")
            data["ha"] = self.ext_obj.get("ha")

            try:
                external_gateway_info = self.ext_obj.get("external_gateway_info", {})
                data["external_network"] = self.network.small_info()
                data["external_ips"] = external_gateway_info.get("external_fixed_ips")
                for conf in data["external_ips"]:
                    subnet = self.container.get_resource_by_extid(conf["subnet_id"])
                    conf["subnet_id"] = subnet.uuid
                data["enable_snat"] = external_gateway_info.get("enable_snat")
            except:
                data["external_network"] = None
                data["external_ips"] = None
                data["enable_snat"] = None

            info["details"].update(data)

        return info

    def register_object(self, objids, desc=""):
        """Register object types, objects and permissions related to module.

        :param objids: objid split by //
        :param desc: object description
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        OpenstackResource.register_object(self, objids, desc=desc)

        # check new HA network
        from ..entity.ops_network import OpenstackNetwork

        # - get ports from router
        if self.ext_id is not None:
            ports = self.container.conn.network.port.list(device_id=self.ext_id)

            for port in ports:
                ext_id = port["network_id"]
                device_owner = port["device_owner"]

                if device_owner == "network:router_ha_interface":
                    if self.container.get_resource_by_extid(ext_id) is None:
                        # new HA network - register as new resource
                        net = self.container.conn.network.get(oid=ext_id)
                        name = net["name"]

                        # get parent project
                        desc = "Openstack %s network %s" % (self.container.name, name)
                        objid = "%s//none//none//%s" % (self.container.objid, id_gen())
                        model = self.add_resource(
                            objid=objid,
                            name=name,
                            resource_class=OpenstackNetwork,
                            ext_id=ext_id,
                            active=True,
                            desc=desc,
                            attrib={},
                            parent=None,
                        )

                        self.logger.debug("Register new network %s" % name)

    # def clean_cache(self):
    #     """Clean cache
    #     """
    #     super(OpenstackRouter, self).clean_cache()
    #
    #     self.cache.delete_by_pattern('openstack.router.get.%s' % self.ext_id)

    @trace(op="view")
    def get_ports(self, network=None):
        """Get router ports.

        :param network: openstack network id [optional]
        :return: List of OpenstackPort instance
        :rtype: list
        :raises ApiManagerError: if query empty return error.
        """
        # get related object
        from ..entity.ops_network import OpenstackNetwork
        from ..entity.ops_project import OpenstackRouter

        # create related object index
        net_index = self.controller.index_resources_by_extid(entity_class=OpenstackNetwork)
        prj_index = self.controller.index_resources_by_extid(entity_class=OpenstackRouter)

        try:
            if network is not None:
                network = self.controller.get_simple_resource(network).ext_id

            # get ports from openstack
            items = self.container.conn.network.port.list(device_id=self.ext_id, network=network)

            # get resources
            res = []
            for item in items:
                # set subnet
                def replace_subnet(item):
                    try:
                        subnet = self.controller.get_resource_by_extid(item["subnet_id"])
                        item["subnet_id"] = subnet.uuid
                    except:
                        item["subnet_id"] = None
                    return item

                for fixed_ip in item["fixed_ips"]:
                    fixed_ip = replace_subnet(fixed_ip)

                port = self.controller.get_resource_by_extid(item["id"])
                port.set_physical_entity(item)
                port.container = self.container
                # set network
                port.network = net_index.get(item["network_id"], None)
                # set project
                port.project = prj_index.get(item.get("tenant_id"), None)
                # set device
                port.device = self

                res.append(port)

            self.logger.debug("Get openstack %s router %s ports: %s" % (self.container.oid, self.oid, truncate(res)))
            return res
        except (QueryError, Exception) as ex:
            self.logger.warning(ex, exc_info=1)
            return []

    @trace(op="update")
    def create_port(self, params, sync=False):
        """Create openstack router port.

        :param params: input params
        :param params.subnet_id: subnet id, uuid
        :param params.ip_address: ip_address [optional]
        :param params.network_id: network id [optional]
        :param sync: set sync task execution
        :return:entity instance
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        kvargs = {}

        # get ipaddress
        ip_address = params.get("ip_address", None)
        if ip_address is not None:
            network = self.container.get_simple_resource(params.get("network_id"), entity_class=OpenstackNetwork)
            kvargs = {"ip_address": ip_address, "network_id": network.ext_id}

        # get subnet
        subnet = self.container.get_simple_resource(params.get("subnet_id"), entity_class=OpenstackSubnet)
        kvargs.update({"subnet_id": subnet.ext_id, "sync": sync})
        steps = [OpenstackRouter.task_path + "router_port_add_step"]
        res = self.action("add_router_port", steps, log="Add router port", check=None, **kvargs)
        return res

    @trace(op="update")
    def delete_port(self, params, sync=False):
        """Delete openstack router port.

        :param params: input params
        :param params.subnet_id: subnet id, uuid
        :param sync: set sync task execution
        :return:entity instance
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # get subnet
        subnet = self.container.get_resource(params.get("subnet_id"), entity_class=OpenstackSubnet)
        kvargs = {"subnet_id": subnet.ext_id, "sync": sync}
        steps = [OpenstackRouter.task_path + "router_port_delete_step"]
        res = self.action("del_router_port", steps, log="Delete router port", check=None, **kvargs)
        return res

    def get_routes(self):
        """get router route"""
        res = []
        if self.ext_obj is not None:
            res = self.ext_obj.get("routes")
        return res

    def add_route(self, route):
        """add route to router

        :param route: route configuration {'destination':.., 'nexthop':..}
        :return:
        """
        if self.ext_id is not None:
            self.clean_cache()
            destination = route["destination"]
            nexthop = route["nexthop"]
            res = self.container.conn.network.router.add_route(self.ext_id, destination, nexthop)
            return res
        return False

    def del_route(self, route):
        """delete route from router

        :param route: route configuration {'destination':.., 'nexthop':..}
        :return:
        """
        if self.ext_id is not None:
            self.clean_cache()
            destination = route["destination"]
            nexthop = route["nexthop"]
            res = self.container.conn.network.router.del_route(self.ext_id, destination, nexthop)
            return res
        return False

    def add_routes(self, routes):
        """add routes to router

        :param routes: routes configuration [{'destination':.., 'nexthop':..}]
        :return: True or False
        """
        if self.ext_id is not None:
            self.clean_cache()
            previous_routes = self.get_routes()
            for route in routes:
                if route not in previous_routes:
                    previous_routes.append(route)
            res = self.container.conn.network.router.add_routes(self.ext_id, previous_routes)
            return res
        return False

    def del_routes(self, routes):
        """delete routes from router

        :param routes: routes configuration [{'destination':.., 'nexthop':..}]
        :return: True or False
        """
        if self.ext_id is not None:
            self.clean_cache()
            previous_routes = self.get_routes()
            for route in routes:
                if route in previous_routes:
                    previous_routes.remove(route)
            res = self.container.conn.network.router.add_routes(self.ext_id, previous_routes)
            return res

        return False

    def reset_routes(self):
        """delete all routes from router

        :return: True or False
        """
        if self.ext_id is not None:
            self.clean_cache()

            from beedrones.openstack.network import OpenstackRouter
            from beehive_resource.plugins.openstack.controller import OpenstackContainer
            from beedrones.openstack.client import OpenstackManager

            openstackContainer: OpenstackContainer = self.container
            openstackManager: OpenstackManager = openstackContainer.conn
            openstackRouter: OpenstackRouter = openstackManager.network.router
            res = openstackRouter.update(self.ext_id, routes=[])
            return res
        return False
