# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Literal, Tuple, TYPE_CHECKING, Optional, Union
from beecell.types.type_dict import dict_get
from beecell.simple import format_date
from beecell.types.type_id import id_gen
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.zone import (
    ComputeZone,
    AvailabilityZoneChildResource,
)

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController
    from beehive_resource.container import ResourceContainer
    from beehive_resource.plugins.provider.helper.share import AbstractProviderShareHelper
    from sqlalchemy.orm.session import Session
    from beehive_resource.container import ResourceLink
    from beehive_resource.plugins.ontap.controller import OntapNetappContainer
    from beehive_resource.typing_extras.share.view import CreateShareParams

class ComputeFileShareV2(ComputeProviderResource):
    """Compute file share like nfs or cifs"""

    objdef = "Provider.ComputeZone.ComputeFileShareV2"
    objuri = "%s/shares/%s"
    objname = "share"
    objdesc = "Provider ComputeFileShare V2"
    task_path = "beehive_resource.plugins.provider.task_v2.share_v2.ComputeFileShareV2Task."

    protocols = ["nfs", "cifs"]

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self._availability_zone: Optional['Site'] = None
        self._compliance_zone: Optional['Site'] = None

        self._main_zone_share: Optional['FileShareV2'] = None
        self._compliance_zone_share: Optional['FileShareV2'] = None

        self._main_physical_share: Optional['OntapNetappVolume'] = None

        self.availability_zone_id: Optional[Union[str, int]] = self.get_attribs("availability_zone", None)
        self.compliance_zone_id: Optional[Union[str, int]] = self.get_attribs("compliance_zone", None)

        self.actions = [
            "extend",
            "shrink",
            "mount",
            "grant_access",
            "revoke_access",
            "replica_suspend",
            "replica_resume",
            "replica_unlink",
            "replica_update",
            "set_online",
            "set_offline",
            "compliance_enable",
            "compliance_disable",
        ]

    def __ensure_is_replica(self):
        """raise exception if not a replica

        :raises Exception: if share role is not "replica"
        """
        if self.share_role!="replica":
            raise Exception("share role error: expected 'replica' but found '%s' for share %s" % (self.share_role,self.oid))

    def replica_get_source_share(self) -> 'ComputeFileShareV2':
        """if current share is a replica, return the source compute share
        NB: uses links as truth

        :raises Exception: if not a replica or if link missing or if more than one link
        :return: replica source compute share
        :rtype: 'ComputeFileShareV2'
        """
        self.__ensure_is_replica()

        instances, total = self.get_linked_resources(link_type="snapmirror", with_perm_tag=False)
        if total == 0:
            raise Exception("Detected misconfiguration: source share not set; check links")
        if total > 1:
            raise Exception("Detected misconfiguration: more than one source share instance")
        return instances[0]

    @property
    def share_role(self) -> str:
        return self.get_attribs("share_role")

    @property
    def availability_zone(self):
        if not self._availability_zone and self.availability_zone_id:
            self._availability_zone = self.controller.get_resource(self.availability_zone_id, entity_class=Site)
        return self._availability_zone

    @availability_zone.setter
    def availability_zone(self, availability_zone: 'Site'):
        # no checks
        # this is used to set this in customize_list
        self._availability_zone = availability_zone

    @property
    def compliance_zone(self):
        if not self._compliance_zone and self.compliance_zone_id:
            self._compliance_zone = self.controller.get_resource(self.compliance_zone_id, entity_class=Site)
        return self._compliance_zone

    @property
    def main_zone_share(self) -> Optional['FileShareV2']:
        """return main zone share, None, or Exception

        :raises Exception: if more than one main share detected for current provider share
        :return: main zone share
        :rtype: Optional['FileShareV2']
        """
        if not self._main_zone_share:
            site = self.get_attribs("availability_zone", None)
            if not site:
                return None
            instances, total = self.get_linked_resources(link_type_filter="relation.%s" % site, with_perm_tag=False)
            if total == 0:
                return None
            if total > 1:
                raise Exception("Detected misconfiguration: more than one main zone instance")
            self._main_zone_share = instances[0]
        return self._main_zone_share

    @main_zone_share.setter
    def main_zone_share(self, zone_share: 'FileShareV2'):
        # no checks
        # used in customize list
        self._main_zone_share = zone_share

    @property
    def main_physical_share(self) -> Optional['OntapNetappVolume']:
        if not self._main_physical_share:
            if self.main_zone_share:
                self._main_physical_share = self.main_zone_share.physical_share
        return self._main_physical_share

    @main_physical_share.setter
    def main_physical_share(self, phy_share):
        # no checks
        # used in customize list
        self._main_physical_share = phy_share

    @property
    def compliance_zone_share(self) -> Optional['FileShareV2']:
        """return compliance zone share, None, or Exception

        :raises Exception: if more than one compliance share detected for current provider share
        :return: compliance zone share
        :rtype: Optional['FileShareV2']
        """
        if not self._compliance_zone_share:
            peer_site = self.get_attribs("compliance_zone", None)
            if not peer_site:
                return None
            instances, total = self.get_linked_resources(link_type_filter="relation.%s" % peer_site, with_perm_tag=False)
            if total == 0:
                return None
            if total > 1:
                raise Exception("Detected misconfiguration: compliance zone instance should be unique")
            self._compliance_zone_share = instances[0]
        return self._compliance_zone_share

    @property
    def compliance_physical_share(self) -> Optional['OntapNetappVolume']:
        """get compliance physical share

        :return: compliance physical share or None or Exception
        :rtype: Optional[OntappNetapp.Volume]
        :raises Exception: on zone share misconfiguration
        """
        if self.compliance_zone_share:
            return self.compliance_zone_share.physical_share
        return None

    @property
    def size(self):
        try:
            return float(self.main_physical_share.get_size())
        except Exception as ex:
            self.logger.error("Error getting size from main physical share: %s", ex)

        try:
            return float(self.get_attribs(key="size"))
        except Exception as e:
            self.logger.error(e, exc_info=True)

    def get_orchestrator(self) -> str:
        return self.get_attribs(key="type")

    def get_orchestrator_tag(self) -> str:
        return self.get_attribs("orchestrator_tag", "default")

    def __get_availability_zone_info(self, info):
        if self.availability_zone is not None:
            info["availability_zone"] = self.availability_zone.small_info()
        else:
            info["availability_zone"] = {}
        return info

    def info(self):
        """Get info.

        :return: dict
        :raise ApiManagerError:
        """
        info = ComputeProviderResource.info(self)
        info["details"] = {}
        info = self.__get_availability_zone_info(info)
        attributes = self.get_attribs()

        # default values
        proto = attributes.get("proto")
        size = attributes.get("size")
        exports = []
        remote_attribs = {}

        if self.main_physical_share:
            physical_share_info = self.main_physical_share.detail()
            remote_attribs = dict_get(physical_share_info, "details.remote_data", default={})
            proto = self.main_physical_share.get_share_proto() or proto
            size = dict_get(physical_share_info, "details.size") or size
            exports = dict_get(physical_share_info, "details.export_locations", default=[])

        info["details"].update(
            {
                "type": attributes.get("type"),
                "proto": proto,
                "size": size,
                "exports": exports,
                "remote_state": dict_get(remote_attribs, "state"),
                "remote_encryption_state": dict_get(remote_attribs, "encryption.state")
            }
        )

        return info

    def detail(self):
        """Get details.

        :return: dict
        :raise ApiManagerError:
        """
        info = ComputeProviderResource.detail(self)
        info["details"] = {}
        info = self.__get_availability_zone_info(info)

        if self.main_physical_share:
            physical_share_info = self.main_physical_share.detail()
            remote_attribs = dict_get(physical_share_info, "details.remote_data",default={})
            exports = dict_get(physical_share_info, "details.export_locations", default=[])
            protocol = self.main_physical_share.get_share_proto()
            cluster = self.main_physical_share.get_attribs("cluster")
            role = self.main_physical_share.get_attribs("role")

            info["details"].update(
                {
                    "size": dict_get(physical_share_info, "details.size"),
                    "size_bytes": dict_get(physical_share_info, "details.size_bytes"),
                    "protocol": protocol,
                    "cluster": cluster,
                    "svm": dict_get(remote_attribs, "svm.name"),
                    "remote_name": dict_get(remote_attribs, "name"),
                    "role": role,
                    "remote_state": dict_get(remote_attribs,"state"),
                    "remote_encryption_state": dict_get(remote_attribs, "encryption.state"),
                    "export_policy": dict_get(remote_attribs, "nas.export_policy.name"),
                    "exports": exports,
                }
            )
            info["details"]["snaplock"] = self.get_snaplock()
            info["details"]["snapmirrors"] = self.get_snapmirrors()
            grants = dict_get(physical_share_info, "details.grants")
            info["details"]["grants"] = self.get_grants(grants)

            if self.share_role == "main":
                info["details"]["snapshot_policy"] = dict_get(remote_attribs, "snapshot_policy.name")
            elif self.share_role=="replica":
                info["details"]["snapmirror_policy"] = dict_get(physical_share_info, "details.snapmirror_policy")

        return info

    def get_snaplock(self, strict=False):
        """Get volume snaplock if exists

        :return: a dict with snaplock details or None
        """
        res = None
        try:
            res = self.compliance_physical_share.get_snaplock_information()
        except Exception as ex:
            self.logger.error(str(ex))
            if strict:
                raise ex
            return None

        if not res:
            return res

        res.update({
            "snaplock_phy_id": self.compliance_physical_share.uuid,
            "snaplock_phy_name": self.compliance_physical_share.name,
            "site": self.compliance_zone.name
        })
        return res

    def get_snapmirrors(self, strict=False) -> List[Dict]:
        """returns snapmirrors information

        :return: list of snapmirrors. each item has
        - source path
        - destination path
        - state
        - healthy

        :rtype: List[Dict]
        """
        instances: List['ComputeFileShareV2']
        instances, _ = self.get_linked_resources(link_type_filter="snapmirror", with_perm_tag=False)

        res = []
        if self.share_role=="main":
            # snapmirror relationship information must be taken from the destination
            for instance in instances:
                if instance.share_role=="replica":
                    relationship = {
                        "replica_id": instance.uuid,
                        "replica_name": instance.name,
                        "site": instance.availability_zone.name
                    }
                    # check added to cover replica creation errors where physical share is not present
                    if instance.main_physical_share:
                        # all snapmirrors that have this replica share as destination
                        snapmirrors = instance.main_physical_share.get_snapmirror_list()
                    else:
                        snapmirrors = None
                    if not snapmirrors or len(snapmirrors)>1:
                        # should never happen
                        self.logger.error("Unexpected number of snapmirrors.")
                        if strict:
                            num_str = "none" if not snapmirrors else str(len(snapmirrors))
                            raise Exception(
                                f"unexpected number of phy-level snapmirrors for "
                                f"provider-level instance {instance.uuid} - "
                                f"expected 1 but found {num_str}"
                            )
                        continue
                    relationship.update(snapmirrors[0])
                    res.append(relationship)
        elif self.share_role=="replica":
            # snapmirror relationship can be taken from phy
            if not instances or len(instances)>1:
                # should never happen
                self.logger.error("Unexpected number of snapmirror links")
                if strict:
                    num_str = "none" if not instances else str(len(instances))
                    raise Exception(
                        f"unexpected number of snapmirror links for "
                        f"provider-level replica {self.uuid} - "
                        f"expected 1 but found {num_str}"
                    )
                return []
            source = instances[0]
            relationship = {
                "source_id": source.uuid,
                "source_name": source.name,
                "site": source.availability_zone.name
            }
            if self.main_physical_share:
                # all snapmirrors that have this replica share as destination
                snapmirrors = self.main_physical_share.get_snapmirror_list()
            else:
                snapmirrors = None
            if not snapmirrors or len(snapmirrors)>1:
                # should never happen
                self.logger.error("Unexpected number of snapmirrors.")
                if strict:
                    num_str = "none" if not snapmirrors else str(len(snapmirrors))
                    raise Exception(
                        f"unexpected number of phy-level snapmirrors for "
                        f"provider share {source.uuid} - "
                        f"expected 1 but found {num_str}"
                    )
            if snapmirrors:
                relationship.update(snapmirrors[0])
            res.append(relationship)
        return res

    def get_grants(self, rules):
        """

        :return:
        """
        res = []
        if rules is None:
            return res
        for rule in rules:
            d = {
                "id": rule.get("id"),
                "access_level": self.__get_access_level(rule),
                "access_superuser": self.__get_access_superuser(rule),
                "protocols": rule.get("protocols"),
                "clients": self.__get_clients(rule)
            }
            res.append(d)
        return res

    @staticmethod
    def __get_clients(rule):
        if rule.get("clients"):
            return rule.get("clients")
        # manila compatibility
        if rule.get("access_to"):
            access_to = rule.get("access_to")
            if isinstance(access_to,str):
                access_to = [access_to]
            return access_to
        return None

    @staticmethod
    def __get_access_level(rule):
        if rule.get("access_level"):
            # manila compatibility
            return rule.get("access_level")
        if "any" or "sys" in rule.get("rw_access"):
            return "rw"
        if "any" or "sys" in rule.get("ro_access"):
            return "ro"
        return "never"

    @staticmethod
    def __get_access_superuser(rule):
        if "any" or "sys" in rule.get("su_access",""):
            return True
        return False


    def check(self):
        """Check resource

        :return:
        """
        errors = []
        try:
            if not self.main_physical_share:
                return {"check": False, "msg": "main share missing"}
        except Exception as ex:
            errors.append("main share unexpected configuration error: %s" % ex)

        share_role = self.share_role
        if not share_role:
            return {"check": False, "msg": "share role missing"}

        # metadata check
        attributes = self.get_attribs()
        # these should always be present
        expected_attribute_keys = ["type", "orchestrator_tag", "availability_zone", "size", "proto", "share_role", "has_quotas"]
        missing_keys = [k for k in expected_attribute_keys if k not in attributes]
        if missing_keys:
            errors.append("missing attribute keys: %s" % ",".join(missing_keys))

        # snapmirrors check
        try:
            _snapmirrors = self.get_snapmirrors(strict=True)
        except Exception as ex:
            errors.append("snapmirrors errors: %s" % ex)

        # snaplock check
        snaplock_expected = self.get_attribs("compliance_zone") is not None
        try:
            cps = self.compliance_physical_share
        except Exception as ex:
            if snaplock_expected:
                errors.append("compliance zone expected but missing or misconfiguration: %s" % ex)
        if cps and not snaplock_expected:
            errors.append("compliance zone not expected but found")

        if cps:
            snaplock_item = None
            try:
                snaplock_item = self.get_snaplock(strict=True)
                if not snaplock_item:
                    raise Exception("snaplock expected but missing")
            except Exception as ex:
                errors.append("snaplock error: %s" % ex)

        return {"check": len(errors)==0, "msg": None if not errors else ",".join(errors)}

    @staticmethod
    def customize_list(controller: 'ResourceController', entities: List['ComputeFileShareV2'], *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        controller.logger.debug("Get compute share availability zones")
        site_idx: Dict[Union[str, int],'Site'] = controller.index_resources_by_id(entity_class=Site)

        compute_share_ids: List[int] = []
        for entity in entities:
            compute_share_ids.append(entity.oid)
            if entity.availability_zone_id is not None:
                entity.availability_zone = site_idx.get(entity.availability_zone_id)

        # get map of compute share id to linked zone shares, for each compute share
        computes_to_zones_map: Dict[int, List['FileShareV2']] = controller.get_directed_linked_resources_internal(
            resources=compute_share_ids, link_type="relation%", run_customize=False
        )
        controller.logger.debug("Get compute share main zone share %s", computes_to_zones_map)

        # list of zone resources ids (only for main zone i.e. main=True in attributes)
        zone_resources_ids: List[int] = [
            zone_res.oid for zone_res_list in computes_to_zones_map.values()
            for zone_res in zone_res_list if zone_res.get_attribs("main",False)
        ]

        zone_to_phy_map: Dict[int,'OntapNetappVolume'] = controller.get_directed_linked_resources_internal(
            resources=zone_resources_ids,link_type="relation", run_customize=False
        )

        for entity in entities:
            zone_resources: List['FileShareV2'] = computes_to_zones_map.get(entity.oid,[])

            main_zone_share: 'FileShareV2' = None
            for z in zone_resources:
                if z.get_attribs("main", False):
                    main_zone_share = z
                    break
            entity.main_zone_share = main_zone_share

            # only one physical inst per zone inst
            main_physical_share = None
            if main_zone_share:
                phy_resources = zone_to_phy_map.get(main_zone_share.oid,[])
                main_physical_share = next(iter(phy_resources), None)
            entity.main_physical_share = main_physical_share

        return entities

    def post_get(self): # TODO
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        pass

    @staticmethod
    def pre_create(controller: 'ResourceController', container: 'ResourceContainer', *args, **kwargs):
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
        ## 1.0 read parameters from view

        ## 1.1 name contains the base name. description will be overwritten for replica
        name = kwargs.get("name")
        description = kwargs.get("desc", name)

        compute_zone = container.get_resource(kwargs.get("parent"), entity_class=ComputeZone)
        orchestrator_type = kwargs.get("type", "ontap")
        orchestrator_tag = kwargs.get("orchestrator_tag")

        ## 1.2 orchestrator tag indicates eventually which awx project to call
        # TODO may depend on future implementation
        awx_orchestrator_tag = kwargs.get("awx_orchestrator_tag")

        site_name = kwargs.get("site")
        share_params: 'CreateShareParams' = kwargs.get("share_params",{})

        compliance = kwargs.get("compliance")
        #compliance_site_name = kwargs.get("compliance_site")

        ## 1.3 init defaults
        compliance_share_params = None
        secondary_site_name = None
        # ontap only
        source_svm_name = None
        #

        ## 2.0 instantiate the appropriate helper
        from beehive_resource.plugins.provider.helper.share import ShareHelperFactory
        helper_class = ShareHelperFactory.get_backend_helper_class(orchestrator_type)
        if helper_class is None:
            raise Exception("Unsupported orchestrator type %s" % orchestrator_type)
        helper = helper_class(
            controller = controller,
            compute_zone = compute_zone
        )

        ## 3.0 set additional parameters
        # - for main: share_role, compliance_share_params (rpo)
        # - for replica: extract share_params, orchestrator from source
        from_id = kwargs.get("from_id")
        if from_id is None:
            ## 3.m creating a main volume
            share_role = "main"
            compliance_share_params = {
                "rpo": kwargs.get("compliance_rpo")
            }
            #secondary_site_name = compliance_site_name
        else:
            ## 3.r creating a replica of an existing share
            ## r.1 find source share
            from_resource: 'ComputeFileShareV2' = container.get_resource(
                oid = from_id, entity_class = ComputeFileShareV2
            )
            if not from_resource.availability_zone:
                raise Exception("Error fetching site information from source share %s" % from_id)

            ## r.2 name and desc set by convention or forced by service
            if not description:
                description = f'replica of {from_resource.name}'

            ## r.3 extract share_params and other attributes from source share
            from_attribs = from_resource.get_attribs()
            orchestrator_type = from_attribs.get("type")
            orchestrator_tag = from_attribs.get("orchestrator_tag")
            kwargs["orchestrator_type"] = orchestrator_type
            kwargs["orchestrator_tag"] = orchestrator_tag

            share_params = {
                "size": from_attribs.get("size"),
                "share_proto": from_attribs.get("proto"),
                "rpo": kwargs.get("rpo"),
                "from_id": from_id
                # encrypted?
                # TODO check what else
            }

            ## r.4 set additional config
            if orchestrator_type=="ontap":
                source_svm_name = from_resource.main_physical_share.get_attribs("svm")
            else:
                raise Exception("replica creation unsupported for orchestrator type %s" % orchestrator_type)

            share_role = "replica"
            compliance = False
            compliance_share_params = {}
            # secondary site name set to contain main site name
            secondary_site_name = from_resource.availability_zone.name

        # NB: must be here, since share_params is defined now both for main and replica
        share_proto = share_params.get("share_proto")
        size = float(share_params.get("size", 0))

        if orchestrator_type!="ontap":
            raise Exception("share creation unsupported for orchestrator type %s" % orchestrator_type)

        ## 4.0 validate parameters and obtain a context
        context = helper.validator.validate_share_params(
            share_role = share_role,
            share_params = share_params,
            main_site_name = site_name,
            compliance_enabled = compliance,
            secondary_site_name = secondary_site_name,
            source_svm_name = source_svm_name
        )

        ## 5.0 integrate params from validated context
        # add ontap information from validated context
        share_params.update({
            "cluster": context.get("main_cluster_name"),
            "svm": context.get("main_svm_name"),
            "share_role": context.get("share_role")
        })

        if compliance:
            compliance_share_params.update({
                "snaplock_cluster": context.get("secondary_cluster_name"),
                "snaplock_svm": context.get("secondary_svm_name")
            })
        #

        ## 6.0 set names according to convention rules
        if from_id:
            source_leaf_name = from_resource.main_physical_share.get_attribs("remote_name")
            vol_name = helper.generate_replica_leaf_name(source_leaf_name)
            new_name = f"dr-{from_resource.name}" # TODO simplify same as other branch?
        else:
            vol_name = helper.generate_main_leaf_name(name, context)
            new_name = helper.generate_root_name_from_leaf(compute_zone, vol_name)
        share_params["vol_name"] = vol_name

        ## TODO 6.1 check quotas
        helper.check_quotas()

        # get compute site e.g. SiteTorino01 and availability zone
        site = container.get_resource(site_name, entity_class=Site)
        availability_zone_id = ComputeProviderResource.get_active_availability_zone(compute_zone, site)

        params = {
            "name": new_name,
            "desc": description,
            "compute_zone": compute_zone.oid,
            "availability_zone": availability_zone_id,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                "size": size,
                "proto": share_proto,
                "share_role": share_role
            },
            "awx_orchestrator_tag": awx_orchestrator_tag,
            "share_params": share_params,
        }

        if compliance:
            secondary_site_name = context.get("secondary_site")
            if secondary_site_name is None:
                raise Exception("compliance site unexpectedly missing")

            # if compliance, get compliance site e.g. SiteVercelli01 and availability zone
            compliance_site = container.get_resource(secondary_site_name, entity_class=Site)
            compliance_availability_zone = ComputeProviderResource.get_active_availability_zone(compute_zone, compliance_site)

            params["compliance"] = compliance
            params["compliance_site"] = secondary_site_name
            params["compliance_share_params"] = compliance_share_params
            params["attribute"]["compliance_zone"] = compliance_site.oid

        kwargs.update(params)

        # create task workflow
        steps = [ComputeFileShareV2.task_path + "create_resource_pre_step"]
        if compliance:
            # determine "compliance" parameters
            # for ontap this means determining cluster fqdn and aggregate
            # these params will then be fed to the next step in the chain
            steps.append({
                "step": ComputeFileShareV2.task_path + 'determine_compliance_params_step',
                "args": [compliance_availability_zone],
            })
        steps.append({
                "step": ComputeFileShareV2.task_path + "create_zone_share_step",
                "args": [availability_zone_id],
        })
        if compliance:
            # try and import created compliance (snaplock) volume, in the other "branch"
            # of the provider resource tree
            is_main = False
            steps.append({
                "step": ComputeFileShareV2.task_path + "import_zone_share_step",
                "args": [compliance_availability_zone, is_main],
            })
        steps.append(ComputeFileShareV2.task_path + "create_resource_post_step")

        kwargs["steps"] = steps
        return kwargs

    @staticmethod
    def pre_import(controller: 'ResourceController', container: 'ResourceContainer', *args, **kwargs): # TODO check rewrite
        ## 1.0 init defaults
        name = kwargs.get("name") # will be overwritten
        description = kwargs.get("desc") # will be overwritten

        compute_zone = container.get_resource(kwargs.get("parent"), entity_class=ComputeZone)
        orchestrator_type = kwargs.get("type", "ontap")
        orchestrator_tag = kwargs.get("orchestrator_tag")

        awx_orchestrator_tag = kwargs.get("awx_orchestrator_tag")

        main_site_name = kwargs.get("site")
        remote_name = kwargs.get("remote_name")

        share_params = {}
        compliance_share_params = {}
        compliance = False
        compliance_site_name = None
        secondary_site_name = None

        ## 2.0 get helper
        from beehive_resource.plugins.provider.helper.share import ShareHelperFactory
        helper_class = ShareHelperFactory.get_backend_helper_class(orchestrator_type)
        if helper_class is None:
            raise Exception("Unsupported orchestrator type %s" % orchestrator_type)
        helper = helper_class(
            controller = controller,
            compute_zone = compute_zone
        )

        if orchestrator_type!="ontap":
            raise ApiManagerError(
                "share import unsupported for orchestrator %s" % orchestrator_type
            )

        ## get compute site e.g. SiteTorino01 and availability zone
        site, avz = ComputeProviderResource.get_site_and_active_zone(container, compute_zone, main_site_name)

        if orchestrator_type=="ontap":
            force_import_as_main = kwargs.get("force_import_as_main")

            ## 3.0 check main site and verify volume actually exists where expected and with the given name
            main_cluster, main_svm_list, compliance_site_name = helper.config_parser.check_storage_site_configuration(
                compute_zone,main_site_name,allow_missing_compliance_configuration=True
            )

            # verify remote volume exists
            ontap_container: OntapNetappContainer
            _,ontap_container = avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, main_cluster)
            try:
                search_res = ontap_container.find_volume(remote_name, main_svm_list)
            except Exception as ex:
                raise ApiManagerError("Error while searching for volume, on valid svms for site %s: %s" % (site.name,ex)) from ex

            ## 4.0 check existence of a compliance zone and verify if a snaplock (compliance) volume is present
            try:
                compliance_cluster_name, svm_list_compliance, _ = helper.config_parser.check_storage_site_configuration(
                    compute_zone, compliance_site_name, allow_missing_compliance_configuration=True
                )
                compliance_site, compliance_avz = ComputeProviderResource.get_site_and_active_zone(container, compute_zone, compliance_site_name)
                compliance_orchestrator,compliance_container = compliance_avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, compliance_cluster_name)
            except Exception as ex:
                # can't say if it's an error here,
                # because maybe there are no snapmirrors and no snaplocks
                controller.logger.warning("compliance site possibly configuration error: %s", ex)
                compliance_container = None
                compliance_orchestrator = None

            # indirect check:
            # - check if there is a snaplock relationship with the following characteristics:
            #       - source volume is the volume that is being imported
            #       - source svm is the svm in which that volume is
            #       - dest volume has snaplock.type = "compliance"
            # - if there is, name is checked against the expected one (needed to disambiguate against replicas)
            #       - [ for a stricter check, svm should be different than source one,
            #           and on a different cluster, and voume should have dp type]
            try:
                rel = ontap_container.get_volume_snaplock_relationship(
                    search_res.vol,
                    strict=True,
                    compliance_container=compliance_container
                )
                if rel:
                    snaplock_svm_name, snaplock_volume_name = dict_get(rel,"destination.path").split(":")

                    cmp_snaplock_volume_name = OntapNetappVolume.format_name_for_cmp(snaplock_volume_name)
                    expected_snaplock_volume_name = OntapNetappVolume.determine_compliance_name(search_res.cmp_name)
                    if cmp_snaplock_volume_name!=expected_snaplock_volume_name:
                        raise Exception("name error: expected %s but found %s" % (expected_snaplock_volume_name,cmp_snaplock_volume_name))

                    compliance_share_params.update({
                        "snaplock_cluster": dict_get(rel, "destination.cluster.name"),
                        "from_provider_import": True,
                        "compliance_vol_name": cmp_snaplock_volume_name,
                        "snaplock_svm": snaplock_svm_name
                    })
                    compliance = True
            except Exception as ex:
                raise Exception("error while checking for snaplock: %s" % ex) from ex

            ## 5.0 check if volume is a replica
            is_replica = False
            rels = []
            try:
                # basically if it's a destination of a snapmirror relationship
                # (could be either replica (dr) or compliance (snaplock). disambiguate later)
                is_replica, rels = ontap_container.check_volume_is_replica(search_res.vol)
            except Exception as ex:
                raise Exception("error while determining share role: %s" % ex) from ex

            if force_import_as_main:
                # regardless if it's a replica or not, forced as main volume.
                # used during migration if needing to import a volume that is a destination
                # of a snapmirror relationship, but will eventually be a main volume
                # and the relationship can't currently be deleted.
                controller.logger.warning(
                    "share_v2 import: forcing volume %s to be main volume",
                    search_res.cmp_name
                )
                is_replica = False

            ## 6.0 fill in params depending on the actual situation
            cz_res: 'ComputeFileShareV2' = None
            share_role = None
            share_role_inner = None
            if is_replica:
                if search_res.vol.get("snaplock",{}).get("type")=="compliance":
                    raise Exception("Do not import snaplock volume. Import main volume instead")

                share_role = "replica"
                share_role_inner = "dr"
                # if replica, check if main volume is already in cmp
                # force user to import that one first, otherwise
                if len(rels)>1:
                    raise Exception("unexpected situation: volume is a replica but has more than one source volume")
                try:
                    rel = rels[0]
                    _main_svm_name,main_vol_name = dict_get(rel, "source.path").split(":")
                    cmp_main_vol_name = OntapNetappVolume.format_name_for_cmp(main_vol_name)
                    p_vol: OntapNetappVolume = controller.get_simple_resource(cmp_main_vol_name,OntapNetappVolume)
                    # assume that it also must be linked correctly
                    tmp_list: List['FileShareV2']
                    tmp_list, _ = p_vol.get_linked_resources_optimized(link_type="relation")
                    if not tmp_list:
                        raise Exception("volume is in cmp but is not linked")
                    avz_res = tmp_list[0]
                    tmp_list: List['ComputeFileShareV2']
                    tmp_list, _ = avz_res.get_linked_resources_optimized(
                        link_type_filter="%relation.%",
                        objdef=ComputeFileShareV2.objdef
                    )
                    if not tmp_list:
                        raise Exception("volume is in cmp but is not completely linked")
                    cz_res = tmp_list[0]
                except Exception as ex:
                    raise Exception((
                        "volume is a replica. error while attempting "
                        "to find source volume %s in cmp: %s. "
                        "If missing import that one first."
                    )  % (cmp_main_vol_name,ex)) from ex
            else:
                share_role = "main"
                share_role_inner = "main"

            ## 7.0 update params
            share_params.update({
                "cluster": main_cluster,
                "svm": search_res.svm.get("name"),
                "vol_name": search_res.cmp_name,
                "vol_ext_id": search_res.vol.get("uuid"),
                "share_role": share_role_inner
            })

            name = helper.generate_root_name_from_leaf(compute_zone, remote_name)

            ## 8.0 make sure there is no existing resource in cmp with the same name
            # NB: mandatory to check here, since we decide the actual name only here ##
            try:
                obj = controller.get_resource(name, container_id=container.oid)
            except Exception:
                obj = None

            if obj is not None:
                raise ApiManagerError(
                    f"resource {name} already exists",
                    code=409,
                )
            ##

        params = {
            "name": name,
            "desc": name,
            "compute_zone": compute_zone.oid,
            "availability_zone": avz.oid,
            "attribute": {
                "type": orchestrator_type,
                "orchestrator_tag": orchestrator_tag,
                "availability_zone": site.oid,
                # these will be filled in later
                #"size": size,
                #"proto": share_proto,
                "share_role": share_role
            },
            "awx_orchestrator_tag": awx_orchestrator_tag,
            "share_params": share_params,
            "compliance": compliance,
        }

        steps = [
            ComputeFileShareV2.task_path + "create_resource_pre_step",
            {
                "step": ComputeFileShareV2.task_path + "import_zone_share_step",
                "args": [avz.oid, True],
            }
        ]
        if compliance and orchestrator_type=="ontap":
            if not compliance_site_name:
                raise Exception("no compliance site set and share to import has snaplock")
            if not compliance_orchestrator:
                raise Exception("compliance site configuration error")

            compliance_share_params.update({
                "compliance_site": compliance_site_name,
                "compliance_cluster": compliance_cluster_name,
                "compliance_svm_list": svm_list_compliance
            })
            params.update({
                "compliance_site": compliance_site_name,
                "compliance_orchestrator": compliance_orchestrator,
                "compliance_share_params": compliance_share_params,
            })
            params["attribute"]["compliance_zone"] = compliance_site.oid
            steps.append({
                "step": ComputeFileShareV2.task_path + "import_zone_share_step",
                "args": [compliance_avz.oid, False],
            })
        elif is_replica and cz_res:
            steps.append({
                "step": ComputeFileShareV2.task_path + "link_replica_step",
                "args": [cz_res.oid]
            })

        keys_to_update = [("size","size"),("share_proto","proto")]
        steps.append({
                "step": ComputeFileShareV2.task_path + "update_config_from_phy_instance_step",
                "args": [None,keys_to_update], # see task.
        })
        steps.append(ComputeFileShareV2.task_path + "create_resource_post_step")

        kwargs.update(params)
        kwargs["steps"] = steps
        return kwargs

    @staticmethod
    def __superuser_mapping(value: bool) -> str:
        mapper = {
            False: "none",
            True: "any",
        }
        return mapper.get(value)

    @staticmethod
    def __access_level_mapping(value: str) -> str:
        mapper = {
            "ro": "none",
            "rw": "any",
        }
        return mapper.get(value)

    def adjust_action_params(self, action_name, action_params):
        """

        :param action_name: the name of the action
        :param action_params: params to perform the action
        :return: kvargs
        :raise ApiManagerError:
        """
        if action_name == "manage_policy":
            # set superuser param to values expected by ansible playbook
            su_access = action_params.pop("su_access", None)
            if su_access is not None:
                action_params["su_access"] = self.__superuser_mapping(su_access)

            rw_access = action_params.pop("rw_access", None)
            if rw_access is not None:
                action_params["rw_access"] = self.__access_level_mapping(rw_access)

            client_type = action_params.pop("client_type", None)
            clients = action_params.pop("clients", [])
            if client_type is None:
                # this is the case of deleting the export policy rule
                action_params["clients"] = clients
            elif client_type == "id":
                client_ip = []
                from beehive_resource.plugins.provider.entity.instance import ComputeInstance
                for client_id in clients:
                    # get ip addresses from ips
                    res: ComputeInstance = self.controller.get_resource(client_id, ComputeInstance)
                    client_ip.append(res.get_ip_address())
                action_params["clients"] = client_ip
            elif client_type == "cidr":
                client_cidr = []
                for client in clients:
                    # discard /32 prefix if present
                    if client[-3:] == "/32":
                        client = client[:-3]
                    client_cidr.append(client)
                action_params["clients"] = client_cidr
            elif client_type == "user":
                # TODO
                raise NotImplementedError()
            else:
                raise ApiManagerError(f"Client type not supported: {client_type}")
            return action_params
        elif action_name == "replica_manage" or action_name=="replica_delete":
            if self.share_role != "replica":
                raise Exception(f"Invalid action {action_name} for specified role. Expected 'replica' but found {self.share_role}")

            # gather needed source share params
            source_share = self.replica_get_source_share()
            action_params["source_cluster"] = source_share.main_physical_share.get_attribs("cluster")
            action_params["source_svm"] = source_share.main_physical_share.get_attribs("svm")
            action_params["source_volume"] = source_share.main_physical_share.get_attribs("remote_name")

            if action_params.get("sub_action","") == "replica_unlink":
                action_params["execute_in_single_transaction"] = True
                action_params["provider_inline_pre_step_function_name"] = "unlink_and_rename_resource_tree"
        else:
            # add params validation/processing for other actions
            pass

        return action_params

    def pre_delete(self, *args, **kwargs):
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
        if self.share_role=="main":
            # check there are no dr shares linked to the current share
            dr_shares, total = self.get_linked_resources(link_type="snapmirror")
            dr_shares_oids = [s.oid for s in dr_shares]
            if total:
                raise ApiManagerError(
                    f"unable to delete. The share you want to delete has {total} linked shares;"
                    "either delete them or break the relationship. "
                    f"replica ids: {dr_shares_oids}"
                )
        elif self.share_role=="replica":
            params = {}
            self.adjust_action_params("replica_delete", params)
            kwargs["source_info"] = params
        else:
            raise ApiManagerError("Invalid share role %s" % self.share_role)

        # get instances
        shares, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [p.oid for p in shares]

        # create task workflow
        kwargs["compliance"] = self.get_attribs("compliance_zone") is not None
        kwargs["steps"] = self.group_remove_step(childs)

        if self.share_role=="replica": # TODO check
            # insert step just before post_expunge
            # possibly unnecessary
            kwargs["steps"].insert(-1,ComputeFileShareV2.task_path + "remove_source_link")

        # NB: kwargs["compliance"] and kwargs["source_info"], if present,
        # get propagated down until OntapNetappVolume.pre_delete

        # fetch awx project information
        awx_orchestrator_tag = kwargs.get("awx_orchestrator_tag")
        if awx_orchestrator_tag:
            site_id = self.get_attribs("availability_zone", None)
            if not site_id:
                self.logger.warning("main site id missing from share config. trying to delete all the same")
            else:
                awx_project = self.controller.get_awx_project(
                    customization_base_name="staas",
                    awx_orchestrator_tag=awx_orchestrator_tag,
                    site_id=site_id,
                    raise_on_error=True
                )
                kwargs["awx_project_id"] = awx_project.oid
            #

        return kwargs

    def unlink_and_rename_resource_tree(self, new_name: str, session: 'Session'=None, **kwargs):
        # TODO check and remove this. do in thext step. already set by action. even better because if this fails the link stays
        # self.remove_source_link()
        return self.rename_resource_tree(new_name, session=session, **kwargs)

    def remove_source_link(self):
        self.del_link_by_type(link_type="snapmirror")

    def rename_resource_tree(self, new_name: str, session: 'Session'=None, **kwargs):
        """rename resource tree (provider, zone, physical)

        :param new_name: base name for physical resource
        :type new_name: str
        :param session: existing session if any, defaults to None. must be given if called from a task
        :type session: Session, optional
        :raises Exception: on any error condition
        :return: None

        imports in function body are mandatory to handle cases when
        function is called from a celery task.
        """
        from beehive_resource.plugins.provider.helper.share import ShareHelperFactory
        orchestrator_type = self.get_orchestrator()
        helper_class = ShareHelperFactory.get_backend_helper_class(orchestrator_type)
        if helper_class is None:
            raise Exception("Unsupported orchestrator type %s" % orchestrator_type)

        # import everything needed in case rename_resource_tree is called from a task,
        # which is the base use case
        from beehive_resource.plugins.provider.entity.zone import ComputeZone, Site

        compute_zone = self.controller.get_resource(self.parent_id, entity_class=ComputeZone)
        main_zone = self.availability_zone

        if not self.main_zone_share:
            raise Exception("Unable to find main zone share")

        if not self.main_physical_share:
            raise Exception("Unable to find main physical share")

        helper = helper_class(
            controller = self.controller,
            compute_zone = compute_zone,
            #share_role = None,
            #site_name = main_zone.name,
            #share_params = {"svm": self.main_physical_share.get_attribs("svm")}, # needed by generate name
            #compliance = False,
            #secondary_site_name = None,
            #compliance_share_params = {}
        )

        if self.get_orchestrator()!="ontap":
            raise Exception("unsupported orchestrator type %s" % self.get_orchestrator())

        from beehive_resource.plugins.provider.helper.share.ontap import OntapShareContext
        context = OntapShareContext(
            share_role="main",
            main_site=main_zone.name,
            main_cluster_name=None, #not needed
            main_svm_name=self.main_physical_share.get_attribs("svm"),
            compliance=False,
            secondary_site=None,
            secondary_cluster_name=None,
            secondary_svm_name=None
        )
        phy_new_name = helper.generate_main_leaf_name(new_name, context)
        zone_new_name = f"{phy_new_name}-avz{main_zone.oid}"
        provider_new_name = helper.generate_root_name_from_leaf(compute_zone, phy_new_name)

        from sqlalchemy import text
        query = text("""
            UPDATE resource
            SET name = (case
                when id = :provider_id then :provider_name
                when id = :zone_id then :zone_name
                when id = :phy_id then :phy_name
            end)
            WHERE id in (:provider_id, :zone_id, :phy_id);
        """)

        if not session:
            session = self.controller.get_session()

        session.execute(query, {
            "provider_id": self.oid,
            "provider_name": provider_new_name,
            "zone_id": self.main_zone_share.oid,
            "zone_name": zone_new_name,
            "phy_id": self.main_physical_share.oid,
            "phy_name": phy_new_name
        })

        self.main_physical_share.clean_cache()
        self.main_zone_share.clean_cache()
        self.clean_cache()
        return {
            "provider_new_name": provider_new_name,
            "zone_new_name": zone_new_name,
            "phy_new_name": phy_new_name
        }

    def share_action(
        self,
        name, sync=False,
        action_params: Dict = None,
        keys_to_update: List[Tuple[str,str]] = None,
        awx_orchestrator_tag: str = None
    ):
        """Execute an action

        :param name: action name
        :param sync: if True run sync task, if False run async task
        :param action_params: Dict containing action parameters
        :param keys_to_update: contains optional list of provider attributes to update, each being a tuple
        with the following format:
            - (s,d) tuple
            - s is the source attribute key, taken from the physical resource e.g. size, details.whatever
            - d is the dest attribute key, as it will be updated or inserted on the provider resource
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        # verify permissions
        self.verify_permisssions("update")

        # check state is ACTIVE
        self.check_active()

        zone_instance = self.main_zone_share
        if zone_instance is None:
            raise Exception("Main zone instance missing")

        if action_params is None:
            action_params = {}
        self.adjust_action_params(name, action_params)

        # get custom action params
        steps = [{
            "step": ComputeFileShareV2.task_path + "send_action_to_zone_instance_step",
            "args": [zone_instance.oid],
        }]

        if action_params and action_params.get("sub_action","") == "replica_unlink":
            steps.append(ComputeFileShareV2.task_path + "remove_source_link")

        if keys_to_update is not None:
            steps.append({
                "step": ComputeFileShareV2.task_path + "update_config_from_phy_instance_step",
                "args": [zone_instance.oid,keys_to_update],
            })

        # fetch awx project information
        if not awx_orchestrator_tag:
            awx_orchestrator_tag = "02"
        site_id = self.get_attribs("availability_zone", None)
        if not site_id:
            raise Exception("main site id missing from share config")
        awx_project = self.controller.get_awx_project(
            customization_base_name="staas",
            awx_orchestrator_tag=awx_orchestrator_tag,
            site_id=site_id,
            raise_on_error=True
        )

        res = super().action(
            name=name, steps=steps, log="Run share action",
            action_params=action_params, sync=sync, awx_project_id=awx_project.oid
        )
        return res

    def compliance_action(
        self,
        name: str,
        sync = False,
        action_params: Dict = None,
        awx_orchestrator_tag: str = None,
        metadata_only: bool = False
    ):
        """Execute a compliance action, typically enable or disable

        :param name: action name
        :param sync: if True run sync task, if False run async task
        :param action_params: Dict containing action parameters
        :param awx_orchestrator_tag:
        :param metadata_only:
        :return: for async task {'taskid': celery task instance id, 'uuid': resource uuid},
            for sync task {'task': task name, 'params': task params, 'uuid': resource uuid}
            for sync resource {'uuid': resource uuid}
        :raises ApiManagerError: if query empty return error.
        """
        if action_params is None:
            action_params = {}

        # verify permissions
        self.verify_permisssions("update")

        if name not in ["compliance_enable", "compliance_disable"]:
            raise ApiManagerError("Unsupported compliance action %s" % name)

        # action executed on provider share.
        # can't be a replica, because replica is never compliant
        if self.share_role != "main":
            raise ApiManagerError(f"Invalid action {name} for specified role. Expected 'main' but found {self.share_role}")

        # check state is ACTIVE
        self.check_active()

        steps = []
        import_params = {}
        if not metadata_only:
            if name == "compliance_enable":
                if self.compliance_zone_share:
                    raise ApiManagerError("Unexpected situation: compliance zone share already present")

                orchestrator_type = self.get_orchestrator()
                orchestrator_tag = self.get_orchestrator_tag()
                compute_zone: 'ComputeZone' = self.controller.get_resource(self.parent_id, entity_class=ComputeZone)

                from beehive_resource.plugins.provider.helper.share import ShareHelperFactory
                helper_class = ShareHelperFactory.get_backend_helper_class(orchestrator_type)
                if helper_class is None:
                    raise Exception("Unsupported orchestrator type %s" % orchestrator_type)
                helper = helper_class(
                    controller = self.controller,
                    compute_zone = compute_zone
                )

                if orchestrator_type != "ontap":
                    raise ApiManagerError(
                        "share import unsupported for orchestrator %s" % orchestrator_type
                    )

                if not self.main_physical_share:
                    raise ApiManagerError("invalid main volume")

                action_params["action_name"] = name
                main_site_name = self.availability_zone.name
                subaction_params = action_params.get("subaction_params", {})
                rpo = subaction_params.get("rpo")

                # condition is commented because the only STAAS v2 orchestrator type we manage
                # at the moment is really "ontap"
                # if orchestrator_type == "ontap":
                # check main site and make sure it has a compliance configuration
                main_cluster_name, _, compliance_site_name = helper.config_parser.check_storage_site_configuration(
                    compute_zone, main_site_name, allow_missing_compliance_configuration=False
                )

                # check compliance site and get cluster and svm
                compliance_cluster_name, svm_list_compliance, _ = helper.config_parser.check_storage_site_configuration(
                    compute_zone, compliance_site_name, allow_missing_compliance_configuration=True
                )

                # get both containers and check for existing snaplock
                main_ontap_container: OntapNetappContainer
                compliance_container: OntapNetappContainer
                _, main_avz = ComputeProviderResource.get_site_and_active_zone(self.container, compute_zone, main_site_name)
                _, main_ontap_container = main_avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, main_cluster_name)
                compliance_site, compliance_avz = ComputeProviderResource.get_site_and_active_zone(self.container, compute_zone, compliance_site_name)
                compliance_orchestrator, compliance_container = compliance_avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, compliance_cluster_name)

                try:
                    rel = main_ontap_container.get_volume_snaplock_relationship(
                        self.main_physical_share.ext_obj_wrap,
                        strict=True,
                        compliance_container=compliance_container
                    )
                    if rel:
                        raise Exception("snaplock already present; dest path: %s" % rel.get("destination").get("path"))
                except Exception as ex:
                    raise Exception("error while checking for existing snaplock: %s" % ex) from ex

                svm = self.main_physical_share.svm.get("name")
                size = self.main_physical_share.get_size()
                vol_name = OntapNetappVolume.format_name_for_cmp(self.main_physical_share.ext_obj_wrap.get("name"))
                emptiest_aggregate, _ = main_ontap_container.conn2.get_svm_emptiest_aggregate(svm_name=svm)

                peer_relationships = compute_zone.staas_conf.get("relationships")
                snaplock_svm = helper.config_parser.get_peer_svm(
                    peer_relationships,
                    main_site_name,
                    compliance_site_name,
                    svm,
                    svm_list_compliance
                )

                snaplock_cluster_fqdn = compliance_container.conn_params.get("host")
                snaplock_emptiest_aggregate, _ = compliance_container.conn2.get_svm_emptiest_aggregate(svm_name=snaplock_svm)

                share_params = {
                    "vol_name": vol_name,
                    "size": size,
                    "share_proto": self.get_attribs("proto"),
                    "aggregate": emptiest_aggregate
                }
                compliance_share_params = {
                    "snaplock_cluster": snaplock_cluster_fqdn,
                    "snaplock_svm": snaplock_svm,
                    "snaplock_aggregate": snaplock_emptiest_aggregate,
                    "rpo": rpo
                }
                import_params = {
                    "orchestrator_type": orchestrator_type,
                    "orchestrator_tag": orchestrator_tag,
                    "share_params": share_params,
                    "compliance_share_params": compliance_share_params,
                    "compliance_orchestrator": compliance_orchestrator
                }

                steps.append({
                    "step": ComputeFileShareV2.task_path + "send_action_to_zone_instance_step",
                    "args": [self.main_zone_share.oid],
                })
                is_main = False
                steps.extend([
                    {
                        "step": ComputeFileShareV2.task_path + "import_zone_share_step",
                        "args": [compliance_avz.oid, is_main],
                    },
                    {
                        "step": ComputeFileShareV2.task_path + "update_config",
                        "args": [[{"compliance_zone": compliance_site.oid}]]
                    }
                ])
            elif name == "compliance_disable":
                zone_share: 'FileShareV2' = self.compliance_zone_share
                if zone_share is None:
                    raise ApiManagerError("Snaplock zone instance not found")

                action_params["compliance"] = True # used by task
                steps.extend([
                    {
                        "step": ComputeFileShareV2.task_path + "remove_child_step",
                        "args": [zone_share.oid]
                    },
                    {
                        "step": ComputeFileShareV2.task_path + "update_config",
                        "args": [[{"compliance_zone": None}]]
                    }
                ])
            else:
                raise ApiManagerError("Unsupported compliance action %s" % name)

        # fetch awx project information
        if not awx_orchestrator_tag:
            awx_orchestrator_tag = "02"
        site_id = self.get_attribs("availability_zone", None)
        if not site_id:
            raise Exception("main site id missing from share config")
        awx_project = self.controller.get_awx_project(
            customization_base_name="staas",
            awx_orchestrator_tag=awx_orchestrator_tag,
            site_id=site_id,
            raise_on_error=True
        )

        res = super().action(
            name=name, steps=steps, log="Run share compliance action",
            action_params=action_params, sync=sync, awx_project_id=awx_project.oid,
            **import_params
        )
        return res

    def get_quotas(self):
        """Get resource quotas

        :return: list of resource quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "share.instances": 1,
            "share.blocks": self.size
        }

        self.logger.debug2("Get ComputeFileShareV2 %s quotas: %s" % (self.uuid, quotas))
        return quotas

    def _get_metric_range(self):
        """Determine metric range based on aggregate disk class."""
        try:
            physical_share_info = self.main_physical_share.detail()
            remote_data = physical_share_info.get("details", {}).get("remote_data", {})
            aggregates = remote_data.get("aggregates", [])
            aggregate_uuid = aggregates[0].get("uuid") if aggregates else None

            if not aggregate_uuid:
                # should be impossible
                return "NA"

            aggregate = (
                self.main_physical_share.container
                .conn2.aggregate
                .get(aggregate_uuid)
            )

            disk_class = (
                aggregate.get("block_storage", {})
                .get("primary", {})
                .get("disk_class")
            )

            return "low" if disk_class == "capacity" else "high"

        except Exception as ex:
            self.logger.warning(
                "unable to determine metric range (high/low). %s", ex
            )
            return "NA"

    def _get_main_metrics(self, metric_range: Literal["high", "low", "NA"]):
        """main metrics; including compliance metrics if present """

        size = self.size
        if size is None:
            # should never happen (i.e. failure to get it from platform and no size in metadata)
            self.logger.error("Unable to determine size in any way. Defaulting to 0")
            size = 0

        metrics: List[Dict[str, Union[int, str]]] = [
            {
                "key": f"sd_gdisk_{metric_range}",
                "value": size,
                "type": 1,
                "unit": "GB",
            }
        ]

        # check and add compliance metrics if any
        try:
            snaplock = self.compliance_physical_share
            if snaplock:
                # snaplock_size = snaplock.get_size()
                #
                # Snaplock size is not updated at the platform level
                # after resizing the primary volume.
                # Since the storage metrics take into account the
                # allocated disk space rather than the disk space
                # actually consumed, it has been decided that the
                # snaplock metric value should be set to the same
                # as that of the primary volume metric.

                metrics.append(
                    {
                        "key": f"sd_gdisk_{metric_range}_compliance",
                        "value": size,
                        "type": 1,
                        "unit": "GB",
                    }
                )
        except Exception as ex:
            self.logger.error(
                "Error retrieving snaplock %s size: %s",
                getattr(snaplock, "oid", None),
                ex,
            )

        return metrics

    def _get_replica_metric(self, metric_range: Literal["high", "low", "NA"]):
        """replica metrics; rpo dependent"""
        snapmirrors = None
        try:
            # all snapmirrors that have this replica share as destination
            snapmirrors = self.main_physical_share.get_snapmirror_list()
        except Exception as ex:
            self.logger.error("error while getting snapmirrors %s", ex)
            return None

        if not snapmirrors:
            self.logger.error("No snapmirrors found for replica")
            return None

        if len(snapmirrors) > 1:
            self.logger.warning(
                "unexpected number of snapmirrors %s", len(snapmirrors)
            )

        rel_uuid = snapmirrors[0].get("uuid")

        try:
            rel_info = self.main_physical_share.get_remote_snapmirror_with_policy(
                controller=None,
                postfix=None,
                container=self.main_physical_share.container,
                relationship_id=rel_uuid,
            )
            rpo_name = rel_info.get("policy", {}).get("name")
        except Exception as ex:
            self.logger.error("error while getting replica policy: %s. defaulting to 'NA'", ex)
            rpo_name = "NA"

        size = self.size
        if size is None:
            # should never happen (i.e. failure to get it from platform and no size in metadata)
            self.logger.error("Unable to determine size in any way. Defaulting to 0")
            size = 0

        return {
            "key": f"sd_gdisk_{metric_range}_{rpo_name}",
            "value": size,
            "type": 1,
            "unit": "GB",
        }

    def get_metrics(self):
        """Get resource metrics

        possible metrics:
        - capacity (sata)
            - sd_gdisk_low: for main volume. equal to size in GB
            - sd_gdisk_low_compliance: for compliance volume. equal to size in GB
            - sd_gdisk_low_{rpo_name}: for replica volume. equal to size in GB
        - solid_state (ssd)
            - sd_gdisk_high: for main volume. equal to size in GB
            - sd_gdisk_high_compliance: for compliance volume. equal to size in GB
            - sd_gdisk_high_{rpo_name}: for replica volume. equal to size in GB

        :return: a dict like this
                Example::

                    {
                        "id": "<provider resource id>",
                        "uuid": "<provider resource uuid>",
                        "metrics": [
                            {
                                "key": "<metric name>",
                                "value: 10,
                                "type": 1, # 1 or CONSUME
                                "unit": "GB"
                            }
                        ],
                        "extraction_date": "2018-03-04 12:00:34 200",
                        "resource_uuid": "<provider resource uuid>"
                    }
        """
        metrics = []

        metric_range = self._get_metric_range()

        if self.share_role=="main":
            metrics.extend(self._get_main_metrics(metric_range))
        elif self.share_role=="replica":
            replica_metric = self._get_replica_metric(metric_range)
            if replica_metric:
                metrics.append(replica_metric)
        else:
            self.logger.error("Unknown share role %s", self.share_role)
            return
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get ComputeFileShareV2 %s metrics: %s", self.uuid, res)
        return res

    def clean_cache(self):
        """clean cache. also cleans main physical and zone cached resources
        """
        try:
            self.main_physical_share.clean_cache()
        except Exception as ex:
            self.logger.error("Error while deleting main physical share cache: %s", str(ex))

        try:
            self.main_zone_share.clean_cache()
        except Exception as ex:
            self.logger.error("Error while deleting main zone share cache: %s", str(ex))

        return super().clean_cache()

