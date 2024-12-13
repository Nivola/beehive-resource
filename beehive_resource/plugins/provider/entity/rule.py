# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from re import match
from ipaddress import IPv4Address
from six import ensure_text
from beecell.network import InternetProtocol
from beecell.simple import get_value
from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource


class ComputeRule(ComputeProviderResource):
    """Compute rule"""

    objdef = "Provider.ComputeZone.ComputeRule"
    objuri = "%s/rules/%s"
    objname = "rule"
    objdesc = "Provider ComputeRule"
    task_path = "beehive_resource.plugins.provider.task_v2.rule.RuleTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        return info

    # def check(self):
    #     """Check resource
    #
    #     :return: True if check is ok
    #     :raises ApiManagerError: raise :class:`.ApiManagerError`
    #     """
    #     zone_rules, total = self.get_linked_resources(link_type_filter='relation%')
    #     res = False
    #     for zone_rule in zone_rules:
    #         res = zone_rule.check()
    #     self.logger.debug('Check zone rule %s: %s' % (self.uuid, res))
    #     return res

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
        :param kvargs.compute_zone: compute zone id
        :param kvargs.source: source SecurityGroup, Cidr. Syntax {'type':.., 'value':..}
        :param kvargs.source.type: can be SecurityGroup or Cidr [default='*']
        :param kvargs.source.value: can be SecurityGroup uuid, Cidr or * [default='*']
        :param kvargs.destination: destination SecurityGroup, Cidr. Syntax {'type':.., 'value':..}
        :param kvargs.destination.type: can be SecurityGroup or Cidr [default='*']
        :param kvargs.destination.value: can be SecurityGroup uuid, Cidr or * [default='*']
        :param kvargs.service: service configuration
        :param kvargs.service.protocol: service protocol. Use number or name [default='*']
        :param kvargs.service.port: comma separated list of ports, single port or ports interval [optional]
        :param kvargs.service.subprotocol: use with icmp [optional]
        :param kvargs.reserved: Flag to use when rule must be reserved to admin management
        :return: (:py:class:`dict`)
        :raise ApiManagerError:

        Ex. service

            {'port':'*', 'protocol':'*'} -> *:*
            {'port':'*', 'protocol':6} -> tcp:*
            {'port':80, 'protocol':6} -> tcp:80
            {'port':80, 'protocol':17} -> udp:80
            {'protocol':1, 'subprotocol':8} -> icmp:echo request
        """
        proto_check = InternetProtocol()

        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        zone_id = kvargs.get("parent")
        reserved = kvargs.get("reserved")
        source = kvargs.get("source")
        destination = kvargs.get("destination")
        service = kvargs.get("service", {"port": "*", "protocol": "*"})
        rule_orchestrator_types = kvargs.get("rule_orchestrator_types")

        # get zone
        compute_zone = container.get_resource(zone_id)

        # check quotas are not exceed
        # new_quotas = {
        #     'compute.security_group_rules': 1,
        # }
        # compute_zone.check_quotas(new_quotas)

        # get availability zones
        multi_avz = True
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
        # avzones, total = compute_zone.get_linked_resources(link_type_filter='relation%')

        def check(source):
            rval = get_value(source, "value", None, exception=True)
            rtype = get_value(source, "type", None, exception=True)
            if rtype not in ["IPSet", "SecurityGroup", "Instance", "Cidr"]:
                raise ApiManagerError("Rule type %s is not supported" % rtype, code=400)

            # check value exist or is correct
            obj = None
            if rtype == "SecurityGroup":
                obj = container.get_simple_resource(rval, entity_class=SecurityGroup)
            elif rtype == "Instance":
                obj = container.get_simple_resource(rval, entity_class=ComputeInstance)
            elif rtype == "Cidr":
                try:
                    ip, prefix = rval.split("/")
                    prefix = int(prefix)
                except ValueError:
                    raise ApiManagerError("Cidr is malformed. Use xxx.xxxx.xxx.xxx/xx syntax", code=400)
                IPv4Address(ensure_text(ip))
                if prefix < 0 or prefix > 32:
                    raise ApiManagerError(
                        "Cidr is malformed. Network prefix must be >= 0 and < 33",
                        code=400,
                    )

            return obj

        # check source and destination are correct
        check(source)
        dest_entity = check(destination)

        # check service
        protocol = get_value(service, "protocol", None, exception=True)

        # convert string protocol in numeric protocol
        if protocol != "*" and not match("^\d+$", protocol):
            protocol = str(proto_check.get_number_from_name(protocol))
            service["protocol"] = protocol

        if protocol in ["6", "17"]:
            port = get_value(service, "port", None, exception=True)
            if match("[0-9]+-[0-9]+", str(port)):
                container.logger.debug("Port is a range")
                min, max = port.split("-")
                min = int(min)
                max = int(max)
                if min >= max:
                    raise ApiManagerError("Start port must be lower than end port", code=400)
                if min < 0 or min > 65535:
                    raise ApiManagerError("Start port can be a number between 0 and 65535", code=400)
                if max < 0 or max > 65535:
                    raise ApiManagerError("End port can be a number between 0 and 65535", code=400)
            elif match("[0-9]+", str(port)):
                container.logger.debug("Port is single")
                port = int(port)
                if port < 0 or port > 65535:
                    raise ApiManagerError("Port can be a number between 0 and 65535", code=400)
            elif port != "*":
                container.logger.debug("Port is all")
                raise ApiManagerError(
                    "Port can be * or a number or an interval between 0 and 65535 ",
                    code=400,
                )
            acl_protocol = "%s:*" % protocol
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
            subprotocol = get_value(service, "subprotocol", None, exception=False)
            service["subprotocol"] = "-1"
            controller.logger.warn(subprotocol)
            controller.logger.warn(type(subprotocol))
            if subprotocol == "-1":
                service["subprotocol"] = subprotocol
            elif subprotocol is not None:
                service["subprotocol"] = subprotocol
                if subprotocol not in icmp:
                    raise ApiManagerError("Icmp type can be in %s" % icmp, code=400)
                acl_protocol = "%s:%s" % (protocol, subprotocol)
        elif protocol == "*":
            port = get_value(service, "port", None, exception=True)
            if port != "*":
                raise ApiManagerError("Protocol * accept only port *", code=400)
            acl_protocol = "*:*"
        else:
            raise ApiManagerError(
                "Protocol %s is not supported. Use 6-tcp, 17-udp, 1-icmp, *-all" % protocol,
                code=400,
            )

        # if rule is not reserved and destination type is SecurityGroup check if SecurityGroup has acl that permit rule
        # creation
        # todo: when all the acl are populated
        # if reserved is False and destination.get('type') == 'SecurityGroup':
        #     acl_source = '%s:%s' % (source.get('type'), source.get('value'))
        #     acl_ports = service.get('port')
        #     if dest_entity.has_acl(acl_source, acl_protocol, acl_ports, where=None) is False:
        #         raise ApiManagerError('Destination security group %s does not permit input to source=%s with proto=%s '
        #                               'and ports=%s' % (dest_entity.uuid, acl_source, acl_protocol, acl_ports))

        params = {
            "orchestrator_tag": orchestrator_tag,
            "service": service,
            "availability_zones": [z for z in availability_zones],
            "attribute": {
                "reserved": reserved,
                "configs": {
                    "source": source,
                    "destination": destination,
                    "service": service,
                },
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeRule.task_path + "create_resource_pre_step",
            ComputeRule.task_path + "link_rule_step",
        ]

        for availability_zone in params["availability_zones"]:
            steps.append(
                {
                    "step": ComputeRule.task_path + "create_zone_rule_step",
                    "args": [availability_zone],
                }
            )

        steps.append(ComputeRule.task_path + "create_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in patch method. Extend this function to manipulate and validate
        patch input params.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs["steps"] = self.group_patch_step(ComputeRule.task_path + "task_patch_zone_rule_step")

        return kvargs

    def get_source(self):
        return self.get_attribs("configs.source")

    def get_dest(self):
        return self.get_attribs("configs.destination")

    def get_service(self):
        return self.get_attribs("configs.service")


class Rule(AvailabilityZoneChildResource):
    """Availability Zone Rule"""

    objdef = "Provider.Region.Site.AvailabilityZone.Rule"
    objuri = "%s/rules/%s"
    objname = "rule"
    objdesc = "Provider Availability Zone Rule"
    task_path = "beehive_resource.plugins.provider.task_v2.rule.RuleTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    def check_vsphere(self, orchestrator, section_id, rule_id):
        """Check vsphere nsx rule

        :param orchestrator: orchestrator instance
        :param section_id: section id
        :param rule_id: rule id
        :return: True if check is ok
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            dfw = orchestrator.get_nsx_dfw()
            dfw.get_layer3_section(oid=section_id)
            rule = dfw.get_rule(section_id, rule_id)
            self.logger.warn(rule)
            if rule == {}:
                self.logger.error("Vsphere nsx dfw rule %s:%s is KO" % (section_id, rule_id))
                return False
            self.logger.debug("Vsphere nsx dfw rule %s:%s is OK" % (section_id, rule_id))
            return True
        except:
            self.logger.error("Vsphere nsx dfw rule %s:%s is KO" % (section_id, rule_id))
            return False

    def check_openstack(self, orchestrator, rule):
        """Check vvsphere nsx rule
        todo:

        :param orchestrator: orchestrator instance
        :param rule: rule id
        :return: True if check is ok
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return True

    def check(self):
        """Check resource

        :return: True if check is ok
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = {}

        # # select remote orchestrators
        # orchestrator_idx = self.get_orchestrators_by_tag('default')
        # required_orchestrators = list(orchestrator_idx.keys())
        #
        # physical_rules, total = self.get_linked_resources(link_type_filter='relation')
        # physical_rules_orchestrators_used = []
        # for r in physical_rules:
        #     if str(r.container.oid) not in physical_rules_orchestrators_used:
        #         physical_rules_orchestrators_used.append(str(r.container.oid))
        #
        # required_orchestrators.sort()
        # physical_rules_orchestrators_used.sort()
        # if required_orchestrators != physical_rules_orchestrators_used:
        #     res = False
        #
        # for physical_rule in physical_rules:
        #     orchestrator_type = physical_rule.get_attribs('type')
        #     if orchestrator_type == 'vsphere':
        #         res1 = self.check_vsphere(physical_rule.container, physical_rule.get_attribs('section'),
        #                                   physical_rule.get_attribs('id'))
        #         res = res & res1
        #     elif orchestrator_type == 'openstack':
        #         res1 = self.check_openstack(physical_rule.container, physical_rule.get_attribs('id'))
        #         res = res & res1
        # self.logger.debug('Check remote rule %s: %s' % (self.uuid, res))
        return res

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
        :param kvargs.source: source RuleGroup, Server, Cidr. Syntax: {'type':.., 'value':..}
        :param kvargs.destination: destination RuleGroup, Server, Cidr. Syntax: {'type':.., 'value':..}
        :param kvargs.service: service configuration [optional]
        :return: kvargs
        :raise ApiManagerError:

        Ex. service:

            {'port':'*', 'protocol':'*'} -> *:*
            {'port':'*', 'protocol':6} -> tcp:*
            {'port':80, 'protocol':6} -> tcp:80
            {'port':80, 'protocol':17} -> udp:80
            {'protocol':1, 'subprotocol':8} -> icmp:echo request
        """
        # get zone
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        availability_zone: AvailabilityZone = controller.get_resource(kvargs.get("parent"))

        # select remote orchestrators
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        # orchestrator_select_types = kvargs.get("orchestrator_select_types")
        # orchestrator_idx = availability_zone.get_orchestrators_by_tag(orchestrator_tag, select_types=orchestrator_select_types)
        orchestrator_idx = availability_zone.get_hypervisors_by_tag(orchestrator_tag)

        params = {"orchestrators": orchestrator_idx}
        kvargs.update(params)

        # create job workflow
        steps = []
        for item in orchestrator_idx.values():
            steps.append(
                {
                    "step": Rule.task_path + "rule_create_orchestrator_resource_step",
                    "args": [item],
                }
            )

        kvargs["steps"] = AvailabilityZoneChildResource.group_create_step(steps)
        kvargs["sync"] = True

        return kvargs

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in patch method. Extend this function to manipulate and validate
        patch input params.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        # select remote orchestrators
        orchestrator_idx = self.get_orchestrators_by_tag(orchestrator_tag)

        params = {
            "tags": "",
            "parent": self.model.parent_id,
            "orchestrators": orchestrator_idx,
        }
        kvargs.update(params)
        kvargs.update(self.get_attribs("configs"))

        # get remote rules
        physical_rules, total = self.get_linked_resources(link_type_filter="relation")
        physical_rules_orchestrators_used = [str(r.container.oid) for r in physical_rules]

        # create job workflow
        steps = []

        new_orchestrators = {}

        # add rulee for absent orchestratore
        for cid, orchestrator in orchestrator_idx.items():
            # check rule exists in the orchestrator
            if cid not in physical_rules_orchestrators_used:
                new_orchestrators[orchestrator.get("id")] = orchestrator

        # check existing rules
        for physical_rule in physical_rules:
            # check rule is correct
            orchestrator_type = physical_rule.get_attribs("type")
            if orchestrator_type == "vsphere":
                res = self.check_vsphere(
                    physical_rule.container,
                    physical_rule.get_attribs("section"),
                    physical_rule.get_attribs("id"),
                )
            elif orchestrator_type == "openstack":
                res = self.check_openstack(physical_rule.container, physical_rule.get_attribs("id"))

            if res is False:
                # remove wrong rule
                physical_rule.expunge()

                orchestrator = orchestrator_idx.get(str(physical_rule.container.oid))
                new_orchestrators[orchestrator.get("id")] = orchestrator

        for orchestrator in new_orchestrators.values():
            steps.append(
                {
                    "step": Rule.task_path + "rule_create_orchestrator_resource_step",
                    "args": [orchestrator],
                }
            )

        kvargs["steps"] = AvailabilityZoneChildResource.group_create_step(steps)
        kvargs["sync"] = True

        return kvargs
