#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import TypedDict, Literal

class CreateShareParams(TypedDict):
    size: int
    share_proto: Literal['nfs', 'cifs']
    encrypted: bool
    snapshot_policy: str
