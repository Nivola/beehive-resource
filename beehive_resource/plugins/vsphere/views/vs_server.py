# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte
import json
import string
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from marshmallow.decorators import validates_schema
from marshmallow.exceptions import ValidationError
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectTaskResponseSchema, ApiObjectSmallResponseSchema, CrudApiJobResponseSchema, ApiManagerError
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beecell.flask.render import render_template
from flask import request


class VsphereServerApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VsphereServer
    parentclass = VsphereFolder


class ListServersRequestSchema(ListResourcesRequestSchema):
    pass


class ListServersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListServersResponseSchema(PaginatedResponseSchema):
    servers = fields.Nested(ListServersParamsResponseSchema, many=True, required=True, allow_none=True)


class ListServers(VsphereServerApiView):
    summary = 'List server'
    description = 'List server'
    definitions = {
        'ListServersResponseSchema': ListServersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListServersRequestSchema)
    parameters_schema = ListServersRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListServersResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetServerResponseSchema(Schema):
    server = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetServer(VsphereServerApiView):
    summary = 'Get server'
    description = 'Get server'
    definitions = {
        'GetServerResponseSchema': GetServerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class ServerNetworkFixedIpRequestSchema(Schema):
    ip = fields.String(required=False, example='10.101.0.9', description='ip address')
    gw = fields.String(required=False, example='10.101.0.1', description='default gateway')
    hostname = fields.String(required=False, example='test', description='host name')
    dns = fields.String(required=False, example='10.10.0.3,10.10.0.4', description='comma separated list of dns')
    dns_search = fields.String(required=False, example='local.domain', description='dns search path')


class ServerNetworkRequestSchema(Schema):
    uuid = fields.String(required=True, example='10', description='network id, uuid')
    subnet_pool = fields.String(required=False, example='ipaddresspool-3', description='nsx subnet pool id',
                                allow_none=True)
    fixed_ip = fields.Nested(ServerNetworkFixedIpRequestSchema, required=False, description='networks configuration',
                             allow_none=True)
    # tag = fields.String(required=False, example='10.101.0.9', description='network tag')


class ServerVolumeRequestSchema(Schema):
    boot_index = fields.Integer(required=False, example=0, allow_none=True,
                                description='boot index of the disk. 0 for the main disk')
    source_type = fields.String(required=False, example='volume', description='The source type of the volume. A '
                                'valid value is: snapshot - creates a volume backed by the given volume snapshot '
                                'referenced via the block_device_mapping_v2.uuid parameter and attaches it to the '
                                'server; volume: uses the existing persistent volume referenced via the block_device_'
                                'mapping_v2.uuid parameter and attaches it to the server; image: creates an '
                                'image-backed volume in the block storage service and attaches it to the server',
                                validate=OneOf(['snapshot', 'volume', 'image']))
    volume_size = fields.Integer(required=False, example=10, description='Size of volume in GB')
    destination_type = fields.String(required=False, example='volume', description='Defines where the volume comes '
                                     'from. A valid value is local or volume. [default=volume]')
    tag = fields.String(example='default', missing='default', description='datastore tag. Use to select datastore')
    uuid = fields.String(example='default', description='This is the uuid of source resource. The uuid '
                         'points to different resources based on the source_type. If source_type is image, the block '
                         'device is created based on the specified image which is retrieved from the image service. '
                         'If source_type is snapshot then the uuid refers to a volume snapshot in the block storage '
                         'service. If source_type is volume then the uuid refers to a volume in the block storage '
                         'service.', required=True)
    volume_type = fields.String(example='default', missing=None, description='The device volume_type. This can be '
                                'used to specify the type of volume which the compute service will create and attach '
                                'to the server. If not specified, the block storage service will provide a default '
                                'volume type. It is only supported with source_type of image or snapshot.')


class CreateServerParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid')
    name = fields.String(required=True, example='test', description='name')
    desc = fields.String(required=True, example='test', description='name')
    folder = fields.String(required=True, example='23', description='folder id, uuid')
    tags = fields.String(example='prova', default='', description='comma separated list of tags')
    accessIPv4 = fields.String(example='', default='', description='ipv4 address')
    accessIPv6 = fields.String(example='', default='', description='ipv6 address')
    flavorRef = fields.String(required=True, example='23', description='server cpu, ram and operating system')
    availability_zone = fields.String(required=True, example='1', description='Specify the cluster id, uuid')
    adminPass = fields.String(required=False, default='', description='The administrative password of the server.')
    networks = fields.Nested(ServerNetworkRequestSchema, required=True, many=True, description='A networks object',
                             allow_none=True)
    security_groups = fields.List(fields.String(example=''), required=True,
                                  description='One or more security groups id or uuid')
    user_data = fields.String(required=False, allow_none=True, description='Configuration information or scripts to '
                              'use upon launch. Must be Base64 encoded.')
    metadata = fields.Dict(example={'template_pwd': ''}, description='server metadata')
    personality = fields.List(fields.Dict(example={'path': '/etc/banner.txt', 'contents': 'udsdsd=='}),
                              required=False, default=[], description='The file path and contents, text only, '
                              'to inject into the server at launch. The maximum size of the file path data is 255 '
                              'bytes. The maximum limit is The number of allowed bytes in the decoded, rather than '
                              'encoded, data.')
    block_device_mapping_v2 = fields.Nested(ServerVolumeRequestSchema, required=True, many=True, allow_none=True,
                                            description='Enables fine grained control of the block device mapping '
                                                        'for an instance')

    @validates_schema
    def validate_data(self, data, *args, **kvargs):
        admin_pass = data.get('adminPass', None)
        admin_pass_set = set(admin_pass)

        special_chars = set('_$#!')
        c1 = admin_pass_set & special_chars
        c2 = admin_pass_set & set(string.digits)

        if len(admin_pass) < 8:
            raise ValidationError('adminPass length must be at least 8')
        elif len(c1) < 1 and len(c2) < 1:
            raise ValidationError('adminPass has not the minimum complexity. Use at least a chars in _$#! and a digit')


class CreateServerRequestSchema(Schema):
    server = fields.Nested(CreateServerParamRequestSchema)


class CreateServerBodyRequestSchema(Schema):
    body = fields.Nested(CreateServerRequestSchema, context='body')


class CreateServer(VsphereServerApiView):
    summary = 'Create server'
    description = 'Create server'
    definitions = {
        'CreateServerRequestSchema': CreateServerRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateServerBodyRequestSchema)
    parameters_schema = CreateServerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateServerParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateServerRequestSchema(Schema):
    server = fields.Nested(UpdateServerParamRequestSchema)


class UpdateServerBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateServerRequestSchema, context='body')


