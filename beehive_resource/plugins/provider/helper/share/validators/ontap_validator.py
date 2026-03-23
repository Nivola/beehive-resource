#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


from typing import Dict, List, Optional, Tuple, TYPE_CHECKING, Literal
from beehive_resource.plugins.provider.helper.share._base import ShareValidator, ShareValidationError, ShareContext
from beehive_resource.plugins.provider.helper.share.config_parsers.ontap_config_parser import OntapStorageConfigParser
if TYPE_CHECKING:
    from beehive_resource.plugins.provider.entity.zone import ComputeZone
    from beehive_resource.typing_extras.share.helper import ShareRequestParams

class OntapShareContext(ShareContext):
    share_role: Literal['main', 'dr'] # overrides parent dict annotation
    main_cluster_name: str
    main_svm_name: str
    secondary_cluster_name: Optional[str]
    secondary_svm_name: Optional[str]

class OntapValidationError(ShareValidationError):
    pass

class OntapStorageValidator(ShareValidator):
    def __init__(
        self,
        compute_zone: 'ComputeZone',
        config_parser: OntapStorageConfigParser
    ):
        self.compute_zone = compute_zone
        self.config_parser = config_parser

    def _validate_share_params_main(
        self,
        main_site_name: str,
        compliance_enabled=True,
        wanted_svm_name: Optional[str] = None,
        wanted_protocol: Optional[Literal["nfs","cifs"]] = None
    ) -> OntapShareContext:
        ## 1.0 check main site and relevant configuration
        if not main_site_name:
            raise OntapValidationError(
                "main site name unexpectedly None or empty: %s" % main_site_name
            )

        ## 1.1 check staas configuration is valid.
        # compliance configuration can be missing in specific cases (account only on one site)
        # or generally we don't check it if it wasn't requested for this specific case.
        main_cluster_name, main_svm_list, compliance_site_name = self.config_parser.check_storage_site_configuration(
            self.compute_zone,
            main_site_name,
            allow_missing_compliance_configuration=not compliance_enabled
        )

        ## 1.2 choose svm to use
        # if expected svm name or expected protocol are given, filter with those
        # otherwise return the first suitable one
        try:
            main_svm_name = self.config_parser.find_first_matching_svm(
                main_svm_list,
                wanted_protocol,
                wanted_svm_name
            )
        except Exception as ex:
            error_str = f"unable to find suitable svm (site: {main_site_name}"
            if wanted_svm_name:
                error_str += f" - wanted svm: {wanted_svm_name}"
            if wanted_protocol:
                error_str += f" - wanted protocol: {wanted_protocol}"
            error_str += f"): {ex}"
            raise OntapValidationError(error_str) from ex

        ret: OntapShareContext = {
            "share_role": "main",
            "main_site": main_site_name,
            "main_cluster_name":  main_cluster_name,
            "main_svm_name": main_svm_name,
            "compliance": compliance_enabled
        }

        # defaults
        compliance_cluster_name = None
        compliance_svm_name = None

        if compliance_enabled:
            ## 2.0 check compliance site and relevant configuration
            if not compliance_site_name:
                raise OntapValidationError(
                    "compliance mode but compliance site name None or empty: %s" % compliance_site_name
                )

            ## 2.1 check compliance staas configuration is valid
            compliance_cluster_name, compliance_svm_list, _ = self.config_parser.check_storage_site_configuration(
                self.compute_zone,
                compliance_site_name,
                allow_missing_compliance_configuration=True
            )

            ## 2.2 get peer svm for compliance zone
            peer_relationships = self.compute_zone.staas_conf.get("relationships")
            compliance_svm_name = self.config_parser.get_peer_svm(
                peer_relationships,
                main_site_name,
                compliance_site_name,
                main_svm_name,
                compliance_svm_list
            )

            ret.update({
                "secondary_site": compliance_site_name,
                "secondary_cluster_name": compliance_cluster_name,
                "secondary_svm_name": compliance_svm_name
            })

        return ret

    def _validate_share_params_replica(
        self,
        replica_site_name: str,
        source_site_name: str,
        source_svm_name: str
    ) -> ShareContext:
        if not source_site_name:
            raise OntapValidationError(
                "source site name unexpectedly None or empty: %s" % source_site_name
            )

        if not replica_site_name:
            raise OntapValidationError(
                "replica site name unexpectedly None or empty: %s" % replica_site_name
            )

        if not source_svm_name:
            raise OntapValidationError(
                "source svm name None or empty: %s" % source_svm_name
            )

        ## 1.0 check sites

        ## 1.a check replica site
        replica_cluster_name, replica_svm_list, _ = self.config_parser.check_storage_site_configuration(
            self.compute_zone,
            replica_site_name,
            allow_missing_compliance_configuration=True
        )

        ## 1.b check source site
        source_cluster_name, source_svm_list, _ = self.config_parser.check_storage_site_configuration(
            self.compute_zone,
            source_site_name
        )

        peer_relationships = self.compute_zone.staas_conf.get("relationships")

        ## 2.0 check source and replica svms

        ## 2.1 check source svm is a valid svm for the source site
        if not any(svm.get("name") == source_svm_name for svm in source_svm_list):
            raise OntapValidationError(
                "Invalid source svm %s for source site %s detected"
                % (source_svm_name, source_site_name)
            )

        # 2.2 get peer svm
        replica_svm_name = self.config_parser.get_peer_svm(
            peer_relationships,
            from_site_name=source_site_name,
            to_site_name=replica_site_name,
            from_svm_name=source_svm_name,
            valid_svm_list=replica_svm_list
        )

        ret: OntapShareContext = {
            "share_role": "dr",
            "main_site": replica_site_name,
            "main_cluster_name": replica_cluster_name,
            "main_svm_name": replica_svm_name,
            "compliance": False,
            "secondary_site": source_site_name,
            "secondary_cluster_name": source_cluster_name,
            "secondary_svm_name": source_svm_name
        }

        return ret

    def validate_share_params(
        self,
        share_role: Literal['main', 'replica'],
        share_params: 'ShareRequestParams',
        main_site_name: str,
        compliance_enabled: bool,
        secondary_site_name: Optional[str] = None,
        source_svm_name: Optional[str] = None,
        **kwargs
    ) -> OntapShareContext:
        # - site_name is "main" site for role main, and "replica" site for role replica
        # - secondary_site_name is compliance site for main, and source site for replica
        OntapStorageValidator.validate_share_role(share_role)

        wanted_svm_name = kwargs.get("wanted_svm_name")
        wanted_protocol = share_params.get("share_proto")

        if share_role=="main":
            context = self._validate_share_params_main(
                main_site_name=main_site_name,
                compliance_enabled=compliance_enabled,
                wanted_protocol=wanted_protocol,
                wanted_svm_name=wanted_svm_name
            )
        elif share_role=="replica":
            context = self._validate_share_params_replica(
                replica_site_name=main_site_name,
                source_site_name=secondary_site_name,
                source_svm_name=source_svm_name
            )


        """
            # ontap netapp volume uses "dr" instead of "replica"
            self.share_role = "dr"

        self.share_params.update({
            "cluster": context.get("main_cluster_name"),
            "svm": context.get("main_svm_name"),
            "share_role": share_role
        })

        if compliance_enabled:
            self.compliance_share_params.update({
                "snaplock_cluster": context.get("secondary_cluster_name"),
                "snaplock_svm": context.get("secondary_svm_name")
            })
            self.secondary_site_name = config.secondary_site
        """
        return context
