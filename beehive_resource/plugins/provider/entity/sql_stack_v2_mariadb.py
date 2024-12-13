# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from typing import Any, Dict
from beecell.password import random_password
from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.sql_stack_v2 import MysqlImportHelper, MysqlUpdateHelper, SqlHelper
from beehive_resource.plugins.provider.entity.sql_stack_v2 import (
    SqlActionHelper,
    SqlCreateHelper,
    SqlImportHelper,
    SqlUpdateHelper,
)
from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackAction, ComputeStackV2
from beehive_resource.plugins.provider.entity.stack_v2_mariadb import ComputeStackMariaDBAction
from beecell.simple import random_password, bool2str, dict_get, truncate, id_gen

# from beehive_resource.plugins.provider.task_v2.stack_v2_mariadb import StackV2MariaDBTask


class MariaDBBase(object):
    engine_params = {
        "versions": ["11.2"],
        "port": 3306,
        "hypervisor": "vsphere",
        "image": "Centos7",
        "volume_flavor": "vol.default",
        "host_group": "default",
        "customization": "mariadb",
        "playbook": {
            "install": "installMariaDB.yml",
            "config_replica": "-",
        },
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
        "lvm": {
            "volume_group": {"data": "vg_data", "backup": "vg_backup"},
            "logical_volume": {"data": "lv_fsdata", "backup": "lv_fsbackup"},
        },
        "mount_point": {
            "data": "/data",
            # 'backup': '/BCK_fisici'
        },
    }


