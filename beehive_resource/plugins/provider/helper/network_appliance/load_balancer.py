# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from ipaddress import ip_address, ip_network
from beecell.simple import dict_get
from beecell.types.type_ip import ip2cidr
from beecell.types.type_string import str2bool
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.gateway import ComputeGateway
from beehive_resource.plugins.provider.helper.network_appliance import AbstractProviderNetworkApplianceHelper
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc, SiteNetwork


class VsphereNsxEdgeFirewallRuleTemplate(object):
    templates = {
        "any2lb": {
            "action": "accept",
            "direction": "in",
            # "source": "any",
            "dest": "to-be-updated",
            # "appl": "ser:tcp+<port>+any",
        },
        "edge2backend": {
            "shared": {
                "action": "accept",
                "direction": "in",
                "source": "to-be-updated",
                "dest": "to-be-updated",
                # "appl": "ser:tcp+<port>+any",
            },
            "private": {
                "action": "accept",
                "direction": "in",
                "source": "to-be-updated",
                # "dest": "any",
                # "appl": "any",
            },
        },
        "interpod": {
            "action": "accept",
            "direction": "in",
            "source": "to-be-updated",
            # "dest": "any",
            # "appl": "any",
        },
    }


class ProviderVsphereHelper(AbstractProviderNetworkApplianceHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.edge = None

    def select_network_appliance(self, site_id, site_network_name, gateway_id, *args, **kvargs):
        """Select the network appliance where configuring the load balancer. In vSphere world, the network appliance
        corresponds with the nsx network edge.

        :param site_id: site id
        :param site_network_name: site network name
        :param gateway_id: internet gateway id
        :param kvargs.selection_criteria: criteria to select the network appliance where configuring the load balancer
        :param kvargs.deployment_env: project deployment environment
        :return: network edge object if exists, None otherwise
        """
        from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge

        if site_network_name is not None:
            # set tags
            l = [site_network_name]
            deployment_env = kvargs.get("deployment_env")
            if deployment_env is not None:
                l.append(deployment_env.lower())
            resourcetags = ",".join(f"edge_{item}" for item in l)

            # get candidate nsx edges
            edges: NsxEdge = self.container.get_nsx_edges(resourcetags=resourcetags)

            orchestrator = self.orchestrator.get("type")

            # get edge selection criteria
            selection_criteria = kvargs.get("selection_criteria")

            max_virtual_server = dict_get(
                selection_criteria,
                orchestrator + ".by_components.max_virtual_server",
                default=60,
            )
            cpu_max_usage = dict_get(
                selection_criteria,
                orchestrator + ".by_performance.max_cpu",
                default=80,
            )
            memory_max_usage = dict_get(
                selection_criteria,
                orchestrator + ".by_performance.max_memory",
                default=80,
            )
            disk_max_usage = dict_get(
                selection_criteria,
                orchestrator + ".by_performance.max_disk",
                default=80,
            )
            self.logger.debug("Nsx edge selection criteria: max_virtual_server: %d" % max_virtual_server)
            self.logger.debug(
                "Nsx edge selection criteria: cpu_max_usage: %d, memory_max_usage: %d, disk_max_usage: %d"
                % (cpu_max_usage, memory_max_usage, disk_max_usage)
            )

            # select edge (if exists) among candidates using selection criteria
            final_edge = None
            for edge in edges:
                # get virtual servers
                virt_servers = edge.get_lb_virt_servers()
                # apply selection criteria
                if virt_servers is not None and len(virt_servers) < max_virtual_server:
                    final_edge = edge
                    break
            if final_edge is None:
                raise ApiManagerError("No suitable edge found")
            return final_edge

        elif gateway_id is not None:
            # get gateway
            compute_gateway: ComputeGateway = self.controller.get_simple_resource(gateway_id)

            # get zone gateway
            from beehive_resource.plugins.provider.entity.gateway import Gateway

            gateways, tot = compute_gateway.get_linked_resources(
                link_type_filter="relation.%s" % site_id,
                objdef=Gateway.objdef,
                run_customize=False,
            )
            if tot == 0:
                raise ApiManagerError("Gateway not found in compute zone %s" % self.compute_zone.uuid)
            gateway = gateways[0]

            # get nsx edge
            edge: NsxEdge = gateway.get_nsx_edge()
            if edge is None:
                raise ApiManagerError("No suitable edge found")
            return edge

        else:
            raise ApiManagerError("No suitable edge found")

    def get_network_appliance(self, edge_id):
        """Get network appliance

        :param edge_id: network appliance id
        :return: network appliance instance
        """
        self.edge: NsxEdge = self.controller.get_simple_resource(edge_id)
        self.edge.set_container(self.controller.get_container(self.edge.container_id))
        self.edge.post_get()

    def __get_ippool(self, site_id, site_network_name=None, gateway_id=None):
        """Get ip pool ext id

        :param gateway_id: internet gateway id
        :param site_id: site id
        :return: ip pool ext id
        """
        site_network: SiteNetwork = None
        if gateway_id is not None:
            # get gateway
            compute_gateway: ComputeGateway = self.controller.get_simple_resource(gateway_id)

            # get linked vpc internet
            vpcs = compute_gateway.get_uplink_vpcs()
            if len(vpcs) != 1:
                raise ApiManagerError("Vpc not found or is not unique")
            vpc_internet = vpcs[0]

            # get site network
            site_network = vpc_internet.get_network_by_site(site_id)

        elif site_network_name is not None:
            # get site network
            site_network = self.controller.get_simple_resource(site_network_name)

        if site_network is None:
            raise Exception("Ip pool not found")

        # get network subnets
        subnets = site_network.get_attribs(key="configs.subnets", default=[])

        # get allocable subnet
        subnets = [subnet for subnet in subnets if subnet.get("allocable") is True]
        if len(subnets) != 1:
            raise ApiManagerError("Ip pool not found")
        subnet = subnets[0]

        # get ip pool
        ippool_id = subnet.get("vsphere_id")
        return ippool_id

    def reserve_ip_address(self, site_id, site_network_name, gateway_id, static_ip):
        """Allocate an IP address for the load balancer

        :param site_id: site id
        :param site_network_name: site network name
        :param gateway_id: internet gateway id
        :param static_ip: ip address specified by the user
        :return: dict with reserved ip address and other info
        """
        # get ip pool
        ippool_id = self.__get_ippool(site_id, site_network_name=site_network_name, gateway_id=gateway_id)

        # allocate ip address
        conn = self.container.conn
        allocated_ips = conn.network.nsx.ippool.allocations(ippool_id)
        if static_ip is not None and static_ip in allocated_ips:
            raise ApiManagerError("Ip address %s specified by user is already allocated" % static_ip)
        new_ip = conn.network.nsx.ippool.allocate(ippool_id, static_ip=static_ip)

        return {
            "ip": new_ip.get("ipAddress"),
            "is_static": True if static_ip is not None else False,
            "ip_pool": ippool_id,
            "gateway": new_ip.get("gateway"),
            "dns": new_ip.get("dnsServer1") + "," + new_ip.get("dnsServer2"),
            "dns_search": new_ip.get("dnsSuffix"),
            "prefix": new_ip.get("prefixLength"),
        }

    def release_ip_address(self, ip_pool, ip_addr):
        """Release IP address allocated for load balancer

        :return:
        """
        self.container.conn.network.nsx.ippool.release(ip_pool, ip_addr)
        self.logger.info("Release ip address %s from ip pool %s" % (ip_addr, ip_pool))

    @staticmethod
    def __any2lb_fw_rule(vs_ip, port):
        """Allow traffic from any source to the virtual server ip.

        :param vs_ip:
        :param port:
        :return:
        """
        rule = VsphereNsxEdgeFirewallRuleTemplate.templates.get("any2lb")
        rule.update({"dest": f"ip:{vs_ip}/32", "appl": f"ser:tcp+{port}+any"})
        return rule

    @staticmethod
    def __edge2backend_fw_rule(is_private, params):
        """Allow traffic from edge to the backends.

        I do this for all the networks; this way we do not have to update rules
        any time a new service was created.

        :param is_private: true or false according the context is private on not
        :param primary_ip:
        :param members:
        :param private_data:
        :return:
        """
        if is_private is False:
            members = params.get("members")
            if not members:
                return None
            primary_ip = params.get("primary_ip")
            port = params.get("port")
            rule = dict_get(VsphereNsxEdgeFirewallRuleTemplate.templates, "edge2backend.shared")
            subnet_mask = 32
            rule.update(
                {
                    "source": f"ip:{primary_ip}/{subnet_mask}",
                    "dest": ",".join(["ip:" + member.get("ip_addr") + "/32" for member in members]),
                    "appl": f"ser:tcp+{port}+any",
                }
            )
        else:
            cidr = params.get("private_master_subnet")
            rule = dict_get(VsphereNsxEdgeFirewallRuleTemplate.templates, "edge2backend.private")
            rule.update({"source": f"ip:{cidr}"})
        return rule

    @staticmethod
    def __interpod_fw_rule(cidr):
        """Allow traffic between vc1 and to2, and between openstack and vsphere

        :return:
        """
        rule = VsphereNsxEdgeFirewallRuleTemplate.templates.get("interpod")
        rule.update({"source": f"ip:{cidr}"})
        return rule

    def __create_fw_rules(self, *args, **kvargs):
        """Create all rules needed by load balancer."""
        fw_rules = {}
        secondary_ip = kvargs.get("secondary_ip")
        port = kvargs.get("port")

        any2lb_fw_rule = self.__any2lb_fw_rule(secondary_ip, port)
        if any2lb_fw_rule is not None:
            fw_rules["any2lb"] = any2lb_fw_rule

        is_private = kvargs.get("is_private")
        edge2backend_fw_rule = self.__edge2backend_fw_rule(is_private, kvargs)
        if edge2backend_fw_rule is not None:
            fw_rules["edge2backend"] = edge2backend_fw_rule

        if is_private:
            cidr = kvargs.get("interpod_subnet")
            interpod_fw_rule = self.__interpod_fw_rule(cidr)
            if interpod_fw_rule is not None:
                fw_rules["interpod"] = interpod_fw_rule

        for k, v in fw_rules.items():
            res = self.__fw_discover_rule(is_private, k, **v)
            if res is not None:
                fw_rules[k] = {"name": res.get("name"), "ext_id": res.get("id"), "is_shared": True}
            else:
                ext_id, name = self.__fw_create_rule(**v)
                fw_rules[k] = {"name": name, "ext_id": ext_id, "is_shared": False}

        return fw_rules

    def __fw_discover_rule(self, is_private, rule_alias, **rule_params):
        """Discover firewall rule if exists"""
        if rule_alias == "any2lb":
            return None
        if rule_alias == "edge2backend" and is_private is False:
            return None
        subnet = rule_params.get("source").split(":")[1]
        for item in self.current_fw_rules:
            rule_type = item.get("ruleType")
            action = item.get("action")
            direction = item.get("direction", "in")
            if not (rule_type == "user" and action == "accept" and direction == "in"):
                continue
            src_ips = dict_get(item, "source.ipAddress")
            if src_ips is None or src_ips == "any":
                continue
            if not isinstance(src_ips, list):
                src_ips = [src_ips]
            for src_ip in src_ips:
                cidr = ip2cidr(src_ip)
                if cidr in [subnet]:
                    self.logger.info("discovered %s fw rule: %s" % (rule_alias, item.get("id")))
                    return item
        self.logger.info("%s firewall rule not found" % rule_alias)
        return None

    def __fw_create_rule(self, **rule_params):
        """Create firewall rule

        :return:
        """
        action = rule_params.get("action")
        direction = rule_params.get("direction")
        source = rule_params.get("source")
        destination = rule_params.get("dest")
        application = rule_params.get("appl")

        name = ComputeGateway.get_firewall_rule_name(action, direction, source, destination, application)

        res = self.edge.add_firewall_rule(
            name,
            action=action,
            enabled=True,
            logged=False,
            direction=direction,
            source=source,
            dest=destination,
            appl=application,
        )
        ext_id = res.get("ext_id")
        if ext_id is None:
            raise ApiManagerError("Cannot create firewall rule %s on network edge %s" % (name, self.edge.name))
        self.logger.info("Create firewall rule %s on network edge %s" % (ext_id, self.edge.name))

        return ext_id, name

    def create_load_balancer(self, **params):
        """Create load balancer

        :param params: load balancer params
        :return: dict
        """
        # get network edge
        if self.edge is None:
            edge_id = dict_get(params, "network_appliance.uuid")
            self.get_network_appliance(edge_id)

        # init response
        resp = {}

        # create actions workflow
        # - add secondary ip address to uplink network interface
        secondary_ip = dict_get(params, "vip.ip")
        vnics = self.edge.get_vnics(vnic_type="uplink")
        uplink_vnic = None
        for vnic in vnics:
            primary_ip = dict_get(vnic, "addressGroups.addressGroup.primaryAddress")
            prefix = dict_get(vnic, "addressGroups.addressGroup.subnetPrefixLength")
            if ip_address(secondary_ip) in ip_network(f"{primary_ip}/{prefix}", False):
                uplink_vnic = vnic
                break
        if uplink_vnic is None:
            raise ApiManagerError("Uplink vnic not found")
        uv_idx = uplink_vnic.get("index")
        self.__vnic_update(uv_idx, secondary_ip)
        # update response
        resp["vnic"] = {
            "uplink": {
                "ext_id": uv_idx,
                "primary_ip": primary_ip,
                "secondary_ip": secondary_ip,
            }
        }

        # - create or select health monitor
        hm_params = params.get("health_monitor")
        # health monitor was not configured
        if hm_params is None:
            hm_ext_id = None
            hm_proto = None
            hm_predefined = None
        else:
            hm_predefined = hm_params.get("predefined")
            hm_proto = hm_params.get("protocol")
            if hm_predefined is False:
                hm_ext_id = self.__lb_create_monitor(hm_params)
                if hm_ext_id is None:
                    raise ApiManagerError("Cannot create custom lb health monitor on network edge %s" % self.edge.name)
            else:
                hm_ext_id = self.__lb_select_monitor(hm_params)
                if hm_ext_id is None:
                    raise ApiManagerError(
                        "Cannot find predefined lb health monitor on network edge %s" % self.edge.name
                    )
        params["target_group"].update({"monitor_id": hm_ext_id})
        # update response
        resp["health_monitor"] = {"ext_id": hm_ext_id, "predefined": hm_predefined, "protocol": hm_proto}

        # - create pool
        pool_params = params.get("target_group")
        pool_ext_id = self.__lb_create_pool(pool_params)
        if pool_ext_id is None:
            raise ApiManagerError("Cannot create lb pool on network edge %s" % self.edge.name)
        params.update({"pool_id": pool_ext_id})
        # update response
        resp["pool"] = {"ext_id": pool_ext_id}

        # - add members to pool
        members = pool_params.get("targets")
        self.__lb_manage_pool_members(pool_ext_id, members, action="add")

        # - create or select application profile
        ap_params = params.get("listener")
        ap_template = ap_params.get("traffic_type")
        ap_predefined = ap_params.get("predefined")
        if ap_predefined is False:
            ap_ext_id = self.__lb_create_app_profile(ap_params)
            if ap_ext_id is None:
                raise ApiManagerError("Cannot create custom lb application profile on network edge %s" % self.edge.name)
        else:
            ap_ext_id = self.__lb_select_app_profile(ap_params)
            if ap_ext_id is None:
                raise ApiManagerError(
                    "Cannot find predefined lb application profile on network edge %s" % self.edge.name
                )
        params.update({"app_profile_id": ap_ext_id})
        # update response
        resp["application_profile"] = {"ext_id": ap_ext_id, "predefined": ap_predefined, "template": ap_template}

        # - create virtual server
        vs_ext_id = self.__lb_create_virt_server(params)
        if vs_ext_id is None:
            raise ApiManagerError("Cannot create lb virtual server on network edge %s" % self.edge.name)
        # update response
        resp["virtual_server"] = {"ext_id": vs_ext_id}

        # - enable load balancer
        self.edge.enable_lb()
        self.logger.info("Enable lb on network edge %s" % self.edge.name)

        # - create firewall rules
        fw_rules_params = {
            "port": params.get("port"),
            "is_private": params.get("is_private"),
            "primary_ip": primary_ip,
            "secondary_ip": secondary_ip,
            "members": members,
            "private_master_subnet": params.get("private_master_subnet"),
            "interpod_subnet": params.get("interpod_subnet"),
        }
        self.current_fw_rules = self.edge.get_firewall_rules()
        resp["fw_rules"] = self.__create_fw_rules(**fw_rules_params)
        return resp

    def get_uplink_vnic(self, edge_id, site_network_name):
        """Get uplink vnic

        :param edge_id:
        :param site_network_name:
        :return:
        """
        # get nsx edge
        if self.edge is None:
            self.get_network_appliance(edge_id)

        # get uplink vnics
        vnics = self.edge.get_vnics(vnic_type="uplink")

        # select vnic
        if len(vnics) == 0:
            raise ApiManagerError("Uplink vnic not found")
        for vnic in vnics:
            portgroup_name = vnic.get("portgroupName", "")
            is_connected = vnic.get("isConnected")
            if str2bool(is_connected) is True and site_network_name.lower() in portgroup_name.lower():
                return vnic
        raise ApiManagerError("Uplink vnic not found")

    @staticmethod
    def get_vnic_primary_ip(vnic):
        """Get vnic primary ip address

        :param vnic: vnic details dict
        """
        primary_ip = dict_get(vnic, "addressGroups.addressGroup.primaryAddress")
        return primary_ip

    def __vnic_update(self, vnic_id, ip_addr):
        self.edge.update_vnic(vnic_id, secondary_ip=ip_addr, action="add")
        self.logger.info(
            "Add secondary ip address %s to vnic %s on network edge %s" % (ip_addr, vnic_id, self.edge.name)
        )
        return True

    def __lb_create_monitor(self, params):
        res = self.edge.add_lb_monitor(**params)
        ext_id = res.get("ext_id")
        self.logger.info("Create custom lb health monitor %s on network edge %s" % (ext_id, self.edge.name))
        return ext_id

    def __lb_select_monitor(self, params):
        orchestrator = self.orchestrator.get("type")
        monitor_name = dict_get(params, "ext_name." + orchestrator + ".name")
        res = self.edge.get_lb_monitors()
        ext_id = next(
            (item.get("monitorId") for item in res if item.get("name") == monitor_name),
            None,
        )
        self.logger.info("Select predefined lb health monitor %s on network edge %s" % (ext_id, self.edge.name))
        return ext_id

    def __lb_create_pool(self, params):
        res = self.edge.add_lb_pool(**params)
        ext_id = res.get("ext_id")
        self.logger.info("Create lb pool %s on network edge %s" % (ext_id, self.edge.name))
        return ext_id

    def __lb_manage_pool_members(self, pool_ext_id, members, action=None):
        res = None
        if action == "add":
            res = self.edge.add_lb_pool_members(pool_ext_id, members)
            self.logger.info("Add members %s to lb pool %s" % ([member.get("name") for member in members], pool_ext_id))
        elif action == "remove":
            res = self.edge.del_lb_pool_members(pool_ext_id, members)
            self.logger.info("Remove members %s from lb pool %s" % (members, pool_ext_id))
        return res

    def __lb_create_app_profile(self, params):
        res = self.edge.add_lb_app_profile(**params)
        ext_id = res.get("ext_id")
        self.logger.info("Create lb application profile %s on network edge %s" % (ext_id, self.edge.name))
        return ext_id

    def __lb_select_app_profile(self, params):
        orchestrator = self.orchestrator.get("type")
        profile_name = dict_get(params, "ext_name." + orchestrator + ".name")
        res = self.edge.get_lb_app_profiles()
        ext_id = next(
            (item.get("applicationProfileId") for item in res if item.get("name") == profile_name),
            None,
        )
        self.logger.info("Select predefined lb application profile %s on network edge %s" % (ext_id, self.edge.name))
        return ext_id

    def __lb_create_virt_server(self, params):
        res = self.edge.add_lb_virt_server(**params)
        ext_id = res.get("ext_id")
        self.logger.info("Create lb virtual server %s on network edge %s" % (ext_id, self.edge.name))
        return ext_id

    def __lb_check_for_disable(self):
        res = self.edge.get_lb_virt_servers()
        if res is None or len(res) > 0:
            return False
        return True

    def update_load_balancer(self, params, ext_refs):
        """Update load balancer

        :param params: load balancer params
        :param ext_refs: external ids of elements composing the load balancer
        :return:
        """
        # get network edge
        if self.edge is None:
            edge_id = dict_get(ext_refs, "network_appliance.uuid")
            self.get_network_appliance(edge_id)

        # update actions workflow
        # - update health monitor
        hm_params = params.get("health_monitor")
        if hm_params is not None:
            hm_predefined = hm_params.get("predefined")
            if hm_predefined is False:
                hm_ext_id = dict_get(ext_refs, "health_monitor.ext_id")
                try:
                    self.__lb_update_monitor(hm_ext_id, hm_params)
                except:
                    raise ApiManagerError("Cannot update custom lb health monitor on network edge %s" % self.edge.name)

        # - update pool
        pool_params = params.get("target_group")
        pool_ext_id = dict_get(ext_refs, "pool.ext_id")
        try:
            self.__lb_update_pool(pool_ext_id, pool_params)
        except:
            raise ApiManagerError("Cannot update lb pool on network edge %s" % self.edge.name)

        # - remove members from pool if any
        members_to_del = pool_params.get("targets_to_del")
        if len(members_to_del) > 0:
            self.__lb_manage_pool_members(pool_ext_id, members_to_del, action="remove")

        # - add members to pool if any
        members_to_add = pool_params.get("targets_to_add")
        if len(members_to_add) > 0:
            self.__lb_manage_pool_members(pool_ext_id, members_to_add, action="add")

        # - update application profile
        ap_params = params.get("listener")
        ap_predefined = ap_params.get("predefined")
        if ap_predefined is False:
            ap_ext_id = dict_get(ext_refs, "application_profile.ext_id")
            try:
                self.__lb_update_app_profile(ap_ext_id, ap_params)
            except:
                raise ApiManagerError("Cannot update custom lb application profile on network edge %s" % self.edge.name)

        # - update virtual server
        vs_ext_id = dict_get(ext_refs, "virtual_server.ext_id")
        try:
            self.__lb_update_virt_server(vs_ext_id, params)
        except:
            raise ApiManagerError("Cannot update lb virtual server on network edge %s" % self.edge.name)

        # - create, update or delete so-called edge2backend firewall rule
        fw_rule = dict_get(ext_refs, "fw_rules.edge2backend")
        if fw_rule is None:
            # create fw rule
            is_private = params.get("is_private")
            if not is_private:
                uv_primary_ip = dict_get(ext_refs, "vnic.uplink.primary_ip")
                port = params.get("port")
                fwr = dict_get(VsphereNsxEdgeFirewallRuleTemplate.templates, "edge2backend.shared")
                fwr.update(
                    {
                        "source": f"ip:{uv_primary_ip}/32",
                        "dest": ",".join(["ip:" + member.get("ip_addr") + "/32" for member in members_to_add]),
                        "appl": f"ser:tcp+{port}+any",
                    }
                )
            else:
                cidr = params.get("private_master_subnet")
                fwr = dict_get(VsphereNsxEdgeFirewallRuleTemplate.templates, "edge2backend.private")
                fwr.update({"source": f"ip:{cidr}"})
            ext_id, name = self.__fw_create_rule(**fwr)
            is_shared = False
        else:
            tot_balanced_targets = pool_params.get("tot_cur_balanced_target")
            ext_id = fw_rule.get("ext_id")
            name = fw_rule.get("ext_id")
            is_shared = fw_rule.get("is_shared")
            if len(members_to_del) == tot_balanced_targets:
                # do not delete fw rule because is shared
                if is_shared:
                    self.logger.info(
                        "Firewall rule %s might be shared with other nsx edge resources, therefore cannot "
                        "be deleted" % ext_id
                    )
                # delete fw rule
                else:
                    try:
                        self.edge.del_firewall_rule(ext_id)
                        self.logger.info("Delete firewall rule %s on network edge %s" % (ext_id, self.edge.name))
                        return {"fw_rules": {}}
                    except:
                        raise ApiManagerError(
                            "Cannot delete firewall rule %s on network edge %s" % (ext_id, self.edge.name)
                        )
            else:
                # update fw rule
                name = self.__fw_update_rule(ext_id, members_to_add, members_to_del)

        res = {"fw_rules": {"edge2backend": {"name": name, "ext_id": ext_id, "is_shared": is_shared}}}

        return res

    def __lb_update_monitor(self, ext_id, params):
        res = self.edge.update_lb_monitor(ext_id, **params)
        self.logger.info("Update custom lb health monitor %s on network edge %s" % (ext_id, self.edge.name))
        return True

    def __lb_update_pool(self, ext_id, params):
        res = self.edge.update_lb_pool(ext_id, **params)
        self.logger.info("Update lb pool %s on network edge %s" % (ext_id, self.edge.name))
        return True

    def __lb_update_app_profile(self, ext_id, params):
        res = self.edge.update_lb_app_profile(ext_id, **params)
        self.logger.info("Update lb application profile %s on network edge %s" % (ext_id, self.edge.name))
        return True

    def __lb_update_virt_server(self, ext_id, params):
        res = self.edge.update_lb_virt_server(ext_id, **params)
        self.logger.info("Update lb virtual server %s on network edge %s" % (ext_id, self.edge.name))
        return True

    def __fw_update_rule(self, ext_id, members_to_add, members_to_del):
        """Update firewall rule

        :param ext_id: firewall rule external id
        :param members_to_add: list of members to add
        :param members_to_del: list of members to remove
        :return:
        """
        # there's nothing to update
        if len(members_to_add) == 0 and len(members_to_del) == 0:
            return None
        res = self.edge.get_firewall_rule_by_id(ext_id)

        action = res.get("action")
        direction = res.get("direction")

        source = res.get("source")
        if source is None:
            upd_source = None
        else:
            src_ips = source.get("ipAddress", [])
            if not isinstance(src_ips, list):
                src_ips = [src_ips]
            for i in range(len(src_ips)):
                ip = src_ips[i]
                ip = ip.replace("/32", "")
                src_ips[i] = ip
            upd_source = ",".join(["ip:" + ip + "/32" for ip in src_ips])

        destination = res.get("destination")
        if destination is None:
            upd_destination = None
        else:
            dst_ips = destination.get("ipAddress", [])
            if not isinstance(dst_ips, list):
                dst_ips = [dst_ips]
            for i in range(len(dst_ips)):
                ip = dst_ips[i]
                ip = ip.replace("/32", "")
                dst_ips[i] = ip
            for item in members_to_add:
                dst_ips.append(item.get("ip_addr"))
            for item in members_to_del:
                dst_ips.remove(item.get("ip_addr"))
            upd_destination = ",".join(["ip:" + ip + "/32" for ip in dst_ips])

        application = res.get("application")
        if application is None:
            upd_application = None
        else:
            protocol = dict_get(application, "service.protocol")
            port = dict_get(application, "service.port")
            src_port = dict_get(application, "service.sourcePort")
            upd_application = f"ser:{protocol}+{port}+{src_port}"

        # update rule name
        upd_name = ComputeGateway.get_firewall_rule_name(
            action, direction, upd_source, upd_destination, upd_application
        )

        dest_add = None
        if len(members_to_add) > 0:
            dest_add = ",".join(["ip:" + item.get("ip_addr") + "/32" for item in members_to_add])
        dest_del = None
        if len(members_to_del) > 0:
            dest_del = ",".join(["ip:" + item.get("ip_addr") + "/32" for item in members_to_del])

        # update rule
        res = self.edge.update_firewall_rule(ext_id, name=upd_name, dest_add=dest_add, dest_del=dest_del)
        self.logger.info("Update firewall rule %s on network edge %s" % (ext_id, self.edge.name))
        return upd_name

    def delete_load_balancer(self, **params):
        """Delete load balancer

        :param params: load balancer params
        """
        # get network edge
        if self.edge is None:
            edge_id = dict_get(params, "network_appliance.uuid")
            self.get_network_appliance(edge_id)

        # delete actions workflow:
        # - delete virtual server
        vs_ext_id = dict_get(params, "virtual_server.ext_id")
        try:
            self.edge.del_lb_virt_server(vs_ext_id)
            self.logger.info("Delete lb virtual server %s on network edge %s" % (vs_ext_id, self.edge.name))
        except:
            raise ApiManagerError("Cannot delete lb virtual server %s on network edge %s" % (vs_ext_id, self.edge.name))

        # - delete secondary ip address from uplink network interface
        vnic_idx = dict_get(params, "vnic.uplink.ext_id")
        secondary_ip = dict_get(params, "vnic.uplink.secondary_ip")
        try:
            self.edge.update_vnic(vnic_idx, secondary_ip=secondary_ip, action="delete")
            self.logger.info(
                "Remove secondary ip address %s from vnic %s on network edge %s"
                % (secondary_ip, vnic_idx, self.edge.name)
            )
        except:
            raise ApiManagerError("Cannot update vnic %s on network edge %s" % (vnic_idx, self.edge.name))

        # - delete custom application profile only
        ap_predefined = dict_get(params, "application_profile.predefined")
        ap_ext_id = dict_get(params, "application_profile.ext_id")
        if ap_predefined is True:
            self.logger.info("Application profile %s is predefined and cannot be deleted" % ap_ext_id)
        else:
            try:
                self.edge.del_lb_app_profile(ap_ext_id)
                self.logger.info(
                    "Delete custom lb application profile %s on network edge %s" % (ap_ext_id, self.edge.name)
                )
            except:
                raise ApiManagerError(
                    "Cannot delete lb application profile %s on network edge %s" % (ap_ext_id, self.edge.name)
                )

        # - delete pool
        pool_ext_id = dict_get(params, "pool.ext_id")
        try:
            self.edge.del_lb_pool(pool_ext_id)
            self.logger.info("Delete lb pool %s on network edge %s" % (pool_ext_id, self.edge.name))
        except:
            raise ApiManagerError("Cannot delete lb pool %s on network edge %s" % (pool_ext_id, self.edge.name))

        # - delete custom health monitor only
        hm_params = params.get("health_monitor")
        if hm_params is not None:
            hm_predefined = hm_params.get("predefined")
            hm_ext_id = hm_params.get("ext_id")
            if hm_predefined is True:
                self.logger.info("Health monitor %s is predefined and cannot be deleted" % hm_ext_id)
            else:
                try:
                    if hm_ext_id is not None:
                        self.edge.del_lb_monitor(hm_ext_id)
                        self.logger.info(
                            "Delete custom lb health monitor %s on network edge %s" % (hm_ext_id, self.edge.name)
                        )
                except:
                    raise ApiManagerError(
                        "Cannot delete custom lb health monitor %s on network edge %s" % (hm_ext_id, self.edge.name)
                    )

        # - delete firewall rules
        fw_rules = dict_get(params, "fw_rules")
        for fw_rule in fw_rules.values():
            fwr_ext_id = fw_rule.get("ext_id")
            is_shared = fw_rule.get("is_shared")
            if is_shared:
                self.logger.info(
                    "Firewall rule %s might be shared with other resources of the nsx edge, therefore cannot be "
                    "deleted" % fwr_ext_id
                )
                continue
            try:
                self.edge.del_firewall_rule(fwr_ext_id)
                self.logger.info("Delete firewall rule %s on network edge %s" % (fwr_ext_id, self.edge.name))
            except:
                raise ApiManagerError(
                    "Cannot delete firewall root %s on network edge %s" % (fwr_ext_id, self.edge.name)
                )

        # - disable load balancer
        if self.__lb_check_for_disable() is True:
            self.edge.disable_lb()
            self.logger.info("Disable lb on network edge %s" % self.edge.name)

        return True

    def import_load_balancer(self, **params):
        """

        :param params: zone load balancer params
        :return:
        """
        lb_config = dict_get(params, "configs")
        site_network_name = lb_config.pop("site_network")
        site_id = lb_config.pop("site")
        network_appliance = lb_config.pop("network_appliance")
        uplink_vnic = dict_get(lb_config, "vnic.uplink")
        virtual_server = lb_config.pop("virtual_server")
        health_monitor = lb_config.pop("health_monitor", None)
        target_group = lb_config.pop("target_group")
        listener = lb_config.pop("listener")
        fw_rules = lb_config.pop("fw_rules")
        any2lb_fw_rule = fw_rules.get("any2lb")
        edge2backend_fw_rule = fw_rules.get("edge2backend")
        interpod_fw_rule = fw_rules.get("interpod")

        # get ip pool
        ippool_id = self.__get_ippool(site_id, site_network_name=site_network_name, gateway_id=None)

        res = {
            "network_appliance": {"uuid": network_appliance.get("uuid"), "ext_id": network_appliance.get("ext_id")},
            "ip_pool": ippool_id,
            "vnic": {
                "uplink": {
                    "ext_id": uplink_vnic.get("index"),
                    "primary_ip": uplink_vnic.get("primary_ip"),
                    "secondary_ip": virtual_server.get("ipAddress"),
                }
            },
            "pool": {"ext_id": target_group.get("poolId")},
            "application_profile": {
                "ext_id": listener.get("applicationProfileId"),
                "template": listener.get("template").lower(),
                "predefined": listener.get("predefined"),
            },
            "virtual_server": {"ext_id": virtual_server.get("virtualServerId")},
            "fw_rules": {
                "any2lb": {
                    "name": any2lb_fw_rule.get("name"),
                    "ext_id": any2lb_fw_rule.get("id"),
                    "is_shared": any2lb_fw_rule.get("is_shared"),
                }
            },
        }

        if edge2backend_fw_rule is not None:
            res["fw_rules"].update(
                {
                    "edge2backend": {
                        "name": edge2backend_fw_rule.get("name"),
                        "ext_id": edge2backend_fw_rule.get("id"),
                        "is_shared": edge2backend_fw_rule.get("is_shared"),
                    }
                }
            )
        if interpod_fw_rule is not None:
            res["fw_rules"].update(
                {
                    "interpod": {
                        "name": interpod_fw_rule.get("name"),
                        "ext_id": interpod_fw_rule.get("id"),
                        "is_shared": interpod_fw_rule.get("is_shared"),
                    }
                }
            )
        if health_monitor is not None:
            res.update(
                {
                    "health_monitor": {
                        "ext_id": health_monitor.get("monitorId"),
                        "protocol": health_monitor.get("type").upper(),
                        "predefined": health_monitor.get("predefined"),
                    }
                }
            )

        return res

    def start(self, edge_id):
        """Enable load balancer

        :param edge_id: nsx edge id
        :return:
        """
        if self.edge is None:
            self.get_network_appliance(edge_id)
        self.edge.enable_lb()
        return True

    def stop(self, edge_id):
        """Disable load balancer

        :param edge_id: nsx edge id
        :return:
        """
        if self.edge is None:
            self.get_network_appliance(edge_id)
        self.edge.disable_lb()
        return True

    def is_lb_enabled(self, edge_id):
        """Get load balancer status

        :param edge_id: network edge id
        :return: True (enabled) or False (disabled)
        """
        if self.edge is None:
            self.get_network_appliance(edge_id)
        return self.edge.is_lb_enabled()


class ProviderOPNsenseHelper(AbstractProviderNetworkApplianceHelper):
    def select_network_appliance(self, *args, **kvargs):
        """Select the network appliance where configuring the load balancer. In OPNsense world, the network appliance
        corresponds with ...

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def get_network_appliance(self, oid):
        """Get network appliance

        :param oid: network appliance id
        :return: network appliance instance
        """
        pass

    def reserve_ip_address(self, *args, **kvargs):
        """Allocate an IP address for the load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def create_load_balancer(self, **params):
        """Create load balancer

        :param params: load balancer params
        :return: dict
        """
        pass

    def update_load_balancer(self, **params):
        """Update load balancer

        :param params: load balancer params
        :return: dict
        """
        pass

    def delete_load_balancer(self, **params):
        """Delete load balancer

        :param params: load balancer params
        """
        pass

    def import_load_balancer(self, **params):
        """Import load balancer

        :param params:
        :return:
        """
        pass


class ProviderHAproxyHelper(AbstractProviderNetworkApplianceHelper):
    def select_network_appliance(self, *args, **kvargs):
        """Select the network appliance where configuring the load balancer. In HAProxy world, the network appliance
        corresponds with ...

        :return:
        """
        pass

    def get_network_appliance(self, oid):
        """Get network appliance

        :param oid: network appliance id
        :return: network appliance instance
        """
        pass

    def reserve_ip_address(self, *args, **kvargs):
        """Allocate an IP address for the load balancer

        :param args:
        :param kvargs:
        :return:
        """
        pass

    def create_load_balancer(self, **kvargs):
        """Create load balancer

        :param kvargs: load balancer params
        :return: dict
        """
        pass

    def update_load_balancer(self, **kvargs):
        """Update load balancer

        :param kvargs: load balancer params
        :return: dict
        """
        pass

    def delete_load_balancer(self, **params):
        """Delete load balancer

        :param params: load balancer params
        """
        pass

    def import_load_balancer(self, **params):
        """Import load balancer

        :param params:
        :return:
        """
        pass
