# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from marshmallow import validates
from marshmallow.validate import OneOf

from beecell.network import InternetProtocol
from beehive_resource.plugins.provider.entity.security_group_acl import SecurityGroupAcl
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
)


class ProviderSecurityGroupAcl(LocalProviderApiView):
    resclass = SecurityGroupAcl
    parentclass = ComputeZone


class ListSecurityGroupAclsRequestSchema(ListResourcesRequestSchema):
    ports = fields.String(
        required=False,
        example="80",
        missing=None,
        description="Comma separated list of ports",
    )
    protocol = fields.String(
        required=False,
        example="tcp",
        missing=None,
        description="Supported **protocol** are only 6 [tcp], 17 [udp], 1 [icmp], * [all]",
    )
    is_default = fields.Boolean(required=False, missing=None, description="Set rule as default if True")
    source = fields.String(
        required=False,
        example="10.102.0.0/24",
        missing=None,
        description="SecurityGroup uuid or Cidr",
    )


class ListSecurityGroupAclsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSecurityGroupAclsResponseSchema(PaginatedResponseSchema):
    security_group_acls = fields.Nested(
        ListSecurityGroupAclsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListSecurityGroupAcls(ProviderSecurityGroupAcl):
    definitions = {
        "ListSecurityGroupAclsResponseSchema": ListSecurityGroupAclsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSecurityGroupAclsRequestSchema)
    parameters_schema = ListSecurityGroupAclsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListSecurityGroupAclsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """
        List security group acls
        List security group acls
        """
        attributes = ""
        is_default = data.get("is_default", None)
        ports = data.get("ports", None)
        proto = data.get("protocol", None)
        source = data.get("source", None)
        if is_default is not None:
            attributes += '{"is_default":%s' % is_default + "%"
        if ports is not None:
            attributes += "%" + '"ports":' + "%" + "%s" % ports + "%"
        if proto is not None:
            proto = InternetProtocol().get_number_from_name(proto)
            attributes += "%" + '"proto":"%s:*"' % proto + "%"
        if source is not None:
            attributes += "%" + '"source":' + "%" + "%s" % source + "%"

        if attributes != "":
            data["attribute"] = attributes
        return self.get_resources(controller, **data)


class GetSecurityGroupAclParamsResponseSchema(ResourceResponseSchema):
    rules = fields.Nested(ResourceSmallResponseSchema, many=True, required=True, allow_none=True)
    rule_groups = fields.Nested(ResourceSmallResponseSchema, many=True, required=True, allow_none=True)


class GetSecurityGroupAclResponseSchema(Schema):
    security_group_acl = fields.Nested(GetSecurityGroupAclParamsResponseSchema, required=True, allow_none=True)


class GetSecurityGroupAcl(ProviderSecurityGroupAcl):
    definitions = {
        "GetSecurityGroupAclResponseSchema": GetSecurityGroupAclResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetSecurityGroupAclResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get security group acl
        Get security group acl
        """
        return self.get_resource(controller, oid)


class CreateSecurityGroupAclSourceRequestSchema(Schema):
    type = fields.String(
        required=True,
        example="SecurityGroup",
        validate=OneOf(["SecurityGroup", "Cidr"]),
        description="Source/destination type supported: SecurityGroup, Instance, Cidr",
    )
    value = fields.String(
        required=True,
        example="3151",
        description="value is the id of the object 3151 or a cidr 10.102.185.0/24",
    )


class CreateSecurityGroupAclServiceRequestSchema(Schema):
    ports = fields.String(
        required=False,
        example="*",
        missing="*",
        description="Comma separated list of ports. Ex. 80, 80,8080. Use * for all the ports",
    )
    protocol = fields.String(
        required=False,
        example="*",
        missing="*",
        description="Supported **protocol** are only 6 [tcp], 17 [udp], 1 [icmp], * [all]",
    )
    subprotocol = fields.String(required=False, example=17, missing="*", description="use this param with icmp")
    where = fields.String(required=False, example=17, missing=None, description="custom rule filter")


class CreateSecurityGroupAclParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    source = fields.Nested(
        CreateSecurityGroupAclSourceRequestSchema,
        required=False,
        allow_none=True,
        description="Acl source",
    )
    service = fields.Nested(
        CreateSecurityGroupAclServiceRequestSchema,
        required=False,
        allow_none=True,
        description="describe protocol and ports to use in rule",
    )
    is_default = fields.Boolean(required=False, missing=False, description="Set rule as default if True")


class CreateSecurityGroupAclRequestSchema(Schema):
    security_group_acl = fields.Nested(CreateSecurityGroupAclParamRequestSchema)


class CreateSecurityGroupAclBodyRequestSchema(Schema):
    body = fields.Nested(CreateSecurityGroupAclRequestSchema, context="body")


class CreateSecurityGroupAcl(ProviderSecurityGroupAcl):
    definitions = {
        "CreateSecurityGroupAclRequestSchema": CreateSecurityGroupAclRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateSecurityGroupAclBodyRequestSchema)
    parameters_schema = CreateSecurityGroupAclRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create security group acl
        Create security group acl
        """
        return self.create_resource(controller, data)


class UpdateSecurityGroupAclParamRequestSchema(Schema):
    pass


class UpdateSecurityGroupAclRequestSchema(Schema):
    security_group_acl = fields.Nested(UpdateSecurityGroupAclParamRequestSchema)


class UpdateSecurityGroupAclBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSecurityGroupAclRequestSchema, context="body")


class UpdateSecurityGroupAcl(ProviderSecurityGroupAcl):
    definitions = {
        "UpdateSecurityGroupAclRequestSchema": UpdateSecurityGroupAclRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateSecurityGroupAclBodyRequestSchema)
    parameters_schema = UpdateSecurityGroupAclRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update security group acl
        Update security group acl
        """
        return self.update_resource(controller, oid, data)


class DeleteSecurityGroupAcl(ProviderSecurityGroupAcl):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete security group acl
        Delete security group acl
        """
        return self.expunge_resource(controller, oid)


class SecurityGroupAclProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: vpc, super_zone
            ("%s/security_group_acls" % base, "GET", ListSecurityGroupAcls, {}),
            ("%s/security_group_acls/<oid>" % base, "GET", GetSecurityGroupAcl, {}),
            ("%s/security_group_acls" % base, "POST", CreateSecurityGroupAcl, {}),
            ("%s/security_group_acls/<oid>" % base, "PUT", UpdateSecurityGroupAcl, {}),
            (
                "%s/security_group_acls/<oid>" % base,
                "DELETE",
                DeleteSecurityGroupAcl,
                {},
            ),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
