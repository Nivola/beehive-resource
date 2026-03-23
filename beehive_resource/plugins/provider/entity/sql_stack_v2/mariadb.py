# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte
# Meta programming staff in order to manage MAriadb dbaas on VM

import copy
from typing import Any, Dict, List

from beecell.simple import random_password, dict_get
from beehive.common.apimanager import ApiManagerError

from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackAction, ComputeStackV2
from beehive_resource.plugins.provider.entity.stack_v2_mariadb import ComputeStackMariaDBAction

from .helper import (
    DbaasBase,
    SqlHelper,
    SqlActionHelper,
    SqlDeleteHelper,
    SqlImportHelper,
    SqlCreateHelper,
    SqlUpdateHelper,
    EngineParams
)
from .mysql import MysqlImportHelper, MysqlUpdateHelper


class MariaDBBase(DbaasBase):
    engine_params: EngineParams = {
        "hypervisor": "vsphere",
        "image": "MariaDB-11.4",
        "volume_flavor": "vol.gold",
        "host_group": "default",
        "lvm": {
            "volume_group": {"data": "vg_data", "backup": "vg_backup"},
            "logical_volume": {"data": "lv_fsdata", "backup": "lv_fsbackup"},
        },
        "mount_point": {"data": "/data"},
        "engine": {
            "port": 3306,
            "customization": "mariadb-v2",
            "license": "general-public-license",
            "charset": "latin1",
            "service_users": {
                "zabbix": [{"name": "rou", "pwd": "Rou!142018", "host": "%", "privs": "*.*:SELECT"}],
                "trilio": [
                    {
                        "name": "trilio",
                        "pwd": "Oliri10!",
                        "host": "localhost",
                        "privs": "*.*:SELECT,PROCESS,RELOAD",
                    }
                ],
                "backup": [
                    {
                        "name": "mybck",
                        "pwd": "y!7t0oNv",
                        "host": "%",
                        "privs": "*.*:SELECT,PROCESS,EXECUTE,SHOW VIEW,EVENT",
                    }
                ],
            },
            "steps_order": {
                "create": [
                    "create_server",
                    "wait_ssh_is_up",
                    "set_etc_hosts",
                    "set_yum_proxy",
                    "set_dnf_proxy",
                    "setup_volume",
                    "setup_nfsbcklogici_add",
                    "install_mariadb",
                    "enable_login_shell",
                    "setup_mailx",
                    "add_users",
                    "install_extensions",
                    "enable_monitoring"
                ],
                "delete": [
                    "setup_nfsbcklogici_delete"
                ]
            }
        },
        "customizations": {
            "wait_ssh_is_up": {
                "playbook": "wait_ssh_is_up.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "set_etc_hosts": {
                "playbook": "set_etc_hosts.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "set_yum_proxy": {
                "playbook": "set_yum_proxy.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "set_dnf_proxy": {
                "playbook": "set_dnf_proxy.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "setup_volume": {
                "playbook": "setup_volume.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "setup_nfsbcklogici_add": {
                "playbook": "pre_dbaas_install.yml",
                "orchestrator_tag": "02",
                "customization": "pre_dbaas_install"
            },
            "setup_mailx": {
                "playbook": "setup_mailx.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "enable_monitoring": {
                "playbook": "install.yml",
                "orchestrator_tag": "default",
                "customization": "zabbix-agent"
            },
            "install_mariadb": {
                "playbook": "installMariaDB.yml",
                "orchestrator_tag": "02",
                "customization": "mariadb-v2"
            },
            "enable_login_shell": {
                "playbook": "enable_login_shell.yml",
                "orchestrator_tag": "default",
                "customization": "os-utility"
            },
            "add_users": {
                "playbook": "UserMgmtMariaDB.yml",
                "orchestrator_tag": "02",
                "customization": "mariadb-v2"
            },
            "install_extensions": {
                "playbook": "extensionMgmtMariaDB.yml",
                "orchestrator_tag": "02",
                "customization": "mariadb-v2"
            },
            "config_replica": {
                 "playbook": "configMysqlReplica.yml",
                 "orchestrator_tag": "default",
                 "customization": "mariadb-v2"
             },
            "setup_nfsbcklogici_delete": {
                "playbook": "pre_dbaas_uninstall.yml",
                "orchestrator_tag": "02",
                "customization": "pre_dbaas_uninstall"
            },
        }
    }

