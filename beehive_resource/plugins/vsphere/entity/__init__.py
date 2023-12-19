# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.container import Resource, AsyncResource


def get_task(task_name):
    return "%s.%s" % (__name__.replace("entity", "task"), task_name)


class VsphereResource(AsyncResource):
    objdef = "Vsphere.Resource"
    objdesc = "Vsphere resources"

    def __init__(self, *args, **kvargs):
        """ """
        AsyncResource.__init__(self, *args, **kvargs)
        self.ext_obj = None

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
        details = info["details"]

        if self.ext_obj is not None:
            try:
                details["overall_status"] = self.ext_obj["overallStatus"]
            except:
                details["overall_status"] = self.ext_obj.overallStatus

        return info

    #
    # vsphere query
    #
    @staticmethod
    # @cache('vsphere.server.list', ttl=30)
    def list_server(controller, postfix, container, *args, **kvargs):
        remote_entitys = container.conn.server.list()
        res = []
        for remote_entity in remote_entitys:
            res.append(container.conn.server.info(remote_entity))
        return res

    # @staticmethod
    # @cache('vsphere.flavor.list', ttl=30)
    # def list_flavor(controller, postfix, container, *args, **kvargs):
    #     remote_entitys = container.conn.flavor.list()
    #     return remote_entitys
    #
    # @staticmethod
    # @cache('vsphere.image.list', ttl=30)
    # def list_image(controller, postfix, container, *args, **kvargs):
    #     remote_entitys = container.conn.image.list()
    #     return remote_entitys
    #
    # @staticmethod
    # @cache('vsphere.volume.list', ttl=30)
    # def list_volume(controller, postfix, container, *args, **kvargs):
    #     remote_entitys = container.conn.volume.list()
    #     return remote_entitys


class NsxResource(AsyncResource):
    objdef = "Vsphere.Resource"
    objdesc = "Vsphere Nsx resource"

    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

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
        details = info["details"]

        if self.ext_obj is not None:
            try:
                details["overall_status"] = getattr(self.ext_obj, "overallStatus", self.ext_obj.overallStatus)
            except:
                pass

        return info
