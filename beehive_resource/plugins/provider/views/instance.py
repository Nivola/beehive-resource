# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from marshmallow.validate import OneOf

from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.image import ComputeImage
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.vpc import Vpc
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema,\
    ResourceResponseSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, \
    GetApiObjectRequestSchema, CrudApiObjectTaskResponseSchema, CrudApiObjectSimpleResponseSchema, \
    CrudApiTaskResponseSchema, ApiManagerError
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import ProviderAPI,\
    LocalProviderApiView, UpdateProviderResourceRequestSchema,\
    CreateProviderResourceRequestSchema


class ProviderInstance(LocalProviderApiView):
    resclass = ComputeInstance
    parentclass = ComputeZone


class ListInstancesRequestSchema(ListResourcesRequestSchema):
    compute_zone = fields.String(context='query', description='super zone id or uuid')
    security_group = fields.String(context='query', description='security group id or uuid')
    vpc = fields.String(context='query', description='vpc id or uuid')
    image = fields.String(context='query', description='image id or uuid')
    flavor = fields.String(context='query', description='flavor id or uuid')
    hypervisor = fields.String(context='query', description='hypervisor name like vsphere or openstack')
    availability_zone = fields.String(context='query', description='availability zone id')


class InstanceFlavorResponseSchema(Schema):
    vcpus = fields.Integer(required=True, example=2, description='virtual cpu number')
    disk = fields.Integer(required=True, example=10, description='root disk siez in GB')
    bandwidth = fields.Integer(required=True, example=1000, description='network bandwidth')
    memory = fields.Integer(required=True, example=2048, description='memory in MB')
    uuid = fields.String(required=True, example='2887', description='flavor uuid')


class InstanceImageResponseSchema(Schema):
    os_ver = fields.String(required=True, example='7.1', description='operating system version')
    os = fields.String(required=True, example='Centos', description='operating system name')
    uuid = fields.String(required=True, example='2887', description='image uuid')


class InstanceNetworkResponseSchema(Schema):
    ip = fields.String(required=True, example='10.102.185.121', description='ip address')
    uuid = fields.String(required=True, example='2887', description='vpc uuid')
    name = fields.String(required=True, example='DCCTP-tst-BE', description='vpc name')
    subnet = fields.String(required=True, example='10.102.78.90/24', description='subnet cidr')


class InstanceBlockDeviceResponseSchema(Schema):
    boot_index = fields.Integer(required=False, example=0,
                                description='boot index of the disk. 0 for the main disk')
    volume_size = fields.Integer(required=False, example=10, description='Size of volume in GB')
    bootable = fields.Boolean(example=True, description='True if volume is bootable')
    encrypted = fields.Boolean(example=False, description='True if volume is encrypted')


class InstanceAttributesResponseSchema(Schema):
    configs = fields.Dict(required=True, example={}, description='custom config')
    type = fields.String(required=True, example='openstack', description='instance type: vsphere or openstack')


class InstanceResponseSchema(ResourceResponseSchema):
    flavor = fields.Nested(InstanceFlavorResponseSchema, required=True, description='flavor', allow_none=True)
    image = fields.Nested(InstanceImageResponseSchema, required=True, description='image', allow_none=True)
    vpcs = fields.Nested(InstanceNetworkResponseSchema, required=True, many=True, description='vpcc list',
                         allow_none=True)
    block_device_mapping = fields.Nested(InstanceBlockDeviceResponseSchema, required=True, many=True,
                                         description='block device mapping list', allow_none=True)
    attributes = fields.Nested(InstanceAttributesResponseSchema, required=True, description='custom attributes',
                               allow_none=True)


class ListInstancesResponseSchema(PaginatedResponseSchema):
    instances = fields.Nested(InstanceResponseSchema, many=True, required=True, allow_none=True)


