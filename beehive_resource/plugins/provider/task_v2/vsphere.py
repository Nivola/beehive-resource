# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import ujson as json
from beecell.simple import id_gen, import_class, dict_set, dict_get
from beedrones.vsphere.client import VsphereError
from beehive.common.task_v2 import TaskError
from beehive_resource.container import CustomResource
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.vpc_v2 import SiteNetwork, PrivateNetwork
from beehive_resource.plugins.provider.task_v2 import AbstractProviderHelper, getLogger
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup
from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfwSection, NsxDfwRule
from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType

logger = getLogger(__name__)


class ProviderVsphere(AbstractProviderHelper):
    def type_mapping(self, mtype, mvalue):
        """Get vsphere type mapping

        :param mtype: type
        :param mvalue: value
        """
        res = None
        try:
            if mtype == "Network":
                resource = self.get_simple_resource(mvalue)
                net = resource.get_physical_resource_from_container(self.cid, VsphereDvpg.objdef)
                res = {
                    "type": "DistributedVirtualPortgroup",
                    "value": net.ext_id,
                    "name": None,
                }
            elif mtype == "Cidr":
                res = {"type": "Ipv4Address", "value": mvalue, "name": None}
            elif mtype == "Server":
                res = {"type": "Ipv4Address", "value": mvalue, "name": None}
            elif mtype == "RuleGroup":
                resource = self.get_simple_resource(mvalue)
                sg = resource.get_physical_resource_from_container(self.cid, NsxSecurityGroup.objdef)
                res = {"type": "SecurityGroup", "value": sg.ext_id, "name": None}
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            return None
        self.logger.debug("Get vsphere type %s:%s mapping: %s" % (mtype, mvalue, res))
        return res

    def set_quotas(self, quotas):
        """Set vsphere folder quotas.

        :param quotas: list of quotas to set
        :return: list
        :rtype: resource list
        :raise TaskError: If task fails
        """
        # get folder
        self.progress("Set folder %s quotas: %s" % (self.resource.uuid, quotas))
        return True

    def create_zone_childs(self, site, quotas=None):
        """Create availability zone childs.

        :param task: task reference
        :param orchestrator: orchestrator
        :param resource: parent resource
        :param site: site where is orchestrator
        :param quotas: list of quotas to set
        :return: resource id
        :rtype: int
        :raise TaskError: If task fails
        """
        datacenter = self.orchestrator["config"]["datacenter"]
        parent_folder = str(site.get_physical_resource_from_container(self.cid, VsphereFolder.objdef).oid)
        folder_id = self.create_folder(datacenter, parent_folder)
        section_id = self.create_section()
        return [folder_id, section_id]

    def create_folder(self, datacenter, folder):
        """Create vsphere folder.

        :parma datacenter: parent datacenter id
        :param folder: parent folder id
        :return: resource oid
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        # create folder
        name = "%s-%s-folder" % (self.resource.name, self.cid)
        prepared_task = self.create_resource(
            VsphereFolder,
            name=name,
            desc=self.resource.desc,
            active=False,
            attribute={},
            parent=None,
            tags="",
            folder_type="vm",
            datacenter=datacenter,
            folder=folder,
        )
        folder = self.add_link(prepared_task)
        self.run_sync_task(prepared_task, msg="stop folder creation")
        return folder.oid

    def create_security_group(self, parent):
        """Create vsphere security group.

        :param parent: parent
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        # create folder
        name = "%s-%s-sg" % (self.resource.name, self.cid)
        prepared_task = self.create_resource(
            NsxSecurityGroup,
            name=name,
            desc=self.resource.desc,
            active=False,
            attribute={},
            parent=None,
            tags="",
        )
        sg = self.add_link(prepared_task)
        self.run_sync_task(prepared_task, msg="stop security group creation")

        return sg.oid

    def create_section(self):
        """Create vsphere section.

        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        name = "%s-%s-section" % (self.resource.name, self.cid)

        # get nsx dfw reference
        dfw = self.container.get_nsx_dfw()
        self.progress("Get nsx dfw %s" % dfw)

        # check section already exists
        if dfw.exist_layer3_section(name=name) is True:
            raise TaskError("Nsx dfw section %s already exists" % name)

        # create dfw section
        data = {"name": name, "action": "allow", "logged": "true", "sync": True}
        prepared_task, code = dfw.create_section(data)
        section_id = self.run_sync_task(prepared_task, msg="stop nsx dfw section creation")

        # create dfw section custom resource
        objid = "%s//%s" % (self.container.objid, id_gen())
        attribs = {
            "id": section_id,
            "type": "vsphere",
            "sub_type": NsxDfwSection.objdef,
        }
        resource_model = self.container.add_resource(
            objid=objid,
            name=name,
            resource_class=CustomResource,
            ext_id=section_id,
            active=True,
            desc=self.resource.desc,
            attrib=attribs,
            parent=None,
            tags=["vsphere"],
        )
        resource_id = resource_model.id
        self.container.update_resource_state(resource_id, 2)
        self.container.activate_resource(resource_id)
        self.progress("Create nsx dfw section resource: %s" % resource_id)

        # set up resource link
        self.add_link(prepared_task={"uuid": resource_id})

        return resource_id

    def create_network(
        self,
        network_type,
        vlan,
        external,
        private,
        physical_network=None,
        public_network=None,
    ):
        """Create vsphere network.

        :param network_type: network type like flat, vlan, vxlan
        :param vlan: network vlan. Use with flat and vlan type
        :param external: True if network is used as external
        :param private: True if network is private
        :param physical_network: [optional] dict like {'<orchestrator_tag>':{'name':<cluster name>, 'dvs':..}}
        :param public_network: None
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-network" % (self.resource.name, self.cid)

            # create normal dvp
            if network_type in ["flat", "vlan"]:
                for cluster_tag, cluster in physical_network.items():
                    config = {
                        "name": "%s.%s" % (name, cluster_tag),
                        "physical_network": cluster.get("dvs"),
                        "network_type": "vlan",
                        "segmentation_id": vlan,
                        "numports": 24,
                    }
                    prepared_task = self.create_resource(VsphereDvpg, **config)
                    self.add_link(prepared_task)
                    self.run_sync_task(prepared_task, msg="stop dvpg creation")

            # create logical switch
            elif network_type == "vxlan":
                config = {
                    "transport_zone": "vdnscope-1",
                    "name": name,
                    "desc": name,
                    "tenant": "private",
                    "guest_allowed": True,
                }
                prepared_task = self.create_resource(NsxLogicalSwitch, **config)
                net = self.add_link(prepared_task)
                self.run_sync_task(prepared_task, msg="stop logical switch creation")
                return net.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(str(ex))

    # def append_network(self, network_type, net_id):
    #     """Append vsphere network.
    #
    #     :param network_type: network type like flat, vlan, vxlan
    #     :param net_id: dvpg id
    #     :return: resource id
    #     :raise TaskError: If task fails
    #     :raise ApiManagerError: :class:`ApiManagerError`
    #     """
    #     try:
    #         # create normal dvp
    #         if network_type in ['flat', 'vlan']:
    #             # get vsphere networks
    #             network = self.get_resource(net_id)
    #             network_id = network.oid
    #
    #             # uri = '/v1.0/nrs/vsphere/network/dvpgs/%s' % net_id
    #             # network = task.invoke_api('resource', uri, 'GET', '').get('dvpg', {})
    #             # network_id = network['id']
    #
    #         # create logical switch
    #         elif network_type == 'vxlan':
    #             pass
    #             # # TODO: create logical switch and setup solution to connect with
    #             # #       private vsphere networks
    #             #
    #             # # create api data
    #             # conf = {
    #             #     'logicalswitch': {
    #             #         'container': cid,
    #             #         'trasport_zone': 'vdnscope-1',
    #             #         'name': name,
    #             #         'desc': name,
    #             #         # 'provider': 'virtual wire provider',
    #             #         'guest_allowed': 'true'
    #             #     }
    #             # }
    #             #
    #             # # create vsphere networks
    #             # uri = '/v1.0/nrs/vsphere/network/nsx_logical_switchs'
    #             # network_id = task.invoke_api('resource', uri, 'GET', json.dumps(conf))
    #
    #         # self.progress('Create network %s' % network_id)
    #         #
    #         # create link
    #         self.get_session(reopen=True)
    #         resource.add_link('%s.%s-link' % (resource.oid, network_id), 'relation', network_id, attributes={})
    #         self.progress('Link vsphere network %s' % network_id)
    #     except Exception as ex:
    #         self.logger.error(ex, exc_info=True)
    #         raise TaskError(ex)

    def create_subnet(
        self,
        cidr,
        gateway,
        routes,
        allocation_pools,
        enable_dhcp,
        dns_nameservers,
        overlap=False,
    ):
        """Create vsphere subnet using an ippool if it does not already exist.

        :param gateway: gateway ip
        :param cidr: subnet cidr
        :param routes: subnet routes [default=None]
        :param allocation_pools: pools of continous ip in the subnet.
            Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
        :param enable_dhcp: if True enable dhcp
        :param dns_nameservers: list of dns. default=['8.8.8.8', '8.8.8.4']
        :param overlap: if True permit subnet overlapping
        :return: entity instance
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        if enable_dhcp is False:
            self.progress("Dhcp is disabled for this subnet. Ippool will be not created")
            return None

        try:
            nsx_manager = self.container.get_nsx_manager()
            startip = allocation_pools[0]["start"]
            stopip = allocation_pools[0]["end"]

            # check ippool already exists
            if overlap is False:
                pools = nsx_manager.get_ippools(pool_range=(startip, stopip))
                if len(pools) > 0:
                    return pools[0]["objectId"]

            # create ippool
            name = "%s-ippool-%s" % (self.resource.name, id_gen())
            if len(dns_nameservers) == 2:
                dns1, dns2 = dns_nameservers
            else:
                dns1 = dns_nameservers[0]
                dns2 = None
            prefix = cidr.split("/")[1]
            ippool_id = nsx_manager.add_ippool(
                name,
                prefix=prefix,
                gateway=gateway,
                dnssuffix=None,
                dns1=dns1,
                dns2=dns2,
                startip=startip,
                stopip=stopip,
            )
            self.progress("Create ippool: %s" % ippool_id)

            return ippool_id
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex.value)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def delete_subnet(self, subnet_id):
        """Delete vsphere subnet.

        :param subnet_id: id of the subnet
        :return: entity instance
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        if subnet_id is None:
            self.progress("dhcp is disabled for this subnet. Ippool does not exist")
            return None

        try:
            nsx_manager = self.container.get_nsx_manager()

            pools = nsx_manager.get_ippools(pool_id=subnet_id)
            if len(pools) == 0:
                self.progress("vsphete ippool %s is not already present" % subnet_id)
                return None

            nsx_manager.del_ippool(subnet_id)
            self.progress("delete vsphere ippool %s" % subnet_id)

            return subnet_id
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex.value)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_rule(self, zone, source, destination, service):
        """Create vsphere rule.

        :param zone: availability zone
        :param source: source
        :param destination: destination
        :param service: service.
            Ex. {'port':'*', 'protocol':'*'} -> *:*
                {'port':'*', 'protocol':6} -> tcp:*
                {'port':80, 'protocol':6} -> tcp:80
                {'port':80, 'protocol':17} -> udp:80
                {'protocol':1, 'subprotocol':8} -> icmp:echo request
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-dfwrule" % (self.resource.name, self.cid)

            # get section id
            cress = zone.get_physical_resources(self.cid, CustomResource.objdef)
            section = [c for c in cress if c.attribs["sub_type"] == NsxDfwSection.objdef][0]
            section = section.ext_id

            policies = []

            # appliedto
            appliedto = {
                "name": "DISTRIBUTED_FIREWALL",
                "value": "DISTRIBUTED_FIREWALL",
                "type": "DISTRIBUTED_FIREWALL",
            }

            # sources
            sources = self.type_mapping(source["type"], source["value"])
            # destinations
            dests = self.type_mapping(destination["type"], destination["value"])

            # service
            port = service

            # sgrule1 -> sgrule1
            if source["type"] == destination["type"] and source["value"] == destination["value"]:
                appliedto = self.type_mapping(source["type"], source["value"])

                policies.append(self.create_nsx_rule(section, name + "-out", "out", sources, dests, port, appliedto))
                policies.append(self.create_nsx_rule(section, name + "-in", "in", sources, dests, port, appliedto))

            # cidr -> sgrule
            elif source["type"] == "Cidr" and destination["type"] in ["RuleGroup"]:
                policies.append(self.create_nsx_rule(section, name + "-in", "in", sources, dests, port, appliedto))

            # env -> cidr
            elif destination["type"] == "Cidr" and source["type"] in ["RuleGroup"]:
                policies.append(self.create_nsx_rule(section, name + "-out", "out", sources, dests, port, appliedto))

            # sgrule1 -> sgrule2
            # sgrule -> server
            # server -> sgrule
            # server -> server
            else:
                policies.append(self.create_nsx_rule(section, name + "-out", "out", sources, dests, port, appliedto))
                policies.append(self.create_nsx_rule(section, name + "-in", "in", sources, dests, port, appliedto))

            return policies
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_nsx_rule(self, section_id, name, direction, source, dest, service, appliedto, logged=True):
        """Create nsx rule

        :param section_id:
        :param name:
        :param direction:
        :param source:
        :param dest:
        :param service:
        :param appliedto:
        :param logged:
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        dfw = self.container.get_nsx_dfw()
        self.progress("Get nsx dfw %s" % dfw)

        # create rule params
        if service == "*":
            service = None
        rule = {
            # 'container': str(self.cid),
            "sectionid": None,
            "name": name,
            "action": "allow",
            "direction": direction,
            "sources": [source],
            "destinations": [dest],
            "services": [service],
            "appliedto": [appliedto],
            "logged": "true",
            "sync": True,
        }
        self.progress("Configure vsphere nsx rule: %s" % rule)

        # get section
        section = dfw.get_layer3_section(oid=section_id)
        rule["sectionid"] = section["id"]

        # create vsphere rule
        prepared_task, code = dfw.create_rule(rule)
        rule_id = self.run_sync_task(prepared_task, msg="top nsx dfw rule creation")

        # create custom resource
        objid = "%s//%s" % (self.container.objid, id_gen())
        name = "nsx_dfw_rule_%s" % rule_id
        desc = name
        attribs = {
            "section": rule["sectionid"],
            "id": rule_id,
            "type": "vsphere",
            "sub_type": NsxDfwRule.objdef,
        }
        resource_model = self.container.add_resource(
            objid=objid,
            name=name,
            resource_class=CustomResource,
            ext_id=rule_id,
            active=True,
            desc=desc,
            attrib=attribs,
            parent=None,
            tags=["vsphere"],
        )
        rule_resource_id = resource_model.id
        self.container.update_resource_state(rule_resource_id, 2)
        self.container.activate_resource(rule_resource_id)
        self.add_link({"uuid": rule_resource_id})
        self.progress("create rule resource: %s" % rule_resource_id)

        return rule_id

    def import_server(self, params):
        """Import vsphere server.

        :param params: configuration params
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            networks = params.get("networks")

            # get server
            server = self.get_resource(params.get("physical_server_id"))

            # set up resource link
            self.add_link(resource_to_link=server)

            # get server networks
            # server_nets = server.detail()['details']['networks']
            server_nets = server.get_network_config()
            server_net_idx = {str(n["net_id"]): n["fixed_ips"] for n in server_nets}

            # assign ip to network conf
            for network_conf in networks:
                physical_net_id = network_conf.get("physical_net_id")
                fixed_ip = network_conf.get("fixed_ip", None)
                if fixed_ip is not None:
                    network_conf["fixed_ip"] = {"ip": server_net_idx[str(physical_net_id)]}

            params["networks"] = networks

            return server.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_server(self, folder, params):
        """Create vsphere server.

        :param folder: parent vsphere folder
        :param params: configuration params
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            flavor_id = params.get("flavor")
            image_id = params.get("image")
            security_groups = params.get("security_groups")
            admin_pass = params.get("admin_pass")
            networks = params.get("networks")
            zone_boot_volume = params.get("zone_boot_volume")
            zone_other_volumes = params.get("zone_other_volumes")
            metadata = params.get("metadata", {})
            user_data = params.get("user_data", "")
            personality = params.get("personality", [])
            host_group = params.get("host_group")
            if metadata is None:
                metadata = {}
            if personality is None:
                personality = []

            uuid = self.resource.uuid
            name = "%s-%s-server" % (self.resource.name, self.cid)
            orchestrator_type = "vsphere"

            # get cluster
            cluster = host_group.get("name", None)
            availability_zone = str(self.get_simple_resource(cluster).oid)

            # get dvs
            dvs = host_group.get("dvs", None)
            dvs = self.get_simple_resource(dvs)
            dvs_id = dvs.oid
            dvs_ext_id = dvs.ext_id
            self.logger.debug("create_server - dvs - dvs_id: %s - dvs_ext_id: %s" % (dvs_id, dvs_ext_id))

            server_conf = {
                "parent": folder.oid,
                "name": name,
                "desc": self.resource.desc,
                "flavorRef": None,
                "availability_zone": availability_zone,
                "adminPass": admin_pass,
                "networks": [],
                "security_groups": [],
                "user_data": user_data,
                "metadata": metadata,
                "personality": personality,
                "block_device_mapping_v2": [],
            }

            # set image
            image = self.get_simple_resource(image_id)
            remote_image = image.get_physical_resource_from_container(self.cid, VsphereServer.objdef)
            image_link = self.task.get_orm_link_among_resources(image_id, remote_image.oid)
            image_attribs = json.loads(image_link.attributes)
            server_conf["imageRef"] = str(remote_image.oid)

            # get admin password
            server_conf.get("metadata", {}).update({"template_pwd": image_attribs.get("template_pwd", "")})

            # set customization_spec_name
            server_conf["customization_spec_name"] = image_attribs.get(
                "customization_spec_name", "WS201x PRVCLOUD custom OS sysprep"
            )

            # set flavor
            flavor = self.get_simple_resource(flavor_id)
            remote_flavor = flavor.get_physical_resource_from_container(self.cid, VsphereFlavor.objdef)
            server_conf["flavorRef"] = str(remote_flavor.oid)

            # get security_groups
            for security_group_id in security_groups:
                env = self.get_simple_resource(security_group_id)
                objdef = orchestrator_mapping(orchestrator_type, 1)
                sg = env.get_physical_resource_from_container(self.cid, objdef)
                server_conf["security_groups"].append(str(sg.oid))

            # set networks
            vsphere_networks = {}
            noproxy = False
            for network_conf in networks:
                """
                {'vpc': 111889, 'id': 112135,
                'subnet': {'dns_nameservers': ['10.103.48.1', '10.103.48.2'], 'gateway': '192.168.200.1',
                           'vsphere_id': 'ipaddresspool-51', 'vsphere_id': '4f22c3ed-4237-4623-8c76-409ebfc4a820'},
                'fixed_ip': {'hostname': 'prv-inst-03b', 'dns_search': 'site03.nivolapiemonte.it'}}
                """
                self.logger.debug("create_server - network_conf: %s" % network_conf)
                uuid = network_conf.get("id")
                subnet = network_conf.get("subnet")

                # get ippool id from subnet config
                subnet_pool1 = subnet.get("allocation_pools_vs", None)
                subnet_pool2 = subnet.get("vsphere_id", None)
                subnet_pool = subnet_pool1 or subnet_pool2
                if subnet_pool1 is None and subnet_pool2 is None:
                    raise Exception("Subnet pool is not defined")
                fixed_ip = network_conf.get("fixed_ip", {})
                network = self.get_simple_resource(uuid)

                if isinstance(network, SiteNetwork):
                    objdef = orchestrator_mapping(orchestrator_type, 2)
                elif isinstance(network, PrivateNetwork):
                    objdef = orchestrator_mapping(orchestrator_type, 3)
                    noproxy = True

                # get all the remote nets (dvpgs)
                remote_net = None
                remote_nets = network.get_physical_resources(self.cid, objdef)
                self.logger.debug("create_server - objdef: %s - remote_nets: %s" % (objdef, remote_nets))

                for rn in remote_nets:
                    self.logger.debug("create_server - rn: %s" % rn)

                    if isinstance(rn, NsxLogicalSwitch):
                        rn.post_get()
                        rn_dvss = rn.get_parent_dvss()
                        self.logger.debug("create_server - rn_dvss: %s" % rn_dvss)
                        if dvs_ext_id in rn_dvss:
                            # get remote_dvpg associated to logical switch for distributed virtual switch dvs
                            remote_net = rn.get_associated_dvpg(dvs_ext_id)
                            vsphere_networks[uuid] = remote_net

                    elif isinstance(rn, VsphereDvpg):
                        rn.post_get()
                        rn_dvs = rn.get_parent_dvs()
                        self.logger.debug("create_server - rn_dvs: %s" % rn_dvs)
                        if rn_dvs.oid == dvs_id:
                            remote_net = rn
                            vsphere_networks[uuid] = rn
                if remote_net is None:
                    raise Exception("No suitable vsphere dvpgs found. Try syncing the dvpgs")

                config = {
                    "uuid": str(remote_net.oid),
                    "subnet_pool": subnet_pool,
                    "fixed_ip": fixed_ip,
                }
                server_conf["networks"].append(config)

            # configure boot volume
            volume = self.get_simple_resource(zone_boot_volume)
            remote_volume = volume.get_physical_resource_from_container(self.cid, VsphereVolume.objdef)
            conf = {
                "boot_index": 0,
                "source_type": "volume",
                "uuid": remote_volume.uuid,
                "destination_type": "volume",
            }
            server_conf["block_device_mapping_v2"].append(conf)

            # set no proxy
            server_conf.get("metadata", {}).update({"no_proxy": noproxy})

            # create remote server
            prepared_task = self.create_resource(VsphereServer, **server_conf)
            server = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop server creation")

            # get final server
            self.get_session(reopen=True)
            server = self.get_resource(server.oid)

            # get server networks
            server_net_idx = {str(n["net_id"]): n["fixed_ips"] for n in server.get_ports()}

            # assign dhcp ip to network conf
            for network_conf in networks:
                remote_net = vsphere_networks[uuid]
                network_conf["fixed_ip"] = {"ip": server_net_idx[str(remote_net.uuid)]}

            params["networks"] = networks

            # attach other volumes to server
            template_disks = server.get_template_disks()
            for zone_other_volume in zone_other_volumes:
                volume = self.get_simple_resource(zone_other_volume)
                from_template = volume.get_attribs("metadata.from_template", default=False)
                remote_volume = volume.get_physical_resource_from_container(self.cid, VsphereVolume.objdef)
                if from_template is False:
                    prepared_task, code = server.add_volume(volume=remote_volume.uuid, sync=True, pwd=admin_pass)
                    self.run_sync_task(
                        prepared_task,
                        msg="attach volume %s to server" % zone_other_volume,
                    )
                elif from_template is True:
                    # get a template disk with the same size of the remote volume
                    for template_disk in template_disks:
                        if template_disk["size"] == remote_volume.get_size():
                            # ext_id = template_disk['unit_number']
                            ext_id = template_disk["disk_object_id"]
                            remote_volume.update_internal(ext_id=ext_id)
                            server.add_link(
                                "%s-%s-volume-link" % (server.oid, remote_volume.oid),
                                "volume",
                                remote_volume.oid,
                                attributes={"boot": False},
                            )
                            template_disks.remove(template_disk)
                self.progress("attach volume %s to server" % zone_other_volume)

            return server.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_stack(self, folder, params, compute_stack_jobid):
        """Create vsphere stack.

        :param folder: parent vsphere folder
        :param params: configuration params
        :param compute_stack_jobid: compute stack jobid
        :return: None
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        return None

    def remote_action(self, remote_object, action, params):
        """Send action to a remote entity based to entity class

        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        if isinstance(remote_object, VsphereServer):
            return self.server_action(action, params)
        elif isinstance(remote_object, NsxIpSet):
            return self.ipset_action(action, params)

    def server_action(self, action, params):
        """Send action to vsphere server.

        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            # get physical server
            remote_server = self.resource.get_physical_resource_from_container(self.cid, VsphereServer.objdef)
            remote_server.post_get()
            action_func = getattr(remote_server, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for vsphere server" % action)

            # run custom check function
            check = getattr(self, "server_action_%s" % action, None)
            if check is not None:
                params = check(**params)
            params["sync"] = True

            prepared_task, code = action_func(**params)
            res = self.run_sync_task(
                prepared_task,
                msg="Run action %s over server %s" % (action, remote_server.uuid),
            )
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise TaskError(ex)

    def ipset_action(self, action, params):
        """Send action to vsphere ipset.

        :param action: ipset action
        :param params: configuration params
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            # get physical server
            remote_ipset = self.resource.get_physical_resource_from_container(self.cid, NsxIpSet.objdef)
            remote_ipset.post_get()
            action_func = getattr(remote_ipset, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for vsphere ipset" % action)

            # run custom check function
            check = getattr(self, "ipset_action_%s" % action, None)
            if check is not None:
                params = check(**params)
            params["sync"] = True

            prepared_task, code = action_func(**params)
            res = self.run_sync_task(
                prepared_task,
                msg="Run action %s over ipset %s" % (action, remote_ipset.uuid),
            )
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise TaskError(ex)

    def volume_action(self, action, params):
        """Send action to vsphere volume.

        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            self.get_session(reopen=True)

            # get physical server
            remote_volume = self.resource.get_physical_resource_from_container(self.cid, VsphereVolume.objdef)
            remote_volume.post_get()
            action_func = getattr(remote_volume, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for vsphere volume" % action)

            # run custom check function
            check = getattr(self, "volume_action_%s" % action, None)
            if check is not None:
                params = check(**params)
            params["sync"] = True

            prepared_task, code = action_func(**params)
            res = self.run_sync_task(
                prepared_task,
                msg="Run action %s over volume %s" % (action, remote_volume.uuid),
            )
            return res
        except Exception as ex:
            self.logger.error(ex, exc_info=False)
            raise TaskError(ex)

    def server_action_set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: zone flavor id
        :return: kvargs
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(flavor)
        remote_flavor = resource.get_physical_resource_from_container(self.cid, VsphereFlavor.objdef)
        return {"flavor": remote_flavor.oid}

    def server_action_add_volume(self, volume=None, *args, **kvargs):
        """Add volume check function

        :param volume: zone volume id
        :return: kvargs
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(self.cid, VsphereVolume.objdef)
        return {"volume": remote_volume.oid}

    def server_action_del_volume(self, volume=None, *args, **kvargs):
        """Del volume check function

        :param volume: zone volume id
        :return: kvargs
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(self.cid, VsphereVolume.objdef)
        return {"volume": remote_volume.oid}

    def server_action_extend_volume(self, volume=None, volume_size=None, *args, **kvargs):
        """Extend volume check function

        :param volume: zone volume id
        :return: kvargs
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_resource(volume)
        remote_volume = resource.get_physical_volume()
        return {"volume": remote_volume.oid, "volume_size": volume_size}

    def server_action_add_security_group(self, security_group=None, *args, **kvargs):
        """Add security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, NsxSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def server_action_del_security_group(self, security_group=None, *args, **kvargs):
        """Del security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, NsxSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def volume_action_set_flavor(self, flavor=None, *args, **kvargs):
        """Set flavor check function

        :param flavor: zone flavor id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(flavor)
        remote_flavor = resource.get_physical_resource_from_container(self.cid, VsphereVolumeType.objdef)
        return {"flavor": remote_flavor.oid}

    def ipset_action_add_security_group(self, security_group=None, *args, **kvargs):
        """Add security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, NsxSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def ipset_action_del_security_group(self, security_group=None, *args, **kvargs):
        """Del security group check function

        :param security_group: zone group id
        :return: kvargs
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource = self.get_simple_resource(security_group)
        remote_security_group = resource.get_physical_resource_from_container(self.cid, NsxSecurityGroup.objdef)
        return {"security_group": remote_security_group.oid}

    def create_ipset(self, fixed_ip, rule_groups):
        """Create vsphere nsx ipset.

        :param fixed_ip: fixed_ip network config
        :param rule_groups: rule group ids
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-ipset" % (self.resource.name, self.cid)

            # get security groups
            remote_sgs = []
            for rule_group_id in rule_groups:
                sg = self.get_simple_resource(rule_group_id)
                remote_sg = sg.get_physical_resource_from_container(self.cid, NsxSecurityGroup.objdef)
                remote_sgs.append(remote_sg)

            # get network configuration
            if fixed_ip is not None:
                ip = fixed_ip.get("ip")
            else:
                # TODO: get ip from dhcp setting
                ip = "127.0.0.1"

            # create nsx ipset
            data = {"name": name, "desc": name, "cidr": "%s/32" % ip}

            # create remote port
            prepared_task = self.create_resource(NsxIpSet, **data)
            ipset = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop ipset creation")

            # add ipset to security group
            # self.get_session(reopen=True)
            for remote_sg in remote_sgs:
                prepared_task, code = remote_sg.add_member({"member": ipset.oid, "sync": True})
                self.run_sync_task(
                    prepared_task,
                    msg="assign ipset %s to security group %s" % (ipset.uuid, remote_sg.uuid),
                )

            return ipset
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def create_flavor(self):
        """Create vsphere flavor.

        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-flavor" % (self.resource.name, self.cid)
            configs = self.resource.get_attribs("configs")

            # create vsphere flavor
            flavor_conf = {
                "name": name,
                "parent": None,
                "desc": self.resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            prepared_task = self.create_resource(VsphereFlavor, **flavor_conf)
            flavor = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="Create vsphere flavor %s" % flavor.uuid)

            return flavor.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_flavor(self, flavor_id):
        """Import vsphere flavor.

        :param flavor_id: flavor_id
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": flavor_id}, attrib={"reuse": True})
        return flavor_id

    def create_volumetype(self):
        """Create vsphere volumetype.

        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-volumetype" % (self.resource.name, self.cid)
            configs = self.resource.get_attribs("configs")

            # create vsphere volumetype
            volumetype_conf = {
                "name": name,
                "parent": None,
                "desc": self.resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            prepared_task = self.create_resource(VsphereVolumeType, **volumetype_conf)
            volumetype = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop volumetype creation")

            return volumetype.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_volumetype(self, volumetype_id):
        """Import vsphere volumetype.

        :param volumetype_id: volumetype_id
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        self.add_link(prepared_task={"uuid": volumetype_id}, attrib={"reuse": True})
        return volumetype_id

    def create_volume(self, compute_volume, folder, params):
        """Create vsphere volume.

        :param compute_volume: compute volume id
        :param folder: parent vsphere folder
        :param params: configuration params
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-volume" % (self.resource.name, self.cid)

            volume_type = params.get("flavor")
            volume = params.get("volume")
            snapshot = params.get("snapshot")
            image = params.get("image")

            # create vsphere volume
            volume_conf = {
                "name": name,
                "parent": folder.oid,
                "desc": self.resource.desc,
                "size": params.get("size"),
            }

            # set volume type
            volume_type = self.get_simple_resource(volume_type)
            remote_volume_type = volume_type.get_physical_resource_from_container(self.cid, VsphereVolumeType.objdef)
            volume_conf["volume_type"] = remote_volume_type.uuid

            # set image
            if image is not None:
                image = self.get_simple_resource(image)
                remote_image = image.get_physical_resource_from_container(self.cid, VsphereServer.objdef)
                volume_conf["imageRef"] = remote_image.uuid

            # set volume
            elif volume is not None:
                volume = self.get_simple_resource(volume)
                remote_volume = volume.get_physical_resource_from_container(self.cid, VsphereVolume.objdef)
                volume_conf["source_volid"] = remote_volume.uuid

            # create remote volume
            prepared_task = self.create_resource(VsphereVolume, **volume_conf)
            volume = self.add_link(prepared_task)
            self.run_sync_task(prepared_task, msg="stop volume creation")

            # update compute_volume attributes
            self.get_session(reopen=True)
            volume = self.get_resource(volume.uuid)
            compute_volume = self.get_simple_resource(compute_volume)
            volume_detail = volume.detail().get("details")

            attribs = compute_volume.get_attribs()
            dict_set(attribs, "configs.bootable", volume_detail.get("bootable"))
            dict_set(attribs, "configs.encrypted", volume_detail.get("encrypted"))
            compute_volume.update_internal(attribute=attribs)

            return volume.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def import_volume(self, volume_id):
        """Import vsphere volume.

        :param volume_id:  volume_id
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        resource_to_link = self.get_simple_resource(volume_id)
        oid = resource_to_link.oid
        self.resource.add_link("%s-%s-link" % (id_gen(), oid), "relation", oid, attributes={"reuse": False})
        self.progress("setup link to resource %s" % oid)
        return volume_id

    def create_image(self, image_id, template_pwd, guest_id, customization_spec_name):
        """Create vsphere image.

        :param image_id: image_id
        :param template_pwd: template admin password
        :param guest_id: vsphere guest_id
        :return: resource id
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        attrib = {
            "reuse": True,
            "template_pwd": template_pwd,
            "guest_id": guest_id,
            "customization_spec_name": customization_spec_name,
        }
        self.add_link(prepared_task={"uuid": image_id}, attrib=attrib)
        return image_id

    def create_gateway(self, role, uplink_ip_address, transport_ip_address, params):
        """Create vsphere edge.

        :param params: configuration params
        :return: list
        :rtype: resource list
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        name = "%s-%s-edge" % (self.resource.name, self.cid)
        self.logger.debug("create_gateway - name: %s" % name)

        host_group = params.get("host_group")
        admin_password = params.get("admin_pwd")
        dns = params.get("dns")
        dns_search = params.get("dns_search")
        size = params.get("flavor")
        uplink_network = params.get("uplink_network")
        uplink_subnet = params.get("uplink_subnet")
        transport_network = params.get("transport_network")
        volume_flavor = params.get("volume_flavor")

        # get folder
        zone = self.resource.get_parent()
        folder = zone.get_physical_resource_from_container(self.cid, VsphereFolder.objdef)

        # get datacenter
        datacenter = dict_get(self.orchestrator, "config.datacenter")

        # get cluster
        clusters = dict_get(self.orchestrator, "config.clusters")
        host_group_config = clusters.get(host_group, None)
        cluster = host_group_config.get("name", None)

        # get volume type
        volume_flavor = self.get_simple_resource(volume_flavor)
        volume_type = volume_flavor.get_physical_resource_from_container(self.cid, VsphereVolumeType.objdef)
        datastore = volume_type.get_best_datastore(5)

        config = {
            "name": name,
            "desc": name,
            "parent": folder.oid,
            "datacenter": datacenter,
            "cluster": cluster,
            "datastore": datastore.oid,
            "pwd": admin_password,
            "dns": dns,
            "domain": dns_search,
            "size": size,
        }

        # add uplink network
        self.logger.debug("create_gateway - uplink_network: %s" % uplink_network)
        self.logger.debug("create_gateway - uplink_subnet: %s" % uplink_subnet)
        if uplink_network is not None and uplink_subnet is not None:
            # get ippool id from subnet config
            subnet_pool1 = uplink_subnet.get("allocation_pools_vs", None)  # sembra non esserci più questo attributo
            subnet_pool2 = uplink_subnet.get("vsphere_id", None)  # aaa
            self.logger.debug("create_gateway - subnet_pool1: %s" % subnet_pool1)
            self.logger.debug("create_gateway - subnet_pool2: %s" % subnet_pool2)
            subnet_pool = subnet_pool1 or subnet_pool2

            uplink_network = self.get_simple_resource(uplink_network)
            uplink_dvpg = uplink_network.get_physical_resource_from_container(self.cid, VsphereDvpg.objdef)

            config.update(
                {
                    "uplink_dvpg": uplink_dvpg.oid,
                    "uplink_ipaddress": uplink_ip_address,
                    "uplink_subnet_pool": subnet_pool,
                }
            )

        self.logger.debug("create_gateway - config: %s" % config)
        prepared_task = self.create_resource(NsxEdge, **config)
        gateway = self.add_link(prepared_task)
        gateway_id = gateway.oid
        self.run_sync_task(prepared_task, msg="stop edge creation")

        # append transport network
        self.logger.debug("create_gateway - transport network - gateway_id: %s" % gateway_id)
        gateway: NsxEdge = self.get_resource(gateway_id)
        transport_network = self.get_simple_resource(transport_network)
        transport_dvpg = transport_network.get_physical_resource_from_container(self.cid, VsphereDvpg.objdef)
        gateway.add_vnic(1, "Internal", transport_dvpg.oid, transport_ip_address)
        self.progress("add transport network with ip: %s" % transport_ip_address)

        return gateway_id

    def remove_resource(self, childs):
        """Delete vsphere resources.

        :param childs: orchestrator childs
        :return: list
        :raise TaskError: If task fails
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            # get all child resources
            resources = []
            self.progress("Start removing vsphere childs: %s" % childs)
            for child in childs:
                definition = child.objdef
                child_id = child.id
                attribs = json.loads(child.attribute)
                link_attr = json.loads(child.link_attr)
                reuse = link_attr.get("reuse", False)

                # get child resource
                entity_class = import_class(child.objclass)
                child = entity_class(
                    self.controller,
                    oid=child.id,
                    objid=child.objid,
                    name=child.name,
                    active=child.active,
                    desc=child.desc,
                    model=child,
                )
                child.container = self.container

                if reuse is True:
                    continue

                try:
                    if definition in [
                        VsphereFolder.objdef,
                        NsxSecurityGroup.objdef,
                        VsphereDvpg.objdef,
                        VsphereServer.objdef,
                        NsxIpSet.objdef,
                        VsphereVolume.objdef,
                        VsphereVolumeType.objdef,
                        NsxLogicalSwitch.objdef,
                        NsxEdge.objdef,
                    ]:
                        prepared_task, code = child.expunge(sync=True)
                        self.run_sync_task(prepared_task, msg="remove child %s" % child.oid)

                    elif definition == CustomResource.objdef:
                        sub_type = attribs["sub_type"]

                        # delete rule
                        if sub_type == NsxDfwRule.objdef:
                            dfw = self.container.get_nsx_dfw()

                            # check rule exists
                            try:
                                rule = dfw.get_rule(attribs["section"], attribs["id"])
                            except:
                                rule = {}
                            if rule == {}:
                                self.progress("Rule %s:%s does not exist" % (attribs["section"], attribs["id"]))
                            else:
                                prepared_task, code = dfw.delete_rule(
                                    {
                                        "sectionid": attribs["section"],
                                        "ruleid": attribs["id"],
                                        "sync": True,
                                    }
                                )
                                self.run_sync_task(
                                    prepared_task,
                                    msg="remove dfw rule %s" % attribs["id"],
                                )

                            # delete resource
                            child.expunge(sync=True)

                        # delete dfw section
                        elif sub_type == NsxDfwSection.objdef:
                            dfw = self.container.get_nsx_dfw()
                            prepared_task, code = dfw.delete_section({"sectionid": attribs["id"], "sync": True})
                            self.run_sync_task(
                                prepared_task,
                                msg="remove dfw section %s" % attribs["id"],
                            )

                            # delete resource
                            child.expunge(sync=True)

                    resources.append(child_id)
                    self.progress("Delete child %s" % child_id)
                except:
                    self.logger.error("Can not delete vsphere child %s" % child_id, exc_info=True)
                    self.progress("Can not delete vsphere child %s" % child_id)
                    raise

            self.progress("Stop removing vsphere childs: %s" % childs)
            return resources
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)
