# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from beecell.simple import id_gen
from beedrones.dns.client import DnsManager
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator, CustomResource, Resource
from beehive_resource.model import ResourceState


def get_task(task_name):
    return "%s.task.%s" % (__name__.rstrip(".controller"), task_name)


class DnsContainer(Orchestrator):
    """Dns container

    **connection syntax:

        {
            "serverdns":{
                "update": ["10.138.153.82", "10.138.217.82"],
                "resolver": ["10.103.48.1", "10.103.48.2"]
            },
            "key": {
                "nivolaprodkey.": "tq1vPSvUQEURKy...."
            }
        }
    """

    objdef = "Dns"
    objdesc = "Dns container"
    objuri = "nrs/dns"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [DnsZone]

        self.conn = None

    def ping(self):
        """Ping container.

        TODO:

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return True

    @staticmethod
    def pre_create(
        controller=None,
        type=None,
        name=None,
        desc=None,
        active=None,
        conn=None,
        **kvargs,
    ):
        """Check input params

        :param controller: resource controller instance
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param active: container active
        :param conn: container connection

                {
                    "serverdns":{
                        "update": ["10.138.153.82", "10.138.217.82"],
                        "resolver": ["10.103.48.1", "10.103.48.2"]
                    },
                    "key": {
                        "nivolaprodkey.": "tq1vPSvUQEURKy...."
                    }
                }

        :return: kvargs
        :raise ApiManagerError:
        """
        # encrypt dns update key
        for k, v in conn.get("key", {}).items():
            conn["key"][k] = controller.encrypt_data(v)

        kvargs = {
            "type": type,
            "name": name,
            "desc": desc,
            "active": active,
            "conn": conn,
        }
        return kvargs

    def pre_change(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def pre_clean(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def get_connection(self):
        """ """
        # decrypt update key
        for k, v in self.conn_params.get("key", {}).items():
            self.conn_params["key"][k] = self.controller.decrypt_data(v)

        conf = self.conn_params
        self.conn = DnsManager(conf.get("serverdns"), zones=conf.get("zones"), dnskey=conf.get("key"))
        Orchestrator.get_connection(self)

    def close_connection(self):
        """ """
        if self.conn is None:
            pass

    def get_zone(self, oid):
        """Get a zone

        :param oid: zone name, uuid or id
        :return: DnsZone instance
        """
        zone = self.get_resource(oid, entity_class=DnsZone)
        return zone


class DnsResource(Resource):
    objdef = "Dns.Resource"
    objuri = "dnsresource"
    objname = "dnsresource"
    objdesc = "Dns resource"

    def __init__(self, *args, **kvargs):
        DnsResource.__init__(self, *args, **kvargs)


class DnsZone(DnsResource):
    objdef = "Dns.DnsZone"
    objuri = "nrs/dns/zones"
    objname = "zone"
    objdesc = "Dns Zone"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

        self.child_classes = [DnsRecordA, DnsRecordCname]

    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        return info

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # check name
        return kvargs

    @staticmethod
    def post_create(controller, container, *args, **kvargs):
        """Check input params

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """

        return None

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # check there are no active child records
        return kvargs

    #
    # custom methdo
    #
    def get_nameservers(self):
        """Get all the nameservers that resolve the zone"""
        res = self.container.conn.query_nameservers(self.name, timeout=1.0)
        resp = []
        for k, vs in res.items():
            if vs is not None:
                for v in vs:
                    resp.append({"start_nameserver": k, "ip_addr": v[0], "fqdn": v[1]})
        self.logger.debug("List zone %s nameservers: %s" % (self.uuid, resp))
        return resp

    def get_authority(self):
        """Get the SOA (Start of Authority) used to manage the zone

        :return: list of dict with the following keys:

            start-nameserver: dns queried
            mname: The <domain-name> of the name server that was the original or primary source of data for this zone.
            rname: A <domain-name> which specifies the mailbox of the person responsible for this zone.
            serial: The unsigned 32 bit version number of the original copy of the zone. Zone transfers preserve this
                value. This value wraps and should be compared using sequence space arithmetic.
            refresh: A 32 bit time interval before the zone should be refreshed.
            retry: A 32 bit time interval that should elapse before a failed refresh should be retried.
            expire: A 32 bit time value that specifies the upper limit on the time interval that can elapse before the
                zone is no longer authoritative.
            minimum: The unsigned 32 bit minimum TTL field that should be exported with any RR from this zone.
            All times are in units of seconds.
        """
        res = self.container.conn.query_authority(self.name)
        resp = []
        for k, v in res.items():
            v["start_nameserver"] = k
            resp.append(v)
        self.logger.debug("Get zone %s authority: %s" % (self.uuid, resp))
        return resp

    def query_remote_record(self, name, recorda=True, recordcname=True, group="resolver"):
        """Get ip address or alias

        :param name: name to resolve
        :param recorda: if True resolve recorda
        :param recordcname: if True resolve recordcname
        :param group: group used for resolution. Can be resolver or update
        """
        fqdn = "%s.%s" % (name, self.name)
        resp = []

        # query record a
        if recorda is True:
            res = self.container.conn.query_record_A(fqdn, timeout=1.0, group=group)
            for k, v in res.items():
                resp.append({"type": "record_a", "start_nameserver": k, "ip_address": v})

        # query cname
        if recordcname is True:
            res = self.container.conn.query_record_CNAME(fqdn, timeout=1.0, group=group)
            for k, v in res.items():
                resp.append({"type": "record_cname", "start_nameserver": k, "base_fqdn": v})

        self.logger.debug("Query name %s in zone %s: %s" % (fqdn, self.uuid, resp))
        return resp

    def create_remote_redcorda(self, ip_addr, name, ttl):
        """Create new record a in remote dns

        :param ip_addr: ip address
        :param name: host name
        :param ttl: time to live
        :return:
        """
        res = self.container.conn.add_record_A(ip_addr, name, self.name, ttl=ttl)
        self.logger.debug("Create remote recorda %s %s in zone %s" % (ip_addr, name, self.name))
        return res

    def create_remote_redcord_cname(self, name, alias, ttl):
        """Create new record cname in remote dns

        :param name: host name
        :param alias: alias
        :param ttl: time to live
        :return:
        """
        res = self.container.conn.add_record_CNAME(name, alias, self.name, ttl=ttl)
        self.logger.debug("Create remote record cname %s %s in zone %s" % (name, alias, self.name))
        return res

    def delete_remote_redcorda(self, name):
        """Delete record in remote dns

        :param ip_addr: ip address
        :param name: host name
        :param ttl: time to live
        :return:
        """
        res = self.container.conn.del_record_A(name, self.name)
        self.logger.debug("Delete remote recorda %s in zone %s" % (name, self.name))
        return res

    def delete_remote_redcord_cname(self, name):
        """Delete record in remote dns

        :param ip_addr: ip address
        :param name: host name
        :param ttl: time to live
        :return:
        """
        res = self.container.conn.del_record_CNAME(name, self.name)
        self.logger.debug("Delete remote recorda %s in zone %s" % (name, self.name))
        return res

    def exist_remote_recorda(self, name):
        """Verify record a already exists

        :param name: name to resolve
        """
        res = False
        for a in self.query_remote_record(name, recordcname=False, group="update"):
            if a.get("ip_address", None) is not None:
                res = True

        return res

    def exist_remote_record_cname(self, name):
        """Verify record cname already exists

        :param name: name to resolve
        """
        res = False
        for a in self.query_remote_record(name, recorda=False, group="update"):
            if a.get("base_fqdn", None) is not None:
                res = True

        return res

    def import_record(self, records):
        """Import record from existing bind config

        :param records: bind records

            [
                (prova123,A,10.11.12.13),
                (prova123_,CNAME,prova123),
                (prova456,A,10.11.12.14),
                (prova890,A,10.11.12.15)
            ]
        """
        resp = {}
        for record in records:
            self.logger.warn("Get record %s" % record)

            ok = True
            if record["type"] == "A":
                items, tot = self.get_resources(
                    name=record["name"],
                    entity_class=DnsRecordA,
                    objdef=DnsRecordA.objdef,
                )
                if tot > 0:
                    self.logger.warn("Record a %s already exists" % record)
                    resp[record["name"]] = False
                    continue

                res = self.query_remote_record(record["name"], recordcname=False, group="resolver")
                for item in res:
                    if item.get("ip_address") is None:
                        ok = False
                        break
                if ok is False:
                    self.logger.warn(
                        "Record a %s does not exists in all nameservers of zone %s" % (record["name"], self.name)
                    )
                    resp[record["name"]] = False
                else:
                    # set ip address
                    attributes = {
                        "ip_address": record["value"],
                        "host_name": record["name"],
                    }
                    objid = "%s//%s" % (self.objid, id_gen())
                    model = self.container.add_resource(
                        objid=objid,
                        name=record["name"],
                        resource_class=DnsRecordA,
                        ext_id=None,
                        active=False,
                        desc=record["name"],
                        attrib=attributes,
                        parent=self.oid,
                    )
                    self.container.update_resource_state(model.id, ResourceState.ACTIVE)
                    self.container.activate_resource(model.id)
                    resp[record["name"]] = True
                    self.logger.debug("Import record a %s in zone %s" % (record, self.name))

            if record["type"] == "CNAME":
                items, tot = self.get_resources(
                    name=record["name"],
                    entity_class=DnsRecordCname,
                    objdef=DnsRecordCname.objdef,
                )
                if tot > 0:
                    self.logger.warn("Record cname %s already exists" % record)
                    resp[record["name"]] = False
                    continue

                res = self.query_remote_record(record["name"], recorda=False, group="resolver")
                for item in res:
                    if item.get("base_fqdn") is None:
                        ok = False
                        break
                if ok is False:
                    self.logger.warn(
                        "Record cname %s does not exists in all nameservers of zone %s" % (record["name"], self.name)
                    )
                    resp[record["name"]] = False
                else:
                    # set ip address
                    attributes = {"alias": record["name"], "host_name": record["value"]}
                    objid = "%s//%s" % (self.objid, id_gen())
                    model = self.container.add_resource(
                        objid=objid,
                        name=record["name"],
                        resource_class=DnsRecordCname,
                        ext_id=None,
                        active=False,
                        desc=record["name"],
                        attrib=attributes,
                        parent=self.oid,
                    )
                    self.container.update_resource_state(model.id, ResourceState.ACTIVE)
                    self.container.activate_resource(model.id)
                    resp[record["name"]] = True
                    self.logger.debug("Import record cname %s in zone %s" % (record, self.name))

        return resp


class DnsRecordA(DnsResource):
    objdef = "Dns.DnsZone.DnsRecordA"
    objuri = "nrs/dns/recordas"
    objname = "recorda"
    objdesc = "Dns DnsRecordA"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

        self.remote_record = {}

    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        parent = self.get_parent()
        self.parent = {"id": parent.oid, "name": parent.name, "uuid": parent.uuid}

        info = Resource.info(self)
        info["name"] = self.get_attribs(key="host_name")
        info["ip_address"] = self.get_attribs(key="ip_address")
        info["fqdn"] = "%s.%s" % (
            self.get_attribs(key="host_name"),
            self.parent.get("name", None),
        )
        info.pop("attributes")
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        parent = self.get_parent()
        self.parent = {"id": parent.oid, "name": parent.name, "uuid": parent.uuid}

        info = Resource.detail(self)
        info["name"] = self.get_attribs(key="host_name")
        info["ip_address"] = self.get_attribs(key="ip_address")
        info["fqdn"] = "%s.%s" % (
            self.get_attribs(key="host_name"),
            self.parent.get("name", None),
        )
        info["details"] = self.remote_record
        info.pop("attributes")
        return info

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        parent = self.get_parent()
        parent.set_container(self.container)
        self.remote_record = parent.query_remote_record(self.name, recordcname=False)
        self.remote_record.extend(parent.query_remote_record(self.name, recordcname=False, group="update"))

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params custom params
        :param kvargs: custom params
        :param kvargs.ip_addr: ip address to associate
        :param kvargs.host_name: host name
        :param kvargs.zone: dns zone
        :return: kvargs
        :raise ApiManagerError:
        """
        state = container.get_base_state()
        # elapsed = 0
        # timeout = 30
        # delta = 0.5
        # while state != 'ACTIVE':
        #     container.logger.warn('Dns container %s is not in ACTIVE state. Wait a little' % container.uuid)
        #     sleep(delta)
        #     elapsed += delta
        #     state = container.get_state()
        #
        #     if elapsed > timeout:
        #         raise ApiManagerError('Dns container %s is locked in a wrong state' % container.uuid)
        #
        # # lock container in state=UPDATING
        # container.update_state(ContainerState.UPDATING)

        # get zone
        zone = kvargs.get("parent")
        name = kvargs.get("name")
        force = kvargs.get("force")
        zone_obj = container.get_zone(zone)

        try:
            obj, tot = container.get_resources(authorize=False, parent=zone_obj.oid, name=name)
        except Exception as ex:
            tot = 0

        if tot > 0:
            raise ApiManagerError("Record a %s already exists in zone %s" % (name, zone))

        if zone_obj.exist_remote_recorda(name) is True:
            container.logger.warn("Record a %s in zone %s dns already exists" % (name, zone_obj.name))
            if force is True:
                zone_obj.delete_remote_redcorda(name)
                container.logger.warn("Delete existing record a %s in zone %s" % (name, zone_obj.name))
            else:
                raise ApiManagerError("Record a %s in zone %s dns already exists" % (name, zone_obj.name))

        elif zone_obj.exist_remote_record_cname(name) is True:
            container.logger.warn("Record cname %s in zone %s dns already exists" % (name, zone_obj.name))
            if force is True:
                zone_obj.delete_remote_redcord_cname(name)
                container.logger.warn("Delete existing record cname %s in zone %s" % (name, zone_obj.name))
            else:
                raise ApiManagerError("Record cname %s in zone %s dns already exists" % (name, zone_obj.name))

        # create remote recorda
        zone_obj.create_remote_redcorda(kvargs.get("ip_addr"), name, kvargs.get("ttl"))

        # set ip address
        kvargs["attribute"] = {"ip_address": kvargs.get("ip_addr"), "host_name": name}

        return kvargs

    @staticmethod
    def post_create(controller, container, *args, **kvargs):
        """Check input params

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # lock container in state=ACTIVE
        # container.update_state(ContainerState.ACTIVE)

        return None

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # res = self.client.replace_record_A(ip_addr, host_name, domain, ttl=300)

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # delete remote recorda
        zone_obj = self.get_parent()
        zone_obj.set_container(self.container)
        zone_obj.delete_remote_redcorda(self.name)

        return kvargs

    def post_delete(self, *args, **kvargs):
        """Post delete function. This function is used in delete method. Extend this function to execute action after
        object was deleted.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return True


