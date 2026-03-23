# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, TYPE_CHECKING, Tuple, Type
from beecell.simple import import_class
from beedrones.ontapp.client import OntapManager, OntapError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator, trace, QueryError
from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
if TYPE_CHECKING:
    from beehive_resource.model import Resource as ModelResource
    from beehive_resource.plugins.ontap.entity import OntapNetappResource

@dataclass
class VolumeSearchResult:
    cmp_name: str # cmp-adapted name for volume
    vol: Dict # ontap volume information as obtained from list api call
    svm: Dict # auxiliary information

def get_task(task_name):
    return "%s.task.%s" % (__name__, task_name)


class OntapNetappContainer(Orchestrator):
    """Ontap Netapp orchestrator

    **connection syntax**:

        {
            "host": ..,
            "port": ..,
            "proto": ..,
            "user": ..,
            "pwd": ..,
            "timeout": 5.0,
        }
    """

    objdef = "OntapNetapp"
    objdesc = "OntapNetapp container"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [OntapNetappSvm, OntapNetappVolume]

        self.conn: Optional['OntapManager'] = None
        self.token = None

    def ping(self):
        """Ping orchestrator.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.conn2.ping()
        except (ApiManagerError, Exception) as ex:
            self.logger.warning("ping ko", exc_info=True)
            res = False
        self.container_ping = res
        return res

    def info(self):
        """Get container info.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Orchestrator.info(self)
        return info

    def detail(self):
        """Get container detail.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Orchestrator.info(self)

        res = info
        res["details"] = {
            "cluster": self.get_cluster_info()
            # 'version': self.conn.version()
        }

        return res

    @property
    def conn2(self) -> OntapManager:
        """wrapper around conn, and get connection
        returns OntapManager
        """
        if self.conn is None or not self.conn.ping():
            self.__new_connection()
        return self.conn

    def __new_connection(self, timeout=30.0):
        """Get ontap connection with new token"""
        try:
            host = self.conn_params.get("host")
            port = self.conn_params.get("port", 80)
            proto = self.conn_params.get("proto", "http")
            user = self.conn_params.get("user")
            pwd = self.conn_params.get("pwd")

            # decrypt password
            pwd = self.decrypt_data(pwd)
            self.conn = OntapManager(host, user, pwd, port=port, proto=proto, timeout=timeout)
            self.conn.authorize()
        except OntapError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400) from ex

    def get_connection(self):
        """Get ontap netapp connection"""
        self.conn2
        Orchestrator.get_connection(self)

    def close_connection(self):
        """close global connection...
        try to avoid using this function.
        """
        # NB: do not use self.conn2 because the property
        # would create a session if one doesn't exist
        if self.conn and self.conn.client:
            self.conn.client.session.close()

    def find_volume(self, volume_name: str, svm_list: List[Dict]) -> VolumeSearchResult:
        """search volume among all valid svms

        :param volume_name: volume name to search for
        :type volume_name: str
        :param svm_list: list of parent svms to consider
        :type svm_list: List[Dict]
        :raises Exception: if not found or more than one found
        :return: found info (svm name, remote volume name, cmp volume name), found volume
        :rtype: Tuple[Dict[str,str],Dict]
        """
        remote_name = OntapNetappVolume.format_name_for_remote(volume_name)
        cmp_name = OntapNetappVolume.format_name_for_cmp(remote_name)

        found_vol = []
        found_svm = None
        for svm in svm_list:
            res: List[Dict] = self.conn2.volume.list(name=remote_name,svm=svm.get("name"))
            if not res:
                continue
            found_svm = svm
            found_vol.extend(res)
        if not found_vol:
            raise Exception("no remote volume found with name %s among svms %s" % (remote_name,svm_list))
        if len(found_vol)>1:
            raise Exception(
                "expected 1 but found %s remote volumes with name %s" % (len(found_vol), remote_name)
            )

        return VolumeSearchResult(
            cmp_name=cmp_name,
            vol=found_vol[0],
            svm=found_svm
        )

    def get_volume_snaplock_relationship(
        self,
        volume: Dict,
        compliance_container: Optional['OntapNetappContainer']=None,
        strict=True
    ):
        """try to find a snapmirror relationship from the specified volume
        to some possible snaplock volume.

        :param volume: dictionary with source volume platform information
        :type volume: Dict
        :param strict: whether to propagate or suppress Exception,
        defaults to True
        :type strict: bool, optional
        :param compliance_container: compliance site ontap container, defaults to None
        if not given, some checks can't be done.
        :type compliance_container: Optional[OntapNetappContainer], optional
        :raises Exception: if any check fails and strict=True, or if critical checks fail
        :return: None or found valid snapmirror relationship to snaplock volume
        :rtype: _type_
        """
        expected_snaplock = volume.get("snapmirror",{}).get("is_protected", False)
        svm_name = volume.get("svm",{}).get("name")
        volume_name = volume.get("name")
        if not svm_name:
            raise Exception("svm name missing")
        if not volume_name:
            raise Exception("volume name missing")

        source_path = f'{svm_name}:{volume_name}'
        rels = self.get_volume_snapmirror_relationships(source_path=source_path, search_remote=True)
        if len(rels)>=1:
            # these include snaplock and regular dr (replica) relationships
            # try and disambiguate by using compliance container
            filtered = []

            # without compliance container we can't check remote metadata
            if not compliance_container:
                self.logger.warning("no compliance container given: unable to do strict check")
                if len(rels)==1 and not strict:
                    # if not strict mode and only one rel, assume it's that one
                    return rels[0]
                raise Exception(
                    "no compliance container given and/or too many snaplocks detected "
                    "(strict=%s - #rels=%s): %s" % (strict,len(rels),rels)
                )
            for rel in rels:
                # try to find and to query destination volume for snaplock.type
                svm_name_x, vol_name_x = rel.get("destination").get("path").split(":")
                filters = {
                    "name": vol_name_x,
                    "svm.name": svm_name_x,
                    "filter_snaplock": True
                }
                v_list = compliance_container.conn2.volume.list(**filters)
                if not v_list:
                    continue
                elif len(v_list)>1:
                    # although should be impossible
                    # to have volumes with same name in same svm
                    raise Exception(
                        f"too many volumes ({len(v_list)}) found with target name "
                        f"({vol_name_x}). Unable to disambiguate"
                    )
                detail_x = v_list[0]
                if detail_x.get("snaplock",{}).get("type")=="compliance":
                    filtered.append(rel)
            if not filtered:
                # they were all dr relationships
                return None
            if len(filtered)>1:
                raise Exception("too many snaplocks detected (%s): %s" % (len(filtered),filtered))
            if not expected_snaplock and strict:
                raise Exception("snaplock should not be present, but found")
            return filtered[0]
        else:
            if expected_snaplock and strict:
                raise Exception("snaplock is present, but cmp is unable to find snaplock")
        return None

    def get_volume_snapmirror_relationships(
        self,
        source_path: str=None, destination_path: str=None,
        search_local=False, search_remote=True
    ):
        if not source_path and not destination_path:
            self.logger.error(
                "Invalid couplet svm_name:volume_name. Can't get snapmirror list."
                "Source path: %s - Destination path: %s." % (source_path,destination_path)
            )
            raise Exception("source_path and destination_path parameters missing")
        try:
            params = {}
            if source_path:
                params["source.path"] = source_path
            if destination_path:
                params["destination.path"] = destination_path
            snapmirror_relationships = self.conn2.snapmirror.list(search_local=search_local,search_remote=search_remote,**params)
            return snapmirror_relationships
        except Exception as ex:
            self.logger.error("Error while retrieving volume snapmirror relationships: %s" % ex)
            raise Exception("Error while retrieving volume snapmirror relationships") from ex

    def check_volume_is_replica(
        self,
        volume: Dict,
    ):
        svm_name = volume.get("svm",{}).get("name")
        volume_name = volume.get("name")
        if not svm_name:
            raise Exception("svm name missing")
        if not volume_name:
            raise Exception("volume name missing")
        destination_path = f'{svm_name}:{volume_name}'
        # we consider a volume a replica if it's the destination of a snapmirror relationship
        rels = self.get_volume_snapmirror_relationships(destination_path=destination_path, search_local=True, search_remote=False)
        # TODO in theory it should only have one relationship of this kind
        is_replica = True if rels and len(rels)>0 else False
        return is_replica, rels

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

        :param controller: (:py:class:`ResourceController`): resource controller instance
        :param type: (:py:class:`str`): container type
        :param name: (:py:class:`str`): container name
        :param desc: (:py:class:`str`): container desc
        :param active: (:py:class:`str`): container active
        :param conn: (:py:class:`dict`): container connection
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # encrypt password
        conn["pwd"] = controller.encrypt_data(conn["pwd"])

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

    def get_cluster_info(self):
        """Get ontap netapp cluster info"""
        res = self.conn.cluster.get()
        return res

    def _discover_restype_cmp(
        self, restype
    ) -> Tuple[Dict[str, List['ModelResource']], List['ModelResource']]:
        """
        Returns resources of the specified type
        already present in cmp.

        :param restype: resource type e.g. OntappNetapp.Volume

        :rtype: Tuple[Dict,List]
        :return: tuple containing resource map and list of resources
        with ext_id not set.
        :raises ApiManagerError:
        """
        # 2 get resources of that type already present in cmp
        try:
            cmp_resources = self.manager.get_resources_by_type(type=restype, container=self.oid)
        except QueryError as ex:
            raise ApiManagerError(f"Query error during restype {restype} discover: {ex}")
        # 3 create cmp resources ext_id map
        res_map: Dict[str, List['ModelResource']] = {}
        problem_list: List['ModelResource'] = []
        for r in cmp_resources:
            if r.ext_id is not None:
                res_map.setdefault(r.ext_id, []).append(r)
            else:
                problem_list.append(r)

        if len(problem_list)>0:
            self.logger.warning(f"Found {len(problem_list)} resources of type {restype} without an ext_id")
            problem_id_list = [r.id for r in problem_list] #TODO CHECK
            self.logger.debug("List ids of such resources: %s",problem_id_list)
        return res_map,problem_list

    @trace(op="use")
    def discover(self, restypes: List, ext_id: Optional[str]=None):
        """Discover remote platform entities

        :param restype: container resource objdef
        :param ext_id: remote entity id [optional]
        :return:

            {
                'new':[
                    'resclass':..,
                    'id':..,
                    'parent':..,
                    'type':..,
                    'name':..
                ],
                'died':[],
                'changed':[]
            }

        :raise ApiManagerError:
        """
        self.verify_permisssions("use")

        def default_remote_resource_differs(
            existing_item: 'OntapNetappResource',
            remote_name: str,
            remote_dict: Dict
        ):
            return existing_item.name!=remote_name

        remote_resources = []
        res = {"new": [], "died": [], "changed": []}

        if restypes is None or len(restypes) == 0:
            raise ApiManagerError(
                f"Invalid restypes {restypes} for ontap container {self.oid}"
            )

        for restype in restypes:
            # 1 import the corresponding class (e.g. OntapNetappSvm, OntapNetappVolume)
            restype_class = self.manager.get_resource_types(value=restype)[0]
            resclass: Type[OntapNetappResource] = import_class(restype_class.objclass)
            # 2,3 discover cmp resources
            cmp_res_map,_ = self._discover_restype_cmp(restype)
            # 4 discover remote resources
            remote_resources: List[Dict] = resclass.discover_remote(container=self, ext_id=ext_id)
            for item in remote_resources:
                # 5 for each remote resource get cmp corresponding resource if present
                item_ext_id = item.get("uuid")
                item_name = item.get("name")
                cmp_res = cmp_res_map.get(item_ext_id)
                if cmp_res is None:
                    self.logger.debug("new resource found: %s", item_name)
                    # 6a add to "new" if not present
                    res["new"].append(resclass.format_for_discover(item_name, item_ext_id))
                else:
                    remote_name = item_name
                    if hasattr(resclass, "format_name_for_cmp"):
                        item["name"] = resclass.format_name_for_cmp(item_name)

                    remote_resource_differs = getattr(resclass,"remote_resource_differs", default_remote_resource_differs)
                    # 6b for each matched element check if changed
                    for matched_element in cmp_res:
                        if remote_resource_differs(matched_element, remote_name, item):
                            # 6b.2 add to "changed" if changed
                            self.logger.debug("resource %s has changed", matched_element.name)
                            cast_inst = self.cast_to_resclass(matched_element, resclass)
                            res["changed"].append(cast_inst.format_for_discover_self())
                    # 6c remove from map
                    cmp_res_map.pop(item_ext_id)

            # 7 the remaining objects in cmp_res_map, are "died", if any
            for ext_id,r_list in cmp_res_map.items():
                for r in r_list:
                    self.logger.debug("resource %s does not exist anymore. It can be deleted", r.name)
                    cast_inst = self.cast_to_resclass(r, resclass)
                    res["died"].append(cast_inst.format_for_discover_self())
        return res

    def cast_to_resclass(self, instance: 'ModelResource', to_resclass: Type['OntapNetappResource']) -> 'OntapNetappResource':
        obj = to_resclass(
            self.controller,
            oid = instance.id,
            objid = instance.objid,
            name = instance.name,
            desc = instance.desc,
            active = instance.active,
            model= instance,
        )
        obj.container = self
        obj.ext_id = instance.ext_id
        return obj
