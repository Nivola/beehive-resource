# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectTaskResponseSchema, ApiObjectSmallResponseSchema, CrudApiJobResponseSchema, CrudApiObjectResponseSchema, \
    CrudApiObjectTaskResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject


class OpenstackOpsServerApiView(OpenstackApiView):
    tags = ['openstack']
    resclass = OpenstackServer
    parentclass = OpenstackProject


class ListOpsServersRequestSchema(ListResourcesRequestSchema):
    pass


class ListOpsServersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListOpsServersResponseSchema(PaginatedResponseSchema):
    servers = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListOpsServers(OpenstackOpsServerApiView):
    tags = ['openstack']
    definitions = {
        'ListOpsServersResponseSchema': ListOpsServersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListOpsServersRequestSchema)
    parameters_schema = ListOpsServersRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListOpsServersResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List server
        List server
        """
        return self.get_resources(controller, **data)


class GetOpsServerResponseSchema(Schema):
    server = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetOpsServer(OpenstackOpsServerApiView):
    tags = ['openstack']
    definitions = {
        'GetOpsServerResponseSchema': GetOpsServerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server
        Get server
        """
        return self.get_resource(controller, oid)


class OpsServerNetworkFixedIpRequestSchema(Schema):
    ip = fields.String(required=False, example='10.101.0.9', description='ip address')
    gw = fields.String(required=False, example='10.101.0.1', description='default gateway')
    hostname = fields.String(required=False, example='test', description='host name')
    dns = fields.String(required=False, example='10.10.0.3,10.10.0.4', description='comma separated list of dns')
    dns_search = fields.String(required=False, example='local.domain', description='dns search path')


class OpsServerNetworkRequestSchema(Schema):
    uuid = fields.String(required=True, example='10', description='network id, uuid or name')
    subnet_uuid = fields.String(required=False, example='10', description='subnet id, uuid or name')
    fixed_ip = fields.Nested(OpsServerNetworkFixedIpRequestSchema, required=False,
                             description='networks configuration', allow_none=True)
    # tag = fields.String(required=False, example='10.101.0.9', description='network tag')


class OpsServerVolumeRequestSchema(Schema):
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
    uuid = fields.String(example='default', missing=None, description='This is the uuid of source resource. The uuid '
                         'points to different resources based on the source_type. If source_type is image, the block '
                         'device is created based on the specified image which is retrieved from the image service. '
                         'If source_type is snapshot then the uuid refers to a volume snapshot in the block storage '
                         'service. If source_type is volume then the uuid refers to a volume in the block storage '
                         'service.')
    volume_type = fields.String(example='default', missing=None, description='The device volume_type. This can be '
                                'used to specify the type of volume which the compute service will create and attach '
                                'to the server. If not specified, the block storage service will provide a default '
                                'volume type. It is only supported with source_type of image or snapshot.')
    clone = fields.Boolean(required=False, example=False, missing=False,
                           description='If True clone volume set using uuid')


class CreateOpsServerParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='name')
    desc = fields.String(required=True, example='test', description='name')
    project = fields.String(required=True, example='23', description='project id, uuid or name')
    tags = fields.String(example='prova', default='', description='comma separated list of tags')
    accessIPv4 = fields.String(example='', default='', description='ipv4 address')
    accessIPv6 = fields.String(example='', default='', description='ipv6 address')
    flavorRef = fields.String(required=True, example='24', description='server cpu, ram and operating system')
    # imageRef = fields.String(required=False, missing=None, description='id, uuid of an image')
    availability_zone = fields.String(required=True, example='1', description='Specify the availability zone')
    adminPass = fields.String(required=False, default='', description='The administrative password of the server.')
    networks = fields.Nested(OpsServerNetworkRequestSchema, required=True, description='A networks object', many=True,
                             allow_none=True)
    security_groups = fields.List(fields.String(example='123'), required=True,
                                  description='One or more security groups id or uuid')
    user_data = fields.String(required=False, default='',
                              description='Configuration information or scripts to use upon launch. Must be Base64 '
                                          'encoded. Pass ssh_key using base64.b64decode({"pubkey":..})')
    metadata = fields.Dict(example={'admin_pwd': ''}, required=False, description='server metadata')
    personality = fields.List(fields.Dict(example=[{'path': '/etc/banner.txt', 'contents': 'udsdsd=='}]),
                              required=False, missing=[],
                              description='The file path and contents, text only, to inject into the server at '
                                          'launch. The maximum size of the file path data is 255 bytes. The maximum '
                                          'limit is The number of allowed bytes in the decoded, rather than encoded, '
                                          'data.')
    block_device_mapping_v2 = fields.Nested(OpsServerVolumeRequestSchema, required=False, many=True, allow_none=True,
                                            description='Enables fine grained control of the block device mapping '
                                                        'for an instance')
    config_drive = fields.Boolean(example=True, default=True, missing=True,
                                  description='enable inject of metadata using config drive')
    # clone_server = fields.String(required=False, default='123', missing=None,
    #                              description='if param exist contains master server used to clone volumes')
    # clone_server_volume_type = fields.String(required=False, default='123', missing=None, description='The device '
    #                                          'volume_type. This is used to specify the type of volume which the compute'
    #                                          ' service will create and attach to the cloned server volumes.')


class CreateOpsServerRequestSchema(Schema):
    server = fields.Nested(CreateOpsServerParamRequestSchema)


class CreateOpsServerBodyRequestSchema(Schema):
    body = fields.Nested(CreateOpsServerRequestSchema, context='body')


class CreateOpsServer(OpenstackOpsServerApiView):
    tags = ['openstack']
    definitions = {
        'CreateOpsServerRequestSchema': CreateOpsServerRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateOpsServerBodyRequestSchema)
    parameters_schema = CreateOpsServerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create server
        Create server
        """
        return self.create_resource(controller, data)


class UpdateOpsServerParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateOpsServerRequestSchema(Schema):
    server = fields.Nested(UpdateOpsServerParamRequestSchema)


class UpdateOpsServerBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateOpsServerRequestSchema, context='body')


class UpdateOpsServer(OpenstackOpsServerApiView):
    tags = ['openstack']
    definitions = {
        'UpdateOpsServerRequestSchema': UpdateOpsServerRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateOpsServerBodyRequestSchema)
    parameters_schema = UpdateOpsServerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update server
        Update server
        """
        return self.update_resource(controller, oid, data)


class DeleteOpsServerRequestSchema(Schema):
    all = fields.Boolean(missing=True, default=True, context='query', description='If True delete all the server '
                         'attached volumes. If False delete only boot volume')


class DeleteOpsServerBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteOpsServerRequestSchema, context='body')


class DeleteOpsServer(OpenstackOpsServerApiView):
    tags = ['openstack']
    definitions = {
        'DeleteOpsServerRequestSchema': DeleteOpsServerRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteOpsServerBodyRequestSchema)
    parameters_schema = DeleteOpsServerRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid, all=data.get('all'))


'''
## hardware
class GetOpsServerHardwareResponseSchema(Schema):
    server_hardware = fields.Dict(required=True, example={})

class GetOpsServerHardware(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerHardwareResponseSchema': GetOpsServerHardwareResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerHardwareResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server hardware
        Get server hardware
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_hardware()
        resp = {'server_hardware':res}
        return resp
'''


class GetOpsServerConsoleResponseSchema(Schema):
    server_console = fields.Dict(required=True, example={})


