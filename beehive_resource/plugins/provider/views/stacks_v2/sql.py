# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations
from marshmallow import validates_schema, ValidationError
from marshmallow.validate import OneOf
from beehive_resource.plugins.provider.entity.sql_stack_v2 import SqlComputeStackV2
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
    ApiManagerError,
)

from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema

from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController


class ProviderStack(LocalProviderApiView):
    resclass = SqlComputeStackV2
    parentclass = ComputeZone


class ListStacksRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(
        context="query",
        metadata={
            "description": 'comma separated list of compute zone id or uuid',
        },
    )


class ListStacksResponseSchema(PaginatedResponseSchema):
    sql_stacks = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
    )


class ListStacks(ProviderStack):
    definitions = {"ListStacksResponseSchema": ListStacksResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListStacksRequestSchema)
    parameters_schema = ListStacksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListStacksResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        """
        List sql_stacks

        # - filter by: tags
        # - filter by: compute_zone
        """
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        data["attribute"] = '%"stack_type":"sql_stack"%'
        data["entity_class"] = self.resclass
        resources, total = self.get_resources_reference(controller, **data)

        resp = [r.info() for r in resources]

        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **data)


class GetStackResponseSchema(Schema):
    sql_stack = fields.Nested(ResourceResponseSchema, required=True)


class GetStack(ProviderStack):
    definitions = {"GetStackResponseSchema": GetStackResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        """
        Get sql_stack
        """
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        info = res.detail()
        return {self.resclass.objname: info}


class CreateStackOracleParamsRequestSchema(Schema):
    oracle_db_name = fields.String(
        required=False,
        metadata={
            "example": 'ORCL0',
            "description": 'Oracle database instance name',
        },
    )

    oracle_partitioning_option = fields.String(
        required=False,
        metadata={
            "example": 'Y',
            "description": 'Oracle partitioning option Y/N',
        },
    )

    oracle_archivelog_mode = fields.String(
        required=False,
        metadata={
            "example": 'Y',
            "description": 'Oracle archivelog mode Y/N',
        },
    )

    oracle_os_user = fields.String(
        required=False,
        metadata={
            "example": 'ora12c',
            "description": 'Oracle os user name',
        },
    )

    oracle_charset = fields.String(
        required=False,
        metadata={
            "example": 'WE8ISO8859P1',
            "description": 'Oracle database charset',
        },
    )

    oracle_natcharset = fields.String(
        required=False,
        metadata={
            "example": 'AL16UTF16',
            "description": 'Oracle database national charset',
        },
    )

    oracle_listener_port = fields.Integer(
        required=False,
        metadata={
            "example": 1522,
            "description": 'Oracle listener port',
        },
    )

    oracle_data_disk_size = fields.Integer(
        required=False,
        load_default=None,
        metadata={
            "example": 30,
            "description": 'Size of oracle datafiles disk',
        },
    )

    oracle_bck_disk_size = fields.Integer(
        required=False,
        load_default=None,
        metadata={
            "example": '20',
            "description": 'Size of oracle recovery disk',
        },
    )

    oracle_starter_pack = fields.String(
        required=False,
        load_default="N",
        metadata={
            "description": 'oracle starter_pack',
        },
    )

    oracle_user_name = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle user_name',
        },
    )

    oracle_user_pwd = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle user_pwd',
        },
    )

    oracle_data_tbs_name = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle datatablespace name',
        },
    )

    oracle_data_tbs_size = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle datatablespace size',
        },
    )

    oracle_data_tbs_next = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle datatablespace next',
        },
    )

    oracle_idx_tbs_name = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle index tablespace name',
        },

    )

    oracle_idx_tbs_size = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle index tablespace size',
        },
    )

    oracle_idx_tbs_next = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle index tablespace next',
        },
    )

    oracle_lob_tbs_name = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle lob tablespace name',
        },
    )

    oracle_lob_tbs_size = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle lob tablespace size',
        },
    )

    oracle_lob_tbs_next = fields.String(
        required=False,
        load_default="--",
        metadata={
            "description": 'oracle lob tablespace next',
        },
    )


