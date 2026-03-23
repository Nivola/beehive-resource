#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import TypedDict, Optional, Protocol

class EntitiesCheckResult(TypedDict):
    check: bool
    msg: Optional[str]
