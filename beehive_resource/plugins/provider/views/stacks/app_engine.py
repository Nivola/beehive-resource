# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.provider.entity.app_stack import AppComputeStack
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    ApiManagerError,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)
from marshmallow.validate import OneOf


class AppProviderAppStack(LocalProviderApiView):
    resclass = AppComputeStack
    parentclass = ComputeZone


class ListAppStacksRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone id or uuid")


class ListAppStacksResponseSchema(PaginatedResponseSchema):
    app_stacks = fields.Nested(ResourceResponseSchema, many=True, required=True)


class ListAppStacks(AppProviderAppStack):
    definitions = {
        "ListAppStacksResponseSchema": ListAppStacksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListAppStacksRequestSchema)
    parameters_schema = ListAppStacksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListAppStacksResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List app_stacks
        List app_stacks

        # - filter by: tags
        # - filter by: compute_zone
        """
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        data["attribute"] = '%"stack_type":"app_stack"%'
        data["entity_class"] = self.resclass
        resources, total = self.get_resources_reference(controller, **data)

        resp = [r.info() for r in resources]

        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **data)


class GetAppStackResponseSchema(Schema):
    app_stack = fields.Nested(ResourceResponseSchema, required=True)


class GetAppStack(AppProviderAppStack):
    definitions = {
        "GetAppStackResponseSchema": GetAppStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetAppStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get app_stack
        Get app_stack
        """
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        info = res.detail()
        return {self.resclass.objname: info}


class GetAppStackResourcesResponseSchema(Schema):
    app_stack_resources = fields.List(fields.Dict(), required=True)


class GetAppStackResources(AppProviderAppStack):
    definitions = {
        "GetAppStackResourcesResponseSchema": GetAppStackResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetAppStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get app_stack resources
        Get app_stack resources
        """
        resource = self.get_resource_reference(controller, oid)
        resources = resource.resources()
        return {
            self.resclass.objname + "_resources": resources,
            "count": len(resources),
        }


class CreateAppStackParamConfigRequestSchema(Schema):
    document_root = fields.String(required=False, example="/var/www", description="[apache-php] document root")
    ftp_server = fields.Boolean(
        required=False,
        example=True,
        description="[apache-php] if true install ftp server",
    )
    smb_server = fields.Boolean(
        required=False,
        example=False,
        description="[apache-php] if true install samba server",
    )
    share_dimension = fields.Integer(
        required=False,
        example=10,
        default=10,
        description="[apache-php] share dimension in GB",
    )
    share_cfg_dimension = fields.Integer(
        required=False,
        example=2,
        default=2,
        description="[apache-php] share config dimension in GB",
    )
    app_port = fields.Integer(
        required=False,
        example=80,
        default=80,
        description="[apache-php] internal application port",
    )
    farm_name = fields.String(
        required=True,
        example="tst-portali",
        description="[apache-php] parent compute zone id or uuid",
    )


class CreateAppStackParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where create sql",
    )
    flavor = fields.String(required=True, example="2995", description="id, uuid or name of the flavor")
    image = fields.String(required=True, example="2995", description="id, uuid or name of the image")
    vpc = fields.String(required=True, example="2995", description="id, uuid or name of the private vpc")
    subnet = fields.String(required=True, example="10.102.167.90/24", description="subnet definition")
    vpc_public = fields.String(
        required=False,
        example="2995",
        missing="",
        allow_none=True,
        description="id, uuid or name of the public vpc",
    )
    is_public = fields.Boolean(
        required=False,
        missing=False,
        description="if True load balancer is on public network",
    )
    security_group = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the private security group",
    )
    routes = fields.List(fields.String(), required=False, example="6.5", description="List of routes")
    key_name = fields.String(
        required=False,
        example="opstkportali",
        default="opstkportali",
        allow_none=True,
        description="Openstack public key name",
    )
    version = fields.String(required=True, example="7", description="App engine version")
    engine = fields.String(
        required=True,
        example="php",
        description="App engine",
        validate=OneOf(["apache-php"]),
    )
    engine_configs = fields.Nested(
        CreateAppStackParamConfigRequestSchema,
        required=True,
        description="App engine specific params",
    )
    resolve = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if stack instances must registered on the availability_zone dns zone",
    )


class CreateAppStackRequestSchema(Schema):
    app_stack = fields.Nested(CreateAppStackParamRequestSchema, context="body")


class CreateAppStackBodyRequestSchema(Schema):
    body = fields.Nested(CreateAppStackRequestSchema, context="body")


class CreateAppStack(AppProviderAppStack):
    definitions = {
        "CreateAppStackRequestSchema": CreateAppStackRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateAppStackBodyRequestSchema)
    parameters_schema = CreateAppStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create app_stack
        Create app_stack
        """
        res = self.create_resource(controller, data)
        return res


class UpdateAppStackParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateAppStackRequestSchema(Schema):
    app_stack = fields.Nested(UpdateAppStackParamRequestSchema)


class UpdateAppStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateAppStackRequestSchema, context="body")


class UpdateAppStack(AppProviderAppStack):
    definitions = {
        "UpdateAppStackRequestSchema": UpdateAppStackRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateAppStackBodyRequestSchema)
    parameters_schema = UpdateAppStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update app_stack
        Update app_stack
        """
        return self.update_resource(controller, oid, data)


class ActionAppStackParamRequestSchema(Schema):
    action = fields.String(
        required=True,
        example="set-password",
        description="Send and action to sql stack",
        validate=OneOf(["set-password"]),
    )
    params = fields.Dict(required=True, example={}, description="The action params")


class ActionAppStackRequestSchema(Schema):
    app_stack_action = fields.Nested(ActionAppStackParamRequestSchema)


class ActionAppStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ActionAppStackRequestSchema, context="body")


class ActionAppStackResponseSchema(Schema):
    app_stack_action = fields.List(fields.Dict(), required=True)


class ActionAppStack(AppProviderAppStack):
    definitions = {
        "ActionAppStackRequestSchema": ActionAppStackRequestSchema,
        "ActionAppStackResponseSchema": ActionAppStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ActionAppStackBodyRequestSchema)
    parameters_schema = ActionAppStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": ActionAppStackResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Run app_stack action
        Run app_stack action
        """
        resource = self.get_resource_reference(controller, oid)
        data = data.get("app_stack_action")
        action = data.get("action")
        params = data.get("params")
        action_func = getattr(action)
        res = resource.send_action(action_func, **params)
        return {self.resclass.objname + "_action": action, "response": res}


class DeleteAppStack(AppProviderAppStack):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete app_stack
        Delete app_stack
        """
        return self.expunge_resource(controller, oid)


class AppStackProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: compute_zone
            ("%s/app_stacks" % base, "GET", ListAppStacks, {}),
            ("%s/app_stacks/<oid>" % base, "GET", GetAppStack, {}),
            ("%s/app_stacks/<oid>/resources" % base, "GET", GetAppStackResources, {}),
            ("%s/app_stacks" % base, "POST", CreateAppStack, {}),
            ("%s/app_stacks/<oid>" % base, "PUT", UpdateAppStack, {}),
            ("%s/app_stacks/<oid>/action" % base, "PUT", ActionAppStack, {}),
            ("%s/app_stacks/<oid>" % base, "DELETE", DeleteAppStack, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
