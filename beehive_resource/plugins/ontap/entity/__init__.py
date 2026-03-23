# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from logging import getLogger
from typing import List,Dict, TYPE_CHECKING, Tuple
from beehive.common.data import cache
from beehive_resource.container import Resource, AsyncResource
if TYPE_CHECKING:
    from beehive_resource.plugins.ontap.controller import OntapNetappContainer
    from beehive_resource.controller import ResourceController

logger = getLogger(__name__)


def get_task(task_name):
    return "%s.%s" % (__name__.replace("entity", "task"), task_name)


class OntapNetappResource(AsyncResource):
    objdef = "OntapNetapp.Resource"
    objdesc = "OntapNetapp resources"

    container: 'OntapNetappContainer'

    def __init__(self, *args, **kvargs):
        super().__init__(*args, **kvargs)

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
    def get_remote_volume(
        controller: 'ResourceController',
        postfix: str,
        container: 'OntapNetappContainer',
        ext_id: str,
        short_info=False, *args, **kvargs
    ) -> Dict:
        """
        NB: because of the decorator, controller and postfix MUST be given.
        Even if unused in this function!!!
        controller e.g. self.controller
        postfix ideally must be unique. e.g. ext_id
        """
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn2.volume.get(ext_id, short_info=short_info)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.svm.get", ttl=1800)
    def get_remote_svm(controller: 'ResourceController', postfix: str, container: 'OntapNetappContainer', ext_id: str, *args, **kvargs):
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn2.svm.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.svm.get", ttl=1800)
    def get_remote_svm_by_name(controller: 'ResourceController', postfix: str, container: 'OntapNetappContainer', svm_name, *args, **kvargs):
        if svm_name is None or svm_name == "":
            return {}
        try:
            remote_entities = container.conn2.svm.list(name=svm_name)
            if len(remote_entities)!=1:
                logger.warning("Invalid number of svms found for name %s. Expected 1 but found %s",svm_name,len(remote_entities))
                return {}
            return remote_entities[0]
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    def get_remote_snapmirror_with_policy(
        controller: 'ResourceController',
        postfix: str,
        container: 'OntapNetappContainer',
        relationship_id: str
    ):
        try:
            return container.conn2.snapmirror.get(
                relationship_id=relationship_id, get_policy_detail=True
            )
        except Exception as ex:
            logger.error("Error while retrieving volume snapmirror relationship: %s", ex)
            raise Exception(
                f"Error while retrieving volume snapmirror relationship: {ex}"
            ) from ex

    @staticmethod
    @cache("ontap_netapp.snapmirror.get", ttl=1800)
    def get_remote_snapmirror(
        controller: 'ResourceController',
        postfix: str,
        container: 'OntapNetappContainer',
        source_path: str=None, destination_path: str=None,
        search_local=False, search_remote=True
    ) -> List[Dict]:
        """
        List volume snapmirror relationships given the source path.
        The source path is in the following format -> "svm_name:volume_name"

        :param container: container
        :param svm_col_volume: source path in the specified format

        NB: output differs depending on whether it's called on source or destination cluster.
        It must be called on destination cluster in order to have snapmirror state and other information

        :return: list of relationship dictionaries
        :rtype: List[Dict]
        :raises Exception: on invalid params or beedrones exception
        """
        if not source_path and not destination_path:
            logger.error("Invalid couplet svm_name:volume_name. Can't get snapmirror list."
                           "Source path: %s - Destination path: %s." % (source_path,destination_path))
            raise Exception("source_path and destination_path parameters missing")
        try:
            params = {}
            if source_path:
                params["source.path"] = source_path
            if destination_path:
                params["destination.path"] = destination_path
            snapmirror_relationships = container.conn2.snapmirror.list(search_local=search_local,search_remote=search_remote,**params)
            return snapmirror_relationships
        except Exception as ex:
            logger.error("Error while retrieving volume snapmirror relationships: %s" % ex)
            raise Exception("Error while retrieving volume snapmirror relationships") from ex

    @staticmethod
    def get_remote_snaplock_info(container: 'OntapNetappContainer', snaplock_volume_id):
        """
        given a volume uuid, fetch snaplock information.
        if volume is a snaplock volume snaplock type will be "compliance",
        otherwise "non-snaplock"
        """
        if not snaplock_volume_id:
            return {}
        try:
            info = container.conn2.volume.get_snaplock_info(snaplock_volume_id)
            return info
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    # @cache("ontap_netapp.nfs_export_policy.get", ttl=1800)
    def get_remote_nfs_export_policy(container: 'OntapNetappContainer', export_policy_id: str):
        if export_policy_id is None or export_policy_id == "":
            return {}
        try:
            remote_entity = container.conn2.protocol.get_nfs_export_policy(export_policy_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("ontap_netapp.cifs_shares.get", ttl=1800)
    def get_remote_cifs_shares(controller: 'ResourceController', postfix: str, container: 'OntapNetappContainer', volume_id: str, *args, **kvargs):
        if volume_id is None or volume_id == "":
            return {}
        try:
            # TODO check
            remote_entity = container.conn2.protocol.list_cifs_shares(**{"volume.uuid": volume_id})
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    # @cache("ontap_netapp.svm.aggregates.get", ttl=1800)
    # we probably don't want to cache these, since we are
    # usually interested in available space
    def get_remote_aggregates(container: 'OntapNetappContainer',svm_ext_id=None) -> List[Dict]:
        """
        obtain the aggregates list.
        if the svm is specified, obtain the list of aggregates
        that are usable by that specific svm.

        :param container: container
        :param svm_ext_id: svm uuid on ontap netapp

        :return: list of aggregate dictionaries
        :rtype: List[Dict]
        """
        #from beedrones.ontapp.client import OntapManager
        #container.conn = OntapManager()
        if svm_ext_id is not None:
            # get aggregates from svm details
            svm = container.conn2.svm.get(svm_ext_id)
            return svm.get("aggregates",[])
        else:
            #list all aggregates
            return container.conn2.aggregate.list_with_space()

    @staticmethod
    def get_svm_emptiest_aggregate(container: 'OntapNetappContainer',svm_ext_id) -> Tuple[Dict,int]:
        """
        return the aggregate with the most available space

        :param container: container
        :param svm_ext_id: svm uuid on ontap netapp

        :return: tuple of aggregate dict and total space available
        :rtype: Tuple[Dict,int]
        """
        svm_aggregates = OntapNetappResource.get_remote_aggregates(container,svm_ext_id)
        if len(svm_aggregates)==0:
            raise Exception("No aggregates found for the specified svm: %s" % svm_ext_id)

        # initial values
        emptiest_aggregate = None
        max_space_available = -1

        for aggregate in svm_aggregates:
            space_available = aggregate.get("space",{}).get("block_storage",{}).get("available",-1)
            if space_available > max_space_available:
                emptiest_aggregate = aggregate
                max_space_available = space_available

        if emptiest_aggregate is None:
            raise Exception("Error while determining aggregates empty space for svm %s" % svm_ext_id)

        return emptiest_aggregate, max_space_available
