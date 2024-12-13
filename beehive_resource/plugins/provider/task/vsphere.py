# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import ujson as json
from celery.utils.log import get_task_logger
from beecell.simple import id_gen, import_class, dict_set
from beedrones.vsphere.client import VsphereError
from beehive.common.task.job import JobError, JobInvokeApiError
from beehive_resource.container import CustomResource
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.vpc import SiteNetwork, PrivateNetwork
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup
from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfwSection, NsxDfwRule
from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType

logger = get_task_logger(__name__)


class ProviderVsphere(object):
    @staticmethod
    def type_mapping(task, cid, mtype, mvalue):
        """Get vsphere type mapping

        :param task: task instance
        :param cid: remote orchestrator id
        """
        res = None
        try:
            if mtype == "Network":
                resource = task.get_resource(mvalue)
                net = resource.get_physical_resource_from_container(cid, VsphereDvpg.objdef)
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
                resource = task.get_resource(mvalue)
                sg = resource.get_physical_resource_from_container(cid, NsxSecurityGroup.objdef)
                res = {"type": "SecurityGroup", "value": sg.ext_id, "name": None}
        except Exception as ex:
            logger.error(ex, exc_info=True)
            return None
        logger.debug("Get vsphere type %s:%s mapping: %s" % (mtype, mvalue, res))
        return res

    @staticmethod
    def set_quotas(task, cid, resource, quotas):
        """Set vsphere folder quotas.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: tenant resoruce
        :param quotas: list of quotas to set
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        # get folder
        folder = task.get_resource(resource.parent_id)
        folder_quotas = []
        task.progress("Set folder %s quotas: %s" % (folder.uuid, folder_quotas))
        return True

    @staticmethod
    def create_zone_childs(task, orchestrator, resource, site, quotas=None):
        """Create availability zone childs.

        :param task: task reference
        :param orchestrator: orchestrator
        :param resource: parent resource
        :param site: site where is orchestrator
        :param quotas: list of quotas to set
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        rcid = orchestrator.get("id")

        datacenter = orchestrator["config"]["datacenter"]
        parent_folder = str(site.get_physical_resource_from_container(rcid, VsphereFolder.objdef).oid)
        folder_id = ProviderVsphere.create_folder(task, rcid, resource, datacenter, parent_folder)
        section_id = ProviderVsphere.create_section(task, rcid, resource)
        return [folder_id, section_id]

    @staticmethod
    def create_folder(task, cid, resource, datacenter, folder):
        """Create vsphere folder.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :parma datacenter: parent datacenter id
        :param folder: parent folder id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        # create folder
        name = "%s-%s-folder" % (resource.name, cid)
        container = task.get_container(cid)
        res = container.resource_factory(
            VsphereFolder,
            name=name,
            desc=resource.desc,
            active=False,
            attribute={},
            parent=None,
            tags="",
            folder_type="vm",
            datacenter=datacenter,
            folder=folder,
        )
        jobid = res[0]["jobid"]
        task.progress("Start folder creation with job: %s" % jobid)

        # set up resource link
        task.get_session(reopen=True)
        folder = task.get_resource(res[0]["uuid"])
        resource.add_link("%s-link" % folder.oid, "relation", folder.oid, attributes={})
        task.progress("Setup link to folder %s" % folder.oid)

        # wait job complete
        task.wait_for_job_complete(jobid)
        task.progress("Stop folder creation with job: %s" % jobid)

    @staticmethod
    def create_security_group(task, cid, resource, parent):
        """Create vsphere security group.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param parent: parent
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        # create folder
        name = "%s-%s-sg" % (resource.name, cid)
        container = task.get_container(cid)
        res = container.resource_factory(
            NsxSecurityGroup,
            name=name,
            desc=resource.desc,
            active=False,
            attribute={},
            parent=None,
            tags="",
        )
        # jobid = res[0]['jobid']
        # task.progress('Start folder creation with job: %s' % jobid)

        # set up resource link
        task.get_session(reopen=True)
        sg = task.get_resource(res[0]["uuid"])
        resource.add_link("%s-link" % sg.oid, "relation", sg.oid, attributes={})
        task.progress("Setup link to security group %s" % sg.oid)

        # wait job complete
        # task.wait_for_job_complete(jobid)
        # task.progress('Stop folder creation with job: %s' % jobid)

        return sg.oid

    @staticmethod
    def create_section(task, cid, resource):
        """Create vsphere section.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        name = "%s-%s-section" % (resource.name, cid)

        # get nsx dfw reference
        container = task.get_container(cid)
        dfw = container.get_nsx_dfw()
        task.progress("Get nsx dfw %s" % dfw)

        # check section already exists
        if dfw.exist_layer3_section(name=name) is True:
            raise JobError("Nsx dfw section %s already exists" % name)

        # create dfw section
        data = {"name": name, "action": "allow", "logged": "true"}
        res = dfw.create_section(data)
        jobid = res[0]["jobid"]
        task.progress("Start nsx dfw section creation with job: %s" % jobid)

        # wait job complete
        res = task.wait_for_job_complete(jobid)
        section_id = res.get("result")
        task.progress("Stop nsx dfw section creation with job: %s" % jobid)

        # create dfw section custom resource
        orchestrator = task.get_container(cid)
        objid = "%s//%s" % (orchestrator.objid, id_gen())
        attribs = {
            "id": section_id,
            "type": "vsphere",
            "sub_type": NsxDfwSection.objdef,
        }
        resource_model = orchestrator.add_resource(
            objid=objid,
            name=name,
            resource_class=CustomResource,
            ext_id=section_id,
            active=True,
            desc=resource.desc,
            attrib=attribs,
            parent=None,
            tags=["vsphere"],
        )
        resource_id = resource_model.id
        orchestrator.update_resource_state(resource_id, 2)
        orchestrator.activate_resource(resource_id)
        task.progress("Create nsx dfw section resource: %s" % resource_id)

        # set up resource link
        task.get_session(reopen=True)
        resource.add_link(
            "%s-%s-link" % (section_id, resource_id),
            "relation",
            resource_id,
            attributes={},
        )
        task.progress("Setup link to section %s" % section_id)

        return section_id

    @staticmethod
    def create_network(
        task,
        cid,
        resource,
        network_type,
        name,
        vlan,
        external,
        private,
        physical_network=None,
        public_network=None,
    ):
        """Create vsphere network.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param network_type: network type like flat, vlan, vxlan
        :param name: network name
        :param vlan: network vlan. Use with flat and vlan type
        :param external: True if network is used as external
        :param private: True if network is private
        :param physical_network: [optional] id of the openVswitch trunk
        :param public_network: [optional] id of the openVswitch public
        :return: resource id
        :raise JobError: :class:`JobError`
        """
        try:
            name = "%s-%s-network" % (resource.name, cid)

            # create normal dvp
            if network_type in ["flat", "vlan"]:
                container = task.get_container(cid)

                config = {
                    "name": name,
                    "physical_network": physical_network,
                    "network_type": "vlan",
                    "segmentation_id": vlan,
                    "numports": 24,
                }
                res = container.resource_factory(VsphereDvpg, **config)
                jobid = res[0]["jobid"]
                task.progress(msg="Start dvpg creation with job: %s" % jobid)
                task.release_session()

                # set up resource link
                task.get_session(reopen=True)
                net = task.get_resource(res[0]["uuid"])
                resource.add_link(
                    "%s.%s-link" % (resource.oid, net.oid),
                    "relation",
                    net.oid,
                    attributes={},
                )

                # wait job complete
                task.wait_for_job_complete(jobid)
                network_id = net.oid
                task.progress(msg="Create dvpg: %s" % name)

            # # create logical switch
            # elif network_type == 'vxlan':
            #     pass
            #     # TODO: create logical switch and setup solution to connect with
            #     #       private vsphere networks
            #
            #     # create api data
            #     conf = {
            #         'logicalswitch': {
            #             'container': cid,
            #             'trasport_zone': 'vdnscope-1',
            #             'name': name,
            #             'desc': name,
            #             #'provider': 'virtual wire provider',
            #             'guest_allowed': 'true'
            #         }
            #     }
            #
            #     # create vsphere networks
            #     uri = '/v1.0/nrs/vsphere/network/nsx_logical_switchs'
            #     network_id = task.invoke_api('resource', uri, 'POST', json.dumps(conf))

        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def append_network(task, resource, network_type, net_id):
        """Append vsphere network.

        :param task: task reference
        :param resource: parent resource
        :param network_type: network type like flat, vlan, vxlan
        :param net_id: dvpg id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # create normal dvp
            if network_type in ["flat", "vlan"]:
                # get vsphere networks
                network = task.get_resource(net_id)
                network_id = network.oid

                # uri = '/v1.0/nrs/vsphere/network/dvpgs/%s' % net_id
                # network = task.invoke_api('resource', uri, 'GET', '').get('dvpg', {})
                # network_id = network['id']

            # create logical switch
            elif network_type == "vxlan":
                pass
                # # TODO: create logical switch and setup solution to connect with
                # #       private vsphere networks
                #
                # # create api data
                # conf = {
                #     'logicalswitch': {
                #         'container': cid,
                #         'trasport_zone': 'vdnscope-1',
                #         'name': name,
                #         'desc': name,
                #         # 'provider': 'virtual wire provider',
                #         'guest_allowed': 'true'
                #     }
                # }
                #
                # # create vsphere networks
                # uri = '/v1.0/nrs/vsphere/network/nsx_logical_switchs'
                # network_id = task.invoke_api('resource', uri, 'GET', json.dumps(conf))

            # task.progress('Create network %s' % network_id)
            #
            # create link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, network_id),
                "relation",
                network_id,
                attributes={},
            )
            task.progress("Link vsphere network %s" % network_id)
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_subnet(
        task,
        cid,
        resource,
        cidr,
        gateway,
        routes,
        allocation_pools,
        enable_dhcp,
        dns_nameservers,
    ):
        """Create vsphere subnet using an ippool if it does not already exist.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent network
        :param gateway: gateway ip
        :param cidr: subnet cidr
        :param routes: subnet routes [defautl=None]
        :param allocation_pools: pools of continous ip in the subnet.
            Ex. [{'start':'194.116.110.200', 'end':'194.116.110.210'}]
        :param enable_dhcp: if True enable dhcp
        :param dns_nameservers: list of dns. default=['8.8.8.8', '8.8.8.4']
        :return: entity instance
        :raise JobError: :class:`JobError`
        """
        if enable_dhcp is False:
            task.progress("Dhcp is disabled for this subnet. Ippool will be not created")
            return None

        try:
            container = task.get_container(cid)
            nsx_manager = container.get_nsx_manager()
            startip = allocation_pools[0]["start"]
            stopip = allocation_pools[0]["end"]

            # check ippool already exists
            pools = nsx_manager.get_ippools(pool_range=(startip, stopip))
            if len(pools) > 0:
                return pools[0]["objectId"]

            # create ippool
            name = "%s-ippool-%s" % (resource.name, id_gen())
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
            task.progress("Create ippool: %s" % ippool_id)

            return ippool_id
        except VsphereError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def delete_subnet(task, cid, resource, subnet_id):
        """Delete vsphere subnet.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent network
        :param subnet_id: id of the subnet
        :return: entity instance
        :raise JobError: :class:`JobError`
        """
        if subnet_id is None:
            task.progress("Dhcp is disabled for this subnet. Ippool does not exist")
            return None

        try:
            container = task.get_container(cid)
            nsx_manager = container.get_nsx_manager()

            pools = nsx_manager.get_ippools(pool_id=subnet_id)
            if len(pools) == 0:
                task.progress("Vsphete ippool %s is not already present" % subnet_id)
                return None

            nsx_manager.del_ippool(subnet_id)
            task.progress("Delete vsphere ippool %s" % subnet_id)

            return subnet_id
        except VsphereError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_rule(task, cid, zone, resource, source, destination, service):
        """Create vsphere rule.

        :param task: task reference
        :param cid: orchestrator id
        :param zone: availability zone
        :param resource: parent resource
        :param source: source
        :param destination: destination
        :param service: service.
            Ex. {'port':'*', 'protocol':'*'} -> *:*
                {'port':'*', 'protocol':6} -> tcp:*
                {'port':80, 'protocol':6} -> tcp:80
                {'port':80, 'protocol':17} -> udp:80
                {'protocol':1, 'subprotocol':8} -> icmp:echo request
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            name = "%s-%s-dfwrule" % (resource.name, cid)

            # get section id
            cress = zone.get_physical_resources(cid, CustomResource.objdef)
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
            sources = ProviderVsphere.type_mapping(task, cid, source["type"], source["value"])
            # destinations
            dests = ProviderVsphere.type_mapping(task, cid, destination["type"], destination["value"])

            # service
            port = service

            # sgrule1 -> sgrule1
            if source["type"] == destination["type"] and source["value"] == destination["value"]:
                appliedto = ProviderVsphere.type_mapping(task, cid, source["type"], source["value"])

                policies.append(
                    ProviderVsphere.create_nsx_rule(
                        task,
                        resource,
                        cid,
                        section,
                        name + "-out",
                        "out",
                        sources,
                        dests,
                        port,
                        appliedto,
                    )
                )
                policies.append(
                    ProviderVsphere.create_nsx_rule(
                        task,
                        resource,
                        cid,
                        section,
                        name + "-in",
                        "in",
                        sources,
                        dests,
                        port,
                        appliedto,
                    )
                )

            # cidr -> sgrule
            elif source["type"] == "Cidr" and destination["type"] in ["RuleGroup"]:
                policies.append(
                    ProviderVsphere.create_nsx_rule(
                        task,
                        resource,
                        cid,
                        section,
                        name + "-in",
                        "in",
                        sources,
                        dests,
                        port,
                        appliedto,
                    )
                )

            # env -> cidr
            elif destination["type"] == "Cidr" and source["type"] in ["RuleGroup"]:
                policies.append(
                    ProviderVsphere.create_nsx_rule(
                        task,
                        resource,
                        cid,
                        section,
                        name + "-out",
                        "out",
                        sources,
                        dests,
                        port,
                        appliedto,
                    )
                )

            # sgrule1 -> sgrule2
            # sgrule -> server
            # server -> sgrule
            # server -> server
            else:
                policies.append(
                    ProviderVsphere.create_nsx_rule(
                        task,
                        resource,
                        cid,
                        section,
                        name + "-out",
                        "out",
                        sources,
                        dests,
                        port,
                        appliedto,
                    )
                )
                policies.append(
                    ProviderVsphere.create_nsx_rule(
                        task,
                        resource,
                        cid,
                        section,
                        name + "-in",
                        "in",
                        sources,
                        dests,
                        port,
                        appliedto,
                    )
                )

            return policies
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_nsx_rule(
        task,
        resource,
        cid,
        section,
        name,
        direction,
        source,
        dest,
        service,
        appliedto,
        logged=True,
    ):
        """Create nsx rule

        :param task: task reference
        :param resource: parent resource
        :param cid: orchestrator id
        """
        task.get_session(reopen=True)

        # get nsx dfw reference
        container = task.get_container(cid)
        dfw = container.get_nsx_dfw()
        task.progress("Get nsx dfw %s" % dfw)

        # create rule params
        if service == "*":
            service = None
        rule = {
            "container": str(cid),
            "sectionid": None,
            "name": name,
            "action": "allow",
            "direction": direction,
            "sources": [source],
            "destinations": [dest],
            "services": [service],
            "appliedto": [appliedto],
            "logged": "true",
        }
        task.progress("Configure vsphere nsx rule: %s" % rule)

        # get section
        section = dfw.get_layer3_section(oid=section)
        rule["sectionid"] = section["id"]

        # create vsphere rule
        res = dfw.create_rule(rule)
        jobid = res[0]["jobid"]
        task.progress("Start nsx dfw rule creation with job: %s" % jobid)

        # wait job complete
        res = task.wait_for_job_complete(jobid)
        rule_id = res.get("result")
        task.progress("Stop nsx dfw rule creation with job: %s" % jobid)

        # create custom resource
        orchestrator = task.get_container(cid)
        objid = "%s//%s" % (orchestrator.objid, id_gen())
        name = "nsx_dfw_rule_%s" % rule_id
        desc = name
        attribs = {
            "section": rule["sectionid"],
            "id": rule_id,
            "type": "vsphere",
            "sub_type": NsxDfwRule.objdef,
        }
        resource_model = orchestrator.add_resource(
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
        resource_id = resource_model.id
        orchestrator.update_resource_state(resource_id, 2)
        orchestrator.activate_resource(resource_id)
        task.release_session()
        task.progress("Create resource: %s" % resource_id)

        task.get_session(reopen=True)
        resource.add_link("dfw-rule-%s-link" % resource_id, "relation", resource_id, attributes={})
        task.release_session()
        task.progress("Setup link to resource to %s" % resource_id)

        return rule_id

    @staticmethod
    def import_server(task, orchestrator, resource, params):
        """Import vsphere server.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param params: configuration params
        :return: resource id
        :raiseJobError: If task fails
        """
        try:
            networks = params.get("networks")

            # set up resource link
            resource.add_link("%s-link" % resource.oid, "relation", resource.oid, attributes={})
            task.progress("Setup link to %s" % resource.oid)

            # get server
            server = task.get_resource_with_detail(params.get("physical_server_id"))

            # set up resource link
            resource.add_link("%s-link" % server.oid, "relation", server.oid, attributes={})
            task.progress("Setup link to %s" % server.oid)

            # get server networks
            server_nets = server.detail()["details"]["networks"]
            server_net_idx = {str(n["net_id"]): n["fixed_ips"] for n in server_nets}

            # assign ip to network conf
            for network_conf in networks:
                physical_net_id = network_conf.get("physical_net_id")
                fixed_ip = network_conf.get("fixed_ip", None)
                if fixed_ip is not None:
                    network_conf["fixed_ip"] = {"ip": server_net_idx[str(physical_net_id)]}

            params["networks"] = networks
            task.set_shared_data(params)
            task.progress("Update shared data with network: %s" % params["networks"])

            return server.oid
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_server(task, orchestrator, resource, folder, params):
        """Create vsphere server.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param folder: parent vsphere folder
        :param params: configuration params
        :return: resource id
        :raiseJobError: If task fails
        """
        try:
            flavor_id = params.get("flavor")
            image_id = params.get("image")
            security_groups = params.get("security_groups")
            admin_pass = params.get("admin_pass")
            networks = params.get("networks")
            # storage = params.get('storage')
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

            uuid = resource.uuid
            cid = orchestrator["id"]
            name = "%s-%s-server" % (resource.name, cid)
            orchestrator_type = "vsphere"

            # get cluster
            cluster = host_group.get("name", None)
            availability_zone = str(task.get_resource_with_no_detail(cluster).oid)

            # get dvs
            dvs = host_group.get("dvs", None)
            dvs = task.get_resource_with_no_detail(dvs).oid

            server_conf = {
                "parent": folder.oid,
                "name": name,
                "desc": resource.desc,
                # 'accessIPv4': None,
                # 'accessIPv6': None,
                "flavorRef": None,
                # 'imageRef': None,
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
            image = task.get_resource_with_no_detail(image_id)
            remote_image = image.get_physical_resource_from_container(cid, VsphereServer.objdef)
            image_link = task.get_orm_link_among_resources(image_id, remote_image.oid)
            image_attribs = json.loads(image_link.attributes)
            server_conf["imageRef"] = str(remote_image.oid)

            # get admin password
            server_conf.get("metadata", {}).update({"template_pwd": image_attribs.get("template_pwd", "")})

            # set flavor
            flavor = task.get_resource(flavor_id)
            remote_flavor = flavor.get_physical_resource_from_container(cid, VsphereFlavor.objdef)
            server_conf["flavorRef"] = str(remote_flavor.oid)

            # get security_groups
            for security_group_id in security_groups:
                env = task.get_resource_with_no_detail(security_group_id)
                objdef = orchestrator_mapping(orchestrator_type, 1)
                sg = env.get_physical_resource_from_container(cid, objdef)
                server_conf["security_groups"].append(str(sg.oid))

            # set networks
            vsphere_networks = {}
            for network_conf in networks:
                uuid = network_conf.get("id")
                subnet = network_conf.get("subnet")

                # get ippool id from subnet config
                subnet_pool1 = subnet.get("allocation_pools_vs", None)
                subnet_pool2 = subnet.get("vsphere_id", None)
                subnet_pool = subnet_pool1 or subnet_pool2
                if subnet_pool1 is None and subnet_pool2 is None:
                    raise Exception("Subnet pool is not defined")
                fixed_ip = network_conf.get("fixed_ip", {})
                network = task.get_resource_with_no_detail(uuid)

                if isinstance(network, SiteNetwork):
                    objdef = orchestrator_mapping(orchestrator_type, 2)
                elif isinstance(network, PrivateNetwork):
                    objdef = orchestrator_mapping(orchestrator_type, 3)

                # get all the remote nets (dvpgs)
                remote_net = None
                remote_nets = network.get_physical_resources(cid, objdef)
                for rn in remote_nets:
                    rn.post_get()
                    rn_dvs = rn.get_parent_dvs()
                    if rn_dvs.oid == dvs:
                        remote_net = rn
                        vsphere_networks[uuid] = rn

                if remote_net is None:
                    raise Exception("No suitable vsphere dvpgs found")

                config = {
                    "uuid": str(remote_net.oid),
                    "subnet_pool": subnet_pool,
                    "fixed_ip": fixed_ip,
                }
                server_conf["networks"].append(config)

            # configure boot volume
            volume = task.get_resource_with_no_detail(zone_boot_volume)
            remote_volume = volume.get_physical_resource_from_container(cid, VsphereVolume.objdef)
            conf = {
                "boot_index": 0,
                "source_type": "volume",
                "uuid": remote_volume.uuid,
                "destination_type": "volume",
            }
            server_conf["block_device_mapping_v2"].append(conf)

            # create remote server
            container = task.get_container(cid)
            res = container.resource_factory(VsphereServer, **server_conf)
            jobid = res[0]["jobid"]
            task.progress("Start vsphere server creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            server = task.get_resource_with_no_detail(res[0]["uuid"])
            resource.add_link("%s-link" % server.oid, "relation", server.oid, attributes={})
            task.progress("Setup vsphere server link to %s" % server.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create vsphere server %s" % server.uuid)

            # get final server
            task.get_session(reopen=True)
            server = task.get_resource_with_detail(res[0]["uuid"])

            # get server networks
            # server_nets = server.detail()['details']['networks']
            # server_net_idx = {str(n['net_id']): n['fixed_ips'] for n in server_nets}
            server_net_idx = {str(n["net_id"]): n["fixed_ips"] for n in server.get_ports()}

            # assign dhcp ip to network conf
            for network_conf in networks:
                remote_net = vsphere_networks[uuid]
                network_conf["fixed_ip"] = {"ip": server_net_idx[str(remote_net.uuid)]}

                # uuid = network_conf.get('id')
                # fixed_ip = network_conf.get('fixed_ip', None)
                # if fixed_ip is not None:
                #     # get remote network
                #     remote_net = vsphere_networks[uuid]
                #     network_conf['fixed_ip'] = {'ip': server_net_idx[str(remote_net.uuid)]}

            params["networks"] = networks
            task.set_shared_data(params)
            task.progress("Update shared data with network: %s" % params["networks"])

            # attach other volumes to server
            for zone_other_volume in zone_other_volumes:
                volume = task.get_resource_with_no_detail(zone_other_volume)
                remote_volume = volume.get_physical_resource_from_container(cid, VsphereVolume.objdef)
                server.add_volume(volume=remote_volume.uuid)
                task.progress("Attach volume %s to server" % zone_other_volume)

            return server.oid
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_stack(task, orchestrator, resource, folder, params, compute_stack_jobid):
        """Create vsphere server.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param resource: parent resource
        :param folder: parent vsphere folder
        :param params: configuration params
        :param compute_stack_jobid**: compute stack jobid
        :return: resource id
        :raiseJobError: If task fails
        """
        try:
            template_uri = params.get("template_uri")
            environment = params.get("environment")
            parameters = params.get("parameters")
            files = params.get("files")
            provider_id = resource.container.oid

            # uuid = resource.uuid
            cid = orchestrator["id"]
            name = "%s-%s-stack" % (resource.name, cid)
            # orchestrator_type = 'vsphere'

            stack_conf = {
                "container": str(cid),
                "folder": str(folder.oid),
                "name": name,
                "desc": resource.desc,
                "template_uri": template_uri,
                "environment": environment,
                "parameters": parameters,
                "files": files,
                "owner": "admin",
            }

            # create remote server
            uri = "/v1.0/nrs/vsphere/stacks"
            stack_id = task.invoke_api("resource", uri, "POST", {"stack": stack_conf}, link=resource.oid)
            task.progress("Create vsphere stack %s" % stack_id)

            # get stack resources list
            uri = "/v1.0/nrs/vsphere/stacks/%s/resources" % stack_id
            resources = task.invoke_api("resource", uri, "GET", "")["resources"]

            # get only servers
            servers = []
            for resource in resources:
                if resource.get("__meta__", {}).get("definition") == "Vsphere.Domain.Project.Server":
                    servers.append(resource)

            # get servers network configuration
            server_confs = []
            for server in servers:
                # get server detail
                uri = "/v1.0/nrs/vsphere/servers/%s" % server["id"]
                server_details = task.invoke_api("resource", uri, "GET", "")["server"]["details"]

                # get networks
                server_nets = server_details["networks"]
                """
                "name": null,
                "fixed_ips": [
                    {
                        "subnet_id": "318a7c82-94a2-4f60-871f-4ca86c7af8df",
                        "ip_address": "10.102.185.159"
                    }
                ],
                "port_state": "ACTIVE",
                "mac_addr": "fa:16:3e:8c:0b:20",
                "port_id": "6b5fb291-d025-497c-87d2-17c9af277fac",
                "net_id": "eeab4682-1844-4b90-b4ef-3de497115f02"
                """

                # get only the first network
                # TODO : verify if other network are important
                server_net = server_nets[0]

                # check network has a parent provider network
                # servre_net_id = task.get_resource(server_net['net_id'])
                provider_nets = task.get_linked_resources(
                    server_net["net_id"],
                    link_type="relation",
                    container_id=None,
                    objdef=None,
                )
                # provider_net = provider_nets[0]
                provider_vpc = task.get_linked_resources(
                    provider_nets[0].id,
                    link_type="relation.%",
                    container_id=None,
                    objdef=None,
                )

                # get security groups
                server_sgss = server_details["security_groups"]

                # check each security groups has a parent provider rule group
                provider_sgss = []
                for server_sgs in server_sgss:
                    rg = task.get_linked_resources(
                        server_sgs["id"],
                        link_type="relation",
                        container_id=None,
                        objdef=None,
                    )
                    if len(rg) > 0:
                        sg = task.get_linked_resources(
                            rg[0].id,
                            link_type="relation.%",
                            container_id=None,
                            objdef=None,
                        )

                        provider_sgss.append(sg[0].id)

                # create server config to use with twins only if exist a linked provider network
                if len(provider_nets) > 0 and len(provider_sgss) > 0:
                    # get subnet
                    fixed_ip = server_net["fixed_ips"][0]
                    uri = "/v1.0/nrs/vsphere/subnets/%s" % fixed_ip["subnet_id"]
                    server_subnet = task.invoke_api("resource", uri, "GET", "")["subnet"]["details"]

                    server_confs.append(
                        {
                            "vpc": provider_vpc[0].id,
                            # 'network': provider_net.id,
                            "subnet_cidr": server_subnet["cidr"],
                            "ip_address": {"ip": fixed_ip["ip_address"]},
                            "security_groups": provider_sgss,
                        }
                    )

            params["server_confs"] = server_confs
            task.set_shared_data(params)
            task.progress("Update shared data with server confs: %s" % params["server_confs"])

            # set shared data in parent compute stack job
            rparams = task.get_shared_data(job=compute_stack_jobid)
            rparams["server_confs"] = server_confs
            task.set_shared_data(rparams, job=compute_stack_jobid)
            task.progress(
                "Update compute stack job %s shared data with server confs: %s"
                % (compute_stack_jobid, rparams["server_confs"])
            )

            return stack_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def server_action(task, cid, resource, action, params):
        """Send action to vsphere server.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: availability zone instance
        :param action: server action
        :param params: configuration params
        :return: resource id
        :raise JobError:
        """
        try:
            task.get_session(reopen=True)

            # get physical server
            remote_server = resource.get_physical_resource_from_container(cid, VsphereServer.objdef)
            remote_server.post_get()
            action_func = getattr(remote_server, action, None)
            if action_func is None:
                raise Exception("Action %s is not supported for vsphere server" % action)

            # run custom check function
            check = getattr(ProviderVsphere, "server_action_%s" % action, None)
            if check is not None:
                params = check(task, cid, **params)

            res = action_func(**params)
            jobid = res[0]["jobid"]
            task.progress("Start run action %s over server %s with job: %s" % (action, remote_server.uuid, jobid))

            task.wait_for_job_complete(jobid)
            task.progress("Run action %s over server %s" % (action, remote_server.uuid))
            return res
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def server_action_set_flavor(task, cid, flavor=None):
        """Set flavor check function

        :param task: task reference
        :param cid: orchestrator id
        :param flavor: zone flavor id
        :return: kvargs
        """
        resource = task.get_resource(flavor)
        remote_flavor = resource.get_physical_resource_from_container(cid, VsphereFlavor.objdef)
        return {"flavor": remote_flavor.oid}

    @staticmethod
    def server_action_add_volume(task, cid, volume=None):
        """Add volume check function

        :param task: task reference
        :param cid: orchestrator id
        :param volume: zone volume id
        :return: kvargs
        """
        resource = task.get_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(cid, VsphereVolume.objdef)
        return {"volume": remote_volume.oid}

    @staticmethod
    def server_action_del_volume(task, cid, volume=None):
        """Del volume check function

        :param task: task reference
        :param cid: orchestrator id
        :param volume: zone volume id
        :return: kvargs
        """
        resource = task.get_resource(volume)
        remote_volume = resource.get_physical_resource_from_container(cid, VsphereVolume.objdef)
        return {"volume": remote_volume.oid}

    @staticmethod
    def create_ipset(task, cid, resource, fixed_ip, rule_groups):
        """Create vsphere nsx ipset.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param fixed_ip: fixed_ip network config
        :param rule_groups: rule group ids
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            name = "%s-%s-ipset" % (resource.name, cid)

            # get security groups
            remote_sgs = []
            for rule_group_id in rule_groups:
                sg = task.get_resource(rule_group_id)
                remote_sg = sg.get_physical_resource_from_container(cid, NsxSecurityGroup.objdef)
                remote_sgs.append(remote_sg.oid)

            # get network configuration
            if fixed_ip is not None:
                ip = fixed_ip.get("ip")
            else:
                # TODO: get ip from dhcp setting
                ip = "127.0.0.1"

            # create nsx ipset
            data = {"name": name, "desc": name, "cidr": "%s/32" % ip}

            # create remote port
            res = container.resource_factory(NsxIpSet, **data)
            jobid = res[0]["jobid"]
            task.progress("Start ipset creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            ipset = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % ipset.oid, "relation", ipset.oid, attributes={})
            task.progress("Setup link to %s" % ipset.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create vsphere nsx ipset %s" % ipset.uuid)

            # add ipset to security group
            task.get_session(reopen=True)
            remote_sg.add_member({"member": ipset.oid})
            jobid = res[0]["jobid"]
            task.progress("Start assign ipset to security group with job: %s" % jobid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Assign ipset %s to security group %s" % (ipset.uuid, remote_sg.uuid))

            return ipset
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_flavor(task, cid, resource):
        """Create vsphere flavor.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            name = "%s-%s-flavor" % (resource.name, cid)
            configs = resource.get_attribs("configs")

            # create vsphere flavor
            flavor_conf = {
                "name": name,
                "parent": None,
                "desc": resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            res = container.resource_factory(VsphereFlavor, **flavor_conf)
            jobid = res[0]["jobid"]
            task.progress("Start flavor creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            flavor = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % flavor.oid, "relation", flavor.oid, attributes={})
            task.progress("Setup link to %s" % flavor.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create vsphere flavor %s" % flavor.uuid)

            return flavor.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_flavor(task, cid, resource, flavor_id):
        """Import vsphere flavor.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param flavor_id: flavor_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, flavor_id),
                "relation",
                flavor_id,
                attributes={"reuse": True},
            )
            task.progress("Setup link to %s" % flavor_id)

            return flavor_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_volumetype(task, cid, resource):
        """Create vsphere volumetype.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            name = "%s-%s-volumetype" % (resource.name, cid)
            configs = resource.get_attribs("configs")

            # create vsphere volumetype
            volumetype_conf = {
                "name": name,
                "parent": None,
                "desc": resource.desc,
                "vcpus": configs.get("vcpus"),
                "ram": configs.get("ram"),
                "disk": configs.get("disk"),
            }

            # create remote port
            res = container.resource_factory(VsphereVolumeType, **volumetype_conf)
            jobid = res[0]["jobid"]
            task.progress("Start volumetype creation with job: %s" % jobid)

            # set up resource link
            task.get_session(reopen=True)
            volumetype = task.get_resource(res[0]["uuid"])
            resource.add_link("%s-link" % volumetype.oid, "relation", volumetype.oid, attributes={})
            task.progress("Setup link to %s" % volumetype.oid)

            # wait job complete
            task.get_session(reopen=True)
            task.wait_for_job_complete(jobid)
            task.progress("Create vsphere volumetype %s" % volumetype.uuid)

            return volumetype.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_volumetype(task, cid, resource, volumetype_id):
        """Import vsphere volumetype.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param volumetype_id: volumetype_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, volumetype_id),
                "relation",
                volumetype_id,
                attributes={"reuse": True},
            )
            task.progress("Setup link to %s" % volumetype_id)

            return volumetype_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_volume(task, orchestrator, compute_volume, resource, folder, params):
        """Create vsphere volume.

        :param task: task reference
        :param orchestrator: remote orchestrator
        :param compute_volume: compute volume id
        :param resource: parent resource
        :param folder: parent vsphere folder
        :param params: configuration params
        :return: resource id
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)

            cid = orchestrator["id"]
            name = "%s-%s-volume" % (resource.name, cid)
            container = task.get_container(cid)

            volume_type = params.get("flavor")
            volume = params.get("volume")
            snapshot = params.get("snapshot")
            image = params.get("image")

            # create vsphere volume
            volume_conf = {
                "name": name,
                "parent": folder.oid,
                "desc": resource.desc,
                "size": params.get("size"),
            }

            # set volume type
            volume_type = task.get_resource(volume_type, run_customize=False)
            remote_volume_type = volume_type.get_physical_resource_from_container(cid, VsphereVolumeType.objdef)
            volume_conf["volume_type"] = remote_volume_type.uuid

            # set image
            if image is not None:
                image = task.get_resource(image, run_customize=False)
                remote_image = image.get_physical_resource_from_container(cid, VsphereServer.objdef)
                volume_conf["imageRef"] = remote_image.uuid

            # set volume
            elif volume is not None:
                volume = task.get_resource(volume, run_customize=False)
                remote_volume = volume.get_physical_resource_from_container(cid, VsphereVolume.objdef)
                volume_conf["source_volid"] = remote_volume.uuid

            # create remote volume
            res = container.resource_factory(VsphereVolume, **volume_conf)
            task.progress("Start volume creation")

            # set up resource link
            task.get_session(reopen=True)
            volume = task.get_resource(res[0]["uuid"], run_customize=False)
            resource.add_link("%s-link" % volume.oid, "relation", volume.oid, attributes={})
            task.progress("Setup link to %s" % volume.oid)

            # update compute_volume attributes
            task.get_session(reopen=True)
            volume = task.get_resource(res[0]["uuid"], run_customize=True, details=True)
            compute_volume = task.get_resource(compute_volume, details=False)
            volume_detail = volume.detail().get("details")
            logger.warn(volume.detail())
            attribs = compute_volume.get_attribs()
            dict_set(attribs, "configs.bootable", volume_detail.get("bootable"))
            dict_set(attribs, "configs.encrypted", volume_detail.get("encrypted"))
            compute_volume.update_internal(attribute=attribs)

            return volume.oid
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def import_volume(task, resource, volume_id):
        """Import vsphere volume.

        :param task: task reference
        :param resource: parent resource
        :param  volume_id:  volume_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, volume_id),
                "relation",
                volume_id,
                attributes={"reuse": False},
            )
            task.progress("Setup link to %s" % volume_id)

            return volume_id
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def create_image(task, cid, resource, image_id, template_pwd, guest_id):
        """Create vsphere image.

        :param task: task reference
        :param cid: orchestrator id
        :param resource: parent resource
        :param image_id: image_id
        :param template_pwd: template admin password
        :param guest_id: vsphere guest_id
        :return: resource id
        :rtype: int
        :raise JobError: If task fails
        """
        try:
            name = "%s-%s-image" % (resource.name, cid)

            # set up resource link
            task.get_session(reopen=True)
            resource.add_link(
                "%s.%s-link" % (resource.oid, image_id),
                "relation",
                image_id,
                attributes={
                    "reuse": True,
                    "template_pwd": template_pwd,
                    "guest_id": guest_id,
                },
            )
            task.progress("Setup link to %s" % image_id)

            return image_id
        except JobInvokeApiError as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex.value)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)

    @staticmethod
    def remove_resource(task, provider, cid, childs):
        """Delete vsphere resources.

        :param task: task reference
        :param provider: provider container
        :param cid: remote orchestrator id
        :parma childs: orchestrator childs
        :return: list
        :rtype: resource list
        :raise JobError: If task fails
        """
        try:
            task.get_session(reopen=True)
            container = task.get_container(cid)

            # get all child resources
            resources = []
            task.progress("Start removing childs %s" % childs)
            for child in childs:
                definition = child.objdef
                child_id = child.id
                attribs = json.loads(child.attribute)
                link_attr = json.loads(child.link_attr)
                reuse = link_attr.get("reuse", False)

                # get child resource
                entity_class = import_class(child.objclass)
                child = entity_class(
                    container.controller,
                    oid=child.id,
                    objid=child.objid,
                    name=child.name,
                    active=child.active,
                    desc=child.desc,
                    model=child,
                )
                child.container = container

                if reuse is True:
                    continue

                try:
                    if definition in [
                        VsphereFolder.objdef,
                        NsxSecurityGroup.objdef,
                        VsphereDvpg.objdef,
                        VsphereServer.objdef,
                        NsxIpSet.objdef,
                    ]:
                        res = child.expunge()
                        jobid = res[0]["jobid"]
                        task.wait_for_job_complete(jobid)

                    elif definition in [VsphereVolume.objdef, VsphereVolumeType.objdef]:
                        child.expunge()
                    elif definition == CustomResource.objdef:
                        sub_type = attribs["sub_type"]
                        logger.warn(attribs)

                        # delete rule
                        if sub_type == NsxDfwRule.objdef:
                            dfw = container.get_nsx_dfw()

                            # check rule exists
                            rule = dfw.get_rule(attribs["section"], attribs["id"])
                            if rule == {}:
                                task.progress("Rule %s:%s does not exist" % (attribs["section"], attribs["id"]))
                            else:
                                dfw.delete_rule(
                                    {
                                        "sectionid": attribs["section"],
                                        "ruleid": attribs["id"],
                                    }
                                )

                            # delete resource
                            child.expunge()

                        # delete dfw section
                        elif sub_type == NsxDfwSection.objdef:
                            dfw = container.get_nsx_dfw()
                            dfw.delete_section({"sectionid": attribs["id"]})

                            # delete resource
                            child.expunge()

                    resources.append(child_id)
                    task.progress("Delete child %s" % child_id)
                except:
                    logger.error("Can not delete vsphere child %s" % child_id, exc_info=1)
                    task.progress("Can not delete vsphere child %s" % child_id)
                    raise

            task.progress("Stop removing childs %s" % childs)
            return resources
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise JobError(ex)
