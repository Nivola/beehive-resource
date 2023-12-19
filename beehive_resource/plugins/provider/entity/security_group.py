# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

# from collections import Set
from re import match
from ipaddress import IPv4Address
from six import ensure_text
from beecell.network import InternetProtocol
from beecell.simple import truncate
from beecell.types.type_id import id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.vpc import Vpc
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource


class SecurityGroup(ComputeProviderResource):
    """SecurityGroup"""

    objdef = "Provider.ComputeZone.Vpc.SecurityGroup"
    objuri = "%s/security_groups/%s"
    objname = "security_group"
    objdesc = "Provider SecurityGroup"
    task_path = "beehive_resource.plugins.provider.task_v2.security_group.SecurityGroupTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.rules = []
        self.compute_zone = None
        self.instances = []

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info["rules"] = [z.info() for z in self.rules]
        info["zabbix_rules"] = self.is_zabbix_proxy_rule_configured()
        info["compute_zone"] = self.compute_zone
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        info["rules"] = [z.info() for z in self.rules]
        info["zabbix_rules"] = self.is_zabbix_proxy_rule_configured()
        info["instances"] = [i.info() for i in self.instances]
        info["compute_zone"] = self.compute_zone
        return info

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
        from beehive_resource.plugins.provider.entity.rule import ComputeRule
        from beehive_resource.plugins.provider.entity.zone import ComputeZone

        resource_ids = []
        for e in entities:
            resource_ids.append(e.oid)
        rules = controller.get_directed_linked_resources_internal(
            resources=resource_ids,
            link_type="rule",
            objdef=ComputeRule.objdef,
            run_customize=False,
        )
        compute_zones = controller.get_indirected_linked_resources_internal(
            resources=resource_ids,
            link_type="sg",
            objdef=ComputeZone.objdef,
            run_customize=False,
        )

        for e in entities:
            entity_rules = rules.get(e.oid, [])
            compute_zone = compute_zones.get(e.oid, [])[0]
            e.rules = entity_rules
            e.compute_zone = compute_zone.oid
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method. Extend this function to extend description
        info returned after query.

        :raise ApiManagerError:
        """
        rules, total = self.get_linked_resources(link_type="rule", size=-1)
        compute_zones, total = self.get_linked_resources(link_type="sg", size=-1, run_customize=False)
        instances, total = self.get_linked_resources(link_type="security-group", size=-1, run_customize=False)
        self.rules = rules
        self.instances = instances
        self.compute_zone = compute_zones[0].oid

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param kvargs.controller: resource controller instance
        :param kvargs.container: container instance
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
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
        :param kvargs.vpc: parent vpc id
        :param kvargs.rules: default rules list [optional]
        :param kvargs.name:
        :param kvargs.source: {'type':.., 'value':..},
        :param kvargs.destination: {'type':.., 'value':..},
        :param kvargs.service: {'port':53, 'protocol':6}
        :return: kvargs
        :raise ApiManagerError:
        """
        vpc_id = kvargs.get("parent")
        multi_avz = True

        # get vpc
        vpc = controller.get_simple_resource(vpc_id, entity_class=Vpc)

        # get compute zone
        compute_zone = controller.get_simple_resource(vpc.parent_id)
        compute_zone.set_container(container)

        # check quotas are not exceed
        # new_quotas = {
        #     'compute.security_groups': 1,
        # }
        # compute_zone.check_quotas(new_quotas)

        # get availability zones
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

        params = {
            "orchestrator_tag": kvargs.get("orchestrator_tag", "default"),
            "vpc_id": vpc.oid,
            "compute_zone_id": compute_zone.oid,
            "availability_zones": [z for z in availability_zones],
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            SecurityGroup.task_path + "create_resource_pre_step",
            SecurityGroup.task_path + "link_security_group_step",
        ]
        for availability_zone in params["availability_zones"]:
            step = {
                "step": SecurityGroup.task_path + "create_rule_group_step",
                "args": [availability_zone],
            }
            steps.append(step)
        steps.append(SecurityGroup.task_path + "create_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # check related instances
        instances, total = self.get_linked_resources(link_type="security-group", size=-1)
        if len(instances) > 0:
            raise ApiManagerError("Security group %s has instances associated" % self.oid)

        # check related rules
        if len(self.get_rules()) > 0:
            raise ApiManagerError("Security group %s has rules associated" % self.oid)

        # get environments
        rule_groups, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in rule_groups]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs

    def get_rules(self):
        """get security group associated rules"""
        from beehive_resource.plugins.provider.entity.rule import ComputeRule

        rules = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid],
            link_type="rule",
            objdef=ComputeRule.objdef,
            run_customize=False,
        )
        return rules.get(self.oid, [])

    def find_rule(self, source, dest, service):
        find_rule = None
        res = False
        for rule in self.rules:
            find = [False, False, False]
            rule_source = rule.get_source()
            rule_dest = rule.get_dest()
            rule_service = rule.get_service()
            if source.get("type") == rule_source.get("type") and source.get("value") == rule_source.get("value"):
                find[0] = True
            if dest.get("type") == rule_dest.get("type") and dest.get("value") == rule_dest.get("value"):
                find[1] = True
            if service.get("port") == rule_service.get("port") and service.get("protocol") == rule_service.get(
                "protocol"
            ):
                find[2] = True
            res = find[0] and find[1] and find[2]
            if res is True:
                find_rule = rule
                self.logger.debug("find rule source=%s, dest=%s, service=%s : %s" % (source, dest, service, res))
                break
        return res, find_rule

    def create_rule(self, source, dest, service, sync=None):
        from .rule import ComputeRule

        name = "%s-rule-%s" % (self.name, id_gen())
        data = {
            "name": name,
            "desc": name,
            "has_quotas": False,
            "parent": self.get_parent().get_parent().oid,
            "reserved": True,
            "source": source,
            "destination": dest,
            "service": service,
        }
        if sync is not None:
            data["sync"] = sync
        res = self.container.resource_factory(ComputeRule, **data)
        self.logger.debug2("create rule source=%s, dest=%s, service=%s : %s" % (source, dest, service, res))
        return res

    def is_zabbix_proxy_rule_configured(self):
        """check if zabbix proxy is configured for the specific availability zone"""
        # get vpc
        vpc = self.get_parent()
        networks = vpc.get_networks().get(vpc.oid, [])
        dest = {"type": "SecurityGroup", "value": self.uuid}
        res = {}
        for network in networks:
            site_name = network.get_site().name
            res[site_name] = False
            try:
                zabbix_proxy = network.get_zabbix_proxy()
                if zabbix_proxy[1] is not None:
                    source = {"type": "Cidr", "value": "%s/32" % zabbix_proxy[0]}
                    service = {"port": "10050", "protocol": "6"}
                    find, find_rule = self.find_rule(source, dest, service)
                    res[site_name] = find
            except:
                pass

        self.logger.debug("check zabbix proxy rules are present: %s" % res)
        return res

    def create_zabbix_proxy_rule(self, site_name):
        """create rule for enable access from zabbix proxy

        :param site_name: site nome
        :return: {'task_id': ...}
        """
        # get vpc
        vpc = self.get_parent()
        networks = vpc.get_networks().get(vpc.oid, [])
        dest = {"type": "SecurityGroup", "value": self.uuid}
        res = {}
        networks = [n for n in networks if n.get_site().name == site_name]
        if len(networks) == 1:
            try:
                zabbix_proxy = networks[0].get_zabbix_proxy()
                if zabbix_proxy[1] is not None:
                    valid_zabbix_proxy_conf = True
                else:
                    valid_zabbix_proxy_conf = False
            except:
                valid_zabbix_proxy_conf = False
        else:
            valid_zabbix_proxy_conf = False
        if valid_zabbix_proxy_conf is False:
            raise ApiManagerError(
                "no valid zabbix proxy configuration found for vpc % and availability zone %s" % (vpc.oid, site_name)
            )
        else:
            source = {"type": "Cidr", "value": "%s/32" % zabbix_proxy[0]}
            dest = {"type": "SecurityGroup", "value": self.uuid}
            service = {"port": "10050", "protocol": "6"}
            # search rule
            find, find_rule = self.find_rule(source, dest, service)
            # create rule
            if find is False:
                res = self.create_rule(source, dest, service)
                self.logger.debug("create zabbix proxy rule for availability zone %s" % site_name)
            else:
                raise ApiManagerError("zabbix proxy rule for availability zone %s already exists" % site_name)
        return res

    def delete_zabbix_proxy_rule(self, site_name):
        """delete rule that enable access from zabbix proxy

        :param site_name: site nome
        :return: {'task_id': ...}
        """
        # get vpc
        vpc = self.get_parent()
        networks = vpc.get_networks().get(vpc.oid, [])
        no_rule_found = False
        res = {}
        networks = [n for n in networks if n.get_site().name == site_name]
        if len(networks) == 1:
            try:
                zabbix_proxy = networks[0].get_zabbix_proxy()
                if zabbix_proxy[1] is not None:
                    source = {"type": "Cidr", "value": "%s/32" % zabbix_proxy[0]}
                    dest = {"type": "SecurityGroup", "value": self.uuid}
                    service = {"port": "10050", "protocol": "6"}
                    find, find_rule = self.find_rule(source, dest, service)
                    if find is True:
                        res = find_rule.expunge()
                    else:
                        no_rule_found = True
                    valid_zabbix_proxy_conf = True
                else:
                    valid_zabbix_proxy_conf = False
            except:
                valid_zabbix_proxy_conf = False
        else:
            valid_zabbix_proxy_conf = False
        if valid_zabbix_proxy_conf is False:
            raise ApiManagerError(
                "no valid zabbix proxy configuration found for vpc % and availability zone %s" % (vpc.oid, site_name)
            )
        if no_rule_found is True:
            raise ApiManagerError("zabbix proxy rule for availability zone %s does not exist" % site_name)
        self.logger.debug("delete zabbix proxy rule for availability zone %s" % site_name)
        return res

    def get_acls(self):
        """List security group acl

        :return: list of acl
        """
        self.verify_permisssions(action="use")

        # get default acl
        from beehive_resource.plugins.provider.entity.security_group_acl import (
            SecurityGroupAcl,
        )

        attribs = '{"is_default":True%'
        acls, tot = self.container.get_resources(
            entity_class=SecurityGroupAcl,
            objdef=SecurityGroupAcl.objdef,
            attribute=attribs,
        )

        # get specific acl
        other_acls, tot = self.get_linked_resources(link_type="acl")

        acls.extend(other_acls)

        self.logger.debug("Get security group %s acls: %s" % (self.uuid, truncate(acls)))
        return acls

    def has_acl(self, source, protocol, ports, where=None):
        """Check security group acl

        :param source: acl source. Can be *:*, Cidr:<>, Sg:<>
        :param protocol: acl protocol. Can be *:*, 7:*, 9:0 or tcp:*
        :param ports: comma separated list of ports, single port or ports interval
        :param where: acl where [optional]
        :return: True if security group available acls map required acl
        """
        proto_check = InternetProtocol()

        # check source
        rtype, rval = source.split(":")
        if rtype not in ["SecurityGroup", "Cidr", "*"]:
            raise ApiManagerError("Rule type %s is not supported" % rtype, code=400)

        # check value exist or is correct
        if rtype == "SecurityGroup":
            self.container.get_resource(rval, entity_class=SecurityGroup)
        elif rtype == "Cidr":
            try:
                ip, prefix = rval.split("/")
                prefix = int(prefix)
            except ValueError:
                raise ApiManagerError("Cidr is malformed. Use xxx.xxxx.xxx.xxx/xx syntax", code=400)
            IPv4Address(ensure_text(ip))
            if prefix < 0 or prefix > 32:
                raise ApiManagerError("Cidr is malformed. Network prefix must be >= 0 and < 33", code=400)

        # convert string protocol in numeric protocol
        protocol, subprotocol = protocol.split(":")

        if protocol != "*" and not match("^\d+$", protocol):
            protocol = str(proto_check.get_number_from_name(protocol))
        if subprotocol != "*" and not match("^\d+$", subprotocol):
            subprotocol = str(proto_check.get_number_from_name(subprotocol))

        requested_ports = ports
        if protocol in ["6", "17"]:
            # ports interval
            if match("[0-9]+-[0-9]+", str(ports)):
                min, max = ports.split("-")
                min = int(min)
                max = int(max)
                if min >= max:
                    raise ApiManagerError("Start port must be lower than end port", code=400)
                if min < 0 or min > 65535:
                    raise ApiManagerError("Start port can be a number between 0 and 65535", code=400)
                if max < 0 or max > 65535:
                    raise ApiManagerError("End port can be a number between 0 and 65535", code=400)
                requested_ports = {"from": min, "to": max}

            # single port
            elif match("[0-9]+", str(ports)):
                ports = int(ports)
                if ports < 0 or ports > 65535:
                    raise ApiManagerError("Port can be a number between 0 and 65535", code=400)
                requested_ports = ports

            # ports list
            elif ports.find(",") > 0:
                requested_ports = ports.split(",")
                for port in requested_ports:
                    try:
                        port = int(port)
                        if port < 0 or port > 65535:
                            raise ApiManagerError("Port can be a number between 0 and 65535", code=400)
                    except:
                        raise ApiManagerError("Port can be a number between 0 and 65535", code=400)

            # all ports
            elif ports != "*":
                raise ApiManagerError(
                    "Port can be * or a number or an interval between 0 and 65535 ",
                    code=400,
                )

        elif protocol == "1":
            icmp = [
                "0",
                "3",
                "4",
                "5",
                "8",
                "9",
                "10",
                "11",
                "12",
                "13",
                "1",
                "4",
                "41",
                "253",
                "254",
            ]
            if subprotocol not in icmp:
                raise ApiManagerError("Icmp type can be in %s" % icmp, code=400)

        elif protocol == "*":
            if ports != "*":
                raise ApiManagerError("Protocol * accept only port *", code=400)
        else:
            raise ApiManagerError(
                "Protocol %s is not supported. Use 6-tcp, 17-udp, 1-icmp, *-all" % protocol,
                code=400,
            )

        # create available acl_list set
        # acl_list = [
        #  '*|*-tcp',
        #  '*|*-tcp',
        #  '*|*-tcp',
        # ]
        # acl_list_with_ports = [
        #  '*|*-tcp', '80',
        #  '*|*-tcp', '4000-5000',
        #  '*|*-tcp', '28,67',
        # ]
        acl_list = []
        acl_list_with_ports = []
        for acl in self.get_acls():
            acl_item = acl.get_source() + "|" + acl.get_proto()
            acl_list.append(acl_item)

            for port in acl.get_ports().split(","):
                acl_list_with_ports.append([acl_item, port])

        self.logger.debug2("Available acl_list set: %s" % acl_list)
        self.logger.debug2("Available acl_list with ports: %s" % acl_list_with_ports)

        # requested acl set for source=*:*, proto=tcp:*, ports=80
        # [
        #  '*|*-tcp',  valid because permits the exact acl
        #  '*|*-*',    valid because permits all the protocols
        #  '*|*-*',    valid because permits all the protocols and ports
        # ]
        self.logger.debug2("Request acl source: %s" % source)
        self.logger.debug2("Request acl protocol: %s:%s" % (protocol, subprotocol))
        self.logger.debug2("Request acl ports: %s" % requested_ports)

        # source
        source_list = []
        source_list.append("*:*")
        if source != "*:*":
            source_list.append(source)

        # protocol
        protocol_list = []
        for item in source_list:
            protocol_list.append(item + "|" + "*:*")
        if protocol != "*:*":
            proto = "%s:%s" % (protocol, subprotocol)
            for item in source_list:
                protocol_list.append(item + "|" + proto)

        self.logger.debug2("Requested pre acl set: %s" % protocol_list)

        # check source and protocol
        acl_intersection = set(acl_list).intersection(set(protocol_list))
        self.logger.debug2("Available acl set: %s" % acl_intersection)

        resp = False
        if len(acl_intersection) > 0:
            # get acl_list with ports
            acl_list_with_ports = filter(lambda x: x[0] in acl_intersection, acl_list_with_ports)
            self.logger.debug2("Available acl set with ports: %s" % acl_list_with_ports)
            acl_ports_index = [item[1] for item in acl_list_with_ports]
            self.logger.debug2("Available acl ports: %s" % acl_ports_index)

            # ports is an interval 4001-4002
            if isinstance(requested_ports, dict) is True:
                for port in acl_ports_index:
                    from_to_ports = port.split("-")
                    if len(from_to_ports) == 2:
                        if requested_ports["from"] >= int(from_to_ports[0]) and requested_ports["to"] <= int(
                            from_to_ports[1]
                        ):
                            resp = True

            # ports is list of ports
            elif isinstance(requested_ports, list) is True:
                resp = len(set(acl_ports_index).intersection(set(requested_ports))) == len(requested_ports)

            # ports is a single port
            elif isinstance(requested_ports, int) is True:
                resp = str(requested_ports) in acl_ports_index

            # all ports
            elif requested_ports == "*":
                resp = str(requested_ports) in acl_ports_index

        self.logger.debug("Check security group %s acls map acl %s: %s" % (self.uuid, (source, protocol, ports), resp))
        return resp

    def add_acl(self, acl_id):
        """Add acl to security group

        :param acl_id: acl id
        :return: True
        """
        self.verify_permisssions(action="use")

        from beehive_resource.plugins.provider.entity.security_group_acl import (
            SecurityGroupAcl,
        )

        resource = self.container.get_resource(
            acl_id, entity_class=SecurityGroupAcl, details=False, run_customize=False
        )
        if self.is_linked(resource.oid):
            raise ApiManagerError("Acl %s is already linked to security group %s" % (resource.uuid, self.uuid))
        if resource.is_default() is True:
            raise ApiManagerError("Default acl %s can not be linked to security group %s" % (resource.uuid, self.uuid))

        self.add_link(
            name="%s-%s-acl" % (self.oid, acl_id),
            type="acl",
            end_resource=acl_id,
            attributes={},
        )

        self.logger.debug("Add security group %s acl %s" % (self.uuid, resource.uuid))
        return resource.uuid

    def del_acl(self, acl_id):
        """Delete acl from security group

        :param acl_id: acl id
        :return: True
        """
        self.verify_permisssions(action="use")

        from beehive_resource.plugins.provider.entity.security_group_acl import (
            SecurityGroupAcl,
        )

        resource = self.container.get_resource(
            acl_id, entity_class=SecurityGroupAcl, details=False, run_customize=False
        )

        self.del_link(acl_id)

        self.logger.debug("Delete security group %s acl %s" % (self.uuid, resource.uuid))
        return resource.uuid


class RuleGroup(AvailabilityZoneChildResource):
    """Availability Zone RuleGroup"""

    objdef = "Provider.Region.Site.AvailabilityZone.RuleGroup"
    objuri = "%s/rulegroups/%s"
    objname = "rulegroup"
    objdesc = "Provider Availability Zone RuleGroup"
    task_path = "beehive_resource.plugins.provider.task_v2.security_group.SecurityGroupTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
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
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.rules: default rules
        :return: kvargs
        :raise ApiManagerError:
        """
        # check necessary params
        zone_id = kvargs.get("parent")
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        # get zone
        zone = container.get_resource(zone_id)

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
        # kvargs['orchestrators'] = orchestrator_idx

        # create job workflow
        steps = []
        for item in orchestrator_idx.values():
            step = {
                "step": RuleGroup.task_path + "rulegroup_create_orchestrator_resource_step",
                "args": [item],
            }
            steps.append(step)

        kvargs["steps"] = AvailabilityZoneChildResource.group_create_step(steps)
        kvargs["sync"] = True
        return kvargs
