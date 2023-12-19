# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from .view import DummyAPIV2
from .controller import DummyContainerV2


class DummyPluginV2(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = DummyContainerV2(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [DummyAPIV2]
        self.module.set_apis(apis)

        self.module.add_container(DummyContainerV2.objdef, DummyContainerV2)