class ListInstances(ProviderInstance):
    summary = 'List instances'
    description = 'List instances'
    definitions = {
        'ListInstancesRequestSchema': ListInstancesRequestSchema,
        'ListInstancesResponseSchema': ListInstancesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListInstancesRequestSchema)
    parameters_schema = ListInstancesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListInstancesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        zone_id = data.get('compute_zone', None)
        sg_id = data.get('security_group', None)
        vpc_id = data.get('vpc', None)
        image_id = data.get('image', None)
        flavor_id = data.get('flavor', None)
        hypervisor = data.get('hypervisor', None)
        availability_zone = data.get('availability_zone', None)

        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, **data)
        elif sg_id is not None:
            return self.get_linked_resources(controller, sg_id, SecurityGroup, 'security-group', **data)
        elif vpc_id is not None:
            return self.get_linked_resources(controller, vpc_id, Vpc, 'vpc', **data)
        elif image_id is not None:
            return self.get_linked_resources(controller, image_id, ComputeImage, 'image', **data)
        elif flavor_id is not None:
            return self.get_linked_resources(controller, flavor_id, ComputeFlavor, 'flavor', **data)
        if hypervisor is not None:
            data['json_attribute_contain'] = {'field': 'type', 'value': '"%s"' % hypervisor}
        if availability_zone is not None:
            availability_zone_id = controller.get_simple_resource(availability_zone).oid
            if 'json_attribute_contain' in data:
                data['json_attribute_contain'] = [data['json_attribute_contain']]
                data['json_attribute_contain'].append(
                    {'field': 'availability_zone', 'value': '%s' % availability_zone_id})
            else:
                data['json_attribute_contain'] = {'field': 'availability_zone', 'value': '%s' % availability_zone_id}
        self.logger.warn(data)

        return self.get_resources(controller, **data)


class GetInstanceResponseSchema(Schema):
    instance = fields.Nested(InstanceResponseSchema, required=True, allow_none=True)


class GetInstance(ProviderInstance):
    summary = 'Get instance'
    description = 'Get instance'
    definitions = {
        'GetInstanceResponseSchema': GetInstanceResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateInstanceBlockDeviceRequestSchema(Schema):
    boot_index = fields.Integer(required=False, example=0,
                                description='boot index of the disk. 0 for the main disk')
    source_type = fields.String(required=False, example='volume', description='The source type of the volume. A '
                                'valid value is: snapshot - creates a volume backed by the given volume snapshot '
                                'referenced via the block_device_mapping_v2.uuid parameter and attaches it to the '
                                'server; volume: uses the existing persistent volume referenced via the block_device_'
                                'mapping_v2.uuid parameter and attaches it to the server; image: creates an '
                                'image-backed volume in the block storage service and attaches it to the server;'
                                'blank: this will be a blank persistent volume', missing=None,
                                validate=OneOf(['snapshot', 'volume', 'image', None]))
    volume_size = fields.Integer(required=False, example=10, description='Size of volume in GB')
    tag = fields.String(example='default', missing='default', description='datastore tag. Use to select datastore')
    uuid = fields.String(example='default', missing=None, description='This is the uuid of source resource. The uuid '
                         'points to different resources based on the source_type. If source_type is image, the block '
                         'device is created based on the specified image which is retrieved from the image service. '
                         'If source_type is snapshot then the uuid refers to a volume snapshot in the block storage '
                         'service. If source_type is volume then the uuid refers to a volume in the block storage '
                         'service.')
    flavor = fields.String(required=False, example='default', description='The volume flavor. This can '
                           'be used to specify the type of volume which the compute service will create and attach '
                           'to the server.')


class CreateInstanceNetworkIpRequestSchema(Schema):
    ip = fields.String(required=False, example='10.102.185.105', description='ip address')
    hostname = fields.String(required=False, example='instance-vsphere01.tstsddc.csi.it', description='host name')
    dns_search = fields.String(required=False, example='tstsddc.csi.it', description='dns search path')


class CreateInstanceNetworkRequestSchema(Schema):
    vpc = fields.String(required=True, example='50', description='id or uuid of the vpc')
    subnet = fields.String(required=True, example='10.102.167.90/24', description='subnet definition')
    fixed_ip = fields.Nested(CreateInstanceNetworkIpRequestSchema, required=False, allow_none=True,
                             description='network fixed ip configuration. Setup ip, hostname')


class CreateInstanceParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
    availability_zone = fields.String(example='2', required=True, description='site id or uuid')
    multi_avz = fields.Boolean(example=False, missing=True, required=False,
                               description='Define if instance must be deployed to work in all the availability zones')
    host_group = fields.String(example='default', missing='default', required=False,
                               description='Define the optional host group where put the instance')
    type = fields.String(required=True, example='vsphere', description='type of the instance: vsphere or openstack')
    flavor = fields.String(required=True, example='12', description='id or uuid of the flavor')
    admin_pass = fields.String(required=True, example='xxxx', description='admin password to set')
    networks = fields.Nested(CreateInstanceNetworkRequestSchema, many=True, required=True, allow_none=True,
                             description='list of networks')
    block_device_mapping = fields.Nested(CreateInstanceBlockDeviceRequestSchema, many=True, required=True,
                                         description='list of block device', allow_none=True)
    security_groups = fields.List(fields.String(example=12), required=True,  description='list of security group ids')
    key_name = fields.String(required=False, example='prova', default='', description='ssh key name or uuid',
                             allow_none=True)
    user_data = fields.String(required=False, example='eyJwdWJrZXkiOiAic3No....', default='', allow_none=True,
                              description='Must be Base64 encoded')
    metadata = fields.Dict(required=False, example={'MyName': 'Apache1'}, description='custom metadata',
                           missing={})
    personality = fields.List(fields.Dict(example=[{'path': '/etc/banner.txt', 'contents': 'dsdsd=='}]),
                              required=False, description='custom file to inject', missing=[])
    resolve = fields.Boolean(example=False, missing=True, required=False,
                             description='define if instance must registered on the availability_zone dns zone')
    manage = fields.Boolean(example=False, missing=True, required=False,
                            description='define if instance must be registered in ssh module for management')


class CreateInstanceRequestSchema(Schema):
    instance = fields.Nested(CreateInstanceParamRequestSchema)


class CreateInstanceBodyRequestSchema(Schema):
    body = fields.Nested(CreateInstanceRequestSchema, context='body')


class CreateInstance(ProviderInstance):
    summary = 'Create instance'
    description = 'Create instance'
    definitions = {
        'CreateInstanceRequestSchema': CreateInstanceRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateInstanceBodyRequestSchema)
    parameters_schema = CreateInstanceRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateInstanceParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateInstanceRequestSchema(Schema):
    instance = fields.Nested(UpdateInstanceParamRequestSchema)


class UpdateInstanceBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateInstanceRequestSchema, context='body')