class GetOpsServerConsole(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerConsoleResponseSchema': GetOpsServerConsoleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerConsoleResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server console
        Get server console

            {
                'type': 'novnc',
                'url': 'http://ctrl-liberty.nuvolacsi.it:6080/vnc_auto....'
            }
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_vnc_console()
        resp = {'server_console':res}
        return resp


class GetOpsServerNetworksResponseSchema(Schema):
    server_networks = fields.Nested(ApiObjectSmallResponseSchema, required=True, many=True, allow_none=True)


class GetOpsServerNetworks(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerNetworksResponseSchema': GetOpsServerNetworksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerNetworksResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server networks
        Get server networks
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_networks()
        resp = {'server_networks':res,
                'count':len(res)}
        return resp


class GetOpsServerVolumesParamsResponseSchema(Schema):
    pass


class GetOpsServerVolumesResponseSchema(Schema):
    server_volumes = fields.Nested(GetOpsServerVolumesParamsResponseSchema, required=True, many=True, allow_none=True)


class GetOpsServerVolumes(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerVolumesResponseSchema': GetOpsServerVolumesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerVolumesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server volumes
        Get server volumes
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_storage()
        resp = {'server_volumes':res,
                'count':len(res)}
        return resp


class GetOpsServerRuntimeAvZoneResponseSchema(Schema):
    name = fields.String(required=True, example='nova')


class GetOpsServerRuntimeHostResponseSchema(Schema):
    id = fields.String(required=True, example='0b6fd70fc49154b1a640a201717c959efb97ad449fd2cea2c6420988')
    name = fields.String(required=True, example='comp-liberty2-kvm.nuvolacsi.it')


class GetOpsServerRuntimeParamsResponseSchema(Schema):
    boot_time = fields.String(required=True, example='2016-10-19T12:26:39.000000')
    host = fields.Nested(GetOpsServerRuntimeHostResponseSchema, required=True, allow_none=True)
    resource_pool = fields.Nested(ApiObjectSmallResponseSchema, required=True, allow_none=True)
    availability_zone = fields.Nested(GetOpsServerRuntimeAvZoneResponseSchema, required=True, allow_none=True)
    server_state = fields.String(required=True, example='active')
    task = fields.String(required=True, allow_none=True, description='server active task')


class GetOpsServerRuntimeResponseSchema(Schema):
    server_runtime = fields.Nested(GetOpsServerRuntimeParamsResponseSchema, required=True, many=True, allow_none=True)


class GetOpsServerRuntime(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerRuntimeResponseSchema': GetOpsServerRuntimeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerRuntimeResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server runtime
        Get server runtime
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_runtime()
        resp = {'server_runtime': res}
        return resp


class GetOpsServerStatsResponseSchema(Schema):
    server_stats = fields.Dict(required=True)


class GetOpsServerStats(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerStatsResponseSchema': GetOpsServerStatsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerStatsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server stats
        Get server stats

        {
            'cpu0_time': 326410000000L,
            'memory': 2097152,
            'memory-actual': 2097152,
            'memory-available': 2049108,
            'memory-major_fault': 542,
            'memory-minor_fault': 5574260,
            'memory-rss': 667896,
            'memory-swap_in': 0,
            'memory-swap_out': 0,
            'memory-unused': 1665356,
            'tap033e6918-13_rx': 40355211,
            'tap033e6918-13_rx_drop': 0,
            'tap033e6918-13_rx_errors': 0,
            'tap033e6918-13_rx_packets': 627185,
            'tap033e6918-13_tx': 4006494,
            'tap033e6918-13_tx_drop': 0,
            'tap033e6918-13_tx_errors': 0,
            'tap033e6918-13_tx_packets': 11721,
            'vda_errors': -1,
            'vda_read': 163897856,
            'vda_read_req': 11610,
            'vda_write': 296491008,
            'vda_write_req': 45558
        }
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_stats()
        resp = {'server_stats':res}
        return resp

'''
## guest
class GetOpsServerGuestParamsResponseSchema(Schema):
    disk = fields.List(fields.Dict, required=True)
    guest = fields.List(fields.Dict, required=True)
    hostname = fields.String(required=True, example='tst-vm2')
    ip_address = fields.String(required=True, example='172.25.5.151')
    ip_stack = fields.List(fields.Dict(example={}), required=True)
    nics = fields.List(fields.Dict(example={}), required=True)
    screen = fields.Dict(example={}, required=True)
    tools = fields.Dict(example={}, required=True)

class GetOpsServerGuestResponseSchema(Schema):
    server_guest = fields.Nested(GetOpsServerGuestParamsResponseSchema,
                                 required=True, many=True, allow_none=True)

class GetOpsServerGuest(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerGuestResponseSchema': GetOpsServerGuestResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerGuestResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server guest
        Get server guest
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_guest_info()
        resp = {'server_guest':res}
        return resp
'''


class GetOpsServerMetadataResponseSchema(Schema):
    server_metadata = fields.Dict(required=True)


class GetOpsServerMetadata(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerMetadataResponseSchema': GetOpsServerMetadataResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerMetadataResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server metadata
        Get server metadata
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_metadata()
        resp = {'server_metadata':res,
                'count':len(res)}
        return resp


class OpsServerActionEventResponseSchema(Schema):
    event = fields.String(required=True, example='compute__do_build_and_run_instance')
    finish_time = fields.String(required=True, example='2016-10-19T12:26:39.000000')
    result = fields.String(required=True, example='Success')
    start_time = fields.String(required=True, example='2016-10-19T12:26:31.000000')
    traceback = fields.String(required=True, example=None, allow_none=True)


class OpsServerActionResponseSchema(Schema):
    action = fields.String(required=True, example='create')
    events = fields.Nested(OpsServerActionEventResponseSchema, required=False, many=True, allow_none=True)
    instance_uuid = fields.UUID(required=True, example='cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0')
    message = fields.String(required=True, example=None, allow_none=True)
    project_id = fields.UUID(required=True, example='cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0')
    request_id = fields.String(required=True, example='req-cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0')
    start_time = fields.String(required=True, example='2016-10-19T12:26:30.000000')
    user_id = fields.String(required=True, example='730cd1699f144275811400d41afa7645')


class GetOpsServerActionsResponseSchema(Schema):
    server_actions = fields.Nested(OpsServerActionResponseSchema, required=True, many=True, allow_none=True)


class GetOpsServerActions(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerActionsResponseSchema': GetOpsServerActionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerActionsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server actions
        Get server actions
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_actions()
        resp = {'server_actions': res,
                'count': len(res)}
        return resp


class GetOpsServerActionRequestSchema(GetApiObjectRequestSchema):
    aid = fields.String(required=True, context='path', description='action id')


class GetOpsServerActionResponseSchema(Schema):
    server_action = fields.Nested(OpsServerActionResponseSchema, required=True, allow_none=True)


class GetOpsServerAction(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerActionResponseSchema': GetOpsServerActionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetOpsServerActionRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerActionResponseSchema
        }
    })

    def get(self, controller, data, oid, aid, *args, **kwargs):
        """
        Get server action
        Get server action
        """
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


class SendOpsServerActionParamsVolumeRequestSchema(Schema):
    volume = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                           description='volume uuid or name')


class SendOpsServerActionParamsSetFlavorRequestSchema(Schema):
    flavor = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                           description='flavor uuid or name')


class SendOpsServerActionParamsMigrateRequestSchema(Schema):
    live = fields.Boolean(required=False, missing=True, default=True,
                          description='If True attempt to run a live migration')
    host = fields.String(required=False, example='4cdf0ea4-159a-45aa-96f2-708e461130e1', description='host uuid')


class SendServerActionParamsCloneRequestSchema(Schema):
    pass


class SendServerActionParamsRestorePointRequestSchema(Schema):
    full = fields.Boolean(required=False, missing=True, default=True,
                          description='If True make a full backup otherwise make an incremental backup')


class SendServerActionParamsDelBackupRestorePointRequestSchema(Schema):
    restore_point = fields.String(required=True, example='daidoe34344d', description='restore point id')


class SendServerActionParamsRestoreFromBackupRequestSchema(Schema):
    restore_point = fields.String(required=True, example='daidoe34344d', description='restore point id')
    name = fields.String(required=True, example='test', description='restored server name')


class SendOpsServerActionParamsRequestSchema(Schema):
    start = fields.Boolean(description='start server')
    stop = fields.Boolean(description='stop server')
    reboot = fields.Boolean(description='reboot server')
    pause = fields.Boolean(description='pause server')
    unpause = fields.Boolean(description='unpause server')
    migrate = fields.Nested(SendOpsServerActionParamsMigrateRequestSchema, description='migrate server')
    # setup_network = fields.String(description='setup server network')
    reset_state = fields.String(description='change server state')
    add_security_group = fields.Nested(SendServerActionParamsSgRequestSchema,
                                       description='add security group to server')
    del_security_group = fields.Nested(SendServerActionParamsSgRequestSchema,
                                       description='remove security group from server')
    add_volume = fields.Nested(SendOpsServerActionParamsVolumeRequestSchema, description='add volume to server')
    del_volume = fields.Nested(SendOpsServerActionParamsVolumeRequestSchema, description='remove volume from server')
    set_flavor = fields.Nested(SendOpsServerActionParamsSetFlavorRequestSchema, description='set flavor to server')
    add_snapshot = fields.Nested(SendServerActionParamsSnapshotRequestSchema, description='add server snapshot')
    del_snapshot = fields.Nested(SendServerActionParamsSnapshotRequestSchema, description='remove server snapshot')
    revert_snapshot = fields.Nested(SendServerActionParamsSnapshotRequestSchema,
                                    description='revert server to snapshot')
    # add_backup_restore_point = fields.Nested(SendServerActionParamsRestorePointRequestSchema,
    #                                          description='add backup restore point')
    # del_backup_restore_point = fields.Nested(SendServerActionParamsDelBackupRestorePointRequestSchema,
    #                                          description='delete server restore point')
    restore_from_backup = fields.Nested(SendServerActionParamsRestoreFromBackupRequestSchema,
                                        description='restore server from backup')


class SendOpsServerActionRequestSchema(Schema):
    server_action = fields.Nested(SendOpsServerActionParamsRequestSchema, required=True)


class SendOpsServerActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendOpsServerActionRequestSchema, context='body')


class SendOpsServerAction(OpenstackOpsServerApiView):
    summary = 'Send server actions'
    description = 'Send server actions'
    definitions = {
        'SendOpsServerActionRequestSchema': SendOpsServerActionRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendOpsServerActionBodyRequestSchema)
    parameters_schema = SendOpsServerActionRequestSchema
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

        return res


class OpsServerSnapshotResponseSchema(Schema):
    pass


class GetOpsServerSnapshotsResponseSchema(Schema):
    server_snapshots = fields.Nested(OpsServerSnapshotResponseSchema, equired=True, many=True, allow_none=True)


class GetOpsServerSnapshots(OpenstackOpsServerApiView):
    summary = 'Get server snapshots'
    description = 'Get server snapshots'
    definitions = {
        'GetOpsServerSnapshotsResponseSchema': GetOpsServerSnapshotsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerSnapshotsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_snapshots()
        resp = {'server_snapshots': res, 'count': len(res)}
        return resp

'''
## snapshot
class GetOpsServerSnapshotRequestSchema(GetApiObjectRequestSchema):
    pass

class GetOpsServerSnapshotResponseSchema(Schema):
    server_actions = fields.Nested(OpsServerSnapshotResponseSchema,
                                    required=True, many=True, allow_none=True)

class GetOpsServerSnapshot(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerSnapshotResponseSchema': GetOpsServerSnapshotResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerSnapshotResponseSchema
        }
    })

    def get(self, controller, data, oid, sid, *args, **kwargs):
        """
        Get server snapshot
        Get server snapshot
        """
        obj = self.get_resource_reference(controller, oid)
        if sid == 'current':
            res = obj.get_current_snapshot()
        else:
            res = obj.get_snapshots(sid)[0]
        resp = {'server_snapshot':res}
        return resp
'''


class GetOpsServerSecurityGroupsResponseSchema(Schema):
    server_security_groups = fields.Nested(ApiObjectSmallResponseSchema, required=True, many=True, allow_none=True)


class GetOpsServerSecurityGroups(OpenstackOpsServerApiView):
    definitions = {
        'GetOpsServerActionsResponseSchema': GetOpsServerActionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetOpsServerActionsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server security groups
        Get server security groups
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_security_groups()
        resp = {'server_security_groups': [sg.info() for sg in res],
                'count': len(res)}
        return resp


# class ChangeOpsServerSecurityGroupRequestSchema(Schema):
#     cmd = fields.String(example='assign', required=True, validate=OneOf(['assign', 'deassign']),
#                         description='Command. Can be assign or deassign')
#     security_group = fields.String(example='test', required=True, description='Security group id, uuid or name')
#
#
# class ChangeOpsServerSecurityGroupBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(ChangeOpsServerSecurityGroupRequestSchema, context='body')
#
#
# class ChangeOpsServerSecurityGroup(OpenstackOpsServerApiView):
#     definitions = {
#         'UpdateResourceRequestSchema': UpdateOpsServerRequestSchema,
#         'CrudApiObjectResponseSchema': CrudApiObjectResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(ChangeOpsServerSecurityGroupBodyRequestSchema)
#     parameters_schema = ChangeOpsServerSecurityGroupRequestSchema
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': CrudApiObjectResponseSchema
#         }
#     })
#
#     def put(self, controller, data, oid, *args, **kwargs):
#         """
#         Change Server SecurityGroup
#         Change Server SecurityGroup
#         """
#         server = self.get_resource_reference(controller, oid)
#         cmd = data.get('cmd', None)
#         sg = data.get('security_group', None)
#         if cmd == 'assign':
#             sg_uuid = server.assign_to_security_group(sg)
#         elif cmd == 'deassign':
#             sg_uuid = server.deassign_from_security_group(sg)
#         return {'uuid': sg_uuid}


class OpenstackServerAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/servers' % base, 'GET', ListOpsServers, {}),
            ('%s/servers/<oid>' % base, 'GET', GetOpsServer, {}),
            ('%s/servers' % base, 'POST', CreateOpsServer, {}),
            ('%s/servers/<oid>' % base, 'PUT', UpdateOpsServer, {}),
            ('%s/servers/<oid>' % base, 'DELETE', DeleteOpsServer, {}),

            # ('%s/servers/<oid>/hw' % base, 'GET', GetOpsServerHardware, {}),
            ('%s/servers/<oid>/console' % base, 'GET', GetOpsServerConsole, {}),
            ('%s/servers/<oid>/networks' % base, 'GET', GetOpsServerNetworks, {}),
            ('%s/servers/<oid>/volumes' % base, 'GET', GetOpsServerVolumes, {}),
            ('%s/servers/<oid>/runtime' % base, 'GET', GetOpsServerRuntime, {}),
            ('%s/servers/<oid>/stats' % base, 'GET', GetOpsServerStats, {}),
            # ('%s/servers/<oid>/guest' % base, 'GET', GetOpsServerGuest, {}),
            ('%s/servers/<oid>/metadata' % base, 'GET', GetOpsServerMetadata, {}),
            ('%s/servers/<oid>/actions' % base, 'GET', GetOpsServerActions, {}),
            ('%s/servers/<oid>/action/<aid>' % base, 'GET', GetOpsServerAction, {}),
            ('%s/servers/<oid>/action' % base, 'PUT', SendOpsServerAction, {}),
            ('%s/servers/<oid>/snapshots' % base, 'GET', GetOpsServerSnapshots, {}),
            # ('%s/servers/<oid>/snapshots/<sid>' % base, 'GET', GetOpsServerSnapshot, {}),
            ('%s/servers/<oid>/security_groups' % base, 'GET', GetOpsServerSecurityGroups, {}),
            # ('%s/servers/<oid>/security_groups' % base, 'PUT', ChangeOpsServerSecurityGroup, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)