class DnsRecordCname(DnsResource):
    objdef = "Dns.DnsZone.DnsRecordCname"
    objuri = "nrs/dns/recordcnames"
    objname = "record_cname"
    objdesc = "Dns DnsRecordCname"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        parent = self.get_parent()
        self.parent = {"id": parent.oid, "name": parent.name, "uuid": parent.uuid}

        info = Resource.info(self)
        info["name"] = self.get_attribs(key="alias")
        info["host_name"] = self.get_attribs(key="host_name")
        info["fqdn"] = "%s.%s" % (
            self.get_attribs(key="alias"),
            self.parent.get("name", None),
        )
        info.pop("attributes")
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        parent = self.get_parent()
        self.parent = {"id": parent.oid, "name": parent.name, "uuid": parent.uuid}

        info = Resource.detail(self)
        info["name"] = self.get_attribs(key="alias")
        info["host_name"] = self.get_attribs(key="host_name")
        info["fqdn"] = "%s.%s" % (
            self.get_attribs(key="alias"),
            self.parent.get("name", None),
        )
        info["details"] = self.remote_record
        info.pop("attributes")
        return info

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        parent = self.get_parent()
        parent.set_container(self.container)
        self.remote_record = parent.query_remote_record(self.name, recorda=False)
        self.remote_record.extend(parent.query_remote_record(self.name, recorda=False, group="update"))

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params custom params
        :param kvargs: custom params

                * **ip_addr: ip address to associate
                * **host_name: host name
                * **zone: dns zone

        :return: kvargs
        :raise ApiManagerError:
        """
        state = container.get_base_state()
        # elapsed = 0
        # timeout = 30
        # delta = 0.5
        # while state != 'ACTIVE':
        #     container.logger.warn('Dns container %s is not in ACTIVE state. Wait a little' % container.uuid)
        #     sleep(delta)
        #     elapsed += delta
        #     state = container.get_state()
        #
        #     if elapsed > timeout:
        #         raise ApiManagerError('Dns container %s is locked in a wrong state' % container.uuid)
        #
        # # lock container in state=UPDATING
        # container.update_state(ContainerState.UPDATING)

        # get zone
        zone = kvargs.get("parent")
        name = kvargs.get("name")
        force = kvargs.get("force")
        zone_obj = container.get_zone(zone)

        try:
            container.get_resources(authorize=False, parent=zone_obj.oid, name=name)
            raise ApiManagerError("Record a %s already exists in zone %s" % zone)
        except Exception as ex:
            pass

        if zone_obj.exist_remote_recorda(name) is True:
            container.logger.warn("Record a %s in zone %s dns already exists" % (name, zone_obj.name))
            if force is True:
                zone_obj.delete_remote_redcorda(name)
                container.logger.warn("Delete existing record a %s in zone %s" % (name, zone_obj.name))
            else:
                raise ApiManagerError("Record a %s in zone %s dns already exists" % (name, zone_obj.name))

        elif zone_obj.exist_remote_record_cname(name) is True:
            container.logger.warn("Record cname %s in zone %s dns already exists" % (name, zone_obj.name))
            if force is True:
                zone_obj.delete_remote_redcord_cname(name)
                container.logger.warn("Delete existing record cname %s in zone %s" % (name, zone_obj.name))
            else:
                raise ApiManagerError("Record cname %s in zone %s dns already exists" % (name, zone_obj.name))

        # create remote recorda
        zone_obj.create_remote_redcord_cname(kvargs.get("host_name"), name, kvargs.get("ttl"))

        # set ip address
        kvargs["attribute"] = {"alias": name, "host_name": kvargs.get("host_name")}

        return kvargs

    @staticmethod
    def post_create(controller, container, *args, **kvargs):
        """Check input params

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # lock container in state=ACTIVE
        # container.update_state(ContainerState.ACTIVE)

        return None

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # res = self.client.replace_record_A(ip_addr, host_name, domain, ttl=300)

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params custom params
        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # delete remote recorda
        zone_obj = self.get_parent()
        zone_obj.set_container(self.container)
        zone_obj.delete_remote_redcord_cname(self.name)

        return kvargs

    def post_delete(self, *args, **kvargs):
        """Post delete function. This function is used in delete method. Extend this function to execute action after
        object was deleted.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return True