class UpdateInstance(ProviderInstance):
    summary = 'Update instance'
    description = 'Update instance'
    definitions = {
        'UpdateInstanceRequestSchema': UpdateInstanceRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateInstanceBodyRequestSchema)
    parameters_schema = UpdateInstanceRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


# class PatchInstanceRequestSchema(Schema):
#     pass
#
#
# class PatchInstanceBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(PatchInstanceRequestSchema, context='body')
#
#
# class PatchInstance(ProviderInstance):
#     definitions = {
#         'PatchInstanceRequestSchema': PatchInstanceRequestSchema,
#         'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(PatchInstanceBodyRequestSchema)
#     parameters_schema = PatchInstanceRequestSchema
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectTaskResponseSchema
#         }
#     })
#
#     def patch(self, controller, data, oid, *args, **kwargs):
#         """
#         Patch instance
#         Patch instance
#         """
#         return self.patch_resource(controller, oid, data)


class DeleteInstance(ProviderInstance):
    summary = 'Patch instance'
    description = 'Patch instance'
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


# class CloneInstanceBlockDeviceRequestSchema(Schema):
#     flavor = fields.String(required=True, example='default', description='The volume flavor. This can '
#                            'be used to specify the type of volume which the compute service will create and attach '
#                            'to the server.')
#
#
# class CloneInstanceParamRequestSchema(CreateProviderResourceRequestSchema):
#     compute_zone = fields.String(required=True, example='1', description='parent compute zone id or uuid')
#     availability_zone = fields.String(example='2', required=True, description='site id or uuid')
#     multi_avz = fields.Boolean(example=False, missing=True, required=False,
#                                description='Define if instance must be deployed to work in all the availability zones')
#     host_group = fields.String(example='default', missing='default', required=False,
#                                description='Define the optional host group where put the instance')
#     type = fields.String(required=True, example='vsphere', description='type of the instance: vsphere or openstack')
#     flavor = fields.String(required=True, example='12', description='id or uuid of the flavor')
#     admin_pass = fields.String(required=True, example='xxxx', description='admin password to set')
#     networks = fields.Nested(CreateInstanceNetworkRequestSchema, many=True, required=True, allow_none=True,
#                              description='list of networks')
#     block_device_mapping = fields.Nested(CloneInstanceBlockDeviceRequestSchema, many=False, required=True,
#                                          description='block device config', allow_none=True)
#     security_groups = fields.List(fields.String(example=12), required=True,  description='list of security group ids')
#     key_name = fields.String(required=False, example='prova', default='', description='ssh key name or uuid',
#                              allow_none=True)
#     user_data = fields.String(required=False, example='eyJwdWJrZXkiOiAic3No....', default='', allow_none=True,
#                               description='Must be Base64 encoded')
#     metadata = fields.Dict(required=False, example={'MyName': 'Apache1'}, description='custom metadata',
#                            missing={})
#     personality = fields.List(fields.Dict(example=[{'path': '/etc/banner.txt', 'contents': 'dsdsd=='}]),
#                               required=False, description='custom file to inject', missing=[])
#     resolve = fields.Boolean(example=False, missing=True, required=False,
#                              description='Define if instance must registered on the availability_zone dns zone')
#
#
# class CloneInstanceRequestSchema(Schema):
#     instance = fields.Nested(CloneInstanceParamRequestSchema)
#
#
# class CloneInstanceBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(CloneInstanceRequestSchema, context='body')
#
#
# class CloneInstance(ProviderInstance):
#     summary = 'Clone instance'
#     description = 'Clone instance'
#     definitions = {
#         'CloneInstanceRequestSchema': CloneInstanceRequestSchema,
#         'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(CloneInstanceBodyRequestSchema)
#     parameters_schema = CloneInstanceRequestSchema
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectTaskResponseSchema
#         }
#     })
#
#     def post(self, controller, data, oid, *args, **kwargs):
#         return self.clone_resource(controller, oid, data)


