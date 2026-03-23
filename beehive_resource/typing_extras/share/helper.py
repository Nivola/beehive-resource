#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import TypedDict, List, Literal, Dict, Optional

SITE_NAMES = Literal['SiteTorino01', 'SiteTorino02', 'SiteVercelli01', 'SiteTorino05', 'SiteGenova06']

class StaasSiteSvmConfig(TypedDict):
    name: str
    protocol: List[Literal['nfs', 'cifs']]
    ext_id: str

class StaasSiteConfig(TypedDict):
    """staas configuration for specific site
    cluster: name of cluster associated to site
    svm: list of svms in that site that can be used
    compliance_site: which site is the one used for compliance
    """
    cluster: str
    svm: List[StaasSiteSvmConfig]
    compliance_site: str

class StaasRelationshipItem(TypedDict):
    source_site: SITE_NAMES
    source_svm: str
    peers: Dict[SITE_NAMES, str]

class StaasConfig(TypedDict):
    """normalized staas configuration for compute zone
    sites: cluster and svms associated to site
    relationships: (source_site,source_svm) -> peer_svm
    """
    sites: Dict[SITE_NAMES, StaasSiteConfig]
    relationships: List[StaasRelationshipItem]

# example config
# {
#   'sites': {
#       'SiteTorino01': {
#           'compliance_site': 'SiteVercelli01',
#           'cluster': 'faspod1',
#           'svm': [
#               {
#                   'name': 'svmp1-sample-name',
#                   'protocol': ['nfs', 'cifs'],
#                   'ext_id': '<uuid>'
#               }
#               ...
#           ]
#       },
#       'SiteTorino02': {
#           'compliance_site': 'SiteVercelli01',
#           'cluster': 'faspod2',
#           'svm': [
#               {
#                   'name': 'svmp2-sample-name',
#                   'protocol': ['nfs', 'cifs'],
#                   'ext_id': '<uuid>'
#               }
#               ...
#           ]
#       },
#       'SiteVercelli01': {
#           'compliance_site': 'SiteTorino01',
#           'cluster': 'faspodge3',
#           'svm': [
#               {
#                   'name': 'svmge3-sample-name',
#                   'protocol': ['nfs', 'cifs'],
#                   'ext_id': '<uuid>'
#               }
#               ...
#           ]
#       }
#   },
#   'relationships': [
#       {
#           'source_site': 'SiteTorino01',
#           'source_svm': 'svmp1-sample-name',
#           'peers': {
#               'SiteTorino02': 'svmp2-sample-name'
#               'SiteVercelli01': 'svmge3-sample-name'
#           }
#       }
#       ...
#   ]
# }

class ShareRequestParams(TypedDict):
    # for main and replica
    size: int
    share_proto: Literal['nfs', 'cifs']
    # for replica only
    rpo: Optional[str]
    from_id: Optional[int]