class CreateStackPostgresqlParamsRequestSchema(Schema):
    geo_extension = fields.Bool(
        required=False,
        load_default=True,
        allow_none=True,
        metadata={
            "example": False,
            "description": 'If True enable geographic extension',
        },
    )

    db_name = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'mydatabase',
            "description": 'Database name',
        },
    )

    encoding = fields.String(
        load_default="UTF-8",
        allow_none=True,
        metadata={
            "example": 'UTF-8',
            "description": 'Database Encoding',
        },
    )

    lc_collate = fields.String(
        load_default="en_US.UTF-8",
        metadata={
            "example": 'en_US.UTF-8',
            "description": 'Database Collate',
        },
    )

    lc_ctype = fields.String(
        required=False,
        load_default="en_US.UTF-8",
        metadata={
            "example": 'en_US.UTF-8',
            "description": 'Database Ctype',
        },
    )

    role_name = fields.String(
        required=False,
        load_default=None,
        allow_none=True,
        metadata={
            "example": 'myuser',
            "description": 'Role name',
        },
    )

    password = fields.String(
        required=False,
        load_default=None,
        allow_none=True,
        metadata={
            "example": 'mypassword',
            "description": 'Role password',
        },
    )
    
    schema_name = fields.String(
        required=False,
        load_default=None,
        allow_none=True,
        metadata={
            "example": 'myschema',
            "description": 'Schema name',
        },
    )

    extensions = fields.String(
        load_default="",
        metadata={
            "example": 'postgis',
            "description": 'comma separeted list of extensions',
        },
    )


class CreateStackParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(
        required=True,
        metadata={
            "example": '1',
            "description": 'parent compute zone id or uuid',
        },
    )

    availability_zone = fields.String(
        required=True,
        metadata={
            "example": '2995',
            "description": 'id, uuid or name of the site where create sql',
        },
    )

    multi_avz = fields.Boolean(
        load_default=True,
        required=False,
        metadata={
            "example": False,
            "description": 'Define if instance must be deployed to work in all the availability zones',
        },
    )

    flavor = fields.String(
        required=True,
        metadata={
            "example": '2995',
            "description": 'id, uuid or name of the flavor',
        },
    )

    volume_flavor = fields.String(
        required=False,
        load_default="compact",
        metadata={
            "example": 'vol.default',
            "description": 'volume size',
        },
    )

    image = fields.String(
        required=False,
        metadata={
            "example": '2995',
            "description": 'id, uuid or name of the image',
        },
    )

    vpc = fields.String(
        required=True,
        metadata={
            "example": '2995',
            "description": 'id, uuid or name of the vpc',
        },
    )

    subnet = fields.String(
        required=True,
        metadata={
            "example": '10.102.167.90/24',
            "description": 'subnet definition',
        },
    )

    security_group = fields.String(
        required=True,
        metadata={
            "example": '2995',
            "description": 'id, uuid or name of the security group',
        },
    )

    db_root_password = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": '',
            "description": 'The database admin password',
        },
    )

    key_name = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": 'Openstack public key name',
        },
    )

    version = fields.String(
        required=False,
        metadata={
            "example": '5.7',
            "description": 'Database engine version',
        },
    )

    engine = fields.String(
        required=False,
        validate=OneOf(['mysql', 'postgresql', 'oracle', 'sqlserver', 'mariadb']),
        metadata={
            "example": 'mysql',
            "description": 'Database engine',
        },
    )

    engine_configs = fields.Dict(
        required=False,
        allow_none=True,
        metadata={
            "description": 'Database engine parameters',
        },
    )

    port = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": '3306',
            "description": 'Database engine port',
        },
    )

    charset = fields.String(
        required=False,
        load_default="latin1",
        allow_none=True,
        metadata={
            "example": 'latin1',
            "description": 'Database charset',
        },
    )

    timezone = fields.String(
        required=False,
        load_default="Europe/Rome",
        allow_none=True,
        metadata={
            "example": 'Europe/Rome',
            "description": 'Database timezone',
        },
    )

    root_disk_size = fields.Integer(
        required=False,
        load_default=40,
        metadata={
            "example": 40,
            "description": 'Size of root disk',
        },
    )

    data_disk_size = fields.Integer(
        required=False,
        load_default=30,
        metadata={
            "example": 30,
            "description": 'Size of data disk',
        },
    )

    resolve = fields.Boolean(
        load_default=True,
        required=False,
        metadata={
            "example": False,
            "description": 'Define if stack instances must registered on the availability_zone dns zone',
        },
    )

    hostname = fields.String(
        required=False,
        metadata={
            "example": 'server1',
            "description": 'server hostname',
        },
    )

    host_group = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'default',
            "description": 'define the optional host group the db instance belongs to',
        },
    )

    customization = fields.String(
        required=False,
        metadata={
            "example": 'mysql',
            "description": 'id, uuid or name of the customization',
        },
    )

    hypervisor = fields.String(
        required=False,
        metadata={
            "example": 'openstack',
            "description": 'type of the hypervisor',
        },
    )

    csi_custom = fields.Boolean(
        required=False,
        load_default=False,
        allow_none=True,
        metadata={
            "example": False,
            "description": 'flag to enable post-installation CSI setup',
        },
    )

    replica = fields.Boolean(
        required=False,
        load_default=False,
        allow_none=True,
        metadata={
            "example": False,
            "description": 'enable database replica',
        },
    )

    replica_arch_type = fields.String(
        required=False,
        validate=OneOf(['MS', 'MM']),
        allow_none=True,
        metadata={
            "example": 'MS',
            "description": (
                'defines the method use to store data in a database replication \\ system, master-slave or'
                'multi-master'
            ),
        },
    )

    replica_role = fields.String(
        required=False,
        validate=OneOf(['M', 'S']),
        allow_none=True,
        metadata={
            "example": 'S',
            "description": (
                'defines the role of the database server in a database replication \\ system, master or slave'
            ),
        },
    )

    replica_sync_type = fields.String(
        required=False,
        validate=OneOf(['async', 'semisync']),
        allow_none=True,
        metadata={
            "example": 'async',
            "description": 'defines the way of writing data to the replica, \\ async or semisync',
        },
    )

    replica_master = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": '116850',
            "description": 'id, uuid or name \\ of master server in a database replication system',
        },
    )

    replica_username = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": 'The user name of the \\ replica',
        },
    )

    replica_password = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": 'Password for replica \\ user',
        },
    )

    db_monitor = fields.Boolean(
        required=False,
        metadata={
            "description": 'Enable database monitoring',
        },
    )

    lvm_vg_data = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'vg_data',
            "description": 'LVM volume group for \\ data storage',
        },
    )

    lvm_vg_backup = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'vg_backup',
            "description": 'LVM volume group \\ for backup storage',
        },
    )

    lvm_lv_data = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'lv_fsdata',
            "description": 'LVM logical volume \\ for data storage',
        },
    )

    lvm_lv_backup = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'lv_fsbackup',
            "description": 'LVM logical \\ volume for backup storage',
        },
    )

    data_dir = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": '/data',
            "description": 'Mount point for data \\ storage',
        },
    )

    backup_dir = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": '/bck',
            "description": 'Mount point for backup \\ storage',
        },
    )

    oracle_params = fields.Nested(
        CreateStackOracleParamsRequestSchema,
        many=False,
        required=False,
        allow_none=True,
        metadata={
            "description": 'Configure Oracle database options',
        },
    )

    postgresql_params = fields.Nested(
        CreateStackPostgresqlParamsRequestSchema,
        many=False,
        required=False,
        allow_none=True,
        metadata={
            "description": 'Configure Postgres database options',
        },
    )

    @validates_schema
    def validate_parameters(self, data, *args, **kvargs):
        pass


