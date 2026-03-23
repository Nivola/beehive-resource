# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations
from logging import getLogger
from logging import Logger
from typing import Any, Dict, Union, TYPE_CHECKING, Type, ClassVar, Set, TypedDict, List, Optional

from beecell.simple import random_password, bool2str, dict_get, truncate, id_gen
from beecell.simple import random_password, dict_get, id_gen
from beecell.types.res.haproxy import HaproxyConfigDict
from beecell.types.res.paas import CreatePaasParamRequestDict
from beecell.types.res.stack import (
    ServiceUserDetail,
    CustomizationDetail,
    CustomizationDict,
    EngineBlock,
    EngineParams,
    OutputsDict,
)
from beehive.common.apimanager import ApiManagerError
from beehive.common.task_v2 import prepare_or_run_task
from beehive_resource.plugins.provider.controller import LocalProvider
from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.image import ComputeImage
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2, ComputeStackAction
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

if TYPE_CHECKING:
    from .paas_stack import PaasStackV2
    from beehive_resource.container import ResourceContainer, Resource
    from beehive_resource.controller import ResourceController
    from beehive_resource.plugins.provider.entity.image import ComputeImage
    from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
    from beehive_resource.plugins.provider.entity.site import Site
    from beehive_resource.plugins.provider.entity.vpc import Vpc
    from beehive_resource.plugins.provider.entity.zone import ComputeZone
# # # from beecell.debug import  dbg


class StackConfigDict(TypedDict):
    # TODO normalizzare compute_zone o parent senbrano
    # essere utilizzate in modo intercambiabile o uno o l'altra
    compute_zone: str
    parent: str
    engine: str
    version: str
    host_group: str
    hypervisor: str
    image: str
    key_name: str
    metrics_prefix: str
    volume_flavor: str
    flavor: str
    steps_order: Dict[str, List[str]]
    customizations: Dict[str, CustomizationDetail]


class EngineConfigDict(StackConfigDict):
    haproxy_config: HaproxyConfigDict


# class PaasKwDict(TypedDict):
#     name: str
#     desc: str
#     multi_avz: str
#     hostname: str
#     timezone: str
#     compute_zone: str
#     parent: str
#     availability_zone: str
#     # get flavor
#     flavor: str
#     # get volume flavor
#     volume_flavor: str
#     # get vpc
#     vpc: str
#     # self.zbx_proxy_ip, self.zbx_proxy_name = vpc_net.get_zabbix_proxy()
#     # subnet
#     subnet: str
#     # allocable_subnet = vpc_net.get_allocable_subnet(subnet)
#     # get security group
#     security_group: str
#     # get key
#     key_name: str
#     engine_configs: EngineConfigDict


