# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import logging
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectTaskResponseSchema, CrudApiTaskResponseSchema
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from flasgger import fields, Schema
from marshmallow.validate import OneOf

from beecell.swagger import SwaggerHelper

logger = logging.getLogger(__name__)


class OpenstackShareApiView(OpenstackApiView):
    resclass = OpenstackShare
    parentclass = OpenstackProject


class ListSharesRequestSchema(ListResourcesRequestSchema):
    pass


class ListSharesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSharesResponseSchema(PaginatedResponseSchema):
    shares = fields.Nested(ListSharesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListShares(OpenstackShareApiView):
    summary = 'List shares'
    description = 'List shares'
    tags = ['openstack']
    definitions = {
        'ListSharesResponseSchema': ListSharesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSharesRequestSchema)
    parameters_schema = ListSharesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSharesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, **data)


class GetShareResponseSchema(Schema):
    share = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetShare(OpenstackShareApiView):
    summary = 'Get share'
    description = 'Get share'
    tags = ['openstack']
    definitions = {
        'GetShareResponseSchema': GetShareResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetShareResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class ListShareTypesRequestSchema(ListResourcesRequestSchema):
    container = fields.String(required=True, example='12', description='Container id, uuid or name', context='query')


class ListShareTypesParamsResponseSchema(ResourceResponseSchema):
    required_extra_specs = fields.Dict(required=True, example={}, description='required extra specs')
    extra_specs = fields.Dict(required=True, example={}, description='extra specs')
    id = fields.String(required=True, example='103c9cb9-00cf-4cf5-a93f-4bd4101dbfaf', description='share type id')
    name = fields.String(required=True, example='netapp-cifs-566', description='share type name')


class ListShareTypesResponseSchema(PaginatedResponseSchema):
    share_types = fields.Nested(ListShareTypesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListShareTypes(OpenstackShareApiView):
    summary = 'List share types'
    description = 'List share types'
    tags = ['openstack']
    definitions = {
        'ListSharesResponseSchema': ListSharesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSharesRequestSchema)
    parameters_schema = ListSharesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSharesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        cid = data.get('container')
        container = controller.get_container(cid)
        res = container.get_manila_share_type_list()
        return {'share_types': res}


class CreateShareParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, example='test', description='name')
    desc = fields.String(required=False, example='test', description='name')
    project = fields.String(required=True, example='23', description='project id, uuid or name')
    tags = fields.String(example='prova', default='', description='comma separated list of tags')
    share_proto = fields.String(required=True, example='NFS', description='The Shared File Systems protocol. A valid '
                                'value is NFS, CIFS, GlusterFS, HDFS, or CephFS. CephFS supported is starting with '
                                'API v2.13.', validate=OneOf(['NFS', 'CIFS']))
    size = fields.Integer(required=True, example=23, description='The share size, in GBs. The requested share size '
                          'cannot be greater than the allowed GB quota. To view the allowed quota, issue a get limits '
                          'request.')
    share_type = fields.String(required=True, example='netapp-nfs-565', description='The share type name. If you '
                               'omit this parameter, the default share type is used. To view the default share type '
                               'set by the administrator, issue a list default share types request. You cannot '
                               'specify both the share_type and volume_type parameters.')
    snapshot_id = fields.String(required=False, example='23', description='The UUID of the share\'s base snapshot.')
    share_group_id = fields.String(required=False, example='23', missing=None,
                                   description='The UUID of the share group.')
    network = fields.String(required=False, example='23', missing=None, description='id of the network to use')
    subnet = fields.String(required=False, example='23', missing=None, description='id of the subnet to use')
    metadata = fields.Dict(required=False, example={}, missing=None,
                           description='One or more metadata key and value pairs as a dictionary of strings.')
    availability_zone = fields.String(required=False, example='nova', missing='nova',
                                      description='The availability zone.')


class CreateShareRequestSchema(Schema):
    share = fields.Nested(CreateShareParamRequestSchema)


class CreateShareBodyRequestSchema(Schema):
    body = fields.Nested(CreateShareRequestSchema, context='body')


class CreateShare(OpenstackShareApiView):
    summary = 'Create share'
    description = 'Create share'
    tags = ['openstack']
    definitions = {
        'CreateShareRequestSchema': CreateShareRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateShareBodyRequestSchema)
    parameters_schema = CreateShareRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateShareParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')


class UpdateShareRequestSchema(Schema):
    share = fields.Nested(UpdateShareParamRequestSchema)


class UpdateShareBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateShareRequestSchema, context='body')


