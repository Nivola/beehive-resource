#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from datetime import datetime
import os
from typing import Protocol #, runtime_checkable

# NB: if using runtime_checkable to check methods/functions,
# be careful since signatures are NOT checked.
# Only their names are checked.

# optionally make it a no-op if it affects performance too much
# (but won't be able to do runtime checks anymore)
DISABLE_RUNTIME_CHECKABLE = os.getenv("DISABLE_RUNTIME_CHECKABLE", "0") == "1"
if DISABLE_RUNTIME_CHECKABLE:
    def runtime_checkable(cls):
        # No-op decorator disables runtime isinstance checks
        return cls
else:
    from typing import runtime_checkable

@runtime_checkable # to validate structural typing with isinstance
class ResourceDbManager_DirectedLinkedResourcesInternal_Return(Protocol):
    # dot notation because this models a sqlalchemy RowProxy
    resource: int # link start resource id, usually provider level resource
    id: int # t1.id = link end resource id
    uuid: str
    objid: str
    name: str
    ext_id: str
    desc: str
    active: bool
    parent_id: int
    container_id: int
    attribute: str
    state: int
    objclass: str # end resource type objclass
    objdef: str # end resource type objdef
    creation_date: datetime
    modification_date: datetime
    expiry_date: datetime
    link_attr: str
    link_type: str
    link_creation: datetime

@runtime_checkable # to validate structural typing with isinstance
class ResourceDbManager_LinkedResourcesInternal_Return(Protocol):
    # dot notation because this models a sqlalchemy RowProxy
    id: int # t1.id = link end resource id
    uuid: str
    objid: str
    name: str
    ext_id: str
    desc: str
    active: bool
    parent_id: int
    container_id: int
    attribute: str
    state: int
    objclass: str # end resource type objclass
    objdef: str # end resource type objdef
    creation_date: datetime
    modification_date: datetime
    expiry_date: datetime
    link_attr: str
