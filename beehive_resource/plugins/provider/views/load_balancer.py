# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte
from marshmallow.validate import OneOf

from beehive_resource.plugins.provider.entity.load_balancer import ComputeLoadBalancer
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    CrudApiObjectTaskResponseSchema,
    GetApiObjectRequestSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
    LocalProviderApiViewV2,
)


class ProviderLoadBalancer(LocalProviderApiViewV2):
    resclass = ComputeLoadBalancer
    parentclass = ComputeZone


class ListLoadBalancersRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone ids or uuids")


class ListLoadBalancersResponseSchema(PaginatedResponseSchema):
    load_balancers = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListLoadBalancers(ProviderLoadBalancer):
    summary = "List load balancers"
    description = "List load balancers"
    definitions = {
        "ListLoadBalancersResponseSchema": ListLoadBalancersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListLoadBalancersRequestSchema)
    parameters_schema = ListLoadBalancersRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListLoadBalancersResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        return self.get_resources(controller, **data)


class GetLoadBalancerItemResponseSchema(ResourceResponseSchema):
    actions = fields.Nested(ResourceResponseSchema, required=False, many=False, allow_none=True)
    resources = fields.Nested(ResourceSmallResponseSchema, required=False, many=False, allow_none=True)


class GetLoadBalancerResponseSchema(Schema):
    load_balancer = fields.Nested(GetLoadBalancerItemResponseSchema, required=True, allow_none=True)


class GetLoadBalancer(ProviderLoadBalancer):
    summary = "Get load balancer"
    description = "Get load balancer"
    definitions = {
        "GetLoadBalancerResponseSchema": GetLoadBalancerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetLoadBalancerResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateLoadBalancerHealthMonitorParamRequestSchema(Schema):
    name = fields.String(required=True, description="health monitor name")
    protocol = fields.String(required=True, description="protocol used to run health checks on targets")
    interval = fields.Integer(
        required=False,
        allow_none=True,
        description="time between two consecutive health checks",
    )
    timeout = fields.Integer(
        required=False,
        allow_none=True,
        description="time within which a response from target must be received",
    )
    max_retries = fields.Integer(
        required=False,
        allow_none=True,
        description="number of consecutive health check failures before considering a target unhealthy",
    )
    method = fields.String(
        required=False,
        allow_none=True,
        description="the HTTP method used for health check",
    )
    request_uri = fields.String(
        required=False,
        allow_none=True,
        description="the destination for health checks on targets",
    )
    expected = fields.String(
        required=False,
        allow_none=True,
        description="the response (usually, a HTTP code) the monitor expects to receive from target",
    )
    predefined = fields.Boolean(
        required=False,
        allow_none=True,
        description="whether the health monitor is predefined or custom",
    )
    ext_name = fields.Dict(
        required=False,
        allow_none=True,
        description="the name of the predefined health monitor for each supported network appliance",
    )


class CreateLoadBalancerTargetsParamRequestSchema(Schema):
    name = fields.String(
        required=True,
        allow_none=False,
        description="target name i.e. service instance name",
    )
    resource_uuid = fields.String(required=True, allow_none=False, description="target resource uuid")
    lb_port = fields.Integer(
        required=True,
        allow_none=False,
        description="port on which target receives traffic from load balancer",
    )
    hm_port = fields.Integer(
        required=False,
        allow_none=True,
        description="port on which target is listening for health checks",
    )


class CreateLoadBalancerTargetGroupParamRequestSchema(Schema):
    name = fields.String(required=True, allow_none=False, description="target group name")
    desc = fields.String(required=False, allow_none=True, description="target group description")
    balancing_algorithm = fields.String(
        required=True,
        allow_none=False,
        description="algorithm used to load balance targets",
    )
    target_type = fields.String(
        required=True,
        allow_none=False,
        description="target type, i.e. vm, container, etc.",
    )
    targets = fields.Nested(
        CreateLoadBalancerTargetsParamRequestSchema,
        required=True,
        many=True,
        allow_none=False,
        description="list of target setting",
    )
    transparent = fields.String(
        required=False,
        allow_none=True,
        description="whether client IP addresses are visible to the backend servers",
    )


class CreateLoadBalancerPersistenceParamRequestSchema(Schema):
    method = fields.String(required=False, allow_none=True, description="persistence method")
    cookie_name = fields.String(required=False, allow_none=True, description="cookie name")
    cookie_mode = fields.String(required=False, allow_none=True, description="cookie mode")
    expire_time = fields.Integer(required=False, allow_none=True, description="persistence expiration time")


class CreateLoadBalancerListenerParamRequestSchema(Schema):
    name = fields.String(required=True, allow_none=False, description="listener name")
    desc = fields.String(required=False, allow_none=True, description="listener description")
    traffic_type = fields.String(
        required=True,
        allow_none=False,
        description="incoming traffic profile the load balancer has to manage",
    )
    persistence = fields.Nested(
        CreateLoadBalancerPersistenceParamRequestSchema,
        required=False,
        allow_none=True,
        description="persistence setting",
    )
    insert_x_forwarded_for = fields.Boolean(
        required=False,
        allow_none=True,
        description="flag to enable/disable insertXForwardedFor header",
    )
    url_redirect = fields.String(required=False, allow_none=True, description="HTTP redirect to")
    predefined = fields.Boolean(
        required=False,
        allow_none=True,
        description="whether the listener is predefined or custom",
    )
    ext_name = fields.Dict(
        required=False,
        allow_none=True,
        description="the name of the predefined listener for each supported network appliance",
    )


class CreateLoadBalancerConfigsRequestSchema(Schema):
    protocol = fields.String(
        required=True,
        allow_none=False,
        description="protocol for connections from clients to load balancer",
    )
    port = fields.Integer(
        required=False,
        allow_none=True,
        description="port on which the load balancer is listening",
    )
    static_ip = fields.String(
        required=False,
        allow_none=True,
        description="The frontend IP address of the load balancer provided by the user",
    )
    max_conn = fields.Integer(required=False, allow_none=True, description="max concurrent connections")
    max_conn_rate = fields.Integer(
        required=False,
        allow_none=True,
        description="max new incoming connection requests per second",
    )
    deployment_env = fields.String(
        required=False,
        allow_none=True,
        description="Project deployment environment",
    )
    listener = fields.Nested(
        CreateLoadBalancerListenerParamRequestSchema,
        required=True,
        allow_none=False,
        description="listener setting",
    )
    target_group = fields.Nested(
        CreateLoadBalancerTargetGroupParamRequestSchema,
        required=True,
        allow_none=False,
        description="target group setting",
    )
    health_monitor = fields.Nested(
        CreateLoadBalancerHealthMonitorParamRequestSchema,
        required=False,
        allow_none=True,
        description="health monitor setting",
    )


class CreateLoadBalancerParamsRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, allow_none=False, description="parent compute zone id")
    site = fields.String(required=True, allow_none=False, description="site id")
    name = fields.String(required=True, allow_none=False, description="load balancer name")
    desc = fields.String(required=False, allow_none=True, description="load balancer description")
    is_private = fields.Boolean(
        required=True,
        allow_none=False,
        description="flag specifying whether the load " "balancer wil be created on a private or shared subnet",
    )
    gateway = fields.String(required=False, allow_none=True, description="internet gateway id, for private cloud only")
    vpc = fields.String(required=False, allow_none=True, description="vpc id, for private cloud only")
    site_network = fields.String(
        required=False, allow_none=True, description="site network name, for shared cloud only"
    )
    lb_configs = fields.Nested(
        CreateLoadBalancerConfigsRequestSchema,
        required=True,
        allow_none=False,
        description="load balancer settings",
    )
    selection_criteria = fields.Dict(
        required=False,
        allow_none=True,
        description="criteria to select the network appliance where configuring the load balancer",
    )