class UpdateShare(OpenstackShareApiView):
    summary = 'Update share'
    description = 'Update share'
    tags = ['openstack']
    definitions = {
        'UpdateShareRequestSchema': UpdateShareRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateShareBodyRequestSchema)
    parameters_schema = UpdateShareRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteShare(OpenstackShareApiView):
    summary = 'Delete share'
    description = 'Delete share'
    tags = ['openstack']
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


class GetShareGrantParamsResponseSchema(Schema):
    access_level = fields.String(required=True, example='rw', description='The access level to the share. To grant '
                                 'or deny access to a share, you specify one of the following share access levels: '
                                 '- rw. Read and write (RW) access. - ro. Read- only (RO) access.')
    state = fields.String(required=True, example='active', description='The state of access rule of a given share. '
                          'This could be new, active or error.')
    id = fields.String(required=True, example='52bea969-78a2-4f7e-ae84-fb4599dc06ca',
                       description='The access rule ID.')
    access_type = fields.String(required=True, example='ip',
                                description='The access rule type. Valid value are: ip, cert, user')
    access_to = fields.String(required=True, example='10.102.186.0/24',
                              description='The value that defines the access.')


class GetShareGrantResponseSchema(Schema):
    share_grant = fields.Nested(GetShareGrantParamsResponseSchema, many=True, allow_none=True)


class GetShareGrant(OpenstackShareApiView):
    summary = 'List share grants'
    description = 'List share grants'
    tags = ['openstack']
    definitions = {
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        res = self.get_resource_reference(controller, oid)
        resp = res.grant_list()
        return {'share_grant': resp}


class CreateShareGrantParamRequestSchema(Schema):
    access_level = fields.String(required=True, example='rw',
                                 description='The access level to the share. To grant or deny access to a share, you '
                                             'specify one of the following share access levels: - rw. Read and write '
                                             '(RW) access. - ro. Read- only (RO) access.')
    access_type = fields.String(required=True, example='ip',
                                description='The access rule type. A valid value for the share access rule type is '
                                            'one of the following values: - ip. Authenticates an instance through its '
                                            'IP address. - cert. Authenticates an instance through a TLS certificate. '
                                            'Specify the TLS identity as the IDENTKEY. - user. Authenticates by a '
                                            'user or group name.')
    access_to = fields.String(required=True, example='10.102.186.0/24',
                              description='The value that defines the access. - ip. A valid format is XX.XX.XX.XX or '
                                          'XX.XX.XX.XX/XX. For example 0.0.0.0/0. - cert. A valid value is any '
                                          'string up to 64 characters long in the common name (CN) of the certificate.'
                                          ' - user. A valid value is an alphanumeric string that can contain some '
                                          'special characters and is from 4 to 32 characters long.')


class CreateShareGrantRequestSchema(Schema):
    share_grant = fields.Nested(CreateShareGrantParamRequestSchema)


class CreateShareGrantBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CreateShareGrantRequestSchema, context='body')


class CreateShareGrant(OpenstackShareApiView):
    summary = 'Add share grant'
    description = 'Add share grant'
    tags = ['openstack']
    definitions = {
        'CreateShareGrantRequestSchema': CreateShareGrantRequestSchema,
        'CrudApiTaskResponseSchema': CrudApiTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateShareGrantBodyRequestSchema)
    parameters_schema = CreateShareGrantRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiTaskResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        res = self.get_resource_reference(controller, oid)
        resp = res.grant_add(data.get('share_grant'))
        return resp


class DeleteShareGrantParamRequestSchema(Schema):
    access_id = fields.String(required=True, example='52bea969-78a2-4f7e-ae84-fb4599dc06ca',
                              description='The UUID of the access rule to which access is granted.')


class DeleteShareGrantRequestSchema(Schema):
    share_grant = fields.Nested(DeleteShareGrantParamRequestSchema)


class DeleteShareGrantBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteShareGrantRequestSchema, context='body')