class GetManageResponseSchema(Schema):
    is_managed = fields.Boolean(required=True, description='Return True if compute zone is managed by ssh module')


class GetManage(ProviderInstance):
    summary = 'Check compute instance is managed'
    description = 'Check compute instance is managed'
    definitions = {
        'GetManageResponseSchema': GetManageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetManageResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        compute_instance = self.get_resource_reference(controller, oid)
        res = compute_instance.is_managed()
        return {'is_managed': res}


class AddManageRequestParamSchema(Schema):
    user = fields.String(required=False, description='Node user', missing='root', example='root')
    password = fields.String(required=False, description='Node user password', missing='', example='test')
    key = fields.String(required=True, description='ssh key name or uuid', example='prova123')


class AddManageRequestSchema(Schema):
    manage = fields.Nested(AddManageRequestParamSchema, required=True, description='Management params')


class AddManageRequestBodySchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddManageRequestSchema, context='body')


class AddManageResponseSchema(Schema):
    manage = fields.Boolean(required=True, description='Ssh group uuid')


class AddManage(ProviderInstance):
    summary = 'Manage compute instance'
    description = 'Manage compute instance'
    definitions = {
        'AddManageRequestSchema': AddManageRequestSchema,
        'AddManageResponseSchema': AddManageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddManageRequestBodySchema)
    parameters_schema = AddManageRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': AddManageResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        compute_instance = self.get_resource_reference(controller, oid)
        res = compute_instance.manage(**data.get('manage'))
        return {'manage': res}


class DeleteManage(ProviderInstance):
    summary = 'Unmanage compute instance'
    description = 'Unmanage compute instance'
    definitions = {
        'CrudApiObjectSimpleResponseSchema': CrudApiObjectSimpleResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        204: {
            'description': 'success'
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        compute_instance = self.get_resource_reference(controller, oid)
        res = compute_instance.unmanage()
        return None


class InstanceActionEventResponseSchema(Schema):
    event = fields.String(required=True, example='compute__do_build_and_run_instance')
    finish_time = fields.String(required=True, example='2016-10-19T12:26:39.000000')
    result = fields.String(required=True, example='Success')
    start_time = fields.String(required=True, example='2016-10-19T12:26:31.000000')
    traceback = fields.String(required=True, example=None, allow_none=True)


class InstanceActionResponseSchema(Schema):
    action = fields.String(required=True, example='create')
    events = fields.Nested(InstanceActionEventResponseSchema, required=False, many=True, allow_none=True)
    instance_uuid = fields.UUID(required=True, example='cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0')
    message = fields.String(required=True, example=None, allow_none=True)
    project_id = fields.UUID(required=True, example='cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0')
    request_id = fields.String(required=True, example='req-cf8cbfc8-d602-4bae-94b7-75f9b8c35ba0')
    start_time = fields.String(required=True, example='2016-10-19T12:26:30.000000')
    user_id = fields.String(required=True, example='730cd1699f144275811400d41afa7645')


class GetInstanceActionsResponseSchema(Schema):
    actions = fields.Nested(InstanceActionResponseSchema, required=True, many=True, allow_none=True)


class GetInstanceActions(ProviderInstance):
    summary = 'Get server actions'
    description = 'Get server actions'
    definitions = {
        'GetInstanceActionsResponseSchema': GetInstanceActionsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceActionsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_actions()
        resp = {'actions': res,
                'count': len(res)}
        return resp


class GetInstanceActionRequestSchema(GetApiObjectRequestSchema):
    aid = fields.String(required=True, context='path', description='action id')


class GetInstanceActionResponseSchema(Schema):
    action = fields.Nested(InstanceActionResponseSchema, required=True, allow_none=True)


class GetInstanceAction(ProviderInstance):
    summary = 'Get server action'
    description = 'Get server action'
    definitions = {
        'GetInstanceActionResponseSchema': GetInstanceActionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetInstanceActionRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceActionResponseSchema
        }
    })

    def get(self, controller, data, oid, aid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_actions(action_id=aid)[0]
        resp = {'action': res}
        return resp


class SendInstanceActionParamsSnapshotRequestSchema(Schema):
    snapshot = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                             description='snapshot name when add or uuid when delete')


class SendInstanceActionParamsSgRequestSchema(Schema):
    security_group = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                                   description='security group uuid')


