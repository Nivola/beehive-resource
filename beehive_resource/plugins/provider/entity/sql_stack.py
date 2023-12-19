# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import random_password, id_gen, bool2str
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack
from beehive_resource.plugins.provider.entity.stack import ComputeStack


class SqlComputeStack(ComputeStack):
    """Sql compute stack"""

    objuri = "%s/sql_stacks/%s"
    objname = "sql_stack"
    task_path = "beehive_resource.plugins.provider.task_v2.stack.StackTask."

    engine = {"mysql": ["5.7"], "postgres": ["9.6"]}

    def __init__(self, *args, **kvargs):
        ComputeStack.__init__(self, *args, **kvargs)

    @staticmethod
    def get_engines():
        """Get list of available engines

        :return: list of {'engine':.., 'version':..}
        """
        res = []
        for k, v in SqlComputeStack.engine.items():
            for v1 in v:
                res.append({"engine": k, "version": v1})
        return res

    def info(self):
        """Get infos.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeStack.info(self)

        info["vpcs"] = [vpc.small_info() for vpc in self.vpcs]
        info["security_groups"] = [sg.small_info() for sg in self.sgs]

        info["stacks"] = []
        for zone_stack in self.zone_stacks:
            listener = zone_stack.output("MasterDatabaseURL")
            if zone_stack.has_remote_stack() is True:
                zone = {
                    "availability_zone": zone_stack.get_site().name,
                    "status_reason": zone_stack.status_reason(),
                    "listener": listener,
                }
                info["stacks"].append(zone)

        return info

    def detail(self):
        """Get details.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = self.info()
        return info

    def get_root_credentials(self):
        """Get database root credentials"""
        user = self.get_attribs("admin_user")
        user["pwd"] = self.controller.decrypt_data(user["pwd"])
        return [user]

    def set_root_credentials(self, credentials):
        """Set database root credentials in resource db

        :param credentials: list of credentials. Ex. {'root': <pwd>}
        """
        credentials[0]["pwd"] = self.controller.encrypt_data(credentials[0]["pwd"])
        self.set_configs("admin_user", credentials[0])

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        resource_ids = [e.oid for e in entities]
        vpcs_all = controller.get_directed_linked_resources_internal(resource_ids, link_type="vpc", run_customize=False)
        sgs_all = controller.get_directed_linked_resources_internal(
            resource_ids, link_type="security-group", run_customize=False
        )
        zone_stacks_all = controller.get_directed_linked_resources_internal(
            resource_ids, link_type="relation%", run_customize=False
        )

        # index zone stacks
        zone_stacks_all_idx = {}
        for zs in zone_stacks_all.values():
            zone_stacks_all_idx.update({z.oid: z for z in zs})

        # get all the physical stacks related to zone stacks
        if len(list(zone_stacks_all_idx.keys())) > 0:
            physical_stacks = controller.get_directed_linked_resources_internal(
                list(zone_stacks_all_idx.keys()),
                link_type="relation",
                run_customize=True,
                objdef=OpenstackHeatStack.objdef,
            )
        for zone_id, zone_stack in zone_stacks_all_idx.items():
            physical_stack = physical_stacks.get(zone_id, None)
            if physical_stack is not None:
                zone_stack.set_remote_stack(physical_stack[0])

        for e in entities:
            e.zone_stacks = zone_stacks_all.get(e.oid, [])
            e.vpcs = vpcs_all.get(e.oid, [])
            e.sgs = sgs_all.get(e.oid, [])

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        get_resources = self.controller.get_directed_linked_resources_internal

        resource_ids = [self.oid]
        vpcs_all = get_resources(resource_ids, link_type="vpc", run_customize=False)
        sgs_all = get_resources(resource_ids, link_type="security-group", run_customize=False)
        zone_stacks_all = get_resources(resource_ids, link_type="relation%", run_customize=False)

        self.zone_stacks = zone_stacks_all.get(self.oid, [])
        self.vpcs = vpcs_all.get(self.oid, [])
        self.sgs = sgs_all.get(self.oid, [])

        for zone_stack in self.zone_stacks:
            zone_stack.get_remote_stack()

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: id, uuid or name of the site where create sql
        :param kvargs.flavor: id, uuid or name of the flavor
        :param kvargs.image: id, uuid or name of the image
        :param kvargs.vpc: id, uuid or name of the vpc
        :param kvargs.subnet: subnet reference
        :param kvargs.security_group: id, uuid or name of the security group
        :param kvargs.db_name: First app database name
        :param kvargs.db_appuser_name: First app user name
        :param kvargs.db_appuser_password: First app user password
        :param kvargs.db_root_name: The database admin account username
        :param kvargs.db_root_password: The database admin password
        :param kvargs.key_name: public key name
        :param kvargs.version: Database engine version
        :param kvargs.engine: Database engine
        :param kvargs.root_disk_size: root disk size [default=40GB]
        :param kvargs.data_disk_size: data disk size [default=30GB]
        :param kvargs.geo_extension: if True enable geographic extension [default=False]
        :return: dict
        :raise ApiManagerError:
        """
        from beehive_resource.plugins.openstack.entity.ops_subnet import OpenstackSubnet

        # get name
        name = kvargs.get("name")

        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        # get super zone
        compute_zone = controller.get_simple_resource(kvargs.get("parent"))
        compute_zone.set_container(container)

        # check quotas are not exceed
        # new_quotas = {
        #     'database.instances': 1,
        # }
        # compute_zone.check_quotas(new_quotas)

        # get availability_zone
        site = controller.get_resource(kvargs.pop("availability_zone"))
        ip_repository = site.get_attribs().get("repo")
        dns_zone = site.get_dns_zone()

        orchestrator_idx = site.get_orchestrators_by_tag(orchestrator_tag, index_field="type")
        orchestrator = orchestrator_idx.get("openstack", None)
        if orchestrator is None:
            raise ApiManagerError("No valid orchestrator found", code=404)

        filter = {"container_id": site.container.oid, "run_customize": False}

        # get flavor
        flavor = controller.get_resource(kvargs.pop("flavor"), **filter)
        zone_flavor, tot = flavor.get_linked_resources(link_type_filter="relation.%s" % site.oid, run_customize=False)
        ops_flavor, tot = zone_flavor[0].get_linked_resources(link_type="relation", container=orchestrator["id"])
        ops_flavor = ops_flavor[0]

        # get image
        image = controller.get_resource(kvargs.pop("image"), **filter)
        zone_image, tot = image.get_linked_resources(link_type_filter="relation.%s" % site.oid, run_customize=False)
        ops_image = zone_image[0].get_physical_resource_from_container(orchestrator["id"], None)

        # get vpc
        vpc = controller.get_resource(kvargs.pop("vpc"), **filter)
        vpc_nets, tot = vpc.get_linked_resources(link_type_filter="relation.%s" % site.oid, run_customize=False)
        ops_net = vpc_nets[0].get_physical_resource_from_container(orchestrator["id"], None)
        vpc_net = vpc_nets[0]

        # get proxy and zabbix proxy
        configs = vpc_net.get_attribs(key="configs")
        proxy = configs.get("proxy")
        zabbix_proxy = configs.get("zabbix_proxy", "")

        # check subnet
        subnet = kvargs.pop("subnet")
        allocable_subnet = vpc_net.get_allocable_subnet(subnet)

        ops_subnet = controller.get_resource(allocable_subnet.get("openstack_id"), entity_class=OpenstackSubnet)

        # get security_group
        security_group = controller.get_resource(kvargs.pop("security_group"), **filter)
        zone_security_group, tot = security_group.get_linked_resources(
            link_type_filter="relation.%s" % site.oid, run_customize=False
        )
        ops_security_group = zone_security_group[0].get_physical_resource_from_container(orchestrator["id"], None)

        # get key
        key = compute_zone.get_ssh_keys(oid=kvargs.get("key_name"))[0]
        openstack_key_name = key.get("attributes", {}).get("openstack_name", None)
        if openstack_key_name is not None:
            key_name = openstack_key_name
        else:
            raise ApiManagerError("Ssh key is not configured to be used in stack creation")

        admin_user = kvargs.pop("db_root_name", "root")
        admin_pwd = kvargs.pop("db_root_password", "mypass")
        # if admin_pwd is None:
        #     admin_pwd = random_password(length=20, strong=True)

        # engine
        engine = kvargs.pop("engine", "mysql")
        version = kvargs.pop("version", "5.7")

        # disk
        root_disk_size = kvargs.pop("root_disk_size", 40)
        data_disk_size = kvargs.pop("data_disk_size", 30)

        orchestrator_type = None
        template_uri1 = None
        if engine == "mysql":
            template_uri1 = "%s/database/mysql%s-1.yaml" % (
                controller.api_manager.stacks_uri,
                version,
            )
            orchestrator_type = "openstack"
            additional_params = {
                "db_root_name": admin_user,
                "db_appuser_name": "dbtest",
                "db_appuser_password": random_password(strong=True),
            }
        elif engine == "postgresql":
            template_uri1 = "%s/database/postgres%s-1.yaml" % (
                controller.api_manager.stacks_uri,
                version,
            )
            orchestrator_type = "openstack"
            additional_params = {
                "postgresql_version": version,
                "postgis_extension": bool2str(kvargs.pop("geo_extension", False)),
                "db_schema_name": "schematest",
                "db_superuser_name": "dbtest",
                "db_superuser_password": "dbtest",
                "db_appuser_name": "usertest",
                "db_appuser_password": "usertest",
            }
        elif engine == "oracle":
            orchestrator_type = "vsphere"
        else:
            raise ApiManagerError("Engine %s is not supported" % engine)

        template = {
            "availability_zone": site.oid,
            "orchestrator_type": orchestrator_type,
            "template_uri": template_uri1,
            "environment": {},
            "parameters": {
                "name": name,
                "dns_zone": dns_zone,
                "instance_type": ops_flavor.ext_id,
                "volume1_size": root_disk_size,
                "volumedata_size": data_disk_size,
                "server_network": ops_net.ext_id,
                "server_network_subnet": ops_subnet.ext_id,
                "proxy_server": proxy,
                # 'zabbix_proxy': zabbix_proxy,
                "security_groups": ops_security_group.ext_id,
                "image_id": ops_image.ext_id,
                "db_name": kvargs.pop("db_name"),
                "db_root_password": admin_pwd,
                "key_name": key_name,
                "ip_repository": ip_repository,
            },
            "owner": "admin",
            "files": None,
        }
        kvargs["templates"] = [template]
        kvargs["parameters"] = {}
        kvargs["attribute"] = {
            "stack_type": "sql_stack",
            "engine": engine,
            "version": version,
            "admin_user": {
                "name": admin_user,
                "pwd": controller.encrypt_data(admin_pwd),
            },
        }
        # extend parameters with engine specific parameters
        template["parameters"].update(additional_params)

        # setup link params
        link_params = [
            ("security-group", security_group.oid),
            ("vpc", vpc.oid),
            ("image", image.oid),
            ("flavor", flavor.oid),
        ]
        kvargs["link_params"] = link_params

        return ComputeStack.pre_create(controller, container, *args, **kvargs)

    # @staticmethod
    # def post_create(controller, *args, **kvargs):
    #     """Post create function. This function is used in object_factory method. Used only for synchronous creation.
    #     Extend this function to execute some operation after entity was created.
    #
    #     :param list args: custom params
    #     :param dict kvargs: custom params
    #     :return: kvargs
    #     :raise ApiManagerError:
    #     """
    #     # create some links
    #     resource = controller.get_resource(kvargs['uuid'])
    #     link_params = kvargs['link_params']
    #     for item in link_params:
    #         resource.add_link(name='%s-%s-%s-%s-link' % (resource.oid, item[1], item[0], id_gen()), type=item[0],
    #                           end_resource=item[1], attributes={})
    #
    #     return None
