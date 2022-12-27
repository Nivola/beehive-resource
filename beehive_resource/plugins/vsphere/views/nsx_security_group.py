# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema, \
    CrudApiObjectJobResponseSchema, CrudApiJobResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup


class VsphereNsxSecurityGroupApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = NsxSecurityGroup
    parentclass = NsxManager


class ListNsxSecurityGroupsRequestSchema(ListResourcesRequestSchema):
    pass


class ListNsxSecurityGroupsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNsxSecurityGroupsResponseSchema(PaginatedResponseSchema):
    nsx_security_groups = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNsxSecurityGroups(VsphereNsxSecurityGroupApiView):
    definitions = {
        'ListNsxSecurityGroupsResponseSchema': ListNsxSecurityGroupsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxSecurityGroupsRequestSchema)
    parameters_schema = ListNsxSecurityGroupsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListNsxSecurityGroupsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List nsx_security_group
        List nsx_security_group
        """
        return self.get_resources(controller, **data)

## get
class GetNsxSecurityGroupResponseSchema(Schema):
    nsx_security_group = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)

class GetNsxSecurityGroup(VsphereNsxSecurityGroupApiView):
    definitions = {
        'GetNsxSecurityGroupResponseSchema': GetNsxSecurityGroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetNsxSecurityGroupResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx_security_group
        Get nsx_security_group
        """
        return self.get_resource(controller, oid)

## create
class CreateNsxSecurityGroupParamRequestSchema(Schema):
    container = fields.String(required=True, example='12',
                              description='container id, uuid or name')
    name = fields.String(required=True, example='test')


class CreateNsxSecurityGroupRequestSchema(Schema):
    nsx_security_group = fields.Nested(CreateNsxSecurityGroupParamRequestSchema)


class CreateNsxSecurityGroupBodyRequestSchema(Schema):
    body = fields.Nested(CreateNsxSecurityGroupRequestSchema, context='body')


class CreateNsxSecurityGroup(VsphereNsxSecurityGroupApiView):
    definitions = {
        'CreateNsxSecurityGroupRequestSchema': CreateNsxSecurityGroupRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateNsxSecurityGroupBodyRequestSchema)
    parameters_schema = CreateNsxSecurityGroupRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create nsx_security_group
        Create nsx_security_group
        """
        return self.create_resource(controller, data)


class UpdateNsxSecurityGroupParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateNsxSecurityGroupRequestSchema(Schema):
    nsx_security_group = fields.Nested(UpdateNsxSecurityGroupParamRequestSchema)

class UpdateNsxSecurityGroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateNsxSecurityGroupRequestSchema, context='body')

class UpdateNsxSecurityGroup(VsphereNsxSecurityGroupApiView):
    definitions = {
        'UpdateNsxSecurityGroupRequestSchema': UpdateNsxSecurityGroupRequestSchema,
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateNsxSecurityGroupBodyRequestSchema)
    parameters_schema = UpdateNsxSecurityGroupRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update nsx_security_group
        Update nsx_security_group
        """
        return self.update_resource(controller, data)

## delete
class DeleteNsxSecurityGroup(VsphereNsxSecurityGroupApiView):
    definitions = {
        'CrudApiObjectJobResponseSchema': CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete nsx_security_group
        Delete nsx_security_group
        """
        return self.expunge_resource(controller, oid)


class UpdateSecurityGroupMemberParamRequestSchema(Schema):
    action = fields.String(example='add', validate=OneOf(['add', 'delete']),
                           description='Action. Can be: add or delete')
    member = fields.String(example='12', description='id, uuid or name of member')


class UpdateSecurityGroupMemberSchema(Schema):
    nsx_security_group_member = fields.Nested(UpdateSecurityGroupMemberParamRequestSchema, required=True)


class UpdateSecurityGroupBodyMemberSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSecurityGroupMemberSchema, context='body')


class UpdateSecurityGroupMember(VsphereNsxSecurityGroupApiView):
    definitions = {
        'UpdateSecurityGroupMemberSchema': UpdateSecurityGroupMemberSchema,
        'CrudApiJobResponseSchema': CrudApiJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateSecurityGroupBodyMemberSchema)
    parameters_schema = UpdateSecurityGroupMemberSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        sg = self.get_resource_reference(controller, oid)
        params = data['nsx_security_group_member']
        cmd = params.pop('action')
        if cmd == 'add':
            res = sg.add_member(params)
        elif cmd == 'delete':
            res = sg.delete_member(params)
        return res


class VsphereNsxSecurityGroupAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + '/network'
        rules = [
            ('%s/nsx_security_groups' % base, 'GET', ListNsxSecurityGroups, {}),
            ('%s/nsx_security_groups/<oid>' % base, 'GET', GetNsxSecurityGroup, {}),
            ('%s/nsx_security_groups' % base, 'POST', CreateNsxSecurityGroup, {}),
            ('%s/nsx_security_groups/<oid>' % base, 'PUT', UpdateNsxSecurityGroup, {}),
            ('%s/nsx_security_groups/<oid>' % base, 'DELETE', DeleteNsxSecurityGroup, {}),
            ('%s/nsx_security_groups/<oid>/members' % base, 'PUT', UpdateSecurityGroupMember, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
