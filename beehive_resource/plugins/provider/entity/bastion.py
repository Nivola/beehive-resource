# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from base64 import b64decode
from datetime import datetime

from six import ensure_text

from beecell.simple import format_date, dict_get, random_password
from beehive.common.apimanager import ApiManagerError
from beehive.common.client.apiclient import BeehiveApiClientError
from beehive.common.data import trace
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.gateway import ComputeGateway
from beehive_resource.plugins.provider.entity.image import ComputeImage
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc


class ComputeBastion(ComputeInstance):
    """Compute bastion instance"""

    objdef = "Provider.ComputeZone.ComputeBastion"
    objuri = "%s/bastions/%s"
    objname = "bastion"
    objdesc = "Provider ComputeBastion"
    task_path = "beehive_resource.plugins.provider.task_v2.bastion.ComputeBastionTask."

    def __init__(self, *args, **kvargs):
        ComputeInstance.__init__(self, *args, **kvargs)

        self.actions = [
            "start",
            "stop",
            "reboot",
            "install_zabbix_proxy",
            "register_zabbix_proxy",
            "enable_monitoring",
            "enable_logging",
            # 'pause',
            # 'unpause',
            # 'migrate',
            # # 'setup_network': self.setup_network,
            # # 'reset_state': self.reset_state,
            # 'add_volume',
            # 'del_volume',
            "set_flavor",
            "add_security_group",
            "del_security_group",
            # 'add_snapshot',
            # 'del_snapshot',
            # 'revert_snapshot',
            # 'add_user',
            # 'del_user',
            # 'set_user_pwd',
            # 'set_ssh_key',
            # 'unset_ssh_key',
        ]

    def get_nat_ip_address(self):
        nat_ip_address = self.get_attribs(key="nat")
        res = "%s:%s" % (nat_ip_address.get("ip_address"), nat_ip_address.get("port"))
        return res

    # def get_real_ip_address(self):
    #     """return ip address used for remote connection"""
    #     nat_ip_address = self.get_attribs(key='nat')
    #     ip_address = nat_ip_address.get('ip_address')
    #     self.logger.info('+++++ ComputeBastion - get_real_ip_address - ip_address: %s' % ip_address)
    #     return ip_address

    # def get_real_ssh_port(self):
    #     """return ssh port used for remote connection"""
    #     nat_ip_address = self.get_attribs(key='nat')
    #     port = nat_ip_address.get('port')
    #     self.logger.info('+++++ ComputeBastion - get_real_ssh_port - port: %s' % port)
    #     return port

    # def get_real_ssh_user(self):
    #     """return ssh port used for remote connection"""
    #     self.logger.info('+++++ ComputeBastion - get_real_ssh_user - user: root')
    #     return 'root'

    def info(self):
        """Get infos.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeInstance.info(self)

        return info

    def detail(self):
        """Get details.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = self.info()
        return info

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "compute.bastions": 1,
        }
        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: site id or uuid
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.flavor: server flavor
        :param kvargs.volume_flavor: server volume flavor
        :param kvargs.image: server image
        :param kvargs.admin_pass: admin password
        :param kvargs.key_name: ssh key name or uuid
        :param kvargs.acl: network acl to apply
        :return: dict
        :raise ApiManagerError:
        """
        orchestrator_type = "vsphere"
        hostname = kvargs.get("name")
        compute_zone_id = kvargs.get("parent")
        site_id = kvargs.get("availability_zone")
        multi_avz = True
        flavor_id = kvargs.get("flavor")
        volume_flavor_id = kvargs.get("volume_flavor")
        image_id = kvargs.get("image")
        key_name = kvargs.get("key_name", None)
        admin_pass = kvargs.get("admin_pass", None)
        host_group = kvargs.get("host_group", "default")
        acl = kvargs.get("acl", [])

        # get compute zone
        from beehive_resource.plugins.provider.entity.zone import ComputeZone

        compute_zone: ComputeZone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        site = container.get_resource(site_id)

        # check bastion does not already exist
        if compute_zone.get_bastion_host() is not None:
            raise ApiManagerError("compute zone %s has already an active bastion host" % compute_zone.oid)

        # check host group
        host_group_config = {}
        if orchestrator_type == "vsphere":
            orchestrators = site.get_orchestrators_by_tag("default", index_field="type")
            orchestrator = orchestrators.get("vsphere")
            clusters = dict_get(orchestrator, "config.clusters")
            host_group_config = clusters.get(host_group, None)
            if host_group_config is None:
                raise ApiManagerError("Host group %s does not exist" % host_group)

        # get main availability zone
        main_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        # get availability zones ACTIVE
        availability_zones = []
        if multi_avz is True:
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
            availability_zones.remove(main_availability_zone)

        # get flavors
        flavor = container.get_simple_resource(flavor_id, entity_class=ComputeFlavor)
        flavor.check_active()

        volume_flavor = container.get_simple_resource(volume_flavor_id, entity_class=ComputeVolumeFlavor)
        volume_flavor.check_active()

        # get image
        image = container.get_simple_resource(image_id, entity_class=ComputeImage)
        image.check_active()

        # get volumes
        block_devices = [
            {
                "boot_index": 0,
                "source_type": "image",
                "volume_size": 50,
                "flavor": volume_flavor.uuid,
                "uuid": image.uuid,
            }
        ]

        # get networks
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

        vpc: Vpc = compute_zone.get_default_vpc()
        vpc_net = vpc.get_network_by_site(site.oid)
        dns_search = vpc_net.get_attribs(key="configs.dns_search", default="nivolalocal")

        # - check subnet
        cidr = vpc.get_cidr()
        allocable_subnet = vpc_net.get_allocable_subnet(cidr, orchestrator_type=orchestrator_type)

        networks = [
            {
                "vpc": vpc.oid,
                "subnet": allocable_subnet,
                "fixed_ip": {"hostname": hostname, "dns_search": dns_search},
            }
        ]

        # get security groups
        security_groups = [sg.uuid for sg in compute_zone.get_default_security_groups(str(vpc.oid))]

        # fqdn
        fqdn = "%s.%s" % (hostname, dns_search)

        # set key_name in metadata
        metadata = {}
        if key_name is not None:
            # read key value
            keys = compute_zone.get_ssh_keys(oid=key_name)
            metadata["pubkey"] = ensure_text(b64decode(keys[0]["pub_key"]))

        # get admin pass
        if admin_pass is None:
            admin_pass = random_password(length=20)

        # get orchestrator tag
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        # orchestrator_select_types = kvargs.get("orchestrator_select_types", None)

        # get nat ipaddress and port
        gw = compute_zone.get_default_gateway()
        nat_ip_address = gw.get_external_ip_address().get("primary")
        nat_port = 11100

        # set params
        params = {
            "hostname": hostname,
            "dns_search": dns_search,
            "orchestrator_tag": orchestrator_tag,
            # "orchestrator_select_types": orchestrator_select_types,
            "compute_zone": compute_zone.oid,
            "flavor": flavor.oid,
            "networks": networks,
            "security_groups": security_groups,
            "block_device_mapping": block_devices,
            "main_availability_zone": main_availability_zone,
            "host_group": host_group_config,
            "metadata": metadata,
            "type": orchestrator_type,
            "admin_pass": admin_pass,
            "resolve": True,
            "manage": True,
            "multi_avz": True,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                # "orchestrator_select_types": orchestrator_select_types,
                "availability_zone": site.oid,
                "host_group": host_group,
                "fqdn": fqdn,
                "key_name": key_name,
                "has_quotas": False,
                "bastion": True,
                "nat": {"ip_address": nat_ip_address, "port": nat_port},
                "configs": {},
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeInstance.task_path + "create_resource_pre_step",
            ComputeBastion.task_path + "create_bastion_security_group_step",
            ComputeInstance.task_path + "link_compute_instance_step",
            ComputeBastion.task_path + "link_compute_bastion_step",
            # ComputeBastion.task_path + 'create_bastion_security_group_step',
        ]
        # create block devices
        for block_device in block_devices:
            steps.append(
                {
                    "step": ComputeInstance.task_path + "create_compute_volume_step",
                    "args": [block_device],
                }
            )
        # create main zone instance
        steps.append(
            {
                "step": ComputeInstance.task_path + "create_zone_instance_step",
                "args": [main_availability_zone],
            }
        )
        # create secondary instance
        for availability_zone in availability_zones:
            steps.append(
                {
                    "step": ComputeInstance.task_path + "create_zone_instance_step",
                    "args": [availability_zone],
                }
            )
        # manage instance
        steps.append(ComputeInstance.task_path + "manage_compute_instance_step")
        # register to dns
        steps.append(ComputeInstance.task_path + "register_dns_compute_instance_step")
        # create nat rule and firewall rule on gateway
        steps.append(ComputeBastion.task_path + "create_gateway_nat_step")

        # post create
        steps.append(ComputeInstance.task_path + "create_resource_post_step")

        # wait till bastion is reachable
        steps.append(ComputeInstance.task_path + "wait_ssh_up_step")

        # create user gateway
        steps.append(ComputeBastion.task_path + "create_user_gateway_step")

        # install zabbix proxy
        steps.append(ComputeBastion.task_path + "install_zabbix_proxy_step")

        # enable monitoring
        steps.append(ComputeBastion.task_path + "enable_monitoring_step")

        # enable logging
        # steps.append(ComputeBastion.task_path + 'enable_logging_step')

        kvargs["steps"] = steps
        return kvargs

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in update method. Extend this function to manipulate and
        validate patch input params.

        :param list args: positional args
        :param dict kvargs: key value args
        :return: kvargs
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # get instances
        instances, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [p.oid for p in instances]

        volumes, total = self.get_linked_resources(link_type_filter="volume%")
        child_volumes = [p.oid for p in volumes]

        # create task workflow
        steps = [
            ComputeInstance.task_path + "expunge_resource_pre_step",
            ComputeInstance.task_path + "unmanage_compute_instance_step",
            ComputeInstance.task_path + "deregister_dns_compute_instance_step",
        ]
        # remove childs
        for child in childs:
            steps.append(
                {
                    "step": ComputeInstance.task_path + "remove_child_step",
                    "args": [child],
                }
            )
        # remove child volumes
        for child in child_volumes:
            steps.append(
                {
                    "step": ComputeInstance.task_path + "remove_compute_volume_step",
                    "args": [child],
                }
            )
            steps.append(
                {
                    "step": ComputeInstance.task_path + "remove_child_step",
                    "args": [child],
                }
            )
        # remove security group and rules
        steps.append(ComputeBastion.task_path + "delete_bastion_security_group_step")
        steps.append(ComputeBastion.task_path + "delete_gateway_nat_step")
        # post expunge
        steps.append(ComputeInstance.task_path + "expunge_resource_post_step")

        kvargs["steps"] = steps
        return kvargs

    def get_bastion_security_group(self):
        """Get bastion security group"""
        sg = None
        sg_name = "SG-%s" % self.name
        # parent=self.vpcs[0].oid,
        sgs, tot = self.container.get_resources(
            name=sg_name,
            authorize=False,
            run_customize=False,
            type=SecurityGroup.objdef,
        )
        if tot == 0:
            # raise ApiManagerError("no bastion security group found in compute zone %s" % self.parent_id)
            self.logger.warning("no bastion security group found %s in compute zone %s" % (sg_name, self.parent_id))
        else:
            sg = sgs[0]
            self.logger.debug("get bastion compute zone %s security group: %s" % (self.parent_id, sg.oid))

        return sg

    #
    # manage through ssh module
    #
    def get_credential(self, username="root"):
        """Get instance credential from ssh module

        :param username: username [default=root]
        """
        # check authorization
        self.verify_permisssions("update")

        try:
            # get node
            res = self.api_client.get_ssh_node(self.fqdn)
            uuid = res.get("id")

            user = self.api_client.get_ssh_user(node_id=uuid, username=username)
            return user
        except BeehiveApiClientError as ex:
            raise ApiManagerError(ex.value)

    @trace(op="update")
    def manage(self, user=None, key=None, password="", *args, **kvargs):
        """Manage compute instance with ssh module. Create group in ssh module where register server.

        :param kvargs.user: ssh node user
        :param kvargs.key: ssh key uuid or name
        :param kvargs.password: user password [default='']
        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        try:
            res = self.api_client.get_ssh_node(self.fqdn)
            uuid = res.get("uuid")
            self.logger.warning(
                "Compute instance %s is already managed by ssh module" % self.uuid,
                exc_info=1,
            )
            return uuid
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                pass
            else:
                raise

        # check compute zone is managed by ssh module
        compute_zone = self.get_parent()
        group = compute_zone.get_ssh_group()

        compute_zone.get_ssh_keys(oid=key)

        ip_address = self.get_nat_ip_address()

        # create ssh node
        uuid = self.api_client.add_ssh_node(
            self.fqdn,
            self.desc,
            ip_address,
            group,
            user,
            key=key,
            attribute="",
            password=password,
        )

        self.logger.debug("Compute instance %s is now managed by ssh group %s" % (self.uuid, uuid))
        return uuid

    @trace(op="update")
    def unmanage(self):
        """Unmanage compute instance with ssh module. Remove group in ssh module where register server.

        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        try:
            res = self.api_client.get_ssh_node(self.fqdn)
            uuid = res.get("uuid")
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                self.logger.warning(
                    "Compute instance %s is not managed by ssh module" % self.uuid,
                    exc_info=1,
                )
            else:
                raise

        uuid = self.api_client.delete_ssh_node(self.fqdn)

        self.logger.debug("Compute instance %s is now unmanaged by ssh module" % (self.uuid))
        return True

    #
    # actions
    #
    def get_zabbix_proxy_name(self):
        return self.fqdn

    def install_zabbix_proxy(self, *args, **kvargs):
        """install zabbix proxy

        :return: kvargs
        """
        site_id = self.get_attribs().get("availability_zone", None)
        site = self.container.get_simple_resource(site_id)

        # select zabbix orchestrator
        orchestrator_tag = "tenant"
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=["zabbix"])
        orchestrator = next(iter(orchestrators.keys()))

        from beehive_resource.plugins.zabbix.controller import ZabbixContainer

        zabbix_container: ZabbixContainer = self.controller.get_container(orchestrator, connect=False)
        # zabbix_server = zabbix_container.get_ip_address()
        conn_params = zabbix_container.conn_params["api"]
        zbx_srv_uri = conn_params.get("uri")
        zbx_srv_usr = conn_params.get("user")
        pwd = conn_params.get("pwd")
        zbx_srv_pwd = zabbix_container.decrypt_data(pwd).decode("utf-8")
        zbx_srv_ip = zabbix_container.get_ip_address(zbx_srv_uri)

        zabbix_pwd = random_password(length=20)
        self.set_configs(key="zabbix_proxy", value={"user": "zabbix", "pwd": zabbix_pwd})

        internal_steps = [
            {
                "step": ComputeInstance.task_path + "apply_customization_action_step",
                "args": [],
            },
        ]
        res = {
            "internal_steps": internal_steps,
            "customization": "zabbix-proxy",
            "playbook": "install.yml",
            "extra_vars": {
                "p_proxy_server": "",
                "p_ip_repository": "",
                "p_no_proxy": "localhost,10.0.0.0/8",
                "p_zabbix_db_user_name": "zabbix",
                "p_zabbix_db_user_pwd": zabbix_pwd,
                # "p_zabbix_server_ip": zbx_srv_ip,
                "p_zabbix_server": zbx_srv_ip,
                "p_zabbix_server_uri": zbx_srv_uri,
                "p_zabbix_server_username": zbx_srv_usr,
                "p_zabbix_server_password": zbx_srv_pwd,
                "p_zabbix_proxy_name": self.fqdn,
            },
        }
        return res

    def register_zabbix_proxy(self, *args, **kvargs):
        """register zabbix proxy

        :return: kvargs
        """
        site_id = self.get_attribs().get("availability_zone", None)
        site = self.container.get_simple_resource(site_id)

        # select zabbix orchestrator
        orchestrator_tag = "tenant"
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=["zabbix"])
        orchestrator = next(iter(orchestrators.keys()))
        zabbix_container = self.controller.get_container(orchestrator, connect=False)
        conn_params = zabbix_container.conn_params["api"]
        zbx_srv_uri = conn_params.get("uri")
        zbx_srv_usr = conn_params.get("user")
        pwd = conn_params.get("pwd")
        zbx_srv_pwd = zabbix_container.decrypt_data(pwd).decode("utf-8")

        zabbix_pwd = random_password(length=20)
        self.set_configs(key="zabbix_proxy", value={"user": "zabbix", "pwd": zabbix_pwd})

        internal_steps = [
            {
                "step": ComputeInstance.task_path + "apply_customization_action_step",
                "args": [],
            },
        ]
        res = {
            "internal_steps": internal_steps,
            "customization": "zabbix-proxy",
            "playbook": "register.yml",
            "extra_vars": {
                "p_proxy_server": "",
                "p_ip_repository": "",
                "p_no_proxy": "localhost,10.0.0.0/8",
                "p_zabbix_server_uri": zbx_srv_uri,
                "p_zabbix_server_username": zbx_srv_usr,
                "p_zabbix_server_password": zbx_srv_pwd,
                "p_zabbix_proxy_name": self.fqdn,
            },
        }
        return res

    def enable_monitoring(self, *args, **kvargs):
        """Enable resources monitoring over compute instance

        :param args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        """
        kvargs["host_groups"] = ["PrivateBastionHost"]
        res = super().enable_monitoring(*args, **kvargs)
        return res

    def disable_monitoring(self, *args, **kvargs):
        """Disable resources monitoring over compute instance

        :param args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        """
        res = super().disable_monitoring(*args, **kvargs)
        return res

    # #
    # # metrics
    # #
    # def get_metrics(self):
    #     """Get resource metrics
    #
    #     :return: a dict like this
    #
    #         {
    #             "id": "1",
    #             "uuid": "vm1",
    #             "metrics": [
    #                 {
    #                     "key": "ram",
    #                     "value: 10,
    #                     "type": 1,
    #                     "unit": "GB"
    #                 }],
    #             "extraction_date": "2018-03-04 12:00:34 200",
    #             "resource_uuid": "12u956-2425234-23654573467-567876"
    #         }
    #     """
    #     metrics = []
    #     res = {
    #         'id': self.oid,
    #         'uuid': self.uuid,
    #         'resource_uuid': self.uuid,
    #         'type': self.objdef,
    #         'metrics': metrics,
    #         'extraction_date': format_date(datetime.today())
    #     }
    #
    #     self.logger.debug('Get compute instance %s metrics: %s' % (self.uuid, res))
    #     return res
