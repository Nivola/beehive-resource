# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2024 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte
from beehive_resource.container import Resource


class ComputeStackMariaDBAction(Resource):
    objdef = "Provider.ComputeZone.ComputeStackV2.ComputeStackMariaDBAction"
    objname = "mariadb action"
    objdesc = "Provider ComputeStack V2 MariaDB Action"

    task_path = "beehive_resource.plugins.provider.task_v2.stack_v2_mariadb.StackV2MariaDBTask."
    # from beehive_resource.plugins.provider.task_v2.stack_v2_mariadb import StackV2MariaDBTask
    # task_path = "%s.%s." % (StackV2MariaDBTask.__module__, StackV2MariaDBTask.__name__)
