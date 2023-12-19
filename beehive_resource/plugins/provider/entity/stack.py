# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from datetime import datetime

from beecell.simple import truncate, format_date, id_gen
from beehive.common.apiclient import BeehiveApiClientError
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace

from beehive_resource.plugins.dns.controller import DnsZone, DnsRecordA
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource


class ComputeStack(ComputeProviderResource):
    """Compute stack"""

    objdef = "Provider.ComputeZone.ComputeStack"
    objuri = "%s/stacks/%s"
    objname = "stack"
    objdesc = "Provider ComputeStack"
    task_path = "beehive_resource.plugins.provider.task_v2.stack.StackTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.zone_stacks = []

    def get_stack_type(self):
        """Return stack type. Example: app_stack, sql_stack"""
        return self.get_attribs("stack_type")

    def get_stack_engine(self):
        """Return stack engine info"""
        return {
            "engine": self.get_attribs("engine"),
            "version": self.get_attribs("version"),
            "engine_configs": self.get_attribs("engine_configs"),
        }

    def get_runstate(self):
        """Get resource running state if exixst.

        :return: None if runstate does not exist
        """
        runstate = []
        for zone_stack in self.zone_stacks:
            remote_stack = zone_stack.get_remote_stack()
            if remote_stack is not None:
                runstate.append(remote_stack.get_status().lower())
        return ",".join(runstate)

    def info(self):
        """Get infos.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeProviderResource.info(self)

        return info

    def detail(self):
        """Get details.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = ComputeProviderResource.detail(self)
        return info

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        resource_ids = [e.oid for e in entities]
        zone_stacks_all = controller.get_directed_linked_resources_internal(
            resource_ids, link_type="relation%", run_customize=False
        )

        # index zone stacks
        zone_stacks_all_idx = {}
        for zs in zone_stacks_all.values():
            zone_stacks_all_idx.update({z.oid: z for z in zs})

        # get all the physical stacks related to zone stacks
        physical_stacks = controller.get_directed_linked_resources_internal(
            list(zone_stacks_all_idx.keys()),
            link_type="relation",
            run_customize=True,
            objdef=OpenstackHeatStack.objdef,
        )
        for zone_id, zone_stack in zone_stacks_all_idx.items():
            physical_stack = physical_stacks.get(zone_id, None)
            if physical_stack is not None:
                zone_stack.set_remote_stack(physical_stack[0])

        for e in entities:
            e.zone_stacks = zone_stacks_all.get(e.oid, [])

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        get_resources = self.controller.get_directed_linked_resources_internal

        resource_ids = [self.oid]
        zone_stacks_all = get_resources(resource_ids, link_type="relation%", run_customize=False)
        self.zone_stacks = zone_stacks_all.get(self.oid, [])

        # index zone stacks
        zone_stacks_idx = {}
        for z in self.zone_stacks:
            zone_stacks_idx[z.oid] = z

        physical_stacks = get_resources(
            list(zone_stacks_idx.keys()),
            link_type="relation",
            run_customize=True,
            objdef=OpenstackHeatStack.objdef,
        )

        for zone_id, zone_stack in zone_stacks_idx.items():
            physical_stack = physical_stacks.get(zone_id, None)
            if physical_stack is not None:
                zone_stack.set_remote_stack(physical_stack[0])

    def __resources(self):
        """Get stack resources.

        :return: list of child resources for each stack child
        :raise ApiManagerError:
        """
        res = {}
        for zone_stack in self.zone_stacks:
            res[zone_stack.parent_id] = zone_stack.resources()

        self.logger.debug2("Get stack %s resources: %s" % (self.uuid, res))
        return res

    def get_quotas(self):
        """Get resource quotas

        :return: list of resoruce quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "instances": 1,
            "cores": 0,
            "ram": 0,
            "blocks": 0,
            "volumes": 0,
            "snapshots": 0,
        }
        for zone_stack in self.zone_stacks:
            for resource in zone_stack.resources():
                if isinstance(resource, OpenstackVolume):
                    resource.post_get()
                    quotas["blocks"] += resource.get_size()
                    quotas["volumes"] += 1
                    # quotas['snapshots'] += len(resource.list_snapshots())
                elif isinstance(resource, OpenstackServer):
                    resource.post_get()
                    if resource.is_running() is True:
                        flavor = resource.get_flavor()
                        quotas["instances"] += 1
                        quotas["cores"] += flavor.get("cpu", 0)
                        quotas["ram"] += flavor.get("memory", 0) / 1024

        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    def resources(self):
        """Get stack resources.

        :return: list of child resources for each stack child
        :raise ApiManagerError:
        """
        res = []
        for zone_stack in self.zone_stacks:
            resources = [z.small_info() for z in zone_stack.resources()]
            res.append(
                {
                    "availability_zone": zone_stack.parent_id,
                    "internal_resources": zone_stack.internal_resources(),
                    "resources": resources,
                }
            )
        return res

    def inputs(self):
        """Get inputs.

        :return: list of inputs for each stack child
        :raise ApiManagerError:
        """
        objs, total = self.get_linked_resources(link_type_filter="relation%")
        res = []
        for obj in objs:
            obj.post_get()
            res.append({"availability_zone": obj.parent_id, "inputs": obj.inputs()})
        return res

    def outputs(self):
        """Get outputs.

        :return: list of outputs for each stack child
        :raise ApiManagerError:
        """
        objs, total = self.get_linked_resources(link_type_filter="relation%")
        res = []
        for obj in objs:
            obj.post_get()
            res.append({"availability_zone": obj.parent_id, "outputs": obj.outputs()})
        return res

    def get_all_servers(self):
        """Get all stack servers.

        :returns: dict like {'<availability zone id>': [<child server>, ..]
        :raise ApiManagerError:
        """
        res = {}
        for zone_stack in self.zone_stacks:
            resources = zone_stack.resources()
            for resource in resources:
                if resource.objdef == OpenstackServer.objdef:
                    resource.post_get()
                    try:
                        res[str(zone_stack.parent_id)].append(resource)
                    except:
                        res[str(zone_stack.parent_id)] = [resource]

        self.logger.debug("Get all stack %s servers: %s" % (self.uuid, truncate(res)))
        return res

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.parameters: stack input parameters
        :param kvargs.templates: list of stack template per availability zone
        :param kvargs.templates.availability_zone: id, uuid or name of the site
        :param kvargs.templates.orchestrator_type: Orchestrator type. Can be openstack or vsphere
        :param kvargs.templates.template_uri: remote template uri
        :param kvargs.templates.environment: additional environment
        :param kvargs.templates.parameters: stack input parameters
        :param kvargs.templates.files: stack input files
        :param kvargs.resolve: Define if stack instances must be registered on the availability_zone dns zone
          [default=True]
        :return: kvargs
        :raise ApiManagerError:
        """
        # get zone
        compute_zone_id = kvargs.get("parent")
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        multi_avz = True

        # get global parameters
        parameters = kvargs.get("parameters")

        # check template
        templates = []
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
        for template in kvargs.get("templates"):
            # template['orchestrator_id'] = controller.get_container(template.pop('orchestrator')).oid
            # get site id
            site = controller.get_resource(
                template.pop("availability_zone"),
                entity_class=Site,
                run_customize=False,
            )
            template["site_id"] = site.oid
            try:
                zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)
                template["availability_zone_id"] = zone
                template["parameters"].update(parameters)
                templates.append(template)
            except:
                controller.logger.warn("Availability zone in site %s is not ACTIVE" % site.uuid)

        kvargs["orchestrator_tag"] = kvargs.get("orchestrator_tag", "default")

        # create job workflow
        steps = [
            ComputeStack.task_path + "create_resource_pre_step",
            ComputeStack.task_path + "link_compute_stack_step",
        ]
        for template in templates:
            stack_id = id_gen()

            steps.append(
                {
                    "step": ComputeStack.task_path + "create_zone_stack_step",
                    "args": [template, stack_id],
                }
            )

            # append create twins steps
            current_availability_zone = template["availability_zone_id"]

            # remove temporarily current availability zone id
            availability_zones.remove(current_availability_zone)

            for availability_zone in availability_zones:
                steps.append(
                    {
                        "step": ComputeStack.task_path + "create_zone_stack_twins_step",
                        "args": [availability_zone, stack_id],
                    }
                )

            # restore removed availability zone id
            availability_zones.append(current_availability_zone)

        steps.extend(
            [
                ComputeStack.task_path + "manage_compute_stack_step",
                ComputeStack.task_path + "register_dns_compute_stack_step",
                ComputeStack.task_path + "create_resource_post_step",
            ]
        )
        kvargs["steps"] = steps

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # get stacks
        stacks, total = self.get_linked_resources(link_type_filter="relation%")

        childs = [p.oid for p in stacks]

        # create task workflow
        steps = [
            ComputeStack.task_path + "expunge_resource_pre_step",
            ComputeStack.task_path + "unmanage_compute_stack_step",
            ComputeStack.task_path + "unregister_dns_compute_stack_step",
        ]
        for child in childs:
            steps.append({"step": ComputeStack.task_path + "remove_child_step", "args": [child]})
        steps.append(ComputeStack.task_path + "expunge_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    def send_action(self, action, *args, **kvargs):
        """Send action to stack

        :param action: action to execute. Required signature action(*args, **kvargs)
        :param args: custom params to send to action
        :param kvargs: custom params to send to action

        :return: kvargs
        :raise ApiManagerError:
        """
        self.verify_permisssions(action="update")

        res = action(self.controller, self, *args, **kvargs)
        self.logger.debug("Send action %s to stack %s" % (action.__name__, self.uuid))
        return res

    #
    # metrics
    #
    def get_metrics(self):
        """Get resource metrics

        :return: a dict like this

        {
            "id": "1",
            "uuid": "vm1",
            "metrics": [
                    {
                        "key": "ram",
                        "value: 10,
                        "type": 1,
                        "unit": "GB"
                    }],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"

        }
        """
        prefix = ""
        if self.get_stack_type() == "sql_stack":
            if self.get_stack_engine().get("engine") == "mysql":
                prefix = "db_mysql_"
            elif self.get_stack_engine().get("engine") == "postgres":
                prefix = "db_pgsql_"
        elif self.get_stack_type() == "app_stack":
            if self.get_stack_engine().get("engine") == "apache-php":
                prefix = "app_php_"

        metrics = {
            "%svcpu" % prefix: 0,
            "%sgbram" % prefix: 0,
            "%sgbdisk_low" % prefix: 0,
            "%sgbdisk_hi" % prefix: 0,
        }

        metric_units = {
            "%svcpu" % prefix: "#",
            "%sgbram" % prefix: "GB",
            "%sgbdisk_low" % prefix: "GB",
            "%sgbdisk_hi" % prefix: "GB",
        }

        for zone_stack in self.zone_stacks:
            for resource in zone_stack.resources():
                if isinstance(resource, OpenstackVolume):
                    resource.post_get()
                    metrics["%sgbdisk_low" % prefix] += resource.get_size()
                elif isinstance(resource, OpenstackServer):
                    resource.post_get()
                    if resource.is_running() is True:
                        flavor = resource.get_flavor()
                        metrics["%svcpu" % prefix] += flavor.get("cpu", 0)
                        metrics["%sgbram" % prefix] += flavor.get("memory", 0) / 1024

        metrics = [{"key": k, "value": v, "type": 1, "unit": metric_units.get(k)} for k, v in metrics.items()]
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get compute stack %s metrics: %s" % (self.uuid, res))
        return res

    #
    # manage through ssh module
    #
    @trace(op="update")
    def is_managed(self, *args, **kvargs):
        """Check compute stack is managed with ssh module.

        :return: True if it is managed
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        for avz_id, servers in self.get_all_servers().items():
            avz = self.controller.get_resource(avz_id)
            dns_zone = avz.get_site().get_dns_zone()
            for server in servers:
                try:
                    # fqdn = '%s.%s' % (server.name, dns_zone)
                    fqdn = server.name.replace("_", "-")
                    self.api_client.get_ssh_node(fqdn)
                except BeehiveApiClientError as ex:
                    if ex.code == 404:
                        self.logger.error("Server %s is not managed by ssh module" % server.uuid)
                        self.logger.error("Compute stack %s is not managed by ssh module" % self.uuid)
                        return False
                    else:
                        raise
        self.logger.debug("Compute stack %s is managed by ssh module" % self.uuid)
        return True

    @trace(op="update")
    def manage(self, user=None, key=None, password="", *args, **kvargs):
        """Manage compute instance with ssh module. Create group in ssh module where register server.

        :param user: ssh node user
        :param key: ssh key uuid or name
        :param password: user password [default='']
        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        # check compute zone is managed by ssh module
        compute_zone = self.get_parent()
        group = compute_zone.get_ssh_group()

        for avz_id, servers in self.get_all_servers().items():
            for server in servers:
                fqdn = server.name.replace("_", "-")
                server_details = server.detail().get("details")

                try:
                    res = self.api_client.get_ssh_node(fqdn)
                    uuid = res.get("uuid")
                    self.logger.warning(
                        "Compute stack %s is already managed by ssh module" % self.uuid,
                        exc_info=1,
                    )
                    return uuid
                except BeehiveApiClientError as ex:
                    if ex.code == 404:
                        pass
                    else:
                        raise

                keys = compute_zone.get_ssh_keys(oid=key)

                # get networks
                server_nets = server_details["networks"]
                server_net = server_nets[0]
                fixed_ip = server_net["fixed_ips"][0]
                ip_address = fixed_ip["ip_address"]

                # create ssh node
                uuid = self.api_client.add_ssh_node(
                    fqdn,
                    server.desc,
                    ip_address,
                    group,
                    user,
                    key=key,
                    attribute="",
                    password=password,
                )
                self.logger.debug(
                    "Compute stack %s server %s is now managed by ssh group %s" % (self.uuid, server.uuid, uuid)
                )

        self.logger.debug("Compute stack %s is now managed by ssh" % self.uuid)
        return self.uuid

    @trace(op="update")
    def unmanage(self, *args, **kvargs):
        """Unmanage compute instance with ssh module. Remove group in ssh module where register server.

        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        for avz_id, servers in self.get_all_servers().items():
            for server in servers:
                fqdn = server.name.replace("_", "-")

                try:
                    res = self.api_client.get_ssh_node(fqdn)
                    uuid = res.get("uuid")
                except BeehiveApiClientError as ex:
                    if ex.code == 404:
                        self.logger.warning(
                            "Compute stack %s is not managed by ssh module" % self.uuid,
                            exc_info=1,
                        )
                    else:
                        raise

                self.api_client.delete_ssh_node(fqdn)

                self.logger.debug(
                    "Compute stack %s server %s is now unmanaged by ssh module" % (self.uuid, server.uuid)
                )

        self.logger.debug("Compute instance %s is now unmanaged by ssh module" % self.uuid)
        return True

    #
    # dns
    #
    @trace(op="update")
    def get_dns_recorda(self, *args, **kvargs):
        """Get compute instance dns recorda.

        :param user: ssh node user
        :param key: ssh key uuid or name
        :param password: user password [default='']
        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("use")

        res = []
        for avz_id, servers in self.get_all_servers().items():
            avz = self.controller.get_resource(avz_id)
            zone_name = avz.get_site().get_dns_zone()

            for server in servers:
                fqdn = server.name.replace("_", "-")
                fqdn = fqdn.split(".")
                name = fqdn[0]
                zone = self.controller.get_resource(zone_name, entity_class=DnsZone)

                recordas, tot = self.controller.get_resources(
                    name=name,
                    parent=zone.oid,
                    entity_class=DnsRecordA,
                    objdef=DnsRecordA.objdef,
                    parents={zone.oid: {"id": zone.oid, "uuid": zone.uuid, "name": zone.name}},
                )
                if tot > 0:
                    recorda = recordas[0]
                    recorda.post_get()
                    res.append(recorda)

                    self.logger.debug("Stack server %s recorda %s" % (server.uuid, res))
        return res

    @trace(op="update")
    def set_dns_recorda(self, force=True, ttl=30):
        """Set compute instance dns recorda.

        :param force: If True force registration of record in dns
        :param ttl: dns record time to live
        :return: recorda uuid
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        try:
            res = []
            for avz_id, servers in self.get_all_servers().items():
                for server in servers:
                    fqdn = server.name.replace("_", "-")
                    fqdn = fqdn.split(".")

                    # if server has no zone name in fqdn bypass dns task
                    if len(fqdn) == 1:
                        continue

                    name = fqdn[0]
                    zone_name = ".".join(fqdn[1:])

                    # get networks
                    try:
                        server_details = server.detail().get("details")
                        fixed_ip = server_details["networks"][0]["fixed_ips"][0]
                        ip_addr = fixed_ip["ip_address"]
                    except:
                        raise ApiManagerError("Server %s ip can not be found" % server.uuid)

                    # get zone
                    try:
                        zone = self.controller.get_resource(zone_name, entity_class=DnsZone)
                    except:
                        continue

                    # check recorda already exixts
                    recordas, tot = self.controller.get_resources(
                        name=name,
                        parent=zone.oid,
                        entity_class=DnsRecordA,
                        objdef=DnsRecordA.objdef,
                        parents={
                            zone.oid: {
                                "id": zone.oid,
                                "uuid": zone.uuid,
                                "name": zone.name,
                            }
                        },
                    )
                    if tot == 0:
                        rec = zone.resource_factory(
                            DnsRecordA,
                            name,
                            desc=name,
                            ip_addr=ip_addr,
                            ttl=ttl,
                            force=force,
                        )[0]
                        self.logger.debug("Create stack server %s recorda %s" % (server.uuid, rec.get("uuid")))
                        res.append(rec.get("uuid"))
                    else:
                        self.logger.error("Recorda for stack server %s already exist" % server.uuid)
                        raise ApiManagerError("Recorda for stack server %s already exist" % server.uuid)
        except:
            self.logger.error("", exc_info=1)
            raise

        return res

    @trace(op="update")
    def unset_dns_recorda(self):
        """Unset compute instance dns recorda.

        :return: recorda uuid
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions("update")

        try:
            res = []
            for avz_id, servers in self.get_all_servers().items():
                for server in servers:
                    fqdn = server.name.replace("_", "-")
                    fqdn = fqdn.split(".")

                    # if server has no zone name in fqdn bypass dns task
                    if len(fqdn) == 1:
                        continue

                    name = fqdn[0]
                    zone_name = ".".join(fqdn[1:])

                    # get zone
                    try:
                        zone = self.controller.get_resource(zone_name, entity_class=DnsZone)
                    except:
                        continue

                    # check recorda already exixts
                    recordas, tot = self.controller.get_resources(
                        name=name,
                        parent=zone.oid,
                        entity_class=DnsRecordA,
                        objdef=DnsRecordA.objdef,
                        parents={
                            zone.oid: {
                                "id": zone.oid,
                                "uuid": zone.uuid,
                                "name": zone.name,
                            }
                        },
                    )
                    if tot == 0:
                        self.logger.warn("Recorda for stack server %s does not exist" % server.uuid)

                    else:
                        uuid = recordas[0].uuid
                        recordas[0].delete()
                        self.logger.debug("Delete stack server %s recorda %s" % (server.uuid, uuid))

                        res.append(uuid)
        except:
            self.logger.error("", exc_info=1)
            raise

        return res


class Stack(AvailabilityZoneChildResource):
    """Availability Zone Stack"""

    objdef = "Provider.Region.Site.AvailabilityZone.Stack"
    objuri = "%s/stacks/%s"
    objname = "zone_stack"
    objdesc = "Provider Availability Zone Stack"
    task_path = "beehive_resource.plugins.provider.task_v2.stack.StackTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

        self.physical_stack = None

    def has_remote_stack(self):
        if self.physical_stack is not None:
            return True
        return False

    def get_remote_stack(self):
        """Get remote stack"""
        return self.physical_stack

    def set_remote_stack(self, remote_stack):
        """Set remote stack

        :param remote_stack: instance of OpenstackHeatStack
        """
        self.physical_stack = remote_stack

    def status_reason(self):
        """Get stack error.

        :return:
        :raise ApiManagerError:
        """
        if self.physical_stack is not None:
            res = self.physical_stack.get_status_reason()
            return res
        return None

    def resources(self):
        """Get resources.

        :return:
        :raise ApiManagerError:
        """
        resources = []
        if self.physical_stack is not None:
            obj_ress, total = self.physical_stack.get_stack_resources()
            resources = obj_ress
        self.logger.debug("Get stack resources : %s" % truncate(resources))
        return resources

    def internal_resources(self):
        """Get internal resources.

        :return:
        :raise ApiManagerError:
        """
        resources = []
        if self.physical_stack is not None:
            obj_ress = self.physical_stack.get_stack_internal_resources()
            resources.extend(obj_ress)
        self.logger.debug("Get stack internal resources : %s" % truncate(resources))
        return resources

    def inputs(self):
        """Get remote stack inputs

        :return: list of inputs
        :raise ApiManagerError:
        """
        if self.physical_stack is not None:
            res = self.physical_stack.get_inputs()
            return res
        return {}

    def outputs(self):
        """Get remote stack outputs

        :return: list of outputs
        :raise ApiManagerError:
        """
        if self.physical_stack is not None:
            res = self.physical_stack.get_outputs()
            return res
        return []

    def output(self, key):
        """Get remote stack output

        ;param key: output key
        :return: list of outputs
        :raise ApiManagerError:
        """
        if self.physical_stack is not None:
            res = self.physical_stack.get_output(key).get("output_value", None)
            return res
        return []

    def events(self):
        """Get remote stack events

        :return:
        :raise ApiManagerError:
        """
        if self.physical_stack is not None:
            res = self.physical_stack.get_events()
            return res
        return None

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input kvargs before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom kvargs
        :param kvargs: custom kvargs
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.attribute.stack: True if related to an OpenstackStack, False if related to a twin
        :param kvargs.attribute.template_uri: None if related to a twin
        :param kvargs.tags: comma separated resource tags to assign [default='']

        :param kvargs.compute_stack: id of the compute stack
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.template: template per availability zone.
        :param kvargs.template.orchestrator_type: Orchestrator type. Can be openstack, vsphere
        :param kvargs.template.template_uri: remote template uri
        :param kvargs.template.environment: additional environment
        :param kvargs.template.parameters: stack input parameters
        :param kvargs.template.files: stack input files
        :return: kvargs
        :raise ApiManagerError:

            ...
        :param kvargs.orchestrators:
        :param kvargs.orchestrators.vsphere: {..}
        :param kvargs.orchestrators.openstack: {..}
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        # templates = kvargs.get('templates')

        # get zone
        zone = container.get_resource(kvargs.get("parent"))

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)

        # index orchestrator by type
        orchestrator_idx = {item["type"]: item for item in orchestrator_idx.values()}

        # set container
        params = {"orchestrators": orchestrator_idx}
        kvargs.update(params)

        # create job workflow
        steps = [
            Stack.task_path + "create_resource_pre_step",
            Stack.task_path + "link_stack_step",
            Stack.task_path + "create_stack_step",
            Stack.task_path + "create_twins_step",
            Stack.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True

        return kvargs

    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs*: custom params
        :return: entities
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        self.get_remote_stack()
