# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from typing import TYPE_CHECKING, Optional
from beecell.simple import id_gen
from beehive_resource.plugins.provider.helper.share._base import (
    AbstractProviderShareHelper,
    ShareHelperFactory,
)
from beehive_resource.plugins.provider.helper.share.config_parsers.ontap_config_parser import OntapStorageConfigParser
from beehive_resource.plugins.provider.helper.share.validators.ontap_validator import OntapStorageValidator, OntapShareContext
if TYPE_CHECKING:
    from beehive_resource.plugins.provider.entity.zone import ComputeZone

class OntapProviderShareHelper(AbstractProviderShareHelper):

    config_parser: 'OntapStorageConfigParser'
    validator: 'OntapStorageValidator'

    def __init__(
        self, controller = None, compute_zone = None
    ):
        """Create a share provider helper

        :param controller: resource controller
        :param compute_zone: resource compute_zone
        """
        self.config_parser = OntapStorageConfigParser()
        self.validator = OntapStorageValidator(compute_zone, self.config_parser)
        super().__init__(controller, compute_zone)

    # move away TODO
    # def _determine_ontap_clients(self, mandatory=False):
    #     """convert provider client list to list of ip addresses

    #     :param mandatory: if there has to be at least one client, defaults to False
    #     :type mandatory: bool, optional
    #     :raises Exception: if mandatory=True and no clients
    #     :raises Exception: if any of the specified clients is in a unexpected site
    #     """
    #     clients = self.share_params.pop("clients", [])  # optional
    #     if mandatory and clients is None:
    #         raise Exception("At least one client must be given in parameter 'clients'")

    #     from beehive_resource.plugins.provider.entity.instance import ComputeInstance

    #     client_ip = []
    #     for client in clients:
    #         res: ComputeInstance = self.controller.get_resource(client, ComputeInstance)
    #         client_site = res.availability_zone.name
    #         if client_site != self.site_name:
    #             raise Exception(
    #                 f"Incorrect site for client {client}: expected {self.site_name} but was"
    #                 f" {client_site}"
    #             )
    #         client_ip.append(res.get_ip_address())

    #     if client_ip:
    #         self.share_params["client_ip"] = client_ip

    #

    @classmethod
    def generate_main_leaf_name(cls, base_name: str, context: OntapShareContext) -> str:
        """
        generate lowest level resource name.
        optionally override for custom logic
        e.g. remove unsupported characters or
        add suffixes.

        :param base_name: base name (name as it should appear on service)
        :type base_name: str
        :param context: share context as obtained from validation
        :type context: Dict (OntapShareContext)
        :return:
        :rtype: str
        """
        from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
        main_svm_name = context.get("main_svm_name")
        if not main_svm_name:
            raise ValueError("main svm missing from context")
        name = f"{main_svm_name}-{base_name}-{id_gen(6)}"
        return OntapNetappVolume.format_name_for_cmp(name)

    @classmethod
    def generate_replica_leaf_name(cls, source_leaf_name: str, context: Optional[OntapShareContext] = None) -> str:
        """
        generate lowest level resource name for replica.

        :param source_leaf_name: _description_
        :type source_leaf_name: str
        :param config: _description_, defaults to None
        :type config: Optional[Dict], optional, OntapShareContext
        :return: replica leaf name
        :rtype: str
        """
        from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
        name = f'dr-{source_leaf_name}'
        return  OntapNetappVolume.format_name_for_cmp(name)

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
        from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
        name = OntapNetappVolume.format_name_for_cmp(leaf_name)
        return super().generate_root_name_from_leaf(compute_zone, name)

ShareHelperFactory.register_backend("ontap", OntapProviderShareHelper)
