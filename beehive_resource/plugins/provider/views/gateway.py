# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte
from marshmallow.validate import OneOf

from beehive_resource.plugins.provider.entity.gateway import ComputeGateway
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
    CrudApiObjectTaskResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)


class ProviderGateway(LocalProviderApiView):
    resclass = ComputeGateway
    parentclass = ComputeZone


class ListGatewaysRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone id or uuid")


class ListGatewaysResponseSchema(PaginatedResponseSchema):
    gateways = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListGateways(ProviderGateway):
    summary = "List gateways"
    description = "List gateways"
    definitions = {
        "ListGatewaysResponseSchema": ListGatewaysResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListGatewaysRequestSchema)
    parameters_schema = ListGatewaysRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListGatewaysResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        return self.get_resources(controller, **data)


class GetGatewayItemResponseSchema(ResourceResponseSchema):
    actions = fields.Nested(ResourceResponseSchema, required=False, many=False, allow_none=True)
    resources = fields.Nested(ResourceSmallResponseSchema, required=False, many=False, allow_none=True)


class GetGatewayResponseSchema(Schema):
    gateway = fields.Nested(GetGatewayItemResponseSchema, required=True, allow_none=True)


class GetGateway(ProviderGateway):
    summary = "Get gateway"
    description = "Get gateway"
    definitions = {
        "GetGatewayResponseSchema": GetGatewayResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetGatewayResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateGatewayParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id")
    # orchestrator_select_types = fields.List(
    #     fields.String(example="vsphere"),
    #     required=False,
    #     allow_none=True,
    #     context="query",
    #     description="orchestrator select types",
    # )
    uplink_vpc = fields.String(required=True, example="1", description="uplink vpc")
    transport_vpc = fields.String(required=True, example="1", description="transport vpc")
    primary_zone = fields.String(required=True, example="1", description="primary zone")
    secondary_zone = fields.String(required=False, example="1", description="secondary zone")
    primary_subnet = fields.String(required=True, example="1", description="primary uplink subnet")
    secondary_subnet = fields.String(required=False, example="1", description="secondary uplink subnet")
    primary_ip_address = fields.String(
        required=False,
        example="10.101.2.3",
        missing=None,
        description="primary zone uplink ip address",
    )
    secondary_ip_address = fields.String(
        required=False,
        example="10.101.2.4",
        missing=None,
        description="secondary zone uplink ip address",
    )
    admin_pwd = fields.String(required=True, example="1", description="admin password")
    dns = fields.String(required=True, example="1", description="dns list")
    dns_search = fields.String(required=True, example="1", description="dns search")
    flavor = fields.String(
        required=False,
        example="compact",
        missing="compact",
        description="gateway size. Can be compact, large, quadlarge, xlarge.",
    )
    volume_flavor = fields.String(
        required=False,
        example="vol.default",
        missing="compact",
        description="gateway size",
    )
    type = fields.String(
        required=False,
        example="vsphere",
        missing="vsphere",
        description="orchestrator type",
    )
    host_group = fields.String(
        required=False,
        example="default",
        missing="default",
        description="define the optional host group where put the gateway",
    )


class CreateGatewayRequestSchema(Schema):
    gateway = fields.Nested(CreateGatewayParamRequestSchema)


class CreateGatewayBodyRequestSchema(Schema):
    body = fields.Nested(CreateGatewayRequestSchema, context="body")


class CreateGateway(ProviderGateway):
    summary = "Create gateway"
    description = "Create gateway"
    definitions = {
        "CreateGatewayRequestSchema": CreateGatewayRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateGatewayBodyRequestSchema)
    parameters_schema = CreateGatewayRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateGatewayParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateGatewayRequestSchema(Schema):
    gateway = fields.Nested(UpdateGatewayParamRequestSchema)


class UpdateGatewayBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateGatewayRequestSchema, context="body")


class UpdateGateway(ProviderGateway):
    summary = "Update gateway"
    description = "Update gateway"
    definitions = {
        "UpdateGatewayRequestSchema": UpdateGatewayRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateGatewayBodyRequestSchema)
    parameters_schema = UpdateGatewayRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteGatewayRequestSchema(Schema):
    pass


class DeleteGateway(ProviderGateway):
    summary = "Delete gateway"
    description = "Delete gateway"
    definitions = {
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
        "DeleteGatewayRequestSchema": DeleteGatewayRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    parameters_schema = DeleteGatewayRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid, **data)


