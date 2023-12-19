# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.container import AsyncResourceV3


class DummyAbstractResourceV2(AsyncResourceV3):
    objdef = "DummyV2.Resource"
    objuri = "dummyresource"
    objname = "dummyresource"
    objdesc = "Dummy resource V2"

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        container.logger.warn("I am the customize_list")
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the post_get")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        pass

    #
    # info and detail
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = super().info()
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = super().detail()
        return info

    #
    # create
    #
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """check input params before resource creation."""
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        container.logger.warn("I am the pre_create")
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return kvargs

    @staticmethod
    def post_create(controller, *args, **kvargs):
        """Post create function.

        :param controller: ApiController instance
        :param list args: positional args
        :param dict kvargs: key value args
        :return: kvargs
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        controller.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        controller.logger.warn("I am the post_create")
        controller.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return None

    #
    # import
    #
    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """check input params before resource creation."""
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        container.logger.warn("I am the pre_import")
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return kvargs

    @staticmethod
    def post_import(controller, *args, **kvargs):
        """Post import function.

        :param controller: ApiController instance
        :param list args: positional args
        :param dict kvargs: key value args
        :return: kvargs
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        controller.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        controller.logger.warn("I am the post_import")
        controller.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return None

    #
    # clone
    #
    @staticmethod
    def pre_clone(controller, container, *args, **kvargs):
        """check input params before resource creation."""
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        container.logger.warn("I am the pre_clone")
        container.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return kvargs

    @staticmethod
    def post_clone(controller, *args, **kvargs):
        """Post clone function.

        :param controller: ApiController instance
        :param list args: positional args
        :param dict kvargs: key value args
        :return: kvargs
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        controller.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        controller.logger.warn("I am the post_clone")
        controller.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return None

    #
    # patch
    #
    def pre_patch(self, *args, **kvargs):
        """check input params before resource patch."""
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the pre_patch")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return kvargs

    def post_patch(self, *args, **kvargs):
        """Post patch function. This function is used in update method.

        :param list args: positional args
        :param dict kvargs: key value args
        :return: True
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the post_patch")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return True

    #
    # update
    #
    def pre_update(self, *args, **kvargs):
        """pre update function. This function is used in update method."""
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the pre_update")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return kvargs

    def post_update(self, *args, **kvargs):
        """Post update function. This function is used in update method.

        :param list args: positional args
        :param dict kvargs: key value args
        :return: True
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the post_update")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return True

    #
    # expunge
    #
    def pre_expunge(self, *args, **kvargs):
        """check input params before resource expunge."""
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the pre_expunge")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return kvargs

    def post_expunge(self, *args, **kvargs):
        """Post expunge function. This function is used in expunge method.

        :param list args: positional args
        :param dict kvargs: key value args
        :return: kvargs
        :raises ApiManagerError: raise :class:`ApiManagerError`
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the post_expunge")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        return True