class MariaDBCreateHelper(SqlCreateHelper):
    default_engine = MariaDBBase

    def internal_run(self):
        self.license = dict_get(self.final_params, "engine.license")
        self.admin_user = self.kvargs.pop("db_root_name", "root")
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=True)
        self.engine_major_version = SqlHelper.get_engine_major_version(self.version, 2)
        self.image = self.get_image() # Already reads fallback from final_params
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        # Get service users for later use
        service_users: Dict[str, Any] = dict_get(self.final_params, "engine.service_users")
        self.monit_user = self.get_db_monit_user(service_users)
        # Note: Adding 'root'@'%' user logic moved to action_add_users
        # Note: Determining 'extensions' logic moved to action_install_extensions

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

        for step_name in create_steps:
            # Standard dynamic action call
            action_method = getattr(self, f"action_{step_name}", None)

            if action_method and callable(action_method):
                self.logger.debug("Appending action: %s", step_name)
                self.actions.append(action_method())

            # Handle missing standard actions
            elif action_method is None:
                self.logger.warning("Action method action_%s not found.", step_name)
            # Handle non-callable attributes
            elif not callable(action_method):
                self.logger.warning("Attribute action_%s found but is not callable.", step_name)

    def set_additional_steps(self) -> List[dict]:
        steps = []
        if self.replica:
            steps.append(
                {
                    "step": ComputeStackV2.task_path + "add_stack_links_step",
                    "args": [self.replica_master],
                }
            )
        return steps

    def action_install_mariadb(self):
        action_name = "install_mariadb"

        # Read customization details from final_params
        customization = self.get_customization(action_name)
        if not customization:
            raise ApiManagerError(
                f"Customization '{action_name}' not found in final_params"
            )

        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        res = {
            "name": action_name,
            "desc": "install mariadb",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent, # Use value read from customization
                "orchestrator_tag": orchestrator_tag, # Use value read from customization
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "playbook": playbook, # Use value read from customization
                "extra_vars": {
                    # These read correctly from instance variables set in internal_run
                    "p_mariadb_repo_version": self.engine_major_version,
                    "p_proxy_server": self.proxy,
                    "p_ip_repository": self.ip_repository,
                    "p_url_repository": self.url_repository,
                    "p_mariadb_root_username": self.admin_user,
                    "p_mariadb_root_password": self.admin_pwd,
                    "p_mariadb_server_ram":  self.server_ram_mb/1024,
                },
            },
        }
        # Replica args logic remains unchanged
        ComputeStackV2.set_replica_args(
            res,
            self.name,
            self.replica,
            self.replica_arch_type,
            self.replica_role,
            self.replica_sync_type,
            self.replica_ip_master,
            self.replica_user,
            self.replica_pwd,
            self.remove_replica,
        )
        return res

    def action_enable_login_shell(self) -> dict: # Removed default args
        action_name = "enable_login_shell"

        # Read customization details from final_params
        customization = self.get_customization(action_name)
        if not customization:
            raise ApiManagerError(
                f"Customization '{action_name}' not found in final_params"
            )

        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        # Keep original user/shell values hardcoded within the action
        user = "mysql"
        shell = "/bin/bash"

        res = {
            "name": action_name,
            "desc": "enable login shell for mariadb user",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent, # Use value read from customization
                "orchestrator_tag": orchestrator_tag, # Use value read from customization
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "playbook": playbook, # Use value read from customization
                "extra_vars": {"p_user": user, "p_shell": shell}, # Values defined above
            },
        }
        return res

    def action_add_users(self) -> dict: # Argument removed
        action_name = "add_users"

        # Read customization details from final_params
        customization = self.get_customization(action_name)
        if not customization:
            raise ApiManagerError(
                f"Customization '{action_name}' not found in final_params"
            )

        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        # Read engine details from final_params
        engine = self.final_params.get("engine", {})
        port = engine.get("port")
        # Use deepcopy to avoid modifying the original defaults
        service_users: Dict[str, Any] = copy.deepcopy(engine.get("service_users", {}))

        # Logic moved from internal_run: Add 'root'@'%' user
        service_users.update(
            {
                "admin": [
                    {
                        "name": "root", # Should match self.admin_user
                        "pwd": self.admin_pwd, # Use the generated admin password
                        "host": "%",
                        "privs": "*.*:ALL,GRANT",
                    }
                ]
            }
        )

        # Adapt users format (now uses service_users from final_params + admin)
        user_lst = []
        for v in service_users.values():
            user_lst.extend(v)

        res = {
            "name": action_name,
            "desc": "add service users and admin",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent,
                "orchestrator_tag": orchestrator_tag,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "playbook": playbook,
                "extra_vars": {
                    "p_mariadb_db_port": port,
                    "p_mariadb_login_name": self.admin_user,
                    "p_mariadb_login_password": self.admin_pwd,
                    "p_mariadb_user_mgmt_type": "addusr",
                    "p_mariadb_users": user_lst, # Now includes root@%
                },
            },
        }
        return res

    def action_install_extensions(self) -> dict: # Argument removed
        action_name = "install_extensions"

        # Read customization details from final_params
        customization = self.get_customization(action_name)
        if not customization:
            raise ApiManagerError(
                f"Customization '{action_name}' not found in final_params"
            )

        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        # Read engine port from final_params
        engine = self.final_params.get("engine", {})
        port = engine.get("port")

        # Logic moved/kept from original internal_run: Determine extensions
        # Note: The original logic checked for MySQL 8.x, which might not apply directly
        # to MariaDB 11.2. Adjust if MariaDB needs different extensions.
        extensions = ["audit:plugin"]
        # Example: If MariaDB 11 needed a different password validation plugin:
        # if "11." in self.version:
        #     extensions.append("some_mariadb_plugin:plugin")
        # For now, we keep the original logic intended for MySQL 8 compatibility check
        # Review if this check is still relevant for MariaDB 11
        if "8." in self.version:
            extensions.append("component_validate_password:component")

        # Adapt extension format (now uses locally determined 'extensions')
        extension_lst = []
        for extension in extensions:
            extension = extension.strip()
            name, e_type = extension.split(":")
            extension_lst.append({"name": name, "type": e_type})

        res = {
            "name": action_name,
            "desc": "install mariadb extensions", # Improved description
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent,
                "orchestrator_tag": orchestrator_tag,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "playbook": playbook,
                "extra_vars": {
                    "p_mariadb_db_port": port,
                    "p_mariadb_root_username": self.admin_user,
                    "p_mariadb_root_password": self.admin_pwd,
                    "p_ip_repository": self.ip_repository,
                    "p_mariadb_extensions": extension_lst,
                    "p_mariadb_db_restart": 1,
                },
            },
        }
        return res