class PaasHelper:
    child_mapping = {}
    child_mapping: Dict[str, Type[PaasHelper]] = {}
    legacy_customizations: Dict[str, CustomizationDetail] = {
        "config_haproxy": {
            "playbook": "lbaas.yml",
            "customization": "haproxy-lbaas",
            "orchestrator_tag": "02",
        },
        'haproxy-lbaas': {
            'customization': 'haproxy-lbaas',
            'orchestrator_tag': '02',
            'playbook': 'lbaas.yml'},
        "wait_ssh_is_up": {
            "playbook": "wait_ssh_is_up.yml",
            "customization": "os-utility",
            "orchestrator_tag": "default",
        },
        "set_yum_proxy": {
            "playbook": "set_yum_proxy.yml",
            "customization": "os-utility",
            "orchestrator_tag": "default",
        },
        "set_dnf_proxy": {
            "playbook": "set_dnf_proxy.yml",
            "customization": "os-utility",
            "orchestrator_tag": "default",
        },
        "setup_mailx": {
            "playbook": "setup_mailx.yml",
            "customization": "os-utility",
            "orchestrator_tag": "default",
        },
        "setup_nfsbcklogici": {
            "customization": "os-utility2",
            "orchestrator_tag": "02",
            "playbook": "setup_nfsbcklogici.yml",
        },
        "enable_monitoring": {
            "customization": "zabbix-agent",
            "playbook": "install.yml",
        },
        "enable_log_forwarding": {
            "customization": "filebeat",
            "playbook": "install.yml",
        },
    }

    @classmethod
    def get_engines(cls) -> Set[str]:
        return cls.child_mapping.keys()

    @classmethod
    def register_child(cls, engine: str, spec: Type[PaasHelper]) -> None:
        cls.child_mapping[engine] = spec

    @classmethod
    def get_helper_by_engine(cls, engine: str) -> Optional[Type[PaasHelper]]:
        return cls.child_mapping.get(engine)

    @property
    def engines(self) -> Set[str]:
        return self.child_mapping.keys()

    def __init__(self, *args, **kvargs):
        """
        initialize
            self.logger
            self.args
            self.kvargs
            self.engine_params
            self.stack_v2_params
            self.inputs
            self.outputs
            self.actions
            self.enabled_monitoring

        """
        self.logger: Logger = getLogger(self.__class__.__module__ + "." + self.__class__.__name__)
        self.args = args
        self.kvargs: CreatePaasParamRequestDict = kvargs

        self.engine_configs = self.kvargs.get("engine_configs",{})
        self.stack_v2_params = {}
        self.inputs = []
        self._customizations: Dict[str, CustomizationDetail] = []
        self.step_order: List[str] = []
        self.outputs: List[OutputsDict] = []
        self.actions: List[dict] = []
        self.enabled_monitoring = False
        self.custom_attributes: dict = {}

    @staticmethod
    def get_engine_major_version(version, n):
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
        l = version.split(".")
        if len(l) > n:
            for i in range(n):
                return ".".join(l[:n])
        return version

    def get_customization(self, action_name: str) -> CustomizationDetail:
        result = self._customizations.get(action_name)
        if result is None:
            result = self.legacy_customizations.get(action_name)
        return result

    def append_action(self, action: str) -> bool:
        """
        Add a dictionary describing a Stack Action to create to the actions list
        action method fullfil a stict  naming convetion and a signature
        i.e.
            def action_<action_name>(self) -> dict:
        they build and return a dictionatry containing the parameters used for create StackActions.
        No parameters are passed to actions method. Al values must be reached from self.

        Returns:
            bool: The method return True if an action methodo is found and succesfully called.
                Otherwise is returned False
        """
        try:
            actionmethod = getattr(self, f"action_{action.strip().lower().translate(str.maketrans('- ', '__'))}")
            if callable(actionmethod):
                self.actions.append(actionmethod())
                return True
            return False
        except AttributeError as ex:
            self.logger.error(ex)
            return False

    def check_params(self):
        """Check params
            Check  parameters that cold not be checked at initialization time
            Overide when needed
            may raise ApiManagerError
        """
        pass

    def set_additional_steps(self) -> List[dict]:
        """
            returns additionals steps for task
            This method  shall be overridden in specialization when needed
        """
        return []

    def internal_run(self) -> None:
        """internal run base   implemetation
            scan step_order and add accion
        """
        # add actions  defined in step_order
        for action in self.step_order:
            if not self.append_action(action):
                self.logger.error("undefined actions %s" % action)

        pass

    def run(self) -> Dict:
        raise NotImplementedError("called run on ", self.__class__.__name__)


