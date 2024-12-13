# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.container import Orchestrator


class DummyContainerV2(Orchestrator):
    """Dummy container

    :param connection: json string like {}
    """

    objdef = "DummyV2"
    objdesc = "Dummy container V2"
    objuri = "dummy"
    version = "v2.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        from .entity.dummy_sync import DummySyncResourceV2
        from .entity.dummy_async import DummyAsyncResourceV2

        self.child_classes = [
            DummySyncResourceV2,
            DummyAsyncResourceV2,
        ]

    def ping(self):
        """Ping container.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return True

    @staticmethod
    def pre_create(
        controller=None,
        type=None,
        name=None,
        desc=None,
        active=None,
        conn=None,
        **kvargs,
    ):
        """Check input params

        :param ResourceController controller: resource controller instance
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param active: container active
        :param conn: container connection
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        kvargs = {
            "type": type,
            "name": name,
            "desc": desc + " test",
            "active": active,
            "conn": {"test": {}},
        }
        return kvargs

    def pre_change(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs

    def pre_clean(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs
