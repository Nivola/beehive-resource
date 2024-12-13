# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

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


class ProviderStack(LocalProviderApiView):
    resclass = SqlComputeStackV2
    parentclass = ComputeZone


class ListStacksRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone id or uuid")


class ListStacksResponseSchema(PaginatedResponseSchema):
    sql_stacks = fields.Nested(ResourceResponseSchema, many=True, required=True)


class ListStacks(ProviderStack):
    definitions = {
        "ListStacksResponseSchema": ListStacksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListStacksRequestSchema)
    parameters_schema = ListStacksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListStacksResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List sql_stacks
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
    definitions = {
        "GetStackResponseSchema": GetStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get sql_stack
        Get sql_stack
        """
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        info = res.detail()
        return {self.resclass.objname: info}


# class GetStackResourcesResponseSchema(Schema):
#     sql_stack_resources = fields.List(fields.Dict(), required=True)
#
#
# class GetStackResources(ProviderStack):
#     definitions = {
#         'GetStackResourcesResponseSchema': GetStackResourcesResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': GetStackResponseSchema
#         }
#     })
#
#     def get(self, controller, data, oid, *args, **kwargs):
#         """
#         Get sql_stack resources
#         Get sql_stack resources
#         """
#         resource = self.get_resource_reference(controller, oid)
#         resources = resource.resources()
#         return {self.resclass.objname+'_resources': resources, 'count': len(resources)}


class CreateStackOracleParamsRequestSchema(Schema):
    oracle_db_name = fields.String(required=False, example="ORCL0", description="Oracle database instance name")
    oracle_partitioning_option = fields.String(
        required=False, example="Y", description="Oracle partitioning option Y/N"
    )
    oracle_archivelog_mode = fields.String(required=False, example="Y", description="Oracle archivelog mode Y/N")
    oracle_os_user = fields.String(required=False, example="ora12c", description="Oracle os user name")
    oracle_charset = fields.String(required=False, example="WE8ISO8859P1", description="Oracle database charset")
    oracle_natcharset = fields.String(
        required=False,
        example="AL16UTF16",
        description="Oracle database national charset",
    )
    oracle_listener_port = fields.Integer(required=False, example=1522, description="Oracle listener port")
    oracle_data_disk_size = fields.Integer(
        required=False,
        example=30,
        missing=None,
        description="Size of oracle datafiles disk",
    )
    oracle_bck_disk_size = fields.Integer(
        required=False,
        example=20,
        missing=None,
        description="Size of oracle recovery disk",
    )


class CreateStackPostgresqlParamsRequestSchema(Schema):
    geo_extension = fields.Bool(
        required=False, example=False, missing=True, allow_none=True, description="If True enable geographic extension"
    )
    db_name = fields.String(required=False, example="mydatabase", allow_none=True, description="Database name")
    encoding = fields.String(
        default="UTF-8", missing="UTF-8", example="UTF-8", allow_none=True, description="Database Encoding"
    )
    lc_collate = fields.String(
        default="en_US.UTF-8", missing="en_US.UTF-8", example="en_US.UTF-8", description="Database Collate"
    )
    lc_ctype = fields.String(
        required=False,
        default="en_US.UTF-8",
        missing="en_US.UTF-8",
        example="en_US.UTF-8",
        description="Database Ctype",
    )
    role_name = fields.String(required=False, missing=None, example="myuser", allow_none=True, description="Role name")
    password = fields.String(
        required=False, missing=None, example="mypassword", allow_none=True, description="Role password"
    )
    schema_name = fields.String(
        required=False, missing=None, example="myschema", allow_none=True, description="Schema name"
    )
    extensions = fields.String(
        default="", missing="", example="postgis", description="comma separeted list of extensions"
    )


class CreateStackParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where create sql",
    )
    multi_avz = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if instance must be deployed to work in all the availability zones",
    )
    flavor = fields.String(required=True, example="2995", description="id, uuid or name of the flavor")
    volume_flavor = fields.String(
        required=False,
        example="vol.default",
        missing="compact",
        description="volume size",
    )
    image = fields.String(required=False, example="2995", description="id, uuid or name of the image")
    vpc = fields.String(required=True, example="2995", description="id, uuid or name of the vpc")
    subnet = fields.String(required=True, example="10.102.167.90/24", description="subnet definition")
    security_group = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the security group",
    )
    # db_name = fields.String(required=True, example='dbtest', description='First app database name')
    # db_appuser_name = fields.String(required=True, example='usertest', description='First app user name')
    # db_appuser_password = fields.String(required=True, example='', description='First app user password')
    # db_root_name = fields.String(required=False, example='root', missing='root',
    #                              description='The database admin account username')
    db_root_password = fields.String(
        required=False,
        example="",
        description="The database admin password",
        allow_none=True,
    )
    key_name = fields.String(
        required=False,
        example="",
        allow_none=True,
        description="Openstack public key name",
    )
    version = fields.String(required=False, example="5.7", description="Database engine version")
    engine = fields.String(
        required=False,
        validate=OneOf(["mysql", "postgresql", "oracle", "sqlserver", "mariadb"]),
        example="mysql",
        description="Database engine",
    )
    port = fields.String(required=False, example=3306, missing=None, description="Database engine port")
    charset = fields.String(
        required=False,
        example="latin1",
        missing="latin1",
        allow_none=True,
        description="Database charset",
    )
    timezone = fields.String(
        required=False,
        example="Europe/Rome",
        missing="Europe/Rome",
        allow_none=True,
        description="Database timezone",
    )
    root_disk_size = fields.Integer(required=False, example=40, missing=40, description="Size of root disk")
    data_disk_size = fields.Integer(required=False, example=30, missing=30, description="Size of data disk")
    resolve = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if stack instances must registered on the availability_zone dns zone",
    )
    hostname = fields.String(required=False, example="server1", description="server hostname")
    host_group = fields.String(
        required=False,
        allow_none=True,
        example="default",
        description="define the optional " "host group the db instance belongs to",
    )
    customization = fields.String(
        required=False,
        example="mysql",
        description="id, uuid or name of the customization",
    )
    hypervisor = fields.String(required=False, example="openstack", description="type of the hypervisor")
    csi_custom = fields.Boolean(
        required=False,
        example=False,
        missing=False,
        allow_none=True,
        description="flag to enable post-installation CSI setup",
    )
    replica = fields.Boolean(
        required=False,
        example=False,
        missing=False,
        allow_none=True,
        description="enable database replica",
    )
    replica_arch_type = fields.String(
        required=False,
        validate=OneOf(["MS", "MM"]),
        example="MS",
        allow_none=True,
        description="defines the method use to store data in a database replication \
                                      system, master-slave or multi-master",
    )
    replica_role = fields.String(
        required=False,
        validate=OneOf(["M", "S"]),
        example="S",
        allow_none=True,
        description="defines the role of the database server in a database replication \
                                 system, master or slave",
    )
    replica_sync_type = fields.String(
        required=False,
        validate=OneOf(["async", "semisync"]),
        example="async",
        allow_none=True,
        description="defines the way of writing data to the replica, \
                                      async or semisync",
    )
    replica_master = fields.String(
        required=False,
        example="116850",
        allow_none=True,
        description="id, uuid or name \
                                   of master server in a database replication system",
    )
    replica_username = fields.String(
        required=False,
        example="",
        allow_none=True,
        description="The user name of the \
                                     replica",
    )
    replica_password = fields.String(
        required=False,
        example="",
        allow_none=True,
        description="Password for replica \
                                     user",
    )
    db_monitor = fields.Boolean(required=False, default=True, description="Enable database monitoring")
    lvm_vg_data = fields.String(
        required=False,
        example="vg_data",
        allow_none=True,
        description="LVM volume group for \
                                data storage",
    )
    lvm_vg_backup = fields.String(
        required=False,
        example="vg_backup",
        allow_none=True,
        description="LVM volume group \
                                  for backup storage",
    )
    lvm_lv_data = fields.String(
        required=False,
        example="lv_fsdata",
        allow_none=True,
        description="LVM logical volume \
                                for data storage",
    )
    lvm_lv_backup = fields.String(
        required=False,
        example="lv_fsbackup",
        allow_none=True,
        description="LVM logical \
                                  volume for backup storage",
    )
    data_dir = fields.String(
        required=False,
        example="/data",
        allow_none=True,
        description="Mount point for data \
                             storage",
    )
    backup_dir = fields.String(
        required=False,
        example="/bck",
        allow_none=True,
        description="Mount point for backup \
                               storage",
    )
    oracle_params = fields.Nested(
        CreateStackOracleParamsRequestSchema,
        many=False,
        required=False,
        allow_none=True,
        description="Configure Oracle database options",
    )
    postgresql_params = fields.Nested(
        CreateStackPostgresqlParamsRequestSchema,
        many=False,
        required=False,
        allow_none=True,
        description="Configure Postgres database options",
    )

    @validates_schema
    def validate_parameters(self, data, *args, **kvargs):
        pass
        # valid_engine = SqlComputeStackV2.engine.keys()
        # if data.get('engine') not in valid_engine:
        #     raise ValidationError('Supported engines are %s' % valid_engine)
        # valid_versions = SqlComputeStackV2.get_versions(data.get('engine'))
        # if data.get('version') not in valid_versions:
        #     raise ValidationError('Supported %s engine versions are %s' % (data.get('engine'), valid_versions))
        # if 'geo_extension' in data and data.get('engine') != 'postgres':
        #     raise ValidationError('geo_extension is supported only by engine postgres')


