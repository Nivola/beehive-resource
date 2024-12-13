# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from marshmallow import validates_schema, ValidationError

from beehive_resource.plugins.provider.entity.sql_stack import SqlComputeStack
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


class ProviderStack(LocalProviderApiView):
    resclass = SqlComputeStack
    parentclass = ComputeZone

    def set_password(self, controller, resource, password):
        """Set new root password for the database

        :param password: new password
        :return:
        """
        attribs = resource.get_attribs()
        attribs["admin_user"]["pwd"] = password
        resource.update(attribute=attribs)
        return True


class ListStacksRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone id or uuid")


class ListStacksResponseSchema(PaginatedResponseSchema):
    sql_stacks = fields.Nested(ResourceResponseSchema, many=True, required=True)


class ListStacks(ProviderStack):
    definitions = {
        "ListStacksResponseSchema": ListStacksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListStacksRequestSchema)
    parameters_schema = ListStacksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListStacksResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List sql_stacks
        List sql_stacks

        # - filter by: tags
        # - filter by: compute_zone
        """
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        data["attribute"] = '%"stack_type":"sql_stack"%'
        data["entity_class"] = self.resclass
        resources, total = self.get_resources_reference(controller, **data)

        resp = [r.info() for r in resources]

        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **data)


class GetStackResponseSchema(Schema):
    sql_stack = fields.Nested(ResourceResponseSchema, required=True)


class GetStack(ProviderStack):
    definitions = {
        "GetStackResponseSchema": GetStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get sql_stack
        Get sql_stack
        """
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        info = res.detail()
        return {self.resclass.objname: info}


class GetStackResourcesResponseSchema(Schema):
    sql_stack_resources = fields.List(fields.Dict(), required=True)


class GetStackResources(ProviderStack):
    definitions = {
        "GetStackResourcesResponseSchema": GetStackResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get sql_stack resources
        Get sql_stack resources
        """
        resource = self.get_resource_reference(controller, oid)
        resources = resource.resources()
        return {
            self.resclass.objname + "_resources": resources,
            "count": len(resources),
        }


class CreateStackParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where create sql",
    )
    flavor = fields.String(required=True, example="2995", description="id, uuid or name of the flavor")
    image = fields.String(required=True, example="2995", description="id, uuid or name of the image")
    vpc = fields.String(required=True, example="2995", description="id, uuid or name of the vpc")
    subnet = fields.String(required=True, example="10.102.167.90/24", description="subnet definition")
    security_group = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the security group",
    )
    db_name = fields.String(required=True, example="dbtest", description="First app database name")
    # db_appuser_name = fields.String(required=True, example='usertest', description='First app user name')
    # db_appuser_password = fields.String(required=True, example='', description='First app user password')
    db_root_name = fields.String(
        required=False,
        example="root",
        missing="root",
        description="The database admin account username",
    )
    db_root_password = fields.String(
        required=False,
        example="",
        description="The database admin password",
        allow_none=True,
    )
    key_name = fields.String(required=False, example="", description="Openstack public key name")
    version = fields.String(required=False, example="5.7", description="Database engine version")
    engine = fields.String(required=False, example="mysql", description="Database engine")
    root_disk_size = fields.Integer(required=False, example=40, missing=40, description="Size of root disk")
    data_disk_size = fields.Integer(required=False, example=30, missing=30, description="Size of data disk")
    geo_extension = fields.Bool(
        required=False,
        example=False,
        missing=False,
        description="If True enable geographic extension. Use only with postgres",
    )
    resolve = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if stack instances must registered on the availability_zone dns zone",
    )

    @validates_schema
    def validate_parameters(self, data, *args, **kvargs):
        valid_engine = SqlComputeStack.engine.keys()
        if data.get("engine") not in valid_engine:
            raise ValidationError("Supported engines are %s" % valid_engine)
        valid_versions = SqlComputeStack.engine.get(data.get("engine"))
        if data.get("version") not in valid_versions:
            raise ValidationError("Supported %s engine versions are %s" % (data.get("engine"), valid_versions))
        # if 'geo_extension' in data and data.get('engine') != 'postgres':
        #     raise ValidationError('geo_extension is supported only by engine postgres')


class CreateStackRequestSchema(Schema):
    sql_stack = fields.Nested(CreateStackParamRequestSchema, context="body")


class CreateStackBodyRequestSchema(Schema):
    body = fields.Nested(CreateStackRequestSchema, context="body")


class CreateStack(ProviderStack):
    definitions = {
        "CreateStackRequestSchema": CreateStackRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateStackBodyRequestSchema)
    parameters_schema = CreateStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create sql_stack
        Create sql_stack
        """
        res = self.create_resource(controller, data)
        return res


class UpdateStackParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateStackRequestSchema(Schema):
    sql_stack = fields.Nested(UpdateStackParamRequestSchema)


class UpdateStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateStackRequestSchema, context="body")