class GetGatewayItemResponseSchema(ResourceResponseSchema):
    user = fields.String(required=True, example="admin", description="user name")
    password = fields.String(required=True, example="admin", description="user password")


class GetGatewayCredentialsResponseSchema(Schema):
    credentials = fields.Nested(GetGatewayItemResponseSchema, required=True, allow_none=True)


class GetGatewayCredentials(ProviderGateway):
    summary = "Get gateway credentials"
    description = "Get gateway credentials"
    definitions = {
        "GetGatewayResponseSchema": GetGatewayResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetGatewayResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.get_credentials(**data)
        return {"credentials": res}


class AddGatewayVpcRequestSchema(Schema):
    vpc = fields.String(required=True, example="1", description="internal vpc")


class AddGatewayVpcBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddGatewayVpcRequestSchema, context="body")


class AddGatewayVpc(ProviderGateway):
    summary = "Add vpc to gateway"
    description = "Add vpc to gateway"
    definitions = {
        "AddGatewayVpcRequestSchema": AddGatewayVpcRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddGatewayVpcBodyRequestSchema)
    parameters_schema = AddGatewayVpcRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.add_internal_vpc(**data)
        return res


class DelGatewayVpcRequestSchema(Schema):
    vpc = fields.String(required=True, example="1", description="internal vpc")


class DelGatewayVpcBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DelGatewayVpcRequestSchema, context="body")


class DelGatewayVpc(ProviderGateway):
    summary = "Add vpc to gateway"
    description = "Add vpc to gateway"
    definitions = {
        "DelGatewayVpcRequestSchema": DelGatewayVpcRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DelGatewayVpcBodyRequestSchema)
    parameters_schema = DelGatewayVpcRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.del_internal_vpc(**data)
        return res


class SetGatewayDefaultRouteRequestSchema(Schema):
    role = fields.String(
        required=False,
        example="default",
        missing="default",
        description="default internet route role to set",
        validate=OneOf(["default", "primary", "secondary"]),
    )


class SetGatewayDefaultRouteBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SetGatewayDefaultRouteRequestSchema, context="body")


class SetGatewayDefaultRoute(ProviderGateway):
    summary = "Set gateway default route"
    description = "Set gateway default route"
    definitions = {
        "SetGatewayDefaultRouteRequestSchema": SetGatewayDefaultRouteRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SetGatewayDefaultRouteBodyRequestSchema)
    parameters_schema = SetGatewayDefaultRouteRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.set_default_route(**data)
        return res


class AddGatewayNatRuleRequestSchema(Schema):
    role = fields.String(
        required=False,
        example="default",
        missing="primary",
        description="set role to use when create nat rule",
        validate=OneOf(["default", "primary", "secondary"]),
    )
    action = fields.String(required=True, example="snat", description="can be dnat, snat")
    enabled = fields.Boolean(required=False, example=True, missing=True, description="rule status")
    logged = fields.Boolean(required=False, example=False, missing=False, description="rule logged")
    original_address = fields.String(required=True, example="10.105.4.5", description="original address")
    translated_address = fields.String(required=True, example="81.240.172.174", description="translated address")
    original_port = fields.Integer(required=False, example=80, missing=None, description="original port")
    translated_port = fields.Integer(required=False, example=8080, missing=None, description="translated port")
    protocol = fields.String(required=False, example="tcp", missing=None, description="protocol")
    vnic = fields.String(required=False, example="vnic0", missing=None, description="nat vnic")


class AddGatewayNatRuleRequestSchema(Schema):
    nat_rule = fields.Nested(AddGatewayNatRuleRequestSchema, required=True, description="nat rule definition")


class AddGatewayNatRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddGatewayNatRuleRequestSchema, context="body")


class AddGatewayNatRule(ProviderGateway):
    summary = "Add gateway nat rule"
    description = "Add gateway nat rule"
    definitions = {
        "AddGatewayNatRuleRequestSchema": AddGatewayNatRuleRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddGatewayNatRuleBodyRequestSchema)
    parameters_schema = AddGatewayNatRuleRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.add_nat_rule_action(**data.get("nat_rule"))
        return res


class DelGatewayNatRuleRequestSchema(Schema):
    role = fields.String(
        required=False,
        example="default",
        missing="primary",
        description="set role to use when create nat rule",
        validate=OneOf(["default", "primary", "secondary"]),
    )
    action = fields.String(required=True, example="snat", description="can be dnat, snat")
    original_address = fields.String(required=True, example="10.105.4.5", description="original address")
    translated_address = fields.String(required=True, example="81.240.172.174", description="translated address")
    original_port = fields.Integer(required=False, example=80, missing=None, description="original port")
    translated_port = fields.Integer(required=False, example=8080, missing=None, description="translated port")
    protocol = fields.String(required=False, example="tcp", missing=None, description="protocol")
    vnic = fields.String(required=False, example="vnic0", missing=None, description="nat vnic")