#
# Create
#
class PaasCreateHelper(PaasHelper):
    """
    PaasCreateHelper
    Args:
        PaasHelper (_type_): _description_

    Raises:
        ApiManagerError: _description_
        ApiManagerError: _description_
        ApiManagerError: _description_
        ApiManagerError: _description_
        ApiManagerError: _description_
        ApiManagerError: _description_
        ApiManagerError: _description_
        ApiManagerError: _description_

    Returns:
        _type_: _description_
    """

    child_mapping: Dict[str, Type[PaasCreateHelper]] = {}
    # {
    #     haproxy-lbaas
    # }

    def __init__(self, controller: ResourceController, container: LocalProvider, *args, **kvargs):
        """_summary_

        Args:
            controller (ResourceController): un istance of the ResourceController
            container (_type_): _description_
        """
        super().__init__(*args, **kvargs)
        self.args = args
        self.kvargs: CreatePaasParamRequestDict = kvargs

        self.controller = controller
        self.container = container
        self.filter = {"container_id": self.container.oid, "run_customize": False}

        self.name = self.kvargs.get("name")
        self.desc = self.kvargs.get("desc")

        self.engine_configs: EngineConfigDict = self.kvargs.get("engine_configs")

        self.haproxy_config: dict = self.engine_configs.get("haproxy_config")
        if self.haproxy_config is not None:
            self.custom_attributes["haproxy_config"] = self.haproxy_config
            self.engine_configs.pop("haproxy_config")

        self.multi_avz = self.kvargs.get("multi_avz")
        self.hostname = self.kvargs.get("hostname", self.name)

        self.host_group = self.kvargs.get("host_group")
        self.hypervisor = self.kvargs.get("hypervisor")
        self.engine = self.kvargs.get("engine")
        self.version = self.kvargs.get("version")
        self.image_name = self.kvargs.get("image")
        self.image: ComputeImage = self.controller.get_resource(self.image_name, **self.filter)

        self._customizations = self.engine_configs.get("customizations")

        self.step_order: List[str] = self.engine_configs.get("steps_order").get("create")

        # get compute zone
        if "compute_zone" in self.kvargs:
            compute_zone_id = self.kvargs.get("compute_zone")
        else:
            compute_zone_id = self.kvargs.get("parent")

        self.compute_zone: ComputeZone = self.container.get_simple_resource(compute_zone_id)
        self.compute_zone.set_container(self.container)
        self.kvargs["parent"] = self.compute_zone.oid

        # get site
        availability_zone = self.kvargs.get("availability_zone")
        self.site: Site = self.controller.get_resource(availability_zone)
        # repository del site per scaricare paccketti aggiuntivi
        self.ip_repository: str = self.site.get_attribs().get("repo")
        # get zabbix server connection params
        orchestrators = self.site.get_orchestrators_by_tag("tenant", select_types=["zabbix"])
        orchestrator_idx = list(orchestrators.keys())[0]
        orchestrator: ResourceContainer = self.controller.get_container(orchestrator_idx)
        conn_params: dict = orchestrator.conn_params["api"]
        self.zbx_srv_uri = conn_params.get("uri")
        self.zbx_srv_usr = conn_params.get("user")
        pwd = conn_params.get("pwd")
        self.zbx_srv_pwd = orchestrator.decrypt_data(pwd).decode("utf-8")
        self.zbx_srv_ip = orchestrator.get_ip_address(self.zbx_srv_uri)

        # get flavor
        flavor_name: str = self.kvargs.get("flavor")
        self.flavor = self.controller.get_resource(flavor_name, entity_class=ComputeFlavor, **self.filter)
        self.flavor.check_active()

        # get ram from flavor
        self.server_ram_mb = int(self.flavor.get_configs().get("memory"))
        self.server_ram_gb = self.server_ram_mb // 1024

        # get volume flavor
        self.volume_flavor: ComputeVolumeFlavor = self.controller.get_resource(
            self.kvargs.pop("volume_flavor"),
            entity_class=ComputeVolumeFlavor,
            **self.filter,
        )
        self.volume_flavor.check_active()

        # get vpc
        vpc_id = self.kvargs.get("vpc")
        self.vpc: Vpc = self.controller.get_resource(vpc_id, **self.filter)
        self.vpc.check_active()

        # get proxy and zabbix proxy
        all_proxy = self.vpc.get_proxies(self.site.oid)
        self.proxy, self.set_proxy = all_proxy.get("http")
        self.zbx_proxy_ip, self.zbx_proxy_name = all_proxy.get("zabbix")

        # check subnet
        self.subnet = self.kvargs.get("subnet")

        # get security group
        security_group = self.kvargs.get("security_group")
        self.security_group: SecurityGroup = self.controller.get_resource(security_group, **self.filter)
        self.security_group.check_active()

        # get key
        key_name = self.kvargs.get("key_name")
        keys = self.compute_zone.get_ssh_keys(oid=key_name)
        if len(keys) > 0:
            self.key_name = keys[0]["uuid"]
        else:
            raise ApiManagerError("ssh key %s does not exist" % key_name)

        # get db related data
        # remove unnecessiry  values from kvargs
        self.kvargs.pop("engine")
        self.kvargs.pop("version")
        self.kvargs.pop("flavor")
        self.kvargs.pop("vpc")
        self.kvargs.pop("subnet")
        self.kvargs.pop("security_group")

        # set zabbix hostgroup
        self.zabbix_host_groups = [self.compute_zone.desc]
        # per zabbix vm Windows
        self.zabbix_host_group = self.compute_zone.desc

        self.os_ver = None
        self.license = None
        self.monit_user = None
        self.stack_ip: str = None
        self.stack_fqdn: str = None
        # - admin user  always random
        self.admin_user = None
        self.admin_pwd = random_password(length=10, strong=False)

    def internal_run(self):
        """This method is overridden by engine specialized class method"""
        self.license = self.engine_configs.get("license")

        self.outputs.append(self.set_output())

        # os_ver = self.image.get_os_version()
        super().internal_run()

        # self.outputs.append(self.set_output())
        # # add actions  defined in step_order
        # for action in self.step_order:
        #     if not self.append_action(action):
        #         self.logger.error("undefined actions %s" % action)


    def run(self):
        self.internal_run()

        self.stack_v2_params["inputs"] = self.inputs
        self.stack_v2_params["outputs"] = self.outputs
        self.stack_v2_params["actions"] = self.actions
        self.stack_v2_params["enabled_monitoring"] = self.enabled_monitoring

        self.kvargs.update(self.stack_v2_params)
        self.kvargs["attribute"] = {
            "metrics_prefix": self.engine_configs.get("metrics_prefix", "paas_"),
            "stack_type": "paas",
            "engine": self.engine,
            "engine_configs": self.engine_configs,
            "version": self.version,
            "volume_flavor": self.volume_flavor.name,
            "license": self.license,
            "users": {
                "administrator": {
                    "username": self.admin_user,
                    "password": self.controller.encrypt_data(self.admin_pwd),
                },
            },
        }
        if self.haproxy_config is not None:
            self.kvargs["attribute"]["haproxy_config"]=self.haproxy_config

        # update attributes with custom_attributes
        self.kvargs["attribute"].update(self.custom_attributes)

        self.kvargs["additional_steps"] = self.set_additional_steps()
        result = ComputeStackV2.pre_create(self.controller, self.container, *self.args, **self.kvargs)
        ### TODO  TEMPORARY LOG
        import pprint
        self.logger.debug(pprint.pformat(result, indent=2))
        return result

    def set_output(self) -> dict:
        """output description

        Returns:
            dict: task output description
        """
        return {
            "name": "ResourceIP",
            "desc": "Master Server IP address",
            "value": "$$action_resource.%s-create_server1::vpcs.0.fixed_ip.ip$$" % self.name,
        }

    def action_create_server(self) -> dict:
        """Create action definition in order to create the server

        Returns:
            dict: Dictionary cotaining the step action definition
        """
        res = {
            "name": "create_server1",
            "desc": "create server",
            "resource": {"type": "ComputeInstance", "operation": "create"},
            "params": {
                "name": "%s-server01" % self.name,
                "desc": "%s Server 01" % self.desc,
                "parent": self.compute_zone.oid,
                "availability_zone": self.site.oid,
                "multi_avz": self.multi_avz,
                "host_group": self.host_group,
                # "orchestrator_tag": self.orchestrator_tag,
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
                        # "volume_size": ,
                        "flavor": self.volume_flavor.oid,
                        "uuid": self.image.oid,
                        "source_type": "image",
                    },
                ],
            },
        }

        return res

    def action_wait_ssh_up(self) -> dict:
        return self.action_wait_ssh_is_up()

    def action_wait_ssh_is_up(self) -> dict:
        """action for wait until server can recive ssh connection

        Returns:
            dict : action step definition
        """
        custom: CustomizationDict = self.get_customization("wait_ssh_is_up")
        if custom is None:
            raise ApiManagerError("customization for wait_ssh_is_up action not found")
        is_private = False
        if self.compute_zone.get_bastion_host() is not None:
            is_private = True

        res = {
            "name": "wait_ssh_is_up",
            "desc": "wait ssh is up",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-wait_ssh_is_up" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": {"is_private": is_private},
            },
        }
        return res

    def action_config_haproxy(self) -> dict:
        return self.action_haproxy_lbaas()

    def action_haproxy_lbaas(self) -> dict:
        """action for wait until server can recive ssh connection

        Returns:
            dict : action step definition
        """
        custom: CustomizationDict = self.get_customization("haproxy-lbaas")
        if custom is None:
            raise ApiManagerError("customization for haproxy-lbaas action not found")
        extra_vars=self.haproxy_config
        if extra_vars is None:
            extra_vars = {}

        res = {
            "name": "haproxy_lbaas",
            "desc": "install haproxy for lbaas",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-haproxy_lbaas" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": extra_vars,
            },
        }
        return res

    def action_set_yum_proxy(self) -> dict:
        """describe action to configure yum proxy

        Returns:
            dict: step action definition
        """
        custom: CustomizationDict = self.get_customization("set_yum_proxy")
        if custom is None:
            raise ApiManagerError("customization for set_yum_proxy action not found")

        res = {
            "name": "set_yum_proxy",
            "desc": "set yum proxy",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-set_yum_proxy" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": {"set_proxy": self.set_proxy, "proxy_server": self.proxy},
            },
        }
        return res

    def action_set_dnf_proxy(self) -> dict:
        """describe action to configure dnf proxy

        Returns:
            dict: step action definition
        """
        custom: CustomizationDict = self.get_customization("set_dnf_proxy")
        if custom is None:
            raise ApiManagerError("customization for set_dnf_proxy action not found")

        res = {
            "name": "set_dnf_proxy",
            "desc": "set dnf proxy",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-set_dnf_proxy" % self.name,
                "parent": custom.get("customization"),
                "compute_zone": self.compute_zone.oid,
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": {"set_proxy": self.set_proxy, "proxy_server": self.proxy},
            },
        }
        return res

    def action_set_etc_hosts(self) -> dict:
        """describe action to configure etc/hosts

        Returns:
            dict: step action definition
        """
        custom: CustomizationDict = self.get_customization("set_etc_hosts")
        if custom is None:
            raise ApiManagerError("customization for set_etc_hosts action not found")

        res = {
            "name": "set_etc_hosts",
            "desc": "set etc/hosts",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-set_etc_hosts" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": {
                    "hostname": "$$action_resource.%s-create_server1::vpcs.0.fixed_ip.hostname$$" % self.name,
                    "ip_addr": "$$action_resource.%s-create_server1::vpcs.0.fixed_ip.ip$$" % self.name,
                },
            },
        }
        return res

    def action_setup_mailx(self) -> dict:
        """describe action to setup and configure mailx server

        Returns:
            dict: step action definition
        """
        custom: CustomizationDict = self.get_customization("setup_mailx")
        if custom is None:
            raise ApiManagerError("customization for setup_mailx action not found")

        res = {
            "name": "setup_mailx",
            "desc": "setup_mailx",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-setup_mailx" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "playbook": "setup_mailx.yml",
                "extra_vars": {
                    "p_client_fqdn": "$$action_resource.%s-create_server1::vpcs.0.fixed_ip.hostname$$" % self.name,
                },
            },
        }
        return res

    def action_enable_monitoring(self) -> dict:
        """describe action to enable monitoring

        Returns:
            dict: step action definition
        """
        custom: CustomizationDict = self.get_customization("enable_monitoring")
        if custom is None:
            raise ApiManagerError("customization for enable_monitoring action not found")

        self.enabled_monitoring = True
        self.logger.debug("+++++ SqlCreateHelper - action_enable_monitoring")
        # vedi - set monitoring su ComputeInstance collegato
        res = {
            "name": "enable_monitoring",
            "desc": "enable monitoring",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-enable_monitoring" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": {
                    "p_ip_repository": self.ip_repository,
                    "p_proxy_server": self.proxy,
                    "p_no_proxy": "localhost,10.0.0.0/8",
                    "p_zabbix_proxy_ip": self.zbx_proxy_ip,
                    "p_zabbix_proxy_name": self.zbx_proxy_name,
                    "p_zabbix_server_ip": self.zbx_srv_ip,
                    "p_zabbix_server_uri": self.zbx_srv_uri,
                    "p_zabbix_server_username": self.zbx_srv_usr,
                    "p_zabbix_server_password": self.zbx_srv_pwd,
                    "p_custom_host_groups": self.zabbix_host_groups,
                    "p_custom_host_group": self.zabbix_host_group,
                    "p_custom_templates": [],
                    "p_target_host": "$$action_resource.%s-create_server1::attributes.fqdn$$" % self.name,
                },
            },
        }
        return res

    def action_enable_log_forwarding(self) -> dict:
        """describe action to enable log forwarding

        Returns:
            dict: step action definition
        """
        custom: CustomizationDict = self.get_customization("enable_monitoring")
        if custom is None:
            raise ApiManagerError("customization for enable_monitoring action not found")

        res = {
            "name": "enable_log_forwarding",
            "desc": "enable log forwarding",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-enable_log_forwarding" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": "$$action_resource.%s-create_server1::id$$" % self.name,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": {
                    "p_ip_repository": self.ip_repository,
                    "p_proxy_server": self.proxy,
                },
            },
        }
        return res


