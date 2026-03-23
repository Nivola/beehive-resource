# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations

from typing import Any

from beecell.simple import random_password, bool2str, dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackAction, ComputeStackPostgresqlAction

from .helper import (
    DbaasBase,
    SqlHelper,
    SqlActionHelper,
    SqlDeleteHelper,
    SqlImportHelper,
    SqlCreateHelper,
    SqlUpdateHelper,
    EngineParams,
    nvl
)

class PostgresqlBase(DbaasBase):
    engine_params: EngineParams = {
        "hypervisor": "vsphere",
        "volume_flavor": "vol.gold",
        "host_group": "default",
        "lvm": {
            "volume_group": {
                "data": "vg_data",
                "backup": "vg_backup"
            },
            "logical_volume": {
                "data": "lv_fsdata",
                "backup": "lv_fsbackup"
            }
        },
        "mount_point": {
            "data": "/data"
        },

        "engine": {
            "port": 5432,
            "customization": "postgresql",
            "license": "general-public-license",
            "charset": "utf8",
            "encoding": "UTF-8",
            "lc_collate": "en_US.UTF-8",
            "lc_ctype": "en_US.UTF-8",
            "geo_extension": True,
            "service_users": {
                "zabbix": [
                    {
                        "name": "zabbute",
                        "pwd": "7nTo6jviqVbD",
                        "attribs": "NOSUPERUSER,INHERIT,NOCREATEDB,NOCREATEROLE,NOREPLICATION",
                        "privs": "CONNECT:postgres"
                    },
                    {
                        "name": "rou",
                        "pwd": "rou!14",
                        "attribs": "NOSUPERUSER,INHERIT,NOCREATEDB,NOCREATEROLE",
                        "privs": "CONNECT:postgres"
                    }
                ]
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
                    "install_postgresql",
                    "add_users",
                    "grant_privs",
                    "setup_mailx",
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
            "install_postgresql": {
                "playbook": "installPostgres.yml",
                "orchestrator_tag": "default",
                "customization": "postgresql"
            },
            "add_users": {
                "playbook": "userMgmtPostgres.yml",
                "orchestrator_tag": "default",
                "customization": "postgresql"
            },
            "grant_privs": {
                "playbook": "privsMgmtPostgres.yml",
                "orchestrator_tag": "default",
                "customization": "postgresql"
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
            "enable_log_forwarding": {
                "playbook": "install.yml",
                "orchestrator_tag": "default",
                "customization": "filebeat"
            },
            "setup_nfsbcklogici_delete": {
                "playbook": "pre_dbaas_uninstall.yml",
                "customization": "pre_dbaas_uninstall",
                "orchestrator_tag": "02"
            },
            "config_replica": {
                "playbook": "configPostgresReplica.yml",
                "orchestrator_tag": "default",
                "customization": "postgresql"
            }
        }
    }


class PostgresqlDeleteHelper(SqlDeleteHelper):
    """
    Delete.
    """
    default_engine = PostgresqlBase


class PostgresqlCreateHelper(SqlCreateHelper):
    """
    Create.
    """
    default_engine = PostgresqlBase

    def internal_run(self):
        # --- Original parameter setup (can be refactored later) ---
        engine = self.final_params.get('engine')
        self.admin_user = "postgres"
        self.admin_pwd = random_password(length=20, strong=True)

        self.engine_major_version = SqlHelper.get_engine_major_version(self.version, 2)
        self.image = self.get_image()  # This method still reads from kvargs, may need refactoring
        self.os_ver = self.image.get_os_version()

        self.custom_attributes = {"postgres:database": "postgres"}
        self.outputs.append(self.set_output())

        # --- NEW: Declarative workflow orchestration ---
        # Read the sequence of steps directly from the final configuration
        steps_order = engine.get("steps_order")
        create_steps = steps_order.get('create', [])

        if not create_steps:
            raise Exception("Workflow steps ('steps_order.create') not found in the final configuration.")

        for step_name in create_steps:
            # Find the corresponding action method dynamically
            action_method = getattr(self, f"action_{step_name}", None)

            if action_method and callable(action_method):
                self.logger.debug("Appending action: %s", step_name)
                self.actions.append(action_method())
            else:
                self.logger.warning("Action method action_%s not found or not callable.", step_name)

    def _get_param(self, param_name_user: str, param_path_final: str, default_value: Any = None) -> Any:
        """
        Gets a parameter value respecting the priority:
        1. User-specific options (from postgresql_params).
        2. Merged configuration (from final_params - definition/defaults).
        3. A provided default value.

        Args:
            param_name_user: The key name in the user parameters (e.g., 'db_name').
            param_path_final: The dotted path key in self.final_params (e.g., 'engine.db_name').
            default_value: The ultimate fallback value if not found anywhere.

        Returns:
            The final parameter value.
        """
        # 1. Check user-specific parameters (highest priority)
        user_params = self.kvargs.get('postgresql_params', {})
        value = user_params.get(param_name_user)

        if value is not None:
            # User provided a value (even if empty string potentially)
            return value
        # 2. Fallback to the merged configuration (definition/defaults)
        return dict_get(self.final_params, param_path_final, default_value)

    def action_install_postgresql(self):
        action_name = "install_postgresql"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        postgis_ext = bool2str(self._get_param('geo_extension', 'engine.geo_extension',
                                               True))

        optional_extensions = self._get_param('extensions',
                                              'engine.extensions',"")

        new_db_name = self._get_param('db_name','engine.db_name')
        new_role_name = self._get_param('role_name', 'engine.role_name')
        new_schema_name = self._get_param('schema_name','engine.schema_name')
        new_db_lc_collate = self._get_param('lc_collate','engine.lc_collate')

        res = {
            "name": action_name,
            "desc": "install postgresql",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",

                # Read 'parent' and 'playbook' from the final, merged configuration
                "parent": parent,
                "playbook": playbook,
                "orchestrator_tag": orchestrator_tag,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "extra_vars": {
                    # Dynamic/contextual values (remain unchanged)
                    "p_proxy_server": self.proxy,
                    "p_ip_repository": self.ip_repository,
                    "p_url_repository": self.build_repo_url(),
                    "p_postgres_repo_version": self.engine_major_version,
                    "p_postgres_admin_pwd": self.admin_pwd,
                    "p_postgres_server_ram": self.server_ram_mb,
                    "p_postgis_ext": postgis_ext,
                    "p_optional_extensions": optional_extensions,
                    "p_new_db_name": nvl(new_db_name),
                    "p_new_role_name": nvl(new_role_name),
                    "p_new_role_pwd": nvl(self._get_param('password', 'engine.password')),
                    "p_new_schema_name": nvl(new_schema_name),
                    "p_new_db_encoding": nvl(self._get_param('encoding', 'engine.charset')),
                    "p_new_db_lc_collate": nvl(new_db_lc_collate),
                    "p_new_db_lc_ctype": nvl(self._get_param('lc_ctype', 'engine.lc_ctype')),
                },
            },
        }
        #check if kms_domain are present
        engine = self.engine_configs
        # self.final_params.get("engine")    
        optvalue= engine.get("kms_domain") 
        if optvalue is not None:
            res["params"]["extra_vars"]["p_kms_domain"] = optvalue
            
        optvalue= engine.get('kms_env')
        if optvalue is not None:
            res["params"]["extra_vars"]["p_kms_env"] = optvalue
            
        optvalue= engine.get('kms_domain_user')
        if optvalue is not None:
            res["params"]["extra_vars"]["p_kms_domain_user"] = optvalue
            
        optvalue= engine.get('kms_domain_pwd')
        if optvalue is not None:
            res["params"]["extra_vars"]["p_kms_domain_pwd"] = optvalue

        return res

    def action_add_users(self):
        action_name = "add_users"
        engine = self.final_params.get("engine")
        service_users = engine.get("service_users")
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        port = engine.get("port")
        # adapt users format to the one accepted by ansible role
        user_lst = []
        for v in service_users.values():
            user_lst.extend(v)

        res = {
            "name": action_name,
            "desc": "add users",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "playbook": playbook,
                "orchestrator_tag": orchestrator_tag,
                "extra_vars": {
                    "p_postgres_db_port": port,
                    "p_postgres_login_username": self.admin_user,
                    "p_postgres_login_password": self.admin_pwd,
                    "p_postgres_mgmt_action": "add_user",
                    "p_postgres_users": user_lst,
                },
            },
        }
        return res

    def action_grant_privs(self):
        action_name = "grant_privs"
        engine = self.final_params.get("engine")
        service_users = engine.get("service_users")
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        port = engine.get("port")
        # adapt privileges format to the one accepted by ansible role
        priv_lst = []
        for v in service_users.values():
            for item in v:
                usr_name = item.get("name")
                privs, db_name = item.get("privs").split(":")
                db_name = db_name.split(".")
                schema_name = "*"
                if len(db_name) > 1:
                    schema_name = db_name[1]
                db_name = db_name[0]
                priv_lst.append(
                    {
                        "user": usr_name,
                        "privs": privs,
                        "db": db_name,
                        "schema": schema_name,
                    }
                )

        res = {
            "name": action_name,
            "desc": "grant privs",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": f"$$action_resource.{self.name}-create_server1::id$$",
                        "extra_vars": {},
                    }
                ],
                "playbook": playbook,
                "orchestrator_tag": orchestrator_tag,
                "extra_vars": {
                    "p_postgres_db_port": port,
                    "p_postgres_login_username": self.admin_user,
                    "p_postgres_login_password": self.admin_pwd,
                    "p_postgres_mgmt_action": "grant_privs",
                    "p_postgres_privs": priv_lst,
                },
            },
        }
        return res


