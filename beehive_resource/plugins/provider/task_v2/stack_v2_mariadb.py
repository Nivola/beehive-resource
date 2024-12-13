# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2
from beehive_resource.plugins.provider.task_v2.stack_v2 import StackV2SqlTask


class StackV2MariaDBTask(StackV2SqlTask):
    """Stack V2 mariadb task"""

    name = "stack_v2_mariadb_task"
    entity_class = ComputeStackV2

    @staticmethod
    @task_step()
    def mariadb_manage_engine_step(task, step_id, params, compute_instance_id, *args, **kvargs):
        """Manage (i.e. start, stop, restart) database engine"""
        data = {
            "customization": "db-utility",
            "playbook": "manage.yml",
            "extra_vars": {
                "engine": params.get("engine"),
                "version": params.get("version"),
                "operation": params.get("action_name"),
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_add_db_step(task, step_id, params, compute_instance_id, db_name, charset, *args, **kvargs):
        """Create database and schema"""
        data = StackV2MariaDBTask.mariadb_commons(params)
        data["playbook"] = "DbMgmtMariaDB.yml"
        extras = {
            "p_mariadb_db_name": db_name,
            "p_mariadb_db_encoding": charset,
            "p_mariadb_db_mgmt_type": "add",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_drop_db_step(task, step_id, params, compute_instance_id, db_name, *args, **kvargs):
        """Delete database"""
        data = StackV2MariaDBTask.mariadb_commons(params)
        data["playbook"] = "DbMgmtMariaDB.yml"
        extras = {"p_mariadb_db_name": db_name, "p_mariadb_db_mgmt_type": "delete"}
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_add_user_step(
        task,
        step_id,
        params,
        compute_instance_id,
        usr_name,
        usr_password,
        *args,
        **kvargs,
    ):
        """Create db user"""
        data = {
            "customization": "db-utility",
            "playbook": "manage.yml",
            "extra_vars": {
                "engine": params.get("engine"),
                "operation": params.get("action_name"),
                "p_port": params.get("port"),
                "p_admin_usr": params.get("admin_usr"),
                "p_admin_pwd": params.get("admin_pwd"),
                "p_usr_name": usr_name,
                "p_usr_pwd": usr_password,
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_change_pwd_step(
        task,
        step_id,
        params,
        compute_instance_id,
        usr_name,
        new_password,
        *args,
        **kvargs,
    ):
        """Update db user password"""
        data = StackV2MariaDBTask.mariadb_commons(params)
        data["playbook"] = "UserMgmtMariaDB.yml"
        extras = {
            "p_mariadb_users": [{"name": usr_name, "pwd": new_password}],
            "p_mariadb_user_mgmt_type": "chpwdusr",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_drop_user_step(task, step_id, params, compute_instance_id, usr_name, *args, **kvargs):
        """Delete db user"""
        data = StackV2MariaDBTask.mariadb_commons(params)
        data["playbook"] = "UserMgmtMariaDB.yml"
        extras = {
            "p_mariadb_users": [{"name": usr_name}],
            "p_mariadb_user_mgmt_type": "delusr",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_grant_privs_step(
        task,
        step_id,
        params,
        compute_instance_id,
        privileges,
        db_name,
        usr_name,
        *args,
        **kvargs,
    ):
        """Assign privileges to db user"""
        data = StackV2MariaDBTask.mariadb_commons(params)
        data["playbook"] = "UserMgmtMariaDB.yml"
        extras = {
            "p_mariadb_users": [{"name": usr_name, "privs": "{}.*:{}".format(db_name, privileges)}],
            "p_mariadb_user_mgmt_type": "addpriv",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_revoke_privs_step(
        task,
        step_id,
        params,
        compute_instance_id,
        privileges,
        db_name,
        usr_name,
        *args,
        **kvargs,
    ):
        """Revoke privileges from db user"""
        data = StackV2MariaDBTask.mariadb_commons(params)
        data["playbook"] = "UserMgmtMariaDB.yml"
        extras = {
            "p_mariadb_users": [{"name": usr_name, "privs": "{} ON {}.*".format(privileges, db_name)}],
            "p_mariadb_user_mgmt_type": "revokepriv",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mariadb_install_extensions_step(
        task,
        step_id,
        params,
        compute_instance_id,
        ip_repository,
        extensions,
        *args,
        **kvargs,
    ):
        """Install db extension(s)"""
        data = {
            "customization": "mariadb",
            "playbook": "extensionMgmtMariaDB.yml",
            "extra_vars": {
                "p_mariadb_db_port": params.get("port"),
                "p_mariadb_root_username": params.get("admin_usr"),
                "p_mariadb_root_password": params.get("admin_pwd"),
                "p_ip_repository": ip_repository,
                "p_mariadb_extensions": extensions,
                "p_mariadb_db_restart": 1,
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    def mariadb_commons(params):
        return {
            "customization": "mariadb",
            "extra_vars": {
                "p_mariadb_db_port": params.get("port"),
                "p_mariadb_login_name": params.get("admin_usr"),
                "p_mariadb_login_password": params.get("admin_pwd"),
            },
        }