class DelGatewayNatRuleRequestSchema(Schema):
    nat_rule = fields.Nested(DelGatewayNatRuleRequestSchema, required=True, description="nat rule definition")


class DelGatewayNatRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DelGatewayNatRuleRequestSchema, context="body")


class DelGatewayNatRule(ProviderGateway):
    summary = "Delete gateway nat rule"
    description = "Delete gateway nat rule"
    definitions = {
        "DelGatewayNatRuleRequestSchema": DelGatewayNatRuleRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DelGatewayNatRuleBodyRequestSchema)
    parameters_schema = DelGatewayNatRuleRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.del_nat_rule_action(**data.get("nat_rule"))
        return res


class GetGatewayNatRuleItemResponseSchema(ResourceResponseSchema):
    # todo
    actions = fields.Nested(ResourceResponseSchema, required=False, many=False, allow_none=True)
    resources = fields.Nested(ResourceSmallResponseSchema, required=False, many=False, allow_none=True)


class GetGatewayNatRuleResponseSchema(Schema):
    nat_rules = fields.Nested(GetGatewayNatRuleItemResponseSchema, required=True, allow_none=True)


class GetGatewayNatRule(ProviderGateway):
    summary = "Get gateway nat rules"
    description = "Get gateway nat rules"
    definitions = {
        "GetGatewayNatRuleResponseSchema": GetGatewayNatRuleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetGatewayNatRuleResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.get_nat_rules()
        return {"nat_rules": res}


class AddGatewayFirewallRuleRequestSchema(Schema):
    role = fields.String(
        required=False,
        example="default",
        missing="default",
        description="set role to use when create firewall rule",
        validate=OneOf(["default", "primary", "secondary"]),
    )
    action = fields.String(
        required=False,
        example="accept",
        missing="accept",
        description="can be accept, deny",
        validate=OneOf(["accept", "deny"]),
    )
    enabled = fields.Boolean(required=False, example=True, missing=True, description="rule status")
    logged = fields.Boolean(required=False, example=False, missing=False, description="rule logged")
    direction = fields.String(
        required=False,
        example="inout",
        missing=None,
        description="rule direction. Can be: in, out, inout",
    )
    source = fields.String(
        required=False,
        example="ip:<ipAddress>",
        missing=None,
        description="rule source. list of comma separated item like: ip:<ipAddress>, "
        "grp:<groupingObjectId>, vnic:<vnicGroupId>",
    )
    dest = fields.String(
        required=False,
        example="ip:<ipAddress>",
        missing=None,
        description="rule destination. list of comma separated item like: ip:<ipAddress>, "
        "grp:<groupingObjectId>, vnic:<vnicGroupId>",
    )
    appl = fields.String(
        required=False,
        example="ser:proto+port+source_port",
        missing=None,
        description="rule application. list of comma separated item like: app:<applicationId>, "
        "ser:proto+port+source_port",
    )


class AddGatewayFirewallRuleRequestSchema(Schema):
    firewall_rule = fields.Nested(
        AddGatewayFirewallRuleRequestSchema,
        required=True,
        description="firewall rule definition",
    )


class AddGatewayFirewallRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddGatewayFirewallRuleRequestSchema, context="body")


class AddGatewayFirewallRule(ProviderGateway):
    summary = "Add gateway firewall rule"
    description = "Add gateway firewall rule"
    definitions = {
        "AddGatewayFirewallRuleRequestSchema": AddGatewayFirewallRuleRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddGatewayFirewallRuleBodyRequestSchema)
    parameters_schema = AddGatewayFirewallRuleRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.add_firewall_rule_action(**data.get("firewall_rule"))
        return res