class UpdateStack(ProviderStack):
    definitions = {
        "UpdateStackRequestSchema": UpdateStackRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateStackBodyRequestSchema)
    parameters_schema = UpdateStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update sql_stack
        Update sql_stack
        """
        return self.update_resource(controller, oid, data)


class ActionStackParamRequestSchema(Schema):
    action = fields.String(
        required=True,
        example="set-password",
        description="Send and action to sql stack",
        validate=OneOf(["set-password"]),
    )
    params = fields.Dict(required=True, example={}, description="The action params")


class ActionStackRequestSchema(Schema):
    sql_stack_action = fields.Nested(ActionStackParamRequestSchema)


class ActionStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ActionStackRequestSchema, context="body")


class ActionStackResponseSchema(Schema):
    sql_stack_action = fields.List(fields.Dict(), required=True)


class ActionStack(ProviderStack):
    definitions = {
        "ActionStackRequestSchema": ActionStackRequestSchema,
        "ActionStackResponseSchema": ActionStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ActionStackBodyRequestSchema)
    parameters_schema = ActionStackRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": ActionStackResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Run sql_stack action
        Run sql_stack action
        """
        resource = self.get_resource_reference(controller, oid)
        data = data.get("sql_stack_action")
        action = data.get("action")
        params = data.get("params")
        action_func = getattr(action)
        res = resource.send_action(action_func, **params)
        return {self.resclass.objname + "_action": action, "response": res}


class DeleteStack(ProviderStack):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete sql_stack
        Delete sql_stack
        """
        return self.expunge_resource(controller, oid)


class GetStackCredentialsResponseSchema(Schema):
    sql_stack_credentials = fields.List(fields.Dict, required=True)


class GetStackCredentials(ProviderStack):
    definitions = {
        "GetStackCredentialsResponseSchema": GetStackCredentialsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get sql_stack credential
        Get sql_stack credential
        """
        resource = self.get_resource_reference(controller, oid)
        users = resource.get_root_credentials()
        return {"sql_stack_credentials": users}


class SetStackCredentialsRequestSchema(Schema):
    sql_stack_credentials = fields.List(
        fields.Dict,
        required=True,
        description='List of dict like {"user: "root", "pwd":<pwd>}',
    )


class SetStackCredentials(ProviderStack):
    definitions = {
        "SetStackCredentialsRequestSchema": SetStackCredentialsRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "success"}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Set sql_stack credential
        Set sql_stack credential
        """
        resource = self.get_resource_reference(controller, oid)
        users = resource.set_root_credentials(data.get("sql_stack_credentials"))
        return True, 204


class GetStackEngineResponseSchema(Schema):
    engine = fields.String(required=True, example="mysql", description="Engine name")
    version = fields.String(required=True, example="5.7", description="Engine version")


class GetStackEnginesResponseSchema(Schema):
    engines = fields.Nested(GetStackEngineResponseSchema, required=True)


class GetStackEngines(ProviderStack):
    definitions = {
        "GetStackEnginesResponseSchema": GetStackEnginesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        Get sql_stack engines
        Get sql_stack engines
        """
        engines = SqlComputeStack.get_engines()
        return {"engines": engines}


class SqlStackProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: compute_zone
            ("%s/sql_stacks" % base, "GET", ListStacks, {}),
            ("%s/sql_stacks/<oid>" % base, "GET", GetStack, {}),
            ("%s/sql_stacks/<oid>/resources" % base, "GET", GetStackResources, {}),
            ("%s/sql_stacks" % base, "POST", CreateStack, {}),
            ("%s/sql_stacks/<oid>" % base, "PUT", UpdateStack, {}),
            ("%s/sql_stacks/<oid>/action" % base, "PUT", ActionStack, {}),
            ("%s/sql_stacks/<oid>" % base, "DELETE", DeleteStack, {}),
            ("%s/sql_stacks/<oid>/credentials" % base, "GET", GetStackCredentials, {}),
            ("%s/sql_stacks/<oid>/credentials" % base, "PUT", SetStackCredentials, {}),
            ("%s/sql_stacks/engines" % base, "GET", GetStackEngines, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
