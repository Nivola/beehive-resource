# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.elk.controller import ElkContainer
from beehive_resource.plugins.elk.views.elk_space import ElkSpaceAPI
from beehive_resource.plugins.elk.views.elk_role import ElkRoleAPI
from beehive_resource.plugins.elk.views.elk_role_mapping import ElkRoleMappingAPI


class ElkPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = ElkContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [ElkSpaceAPI, ElkRoleAPI, ElkRoleMappingAPI]
        self.module.set_apis(apis)

        self.module.add_container(ElkContainer.objdef, ElkContainer)
