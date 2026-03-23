# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Dict,TYPE_CHECKING, Optional, List, Literal, Type, overload, TypedDict
from beehive_resource.plugins.provider.helper import AbstractBaseProviderHelper,Singleton
from beecell.simple import id_gen
if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController
    from beehive_resource.plugins.provider.entity.zone import ComputeZone
    from .ontap import OntapProviderShareHelper

class ShareContext(TypedDict):
    share_role: Literal["main", "replica"]
    main_site: str
    secondary_site: Optional[str]
    compliance: bool

class ComputeZoneStaasConfError(Exception):
    """ for errors in compute zone storage configuration """
    pass

class ShareValidationError(Exception):
    """ for validation errors when creating a new share """
    pass

class StorageConfigParser(ABC):

    @classmethod
    @abstractmethod
    def check_storage_configuration(
        cls, compute_zone: 'ComputeZone', site_names: List[str]
    ):
        """
        checks and returns compute zone storage configuration

        :param compute_zone: target compute zone
        :type compute_zone: ComputeZone
        :param site_names: list of sites
        :type site_names: List[str]
        :raises NotImplementedError: subclasses should implement this method
        """
        raise NotImplementedError("Subclasses should implement this method")

    @classmethod
    @abstractmethod
    def check_storage_site_configuration(
        cls, compute_zone: 'ComputeZone', site_name: str, allow_missing_compliance_configuration=False
    ):
        """checks compute zone configuration for the specified site.

        :param compute_zone: the compute zone whose configuration to check
        :type compute_zone: ComputeZone
        :param site_name: the site name e.g. SiteTorino01
        :type site_name: str
        :param allow_missing_compliance_configuration: if False,
        raises on missing compliance configuration. default = False
        :type allow_missing_compliance_configuration: bool, optional
        :raises NotImplementedError: subclasses should implement this method
        """
        raise NotImplementedError("Subclasses should implement this method")

    @classmethod
    def validate_compliance_mappings(cls, main_site_name: str, peer_site_name: str) -> None:
        """checks if each site has a valid peer site.
        - main site and peer size can't be the same site
        - additionally, they can't both be on Torino

        :param main_site_name: source site name
        :type main_site_name: str
        :param peer_site_name: peer site name
        :type peer_site_name: str
        :raises Exception: on invalid association
        """
        if main_site_name is None or peer_site_name is None:
            raise ComputeZoneStaasConfError(
                f"invalid storage site relationship. missing value - site: {main_site_name} - peer_site: {peer_site_name}"
            )

        if (main_site_name == peer_site_name):
            raise ComputeZoneStaasConfError(
                f"invalid storage site relationship: site and peer site can't be the same site (site: {main_site_name})"
            )

        if ( ("torino" in main_site_name.lower()) and ("torino" in peer_site_name.lower()) ):
            raise ComputeZoneStaasConfError(
                "invalid storage site relationship: site and peer site can't both be on Torino - site:"
                f" {main_site_name} - peer_site: {peer_site_name}"
            )

class ShareValidator(ABC):
    def __init__(self, compute_zone: 'ComputeZone', config_parser: 'StorageConfigParser'):
        self.compute_zone = compute_zone
        self.config_parser = config_parser

    @classmethod
    def validate_share_role(cls, share_role: Literal["main", "replica"]):
        if not share_role or share_role not in ["main", "replica"]:
            raise Exception("Invalid share role %s" % share_role)

    @abstractmethod
    def validate_share_params(
        self,
        share_role: Literal['main', 'replica'],
        share_params: Dict,
        main_site_name: str,
        compliance_enabled: bool,
        secondary_site_name: Optional[str] = None,
        **kwargs
    ) -> ShareContext:
        """validate share params

        :param kwargs: additional params needed, if any
        :raises NotImplementedError:
        :return: Dict with validated params
        :rtype: Dict
        """
        raise NotImplementedError("Subclasses should implement this method")

class AbstractProviderShareHelper(AbstractBaseProviderHelper):

    def __init__(
        self, controller = None, compute_zone = None
    ):
        """Create a share provider helper

        :param controller: resource controller
        :param compute_zone: resource compute_zone
        """
        super().__init__(controller, compute_zone)
        self.config_parser: Optional[StorageConfigParser]
        self.validator: Optional[ShareValidator]
        assert self.config_parser is not None, "Subclasses must set self.config_parser"
        assert self.validator is not None, "Subclasses must set self.validator"

    def check_quotas(self, quotas_to_check: Dict = None):
        """
        check quotas

        :param quotas_to_check: dict containing staas specific quotas
        e.g. { "share.instances": 1 }
        :type quotas_to_check: Dict
        """
        if quotas_to_check:
            # only check staas specific quotas
            self.compute_zone.check_quotas(quotas_to_check, check_all=False)

    @classmethod
    def generate_root_name_from_leaf(cls, compute_zone: 'ComputeZone', leaf_name: str) -> str:
        """determine provider level resource name given "leaf" resource name. used for import.
        (and optionally for create too)

        :param compute_zone: the compute zone
        :type compute_zone: ComputeZone
        :param leaf_name: lowest level resource name
        :type leaf_name: str
        :return: provider level new resource name
        :rtype: str
        """
        return f"{leaf_name}-cz{compute_zone.oid}"

    @classmethod
    def generate_main_leaf_name(cls, base_name: str, context: ShareContext) -> str:
        """
        generate lowest level resource name.
        optionally override for custom logic
        e.g. remove unsupported characters or
        add suffixes.

        :param base_name: base name (name as it should appear on service)
        :type base_name: str
        :return: leaf level new resource name
        :rtype: str
        """
        main_site = context.get("main_site")
        if not main_site:
            raise ValueError("main site missing from context")
        return f"{main_site}-{base_name}-{id_gen(6)}"

    @classmethod
    def generate_replica_leaf_name(cls, source_leaf_name: str, config: Optional[ShareContext] = None):
        """generate lowest level resource name for replica

        :param source_name: name of the source leaf resource
        :type source_name: str
        :param context: optional context to use, defaults to None
        :type context: Dict (ShareContext), optional
        :return: leaf level new resource name
        :rtype: str
        """
        return f"replica-{source_leaf_name}"

class ShareHelperFactory(metaclass=Singleton):
    _backends: Dict[str, Type[AbstractProviderShareHelper]] = {}

    @classmethod
    def register_backend(cls, backend_name, backend_helper_class: Type[AbstractProviderShareHelper]):
        cls._backends[backend_name] = backend_helper_class

    # Overloads for better typing
    @overload
    @classmethod
    def get_backend_helper_class(cls, backend_name: Literal["ontap"]) -> Type['OntapProviderShareHelper']: ...

    #@overload
    #@classmethod
    #def get_backend_helper_class(cls, backend_name: Literal["openstack"]) -> Type[OpenstackProviderShareHelper]: ...

    @classmethod
    def get_backend_helper_class(cls, backend_name) -> Type[AbstractProviderShareHelper]:
        if backend_name not in cls._backends:
            raise ValueError(f"Unknown backend: {backend_name}")
        return cls._backends[backend_name]