class CreateLoadBalancerRequestSchema(Schema):
    load_balancer = fields.Nested(CreateLoadBalancerParamsRequestSchema)


class CreateLoadBalancerBodyRequestSchema(Schema):
    body = fields.Nested(CreateLoadBalancerRequestSchema, context="body")


class CreateLoadBalancer(ProviderLoadBalancer):
    summary = "Create load balancer"
    description = "Create load balancer"
    definitions = {
        "CreateLoadBalancerRequestSchema": CreateLoadBalancerRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateLoadBalancerBodyRequestSchema)
    parameters_schema = CreateLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class ImportLoadBalancerListenerParamRequestSchema(Schema):
    #
    # TODO: complete with supported params
    #
    pass


class ImportLoadBalancerTargetGroupParamRequestSchema(Schema):
    #
    # TODO: complete with supported params
    #
    pass


class ImportLoadBalancerHealthMonitorParamRequestSchema(Schema):
    #
    # TODO: complete with supported params
    #
    pass


class ImportLoadBalancerConfigsRequestSchema(Schema):
    protocol = fields.String(
        required=True,
        allow_none=False,
        description="protocol for connections from clients to load balancer",
    )
    port = fields.Integer(
        required=False,
        allow_none=True,
        description="port on which the load balancer is listening",
    )
    virtual_ip_address = fields.String(
        required=False,
        allow_none=True,
        description="The frontend IP address of the load balancer",
    )
    is_vip_static = fields.Boolean(
        required=False,
        allow_none=True,
        description="Whether the load balancer frontend IP address is static or not",
    )
    max_conn = fields.Integer(required=False, allow_none=True, description="max concurrent connections")
    max_conn_rate = fields.Integer(
        required=False,
        allow_none=True,
        description="max new incoming connection requests per second",
    )
    listener = fields.Nested(
        ImportLoadBalancerListenerParamRequestSchema,
        required=True,
        allow_none=False,
        description="listener setting",
    )
    target_group = fields.Nested(
        ImportLoadBalancerTargetGroupParamRequestSchema,
        required=True,
        allow_none=False,
        description="target group setting",
    )
    health_monitor = fields.Nested(
        ImportLoadBalancerHealthMonitorParamRequestSchema,
        required=False,
        allow_none=True,
        description="health monitor setting",
    )


class ImportLoadBalancerParamsRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, allow_none=False, description="parent compute zone id")
    vpc = fields.String(required=True, allow_none=False, description="vpc uuid")
    site = fields.String(required=True, allow_none=False, description="site uuid")
    name = fields.String(required=True, allow_none=False, description="load balancer name")
    desc = fields.String(required=False, allow_none=True, description="load balancer description")
    lb_configs = fields.Nested(
        ImportLoadBalancerConfigsRequestSchema,
        required=True,
        allow_none=False,
        description="load balancer settings",
    )


class ImportLoadBalancerRequestSchema(Schema):
    load_balancer = fields.Nested(ImportLoadBalancerParamsRequestSchema)


class ImportLoadBalancerBodyRequestSchema(Schema):
    body = fields.Nested(ImportLoadBalancerRequestSchema, context="body")


class ImportLoadBalancer(ProviderLoadBalancer):
    definitions = {
        "ImportLoadBalancerRequestSchema": ImportLoadBalancerRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ImportLoadBalancerBodyRequestSchema)
    parameters_schema = ImportLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """Create load balancer"""
        return self.create_resource(controller, data)


class UpdateLoadBalancerParamsRequestSchema(Schema):
    desc = fields.String(required=False)
    lb_configs = fields.Dict(default=False)


class UpdateLoadBalancerRequestSchema(Schema):
    load_balancer = fields.Nested(UpdateLoadBalancerParamsRequestSchema)


class UpdateLoadBalancerBodyRequestSchema(Schema):
    body = fields.Nested(UpdateLoadBalancerRequestSchema, context="body")


class UpdateLoadBalancer(ProviderLoadBalancer):
    summary = "Update load balancer"
    description = "Update load balancer"
    definitions = {
        "UpdateLoadBalancerRequestSchema": UpdateLoadBalancerRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateLoadBalancerBodyRequestSchema)
    parameters_schema = UpdateLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)


class DeleteLoadBalancerRequestSchema(Schema):
    pass


class DeleteLoadBalancer(ProviderLoadBalancer):
    summary = "Delete load balancer"
    description = "Delete load balancer"
    definitions = {
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
        "DeleteLoadBalancerRequestSchema": DeleteLoadBalancerRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    parameters_schema = DeleteLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid, **data)


class ActionLoadBalancerRequest1Schema(Schema):
    stop = fields.Boolean(description="Disable load balancer")
    start = fields.Boolean(description="Enable load balancer")


class ActionLoadBalancerRequestSchema(Schema):
    action = fields.Nested(ActionLoadBalancerRequest1Schema, required=True)


class ActionLoadBalancerBodyRequestSchema(Schema):
    body = fields.Nested(ActionLoadBalancerRequestSchema, context="body")


class ActionLoadBalancer(ProviderLoadBalancer):
    summary = "Run load balancer action"
    description = "Run load balancer action"
    definitions = {
        "ActionLoadBalancerRequestSchema": ActionLoadBalancerRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ActionLoadBalancerBodyRequestSchema)
    parameters_schema = ActionLoadBalancerRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        resource = self.get_resource_reference(controller, oid)
        actions = data.get("action")
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {"action_params": params}
        res = resource.action(action, **params)
        return res


class LoadBalancerProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/loadbalancers" % base, "GET", ListLoadBalancers, {}),
            ("%s/loadbalancers/<oid>" % base, "GET", GetLoadBalancer, {}),
            ("%s/loadbalancers" % base, "POST", CreateLoadBalancer, {}),
            ("%s/loadbalancers/import" % base, "POST", ImportLoadBalancer, {}),
            ("%s/loadbalancers/<oid>" % base, "PUT", UpdateLoadBalancer, {}),
            ("%s/loadbalancers/<oid>" % base, "DELETE", DeleteLoadBalancer, {}),
            ("%s/loadbalancers/<oid>/action" % base, "PUT", ActionLoadBalancer, {}),
            # firewall
            # ('%s/loadbalancers/<oid>/firewall' % base, 'GET', GetLoadBalancerFirewallRule, {}),
            # ('%s/loadbalancers/<oid>/firewall' % base, 'POST', AddLoadBalancerFirewallRule, {}),
            # ('%s/loadbalancers/<oid>/firewall' % base, 'DELETE', DelLoadBalancerFirewallRule, {}),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
