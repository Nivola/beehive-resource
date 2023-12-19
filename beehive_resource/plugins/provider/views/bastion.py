# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from marshmallow.validate import OneOf
from beehive_resource.plugins.provider.entity.bastion import ComputeBastion
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
    CrudApiTaskResponseSchema,
    ApiManagerError,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
)


class ProviderBastion(LocalProviderApiView):
    resclass = ComputeBastion
    parentclass = ComputeZone


class ListBastionsRequestSchema(ListResourcesRequestSchema):
    compute_zone = fields.String(context="query", description="super zone id or uuid")
    security_group = fields.String(context="query", description="security group id or uuid")
    vpc = fields.String(context="query", description="vpc id or uuid")
    image = fields.String(context="query", description="image id or uuid")
    flavor = fields.String(context="query", description="flavor id or uuid")
    hypervisor = fields.String(context="query", description="hypervisor name like vsphere or openstack")


class BastionFlavorResponseSchema(Schema):
    vcpus = fields.Integer(required=True, example=2, description="virtual cpu number")
    disk = fields.Integer(required=True, example=10, description="root disk siez in GB")
    bandwidth = fields.Integer(required=True, example=1000, description="network bandwidth")
    memory = fields.Integer(required=True, example=2048, description="memory in MB")
    uuid = fields.String(required=True, example="2887", description="flavor uuid")


class BastionImageResponseSchema(Schema):
    os_ver = fields.String(required=True, example="7.1", description="operating system version")
    os = fields.String(required=True, example="Centos", description="operating system name")
    uuid = fields.String(required=True, example="2887", description="image uuid")


class BastionNetworkResponseSchema(Schema):
    ip = fields.String(required=True, example="10.102.185.121", description="ip address")
    uuid = fields.String(required=True, example="2887", description="vpc uuid")
    name = fields.String(required=True, example="DCCTP-tst-BE", description="vpc name")
    subnet = fields.String(required=True, example="10.102.78.90/24", description="subnet cidr")


class BastionBlockDeviceResponseSchema(Schema):
    boot_index = fields.Integer(
        required=False,
        example=0,
        description="boot index of the disk. 0 for the main disk",
    )
    volume_size = fields.Integer(required=False, example=10, description="Size of volume in GB")
    bootable = fields.Boolean(example=True, description="True if volume is bootable")
    encrypted = fields.Boolean(example=False, description="True if volume is encrypted")


class BastionAttributesResponseSchema(Schema):
    configs = fields.Dict(required=True, example={}, description="custom config")
    type = fields.String(
        required=True,
        example="openstack",
        description="bastion type: vsphere or openstack",
    )


class BastionResponseSchema(ResourceResponseSchema):
    flavor = fields.Nested(
        BastionFlavorResponseSchema,
        required=True,
        description="flavor",
        allow_none=True,
    )
    image = fields.Nested(BastionImageResponseSchema, required=True, description="image", allow_none=True)
    vpcs = fields.Nested(
        BastionNetworkResponseSchema,
        required=True,
        many=True,
        description="vpcc list",
        allow_none=True,
    )
    block_device_mapping = fields.Nested(
        BastionBlockDeviceResponseSchema,
        required=True,
        many=True,
        description="block device mapping list",
        allow_none=True,
    )
    attributes = fields.Nested(
        BastionAttributesResponseSchema,
        required=True,
        description="custom attributes",
        allow_none=True,
    )


class ListBastionsResponseSchema(PaginatedResponseSchema):
    bastions = fields.Nested(BastionResponseSchema, many=True, required=True, allow_none=True)


