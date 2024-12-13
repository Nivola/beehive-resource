# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

"""
To enable module:

open the resource schema:

add in container_type table
    NULL, 'orchestrator', 'Dns', 'beehive_resource.plugins.dns.controller.DnsContainer'
add in resource_type table
    '73', 'Dns.DnsZone', 'beehive_resource.plugins.dns.controller.DnsZone'
    '74', 'Dns.DnsZone.DnsRecordA', 'beehive_resource.plugins.dns.controller.DnsRecordA'
    '75', 'Dns.DnsZone.DnsRecordCname', 'beehive_resource.plugins.dns.controller.DnsRecordCname'


beehive auth objects add-type container Dns
beehive auth objects add-type resource Dns
beehive auth objects add-type resource Dns.DnsZone
beehive auth objects add-type resource Dns.DnsZone.DnsRecordA
beehive auth objects add-type resource Dns.DnsZone.DnsRecordCname
beehive auth objects add container Dns "*" "Dns"
beehive auth objects add resource Dns "*" "Dns"
beehive auth objects add resource Dns.DnsZone "*\/\/*" "Dns Zone"
beehive auth objects add resource Dns.DnsZone.DnsRecordA "*\/\/*\/\/*" "Dns Record A"
beehive auth objects add resource Dns.DnsZone.DnsRecordCname "*\/\/*\/\/*" "Dns Record Cname"
beehive auth objects perms subsystem=resource type=Dns*

For each permissions with action *:
beehive auth roles add-perm ApiSuperAdmin <perm_id>
"""
from beehive_resource.plugins.dns.controller import DnsContainer
from beehive_resource.plugins.dns.views.record_a import DnsRecordAAPI
from beehive_resource.plugins.dns.views.record_cname import DnsRecordCnameAPI
from beehive_resource.plugins.dns.views.zones import DnsZoneAPI


class DnsPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = DnsContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [DnsZoneAPI, DnsRecordAAPI, DnsRecordCnameAPI]
        self.module.set_apis(apis)

        self.module.add_container(DnsContainer.objdef, DnsContainer)
