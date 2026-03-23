#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import Dict, List, Optional, Tuple, Iterable, TYPE_CHECKING, Literal
from beehive_resource.plugins.provider.helper.share._base import StorageConfigParser, ComputeZoneStaasConfError
if TYPE_CHECKING:
    from beehive_resource.plugins.provider.entity.zone import ComputeZone
    from beehive_resource.typing_extras.share.helper import StaasRelationshipItem, StaasSiteSvmConfig, StaasConfig

class ComputeZoneOntapConfError(ComputeZoneStaasConfError):
    pass

class OntapStorageConfigParser(StorageConfigParser):

    @classmethod
    def check_storage_site_configuration(
        cls,
        compute_zone: 'ComputeZone',
        site_name: str,
        allow_missing_compliance_configuration: bool = False
    ) -> Tuple[str, List['StaasSiteSvmConfig'], Optional[str]]:
        """
        Validates the storage ontap configuration for a specific site.

        Returns a tuple with the following:
        - site_fas_cluster: name of the cluster associated to the specified site
        - site_svm_list: list of dicts representing SVMs, each with
            - name
            - ext_id
            - list of supported protocols (nfs, cifs)
        - site_compliance_site: name of compliance site of specified site, if any

        :param compute_zone: the compute zone we have to check the configuration of
        :type compute_zone: ComputeZone
        :param site_name: the site name e.g. SiteTorino01
        :type site_name: str
        :param allow_missing_compliance_configuration:
        if False, raise if compliance site configuration is missing.
        defaults to False
        :type allow_missing_compliance_configuration: bool, optional
        :return site_fas_cluster, site_svm_list, site_compliance_site: each svm in the list
        contains its name, its ext_id and the list of supported protocols [nfs,cifs]
        :rtype: Tuple[str,List[Dict], str]
        :raises: Exception if any check fails
        """
        # check compute zone is configured for new staas api and for target site
        site_staas_conf = compute_zone.staas_conf.get("sites",{}).get(site_name)
        if site_staas_conf is None:
            raise ComputeZoneOntapConfError(
                f"Compute zone {compute_zone.name} ({compute_zone.oid}) is "
                f"not configured to use new storage api for site {site_name}"
            )

        # for target site, get: cluster name, compliance site, and list of SVMs
        site_fas_cluster = site_staas_conf.get("cluster")
        site_compliance_site = site_staas_conf.get("compliance_site")
        site_svm_list = site_staas_conf.get("svm")

        if site_fas_cluster is None or not site_svm_list:
            # no fas cluster set, or no svms set
            raise ComputeZoneOntapConfError(
                f"Compute zone {compute_zone.name} ({compute_zone.oid}) "
                f"has incorrect staas configuration for site {site_name}: "
                f"- cluster: {site_fas_cluster}\n- svm list: {site_svm_list}"
            )

        # compliance site should be defined and mapped against main site
        if site_compliance_site is None and (not allow_missing_compliance_configuration):
            raise ComputeZoneOntapConfError(
                f"Compute zone {compute_zone.name} ({compute_zone.oid}) does not have"
                f"a configured compliance site for site {site_name}"
            )

        return site_fas_cluster, site_svm_list, site_compliance_site

    @classmethod
    def check_storage_configuration(
        cls, compute_zone: "ComputeZone", site_names: List[str]
    ) -> 'StaasConfig':
        """
        checks and returns compute zone storage configuration

        :returns: a dictionary containing the configuration
        :raises: Exception if any check fails
        """
        svm_site_names = compute_zone.staas_conf.get("sites").keys()
        if not (set(svm_site_names) <= set(site_names)):
            raise ComputeZoneOntapConfError(
                "Mismatch between compute zone usable sites {} and configured storage sites {}"
                .format(set(site_names), set(svm_site_names))
            )
        for site_name in svm_site_names:
            _, _, peer_site_name = cls.check_storage_site_configuration(
                compute_zone, site_name
            )
            cls.validate_compliance_mappings(site_name, peer_site_name)

        return compute_zone.staas_conf

    @classmethod
    def get_peer_svm(
        cls,
        relationships: List['StaasRelationshipItem'],
        from_site_name: str,
        to_site_name: str,
        from_svm_name: str,
        valid_svm_list: List['StaasSiteSvmConfig'] = None
    ):
        """get secondary svm associated to primary svm

        :param relationships: conf dictionary
        :type relationships: Dict
        :param from_site_name: main site name
        :type from_site_name: str
        :param to_site_name: secondary site name
        :type to_site_name: str
        :param from_svm_name: main svm name
        :type from_svm_name: str
        :param valid_svm_list: list of valid svms, defaults to None
        :type valid_svm_list: Iterable[Dict], optional
        :raises Exception: on invalid or None peer
        :return: _description_
        :rtype: _type_
        """
        # get expected "to" svm from "from" site configuration
        expected_peer_svm = None
        for rel in relationships:
            source_site = rel.get("source_site")
            source_svm = rel.get("source_svm")
            if source_site == from_site_name and source_svm == from_svm_name:
                peers = rel.get("peers")
                expected_peer_svm = peers.get(to_site_name)

        if not expected_peer_svm:
            raise ComputeZoneOntapConfError(
                f"no peer svm in {to_site_name} (in site {to_site_name}) "
                f"is set for svm {from_svm_name} (in site {from_site_name})"
            )

        # in case a list of valid svms is given, check validity
        if valid_svm_list:
            if not any(svm.get("name") == expected_peer_svm for svm in valid_svm_list):
                raise ComputeZoneOntapConfError(
                    f"invalid peer svm {expected_peer_svm} (in site {to_site_name}) "
                    f"for svm {from_svm_name} (in site {from_site_name})"
                )
        return expected_peer_svm

    @classmethod
    def find_first_matching_svm(
        cls,
        svm_list: List['StaasSiteSvmConfig'],
        wanted_protocol: Optional[Literal['nfs', 'cifs']] = None,
        wanted_svm_name: Optional[str] = None
    ) -> str:
        # get first svm that supports the wanted protocol, from the list
        if wanted_protocol is None and wanted_svm_name is None:
            found_svm = next(svm_list, None)
        else:
            found_svm = None
            for svm in svm_list:
                # if svm name specified, skip all non-matching ones
                if wanted_svm_name is not None and svm.get("name")!=wanted_svm_name:
                    continue
                if wanted_protocol is None:
                    found_svm = svm
                    break
                if wanted_protocol in svm.get("protocol"):
                    found_svm = svm
                    break
        if not found_svm:
            raise Exception("no valid svm found")
        found_svm_name = found_svm.get("name")
        if not found_svm_name:
            raise Exception(f"svm name empty: {found_svm_name}")
        return found_svm_name
