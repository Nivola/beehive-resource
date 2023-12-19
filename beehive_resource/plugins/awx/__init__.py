# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.awx.controller import AwxContainer
from beehive_resource.plugins.awx.views.awx_project import AwxProjectAPI
from beehive_resource.plugins.awx.views.awx_job_template import AwxJobTemplateAPI


class AwxPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = AwxContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            AwxProjectAPI,
            AwxJobTemplateAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(AwxContainer.objdef, AwxContainer)