class UpdateServer(VsphereServerApiView):
    summary = 'Update server'
    description = 'Update server'
    definitions = {
        'UpdateServerRequestSchema': UpdateServerRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateServerBodyRequestSchema)
    parameters_schema = UpdateServerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteServer(VsphereServerApiView):
    summary = 'Delete server'
    description = 'Delete server'
    definitions = {
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GetServerHardwareResponseSchema(Schema):
    server_hardware = fields.Dict(required=True, example={})


class GetServerHardware(VsphereServerApiView):
    summary = 'Get server hardware'
    description = 'Get server hardware'
    definitions = {
        'GetServerHardwareResponseSchema': GetServerHardwareResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerHardwareResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_hardware()
        resp = {'server_hardware': res}
        return resp


class GetServerConsoleResponseSchema(Schema):
    server_console = fields.Dict(required=True, example={})


class GetServerConsole(VsphereServerApiView):
    summary = 'Get server console'
    description = 'Get server console'
    definitions = {
        'GetServerConsoleResponseSchema': GetServerConsoleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerConsoleResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_vnc_console()
        resp = {'server_console': res}
        return resp


class GetServerNetworksResponseSchema(Schema):
    server_networks = fields.Nested(ApiObjectSmallResponseSchema, required=True, many=True, allow_none=True)


class GetServerNetworks(VsphereServerApiView):
    summary = 'Get server networks'
    description = 'Get server networks'
    definitions = {
        'GetServerNetworksResponseSchema': GetServerNetworksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerNetworksResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_networks()
        resp = {'server_networks': res, 'count': len(res)}
        return resp


class GetServerVolumesParamsResponseSchema(Schema):
    committed = fields.Float(required=True, example=1.0)
    datastore = fields.Nested(ApiObjectSmallResponseSchema, required=True, allow_none=True)
    uncommitted = fields.Float(required=True, example=6.0)
    unshared = fields.Float(required=True, example=1.0)
    url = fields.String(required=True, example='/vmfs/volumes/01ce0616-7bc9f86e')


class GetServerVolumesResponseSchema(Schema):
    server_volumes = fields.Nested(GetServerVolumesParamsResponseSchema, required=True, many=True, allow_none=True)


class GetServerVolumes(VsphereServerApiView):
    summary = 'Get server volumes'
    description = 'Get server volumes'
    definitions = {
        'GetServerVolumesResponseSchema': GetServerVolumesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerVolumesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_storage()
        resp = {'server_volumes': res, 'count': len(res)}
        return resp


class GetServerRuntimeParamsResponseSchema(Schema):
    boot_time = fields.Integer(required=True, example=1475479935)
    host = fields.Nested(ApiObjectSmallResponseSchema, required=True, allow_none=True)
    resource_pool = fields.Nested(ApiObjectSmallResponseSchema, required=True, allow_none=True)


class GetServerRuntimeResponseSchema(Schema):
    server_runtime = fields.Nested(GetServerRuntimeParamsResponseSchema, required=True, many=True, allow_none=True)


class GetServerRuntime(VsphereServerApiView):
    summary = 'Get server runtime'
    description = 'Get server runtime'
    definitions = {
        'GetServerRuntimeResponseSchema': GetServerRuntimeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerRuntimeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_runtime()
        resp = {'server_runtime': res}
        return resp


class GetServerStatsParamsResponseSchema(Schema):
    balloonedMemory = fields.Integer(required=True, example=0)
    compressedMemory = fields.Integer(required=True, example=0)
    consumedOverheadMemory = fields.Integer(required=True, example=38)
    distributedCpuEntitlement = fields.Integer(required=True, example=0)
    distributedMemoryEntitlement = fields.Integer(required=True, example=390)
    dynamicProperty = fields.List(fields.String, required=True, example=[])
    dynamicType = fields.Integer(required=True, example=None)
    ftLatencyStatus = fields.String(required=True, example='gray')
    ftLogBandwidth = fields.Integer(required=True, example=-1)
    ftSecondaryLatency = fields.Integer(required=True, example=-1)
    guestHeartbeatStatus = fields.String(required=True, example='green')
    guestMemoryUsage = fields.Integer(required=True, example=30)
    hostMemoryUsage = fields.Integer(required=True, example=337)
    overallCpuDemand = fields.Integer(required=True, example=0)
    overallCpuUsage = fields.Integer(required=True, example=0)
    privateMemory = fields.Integer(required=True, example=300)
    sharedMemory = fields.Integer(required=True, example=0)
    ssdSwappedMemory = fields.Integer(required=True, example=0)
    staticCpuEntitlement = fields.Integer(required=True, example=2260)
    staticMemoryEntitlement = fields.Integer(required=True, example=1092)
    swappedMemory = fields.Integer(required=True, example=9)
    uptimeSeconds = fields.Integer(required=True, example=1824053)


class GetServerStatsResponseSchema(Schema):
    server_stats = fields.Nested(GetServerStatsParamsResponseSchema, required=True, many=True, allow_none=True)


class GetServerStats(VsphereServerApiView):
    summary = 'Get server statistics'
    description = 'Get server statistics'
    definitions = {
        'GetServerStatsResponseSchema': GetServerStatsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerStatsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_stats()
        resp = {'server_stats': res}
        return resp


class GetServerGuestParamsResponseSchema(Schema):
    disk = fields.List(fields.Dict, required=True)
    guest = fields.List(fields.Dict, required=True)
    hostname = fields.String(required=True, example='tst-vm2')
    ip_address = fields.String(required=True, example='172.25.5.151')
    ip_stack = fields.List(fields.Dict(example={}), required=True)
    nics = fields.List(fields.Dict(example={}), required=True)
    screen = fields.Dict(example={}, required=True)
    tools = fields.Dict(example={}, required=True)


class GetServerGuestResponseSchema(Schema):
    server_guest = fields.Nested(GetServerGuestParamsResponseSchema, required=True, many=True, allow_none=True)


class GetServerGuest(VsphereServerApiView):
    summary = 'Get server guest'
    description = 'Get server guest'
    definitions = {
        'GetServerGuestResponseSchema': GetServerGuestResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerGuestResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_guest_info()
        resp = {'server_guest': res}
        return resp


class GetServerMetadataResponseSchema(Schema):
    server_metadata = fields.Dict(required=True, many=True)


class GetServerMetadata(VsphereServerApiView):
    summary = 'Get server metadata'
    description = 'Get server metadata'
    definitions = {
        'GetServerMetadataResponseSchema': GetServerMetadataResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerMetadataResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_metadata()
        resp = {'server_metadata': res, 'count': len(res)}
        return resp


class ServerActionResponseSchema(Schema):
    pass


class GetServerActionsResponseSchema(Schema):
    server_actions = fields.Nested(ServerActionResponseSchema, required=True, many=True, allow_none=True)


class GetServerActions(VsphereServerApiView):
    summary = 'Get server actions'
    description = 'Get server actions'
    definitions = {
        'GetServerActionsResponseSchema': GetServerActionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerActionsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_actions()
        resp = {'server_actions': res, 'count': len(res)}
        return resp


class GetServerActionRequestSchema(GetApiObjectRequestSchema):
    aid = fields.String(required=True, context='path', description='action id')


class GetServerActionResponseSchema(Schema):
    server_action = fields.Nested(ServerActionResponseSchema, required=True, allow_none=True)


class GetServerAction(VsphereServerApiView):
    summary = 'Get server action'
    description = 'Get server action'
    definitions = {
        'GetServerActionResponseSchema': GetServerActionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetServerActionRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerActionResponseSchema
        }
    })

    def get(self, controller, data, oid, aid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_actions(action_id=aid)[0]
        resp = {'server_action': res}
        return resp


class SendServerActionParamsSnapshotRequestSchema(Schema):
    snapshot = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                             description='snapshot name when add or uuid when delete')


class SendServerActionParamsSgRequestSchema(Schema):
    security_group = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                                   description='security group uuid')


class SendServerActionParamsVolumeRequestSchema(Schema):
    volume = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                           description='security group uuid')


class SendServerActionParamsSetFlavorRequestSchema(Schema):
    flavor = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                           description='flavor uuid')


class SendServerActionParamsRequestSchema(Schema):
    start = fields.Boolean(description='start server')
    stop = fields.Boolean(description='stop server')
    reboot = fields.Boolean(description='reboot server')
    # pause = fields.Boolean(description='pause server')
    # unpause = fields.Boolean(description='unpause server')
    # migrate = fields.Nested(SendServerActionParamsMigrateRequestSchema, description='migrate server')
    # setup_network = fields.String(description='setup server network')
    reset_state = fields.String(description='change server state')
    add_security_group = fields.Nested(SendServerActionParamsSgRequestSchema,
                                       description='add security group to server')
    del_security_group = fields.Nested(SendServerActionParamsSgRequestSchema,
                                       description='remove security group from server')
    add_volume = fields.Nested(SendServerActionParamsVolumeRequestSchema, description='add volume to server')
    del_volume = fields.Nested(SendServerActionParamsVolumeRequestSchema, description='remove volume from server')
    set_flavor = fields.Nested(SendServerActionParamsSetFlavorRequestSchema, description='set flavor to server')
    add_snapshot = fields.Nested(SendServerActionParamsSnapshotRequestSchema, description='add server snapshot')
    del_snapshot = fields.Nested(SendServerActionParamsSnapshotRequestSchema, description='remove server snapshot')
    revert_snapshot = fields.Nested(SendServerActionParamsSnapshotRequestSchema,
                                    description='revert server to snapshot')


class SendServerActionRequestSchema(Schema):
    server_action = fields.Nested(SendServerActionParamsRequestSchema, required=True)


class SendServerActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendServerActionRequestSchema, context='body')


class SendServerAction(VsphereServerApiView):
    summary = 'Send server actions'
    description = 'Send server actions'
    definitions = {
        'SendServerActionRequestSchema': SendServerActionRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendServerActionBodyRequestSchema)
    parameters_schema = SendServerActionRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        server = self.get_resource_reference(controller, oid)
        actions = data.get('server_action')
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {'param': params}

        if action in server.actions.keys():
            res = server.actions.get(action)(**params)
        else:
            raise ApiManagerError('Action %s is not supported' % action)

        return res


class ServerSnapshotResponseSchema(Schema):
    pass


class GetServerSnapshotsResponseSchema(Schema):
    server_snapshots = fields.Nested(ServerSnapshotResponseSchema, required=True, many=True, allow_none=True)


class GetServerSnapshots(VsphereServerApiView):
    summary = 'Get server snapshots'
    description = 'Get server snapshots'
    definitions = {
        'GetServerSnapshotsResponseSchema': GetServerSnapshotsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerSnapshotsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = controller.get_resource(oid)
        res = obj.get_snapshots()
        resp = {'server_snapshots': res, 'count': len(res)}
        return resp


# class GetServerSnapshotRequestSchema(GetApiObjectRequestSchema):
#     pass
#
#
# class GetServerSnapshotResponseSchema(Schema):
#     server_actions = fields.Nested(ServerSnapshotResponseSchema, required=True, many=True, allow_none=True)
#
#
# class GetServerSnapshot(VsphereServerApiView):
#     summary = 'Get server snapshot'
#     description = 'Get server snapshot'
#     definitions = {
#         'GetServerSnapshotResponseSchema': GetServerSnapshotResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': GetServerSnapshotResponseSchema
#         }
#     })
#
#     def get(self, controller, data, oid, sid, *args, **kwargs):
#         obj = controller.get_resource(oid)
#         if sid == 'current':
#             res = obj.get_current_snapshot()
#         else:
#             res = obj.get_snapshots(sid)[0]
#         resp = {'server_snapshot': res}
#         return resp


class GetServerSecurityGroupsResponseSchema(Schema):
    server_security_groups = fields.Nested(ApiObjectSmallResponseSchema, required=True, many=True, allow_none=True)


class GetServerSecurityGroups(VsphereServerApiView):
    definitions = {
        'GetServerActionsResponseSchema': GetServerActionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetServerActionsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server security groups
        Get server security groups
        """
        obj = controller.get_resource(oid)
        res = obj.get_security_groups()
        resp = {'server_security_groups': [i.small_info() for i in res],
                'count': len(res)}
        return resp


# ## change security group
# class ChangeServerSecurityGroupRequestSchema(Schema):
#     cmd = fields.String(example='assign', required=True, validate=OneOf(['assign', 'deassign']),
#                         description='Command. Can be assign or deassign')
#     security_group = fields.String(example='test', required=True, description='Security group id, uuid')
#
#
# class ChangeServerSecurityGroupBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(ChangeServerSecurityGroupRequestSchema, context='body')
#
#
# class ChangeServerSecurityGroup(VsphereServerApiView):
#     summary = 'Assign or deassign Server SecurityGroup'
#     description = 'Assign or deassign Server SecurityGroup'
#     definitions = {
#         'ChangeServerSecurityGroupRequestSchema': ChangeServerSecurityGroupRequestSchema,
#         'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(ChangeServerSecurityGroupBodyRequestSchema)
#     parameters_schema = ChangeServerSecurityGroupRequestSchema
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectTaskResponseSchema
#         }
#     })
#
#     def put(self, controller, data, oid, *args, **kwargs):
#         server = controller.get_resource(oid)
#         cmd = data.get('cmd', None)
#         sg = data.get('security_group', None)
#         if cmd == 'assign':
#             res = server.assign_to_security_group(sg)
#         elif cmd == 'deassign':
#             res = server.deassign_from_security_group(sg)
#         return res


class GetServerHtml5ConsoleRequest(Schema):
    token = fields.String(required=True, context='query', description='authorization token')


class GetServerHtml5Console(VsphereServerApiView):
    definitions = {
        'GetServerHtml5ConsoleRequest': GetServerHtml5ConsoleRequest,
    }
    parameters = SwaggerHelper().get_parameters(GetServerHtml5ConsoleRequest)
    responses = {
        200: {
            'description': 'return html5 console page'
        }
    }

    def get(self, controller, data, *args, **kwargs):
        token = data.get('token')
        # json_token_data = controller.redis_manager.get(VsphereServer.console_prefix + token)
        json_token_data = controller.redis_identity_manager.get(VsphereServer.console_prefix + token)
        token_data = json.loads(json_token_data)
        wss_uri = token_data.get('uri')
        staticuri = token_data.get('staticuri')

        # set content type
        self.response_mime = 'text/html'
        resp = render_template(
            'console.html',
            wssuri=wss_uri,
            staticuri=staticuri,
        ), 200

        return resp


class VsphereServerAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ('%s/servers' % base, 'GET', ListServers, {}),
            ('%s/servers/<oid>' % base, 'GET', GetServer, {}),
            ('%s/servers' % base, 'POST', CreateServer, {}),
            ('%s/servers/<oid>' % base, 'PUT', UpdateServer, {}),
            ('%s/servers/<oid>' % base, 'DELETE', DeleteServer, {}),

            ('%s/servers/<oid>/hw' % base, 'GET', GetServerHardware, {}),
            ('%s/servers/<oid>/console' % base, 'GET', GetServerConsole, {}),
            ('%s/servers/<oid>/networks' % base, 'GET', GetServerNetworks, {}),
            ('%s/servers/<oid>/volumes' % base, 'GET', GetServerVolumes, {}),
            ('%s/servers/<oid>/runtime' % base, 'GET', GetServerRuntime, {}),
            ('%s/servers/<oid>/stats' % base, 'GET', GetServerStats, {}),
            ('%s/servers/<oid>/guest' % base, 'GET', GetServerGuest, {}),
            # ('%s/servers/<oid>/metadata' % base, 'GET', GetServerMetadata, {}),
            # ('%s/servers/<oid>/actions' % base, 'GET', GetServerActions, {}),
            # ('%s/servers/<oid>/action/<aid>' % base, 'GET', GetServerAction, {}),
            ('%s/servers/<oid>/action' % base, 'PUT', SendServerAction, {}),
            ('%s/servers/<oid>/snapshots' % base, 'GET', GetServerSnapshots, {}),
            # ('%s/servers/<oid>/snapshots/<sid>' % base, 'GET', GetServerSnapshot, {}),
            ('%s/servers/<oid>/security_groups' % base, 'GET', GetServerSecurityGroups, {}),
            # ('%s/servers/<oid>/security_groups' % base, 'PUT', ChangeServerSecurityGroup, {}),

            # html console
            ('console/vnc_auto.html', 'GET', GetServerHtml5Console, {'secure': False}),

        ]

        VsphereAPI.register_api(module, rules, **kwargs)
