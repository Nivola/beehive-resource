# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from re import match
from ipaddress import IPv4Address
import ujson as json
from six import ensure_text
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beecell.simple import dict_get
from beecell.network import InternetProtocol
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup


class SecurityGroupAcl(ComputeProviderResource):
    """SecurityGroupAcl"""

    objdef = "Provider.ComputeZone.SecurityGroupAcl"
    objuri = "%s/security_group_acls/%s"
    objname = "security_group_acl"
    objdesc = "Provider SecurityGroupAcl"

    create_task = None
    import_task = None
    update_task = None
    patch_task = None
    delete_task = None
    expunge_task = None
    action_task = None

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

    def is_default(self):
        return self.get_attribs("is_default")

    def get_source(self):
        return self.get_attribs("source")

    def get_ports(self):
        return self.get_attribs("ports")

    def get_proto(self):
        return self.get_attribs("proto")

    def get_where(self):
        return self.get_attribs("where")

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        proto = info["attributes"]["proto"]
        if proto != "*:*":
            proto_check = InternetProtocol()
            proto, subproto = proto.split(":")
            proto = proto_check.get_name_from_number(int(proto))
            if subproto != "*":
                subproto = proto_check.get_name_from_number(int(subproto))
            info["attributes"]["proto"] = "%s:%s" % (proto, subproto)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        proto = info["attributes"]["proto"]
        if proto != "*:*":
            proto_check = InternetProtocol()
            proto, subproto = proto.split(":")
            proto = proto_check.get_name_from_number(int(proto))
            if subproto != "*":
                subproto = proto_check.get_name_from_number(int(subproto))
            info["attributes"]["proto"] = "%s:%s" % (proto, subproto)
        return info

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
        :param kvargs.is_deafult: set if acl is default
        :param kvargs.source: source SecurityGroup, Cidr. Syntax {'type':.., 'value':..}
        :param kvargs.source.type: can be SecurityGroup or Cidr [default='*']
        :param kvargs.source.value: can be SecurityGroup uuid, Cidr or * [default='*']
        :param kvargs.service: service configuration
        :param kvargs.service.protocol: service protocol. Use number or name [default='*']
        :param kvargs.service.ports: comma separated list of ports, single port or ports interval [optional]
        :param kvargs.service.subprotocol: use with icmp. Use number [optional]
        :param kvargs.service.where: custom firewall applied filter . Ex. protocol introspection action [optional]
        :return: kvargs
        :raise ApiManagerError:
        """
        is_default = dict_get(kvargs, "is_default", default=False)
        source_type = dict_get(kvargs, "source.type", default="*")
        source_value = dict_get(kvargs, "source.value", default="*")
        proto = dict_get(kvargs, "service.protocol", default="*")
        ports = dict_get(kvargs, "service.ports", default="*")
        subproto = dict_get(kvargs, "service.subprotocol", default="*")
        where = dict_get(kvargs, "service.where", default=None)

        proto_check = InternetProtocol()

        # check if proto is set as a string
        if proto != "*" and not match("^\d+$", proto):
            proto = str(proto_check.get_number_from_name(proto))

        # check if proto is set as a string
        if subproto != "*" and not match("^\d+$", subproto):
            subproto = str(proto_check.get_number_from_name(subproto))

        if proto in ["6", "17"]:
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

            # single port
            elif match("[0-9]+", str(ports)):
                ports = int(ports)
                if ports < 0 or ports > 65535:
                    raise ApiManagerError("Port can be a number between 0 and 65535", code=400)

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

        elif proto == "1":
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
            if subproto not in icmp:
                raise ApiManagerError("Icmp type can be in %s" % icmp, code=400)

        # check source
        if source_type == "SecurityGroup":
            source_value = container.get_simple_resource(source_value, entity_class=SecurityGroup)
            source_value = source_value.uuid
        elif source_type == "Cidr":
            try:
                ip, prefix = source_value.split("/")
                prefix = int(prefix)
            except ValueError:
                raise ApiManagerError("Cidr is malformed. Use xxx.xxxx.xxx.xxx/xx syntax", code=400)
            IPv4Address(ensure_text(ip))
            if prefix < 0 or prefix > 32:
                raise ApiManagerError("Cidr is malformed. Network prefix must be >= 0 and < 33", code=400)

        attribs = {
            "is_default": is_default,
            "source": "%s:%s" % (source_type, source_value),
            "proto": "%s:%s" % (proto, subproto),
            "ports": ports,
            "where": where,
        }
        kvargs["attribute"] = json.dumps(attribs)

        return kvargs

    def pre_update(*args, **kvargs):
        """
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.is_deafult: set if acl is default
        :param kvargs.source: source source SecurityGroup, Cidr. Syntax {'type':.., 'value':..}
        :param kvargs.source.type: can be SecurityGroup or Cidr [default='*']
        :param kvargs.source.value: can be SecurityGroup uuid, Cidr or * [default='*']
        :param kvargs.service: service configuration
        :param kvargs.service.protocol: service protocol. Use number or name [default='*']
        :param kvargs.service.ports: comma separated list of ports [optional]
        :param kvargs.service.subprotocol: use with icmp. Use number [optional]
        :param kvargs.service.where: custom firewall applied filter . Ex. protocol introspection action [optional]
        :return: kvargs
        :raise ApiManagerError:
        """

        # todo

        is_default = dict_get(kvargs, "is_default", False)
        source_type = dict_get(kvargs, "source.type", "*")
        source_value = dict_get(kvargs, "source.value", "*")
        proto = dict_get(kvargs, "service.protocol", "*")
        ports = dict_get(kvargs, "service.ports", "*")
        subproto = dict_get(kvargs, "service.subprotocol", "*")
        where = dict_get(kvargs, "service.where", None)

        proto_check = InternetProtocol()

        # check if proto is set as a string
        if not match("^\d+$", proto) and proto != "*":
            proto = proto_check.get_number_from_name(proto)

        # check if proto is set as a string
        if not match("^\d+$", subproto) and subproto != "*":
            subproto = proto_check.get_number_from_name(subproto)

        # check source
        if source_type == "SecurityGroup":
            source_value = container.get_resource(
                source_value,
                entity_class=SecurityGroup,
                details=False,
                run_customize=False,
            )
            source_value = source_value.uuid
        elif source_type == "Cidr":
            try:
                ip, prefix = source_value.split("/")
                prefix = int(prefix)
            except ValueError:
                raise ApiManagerError("Cidr is malformed. Use xxx.xxxx.xxx.xxx/xx syntax", code=400)
            IPv4Address(ensure_text(ip))
            if prefix < 0 or prefix > 32:
                raise ApiManagerError("Cidr is malformed. Network prefix must be >= 0 and < 33", code=400)

        attribs = {
            "is_default": is_default,
            "source": "%s:%s" % (source_type, source_value),
            "proto": "%s:%s" % (proto, subproto),
            "ports": ports,
            "where": where,
        }
        kvargs["attributes"] = json.dumps(attribs)

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
        # check related objects
        sgs, total = self.get_linked_resources(link_type="acl")
        if len(sgs) > 0:
            raise ApiManagerError("Security group acl has security group associated")

        return kvargs