class SendInstanceActionParamsVolumeRequestSchema(Schema):
    volume = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                           description='volume uuid or name')


class SendInstanceActionParamsSetFlavorRequestSchema(Schema):
    flavor = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                           description='flavor uuid or name')


class SendInstanceActionParamsMigrateRequestSchema(Schema):
    live = fields.Boolean(required=False, missing=True, default=False,
                          description='If True attempt to run a live migration')
    host = fields.String(required=False, example='4cdf0ea4-159a-45aa-96f2-708e461130e1', description='host uuid')


class SendInstanceActionParamsAddUserRequestSchema(Schema):
    user_name = fields.String(required=True, example='prova', description='user name')
    user_pwd = fields.String(required=True, example='prova', description='user password')
    user_ssh_key = fields.String(required=False, example='test-key', missing=None, description='user ssh key')


class SendInstanceActionParamsDelUserRequestSchema(Schema):
    user_name = fields.String(required=True, example='prova', description='user name')


class SendInstanceActionParamsSetUserPwdRequestSchema(Schema):
    user_name = fields.String(required=True, example='prova', description='user name')
    user_pwd = fields.String(required=True, example='prova', description='user password')


class SendInstanceActionParamsSetSshKeyRequestSchema(Schema):
    user_name = fields.String(required=True, example='prova', description='user name')
    user_ssh_key = fields.String(required=True, example='prova', description='user ssh key')


class SendInstanceActionParamsUnsetSshKeyRequestSchema(Schema):
    user_name = fields.String(required=True, example='prova', description='user name')
    user_ssh_key = fields.String(required=True, example='prova', description='user ssh key')


class SendInstanceActionParamsEnableMonitoringRequestSchema(Schema):
    host_group = fields.String(required=False, example='Csi.Datacenter.test', allow_none=True,
                               description='the account hostgroup in the form Organization.Division.Account the '
                                           'compute instance to monitor belongs to')
    templates = fields.String(required=False, example='db,linux', allow_none=True,
                              description='comma separated list of zabbix agent template name')


class SendInstanceActionParamsDisableMonitoringRequestSchema(Schema):
    pass


class SendInstanceActionParamsDisableLoggingRequestSchema(Schema):
    pass


class SendInstanceActionParamsEnableLoggingRequestSchema(Schema):
    host_group = fields.String(required=False, example='Csi.Datacenter.test', allow_none=True,
                               description='the account hostgroup in the form Organization.Division.Account the '
                                           'compute instance to monitor belongs to')
    files = fields.String(required=False, example='db,linux', allow_none=True,
                          description='comma separated list of files to capture')
    logstash_port = fields.Integer(required=False, allow_none=True, missing=5044, example=5044,
                                   description='logstash pipeline port')


class SendInstanceActionParamsEnableLogModuleRequestSchema(Schema):
    module = fields.String(required=False, example='apache, mysql', allow_none=True,
                           description='comma separated list of files to capture')
    module_params = fields.Dict(default={}, allow_none=True)


class SendInstanceActionParamsDisableLogModuleRequestSchema(Schema):
    module = fields.String(required=False, example='apache, mysql', allow_none=True,
                           description='comma separated list of files to capture')
    module_params = fields.Dict(default={}, allow_none=True)


class SendInstanceActionParamsEnableBackupRequestSchema(Schema):
    pass


class SendInstanceActionParamsDisableBackupRequestSchema(Schema):
    pass


class SendInstanceActionParamsAddBackupRestorePointRequestSchema(Schema):
    full = fields.Boolean(required=False, missing=True, default=True,
                          description='If True make a full backup otherwise make an incremental backup')


class SendInstanceActionParamsDelBackupRestorePointRequestSchema(Schema):
    restore_point = fields.String(required=True, example='daidoe34344d', description='restore point id')


class SendInstanceActionParamsRestoreFromBackupRequestSchema(Schema):
    restore_point = fields.String(required=True, example='daidoe34344d', description='restore point id')
    instance_name = fields.String(required=True, example='test', description='restored instance name')


