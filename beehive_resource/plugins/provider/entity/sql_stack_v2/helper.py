# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from __future__ import annotations
import collections.abc
import copy
from logging import getLogger
from typing import Any, Optional, Dict, List, TYPE_CHECKING, Type, Set, TypedDict

from beecell.types.type_dict import recursive_update
from beecell.simple import random_password, dict_get, id_gen

from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import prepare_or_run_task

from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
from beehive_resource.plugins.awx.entity.awx_project import AwxProject
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.image import ComputeImage

from beehive_resource.plugins.provider.entity.stack_v2 import (
    ComputeStackV2,
    ComputeStackAction,
)

if TYPE_CHECKING:
    from .sqlcomputestackv2 import SqlComputeStackV2
    from beehive_resource.controller import ResourceController
    from beehive_resource.container import Resource


def nvl( value:Any, ifnull : Any='None')->Any:
    """Null value inspered by oracle sql nvl 
    if value is None return ifnull else return value

    Args:
        value (Any): value to check
        ifnull (Any, optional): return value when value is None. Defaults to 'None'.

    Returns:
        Any: if value is None return ifnull else return value
    """
    if value is None:
        return ifnull
    return value

class VolumeGroup(TypedDict, total=False):
    data: str
    backup: str

class LogicalVolume(TypedDict, total=False):
    data: str
    backup: str

class LVM(TypedDict, total=False):
    volume_group: VolumeGroup
    logical_volume: LogicalVolume

class MountPoint(TypedDict, total=False):
    data: str
    backup: str

class ServiceUserDetail(TypedDict, total=False):
    name: str
    pwd: str
    host: str
    privs: str

ServiceUsers = Dict[str, List[ServiceUserDetail]]

class Customization(TypedDict, total=False):
    playbook: str
    orchestrator_tag: Optional[str]
    customization: str

Customizations = Dict[str, Customization]

class Engine(TypedDict, total=False):
    port: int
    customization: str
    license: str
    charset: str
    encoding: Optional[str]
    lc_collate: Optional[str]
    lc_ctype: Optional[str]
    geo_extension: Optional[bool]
    service_users: ServiceUsers
    steps_order: Dict[str, List[str]]

class EngineParams(TypedDict, total=False):
    hypervisor: str
    image: str
    volume_flavor: str
    host_group: str
    lvm: LVM
    mount_point: MountPoint
    engine: Engine
    customizations: Customizations
    os_dbuser: str
    oversion: str
    db_name: str
    arch_mode: str
    part_option: str
    nat_charset: str
    lsn_port: str
    data_tbs_next: str
    data_tbs_size: str
    idx_tbs_next: str
    idx_tbs_size: str
    lob_tbs_next: str
    lob_tbs_size: str


class DbaasBase:
    child_mapping: Dict[str, Type[SqlHelper]] = {}
    engine_params:EngineParams = {}

    @classmethod
    def register_child(cls, engine: str, spec: Type[SqlHelper]) -> None:
        cls.child_mapping[engine] = spec

    @classmethod
    def get_helper_by_engine(cls, engine: str) -> Type[SqlHelper]:
        return cls.child_mapping.get(engine)

    @classmethod
    def get_engines(cls) -> Set[str]:
        return cls.child_mapping.keys()


class SqlHelper:
    child_mapping: Dict[str, Type[SqlHelper]] = {}
    default_engine: DbaasBase

    def __init__(self, *args, **kvargs):
        self.logger = getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

        self.args = args
        self.kvargs = kvargs

        self.engine_params = self.default_engine.engine_params
        self.stack_v2_params = {}
        self.inputs = []
        self.outputs = []
        self.actions = []
        self.enabled_monitoring = False

    @classmethod
    def register_child(cls, engine: str, spec: Type[SqlHelper]) -> None:
        print(
            "|||||||||||||||||||||||||||||||||||||||||||||||||||",
            cls.__name__,
            engine,
            spec.__name__,
            sep=", ",
            end="\n",
        )
        cls.child_mapping[engine] = spec

    @classmethod
    def get_helper_by_engine(cls, engine: str) -> Type[SqlHelper]:
        print(
            "|||||||||||||||||||||||||||||||||||||||||||||||||||",
            cls.__name__,
            "mapping",
            cls.child_mapping,
            "search",
            engine,
            sep=", ",
            end="\n",
        )
        return cls.child_mapping.get(engine)

    @property
    def engines(self) -> Set[str]:
        return self.default_engine.get_engines()

    @staticmethod
    def get_engine_major_version(version_string: str, n: int) -> str:
        """
        Extracts the first 'n' dot-separated components from a string.

        Args:
            version_string: The input string (e.g., "15.5.7.6.8").
            n: The number of components to keep.

        Returns:
            A substring containing the first 'n' components joined by dots.
            Returns an empty string if n is 0 or input is invalid.
            Returns the original string if n is >= the number of components.
        """
        parts = version_string.split('.')
        return '.'.join(parts[:n])

    @staticmethod
    def get_db_monit_user(users):
        """Get credentials of db user account used to collect database metrics

        :param users: dictionary of non-administrative database user accounts
        :return: a dict like this: {'name' ..., 'pwd': ...}
        """
        try:
            monit_user = users.get("zabbix")[0]
            username = monit_user.get("name")
            password = monit_user.get("pwd")
            if not username or not password:
                return None
            return {"name": username, "pwd": password}
        except:
            return None

    def _build_final_params(self):
        """
        Build the final configuration dictionary 'self.final_params'.

        This method merges the three configuration sources following the
        established hierarchy of precedence.
        """
        # --- Phase 1: Create the base configuration (Defaults + Definition YML) ---

        # Start with a deepcopy of the restructured defaults
        defaults = copy.deepcopy(self.default_engine.engine_params)

        # Get overrides from the definition YML (within sql_stack_data)
        definition_overrides = self.kvargs.get("engine_configs", {})

        # Merge them to create the base configuration
        base_params = recursive_update(defaults, definition_overrides)
        self.final_params = base_params

        self.logger.debug("Final params: %s", self.final_params)

    def get_customization(self, action_name):
        customizations = self.final_params.get("customizations")
        return customizations.get(action_name)

    def check_params(self) -> None:
        pass

    def internal_run(self) -> None:
        pass

    def run(self) -> Dict:
        raise NotImplementedError("called run on ", self.__class__.__name__)


