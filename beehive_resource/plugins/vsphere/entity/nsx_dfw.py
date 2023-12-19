# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import truncate, id_gen
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.plugins.vsphere.entity import NsxResource
from beehive.common.apimanager import ApiManagerError
from beedrones.vsphere.client import VsphereError
from beehive.common.data import trace
from beehive.common.task.canvas import signature
from beehive.common.task.manager import task_manager
from beehive_resource.plugins.vsphere.entity import get_task


class NsxDfw(NsxResource):
    objdef = "Vsphere.Nsx.Dfw"
    objuri = "nsx_dfws"
    objname = "nsx_dfw"
    objdesc = "Nsx distributed firewall"

    default_tags = ["vsphere", "network"]

    section_add_task = "beehive_resource.plugins.vsphere.task_v2.nsx_dfw.section_add_task"
    section_delete_task = "beehive_resource.plugins.vsphere.task_v2.nsx_dfw.section_delete_task"
    rule_add_task = "beehive_resource.plugins.vsphere.task_v2.nsx_dfw.rule_add_task"
    rule_update_task = "beehive_resource.plugins.vsphere.task_v2.nsx_dfw.rule_update_task"
    rule_move_task = "beehive_resource.plugins.vsphere.task_v2.nsx_dfw.rule_move_task"
    rule_delete_task = "beehive_resource.plugins.vsphere.task_v2.nsx_dfw.rule_delete_task"

    def __init__(self, *args, **kvargs):
        """ """
        NsxResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []

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
        items = []

        nsx_manager = container.conn.system.nsx.summary_info()
        nsx_manager_id = nsx_manager["hostName"]
        items.append(
            (
                "%s-dfw" % nsx_manager["hostName"],
                "%s Dfw" % nsx_manager["applianceName"],
                nsx_manager_id,
                None,
            )
        )

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = NsxDfw
                res.append(
                    (
                        resclass,
                        item[0],
                        parent_id,
                        resclass.objdef,
                        item[1],
                        parent_class,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # query vsphere nsx
        nsx_manager = container.conn.system.nsx.summary_info()
        items = [
            {
                "id": "%s-dfw" % nsx_manager["hostName"],
                "name": "%s Dfw" % nsx_manager["applianceName"],
            }
        ]

        return items

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

        parent = container.get_resource_by_extid(parent_id)
        parent_id = parent.oid
        objid = "%s//%s" % (parent.objid, id_gen())

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
        for entity in entities:
            entity.set_physical_entity("nsx")
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        self.set_physical_entity("nsx")

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = NsxResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = NsxResource.detail(self)
        return info

    #
    # list, get sections and rules
    #
    def __get_section(self, section):
        """ """
        section = section.pop("section")
        if isinstance(section, dict):
            section = [section]
        for s in section:
            rules = s.pop("rule", [])
            if isinstance(rules, dict):
                rules = [rules]
            s["rules"] = rules
        return section

    @trace(op="use")
    def get_config(self):
        """Get distributed firewall configuration.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            conf = self.container.conn.network.nsx.dfw.get_config()
            conf["layer2Sections"] = self.__get_section(conf.pop("layer2Sections"))
            conf["layer3RedirectSections"] = self.__get_section(conf.pop("layer3RedirectSections"))
            conf["layer3Sections"] = self.__get_section(conf.pop("layer3Sections"))

            self.logger.debug("Get difw configuration: %s" % truncate(conf))
            return conf
        except (VsphereError, Exception) as ex:
            self.logger.warning(ex, exc_info=True)
            return {}

    @trace(op="use")
    def get_layer3_section(self, oid=None, name=None):
        """Get distributed firewall l3 sections.

        :param oid: unique id  [optional]
        :param name: name. Ex. org1, sub2 [optional]
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            conf = self.container.conn.network.nsx.dfw.get_layer3_section(sectionid=oid, name=name)
            conf.pop("class", None)
            rules = conf.pop("rule", [])
            if isinstance(rules, dict):
                rules = [rules]
            conf["rules"] = rules
            self.logger.debug("Get nsx distributed firewall section %s, %s: %s" % (oid, name, truncate(conf)))
            return conf
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=400)

    @trace(op="use")
    def exist_layer3_section(self, oid=None, name=None):
        """Check distributed firewall l3 section exists

        :param oid: unique id  [optional]
        :param name: name. Ex. org1, sub2 [optional]
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            conf = self.container.conn.network.nsx.dfw.get_layer3_section(sectionid=oid, name=name)
            conf.pop("class", None)
            rules = conf.pop("rule", [])
            if isinstance(rules, dict):
                rules = [rules]
            conf["rules"] = rules
            self.logger.debug("Get nsx distributed firewall section %s, %s: %s" % (oid, name, truncate(conf)))
            return True
        except VsphereError as ex:
            self.logger.warning(ex)
            return False

    @trace(op="use")
    def get_section_rules(self, sectionid):
        """Get distributed firewall rules in a section.

        :param sectionid: section id
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            conf = self.container.conn.network.nsx.dfw.get_layer3_section(sectionid)["rules"]
            self.logger.debug("Get distributed firewall section %s rules: %s" % (sectionid, truncate(conf)))

            return conf
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=400)

    @trace(op="use")
    def get_rule(self, sectionid, ruleid):
        """Get distributed firewall rule.

        :param sectionid: section id
        :param ruleid: rule id
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            conf = self.container.conn.network.nsx.dfw.get_rule(sectionid, ruleid)
            self.logger.debug("Get distributed firewall rule %s: %s" % (ruleid, truncate(conf)))
            return conf
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=400)

    @trace(op="use")
    def get_exclusion_list(self):
        """Get exclusion list

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            res = self.container.conn.network.nsx.dfw.get_exclusion_list()
            members = res.pop("excludeMember", [])
            if isinstance(members, dict):
                members = [members]
            res["excludeMember"] = []
            for item in members:
                res["excludeMember"].append(item.pop("member"))
            self.logger.debug("Get distributed firewall exclusion list: %s" % truncate(res))
            return res
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=400)

    #
    # create, update, delete sections and rules
    #
    @trace(op="update")
    def create_section(self, params):
        """Create dfw section

        :param params: add params
        :param params.name: section name
        :param params.action: new action value. Ie: allow, deny, reject [default=allow]
        :param params.logged: if True rule is logged [default=true]
        :return: {'taskid':<task id>}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("update")

        # run celery job
        params.update(
            {
                "cid": self.container.oid,
                "objid": self.objid,
                "alias": "NsxSection.create"
                # 'alias': 'section-%s.create' % params['name']
            }
        )
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.section_add_task, params, sync=params.pop("sync", False))
        self.logger.info("Create dfw section %s using task %s" % (self.uuid, res))
        return res

    @trace(op="update")
    def delete_section(self, params):
        """Delete dfw section

        :param params: add params
        :param params.sectionid: section id
        :return: {'taskid':<task id>}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("update")

        # run celery job
        params.update(
            {
                "cid": self.container.oid,
                "objid": self.objid,
                "alias": "NsxSection.delete"
                # 'alias': 'section-%s.delete' % params['sectionid']
            }
        )
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.section_delete_task, params, sync=params.pop("sync", False))
        self.logger.info("Delete dfw section %s using task %s" % (self.uuid, res))
        return res

    @trace(op="update")
    def create_rule(self, params):
        """Create dfw rule

        :param params: add params
        :param params.sectionid: section id
        :param params.name: rule name
        :param params.action: new action value. Ie: allow, deny, reject [optional]
        :param params.logged: if 'true' rule is logged
        :param params.direction: rule direction: in, out, inout
        :param params.sources: List like [{'name':, 'value':, 'type':, }] [optional]

                Ex: [{'name':'db-vm-01', 'value':'vm-84', 'type':'VirtualMachine'}]
                Ex: [{'name':None, 'value':'10.1.1.0/24', 'type':'Ipv4Address'}]
                Ex: [{'name':'WEB-LS', 'value':'virtualwire-9',
                      'type':'VirtualWire'}]
                Ex: [{'name':'APP-LS', 'value':'virtualwire-10',
                      'type':'VirtualWire'}]
                Ex: [{'name':'SG-WEB2', 'value':'securitygroup-22',
                      'type':'SecurityGroup'}]
                Ex: [{'name':'PAN-app-vm2-01 - Network adapter 1',
                      'value':'50031300-ad53-cc80-f9cb-a97254336c01.000',
                          'type':'vnic'}]

        :param params.destinations: List like [{'name':, 'value':, 'type':, }] [optional]

                Ex: [{'name':'WEB-LS', 'value':'virtualwire-9',
                      'type':'VirtualWire'}]
                Ex: [{'name':'APP-LS', 'value':'virtualwire-10',
                      'type':'VirtualWire'}]
                Ex: [{'name':'SG-WEB-1', 'value':'securitygroup-21',
                      'type':'SecurityGroup'}]

        :param params.services: List like examples [optional]

                Ex: [{'name':'ICMP Echo Reply', 'value':'application-337',
                      'type':'Application'}]
                Ex: [{'name':'ICMP Echo', 'value':'application-70',
                      'type':'Application'}]
                Ex: [{'name':'SSH', 'value':'application-223',
                      'type':'Application'}]
                Ex: [{'name':'DHCP-Client', 'value':'application-223',
                      'type':'Application'},
                     {'name':'DHCP-Server', 'value':'application-223',
                      'type':'Application'}]
                Ex: [{'name':'HTTP', 'value':'application-278',
                      'type':'Application'},
                     {'name':'HTTPS', 'value':'application-335',
                      'type':'Application'}]
                Ex. [{'port':'*', 'protocol':'*'}] -> *:*
                    [{'port':'*', 'protocol':6}] -> tcp:*
                    [{'port':80, 'protocol':6}] -> tcp:80
                    [{'port':80, 'protocol':17}] -> udp:80
                    [{'protocol':1, 'subprotocol':8}] -> icmp:echo request

                Get id from https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
                For icmp Summary of Message Types:
                   0  Echo Reply
                   3  Destination Unreachable
                   4  Source Quench
                   5  Redirect
                   8  Echo
                  11  Time Exceeded
                  12  Parameter Problem
                  13  Timestamp
                  14  Timestamp Reply
                  15  Information Request
                  16  Information Reply

        :param params.appliedto: List like [{'name':, 'value':, 'type':, }] [optional]

                Ex: [{'name':'DISTRIBUTED_FIREWALL',
                      'value':'DISTRIBUTED_FIREWALL',
                      'type':'DISTRIBUTED_FIREWALL'}]
                Ex: [{'name':'ALL_PROFILE_BINDINGS',
                      'value':'ALL_PROFILE_BINDINGS',
                      'type':'ALL_PROFILE_BINDINGS'}]
                Ex: [{'name':'db-vm-01', 'value':'vm-84', 'type':'VirtualMachine'}]
                Ex: [{'name':'SG-WEB-1', 'value':'securitygroup-21',
                      'type':'SecurityGroup'},
                     {'name':'SG-WEB2', 'value':'securitygroup-22',
                      'type':'SecurityGroup'}]

        :return: {'taskid':<task id>}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("update")

        # run celery job
        params.update(
            {
                "cid": self.container.oid,
                "objid": self.objid,
                "alias": "NsxRule.create"
                # 'alias': 'rule-%s.create' % params['name']
            }
        )
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.rule_add_task, params, sync=params.pop("sync", False))
        self.logger.info("Add dfw section rule %s using task %s" % (self.uuid, res))
        return res

    @trace(op="update")
    def update_rule(self, params):
        """Update dfw rule

        :param params: add params
        :param params.sectionid: section id
        :param params.ruleid: rule id
        :param params.name: new rule name [optionale]
        :param params.action: new action value. Ie: allow, deny, reject [optional]
        :param params.disable: True if rule is disbles [optional]
        :return: {'taskid':<task id>}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("update")

        # run celery job
        params.update(
            {
                "cid": self.container.oid,
                "objid": self.objid,
                "alias": "NsxRule.update"
                # 'alias': 'rule-%s.update' % params['ruleid']
            }
        )
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.rule_update_task, params, sync=params.pop("sync", False))
        self.logger.info("Update dfw section rule %s using task %s" % (self.uuid, res))
        return res

    @trace(op="update")
    def move_rule(self, params):
        """Move dfw rule after another rule

        :param params: add params
        :param params.sectionid: section id
        :param params.ruleid: rule id
        :param params.ruleafter: rule id, put rule after this.
        :return: {'taskid':<task id>}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("update")

        # run celery job
        params.update(
            {
                "cid": self.container.oid,
                "objid": self.objid,
                "alias": "NsxRule.move"
                # 'alias': 'rule-%s.move' % params['ruleid']
            }
        )
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.rule_move_task, params, sync=params.pop("sync", False))
        self.logger.info("Move dfw section rule %s using task %s" % (self.uuid, res))
        return res

    @trace(op="update")
    def delete_rule(self, params):
        """Delete dfw rule

        :param params: add params
        :param params.sectionid: section id
        :param params.ruleid: rule id
        :return: {'taskid':<task id>}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # check authorization
        self.verify_permisssions("update")

        # run celery job
        params.update(
            {
                "cid": self.container.oid,
                "objid": self.objid,
                "alias": "NsxRule.delete"
                # 'alias': 'rule-%s.delete' % params['ruleid']
            }
        )
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.rule_delete_task, params, sync=params.pop("sync", False))
        self.logger.info("Delete dfw section rule %s using task %s" % (self.uuid, res))
        return res

    #
    # service
    #
    @trace(op="use")
    def get_services(self, proto=None, ports=None):
        """Get distributed firewall services

        :param proto: service protocol. Ex. TCP, UDP, ICMP, ..
        :param ports: service ports. Ex. 80, 8080,7200,7210,7269,7270,7575, 9000-9100
        :return: dfw services list
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            if proto is None:
                res = self.container.conn.network.nsx.service.list()
            elif proto is not None and ports is not None:
                res = self.container.conn.network.nsx.service.get(proto, ports)

            if res is None:
                raise Exception("Nsx dfw service for protocol %s and ports %s not found" % (proto, ports))

            self.logger.debug("Get distributed firewall services: %s" % truncate(res))
            return res
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=404)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="use")
    def create_service(self, proto, ports, name, desc):
        """Get distributed firewall services

        :param proto: service protocol. Ex. TCP, UDP, ICMP, ..
        :param ports: service ports. Ex. 80, 8080, 7200,7210,7269,7270,7575, 9000-9100
        :param name: service name
        :param desc: service desc
        :return: dfw service
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("update")

        try:
            res = self.container.conn.network.nsx.service.create(proto, ports, name, desc)
            self.logger.debug("Create distributed firewall service: %s" % res)
            return res
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=400)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    @trace(op="use")
    def delete_service(self, service_id):
        """Delete distributed firewall service

        :param service_id: service id
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("update")

        try:
            res = self.container.conn.network.nsx.service.delete(service_id)
            self.logger.debug("Delete distributed firewall service %s: %s" % (service_id, res))
            return True
        except VsphereError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex.value, code=400)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)


class NsxDfwSection(NsxResource):
    objdef = "Vsphere.Nsx.Dfw.Section"
    objdesc = "Vsphere Nsx dfw section"


class NsxDfwRule(NsxResource):
    objdef = "Vsphere.Nsx.Dfw.Rule"
    objdesc = " VsphereNsx dfw rule"