class CreateStackRequestSchema(Schema):
    sql_stack = fields.Nested(
        CreateStackParamRequestSchema,
        context="body",
    )


class CreateStackBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateStackRequestSchema,
        context="body",
    )


class CreateStack(ProviderStack):
    summary = "Create sql stack"
    description = "Create sql stack"

    definitions = {
        "CreateStackRequestSchema": CreateStackRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateStackBodyRequestSchema)
    parameters_schema = CreateStackRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller: ResourceController, data: dict, *args, **kwargs):
        # move engine_config parameters into attribute in order to store info in model
        engine_configs: dict = data["sql_stack"].get("engine_configs", {})
        attribute: dict = data.get("attribute", {})
        attribute.update({"engine_configs": engine_configs})
        controller.logger.debug(f"!!!GADU data {data}")
        # data["attribute"]= attribute
        res = self.create_resource(controller, data)
        return res


class UpdateStackParamRequestSchema(UpdateProviderResourceRequestSchema):
    remove_replica = fields.Boolean(
        required=False,
        load_default=False,
        allow_none=True,
        metadata={
            "example": False,
            "description": 'if true, promotes a master or slave instance to a standalone DB \\ instance',
        },
    )

    replica_arch_type = fields.String(
        required=False,
        validate=OneOf(['MS', 'MM']),
        load_default="MS",
        allow_none=True,
        metadata={
            "example": 'MS',
            "description": (
                'defines the method use to store data in a database \\ replication system, master-slave or'
                'multi-master'
            ),
        },
    )

    replica_role = fields.String(
        required=False,
        validate=OneOf(['M', 'S']),
        load_default="S",
        allow_none=True,
        metadata={
            "example": 'S',
            "description": (
                'defines the role of the database server in a database replication \\ system, master or slave'
            ),
        },
    )

    replica_sync_type = fields.String(
        required=False,
        validate=OneOf(['async', 'semisync']),
        load_default="async",
        allow_none=True,
        metadata={
            "example": 'async',
            "description": 'defines the way of writing data \\ to the replica, async or semisync',
        },
    )

    replica_master = fields.String(
        required=False,
        load_default=None,
        allow_none=True,
        metadata={
            "example": '116850',
            "description": 'id, uuid or name of master server in a database replication system',
        },
    )

    replica_username = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": 'The user name of the \\ replica',
        },
    )

    replica_password = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": 'Password for replica \\ user',
        },
    )


class UpdateStackRequestSchema(Schema):
    sql_stack = fields.Nested(UpdateStackParamRequestSchema)


class UpdateStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateStackRequestSchema, context="body")


