# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema,\
    CrudApiObjectJobResponseSchema, CrudApiObjectResponseSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema


class OpenstackProjectApiView(OpenstackApiView):
    resclass = OpenstackProject
    parentclass = OpenstackDomain


class ListProjectsRequestSchema(ListResourcesRequestSchema):
    pass


class ListProjectsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListProjectsResponseSchema(PaginatedResponseSchema):
    projects = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListProjects(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'ListProjectsResponseSchema': ListProjectsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListProjectsRequestSchema)
    parameters_schema = ListProjectsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListProjectsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List project
        List project
        """
        return self.get_resources(controller, **data)


class GetProjectResponseSchema(Schema):
    project = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetProject(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'GetProjectResponseSchema': GetProjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetProjectResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get project
        Get project
        """
        return self.get_resource(controller, oid)


class CreateProjectParamRequestSchema(Schema):
    container = fields.String(required=True, example='12', description='container id, uuid or name')
    name = fields.String(required=True, default='test')
    desc = fields.String(required=True, default='test')
    domain_id = fields.String(required=True, default='default')
    enabled = fields.Boolean(default=True)
    is_domain = fields.Boolean(default=False)
    project_id = fields.String(default='')
    tags = fields.String(default='')


class CreateProjectRequestSchema(Schema):
    project = fields.Nested(CreateProjectParamRequestSchema)


class CreateProjectBodyRequestSchema(Schema):
    body = fields.Nested(CreateProjectRequestSchema, context='body')


class CreateProject(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'CreateProjectRequestSchema': CreateProjectRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateProjectBodyRequestSchema)
    parameters_schema = CreateProjectRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create project
        Create project
        """
        return self.create_resource(controller, data)


class UpdateProjectParamRequestSchema(Schema):
    name = fields.String(default='test')
    desc = fields.String(default='test')
    enabled = fields.Boolean(default=True)


class UpdateProjectRequestSchema(Schema):
    project = fields.Nested(UpdateProjectParamRequestSchema)


class UpdateProjectBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateProjectRequestSchema, context='body')


class UpdateProject(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'UpdateProjectRequestSchema':UpdateProjectRequestSchema,
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateProjectBodyRequestSchema)
    parameters_schema = UpdateProjectRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update project
        Update project
        """
        return self.update_resource(controller, oid, data)


class DeleteProject(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'CrudApiObjectJobResponseSchema':CrudApiObjectJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class GetProjectQuotasResponseSchema(Schema):
    count = fields.Integer(required=True, default=10)
    quotas = fields.Dict(required=True, default={})


class GetProjectQuotas(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'GetApiObjectRequestSchema': GetApiObjectRequestSchema,
        'GetProjectQuotasResponseSchema': GetProjectQuotasResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetProjectQuotasResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        project = self.get_resource_reference(controller, oid)
        res = project.get_quotas()
        resp = {'quotas': res,
                'count': len(res)}
        return resp


class SetProjectQuotaResponseSchema(Schema):
    type = fields.String(required=True, example='compute', description='One of compute, network, block')
    quota = fields.String(required=True, example='cores', description='name of quota param to set')
    value = fields.String(required=True, example='12', description='value of quota to set')


class SetProjectQuotasResponseSchema(Schema):
    quotas = fields.Nested(SetProjectQuotaResponseSchema, many=True, required=True, allow_none=True)


class SetProjectQuotas(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'GetApiObjectRequestSchema': GetApiObjectRequestSchema,
        'GetProjectQuotasResponseSchema': GetProjectQuotasResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetProjectQuotasResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        project = self.get_resource_reference(controller, oid)
        res = project.set_quotas(data.get('quotas'))
        resp = data
        return resp


class GetProjectLimitsResponseSchema(Schema):
    count = fields.Integer(required=True, default=10)
    limits = fields.Dict(required=True, default={})


class GetProjectLimits(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'GetApiObjectRequestSchema': GetApiObjectRequestSchema,
        'GetProjectLimitsResponseSchema': GetProjectLimitsResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetProjectLimitsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        project = self.get_resource_reference(controller, oid)
        res = project.get_limits()
        resp = {'limits':res,
                'count':len(res)}
        return resp


class GetProjectMembersParamsResponseSchema(Schema):
    groups = fields.List(fields.Dict, required=True)
    users = fields.List(fields.Dict, required=True)


class GetProjectMembersResponseSchema(Schema):
    count = fields.Integer(required=True, default=10)
    members = fields.Nested(GetProjectMembersParamsResponseSchema, required=True, allow_none=True)


class GetProjectMembers(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'GetApiObjectRequestSchema': GetApiObjectRequestSchema,
        'GetProjectMembersResponseSchema': GetProjectMembersResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetProjectMembersResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        project = self.get_resource_reference(controller, oid)
        res = project.get_members()
        resp = {'members': res, 'count': len(res)}
        return resp


class AssignProjectMemberParamRequestSchema(Schema):
    action = fields.String(required=True, default='assign')
    user = fields.String(required=True, default='db078b20-19c6-4f0e-909c-94745de667d4')
    role = fields.String(required=True, default='db078b20-19c6-4f0e-909c-94745de667d4')


class AssignProjectMemberRequestSchema(Schema):
    project = fields.Nested(AssignProjectMemberParamRequestSchema)


class AssignProjectMemberBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AssignProjectMemberRequestSchema, context='body')


class AssignProjectMember(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'AssignProjectMemberRequestSchema': AssignProjectMemberRequestSchema,
        'CrudApiObjectResponseSchema': CrudApiObjectResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(AssignProjectMemberBodyRequestSchema)
    parameters_schema = AssignProjectMemberRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Assign/deassign project members
        Assign/deassign project members
        """
        project = self.get_resource_reference(controller, oid)
        data = data.get(self.resclass.objname)
        cmd = data['action']
        user = data['user']
        role = data['role']
        if cmd == 'assign':
            res = project.assign_member(user, role)
        elif cmd == 'deassign':
            res = project.deassign_member(user, role)
        return res


class GetProjectSecurityGroupResponseSchema(PaginatedResponseSchema):
    projects = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class GetProjectSecurityGroup(OpenstackProjectApiView):
    tags = ['openstack']
    definitions = {
        'GetApiObjectRequestSchema': GetApiObjectRequestSchema,
        'GetProjectSecurityGroupResponseSchema': GetProjectSecurityGroupResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetProjectSecurityGroupResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        project = self.get_resource_reference(controller, oid)
        res, total = project.get_security_groups()
        resp = [r.info() for r in res]
        return self.format_paginated_response(resp, 'security_groups', total, **kwargs)


class OpenstackProjectAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/projects' % base, 'GET', ListProjects, {}),
            ('%s/projects/<oid>' % base, 'GET', GetProject, {}),
            ('%s/projects' % base, 'POST', CreateProject, {}),
            ('%s/projects/<oid>' % base, 'PUT', UpdateProject, {}),
            ('%s/projects/<oid>' % base, 'DELETE', DeleteProject, {}),

            ('%s/projects/<oid>/quotas' % base, 'GET', GetProjectQuotas, {}),
            ('%s/projects/<oid>/quotas' % base, 'POST', SetProjectQuotas, {}),
            ('%s/projects/<oid>/limits' % base, 'GET', GetProjectLimits, {}),

            ('%s/projects/<oid>/members' % base, 'GET', GetProjectMembers, {}),
            ('%s/projects/<oid>/members' % base, 'PUT', AssignProjectMember, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