class MariaDBImportHelper(MysqlImportHelper):
    default_engine = MariaDBBase

class MariaDBUpdateHelper(MysqlUpdateHelper):
    default_engine = MariaDBBase

class MariaDBActionHelper(SqlActionHelper):
    default_engine = MariaDBBase

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)

    def stop(self, **kwargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is already stopped")

        force = self.kvargs.get("force", False)

        # create task workflow
        steps = []

        if not force:
            steps.append(
                {
                    "step": ComputeStackMariaDBAction.task_path + "mariadb_manage_engine_step",
                    "args": [self.compute_instance.oid],
                }
            )
        # - stop server
        steps.append(
            {
                "step": ComputeStackAction.task_path + "sql_run_action_on_server_step",
                "args": [self.compute_instance.oid],
            }
        )

        self.kvargs["steps"] = steps

    def start(self, **kvargs):
        if self.compute_instance.is_running() is True:
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is already running")

        # create task workflow
        # start server
        steps = [
            {
                "step": ComputeStackAction.task_path + "sql_run_action_on_server_step",
                "args": [self.compute_instance.oid],
            }
        ]
        # wait server is up and running
        action_name_wait = "wait_ssh_is_up"
        customization_wait = self.get_customization(action_name_wait)
        if not customization_wait:
            raise ApiManagerError(f"Customization '{action_name_wait}' not found in final_params for start action")

        # Prepare data dict for the task step, ensuring necessary keys are present
        data_wait = {
            "customization": customization_wait.get("customization"),
            "playbook": customization_wait.get("playbook"),
            "orchestrator_tag": customization_wait.get("orchestrator_tag")
        }
        # Check if essential data is missing
        if not data_wait["customization"] or not data_wait["playbook"]:
            raise ApiManagerError(
                f"Missing 'customization' or 'playbook' in customization details for '{action_name_wait}'"
            )

        steps.append(
            {
                "step": ComputeStackAction.task_path + "sql_invoke_apply_customization_step",
                "args": [self.compute_instance.oid, data_wait], # <-- Use dynamically built data
            }
        )
        # - start engine
        steps.append(
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_manage_engine_step",
                "args": [self.compute_instance.oid],
            }
        )
        self.kvargs["steps"] = steps

    def restart(self, **kvargs):
        steps = []
        if self.compute_instance.is_running():
            self.logger.info("Server %s is running, restart database service", self.compute_instance.uuid)
            # restart engine
            steps.append(
                {
                    "step": ComputeStackMariaDBAction.task_path + "mariadb_manage_engine_step",
                    "args": [self.compute_instance.oid],
                }
            )
            self.kvargs["steps"] = steps
        else:
            self.logger.info("Server %s is stopped, start server and database service", self.compute_instance.uuid)
            self.start(**kvargs)

    def __run_mariadb_query(self, query):
        # get db admin credentials
        admin_user = self.get_db_admin_user()

        # --skip-column-names
        cmd = "mariadb -e '%s' -B -r -p'%s' | sed 's/\t/,/g'" % (
            query,
            admin_user.get("pwd"),
        )
        res = self.compute_instance.run_ad_hoc_command(cmd, parse="text")
        res = res.split("\n")[1:]
        return res

    @staticmethod
    def __remove_warning(s):
        idx = s.find("mysql: [Warning]")
        # warning msg not found
        if idx == -1:
            return s
        # warning msg found
        return s[:idx]

    def get_dbs(self):
        """"""
        self.get_compute_instance()
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        query = "SELECT * FROM information_schema.schemata;"
        dbs = self.__run_mariadb_query(query)

        res = []
        for item in dbs:
            item = self.__remove_warning(item)
            item = item.split(",")
            if item[1] in ["performance_schema", "information_schema", "sys", "mysql"]:
                continue
            res.append(
                {
                    "db_name": item[1],
                    "charset": item[2],
                    "collation": item[3],
                    "access_privileges": None,
                }
            )
        self.logger.info("get sql stack %s dbs: %s", self.stack.oid, res)
        return res

    def add_db(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        db_name = self.kvargs.get("db_name")
        charset = self.kvargs.get("charset")
        if charset is None:
            charset = dict_get(self.final_params, "engine.charset")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_add_db_step",
                "args": [self.compute_instance.oid, db_name, charset],
            }
        ]
        self.kvargs["steps"] = steps

    def drop_db(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        db_name = self.kvargs.get("db_name")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_drop_db_step",
                "args": [self.compute_instance.oid, db_name],
            }
        ]
        self.kvargs["steps"] = steps

    def get_users(self):
        self.get_compute_instance()
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        query = "SELECT Host,User,max_connections,plugin FROM mysql.user;"
        users = self.__run_mariadb_query(query)

        query = "SELECT * from information_schema.SCHEMA_PRIVILEGES;"
        grants = self.__run_mariadb_query(query)
        grants_res = {}
        for item in grants:
            item = item.split(",")
            grant = {"db": item[2], "privilege": item[3]}
            try:
                grants_res[item[0]].append(grant)
            except:
                grants_res[item[0]] = [grant]

        res = []
        for item in users:
            item = self.__remove_warning(item)
            item = item.split(",")
            res.append(
                {
                    "host": item[0],
                    "user": item[1],
                    "grants": grants_res.get("'%s'@'%s'" % (item[1], item[0])),
                    "max_connections": item[2],
                    "plugin": item[3],
                    "account_locked": 'N',
                }
            )
        self.logger.info("get sql stack %s dbs: %s", self.stack.oid, res)
        return res

    def add_user(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        usr_name = self.kvargs.get("name")
        usr_password = self.kvargs.get("password")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_add_user_step",
                "args": [self.compute_instance.oid, usr_name, usr_password],
            }
        ]
        self.kvargs["steps"] = steps

    def drop_user(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        usr_name = self.kvargs.get("name")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_drop_user_step",
                "args": [self.compute_instance.oid, usr_name],
            }
        ]
        self.kvargs["steps"] = steps

    def grant_privs(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        privileges = self.kvargs.get("privileges")
        db_name = self.kvargs.get("db_name")
        usr_name = self.kvargs.get("usr_name")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_grant_privs_step",
                "args": [
                    self.compute_instance.oid,
                    privileges,
                    db_name,
                    usr_name,
                ],
            }
        ]
        self.kvargs["steps"] = steps

    def revoke_privs(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        privileges = self.kvargs.get("privileges")
        db_name = self.kvargs.get("db_name")
        usr_name = self.kvargs.get("usr_name")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_revoke_privs_step",
                "args": [
                    self.compute_instance.oid,
                    privileges,
                    db_name,
                    usr_name,
                ],
            }
        ]
        self.kvargs["steps"] = steps

    def change_pwd(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        usr_name = self.kvargs.get("name")
        usr_new_password = self.kvargs.get("new_password")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_change_pwd_step",
                "args": [self.compute_instance.oid, usr_name, usr_new_password],
            }
        ]
        self.kvargs["steps"] = steps

    def install_extensions(self, **kwargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        # get extensions
        extensions = self.kvargs.get("extensions")
        if not isinstance(extensions, list):
            extensions = [extensions]

        # get vpc
        vpcs, _ = self.compute_instance.get_linked_resources(link_type="vpc", authorize=False, run_customize=False)
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.compute_instance.get_attribs().get("availability_zone")
        site = self.compute_instance.controller.get_resource(site_id)
        ip_repository = site.get_attribs().get("repo")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_install_extensions_step",
                "args": [self.compute_instance.oid, ip_repository, extensions],
            }
        ]
        self.kvargs["steps"] = steps


class MariaDBDeleteHelper(SqlDeleteHelper):
    default_engine = MariaDBBase


DbaasBase.register_child("mariadb", MariaDBBase)
SqlDeleteHelper.register_child("mariadb", MariaDBDeleteHelper)
SqlCreateHelper.register_child("mariadb", MariaDBCreateHelper)
SqlImportHelper.register_child("mariadb", MariaDBImportHelper)
SqlUpdateHelper.register_child("mariadb", MariaDBUpdateHelper)
SqlActionHelper.register_child("mariadb", MariaDBActionHelper)