class MariaDBCreateHelper(SqlCreateHelper):
    playbook_extension_mgmt: str = "extensionMgmtMariaDB.yml"
    playbook_enable_login_shell: str = "enable_login_shell.yml"
    playbook_user_mgmt: str = "UserMgmtMariaDB.yml"

    def __init__(self, controller, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = MariaDBBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, "license")
        self.admin_user = self.kvargs.pop("db_root_name", "root")
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=True)
        self.engine_major_version = SqlHelper.get_engine_major_version(self.version, 2)
        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        # get users for monitoring, backup, etc.
        service_users: Dict[str, Any] = self.engine_params.get("service_users", {})
        self.monit_user = self.get_db_monit_user(service_users)
        # add user account 'root'@'%'
        service_users.update(
            {
                "admin": [
                    {
                        "name": "root",
                        "pwd": self.admin_pwd,
                        "host": "%",
                        "privs": "*.*:ALL,GRANT",
                    }
                ]
            }
        )

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_create_server())
        # - wait ssh is up and running
        self.actions.append(self.action_wait_ssh_up())
        # - set etc/hosts
        self.actions.append(self.action_set_etc_hosts())
        if self.image.name == "OracleLinux8":
            # - set dnf proxy
            self.actions.append(self.action_set_dnf_proxy())
        # - setup volume (prepare, format, mount)
        data_device = self.get_volume_device_path("b")
        self.actions.append(
            self.action_setup_volume(
                data_dir=self.data_dir,
                data_device=data_device,
                volume_group=self.lvm_vg_data,
                logical_volume=self.lvm_lv_data,
            )
        )
        # - install mariadb
        # todo: port, charset, timezone, db_appuser_name, db_appuser_name
        self.actions.append(self.action_install_mariadb())
        # - enable login shell for mariadb user
        self.actions.append(self.action_enable_login_shell(user="mysql", shell="/bin/bash"))
        # - create users for backup and monitoring
        self.actions.append(self.action_add_users(service_users))
        # - install extensions (i.e. plugins or components)
        extensions = ["audit:plugin"]
        if "8." in self.version:
            extensions.append("component_validate_password:component")
        self.actions.append(self.action_install_extensions(extensions))
        if self.monit_user:
            # - enable monitoring
            self.actions.append(self.action_enable_monitoring())
        # - enable log forwarding
        # self.actions.append(self.action_enable_log_forwarding())
        if self.csi_custom:
            # todo: add actions
            pass

    def set_additional_steps(self):
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
        res = {
            "name": "install_mariadb",
            "desc": "install mariadb",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-install_mariadb" % self.name,
                "parent": self.compute_customization.oid,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": self.playbook,
                "extra_vars": {
                    "p_mariadb_repo_version": self.engine_major_version,
                    "p_proxy_server": self.proxy,
                    "p_ip_repository": self.ip_repository,
                    "p_url_repository": self.url_repository,
                    "p_mariadb_root_username": self.admin_user,
                    "p_mariadb_root_password": self.admin_pwd,
                    "p_mariadb_server_ram": self.server_ram_gb,
                },
            },
        }
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

    def action_enable_login_shell(self, user="mysql", shell="/bin/bash"):
        res = {
            "name": "enable_login_shell",
            "desc": "enable_login_shell",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-enable_login_shell" % self.name,
                "parent": "os-utility",
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": self.playbook_enable_login_shell,
                "extra_vars": {"p_user": user, "p_shell": shell},
            },
        }
        return res

    def action_add_users(self, users):
        # adapt users format to the one accepted by ansible role
        user_lst = []
        for v in users.values():
            user_lst.extend(v)

        res = {
            "name": "add_users",
            "desc": "add_users",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-add_users" % self.name,
                "parent": self.compute_customization.oid,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": self.playbook_user_mgmt,
                "extra_vars": {
                    "p_mariadb_db_port": self.port,
                    "p_mariadb_login_name": self.admin_user,
                    "p_mariadb_login_password": self.admin_pwd,
                    "p_mariadb_user_mgmt_type": "addusr",
                    "p_mariadb_users": user_lst,
                },
            },
        }
        return res

    def action_install_extensions(self, extensions):
        # adapt extension format to the one accepted by ansible role
        extension_lst = []
        for extension in extensions:
            extension = extension.strip()
            name, type = extension.split(":")
            extension_lst.append({"name": name, "type": type})

        res = {
            "name": "install_extensions",
            "desc": "install_extensions",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-install_extensions" % self.name,
                "parent": self.compute_customization.oid,
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": self.playbook_extension_mgmt,
                "extra_vars": {
                    "p_mariadb_db_port": self.port,
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
    def __init__(self, controller, container, *args, **kvargs):
        SqlImportHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = MariaDBBase.engine_params


class MariaDBUpdateHelper(MysqlUpdateHelper):
    def __init__(self, *args, **kvargs):
        SqlUpdateHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = MariaDBBase.engine_params


class MariaDBActionHelper(SqlActionHelper):
    def __init__(self, *args, **kvargs):
        SqlActionHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = MariaDBBase.engine_params

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)

    def stop(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is already stopped" % self.compute_instance.uuid)

        force = self.kvargs.get("force", False)

        # create task workflow
        steps = []
        # - stop engine
        # task_path = "%s.%s." % (StackV2MariaDBTask.__module__, StackV2MariaDBTask.__name__)
        # self.logger.info("+++++ stop - task_path: %s" % task_path)

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
            raise ApiManagerError("Server %s is already running" % self.compute_instance.uuid)

        # create task workflow
        # - start server
        # task_path = "%s.%s." % (StackV2MariaDBTask.__module__, StackV2MariaDBTask.__name__)
        # self.logger.info("+++++ start - task_path: %s" % task_path)

        steps = [
            {
                "step": ComputeStackAction.task_path + "sql_run_action_on_server_step",
                "args": [self.compute_instance.oid],
            }
        ]
        # - wait server is up and running
        data = {
            "customization": "os-utility",
            "playbook": "wait_ssh_is_up.yml",
        }
        steps.append(
            {
                "step": ComputeStackAction.task_path + "sql_invoke_apply_customization_step",
                "args": [self.compute_instance.oid, data],
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
        if self.compute_instance.is_running() is True:
            self.logger.info("Server %s is running, restart database service" % self.compute_instance.uuid)
            # restart engine
            steps.append(
                {
                    "step": ComputeStackMariaDBAction.task_path + "mariadb_manage_engine_step",
                    "args": [self.compute_instance.oid],
                }
            )
            self.kvargs["steps"] = steps
        else:
            self.logger.info("Server %s is stopped, start server and database service" % self.compute_instance.uuid)
            self.start(**kvargs)

    def __run_mariadb_query(self, query):
        # get db admin credentials
        admin_user = self.get_db_admin_user()

        # cmd = "mysqlsh --json=raw --sql --uri '%s:%s@localhost:3306' -e '%s' | head -2 | tail -1" % \
        #       (admin_user.get('name'), admin_user.get('pwd'), query)

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
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

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
        self.logger.info("get sql stack %s dbs: %s" % (self.stack.oid, res))
        return res

    def add_db(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

        db_name = self.kvargs.get("db_name")
        charset = self.kvargs.get("charset")
        if charset is None:
            charset = dict_get(self.engine_params, "charset")

        # create task workflow
        steps = [
            {
                "step": ComputeStackMariaDBAction.task_path + "mariadb_add_db_step",
                "args": [self.compute_instance.oid, db_name, charset],
            }
        ]
        self.kvargs["steps"] = steps

    def drop_db(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

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
        """"""
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        query = "SELECT Host,User,max_connections,plugin,account_locked FROM mysql.user;"
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
                    "account_locked": item[4],
                }
            )
        self.logger.info("get sql stack %s dbs: %s" % (self.stack.oid, truncate(res)))
        return res

    def add_user(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

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
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

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
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

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
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

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
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

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
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # TODO: check engine status

        # get extensions
        extensions = self.kvargs.get("extensions")
        if not isinstance(extensions, list):
            extensions = [extensions]

        # get vpc
        vpcs, total = self.compute_instance.get_linked_resources(link_type="vpc", authorize=False, run_customize=False)
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