class FileShareV2(AvailabilityZoneChildResource):
    """Availability Zone File Share"""

    objdef = "Provider.Region.Site.AvailabilityZone.FileShareV2"
    objuri = "%s/shares/%s"
    objname = "share"
    objdesc = "Provider Availability Zone File Share V2"
    task_path = "beehive_resource.plugins.provider.task_v2.share_v2.ComputeFileShareV2Task."

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)
        self._physical_share: OntapNetappVolume = None

    def detail(self):
        """Get remote share detail

        :return: dict with information
        :rtype: dict
        """
        info = self.info()
        return info

    @property
    def physical_share(self) -> OntapNetappVolume:
        """Get remote physical share from orchestrator

        :return: linked physical share
        """
        if not self._physical_share:
            inst_type = self.get_attribs("type")
            if not inst_type:
                return None
            if inst_type == "ontap":
                objdef = OntapNetappVolume.objdef
            else:
                raise Exception("Unsupported share type %s" % inst_type)

            try:
                share = self.get_physical_resource(objdef)
                self._physical_share = share
            except Exception as ex:
                self.logger.error("Error while getting physical share of type %s: %s", objdef, ex)
        return self._physical_share

    @staticmethod
    def pre_create(controller: 'ResourceController', container, *args, **kwargs):
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
        steps = [
            FileShareV2.task_path + "create_resource_pre_step",
            FileShareV2.task_path + "create_physical_share_step",
            FileShareV2.task_path + "create_resource_post_step",
        ]
        kwargs["steps"] = steps
        kwargs["sync"] = True

        return kwargs

    @staticmethod
    def pre_import(controller: 'ResourceController', container, *args, **kwargs):
        steps = [
            FileShareV2.task_path + "create_resource_pre_step",
            FileShareV2.task_path + "import_physical_share_step",
            FileShareV2.task_path + "create_resource_post_step",
        ]
        kwargs["steps"] = steps
        kwargs["sync"] = True

        return kwargs

    def pre_delete(self, *args, **kwargs):
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
        # select physical orchestrator
        orch_type = self.get_attribs("type")
        if orch_type:
            orchestrator_idx = self.get_orchestrators(select_types=[orch_type])
        else:
            orchestrator_idx = self.get_orchestrators(select_types=["ontap","openstack"])

        # for ontap, if compute file share is compliant, i.e. snaplock is present
        # the main zone is the one with the main volume,
        # while the non-main one is where the snaplock volume is.
        # ontap replicas only have one main zone.
        if orch_type=='ontap' and self.get_attribs("main", True) == False:
            # mark snaplock volume as deletable after x days,
            # delete snapmirror relationship,
            # delete zone resource
            kwargs["steps"] = [
                self.task_path + "expunge_resource_pre_step",
                self.task_path + "detach_compliance_physical_resource_step",
                self.task_path + "expunge_resource_post_step"
            ]
        else:
            # normal deletion
            kwargs["steps"] = self.group_remove_step(orchestrator_idx)
        kwargs["sync"] = True
        return kwargs

    def action(self, name, action_params: Dict = None, sync = True, awx_params: Dict = None,
               import_params: Dict = None, **kwargs):
        """Execute an action

        :param name: action name
        :param action_params: action params
        :param params.internal_step: custom internal_step [default=instance_action_step]
        :param hypervisor: orchestrator type
        :param hypervisor_tag: orchestrator tag
        :raises ApiManagerError: if query empty return error.
        """
        if action_params is None:
            action_params = {}

        # run custom check function
        check = getattr(self, name, None)
        if check is not None:
            params = check(**action_params)

        # clean cache
        self.clean_cache()

        instances, total = self.get_linked_resources(link_type_filter="relation", with_perm_tag=False)
        if total != 1: # instances should be in this case a list of one element (i.e. the volume)
            raise Exception("unexpected number of linked resources: expected 1 but was %s" % total)

        # get custom action params
        steps = [{
            "step": ComputeFileShareV2.task_path + "send_action_to_phyres_step",
            "args": [instances[0].oid],
        }]

        res = super().action(
            name=name, steps=steps, log="Run avz fileshare action",
            action_params=action_params, sync=sync, awx_params=awx_params,
            import_params=import_params
        )
        return res
