# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from datetime import datetime
from random import randint
from beecell.simple import format_date, id_gen
from beedrones.ontapp.volume import OntapVolume
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.ontap import OntapNetappContainer
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource


class ComputeFileShareV2(ComputeProviderResource):
    """Compute file share like nfs or cifs"""

    objdef = "Provider.ComputeZone.ComputeFileShareV2"
    objuri = "%s/shares/%s"
    objname = "share"
    objdesc = "Provider ComputeFileShare V2"
    task_path = "beehive_resource.plugins.provider.task_v2.share_v2.ComputeFileShareV2Task."

    protos = ["nfs", "cifs"]
    snapshot_policies = ["staas_snap_8h_7d_14w"]

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
                "ontap_volume": self.get_attribs(key="ontap_volume"),  # TODO check
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
                # "grants": self.grant_list(),
                "netapp_volume": self.get_attribs(key="netapp_volume"),  # TODO check
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
        # self.logger.debug2("Get compute share availability zones: %s" % self.availability_zone)
        self.logger.error("Get compute share availability zones: %s" % self.availability_zone_id)  # TODO warning
        # get main zone instance
        res = self.controller.get_directed_linked_resources_internal(resources=[self.oid], link_type="relation%")
        for resource, zone_insts in res.items():
            for zone_inst in zone_insts:
                if zone_inst.get_attribs().get("main", False) is True:
                    self.main_zone_share = zone_inst
        self.logger.debug2("Get compute share main zone instance: %s" % self.main_zone_share)
        self.logger.error("Get compute share main zone instance: %s" % self.main_zone_share)

        # set physical_server
        if self.main_zone_share is not None:
            self.physical_share = self.main_zone_share.get_physical_share()
        self.logger.debug2("Get physical share: %s" % self.physical_share)
        self.logger.error("Get physical share: %s" % self.physical_share)

        # get other linked entities
        objdefs = [Vpc.objdef]
        linked = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], objdefs=objdefs, run_customize=False
        )
        self.logger.debug2("Get compute share linked entities: %s" % linked)
        self.logger.error("Get compute share linked entities: %s" % linked)

        for entity in linked.get(self.oid, []):
            if isinstance(entity, Vpc):
                self.vpcs.append(entity)

    from beehive_resource.controller import ResourceController

    @staticmethod
    def pre_create(controller: ResourceController, container, *args, **kwargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kwargs: custom params
        :param kwargs.objid: resource objid
        :param kwargs.parent: resource parent id [default=None]
        :param kwargs.cid: container id
        :param kwargs.name: resource name
        :param kwargs.desc: resource desc
        :param kwargs.ext_id: resource ext_id [default=None]
        :param kwargs.active: resource active [default=False]
        :param kwargs.attribute: attributes [default={}]
        :param kwargs.tags: comma separated resource tags to assign [default='']
        :param kwargs.type: orchestrator type. Ex. vsphere|openstack|ontap [default='openstack']
        :param kwargs.compute_zone: parent compute zone id or uuid
        :param kwargs.network: vpc id or uuid or name
        :param kwargs.subnet: subnet cidr [optional]
        :param kwargs.size: share size in GB
        :param kwargs.availability_zone: site id or uuid
        :param kwargs.multi_avz: if True deploy instance over all the active availability zones
        :param kwargs.share_proto: shared file Systems protocol
        :param kwargs.share_label: shared file Systems label [optional]
        :param kwargs.share_volume: existing ontap volume physical id [optional]
        :param kwargs.orchestrator_tag: orchestrators tag
        :return: dict
        :raise ApiManagerError:
        """
        name = kwargs.get("name")
        desc = kwargs.get("desc", name)
        compute_zone = container.get_resource(kwargs.get("parent"))

        orchestrator_type = kwargs.get("type", "ontap")
        orchestrator_tag = kwargs.get("orchestrator_tag")

        if orchestrator_type == "ontap":
            share_params = kwargs.get("ontap_share_params")
        else:
            raise Exception("Unsupported orchestrator type %s" % orchestrator_type)

        share_svm = share_params.get("svm")
        share_proto = share_params.get("share_proto")
        size = int(share_params.get("size", 0))
        # snapshot_policy = share_params.get("snapshot_policy")

        site = kwargs.get("site")
        clients = share_params.pop("clients")
        if clients is None:
            raise Exception("At least one client must be given in parameter 'clients'")

        client_fqdn = []
        from beehive_resource.plugins.provider.entity.instance import ComputeInstance

        for client in clients:
            res = controller.get_resource(client, ComputeInstance)
            client_site = res.availability_zone.name
            if client_site != site:
                raise Exception(f"Incorrect site for client {client}: expected {site} but was {client_site}")
            # avz_client.append(res.main_zone_instance.oid)
            client_fqdn.append(res.fqdn)

        # share_params["avz_client"] = avz_client
        share_params["client_fqdn"] = client_fqdn

        awx_orchestrator_tag = kwargs.get("awx_orchestrator_tag", "V2")
        ####################################################################
        ## SCOMMENTARE A FINE SVILUPPO
        # # check quotas are not exceed
        # new_quotas = {
        #     'share.instances': 1,
        #     'share.blocks': size
        # }
        # compute_zone.check_quotas(new_quotas)

        # build share name
        # name = (f"{share_svm}-{name}-{id_gen(8)}".replace("-", "_"))

        # get compute site
        site = container.get_resource(kwargs.get("site"))

        # get availability zone
        availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        ####################################################################
        ## SPOSTARE SOTTO PLUGIN ONTAP
        # get and select aggregate
        # orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=[orchestrator_type])
        # orchestrator = next(iter(orchestrators.keys()))
        # from beehive_resource.plugins.ontap.controller import OntapNetappContainer
        # ontap_container: OntapNetappContainer = controller.get_container(orchestrator, connect=False)
        # ontap_container.get_connection()
        # aggregates = ontap_container.conn.aggregate.list()
        # print(f"____aggregates={aggregates}")

        # share_compliance = False
        # if snaplock_cluster is not None and snaplock_svm is not None:
        #    share_compliance = True

        # set params
        share_params["vol_name"] = name  # set aside for later use
        params = {
            "name": f"{share_svm}-{name}-{id_gen(6)}",
            "desc": desc,
            "compute_zone": compute_zone.oid,
            "availability_zone": availability_zone,
            # "share_compliance": share_compliance,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                "size": size,
                "proto": share_proto,
                # "snapshot_policy": snapshot_policy,
            },
            "awx_orchestrator_tag": awx_orchestrator_tag,
            "share_params": share_params,
        }
        kwargs.update(params)

        # create task workflow
        steps = [
            ComputeFileShareV2.task_path + "create_resource_pre_step",
            {
                "step": ComputeFileShareV2.task_path + "create_zone_share_step",
                "args": [availability_zone],
            },
            ComputeFileShareV2.task_path + "create_resource_post_step",
        ]
        kwargs["steps"] = steps

        return kwargs

    # TODO temporarily removed other methods. restore after creation OK


class FileShareV2(AvailabilityZoneChildResource):
    """Availability Zone File Share"""

    objdef = "Provider.Region.Site.AvailabilityZone.FileShareV2"
    objuri = "%s/shares/%s"
    objname = "share"
    objdesc = "Provider Availability Zone File Share V2"
    task_path = "beehive_resource.plugins.provider.task_v2.share_v2.ComputeFileShareV2Task."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

        self.__internal_share = None  # TODO controlla chi assegna questo valore

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
    def pre_create(controller, container, *args, **kwargs):
        """Check input kvargs before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom args (empty)
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
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.orchestrator_type: orchestrator type. e.g. ontap
        :param kvargs.compute_zone: parent compute_zone
        :param kvargs.orchestrators:
        :param kvargs.main_orchestrator:
        :raise ApiManagerError:
        """
        avz_id = kwargs.get("parent")
        orchestrator_tag = kwargs.pop("orchestrator_tag")
        orchestrator_type = kwargs.pop("orchestrator_type")
        share_params = kwargs.get("share_params")

        # get availability_zone
        from beehive_resource.plugins.provider.entity.site import Site

        avz: Site = container.get_simple_resource(avz_id)

        # select remote orchestrator with the same name as the cluster
        orchestrators = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=[orchestrator_type])
        orchestrators = list(orchestrators.values())
        if orchestrator_type != "ontap":
            orchestrator = orchestrators[0]  # legacy support
        else:
            orchestrator = None
            orchestrator_name = share_params.get("cluster")
            for orch in orchestrators:
                container = controller.get_container(orch.get("id"), connect=False, cache=False)
                if container.name == orchestrator_name:
                    orchestrator = orch
                    kwargs["share_params"]["cluster"] = container.conn_params.get("host")

            if orchestrator is None:
                raise Exception(
                    "No valid zone orchestrator found (tag: %s - name: %s)" % (orchestrator_tag, orchestrator_name)
                )

            snaplock_orchestrator = None
            snaplock_orchestrator_name = share_params.get("snaplock_cluster")
            """
            elif snaplock_orchestrator_name is not None and container.name==snaplock_orchestrator_name:
                    snaplock_orchestrator = orch
                    kwargs["share_params"]["snaplock_cluster"] = container.conn_params.get("host")

            if snaplock_orchestrator_name is not None and snaplock_orchestrator is None:
                raise Exception("No valid ")
            """
            if snaplock_orchestrator_name is not None:
                # TODO for now:
                kwargs["share_params"]["snaplock_cluster"] = f"{snaplock_orchestrator_name}.csi.it"

        kwargs.update({"orchestrator": orchestrator})
        # update cluster e.g. faspod1 -> faspod1.csi.it

        steps = [
            FileShareV2.task_path + "create_resource_pre_step",
            FileShareV2.task_path + "create_physical_share_step",
            # FileShareV2.task_path + "link_share_step",
            FileShareV2.task_path + "create_resource_post_step",
        ]
        kwargs["steps"] = steps
        kwargs["sync"] = True

        return kwargs

    # TODO temporarily removed other methods. restore after creation OK    @staticmethod
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


#    def post_get(self):
#        """Post get function. This function is used in get_entity method.
#        Extend this function to extend description info returned after query.#
#
#        :return: None
#        :raise ApiManagerError:
#        """
#        pass
