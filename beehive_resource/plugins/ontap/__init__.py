# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.ontap.controller import OntapNetappContainer
from beehive_resource.plugins.ontap.views.volume import OntapNetappVolumeAPI


class OntapNetappPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = OntapNetappContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            OntapNetappVolumeAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(OntapNetappContainer.objdef, OntapNetappContainer)