class SendInstanceActionParamsRequestSchema(Schema):
    start = fields.Boolean(description='start server')
    stop = fields.Boolean(description='stop server')
    reboot = fields.Boolean(description='reboot server')
    pause = fields.Boolean(description='pause server')
    unpause = fields.Boolean(description='unpause server')
    migrate = fields.Nested(SendInstanceActionParamsMigrateRequestSchema, description='migrate server')
    # setup_network = fields.String(description='setup server network')
    reset_state = fields.String(description='change server state')
    add_volume = fields.Nested(SendInstanceActionParamsVolumeRequestSchema, description='add volume to server')
    del_volume = fields.Nested(SendInstanceActionParamsVolumeRequestSchema, description='remove volume from server')
    set_flavor = fields.Nested(SendInstanceActionParamsSetFlavorRequestSchema, description='set flavor to server')
    add_snapshot = fields.Nested(SendInstanceActionParamsSnapshotRequestSchema, description='add server snapshot')
    del_snapshot = fields.Nested(SendInstanceActionParamsSnapshotRequestSchema, description='remove server snapshot')
    revert_snapshot = fields.Nested(SendInstanceActionParamsSnapshotRequestSchema,
                                    description='revert server to snapshot')
    add_security_group = fields.Nested(SendInstanceActionParamsSgRequestSchema,
                                       description='add security group to server')
    del_security_group = fields.Nested(SendInstanceActionParamsSgRequestSchema,
                                       description='remove security group from server')
    add_user = fields.Nested(SendInstanceActionParamsAddUserRequestSchema, description='add instance user')
    del_user = fields.Nested(SendInstanceActionParamsDelUserRequestSchema, description='delete instance user')
    set_user_pwd = fields.Nested(SendInstanceActionParamsSetUserPwdRequestSchema,
                                 description='set instance user password')
    set_ssh_key = fields.Nested(SendInstanceActionParamsSetSshKeyRequestSchema, description='set instance user ssh key')
    unset_ssh_key = fields.Nested(SendInstanceActionParamsUnsetSshKeyRequestSchema,
                                  description='unset instance user ssh key')
    enable_monitoring = fields.Nested(SendInstanceActionParamsEnableMonitoringRequestSchema,
                                      description='enable resources monitoring over compute instance')
    disable_monitoring = fields.Nested(SendInstanceActionParamsDisableMonitoringRequestSchema,
                                       description='disable resources monitoring over compute instance')
    enable_logging = fields.Nested(SendInstanceActionParamsEnableLoggingRequestSchema,
                                   description='enable log forwarding over compute instance')
    disable_logging = fields.Nested(SendInstanceActionParamsDisableLoggingRequestSchema,
                                    description='disable log forwarding over compute instance')
    enable_log_module = fields.Nested(SendInstanceActionParamsEnableLogModuleRequestSchema,
                                      description='enable log module over compute instance')
    disable_log_module = fields.Nested(SendInstanceActionParamsDisableLogModuleRequestSchema,
                                       description='disable log module over compute instance')
    #enable_backup = fields.Nested(SendInstanceActionParamsEnableBackupRequestSchema,
    #                              description='enable compute instance backup')
    #disable_backup = fields.Nested(SendInstanceActionParamsDisableBackupRequestSchema,
    #                               description='disable compute instance backup')
    #add_backup_restore_point = fields.Nested(SendInstanceActionParamsAddBackupRestorePointRequestSchema,
    #                                         description='add compute instance restore point')
    #del_backup_restore_point = fields.Nested(SendInstanceActionParamsDelBackupRestorePointRequestSchema,
    #                                         description='delete compute instance restore point')
    restore_from_backup = fields.Nested(SendInstanceActionParamsRestoreFromBackupRequestSchema,
                                        description='restore compute instance from backup')


class SendInstanceActionRequestSchema(Schema):
    action = fields.Nested(SendInstanceActionParamsRequestSchema, required=True)
    schedule = fields.Dict(required=False, missing=None, description='schedule to use when you want to run a scheduled '
                                                                     'action')


class SendInstanceActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendInstanceActionRequestSchema, context='body')


class SendInstanceAction(ProviderInstance):
    summary = 'Send server action'
    description = 'Send server action'
    definitions = {
        'SendInstanceActionRequestSchema': SendInstanceActionRequestSchema,
        'CrudApiTaskResponseSchema': CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendInstanceActionBodyRequestSchema)
    parameters_schema = SendInstanceActionRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        from beehive_resource.container import Resource

        instance: Resource = self.get_resource_reference(controller, oid)
        actions = data.get('action')
        schedule = data.get('schedule')
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {'param': params}
        instance.check_active()
        if action in instance.actions:
            if schedule is not None:
                task = instance.scheduled_action(action, schedule=schedule, params=params)
            else:
                task = instance.action(action, **params)
        else:
            raise ApiManagerError('Action %s not supported for instance' % action)

        return task