class UpdateStack(ProviderStack):
    definitions = {
        "UpdateStackRequestSchema": UpdateStackRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateStackBodyRequestSchema)
    parameters_schema = UpdateStackRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update sql_stack
        """
        return self.update_resource(controller, oid, data)


class ActionStackParamsStopRequestSchema(Schema):
    force = fields.Boolean(
        required=False,
        allow_none=True,
        load_default=False,
        metadata={
            "description": (
                'Force database instance to stop, i.e shut down the vm without first stopping the database engine'
            ),
        },
    )


class ActionStackParamsCreateDbRequestSchema(Schema):
    db_name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test',
            "description": 'Database name',
        },
    )

    charset = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'latin1',
            "description": 'Database charset',
        },
    )


class ActionStackParamsDeleteDbRequestSchema(Schema):
    db_name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test',
            "description": 'Database name',
        },
    )


class ActionStackParamsGetUsersRequestSchema(Schema):
    host = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test_usr',
            "description": 'Host name',
        },
    )

    user = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test!1234',
            "description": 'User name',
        },
    )

    privileges = fields.Dict(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test!1234',
            "description": 'User privileges',
        },
    )


class ActionStackParamsCreateUserRequestSchema(Schema):
    name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test_usr',
            "description": 'User name',
        },
    )

    password = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test!1234',
            "description": 'User password',
        },
    )


class ActionStackParamsDeleteUserRequestSchema(Schema):
    name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test_usr',
            "description": 'User name',
        },
    )

    # params below are specific for PostgreSQL only
    force = fields.Boolean(
        required=False,
        load_default=False,
        metadata={
            "description": 'Force user deletion',
        },
    )


class ActionStackParamsGrantPrivilegesRequestSchema(Schema):
    privileges = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'SELECT,INSERT,DELETE,UPDATE',
            "description": 'Privileges string in the format priv1,priv2,...,privN',
        },
    )

    db_name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test',
            "description": 'Database name',
        },
    )

    usr_name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test_usr',
            "description": 'User name',
        },
    )


class ActionStackParamsRevokePrivilegesRequestSchema(Schema):
    privileges = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'DELETE,UPDATE',
            "description": 'Privileges string in the format priv1,priv2,...,privN',
        },
    )

    db_name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test',
            "description": 'Database name',
        },
    )

    usr_name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test_usr',
            "description": 'User name',
        },
    )


class ActionStackParamsChangePasswordRequestSchema(Schema):
    name = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test_usr',
            "description": 'User name',
        },
    )

    new_password = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'test!5678',
            "description": 'New user password',
        },
    )


class ActionStackParamsSecurityGroupRequestSchema(Schema):
    security_group = fields.String(
        required=True,
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
            "description": 'Security group uuid',
        },
    )


class ActionStackParamsSetFlavorRequestSchema(Schema):
    flavor = fields.String(
        required=True,
        metadata={
            "example": 'vm.s1.small',
            "description": 'flavor uuid or name',
        },
    )


class ActionStackParamsEnableMonitoringRequestSchema(Schema):
    host_group = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'Csi.Datacenter.test',
            "description": (
                'the account hostgroup in the form Organization.Division.Account the compute instance to monitor'
                'belongs to'
            ),
        },
    )

    templates = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'db,linux',
            "description": 'comma separated list of zabbix agent template name',
        },
    )


class ActionStackParamsDisableMonitoringRequestSchema(Schema):
    deregister_only = fields.Boolean(
        required=False,
        allow_none=True,
        metadata={
            "description": 'deregister_only on zabbix, not disinstall agent',
        },
    )


class ActionStackParamsEnableLoggingRequestSchema(Schema):
    host_group = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'Csi.Datacenter.test',
            "description": (
                'the account hostgroup in the form Organization.Division.Account the compute instance to monitor'
                'belongs to'
            ),
        },
    )

    files = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'db,linux',
            "description": 'comma separated list of files to capture',
        },
    )

    logstash_port = fields.Integer(
        required=False,
        allow_none=True,
        load_default=5044,
        metadata={
            "example": 5044,
            "description": 'logstash pipeline port',
        },
    )


class ActionStackParamsDisableLoggingRequestSchema(Schema):
    pass


class ActionStackParamsEnableLogModuleRequestSchema(Schema):
    module = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'apache, mysql',
            "description": 'comma separated list of files to capture',
        },
    )

    module_params = fields.Dict(allow_none=True)


class ActionStackParamsDisableLogModuleRequestSchema(Schema):
    module = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'apache, mysql',
            "description": 'comma separated list of files to capture',
        },
    )

    module_params = fields.Dict(allow_none=True)


class ActionStackParamsEnableMailxRequestSchema(Schema):
    relayhost = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'xxx.csi.it',
            "description": (
                'remote mail server Postfix sends outgoing messages to, instead of trying to deliver them directly to'
                'their destination'
            ),
        },
    )


class ActionStackParamsHaproxyRegisterRequestSchema(Schema):
    port_ini = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": '10100',
            "description": 'First port number (included) in haproxy range of ports that client can connect to',
        },
    )

    port_fin = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": '10999',
            "description": 'Last port number (excluded) in haproxy range of ports that client can connect to',
        },
    )


class ActionStackParamsResizeRequestSchema(Schema):
    new_data_disk_size = fields.Integer(
        required=True,
        allow_none=False,
        metadata={
            "example": 30,
            "description": 'The total storage space of data disk after resize',
        },
    )


class ActionStackParamsRequestSchema(Schema):
    stop = fields.Nested(
        ActionStackParamsStopRequestSchema,
        metadata={
            "description": 'Stop database server',
        },
    )

    start = fields.Boolean(
        metadata={
            "description": 'Start database server',
        },
    )

    restart = fields.Boolean(
        metadata={
            "description": 'Restart database server',
        },
    )

    add_security_group = fields.Nested(
        ActionStackParamsSecurityGroupRequestSchema,
        metadata={
            "description": 'Add security group to database server',
        },
    )

    del_security_group = fields.Nested(
        ActionStackParamsSecurityGroupRequestSchema,
        metadata={
            "description": 'Remove security group from database server',
        },
    )

    set_flavor = fields.Nested(
        ActionStackParamsSetFlavorRequestSchema,
        metadata={
            "description": 'Set flavor to database server',
        },
    )

    get_dbs = fields.Boolean(
        metadata={
            "description": 'List databases',
        },
    )

    add_db = fields.Nested(
        ActionStackParamsCreateDbRequestSchema,
        metadata={
            "description": (
                'Create database and schema. For postgres use db1 to create database db1 and db1.schema1 to create'
                'schema schema1 in database db1'
            ),
        },
    )

    drop_db = fields.Nested(
        ActionStackParamsDeleteDbRequestSchema,
        metadata={
            "description": (
                'Delete database and schema. For postgres use db1 to remove database db1 and db1.schema1 to remove'
                'schema schema1 in database db1'
            ),
        },
    )

    get_users = fields.Boolean(
        metadata={
            "description": 'List users',
        },
    )

    add_user = fields.Nested(
        ActionStackParamsCreateUserRequestSchema,
        metadata={
            "description": 'Create user',
        },
    )

    drop_user = fields.Nested(
        ActionStackParamsDeleteUserRequestSchema,
        metadata={
            "description": 'Delete user',
        },
    )

    grant_privs = fields.Nested(
        ActionStackParamsGrantPrivilegesRequestSchema,
        metadata={
            "description": 'Assign privileges to user',
        },
    )

    revoke_privs = fields.Nested(
        ActionStackParamsRevokePrivilegesRequestSchema,
        metadata={
            "description": 'Revoke privileges to user',
        },
    )

    change_pwd = fields.Nested(
        ActionStackParamsChangePasswordRequestSchema,
        metadata={
            "description": 'Change user password',
        },
    )

    install_extensions = fields.Dict(
        metadata={
            "description": 'Install extensions on database server',
        },
    )

    enable_monitoring = fields.Nested(
        ActionStackParamsEnableMonitoringRequestSchema,
        metadata={
            "description": 'Enable resources monitoring over sql stack',
        },
    )

    disable_monitoring = fields.Nested(
        ActionStackParamsDisableMonitoringRequestSchema,
        metadata={
            "description": 'Disable resources monitoring over sql stack',
        },
    )

    enable_logging = fields.Nested(
        ActionStackParamsEnableLoggingRequestSchema,
        metadata={
            "description": 'Enable log forwarding over sql stack',
        },
    )

    disable_logging = fields.Nested(
        ActionStackParamsDisableLoggingRequestSchema,
        metadata={
            "description": 'Disable log forwarding over sql stack',
        },
    )

    enable_log_module = fields.Nested(
        ActionStackParamsEnableLogModuleRequestSchema,
        metadata={
            "description": 'enable log module over compute instance',
        },
    )

    disable_log_module = fields.Nested(
        ActionStackParamsDisableLogModuleRequestSchema,
        metadata={
            "description": 'disable log module over compute instance',
        },
    )

    enable_mailx = fields.Nested(
        ActionStackParamsEnableMailxRequestSchema,
        metadata={
            "description": 'Enable mailx over sql stack',
        },
    )

    haproxy_register = fields.Nested(
        ActionStackParamsHaproxyRegisterRequestSchema,
        metadata={
            "description": 'Register database server on haproxy',
        },
    )

    haproxy_deregister = fields.Boolean(
        metadata={
            "description": 'Deregister database server from haproxy',
        },
    )

    resize = fields.Nested(
        ActionStackParamsResizeRequestSchema,
        metadata={
            "description": 'Resize database storage capacity',
        },
    )


class ActionStackRequestSchema(Schema):
    action = fields.Nested(
        ActionStackParamsRequestSchema,
        required=True,
    )


class ActionStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        ActionStackRequestSchema,
        context="body",
    )


class ActionStackResponseSchema(Schema):
    dbs = fields.List(
        fields.Dict,
        required=False,
        dump_default={},
        metadata={
            "description": 'sql stack database list',
        },
    )

    users = fields.List(
        fields.Dict,
        required=False,
        dump_default={},
        metadata={
            "description": 'sql stack user list',
        },
    )


class ActionStack(ProviderStack):
    definitions = {
        "ActionStackRequestSchema": ActionStackRequestSchema,
        "ActionStackResponseSchema": ActionStackResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ActionStackBodyRequestSchema)
    parameters_schema = ActionStackRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
            200: {"description": "success", "schema": ActionStackResponseSchema},
        }
    )

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Run sql_stack action
        """
        resource: SqlComputeStackV2 = self.get_resource_reference(controller, oid)
        actions = data.get("action")
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {"param": params}

        if action in resource.actions:
            self.logger.debug("+++++ put - action: %s" % action)
            if action == "get_dbs":
                res = {"dbs": resource.get_schemas()}
            elif action == "get_users":
                res = {"users": resource.get_users()}
            else:
                res = resource.action(action, **params)
        else:
            raise ApiManagerError("Stack action %s not supported" % action)

        return res


