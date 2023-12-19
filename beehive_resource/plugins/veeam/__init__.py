# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.veeam.controller import VeeamContainer
from beehive_resource.plugins.veeam.views.veeam_job import VeeamJobAPI


class VeeamPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = VeeamContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [VeeamJobAPI]
        self.module.set_apis(apis)

        self.module.add_container(VeeamContainer.objdef, VeeamContainer)
