# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beehive.common.data import cache
from beehive_resource.container import Resource


logger = getLogger(__name__)


def get_task(task_name):
    return "%s.%s" % (__name__.replace("entity", "task"), task_name)


class OntapNetappResource(Resource):
    objdef = "OntapNetapp.Resource"
    objdesc = "OntapNetapp resources"

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
    @cache("ontap_netapp.volume.get", ttl=1800)
    def get_remote_volume(controller, postfix, container, ext_id, *args, **kvargs):
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn.volume.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.svm.get", ttl=1800)
    def get_remote_svm(controller, postfix, container, ext_id, *args, **kvargs):
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn.svm.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.snapmirror.get", ttl=1800)
    def get_remote_snapmirror(controller, postfix, container, svm_volume, *args, **kvargs):
        if svm_volume is None or svm_volume == "":
            return {}
        try:
            remote_entity = container.conn.snapmirror.list(**{"source.path": svm_volume})[0]
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.nfs_export_policy.get", ttl=1800)
    def get_remote_nfs_export_policy(controller, postfix, container, export_policy_id, *args, **kvargs):
        if export_policy_id is None or export_policy_id == "":
            return {}
        try:
            remote_entity = container.conn.protocol.get_nfs_export_policy(export_policy_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.cifs_shares.get", ttl=1800)
    def get_remote_cifs_shares(controller, postfix, container, volume_id, *args, **kvargs):
        if volume_id is None or volume_id == "":
            return {}
        try:
            remote_entity = container.conn.protocol.list_cifs_shares(**{"volume.uuid": volume_id})
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}
