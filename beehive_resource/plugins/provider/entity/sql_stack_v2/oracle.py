# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from __future__ import annotations

from typing import TYPE_CHECKING, Union, Dict, Any

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

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController

NO_VALUE = "--"


class OracleBase(DbaasBase):
    engine_params: EngineParams = {
        "hypervisor": "vsphere",
        "image": "Oracle19EE",
        "volume_flavor": "vol.oracle.default",
        "host_group": "default",
        "os_dbuser": "ora19c",
        "oversion": "19c",
        "db_name": "ORCL0",
        "arch_mode": "Y",
        "part_option": "Y",
        "nat_charset": "AL16UTF16",
        "lsn_port": "1522",
        "data_tbs_next": "32M",
        "data_tbs_size": "2048M",
        "idx_tbs_next": "16M",
        "idx_tbs_size": "1024M",
        "lob_tbs_next": "32M",
        "lob_tbs_size": "2048M",
        "lvm": {
            "volume_group": {"data": "vg_oradata", "backup": "vg_orabck"},
            "logical_volume": {"data": "lv_oradata", "backup": "lv_orabck"},
        },
        "mount_point": {"data": "/oradata", "backup": "/BCK_fisici"},

        "engine": {
            "port": 1521,
            "customization": "oracle",
            "license": "license-included",
            "charset": "WE8ISO8859P1",
            "service_users": {
                "zabbix": [{"name": "rou", "pwd": "Rou!142018", "host": "%", "privs": "*.*:SELECT"}]
            },
            "steps_order": {
                "create": [
                    "create_server",
                    "wait_ssh_is_up",
                    "set_yum_proxy",
                    "setup_volume_data",
                    "setup_volume_bck",
                    "setup_nfsbcklogici_add",
                    "install_oracle",
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
            "install_oracle": {
                "playbook": "CreateDboracle.yml",  #
                "orchestrator_tag": "default",
                "customization": "oracle"  #
            },
            "setup_nfsbcklogici_delete": {
                "playbook": "pre_dbaas_uninstall.yml",
                "orchestrator_tag": "02",
                "customization": "pre_dbaas_uninstall"
            }
        }
    }


class OracleDeleteHelper(SqlDeleteHelper):
    """
    Delete.
    """
    default_engine = OracleBase

    def __init__(self, stack, *args, **kvargs):
        SqlDeleteHelper.__init__(self, stack, *args, **kvargs)
        # set default engine params
        self.engine_params = OracleBase.engine_params
        self._build_final_params()


class OracleCreateHelperNew(SqlCreateHelper):
    """
    Create.
    """
    default_engine = OracleBase

    def __init__(self, controller: ResourceController, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        if TYPE_CHECKING:
            # oracle user password for  monitoring
            self.ora_user_eidp_pwd: Union[str, None]
            self.ora_user_csimon_pwd: Union[str, None]
            self.ora_user_perfstat_pwd: Union[str, None]
            self.ora_user_fw_pwd: Union[str, None]
            self.ora_user_pdbadmin_pwd: Union[str, None]
            self.ora_version: Union[str, None]
            self.ora_db_name: Union[str, None]
            self.ora_charset: Union[str, None]
            self.charset: Union[str, None]
            self.ora_nat_cset: Union[str, None]
            self.ora_dataf_path: Union[str, None]
            self.backup_dir: Union[str, None]
            self.ora_os_user: Union[str, None]
            self.ora_arch_mode: Union[str, None]
            self.ora_part_option: Union[str, None]
            self.ora_lsn_port: Union[str, None]
            self.oracle_data_disk_size: Union[int, None]
            self.oracle_bck_disk_size: Union[int, None]
            self.ora_recovf_path: Union[str, None]
            self.ora_splunkdir_fwuser: Union[str, None]
            self.ora_dir_fwuser: Union[str, None]
            self.ora_logdir_fwuser: Union[str, None]
            # starter pack
            self.ora_starter_pack: Union[str, None]
            self.ora_user_name: Union[str, None]
            self.ora_user_pwd: Union[str, None]
            self.ora_data_tbs_name: Union[str, None]
            self.ora_data_tbs_next: Union[str, None]
            self.ora_data_tbs_size: Union[str, None]
            self.ora_idx_tbs_name: Union[str, None]
            self.ora_idx_tbs_next: Union[str, None]
            self.ora_idx_tbs_size: Union[str, None]
            self.ora_lob_tbs_name: Union[str, None]
            self.ora_lob_tbs_next: Union[str, None]
            self.ora_lob_tbs_size: Union[str, None]

        # set default engine params
        self.engine_params = OracleBase.engine_params

    def _get_ora_param(self, user_key: str, final_path: str, default: Any = None) -> Any:
        """
        Retrieves a parameter respecting the hierarchy:
        1. User input (from oracle_params)
        2. Final configuration (Definition YML + Defaults)
        3. Default (fallback)
        """
        user_params = self.kvargs.get('oracle_params', {})
        value = user_params.get(user_key)

        if value is not None:
            return value

        # If final_path is None, it means we don't have a default path
        # in final_params. Just return the default value.
        if final_path is None:
            return default

        # Look in self.final_params
        return dict_get(self.final_params, final_path, default=default)

    def action_create_server(self) -> dict:
        """
        Create action definition in order to create the server

        Returns:
            dict: Dictionary cotaining the step action definition
        """
        res = SqlCreateHelper.action_create_server(self)

        res["params"]["block_device_mapping"].append(
            {
                "boot_index": 2,
                "volume_size": self.bck_disk_size,
                "flavor": self.volume_flavor.oid,
                "volume_tags": "nws$volume_bck",
            }
        )

        return res

    def check_params(self):
        """
        Check parameters are set and does some initialization.

        Raises:
            ApiManagerError: _description_
        """
        # Call parent: Initializes self.final_params and base kvargs
        SqlCreateHelper.check_params(self)

        # Init Oracle Passwords
        self.ora_user_eidp_pwd = random_password(length=20, strong=False)
        self.ora_user_csimon_pwd = random_password(length=20, strong=False)
        self.ora_user_perfstat_pwd = random_password(length=20, strong=False)
        self.ora_user_fw_pwd = random_password(length=20, strong=False)
        self.ora_user_pdbadmin_pwd = random_password(length=20, strong=False)

        # Get user input dictionary
        oracle_parameters = self.kvargs.get("oracle_params", {})

        # Read ora_version from final_params (based on self.version set by parent)
        self.ora_version = dict_get(
            self.final_params, f"oversion"
        )

        # ora_db_name: Read from user input, fallback to final_params
        self.ora_db_name = oracle_parameters.get("oracle_db_name")
        if self.ora_db_name is None:
            self.ora_db_name = dict_get(self.final_params, "db_name")

        # ora_charset: Read from user input, fallback to final_params
        self.ora_charset = oracle_parameters.get("oracle_charset")
        if self.ora_charset is None:
            self.ora_charset = dict_get(self.final_params, "engine.charset")
        self.charset = self.ora_charset

        # ora_nat_cset: Read from user input, fallback to final_params
        self.ora_nat_cset = oracle_parameters.get("oracle_natcharset")
        if self.ora_nat_cset is None:
            self.ora_nat_cset = dict_get(self.final_params, "nat_charset")

        # ora_dataf_path: Use self.data_dir (set by parent or fallback here)
        if self.data_dir is None:
            self.data_dir = dict_get(self.final_params, "mount_point.data")

        self.ora_dataf_path = self.data_dir

        # backup_dir: Read from user input, fallback to final_params
        self.backup_dir = self.kvargs.get("backup_dir")
        if self.backup_dir is None:
            self.backup_dir = dict_get(self.final_params, "mount_point.backup")

        # ora_os_user: Read from user input, fallback to final_params
        self.ora_os_user = oracle_parameters.get("oracle_os_user")
        if self.ora_os_user is None:
            self.ora_os_user = dict_get(
                self.final_params, "os_dbuser"
            )

        # ora_arch_mode: Read from user input, fallback to final_params
        self.ora_arch_mode = oracle_parameters.get("oracle_archivelog_mode")
        if self.ora_arch_mode is None:
            self.ora_arch_mode = dict_get(self.final_params, "arch_mode")

        # ora_part_option: Read from user input, fallback to final_params
        self.ora_part_option = oracle_parameters.get("oracle_partitioning_option")
        if self.ora_part_option is None:
            self.ora_part_option = dict_get(self.final_params, "part_option")

        # ora_lsn_port: Read from user input, fallback to final_params
        self.ora_lsn_port = oracle_parameters.get("oracle_listener_port")
        if self.ora_lsn_port is None:
            self.ora_lsn_port = dict_get(self.final_params, "lsn_port")

        # Disk sizes: Read from user input (NO FALLBACK)
        self.oracle_data_disk_size = oracle_parameters.get("oracle_data_disk_size")
        self.oracle_bck_disk_size = oracle_parameters.get("oracle_bck_disk_size")

        # Path construction logic
        self.ora_recovf_path = self.backup_dir + "/orabck_" + self.ora_db_name + "/RMan"
        self.ora_splunkdir_fwuser = self.ora_dataf_path + "/" + self.ora_db_name + "/FW/fwsplunk"
        self.ora_dir_fwuser = self.ora_dataf_path + "/" + self.ora_db_name + "/FW/fw"
        self.ora_logdir_fwuser = self.ora_dataf_path + "/" + self.ora_db_name + "/FW/fwlog"

        # Oracle starter pack (schema and tablespaces)
        # Direct assignments from user input
        self.ora_starter_pack = oracle_parameters.get("oracle_starter_pack")
        self.ora_user_name = oracle_parameters.get("oracle_user_name")
        self.ora_user_pwd = oracle_parameters.get("oracle_user_pwd")
        self.ora_data_tbs_name = oracle_parameters.get("oracle_data_tbs_name")
        self.ora_data_tbs_next = oracle_parameters.get("oracle_data_tbs_next")
        self.ora_data_tbs_size = oracle_parameters.get("oracle_data_tbs_size")
        self.ora_idx_tbs_name = oracle_parameters.get("oracle_idx_tbs_name")
        self.ora_idx_tbs_next = oracle_parameters.get("oracle_idx_tbs_next")
        self.ora_idx_tbs_size = oracle_parameters.get("oracle_idx_tbs_size")
        self.ora_lob_tbs_name = oracle_parameters.get("oracle_lob_tbs_name")
        self.ora_lob_tbs_next = oracle_parameters.get("oracle_lob_tbs_next")
        self.ora_lob_tbs_size = oracle_parameters.get("oracle_lob_tbs_size")

        # Starter pack validation and fallback logic (fallbacks updated)
        if self.ora_starter_pack == "Y":
            # Mandatory checks
            if (
                self.ora_user_name == NO_VALUE
                or self.ora_user_name is None
                or self.ora_user_pwd == NO_VALUE
                or self.ora_user_pwd is None
            ):
                raise ApiManagerError("starter pack mandatory parameters not set ")
            # Default name assignment
            if self.ora_data_tbs_name == NO_VALUE or self.ora_data_tbs_name is None:
                self.ora_data_tbs_name = f"{self.ora_user_name}_TBL"

            # Fallbacks updated
            if self.ora_data_tbs_next == NO_VALUE or self.ora_data_tbs_next is None:
                self.ora_data_tbs_next = dict_get(self.final_params, "data_tbs_next")
            if self.ora_data_tbs_size == NO_VALUE or self.ora_data_tbs_size is None:
                self.ora_data_tbs_size = dict_get(self.final_params, "data_tbs_size")

            # Index Tablespace (fallbacks updated)
            if self.ora_idx_tbs_name != NO_VALUE and self.ora_idx_tbs_name is not None:
                if self.ora_idx_tbs_next == NO_VALUE or self.ora_idx_tbs_next is None:
                    self.ora_idx_tbs_next = dict_get(self.final_params, "idx_tbs_next")
                if self.ora_idx_tbs_size == NO_VALUE or self.ora_idx_tbs_size is None:
                    self.ora_idx_tbs_size = dict_get(self.final_params, "idx_tbs_size")
            else:
                self.ora_idx_tbs_name = NO_VALUE
                self.ora_idx_tbs_next = NO_VALUE
                self.ora_idx_tbs_size = NO_VALUE

            # Lob Tablespace (fallbacks updated)
            if self.ora_lob_tbs_name != NO_VALUE and self.ora_lob_tbs_name is not None:
                if self.ora_lob_tbs_next == NO_VALUE or self.ora_lob_tbs_next is None:
                    self.ora_lob_tbs_next = dict_get(self.final_params, "lob_tbs_next")
                if self.ora_lob_tbs_size == NO_VALUE or self.ora_lob_tbs_size is None:
                    self.ora_lob_tbs_size = dict_get(self.final_params, "lob_tbs_size")
            else:
                self.ora_lob_tbs_name = NO_VALUE
                self.ora_lob_tbs_next = NO_VALUE
                self.ora_lob_tbs_size = NO_VALUE
        else:
             # Logic to set NO_VALUE if starter pack is not 'Y'
            self.ora_starter_pack = "N"
            self.ora_user_name = NO_VALUE
            self.ora_user_pwd = NO_VALUE
            self.ora_data_tbs_name = NO_VALUE
            self.ora_data_tbs_next = NO_VALUE
            self.ora_data_tbs_size = NO_VALUE
            self.ora_idx_tbs_name = NO_VALUE
            self.ora_idx_tbs_next = NO_VALUE
            self.ora_idx_tbs_size = NO_VALUE
            self.ora_lob_tbs_name = NO_VALUE
            self.ora_lob_tbs_next = NO_VALUE
            self.ora_lob_tbs_size = NO_VALUE

    def internal_run(self):
        self.license = dict_get(self.final_params, "engine.license")

        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        # Read service_users from the correct engine block
        service_users: Dict[str, Any] = dict_get(
            self.final_params, "engine.service_users"
        )
        self.monit_user = self.get_db_monit_user(service_users)
        self.outputs.append(self.set_output())

        self.admin_user = self.kvargs.pop("db_root_name", "sys")
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=False)

        self.ora_user_sys = self.admin_user
        self.ora_user_sys_pwd = random_password(length=20, strong=False)
        self.ora_user_system = self.db_superuser_name
        self.ora_user_system_pwd = random_password(length=20, strong=False)

        # check_params already set self.oracle_data_disk_size
        if self.oracle_data_disk_size is not None:
            self.data_disk_size = self.oracle_data_disk_size

        if self.oracle_bck_disk_size is not None:
            self.bck_disk_size = self.oracle_bck_disk_size

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
            else:
                self.logger.warning(
                    "Action method action_%s not found or not callable.", step_name
                )

    def _action_setup_oracle_volume(
            self,
            action_name_suffix: str,
            boot_index: int,
            data_dir: str,
            data_device: str,
            volume_group: str,
            logical_volume: str,
    ) -> dict:
        """
        Private helper to build a 'setup_volume' action dictionary.
        This is parameterized because Oracle needs to call it twice
        (for /oradata and /BCK_fisici).
        """
        # We use a generic key "setup_volume" to read customization info
        action_key = "setup_volume"
        customization = self.get_customization(action_key)
        if not customization:
            raise ApiManagerError(
                f"Customization '{action_key}' not found in final_params"
            )

        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        action_name = f"setup_volume_{action_name_suffix}"

        res = {
            "name": action_name,
            "desc": f"setup volume {boot_index} ({data_dir})",
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
                    "data_dir": data_dir,
                    "data_device": data_device,
                    "volume_group": volume_group,
                    "logical_volume": logical_volume,
                    "proxy_server": self.proxy,
                },
            },
        }
        return res

    def action_setup_volume_data(self) -> dict:
        """
        Wrapper action for setting up the /oradata volume.
        Calls the private _action_setup_oracle_volume helper.
        """
        volume_group = dict_get(
            self.final_params, "lvm.volume_group.data"
        )
        logical_volume = dict_get(
            self.final_params, "lvm.logical_volume.data"
        )
        ora_data_device = self.get_volume_device_path("c")

        return self._action_setup_oracle_volume(
            action_name_suffix="data",
            boot_index=2,
            data_dir=self.ora_dataf_path,
            data_device=ora_data_device,
            volume_group=volume_group,
            logical_volume=logical_volume,
        )

    def action_setup_volume_bck(self) -> dict:
        """
        Wrapper action for setting up the /BCK_fisici volume.
        Calls the private _action_setup_oracle_volume helper.
        """
        volume_group = dict_get(
            self.final_params, "lvm.volume_group.backup"
        )
        logical_volume = dict_get(
            self.final_params, "lvm.logical_volume.backup"
        )
        bck_data_device = self.get_volume_device_path("d")

        return self._action_setup_oracle_volume(
            action_name_suffix="bck",
            boot_index=3,
            data_dir=self.backup_dir,
            data_device=bck_data_device,
            volume_group=volume_group,
            logical_volume=logical_volume,
        )

    def action_install_oracle(self):
        action_name = "install_oracle"

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
            "desc": "install oracle",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}",
                "parent": parent,  # MODIFIED
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
                    # Comments restored
                    "p_oracle_user": self.ora_os_user,
                    "p_db_name": self.ora_db_name,  # O
                    "p_listener_port": self.ora_lsn_port,  # D=1522
                    "p_system_pwd": self.ora_user_system_pwd,  # generated
                    "p_sys_pwd": self.ora_user_sys_pwd,  # generated
                    "p_datafile_path": self.ora_dataf_path,  # D=/oradata
                    "p_controlfile_path": self.ora_dataf_path,  # D=/oradata
                    "p_flash_recov_path": self.ora_recovf_path,  # D=/BCK_fisici/orabck_$p_db_name/RMan
                    "p_redolog_path": self.ora_dataf_path,  # D=/oradata
                    "p_archivelogmode": self.ora_arch_mode,  # D=Y
                    "p_archivelog_path": self.ora_recovf_path,  # D=/BCK_fisici/orabck_$p_db_name/RMan
                    "p_dbcharset": self.ora_charset,  # O
                    "p_national_charset": self.ora_nat_cset,  # D=AL16UTF16
                    "p_partitioning": self.ora_part_option,  # D=Y
                    "p_eidp_pwd": self.ora_user_eidp_pwd,  # generated
                    "p_csimon_pwd": self.ora_user_csimon_pwd,  # generated
                    "p_perfstat_pwd": self.ora_user_perfstat_pwd,  # generated
                    "p_fwuser_pwd": self.ora_user_fw_pwd,  # generated
                    "p_fwuser_dir": self.ora_dir_fwuser,  # D=/oradata/$p_db_name/FW/fw
                    "p_fwuser_logdir": self.ora_logdir_fwuser,  # D=/oradata/$p_db_name/FW/fwlog
                    "p_fwuser_splunkdir": self.ora_splunkdir_fwuser,  # D=/oradata/$p_db_name/FW/fwsplunk
                    "p_pdbadmin_pwd": self.ora_user_pdbadmin_pwd,  # generated
                    "p_oracle_version": self.ora_version,  # O in (11g,12c,19c)
                    "p_adv_sec": "N",  # fisso
                    "p_starter_pack": self.ora_starter_pack,
                    "p_user_name": self.ora_user_name,
                    "p_user_pwd": self.ora_user_pwd,
                    "p_data_tbl": self.ora_data_tbs_name,
                    "p_size_data_tbl": self.ora_data_tbs_size,
                    "p_next_data_tbl": self.ora_data_tbs_next,
                    "p_idx_tbl": self.ora_idx_tbs_name,
                    "p_size_idx_tbl": self.ora_idx_tbs_size,
                    "p_next_idx_tbl": self.ora_idx_tbs_next,
                    "p_lob_tbl": self.ora_lob_tbs_name,
                    "p_size_lob_tbl": self.ora_lob_tbs_size,
                    "p_next_lob_tbl": self.ora_lob_tbs_next,
                },
            },
        }

        return res


class OracleImportHelper(SqlImportHelper):
    """
    Import.
    """
    default_engine = OracleBase

    def internal_run(self):
        self.license = dict_get(self.final_params, "engine.license")
        self.admin_user = self.kvargs.pop("db_root_name", "sys")
        self.outputs.append(self.set_output())
        self.actions.append(self.action_import_server())


class OracleUpdateHelper(SqlUpdateHelper):
    """
    Update.
    """
    default_engine = OracleBase

    def internal_run(self):
        pass


class OracleActionHelper(SqlActionHelper):
    """
    Actions.
    """
    default_engine = OracleBase

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)


DbaasBase.register_child("oracle", OracleBase)
SqlDeleteHelper.register_child("oracle", OracleDeleteHelper)
SqlCreateHelper.register_child("oracle", OracleCreateHelperNew)
SqlImportHelper.register_child("oracle", OracleImportHelper)
SqlUpdateHelper.register_child("oracle", OracleUpdateHelper)
SqlActionHelper.register_child("oracle", OracleActionHelper)