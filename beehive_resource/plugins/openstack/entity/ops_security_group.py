# SPDX-License-Identifier: EUPL-1.2
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import id_gen
from beehive.common.data import trace
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.plugins.openstack.entity import OpenstackResource


class OpenstackSecurityGroup(OpenstackResource):
    objdef = "Openstack.Domain.Project.SecurityGroup"
    objuri = "security_groups"
    objname = "security_group"
    objdesc = "Openstack security groups"

    default_tags = ["openstack", "security_group"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_security_group.SecurityGroupTask."

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)
        :raises ApiManagerError:
        """
        # get from openstack
        if ext_id is not None:
            items = container.conn.network.security_group.get()
        else:
            items = container.conn.network.security_group.list()

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = item["tenant_id"]
                if str(parent_id) == "":
                    parent_id = None

                res.append(
                    (
                        OpenstackSecurityGroup,
                        item["id"],
                        parent_id,
                        OpenstackSecurityGroup.objdef,
                        name,
                        level,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        return container.conn.network.security_group.list()

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        level = entity[5]

        # get parent security_group
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            objid = "%s//%s" % (parent.objid, id_gen())
            parent_id = parent.oid
        else:
            objid = "%s//none//none//%s" % (container.objid, id_gen())
            parent_id = None

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent_id,
            "tags": resclass.default_tags,
        }
        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        # remote_entities = container.conn.network.security_group.list()
        #
        # # create index of related objs
        #
        # # create index of remote objs
        # remote_entities_index = {i['id']: i for i in remote_entities}
        #
        for entity in entities:
            ext_id = entity.ext_id
            ext_obj = OpenstackSecurityGroup.get_remote_securitygroup(controller, ext_id, container, ext_id)
            entity.set_physical_entity(ext_obj)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_id = self.ext_id
        ext_obj = OpenstackSecurityGroup.get_remote_securitygroup(self.controller, ext_id, self.container, ext_id)
        self.set_physical_entity(ext_obj)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackSecurityGroup.task_path + "create_resource_pre_step",
            OpenstackSecurityGroup.task_path + "security_group_create_physical_step",
            OpenstackSecurityGroup.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackSecurityGroup.task_path + "update_resource_pre_step",
            OpenstackSecurityGroup.task_path + "security_group_update_physical_step",
            OpenstackSecurityGroup.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackSecurityGroup.task_path + "expunge_resource_pre_step",
            OpenstackSecurityGroup.task_path + "security_group_expunge_physical_step",
            OpenstackSecurityGroup.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            rules = self.ext_obj.get("security_group_rules", [])
            data = {"rules": len(rules)}
            info["details"].update(data)

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            rules = self.ext_obj.get("security_group_rules", [])
            for rule in rules:
                sg = rule.pop("remote_group_id")
                if sg is not None:
                    resource = self.controller.get_resource_by_extid(sg)
                    rule["remote_group"] = resource.small_info()
                else:
                    rule["remote_group"] = {
                        "id": None,
                        "ext_id": None,
                        "name": None,
                        "uri": None,
                    }

            data = {"rules": rules}

            info["details"].update(data)

        return info

    @trace(op="update")
    def create_rule(self, params, sync=False):
        """Delete openstack security group rule.

        :param sync: run task as synchronous
        :param params: custom params
        :param params.direction: ingress or egress
        :param params.ethertype: Must be IPv4 or IPv6
        :param params.port_range_min: The minimum port number in the range that is matched by the security group rule.
            If the protocol is TCP or UDP, this value must be less than or equal to the port_range_max attribute value.
            If the protocol is ICMP, this value must be an ICMP type. [otpional]
        :param params.port_range_max: The maximum port number in the range that is matched by the security group rule.
            The port_range_min attribute constrains the port_range_max attribute. If the protocol is ICMP, this value
            must be an ICMP type. [optional]
        :param params.protocol: The protocol that is matched by the security group rule. Valid values are null, tcp,
            udp, and icmp. [optional]
        :param params.remote_group_id: The remote group UUID to associate with this security group rule. You can specify
            either the remote_group_id or remote_ip_prefix attribute in the request body. [optional]
        :param params.remote_ip_prefix: The remote IP prefix to associate with this security group rule. You can specify
            either the remote_group_id or remote_ip_prefix attribute in the request body. This attribute matches the
            IP prefix as the source IP address of the IP packet. [otpional]
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        direction = params.get("direction", "ingress")
        ethertype = params.get("ethertype", "IPv4")
        port_range_min = params.get("port_range_min", None)
        port_range_max = params.get("port_range_max", None)
        protocol = params.get("protocol", "tcp")
        remote_group_id = params.get("remote_group_id", None)
        remote_ip_prefix = params.get("remote_ip_prefix", None)

        remote_group = None
        if remote_group_id is not None:
            remote_group = self.controller.get_resource(remote_group_id)
            remote_group = remote_group.ext_id

        kvargs = {
            "direction": direction,
            "ethertype": ethertype,
            "port_range_min": port_range_min,
            "port_range_max": port_range_max,
            "protocol": protocol,
            "remote_group_extid": remote_group,
            "remote_ip_prefix": remote_ip_prefix,
            "sync": sync,
        }
        steps = [OpenstackSecurityGroup.task_path + "security_group_rule_create_step"]
        res = self.action(
            "create_rule",
            steps,
            log="Creeate security group %s rule" % self.oid,
            check=None,
            **kvargs,
        )
        return res

    @trace(op="update")
    def delete_rule(self, params, sync=False):
        """Delete openstack security group rule.

        :param sync: run task as synchronous
        :param params: custom params
        :param params.rule_id: rule id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        rule = params.get("rule_id", None)

        kvargs = {"rule_id": rule, "sync": sync}
        steps = [OpenstackSecurityGroup.task_path + "security_group_rule_delete_step"]
        res = self.action(
            "delete_rule",
            steps,
            log="Delete security group %s rule" % self.oid,
            check=None,
            **kvargs,
        )
        return res

    @trace(op="update")
    def reset_rule(self, *args, **kvargs):
        """Delete all openstack security group rules.

        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        steps = [OpenstackSecurityGroup.task_path + "security_group_rule_reset_step"]
        res = self.action(
            "reset_rule",
            steps,
            log="Reset security group %s rules" % self.oid,
            check=None,
            **kvargs,
        )
        return res

    def is_member(self, member):
        return True


class OpenstackSecurityGroupRule(OpenstackResource):
    objdef = "Openstack.Domain.Project.SecurityGroup.Rule"
    objdesc = "Openstack security group rule"
