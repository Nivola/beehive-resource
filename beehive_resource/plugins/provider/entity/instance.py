# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte
from ipaddress import IPv4Network
from urllib.parse import urlparse

import ujson as json
from base64 import b64decode
from datetime import datetime
from random import randint
from passlib.handlers.sha2_crypt import sha512_crypt
from beecell.simple import format_date, truncate, dict_get, id_gen, dict_set
from beecell.types.type_string import str2bool
from beehive.common.apiclient import BeehiveApiClientError
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace, operation
from beehive.common.task_v2 import prepare_or_run_task, run_async
from beehive_resource.container import Resource
from beehive_resource.model import ResourceState
from beehive_resource.plugins.dns.controller import DnsRecordCname, DnsZone, DnsRecordA
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.image import ComputeImage, Image
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.volume import ComputeVolume, Volume
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc, SiteNetwork
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from six import ensure_text
from logging import getLogger
from beecell.simple import jsonDumps

logger = getLogger(__name__)


class ComputeInstance(ComputeProviderResource):
    """Compute instance"""

    objdef = "Provider.ComputeZone.ComputeInstance"
    objuri = "%s/instances/%s"
    objname = "instance"
    objdesc = "Provider ComputeInstance"
    task_path = "beehive_resource.plugins.provider.task_v2.instance.ComputeInstanceTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.fqdn = self.get_attribs().get("fqdn", "")
        self.main_zone_instance = None
        self.availability_zone = None
        self.image = None
        self.flavor = None
        self.sgs = []
        self.vpcs = []
        self.volumes = []
        self.physical_server = None
        self.physical_server_status = "unknown"
        self.runstate_cache_key = "ComputeInstance.runstate.%s" % self.oid
        self.backup_cache_key = "ComputeInstance.backup.%s" % self.oid
        self.monitor_cache_key = "ComputeInstance.monitor.%s" % self.oid

        try:
            self.availability_zone_id = self.get_attribs().get("availability_zone", None)
        except:
            self.availability_zone_id = None

        self.actions = [
            "start",
            "stop",
            "reboot",
            "pause",
            "unpause",
            "migrate",
            # 'setup_network': self.setup_network,
            # 'reset_state': self.reset_state,
            "add_volume",
            "del_volume",
            "extend_volume",
            "set_flavor",
            "add_security_group",
            "del_security_group",
            "add_snapshot",
            "del_snapshot",
            "revert_snapshot",
            "add_user",
            "del_user",
            "set_user_pwd",
            "set_ssh_key",
            "unset_ssh_key",
            "enable_monitoring",
            "disable_monitoring",
            "enable_logging",
            "disable_logging",
            # 'add_backup_restore_point',
            # 'del_backup_restore_point',
            "enable_log_module",
            "disable_log_module",
            "restore_from_backup",
        ]

    def is_windows(self):
        if self.image is not None:
            # self.logger.debug('+++++ is_windows - self.image.get_configs(): %s' % self.image.get_configs())
            image_name = self.image.get_configs().get("os")
        else:
            # self.logger.debug('+++++ is_windows - self.attribs(): %s' % self.attribs)
            image_name = self.get_attribs(key="os.name")

        # NOTA: se image_name is None non caricare la risorsa con get_simple_resource
        # self.logger.debug('+++++ is_windows - image_name: %s' % image_name)
        if image_name == "Windows":
            return True
        return False

    def get_normalized_os(self) -> str:
        """get normalized name for os

        Returns:
            str: [description]
        """
        os = "unknown"
        if self.image is not None:
            config = self.image.get_configs()
            os = config.get("os")
        else:
            os = self.get_attribs(key="os.name", default="")
        os = os.lower().strip(" -_.0123456789")

        if os.find("windows") >= 0:
            return "windows"
        elif os.find("redhat") >= 0:
            return "redhat"
        elif os.find("centos") >= 0:
            return "centos"
        elif os.find("ubuntu") >= 0:
            return "ubuntu"
        elif os.find("oraclelinux") >= 0:
            return "oraclelinux"
        else:
            return os

    def is_image_py3(self):
        """check if image is python 3 compliant"""
        images, total = self.get_linked_resources(link_type="image", with_perm_tag=False, run_customize=False)
        if total > 0:
            image = images[0]
            name = image.get_attribs(key="configs.os")
            version = str(image.get_attribs(key="configs.os_ver"))
            if (version == "8" and name in ["OracleLinux", "RedhatLinux", "centos"]) or (
                version == "18" and name in ["ubuntu"]
            ):
                return True
        return False

    def get_hypervisor(self):
        hypervisor = self.get_attribs().get("type")
        return hypervisor

    def get_hypervisor_tag(self):
        hypervisor = self.get_attribs().get("orchestrator_tag", "default")
        return hypervisor

    def get_key_name(self):
        key_name = self.get_attribs(key="key_name", default=None)
        return key_name

    def get_main_zone_instance(self):
        site = self.get_attribs().get("availability_zone", None)
        if site is None:
            return None
        instances, total = self.get_linked_resources(link_type_filter="relation.%s" % site, with_perm_tag=False)
        res = None
        if total == 1:
            res = instances[0]
        return res

    def get_main_availability_zone(self):
        site = self.get_attribs().get("availability_zone", None)
        if site is None:
            return None
        return self.controller.get_simple_resource(site)

    def __get_image_info(self, info):
        if self.image is not None:
            info["image"] = self.image.get_configs()
            info["image"]["name"] = self.image.name
            info["image"]["uuid"] = self.image.uuid
        else:
            info["image"] = {
                "os": self.get_attribs(key="os.name"),
                "os_ver": self.get_attribs(key="os.version"),
            }
        return info

    def __get_flavor_info(self, info):
        self.flavor = self.get_flavor()
        if self.flavor is not None:
            info["flavor"] = self.flavor.get_configs()
            info["flavor"]["name"] = self.flavor.name
            info["flavor"]["uuid"] = self.flavor.uuid
        else:
            info["flavor"] = {}
        return info

    def __get_security_groups_info(self, info):
        info["security_groups"] = []
        for sg in self.sgs:
            info["security_groups"].append({"uuid": sg.uuid, "name": sg.name})

        return info

    def __get_availability_zone_info(self, info):
        if self.availability_zone is not None:
            info["availability_zone"] = self.availability_zone.small_info()
        else:
            info["availability_zone"] = {}
        return info

    def __get_network_info(self, info):
        for vpc in self.vpcs:
            attrib = json.loads(vpc.link_attr)
            info["vpcs"].append(
                {
                    "uuid": vpc.uuid,
                    "name": vpc.name,
                    # 'gateway': attrib.get('gateway', None),
                    # 'subnet': attrib.get('subnet', {}).get('cidr', None),
                    "fixed_ip": attrib.get("fixed_ip", {}),
                }
            )
            info["vpcs"][0]["fixed_ip"]["hostname"] = self.fqdn
        return info

    def __get_volume_info(self, info):
        info["block_device_mapping"] = []
        for volume in self.volumes:
            attachment = volume.link_creation
            if type(attachment) != str:
                attachment = format_date(attachment)
            data = {
                "name": volume.name,
                "id": volume.uuid,
                "boot_index": volume.link_type.replace("volume.", ""),
                "volume_size": volume.get_attribs("configs.size"),
                "bootable": volume.get_attribs("configs.bootable"),
                "encrypted": volume.get_attribs("configs.encrypted"),
                "attachment": attachment,
            }
            info["block_device_mapping"].append(data)
        return info

    def __get_services(self, info):
        dict_set(info, "attributes.backup_enabled", self.has_backup())
        dict_set(
            info,
            "attributes.monitoring_enabled",
            str2bool(self.is_monitoring_enabled()),
        )
        dict_set(info, "attributes.logging_enabled", str2bool(self.is_logging_enabled()))
        return info

    def __get_host(self, info):
        dict_set(info, "attributes.host", self.get_host())
        dict_set(info, "attributes.host_group", self.get_host_group())
        return info

    def get_ip_address(self):
        vpc_links, total = self.get_links(type="vpc")
        ip_address = vpc_links[0].attribs.get("fixed_ip", {}).get("ip", "")
        return ip_address

    def get_fqdn(self):
        return self.get_attribs("fqdn")

    def get_flavor(self):
        """get instance flavor"""
        if self.flavor is not None:
            return self.flavor
        links, tot = self.get_out_links(type="flavor")
        if tot > 0:
            flavor = links[0].get_end_resource()
            self.logger.debug2("Get compute instance flavor: %s" % flavor)
            return flavor
        return None

    def get_real_ip_address(self):
        """return ip address used for remote connection"""
        return self.get_ip_address()

    def get_real_ssh_port(self):
        """return ssh port used for remote connection"""
        return 22

    def get_real_admin_user(self):
        """return admin user used for remote connection"""
        username = "root"
        if self.is_windows() is True:
            username = "Administrator"
        return username

    def get_real_admin_credential(self):
        """return admin credential used for remote connection"""
        credential = self.get_credential()
        res = {
            "username": self.get_real_admin_user(),
            "password": credential.get("password", None),
        }

        if not self.is_windows():
            res.update({"ssh_key_data": credential.get("ssh_key_data", None)})

        return res

    def get_runstate(self, cache=True, ttl=1800):
        """Get resource running state if exist.

        :param cache: if True get data from cache
        :param ttl: cache time to live [default=1800]
        :return: None if runstate does not exist
        """

        def func():
            ret = self.get_physical_server_param("get_status")
            if ret is None:
                ret = None
            return ret

        if self.state not in [2, 4]:
            res = func()
        else:
            res = self.cache_data(self.runstate_cache_key, func, cache, ttl)
        return res

    def get_runstate_DEPRECATED(self):
        """Get resource running state if exixst.

        DEPRECATED

        :return: None if runstate does not exist
        """
        return self.physical_server_status

    def get_cache(self):
        """Get cache items"""
        res = ComputeProviderResource.get_cache(self)
        ps = self.get_physical_server()
        if ps is not None:
            res.extend(ps.get_cache())
        return res

    def clean_cache(self):
        """Clean cache"""
        # logger.debug("+++++ clean_cache - ComputeInstance")
        ComputeProviderResource.clean_cache(self)
        ps = self.get_physical_server()
        if ps is not None:
            ps.clean_cache()

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            info = self.get_cached("info")
            if info is None:
                info = Resource.info(self)
                info["hypervisor"] = self.get_hypervisor()
                info["vpcs"] = []
                info = self.__get_image_info(info)
                info = self.__get_flavor_info(info)
                info = self.__get_availability_zone_info(info)
                info = self.__get_network_info(info)
                info = self.__get_volume_info(info)
                info = self.__get_security_groups_info(info)
                info = self.__get_services(info)
                info = self.__get_host(info)
                self.set_cache("info", info)
        except:
            self.logger.warn("", exc_info=True)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            info = self.get_cached("detail")
            if info is None:
                info = Resource.detail(self)

                info["hypervisor"] = self.get_hypervisor()
                info["vpcs"] = []

                info = self.__get_image_info(info)
                info = self.__get_flavor_info(info)
                info = self.__get_availability_zone_info(info)
                info = self.__get_network_info(info)
                info = self.__get_volume_info(info)
                info = self.__get_security_groups_info(info)
                info = self.__get_services(info)
                info = self.__get_host(info)
                self.set_cache("detail", info)
        except:
            self.logger.warn("", exc_info=True)
        return info

    def __check_or_update_sg(self, update=False):
        # get sites
        availability_zones, tot = self.get_parent().get_linked_resources(
            link_type_filter="relation%", with_perm_tag=False, run_customize=False
        )
        sites = [a.get_parent() for a in availability_zones]

        # get sgs
        sgs, tot = self.get_linked_resources(link_type="security-group", with_perm_tag=False, run_customize=False)

        mappings = {
            "Openstack.Domain.Project.Network.Port": "Openstack.Domain.Project.SecurityGroup",
            "Openstack.Domain.Project.Server": "Openstack.Domain.Project.SecurityGroup",
            "Vsphere.Nsx.IpSet": "Vsphere.Nsx.NsxSecurityGroup",
            "Vsphere.DataCenter.Folder.Server": "Vsphere.Nsx.NsxSecurityGroup",
        }
        res = {}
        check = True
        for site in sites:
            res[site.name] = {}
            zone_instance, tot = self.get_linked_resources(
                link_type_filter="relation.%s" % site.oid,
                with_perm_tag=False,
                run_customize=False,
            )
            if len(zone_instance) > 0:
                items, tot = zone_instance[0].get_linked_resources(
                    link_type_filter="relation",
                    with_perm_tag=False,
                    run_customize=False,
                )
                for item in items:
                    self.logger.warn("%s[%s]" % (item.objdef, item.ext_id))

                    for sg in sgs:
                        zone_sg, tot = sg.get_linked_resources(
                            link_type_filter="relation.%s" % site.oid,
                            with_perm_tag=False,
                            run_customize=False,
                        )
                        sg_type = mappings.get(item.objdef)
                        run_customize = False
                        if sg_type == "Vsphere.Nsx.NsxSecurityGroup":
                            run_customize = False
                        sgitems, tot = zone_sg[0].get_linked_resources(
                            link_type_filter="relation",
                            with_perm_tag=False,
                            run_customize=run_customize,
                            type=sg_type,
                        )
                        for sgitem in sgitems:
                            if sg_type == "Vsphere.Nsx.NsxSecurityGroup":
                                sgitem.set_container(self.controller.get_container(sgitem.container_id))
                                sgitem.post_get()
                            is_member = sgitem.is_member(item)
                            res[site.name][sg_type] = {
                                "sg_ext_id": sgitem.ext_id,
                                "ext_id": item.ext_id,
                                "is_member": is_member,
                            }
                            check = check and is_member
                            if is_member is False and update is True:
                                # add item to sg
                                sgitem.container.conn.network.nsx.sg.add_member(sgitem.ext_id, item.ext_id)
                                pass
        return check, res

    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        operation.cache = False

        # set container
        self.set_container(self.controller.get_container(self.container_id))

        #### use to recover error in security group ####
        check, msg = self.__check_or_update_sg()
        #### use to recover error in security group ####

        try:
            physical_server = self.get_physical_server()
        except ApiManagerError as ex:
            physical_server = None
            check = False
            msg = ex.value

        if physical_server is None:
            check = False
            msg = "physical server does not exist"
        else:
            flavor = self.get_flavor().name
            remote_flavor = self.physical_server.get_flavor_resource().name

            # check flavor
            if flavor != remote_flavor:
                check = False
                msg = "instance flavor %s does not match with remote server flavor %s" % (flavor, remote_flavor)
            # get physical server volumes
            elif len(self.get_volumes()) != len(physical_server.get_volumes()):
                check = False
                msg = "volumes number does not match with remote server"
            else:
                check = True
                msg = None
                pcheck = physical_server.check().get("check")
                if pcheck is False:
                    check = False
                    msg = "no remote server found"
        res = {"check": check, "msg": msg}
        self.logger.debug2("Check resource %s: %s" % (self.uuid, res))
        return res

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "compute.instances": 1,
            "compute.cores": 0,
            "compute.ram": 0,
            "compute.blocks": 0,
            "compute.volumes": 0,
        }

        cores = self.get_attribs("quotas.compute.cores")
        ram = self.get_attribs("quotas.compute.ram")
        # cores = self.get_attribs().get('cores')
        # ram = self.get_attribs().get('ram')
        self.logger.debug("Get resource - cores: %s - ram: %s" % (cores, ram))

        if cores is None or ram is None:
            if self.flavor is None:
                # self.logger.debug('Get resource %s - get flavor' % (self.uuid))
                self.flavor = self.get_flavor()

            self.logger.debug(
                "Get resource %s - is_running: %s - flavor: %s" % (self.uuid, self.is_running(), self.flavor)
            )

            if self.is_running() is True and self.flavor is not None:
                if self.has_quotas() is False:
                    self.logger.debug("Get resource %s - has_quotas False" % (self.uuid))
                else:
                    flavor = self.flavor.get_configs()
                    quotas["compute.cores"] = flavor.get("vcpus", 0)
                    quotas["compute.ram"] = flavor.get("memory", 0)

                    self.set_configs("quotas.compute.cores", quotas["compute.cores"])
                    self.set_configs("quotas.compute.ram", quotas["compute.ram"])

        else:
            quotas["compute.cores"] = cores
            quotas["compute.ram"] = ram

        # confronto con logica di get_metrics
        # physical_server = self.get_physical_server()
        # cpu = 0
        # if physical_server is not None:
        #     data = physical_server.info().get('details')
        #     if data.get('state') == 'poweredOn':
        #         cpu = data.get('cpu')
        # if cpu != quotas['compute.cores']:
        #     self.logger.debug('+++++ Get resource %s - different cpu: %s - compute.cores: %s' % (self.uuid, cpu, quotas['compute.cores']))

        self.logger.debug("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    def disable_quotas(self):
        """Disable resource quotas discover

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = super().disable_quotas()

        for volume in self.get_volumes():
            volume.disable_quotas()
        return res

    def is_running(self):
        """True if server is running"""
        # status = self.physical_server_status
        status = self.get_runstate()
        if status is not None and status == "poweredOn":
            return True
        else:
            return False

    def get_physical_server(self):
        """Get physical server"""
        if self.physical_server is None:
            if self.main_zone_instance is None:
                # get main zone instance
                res = self.controller.get_directed_linked_resources_internal(
                    resources=[self.oid],
                    link_type="relation%",
                )
                for _, zone_instances in res.items():
                    for zone_instance in zone_instances:
                        if zone_instance is not None and zone_instance.get_attribs().get("main", False):
                            self.main_zone_instance = zone_instance
                            break

            if self.main_zone_instance is not None:
                self.physical_server = self.main_zone_instance.get_physical_server()

        self.logger.debug("Get compute instance %s physical server: %s" % (self.uuid, self.physical_server))
        return self.physical_server

    def get_physical_server_param(self, method, *args, **kwargs):
        """Get physical server param from some internal class method

        :param method: physical server internal method to execute
        :param args: custom internal method positional args
        :param kwargs: custom internal method key value args
        :return: method response
        """
        ret = None

        # get get_physical_server
        ps = self.get_physical_server()
        if ps is not None:
            func = getattr(ps, method)
            ret = func(*args, **kwargs)

        return ret

    def get_host(self):
        return self.get_physical_server_param("get_host")

    def get_host_group(self):
        return self.get_physical_server_param("get_host_group")

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        # get main availability zones
        zone_idx = controller.index_resources_by_id(entity_class=Site)

        resource_idx = {}
        resource_ids = []
        for e in entities:
            resource_idx[e.oid] = e
            resource_ids.append(e.oid)

        # get main availability zones
        zone_idx = controller.index_resources_by_id(entity_class=Site)
        for entity in entities:
            if entity.availability_zone_id is not None:
                entity.availability_zone = zone_idx.get(entity.availability_zone_id)
        controller.logger.debug2("Get compute instance availability zones")

        # get other linked entities
        controller.logger.debug2("Get compute instance linked entities")
        objdefs = [
            ComputeImage.objdef,
            SecurityGroup.objdef,
            Vpc.objdef,
            ComputeVolume.objdef,
        ]
        # objdefs = [ComputeImage.objdef, ComputeFlavor.objdef, SecurityGroup.objdef, Vpc.objdef, ComputeVolume.objdef]
        linked = controller.get_directed_linked_resources_internal(
            resources=resource_ids, objdefs=objdefs, run_customize=False
        )

        for resource, enitities in linked.items():
            res = resource_idx[resource]
            for entity in enitities:
                if isinstance(entity, ComputeImage):
                    res.image = entity
                elif isinstance(entity, ComputeFlavor):
                    res.flavor = entity
                elif isinstance(entity, SecurityGroup):
                    res.sgs.append(entity)
                elif isinstance(entity, Vpc):
                    res.vpcs.append(entity)
                elif isinstance(entity, ComputeVolume):
                    res.volumes.append(entity)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        # get main availability zones
        if self.availability_zone_id is not None:
            self.availability_zone = self.controller.get_simple_resource(self.availability_zone_id)
        self.logger.debug2("Get compute instance availability zones: %s" % self.availability_zone)

        # get main zone instance
        res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    self.main_zone_instance = zone_inst
        self.logger.debug2("Get compute instance main zone instance: %s" % self.main_zone_instance)

        # set physical_server
        if self.main_zone_instance is not None:
            self.physical_server = self.main_zone_instance.get_physical_server()
            if self.physical_server is not None:
                self.physical_server_status = self.physical_server.get_status()
        self.logger.debug2("Get physical server: %s" % self.physical_server)

        # get other linked entities
        objdefs = [
            ComputeImage.objdef,
            ComputeFlavor.objdef,
            SecurityGroup.objdef,
            Vpc.objdef,
            ComputeVolume.objdef,
        ]
        # objdefs = [ComputeImage.objdef, CSecurityGroup.objdef, Vpc.objdef, ComputeVolume.objdef]
        linked = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], objdefs=objdefs, run_customize=False
        )
        self.logger.debug2("Get compute instance linked entities: %s" % linked)

        for entity in linked.get(self.oid, []):
            if isinstance(entity, ComputeImage):
                self.image = entity
            elif isinstance(entity, ComputeFlavor):
                self.flavor = entity
            elif isinstance(entity, SecurityGroup):
                self.sgs.append(entity)
            elif isinstance(entity, Vpc):
                self.vpcs.append(entity)
            elif isinstance(entity, ComputeVolume):
                self.volumes.append(entity)

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used in container resource_import_factory method.

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
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :param kvargs.configs.multi_avz: if True create instance to act in all the availability zones [default=True]
        :param kvargs.configs.orchestrator_tag: orchestrator tag [default=default]
        :param kvargs.configs.hostname: hostname [default=name]
        :param kvargs.configs.key_name: key name [optional]
        :param kvargs.configs.admin_pass: admin password [optional]
        :param kvargs.configs.image: image resource id [optional]
        :param kvargs.configs.resolve: define if instance must be registered on the availability zone dns zone
            [default=True]
        :param kvargs.configs.manage: define if instance must be registered in ssh module for management [default=True]
        :return: kvargs
        :raise ApiManagerError:
        """
        physical_id = kvargs.get("physical_id")
        params = kvargs.get("configs", {})

        # check server type from ext_id
        server = controller.get_resource(physical_id)
        if isinstance(server, OpenstackServer) is True:
            orchestrator_type = "openstack"
        elif isinstance(server, VsphereServer) is True:
            orchestrator_type = "vsphere"
        else:
            raise ApiManagerError("ComputeInstance require Openstack or Vpshere server as physical_id")

        # check parent compute zone match server parent
        project_id = server.parent_id
        parent = container.get_aggregated_resource_from_physical_resource(project_id)
        parent.set_container(container)
        kvargs["objid"] = "%s//%s" % (parent.objid, id_gen())
        kvargs["parent"] = parent.oid

        from beehive_resource.plugins.provider.entity.zone import ComputeZone

        compute_zone: ComputeZone = parent

        # get main availability zone
        main_availability_zone = container.get_availability_zone_from_physical_resource(project_id)
        site = main_availability_zone.get_parent()
        main_availability_zone = main_availability_zone.oid
        multi_avz = params.get("multi_avz", True)

        # get availability zones ACTIVE
        availability_zones = []
        if multi_avz is True:
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
            availability_zones.remove(main_availability_zone)

        # get flavor
        mapping_flavor = server.get_flavor_resource()
        if mapping_flavor is None:
            raise ApiManagerError("no mapping flavor found for server %s" % server.oid)
        flavor = container.get_aggregated_resource_from_physical_resource(mapping_flavor.oid)

        # get host group
        host_group_config = None
        host_group = None

        # get volumes
        total_storage = 0
        block_devices = server.get_volumes()
        for volume in block_devices:
            total_storage += volume.get("size")

        # get networks
        nets = []
        for network in server.get_networks():
            physical_net_id = network.get("id")
            physical_net_uuid = network.get("uuid")

            # get vpc
            vpc = container.get_aggregated_resource_from_physical_resource(physical_net_id, parent_id=parent.oid)
            zone_net = container.get_zone_resource_from_physical_resource(physical_net_id)
            attrib = zone_net.attribs["configs"]
            dns_search = attrib.get("dns_search", "nivolalocal")

            # - check subnet
            if orchestrator_type == "vsphere":
                # cidr = network.get('subnet')
                allocable_subnet = zone_net.get_allocable_subnet(None, orchestrator_type=orchestrator_type)
            elif orchestrator_type == "openstack":
                allocable_subnet = zone_net.get_allocable_subnet(orchestrator_type=orchestrator_type)
                # # get subnet
                # vpc_net_subnets = attrib.get('subnets')
                # allocable_subnet = None
                # for item in vpc_net_subnets:
                #     if item.get('allocable', True) is True:
                #         allocable_subnet = item
                # if allocable_subnet is None:
                #     raise ApiManagerError('No available subnet found in network %s ' % zone_net.oid)

            nets.append(
                {
                    "vpc": vpc.oid,
                    "id": zone_net.oid,
                    "physical_net_id": physical_net_uuid,
                    "subnet": allocable_subnet,
                    # 'other_subnets': not_allocable_subnet,
                    "fixed_ip": {
                        "dns_search": dns_search,
                        "ip": server.get_main_ip_address(),
                    },
                }
            )

        # get security groups
        sgs = []
        for sg in server.get_security_groups():
            obj = container.get_aggregated_resource_from_physical_resource(sg.oid)
            sgs.append(obj.oid)

        # fqdn
        hostname = params.get("hostname", kvargs.get("name"))
        fixed_ip0 = nets[0]["fixed_ip"]
        fqdn_name = hostname.replace("_", "-")
        fqdn = "%s.%s" % (fqdn_name, fixed_ip0.get("dns_search"))

        # get key_name or admin_pass
        key_name = params.get("key_name", None)
        admin_pass = params.get("admin_pass", None)
        if key_name is None and admin_pass is None:
            raise ApiManagerError("at least key_name or admin_pass must be set")
        if key_name is not None:
            # read key value
            keys = compute_zone.get_ssh_keys(oid=key_name)
            if len(keys) > 0:
                # kvargs['key_name'] = keys[0]['id']
                kvargs["key_name"] = keys[0]["uuid"]
        if admin_pass is not None:
            kvargs["admin_pass"] = admin_pass

        orchestrator_tag = params.get("orchestrator_tag", "default")

        manage = params.get("manage", True)
        manage = manage and compute_zone.is_managed()

        # get image
        image = container.get_simple_resource(params["image"], entity_class=ComputeImage)
        image.check_active()

        # set params
        params = {
            "hostname": hostname,
            "orchestrator_tag": orchestrator_tag,
            "compute_zone": compute_zone.oid,
            "flavor": flavor.oid,
            "networks": nets,
            "security_groups": sgs,
            "main_availability_zone": main_availability_zone,
            "host_group": host_group_config,
            "type": orchestrator_type,
            "resolve": params.get("resolve", True),
            "manage": manage,
            "image_id": image.oid,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                "host_group": host_group,
                "fqdn": fqdn,
                "key_name": key_name,
                # 'os': image,
                "configs": {},
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeInstance.task_path + "create_resource_pre_step",
            ComputeInstance.task_path + "link_compute_instance_step",
            {
                "step": ComputeInstance.task_path + "import_zone_instance_step",
                "args": [main_availability_zone],
            },
            ComputeInstance.task_path + "import_compute_volumes_step",
        ]
        # create secondary instance
        for availability_zone in availability_zones:
            steps.append(
                {
                    "step": ComputeInstance.task_path + "import_zone_instance_step",
                    "args": [availability_zone],
                }
            )
        # manage instance
        steps.append(ComputeInstance.task_path + "manage_compute_instance_step")
        # register to dns
        steps.append(ComputeInstance.task_path + "register_dns_compute_instance_step")
        # post create
        steps.append(ComputeInstance.task_path + "create_resource_post_step")

        kvargs["steps"] = steps
        return kvargs

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
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: site id or uuid
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.flavor: server flavor
        :param kvargs.admin_pass: admin password
        :param kvargs.security_groups: list of security groups id or uuid
        :param kvargs.networks: list of networks to configure on server
        :param kvargs.networks.x.vpc: vpc id or uuid
        :param kvargs.networks.x.subnet: subnet reference [optional]
        :param kvargs.networks.x.fixed_ip: dictionary with network configuration [optional]
        :param kvargs.networks.x.fixed_ip.ip: ip address [optional]
        :param kvargs.networks.x.fixed_ip.hostname: hostname [optional]
        :param kvargs.block_device_mapping: Enables fine grained control of the block device mapping for an instance.
        :param kvargs.block_device_mapping.x.device_name: A path to the device for the volume that you want to use to
            boot the server. [TODO]
        :param kvargs.block_device_mapping.x.source_type: The source type of the volume. A valid value is: snapshot -
            creates a volume backed by the given volume snapshot referenced via the block_device_mapping_v2.uuid
            parameter and attaches it to the server, volume - uses the existing persistent volume referenced via the
            block_device_mapping_v2.uuid parameter and attaches it to the server, image - creates an image-backed
            volume in the block storage service and attaches it to the server
        :param kvargs.block_device_mapping.x.volume_size: size of volume in GB
        :param kvargs.block_device_mapping.x.uuid: This is the uuid of source resource. The uuid points to different
            resources based on the source_type. If source_type is image, the block device is created based on the
            specified image which is retrieved from the image service. If source_type is snapshot then the uuid refers
            to a volume snapshot in the block storage service. If source_type is volume then the uuid refers to a
            volume in the block storage service.
        :param kvargs.block_device_mapping.x.flavor: The volumeflavor. This can be used to specify the type
            of volume which the compute service will create and attach to the server.
        :param kvargs.block_device_mapping.x.delete_on_termination: To delete the boot volume when the server is
            destroyed, specify true. Otherwise, specify false. [TODO]
        :param kvargs.block_device_mapping.x.guest_format: Specifies the guest server disk file system format, such as
            ephemeral or swap. [TODO]
        :param kvargs.block_device_mapping.x.boot_index: Defines the order in which a hypervisor tries devices when it
            attempts to boot the guest from storage. Give each device a unique boot index starting from 0. To
            disable a device from booting, set the boot index to a negative value or use the default boot index
            value, which is None. The simplest usage is, set the boot index of the boot device to 0 and use the
            default boot index value, None, for any other devices. Some hypervisors might not support booting from
            multiple devices; these hypervisors consider only the device with a boot index of 0. Some hypervisors
            support booting from multiple devices but only if the devices are of different types. For example, a
            disk and CD-ROM. [TODO]
        :param kvargs.block_device_mapping.x.tag: datastore tag (ex. user oracle to create server vsphere in cluster
            oracle)
        :param kvargs.user_data: Ex. 'IyEvYmluL2Jhc2gKL2Jpbi9zdQplY2hvICJJIGFtIGluIHlvdSEiCg==',
        :param kvargs.key_name: ssh key name or uuid
        :param kvargs.metadata: custom metadata. To create vsphere server in a non default cluster specify the key
            cluster=cluster_name and dvs=dvs_name. Ex. {'My Server Name' : 'Apache1'}
        :param kvargs.personality: Ex. [{'path': '/etc/banner.txt', 'contents': 'dsdsd=='}]
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.resolve: define if instance must be registered on the availability zone dns zone [default=True]
        :param kvargs.manage: define if instance must be registered in ssh module for management [default=True]
        :return: dict
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get("type")
        compute_zone_id = kvargs.get("parent")
        site_id = kvargs.get("availability_zone")
        multi_avz = kvargs.get("multi_avz")
        flavor_id = kvargs.get("flavor")
        sg_ids = kvargs.get("security_groups", [])
        networks = kvargs.get("networks")
        block_devices = kvargs.pop("block_device_mapping", [])
        key_name = kvargs.get("key_name", None)
        metadata = kvargs.get("metadata", {})
        host_group = kvargs.get("host_group", "default")
        check_main_vol_size = kvargs.get("check_main_vol_size", True)

        # get compute zone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        site = container.get_resource(site_id)

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
        # availability_zones = []
        # if multi_avz is True:
        #     availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
        #     availability_zones.remove(main_availability_zone)

        # get flavor
        flavor = container.get_simple_resource(flavor_id, entity_class=ComputeFlavor)
        flavor.check_active()
        flavor_attrib = flavor.get_attribs().get("configs")

        # get volumes
        total_storage = 0
        template_additional_disks = []
        max_boot_index = 0
        for block_device in block_devices:
            boot_index = block_device.get("boot_index", None)
            source_type = block_device.get("source_type")
            volume_size = block_device.get("volume_size", None)
            volume_flavor = block_device.get("flavor", None)

            max_boot_index = max(max_boot_index, boot_index)

            if boot_index != 0 and volume_size is None:
                raise ApiManagerError("Additional disks must define size")
            if boot_index == 0 and volume_size is None:
                volume_size = flavor_attrib.get("disk")

            if source_type == "image":
                obj = container.get_simple_resource(volume_flavor, entity_class=ComputeVolumeFlavor)
                block_device["flavor"] = obj.uuid

                if boot_index != 0:
                    raise ApiManagerError("Only boot disk can be created by an image")
                obj = container.get_simple_resource(block_device["uuid"], entity_class=ComputeImage)
                obj.check_active()

                # check image exists in selected availability zone
                imgs, tot = obj.get_linked_resources(
                    link_type="relation.%s" % site.oid,
                    run_customize=False,
                    objdef=Image.objdef,
                )
                if tot == 0:
                    raise ApiManagerError(
                        "Image %s does not exist in availability zone %s" % (block_device["uuid"], site.uuid)
                    )

                if check_main_vol_size and boot_index == 0:
                    from beehive_resource.plugins.openstack.entity.ops_image import (
                        OpenstackImage,
                    )
                    from beehive_resource.plugins.vsphere.entity.vs_server import (
                        VsphereServer,
                    )

                    template_res_type = VsphereServer if orchestrator_type == "vsphere" else OpenstackImage
                    disk_size_var_name = "disk" if orchestrator_type == "vsphere" else "minDisk"
                    template, tot = imgs[0].get_linked_resources(
                        link_type="relation",
                        run_customize=True,  # altrimenti info() non contiene i dati relativi alla dimensione minima volume
                        objdef=template_res_type.objdef,
                    )
                    if tot == 0:
                        raise ApiManagerError(
                            "Template for image %s does not exist for hypervisor %s in availability zone %s"
                            % (block_device["uuid"], orchestrator_type, site.uuid)
                        )
                    template_min_disk_size = template[0].info().get("details", {}).get(disk_size_var_name, 0)
                    if volume_size < template_min_disk_size:
                        raise ApiManagerError(
                            "Template for image %s with hypervisor %s in availability zone %s requires a main disk of min size %s, but %s was given"
                            % (
                                block_device["uuid"],
                                orchestrator_type,
                                site.uuid,
                                template_min_disk_size,
                                volume_size,
                            )
                        )

                # if orchestrator type is vsphere get server template
                template_disks = obj.get_attribs(key="configs.template_disks")
                if template_disks is not None:
                    for disk_size in template_disks.split(","):
                        template_additional_disks.append(
                            {
                                "boot_index": None,
                                "volume_size": int(disk_size),
                                "flavor": volume_flavor,
                                "from_template": True,
                            }
                        )

                image_volume_size = obj.get_attribs(key="configs.min_disk_size")
                if volume_size < image_volume_size:
                    volume_size = image_volume_size
                block_device["volume_size"] = volume_size
                block_device["uuid"] = obj.uuid
            elif source_type == "volume":
                if orchestrator_type == "vsphere":
                    raise ApiManagerError("Source type volume is not yet supported for type vsphere")
                obj = container.get_simple_resource(block_device["uuid"], entity_class=ComputeVolume)
                obj.check_active()
                block_device["uuid"] = obj.oid

                # get volume flavor
                obj = container.get_simple_resource(volume_flavor, entity_class=ComputeVolumeFlavor)
                obj.check_active()
                block_device["flavor"] = obj.uuid
            elif source_type == "snapshot":
                # todo
                raise ApiManagerError("Source type snapshot is not yet supported")

        # add template_additional_disks
        for template_additional_disk in template_additional_disks:
            max_boot_index += 1
            template_additional_disk["boot_index"] = max_boot_index
            block_devices.append(template_additional_disk)

        # get networks
        nets = []
        for network in networks:
            # get vpc
            vpc: Vpc = container.get_simple_resource(network["vpc"], entity_class=Vpc)
            vpc.check_active()
            if vpc.parent_id != compute_zone.oid:
                raise ApiManagerError("Vpc %s is not in compute zone  %s" % (network["vpc"], compute_zone.oid))

            vpc_net: SiteNetwork = vpc.get_network_by_site(site.oid)  # vede i link "relation." + site
            vpc_net_id = vpc_net.oid

            # check if network is global or private
            if IPv4Network(vpc_net.get_cidr()).is_private is False:
                multi_avz = False

            # - get fixed_ip
            fixed_ip = network.get("fixed_ip", {})

            # - get hostname
            hostname = fixed_ip.get("hostname", kvargs.get("name"))

            # - verify that vpc is not external
            attrib = vpc_net.get_attribs(key="configs")
            if attrib.get("external", False) is True:
                raise ApiManagerError("Vpc %s is external" % vpc_net_id)

            # - get http proxy
            http_proxy = attrib.get("proxy", None)
            if http_proxy is not None:
                metadata["http_proxy"] = http_proxy

            # - get network dns_search
            dns_search = attrib.get("dns_search", "nivolalocal")
            fixed_ip["dns_search"] = dns_search

            # - check subnet
            cidr = network.get("subnet")
            # orchestrator_type non serve!
            allocable_subnet = vpc_net.get_allocable_subnet(cidr, orchestrator_type=orchestrator_type)

            nets.append(
                {
                    "vpc": vpc.oid,
                    "subnet": allocable_subnet,
                    # 'other_subnets': not_allocable_subnet,
                    "fixed_ip": fixed_ip,
                }
            )

        # get remote security groups
        sgs = []
        for sg_id in sg_ids:
            obj = container.get_simple_resource(sg_id, entity_class=SecurityGroup)
            obj.check_active()
            sgs.append(obj.oid)

        # fqdn
        fixed_ip0 = nets[0]["fixed_ip"]
        fqdn_name = hostname.replace("_", "-")
        fqdn = "%s.%s" % (fqdn_name, fixed_ip0.get("dns_search"))

        # set key_name in metadata
        if key_name is not None:
            # read key value
            keys = compute_zone.get_ssh_keys(oid=key_name)
            metadata["pubkey"] = ensure_text(b64decode(keys[0]["pub_key"]))

        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        manage = kvargs.get("manage", True)
        manage = manage and compute_zone.is_managed()

        # get availability zones ACTIVE
        availability_zones = []
        if multi_avz is True:
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
            availability_zones.remove(main_availability_zone)

        # set params
        params = {
            "hostname": hostname,
            "orchestrator_tag": orchestrator_tag,
            "compute_zone": compute_zone.oid,
            "flavor": flavor.oid,
            "networks": nets,
            "security_groups": sgs,
            "main_availability_zone": main_availability_zone,
            "host_group": host_group_config,
            "metadata": metadata,
            "resolve": kvargs.get("resolve", True),
            "manage": manage,
            "multi_avz": multi_avz,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                "host_group": host_group,
                "fqdn": fqdn,
                "key_name": key_name,
                "configs": {},
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeInstance.task_path + "create_resource_pre_step",
            ComputeInstance.task_path + "link_compute_instance_step",
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
        # post create
        steps.append(ComputeInstance.task_path + "create_resource_post_step")

        kvargs["steps"] = steps
        return kvargs

    def do_patch(self, **params):
        """method to execute to make custom resource operations useful to complete patch

        :param params: custom params required by task
        """
        physical_server = self.get_physical_server()
        # Patch2 is bugged and then I use tha patch
        # physical_server.patch2({}, sync=True)
        physical_server.patch()

        # patch volumes
        volumes = self.get_volumes()
        physical_volumes = {pv.oid: pv for pv in physical_server.get_volume_resources()}
        physical_volumes_present = []

        for volume in volumes:
            physical_volume = volume.get_physical_volume()
            if physical_volume.oid in physical_volumes.keys():
                physical_volumes_present.append(physical_volume.oid)
        physical_volumes_missed = [
            pv for pv_id, pv in physical_volumes.items() if pv_id not in physical_volumes_present
        ]

        # self.logger.warn(physical_volumes)
        # self.logger.warn(physical_volumes_present)
        self.logger.warn("this volumes are missing and must be added" % physical_volumes_missed)

        # run import volume task
        index = 1
        for physical_volume in physical_volumes_missed:
            disk_index = physical_volume.get_disk_index()
            if disk_index is None:
                disk_index = id_gen(length=4)
            data = {
                "parent": self.parent_id,
                "name": "%s-volume-%s" % (self.name, disk_index),
                "desc": "Volume %s" % params.get("desc"),
                "physical_id": physical_volume.uuid,
                "set_as_sync": True,
            }
            res, code = self.container.resource_import_factory(ComputeVolume, **data)
            volume_resource_uuid = res["uuid"]
            volume = self.container.get_simple_resource(volume_resource_uuid)
            self.add_link(
                "%s-volume-%s-link" % (self.oid, volume.oid),
                "volume.%s" % disk_index,
                volume.oid,
            )
            self.logger.debug("Link volume %s to instance %s" % (volume.oid, self.oid))
        self.clean_cache()
        return {"uuid": self.uuid}, 200

    @trace(op="patch")
    def patch(self, **params):
        """Patch resource using a celery job or the synchronous function patch_resource.

        :param params: custom params required by task
        :param params.sync: if True run sync task, if False run async task
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        #### use to recover error in security group ####
        # res, check = self.__check_or_update_sg(update=True)
        # self.update_state(ResourceState.ACTIVE)
        #
        # return {'uuid': self.uuid}, 200
        #### use to recover error in security group ####

        # self.do_patch(**params)

        # sync = params.pop('sync', False)
        # # verify permissions
        # self.verify_permisssions('patch')
        #
        # # change resource state
        # self.update_state(ResourceState.UPDATING)
        #
        # # run an optional pre patch function
        # params = self.pre_patch(**params)
        # self.logger.debug('params after pre udpate: %s' % params)
        #
        # # clean cache
        # self.clean_cache()
        #
        # # force patch with internal patch
        # force = params.pop('force', False)
        # self.logger.debug('Force patch: %s' % force)
        #
        #
        # self.patch_internal(**params)
        # if 'state' not in params:
        #     self.update_state(ResourceState.ACTIVE)
        # return {'uuid': self.uuid}, 200

    # def pre_patch(self, *args, **kvargs):
    #     """Pre patch function. This function is used in patch method. Extend this function to manipulate and validate
    #     patch input params.
    #
    #     :param args: custom params
    #     :param kvargs: custom params
    #     :param kvargs.cid: container id
    #     :param kvargs.id: resource id
    #     :param kvargs.uuid: resource uuid
    #     :param kvargs.objid: resource objid
    #     :param kvargs.ext_id: resource remote id
    #     :param kvargs.*orchestrator_tag: orchestrators tag
    #     :return: kvargs
    #     :raise ApiManagerError:
    #     """
    #     kvargs['steps'] = self.group_patch_step([
    #         self.task_path + 'remove_wrong_compute_volumes_step',
    #         self.task_path + 'import_compute_volumes_step'
    #     ])
    #
    #     return kvargs

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
        # post expunge
        steps.append(ComputeInstance.task_path + "expunge_resource_post_step")

        kvargs["steps"] = steps
        return kvargs

    #
    # manage through ssh module
    #
    @trace(op="update")
    def is_managed(self, *args, **kvargs):
        """Check compute instance is managed with ssh module.

        :return: True if it is managed
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        try:
            self.api_client.get_ssh_node(self.fqdn)
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                self.logger.debug("Compute instance %s is not managed by ssh module" % self.uuid)
                return False
            self.logger.error("Compute instance %s" % self.uuid, exc_info=True)
            raise
        self.logger.debug("Compute instance %s is managed by ssh module" % self.uuid)
        return True

    def get_credential(self, username="root"):
        """Get instance credential from ssh module

        :param username: username [default=root]
        """
        # check authorization
        self.verify_permisssions("update")

        if self.is_windows() is True:
            username = "Administrator"

        try:
            # get node
            # self.logger.debug('+++++ get_credential - self.fqdn: %s' % self.fqdn)
            res = self.api_client.get_ssh_node(self.fqdn)
            uuid = res.get("id")
            # self.logger.debug('+++++ get_credential - uuid: %s' % uuid)

            # self.logger.debug('+++++ get_credential - username: %s' % username)
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
                exc_info=True,
            )
            return uuid
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                pass
            else:
                raise

        # check compute zone is managed by ssh module
        from beehive_resource.plugins.provider.entity.zone import ComputeZone

        compute_zone: ComputeZone = self.get_parent()
        group = compute_zone.get_ssh_group()

        # check ssh key
        compute_zone.get_ssh_keys(oid=key)

        # get ip address
        ip_address = self.get_ip_address()

        # check if bastion exist in tenant
        bastion_host = compute_zone.get_bastion_host()
        attribute = ""
        if bastion_host is not None:
            try:
                bastion_ssh_node = self.api_client.get_ssh_node(bastion_host.fqdn)
                attribute = {"gateway": bastion_ssh_node.get("id")}
            except BeehiveApiClientError as ex:
                if ex.code == 404:
                    pass

        # create ssh node
        uuid = self.api_client.add_ssh_node(
            self.fqdn,
            self.desc,
            ip_address,
            group,
            user,
            key=key,
            attribute=jsonDumps(attribute),
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
                    exc_info=True,
                )
            else:
                raise

        uuid = self.api_client.delete_ssh_node(self.fqdn)

        self.logger.debug("Compute instance %s is now unmanaged by ssh module" % (self.uuid))
        return True

    #
    # dns
    #
    @trace(op="update")
    def get_dns_recorda(self, *args, **kvargs):
        """Get compute instance dns recorda.

        :param user: ssh node user
        :param key: ssh key uuid or name
        :param password: user password [default='']
        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("use")

        try:
            recorda = self.get_cached("get_dns_recorda")
            if recorda is None:
                recorda = None
                fqdn = self.fqdn.split(".")
                name = fqdn[0]
                zone_name = ".".join(fqdn[1:])
                zone = self.controller.get_resource(zone_name, entity_class=DnsZone)
                recordas, tot = self.controller.get_resources(
                    name=name,
                    parent=zone.oid,
                    entity_class=DnsRecordA,
                    objdef=DnsRecordA.objdef,
                    parents={zone.oid: {"id": zone.oid, "uuid": zone.uuid, "name": zone.name}},
                )
                if tot > 0:
                    recorda = recordas[0]
                    recorda.post_get()

                self.logger.debug("Compute instance %s recorda %s" % (self.uuid, recorda))
                self.set_cache("get_dns_recorda", recorda, ttl=3600)
            return recorda
        except ApiManagerError as ex:
            self.logger.error(ex.value, exc_info=True)
            return None

    @trace(op="update")
    def set_dns_recorda(self, force=True, ttl=30):
        """Set compute instance dns recorda.

        :param force: If True force registration of record in dns
        :param ttl: dns record time to live
        :return: recorda uuid
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # check recorda does not exist
        recorda = self.get_dns_recorda()
        self.reset_cache("get_dns_recorda")
        if recorda is None:
            fqdn = self.fqdn.split(".")
            name = fqdn[0]
            zone_name = ".".join(fqdn[1:])
            ip_addr = self.get_ip_address()

            # get zone
            zone = self.controller.get_resource(zone_name, entity_class=DnsZone)

            res = zone.resource_factory(DnsRecordA, name, desc=name, ip_addr=ip_addr, ttl=ttl, force=force)[0]

            self.logger.debug("Create instance %s recorda %s" % (self.uuid, res.get("uuid")))
            return res.get("uuid")
        else:
            self.logger.error("Recorda for instance %s already exist" % self.uuid)
            raise ApiManagerError("Recorda for instance %s already exist" % self.uuid)

    @trace(op="update")
    def unset_dns_recorda(self):
        """Unset compute instance dns recorda.

        :return: recorda uuid
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # check recorda does not exist
        recorda = self.get_dns_recorda()
        self.reset_cache("get_dns_recorda")

        if recorda is not None:
            uuid = recorda.uuid

            if recorda.get_base_state() not in ["ACTIVE", "ERROR"]:
                raise ApiManagerError("Recorda %s is not in a valid state" % uuid, code=400)
            recorda.delete()

            self.logger.debug("Delete instance %s recorda %s" % (self.uuid, uuid))
            return uuid
        else:
            self.logger.error("Recorda for instance %s does not exist" % self.uuid)
            raise ApiManagerError("Recorda for instance %s does not exist" % self.uuid)

    #
    # volumes
    #
    def get_volumes(self):
        """Get instance volume list"""
        volumes = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="volume%")
        return volumes.get(self.oid, [])

    def has_volume(self, volume_id):
        """Check if volume already attached to instance

        :param volume_id: volume uuid
        :return:
        """
        for volume in self.get_volumes():
            if volume.uuid == volume_id:
                return True
        return False

    #
    # snapshots
    #
    def get_snapshots(self):
        """Get instance snapshots list

        :return: [{'id':.., 'name':.., 'created_at':.., 'status':..}]
        """
        res = self.get_cached("get_snapshots")
        if res is None:
            res = []
            physical_server = self.get_physical_server()
            res = physical_server.get_snapshots()
            self.set_cache("get_snapshots", res, ttl=3600)
        return res

    #
    # backup
    #
    def is_backup_configurable(self, *args, **kwargs):
        """check if backup is configurable for this instance

        :param args:
        :param kwargs:
        :return: True or False
        """
        res = False

        # get site
        site_id = self.get_attribs().get("availability_zone")
        site = self.controller.get_resource(site_id)
        cluster_allowed = site.get_attribs().get("config.backup")
        # cluster_allowed: {'openstack': ['default', 'bck'], 'vsphere': ['default', 'oracle']}

        self.logger.debug("backup for instance %s is configurable? %s" % (self.oid, res))
        return res

    def has_backup(self, cache=True, ttl=1800):
        """check if instance has backup associated

        :return: True if instance has backup workload associated
        """

        def func():
            ret = self.get_physical_server_param("has_backup")
            if ret is None:
                ret = False
            return ret

        res = self.cache_data(self.backup_cache_key, func, cache, ttl)
        return res

    def get_physical_backup(self, cache=True, ttl=1800):
        """get info of physical backup associated

        :return: backup info
        """

        job = {}

        physical_server = self.get_physical_server()
        if physical_server is not None:
            job = self.get_physical_server().get_backup_job()
        res = job
        return res

    def get_physical_backup_status(self, size, page, cache=True, ttl=1800):
        """get status of physical backup associated

        :return: backup info
        """
        job = None
        restore_points = []
        restore_point_total = 0

        hypervisor = self.get_hypervisor()
        self.logger.debug("+++++ AAA - get_physical_backup_status - hypervisor: %s" % (hypervisor))

        if hypervisor == "openstack":
            physical_server: OpenstackServer = self.get_physical_server()
            if physical_server is not None:
                # implemented for openstack
                if hasattr(physical_server, "get_trilio_backup"):
                    workload_name, workload_id = physical_server.get_trilio_backup()
                    job = workload_id
                    if workload_id is not None:
                        restore_points = physical_server.get_backup_restore_points(workload_id)
                    res = {"job": job, "restore_points": restore_points, "restore_point_total": len(restore_points)}
                else:
                    res = {"job": "", "restore_points": restore_points, "restore_point_total": len(restore_points)}

        elif hypervisor == "vsphere":
            site_id = self.get_attribs().get("availability_zone")
            self.logger.debug("+++++ AAA - get_physical_backup_status - site_id: %s" % (site_id))
            site: Site = self.controller.get_resource(site_id)

            hypervisor_tag = "default"
            orchestrator_idx_veeam = site.get_orchestrators_by_tag(hypervisor_tag, select_types=["veeam"])
            self.logger.debug("+++++ AAA - get_backup_jobs - orchestrator_idx_veeam: %s" % orchestrator_idx_veeam)
            veeam_id_container = list(orchestrator_idx_veeam.keys())[0]
            self.logger.debug("+++++ AAA - get_backup_jobs - veeam_id_container: %s" % veeam_id_container)

            from beehive_resource.controller import ResourceController
            from beehive_resource.plugins.veeam.controller import VeeamContainer, VeeamManager

            resourceController: ResourceController = self.controller
            veeamContainer: VeeamContainer = resourceController.get_container(veeam_id_container)
            veeamContainer.get_connection()

            physical_server: Resource = self.get_physical_server()
            server_name = physical_server.name
            ext_id = physical_server.ext_id
            self.logger.debug(
                "+++++ AAA - get_backup_jobs - list restore point for server_name: %s - ext_id: %s"
                % (server_name, ext_id)
            )
            # server_name = "dev-beehive-01" # test

            page = page + 1

            from beedrones.veeam.restore_point import VeeamRestorePoint

            veeamManager: VeeamManager = veeamContainer.conn_veeam
            veeamRestorePoint: VeeamRestorePoint = veeamManager.restorepoint
            veeam_restore_point = veeamRestorePoint.list(restorepoint_name=server_name, page_size=size, page=page)

            veeam_restore_point_data = veeam_restore_point["data"]
            veeam_restore_point_pagination = veeam_restore_point["pagination"]
            restore_point_total = veeam_restore_point_pagination["total"]
            self.logger.debug("+++++ AAA - get_backup_jobs - veeam_restore_point_data: %s" % veeam_restore_point_data)

            resource_type = "ComputeInstance"
            restore_points = [
                {
                    "id": restore_point.get("id"),
                    "name": restore_point.get("name"),
                    "desc": "-",
                    "created": restore_point.get("creationTime"),
                    "type": "-",
                    "status": "-",
                    "hypervisor": hypervisor,
                    "site": site.name,
                    "resource_type": resource_type,
                }
                for restore_point in veeam_restore_point_data
            ]

            res = {"job": "", "restore_points": restore_points, "restore_point_total": restore_point_total}

        return res

    def get_physical_backup_restore_status(self, restore_point, cache=True, ttl=1800):
        """get status of physical backup restores

        :return: backup info
        """
        restores = []
        physical_server = self.get_physical_server()
        if physical_server is not None:
            restores = physical_server.get_backup_restore_status(restore_point)
        res = {"restores": restores}
        return res

    #
    # metrics
    #
    def is_image_commercial(self):
        if self.image is not None:
            config = self.image.get_configs()
            os = config.get("os").lower()
            if os.find("windows") >= 0 or os.find("redhat") >= 0:
                return 1
        return 0

    def is_image_opensource(self):
        if self.image is not None:
            config = self.image.get_configs()
            os = config.get("os").lower()
            if os.find("centos") >= 0 or os.find("ubuntu") >= 0 or config.get("os").find("OracleLinux") >= 0:
                return 1
        return 0

    # objs ZabbixHost created/deleted with synchronizes cli command
    # per test cache=False
    def is_monitoring_enabled(self, cache=False, ttl=300):
        def func():
            filter_name = self.fqdn
            if self.is_windows() is True:
                filter_name = self.fqdn.split(".")[0] + "%"
            self.logger.debug(
                "+++++ AAA - is_monitoring_enabled - func - oid: %s - filter_name: %s" % (self.oid, filter_name)
            )

            from beehive_resource.plugins.zabbix.entity.zbx_host import ZabbixHost
            from beehive_resource.controller import ResourceController

            resourceController: ResourceController = self.controller
            # res, total = resourceController.get_resources(type=ZabbixHost.objdef, name=filter_name)
            res, total = resourceController.get_resources(
                objdef=ZabbixHost.objdef, type=ZabbixHost.objdef, name=filter_name, run_customize=False
            )
            self.logger.debug(
                "+++++ AAA - is_monitoring_enabled - func - oid: %s - res: %s - total: %s" % (self.oid, res, total)
            )
            if total >= 1:
                return 1

            return 0

        str_monitoring_wait_sync_till = self.get_attribs(key="monitoring_wait_sync_till")
        if str_monitoring_wait_sync_till is not None:
            self.logger.debug(
                "+++++ AAA - is_monitoring_enabled - str_monitoring_wait_sync_till: %s" % str_monitoring_wait_sync_till
            )
            monitoring_wait_sync_till = datetime.strptime(str_monitoring_wait_sync_till, "%m/%d/%Y, %H:%M:%S")

            dt = datetime.now()
            if dt < monitoring_wait_sync_till:
                self.logger.debug("+++++ AAA - is_monitoring_enabled - from monitoring_enabled")
                if self.get_attribs(key="monitoring_enabled", default=False) is True:
                    res = 1
                else:
                    res = 0
            else:
                self.logger.debug("+++++ AAA - is_monitoring_enabled - unset monitoring_wait_sync_till")
                self.unset_configs(key="monitoring_wait_sync_till")
                res = self.cache_data(self.monitor_cache_key, func, cache, ttl)
        else:
            res = self.cache_data(self.monitor_cache_key, func, cache, ttl)

        # res = func()
        return res

    # def is_monitoring_enabled(self, cache=True):
    #     if self.get_attribs(key='monitoring_enabled', default=False) is True:
    #         return 1
    #     return 0

    def is_logging_enabled(self):
        if self.get_attribs(key="logging_enabled", default=False) is True:
            return 1
        return 0

    def is_backup_enabled(self):
        res = self.has_backup()
        if res is True:
            return 1
        return 0

        # if self.get_attribs(key='backup_enabled', default=False) is True:
        #     return 1
        # return 0

    def get_metrics(self):
        """Get resource metrics

        :return: a dict like this

            {
                "id": "1",
                "uuid": "vm1",
                "metrics": [
                    {
                        "key": "ram",
                        "value: 10,
                        "type": 1,
                        "unit": "GB"
                    }],
                "extraction_date": "2018-03-04 12:00:34 200",
                "resource_uuid": "12u956-2425234-23654573467-567876"
            }
        """
        if self.has_quotas() is False:
            self.logger.warning("Compute instance %s has metric disabled" % self.oid)
            return {
                "id": self.oid,
                "uuid": self.uuid,
                "resource_uuid": self.uuid,
                "type": self.objdef,
                "metrics": [],
                "extraction_date": format_date(datetime.today()),
            }

        # base metric units
        metric_units = {
            "vm_os": "#",
            "vm_hyp": "#",
            "vm_os_ty": "#",
            # 'vm_lic_com': '#',
            # 'vm_lic_os': '#',
            "vm_float_ip": "#",
            "vm_monit": "#",
            "vm_log": "#",
            # 'vm_bck': '#',
            "vcpu": "#",
            "gbram": "GB",
            # 'gbdisk_hi': 'GB',
            # 'gbdisk_low': 'GB'
        }

        # get hypervisor specific metric label
        hypervisor = self.get_hypervisor()
        os = self.get_normalized_os()
        # base metric label
        metric_labels = {
            # 'vm_lic_com': 'vm_lic_com',
            # 'vm_lic_os': 'vm_lic_os',
            "vm_float_ip": "vm_float_ip",
            "vm_monit": "vm_monit",
            "vm_log": "vm_log",
            "vm_os_ty": f"vm_{os}_{hypervisor}",
            # 'vm_bck': 'vm_bck',
        }

        if hypervisor == "openstack":
            metric_labels.update(
                {
                    "vcpu": "vm_vcpu_os",
                    "gbram": "vm_gbram_os",
                    # 'gbdisk_hi': 'vm_gbdisk_hi_os',
                    # 'gbdisk_low': 'vm_gbdisk_low_os'
                }
            )
        elif hypervisor == "vsphere":
            metric_labels.update(
                {
                    "vcpu": "vm_vcpu_com",
                    "gbram": "vm_gbram_com",
                    # 'gbdisk_hi': 'vm_gbdisk_hi_com',
                    # 'gbdisk_low': 'vm_gbdisk_low_com'
                }
            )

        metrics = {
            metric_labels.get("vcpu"): 0,
            metric_labels.get("gbram"): 0,
            # metric_labels.get('gbdisk_low'): 0,
            # metric_labels.get('gbdisk_hi'): 0,
            metric_labels.get("vm_os_ty"): 1,
            # metric_labels.get('vm_lic_com'): self.is_image_commercial(),
            # metric_labels.get('vm_lic_os'): self.is_image_opensource(),
            metric_labels.get("vm_float_ip"): 0,
            metric_labels.get("vm_monit"): self.is_monitoring_enabled(),
            metric_labels.get("vm_log"): self.is_logging_enabled(),
            # metric_labels.get('vm_bck'): 0,
        }

        physical_server = self.get_physical_server()
        if physical_server is not None:
            data = physical_server.info().get("details")
            disk = data.get("disk")
            memory = 0
            cpu = 0
            if data.get("state") == "poweredOn":
                memory = data.get("memory")
                if memory is None:
                    memory = data.get("ram")
                cpu = data.get("cpu")

                self.set_configs("quotas.compute.cores", cpu)
                self.set_configs("quotas.compute.ram", memory)

            metrics = {
                metric_labels.get("vcpu"): cpu,
                metric_labels.get("gbram"): memory / 1024,
                # metric_labels.get('gbdisk_low'): disk,
                # metric_labels.get('vm_lic_com'): self.is_image_commercial(),
                # metric_labels.get('vm_lic_os'): self.is_image_opensource(),
                metric_labels.get("vm_os_ty"): 1,
                metric_labels.get("vm_float_ip"): 0,
                metric_labels.get("vm_monit"): self.is_monitoring_enabled(),
                metric_labels.get("vm_log"): self.is_logging_enabled(),
                # metric_labels.get('vm_bck'): self.is_backup_enabled(),
            }
            metric_units = {metric_labels.get(k): v for k, v in metric_units.items()}

        metrics = [{"key": k, "value": v, "type": 1, "unit": metric_units.get(k)} for k, v in metrics.items()]
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get compute instance %s metrics: %s" % (self.oid, res))
        return res

    #
    # scheduled actions
    #
    def scheduled_action(self, action, schedule=None, params=None):
        """Create scheduled action

        :param action: action name
        :param schedule: schedule [optional]
        :param params: action params [optional]
        :return: schedule name
        :raises ApiManagerError if query empty return error.
        """
        self.verify_permisssions("update")

        if schedule is None:
            schedule = {"type": "timedelta", "minutes": 1}
        params = {
            "id": self.oid,
            "action": action,
            "action_params": params,
            "steps": [
                # self.task_path + 'remove_schedule_step',
                self.task_path
                + "run_scheduled_action_step"
            ],
        }
        schedule_name = super().scheduled_action(
            "%s.%s" % (action, self.oid),
            schedule,
            params=params,
            task_path="beehive_resource.plugins.provider.task_v2.",
            task_name="provider_resource_scheduled_action_task",
        )

        return schedule_name

    #
    # apply customization
    #
    def set_ansible_ssh_common_args(self, data, username="root"):
        # ansible_ssh_common_args: '-o ProxyCommand="sshpass -p mypass ssh -o StrictHostKeyChecking=no -W %h:%p -q ' \
        #                          'root@84.1.2.3 -p 11100"'
        from beehive_resource.plugins.provider.entity.bastion import ComputeBastion
        from beehive_resource.plugins.provider.entity.zone import ComputeZone

        computeZone: ComputeZone = self.get_parent()
        bastion_host: ComputeBastion = computeZone.get_bastion_host()
        if bastion_host is None:
            return data

        nat_ip_address, nat_ip_port = bastion_host.get_nat_ip_address().split(":")
        params = {
            "username": username,
            "pwd": bastion_host.get_credential(username=username).get("password"),
            "host": nat_ip_address,
            "port": nat_ip_port,
        }
        ansible_ssh_common_args = (
            "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "
            '-o ProxyCommand="sshpass -p {pwd} ssh -o UserKnownHostsFile=/dev/null '
            "-o StrictHostKeyChecking=no -W %h:%p -q "
            '{username}@{host} -p {port}"'.format(**params)
        )
        data["ansible_ssh_common_args"] = ansible_ssh_common_args

        data["ansible_host"] = self.get_ip_address()
        data["ansible_connection"] = "ssh"

        # set python3 path
        if self.is_image_py3() is True:
            data["ansible_python_interpreter"] = "/usr/bin/python3"
        else:
            data["ansible_python_interpreter"] = "/usr/bin/python"

        return data

    #
    # actions
    #
    def action(self, name, sync=False, *args, **kvargs):
        """Execute an action

        :param name: action name
        :param sync: if True run sync task, if False run async task
        :param args: custom positional args
        :param kvargs: custom key value args
        :param kvargs.internal_steps: custom action internal steps
        :param kvargs.hypervisor: custom action hypervisor
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        zone_instance = self.get_main_zone_instance()

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            kvargs = check(**kvargs)

        # clean cache
        self.clean_cache()

        # get custom action params
        internal_step = {
            "step": ComputeInstance.task_path + "send_action_to_zone_instance_step",
            "args": [zone_instance.oid],
        }
        internal_steps = kvargs.pop("internal_steps", [internal_step])
        hypervisor = kvargs.get("hypervisor", self.get_hypervisor())

        # create internal steps
        run_steps = [ComputeInstance.task_path + "action_resource_pre_step"]
        run_steps.extend(internal_steps)
        run_steps.append(ComputeInstance.task_path + "action_resource_post_step")

        # manage params
        params = {
            "cid": self.container.oid,
            "id": self.oid,
            "objid": self.objid,
            "ext_id": self.ext_id,
            "action_name": name,
            "hypervisor": hypervisor,
            "hypervisor_tag": self.get_hypervisor_tag(),
            "steps": run_steps,
            "alias": "%s.%s" % (self.__class__.__name__, name),
            # 'sync': True
        }
        params.update(kvargs)
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, params, sync=sync)
        self.logger.info("%s compute instance %s using task" % (name, self.uuid))
        return res

    def start(self, *rags, **kvargs):
        """Start check function

        :return: kvargs
        """
        if self.is_running() is True:
            raise ApiManagerError("Instance %s is already running" % self.uuid)

        return {}

    def stop(self, *rags, **kvargs):
        """Stop check function

        :return: kvargs
        """
        if self.is_running() is False:
            raise ApiManagerError("Instance %s is not running" % self.uuid)

        return {}

    def reboot(self, *rags, **kvargs):
        """Reboot check function

        :return: kvargs
        """
        if self.is_running() is False:
            raise ApiManagerError("Instance %s is not running" % self.uuid)

        return {}

    def set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: compute flavor uuid or name
        :return: kvargs
        """
        res = self.container.get_resource(flavor, entity_class=ComputeFlavor, run_customize=False)

        # check flavor not already linked
        links, total = self.get_linked_resources(link_type="flavor")
        if links[0].oid == res.oid:
            raise ApiManagerError("Flavor %s already assigned to instance %s" % (res.uuid, self.uuid))

        return {"flavor": res.oid}

    def add_volume(self, volume=None, *args, **kvargs):
        """Add volume check function

        :param volume: compute volume uuid or name
        :return: kvargs
        """
        if volume is None:
            # search volume in kvargs
            try:
                volume = kvargs["data"]["action"]["add_volume"]["volume"]
            except KeyError:
                pass
        res = self.container.get_resource(volume, entity_class=ComputeVolume)
        if res.is_allocated() is True:
            raise ApiManagerError("Volume %s is already allocated" % res.uuid)
        if res.get_hypervisor() != self.get_hypervisor():
            raise ApiManagerError("Volume %s hypervisor mismatch with instance %s hypervisor" % (res.uuid, self.uuid))

        return {"volume": res.oid}

    def del_volume(self, volume=None, *args, **kvargs):
        """Del volume check function

        :param volume: compute volume uuid or name
        :return: kvargs
        """
        res = self.container.get_simple_resource(volume, entity_class=ComputeVolume)
        if self.has_volume(res.uuid) is False:
            raise ApiManagerError("Volume %s is not attached to instance" % res.uuid)

        return {"volume": res.oid}

    def extend_volume(self, volume=None, *args, **kvargs):
        """Extend volume check function

        :param volume: compute volume uuid or name
        :return: kvargs
        """
        res = self.container.get_simple_resource(volume, entity_class=ComputeVolume)
        if self.has_volume(res.uuid) is False:
            raise ApiManagerError("Volume %s is not attached to instance" % res.uuid)
        kvargs["volume"] = res.oid
        return kvargs

    def add_security_group(self, security_group=None, *args, **kvargs):
        """Add security group check function

        :param security_group: security group uuid or name
        :return: kvargs
        """
        res = self.container.get_resource(security_group, entity_class=SecurityGroup)
        internal_steps = []
        zone_instances, total = self.get_linked_resources(link_type_filter="relation%")
        for zone_instance in zone_instances:
            internal_step = {
                "step": ComputeInstance.task_path + "send_action_to_zone_instance_step",
                "args": [zone_instance.oid],
            }
            internal_steps.append(internal_step)
        res = {
            "internal_steps": internal_steps,
            "hypervisor": None,
            "security_group": res.oid,
        }
        return res

    def del_security_group(self, security_group=None, *args, **kvargs):
        """Del security group check function

        :param security_group: security group uuid or name
        :return: kvargs
        """
        res = self.container.get_simple_resource(security_group, entity_class=SecurityGroup)
        internal_steps = []
        zone_instances, total = self.get_linked_resources(link_type_filter="relation%")
        for zone_instance in zone_instances:
            internal_step = {
                "step": ComputeInstance.task_path + "send_action_to_zone_instance_step",
                "args": [zone_instance.oid],
            }
            internal_steps.append(internal_step)
        res = {
            "internal_steps": internal_steps,
            "hypervisor": None,
            "security_group": res.oid,
        }
        return res

    def add_snapshot(self, snapshot=None, *args, **kvargs):
        """Add snapshot check function

        :param snapshot: snapshot name
        :return: kvargs
        """
        return {"snapshot": snapshot}

    def del_snapshot(self, snapshot=None, *args, **kvargs):
        """Del snapshot check function

        :param snapshot: snapshot id
        :return: kvargs
        """
        return {"snapshot": snapshot}

    def revert_snapshot(self, snapshot=None, *args, **kvargs):
        """Revert snapshot check function

        :param snapshot: snapshot id
        :return: kvargs
        """
        return {"snapshot": snapshot}

    # backup action
    # def add_backup_restore_point(self, full=True, *args, **kvargs):
    #     """add physical backup restore point
    #
    #     :param full: if full is True make a full backup otherwise make an incremental backup
    #     :return: kvargs
    #     """
    #     if self.get_physical_server().has_backup() is False:
    #         raise ApiManagerError('instance %s has no backup job associated' % self.oid)
    #
    #     res = {'full': full}
    #     return res
    #
    # def del_backup_restore_point(self, restore_point=None, *args, **kvargs):
    #     """delete physical backup restore point
    #
    #     :param restore_point: restore point id
    #     :return: kvargs
    #     """
    #     if self.get_physical_server().has_backup_restore_point(restore_point) is False:
    #         raise ApiManagerError('instance %s has no backup restore point %s associated' % (self.oid, restore_point))
    #
    #     res = {'restore_point': restore_point}
    #     return res

    def restore_from_backup(self, restore_point=None, instance_name=None, *args, **kvargs):
        """add physical backup restore point

        :param restore_point: restore point id
        :param instance_name: restored instance name
        :return: kvargs
        """
        hypervisor = self.get_hypervisor()
        if hypervisor not in ["openstack"]:
            raise ApiManagerError("hypervisor %s is not supported" % hypervisor)

        if self.get_physical_server().has_backup_restore_point(restore_point) is False:
            raise ApiManagerError("instance %s has no backup restore point %s associated" % (self.oid, restore_point))

        zone_instance = self.get_main_zone_instance()
        server_name = "%s-avz%s-%s-server" % (
            instance_name,
            zone_instance.get_parent().parent_id,
            zone_instance.get_physical_server().container_id,
        )

        internal_steps = [
            {
                "step": ComputeInstance.task_path + "send_action_to_zone_instance_step",
                "args": [zone_instance.oid],
            },
            {
                "step": ComputeInstance.task_path + "import_restored_server_step",
                "args": [],
            },
        ]
        res = {
            "internal_steps": internal_steps,
            "restore_point": restore_point,
            "server_name": server_name,
            "instance_name": instance_name,
        }
        return res

    # user action
    def manage_user_with_ssh_module(self, user, key, password):
        try:
            node = self.api_client.get_ssh_node(self.fqdn)
        except BeehiveApiClientError as ex:
            self.logger.error("Compute instance %s is not managed by ssh module" % self.uuid)

        # create ssh node user
        uuid = self.api_client.add_ssh_user(node, user, key, password=password)
        return uuid

    def unmanage_user_with_ssh_module(self, user):
        try:
            node = self.api_client.get_ssh_node(self.fqdn)
        except BeehiveApiClientError as ex:
            self.logger.error("Compute instance %s is not managed by ssh module" % self.uuid)

        # delete ssh node user
        self.api_client.delete_ssh_user("%s-%s" % (node.get("name"), user))
        self.logger.warn(user)
        return True

    def set_user_password_with_ssh_module(self, user, password):
        try:
            node = self.api_client.get_ssh_node(self.fqdn)
        except BeehiveApiClientError as ex:
            self.logger.error("Compute instance %s is not managed by ssh module" % self.uuid)

        # delete ssh node user
        self.api_client.update_ssh_user("%s-%s" % (node.get("name"), user), password=password)
        return True

    def add_user(self, user_name=None, user_pwd=None, user_ssh_key=None, *args, **kvargs):
        """Create user in instance

        :param user_name: user name
        :param user_pwd: user password
        :param user_ssh_key: user ssh key
        :return: kvargs
        """
        # check ssh key
        if user_ssh_key is None:
            user_ssh_key = ""
            key_id = None
        else:
            # check key exists
            compute_zone = self.get_parent()
            keys = compute_zone.get_ssh_keys(oid=user_ssh_key)
            key_id = keys[0]["uuid"]
            user_ssh_key = b64decode(keys[0].get("pub_key")).decode("utf-8")

        ansible_pwd = sha512_crypt.using(rounds=5000).hash(user_pwd)

        internal_steps = [
            {
                "step": ComputeInstance.task_path + "apply_customization_action_step",
                "args": [],
            },
            {"step": ComputeInstance.task_path + "manage_user_action_step", "args": []},
        ]
        res = {
            "internal_steps": internal_steps,
            "cmd": "add",
            "customization": "os-utility",
            "playbook": "manage_user.yml",
            "key_id": key_id,
            "password": user_pwd,
            "extra_vars": {
                "operation": "create",
                "user_name": user_name,
                "user_desc": user_name,
                "user_password": ansible_pwd,
                "user_ssh_key": user_ssh_key,
            },
        }
        return res

    def del_user(self, user_name=None, *args, **kvargs):
        """Create user in instance

        :param user_name: user name
        :return: kvargs
        """
        internal_steps = [
            {
                "step": ComputeInstance.task_path + "apply_customization_action_step",
                "args": [],
            },
            {"step": ComputeInstance.task_path + "manage_user_action_step", "args": []},
        ]
        res = {
            "internal_steps": internal_steps,
            "cmd": "del",
            "customization": "os-utility",
            "playbook": "manage_user.yml",
            "extra_vars": {"operation": "delete", "user_name": user_name},
        }
        return res

    def set_user_pwd(self, user_name=None, user_pwd=None, *args, **kvargs):
        """Set user password in instance

        :param user_name: user name
        :param user_pwd: user password
        :return: kvargs
        """
        ansible_pwd = sha512_crypt.using(rounds=5000).hash(user_pwd)

        internal_steps = [
            {
                "step": ComputeInstance.task_path + "apply_customization_action_step",
                "args": [],
            },
            {"step": ComputeInstance.task_path + "manage_user_action_step", "args": []},
        ]
        res = {
            "internal_steps": internal_steps,
            "cmd": "set-password",
            "customization": "os-utility",
            "playbook": "manage_user.yml",
            "password": user_pwd,
            "extra_vars": {
                "operation": "update-password",
                "user_name": user_name,
                "user_password": ansible_pwd,
            },
        }
        return res

    def set_ssh_key(self, user_name=None, user_ssh_key=None, *args, **kvargs):
        """Set user ssh key

        :param user_name: user name
        :param user_pwd: user password
        :param user_ssh_key: user ssh key
        :return: kvargs
        """
        internal_steps = []
        internal_step = {
            "step": ComputeInstance.task_path + "apply_customization_action_step",
            "args": [],
        }
        internal_steps.append(internal_step)
        res = {
            "internal_steps": internal_steps,
            "customization": "os-utility",
            "playbook": "manage_user.yml",
            "extra_vars": {
                "operation": "set-ssh-key",
                "user_name": user_name,
                "user_ssh_key": user_ssh_key,
            },
        }
        return res

    def unset_ssh_key(self, user_name=None, user_ssh_key=None, *args, **kvargs):
        """Unset user ssh key

        :param user_name: user name
        :param user_pwd: user password
        :param user_ssh_key: user ssh key
        :return: kvargs
        """
        internal_steps = []
        internal_step = {
            "step": ComputeInstance.task_path + "apply_customization_action_step",
            "args": [],
        }
        internal_steps.append(internal_step)
        res = {
            "internal_steps": internal_steps,
            "customization": "os-utility",
            "playbook": "manage_user.yml",
            "extra_vars": {
                "operation": "unset-ssh-key",
                "user_name": user_name,
                "user_ssh_key": user_ssh_key,
            },
        }
        return res

    def pre_monitoring(self):
        # get vpc
        vpcs, total = self.get_linked_resources(link_type="vpc", authorize=False, run_customize=False)
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.get_attribs().get("availability_zone")
        site = self.controller.get_resource(site_id)
        ip_repository = site.get_attribs().get("repo")

        # get zabbix server connection params
        orchestrator_tag = "tenant"
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=["zabbix"])
        orchestrator = next(iter(orchestrators.keys()))
        zabbix_container = self.controller.get_container(orchestrator, connect=False)
        conn_params = zabbix_container.conn_params["api"]
        zbx_srv_uri = conn_params.get("uri")
        zbx_srv_usr = conn_params.get("user")
        pwd = conn_params.get("pwd")
        zbx_srv_pwd = zabbix_container.decrypt_data(pwd).decode("utf-8")

        # get proxy
        all_proxies = vpc.get_proxies(site.oid)
        proxy, set_proxy = all_proxies.get("http")
        zbx_proxy_ip, zbx_proxy_name = all_proxies.get("zabbix")

        return {
            "ip_repository": ip_repository,
            "proxy": proxy,
            "zabbix_server_uri": zbx_srv_uri,
            "zabbix_server_username": zbx_srv_usr,
            "zabbix_server_password": zbx_srv_pwd,
            "zabbix_proxy_ip": zbx_proxy_ip,
            "zabbix_proxy_name": zbx_proxy_name,
        }

    def enable_monitoring(self, *args, **kvargs):
        """Enable resources monitoring over compute instance

        :param args: custom params
        :param dict kvargs: custom params
        :return: updated kvargs
        """
        params = self.pre_monitoring()
        ip_repository = params.get("ip_repository")
        proxy = params.get("proxy")
        zbx_srv_uri = params.get("zabbix_server_uri")
        zbx_srv_usr = params.get("zabbix_server_username")
        zbx_srv_pwd = params.get("zabbix_server_password")
        zbx_proxy_ip = params.get("zabbix_proxy_ip")
        zbx_proxy_name = params.get("zabbix_proxy_name")

        # get custom hostgroup
        host_group = kvargs.get("host_group")
        host_groups = kvargs.get("host_groups", None)
        if host_groups is None:
            host_groups = [self.get_parent().desc]
        if host_group is not None:
            host_groups.append(host_group)
        self.logger.debug("+++++ enable_monitoring - host_groups: %s" % host_groups)

        # per Windows
        host_group = None
        if len(host_groups) > 0:
            host_group = host_groups[0]

        # get custom templates
        templates = kvargs.get("templates", None)
        if templates is None:
            templates = []

        # set tasks
        internal_steps = [
            ComputeInstance.task_path + "apply_customization_action_step",
            ComputeInstance.task_path + "enable_monitoring_step",
        ]
        res = {
            "internal_steps": internal_steps,
            "customization": "zabbix-agent",
            "playbook": "install.yml",
            "extra_vars": {
                "p_ip_repository": ip_repository,
                "p_proxy_server": proxy,
                "p_no_proxy": "localhost,10.0.0.0/8",
                "p_zabbix_server": zbx_srv_uri,
                "p_zabbix_server_username": zbx_srv_usr,
                "p_zabbix_server_password": zbx_srv_pwd,
                "p_zabbix_proxy_ip": zbx_proxy_ip,
                "p_zabbix_proxy_name": zbx_proxy_name,
                "p_custom_host_groups": host_groups,
                "p_custom_host_group": host_group,
                "p_custom_templates": templates,
                "p_target_host": self.fqdn,
            },
        }
        self.logger.debug("+++++ enable_monitoring - res: %s" % res)

        # update res.extra_vars with extra_vars parameter passed in kvargs if exists
        extra_vars = kvargs.pop("extra_vars", None)
        if extra_vars is not None:
            res["extra_vars"].update(extra_vars)

        return res

    def disable_monitoring(self, *args, **kvargs):
        """Disable resources monitoring over compute instance

        :return: kvargs
        """
        # self.logger.debug("+++++ disable_monitoring - args: %s - kvargs: %s" % (args, kvargs))
        deregister_only = kvargs.get("deregister_only")
        if deregister_only is not None and deregister_only == True:
            self.logger.debug("+++++ disable_monitoring - deregister_only - remove ZabbixHost")
            # viene solo deregistrato su zabbix
            # remove zabbix agent config from zabbix
            from beehive_resource.plugins.zabbix.entity.zbx_host import ZabbixHost

            from beehive_resource.controller import ResourceController

            resourceController: ResourceController = self.controller
            self.logger.debug("+++++ disable_monitoring - self.fqdn: %s - %s" % (self.fqdn, self.fqdn.split(".")[0]))

            filter_name = self.fqdn
            if self.is_windows() is True:
                filter_name = self.fqdn.split(".")[0] + "%"

            res, total = resourceController.get_resources(type=ZabbixHost.objdef, name=filter_name)
            self.logger.debug("+++++ disable_monitoring - res: %s, total: %s" % (res, total))
            if total == 0 or len(res) == 0:
                self.logger.warn("+++++ disable_monitoring - ZabbixHost not found for %s" % self.fqdn)

                self.logger.debug("+++++ disable_monitoring - deregister_only not uninstall zabbix agent")
                params_monitoring = self.pre_monitoring()
                proxy = params_monitoring.get("proxy")
                zbx_srv_uri = params_monitoring.get("zabbix_server_uri")
                zbx_srv_usr = params_monitoring.get("zabbix_server_username")
                zbx_srv_pwd = params_monitoring.get("zabbix_server_password")

                # set tasks
                internal_steps = [
                    ComputeInstance.task_path + "apply_customization_action_step",
                    ComputeInstance.task_path + "disable_monitoring_step",
                ]
                res = {
                    "internal_steps": internal_steps,
                    "customization": "zabbix-agent",
                    "playbook": "deregister.yml",
                    "extra_vars": {
                        "p_zabbix_server": zbx_srv_uri,
                        "p_zabbix_server_username": zbx_srv_usr,
                        "p_zabbix_server_password": zbx_srv_pwd,
                        "p_target_host": self.fqdn,
                        "p_proxy_server": proxy,
                    },
                }

            else:
                zabbixHost: ZabbixHost = res[0]
                zabbixHost.expunge2({}, sync=True)
                res = {"internal_steps": []}

        else:
            if self.is_monitoring_enabled(cache=False) == 0:
                self.logger.debug("+++++ disable_monitoring - monitoring is not enabled - do nothing")
                res = {"internal_steps": []}
            else:
                self.logger.debug("+++++ disable_monitoring - monitoring is enabled - remove also zabbix agent")
                params_monitoring = self.pre_monitoring()
                proxy = params_monitoring.get("proxy")
                zbx_srv_uri = params_monitoring.get("zabbix_server_uri")
                zbx_srv_usr = params_monitoring.get("zabbix_server_username")
                zbx_srv_pwd = params_monitoring.get("zabbix_server_password")

                # set tasks
                internal_steps = [
                    ComputeInstance.task_path + "apply_customization_action_step",
                    ComputeInstance.task_path + "disable_monitoring_step",
                ]
                res = {
                    "internal_steps": internal_steps,
                    "customization": "zabbix-agent",
                    "playbook": "uninstall.yml",
                    "extra_vars": {
                        "p_zabbix_server": zbx_srv_uri,
                        "p_zabbix_server_username": zbx_srv_usr,
                        "p_zabbix_server_password": zbx_srv_pwd,
                        "p_target_host": self.fqdn,
                        "p_proxy_server": proxy,
                    },
                }

        return res

    def enable_log_module(self, *args, **kvargs):
        """Enable log module

        :param args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        """
        self.logger.info("+++++ enable_log_module - args: {}".format(args))
        self.logger.info("+++++ enable_log_module - kvargs: {}".format(kvargs))

        module = kvargs.get("module", None)
        # potrebbero arrivare già giusti dalla definition
        module_params = kvargs.get("module_params", None)

        # set tasks
        internal_steps = [
            ComputeInstance.task_path + "apply_customization_action_step",
            ComputeInstance.task_path + "enable_log_module_step",
        ]

        # params = {
        #     'name': module,
        #     'logs': [
        #         '/appserv/tomcat90/clu001node01/logs/*.log',
        #     ],
        #     'input': 'file'
        # }

        res = {
            "internal_steps": internal_steps,
            "customization": "filebeat",
            "playbook": "modules_start.yml",
            "extra_vars": {"p_module": module_params},
        }
        return res

    def disable_log_module(self, *args, **kvargs):
        """Disable log module

        :param args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        """
        self.logger.info("+++++ disable_log_module - args: {}".format(args))
        self.logger.info("+++++ disable_log_module - kvargs: {}".format(kvargs))

        module = kvargs.get("module", None)
        # potrebbero arrivare già giusti dalla definition
        module_params = kvargs.get("module_params", None)

        # set tasks
        internal_steps = [
            ComputeInstance.task_path + "apply_customization_action_step",
            ComputeInstance.task_path + "disable_log_module_step",
        ]

        # params = {
        #     'name': module
        # }

        res = {
            "internal_steps": internal_steps,
            "customization": "filebeat",
            "playbook": "modules_stop.yml",
            "extra_vars": {"p_module": module_params},
        }
        return res

    def disable_logging(self, *args, **kvargs):
        """Disable logging

        :param args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        """
        self.logger.info("+++++ disable_logging - args: {}".format(args))
        self.logger.info("+++++ disable_logging - kvargs: {}".format(kvargs))

        # set tasks
        internal_steps = [
            ComputeInstance.task_path + "apply_customization_action_step",
            ComputeInstance.task_path + "disable_logging_step",
        ]

        res = {
            "internal_steps": internal_steps,
            "customization": "filebeat",
            "playbook": "uninstall.yml",
            "extra_vars": {},
        }
        return res

    def enable_logging(self, *args, **kvargs):
        """Enable log forwarding over compute instance

        :param args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        """
        # get vpc
        vpcs, total = self.get_linked_resources(link_type="vpc", authorize=False, run_customize=False)
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.get_attribs().get("availability_zone")
        site = self.controller.get_resource(site_id)
        ip_repository = site.get_attribs().get("repo")
        parent_desc = self.get_parent().desc

        # get proxy
        all_proxies = vpc.get_proxies(site_id)
        proxy, set_proxy = all_proxies.get("http")

        logstash_proxy = all_proxies.get("socks")
        logstash_server = site.get_logstash()
        logstash_port = kvargs.get("logstash_port", 5044)
        index_name = parent_desc.lower()
        p_cert_dns = parent_desc.lower()

        inputs = kvargs.get("files", None)
        if inputs is None:
            inputs = ["/var/log/messages", "/var/log/*.log"]

        # get awx container
        orchestrator_tag = "default"
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=["awx"])
        orchestrator = next(iter(orchestrators.values()))

        # get awx inventory
        inventories = dict_get(orchestrator, "config.inventories", default=[])
        if len(inventories) < 1:
            raise ApiManagerError("no awx inventory configured for orchestrator %s" % orchestrator["id"])
        inventory = inventories[0]
        inventory_id = inventory.get("id")
        ssh_cred_id = inventory.get("credential")

        # get customization
        from beehive_resource.plugins.provider.entity.customization import (
            ComputeCustomization,
        )
        from beehive_resource.plugins.awx.entity.awx_project import AwxProject

        compute_customization = self.controller.get_simple_resource("filebeat", entity_class=ComputeCustomization)
        customization = compute_customization.get_local_resource(site_id)
        awx_project = customization.get_physical_resource(AwxProject.objdef)

        template_name = "filebeat-%s-create-cert-%s" % (index_name, id_gen(8))
        job_template_args = [
            {
                "name": template_name,
                "desc": template_name,
                "inventory": inventory_id,
                "project": awx_project.oid,
                "playbook": "certificate.yml",
                "verbosity": 0,
                "ssh_cred_id": ssh_cred_id,
                "extra_vars": "p_cert_dns:%s" % p_cert_dns,
            },
            orchestrator,
        ]

        internal_steps = [
            {
                "step": ComputeInstance.task_path + "create_awx_job_template_step",
                "args": job_template_args,
            },
            ComputeInstance.task_path + "apply_customization_action_step",
            ComputeInstance.task_path + "enable_logging_step",
        ]
        res = {
            "internal_steps": internal_steps,
            "customization": "filebeat",
            "playbook": "install.yml",
            "extra_vars": {
                "p_ip_repository": ip_repository,
                "p_proxy_server": proxy,
                "p_no_proxy": "localhost,10.0.0.0/8",
                "p_logstash_server": logstash_server,
                "p_logstash_port": logstash_port,
                "p_logstash_proxy": logstash_proxy,
                "p_index_name": index_name,
                "p_inputs": inputs,
                "p_cert_dns": p_cert_dns,
            },
        }
        return res

    def run_ad_hoc_command(self, command, *args, **kvargs):
        """Create awx ad hoc command resource

        :param command: command to execute
        :param kvargs: custom params
        :param kvargs.parse: set output parser. Can be json or text
        :return: command output
        """
        from beehive_resource.plugins.awx.entity.awx_ad_hoc_command import (
            AwxAdHocCommand,
        )

        # get site
        site_id = self.get_attribs().get("availability_zone")
        site = self.controller.get_resource(site_id)

        # get awx container
        orchestrator_tag = "default"
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=["awx"])
        orchestrator = next(iter(orchestrators.values()))

        # set awx_job_template params
        name = "%s-ad-hoc-cmd-%s" % (self.name, id_gen())
        pwd = self.get_credential().get("password")
        user = self.get_real_admin_user()

        extra_vars = {
            "ansible_user": user,
            "ansible_password": pwd,
            "ansible_port": self.get_real_ssh_port(),
            "ansible_pipelining": True,
            "ansible_connection": "ssh",
            "ansible_ssh_common_args": "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no",
        }
        extra_vars = self.set_ansible_ssh_common_args(extra_vars)
        awx_ad_hoc_command_params = {
            "name": name,
            "desc": name,
            "organization": orchestrator["config"].get("organization"),
            "verbosity": 0,
            "ssh_creds": {"username": user, "password": pwd},
            "hosts": [{"ip_addr": self.get_ip_address(), "extra_vars": extra_vars}],
            "module_name": "shell",
            "module_args": command,
            "attribute": {},
            "sync": True,
        }

        # create awx_job_template
        awx_container = self.controller.get_container(orchestrator["id"])
        res = awx_container.resource_factory(AwxAdHocCommand, **awx_ad_hoc_command_params)
        uuid = res[0].get("uuid")
        resource = self.controller.get_resource(uuid)
        output = resource.get_stdout(parse=kvargs.get("parse", "json"))

        return output

    def apply_customization(self, name, ac_data, sync=False, *args, **kvargs):
        """Execute an action by running an applied customization

        :param name: the name of the action to be executed
        :param ac_data: applied customization data, i.e. customization, playbook, extra_vars
        :param sync: if True run sync task, if False run async task
        :param args: custom positional args
        :param kvargs: custom key value args
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        # clean cache
        self.clean_cache()

        # create task workflow
        run_steps = [
            ComputeInstance.task_path + "action_resource_pre_step",
            ComputeInstance.task_path + "apply_customization_action_step",
            ComputeInstance.task_path + "action_resource_post_step",
        ]

        # manage params
        cid = self.container_id
        if self.container is not None:
            cid = self.container.oid

        params = {
            # 'cid': self.container.oid, # container can be None
            "cid": cid,
            "id": self.oid,
            "objid": self.objid,
            "ext_id": self.ext_id,
            "action_name": name,
            "hypervisor": kvargs.get("hypervisor", self.get_hypervisor()),
            "hypervisor_tag": self.get_hypervisor_tag(),
            "steps": run_steps,
            # 'sync': True
        }
        params.update(ac_data)
        params.update(kvargs)
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, params, sync=sync)
        self.logger.info("Apply customization %s on compute instance %s using task - res: %s" % (name, self.uuid, res))
        return res

    #
    # console
    #
    @trace(op="use")
    def get_console(self):
        """Get console.

        :raise ApiManagerError:
        :return: console link { 'type': 'novnc', 'url': 'http://ctrl-liberty.nuvolacsi.it:6080/vnc_auto....' }
        """
        # verify permissions
        self.verify_permisssions("use")

        if self.get_hypervisor() == "openstack":
            url_path = "/vnc_auto.html"
        elif self.get_hypervisor() == "vsphere":
            url_path = "/vnc_auto2.html"

        # get console endpoint from site
        site = self.controller.get_simple_resource(self.get_attribs(key="availability_zone"))
        endpoint = site.get_attribs(key="config.console_base_uri", default="")

        physical_server = self.main_zone_instance.get_physical_server()
        res = physical_server.get_vnc_console(endpoint)
        url = res.get("url", None)
        if url is not None:
            url_parsed = urlparse(url)
            endpoint = endpoint.split("://")
            url_parsed = url_parsed._replace(scheme=endpoint[0])
            url_parsed = url_parsed._replace(netloc=endpoint[1])
            url_parsed = url_parsed._replace(path=url_path)
            new_url = url_parsed.geturl()
            res["url"] = new_url

        self.logger.debug("Get server %s console: %s" % (self.name, res))
        return res


class Instance(AvailabilityZoneChildResource):
    """Availability Zone Instance"""

    objdef = "Provider.Region.Site.AvailabilityZone.Instance"
    objuri = "%s/instances/%s"
    objname = "instance"
    objdesc = "Provider Availability Zone Instance"
    task_path = "beehive_resource.plugins.provider.task_v2.instance.ComputeInstanceTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    def is_main(self):
        """Check if it is the main zone instance

        :return: True or False
        """
        return self.get_attribs("main", default=False)

    def get_networks(self):
        """Get networks"""
        nets = []
        links = self.get_links("network")
        for link in links:
            nets.append(link.get_end_resource())
        return nets

    def get_physical_server(self):
        """Get remote physical server from orchestrator

        :return:
        """
        inst_type = self.get_attribs().get("type")
        if inst_type == "vsphere":
            objdef = VsphereServer.objdef
        elif inst_type == "openstack":
            objdef = OpenstackServer.objdef
        try:
            server = self.get_physical_resource(objdef)
        except:
            server = None
        return server

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource id to import [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag")
        orchestrator_type = kvargs.pop("type")
        main = kvargs.get("main")

        # get availability_zone
        availability_zone = container.get_simple_resource(kvargs.get("parent"))

        # select remote orchestrators
        orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag)

        # select main available orchestrators
        available_main_orchestrators = []
        for k, v in orchestrator_idx.items():
            if orchestrator_type == v["type"]:
                available_main_orchestrators.append(v)

        # main orchestrator is where instance will be created
        main_orchestrator = None
        if main is True:
            if len(available_main_orchestrators) > 0:
                index = randint(0, len(available_main_orchestrators) - 1)
                main_orchestrator = str(available_main_orchestrators[index]["id"])
            else:
                raise ApiManagerError("No available orchestrator exist where create server", code=404)

        # set container
        params = {
            "main_orchestrator": main_orchestrator,
            "orchestrators": orchestrator_idx,
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            Instance.task_path + "create_resource_pre_step",
            Instance.task_path + "link_instance_step",
            Instance.task_path + "import_main_server_step",
            Instance.task_path + "configure_network_step",
            Instance.task_path + "create_twins_step",
            Instance.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True
        return kvargs

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.main: True if this is the main instance where create server
        :param kvargs.compute_instance: id of the related compute instance
        :param kvargs.flavor: server flavor
        :param kvargs.image: server image
        :param kvargs.admin_pass: admin password
        :param kvargs.security_groups: list of security groups id or uuid
        :param kvargs.networks: list of networks to configure on server
        :param kvargs.networks.id: vpc id or uuid
        :param kvargs.networks.subnet: subnet reference [optional]
        :param kvargs.networks.fixed_ip : dictionary with network configuration [optional]
        :param kvargs.networks.fixed_ip.ip: [optional]
        :param kvargs.networks.fixed_ip.hostname: [optional]
        :param kvargs.user_data: Ex. 'IyEvYmluL2Jhc2gKL2Jpbi9zdQplY2hvICJJIGFtIGluIHlvdSEiCg==',
        :param kvargs.metadata: Ex. {'My Server Name' : 'Apache1'}
        :param kvargs.personality: Ex. [{'path': '/etc/banner.txt', 'contents': 'dsdsd=='}]
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag")
        orchestrator_type = kvargs.pop("type")
        main = kvargs.get("main")

        # get availability_zone
        availability_zone = container.get_simple_resource(kvargs.get("parent"))
        site_id = availability_zone.parent_id

        # get zone volumes
        compute_instance = container.get_simple_resource(kvargs.get("compute_instance"))
        compute_volumes, tot = compute_instance.get_linked_resources(
            link_type_filter="volume%",
            entity_class=ComputeVolume,
            objdef=ComputeVolume.objdef,
            run_customize=False,
        )
        compute_volumes.reverse()

        # get boot and other zone volumes
        zone_boot_volume = None
        zone_other_volumes = []

        if main is True:
            for compute_volume in compute_volumes:
                volumes, tot = compute_volume.get_linked_resources(
                    link_type_filter="relation.%s" % site_id,
                    entity_class=Volume,
                    objdef=Volume.objdef,
                    run_customize=False,
                )
                volume = volumes[0]
                bootable = compute_volume.is_bootable()
                if bootable is True:
                    zone_boot_volume = volume.oid
                else:
                    zone_other_volumes.append(volume.oid)

        # select remote orchestrators
        orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag)

        # select main available orchestrators
        available_main_orchestrators = []
        for k, v in orchestrator_idx.items():
            if orchestrator_type == v["type"]:
                available_main_orchestrators.append(v)

        # main orchestrator is where instance will be created
        main_orchestrator = None
        if main is True:
            if len(available_main_orchestrators) > 0:
                index = randint(0, len(available_main_orchestrators) - 1)
                main_orchestrator = str(available_main_orchestrators[index]["id"])
            else:
                raise ApiManagerError("No available orchestrator exist where create server", code=404)

        # set container
        params = {
            "main_orchestrator": main_orchestrator,
            "orchestrators": orchestrator_idx,
            "zone_boot_volume": zone_boot_volume,
            "zone_other_volumes": zone_other_volumes,
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            Instance.task_path + "create_resource_pre_step",
            Instance.task_path + "link_instance_step",
            Instance.task_path + "create_main_server_step",
            Instance.task_path + "configure_network_step",
            Instance.task_path + "create_twins_step",
            Instance.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True
        return kvargs

    @staticmethod
    def pre_clone(controller, container, *args, **kvargs):
        """Check input params before resource cloning. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.main: True if this is the main instance where create server
        :param kvargs.compute_instance: id of the related compute instance
        :param kvargs.flavor: server flavor
        :param kvargs.image: server image
        :param kvargs.admin_pass: admin password
        :param kvargs.security_groups: list of security groups id or uuid
        :param kvargs.networks: list of networks to configure on server
        :param kvargs.networks.id: vpc id or uuid
        :param kvargs.networks.subnet: subnet reference [optional]
        :param kvargs.networks.fixed_ip : dictionary with network configuration [optional]
        :param kvargs.networks.fixed_ip.ip: [optional]
        :param kvargs.networks.fixed_ip.hostname: [optional]
        :param kvargs.clone_instance: instance to clone
        :param kvargs.clone_instance_volume_flavor: The volumeflavor. This can be used to specify the type of volume
            which the compute service will create and attach to the server.
        :param kvargs.user_data: Ex. 'IyEvYmluL2Jhc2gKL2Jpbi9zdQplY2hvICJJIGFtIGluIHlvdSEiCg==',
        :param kvargs.metadata: Ex. {'My Server Name' : 'Apache1'}
        :param kvargs.personality: Ex. [{'path': '/etc/banner.txt', 'contents': 'dsdsd=='}]
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag")
        orchestrator_type = kvargs.pop("type")
        main = kvargs.get("main")

        # get availability_zone
        availability_zone = container.get_simple_resource(kvargs.get("parent"))
        # site_id = availability_zone.parent_id

        # get zone volumes
        # compute_instance = container.get_simple_resource(kvargs.get('compute_instance'))
        # compute_volumes, tot = compute_instance.get_linked_resources(
        #     link_type_filter='volume%', entity_class=ComputeVolume, objdef=ComputeVolume.objdef, run_customize=False)

        # get boot and other zone volumes
        # zone_boot_volume = None
        # zone_other_volumes = []

        # if main is True:
        #     for compute_volume in compute_volumes:
        #         volumes, tot = compute_volume.get_linked_resources(
        #             link_type_filter='relation.%s' % site_id, entity_class=Volume, objdef=Volume.objdef,
        #             run_customize=False)
        #         volume = volumes[0]
        #         bootable = compute_volume.is_bootable()
        #         if bootable is True:
        #             zone_boot_volume = volume.oid
        #         else:
        #             zone_other_volumes.append(volume.oid)

        # select remote orchestrators
        orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag)

        # select main available orchestrators
        available_main_orchestrators = []
        for k, v in orchestrator_idx.items():
            if orchestrator_type == v["type"]:
                available_main_orchestrators.append(v)

        # main orchestrator is where instance will be created
        main_orchestrator = None
        if main is True:
            if len(available_main_orchestrators) > 0:
                index = randint(0, len(available_main_orchestrators) - 1)
                main_orchestrator = str(available_main_orchestrators[index]["id"])
            else:
                raise ApiManagerError("No available orchestrator exist where create server", code=404)

        # set container
        params = {
            "main_orchestrator": main_orchestrator,
            "orchestrators": orchestrator_idx,
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            Instance.task_path + "create_resource_pre_step",
            Instance.task_path + "link_instance_step",
            Instance.task_path + "clone_main_server_step",
            Instance.task_path + "configure_network_step",
            Instance.task_path + "create_twins_step",
            Instance.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True
        return kvargs

    def action(self, name, params, hypervisor, hypervisor_tag):
        """Execute an action

        :param name: action name
        :param params: action params
        :param params.internal_step: custom internal_step [default=instance_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        orchestrator_idx = self.get_orchestrators_by_tag(hypervisor_tag, index_field="type")
        # if hypervisor is None return all the orchestrator else return only main orchestrator
        if hypervisor is not None:
            orchestrators = [orchestrator_idx[hypervisor]]
        else:
            orchestrators = list(orchestrator_idx.values())

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            params = check(**params)

        # get custom internal step
        internal_step = params.pop("internal_step", "instance_action_step")

        # clean cache
        self.clean_cache()

        # create internal steps
        run_steps = [Instance.task_path + "action_resource_pre_step"]
        for orchestrator in orchestrators:
            step = {"step": Instance.task_path + internal_step, "args": [orchestrator]}
            run_steps.append(step)
        run_steps.append(Instance.task_path + "action_resource_post_step")

        # manage params
        params.update(
            {
                "cid": self.container.oid,
                "id": self.oid,
                "objid": self.objid,
                "ext_id": self.ext_id,
                "action_name": name,
                "steps": run_steps,
                "alias": "%s.%s" % (self.__class__.__name__, name),
                # 'alias': '%s.%s' % (self.name, name)
            }
        )
        params.update(self.get_user())

        res = prepare_or_run_task(self, self.action_task, params, sync=True)
        self.logger.info("%s zone instance %s using task" % (name, self.uuid))
        return res

    def set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: compute flavor id
        :return: kvargs
        """
        site = self.get_site()
        compute_flavor = self.container.get_resource(flavor)
        flavors, total = compute_flavor.get_linked_resources(link_type_filter="relation.%s" % site.oid)
        return {"flavor": flavors[0].oid}

    def add_volume(self, volume=None, *args, **kvargs):
        """Add volume check function

        :param volume: compute volume uuid or name
        :return: kvargs
        """
        site = self.get_site()
        compute_volume = self.container.get_resource(volume)
        volumes, total = compute_volume.get_linked_resources(link_type_filter="relation.%s" % site.oid)
        return {"volume": volumes[0].oid}

    def del_volume(self, volume=None, *args, **kvargs):
        """Del volume check function

        :param volume: compute volume uuid or name
        :return: kvargs
        """
        site = self.get_site()
        compute_volume = self.container.get_resource(volume)
        volumes, total = compute_volume.get_linked_resources(link_type_filter="relation.%s" % site.oid)
        return {"volume": volumes[0].oid}

    def add_security_group(self, security_group=None, *args, **kvargs):
        """Add security group check function

        :param security_group: security group uuid or name
        :return: kvargs
        """
        site = self.get_site()
        compute_sg = self.container.get_resource(security_group)
        sgs, total = compute_sg.get_linked_resources(link_type_filter="relation.%s" % site.oid)
        res = {
            "internal_step": "instance_security_group_action_step",
            "security_group": sgs[0].oid,
        }
        return res

    def del_security_group(self, security_group=None, *args, **kvargs):
        """Del security group check function

        :param security_group: security group uuid or name
        :return: kvargs
        """
        site = self.get_site()
        compute_sg = self.container.get_simple_resource(security_group)
        sgs, total = compute_sg.get_linked_resources(link_type_filter="relation.%s" % site.oid)
        res = {
            "internal_step": "instance_security_group_action_step",
            "security_group": sgs[0].oid,
        }
        return res

    def add_snapshot(self, snapshot=None, *args, **kvargs):
        """Add snapshot check function

        :param snapshot: snapshot name
        :return: kvargs
        """
        return {"snapshot": snapshot}

    def del_snapshot(self, snapshot=None, *args, **kvargs):
        """Del snapshot check function

        :param snapshot: snapshot id
        :return: kvargs
        """
        return {"snapshot": snapshot}

    def revert_snapshot(self, snapshot=None, *args, **kvargs):
        """Revert snapshot check function

        :param snapshot: snapshot id
        :return: kvargs
        """
        return {"snapshot": snapshot}