class ListBastions(ProviderBastion):
    definitions = {
        "ListBastionsRequestSchema": ListBastionsRequestSchema,
        "ListBastionsResponseSchema": ListBastionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListBastionsRequestSchema)
    parameters_schema = ListBastionsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListBastionsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List bastions
        List bastions

        RunState:
        - noState
        - poweredOn
        - blocked
        - suspended
        - poweredOff
        - crashed
        - resize [only openstack bastion]
        - update [only openstack bastion]
        - deleted [only openstack bastion]
        - reboot [only openstack bastion]

        # - filter by: tags
        # - filter by: super_zone, security_group, vpc, network, image,
        #              flavor
        """
        zone_id = data.get("compute_zone", None)

        if zone_id is not None:
            zone = controller.get_simple_resource(zone_id)
            bastion = zone.get_bastion_host()
            if bastion is None:
                raise ApiManagerError("no bastion hots found", code=404)
            resp = {
                "bastions": [bastion.info()],
                "count": 1,
                "page": 0,
                "total": 1,
                "sort": {"field": "id", "order": "asc"},
            }
            return resp

        return self.get_resources(controller, **data)


class GetBastionResponseSchema(Schema):
    bastion = fields.Nested(BastionResponseSchema, required=True, allow_none=True)


class GetBastion(ProviderBastion):
    summary = "Get bastion"
    description = "Get bastion"
    definitions = {
        "GetBastionResponseSchema": GetBastionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetBastionResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateBastionBlockDeviceRequestSchema(Schema):
    boot_index = fields.Integer(
        required=False,
        example=0,
        description="boot index of the disk. 0 for the main disk",
    )
    source_type = fields.String(
        required=False,
        example="volume",
        description="The source type of the volume. A "
        "valid value is: snapshot - creates a volume backed by the given volume snapshot "
        "referenced via the block_device_mapping_v2.uuid parameter and attaches it to the "
        "server; volume: uses the existing persistent volume referenced via the block_device_"
        "mapping_v2.uuid parameter and attaches it to the server; image: creates an "
        "image-backed volume in the block storage service and attaches it to the server;"
        "blank: this will be a blank persistent volume",
        missing=None,
        validate=OneOf(["snapshot", "volume", "image", None]),
    )
    volume_size = fields.Integer(required=False, example=10, description="Size of volume in GB")
    tag = fields.String(
        example="default",
        missing="default",
        description="datastore tag. Use to select datastore",
    )
    uuid = fields.String(
        example="default",
        missing=None,
        description="This is the uuid of source resource. The uuid "
        "points to different resources based on the source_type. If source_type is image, the block "
        "device is created based on the specified image which is retrieved from the image service. "
        "If source_type is snapshot then the uuid refers to a volume snapshot in the block storage "
        "service. If source_type is volume then the uuid refers to a volume in the block storage "
        "service.",
    )
    flavor = fields.String(
        required=False,
        example="default",
        description="The volume flavor. This can "
        "be used to specify the type of volume which the compute service will create and attach "
        "to the server.",
    )


class CreateBastionNetworkIpRequestSchema(Schema):
    ip = fields.String(required=False, example="10.102.185.105", description="ip address")
    hostname = fields.String(
        required=False,
        example="bastion-vsphere01.tstsddc.csi.it",
        description="host name",
    )
    dns_search = fields.String(required=False, example="tstsddc.csi.it", description="dns search path")


class CreateBastionAclRequestSchema(Schema):
    subnet = fields.String(required=True, example="10.102.167.90/24", description="subnet definition")


class CreateBastionParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    availability_zone = fields.String(required=True, example="2", description="site id or uuid")
    host_group = fields.String(
        required=False,
        example="default",
        missing="default",
        description="Define the optional host group where put the bastion",
    )
    flavor = fields.String(
        required=False,
        example="vm.s1.micro",
        missing="vm.s1.micro",
        description="id or uuid of the flavor",
    )
    volume_flavor = fields.String(
        required=False,
        example="vol.default",
        missing="vol.default",
        description="id or uuid of the volume flavor",
    )
    image = fields.String(
        required=False,
        example="Centos7",
        missing="Centos7",
        description="id or uuid of the image",
    )
    admin_pass = fields.String(
        required=False,
        example="test",
        missing=None,
        description="admin password to set",
    )
    key_name = fields.String(
        required=False,
        example="bastion-key",
        missing="bastion-key",
        description="ssh key name or uuid",
    )
    acl = fields.Nested(
        CreateBastionAclRequestSchema,
        many=True,
        required=False,
        allow_none=True,
        description="list of network acl",
    )


class CreateBastionRequestSchema(Schema):
    bastion = fields.Nested(CreateBastionParamRequestSchema)


class CreateBastionBodyRequestSchema(Schema):
    body = fields.Nested(CreateBastionRequestSchema, context="body")


class CreateBastion(ProviderBastion):
    summary = "Create bastion"
    description = "Create bastion"
    definitions = {
        "CreateBastionRequestSchema": CreateBastionRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateBastionBodyRequestSchema)
    parameters_schema = CreateBastionRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class DeleteBastion(ProviderBastion):
    summary = "Patch bastion"
    description = "Patch bastion"
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class SendBastionActionParamsSnapshotRequestSchema(Schema):
    snapshot = fields.String(
        required=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="snapshot name when add or uuid when delete",
    )


class SendBastionActionParamsSgRequestSchema(Schema):
    security_group = fields.String(
        required=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="security group uuid",
    )


class SendBastionActionParamsVolumeRequestSchema(Schema):
    volume = fields.String(
        required=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="volume uuid or name",
    )


class SendBastionActionParamsSetFlavorRequestSchema(Schema):
    flavor = fields.String(
        required=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="flavor uuid or name",
    )


class SendBastionActionParamsMigrateRequestSchema(Schema):
    live = fields.Boolean(
        required=False,
        missing=False,
        default=False,
        description="If True attempt to run a live migration",
    )
    host = fields.String(
        required=False,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="host uuid",
    )


class SendBastionActionParamsAddUserRequestSchema(Schema):
    user_name = fields.String(required=True, example="prova", description="user name")
    user_pwd = fields.String(required=True, example="prova", description="user password")
    user_ssh_key = fields.String(required=False, example="test-key", missing=None, description="user ssh key")


class SendBastionActionParamsDelUserRequestSchema(Schema):
    user_name = fields.String(required=True, example="prova", description="user name")


class SendBastionActionParamsSetUserPwdRequestSchema(Schema):
    user_name = fields.String(required=True, example="prova", description="user name")
    user_pwd = fields.String(required=True, example="prova", description="user password")


class SendBastionActionParamsSetSshKeyRequestSchema(Schema):
    user_name = fields.String(required=True, example="prova", description="user name")
    user_ssh_key = fields.String(required=True, example="prova", description="user ssh key")


class SendBastionActionParamsUnsetSshKeyRequestSchema(Schema):
    user_name = fields.String(required=True, example="prova", description="user name")
    user_ssh_key = fields.String(required=True, example="prova", description="user ssh key")


class SendBastionActionParamsEnableMonitoringRequestSchema(Schema):
    host_group = fields.String(
        required=False,
        missing="PrivateBastionHost",
        allow_none=True,
        description="the account hostgroup in the form Organization.Division.Account the "
        "bastion to monitor belongs to",
    )


class SendBastionActionParamsRequestSchema(Schema):
    start = fields.Boolean(description="start server")
    stop = fields.Boolean(description="stop server")
    reboot = fields.Boolean(description="reboot server")
    install_zabbix_proxy = fields.Boolean(description="install zabbix proxy")
    register_zabbix_proxy = fields.Boolean(description="register zabbix proxy")
    enable_monitoring = fields.Nested(
        SendBastionActionParamsEnableMonitoringRequestSchema,
        description="enable resources monitoring over bastion",
    )
    enable_logging = fields.Boolean(description="enable log forwarding over bastion")
    # pause = fields.Boolean(description='pause server')
    # unpause = fields.Boolean(description='unpause server')
    # migrate = fields.Nested(SendBastionActionParamsMigrateRequestSchema, description='migrate server')
    # # setup_network = fields.String(description='setup server network')
    # reset_state = fields.String(description='change server state')
    # add_volume = fields.Nested(SendBastionActionParamsVolumeRequestSchema, description='add volume to server')
    # del_volume = fields.Nested(SendBastionActionParamsVolumeRequestSchema, description='remove volume from server')
    set_flavor = fields.Nested(
        SendBastionActionParamsSetFlavorRequestSchema,
        description="set flavor to server",
    )
    # add_snapshot = fields.Nested(SendBastionActionParamsSnapshotRequestSchema, description='add server snapshot')
    # del_snapshot = fields.Nested(SendBastionActionParamsSnapshotRequestSchema, description='remove server snapshot')
    # revert_snapshot = fields.Nested(SendBastionActionParamsSnapshotRequestSchema,
    #                                 description='revert server to snapshot')
    add_security_group = fields.Nested(
        SendBastionActionParamsSgRequestSchema,
        description="add security group to server",
    )
    del_security_group = fields.Nested(
        SendBastionActionParamsSgRequestSchema,
        description="remove security group from server",
    )
    # add_user = fields.Nested(SendBastionActionParamsAddUserRequestSchema, description='add bastion user')
    # del_user = fields.Nested(SendBastionActionParamsDelUserRequestSchema, description='delete bastion user')
    # set_user_pwd = fields.Nested(SendBastionActionParamsSetUserPwdRequestSchema,
    #                              description='set bastion user password')
    # set_ssh_key = fields.Nested(SendBastionActionParamsSetSshKeyRequestSchema, description='set bastion user ssh key')
    # unset_ssh_key = fields.Nested(SendBastionActionParamsUnsetSshKeyRequestSchema,
    #                               description='unset bastion user ssh key')


class SendBastionActionRequestSchema(Schema):
    action = fields.Nested(SendBastionActionParamsRequestSchema, required=True)
    schedule = fields.Dict(
        required=False,
        missing=None,
        description="schedule to use when you want to run a scheduled " "action",
    )


class SendBastionActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendBastionActionRequestSchema, context="body")


class SendBastionAction(ProviderBastion):
    summary = "Send server action"
    description = "Send server action"
    definitions = {
        "SendBastionActionRequestSchema": SendBastionActionRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendBastionActionBodyRequestSchema)
    parameters_schema = SendBastionActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        bastion = self.get_resource_reference(controller, oid)
        actions = data.get("action")
        schedule = data.get("schedule")
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {"param": params}

        if action in bastion.actions:
            if schedule is not None:
                task = bastion.scheduled_action(action, schedule=schedule, params=params)
            else:
                task = bastion.action(action, **params)
        else:
            raise ApiManagerError("Action %s not supported for bastion" % action)

        return task


class BastionProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: super_zone, security_group, vpc, network, image, flavor
            ("%s/bastions" % base, "GET", ListBastions, {}),
            ("%s/bastions/<oid>" % base, "GET", GetBastion, {}),
            ("%s/bastions" % base, "POST", CreateBastion, {}),
            # ('%s/bastions/<oid>' % base, 'PUT', UpdateBastion, {}),
            # # ('%s/bastions/<oid>' % base, 'PATCH', PatchBastion, {}),
            ("%s/bastions/<oid>" % base, "DELETE", DeleteBastion, {}),
            ("%s/bastions/<oid>/actions" % base, "PUT", SendBastionAction, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