class DeleteShareGrant(OpenstackShareApiView):
    summary = 'Remove share grant'
    description = 'Remove share grant'
    tags = ['openstack']
    definitions = {
        'DeleteShareGrantRequestSchema': DeleteShareGrantRequestSchema,
        'CrudApiTaskResponseSchema': CrudApiTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteShareGrantBodyRequestSchema)
    parameters_schema = DeleteShareGrantRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        res = self.get_resource_reference(controller, oid)
        resp = res.grant_remove(data.get('share_grant'))
        return resp


class ExtendShareRequestSchema(Schema):
    new_size = fields.Integer(required=True, example=10, description='New size of the share, in GBs.')


class ExtendShareBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ExtendShareRequestSchema, context='body')


class ExtendShare(OpenstackShareApiView):
    summary = 'Increases the size of a share'
    description = 'Increases the size of a share'
    tags = ['openstack']
    definitions = {
        'ExtendShareRequestSchema': ExtendShareRequestSchema,
        'CrudApiTaskResponseSchema': CrudApiTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(ExtendShareBodyRequestSchema)
    parameters_schema = ExtendShareRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        res = self.get_resource_reference(controller, oid)
        resp = res.size_extend(data)
        return resp


class ShrinkShareRequestSchema(Schema):
    new_size = fields.Integer(required=True, example=10, description='New size of the share, in GBs.')


class ShrinkShareBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ShrinkShareRequestSchema, context='body')


class ShrinkShare(OpenstackShareApiView):
    summary = 'Shrink the size of a share'
    description = 'Shrink the size of a share'
    tags = ['openstack']
    definitions = {
        'ShrinkShareRequestSchema': ShrinkShareRequestSchema,
        'CrudApiTaskResponseSchema': CrudApiTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(ShrinkShareBodyRequestSchema)
    parameters_schema = ShrinkShareRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        res = self.get_resource_reference(controller, oid)
        resp = res.size_shrink(data)
        return resp


class GetShareNetworkResponseSchema(Schema):
    id = fields.String(required=True, exmaple='test', description='share network id')
    mtu = fields.Integer(required=True, exmaple=1500, description='share network mtu')
    name = fields.String(required=True, exmaple='test', description='share network name')
    description = fields.String(required=True, exmaple='test', description='share network description')
    segmentation_id = fields.Integer(required=True, exmaple=1378, description='share network segmentation_id')
    created_at = fields.String(required=True, exmaple='2020-10-05T07:09:36.0',
                               description='share network creation date')
    updated_at = fields.String(required=True, exmaple='2020-10-05T07:09:36.0',
                               description='share network update date')
    neutron_subnet_id = fields.String(required=True, exmaple='4dbd4f6c-aefe-4a36-9c67-050f96857f33',
                                      description='neutron openstack network subnet id')
    network_type = fields.String(required=True, exmaple='test', description='share network type')
    gateway = fields.String(required=True, exmaple='test', description='share network gateway')
    neutron_net_id = fields.String(required=True, exmaple='test', description='neutron openstack network id')
    ip_version = fields.String(required=True, exmaple='ipv4', description='share network ip version')
    cidr = fields.String(required=True, exmaple='10.102.90.0/24', description='share network cidr')
    project_id = fields.String(required=True, exmaple='1a09ddd80cc24e19bff8d297cf7b2773',
                               description='share network openstack project id')


class GetShareNetworksResponseSchema(Schema):
    share_networks = fields.Nested(GetShareNetworkResponseSchema, required=True, allow_none=True)


class GetShareNetworksRequestSchema(Schema):
    container = fields.String(context='query', description='resource container id, uuid or name')


class GetShareNetworks(OpenstackShareApiView):
    summary = 'Get share networks'
    description = 'Get share networks'
    tags = ['openstack']
    definitions = {
        'GetShareNetworksResponseSchema': GetShareNetworksResponseSchema,
        'GetShareNetworksRequestSchema': GetShareNetworksRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetShareNetworksRequestSchema)
    parameters_schema = GetShareNetworksRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetShareNetworksResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        cid = data.get('container')
        container = controller.get_container(cid)
        res = container.get_manila_share_networks()
        return {'share_networks': res}


class CreateShareNetworkParamRequestSchema(Schema):
    container = fields.String(required=True, description='resource container id, uuid or name')
    name = fields.String(required=True, exmaple='test', description='share network name')
    description = fields.String(required=False, exmaple='test', description='share network description')
    network = fields.String(required=True, exmaple='test', description='The UUID of a neutron network when setting up '
                            'or updating a share network subnet with neutron. Specify both a neutron network and a '
                            'neutron subnet that belongs to that neutron network')
    subnet = fields.String(required=True, exmaple='test', description='The UUID of the neutron subnet when setting up '
                           'or updating a share network subnet with neutron. Specify both a neutron network and a '
                           'neutron subnet that belongs to that neutron network')
    availability_zone = fields.String(required=False, exmaple='test', missing='nova', description='The UUID or name of '
                                      'an availability zone for the share network subnet')


class CreateShareNetworkRequestSchema(Schema):
    share_network = fields.Nested(CreateShareNetworkParamRequestSchema)


class CreateShareNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CreateShareNetworkRequestSchema, context='body')