class DeleteStack(ProviderStack):
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller: ResourceController, data, oid, *args, **kwargs):
        """
        Delete sql_stack
        """
        res = self.expunge_resource(controller, oid)
        return res


class GetStackCredentialsResponseSchema(Schema):
    sql_stack_credentials = fields.List(fields.Dict, required=True)


class GetStackCredentials(ProviderStack):
    summary = "Get sql stack credentials"
    description = "Get sql stack credentials"
    definitions = {"GetStackCredentialsResponseSchema": GetStackCredentialsResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get sql_stack credential
        """
        resource = self.get_resource_reference(controller, oid)
        users = resource.get_credentials()
        return {"sql_stack_credentials": users}


class SetStackCredentialsRequestSchema(Schema):
    user = fields.String(
        required=True,
        metadata={
            "example": 'root',
            "description": 'User name',
        },
    )

    password = fields.String(
        required=True,
        metadata={
            "example": 'mypass',
            "description": 'User password',
        },
    )


class SetStackCredentials(ProviderStack):
    summary = "Set sql stack credential"
    description = "Set sql stack credential"
    definitions = {"SetStackCredentialsRequestSchema": SetStackCredentialsRequestSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "success"}})

    def put(self, controller, data, oid, *args, **kwargs):
        resource = self.get_resource_reference(controller, oid)
        res = resource.set_credential(**data)
        return res, 204


class GetStackEngineResponseSchema(Schema):
    engine = fields.String(
        required=True,
        metadata={
            "example": 'mysql',
            "description": 'Engine name',
        },
    )

    version = fields.String(
        required=True,
        metadata={
            "example": '5.7',
            "description": 'Engine version',
        },
    )


class GetStackEnginesResponseSchema(Schema):
    engines = fields.Nested(GetStackEngineResponseSchema, required=True)


class GetStackEngines(ProviderStack):
    definitions = {"GetStackEnginesResponseSchema": GetStackEnginesResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        Get sql_stack engines
        """
        engines = SqlComputeStackV2.get_engines()
        return {"engines": engines}


class GetStackBackupJobResponseSchema(Schema):
    id = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job id',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job name',
        },
    )

    created = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job creation date',
        },
    )

    updated = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job update date',
        },
    )

    error = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job error',
        },
    )

    usage = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job storage usage',
        },
    )

    status = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job status',
        },
    )

    type = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job type',
        },
    )

    schedule = fields.Dict(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job schedule',
        },
    )


