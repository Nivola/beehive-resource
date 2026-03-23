# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from __future__ import annotations
from enum import Enum
import logging
from typing import List,Dict,Optional, Union, TYPE_CHECKING, Literal, Tuple, Type
from beehive.common.data import trace
from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.ontap.entity import OntapNetappResource

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from beehive_resource.container import IRESOURCE
    from beehive_resource.plugins.ontap.controller import OntapNetappContainer
    from beehive_resource.controller import ResourceController

    #legacy (deprecated)
    from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm

class OntapNetappVolume(OntapNetappResource):
    """
    ontap volume
    """
    objdef = "OntapNetapp.Volume"
    objuri = "volumes"
    objname = "volume"
    objdesc = "OntapNetapp Volume"

    default_tags = ["ontap", "storage"]
    task_base_path = 'beehive_resource.plugins.ontap.task_v2.ontap_volume.OntapVolumeTask.'
    action_task_base_path = 'beehive_resource.plugins.ontap.task_v2.ontap_volume.OntapVolumeActionTask.'

    @classmethod
    def get_deletable_snaplocks(cls, controller: 'ResourceController', limit=20, offset=0):
        from beehive_resource.model import Resource as ModelResource
        from sqlalchemy import select, and_
        from sqlalchemy.sql import func
        from datetime import datetime

        now_str = datetime.now().isoformat(timespec='seconds')

        session = controller.get_session()
        filters = and_(
            ModelResource.type.has(value=OntapNetappVolume.objdef),
            #ModelResource.expiry_date!=None,
            #ModelResource.expiry_date<=datetime.now(),
            func.str_to_date(
                func.json_unquote(func.json_extract(ModelResource.attribute, '$.delete_after')),
                '%Y-%m-%dT%H:%i:%s'
            )<=now_str,
            func.json_unquote(func.json_extract(ModelResource.attribute, '$.deletable')) == 'true'
        )

        count_stmt = select(func.count()).select_from(ModelResource).where(filters)
        total = session.execute(count_stmt).scalar()

        resp = []
        if total:
            stmt = (
                select(ModelResource)
                .where(filters)
                .limit(limit)
                .offset(offset)
                .order_by(ModelResource.id.desc())
            )

            result = session.execute(stmt).scalars().all()

            for entity in result:
                obj = OntapNetappVolume(
                    controller,
                    oid=entity.id,
                    objid=entity.objid,
                    name=entity.name,
                    active=entity.active,
                    desc=entity.desc,
                    model=entity,
                )
                resp.append(obj.info())
        return resp, total

    def __init__(self, *args, **kvargs):
        """ """
        OntapNetappResource.__init__(self, *args, **kvargs)

        self._svm_legacy = None
        self._svm = None

    @property
    def container_wrap(self) -> 'OntapNetappContainer':
        """wrapper around self.container
        if container is set (by controller common logic) return that,
        otherwise use container id from database and fetch it

        :return: container
        :rtype: OntapNetappContainer
        """
        if self.container is None:
            self.container =  self.controller.get_container(self.model.container_id)
        return self.container

    @property
    def ext_obj_wrap(self) -> Dict:
        """return remote volume information

        :raises ApiManagerError: _description_
        :raises Exception: _description_
        :raises ValueError: _description_
        :return: _description_
        :rtype: Dict
        """
        if self.ext_obj is None:
            try:
                self.ext_obj = OntapNetappResource.get_remote_volume(
                    controller=self.controller,
                    postfix=self.ext_id,
                    ext_id=self.ext_id,
                    container=self.container_wrap,
                    short_info=True
                )
            except Exception as ex:
                raise ApiManagerError(f"Unable to query remote resource: {ex}") from ex
        return self.ext_obj

    @property
    def svm_legacy(self) -> 'OntapNetappSvm':
        """old version - legacy - deprecated

        :return: parent svm in cmp
        :rtype: OntapNetappSvm
        """
        if self._svm_legacy is None:
            svm_resource_id = self.get_attribs("svm")
            self._svm_legacy = self.controller.get_resource(svm_resource_id)
        return self._svm_legacy

    @property
    def svm(self) -> Dict:
        """get volume remote svm dictionary information

        :return: svm representation
        :rtype: Dict
        """
        if self._svm is None:
            svm_name = self.get_attribs("svm")
            self._svm = self.get_remote_svm_by_name(self.controller,svm_name,self.container_wrap,svm_name)
        return self._svm

    @property
    def svm_ip_interfaces(self) -> List[Dict]:
        """get svm ip interfaces with an active nfs or cifs service

        :raises ApiManagerError: if svm can't be found
        :raises ApiManagerError: if svm has no interfaces
        :return: name and ip for each interface with nfs or cifs active services
        :rtype: List[Dict]
        """
        if not self.svm:
            raise ApiManagerError("Can't show ip interfaces, svm field does not have a valid value")

        res = []
        ip_interfaces = dict_get(self.svm, "ip_interfaces")
        if ip_interfaces is None:
            raise ApiManagerError("svm %s ip_interfaces field missing" % self.get_attribs("svm"))
        else:
            for ip_interface in ip_interfaces:
                services = dict_get(ip_interface, "services")
                if "data_nfs" in services or "data_cifs" in services:
                    res.append(
                        {
                            "name": dict_get(ip_interface, "name"),
                            "ip": dict_get(ip_interface, "ip.address"),
                        }
                    )
        return res

    @property
    def export_locations(self) -> List[str]:
        """get share export locations

        :return: list of formatted export locations
        :rtype: List[str]
        :raises ValueError: if unsupported security style
        :raises Exception: if not even one ip address is found
        """
        res = []
        mounts = []
        nas_security_style = dict_get(self.ext_obj_wrap, "nas.security_style")
        nas_path = dict_get(self.ext_obj_wrap, "nas.path")
        if not nas_path:
            return res
        for ip_interface in self.svm_ip_interfaces:
            ip = ip_interface.get("ip")
            if ip is not None:
                export_location = OntapNetappVolume.get_format_export_location(
                    nas_security_style,
                    nas_path,
                    ip
                )
                mounts.append(export_location)
            else:
                self.logger.warning("volume %s interface has no ip address", self.oid)

        if mounts:
            res.append({
                "id": nas_path,
                "protocol": self.get_share_proto(),
                "mounts": mounts
            })
        #if not res:
        #    raise Exception("no valid ip interface for host svm")

        self.logger.debug("get volume %s export locations: %s", self.oid, res)
        return res

    #
    # enums for class related constants and constants combinations
    #
    class Role(Enum):
        """enum listing all possible volume roles, as follows:
        - main: a normal volume
        - snaplock: a snaplock volume
        - dr: a snapmirror volume
        """
        MAIN = "main"
        SNAPLOCK = "snaplock"
        DR = "dr"

        @classmethod
        def get_all_values(cls):
            return [c.value for c in cls]

    class SuperuserSecurityPolicy(Enum):
        NONE = "none"
        ANY = "any"

        @classmethod
        def get_all_values(cls):
            return [c.value for c in cls]

    class RwRule(Enum):
        RO = "never"
        RW = "any"

        @classmethod
        def get_all_values(cls):
            return [c.value for c in cls]

    class PolicyRule(Enum):
        RO = "never","none"
        RW = "any","none"
        RW_SU = "any","any"

        def __init__(self, rw_rule: str, superuser_security_policy: str):
            self.rw_rule = rw_rule
            self.superuser_security_policy = superuser_security_policy

        @classmethod
        def from_values(
            cls,
            rw_rule: Union[str,'OntapNetappVolume.RwRule'],
            superuser_security_policy: Union[str,'OntapNetappVolume.SuperuserSecurityPolicy']
        ) -> 'OntapNetappVolume.PolicyRule':
            if isinstance(rw_rule, OntapNetappVolume.RwRule):
                rw_rule = rw_rule.value
            if isinstance(superuser_security_policy, OntapNetappVolume.SuperuserSecurityPolicy):
                superuser_security_policy = superuser_security_policy.value
            return cls((rw_rule,superuser_security_policy))

        @classmethod
        def get_all_values(cls):
            return [c.value for c in cls]

    class SecurityStyle(Enum):
        UNIX = "unix"
        NTFS = "ntfs"
        MIXED = "mixed" # should not be used unless absolutely necessary. no idea how to handle it.

        @classmethod
        def get_all_values(cls):
            return [c.value for c in cls]

        @classmethod
        def from_protocol(cls, protocol: Union[str,'OntapNetappVolume.VolProtocol']):
            if isinstance(protocol,OntapNetappVolume.VolProtocol):
                protocol = protocol.value
            if protocol == OntapNetappVolume.VolProtocol.CIFS.value:
                return cls.NTFS
            elif protocol == OntapNetappVolume.VolProtocol.NFS.value:
                return cls.UNIX
            else:
                raise ValueError("Unsupported share protocol %s. Supported values are %s",protocol,OntapNetappVolume.VolProtocol.get_all_values())

    class VolProtocol(Enum):
        NFS = "nfs"
        CIFS = "cifs"

        @classmethod
        def get_all_values(cls):
            return [c.value for c in cls]

        @classmethod
        def from_security_style(cls, security_style: Union[str,'OntapNetappVolume.SecurityStyle']):
            if isinstance(security_style,OntapNetappVolume.SecurityStyle):
                security_style = security_style.value
            if security_style == OntapNetappVolume.SecurityStyle.NTFS.value:
                return cls.CIFS
            elif security_style == OntapNetappVolume.SecurityStyle.UNIX.value:
                return cls.NFS
            else:
                raise ValueError("Unsupported security style %s. Supported values are %s" %
                                 (security_style, OntapNetappVolume.SecurityStyle.get_all_values()))

    #
    # utility static methods
    #
    @staticmethod
    def determine_compliance_name(name: str) -> str:
        if "snaplock" in name:
            raise Exception("Invalid name for non-compliance volume")
        return f"{name}-snaplock"

    @staticmethod
    def format_name_for_cmp(name: str) -> str:
        """format name for cmp.
        Replace invalid characters.

        :param name: remote resource name
        :type name: str
        :return: valid name for cmp
        :rtype: str
        """
        return name.replace("_","-")

    @staticmethod
    def format_name_for_remote(name: str) -> str:
        """format name for remote container.
        Replace invalid characters

        :param name: cmp resource name
        :type name: str
        :return: valid name for remote container
        :rtype: str
        """
        return name.replace("-","_")


    @staticmethod
    def get_format_export_location(security_style: str, path: str,ip_addr: str) -> str:
        """get and format export location.
        - if unix format is ip:path
        - if windows format is \ip\path

        :param security_style: security style (unix or ntfs)
        :type security_style: str
        :param path: export path
        :type path: str
        :param ip_addr: interface ip address
        :type ip_addr: str
        :raises ValueError: if unsupported security style
        :return: formatted export location
        :rtype: str
        """
        if security_style is None:
            # special case when volume is not mounted,
            # security style is not returned by the ontap api
            return None
        if security_style == "unix":
            export_location = f"{ip_addr}:{path}"
        elif security_style == "ntfs":
            formatted_path = path.replace("/", "\\")
            export_location = f"\\\\{ip_addr}{formatted_path}"
        else:
            raise ValueError(f"Unsupported share security style: {security_style}. Allowed values are [unix,ntfs]")
        return export_location

    #
    # discover, synchronize
    #
    @staticmethod
    def remote_resource_differs(
        existing_item: 'OntapNetappVolume',
        remote_name: str,
        remote_dict: Dict
    ):
        """determine if cmp resource is different from remote resource
        """
        # TODO check any static attributes
        expected_name = OntapNetappVolume.format_name_for_remote(existing_item.name)
        return expected_name != remote_name

    @staticmethod
    def discover_remote(container: 'OntapNetappContainer', ext_id=None, name=None):
        """
        Discover remote volumes that may or may not be already in cmp
        """
        manager = container.conn2
        if ext_id is not None:
            container.logger.debug("%s: Searching for volume with ext_id %s", container.name, ext_id)
            items = [manager.volume.get(ext_id)]
        elif name is not None:
            container.logger.debug("%s: Searching for volume with name %s", container.name, name)
            items = manager.volume.list(**{"name": name})
        else:
            container.logger.warning("Querying all remote volumes...")
            items = manager.volume.list()
        return items

    @staticmethod
    def discover_new(
        container: 'OntapNetappContainer',
        ext_id: Optional[str] = None,
        res_ext_ids: Optional[List[str]] = None
    ) -> List[Tuple[Type[IRESOURCE], Union[str, int], Union[str, int], str, str, Type[IRESOURCE]]]:
        """Discover method used when synchronize beehive container with remote platform.

        :param container: used to communicate with remote platform
        :param ext_id: remote platform entity id. ONLY WHEN SYNCHRONIZE A SINGLE EXT ID REMOTE OBJ
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resclass, ext_id, parent_id, resclass_objdef, name, parent_class)

        :raises ApiManagerError:
        """
        if res_ext_ids is None:
            res_ext_ids = []
        items = OntapNetappVolume.discover_remote(container=container,ext_id=ext_id)

        res = []
        for item in items:
            uuid = item.get("uuid")
            name = item.get("name")
            if uuid not in res_ext_ids:
                res.append(
                    (
                        OntapNetappVolume,
                        uuid,
                        None,
                        OntapNetappVolume.objdef,
                        name,
                        None,
                        (dict_get(item, "svm.uuid"), dict_get(item, "svm.name")),
                    )
                )
        return res


    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data:

            {
                'resclass': ..,
                'objid': ..,
                'name': ..,
                'ext_id': ..,
                'active': ..,
                'desc': ..,
                'attrib': ..,
                'parent': ..,
                'tags': ..
            }

        :raises ApiManagerError:
        """
        raise DeprecationWarning("Unsupported for OntapNetappVolume: call new import method from command line instead")
        # TODO rewrite so that it calls the import code?

        #resclass = entity[0]
        #ext_id = entity[1]
        #parent_id = entity[2]
        #name = entity[4]
        #(svm_ext_id, svm_name) = entity[6]

        #objid = "%s//%s" % (container.objid, id_gen())

        #res = {
        #    "resource_class": resclass,
        #    "objid": objid,
        #    "name": OntapNetappVolume.format_name_for_cmp(name),
        #    "ext_id": ext_id,
        #    "active": True,
        #    "desc": resclass.objdesc,
        #    "attrib": {"svm_ext_id": svm_ext_id, "svm_name": svm_name},
        #    "parent": parent_id,
        #    "tags": resclass.default_tags,
        #}

        #return res

    #
    # internal get, list, related methods
    #

    def info(self):
        """Get infos.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OntapNetappResource.info(self)
        info["role"] = self.get_role()
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OntapNetappResource.detail(self)
        info["role"] = self.get_role()

        if self.ext_id is None or self.ext_id=="":
            info["details"]["error_list"] = [f"Invalid value for ext_id: '{self.ext_id}'"]
            return info

        info["details"]["remote_data"] = self.ext_obj_wrap

        # init error list
        error_list = [] # list of errors to show without giving an exception

        try:
            info["details"]["size"] = self.get_size()
            info["details"]["size_bytes"] = self.get_size_bytes()
        except Exception as ex:
            error_list.append(str(ex))

        try:
            snapmirrors = self.get_snapmirror_list()
            info["details"]["snapmirror"] = snapmirrors
            if self.get_role() == OntapNetappVolume.Role.DR.value:
                # in case of DR, the snapmirror list is composed of one item because only a DR per site can exist by design
                rel_uuid = snapmirrors[0].get("uuid")
                info["details"]["snapmirror_policy"] = self.get_snapmirror_policy(rel_uuid)
        except Exception as ex:
            error_list.append(str(ex))

        try:
            info["details"]["export_locations"] = self.export_locations
        except ApiManagerError as ex:
            # info["details"]["export_locations"] = "N/A" # move to cli
            error_list.append(ex.value)

        # legacy export locations
        try:
            info["export_locations"] = self.get_export_locations()
        except (ApiManagerError,Exception) as ex:
            # info["export_locations"] = "N/A" # move to cli
            error_list.append(str(ex))

        try:
            info["details"]["grants"] = self.grant_list()
        except ApiManagerError as ex:
            error_list.append(ex.value)

        #info["details"]["errors"] = ", ".join(error_list)

        return info

    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        return entities

    #
    # pre,post methods
    #
    def post_get(self): # TODO remove if not implemented
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        pass

    @staticmethod
    def pre_create(controller: 'ResourceController', container, *args, **kwargs):
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
        :param kvargs.ontap_volume_id: physical id of volume in ontap netapp platform
        :return: kvargs
        :raise ApiManagerError:
        """
        netapp_volume_id = kwargs.get("ontap_volume_id")
        if netapp_volume_id is not None:
            #
            # v1.0 staas - legacy
            #
            netapp_volume = OntapNetappVolume.get_remote_volume(controller, netapp_volume_id, container, netapp_volume_id)

            if netapp_volume == {}:
                raise ApiManagerError("ontap netapp volume %s was not found" % netapp_volume_id)
            kwargs["ext_id"] = netapp_volume_id

            # get svm
            netapp_svm_id = dict_get(netapp_volume, "svm.uuid")

            # check netapp svm resource exists
            svm_resource = controller.get_resource_by_extid(netapp_svm_id)

            # create netapp svm resource
            if svm_resource is None:
                netapp_svm = OntapNetappVolume.get_remote_svm(controller, netapp_svm_id, container, netapp_svm_id)
                name = netapp_svm.get("name")
                svm_conf = {
                    "name": name,
                    "desc": name,
                    "ext_id": netapp_svm_id,
                    "parent": None,
                }
                from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm
                resource_uuid, code = container.resource_factory(OntapNetappSvm, **svm_conf)
                svm_resource = controller.get_simple_resource(resource_uuid.get("uuid"))

            kwargs["attribute"]["svm"] = svm_resource.oid
        else:
            #
            # v2.0 staas - new
            #
            role = kwargs.get("role",OntapNetappVolume.Role.MAIN.value)
            _ = OntapNetappVolume.Role(role) # check valid

            # keep awx params aside for deletion and other operations
            awx_params = kwargs.get("awx_params")

            share_params = kwargs.get("share_params")
            ontap_name = OntapNetappVolume.format_name_for_remote(kwargs.get("name"))
            share_protocol = OntapNetappVolume.VolProtocol(share_params.get("share_proto")).value
            security_style = OntapNetappVolume.SecurityStyle.from_protocol(share_protocol).value

            cluster = share_params.get("cluster")
            svm = share_params.get("svm")
            volume_size = share_params.get("size")

            if volume_size:
                # simple size check
                try:
                    v_size = int(float(volume_size))
                    if v_size <= 0:
                        raise ValueError("negative size")
                except ValueError as ex:
                    raise ValueError("invalid volume size") from ex

            from_id = share_params.get("from_id")
            extra_vars = {}
            if role==OntapNetappVolume.Role.DR.value and from_id:
                # replica creation
                kwargs["awx_playbook"] = "snapmirror.yaml"
                source_volume = controller.get_resource(oid=from_id,entity_class=OntapNetappVolume)
                source_attribs = source_volume.get_attribs()
                source_cluster = source_attribs.get("cluster")
                source_svm = source_attribs.get("svm")
                source_volume = source_attribs.get("remote_name")
                source_size = int(float(source_attribs.get("size")))
                replica_rpo = share_params.get("rpo")
                extra_vars = {
                    "p_source_cluster": source_cluster,
                    "p_source_vserver": source_svm,
                    "p_volume": source_volume,
                    "p_volume_size": source_size,
                    "p_destination_cluster": cluster,
                    "p_destination_vserver": svm,
                    "p_destination_volume": ontap_name, #(default dr_${p_volume})
                    "p_rpo": replica_rpo,
                    "p_operation": "create"
                }
            elif role==OntapNetappVolume.Role.MAIN.value and not from_id:
                # normal volume creation
                kwargs["awx_playbook"] = "volume.yaml"
                extra_vars = {
                    "p_cluster": cluster,
                    "p_vserver": svm,
                    "p_volume": ontap_name,
                    "p_aggr": share_params.get("aggregate"),
                    "p_volume_size": share_params.get("size"),
                    "p_protocol": share_protocol,
                    "p_security_style": security_style,
                    # se la passo ma non esiste usa "default" che però non è il default da utilizzare...
                    #"p_snapshot_policy": share_params.get("snapshot_policy"), # optional, defaults to None, which defaults to... see playbook
                    "p_volume_type": "rw",
                    "p_client": share_params.get("client_ip",[]), #optional, can be changed later
                    "p_iscompliance": False, # default
                    "p_encrypt": share_params.get("encrypted", False),
                    "p_operation": "create"
                }
                snapshot_policy = share_params.get("snapshot_policy")
                if snapshot_policy:
                    extra_vars.update({"p_snapshot_policy": snapshot_policy})

                if kwargs.get("compliance"):
                    compliance_share_params = kwargs.get("compliance_share_params")
                    snaplock_cluster = compliance_share_params.get("snaplock_cluster")
                    snaplock_svm = compliance_share_params.get("snaplock_svm")
                    snaplock_aggregate = compliance_share_params.get("snaplock_aggregate")
                    snaplock_rpo = compliance_share_params.get("rpo")
                    extra_vars.update({
                        "p_iscompliance": True,
                        "p_destination_cluster": snaplock_cluster,
                        "p_destination_vserver": snaplock_svm,
                        "p_destination_aggr": snaplock_aggregate,
                        "p_rpo": snaplock_rpo, # retention period? (12h or 24h)
                        # nel playbook: snapmirror_policy_name "staas_vault_7dlock_14d_5w"
                        # nel playbook: snapmirror_policy: "{{ snapmirror_policy_name }}_{{ p_rpo }}"
                    })
            elif kwargs.get("allow_snaplock_import",False):
                # TODO change behavior for snaplock import. now it's ok. better if moved elsewhere
                kwargs.pop("allow_snaplock_import")
            else:
                raise Exception("Invalid role-params combination: role = %s - from_id = %s" % (role,from_id))

            if extra_vars: # TODO check import case
                kwargs["extra_vars"] = extra_vars
            kwargs["remote_name"] = ontap_name
            steps = [
                OntapNetappVolume.task_base_path + "create_resource_pre_step",
                OntapNetappVolume.task_base_path + "volume_create_physical_step",
                OntapNetappVolume.task_base_path + "create_resource_post_step",
            ]
            kwargs["steps"] = steps

            # should be False, when called from ontap resource create endpoint,
            # for tasks it depends, but generally True if using run_sync_task later
            kwargs["sync"] = kwargs.get("sync",False)

            kwargs["attribute"] = {
                "size":  volume_size,
                "share_proto": share_protocol,
                "cluster": cluster,
                "svm": svm,
                "remote_name": ontap_name,
                "awx_params": awx_params,
                "role": role
            }
            if kwargs.get("dry_run",False):
                from beehive_resource.plugins.ontap.task_v2.dry_run import resolve_dryrun
                steps = [resolve_dryrun(step,False) for step in steps]
                kwargs["steps"] = steps

        return kwargs

    @staticmethod
    def pre_import(controller: 'ResourceController', container: 'OntapNetappContainer', *args, **kwargs):
        """
        check input params before resource import
        same as pre_create, but different steps and name handling
        """
        # make sure name formatted correctly for cmp

        kwargs["name"] = OntapNetappVolume.format_name_for_cmp(kwargs.get("name"))
        remote_name = OntapNetappVolume.format_name_for_remote(kwargs.get("name"))

        # check if volume to import exists
        remote_volumes = container.conn2.volume.list(name=remote_name)
        if len(remote_volumes)==0:
            raise Exception("Remote volume with name %s not found" % remote_name)
        if len(remote_volumes)>1:
            raise Exception("More than one volume with name %s" % remote_name)

        # get metadata from volume
        remote_volume = remote_volumes[0]
        if kwargs.get("vol_ext_id"):
            remote_ext_id = remote_volume.get("uuid")
            expected_ext_id = kwargs.get("vol_ext_id")
            # expected ext id was known before import (e.g. import of already existing volume)
            if remote_ext_id != expected_ext_id:
                raise Exception(
                    "unexpected ext_id found remotely. was expecting %s but found %s"
                    % (expected_ext_id, remote_ext_id)
                )
            # ignore metadata and sync it later
            # TODO
            kwargs["sync"] = kwargs.get("sync",False)
            role = kwargs.get("role",OntapNetappVolume.Role.MAIN.value)
            _ = OntapNetappVolume.Role(role)
            kwargs["attribute"] = {
                #"size":  volume_size,
                #"share_proto": share_protocol,
                "cluster": kwargs["share_params"]["cluster"],
                "svm": kwargs["share_params"]["svm"],
                "remote_name": remote_name,
                #"awx_params": awx_params,
                "role": role
            }
            kwargs["remote_name"] = remote_name # mandatory
        else:
            try:
                size = round(remote_volume.get("space").get("size") / 1073741824, 3)
                security_style = OntapNetappVolume.SecurityStyle(remote_volume.get("nas").get("security_style")).value
                kwargs["share_params"]["size"] = size
                kwargs["share_params"]["share_proto"] = OntapNetappVolume.VolProtocol.from_security_style(security_style).value
            except Exception as ex:
                # sync later
                controller.logger.warning("metadata error during import: %s" % ex)

            kwargs["allow_snaplock_import"] = True # TODO handle this case better
            kwargs = OntapNetappVolume.pre_create(controller,container,*args,**kwargs)
            kwargs.pop("extra_vars", None)

        steps = [
            OntapNetappVolume.task_base_path + "create_resource_pre_step",
            OntapNetappVolume.task_base_path + "volume_import_physical_step",
            OntapNetappVolume.task_base_path + "create_resource_post_step",
            OntapNetappVolume.task_base_path + "check_update_info_against_remote_volume_v2",
        ]
        if kwargs.get("dry_run",False):
            from beehive_resource.plugins.ontap.task_v2.dry_run import resolve_dryrun
            steps = [resolve_dryrun(step,False) for step in steps]
            kwargs["steps"] = steps
        kwargs["steps"] = steps
        return kwargs

    def pre_delete(self, *args, **kwargs):
        """Pre delete function. This function is used in delete method."""
        if self.parent is not None:
            #vecchia gestione
            return kwargs

        if self.ext_id and self.ext_id!="": # in case ext_id unset by cli
            steps = [
                OntapNetappVolume.task_base_path + "expunge_resource_pre_step"
            ]
            if self.get_role()==OntapNetappVolume.Role.DR.value and len(self.get_snapmirror_list())>0:
                compliance = False
                awx_playbook_unlink = "snapmirror.yaml"
                operation = "delete"
                source_info = kwargs.get("source_info")
                if not source_info:
                    raise Exception("Source information missing")
                extra_vars_unlink = {
                    "p_source_cluster": source_info.get("source_cluster"),
                    "p_source_vserver": source_info.get("source_svm"),
                    "p_volume": source_info.get("source_volume"),
                    "p_destination_cluster": self.get_attribs("cluster"),
                    "p_destination_vserver": self.get_attribs("svm"),
                    "p_destination_volume": self.get_attribs("remote_name"),
                    "p_operation": operation,
                    "p_iscompliance": compliance,
                }

                steps.append({
                        "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                        "args": [operation, awx_playbook_unlink, extra_vars_unlink]
                })
            elif self.get_role()==OntapNetappVolume.Role.SNAPLOCK.value:
                self.check_snaplock_can_be_deleted()
                compliance = False
            else:
                # main volume
                # compliance = kwargs.get("compliance")
                compliance = False # for main volume deletion. in any case, compliance or not.

            if compliance is None:
                compliance = self.get_attribs("awx_params",{}).get("p_iscompliance",False) # ??? this is probably always wrong

            awx_playbook_del = "volume.yaml"
            extra_vars_del = {
                "p_cluster": self.get_attribs("cluster"),
                "p_vserver" : self.get_attribs("svm"),
                "p_volume": self.get_attribs("remote_name"),
                "p_operation": "delete",
                "p_iscompliance": compliance,
            }
            steps.extend([
                {
                    "step": OntapNetappVolume.task_base_path + "volume_delete_physical_step",
                    "args": [awx_playbook_del, extra_vars_del],
                },
                OntapNetappVolume.task_base_path + "expunge_resource_post_step",
            ])
            awx_params = kwargs.get("awx_params")
            if not awx_params:
                kwargs["awx_params"] = self.get_attribs("awx_params")
            kwargs["steps"] = steps
        else:
            steps = [
                OntapNetappVolume.task_base_path + "expunge_resource_pre_step",
                OntapNetappVolume.task_base_path + "expunge_resource_post_step",
            ]
            kwargs["steps"] = steps
        return kwargs

    #
    # info
    #

    def get_size_bytes(self):
        """
        get overall volume size in bytes
        """
        # TODO check when size != space.size
        size_bytes = dict_get(self.ext_obj_wrap, "size")
        if size_bytes is None:
            self.logger.error("unable to get size")
            raise ApiManagerError("unable to get size")
        return size_bytes

    def get_size(self):
        """
        get overall volume size in GB
        """
        # TODO check when size != space.size
        size_bytes = dict_get(self.ext_obj_wrap, "size")
        if size_bytes is None:
            self.logger.error("unable to get size")
            raise ApiManagerError("unable to get size")
        size = round(size_bytes / 1073741824, 3)
        return size

    def get_share_proto(self) -> str:
        """get share proto

        :return: share protocol (nfs,cifs) or None
        :rtype: str
        """
        # get principal share protocol
        res = None
        nas_security_style = dict_get(self.ext_obj_wrap, "nas.security_style")
        if not nas_security_style:
            # special case when volume is not mounted,
            # security style is not returned by the ontap api
            return None
        try:
            res = OntapNetappVolume.VolProtocol.from_security_style(nas_security_style).value
        except ValueError as ex:
            self.logger.error("Invalid security style: %s", nas_security_style)
        self.logger.debug("get volume %s share protocol: %s", self.oid, res)
        return res

    def get_export_locations(self) -> List[str]:
        """get share export locations

        :return: list of formatted export locations
        :rtype: List[str]
        :raises ValueError: if unsupported security style
        """
        res = []
        if self.ext_obj_wrap and self.svm_legacy:
            nas_security_style = dict_get(self.ext_obj_wrap, "nas.security_style")
            nas_path = dict_get(self.ext_obj_wrap, "nas.path", default="")
            mounts = []
            for ip_interface in self.svm_legacy.get_ip_interfaces():
                ip = ip_interface.get("ip")
                if ip is not None:
                    export_location = OntapNetappVolume.get_format_export_location(
                        nas_security_style,
                        nas_path,
                        ip
                    )
                    mounts.append(export_location)
                else:
                    self.logger.warning("volume %s interface has no ip address", self.oid)
            if mounts:
                res.append({
                    "protocol": self.get_share_proto(),
                    "mounts": mounts
                })
        self.logger.debug("get volume %s export locations: %s", self.oid, res)
        return res

    def grant_list(self): # TODO rewrite completely
        """Get volume grant list

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
        res = []
        security_style = dict_get(self.ext_obj_wrap, "nas.security_style")
        if security_style == "ntfs":
            shares = self.get_remote_cifs_shares(self.controller, self.ext_id, self.container_wrap, self.ext_id)
            for share in shares:
                for rule in share.pop("acls", []):
                    if rule.get("permission", None) != "full_control":
                        access_level = "ro"
                    else:
                        access_level = "rw"
                    # TODO rewrite
                    acl = {
                        "access_key": None,
                        "created_at": None,
                        "updated_at": None,
                        "access_type": "ip",
                        "access_to": dict_get(rule, "user_or_group"),
                        "access_level": access_level,
                        "state": "active",
                        "id": None,
                    }
                    res.append(acl)
        elif security_style == "unix":
            export_policy = dict_get(self.ext_obj_wrap, "nas.export_policy")
            if export_policy is not None:
                policy_id = export_policy.get("id")
                export_policy = self.get_remote_nfs_export_policy(self.container_wrap, policy_id)
                for rule in export_policy.pop("rules", []):
                    acl = {
                        "id": rule.get("index"),
                        "ro_access": rule.get("ro_rule"),
                        "rw_access": rule.get("rw_rule"),
                        "su_access": rule.get("superuser"),
                        "protocols": rule.get("protocols"),
                        "clients": [client.get("match") for client in rule.get("clients")]
                    }
                    res.append(acl)
        return res

    def get_snaplock_information(self):
        """return snaplock information

        :return: dictionary containing: \n
            - uuid \n
            - source path \n
            - destination path \n
            - state (e.g. mirrored, broken off) \n
            - healthy (i.e. True, False) \n
            or None if not a snaplock volume \n
        :rtype: Dict[str,Any] | None
        """
        if self.get_role()!=OntapNetappVolume.Role.SNAPLOCK.value:
            return None
        svm_name = self.get_attribs("svm")
        remote_volume_name = self.ext_obj_wrap.get("name")
        svm_col_volume = f"{svm_name}:{remote_volume_name}"
        self.logger.debug("Searching for snaplock relationship")
        res = self.get_remote_snapmirror(
            self.controller, self.ext_id, self.container_wrap,
            destination_path=svm_col_volume, search_local=True, search_remote=False
        )
        if not res:
            self.logger.error("Unable to find snaplock relationship using destination path: %s", svm_col_volume)
            return None
        # len(res)>1 should be impossible.
        snaplock_relationship = res[0]
        return {
            "uuid": snaplock_relationship.get("uuid"),
            "source_path": snaplock_relationship.get("source",{}).get("path"),
            "dest_path": snaplock_relationship.get("destination",{}).get("path"),
            "state": snaplock_relationship.get("state"),
            "healthy": snaplock_relationship.get("healthy"),
            "policy_name": snaplock_relationship.get("policy",{}).get("name")
        }

    def get_snapmirror_list(self):
        """
        get volume snapmirror destination list. use it to cross-check with links to snapmirror volumes in cmp

        :raises Exception:
        :return: list of snapmirror information, each containing: \n
            - uuid \n
            - source path \n
            - destination path \n
            - state (e.g. mirrored, broken off) \n
            - healthy (i.e. True, False) \n
        :rtype: List[Dict] | []
        """
        svm_name = self.get_attribs("svm")
        remote_volume_name = self.ext_obj_wrap.get("name")
        svm_col_volume = f"{svm_name}:{remote_volume_name}"
        if self.get_role()==OntapNetappVolume.Role.MAIN.value and self.has_snapmirror():
            snapmirror_list = self.get_remote_snapmirror(
                self.controller, self.ext_id, self.container_wrap,
                source_path=svm_col_volume, search_local=False, search_remote=True
            )
            self.logger.debug("get snapmirrors with source_path '%s': %s",svm_col_volume, snapmirror_list)
        elif self.get_role()==OntapNetappVolume.Role.DR.value:
            snapmirror_list = self.get_remote_snapmirror(
                self.controller, self.ext_id, self.container_wrap,
                destination_path=svm_col_volume, search_local=True, search_remote=False
            )
            self.logger.debug("get snapmirrors with destination_path '%s': %s",svm_col_volume, snapmirror_list)
        else:
            self.logger.debug("skipping snapmirrors search for volume with role %s",self.get_role())
            return []
        ret = []
        for r in snapmirror_list:
            ret.append({
                "uuid": r.get("uuid"),
                "source_path": r.get("source",{}).get("path"),
                "dest_path": r.get("destination",{}).get("path"),
                "state": r.get("state"),      # NB: only available on destination
                "healthy": r.get("healthy"),  # NB: only available on destination
                "policy_name": r.get("policy",{}).get("name")
            })
        return ret

    def get_snapmirror_policy(self, relationship_id: str) -> str:
        """Get the policy associated to the given snapmirror relationship

        :param relationship_id: snapmirror relationship uuid
        :return: snapmirror policy
        """
        rel_info = self.get_remote_snapmirror_with_policy(
            controller=None,
            postfix=None,
            container=self.container_wrap,
            relationship_id=relationship_id
        )
        return rel_info.get("policy", {}).get("name")

    def has_snapmirror(self):
        """
        check if snapmirror is configured
        NB: it might take some time to change, after snapmirror creation. it's not instant.
        """
        if dict_get(self.ext_obj_wrap, "snapmirror.is_protected", default=False) is True:
            return True
        return False

    def get_role(self) -> Optional[str]:
        """return volume "role".
        It can be one of the following:
        - "main": a normal volume
        - "snaplock": a snaplock volume
        - "dr": a snapmirror dr volume
        - None if not set

        :return: the volume "role"
        :rtype: Optional[str]
        """
        return self.get_attribs("role")

    def delete_snaplock_relationship(self):
        """delete snaplock relationship from ontap

        :raises Exception: if error
        """
        role = self.get_role()
        if role != OntapNetappVolume.Role.SNAPLOCK.value:
            raise Exception("Invalid role: volume is not a snaplock volume")
        res = self.get_snaplock_information()
        if not res:
            # nothing to do
            self.logger.info("No snaplock found. Nothing to delete")
            return
        relationship_uuid = res.get("uuid")
        self.container_wrap.conn2.snapmirror.delete(relationship_uuid)
        self.logger.info("Snaplock relationship deleted")

    def schedule_for_deletion(self, days_offset: int):
        """set attributes so that
        snaplock volume can be deleted by a batch

        :param days_offset: offset in days
        :type days_offset: int

        rounds up to next day
        """
        role = self.get_role()
        if role != OntapNetappVolume.Role.SNAPLOCK.value:
            raise Exception("Invalid role: volume is not a snaplock volume")
        from datetime import date, timedelta, datetime
        dt = datetime.combine(date.today(), datetime.min.time())
        delete_after = dt + timedelta(days=float(days_offset))
        self.set_configs(key="delete_after", value=delete_after.isoformat())
        self.set_configs(key="deletable", value=True)

    def check_snaplock_can_be_deleted(self):
        """
        raise exception if snaplock can't be deleted yet or other error conditions
        """
        if self.get_role() != OntapNetappVolume.Role.SNAPLOCK.value:
            raise Exception("Invalid volume role %s" % self.get_role())
        snaplock_info = self.get_remote_snaplock_info(self.container_wrap,self.ext_id).get("snaplock")
        if not snaplock_info:
            raise Exception("Unable to fetch snaplock information")
        snaplock_type = snaplock_info.get("type")
        if snaplock_type != "compliance":
            raise Exception("Unexpected: snaplock type is not 'compliance' but is %s" % snaplock_type)
        if not self.get_attribs("deletable",False):
            raise Exception("Snaplock volume not yet set for deletion")
        if self.get_snaplock_information():
            raise Exception("Unexpected situation. Found a snapmirror relationship.")
        cmp_check = self.get_attribs("delete_after")
        from datetime import datetime
        if cmp_check:
            try:
                cmp_check = datetime.fromisoformat(cmp_check)
                if datetime.today() < cmp_check:
                    # specific check date set and today is not after the target date
                    raise Exception(f"Not yet time to attempt deletion: delete after {cmp_check}")
            except (TypeError, ValueError) as ex:
                self.logger.error("Error checking snaplock cmp date threshold for deletion: %s" % ex)

        compliance_clock_time = snaplock_info.get("compliance_clock_time")
        expiry_time = snaplock_info.get("expiry_time")
        try:
            compliance_clock_time = datetime.fromisoformat(compliance_clock_time)
            expiry_time = datetime.fromisoformat(expiry_time)
            if compliance_clock_time <= expiry_time:
                raise Exception("Not yet time for deletion. Expiry time: %s" % expiry_time)
        except (TypeError, ValueError) as ex:
            self.logger.error("Error checking snaplock remote date threshold for deletion: %s" % ex)
        # continue and attempt to delete it all the same hoping only the metadata or checks are wrong
        return

    def check(self):
        """Check resource

        :return: dict with check result. {'check': True, 'msg': None}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        result = False
        errors = []
        # TODO
        raise NotImplementedError
        res = {"check": True, "msg": None}
        return res

    def clean_cache(self):
        """Clean cache and unset properties that can change"""
        # deletes by pattern *.<ext_id>
        # so it also deletes ontap_netapp.volume.get.<ext_id>
        super().clean_cache()
        self.ext_obj = None
        #self._svm_legacy = None
        #self._svm = None

    def check_update_info_against_remote_volume(self):
        self.clean_cache()
        self.set_configs("size",self.get_size())
        self.set_configs("share_proto",self.get_share_proto())
        self.set_configs("remote_name",self.ext_obj_wrap.get("name"))

    # actions
    @trace(op='update')
    def resize(self, extend_shrink: str, new_size: int, awx_params: Dict = None, **kvargs):
        self.check_active()

        # TODO check quotas at provider level
        current_size = self.get_size()

        if extend_shrink=="extend" and new_size<=current_size:
            raise ApiManagerError("Requested volume extend, but new size (%s) is same or less than current size (%s)" % (new_size,current_size))
        elif extend_shrink=="shrink" and new_size>=current_size:
            raise ApiManagerError("Requested volume shrink, but new size (%s) is same or more than current size (%s)" % (new_size,current_size))

        operation = "resize"
        awx_playbook = "volume.yaml"
        extra_vars = {
            "p_cluster": self.get_attribs("cluster"),
            "p_vserver" : self.get_attribs("svm"),
            "p_volume": self.get_attribs("remote_name"),
            "p_volume_size": new_size,
            "p_operation": operation,
            "p_iscompliance": "false",
        }
        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("resize",steps=steps,log="Run volume resize action",
                             awx_params=awx_params, sync=True)
        return res

    @trace(op='update')
    def manage_policy(
        self,
        action: str = None,
        su_access: str = None,
        rw_access: str = None,
        clients: List = None,
        access_ids: List = None,
        protocol: str = None,
        awx_params: Dict = None,
        **kvargs
    ):
        self.check_active()

        awx_playbook = "volume.yaml"

        if not protocol:
            protocol = self.get_attribs("share_proto")

        extra_vars = {
            "p_cluster": self.get_attribs("cluster"),
            "p_vserver": self.get_attribs("svm"),
            "p_volume": self.get_attribs("remote_name"),
        }

        if action == "grant_access":
            operation = "addpolicy"
            extra_vars.update(
                {
                    "p_operation": operation,
                    "p_rw_rule": rw_access,
                    "p_su_security": su_access,
                    "p_protocol": protocol,
                    "p_client": clients,
                    "p_iscompliance": "false",
                }
            )
        elif action == "revoke_access":
            operation = "rmpolicy"
            extra_vars.update(
                {
                    "p_operation": operation,
                    "p_rule_index": access_ids,
                }
            )
        else:
            raise ApiManagerError(f"Action is not supported: {action}")

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action(f"{action}", steps=steps, log="Run volume policy action",
                             awx_params=awx_params, sync=True)
        return res

    @trace(op='update')
    def set_volume_state(self, wanted_state: Literal["offline","online"], awx_params: Dict = None, **kvargs):
        """set ontap volume state. List of possible states;
        - Online: Read and write access to this volume is allowed.
        - Restricted: Some operations, such as parity reconstruction, are allowed, but data access is not allowed.
        - Offline: No access to the volume is allowed.
        This command supports ONLINE and OFFLINE only.

        :param wanted_state: the desired state
        :type wanted_state: Literal[&quot;offline&quot;,&quot;online&quot;]
        :raises Exception: _description_
        :raises Exception: _description_
        :return: _description_
        :rtype: _type_
        """
        self.check_active()

        awx_playbook = "volume.yaml"
        extra_vars = {
            "p_cluster": self.get_attribs("cluster"),
            "p_vserver": self.get_attribs("svm"),
            "p_volume": self.get_attribs("remote_name"),
            "p_operation": wanted_state
        }
        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": ["set_volume_state", awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("set_volume_state", steps=steps,log="Set volume state action",
                             awx_params=awx_params, sync=True)
        return res

    @trace(op="update")
    def manage_snapshot_policy(self, action: str = None, snapshot_policy: str = None, awx_params: Dict = None, **kvargs):
        """Manage ontap volume snapshot policy

        :param action: the operation to execute
        :param snapshot_policy: the snapshot policy to apply
        :raises Exception: _description_
        :return: _description_
        """
        self.check_active()

        awx_playbook = "snapshot.yaml"

        extra_vars = {
            "p_cluster": self.get_attribs("cluster"),
            "p_vserver": self.get_attribs("svm"),
            "p_volume": self.get_attribs("remote_name"),
            "p_snapshot": snapshot_policy,
        }

        if action == "update":
            extra_vars.update({"p_operation": action})
        else:
            raise Exception("Unknown action: %s" % action)

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": ["set_volume_state", awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("set_volume_state", steps=steps, log="Set volume state action",
                             awx_params=awx_params, sync=True)
        return res

    @trace(op='update')
    def manage(self, sub_action: str, **kwargs):
        if sub_action=="mount":
            return self._mount()

    @trace(op='update')
    def compliance_enable(self, **kwargs):
        src_cluster = self.get_attribs("cluster")
        src_svm = self.get_attribs("svm")
        src_aggregate = kwargs.get("aggregate")
        src_volume = self.get_attribs("remote_name")
        src_volume_size = int(float(self.get_attribs("size")))
        compliance_share_params = kwargs.get("compliance_share_params")
        dst_cluster = compliance_share_params.get("snaplock_cluster")
        dst_aggregate = compliance_share_params.get("snaplock_aggregate")
        dst_svm = compliance_share_params.get("snaplock_svm")
        dst_rpo = compliance_share_params.get("rpo")
        encrypted = dict_get(self.ext_obj_wrap, "encryption.enabled", default=False)
        nas_security_style = dict_get(self.ext_obj_wrap, "nas.security_style")
        awx_params = kwargs.get("awx_params")

        return self._compliance_enable(
            src_cluster=src_cluster,
            src_svm=src_svm,
            src_volume=src_volume,
            src_aggregate=src_aggregate,
            src_volume_size=src_volume_size,
            dst_cluster=dst_cluster,
            dst_aggregate=dst_aggregate,
            dst_svm=dst_svm,
            dst_rpo=dst_rpo,
            encrypted=encrypted,
            security_style=nas_security_style,
            awx_params=awx_params
        )

    def _compliance_enable(self,
        src_cluster: str, src_svm: str, src_aggregate: str, src_volume: str, src_volume_size: int,
        security_style: str, dst_cluster: str, dst_aggregate: str, dst_svm: str, dst_rpo: str,
        encrypted: str, awx_params: Dict = None):

        self.check_active()

        awx_playbook = "volume.yaml"
        operation = "create"
        extra_vars = {
            "p_cluster": src_cluster,
            "p_vserver": src_svm,
            "p_aggr": src_aggregate,
            "p_volume": src_volume,
            "p_volume_size": src_volume_size,
            "p_encrypt": encrypted,
            "p_security_style": security_style,
            "p_destination_cluster": dst_cluster,
            "p_destination_aggr": dst_aggregate,
            "p_destination_vserver": dst_svm,
            "p_rpo": dst_rpo,
            "p_iscompliance": "true",
            "p_operation": operation,
        }

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("compliance_enable", steps=steps, log="Run volume resize action",
                             awx_params=awx_params, sync=True)
        return res

    @trace(op='update')
    def replica_manage(
        self, sub_action: str,
        source_cluster: str, source_svm: str, source_volume: str,
        new_name: str = None, rpo: str = None,
        awx_params = None, **kwargs
    ):
        destination_cluster = self.get_attribs("cluster")
        destination_svm = self.get_attribs("svm")
        destination_volume = self.get_attribs("remote_name")

        execute_in_single_transaction = kwargs.get("execute_in_single_transaction", False)

        if sub_action=="replica_suspend":
            return self._replica_suspend(
                source_cluster=source_cluster,
                source_svm=source_svm,
                source_volume=source_volume,
                destination_cluster=destination_cluster,
                destination_svm=destination_svm,
                destination_volume=destination_volume,
                execute_in_single_transaction=execute_in_single_transaction
            )
        elif sub_action=="replica_resume":
            return self._replica_resume(
                source_cluster=source_cluster,
                source_svm=source_svm,
                source_volume=source_volume,
                destination_cluster=destination_cluster,
                destination_svm=destination_svm,
                destination_volume=destination_volume,
                execute_in_single_transaction=execute_in_single_transaction,
                awx_params=awx_params
            )
        elif sub_action=="replica_unlink":
            if not new_name:
                raise Exception("Must provide new name for the former replica volume, when deleting snapmirror relationship")

            encrypted = dict_get(self.ext_obj_wrap, "encryption.enabled", default=False)
            current_remote_name = self.ext_obj_wrap.get("name")
            if current_remote_name!=destination_volume:
                # trying to handle cases when cmp error after rename
                # after which case, launch this command again
                destination_volume = current_remote_name

            return self._replica_unlink(
                source_cluster=source_cluster,
                source_svm=source_svm,
                source_volume=source_volume,
                destination_cluster=destination_cluster,
                destination_svm=destination_svm,
                destination_volume=destination_volume,
                new_name=new_name,
                execute_in_single_transaction=execute_in_single_transaction,
                encrypted=encrypted,
                awx_params=awx_params
            )
        elif sub_action == "replica_update":
            return self._replica_update(
                source_cluster=source_cluster,
                source_svm=source_svm,
                source_volume=source_volume,
                destination_cluster=destination_cluster,
                destination_svm=destination_svm,
                destination_volume=destination_volume,
                destination_rpo=rpo,
                execute_in_single_transaction=execute_in_single_transaction,
                awx_params=awx_params
            )
        #elif sub_action=="replica_mount":
        #    return self._replica_mount()
        else:
            raise Exception("Invalid action %s" % sub_action)

    def _replica_suspend(
        self,
        source_cluster: str, source_svm: str, source_volume: str,
        destination_cluster: str, destination_svm: str, destination_volume: str,
        execute_in_single_transaction = False,
        awx_params: Dict = None
    ):
        self.check_active()

        awx_playbook = "snapmirror.yaml"
        operation = "broken"
        extra_vars = {
            "p_source_cluster": source_cluster,
            "p_source_vserver": source_svm,
            "p_volume": source_volume,
            "p_destination_cluster": destination_cluster,
            "p_destination_vserver": destination_svm,
            "p_destination_volume": destination_volume,
            "p_operation": operation,
            "p_iscompliance": "false",
        }

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("replica_suspend", steps=steps,log="Suspend replica relationship",
                             awx_params=awx_params, sync=True)
        return res

    def _replica_resume(
        self,
        source_cluster: str, source_svm: str, source_volume: str,
        destination_cluster: str, destination_svm: str, destination_volume: str,
        execute_in_single_transaction = False,
        awx_params: Dict = None
    ):
        self.check_active()

        awx_playbook = "snapmirror.yaml"
        operation = "active"
        extra_vars = {
            "p_source_cluster": source_cluster,
            "p_source_vserver": source_svm,
            "p_volume": source_volume,
            "p_destination_cluster": destination_cluster,
            "p_destination_vserver" : destination_svm,
            "p_destination_volume": destination_volume,
            "p_operation": operation,
            "p_iscompliance": "false",
        }

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("replica_resume", steps=steps,log="Resume replica relationship",
                             awx_params=awx_params, sync=True)
        return res

    def _replica_unlink(
        self,
        source_cluster: str, source_svm: str, source_volume: str,
        destination_cluster: str, destination_svm: str, destination_volume: str,
        new_name: str, execute_in_single_transaction = True, encrypted: bool = False,
        awx_params: Dict = None
    ):
        self.check_active()
        if self.get_role()!= OntapNetappVolume.Role.DR.value:
            raise Exception("Invalid volume role %s for action replica_unlink" % self.get_role())

        if not new_name:
            raise Exception("new_name parameter missing")

        remote_name = self.format_name_for_remote(new_name)
        if remote_name.startswith("dr_"):
            raise Exception("new_name must not start with string 'dr_'. original: %s - after substitution rules: %s" % (new_name, remote_name))

        # update role here. we are already in a transaction so in case of errors everything will be rolled back
        self.set_configs("role", OntapNetappVolume.Role.MAIN.value)

        awx_playbook1 = "snapmirror.yaml"
        operation1 = "delete"
        extra_vars1 = {
            "p_source_cluster": source_cluster,
            "p_source_vserver": source_svm,
            "p_volume": source_volume,
            "p_destination_cluster": destination_cluster,
            "p_destination_vserver" : destination_svm,
            "p_destination_volume": destination_volume,
            "p_operation": operation1,
            "p_iscompliance": "false",
        }

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        awx_playbook2 = "volume.yaml"
        operation2 = "rename"
        extra_vars2 = {
            "p_cluster": destination_cluster,
            "p_vserver": destination_svm,
            "p_volume": destination_volume,
            "p_operation": operation2,
            "p_newvolume": remote_name,
            "p_encrypt": encrypted,
        }
        # TODO rivedere extra vars quando ci sono diversi step
        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation1,awx_playbook1, extra_vars1]
            },
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation2,awx_playbook2, extra_vars2]
            },
            {
                "step": OntapNetappVolume.task_base_path + "check_update_info_against_remote_volume",
                "args": [self.oid]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("replica_unlink", steps=steps,log="making volume independent",
                             awx_params=awx_params, sync=True,
                             execute_in_single_transaction=execute_in_single_transaction)
        return res

    def _replica_update(
        self,
        source_cluster: str, source_svm: str, source_volume: str,
        destination_cluster: str, destination_svm: str, destination_volume: str,
        destination_rpo: str , execute_in_single_transaction = False,
        awx_params: Dict = None
    ):
        self.check_active()

        awx_playbook = "snapmirror.yaml"
        operation = "policy"
        extra_vars = {
            "p_source_cluster": source_cluster,
            "p_source_vserver": source_svm,
            "p_volume": source_volume,
            "p_destination_cluster": destination_cluster,
            "p_destination_vserver" : destination_svm,
            "p_destination_volume": destination_volume,
            "p_operation": operation,
        }
        if destination_rpo:
            extra_vars.update({"p_rpo": destination_rpo})

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            }
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("replica_resume", steps=steps,log="Resume replica relationship",
                             awx_params=awx_params, sync=True)
        return res


    def _mount(
        self, awx_params: Dict = None
    ):
        self.check_active()
        #if self.get_role()!= OntapNetappVolume.Role.DR.value:
        #    raise Exception("Invalid volume role %s for action replica_mount", self.get_role())

        awx_playbook = "volume.yaml"
        operation = "mount"
        extra_vars = {
            "p_cluster": self.get_attribs("cluster"),
            "p_vserver" : self.get_attribs("svm"),
            "p_volume": self.get_attribs("remote_name"),
            "p_client": [],
            "p_operation": operation,
            "p_iscompliance": "false",
        }

        if not awx_params:
            awx_params = self.get_attribs("awx_params")

        steps = [
            {
                "step": OntapNetappVolume.action_task_base_path + "volume_action_physical_step",
                "args": [operation, awx_playbook, extra_vars]
            },
        ]

        # params passed as "kwargs" by passing key=value
        res = super().action("mount", steps=steps,log="making volume mountable",
                             awx_params=awx_params, sync=True)
        return res