#
# Delete
#
class PaasDeleteHelper(PaasHelper):
    child_mapping: Dict[str, Type[PaasDeleteHelper]] = {}

    def __init__(self, stack: PaasStackV2, *args, **kvargs):
        PaasHelper.__init__(self, *args, **kvargs)

        self.stack = stack
        self.engine_configs = stack.attribs.get("engine_configs",{})
        self.engine: str = ""
        self.engine_major_version: str = ""
        self.compute_zone: Resource = None
        self.compute_instance_info: str = ""
        self.compute_instance: ComputeInstance = None
        self.os_ver: str = ""
        self.fqdn: str = ""
        self.fulldelete: bool = True

        # self.check_params()

    def get_compute_instance(self):
        """Get compute instance linked to stack"""

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

    # def internal_run(self):
    #     pass

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

        # get stacks
        # resources, total = self.get_linked_resources(link_type_filter='relation%')
        # actions, total = self.get_linked_resources(link_type_filter='action%')

        ## actions (ComputeStackAction) done during stack life
        doneactions = self.stack.get_actions()
        doneactions.reverse()
        ## action to run before deleteting
        actions: List[dict] = []
        for action in self.actions:
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

            ### ATTENTION we do not supporto $$ parameters.'
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
        # first standard steps sequence for update thet stack

        steps = []

        # steps.append( ComputeStackV2.task_path + "update_resource_pre_step")
        steps.append(ComputeStackV2.task_path + "expunge_resource_pre_step"),
        if len(actions) > 0:
            steps.append(ComputeStackV2.task_path + "create_stack_actions_step")

        # steps to run actions
        for action in actions:
            step = {
                "step": ComputeStackV2.task_path + "run_stack_action_step",
                "args": [f"{self.stack.name}-{action.get('name')}"],
            }
            steps.append(step)

        # scan all the ComputeStackAction  executed for then stack and  prepare the delet task
        # steps to delete all action that has been runned
        for doneaction in doneactions:
            if preserve is False:
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
        # steps to delet action created while deleting
        for todoaction in actions:
            if preserve is False:
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
        """Check parameters are set and does some initialization

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
        self.engine_major_version = PaasHelper.get_engine_major_version(engine_version, 2)

        # get image
        resources = self.compute_instance.controller.get_directed_linked_resources_internal(
            resources=[self.compute_instance.oid],
            link_type="image",
            objdef=ComputeImage.objdef,
        )
        image = resources.get(self.compute_instance.oid)[0]
        self.os_ver = image.get_os_version()
        self.compute_instance_info = self.compute_instance.info()
        self.fqdn = dict_get(self.compute_instance_info, "attributes.fqdn")

        # self.compute_instance.get_credential()
        self.logger.debug("+++++ check_params - get_ssh_node - fqdn: %s" % self.fqdn)
        if not self.compute_instance.is_managed():
            self.fulldelete = False


#
# Update
#
class PaasUpdateHelper(PaasHelper):
    child_mapping: Dict[str, Type[PaasUpdateHelper]] = {}

    def __init__(self, stack:PaasStackV2, *args, **kvargs):
        super().__init__(self, *args, **kvargs)
        self.stack: PaasStackV2 = stack
        self.name : str = self.stack.name
        self.haproxy_config: Optional[HaproxyConfigDict] = self.engine_configs.get("haproxy_config")
        self.engine_configs: dict = stack.attribs.get("engine_configs",{})
        self.stack.attribs["haproxy_config"]=self.haproxy_config
        self.stack.save_attribs()

        self.compute_zone: ComputeZone = self.stack.get_parent()
        self.kvargs["parent"] = self.compute_zone.oid
        self.engine: str = self.stack.get_attribs(key="engine")
        self.compute_instance : ComputeInstance

        if self.stack.compute_instance is None:
            resources  =self.stack.get_child_resources()
            for resource in resources:
                if isinstance(resource, ComputeInstance):
                    self.compute_instance = resource
        else:
            self.compute_instance = self.stack.compute_instance

        self._customizations = self.engine_configs.get("customizations")

        self.step_order: List[str] = self.engine_configs.get("steps_order").get("update",[])


        # users
        # - admin user
        # self.admin_user = self.stack.get_attribs("users").get("administrator").get("username")
        # admin_pwd = self.stack.get_attribs("users").get("administrator").get("password")
        # self.admin_pwd = self.stack.controller.decrypt_data(admin_pwd).decode("utf-8")


    # def set_additional_steps(self) -> List[dict]:
    #     """This method is overridden by engine specialized class method"""
    #     self.logger.error("class %s does not implement set_additional_steps", self.__class__)
    #     return None

    def action_haproxy_lbaas(self) -> dict:
        """action for wait until server can recive ssh connection

        Returns:
            dict : action step definition
        """
        custom: CustomizationDict = self.get_customization("haproxy-lbaas")
        if custom is None:
            raise ApiManagerError("customization for haproxy-lbaas action not found")
        # # # dbg (self.haproxy_config)
        extra_vars=self.haproxy_config
        if extra_vars is None:
            extra_vars = {}

        res = {
            "name": "haproxy_lbaas",
            "desc": "install haproxy for lbaas",
            "resource": {"type": "AppliedComputeCustomization", "operation": "create"},
            "params": {
                "name": "%s-haproxy_lbaas" % self.name,
                "parent": custom.get("customization"),
                "orchestrator_tag": custom.get("orchestrator_tag"),
                "compute_zone": self.compute_zone.oid,
                "instances": [
                    {
                        "id": self.compute_instance.oid,
                        "extra_vars": {},
                    }
                ],
                "playbook": custom.get("playbook"),
                "extra_vars": extra_vars,
            },
        }
        return res


    def run(self):
        self.internal_run()
        # update stack params
        self.stack_v2_params["actions"] = self.actions
        self.kvargs.update(self.stack_v2_params)

        # additional steps
        self.kvargs["additional_steps"] = self.set_additional_steps()

        return ComputeStackV2.pre_update(self.stack, *self.args, **self.kvargs)


#
# Import
#
class PaasImportHelper(PaasHelper):
    child_mapping: Dict[str, Type[PaasImportHelper]] = {}

    def __init__(self, controller, container, *args, **kvargs):
        PaasHelper.__init__(self, *args, **kvargs)

        self.controller = controller
        self.container = container

        physical_id = self.kvargs.get("physical_id")
        params = self.kvargs.pop("configs", {})

        # check server type from ext_id
        self.compute_instance = controller.get_resource(physical_id)
        if isinstance(self.compute_instance, ComputeInstance) is False:
            raise ApiManagerError("SqlComputeStack require ComputeInstance as physical resource")

        self.compute_instance_info = self.compute_instance.info()
        self.compute_instance_avz_num = len(self.compute_instance.get_dedploy_availability_zones())

        # # get compute zone
        # self.compute_zone = self.compute_instance.get_parent()
        # self.compute_zone.set_container(self.container)
        # self.kvargs['parent'] = self.compute_zone.oid
        # self.kvargs['objid'] = '%s//%s' % (self.compute_zone.objid, id_gen())

        self.name = self.kvargs.get("name")
        self.desc = self.kvargs.get("desc")

        self.multi_avz = True if self.compute_instance_avz_num > 0 else False
        self.host_group = dict_get(self.compute_instance_info, "attributes.host_group")
        self.orchestrator_tag = dict_get(self.compute_instance_info, "attributes.orchestrator_tag")
        self.hostname = dict_get(self.compute_instance_info, "attributes.fqdn")
        self.hypervisor = dict_get(self.compute_instance_info, "hypervisor")
        self.charset = params.get("charset", "latin1")
        self.timezone = params.get("timezone", "Europe/Rome")
        self.engine = params.get("engine")
        self.version = params.get("version")

        # get engine port
        self.port = params.get("port", None)

        # get data size
        block_device_mapping = self.compute_instance_info.get("block_device_mapping")
        self.data_disk_size = sum([b["volume_size"] for b in block_device_mapping[1:]])

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
        self.license = None

        self.replica = False

    def internal_run(self):
        pass

    def check_params(self):
        if self.port is None:
            self.port = dict_get(self.engine_params, "port")

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
            "license": self.license,
            "replica": self.replica,
            "port": self.port,
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

        # set additional steps
        # self.kvargs['additional_steps'] = self.set_additional_steps()

        return ComputeStackV2.pre_import(self.controller, self.container, *self.args, **self.kvargs)

    def set_output(self)->dict:
        return {
            "name": "ResourceIP",
            "desc": "Master Server IP address",
            "value": "$$action_resource.%s-import_server1::vpcs.0.fixed_ip.ip$$" % self.name,
        }

    def action_import_server(self):
        return {
            "name": "import_server1",
            "desc": "import server",
            "resource": {"type": "ComputeInstance", "operation": "import"},
            "params": {
                "uuid": self.compute_instance.uuid,
                # 'name': '%s-server01' % self.name,
                # 'desc': '%s Server 01' % self.desc,
                # 'parent': self.compute_zone.oid,
                # 'availability_zone': self.site.oid,
                # 'multi_avz': self.multi_avz,
                # 'host_group': self.host_group,
                # 'orchestrator_tag': self.orchestrator_tag,
                # 'networks': [
                #     {
                #         'subnet': self.subnet,
                #         'vpc': self.vpc.oid,
                #         'fixed_ip': {
                #             'hostname': self.hostname
                #         }
                #     }
                # ],
                # 'flavor': self.flavor.oid,
                # 'security_groups': [self.security_group.oid],
                # 'admin_pass': random_password(length=10, strong=True),
                # 'key_name': self.key_name,
                # 'type': self.hypervisor,
                # 'user_data': None,
                # 'resolve': True,
                # 'manage': True,
                # 'block_device_mapping': [
                #     {
                #         'boot_index': 0,
                #         'volume_size': self.root_disk_size,
                #         'flavor': self.volume_flavor.oid,
                #         'uuid': self.image.oid,
                #         'source_type': 'image',
                #     },
                #     {
                #         'boot_index': 1,
                #         'volume_size': self.data_disk_size,
                #         'flavor': self.volume_flavor.oid,
                #     }
                # ]
            },
        }


#
# Actions
#
class PaasActionHelper(PaasHelper):
    child_mapping: Dict[str, Type[PaasActionHelper]] = {}

    def __init__(self, stack, operation, *args, **kvargs):
        PaasHelper.__init__(self, *args, **kvargs)

        self.logger = getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

        self.stack = stack
        self.operation = operation

    def get_compute_instance(self):
        """Get compute instance linked to stack"""
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
        # verify permissions
        self.stack.verify_permisssions("update")

        # check state is ACTIVE
        self.stack.check_active()

        # get compute zone
        self.compute_zone = self.stack.get_parent()
        self.kvargs["parent"] = self.compute_zone.oid
        self.get_compute_instance()

    def internal_run(self):
        """This method must be overridden by engine specialized class method"""
        pass

    def set_additional_steps(self) -> List[dict]:
        """This method should be overridden by engine specialized class method"""
        return None

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
        self.run_server_action(**kwargs)

    def del_security_group(self, **kwargs):
        self.run_server_action(**kwargs)

    def set_flavor(self, **kwargs):
        self.run_server_action(**kwargs)

    def enable_monitoring(self, **kwargs):
        monit_user = self.get_db_monit_user(self.engine_params.get("service_users"))
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
        self.run_server_action(self, **kwargs)

    def disable_monitoring(self, **kwargs):
        self.run_server_action(**kwargs)

    def enable_logging(self, **kwargs):
        self.run_server_action(**kwargs)

    def disable_logging(self, **kwargs):
        self.run_server_action(**kwargs)

    def enable_log_module(self, **kwargs):
        self.run_server_action(**kwargs)

    def disable_log_module(self, **kwargs):
        self.run_server_action(**kwargs)

    def enable_mailx(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

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
        """Common operations to do before registering on / de-registering from haproxy"""
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
            raise ApiManagerError("No awx inventory configured for orchestrator %s" % orchestrator["id"])
        inventory = inventories[0]
        inventory_id = inventory.get("id")
        ssh_cred_id = inventory.get("credential")

        # get awx project
        from beehive_resource.plugins.provider.entity.customization import (
            ComputeCustomization,
        )
        from beehive_resource.plugins.awx.entity.awx_project import AwxProject

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
        """Register database server on haproxy"""
        res = self.pre_register_deregister()
        job_template_args = res[0]
        orchestrator = res[1]

        # get db engine port
        engine_port = self.stack.get_attribs(key="port")

        # get db server ip address
        vpc_links, total = self.compute_instance.get_links(type="vpc")
        server_ip = vpc_links[0].attribs.get("fixed_ip", {}).get("ip", "")

        job_template_args["name"] = "%s-register_on_haproxy-jobtemplate-%s" % (  # name job visible on Awx
            self.stack.name,
            id_gen(10),
        )
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
        """Deregister database server from haproxy"""
        res = self.pre_register_deregister()
        job_template_args = res[0]
        orchestrator = res[1]

        job_template_args["name"] = "%s-deregister_from_haproxy-jobtemplate-%s" % (
            self.stack.name,
            id_gen(10),
        )
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
        """Increase database storage capacity"""
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # validate disk size
        data_disk_size = self.stack.get_allocated_storage()
        # data_disk_size = self.stack.get_attribs(key='allocated_storage')
        new_data_disk_size = self.kvargs.pop("new_data_disk_size")
        if new_data_disk_size < data_disk_size:
            raise ApiManagerError("New storage value must be greater than the current value")
        disk_size = new_data_disk_size - data_disk_size

        # get vpc
        vpcs, total = self.compute_instance.get_linked_resources(link_type="vpc")
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.compute_instance.get_attribs().get("availability_zone")

        # get proxy
        all_proxies = vpc.get_proxies(site_id)
        proxy, set_proxy = all_proxies.get("http")

        # get hypervisor
        hypervisor = self.compute_instance.get_hypervisor()

        # get lvm parameters
        vg_data = self.stack.get_attribs(key="lvm.volume_group.data")
        if vg_data is None:
            vg_data = dict_get(self.engine_params, "lvm.volume_group.data")
        lv_data = self.stack.get_attribs(key="lvm.logical_volume.data")
        if lv_data is None:
            lv_data = dict_get(self.engine_params, "lvm.logical_volume.data")

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
        self.logger.debug("+++++ run_server_action - kwargs: %s" % kwargs)
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError("Server %s is stopped" % self.compute_instance.uuid)

        # get extra vars if exist
        extra_vars = kwargs.pop("extra_vars", None)
        self.logger.debug("+++++ run_server_action - extra_vars: %s" % extra_vars)
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
        engine_major_version = PaasHelper.get_engine_major_version(engine_version, 2)

        # get port
        port = self.stack.get_attribs(key="port")

        # get db admin credentials
        admin_user = self.get_db_admin_user()
        admin_usr = admin_user.get("name")
        admin_pwd = admin_user.get("pwd")

        # task workflow
        run_steps = [ComputeStackV2.task_path + "action_resource_pre_step"]
        run_steps.extend(self.kvargs.pop("steps", []))
        run_steps.append(ComputeStackV2.task_path + "action_resource_post_step")

        # manage params
        params = {
            "cid": self.stack.container.oid,
            "id": self.stack.oid,
            "objid": self.stack.objid,
            "ext_id": self.stack.ext_id,
            "engine": engine,
            "version": engine_major_version,
            "port": port,
            "admin_usr": admin_usr,
            "admin_pwd": admin_pwd,
            "action_name": self.operation,
            "steps": run_steps,
            "alias": "%s.%s" % (self.__class__.__name__, self.operation),
            # 'sync': True
        }
        params.update(self.kvargs)
        params.update(self.stack.get_user())
        res = prepare_or_run_task(self.stack, self.stack.action_task, params, sync=False)
        self.logger.info("Execute %s action on compute stack %s using task" % (self.operation, self.stack.uuid))
        return res


PaasHelper.register_child("lbaas", PaasHelper)
PaasCreateHelper.register_child("lbaas", PaasCreateHelper)
PaasDeleteHelper.register_child("lbaas", PaasDeleteHelper)
PaasUpdateHelper.register_child("lbaas", PaasUpdateHelper)
PaasImportHelper.register_child("lbaas", PaasImportHelper)
PaasActionHelper.register_child("lbaas", PaasActionHelper)
