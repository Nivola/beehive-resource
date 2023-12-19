# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from datetime import datetime
from random import randint
from beecell.simple import format_date, id_gen
from beedrones.ontapp.volume import OntapVolume
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.vpc_v2 import (
    Vpc,
    PrivateNetwork,
    SiteNetwork,
)
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource


class ComputeFileShare(ComputeProviderResource):
    """Compute file share like nfs or cifs"""

    objdef = "Provider.ComputeZone.ComputeFileShare"
    objuri = "%s/shares/%s"
    objname = "share"
    objdesc = "Provider ComputeFileShare"
    task_path = "beehive_resource.plugins.provider.task_v2.share.ComputeFileShareTask."

    protos = ["nfs", "cifs"]

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.availability_zone = None
        self.main_zone_share = None
        self.physical_share = None
        self.vpcs = []

        try:
            self.availability_zone_id = self.get_attribs().get("availability_zone", None)
        except:
            self.availability_zone_id = None

        self.actions = [
            "extend",
            "shrink",
        ]

    def get_size(self):
        return self.get_attribs(key="size")

    def get_hypervisor(self):
        hypervisor = self.get_attribs(key="type")
        return hypervisor

    def get_hypervisor_tag(self):
        hypervisor = self.get_attribs().get("orchestrator_tag", "default")
        return hypervisor

    def get_type(self):
        return self.get_attribs(key="orchestrator_type")

    def __get_availability_zone_info(self, info):
        if self.availability_zone is not None:
            info["availability_zone"] = self.availability_zone.small_info()
        else:
            info["availability_zone"] = {}
        return info

    def __get_network_info(self, info):
        info["vpcs"] = []
        for vpc in self.vpcs:
            info["vpcs"].append({"uuid": vpc.uuid, "name": vpc.name})
        return info

    def info(self):
        """Get infos.

        :return: dict
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeProviderResource.info(self)
        info = self.__get_availability_zone_info(info)
        info = self.__get_network_info(info)
        info.pop("attributes")
        exports = self.get_attribs().get("exports", [])
        export = None
        if len(exports) > 0:
            export = exports[0]
        info["details"].update(
            {
                "size": self.get_attribs(key="size"),
                "type": self.get_attribs(key="type"),
                "export": export,
                "proto": self.get_attribs(key="proto"),
                "subnet": self.get_attribs(key="subnet"),
                "ontap_volume": self.get_attribs(key="ontap_volume"),
            }
        )
        return info

    def detail(self):
        """Get details.

        :return: dict
        :raise ApiManagerError:
        """
        info = ComputeProviderResource.detail(self)
        info = self.__get_availability_zone_info(info)
        info = self.__get_network_info(info)
        info.pop("attributes")
        exports = self.get_attribs().get("exports", [])
        export = None
        if len(exports) > 0:
            export = exports[0]
        info["details"].update(
            {
                "size": self.get_attribs(key="size"),
                "type": self.get_attribs(key="type"),
                "export": export,
                "proto": self.get_attribs(key="proto"),
                "subnet": self.get_attribs(key="subnet"),
                "grants": self.grant_list(),
                "netapp_volume": self.get_attribs(key="netapp_volume"),
            }
        )
        return info

    # def check(self):
    #     """Check resource
    #
    #     :return: True if check is ok
    #     :raises ApiManagerError: raise :class:`.ApiManagerError`
    #     """
    #     res = False
    #     if self.physical_server is not None and self.physical_server.check() is True:
    #         res = True
    #     self.logger.debug('Check resource %s: %s' % (self.uuid, res))
    #     return res

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
        resource_idx = {}
        resource_ids = []
        for e in entities:
            resource_idx[e.oid] = e
            resource_ids.append(e.oid)

        # get main availability zones
        zone_idx = controller.index_resources_by_id(entity_class=Site)
        for entity in entities:
            if entity.availability_zone_id is not None:
                entity.availability_zone = zone_idx.get(entity.availability_zone_id)
        controller.logger.debug2("Get compute share availability zones")

        # get main zone instance
        res = controller.get_directed_linked_resources_internal(
            resources=resource_ids, link_type="relation%", run_customize=False
        )
        controller.logger.debug2("Get compute share main zone share")

        # get physical share list
        zone_insts_ids = []
        for items in res.values():
            zone_insts_ids.extend([item.oid for item in items])

        controller.logger.debug2("Get zone instance physical share")
        objdefs = [OpenstackShare.objdef]
        remote_servers = controller.get_directed_linked_resources_internal(
            resources=zone_insts_ids,
            link_type="relation",
            objdefs=objdefs,
            run_customize=True,
            customize_func="customize_list",
        )
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    physical_shares = remote_servers.get(zone_inst.oid, [])
                    resource_idx[resource].main_zone_share = zone_inst
                    resource_idx[resource].physical_server_status = None
                    if len(physical_shares) > 0 and physical_shares[0] is not None:
                        resource_idx[resource].physical_share = physical_shares[0]

        # get other linked entities
        controller.logger.debug2("Get compute instance linked entities")
        objdefs = [Vpc.objdef]
        linked = controller.get_directed_linked_resources_internal(
            resources=resource_ids, objdefs=objdefs, run_customize=False
        )

        for resource, enitities in linked.items():
            res = resource_idx[resource]
            for entity in enitities:
                if isinstance(entity, Vpc):
                    res.vpcs.append(entity)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        # get main availability zones
        if self.availability_zone_id is not None:
            self.availability_zone = self.controller.get_resource(self.availability_zone_id, run_customize=False)
        self.logger.debug2("Get compute share availability zones: %s" % self.availability_zone)
        self.logger.warn("Get compute share availability zones: %s" % self.availability_zone_id)
        # get main zone instance
        res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    self.main_zone_share = zone_inst
        self.logger.debug2("Get compute share main zone instance: %s" % self.main_zone_share)

        # set physical_server
        if self.main_zone_share is not None:
            self.physical_share = self.main_zone_share.get_physical_share()
        self.logger.debug2("Get physical share: %s" % self.physical_share)

        # get other linked entities
        objdefs = [Vpc.objdef]
        linked = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], objdefs=objdefs, run_customize=False
        )
        self.logger.debug2("Get compute share linked entities: %s" % linked)

        for entity in linked.get(self.oid, []):
            if isinstance(entity, Vpc):
                self.vpcs.append(entity)

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
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack|ontap [default='openstack']
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.network: vpc id or uuid or name
        :param kvargs.subnet: subnet cidr [optional]
        :param kvargs.size: share size in GB
        :param kvargs.availability_zone: site id or uuid
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones
        :param kvargs.share_proto: shared file Systems protocol
        :param kvargs.share_label: shared file Systems label [optional]
        :param kvargs.share_volume: existing ontap volume physical id [optional]
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: dict
        :raise ApiManagerError:
        """
        # get compute zone
        compute_zone = container.get_resource(kvargs.get("parent"))
        multi_avz = kvargs.get("multi_avz")
        network = kvargs.get("network")
        subnet = kvargs.get("subnet")
        size = int(kvargs.get("size", 0))
        share_proto = kvargs.get("share_proto")
        share_label = kvargs.get("share_label")
        share_volume = kvargs.get("share_volume", None)
        orchestrator_type = kvargs.get("type", "openstack")
        orchestrator_tag = kvargs.get("orchestrator_tag", "default")

        # check quotas are not exceed
        # new_quotas = {
        #     'share.instances': 1,
        #     'share.blocks': size
        # }
        # compute_zone.check_quotas(new_quotas)

        # get compute site
        site = container.get_resource(kvargs.get("availability_zone"))

        # get main availability zone
        main_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        # get availability zones ACTIVE
        availability_zones = []
        if multi_avz is True:
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
            availability_zones.remove(main_availability_zone)

        # get vpc
        vpc = container.get_resource(network, entity_class=Vpc)
        if vpc.parent_id != compute_zone.oid:
            raise ApiManagerError("Vpc %s is not in compute zone %s" % (network, compute_zone.uuid))

        # if vpc is private check subnet field
        if vpc.is_private() is True:
            # get vpc zone network
            vpc_nets, total = vpc.get_linked_resources(link_type="relation.%s" % site.oid, objdef=PrivateNetwork.objdef)
            vpc_net = vpc_nets[0]

            # check subnet is defined
            if subnet is None:
                raise ApiManagerError("subnet must be defined for private vpc")

            # check subnet is allocable
            if subnet != vpc_net.get_cidr():
                raise ApiManagerError("subnet %s does not exist in private vpc %s" % (subnet, network))

            vlan = None

        elif vpc.is_shared() is True:
            # get vpc zone network
            vpc_nets, total = vpc.get_linked_resources(link_type="relation.%s" % site.oid, objdef=SiteNetwork.objdef)
            vpc_net = vpc_nets[0]

            # get network vlan
            attrib = vpc_net.attribs["configs"]
            vlan = attrib.get("vlan", "")
        else:
            raise ApiManagerError("vpc %s is not private or shared" % vpc)

        # set params
        params = {
            "orchestrator_tag": orchestrator_tag,
            "orchestrator_type": orchestrator_type,
            "compute_zone": compute_zone.oid,
            "main_availability_zone": main_availability_zone,
            # 'availability_zones': availability_zones,
            "network": {
                "vpc": vpc.oid,
                "vlan": vlan,
                "subnet": subnet,
                "label": share_label,
            },
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                "size": size,
                "proto": share_proto,
                "subnet": subnet,
            },
        }
        if orchestrator_type == "ontap":
            if share_volume is None:
                raise ApiManagerError("ontap orchestrator requires share_volume param is configured")
            params["attribute"]["ontap_volume"] = share_volume

        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeFileShare.task_path + "create_resource_pre_step",
            ComputeFileShare.task_path + "create_compute_share_link_step",
            {
                "step": ComputeFileShare.task_path + "create_zone_share_step",
                "args": [main_availability_zone, True],
            },
        ]

        for zone_id in availability_zones:
            step = {
                "step": ComputeFileShare.task_path + "create_zone_share_step",
                "args": [zone_id, False],
            }
            steps.append(step)

        steps.append(ComputeFileShare.task_path + "create_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used in container resource_import_factory method.

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
        :return: extended kvargs
        :raise ApiManagerError:
        """
        physical_id = kvargs.get("physical_id")
        params = kvargs.get("configs", {})

        # check share type from ext_id
        share = controller.get_resource(physical_id)
        if isinstance(share, OpenstackShare) is True:
            orchestrator_type = "openstack"
        # elif isinstance(server, VsphereServer) is True:
        #     orchestrator_type = 'vsphere'
        else:
            raise ApiManagerError("ComputeFileShare require Openstack share as physical_id")

        # check parent compute zone match share parent
        project_id = share.parent_id
        parent = container.get_aggregated_resource_from_physical_resource(project_id)
        parent.set_container(container)
        kvargs["objid"] = "%s//%s" % (parent.objid, id_gen())
        kvargs["parent"] = parent.oid
        compute_zone = parent

        # get resource to import
        resource = controller.get_resource(physical_id)
        size = resource.get_size()
        proto = resource.get_proto()
        metadata = {}
        orchestrator_tag = None
        multi_avz = False

        # get main availability zone
        main_availability_zone = container.get_availability_zone_from_physical_resource(project_id)
        site = main_availability_zone.get_parent()
        main_availability_zone = main_availability_zone.oid
        multi_avz = params.get("multi_avz", True)

        # get availability zones ACTIVE
        availability_zones = []
        if multi_avz is True:
            availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)
            availability_zones.remove(main_availability_zone)

        # get share network
        ops_share_network = resource.get_network()
        vpc = container.get_aggregated_resource_from_physical_resource(ops_share_network.oid)
        vlan = ops_share_network.get_vlan()

        # check quotas are not exceed for imported share
        new_quotas = {"share.instances": 1, "share.blocks": int(size)}
        compute_zone.check_quotas(new_quotas)

        # set params
        params = {
            "orchestrator_tag": orchestrator_tag,
            "type": orchestrator_type,
            "compute_zone": compute_zone.oid,
            "main_availability_zone": main_availability_zone,
            "network": {"vpc": vpc.oid, "vlan": vlan},
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                "size": size,
                "proto": proto,
            },
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            ComputeFileShare.task_path + "create_resource_pre_step",
            ComputeFileShare.task_path + "create_compute_share_link_step",
            {
                "step": ComputeFileShare.task_path + "import_zone_share_step",
                "args": [main_availability_zone],
            },
            ComputeFileShare.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.size: share size in gb
        :param kvargs.grant: grant configuration
        :param kvargs.grant.access_level: The access level to the share: ro, rw
        :param kvargs.grant.access_type: The access rule type: ip, cert, user
        :param kvargs.grant.access_to: The value that defines the access.
            - ip. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0.
            - cert. A valid value is any string up to 64 characters long in the common name (CN) of the certificate.
            - user. A valid value is an alphanumeric string that can contain some special characters and is from
              4 to 32 characters long
        :param kvargs.grant.access_id: The UUID of the access rule to which access is granted.
        :param kvargs.grant.action: Set grant action: add or del
        :return: kvargs
        :raise ApiManagerError:
        """
        main_availability_zone = self.get_attribs().get("availability_zone")
        orchestrator_tag = self.get_attribs().get("orchestrator_tag")
        proto = self.get_attribs().get("proto")
        grant = kvargs.get("grant", None)
        new_size = kvargs.get("size", None)

        if new_size is not None and self.get_attribs().get("size") == new_size:
            kvargs.pop("size")
            new_size = None

        if self.get_type() == "ontap":
            if new_size is not None:
                raise ApiManagerError("change size is disabled for share of type ontap")
            if grant is not None:
                raise ApiManagerError("assign/deassign of grant is disabled for share of type ontap")

        # if grant is not None:
        #     if proto == 'nfs' and grant.get('action') == 'add' and grant.get('access_type') != 'ip':
        #         raise ApiManagerError('Only access_type=ip is supported for proto=nfs')
        #     elif proto == 'cifs' and grant.get('action') == 'add' and grant.get('access_type') != 'user':
        #         raise ApiManagerError('Only access_type=user is supported for proto=cifs')

        zone_shares, total = self.get_linked_resources(link_type_filter="relation%")

        # create task workflow
        steps = [ComputeFileShare.task_path + "update_resource_pre_step"]
        for zone_share in zone_shares:
            main = False
            if zone_share.parent_id == main_availability_zone:
                main = True
            subtask = {
                "step": ComputeFileShare.task_path + "update_zone_share_step",
                "args": [zone_share.oid, main],
            }
            steps.append(subtask)
        steps.append(ComputeFileShare.task_path + "update_resource_post_step")

        kvargs["steps"] = steps
        kvargs["attribute"] = self.get_attribs()

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
        # get instances
        shares, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [p.oid for p in shares]

        # create task workflow
        kvargs["steps"] = self.group_remove_step(childs)

        return kvargs

    def grant_list(self):
        """Get grant list

        :raise ApiManagerError:
        :return: grant list::

            {'SiteVercelli01': [
                {
                    "access_level": "rw",
                    "state": "error",
                    "id": "507bf114-36f2-4f56-8cf4-857985ca87c1",
                    "access_type": "cert",
                    "access_to": "example.com",
                    "access_key": null
                },..
            ]}
        """
        grants = {}
        if self.physical_share is not None:
            zone_name = self.availability_zone.name
            grants[zone_name] = self.physical_share.grant_list()

        self.logger.debug("Get compute share %s grants: %s" % (self.uuid, grants))
        return grants

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {"instances": 1, "blocks": self.get_size()}

        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

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
        # value for key are
        # - sd_gdisk_high: high performance
        # - sd_gdisk_low: low performance
        metrics = [{"key": "sd_gdisk_low", "value": self.get_size(), "type": 1, "unit": "GB"}]
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get compute file share %s metrics: %s" % (self.uuid, res))
        return res


class FileShare(AvailabilityZoneChildResource):
    """Availability Zone File Share"""

    objdef = "Provider.Region.Site.AvailabilityZone.FileShare"
    objuri = "%s/shares/%s"
    objname = "share"
    objdesc = "Provider Availability Zone File Share"
    task_path = "beehive_resource.plugins.provider.task_v2.share.ComputeFileShareTask."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

        self.__internal_share = None

    def detail(self):
        """Get remote share detail

        **Returns:**

        :raise ApiManagerError:
        """
        info = {}
        if self.__internal_share is not None:
            res = self.__internal_share.detail()
            self.logger.warning("$$$$ res %s" % res)
            info.update(
                {
                    "size": res.get("details", {}).get("size", 0),
                    "share_type": res.get("details", {}).get("share_type", ""),
                    "share_proto": res.get("details", {}).get("share_proto", ""),
                    "export_locations": res.get("details", {}).get("export_locations", []),
                }
            )
        return info

    def get_physical_share(self):
        """Get remote physical share from orchestrator

        :return: OpenstackShare instance or other
        """
        inst_type = self.get_attribs().get("type")
        if inst_type == "openstack":
            objdef = OpenstackShare.objdef
        elif inst_type == "ontap":
            objdef = OntapNetappVolume.objdef
        try:
            share = self.get_physical_resource(objdef)
        except:
            share = None
        return share

    def update_size(self, old_size, new_size):
        """Update share size

        :param old_size: original size in GB
        :param new_size: new size in GB
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        """
        res = {}
        remote_share = self.get_physical_share()
        if new_size > old_size:
            res = remote_share.size_extend({"new_size": new_size, "sync": True})
        elif new_size < old_size:
            res = remote_share.size_shrink({"new_size": new_size, "sync": True})

        return res

    def grant_list(self):
        """Get grant list

        :raise ApiManagerError:
        :return: grant list::

            [
                {
                    "access_level": "rw",
                    "state": "error",
                    "id": "507bf114-36f2-4f56-8cf4-857985ca87c1",
                    "access_type": "cert",
                    "access_to": "example.com",
                    "access_key": null
                },
                {
                    "access_level": "rw",
                    "state": "active",
                    "id": "a25b2df3-90bd-4add-afa6-5f0dbbd50452",
                    "access_type": "ip",
                    "access_to": "0.0.0.0/0",
                    "access_key": null
                }
            ]
        """
        remote_share = self.get_physical_share()
        res = remote_share.grant_list()

        return res

    def grant_set(self, params):
        """Set grant

        :param params: dict with params
        :param params.action: add to add grant, del to delete grant
        :param params.access_id: The UUID of the access rule to which access is granted. Use with action=del
        :param params.access_level: The access level to the share. To grant or deny access to a share, you specify one
            of the following share access levels: - rw. Read and write (RW) access. - ro. Read- only (RO) access.
            Use with action=add
        :param params.access_type: The access rule type. Use with action=add. A valid value for the share access rule
            type is one of the following values:
            - ip. Authenticates an instance through its IP address. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX.
              For example 0.0.0.0/0. - cert. Authenticates an instance through a TLS certificate. Specify the TLS
              identity as the IDENTKEY. A valid value is any string up to 64 characters long in the common name (CN) of
              the certificate. The meaning of a string depends on its interpretation.
            - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain some
              special characters and is from 4 to 32 characters long.
        :param params.access_to: The value that defines the access. Use with action=add. The back end grants or denies
            the access to it. A valid value is one of these values:
            - ip. Authenticates an instance through its IP address. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX.
              For example 0.0.0.0/0.
            - cert. Authenticates an instance through a TLS certificate. Specify the TLS identity as the IDENTKEY. A
              valid value is any string up to 64 characters long in the common name (CN) of the certificate. The meaning
              of a string depends on its interpretation.
            - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain some
              special characters and is from 4 to 32 characters long.
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        """
        res = {}
        remote_share = self.get_physical_share()
        action = params.pop("action", None)
        params["sync"] = True
        if action == "add":
            res = remote_share.grant_add(params)
        elif action == "del":
            res = remote_share.grant_remove(params)

        return res

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input kvargs before resource creation. This function is used
        in container resource_factory method.

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
        :param kvargs.attribute.main: if True set this as main zone share
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.size: share size, in GBs
        :param kvargs.network: network
        :param kvargs.network.vpc: vpc id
        :param kvargs.network.vlan: network vlan
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.orchestrator_type: orchestrator type. Ex. vsphere|openstack
        :param kvargs.compute_zone: parent compute_zone
        :param kvargs.orchestrators:
        :param kvargs.main_orchestrator:
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.pop("orchestrator_tag")
        orchestrator_type = kvargs.pop("orchestrator_type")
        main = kvargs.get("main")

        # get availability_zone
        availability_zone = controller.get_simple_resource(kvargs.get("parent"))

        # select remote orchestrators
        orchestrator_idx = availability_zone.get_orchestrators_by_tag(
            orchestrator_tag, select_types=["vsphere", "openstack", "ontap"]
        )
        # select main available orchestrators
        available_main_orchestrators = []
        for k, v in orchestrator_idx.items():
            if orchestrator_type == v["type"]:
                available_main_orchestrators.append(v)
        # main orchestrator is where instance will be created
        main_orchestrator = None
        if main is True:
            if len(available_main_orchestrators) > 0:
                index = randint(0, len(available_main_orchestrators) - 1)
                main_orchestrator = str(available_main_orchestrators[index]["id"])
            else:
                raise ApiManagerError("No available orchestrator exist where create share", code=404)

        # set container
        params = {
            "main_orchestrator": main_orchestrator,
            "orchestrators": orchestrator_idx,
        }
        kvargs.update(params)

        # create job workflow
        steps = [
            ComputeFileShare.task_path + "create_resource_pre_step",
            ComputeFileShare.task_path + "link_share_step",
            ComputeFileShare.task_path + "create_main_share_step",
            ComputeFileShare.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        kvargs["sync"] = True

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used
        in container resource_import_factory method.

        :param controller: resource controller volume
        :param container: container volume
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource id to import [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :param kvargs.main: if True this is the main volume [optional]
        :param kvargs.compute_share: compute share id
        :param kvargs.type: orchestrator type. Ex. vsphere|openstack [optional]
        :param kvargs.share_proto: share proto
        :param kvargs.size: share size in GB
        :param kvargs.network: network
        :param kvargs.network.vpc: vpc id
        :param kvargs.network.vlan: network vlan
        :return: extended kvargs
        :raise ApiManagerError:
        """
        # create job workflow
        steps = [
            ComputeFileShare.task_path + "create_resource_pre_step",
            ComputeFileShare.task_path + "link_share_step",
            ComputeFileShare.task_path + "import_main_share_step",
            ComputeFileShare.task_path + "create_resource_post_step",
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
        :param kvargs: custom params
        :return: entities
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return: None
        :raise ApiManagerError:
        """
        pass

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource physical id
        :return: kvargs
        :raise ApiManagerError:
        """
        # select physical orchestrators
        orchestrator_idx = self.get_orchestrators(select_types=["vsphere", "openstack", "ontap"])
        kvargs["steps"] = self.group_remove_step(orchestrator_idx)
        kvargs["sync"] = True
        return kvargs
