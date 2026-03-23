#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import TypedDict, Dict, Optional

class ResourceTaskBaseParams(TypedDict):
    alias: str # e.g. "%s.import" % resource_class.__name__,
    cid: int
    name: str
    desc: str
    ext_id: Optional[str]
    active: bool
    attribute: Dict
    tags: Optional[str] # can't actually be None. is forced to be "" in that case.

    objid: str
    parent: int

    # added by resource factory, if create task
    id: int
    uuid: str

    sync: bool