#
# Delete
#
class SqlDeleteHelper(SqlHelper):
    child_mapping: Dict[str, Type[SqlDeleteHelper]] = {}

    def __init__(self, stack: SqlComputeStackV2, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self.stack = stack
        self.engine: str = ""
        self.engine_major_version: str = ""
        self.compute_zone: Resource = None
        self.compute_instance_info: str = ""
        self.compute_instance: ComputeInstance = None
        self.os_ver: str = ""
        self.fqdn: str = ""
        self.fulldelete: bool = True
        # As the final step, call the builder method
        self._build_final_params()

        # self.check_params()

    def get_compute_instance(self):
        """
        Get compute instance linked to stack
        """

        resources = self.stack.controller.get_directed_linked_resources_internal(
            resources=[self.stack.oid],
            link_type="resource%",
            objdef=ComputeInstance.objdef,
        )
        resources = resources.get(self.stack.oid)
        if resources is not None and len(resources) > 0:
            self.compute_instance: ComputeInstance = resources[0]
        else:
            self.compute_instance: ComputeInstance = None

    def internal_run(self):
        if self.fulldelete:
            self.actions.append(self.action_setup_nfsbcklogici_delete())

    def run(self):
        """
        Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.helperactions:

        :param kvargs.preserve: if True preserve resource when stack is removed
        :return: kvargs
        :raise ApiManagerError:
        """
        self.check_params()
        self.internal_run()
        self.stack_v2_params["inputs"] = self.inputs
        self.stack_v2_params["outputs"] = self.outputs
        self.stack_v2_params["actions"] = self.actions
        # self.kvargs["helperactions"] = self.actions

        preserve = self.kvargs.get("preserve", False)

        ## actions (ComputeStackAction) done during stack life
        done_actions = self.stack.get_actions()
        done_actions.reverse()
        ## action to run before deletting
        actions: List[dict] = []
        for action in self.actions:
            if action is None:
                continue
            # set stack container as stack resource container
            action["container"] = self.stack.container.oid
            # set stack compute_zone as stack resource compute_zone
            action["compute_zone"] = self.stack.parent_id

            action_name = action.get("name")
            action_resource = action.get("resource")

            # check action resource type
            res_type = action_resource.get("type", None)
            if res_type is not None:
                ComputeStackV2.get_resource_class(res_type)

            # check action resource uuid exists
            res_id = action_resource.get("oid", None)
            if res_id is not None:
                self.stack.container.get_simple_resource(res_id)

            if res_type is None and res_id is None:
                raise ApiManagerError("at least one of resource type or resource id must be set")

            ### ATTENTION we do not support $$ parameters.'
            params = action.get("params", {})
            action["params"] = params
            actions.append(
                {
                    "name": action_name,
                    "desc": action.get("desc", action_name),
                    "orchestrator_tag": params.get("orchestrator_tag"),
                    "active": False,
                    "attribute": {
                        "resource": action_resource,
                        "params": params,
                    },
                }
            )

        self.kvargs["actions"] = actions

        # create task workflow
        steps = []

        steps.append(ComputeStackV2.task_path + "expunge_resource_pre_step")
        if len(actions) > 0:
            steps.append(ComputeStackV2.task_path + "create_stack_actions_step")

        # steps to run actions
        for action in actions:
            step = {
                "step": ComputeStackV2.task_path + "run_stack_action_step",
                "args": [f"{self.stack.name}-{action.get('name')}"],
            }
            steps.append(step)

        # then standard steps sequence for delete the stack
        # scan all the ComputeStackAction  executed for then stack and  prepare the delet task
        # steps to delete all action that has been run
        for doneaction in done_actions:
            if not preserve:
                steps.append(
                    {
                        "step": ComputeStackV2.task_path + "remove_stack_resource_step",
                        "args": [doneaction.oid],
                    }
                )
            steps.append(
                {
                    "step": ComputeStackV2.task_path + "remove_stack_action_step",
                    "args": [doneaction.oid],
                }
            )
        # steps to delete action created while deleting
        for todoaction in actions:
            if not preserve:
                steps.append(
                    {
                        "step": ComputeStackV2.task_path + "remove_stack_resource_step_by_name",
                        "args": [f"{self.stack.name}-{todoaction.get('name')}"],
                    }
                )
            steps.append(
                {
                    "step": ComputeStackV2.task_path + "remove_stack_action_step_by_name",
                    "args": [f"{self.stack.name}-{todoaction.get('name')}"],
                }
            )
        # last step to finalize
        steps.append(ComputeStackV2.task_path + "expunge_resource_post_step")
        self.kvargs["steps"] = steps
        self.kvargs["child_num"] = 0

        return self.kvargs

    def check_params(self):
        """
        Check parameters are set and does some initialization

        Raises:
            ApiManagerError: _description_
        """
        if "engine" in self.kvargs:
            self.engine = self.kvargs.get("engine")
        else:
            self.engine = self.stack.get_attribs(key="engine")

        # get compute zone
        if "compute_zone" in self.kvargs:
            compute_zone_id = self.kvargs.get("compute_zone")
        else:
            compute_zone_id = self.stack.parent_id
        self.compute_zone = self.stack.container.get_simple_resource(compute_zone_id)
        self.get_compute_instance()
        engine_version = self.stack.get_attribs("version")
        self.engine_major_version = SqlHelper.get_engine_major_version(engine_version, 2)

        # get image
        if self.compute_instance is None:
            return
        resources = self.compute_instance.controller.get_directed_linked_resources_internal(
            resources=[self.compute_instance.oid],
            link_type="image",
            objdef=ComputeImage.objdef,
        )
        image = resources.get(self.compute_instance.oid)[0]
        self.os_ver = image.get_os_version()
        self.compute_instance_info = self.compute_instance.info()
        self.fqdn = dict_get(self.compute_instance_info, "attributes.fqdn")

        self.logger.debug("+++++ check_params - get_ssh_node - fqdn: %s", self.fqdn)
        if not self.compute_instance.is_managed():
            self.fulldelete = False

    def action_setup_nfsbcklogici_delete(self):
        action_name = "setup_nfsbcklogici_delete"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        if self.compute_instance is None:
            return

        res = {
            "name": action_name,
            "desc": "setup nfsbcklogici delete",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.stack.name}_{action_name}",
                "parent": parent,
                "orchestrator_tag": orchestrator_tag,
                "compute_zone": self.compute_zone.oid,
                "instances": [{"id": self.compute_instance.oid, "extra_vars": {}}],
                "playbook": playbook,
                "extra_vars": {
                    "p_dbms_engine": self.engine + ":" + self.os_ver,
                    "p_dbms_version": self.engine_major_version,
                    "p_client_fqdn": self.fqdn,
                },
            },
        }
        return res


