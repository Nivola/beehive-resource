# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beedrones.veeam.client_veeam import VeeamManager
from beehive.common.data import cache
from beehive_resource.container import Resource, AsyncResource

logger = logging.getLogger(__name__)


class VeeamResource(AsyncResource):
    objdef = "Veeam.Resource"
    objdesc = "Veeam resources"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

    def info(self):
        """Get infos.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)

        return info

    @staticmethod
    @cache("veeam.job.get", ttl=86400)
    def get_remote_job(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            from beehive_resource.plugins.veeam.controller import VeeamContainer

            veeamContainer: VeeamContainer = container
            remote_entity = veeamContainer.conn_veeam.job.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}
