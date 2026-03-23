# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte
"""Helpers for paas
"""
from __future__ import annotations

from beecell.simple import random_password, bool2str, dict_get, truncate, id_gen
from beecell.types.type_dict import dict_set
from beecell.types.type_string import str2bool
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.sql_stack_v2 import SqlComputeStackV2
from beehive_resource.plugins.provider.entity.stack_v2 import (
    ComputeStackV2,
    ComputeStackAction,
)
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.image import ComputeImage
from beehive.common.task_v2 import prepare_or_run_task
from logging import getLogger
from typing import Any, Dict, Union, TYPE_CHECKING, Type, List, Set
from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

from .helper import (
    PaasHelper,
    PaasCreateHelper,
    PaasActionHelper,
    PaasImportHelper,
    PaasDeleteHelper,
    PaasUpdateHelper,
)

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController
    from beehive_resource.container import ResourceContainer, Resource


# logger = getLogger(__name__)


class PaasStackV2(SqlComputeStackV2):
    """Sql compute stack"""

    objuri = "%s/paas/%s"
    objname = "paas"
    task_path = "beehive_resource.plugins.provider.task_v2.stack_v2.StackV2Task."

    def info(self):
        """Get infos.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeStackV2.info(self)
        info["flavor"] = None
        info["vpc"] = None
        info["security_groups"] = []
        info["allocated_storage"] = 0

        objdefs = [ComputeFlavor.objdef, SecurityGroup.objdef, Vpc.objdef]
        if self.compute_instance is not None:
            info["availability_zone"] = self.compute_instance.get_main_availability_zone().small_info()
            info["allocated_storage"] = sum([b.get_size() for b in self.compute_instance.get_volumes()])

            linked = self.controller.get_directed_linked_resources_internal(
                resources=[self.compute_instance.oid],
                objdefs=objdefs,
                run_customize=False,
            )

            for resource, entities in linked.items():
                for entity in entities:
                    if isinstance(entity, ComputeFlavor):
                        info["flavor"] = entity.small_info()
                    elif isinstance(entity, SecurityGroup):
                        info["security_groups"].append(entity.small_info())
                    elif isinstance(entity, Vpc):
                        info["vpc"] = entity.small_info()

        info["listener"] = {
            "address": self.get_outputs("ResourceIP.value"),
            # "port": self.get_attribs("port"),
        }

        return info

    def detail(self):
        """Get details.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = self.info()
        return info

    @staticmethod
    def get_engines()->Set[str]:
        """gett engine list

        Returns:
            _type_: _description_
        """
        return PaasCreateHelper.get_engines()  # .engines

    def get_child_resources(self, uuid=None):
        """Get child resources

        :param uuid: action resource uuid
        :return: resources list
        :raise ApiManagerError:
        """
        resources = super().get_child_resources(uuid=uuid)
        for resource in resources:
            if isinstance(resource, ComputeInstance):
                self.compute_instance = resource
        return resources

    def get_compute_instance(self):
        """Get sql stack compute instance"""
        # get compute instance linked to stack
        resources = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], link_type="resource%", objdef=ComputeInstance.objdef
        )

    def get_runstate(self, cache=True, ttl=1800):
        """Get resource running state if exist.

        :param cache: if True get data from cache
        :param ttl: cache time to live [default=1800]
        :return: None if runstate does not exist
        """
        return SqlComputeStackV2.get_runstate(self)

    def get_credentials(self):
        """Get database credentials"""
        self.verify_permisssions("use")

        res = []
        users = self.get_attribs("users")
        # new user registration
        if users.get("administrator", None) is not None:
            for k, v in users.items():
                res.append(
                    (
                        {
                            "type": k,
                            "name": v.get("username"),
                            "password": self.controller.decrypt_data(v.get("password")),
                        }
                    )
                )
        # old user registration
        else:
            for k, v in users.items():
                res.append(
                    (
                        {
                            "type": None,
                            "name": k,
                            "password": self.controller.decrypt_data(v),
                        }
                    )
                )
        return res

    def set_credential(self, user, password):
        """Set database credential

        :param user: user name. In new style use administrator
        :param password: user password
        :return: True
        """
        self.verify_permisssions("update")

        password = self.controller.encrypt_data(password)

        users = self.get_attribs("users")
        # new user registration
        if users.get("administrator", None) is not None:
            self.set_configs(key="users.%s.password" % user, value=password)
        # old user registration
        else:
            self.set_configs(key="users.%s" % user, value=password)

        return True

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        entities = ComputeStackV2.customize_list(controller, entities, *args, **kvargs)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        get_resources = self.controller.get_directed_linked_resources_internal

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """
        pre create  set up all parameters for the asyncronus task in ordere ti create the resource.
        meta-programming the parmeters describs a set of action to be taken in order to create a dbaas
        Check input params before resource creation. This function is caolled by the  in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: id, uuid or name of the site where create the database
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.flavor: id, uuid or name of the flavor
        :param kvargs.image: id, uuid or name of the image
        :param kvargs.hypervisor: type of hypervisor
        :param kvargs.customization: customization used to install db
        :param kvargs.vpc: id, uuid or name of the vpc
        :param kvargs.subnet: subnet reference
        :param kvargs.security_group: id, uuid or name of the security group
        :param kvargs.hostname: hostname
        :param kvargs.key_name: public key name
        :param kvargs.volumeflavor: volume flavor to use in compute instance
        :param kvargs.db_root_name: The database admin account username
        :param kvargs.db_root_password: The database admin password
        :param kvargs.db_name: First app database name
        :param kvargs.db_appuser_name: First app user name
        :param kvargs.db_appuser_password: First app user password
        :param kvargs.engine: Database engine
        :param kvargs.version: Database engine version
        :param kvargs.port: database instance port [optional]
        :param kvargs.root_disk_size: root disk size [default=40GB]
        :param kvargs.data_disk_size: data disk size [default=30GB]
        :param kvargs.charset: database charset [default=latin1]
        :param kvargs.timezone: database timezone [default=Europe/Rome]
        :param kvargs.replica: enable database replica [default=False]
        :param kvargs.mysql: dictionary with mysql specific configuration params [optional]
        :param kvargs.postgresql: dictionary with postgres specific configuration params [optional]
        :param kvargs.postgresql.geo_extension: if True enable geographic extension [default=False]
        :param kvargs.oracle: dictionary with oracle specific configuration params [optional]
        :param kvargs.sqlserver: dictionary with sqlserver specific configuration params [optional]
        :param kvargs.csi_custom: flag to enable post-installation CSI setup [optional]
        :return: dict
        :raise ApiManagerError:
        """
        # helper_class = SqlCreateHelper(controller, container, *args, **kvargs).get_helper_by_engine(
        #     kvargs.get("engine")
        # )
        helper_class = PaasCreateHelper.get_helper_by_engine(kvargs.get("engine"))

        helper: PaasCreateHelper = helper_class(controller, container, *args, **kvargs)
        # example
        # helper: PostgresqlCreateHelper = helper_class(controller, container, *args, **kvargs)
        kvargs = helper.run()
        
        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used in container resource_import_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :param kvargs.configs.charset: db charset [default=latin1]
        :param kvargs.configs.timezone: db timezone [default=Europe/Rome]
        :param kvargs.configs.engine: db engine
        :param kvargs.configs.version: db engine version
        :param kvargs.configs.pwd: db passwords
        :param kvargs.configs.pwd.admin: db admin password
        :return: kvargs
        :raise ApiManagerError:
        """
        engine = dict_get(kvargs, "configs.engine")
        helper_class = PaasImportHelper.get_helper_by_engine(engine)
        helper: PaasImportHelper = helper_class(controller, container, *args, **kvargs)
        kvargs = helper.run()
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.
        Following updates are handled:
        - from standalone DB instance to master replica DB instance
        - from standalone DB instance to slave replica DB instance
        - from master replica DB instance to standalone DB instance
        - from slave replica DB instance to standalone DB instance

        :param args: custom params
        :param dict kvargs: custom params
        :return: dict
        :raise ApiManagerError:
        """
        engine = self.get_attribs(key="engine")
        helper_class = PaasUpdateHelper.get_helper_by_engine(engine)
        helper: PaasUpdateHelper = helper_class(self, *args, **kvargs)
        kvargs = helper.run()
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre update function. This function is used in update method."""
        engine = self.get_attribs(key="engine")
        helper_class = PaasDeleteHelper.get_helper_by_engine(engine)
        helper: PaasDeleteHelper = helper_class(self, engine=engine, *args, **kvargs)
        kvargs = helper.run()
        return kvargs

    def action(self, action, *args, **kvargs):
        """Execute an action

        :param action: action name
        :param args: custom params
        :param dict kvargs: custom params
        :return: dict
        :raise ApiManagerError:
        """
        engine = self.get_attribs(key="engine")
        helper_class = PaasActionHelper.get_helper_by_engine(engine)
        helper: PaasActionHelper = helper_class(self, action, *args, **kvargs)
        self.logger.debug("+++++ action - helper_class: %s - action: %s" % (helper_class, action))
        kvargs = helper.run()
        return kvargs

    def get_schemas(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        engine = self.get_attribs(key="engine")
        helper_class = PaasActionHelper.get_helper_by_engine(engine)
        helper: PaasActionHelper = helper_class(self, None)
        dbs = helper.get_dbs()
        return dbs

    def get_users(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        engine = self.get_attribs(key="engine")
        helper_class = PaasActionHelper.get_helper_by_engine(engine)
        helper: PaasActionHelper = helper_class(self, None)
        dbs = helper.get_users()
        return dbs
