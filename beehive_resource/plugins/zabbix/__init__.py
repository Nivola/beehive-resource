# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.zabbix.controller import ZabbixContainer
from beehive_resource.plugins.zabbix.views.zbx_host import ZabbixHostAPI
from beehive_resource.plugins.zabbix.views.zbx_hostgroup import ZabbixHostgroupAPI
from beehive_resource.plugins.zabbix.views.zbx_template import ZabbixTemplateAPI
from beehive_resource.plugins.zabbix.views.zbx_usergroup import ZabbixUsergroupAPI
from beehive_resource.plugins.zabbix.views.zbx_action import ZabbixActionAPI


class ZabbixPlugin(object):
    SEVERITY_DESC_INFORMATION: str = "Information"
    SEVERITY_DESC_WARNING: str = "Warning"
    SEVERITY_DESC_AVERAGE: str = "Average"
    SEVERITY_DESC_HIGH: str = "High"
    SEVERITY_DESC_DISASTER: str = "Disaster"

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
            ZabbixUsergroupAPI,
            ZabbixActionAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(ZabbixContainer.objdef, ZabbixContainer)
