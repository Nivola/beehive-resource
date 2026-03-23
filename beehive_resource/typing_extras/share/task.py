#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import TypedDict, List, Literal, Dict, Optional
from beehive_resource.typing_extras.common.task import ResourceTaskBaseParams


# to move elsewhere
class OrchestratorInfo(TypedDict):
    type: str
    id: str
    tag: str
    config: Dict
#

class FileShareV2Attribute(TypedDict):
    main: bool
    type: str
    tag: str
    has_quotas: bool

class FileShareV2_ImportPhysicalShareStepParams_ShareParams(TypedDict):
    cluster: str
    svm: str
    vol_name: str
    vol_ext_id: Optional[str]
    share_role: Literal["main","dr"] # role of the provider share
    # if importing snaplock volume
    compliance_vol_ext_id: Optional[str]
    compliance_vol_name: Optional[str]

class FileShareV2_ImportPhysicalShareStepParams(ResourceTaskBaseParams):
    attribute: FileShareV2Attribute # forcing more specific type than base class

    compliance: bool
    orchestrator_type: str
    orchestrator_tag: str
    orchestrator: OrchestratorInfo
    share_params: FileShareV2_ImportPhysicalShareStepParams_ShareParams
