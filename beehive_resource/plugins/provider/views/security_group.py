# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.vpc import Vpc
from beehive_resource.view import ListResourcesRequestSchema,\
    ResourceResponseSchema, ResourceSmallResponseSchema
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, \
    GetApiObjectRequestSchema, CrudApiObjectTaskResponseSchema, CrudApiObjectResponseSchema
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import ProviderAPI,\
    LocalProviderApiView, CreateProviderResourceRequestSchema


class ProviderSecurityGroup(LocalProviderApiView):
    resclass = SecurityGroup
    parentclass = Vpc


class ListSecurityGroupsRequestSchema(ListResourcesRequestSchema):
    vpc = fields.String(context='query', description='vpc id, uuid')
    compute_zone = fields.String(context='query', description='compute zone id, uuid')
    instance = fields.String(context='query', description='compute instance id, uuid')


class ListSecurityGroupsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSecurityGroupsResponseSchema(PaginatedResponseSchema):
    security_groups = fields.Nested(ListSecurityGroupsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListSecurityGroups(ProviderSecurityGroup):
    definitions = {
        'ListSecurityGroupsResponseSchema': ListSecurityGroupsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSecurityGroupsRequestSchema)
    parameters_schema = ListSecurityGroupsRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSecurityGroupsResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List security groups
        List security groups
        """
        from ..entity.zone import ComputeZone
        from ..entity.instance import ComputeInstance

        zone_id = data.get('super_zone', None)
        vpc_id = data.get('vpc', None)
        instance_id = data.get('instance', None)
        if vpc_id is not None:
            return self.get_resources_by_parent(controller, vpc_id, 'Vcp')
        elif zone_id is not None:
            return self.get_linked_resources(controller, zone_id, ComputeZone, 'sg')
        elif instance_id is not None:
            return self.get_linked_resources(controller, instance_id, ComputeInstance, 'security-group')
        return self.get_resources(controller, **data)


class GetSecurityGroupParamsResponseSchema(ResourceResponseSchema):
    rules = fields.Nested(ResourceSmallResponseSchema, many=True, required=True, allow_none=True)
    rule_groups = fields.Nested(ResourceSmallResponseSchema, many=True, required=True, allow_none=True)


class GetSecurityGroupResponseSchema(Schema):
    security_group = fields.Nested(GetSecurityGroupParamsResponseSchema, required=True, allow_none=True)


class GetSecurityGroup(ProviderSecurityGroup):
    definitions = {
        'GetSecurityGroupResponseSchema': GetSecurityGroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetSecurityGroupResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get security group
        Get security group
        """
        return self.get_resource(controller, oid)


class CreateSecurityGroupParamRequestSchema(CreateProviderResourceRequestSchema):
    vpc = fields.String(required=True, example='test', description='id of the parent vpc')


class CreateSecurityGroupRequestSchema(Schema):
    security_group = fields.Nested(CreateSecurityGroupParamRequestSchema)


class CreateSecurityGroupBodyRequestSchema(Schema):
    body = fields.Nested(CreateSecurityGroupRequestSchema, context='body')


class CreateSecurityGroup(ProviderSecurityGroup):
    definitions = {
        'CreateSecurityGroupRequestSchema': CreateSecurityGroupRequestSchema,
        'CrudApiObjectTaskResponseSchema':CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateSecurityGroupBodyRequestSchema)
    parameters_schema = CreateSecurityGroupRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create security group
        Create security group
        """
        data['tag'] = data.pop('orchestartor_tag', 'default')
        return self.create_resource(controller, data)


class UpdateSecurityGroupParamRequestSchema(Schema):
    pass


class UpdateSecurityGroupRequestSchema(Schema):
    security_group = fields.Nested(UpdateSecurityGroupParamRequestSchema)


class UpdateSecurityGroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSecurityGroupRequestSchema, context='body')


class UpdateSecurityGroup(ProviderSecurityGroup):
    summary = 'Update security group'
    description = 'Update security group'
    definitions = {
        'UpdateSecurityGroupRequestSchema': UpdateSecurityGroupRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateSecurityGroupBodyRequestSchema)
    parameters_schema = UpdateSecurityGroupRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteSecurityGroup(ProviderSecurityGroup):
    summary = 'Delete security group'
    description = 'Delete security group'
    definitions = {
        'CrudApiObjectTaskResponseSchema':CrudApiObjectTaskResponseSchema
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


class ListSecurityGroupAclsResponseSchema(Schema):
    security_group_acls = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class ListSecurityGroupAcls(ProviderSecurityGroup):
    definitions = {
        'ListSecurityGroupAclsResponseSchema': ListSecurityGroupAclsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetSecurityGroupResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get security group acls
        Get security group acls
        """
        resource = self.get_resource_reference(controller, oid, run_customize=False)
        acls = resource.get_acls()
        return {'security_group_acls': [item.info() for item in acls]}


class AddSecurityGroupAclParamRequestSchema(Schema):
    acl_id = fields.String(required=True, example='12', description='id of the security group acl')


class AddSecurityGroupAclRequestSchema(Schema):
    security_group_acl = fields.Nested(AddSecurityGroupAclParamRequestSchema)


class AddSecurityGroupAclBodyRequestSchema(Schema):
    body = fields.Nested(AddSecurityGroupAclRequestSchema, context='body')


class AddSecurityGroupAcl(ProviderSecurityGroup):
    definitions = {
        'AddSecurityGroupAclRequestSchema': AddSecurityGroupAclRequestSchema,
        'CrudApiObjectResponseSchema': CrudApiObjectResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(AddSecurityGroupAclBodyRequestSchema)
    parameters_schema = AddSecurityGroupAclRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Add acl to security group
        Add acl to security group
        """
        resource = self.get_resource_reference(controller, oid, run_customize=False)
        res = resource.add_acl(data.get('security_group_acl').get('acl_id'))
        return {'uuid': res}


class DelSecurityGroupAclParamRequestSchema(Schema):
    acl_id = fields.String(required=True, example='12', description='id of the security group acl')


class DelSecurityGroupAclRequestSchema(Schema):
    security_group_acl = fields.Nested(DelSecurityGroupAclParamRequestSchema)


class DelSecurityGroupAclBodyRequestSchema(Schema):
    body = fields.Nested(DelSecurityGroupAclRequestSchema, context='body')


class DelSecurityGroupAcl(ProviderSecurityGroup):
    definitions = {
        'DelSecurityGroupAclRequestSchema': DelSecurityGroupAclRequestSchema,
        'CrudApiObjectResponseSchema': CrudApiObjectResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DelSecurityGroupAclBodyRequestSchema)
    parameters_schema = DelSecurityGroupAclRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Add acl to security group
        Add acl to security group
        """
        resource = self.get_resource_reference(controller, oid, run_customize=False)
        res = resource.del_acl(data.get('security_group_acl').get('acl_id'))
        return {'uuid': res}


class HasSecurityGroupAclRequestSchema(Schema):
    source = fields.String(required=False, context='query', example='*:*', missing='*:*',
                           description='acl source. Can be *:*, Cidr:<>, SecurityGroup:<>')
    protocol = fields.String(required=False, context='query', example='*:*', missing='*:*',
                             description='acl protocol. Can be *:*, 7:*, 9:0 or tcp:*')
    ports = fields.String(required=False, context='query', example='*', missing='*',
                          description='Comma separated acl ports (80,8000), single port (80) or port interval '
                                      '(4001-4002). * for all')


class HasSecurityGroupAclResponseSchema(Schema):
    security_group_acl_check = fields.Boolean(required=True, allow_none=True)


class HasSecurityGroupAcl(ProviderSecurityGroup):
    definitions = {
        'HasSecurityGroupAclRequestSchema': HasSecurityGroupAclRequestSchema,
        'HasSecurityGroupAclResponseSchema': HasSecurityGroupAclResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(HasSecurityGroupAclRequestSchema)
    parameters_schema = HasSecurityGroupAclRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': HasSecurityGroupAclResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Check security group acl
        Check security group acl
        """
        resource = self.get_resource_reference(controller, oid, run_customize=False)
        data['source'] = data.get('source').replace('SecurityGroup', 'Sg')
        res = resource.has_acl(data.get('source'), data.get('protocol'), data.get('ports'))
        return {'security_group_acl_check': res}


#
# zabbix
#
class CreateSecurityGroupZabbixRuleRequestSchema(Schema):
    availability_zone = fields.String(required=True, example='SiteTorino01', description='Availability zone name')


class CreateSecurityGroupZabbixRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CreateSecurityGroupZabbixRuleRequestSchema, context='body')


class CreateSecurityGroupZabbixRule(ProviderSecurityGroup):
    summary = 'Update security group'
    description = 'Update security group'
    definitions = {
        'CreateSecurityGroupZabbixRuleRequestSchema': CreateSecurityGroupZabbixRuleRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateSecurityGroupZabbixRuleBodyRequestSchema)
    parameters_schema = CreateSecurityGroupZabbixRuleRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        availability_zone = data.get('availability_zone')
        resource = controller.get_resource(oid)
        res = resource.create_zabbix_proxy_rule(availability_zone)
        return res


class DeleteSecurityGroupZabbixRuleRequestSchema(Schema):
    availability_zone = fields.String(required=True, example='SiteTorino01', description='Availability zone name')


class DeleteSecurityGroupZabbixRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteSecurityGroupZabbixRuleRequestSchema, context='body')


class DeleteSecurityGroupZabbixRule(ProviderSecurityGroup):
    summary = 'Delete security group zabbix rule in a specific availability zone'
    description = 'Delete security group zabbix rule in a specific availability zone'
    definitions = {
        'DeleteSecurityGroupZabbixRuleRequestSchema': DeleteSecurityGroupZabbixRuleRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteSecurityGroupZabbixRuleBodyRequestSchema)
    parameters_schema = DeleteSecurityGroupZabbixRuleRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        availability_zone = data.get('availability_zone')
        resource = controller.get_resource(oid)
        res = resource.delete_zabbix_proxy_rule(availability_zone)
        return res


class SecurityGroupProviderAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: vpc, super_zone
            ('%s/security_groups' % base, 'GET', ListSecurityGroups, {}),
            ('%s/security_groups/<oid>' % base, 'GET', GetSecurityGroup, {}),
            ('%s/security_groups' % base, 'POST', CreateSecurityGroup, {}),
            ('%s/security_groups/<oid>' % base, 'PUT', UpdateSecurityGroup, {}),
            ('%s/security_groups/<oid>' % base, 'DELETE', DeleteSecurityGroup, {}),

            ('%s/security_groups/<oid>/zabbix' % base, 'POST', CreateSecurityGroupZabbixRule, {}),
            ('%s/security_groups/<oid>/zabbix' % base, 'DELETE', DeleteSecurityGroupZabbixRule, {}),

            ('%s/security_groups/<oid>/acls' % base, 'GET', ListSecurityGroupAcls, {}),
            ('%s/security_groups/<oid>/acls/check' % base, 'GET', HasSecurityGroupAcl, {}),
            ('%s/security_groups/<oid>/acls' % base, 'POST', AddSecurityGroupAcl, {}),
            ('%s/security_groups/<oid>/acls' % base, 'DELETE', DelSecurityGroupAcl, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)