#
# Create
#
class SqlCreateHelper(SqlHelper):
    child_mapping: Dict[str, Type[SqlCreateHelper]] = {}

    def __init__(self, controller: ResourceController, container, *args, **kvargs):
        """
        Cleaned constructor. Initializes only essential context objects and state.
        Configuration is now handled by the _build_final_params method.
        """
        # Call to the parent constructor
        super().__init__(*args, **kvargs)

        # === Essential context objects ===
        self.controller = controller
        self.container = container

        # === State accumulators for the workflow ===
        self.inputs = []
        self.outputs = []
        self.actions = []

        # === Initialize all attributes from kvargs to fix 'no-member' errors ===
        self.engine_configs: dict = self.kvargs.get("engine_configs", {})
        self.name: str = self.kvargs.get("name")
        self.desc: str = self.kvargs.get("desc")
        self.engine: str = self.kvargs.get("engine")
        self.version: str = self.kvargs.get("version")
        self.charset: str = self.kvargs.get("charset")
        self.timezone: str = self.kvargs.get("timezone")

        self.hypervisor: str = self.kvargs.get("hypervisor")
        self.image: str = self.kvargs.get("image")
        self.flavor: str = self.kvargs.get("flavor")
        self.volume_flavor: str = self.kvargs.get("volume_flavor")
        self.host_group: str = self.kvargs.get("host_group")
        self.subnet: str = self.kvargs.get("subnet")
        self.security_group: str = self.kvargs.get("security_group")
        self.key_name: str = self.kvargs.get("key_name")
        self.hostname: str = self.kvargs.get("hostname", self.name)

        self.root_disk_size: int = self.kvargs.get("root_disk_size")
        self.data_disk_size: int = self.kvargs.get("data_disk_size")
        self.bck_disk_size: int = self.kvargs.get("bck_disk_size")
        self.data_dir: str = self.kvargs.get("data_dir")
        self.backup_dir: str = self.kvargs.get("backup_dir")
        self.lvm_vg_data: str = self.kvargs.get("lvm_vg_data")
        self.lvm_vg_backup: str = self.kvargs.get("lvm_vg_backup")
        self.lvm_lv_data: str = self.kvargs.get("lvm_lv_data")
        self.lvm_lv_backup: str = self.kvargs.get("lvm_lv_backup")

        self.replica: bool = self.kvargs.get("replica", False)
        self.remove_replica: bool = self.kvargs.get("remove_replica", False)
        self.replica_arch_type: str = self.kvargs.get("replica_arch_type")
        self.replica_role: str = self.kvargs.get("replica_role")
        self.replica_sync_type: str = self.kvargs.get("replica_sync_type")
        self.replica_master: str = self.kvargs.get("replica_master")

        self.db_monitor: bool = self.kvargs.get("db_monitor", True)

        self.filter: dict = self.kvargs.get("filter", {})
        self.multi_avz: bool = self.kvargs.get("multi_avz")
        self.orchestrator_tag: str = self.kvargs.get("orchestrator_tag")
        self.resolve: bool = self.kvargs.get("resolve")

        # === Placeholders for attributes calculated at runtime ===
        self.os_ver: str = None
        self.custom_attributes: dict = {}
        self.replica_ip_master: str = None
        self.admin_pwd: str = self.kvargs.get("db_root_password")
        self.monit_user: dict = None
        self.compute_zone: Resource = None
        self.site: Resource = None
        self.vpc: Resource = None
        self.proxy: str = None
        self.set_proxy: bool = False
        self.ip_repository: str = None
        self.server_ram_mb: int = 0
        self.url_repository: str = None
        self.engine_major_version: str = None

    def check_params(self):
        """
        Check parameters are set and does some initialization

        Raises:
            ApiManagerError: _description_
        """
        # get compute zone
        if "compute_zone" in self.kvargs:
            compute_zone_id = self.kvargs.get("compute_zone")
        else:
            compute_zone_id = self.kvargs.get("parent")
        self.compute_zone = self.container.get_simple_resource(compute_zone_id)
        self.compute_zone.set_container(self.container)
        self.kvargs["parent"] = self.compute_zone.oid

        self.site = self.controller.get_resource(self.kvargs.get("availability_zone"))

        self.filter = {"container_id": self.container.oid, "run_customize": False}

        # get flavor
        self.flavor = self.controller.get_resource(self.kvargs.pop("flavor"), entity_class=ComputeFlavor, **self.filter)
        self.flavor.check_active()

        # get volume flavor
        self.volume_flavor = self.controller.get_resource(
            self.kvargs.pop("volume_flavor"),
            entity_class=ComputeVolumeFlavor,
            **self.filter,
        )
        self.volume_flavor.check_active()


        self.vpc = self.controller.get_resource(self.kvargs.pop("vpc"), **self.filter)
        self.vpc.check_active()

        # get security group
        self.security_group = self.controller.get_resource(self.kvargs.pop("security_group"), **self.filter)
        self.security_group.check_active()

        all_proxy = self.vpc.get_proxies(self.site.oid)
        self.proxy, self.set_proxy = all_proxy.get("http", (None, False))
        self.ip_repository = self.site.get_attribs().get("repo")
        if self.flavor:
            self.server_ram_mb = int(self.flavor.get_configs().get("memory", 0))

        # As the final step, call the builder method
        self._build_final_params()

    def get_image(self):
        """
        Get image resource

        :param filter: custom filter
        :return: Image instance
        """
        image = self.kvargs.get("image")
        if image is None:
            image = dict_get(self.final_params, "image")
        return self.controller.get_resource(image, **self.filter)

    def build_repo_url(self, port=80):
        url = "http://" + "/".join((self.ip_repository, "repos", self.os_ver, self.engine, self.version))
        if port != 80:
            url += f":{port}"
        return url

    def get_volume_device_path(self, device_letter) -> str:
        """
        Get device path for a specific hypervisor

        :param device_letter: device letter like a, b, c
        Returns:
            str: device path like /dev/sda for vpshere or /dev/vda for openstack
        """
        if self.hypervisor != "openstack":
            return f"/dev/sd{device_letter}"
        return f"/dev/vd{device_letter}"

    def check_replica_params(self):
        """check parameters for replcas are set

        Raises:
            ApiManagerError: _description_
        """
        # replica consistency check
        if self.replica and self.replica_master is None:
            raise ApiManagerError("Replica master cannot be null when replication is enabled")

        if self.replica:
            # get master stack object
            master_stack = self.controller.get_resource(self.replica_master, entity_class=ComputeStackV2)
            # get master server ip address
            resources, _ = master_stack.get_linked_resources(
                link_type_filter="resource.%",
                objdef=ComputeInstance.objdef,
                run_customize=False,
            )
            self.compute_instance = resources[0]
            vpc_links, _ = self.compute_instance.get_links(type="vpc")
            self.replica_ip_master = vpc_links[0].attribs.get("fixed_ip", {}).get("ip", "")

            # users
            master_stack_attribs = master_stack.get_attribs()
            users = master_stack_attribs.get("users")
            # - admin user
            admin_pwd = users.get("administrator").get("password")
            self.admin_pwd = self.controller.decrypt_data(admin_pwd).decode("utf-8")

            # - super user
            self.db_superuser_name = users.get("superuser").get("username")
            db_superuser_pwd = users.get("superuser").get("password")
            self.db_superuser_pwd = self.controller.decrypt_data(db_superuser_pwd).decode("utf-8")

            # - app user
            self.db_appuser_name = users.get("appuser").get("username")
            db_appuser_pwd = users.get("appuser").get("password")
            self.db_appuser_pwd = self.controller.decrypt_data(db_appuser_pwd).decode("utf-8")

            # - replica user
            self.replica_user = users.get("replica").get("username")
            replica_pwd = users.get("replica").get("password")
            self.replica_pwd = self.controller.decrypt_data(replica_pwd).decode("utf-8")
        else:
            # - admin user
            self.admin_user = None
            self.admin_pwd = self.kvargs.pop("db_root_password", None)

            # - super user
            self.db_superuser_name = self.kvargs.pop("db_superuser_name", "system")
            self.db_superuser_pwd = self.kvargs.pop("db_superuser_password", random_password(length=10, strong=False))

            # - app user
            self.db_appuser_name = self.kvargs.pop("db_appuser_name", "test")
            self.db_appuser_pwd = self.kvargs.pop("db_appuser_password", random_password(length=10, strong=False))

            # - replica user
            self.replica_user = None
            self.replica_pwd = None

    def internal_run(self):
        """
        This method is overridden by engine specialized class method
        """
        self.logger.error("internal_run non implemented for %s", self.__class__)

    def run(self):
        self.check_params()
        self.check_replica_params()
        self.internal_run()

        self.stack_v2_params["inputs"] = self.inputs
        self.stack_v2_params["outputs"] = self.outputs
        self.stack_v2_params["actions"] = self.actions
        self.stack_v2_params["enabled_monitoring"] = self.enabled_monitoring

        self.kvargs.update(self.stack_v2_params)
        self.kvargs["attribute"] = {
            "stack_type": "sql_stack",
            "engine": self.engine,
            "engine_configs": self.engine_configs,
            "version": self.version,
            "allocated_storage": self.data_disk_size,
            "volume_flavor": self.volume_flavor.name,
            "charset": self.charset,
            "timezone": self.timezone,
            "replica": self.replica,
            "users": {
                "administrator": {
                    "username": self.admin_user,
                    "password": self.controller.encrypt_data(self.admin_pwd),
                },
                "superuser": {
                    "username": self.db_superuser_name,
                    "password": self.controller.encrypt_data(self.db_superuser_pwd),
                },
                "appuser": {
                    "username": self.db_appuser_name,
                    "password": self.controller.encrypt_data(self.db_appuser_pwd),
                },
            },
            "lvm": {
                "volume_group": {
                    "data": self.lvm_vg_data,
                    "backup": self.lvm_vg_backup,
                },
                "logical_volume": {
                    "data": self.lvm_lv_data,
                    "backup": self.lvm_lv_backup,
                },
            },
            "mount_point": {
                "data": self.data_dir,
                # 'backup': self.backup_dir
            },
        }

        # update attributes with custom_attributes
        self.kvargs["attribute"].update(self.custom_attributes)

        if self.replica:
            self.kvargs["attribute"].update(
                {
                    "replica_role": self.replica_role,
                    "replica_arch_type": self.replica_arch_type,
                    "replica_sync_type": self.replica_sync_type,
                    "replica_master": self.replica_master,
                }
            )
            self.kvargs["attribute"]["users"].update(
                {
                    "replica": {
                        "username": self.replica_user,
                        "password": self.controller.encrypt_data(self.replica_pwd),
                    }
                }
            )
        return ComputeStackV2.pre_create(self.controller, self.container, *self.args, **self.kvargs)

    def set_output(self) -> dict:
        """
        Output description

        Returns:
            dict: task output description
        """
        return {
            "name": "ResourceIP",
            "desc": "Master Server IP address",
            "value": f"$$action_resource.{self.name}-create_server1::vpcs.0.fixed_ip.ip$$",
        }

    def action_create_server(self) -> dict:
        """
        Create action definition in order to create the server

        Returns:
            dict: Dictionary containing the step action definition
        """
        res = {
            "name": "create_server1",
            "desc": "create server",
            "resource": {"type": "ComputeInstance", "operation": "create"},
            "params": {
                "name": f"{self.name}-server01",
                "desc": f"{self.desc} Server 01",
                "parent": self.compute_zone.oid,
                "availability_zone": self.site.oid,
                "multi_avz": self.multi_avz,
                "host_group": self.host_group,
                "orchestrator_tag": self.orchestrator_tag,
                "networks": [
                    {
                        "subnet": self.subnet,
                        "vpc": self.vpc.oid,
                        "fixed_ip": {"hostname": self.hostname},
                    }
                ],
                "flavor": self.flavor.oid,
                "security_groups": [self.security_group.oid],
                "admin_pass": random_password(length=10, strong=True),
                "key_name": self.key_name,
                "type": self.hypervisor,
                "user_data": None,
                "resolve": True,
                "manage": True,
                "block_device_mapping": [
                    {
                        "boot_index": 0,
                        "volume_size": self.root_disk_size,
                        "flavor": self.volume_flavor.oid,
                        "uuid": self.image.oid,
                        "source_type": "image",
                    },
                    {
                        "boot_index": 1,
                        "volume_size": self.data_disk_size,
                        "flavor": self.volume_flavor.oid,
                    },
                ],
            },
        }

        return res


    def action_wait_ssh_is_up(self) -> dict:
        """
        Action for wait server is able to receive ssh connection

        Returns:
            dict : action step definition
        """
        is_private = self.compute_zone.get_bastion_host() is not None
        action_name = "wait_ssh_is_up"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        res = {
            "name": action_name,
            "desc": "wait ssh is up",
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
                "extra_vars": {"is_private": is_private},
            },
        }
        return res

    def action_set_yum_proxy(self) -> dict:
        """
        Describe action to configure yum proxy

        Returns:
            dict: step action definition
        """
        action_name = "set_yum_proxy"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        res = {
            "name": action_name,
            "desc": "set yum proxy",
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
                "extra_vars": {"set_proxy": self.set_proxy, "proxy_server": self.proxy},
            },
        }
        return res

    def action_set_dnf_proxy(self) -> dict:
        """
        Describe action to configure dnf proxy

        Returns:
            dict: step action definition
        """
        action_name = "set_dnf_proxy"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        res = {
            "name": action_name,
            "desc": "set dnf proxy",
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
                "extra_vars": {"set_proxy": self.set_proxy, "proxy_server": self.proxy},
            },
        }
        return res

    def action_set_etc_hosts(self) -> dict:
        """
        Describe action to configure etc/hosts

        Returns:
            dict: step action definition
        """
        action_name = "set_etc_hosts"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        res = {
            "name": action_name,
            "desc": "set etc/hosts",
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
                    "hostname": f"$$action_resource.{self.name}-create_server1::vpcs.0.fixed_ip.hostname$$",
                    "ip_addr": f"$$action_resource.{self.name}-create_server1::vpcs.0.fixed_ip.ip$$",
                },
            },
        }
        return res

    def action_setup_mailx(self) -> dict:
        """describe action to setup and configure mailx server

        Returns:
            dict: step action definition
        """
        action_name = "setup_mailx"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        res = {
            "name": action_name,
            "desc": "setup mailx",
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
                    "p_client_fqdn": f"$$action_resource.{self.name}-create_server1::vpcs.0.fixed_ip.hostname$$",
                },
            },
        }
        return res

    def action_setup_volume(
        self,
    ) -> dict:
        """
        Describe action to setup volume

        Args for action taken by final_params:
            boot_index (int, optional): _description_. Defaults to 1.
            data_dir (str, optional): _description_. Defaults to "/data".
            data_device (str, optional): _description_. Defaults to "/dev/vdb".
            volume_group (str, optional): _description_. Defaults to "vg_data".
            logical_volume (str, optional): _description_. Defaults to "lv_fsdata".

        Returns:
            dict: step action
        """
        action_name = "setup_volume"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        final_params = self.final_params
        data_device = self.get_volume_device_path("b")
        data_dir = final_params.get("mount_point").get("data")
        volume_group = final_params.get("lvm").get("volume_group").get("data")
        logical_volume = final_params.get("lvm").get("logical_volume").get("data")
        boot_index = 1

        res = {
            "name": f"setup_volume_{boot_index}",
            "desc": f"setup volume {boot_index}",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}-{action_name}_{boot_index}",
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

    def action_setup_nfsbcklogici_add(self):
        action_name = "setup_nfsbcklogici_add"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        p_client_fqdn = f"$$action_resource.{self.name}-create_server1::vpcs.0.fixed_ip.hostname$$"
        p_client_ip = f"$$action_resource.{self.name}-create_server1::vpcs.0.fixed_ip.ip$$"
        instances = [{"id": f"$$action_resource.{self.name}-create_server1::id$$", "extra_vars": {}}]

        engine_major_version = SqlHelper.get_engine_major_version(self.version, 2)
        res = {
            "name": action_name,
            "desc": "setup nfsbcklogici add",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}_{action_name}",
                "parent": parent,
                "orchestrator_tag": orchestrator_tag,
                "compute_zone": self.compute_zone.oid,
                "instances": instances,
                "playbook": playbook,
                "extra_vars": {
                    "p_dbms_engine": self.engine + ":" + self.os_ver,
                    "p_dbms_version": engine_major_version,
                    "p_client_fqdn": p_client_fqdn,
                    "p_client_ip": p_client_ip,
                },
            },
        }
        return res

    def action_enable_monitoring(self) -> dict:
        """
        Describe action to enable monitoring

        Returns:
            dict: step action definition
        """
        action_name = "enable_monitoring"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")

        orchestrators = self.site.get_orchestrators_by_tag("tenant", select_types=["zabbix"])
        orchestrator_idx = list(orchestrators.keys())[0]
        orchestrator = self.controller.get_container(orchestrator_idx)

        engine = self.final_params.get("engine")
        service_users = engine.get("service_users")
        monit_user = self.get_db_monit_user(service_users)
        self.enabled_monitoring = True

        all_proxy = self.vpc.get_proxies(self.site.oid)
        zbx_proxy = all_proxy.get("zabbix")
        zbx_proxy_ip = zbx_proxy[0]
        zabbix_proxy_name = zbx_proxy[1]

        conn_params = orchestrator.conn_params["api"]
        zbx_srv_uri = conn_params.get("uri")
        zbx_srv_usr = conn_params.get("user")
        pwd = conn_params.get("pwd")
        zbx_srv_pwd = orchestrator.decrypt_data(pwd).decode("utf-8")
        zbx_srv_ip = orchestrator.get_ip_address(zbx_srv_uri)

        zabbix_host_groups = [self.compute_zone.desc]
        # for zabbix on Windows vm
        zabbix_host_group = None
        if len(zabbix_host_groups) > 0:
            zabbix_host_group = zabbix_host_groups[0]

        self.logger.debug("+++++ SqlCreateHelper - action_enable_monitoring")
        res = {
            "name": action_name,
            "desc": "enable monitoring",
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
                    "p_ip_repository": self.ip_repository,
                    "p_proxy_server": self.proxy,
                    "p_no_proxy": "localhost,10.0.0.0/8",
                    "p_zabbix_proxy_ip": zbx_proxy_ip,
                    "p_zabbix_proxy_name": zabbix_proxy_name,
                    "p_zabbix_server_ip": zbx_srv_ip,
                    "p_zabbix_server_uri": zbx_srv_uri,
                    "p_zabbix_server_username": zbx_srv_usr,
                    "p_zabbix_server_password": zbx_srv_pwd,
                    "p_custom_host_groups": zabbix_host_groups,
                    "p_custom_host_group": zabbix_host_group,
                    "p_custom_templates": [],
                    "p_target_host": f"$$action_resource.{self.name}-create_server1::attributes.fqdn$$",
                    "p_db_monitor_flag": self.db_monitor,
                    "p_db_engine": self.engine + ":" + self.os_ver,
                    "p_db_monit_username": monit_user.get("name"),
                    "p_db_monit_password": monit_user.get("pwd"),
                },
            },
        }
        return res

    def action_enable_log_forwarding(self) -> dict:
        """
        Describe action to enable log forwarding

        Returns:
            dict: step action definition
        """
        action_name = "enable_log_forwarding"
        customization = self.get_customization(action_name)
        parent = customization.get("customization")
        playbook = customization.get("playbook")
        orchestrator_tag = customization.get("orchestrator_tag")
        res = {
            "name": action_name,
            "desc": "enable log forwarding",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": f"{self.name}_{action_name}",
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
                    "p_ip_repository": self.ip_repository,
                    "p_proxy_server": self.proxy,
                },
            },
        }
        return res