class PostgresqlImportHelper(SqlImportHelper):
    """
    Import.
    """
    default_engine = PostgresqlBase

    def internal_run(self):
        self.admin_user = "postgres"

        self.outputs.append(self.set_output())

        # import create vm and volumes data in cmp
        self.actions.append(self.action_import_server())


class PostgresqlUpdateHelper(SqlUpdateHelper):
    """
    Update.
    """
    default_engine = PostgresqlBase

    def internal_run(self):
        pass


class PostgresqlActionHelper(SqlActionHelper):
    """
    Actions.
    """
    default_engine = PostgresqlBase

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
        # - stop engine
        if not force:
            steps.append(
                {
                    "step": ComputeStackPostgresqlAction.task_path + "pgsql_manage_engine_step",
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
        if self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is already running")

        # create task workflow
        # - start server
        steps = [
            {
                "step": ComputeStackAction.task_path + "sql_run_action_on_server_step",
                "args": [self.compute_instance.oid],
            }
        ]
        # - wait server is up and running
        data = {"customization": "os-utility", "playbook": "wait_ssh_is_up.yml"}
        steps.append(
            {
                "step": ComputeStackAction.task_path + "sql_invoke_apply_customization_step",
                "args": [self.compute_instance.oid, data],
            }
        )
        # - start engine
        steps.append(
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_manage_engine_step",
                "args": [self.compute_instance.oid],
            }
        )
        self.kvargs["steps"] = steps

    def restart(self, **kvargs):
        steps = []
        if self.compute_instance.is_running() is True:
            self.logger.info("Server %s is running, restart database service", self.compute_instance.uuid)
            # restart engine
            steps.append(
                {
                    "step": ComputeStackPostgresqlAction.task_path + "pgsql_manage_engine_step",
                    "args": [self.compute_instance.oid],
                }
            )
            self.kvargs["steps"] = steps
        else:
            self.logger.info("Server %s is stopped, start server and database service", self.compute_instance.uuid)
            self.start(**kvargs)

    def __run_pgsql_query(self, query, database="postgres"):
        cmd = "su - postgres -c \"psql -c \\\"%s\\\" -At -R '+++' -F '|' -d '%s'\"" % (
            query,
            database,
        )
        self.logger.warn(cmd)
        res = self.compute_instance.run_ad_hoc_command(cmd, parse="text")
        res = res.replace("\n", ",").split("+++")
        return res

    def get_dbs(self):
        self.get_compute_instance()
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        query = r"\l+"
        dbs = self.__run_pgsql_query(query)
        self.logger.warn(dbs)
        res = []
        for item in dbs:
            item = item.split("|")

            if item[0].find("template") >= 0:
                continue

            # get database schemas
            query = "SELECT schema_name FROM information_schema.schemata;"
            schemas = self.__run_pgsql_query(query, database=item[0])
            res_schemas = []
            for schema in schemas:
                if schema == "information_schema" or schema.find("pg_") >= 0:
                    continue
                res_schemas.append(schema)

            res.append(
                {
                    "db_name": item[0],
                    "charset": item[2],
                    "collation": item[3],
                    "access_privileges": item[5],
                    "size": item[6],
                    "schemas": res_schemas,
                }
            )
        self.logger.info("get sql stack %s dbs: %s" , self.stack.oid, res)
        return res

    def add_db(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        db_name = self.kvargs.get("db_name")
        db_name = db_name.split(".")
        schema = "*"
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]
        charset = self.kvargs.get("charset")
        if charset is None:
            charset = dict_get(self.engine_params, "charset")
        charset = charset.upper()

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_add_db_step",
                "args": [self.compute_instance.oid, db_name, charset, schema],
            }
        ]
        self.kvargs["steps"] = steps

    def drop_db(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        db_name = self.kvargs.get("db_name")
        db_name = db_name.split(".")
        schema = "*"
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_drop_db_step",
                "args": [self.compute_instance.oid, db_name, schema],
            }
        ]
        self.kvargs["steps"] = steps

    def get_users(self):
        self.get_compute_instance()
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        query = r"\du"
        users = self.__run_pgsql_query(query)

        res = []
        for item in users:
            item = item.split("|")
            res.append(
                {
                    "host": "%",
                    "user": item[0],
                    "grants": [],  # grants_res.get('\'%s\'@\'%s\'' % (item[1], item[0])),
                    "max_connections": "",
                    "plugin": "",
                    "account_locked": "",
                }
            )
        self.logger.info("get sql stack %s dbs: %s", self.stack.oid, res)
        return res

    def add_user(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        usr_name = self.kvargs.get("name")
        usr_password = self.kvargs.get("password")
        usr_attribs = self.kvargs.get("attribs", "")

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_add_user_step",
                "args": [
                    self.compute_instance.oid,
                    usr_name,
                    usr_password,
                    usr_attribs,
                ],
            }
        ]
        self.kvargs["steps"] = steps

    def drop_user(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        usr_name = self.kvargs.get("name")
        force = bool2str(self.kvargs.get("force", False))

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_drop_user_step",
                "args": [self.compute_instance.oid, usr_name, force],
            }
        ]
        self.kvargs["steps"] = steps

    def grant_privs(self, **kvargs):
        if not self.compute_instance.is_running():
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        privileges = self.kvargs.get("privileges")
        usr_name = self.kvargs.get("usr_name")
        db_name = self.kvargs.get("db_name")
        db_name = db_name.split(".")
        schema = "*"
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_manage_privs_step",
                "args": [
                    self.compute_instance.oid,
                    privileges,
                    db_name,
                    schema,
                    usr_name,
                ],
            }
        ]
        self.kvargs["steps"] = steps

    def revoke_privs(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        privileges = self.kvargs.get("privileges")
        db_name = self.kvargs.get("db_name")
        usr_name = self.kvargs.get("usr_name")
        db_name = db_name.split(".")
        schema = "*"
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_manage_privs_step",
                "args": [
                    self.compute_instance.oid,
                    privileges,
                    db_name,
                    schema,
                    usr_name,
                ],
            }
        ]
        self.kvargs["steps"] = steps

    def change_pwd(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        usr_name = self.kvargs.get("name")
        usr_new_password = self.kvargs.get("new_password")

        # create task workflow
        steps = [
            {
                "step": ComputeStackPostgresqlAction.task_path + "pgsql_change_user_pwd_step",
                "args": [self.compute_instance.oid, usr_name, usr_new_password],
            }
        ]
        self.kvargs["steps"] = steps


DbaasBase.register_child("postgresql", PostgresqlBase)
SqlDeleteHelper.register_child("postgresql", PostgresqlDeleteHelper)
SqlCreateHelper.register_child("postgresql", PostgresqlCreateHelper)
SqlImportHelper.register_child("postgresql", PostgresqlImportHelper)
SqlUpdateHelper.register_child("postgresql", PostgresqlUpdateHelper)
SqlActionHelper.register_child("postgresql", PostgresqlActionHelper)