class GetInstanceConsoleParamsResponseSchema(Schema):
    url = fields.String(required=True, example='console url')
    type = fields.String(required=True, example='console type')


class GetInstanceConsoleResponseSchema(Schema):
    console = fields.Nested(GetInstanceConsoleParamsResponseSchema, required=True, many=True, allow_none=True)


class GetInstanceConsole(ProviderInstance):
    summary = 'Get server console'
    description = 'Get server console'
    definitions = {
        'GetInstanceConsoleResponseSchema': GetInstanceConsoleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceConsoleResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_console()
        resp = {'console': res}
        return resp


class RunInstanceCommandRequestSchema(Schema):
    command = fields.String(required=True, example='ls -l', description='command to execute')


class RunInstanceCommandBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(RunInstanceCommandRequestSchema, context='body')


class RunInstanceCommandResponseSchema(Schema):
    output = fields.Dict(required=True, description='command output')


class RunInstanceCommand(ProviderInstance):
    summary = 'Run command on server'
    description = 'Run command on server'
    definitions = {
        'RunInstanceCommandRequestSchema': RunInstanceCommandRequestSchema,
        'RunInstanceCommandResponseSchema': RunInstanceCommandResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(RunInstanceCommandBodyRequestSchema)
    parameters_schema = RunInstanceCommandRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': RunInstanceCommandResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        obj : ComputeInstance = self.get_resource_reference(controller, oid)
        res = obj.run_ad_hoc_command(data.get('command'))
        resp = {'output': res}
        return resp


class GetInstanceDnsResponseSchema(Schema):
    dns = fields.Dict(required=True)


class GetInstanceDns(ProviderInstance):
    summary = 'Get server dns recorda'
    description = 'Get server dns recorda'
    definitions = {
        'GetInstanceDnsResponseSchema': GetInstanceDnsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceDnsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj: ComputeInstance = self.get_resource_reference(controller, oid, run_customize=False)
        res = obj.get_dns_recorda()
        if res is not None:
            res = res.detail()
        else:
            res = {}
        resp = {'dns': res}
        return resp


class SetInstanceDns(ProviderInstance):
    summary = 'Set server dns recorda'
    description = 'Set server dns recorda'
    definitions = {
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        obj: ComputeInstance = self.get_resource_reference(controller, oid, run_customize=False)

        # check instance status
        if obj.get_base_state() != 'ACTIVE':
            raise ApiManagerError('Instance %s is not in ACTIVE state' % obj.uuid)

        res = obj.set_dns_recorda(force=True, ttl=30)
        resp = {'uuid': res}
        return resp


class UnSetInstanceDns(ProviderInstance):
    summary = 'Unset server dns recorda'
    description = 'Unset server dns recorda'
    definitions = {
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid, run_customize=False)

        # check instance status
        if obj.get_base_state() != 'ACTIVE':
            raise ApiManagerError('Instance %s is not in ACTIVE state' % obj.uuid)

        res = obj.unset_dns_recorda()
        resp = {'uuid': res}
        return resp


class OpsServerSnapshotResponseSchema(Schema):
    pass


class GetInstanceSnapshotsResponseSchema(Schema):
    snapshots = fields.Nested(OpsServerSnapshotResponseSchema, required=True, many=True, allow_none=True)


class GetInstanceSnapshots(ProviderInstance):
    summary = 'Get instance snapshots'
    description = 'Get instance snapshots'
    definitions = {
        'GetInstanceSnapshotsResponseSchema': GetInstanceSnapshotsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceSnapshotsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_snapshots()
        resp = {'snapshots': res, 'count': len(res)}
        return resp


class GetInstanceBackupJobResponseSchema(Schema):
    id = fields.String(required=True, example='job1', description='job id')
    name = fields.String(required=True, example='job1', description='job name')
    created = fields.String(required=True, example='job1', description='job creation date')
    updated = fields.String(required=True, example='job1', description='job update date')
    error = fields.String(required=True, example='job1', description='job error')
    usage = fields.String(required=True, example='job1', description='job storage usage')
    status = fields.String(required=True, example='job1', description='job status')
    type = fields.String(required=True, example='job1', description='job type')
    schedule = fields.Dict(required=True, example='job1', description='job schedule')


class GetInstanceBackupRestorePointResponseSchema(Schema):
    id = fields.String(required=True, example='job1', description='restore point id')
    name = fields.String(required=True, example='job1', description='restore point name')
    desc = fields.String(required=True, example='job1', description='restore point description')
    created = fields.String(required=True, example='job1', description='restore point creation date')
    type = fields.String(required=True, example='job1', description='restore point type')
    status = fields.String(required=True, example='job1', description='restore point status')


class GetInstanceBackupResponseSchema(Schema):
    job = fields.Nested(GetInstanceBackupJobResponseSchema, required=True, many=False, allow_none=True)
    restore_points = fields.Nested(GetInstanceBackupRestorePointResponseSchema, required=True, many=True, allow_none=True)


class GetInstanceBackup(ProviderInstance):
    summary = 'Get instance backup info'
    description = 'Get instance backup info'
    definitions = {
        'GetInstanceBackupResponseSchema': GetInstanceBackupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceBackupResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):

        obj: ComputeInstance = self.get_resource_reference(controller, oid)
        resp = obj.get_physical_backup_status()
        return resp


class GetInstanceBackupRestoreResponseSchema(Schema):
    id = fields.String(required=True, example='job1', description='restore point id')
    name = fields.String(required=True, example='job1', description='restore point name')
    desc = fields.String(required=True, example='job1', description='restore point description')
    created = fields.String(required=True, example='job1', description='restore point creation date')
    type = fields.String(required=True, example='job1', description='restore point type')
    status = fields.String(required=True, example='job1', description='restore point status')


class GetInstanceBackupRestoresResponseSchema(Schema):
    restores = fields.Nested(GetInstanceBackupRestoreResponseSchema, required=True, many=True, allow_none=True)


class GetInstanceBackupRestoresRequestSchema(GetApiObjectRequestSchema):
    sid = fields.String(required=True, description='snapshot id', context='path')


class GetInstanceBackupRestores(ProviderInstance):
    summary = 'Get instance backup info'
    description = 'Get instance backup info'
    definitions = {
        'GetInstanceBackupRestoresResponseSchema': GetInstanceBackupRestoresResponseSchema,
        'GetInstanceBackupRestoresRequestSchema': GetInstanceBackupRestoresRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetInstanceBackupRestoresRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetInstanceBackupRestoresResponseSchema
        }
    })

    def get(self, controller, data, oid, sid, *args, **kwargs):
        obj = self.get_resource_reference(controller, oid)
        resp = obj.get_physical_backup_restore_status(sid)
        return resp


class InstanceProviderAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: super_zone, security_group, vpc, network, image, flavor
            ('%s/instances' % base, 'GET', ListInstances, {}),
            ('%s/instances/<oid>' % base, 'GET', GetInstance, {}),
            ('%s/instances' % base, 'POST', CreateInstance, {}),
            ('%s/instances/<oid>' % base, 'PUT', UpdateInstance, {}),
            # ('%s/instances/<oid>' % base, 'PATCH', PatchInstance, {}),
            ('%s/instances/<oid>' % base, 'DELETE', DeleteInstance, {}),
            # ('%s/instances/<oid>/clone' % base, 'POST', CloneInstance, {}),

            ('%s/instances/<oid>/manage' % base, 'GET', GetManage, {}),
            ('%s/instances/<oid>/manage' % base, 'POST', AddManage, {}),
            ('%s/instances/<oid>/manage' % base, 'DELETE', DeleteManage, {}),

            ('%s/instances/<oid>/actions' % base, 'GET', GetInstanceActions, {}),
            ('%s/instances/<oid>/actions/<aid>' % base, 'GET', GetInstanceAction, {}),
            ('%s/instances/<oid>/actions' % base, 'PUT', SendInstanceAction, {}),

            ('%s/instances/<oid>/console' % base, 'GET', GetInstanceConsole, {}),

            ('%s/instances/<oid>/command' % base, 'PUT', RunInstanceCommand, {}),

            ('%s/instances/<oid>/dns' % base, 'GET', GetInstanceDns, {}),
            ('%s/instances/<oid>/dns' % base, 'POST', SetInstanceDns, {}),
            ('%s/instances/<oid>/dns' % base, 'DELETE', UnSetInstanceDns, {}),

            ('%s/instances/<oid>/snapshots' % base, 'GET', GetInstanceSnapshots, {}),

            ('%s/instances/<oid>/backup/restore_points' % base, 'GET', GetInstanceBackup, {}),
            ('%s/instances/<oid>/backup/restore_points/<sid>/restores' % base, 'GET', GetInstanceBackupRestores, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