#
# Import
#
class SqlImportHelper(SqlHelper):
    child_mapping: Dict[str, Type[SqlImportHelper]] = {}

    def __init__(self, controller, container, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self._build_final_params()
        self.controller = controller
        self.container = container

        physical_id = self.kvargs.get("physical_id")
        params = self.kvargs.pop("configs", {})

        # check server type from ext_id
        self.compute_instance = controller.get_resource(physical_id)
        if not isinstance(self.compute_instance, ComputeInstance):
            raise ApiManagerError("SqlComputeStack require ComputeInstance as physical resource")

        self.compute_instance_info = self.compute_instance.info()
        self.compute_instance_avz_num = len(self.compute_instance.get_dedploy_availability_zones())

        self.name = self.kvargs.get("name")
        self.desc = self.kvargs.get("desc")

        self.multi_avz = self.compute_instance_avz_num > 0
        self.host_group = dict_get(self.compute_instance_info, "attributes.host_group")
        self.orchestrator_tag = dict_get(self.compute_instance_info, "attributes.orchestrator_tag")
        self.hostname = dict_get(self.compute_instance_info, "attributes.fqdn")
        self.hypervisor = dict_get(self.compute_instance_info, "hypervisor")
        self.charset = params.get("charset", "latin1")
        self.timezone = params.get("timezone", "Europe/Rome")
        self.engine = params.get("engine")
        self.version = params.get("version")

        # get data size
        block_device_mapping = self.compute_instance_info.get("block_device_mapping")
        self.data_disk_size = sum(b["volume_size"] for b in block_device_mapping[1:])

        # get volume flavor
        main_volume = self.controller.get_resource(block_device_mapping[0]["id"])
        # self.volume_flavor_name = main_volume.get_flavor().get('name')
        self.volume_flavor_name = main_volume.get_flavor().name

        # super user
        self.admin_user: str = None
        self.admin_pwd = dict_get(params, "pwd.admin")
        self.db_superuser_name = dict_get(params, "db_superuser_name", default="system")
        self.db_superuser_pwd = dict_get(params, "pwd.db_superuser", default="")
        self.db_appuser_name = dict_get(params, "db_appuser_name", default="test")
        self.db_appuser_pwd = dict_get(params, "pwd.db_appuser", default="")

        self.custom_attributes = {}

        self.image = None

        self.replica = False

    def internal_run(self):
        pass

    def check_params(self):
        pass

    def run(self):
        self.check_params()
        self.internal_run()

        self.stack_v2_params["inputs"] = self.inputs
        self.stack_v2_params["outputs"] = self.outputs
        self.stack_v2_params["actions"] = self.actions
        self.kvargs.update(self.stack_v2_params)
        self.kvargs["attribute"] = {
            "stack_type": "sql_stack",
            "engine": self.engine,
            "version": self.version,
            "allocated_storage": self.data_disk_size,
            "volume_flavor": self.volume_flavor_name,
            "charset": self.charset,
            "timezone": self.timezone,
            "replica": self.replica,
            "postgres:database": "postgres",
            "has_quotas": True,
            "users": {
                "administrator": {
                    "username": self.admin_user,
                    "password": self.controller.encrypt_data(self.admin_pwd),
                },
                "superuser": {
                    "username": self.db_superuser_name,
                    "password": self.controller.encrypt_data(self.db_superuser_pwd),
                },
                "appuser": {
                    "username": self.db_appuser_name,
                    "password": self.controller.encrypt_data(self.db_appuser_pwd),
                },
            },
        }

        # update attributes with custom_attributes
        self.kvargs["attribute"].update(self.custom_attributes)

        return ComputeStackV2.pre_import(self.controller, self.container, *self.args, **self.kvargs)

    def set_output(self):
        return {
            "name": "ResourceIP",
            "desc": "Master Server IP address",
            "value": f"$$action_resource.{self.name}-import_server1::vpcs.0.fixed_ip.ip$$",
        }

    def action_import_server(self):
        return {
            "name": "import_server1",
            "desc": "import server",
            "resource": {"type": "ComputeInstance", "operation": "import"},
            "params": {
                "uuid": self.compute_instance.uuid,
            },
        }


#
# Update
#
class SqlUpdateHelper(SqlHelper):
    child_mapping: Dict[str, Type[SqlUpdateHelper]] = {}

    def __init__(self, stack, *args, **kvargs):
        super().__init__(self, *args, **kvargs)
        self.stack = stack

    def check_params(self):
        self._build_final_params()
        # get compute zone
        self.compute_zone = self.stack.get_parent()
        self.kvargs["parent"] = self.compute_zone.oid

        # get engine
        self.engine = self.stack.get_attribs(key="engine")

        # get compute customization
        customization = self.kvargs.get("customization")
        if customization is None:
            customization = dict_get(self.final_params, "engine.customization")
        self.compute_customization = self.stack.container.get_simple_resource(
            customization, entity_class=ComputeCustomization
        )

        # get playbook
        self.playbook = dict_get(self.final_params, "customizations.config_replica.playbook")

        # users
        # - admin user
        self.admin_user = self.stack.get_attribs("users").get("administrator").get("username")
        admin_pwd = self.stack.get_attribs("users").get("administrator").get("password")
        self.admin_pwd = self.stack.controller.decrypt_data(admin_pwd).decode("utf-8")

    def check_replica_params(self):
        self.remove_replica = self.kvargs.get("remove_replica", False)
        if self.remove_replica:
            # get replica params from stack object attributes
            stack_attribs = self.stack.get_attribs()
            self.replica_arch_type = stack_attribs.get("replica_arch_type")
            self.replica_role = stack_attribs.get("replica_role")
            self.replica_sync_type = stack_attribs.get("replica_sync_type")
            self.replica_master = stack_attribs.get("replica_master")
        else:
            # get replica params from kvargs
            self.replica_arch_type = self.kvargs.get("replica_arch_type", "MS")
            self.replica_role = self.kvargs.get("replica_role", "S")
            self.replica_sync_type = self.kvargs.get("replica_sync_type", "async")
            self.replica_master = self.kvargs.get("replica_master")

        # replica consistency checks
        if self.replica_role == "S" and self.replica_master is None:
            raise ApiManagerError("Missing replica master")

        # get compute instance linked to stack
        resources = self.stack.controller.get_directed_linked_resources_internal(
            resources=[self.stack.oid],
            link_type="resource%",
            objdef=ComputeInstance.objdef,
        )
        self.compute_instance = resources.get(self.stack.oid)[0]

        if self.replica_role == "M":
            # get compute instance ip address and set it as ip address of master server
            vpc_links, _ = self.compute_instance.get_links(type="vpc")
            self.replica_ip_master = vpc_links[0].attribs.get("fixed_ip", {}).get("ip", "")

            # users
            # - replica user
            self.replica_user = self.kvargs.get("replica_username", "replica")
            self.replica_pwd = self.kvargs.get("replica_password", random_password(length=20, strong=True))
        # slave
        else:
            # get master stack object
            master_stack = self.stack.controller.get_resource(self.replica_master, entity_class=ComputeStackV2)
            # get master stack attributes
            master_stack_attribs = master_stack.get_attribs()
            # get compute instance linked to master stack
            resources, _ = master_stack.get_linked_resources(
                link_type_filter="resource.%",
                objdef=ComputeInstance.objdef,
                run_customize=False,
            )
            master_compute_instance = resources[0]
            # get master compute instance ip address and set it as ip address of master server
            vpc_links, _ = master_compute_instance.get_links(type="vpc")
            self.replica_ip_master = vpc_links[0].attribs.get("fixed_ip", {}).get("ip", "")

            # users
            # - replica user
            users = master_stack_attribs.get("users")
            self.replica_user = users.get("replica").get("username")
            replica_pwd = users.get("replica").get("password")
            self.replica_pwd = self.stack.controller.decrypt_data(replica_pwd).decode("utf-8")

    def internal_run(self):
        """
        This method is overridden by engine specialized class method
        """
        self.logger.error("class %s does not implement internal_run", self.__class__)


    def run(self):
        self.check_params()
        self.check_replica_params()
        self.internal_run()

        # update stack params
        self.stack_v2_params["actions"] = self.actions
        self.kvargs.update(self.stack_v2_params)

        # update object attributes
        attribs = {
            "replica_arch_type": self.replica_arch_type,
            "replica_role": self.replica_role,
            "replica_sync_type": self.replica_sync_type,
            "replica_master": self.replica_master,
        }
        if self.remove_replica:
            self.stack.set_configs(key="replica", value=False)
            for k in attribs:
                self.stack.unset_configs(key=k)
            self.stack.unset_configs(key="users.replica")
        else:
            self.stack.set_configs(key="replica", value=True)
            for k, v in attribs.items():
                self.stack.set_configs(key=k, value=v)
            self.stack.set_configs(key="users.replica.username", value=self.replica_user)
            self.stack.set_configs(
                key="users.replica.password",
                value=self.stack.controller.encrypt_data(self.replica_pwd),
            )

        return ComputeStackV2.pre_update(self.stack, *self.args, **self.kvargs)


#
# Actions
#
class SqlActionHelper(SqlHelper):
    child_mapping: Dict[str, Type[SqlHelper]] = {}

    def __init__(self, stack, operation, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self.logger = getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

        self.stack = stack
        self.operation = operation

    def get_compute_instance(self):
        """
        Get compute instance linked to stack
        """
        resources = self.stack.controller.get_directed_linked_resources_internal(
            resources=[self.stack.oid],
            link_type="resource%",
            objdef=ComputeInstance.objdef,
        )
        resources = resources.get(self.stack.oid)
        if resources is not None and len(resources) > 0:
            self.compute_instance: ComputeInstance = resources[0]
        else:
            self.compute_instance: ComputeInstance = None

    def check_params(self):
        self._build_final_params()
        # verify permissions
        self.stack.verify_permisssions("update")

        # check state is ACTIVE
        self.stack.check_active()

        # get compute zone
        self.compute_zone = self.stack.get_parent()
        self.kvargs["parent"] = self.compute_zone.oid
        self.get_compute_instance()

    def internal_run(self):
        """
        This method must be overridden by engine specialized class method
        """
        pass

    def get_db_admin_user(self):
        users = self.stack.get_attribs("users")
        # new user registration
        if users.get("administrator", None) is not None:
            admin_usr = self.stack.get_attribs("users.administrator.username")
            admin_pwd = self.stack.get_attribs("users.administrator.password")
        # old user registration
        else:
            # todo: verify for the other db engine except for mysql
            admin_usr = "root"
            admin_pwd = self.stack.get_attribs("users.root")
        admin_pwd = self.stack.controller.decrypt_data(admin_pwd).decode("utf-8")

        return {"name": admin_usr, "pwd": admin_pwd}

    def add_security_group(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def del_security_group(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def set_flavor(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_monitoring(self, **kwargs):
        service_users = dict_get(self.final_params, "engine.service_users")
        monit_user = self.get_db_monit_user(service_users)
        if not monit_user:
            raise ApiManagerError("Unable to find user account for database monitoring")

        # get image
        resources = self.compute_instance.controller.get_directed_linked_resources_internal(
            resources=[self.compute_instance.oid],
            link_type="image",
            objdef=ComputeImage.objdef,
        )
        image = resources.get(self.compute_instance.oid)[0]
        os_ver = image.get_os_version()

        # add specific db monitoring parameters for ansible playbook
        kwargs.update(
            {
                "extra_vars": {
                    "p_db_monitor_flag": True,
                    "p_db_engine": self.stack.get_attribs(key="engine") + ":" + os_ver,
                    "p_db_monit_username": monit_user.get("name"),
                    "p_db_monit_password": monit_user.get("pwd"),
                }
            }
        )
        SqlActionHelper.run_server_action(self, **kwargs)

    def disable_monitoring(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_logging(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def disable_logging(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_log_module(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def disable_log_module(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_mailx(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError(f"Server { self.compute_instance.uuid} is stopped")

        # get site attributes
        site_id = self.compute_instance.get_attribs(key="availability_zone")
        site = self.compute_instance.controller.get_resource(site_id)
        site_attribs = site.get_attribs(key="config")

        # get domain
        domain = site_attribs.get("zone")

        # get relayhost
        relayhost = self.kvargs.get("relayhost")
        if relayhost is None:
            relayhost = site_attribs.get("postfix_relayhost")

        # create task workflow
        steps = [
            {
                "step": ComputeStackAction.task_path + "sql_enable_mailx_step",
                "args": [self.compute_instance.oid, relayhost, domain],
            }
        ]
        self.kvargs["steps"] = steps

    def pre_register_deregister(self):
        """
        Common operations to do before registering on / de-registering from haproxy
        """
        # get site
        site_id = self.compute_instance.get_attribs().get("availability_zone")
        site = self.compute_instance.controller.get_resource(site_id)

        # get awx container
        orchestrator_tag = "default"
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=["awx"])
        orchestrator = next(iter(orchestrators.values()))

        # get awx inventory
        inventories = dict_get(orchestrator, "config.inventories", default=[])
        if len(inventories) < 1:
            orchestrator_id = orchestrator["id"]
            raise ApiManagerError(f"No awx inventory configured for orchestrator {orchestrator_id}")
        inventory = inventories[0]
        inventory_id = inventory.get("id")
        ssh_cred_id = inventory.get("credential")

        compute_customization = self.stack.container.get_simple_resource("haproxy", entity_class=ComputeCustomization)
        customization = compute_customization.get_local_resource(site_id)
        awx_project = customization.get_physical_resource(AwxProject.objdef)

        return [
            {
                "inventory": inventory_id,
                "project": awx_project.oid,
                "playbook": "manage_reg.yml",
                "verbosity": 0,
                "ssh_cred_id": ssh_cred_id,
            },
            orchestrator,
        ]

    def haproxy_register(self, **kwargs):
        """
        Register database server on haproxy
        """
        res = self.pre_register_deregister()
        job_template_args = res[0]
        orchestrator = res[1]

        # get db engine port
        engine = self.final_params.get("engine", {})
        engine_port = engine.get("port")

        # get db server ip address
        vpc_links, _ = self.compute_instance.get_links(type="vpc")
        server_ip = vpc_links[0].attribs.get("fixed_ip", {}).get("ip", "")
        stack_name = self.stack.name
        uuid= id_gen(10)

        job_template_args["name"] = f"{stack_name}-register_on_haproxy-jobtemplate-{uuid}"
        job_template_args["desc"] = "register database server on haproxy"
        job_template_args["extra_vars"] = {
            "server_name": self.stack.name,
            "server_ip": server_ip,
            "engine_port": engine_port,
            "operation": "add",
        }

        # get initial and final port numbers of haproxy range of ports the clients can connect to
        hap_port_ini = self.kvargs.get("port_ini")
        hap_port_fin = self.kvargs.get("port_fin")

        if (hap_port_ini is not None) and (hap_port_fin is not None):
            job_template_args["extra_vars"].update(
                {
                    "hap_port_ini": hap_port_ini,
                    "hap_port_fin": hap_port_fin,
                }
            )

        # create task workflow
        steps = [
            {
                "step": ComputeStackAction.task_path + "create_awx_job_template_step",
                "args": [job_template_args, orchestrator],
            },
            # ComputeStackAction.task_path + "haproxy_save_port",
        ]
        self.kvargs["steps"] = steps

    def haproxy_deregister(self, **kwargs):
        """
        Deregister database server from haproxy
        """
        res = self.pre_register_deregister()
        job_template_args = res[0]
        orchestrator = res[1]
        stack_name = self.stack.name
        uuid = id_gen(10)

        job_template_args["name"] = f"{stack_name}-deregister_from_haproxy-jobtemplate-{uuid}"
        job_template_args["desc"] = "deregister database server from haproxy"
        job_template_args["extra_vars"] = {
            "server_name": self.stack.name,
            "operation": "del",
        }

        # create task workflow
        steps = [
            {
                "step": ComputeStackAction.task_path + "create_awx_job_template_step",
                "args": [job_template_args, orchestrator],
            }
        ]
        self.kvargs["steps"] = steps

    def resize(self, **kwargs):
        """
        Increase database storage capacity
        """
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError(f"Server {self.compute_instance.uuid} is stopped")

        # validate disk size
        data_disk_size = self.stack.get_allocated_storage()
        new_data_disk_size = self.kvargs.pop("new_data_disk_size")
        if new_data_disk_size < data_disk_size:
            msg = (f"Invalid resize: new size ({new_data_disk_size} GB) must be "
                   f"greater than current size ({data_disk_size} GB)")
            raise ApiManagerError(msg)
        disk_size = new_data_disk_size - data_disk_size

        # get vpc
        vpcs, _ = self.compute_instance.get_linked_resources(link_type="vpc")
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.compute_instance.get_attribs().get("availability_zone")

        # get proxy
        all_proxies = vpc.get_proxies(site_id)
        proxy, _ = all_proxies.get("http")

        # get hypervisor
        hypervisor = self.compute_instance.get_hypervisor()

        # get lvm parameters
        vg_data = self.stack.get_attribs(key="lvm.volume_group.data")
        if vg_data is None:
            vg_data = dict_get(self.final_params, "lvm.volume_group.data")
        lv_data = self.stack.get_attribs(key="lvm.logical_volume.data")
        if lv_data is None:
            lv_data = dict_get(self.final_params, "lvm.logical_volume.data")

        ac_params = {
            "customization": "os-utility",
            "playbook": "extend_volume.yml",
            "extra_vars": {
                "volume_group": vg_data,
                "logical_volume": lv_data,
                "proxy_server": proxy,
                "hypervisor": hypervisor,
            },
        }

        # create task workflow
        steps = [
            # - create volume
            {
                "step": ComputeStackAction.task_path + "sql_create_compute_volume_step",
                "args": [self.compute_instance.oid, disk_size],
            },
            # - attach volume to vm
            {
                "step": ComputeStackAction.task_path + "sql_run_action_on_server_step",
                "args": [self.compute_instance.oid],
            },
            # - extend vg and lv
            {
                "step": ComputeStackAction.task_path + "sql_invoke_apply_customization_step",
                "args": [self.compute_instance.oid, ac_params],
            },
            # - update allocated storage attribute
            {
                "step": ComputeStackAction.task_path + "sql_update_allocated_storage_step",
                "args": [new_data_disk_size],
            },
        ]

        self.kvargs["steps"] = steps

    def run_server_action(self, **kwargs):
        self.logger.debug("+++++ run_server_action - kwargs: %s", kwargs)
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError(f"Server { self.compute_instance.uuid} is stopped")

        # get extra vars if exist
        extra_vars = kwargs.pop("extra_vars", None)
        self.logger.debug("+++++ run_server_action - extra_vars: %s", extra_vars)
        if extra_vars is not None:
            self.kvargs["extra_vars"] = extra_vars

        # create task workflow
        steps = [
            {
                "step": ComputeStackAction.task_path + "sql_run_action_on_server_step",
                "args": [self.compute_instance.oid],
            }
        ]
        self.kvargs["steps"] = steps

    def run(self):
        self.check_params()
        self.internal_run()

        # get engine
        engine = self.stack.get_attribs(key="engine")

        # get engine major version
        engine_version = self.stack.get_attribs(key="version")
        engine_major_version = SqlHelper.get_engine_major_version(engine_version, 2)

        # get port
        engine = self.final_params.get("engine", {})
        engine_port = engine.get("port")

        # get db admin credentials
        admin_user = self.get_db_admin_user()
        admin_usr = admin_user.get("name")
        admin_pwd = admin_user.get("pwd")

        # task workflow
        run_steps = [ComputeStackV2.task_path + "action_resource_pre_step"]
        run_steps.extend(self.kvargs.pop("steps", []))
        run_steps.append(ComputeStackV2.task_path + "action_resource_post_step")

        class_name = self.__class__.__name__

        # manage params
        params = {
            "cid": self.stack.container.oid,
            "id": self.stack.oid,
            "objid": self.stack.objid,
            "ext_id": self.stack.ext_id,
            "engine": engine,
            "version": engine_major_version,
            "port": engine_port,
            "admin_usr": admin_usr,
            "admin_pwd": admin_pwd,
            "action_name": self.operation,
            "steps": run_steps,
            "alias": f"{class_name}.{self.operation}",
            # 'sync': True
        }
        params.update(self.kvargs)
        params.update(self.stack.get_user())
        res = prepare_or_run_task(self.stack, self.stack.action_task, params, sync=False)
        self.logger.info("Execute %s action on compute stack %s using task", self.operation, self.stack.uuid)
        return res
