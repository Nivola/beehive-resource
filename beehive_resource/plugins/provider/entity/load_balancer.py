# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from copy import deepcopy
from beecell.types.type_dict import dict_get, dict_set
from beecell.types.type_id import id_gen
from beehive.common.task_v2 import run_async, prepare_or_run_task
from beehive_resource.controller import ResourceController
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.util import create_resource
from beehive_resource.container import Resource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.provider.entity.instance import ComputeInstance, Instance
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

from logging import getLogger

logger = getLogger(__name__)


class ComputeLoadBalancer(ComputeProviderResource):
    """Compute load balancer"""

    objdef = "Provider.ComputeZone.ComputeLoadBalancer"
    objuri = "%s/loadbalancers/%s"
    objname = "load_balancer"
    objdesc = "Provider ComputeLoadBalancer"
    task_path = "beehive_resource.plugins.provider.task_v2.load_balancer.LoadBalancerTask."

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)
        self.actions = []
        self.helper = None

    def get_hypervisor(self):
        return self.get_attribs(key="orchestrator_type")

    def get_network_appliance_helper(self):
        compute_zone = self.get_parent()
        hypervisor = self.get_hypervisor()
        site_id = self.get_attribs(key="site")
        self.controller: ResourceController
        site = self.controller.get_simple_resource(site_id)
        self.helper = compute_zone.get_network_appliance_helper(hypervisor, self.controller, site)
        return self.helper

    def get_status(self):
        if self.helper is None:
            self.get_network_appliance_helper()
        network_appliance_id = dict_get(self.get_attribs(), "network_appliance.uuid")
        return self.helper.is_lb_enabled(network_appliance_id)

    @staticmethod
    def get_private_master_subnet(vpc):
        """

        :param vpc:
        :return:
        """
        return vpc.get_attribs(key="configs.cidr")

    @staticmethod
    def get_interpod_subnet(compute_zone):
        """

        :return:
        """
        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway

        compute_gateway: ComputeGateway = compute_zone.get_default_gateway()
        interpod_vpc = dict_get(compute_gateway.info(), "vpc.transport")
        if interpod_vpc is None:
            raise ApiManagerError("Interpod vpc not found")
        if not isinstance(interpod_vpc, list):
            interpod_vpc = [interpod_vpc]
        if len(interpod_vpc) != 1:
            raise ApiManagerError("Interpod vpc is not unique")
        interpod_vpc = interpod_vpc[0]
        cidr = interpod_vpc.get("cidr")
        return cidr

    def __get_availability_zone_info(self, info):
        site_id = self.get_attribs().get("site")
        availability_zone = self.controller.get_simple_resource(site_id)
        if availability_zone:
            info["availability_zone"] = availability_zone.small_info()
        else:
            info["availability_zone"] = {}
        return info

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        info = self.__get_availability_zone_info(info)
        parent = self.get_parent()
        info["parent_desc"] = parent.desc
        try:
            status_mapping = {True: "Enabled", False: "Disabled", None: "Unknown"}
            info["runstate"] = status_mapping.get(self.get_status())
        except:
            self.logger.warning("", exc_info=True)

        return info

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "network.loadbalancers": 1,
        }
        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return self.info()

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
        return kvargs

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        pass

    @staticmethod
    def __target_type_mapping(target_type):
        mapping = {
            "vm": ComputeInstance,
        }
        return mapping.get(target_type)

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
        :param kvargs.orchestrator_tag: orchestrators tag [default=default]
        :param kvargs.type: orchestrator type. Ex. vsphere|pfsense
        :return: dict
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get("type", "vsphere")
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")
        compute_zone_id = kvargs.get("parent")
        is_private = kvargs.get("is_private")
        site_id = kvargs.get("site")
        site_network_name = kvargs.get("site_network")
        gateway_uuid = kvargs.get("gateway")
        multi_avz = kvargs.get("multi_avz", False)
        vpc_id = kvargs.get("vpc")
        lb_configs = kvargs.get("lb_configs")
        target_type = dict_get(lb_configs, "target_group.target_type")
        targets = dict_get(lb_configs, "target_group.targets")
        static_ip = dict_get(lb_configs, "static_ip")
        selection_criteria = kvargs.get("selection_criteria")
        deployment_env = lb_configs.get("deployment_env")

        controller: ResourceController

        name = kvargs.get("name")
        desc = kvargs.get("desc")
        lb_configs.update({"name": name, "desc": desc})

        # get compute zone
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)

        lb_configs["is_private"] = is_private

        # get vpc
        if vpc_id is not None:
            vpc: Vpc = controller.get_simple_resource(vpc_id)
            private_master_subnet = ComputeLoadBalancer.get_private_master_subnet(vpc)
            interpod_subnet = ComputeLoadBalancer.get_interpod_subnet(compute_zone)
            lb_configs["private_master_subnet"] = private_master_subnet
            lb_configs["interpod_subnet"] = interpod_subnet

        # get site
        site = controller.get_simple_resource(site_id)

        # get availability zone
        main_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        entity_class = ComputeLoadBalancer.__target_type_mapping(target_type)
        for target in targets:
            # get compute resource
            compute_resource = controller.get_resource(target.get("resource_uuid"), entity_class=entity_class)

            # get ip address and fqdn
            ip_addr = compute_resource.get_ip_address()
            fqdn = compute_resource.get_fqdn()

            # get hypervisor on which the physical resource is located
            hypervisor = compute_resource.get_hypervisor()
            if hypervisor not in ["vsphere", "openstack"]:
                raise ApiManagerError("Unknown hypervisor: %s" % hypervisor)

            # get logical resource in main zone
            zone_resource = compute_resource.get_main_zone_instance()

            # get physical resource depending on hypervisor
            if hypervisor == "vsphere":
                physical_resource = zone_resource.get_physical_resource(VsphereServer.objdef)
            else:  # hypervisor == 'openstack'
                physical_resource = zone_resource.get_physical_resource(NsxIpSet.objdef)

            # get physical resource id a.k.a. ext_id
            ext_id = physical_resource.ext_id

            # update target info
            target.update({"ip_addr": ip_addr, "fqdn": fqdn, "ext_id": ext_id})

        # init helper
        helper = compute_zone.get_network_appliance_helper(orchestrator_type, controller, site)

        # select network appliance
        net_appl = helper.select_network_appliance(
            site.oid,
            site_network_name,
            gateway_uuid,
            selection_criteria=selection_criteria,
            deployment_env=deployment_env,
        )
        logger.info("Selected network appliance: %s" % net_appl.uuid)
        kvargs["lb_configs"].update(
            {
                "network_appliance": {
                    "uuid": net_appl.uuid,
                    "ext_id": net_appl.ext_id,
                }
            }
        )

        # get uplink vnic
        uplink_vnic = helper.get_uplink_vnic(net_appl.uuid, site_network_name)

        # get uplink vnic primary ip
        primary_ip = helper.get_vnic_primary_ip(uplink_vnic)
        logger.info("Network appliance %s uplink vnic primary ip: %s" % (net_appl.uuid, primary_ip))

        # look for an unallocated ip address to reserve for load balancer
        reserved_ip = helper.reserve_ip_address(site.oid, site_network_name, gateway_uuid, static_ip)
        logger.info("Reserved ip address for load balancer frontend: %s" % reserved_ip)
        kvargs["lb_configs"].update({"vip": reserved_ip})

        params = {
            "orchestrator_tag": orchestrator_tag,
            "compute_zone": compute_zone.oid,
            "availability_zone": main_availability_zone,
            "multi_avz": multi_avz,
            "attribute": {
                "orchestrator_type": orchestrator_type,
                "site": site.oid,
                "vip": reserved_ip.get("ip"),
                "is_static": reserved_ip.get("is_static"),
                "balanced_targets": [
                    {
                        "uuid": target.get("resource_uuid"),
                        "ip_addr": target.get("ip_addr"),
                    }
                    for target in targets
                ],
                "network_appliance": {
                    "uuid": net_appl.uuid,
                    "name": net_appl.name,
                },
                "helper_class": helper.__class__.__module__ + "." + helper.__class__.__name__,
                "imported": False,
                "configs": {},
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeLoadBalancer.task_path + "create_resource_pre_step",
            {
                "step": ComputeLoadBalancer.task_path + "create_zone_load_balancer_step",
                "args": [main_availability_zone],
            },
            ComputeLoadBalancer.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import.
           This function is used in container resource_import_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom positional params
        :param kvargs: custom key-value params
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        attribs = kvargs.get("attribute", {})
        compute_zone_id = attribs.get("compute_zone")
        site_network_name = attribs.get("site_network")
        multi_avz = attribs.get("multi_avz", False)

        lb_configs = kvargs.pop("configs", {})
        network_appliance = lb_configs.get("network_appliance")
        tags = network_appliance.pop("tags", None)
        targets = dict_get(lb_configs, "target_group.member")
        if not isinstance(targets, list):
            targets = [targets]
        vip = dict_get(lb_configs, "virtual_server.ipAddress")
        static_ip = dict_get(lb_configs, "virtual_server.is_vip_static")

        orchestrator_type = kvargs.get("type", network_appliance.get("type"))

        # set description
        kvargs.update({"desc": kvargs.get("name")})

        # get parent compute zone and set objid
        from beehive_resource.plugins.provider.entity.zone import ComputeZone

        compute_zone: ComputeZone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        kvargs["parent"] = compute_zone.oid
        kvargs["objid"] = "%s//%s" % (compute_zone.objid, id_gen())

        # get site
        site_network = controller.get_simple_resource(site_network_name)
        site = site_network.get_parent()
        lb_configs["site"] = site.oid

        # get availability zone
        main_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        # init helper
        helper = compute_zone.get_network_appliance_helper(orchestrator_type, controller, site)
        helper_class = helper.__class__.__module__ + "." + helper.__class__.__name__
        lb_configs["helper_class"] = helper_class

        params = {
            "orchestrator_tag": orchestrator_tag,
            "compute_zone": compute_zone.oid,
            "availability_zone": main_availability_zone,
            "multi_avz": multi_avz,
            "attribute": {
                "orchestrator_type": orchestrator_type,
                "site": site.oid,
                "vip": vip,
                "is_static": static_ip,
                "balanced_targets": [
                    {
                        "uuid": target.get("resource_uuid"),
                        "ip_addr": target.get("ipAddress"),
                    }
                    for target in targets
                ],
                "network_appliance": network_appliance,
                "helper_class": helper_class,
                "has_quotas": True,
                "imported": True,
            },
            "configs": lb_configs,
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeLoadBalancer.task_path + "create_resource_pre_step",
            {
                "step": ComputeLoadBalancer.task_path + "import_zone_load_balancer_step",
                "args": [main_availability_zone],
            },
            ComputeLoadBalancer.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom positional params
        :param kvargs: custom key-value params
        :return: kvargs
        :raise ApiManagerError:
        """
        site_id = self.get_attribs().get("site")
        lb_configs = kvargs.get("lb_configs")
        target_type = dict_get(lb_configs, "target_group.target_type")

        targets = lb_configs.get("target_group").pop("targets", [])
        cur_balanced_targets = self.get_attribs(key="balanced_targets")

        # determine targets to add to and to remove from target group
        targets = {item.get("resource_uuid"): item for item in targets}
        cur_balanced_targets = {item.get("uuid"): item for item in cur_balanced_targets}
        targets_to_add = []
        targets_to_del = []
        a_list = list(cur_balanced_targets.keys())
        if sorted(targets.keys()) != sorted(cur_balanced_targets.keys()):
            for target_k, target_v in cur_balanced_targets.items():
                if target_k not in targets.keys():
                    targets_to_del.append(target_v)
                    a_list.remove(target_k)
            for target_k, target_v in targets.items():
                if target_k not in cur_balanced_targets.keys():
                    targets_to_add.append(target_v)
                    a_list.append(target_k)

        entity_class = ComputeLoadBalancer.__target_type_mapping(target_type)

        new_balanced_targets = []
        for item in a_list:
            self.controller: ResourceController
            compute_resource = self.controller.get_resource(item, entity_class=entity_class)
            ip_addr = compute_resource.get_ip_address()
            new_balanced_targets.append({"uuid": item, "ip_addr": ip_addr})

        for target in targets_to_add:
            # get compute resource
            compute_resource = self.controller.get_resource(target.get("resource_uuid"), entity_class=entity_class)

            # get ip address and fqdn
            ip_addr = compute_resource.get_ip_address()
            fqdn = compute_resource.get_fqdn()

            # get hypervisor on which the physical resource is located
            hypervisor = compute_resource.get_hypervisor()
            if hypervisor not in ["vsphere", "openstack"]:
                raise ApiManagerError("Unknown hypervisor: %s" % hypervisor)

            # get logical resource in main zone
            zone_resource = compute_resource.get_main_zone_instance()

            # get physical resource depending on hypervisor
            if hypervisor == "vsphere":
                physical_resource = zone_resource.get_physical_resource(VsphereServer.objdef)
            else:  # hypervisor == 'openstack'
                physical_resource = zone_resource.get_physical_resource(NsxIpSet.objdef)

            # get physical resource id a.k.a. ext_id
            ext_id = physical_resource.ext_id

            # update target info
            target.update({"ip_addr": ip_addr, "fqdn": fqdn, "ext_id": ext_id})

        dict_set(lb_configs, "target_group.targets_to_add", targets_to_add)
        dict_set(lb_configs, "target_group.targets_to_del", targets_to_del)
        dict_set(lb_configs, "target_group.tot_cur_balanced_target", len(cur_balanced_targets))
        self.logger.debug("Targets to add to target group: %s" % targets_to_add)
        self.logger.debug("Targets to remove from target group: %s" % targets_to_add)

        # generate task workflow
        steps = [
            ComputeLoadBalancer.task_path + "update_resource_pre_step",
            {
                "step": ComputeLoadBalancer.task_path + "update_load_balancer_step",
                "args": [site_id, new_balanced_targets],
            },
            ComputeLoadBalancer.task_path + "update_resource_post_step",
        ]
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
        # get related entities
        entities, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [e.oid for e in entities]

        # create task workflow
        steps = [ComputeLoadBalancer.task_path + "expunge_resource_pre_step"]
        # remove childs
        for child in childs:
            steps.extend(
                [
                    {
                        "step": ComputeLoadBalancer.task_path + "delete_load_balancer_step",
                        "args": [child],
                    }
                ]
            )
        steps.append(ComputeLoadBalancer.task_path + "expunge_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    def action(self, action, *args, **kvargs):
        """Run an action

        :param action: action name
        :param args: custom positional params
        :param kvargs: custom key=value params
        :return: dict
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        # clean cache
        self.clean_cache()

        # create task workflow
        steps = [
            ComputeLoadBalancer.task_path + "action_resource_pre_step",
            ComputeLoadBalancer.task_path + "run_action_step",
            ComputeLoadBalancer.task_path + "action_resource_post_step",
        ]

        # manage params
        params = {
            "cid": self.container_id,
            "id": self.oid,
            "objid": self.objid,
            "ext_id": self.ext_id,
            "action_name": action,
            "steps": steps,
            # 'alias': '%s.%s' % (self.__class__.__name__, action),
        }
        params.update(kvargs)
        params.update(self.get_user())
        res = prepare_or_run_task(self, self.action_task, params, sync=False)
        self.logger.info("Run action '%s' on load balancer %s" % (action, self.uuid))
        return res


class LoadBalancer(AvailabilityZoneChildResource):
    """Availability Zone Instance"""

    objdef = "Provider.Region.Site.AvailabilityZone.LoadBalancer"
    objuri = "%s/loadlalancers/%s"
    objname = "load_balancer"
    objdesc = "Provider Availability Zone Load Balancer"
    task_path = "beehive_resource.plugins.provider.task_v2.load_balancer.LoadBalancerTask."

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
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.role: gateway role. Can be: primary, secondary or backup
        :param kvargs.uplink_network: uplink network
        :param kvargs.uplink_subnet: uplink subnet
        :param kvargs.transport_network: transport network
        :param kvargs.transport_subnet: transport subnet
        :param kvargs.admin_pwd: admin password
        :param kvargs.dns: dns list
        :param kvargs.dns_search: dns zone
        :param kvargs.flavor: server flavor
        :param kvargs.volume_flavor: volume flavor
        :param kvargs.orchestrator_tag: orchestrator tag [default=default]
        :param kvargs.type: orchestrator type. Can be: vsphere, pfsense
        :param kvargs.ip_address: uplink ip address [optional]
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get("orchestrator_type")

        # create task workflow
        steps = [
            LoadBalancer.task_path + "create_resource_pre_step",
            {
                "step": LoadBalancer.task_path + "create_load_balancer_physical_resource_step",
                "args": [orchestrator_type],
            },
            LoadBalancer.task_path + "create_resource_post_step",
        ]

        kvargs["steps"] = steps
        kvargs["sync"] = True
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args:
        :param kvargs:
        :return:
        """
        steps = [
            LoadBalancer.task_path + "update_resource_pre_step",
            LoadBalancer.task_path + "update_zone_load_balancer_step",
            LoadBalancer.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used
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
        :param kvargs.ext_id: resource id to import [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :return: kvargs
        :raise ApiManagerError:
        """
        # create task workflow
        steps = [
            LoadBalancer.task_path + "create_resource_pre_step",
            LoadBalancer.task_path + "import_physical_load_balancer_step",
            LoadBalancer.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True

        return kvargs