class DelGatewayFirewallRuleRequestSchema(Schema):
    role = fields.String(
        required=False,
        example="default",
        missing="default",
        description="set role to use when create firewall rule",
        validate=OneOf(["default", "primary", "secondary"]),
    )
    action = fields.String(
        required=False,
        example="accept",
        missing=None,
        description="can be accept, deny",
        validate=OneOf(["accept", "deny"]),
    )
    direction = fields.String(
        required=False,
        example="inout",
        missing=None,
        description="rule direction. Can be: in, out, inout",
    )
    source = fields.String(
        required=False,
        example="ip:<ipAddress>",
        missing=None,
        description="rule source. list of comma separated item like: ip:<ipAddress>, "
        "grp:<groupingObjectId>, vnic:<vnicGroupId>",
    )
    dest = fields.String(
        required=False,
        example="ip:<ipAddress>",
        missing=None,
        description="rule destination. list of comma separated item like: ip:<ipAddress>, "
        "grp:<groupingObjectId>, vnic:<vnicGroupId>",
    )
    appl = fields.String(
        required=False,
        example="ser:proto+port+source_port",
        missing=None,
        description="rule application. list of comma separated item like: app:<applicationId>, "
        "ser:proto+port+source_port",
    )


class DelGatewayFirewallRuleRequestSchema(Schema):
    firewall_rule = fields.Nested(
        DelGatewayFirewallRuleRequestSchema,
        required=True,
        description="firewall rule definition",
    )


class DelGatewayFirewallRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DelGatewayFirewallRuleRequestSchema, context="body")


class DelGatewayFirewallRule(ProviderGateway):
    summary = "Delete gateway firewall rule"
    description = "Delete gateway firewall rule"
    definitions = {
        "DelGatewayFirewallRuleRequestSchema": DelGatewayFirewallRuleRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DelGatewayFirewallRuleBodyRequestSchema)
    parameters_schema = DelGatewayFirewallRuleRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.del_firewall_rule_action(**data.get("firewall_rule"))
        return res


class GetGatewayFirewallRuleItemResponseSchema(ResourceResponseSchema):
    # todo
    actions = fields.Nested(ResourceResponseSchema, required=False, many=False, allow_none=True)
    resources = fields.Nested(ResourceSmallResponseSchema, required=False, many=False, allow_none=True)


class GetGatewayFirewallRuleResponseSchema(Schema):
    firewall_rules = fields.Nested(GetGatewayFirewallRuleItemResponseSchema, required=True, allow_none=True)


class GetGatewayFirewallRule(ProviderGateway):
    summary = "Get gateway firewall rules"
    description = "Get gateway firewall rules"
    definitions = {
        "GetGatewayFirewallRuleResponseSchema": GetGatewayFirewallRuleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetGatewayFirewallRuleResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        res = compute_gateway.get_firewall_rules()
        return {"firewall_rules": res}


class GetGatewayBastionResponseSchema(Schema):
    bastion = fields.Nested(ResourceResponseSchema, required=True)


class GetGatewayBastion(ProviderGateway):
    summary = "Get gateway nat rules"
    description = "Get gateway nat rules"
    definitions = {
        "GetGatewayBastionResponseSchema": GetGatewayBastionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetGatewayBastionResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        compute_gateway: ComputeGateway = self.get_resource_reference(controller, oid)
        bastion = compute_gateway.get_bastion()
        if bastion is not None:
            res = bastion.info()
        else:
            res = {}
        return {"bastion": res}


class GatewayProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/gateways" % base, "GET", ListGateways, {}),
            ("%s/gateways/<oid>" % base, "GET", GetGateway, {}),
            ("%s/gateways" % base, "POST", CreateGateway, {}),
            ("%s/gateways/<oid>" % base, "PUT", UpdateGateway, {}),
            ("%s/gateways/<oid>" % base, "DELETE", DeleteGateway, {}),
            ("%s/gateways/<oid>/credentials" % base, "GET", GetGatewayCredentials, {}),
            ("%s/gateways/<oid>/vpc" % base, "POST", AddGatewayVpc, {}),
            ("%s/gateways/<oid>/vpc" % base, "DELETE", DelGatewayVpc, {}),
            # route
            (
                "%s/gateways/<oid>/route/default" % base,
                "PUT",
                SetGatewayDefaultRoute,
                {},
            ),
            # firewall
            ("%s/gateways/<oid>/firewall" % base, "GET", GetGatewayFirewallRule, {}),
            ("%s/gateways/<oid>/firewall" % base, "POST", AddGatewayFirewallRule, {}),
            ("%s/gateways/<oid>/firewall" % base, "DELETE", DelGatewayFirewallRule, {}),
            # nat
            ("%s/gateways/<oid>/nat" % base, "GET", GetGatewayNatRule, {}),
            ("%s/gateways/<oid>/nat" % base, "POST", AddGatewayNatRule, {}),
            ("%s/gateways/<oid>/nat" % base, "DELETE", DelGatewayNatRule, {}),
            # bastion
            ("%s/gateways/<oid>/bastion" % base, "GET", GetGatewayBastion, {}),
        ]

        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
