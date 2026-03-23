# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations

from beecell.simple import random_password, dict_get
from beehive.common.apimanager import ApiManagerError

from .helper import (
    DbaasBase,
    SqlActionHelper,
    SqlDeleteHelper,
    SqlImportHelper,
    SqlCreateHelper,
    SqlUpdateHelper,
    EngineParams
)

class SqlserverBase(DbaasBase):
    engine_params: EngineParams = {
        "hypervisor": "vsphere",
        "image": "mssql2019",
        "volume_flavor": "vol.default",
        "host_group": "default",
        "engine": {
            "port": 1433,
            "customization": "sqlserver",
            "license": "license-included",
            "service_users": {},
            "steps_order": {
                "create": [
                    "create_server",
                ],
                "delete": []
            }
        },
    }


class SqlserverDeleteHelper(SqlDeleteHelper):
    """
    Delete.
    """
    default_engine = SqlserverBase

    def internal_run(self):
        pass


class SqlserverCreateHelper(SqlCreateHelper):
    """
    Create.
    """
    default_engine = SqlserverBase

    def internal_run(self):
        self.license = dict_get(self.final_params, "engine.license")
        self.admin_user = self.kvargs.pop("db_root_name", "admin")
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=False)

        self.image = self.get_image()  # Correctly reads from final_params
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        self.outputs.append(self.set_output())

        engine = self.final_params.get("engine", {})
        steps_order = engine.get("steps_order")
        if not steps_order:
            raise Exception(
                "Workflow steps ('engine.steps_order') not found in final_params."
            )

        create_steps = steps_order.get("create", [])
        if not create_steps:
            raise Exception(
                "Workflow steps ('engine.steps_order.create') not found."
            )

        # Loop executes steps exactly as listed in final_params
        for step_name in create_steps:
            action_method = getattr(self, f"action_{step_name}", None)

            if action_method and callable(action_method):
                self.logger.debug("Appending action: %s", step_name)
                self.actions.append(action_method())
            # Handle missing or non-callable actions
            elif action_method is None:
                self.logger.warning(
                    "Action method action_%s not found.", step_name
                )
            elif not callable(action_method):
                self.logger.warning(
                    "Attribute action_%s found but is not callable.", step_name
                )


#
# Import
#
class SqlserverImportHelper(SqlImportHelper):
    default_engine = SqlserverBase

    def internal_run(self):
        self.license = dict_get(self.final_params, "engine.license")
        self.admin_user = self.kvargs.pop("db_root_name", "admin")

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_import_server())


class SqlserverUpdateHelper(SqlUpdateHelper):
    """
    Update.
    """
    default_engine = SqlserverBase

    def internal_run(self):
        pass


class SqlserverActionHelper(SqlActionHelper):
    """
    Actions.
    """
    default_engine = SqlserverBase

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)


DbaasBase.register_child("sqlserver", SqlserverBase)
SqlDeleteHelper.register_child("sqlserver", SqlserverDeleteHelper)
SqlCreateHelper.register_child("sqlserver", SqlserverCreateHelper)
SqlImportHelper.register_child("sqlserver", SqlserverImportHelper)
SqlUpdateHelper.register_child("sqlserver", SqlserverUpdateHelper)
SqlActionHelper.register_child("sqlserver", SqlserverActionHelper)
