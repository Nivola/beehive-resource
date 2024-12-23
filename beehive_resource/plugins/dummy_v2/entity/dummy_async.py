# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.task_v2 import run_async
from beehive_resource.plugins.dummy_v2.entity import DummyAbstractResourceV2
from beehive_resource.util import (
    create_resource,
    import_resource,
    clone_resource,
    patch_resource,
    update_resource,
    expunge_resource,
)


class DummyAsyncResourceV2(DummyAbstractResourceV2):
    objdef = "DummyV2.AsyncResource"
    objuri = "asyncresource"
    objname = "asyncresource"
    objdesc = "Dummy V2 async resource"

    #
    # create
    #
    @run_async(action="insert", alias="create_resource")
    @create_resource()
    def do_create(self, **params):
        """method to execute to make custom resource operations useful to complete create

        :param params: custom params required by task
        :return:
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the do_create")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        pass

    #
    # import
    #
    @run_async(action="insert", alias="import_resource")
    @import_resource()
    def do_import(self, **params):
        """method to execute to make custom resource operations useful to complete import

        :param params: custom params required by task
        :return:
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the do_import")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        pass

    #
    # clone
    #
    @run_async(action="insert", alias="clone_resource")
    @clone_resource()
    def do_clone(self, **params):
        """method to execute to make custom resource operations useful to complete clone

        :param params: custom params required by task
        :return:
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the do_clone")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        pass

    #
    # patch
    #
    @run_async(action="delete", alias="patch_resource")
    @patch_resource()
    def do_patch(self, **params):
        """method to execute to make custom resource operations useful to complete patch

        :param params: custom params required by task
        :return:
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the do_patch")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        pass

    #
    # update
    #
    @run_async(action="delete", alias="update_resource")
    @update_resource()
    def do_update(self, **params):
        """method to execute to make custom resource operations useful to complete update

        :param params: custom params required by task
        :return:
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the do_update")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        pass

    #
    # expunge
    #
    @run_async(action="delete", alias="expunge_resource")
    @expunge_resource()
    def do_expunge(self, **params):
        """method to execute to make custom resource operations useful to complete expunge

        :param params: custom params required by task
        :return:
        """
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
        self.logger.warn("I am the do_expunge")
        self.logger.warn("$$$$$$$$$$$$$$$$$$$$$$$$")
