# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from beehive_resource.plugins.zabbix.controller import ZabbixContainer
from beehive_resource.plugins.zabbix.views.zbx_host import ZabbixHostAPI
from beehive_resource.plugins.zabbix.views.zbx_hostgroup import ZabbixHostgroupAPI
from beehive_resource.plugins.zabbix.views.zbx_template import ZabbixTemplateAPI


class ZabbixPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = ZabbixContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            ZabbixHostAPI,
            ZabbixHostgroupAPI,
            ZabbixTemplateAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(ZabbixContainer.objdef, ZabbixContainer)
