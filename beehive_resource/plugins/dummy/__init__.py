# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from .view import DummyAPI
from .controller import DummyContainer


class DummyPlugin(object):
    def __init__(self, module):
        self.module = module
    
    def init(self):
        service = DummyContainer(self.module.get_controller())
        service.init_object()
    
    def register(self):
        apis = [DummyAPI]
        self.module.set_apis(apis)
        
        self.module.add_container(DummyContainer.objdef, DummyContainer)
