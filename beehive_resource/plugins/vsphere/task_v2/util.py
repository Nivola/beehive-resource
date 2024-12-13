# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import ujson as json
import base64
from celery.utils.log import get_task_logger
from gevent import sleep

from beecell.simple import id_gen, prefixlength_to_netmask
from beedrones.vsphere.server import VsphereGuestUtils
from beehive.common.task.job import job_task, task_local, job, JobError, Job
from beehive.common.task_v2 import run_sync_task
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.model import ResourceState
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType

logger = get_task_logger(__name__)


class VsphereServerBaseHelper(object):
    """Some vsphere server base helper methods"""

    def __init__(self, task, step_id, orchestrator, params, username="root", password=None):
        from beehive_resource.plugins.vsphere import VsphereContainer
        from beedrones.vsphere.client import VsphereManager

        vsphereContainer: VsphereContainer = orchestrator

        self.task = task
        self.orchestrator: VsphereContainer = vsphereContainer
        self.conn: VsphereManager = vsphereContainer.conn
        self.params = params
        self.user = username
        self.step_id = step_id
        self.template_pwd = password
        if self.template_pwd is None:
            logger.warn("Root password is not defined. Guest customization is not applicable")

    def progress(self, msg):
        self.task.progress(self.step_id, msg=msg)

    def check_server_up_and_configured(self, server):
        # get network config
        network = self.params.get("networks")[0]
        fixed_ip = network.get("fixed_ip", {})
        guest_host_name = fixed_ip.get("hostname", server.name)
        self.conn.server.wait_guest_hostname_is_set(server=server, hostname=guest_host_name, delta=20, maxtime=900)

    def is_windows(self, server):
        return VsphereGuestUtils.guest_is_windows(server)

    def reboot_windows_server(self, server):
        if self.is_windows(server):
            self.conn.server.reboot(server)
            sleep(5)
            self.wait_guest_tools_is_running(server)
            self.progress("Reboot server %s" % server)

    def set_admin_user_name(self, server):
        if self.is_windows(server):
            self.user = "Administrator"

    def set_ext_id(self, server_id, mor_id):
        # update resource
        self.orchestrator.update_resource(server_id, ext_id=mor_id)

    def get_volume_type(self, volume):
        volume_types, tot = self.orchestrator.get_resources(type=VsphereVolumeType.objdef)
        volume_type = None
        for vt in volume_types:
            if vt.has_datastore(volume.get("storage")) is True:
                volume_type = vt
                break
        if volume_type is None:
            raise JobError("No volume type found for volume %s" % volume.get("id"))
        logger.debug("Get volume type: %s" % volume_type)
        return volume_type

    def create_volume(self, name, desc, parent_id, server, volume_type, config, boot=False):
        source_type = config.get("source_type")
        volume_size = config.get("volume_size")

        image = None
        snapshot = None
        volume_uuid = None
        prepared_task = None
        if source_type == "image":
            image = config.get("uuid")
            prepared_task, code = self.orchestrator.resource_factory(
                VsphereVolume,
                name=name,
                desc=desc,
                parent=parent_id,
                size=volume_size,
                volume_type=volume_type,
                sync=True,
                source_volid=volume_uuid,
                snapshot_id=snapshot,
                imageRef=image,
            )
            volume_id = prepared_task.get("uuid")
            self.progress("Create volume resource %s" % volume_id)

        elif source_type in ["volume"]:
            # get existing volume
            volume_id = config.get("uuid")
            self.progress("Get existing volume resource %s" % volume_id)

        elif source_type is None:
            prepared_task, code = self.orchestrator.resource_factory(
                VsphereVolume,
                name=name,
                desc=desc,
                parent=parent_id,
                size=volume_size,
                volume_type=volume_type,
                sync=True,
                source_volid=volume_uuid,
                snapshot_id=snapshot,
                imageRef=image,
            )
            volume_id = prepared_task.get("uuid")
            self.progress("Create volume resource %s" % volume_id)

        # link volume id to server
        server.add_link(
            "%s-%s-volume-link" % (server.oid, volume_id),
            "volume",
            volume_id,
            attributes={"boot": boot},
        )
        self.progress("Setup volume link from %s to server %s" % (volume_id, server.oid))

        # run task
        if prepared_task is not None:
            run_sync_task(prepared_task, self.task, self.step_id)

        self.progress("Create volume %s - Completed" % volume_id)

        return volume_id

    def set_volumes_ext_id(self, inst, volumes):
        disks = self.conn.server.detail(inst).get("volumes")
        index = 0
        for volume in volumes:
            # volume_ext_id = disks[index]['unit_number']
            volume_ext_id = disks[index]["disk_object_id"]
            resource = self.task.get_simple_resource(volume)
            self.orchestrator.update_resource(resource.oid, ext_id=volume_ext_id)
            index += 1

    def connect_network(self, inst, network):
        try:
            # connect network
            net_number = 1
            vsphere_task = self.conn.server.hardware.update_network(
                inst, net_number, connect=True, network=network.ext_obj
            )
        except:
            # add network
            vsphere_task = self.conn.server.hardware.add_network(inst, network.ext_obj)

        # loop until vsphere task has finished
        self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress("Connect network %s" % network.ext_id)

    def __resource_to_vsphere(
        self,
        resource,
    ):
        """
        Take a vsphere object and return ext_obj the vsphere object to be passed to beedrones

        """
        if resource is not None:
            return resource.ext_obj
        return None

    def clone_from_template(
        self,
        server_id,
        name,
        folder,
        volume_type_id,
        volumes,
        network,
        resource_pool=None,
        cluster=None,
        customization_spec_name="WS201x PRVCLOUD custom OS sysprep",
    ):
        flavor = self.params.get("flavorRef")
        memory_mb = flavor.get("ram")
        cpu = flavor.get("vcpus")
        if cpu < 2:
            core_per_socket = 1
        else:
            core_per_socket = int(cpu / 2)

        # get volumes
        disks = []
        main_volume = volumes[0]

        # get total volume size required
        total_size = sum([volume.get("volume_size") for volume in volumes])

        # get datastore for all the disks. Use the volume_type of the main volume for all the volume
        volume_type = self.task.get_simple_resource(volume_type_id)
        volume_tag = main_volume.get("tag", None)
        datastore = volume_type.get_best_datastore(total_size, tag=volume_tag)

        # get template reference
        image_id = main_volume.get("image_id")
        template: VsphereServer = self.task.get_resource(image_id)

        if template is None:
            logger.error("template is None - resource image_id: %s not found" % (image_id))
            raise JobError("Vsphere template not found %s" % image_id)

        if template.ext_obj is None:
            logger.error("template: %s" % template)
            logger.error("template.ext_obj is None - image_id: %s" % (image_id))
            raise JobError("Vsphere template server not found - template name: %s" % template.name)

        for volume in volumes:
            disk_type = "secondary"
            if volume.get("boot_index", None) == 0:
                disk_type = "main"
            disks.append(
                {
                    "type": disk_type,
                    "name": "%s-disk-%s" % (name, id_gen(length=6)),
                    "size": volume.get("volume_size"),
                    "thin": True,
                    "datastore": datastore.ext_obj,
                }
            )

        if resource_pool is not None:
            resource_pool = resource_pool.ext_obj
        elif cluster is not None:
            cluster = cluster.ext_obj

        # get network config
        fixed_ip = self.params.get("networks")[0].get("fixed_ip", {})

        guest_host_name = fixed_ip.get("hostname", name)
        network_config = {
            "ip_address": fixed_ip.get("ip"),
            "ip_netmask": prefixlength_to_netmask(fixed_ip.get("prefix")),
            "ip_gateway": fixed_ip.get("gw"),
            "dns_server_list": fixed_ip.get("dns").split(","),
            "dns_domain": fixed_ip.get("dns_search", "local"),
        }

        metadata = self.params.get("metadata", {})
        # get proxy configuration
        http_proxy = None
        if not metadata.get("no_proxy"):
            http_proxy = metadata.get("http_proxy")
        https_proxy = http_proxy

        cust_spec = self.conn.server.customization.build_custom_spec(
            template.ext_obj,
            customization_spec_name,
            network_config,
            guest_host_name,
            self.template_pwd,
            admin_username=self.user,
            http_proxy=http_proxy,
            https_proxy=https_proxy,
        )

        self.progress(f"Clone {name} from template {template.name}")
        # clone template
        vsphere_task = self.conn.server.create_from_template(
            template.ext_obj,
            name,
            folder.ext_obj,
            datastore.ext_obj,
            resource_pool=resource_pool,
            cluster=cluster,
            power_on=False,
            customization=cust_spec,
        )

        # get physical server
        inst = self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        inst_mo_id = inst._moId
        self.progress(f"Get physical server: {inst_mo_id}")

        # set physical server
        self.set_ext_id(server_id, inst_mo_id)
        self.progress(f"Set physical server: {inst_mo_id}")

        # reconfigure vm
        self.progress(f"Reconfigure server {name}")
        vsphere_task = self.conn.server.reconfigure(
            inst,
            network.ext_obj,
            disks=disks,
            memoryMB=memory_mb,
            numCPUs=cpu,
            numCoresPerSocket=core_per_socket,
        )
        self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress(f"Reconfigured server {name}")

        # start server
        self.start(inst)

        # loop until vsphere customization has finished
        self.wait_for_customization(server_id)
        self.progress(f"Customized server {name}")

        # wait for guest tools is running
        self.wait_guest_tools_is_running(inst, maxtime=600)

        # check server is up and configured
        if self.is_windows(template.ext_obj):
            self.check_server_up_and_configured(inst)

        self.progress(f"Cloned {name} from template {template.name}")
        return inst

    def clone_from_server(
        self,
        dest_server_oid,
        source_server_oid,
        clone_name,
        dest_folder,
        volume_type_id,
        volumes,
        dest_network,
        dest_cluster=None,
        source_vm_username="root",
        source_vm_password=None,
    ):
        res_source_server = self.task.get_resource(source_server_oid)
        source_conn = res_source_server.container.conn
        metadata = self.params.get("metadata", {})
        client_dest = self.conn

        # network configuration
        net = self.params.get("networks", [])
        fallback_hostname = "vmwarevirtualplatform01"
        fallback_domain = "local"

        net_param = next(iter(net), {})
        fixed_ip = net_param.get("fixed_ip")
        ip_addr = fixed_ip.get("ip")
        subnet = prefixlength_to_netmask(fixed_ip.get("prefix"))
        hostname = fixed_ip.get("hostname", fallback_hostname)
        default_gw = fixed_ip.get("gw")
        domain_name = fixed_ip.get("dns_search", fallback_domain)
        dns_servers = fixed_ip.get("dns", "").split(",")

        # get proxy configuration
        http_proxy = None
        if not metadata.get("no_proxy"):
            http_proxy = metadata.get("http_proxy")
        https_proxy = http_proxy

        # get total volume size required
        main_volume = volumes[0]
        total_size = sum([volume.get("volume_size") for volume in volumes])

        # get datastore for all the disks.
        volume_type = self.task.get_simple_resource(volume_type_id)
        # use the volume_type of the main volume for all the volume
        dest_datastore = volume_type.get_best_datastore(total_size, tag=main_volume.get("tag"))

        vsphere_task = source_conn.server.create_clone(
            self.__resource_to_vsphere(res_source_server),
            clone_name,
            hostname,
            domain_name,
            client_dest,
            self.__resource_to_vsphere(dest_folder),
            self.__resource_to_vsphere(dest_datastore),
            self.__resource_to_vsphere(dest_cluster),
            self.__resource_to_vsphere(dest_network),
            source_vm_password,
            ip_addr,
            subnet,
            default_gw,
            dns_servers,
            http_proxy,
            https_proxy,
            source_vm_username=source_vm_username,
            source_vm_password=source_vm_password,
        )

        # call the vsphere clone task
        inst = self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress(
            "Cloning server %s (%s) into %s (%s)"
            % (res_source_server.name, source_server_oid, clone_name, source_server_oid)
        )

        # set physical server
        mo_id = inst._moId
        self.set_ext_id(dest_server_oid, mo_id)
        self.progress("Set physical vm %s to server %s (%s)" % (mo_id, source_server_oid, dest_server_oid))

        # wait for customization
        self.wait_for_customization(dest_server_oid)

        # when cloning cross pod new server instance needed
        res_dest_server = self.task.get_resource(dest_server_oid)
        res_inst = self.__resource_to_vsphere(res_dest_server)
        # wait for guest tools is running
        self.wait_guest_tools_is_running(res_inst, maxtime=600)

        self.progress(
            "Cloned server %s (%s) from server %s (%s) "
            % (clone_name, dest_server_oid, res_source_server.name, source_server_oid)
        )

        return res_inst

    def linked_clone_from_server(
        self,
        server_id,
        name,
        folder,
        volumes,
        network,
        resource_pool=None,
        cluster=None,
    ):
        """TODO: manage multiple disks"""
        # get server reference
        server_id = self.params.get("imageRef")
        server = self.task.get_resource(server_id)

        # get volumes
        disks = []
        for volume in volumes:
            datastore_id = volume.get("uuid")
            datastore = self.task.get_resource(datastore_id)
            disks.append(
                {
                    "name": "%s-disk-%s" % (name, id_gen(length=6)),
                    "size": volume.get("volume_size"),
                    "thin": False,
                    "datastore": datastore.ext_obj,
                }
            )
        main_volume = disks.pop(0)
        main_datastore = main_volume.get("datastore")

        if resource_pool is not None:
            resource_pool = resource_pool.ext_obj
        elif cluster is not None:
            cluster = cluster.ext_obj

        # start creation
        vsphere_task = self.conn.server.create_linked_clone(
            server.ext_obj,
            name,
            folder.ext_obj,
            main_datastore,
            resource_pool=resource_pool.ext_obj,
            cluster=cluster,
            power_on=False,
        )

        # get physical server
        inst = self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress("Get physical server: %s" % inst._moId)

        # set physical server
        self.set_ext_id(server_id, inst._moId)
        self.progress("Set physical server: %s" % inst._moId)

        self.progress("Server %s cloned" % server.name)

        # todo: add other volumes

        # connect network
        self.connect_network(inst, network)

        self.progress("Linked clone of server %s from server" % name)

        return inst

    def create_new(
        self,
        server_id,
        name,
        folder,
        volumes,
        datastore,
        network,
        resource_pool=None,
        cluster=None,
    ):
        """TODO: manage multiple disks"""
        # get params
        disk_size_gb = volumes[0].get("volume_size")
        flavor = self.params.get("flavorRef")
        guest_id = flavor.get("guest_id")
        memory_mb = flavor.get("ram")
        cpu = flavor.get("vcpus")
        core_x_socket = flavor.get("core_x_socket")
        version = flavor.get("version")

        # get volumes
        disks = []
        for volume in volumes:
            datastore_id = volume.get("uuid")
            datastore = self.task.get_resource(datastore_id)
            disks.append(
                {
                    "name": "%s-disk-%s" % (name, id_gen(length=6)),
                    "size": volume.get("volume_size"),
                    "thin": False,
                    "datastore": datastore.ext_obj,
                    "datastore_name": datastore.name,
                }
            )
        main_volume = disks.pop(0)
        main_datastore = main_volume.get("datastore")

        if resource_pool is not None:
            resource_pool = resource_pool.ext_obj
        elif cluster is not None:
            cluster = cluster.ext_obj

        # start creation
        vsphere_task = self.conn.server.create(
            name,
            guest_id,
            main_datastore,
            folder.ext_obj,
            network.ext_obj,
            memory_mb=memory_mb,
            cpu=cpu,
            core_x_socket=core_x_socket,
            disk_size_gb=int(disk_size_gb),
            version=version,
            power_on=False,
            resource_pool=resource_pool.ext_obj,
            cluster=cluster,
        )

        # get physical server
        inst = self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress("Get physical server: %s" % inst._moId)

        # set physical server
        self.set_ext_id(server_id, inst._moId)
        self.progress("Set physical server: %s" % inst._moId)

        # # loop until vsphere task has finished
        # inst = self.orchestrator.query_remote_task(self.task, task)
        self.progress("Server %s created" % name)

        # todo: add other volumes

        return inst

    def set_security_group(self, inst):
        inst_id = inst._moId
        securitygroups = self.params.get("security_groups")
        for sg in securitygroups:
            try:
                sg = self.task.get_simple_resource(sg)
            except:
                logger.warn("Vsphere security group %s does not exist" % sg["uuid"])
                self.update(
                    "PROGRESS",
                    msg="Vsphere security group %s does not exist" % sg["uuid"],
                )

            self.conn.network.nsx.sg.add_member(sg.ext_id, inst_id)

    def start(self, inst):
        inst_id = inst._moId
        vsphere_task = self.conn.server.start(inst)
        self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress("Start server %s" % inst_id)

    def stop(self, inst):
        state = inst.runtime.powerState
        oid = inst._moId
        logger.debug("Server %s current powerState is: %s" % (oid, state))
        if format(state) == "poweredOn":
            self.conn.server.stop(inst)
            # loop until vsphere task has finished
            # self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
            self.progress("Power off server %s" % oid)

    def release_network_ip_address(self, resource):
        # get ip and ippool
        ip_config = resource.get_ip_address_config()
        # release ip
        if ip_config is not None:
            subnet_pool = ip_config.get("subnet_pool", None)
            ip = ip_config.get("ip", None)
            if subnet_pool is not None and ip is not None:
                self.conn.network.nsx.ippool.release(subnet_pool, ip)
                self.progress("Release ip %s from subnet pool %s" % (ip, subnet_pool))

    def delete(self, resource, inst):
        # delete vsphere server
        oid = inst._moId
        vsphere_task = self.conn.server.remove(inst)
        # loop until vsphere task has finished
        self.orchestrator.query_remote_task(self.task, self.step_id, vsphere_task)
        self.progress("Remove server %s" % oid)

    def wait_for_customization(self, server_oid):
        resource_server = self.task.get_resource(server_oid)
        conn = resource_server.container.conn
        platform_server = resource_server.ext_obj
        self.progress(msg="Waiting for customization for server %s" % server_oid)
        is_customization_ok, error_msg = conn.server.wait_for_customization(platform_server)
        if not is_customization_ok:
            raise Exception("Customization failed for server %s: %s " % (server_oid, error_msg))
        else:
            self.progress(msg="Customization done successfully for server %s" % server_oid)

    def wait_guest_tools_is_running(self, inst, maxtime=240, delta=3):
        # wait until guest tools are running
        elapsed = 0
        status = self.conn.server.guest_tools_is_running(inst)
        while status is not True:
            status = self.conn.server.guest_tools_is_running(inst)
            self.progress(msg="Wait guest tools are running")
            # sleep a little
            sleep(delta)
            elapsed += delta
            if elapsed > maxtime:
                raise Exception(
                    "Guest tools are not still running on server %s after %s s. Task will be blocked"
                    % (inst._moId, maxtime)
                )
        self.progress(msg="Guest tools are running for server %s" % inst._moId)

    def reserve_network_ip_address(self):
        # setup only the first network
        networks = self.params.get("networks")
        subnet_pool = networks[0].get("subnet_pool", None)
        fixed_ip = networks[0].get("fixed_ip", {})
        dns_search = fixed_ip.get("dns_search", None)
        # if subnet_pool is not None and fixed_ip.get('ip', None) is None:
        if subnet_pool is not None:
            new_ip = self.conn.network.nsx.ippool.allocate(subnet_pool, static_ip=fixed_ip.get("ip", None))
            if dns_search is None:
                dns_search = new_ip.get("dnsSuffix")
            fixed_ip.update(
                {
                    "ip": new_ip.get("ipAddress"),
                    "gw": new_ip.get("gateway"),
                    "dns": new_ip.get("dnsServer1") + "," + new_ip.get("dnsServer2"),
                    "dns_search": dns_search,
                    "prefix": new_ip.get("prefixLength"),
                }
            )

        self.params["networks"][0]["fixed_ip"] = fixed_ip

    def disable_firewall(self, inst):
        if self.is_windows(inst) is True:
            # get ssh pwd
            ssh_pwd = self.params.get("adminPass", None)
            if ssh_pwd is None:
                logger.warn("ssh password is not defined.")
                return False

            # disable firewall
            self.wait_guest_tools_is_running(inst)
            self.conn.server.guest_disable_firewall(inst, ssh_pwd)
            self.progress("Disable server %s firewall" % inst.name)
        return True

    def setup_network(self, inst):
        # get network config
        networks = self.params.get("networks")
        subnet_pool = networks[0].get("subnet_pool", None)
        config = networks[0].get("fixed_ip", {})

        # exec only for linux server
        if self.is_windows(inst) is False:
            if config is not None:
                self.wait_guest_tools_is_running(inst)
                self.set_admin_user_name(inst)

                # configure ip
                ipaddr = config.get("ip")
                macaddr = self.conn.server.hardware.get_original_devices(inst, dev_type="vim.vm.device.VirtualVmxnet3")[
                    0
                ].macAddress
                gw = config.get("gw")
                hostname = config.get("hostname", inst.name)
                dns = config.get("dns", "")
                dns_search = config.get("dns_search", "local")

                prefix = config.get("prefix", 24)
                self.conn.server.guest_setup_network(
                    inst,
                    self.template_pwd,
                    ipaddr,
                    macaddr,
                    gw,
                    hostname,
                    dns,
                    dns_search,
                    conn_name="net01",
                    user=self.user,
                    prefix=prefix,
                )
            else:
                logger.warn("Network interface configuration is wrong")

        self.progress("Update network configuration")

        return [
            {
                "uuid": networks[0].get("uuid"),
                "ip": config.get("ip"),
                "subnet_pool": subnet_pool,
            }
        ]

    def guest_setup_install_software(self, inst):
        # install packages
        packages = self.params.get("metadata", {}).get("packages", None)
        self.conn.server.guest_setup_install_software(inst, self.user, self.template_pwd, pkgs=packages)
        self.progress("install packages")
        return None

    def setup_proxy(self, inst):
        no_proxy = self.params.get("metadata", {}).get("no_proxy", False)
        http_proxy = self.params.get("metadata", {}).get("http_proxy", None)

        # disable proxy
        if no_proxy is True:
            self.conn.server.disable_proxy(inst, self.user, self.template_pwd)
            self.progress("disable proxy")

        # configure proxy
        if http_proxy is not None:
            self.conn.server.configure_proxy(inst, self.user, self.template_pwd, http_proxy)
            self.progress("configure http proxy")
        return None

    def setup_ssh_key(self, inst):
        """
        Setup ssh key for admin username. It can be root or a non root sudoers.
        No windows implementation.
        """
        if self.is_windows(inst):
            logger.warn("No setup ssh key for windows.")
            return
        self.wait_guest_tools_is_running(inst)
        # get ssh key
        ssh_key = self.params.get("metadata", {}).get("pubkey", None)
        username = self.params.get("admin_username", None)
        if ssh_key is None:
            logger.warn("Ssh key is not defined.")
            return None

        self.conn.server.guest_setup_ssh_key(
            inst,
            self.user,
            self.template_pwd,
            ssh_key,
            admin_username=username,
        )
        self.progress("Setup ssh key.")

    def setup_ssh_pwd(self, inst):
        """
        Setup ssh password. It can be root or a non root sudoers.
        No windows implementation.
        """
        if self.is_windows(inst):
            logger.warn("No setup ssh password for windows.")
            return
        # get ssh pwd
        password = self.params.get("adminPass", None)
        username = self.params.get("admin_username", None)
        if password is None:
            logger.warn("ssh password is not defined.")
            return None

        self.conn.server.guest_setup_admin_password(
            inst,
            self.user,
            self.template_pwd,
            password,
            admin_username=username,
        )
        self.progress("Setup ssh password.")

    def create_server(
        self,
        server_oid,
        name,
        folder_id,
        datastore_id,
        resource_pool_id,
        network_id,
        source_type="image",
        customization_spec_name="WS201x PRVCLOUD custom OS sysprep",
    ):
        logger.info("Create new server %s - START" % name)

        # get folder
        folder = self.task.get_resource(folder_id)

        # create resource
        objid = "%s//%s" % (folder.objid, id_gen())
        model = self.orchestrator.add_resource(
            objid=objid,
            name=name,
            resource_class=VsphereServer,
            ext_id=None,
            active=False,
            desc="Stack server %s" % name,
            attrib={},
            parent=folder.oid,
        )
        self.orchestrator.update_resource_state(model.id, ResourceState.BUILDING)

        # get resource pool
        resource_pool = self.task.get_resource(resource_pool_id)

        # get volumes
        datastore = self.task.get_resource(datastore_id)

        # get networks
        network = self.task.get_resource(network_id)

        # clone server from template
        if source_type == "image":
            inst = self.clone_from_template(
                server_oid,
                name,
                folder,
                datastore,
                resource_pool,
                network,
                customization_spec_name=customization_spec_name,
            )

        # clone server from snapshot - linked clone
        elif source_type == "snapshot":
            inst = self.linked_clone_from_server(server_oid, name, folder, datastore, resource_pool, network)

        # create new server
        elif source_type == "volume":
            volumes = None
            inst = self.create_new(name, folder, volumes, resource_pool, datastore, network)
        else:
            raise JobError("Source type %s is not supported" % source_type)

        # set server security groups
        self.set_security_group(inst)

        # start server
        self.start(inst)

        # set network interface ip
        self.setup_network(inst)

        # setup ssh key
        self.setup_ssh_key(inst)

        # setup ssh password
        self.setup_ssh_pwd(inst)

        self.orchestrator.update_resource_state(model.id, ResourceState.ACTIVE)
        self.orchestrator.activate_resource(model.id)

        logger.info("Create new server %s - %s - STOP" % (name, model.oid))

        return model.oid


class VsphereServerHelper(VsphereServerBaseHelper):
    """vsphere server helper methods"""

    def __init__(self, task, step_id, orchestrator, params):
        super().__init__(
            task, step_id, orchestrator, params, password=params.get("metadata", {}).get("template_pwd", None)
        )
