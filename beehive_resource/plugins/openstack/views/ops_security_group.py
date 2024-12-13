# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_security_group import (
    OpenstackSecurityGroup,
)
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    CrudApiJobResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject


class OpenstackSecurityGroupApiView(OpenstackApiView):
    tags = ["openstack"]
    resclass = OpenstackSecurityGroup
    parentclass = OpenstackProject


class ListSecurityGroupsRequestSchema(ListResourcesRequestSchema):
    pass


class ListSecurityGroupsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListSecurityGroupsResponseSchema(PaginatedResponseSchema):
    security_groups = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListSecurityGroups(OpenstackSecurityGroupApiView):
    definitions = {
        "ListSecurityGroupsResponseSchema": ListSecurityGroupsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSecurityGroupsRequestSchema)
    parameters_schema = ListSecurityGroupsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListSecurityGroupsResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """
        List security_group
        List security_group
        """
        return self.get_resources(controller, **data)


class GetSecurityGroupResponseSchema(Schema):
    security_group = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetSecurityGroup(OpenstackSecurityGroupApiView):
    definitions = {
        "GetSecurityGroupResponseSchema": GetSecurityGroupResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetSecurityGroupResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get security_group
        Get security_group
        """
        return self.get_resource(controller, oid)


class CreateOpsSecurityGroupParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    project = fields.String(required=True, default="12")
    name = fields.String(required=True, default="test")
    desc = fields.String(required=True, default="test")
    tags = fields.String(default="")


class CreateOpsSecurityGroupRequestSchema(Schema):
    security_group = fields.Nested(CreateOpsSecurityGroupParamRequestSchema)


class CreateOpsSecurityGroupBodyRequestSchema(Schema):
    body = fields.Nested(CreateOpsSecurityGroupRequestSchema, context="body")


class CreateOpsSecurityGroup(OpenstackSecurityGroupApiView):
    definitions = {
        "CreateOpsSecurityGroupRequestSchema": CreateOpsSecurityGroupRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateOpsSecurityGroupBodyRequestSchema)
    parameters_schema = CreateOpsSecurityGroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create security_group
        Create security_group
        """
        return self.create_resource(controller, data)


class UpdateSecurityGroupParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    enabled = fields.Boolean(default=True)


class UpdateSecurityGroupRequestSchema(Schema):
    security_group = fields.Nested(UpdateSecurityGroupParamRequestSchema)


class UpdateSecurityGroupBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateSecurityGroupRequestSchema, context="body")


class UpdateSecurityGroup(OpenstackSecurityGroupApiView):
    definitions = {
        "UpdateSecurityGroupRequestSchema": UpdateSecurityGroupRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateSecurityGroupBodyRequestSchema)
    parameters_schema = UpdateSecurityGroupRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update security_group
        Update security_group
        """
        return self.update_resource(controller, oid, data)


class DeleteSecurityGroup(OpenstackSecurityGroupApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class ResetSecurityGroups(OpenstackSecurityGroupApiView):
    definitions = {
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        sg = self.get_resource(controller, oid)
        job = sg.reset_rule(data.get("security_group_rule"))
        return job


class CreateSecurityGroupsRuleParamRequestSchema(Schema):
    direction = fields.String(
        required=True,
        default="ingress",
        example="ingress",
        description="ingress or egress",
    )
    ethertype = fields.String(
        required=True,
        default="IPv4",
        example="IPv4",
        description="Must be IPv4 or IPv6",
    )
    port_range_min = fields.String(
        required=False,
        example="9000",
        description="The minimum port number in the range that is matched by "
        "the security group rule. If the protocol is TCP or UDP, this value "
        "must be less than or equal to the port_range_max attribute value. If "
        "the protocol is ICMP, this value must be an ICMP type",
        allow_none=True,
    )
    port_range_max = fields.String(
        required=False,
        example="9010",
        description="The maximum port number in the range that is matched by "
        "the security group rule. The port_range_min attribute constrains "
        "the port_range_max attribute. If the protocol is ICMP, this value "
        "must be an ICMP type",
        allow_none=True,
    )
    protocol = fields.String(
        required=False,
        example="tcp",
        description="The protocol that is matched by the security group rule. "
        "Valid values are null, tcp, udp, and icmp",
        allow_none=True,
    )
    remote_group_id = fields.String(
        required=False,
        example="12",
        description="The remote group UUID to associate with this security "
        "group rule. You can specify either the remote_group_id or "
        "remote_ip_prefix attribute in the request body",
        allow_none=True,
    )
    remote_ip_prefix = fields.String(
        required=False,
        example="12",
        description="The remote IP prefix to associate with this security "
        "group rule. You can specify either the remote_group_id or remote_ip_"
        "prefix attribute in the request body. This attribute matches the IP "
        "prefix as the source IP address of the IP packet",
        allow_none=True,
    )


class CreateSecurityGroupsRuleRequestSchema(Schema):
    security_group_rule = fields.Nested(CreateSecurityGroupsRuleParamRequestSchema)


class CreateSecurityGroupsRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CreateSecurityGroupsRuleRequestSchema, context="body")


class CreateSecurityGroupsRule(OpenstackSecurityGroupApiView):
    definitions = {
        "CreateSecurityGroupsRuleRequestSchema": CreateSecurityGroupsRuleRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateSecurityGroupsRuleBodyRequestSchema)
    parameters_schema = CreateSecurityGroupsRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def post(self, controller, data, oid, *args, **kwargs):
        sg = self.get_resource_reference(controller, oid)
        job = sg.create_rule(data.get("security_group_rule"))
        return job


class DeleteSecurityGroupsRuleParamRequestSchema(Schema):
    rule_id = fields.String(
        required=False,
        default="12",
        example="12",
        description="Security griup rule opensatck id",
    )


class DeleteSecurityGroupsRuleRequestSchema(Schema):
    security_group_rule = fields.Nested(DeleteSecurityGroupsRuleParamRequestSchema, required=False)


class DeleteSecurityGroupsRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteSecurityGroupsRuleRequestSchema, context="body")


class DeleteSecurityGroupsRule(OpenstackSecurityGroupApiView):
    definitions = {
        "DeleteSecurityGroupsRuleRequestSchema": DeleteSecurityGroupsRuleRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteSecurityGroupsRuleBodyRequestSchema)
    parameters_schema = DeleteSecurityGroupsRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete security group rules
        Delete security group rules. If security_group_rule is not specified
        delete all rules.
        """
        sg = self.get_resource_reference(controller, oid)
        if data.get("security_group_rule", None) is None:
            job = sg.reset_rule()
        else:
            job = sg.delete_rule(data.get("security_group_rule"))

        return job


class OpenstackSecurityGroupAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/security_groups" % base, "GET", ListSecurityGroups, {}),
            ("%s/security_groups/<oid>" % base, "GET", GetSecurityGroup, {}),
            ("%s/security_groups" % base, "POST", CreateOpsSecurityGroup, {}),
            ("%s/security_groups/<oid>" % base, "PUT", UpdateSecurityGroup, {}),
            ("%s/security_groups/<oid>" % base, "DELETE", DeleteSecurityGroup, {}),
            (
                "%s/security_groups/<oid>/reset" % base,
                "DELETE",
                ResetSecurityGroups,
                {},
            ),
            (
                "%s/security_groups/<oid>/rules" % base,
                "POST",
                CreateSecurityGroupsRule,
                {},
            ),
            (
                "%s/security_groups/<oid>/rules" % base,
                "DELETE",
                DeleteSecurityGroupsRule,
                {},
            ),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