class GetStackBackupRestorePointResponseSchema(Schema):
    id = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'restore point id',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'restore point name',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'restore point description',
        },
    )

    created = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'restore point creation date',
        },
    )

    type = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'restore point type',
        },
    )

    status = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'restore point status',
        },
    )


class GetStackBackupResponseSchema(Schema):
    job = fields.Nested(GetStackBackupJobResponseSchema, required=True, many=False, allow_none=True)
    restore_points = fields.Nested(
        GetStackBackupRestorePointResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )

    restore_point_total = fields.Int(
        required=True,
        allow_none=True,
        metadata={
            "example": '1',
            "description": 'total number of restore point',
        },
    )


class GetStackBackupRestorePointsRequestSchema(Schema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'oid',
        },
    )

    size = fields.Int(
        required=False,
        load_default=20,
        context="query",
        metadata={
            "description": 'size',
        },
    )

    page = fields.Integer(
        required=False,
        load_default=0,
        context="query",
        metadata={
            "description": 'page',
        },
    )


class GetStackBackup(ProviderStack):
    summary = "Get stack backup info"
    description = "Get stack backup info"

    definitions = {
        "GetStackBackupRestorePointsRequestSchema": GetStackBackupRestorePointsRequestSchema,
        "GetStackBackupResponseSchema": GetStackBackupResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetStackBackupRestorePointsRequestSchema)
    parameters_schema = GetStackBackupRestorePointsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackBackupResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        self.logger.debug("+++++ AAA - data: %s" % data)
        size = data.get("size")
        page = int(data.get("page"))

        from beehive_resource.plugins.provider.entity.stack import ComputeStack

        # computeStack: ComputeStack = self.get_resource_reference(controller, oid)
        computeStack: SqlComputeStackV2 = self.get_resource_reference(controller, oid)
        # res = computeStack.get_physical_backup_status(size, page)
        res = computeStack.get_compute_instance().get_physical_backup_status(size, page)
        return res


class SqlStackV2ProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: compute_zone
            ("%s/sql_stacks" % base, "GET", ListStacks, {}),
            ("%s/sql_stacks/<oid>" % base, "GET", GetStack, {}),
            # ('%s/sql_stacks/<oid>/resources' % base, 'GET', GetStackResources, {}),
            ("%s/sql_stacks" % base, "POST", CreateStack, {}),
            ("%s/sql_stacks/<oid>" % base, "PUT", UpdateStack, {}),
            ("%s/sql_stacks/<oid>/action" % base, "PUT", ActionStack, {}),
            ("%s/sql_stacks/<oid>" % base, "DELETE", DeleteStack, {}),
            ("%s/sql_stacks/<oid>/credentials" % base, "GET", GetStackCredentials, {}),
            ("%s/sql_stacks/<oid>/credentials" % base, "PUT", SetStackCredentials, {}),
            ("%s/sql_stacks/engines" % base, "GET", GetStackEngines, {}),
            (
                "%s/sql_stacks/<oid>/backup/restore_points" % base,
                "GET",
                GetStackBackup,
                {},
            ),
        ]
        kwargs["version"] = "v2.0"
        ProviderAPI.register_api(module, rules, **kwargs)