class CreateShareNetworkResponseSchema(Schema):
    share_network = fields.String(required=True, exmaple='test', description='share network id')


class CreateShareNetwork(OpenstackShareApiView):
    summary = 'Create share network'
    description = 'Create share network'
    tags = ['openstack']
    definitions = {
        'CreateShareNetworkRequestSchema': CreateShareNetworkRequestSchema,
        'CreateShareNetworkResponseSchema': CreateShareNetworkResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateShareNetworkBodyRequestSchema)
    parameters_schema = CreateShareNetworkRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CreateShareNetworkResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        cid = data.pop('container')
        container = controller.get_container(cid)
        res = container.add_manila_share_network(**data.get('share_network'))
        return {'share_network': res}


class DeleteShareNetworkParamRequestSchema(Schema):
    container = fields.String(required=True, description='resource container id, uuid or name')
    id = fields.String(required=True, exmaple='test', description='share network id')


class DeleteShareNetworkRequestSchema(Schema):
    share_network = fields.Nested(DeleteShareNetworkParamRequestSchema)


class DeleteShareNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteShareNetworkRequestSchema, context='body')


class DeleteShareNetworkResponseSchema(Schema):
    share_network = fields.String(required=True, exmaple='test', description='share network id')


class DeleteShareNetwork(OpenstackShareApiView):
    summary = 'Delete share network'
    description = 'Delete share network'
    tags = ['openstack']
    definitions = {
        'DeleteShareNetworkRequestSchema': DeleteShareNetworkRequestSchema,
        'DeleteShareNetworkResponseSchema': DeleteShareNetworkResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteShareNetworkBodyRequestSchema)
    parameters_schema = DeleteShareNetworkRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': DeleteShareNetworkResponseSchema
        }
    })

    def delete(self, controller, data, *args, **kwargs):
        cid = data.pop('container')
        container = controller.get_container(cid)
        res = container.delete_manila_share_network(data.get('share_network').get('id'))
        return {'share_network': res}


class OpenstackShareAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/shares' % base, 'GET', ListShares, {}),
            ('%s/shares/<oid>' % base, 'GET', GetShare, {}),
            ('%s/shares' % base, 'POST', CreateShare, {}),
            ('%s/shares/<oid>' % base, 'PUT', UpdateShare, {}),
            ('%s/shares/<oid>' % base, 'DELETE', DeleteShare, {}),

            ('%s/shares/types' % base, 'GET', ListShareTypes, {}),

            ('%s/shares/networks' % base, 'GET', GetShareNetworks, {}),
            ('%s/shares/networks' % base, 'POST', CreateShareNetwork, {}),
            ('%s/shares/networks' % base, 'DELETE', DeleteShareNetwork, {}),

            ('%s/shares/<oid>/grant' % base, 'GET', GetShareGrant, {}),
            ('%s/shares/<oid>/grant' % base, 'POST', CreateShareGrant, {}),
            ('%s/shares/<oid>/grant' % base, 'DELETE', DeleteShareGrant, {}),
            ('%s/shares/<oid>/extend' % base, 'PUT', ExtendShare, {}),
            ('%s/shares/<oid>/shrink' % base, 'PUT', ShrinkShare, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