class CreateStackRequestSchema(Schema):
    sql_stack = fields.Nested(CreateStackParamRequestSchema, context="body")


class CreateStackBodyRequestSchema(Schema):
    body = fields.Nested(CreateStackRequestSchema, context="body")


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

    def post(self, controller, data, *args, **kwargs):
        res = self.create_resource(controller, data)
        return res


class UpdateStackParamRequestSchema(UpdateProviderResourceRequestSchema):
    remove_replica = fields.Boolean(
        required=False,
        example=False,
        missing=False,
        allow_none=True,
        description="if true, promotes a master or slave instance to a standalone DB \
                                    instance",
    )
    replica_arch_type = fields.String(
        required=False,
        validate=OneOf(["MS", "MM"]),
        example="MS",
        missing="MS",
        allow_none=True,
        description="defines the method use to store data in a database \
                                      replication system, master-slave or multi-master",
    )
    replica_role = fields.String(
        required=False,
        validate=OneOf(["M", "S"]),
        example="S",
        missing="S",
        allow_none=True,
        description="defines the role of the database server in a database replication \
                                 system, master or slave",
    )
    replica_sync_type = fields.String(
        required=False,
        validate=OneOf(["async", "semisync"]),
        example="async",
        missing="async",
        allow_none=True,
        description="defines the way of writing data \
                                      to the replica, async or semisync",
    )
    replica_master = fields.String(
        required=False,
        example="116850",
        missing=None,
        allow_none=True,
        description="id, uuid or name of master server in a database replication system",
    )
    replica_username = fields.String(
        required=False,
        example="",
        allow_none=True,
        description="The user name of the \
                                     replica",
    )
    replica_password = fields.String(
        required=False,
        example="",
        allow_none=True,
        description="Password for replica \
                                     user",
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
        Update sql_stack
        """
        return self.update_resource(controller, oid, data)


class ActionStackParamsStopRequestSchema(Schema):
    force = fields.Boolean(
        required=False,
        allow_none=True,
        missing=False,
        description="Force database instance to stop, i.e shut down the vm without first stopping "
        "the database engine",
    )


class ActionStackParamsCreateDbRequestSchema(Schema):
    db_name = fields.String(required=True, example="test", allow_none=False, description="Database name ")
    charset = fields.String(
        required=False,
        example="latin1",
        allow_none=True,
        description="Database charset",
    )


class ActionStackParamsDeleteDbRequestSchema(Schema):
    db_name = fields.String(required=True, example="test", allow_none=False, description="Database name")


class ActionStackParamsGetUsersRequestSchema(Schema):
    host = fields.String(required=True, example="test_usr", allow_none=False, description="Host name")
    user = fields.String(required=True, example="test!1234", allow_none=False, description="User name")
    privileges = fields.Dict(
        required=True,
        example="test!1234",
        allow_none=False,
        description="User privileges",
    )
    # 'max_questions': item.get('max_questions'),
    # 'max_updates': item.get('max_updates'),
    # 'max_connections': item.get('max_connections'),
    # 'max_user_connections': item.get('max_user_connections'),
    # 'plugin': item.get('plugin'),
    # # 'authentication_string': item.get('authentication_string'),
    # 'password_expired': item.get('password_expired'),
    # 'password_last_changed': item.get('password_last_changed'),
    # 'password_lifetime': item.get('password_lifetime'),
    # 'account_locked': item.get('account_locked'),


class ActionStackParamsCreateUserRequestSchema(Schema):
    name = fields.String(required=True, example="test_usr", allow_none=False, description="User name")
    password = fields.String(
        required=True,
        example="test!1234",
        allow_none=False,
        description="User password",
    )


class ActionStackParamsDeleteUserRequestSchema(Schema):
    name = fields.String(required=True, example="test_usr", allow_none=False, description="User name")
    # params below are specific for PostgreSQL only
    force = fields.Boolean(required=False, default=False, missing=False, description="Force user deletion")


class ActionStackParamsGrantPrivilegesRequestSchema(Schema):
    privileges = fields.String(
        required=True,
        example="SELECT,INSERT,DELETE,UPDATE",
        allow_none=False,
        description="Privileges string in the format priv1,priv2,...,privN",
    )
    db_name = fields.String(required=True, example="test", allow_none=False, description="Database name")
    usr_name = fields.String(required=True, example="test_usr", allow_none=False, description="User name")


class ActionStackParamsRevokePrivilegesRequestSchema(Schema):
    privileges = fields.String(
        required=True,
        example="DELETE,UPDATE",
        allow_none=False,
        description="Privileges string in the format priv1,priv2,...,privN",
    )
    db_name = fields.String(required=True, example="test", allow_none=False, description="Database name")
    usr_name = fields.String(required=True, example="test_usr", allow_none=False, description="User name")


class ActionStackParamsChangePasswordRequestSchema(Schema):
    name = fields.String(required=True, example="test_usr", allow_none=False, description="User name")
    new_password = fields.String(
        required=True,
        example="test!5678",
        allow_none=False,
        description="New user password",
    )


class ActionStackParamsSecurityGroupRequestSchema(Schema):
    security_group = fields.String(
        required=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="Security group uuid",
    )


class ActionStackParamsSetFlavorRequestSchema(Schema):
    flavor = fields.String(required=True, example="vm.s1.small", description="flavor uuid or name")


class ActionStackParamsEnableMonitoringRequestSchema(Schema):
    host_group = fields.String(
        required=False,
        example="Csi.Datacenter.test",
        allow_none=True,
        description="the account hostgroup in the form Organization.Division.Account the "
        "compute instance to monitor belongs to",
    )
    templates = fields.String(
        required=False,
        example="db,linux",
        allow_none=True,
        description="comma separated list of zabbix agent template name",
    )


class ActionStackParamsDisableMonitoringRequestSchema(Schema):
    deregister_only = fields.Boolean(
        required=False,
        allow_none=True,
        description="deregister_only on zabbix, not disinstall agent",
    )


class ActionStackParamsEnableLoggingRequestSchema(Schema):
    host_group = fields.String(
        required=False,
        example="Csi.Datacenter.test",
        allow_none=True,
        description="the account hostgroup in the form Organization.Division.Account the "
        "compute instance to monitor belongs to",
    )
    files = fields.String(
        required=False,
        example="db,linux",
        allow_none=True,
        description="comma separated list of files to capture",
    )
    logstash_port = fields.Integer(
        required=False,
        allow_none=True,
        missing=5044,
        example=5044,
        description="logstash pipeline port",
    )


class ActionStackParamsEnableMailxRequestSchema(Schema):
    relayhost = fields.String(
        required=False,
        allow_none=True,
        example="xxx.csi.it",
        description="remote mail server Postfix sends outgoing messages to, instead of trying to "
        "deliver them directly to their destination",
    )


class ActionStackParamsHaproxyRegisterRequestSchema(Schema):
    port_ini = fields.String(
        required=False,
        allow_none=True,
        example="10100",
        description="First port number " "(included) in haproxy range of ports that client can connect to",
    )
    port_fin = fields.String(
        required=False,
        allow_none=True,
        example="10999",
        description="Last port number " "(excluded) in haproxy range of ports that client can connect to",
    )


class ActionStackParamsResizeRequestSchema(Schema):
    new_data_disk_size = fields.Integer(
        required=True,
        example=30,
        allow_none=False,
        description="The total storage space of data disk after resize",
    )


class ActionStackParamsRequestSchema(Schema):
    stop = fields.Nested(ActionStackParamsStopRequestSchema, description="Stop database server")
    start = fields.Boolean(description="Start database server")
    restart = fields.Boolean(description="Restart database server")
    add_security_group = fields.Nested(
        ActionStackParamsSecurityGroupRequestSchema,
        description="Add security group to database server",
    )
    del_security_group = fields.Nested(
        ActionStackParamsSecurityGroupRequestSchema,
        description="Remove security group from database server",
    )
    set_flavor = fields.Nested(
        ActionStackParamsSetFlavorRequestSchema,
        description="Set flavor to database server",
    )
    get_dbs = fields.Boolean(description="List databases")
    add_db = fields.Nested(
        ActionStackParamsCreateDbRequestSchema,
        description="Create database and schema. For "
        "postgres use db1 to create database db1 and db1.schema1 to create schema schema1 in "
        "database db1",
    )
    drop_db = fields.Nested(
        ActionStackParamsDeleteDbRequestSchema,
        description="Delete database and schema. For "
        "postgres use db1 to remove database db1 and db1.schema1 to remove schema schema1 in "
        "database db1",
    )
    get_users = fields.Boolean(description="List users")
    add_user = fields.Nested(ActionStackParamsCreateUserRequestSchema, description="Create user")
    drop_user = fields.Nested(ActionStackParamsDeleteUserRequestSchema, description="Delete user")
    grant_privs = fields.Nested(
        ActionStackParamsGrantPrivilegesRequestSchema,
        description="Assign privileges to user",
    )
    revoke_privs = fields.Nested(
        ActionStackParamsRevokePrivilegesRequestSchema,
        description="Revoke privileges to user",
    )
    change_pwd = fields.Nested(ActionStackParamsChangePasswordRequestSchema, description="Change user password")
    install_extensions = fields.Dict(description="Install extensions on database server", default=[])
    enable_monitoring = fields.Nested(
        ActionStackParamsEnableMonitoringRequestSchema,
        description="Enable resources monitoring over sql stack",
    )
    disable_monitoring = fields.Nested(
        ActionStackParamsDisableMonitoringRequestSchema,
        description="Disable resources monitoring over sql stack",
    )
    enable_logging = fields.Nested(
        ActionStackParamsEnableLoggingRequestSchema,
        description="Enable log forwarding over sql stack",
    )
    enable_mailx = fields.Nested(
        ActionStackParamsEnableMailxRequestSchema,
        description="Enable mailx over sql stack",
    )
    haproxy_register = fields.Nested(
        ActionStackParamsHaproxyRegisterRequestSchema,
        description="Register database server on haproxy",
    )
    haproxy_deregister = fields.Boolean(description="Deregister database server from haproxy")
    resize = fields.Nested(
        ActionStackParamsResizeRequestSchema,
        description="Resize database storage capacity",
    )


class ActionStackRequestSchema(Schema):
    action = fields.Nested(ActionStackParamsRequestSchema, required=True)


class ActionStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ActionStackRequestSchema, context="body")


class ActionStackResponseSchema(Schema):
    # taskid = fields.UUID(default='db078b20-19c6-4f0e-909c-94745de667d4',
    #                      example='6d960236-d280-46d2-817d-f3ce8f0aeff7',
    #                      required=False, description='task id')
    # uuid = fields.UUID(required=False,  default='6d960236-d280-46d2-817d-f3ce8f0aeff7',
    #                    example='6d960236-d280-46d2-817d-f3ce8f0aeff7', description='sql stack uuid')
    dbs = fields.List(
        fields.Dict,
        required=False,
        default={},
        example={},
        description="sql stack database list",
    )
    users = fields.List(
        fields.Dict,
        required=False,
        default={},
        example={},
        description="sql stack user list",
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
        Run sql_stack action
        """
        resource: SqlComputeStackV2 = self.get_resource_reference(controller, oid)
        actions = data.get("action")
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {"param": params}

        if action in resource.actions:
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

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete sql_stack
        Delete sql_stack
        """
        return self.expunge_resource(controller, oid)


class GetStackCredentialsResponseSchema(Schema):
    sql_stack_credentials = fields.List(fields.Dict, required=True)


class GetStackCredentials(ProviderStack):
    summary = "Get sql stack credentials"
    description = "Get sql stack credentials"
    definitions = {
        "GetStackCredentialsResponseSchema": GetStackCredentialsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get sql_stack credential
        Get sql_stack credential
        """
        resource = self.get_resource_reference(controller, oid)
        users = resource.get_credentials()
        return {"sql_stack_credentials": users}


class SetStackCredentialsRequestSchema(Schema):
    user = fields.String(required=True, example="root", description="User name")
    password = fields.String(required=True, example="mypass", description="User password")


class SetStackCredentials(ProviderStack):
    summary = "Set sql stack credential"
    description = "Set sql stack credential"
    definitions = {
        "SetStackCredentialsRequestSchema": SetStackCredentialsRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "success"}})

    def put(self, controller, data, oid, *args, **kwargs):
        resource = self.get_resource_reference(controller, oid)
        res = resource.set_credential(**data)
        return res, 204


class GetStackEngineResponseSchema(Schema):
    engine = fields.String(required=True, example="mysql", description="Engine name")
    version = fields.String(required=True, example="5.7", description="Engine version")


class GetStackEnginesResponseSchema(Schema):
    engines = fields.Nested(GetStackEngineResponseSchema, required=True)


class GetStackEngines(ProviderStack):
    definitions = {
        "GetStackEnginesResponseSchema": GetStackEnginesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        Get sql_stack engines
        Get sql_stack engines
        """
        engines = SqlComputeStackV2.get_engines()
        return {"engines": engines}


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
        ]
        kwargs["version"] = "v2.0"
        ProviderAPI.register_api(module, rules, **kwargs)
