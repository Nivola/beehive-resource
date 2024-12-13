# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import logging
from beedrones.trilio.client import TrilioManager
from beehive.common.data import cache
from beehive_resource.container import Resource, AsyncResource

logger = logging.getLogger(__name__)


def get_task(task_name):
    return "%s.%s" % (__name__.replace("entity", "task"), task_name)


class OpenstackResource(AsyncResource):
    objdef = "Openstack.Resource"
    objdesc = "Openstack resources"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)
        # self.ext_obj = {}
        self.ext_obj = None

    @property
    def opsk_session(self):
        return self.container.conn.session

    @property
    def conn(self):
        try:
            return self.container.connection
        except:
            return None

    '''def get_state(self):
        """Get resoruce state.

        **Return:**

            State can be:

            * PENDING = 0
            * BUILDING =1
            * ACTIVE = 2
            * UPDATING = 3
            * ERROR = 4
            * DELETING = 5
            * DELETED = 6
            * EXPUNGING = 7
            * EXPUNGED = 8
            * UNKNOWN = 9
        """
        if self.ext_obj is None:
            res = ResourceState.state[ResourceState.UNKNOWN]
        else:
            res = ResourceState.state[self.model.state]
        return res'''

    def info(self):
        """Get info.

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
        if self.ext_obj is not None:
            info["details"] = {"admin_state_up": self.ext_obj.get("admin_state_up", None)}
        return info

    def get_openstack_manager(self, project_id=None):
        # def get_connection(self):
        """Get openstack connection specific for the project"""
        from beehive_resource.plugins.openstack.controller import OpenstackContainer

        if self.container is not None:
            openstackContainer: OpenstackContainer = self.container
            # openstackManager = openstackContainer.get_connection(projectid=self.oid)
            openstackManager = openstackContainer.get_connection(projectid=project_id)
            return openstackManager

    def get_trilio_manager(self, project_id=None):
        openstackManager = self.get_openstack_manager(project_id)

        from beedrones.trilio.client import TrilioManager

        trilio_conn: TrilioManager = self.get_container_trilio_connection(openstackManager)
        return trilio_conn

    #
    # container connection - trilio_conn: TrilioManager
    #
    def get_container_trilio_connection(self, openstackManager) -> TrilioManager:
        if self.container is not None:
            from beehive_resource.plugins.openstack.controller import OpenstackContainer

            openstackContainer: OpenstackContainer = self.container
            return openstackContainer.get_trilio_connection(openstackManager)
        return None

    #
    # openstack query
    #
    # @staticmethod
    # @cache('openstack.server.list', ttl=1800)
    # def list_server(controller, postfix, container, *args, **kvargs):
    #     remote_entities = container.conn.server.list(detail=True)
    #     return remote_entities

    @staticmethod
    @cache("openstack.aggregate.list", ttl=600)
    def list_remote_aggregate(controller, postfix, container, *args, **kvargs):
        remote_entities = container.conn.system.compute_host_aggregates()
        return remote_entities

    @staticmethod
    @cache("openstack.server.get", ttl=1800)
    def get_remote_server(controller, postfix, container, ext_id, *args, **kvargs):
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn.server.get(oid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.server.list", ttl=120)
    def list_remote_server(controller, postfix, container, ext_id, *args, **kvargs):
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn.server.list(all_tenants=True, detail=True)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return []

    @staticmethod
    @cache("openstack.securitygroup.get", ttl=1800)
    def get_remote_securitygroup(controller, postfix, container, ext_id, *args, **kvargs):
        if ext_id is None or ext_id == "":
            return {}
        try:
            remote_entity = container.conn.network.security_group.get(oid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.server.interfaces.get", ttl=1800)
    def get_remote_server_port_interfaces(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.server.get_port_interfaces(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.flavor.list", ttl=1800)
    def list_remote_flavor(controller, postfix, container, *args, **kvargs):
        remote_entities = container.conn.flavor.list(detail=True)
        return remote_entities

    @staticmethod
    @cache("openstack.flavor.get", ttl=1800)
    def get_remote_flavor(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.flavor.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.image.list", ttl=1800)
    def list_remote_image(controller, postfix, container, *args, **kvargs):
        remote_entities = container.conn.image.list(detail=True)
        return remote_entities

    @staticmethod
    @cache("openstack.image.get", ttl=1800)
    def get_remote_image(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.image.get(oid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.volume.get", ttl=1800)
    def get_remote_volume(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.volume_v3.get(oid=ext_id, *args, **kvargs)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.volume.list", ttl=120)
    def list_remote_volume(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.volume_v3.list_all(detail=True, limit=500)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return []

    @staticmethod
    @cache("openstack.volume_v3.snapshot.list", ttl=1800)
    def list_remote_volume_snapshots(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.volume_v3.snapshot.list(volume_id=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return []

    @staticmethod
    @cache("openstack.port.get", ttl=1800)
    def get_remote_port(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.network.port.get(oid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.subnet.get", ttl=1800)
    def get_remote_subnet(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.network.subnet.get(oid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.volumetype.list", ttl=1800)
    def list_remote_volume_type(controller, postfix, container, *args, **kvargs):
        try:
            remote_entities = container.conn.volume_v3.type.list()
            return remote_entities
        except:
            logger.warning("", exc_info=True)
            return []

    @staticmethod
    @cache("openstack.stack.get", ttl=1800)
    def get_remote_stack(controller, postfix, container, name, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.heat.stack.get(stack_name=name, oid=ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.share.get", ttl=1800)
    def get_remote_share(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.manila.share.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.share.get", ttl=1800)
    def get_remote_share_export_locations(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.manila.share.list_export_locations(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}

    @staticmethod
    @cache("openstack.router.get", ttl=1800)
    def get_remote_router(controller, postfix, container, ext_id, *args, **kvargs):
        try:
            remote_entity = container.conn.network.router.get(ext_id)
            return remote_entity
        except:
            logger.warning("", exc_info=True)
            return {}
