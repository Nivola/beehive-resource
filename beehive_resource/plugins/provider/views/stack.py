# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.entity.stack import ComputeStack
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
    CrudApiObjectSimpleResponseSchema,
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
    resclass = ComputeStack
    parentclass = ComputeZone


class ListStacksRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(context="query", description="comma separated list of compute zone id or uuid")


class ListStacksResponseSchema(PaginatedResponseSchema):
    stacks = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListStacks(ProviderStack):
    definitions = {
        "ListStacksResponseSchema": ListStacksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListStacksRequestSchema)
    parameters_schema = ListStacksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListStacksResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List stacks
        List stacks

        # - filter by: tags
        # - filter by: compute_zone
        """
        compute_zones = data.pop("compute_zones", None)
        if compute_zones is not None:
            data["parent_list"] = compute_zones.split(",")

        return self.get_resources(controller, **data)


class GetStackResponseSchema(Schema):
    stack = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetStack(ProviderStack):
    definitions = {
        "GetStackResponseSchema": GetStackResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get stack
        Get stack
        """
        return self.get_resource(controller, oid)


class GetStackResourcesResponseSchema(Schema):
    stack_resources = fields.List(fields.Dict(), required=True)


class GetStackResources(ProviderStack):
    definitions = {
        "GetStackResourcesResponseSchema": GetStackResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get stack resources
        Get stack resources
        """
        resource = self.get_resource_reference(controller, oid)
        resources = resource.resources()
        return {"stack_resources": resources, "count": len(resources)}


class GetStackInputsResponseSchema(Schema):
    stack_inputs = fields.List(fields.Dict(), required=True)


class GetStackInputs(ProviderStack):
    definitions = {
        "GetStackInputsResponseSchema": GetStackInputsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackInputsResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get stack inputs
        Get stack inputs
        """
        resource = self.get_resource_reference(controller, oid)
        inputs = resource.inputs()
        return {"stack_inputs": inputs, "count": len(inputs)}


class GetStackOutputsResponseSchema(Schema):
    stack_outputs = fields.List(fields.Dict(), required=True)


class GetStackOutputs(ProviderStack):
    definitions = {
        "GetStackOutputsResponseSchema": GetStackOutputsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackOutputsResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get stack outputs
        Get stack outputs
        """
        resource = self.get_resource_reference(controller, oid)
        outputs = resource.outputs()
        return {"stack_outputs": outputs, "count": len(outputs)}


class CreateStackTemplateRequestSchema(Schema):
    availability_zone = fields.String(
        required=True,
        example="2995",
        description="id, uuid or name of the site where is located the orchestrator",
    )
    orchestrator_type = fields.String(
        required=True,
        example="openstack",
        description="Orchestrator type. Can be " "openstack",
        validate=OneOf(["openstack"]),
    )
    template_uri = fields.String(
        required=True,
        example="https://localhost/hot/test_template.yaml",
        description="remote template uri",
    )
    owner = fields.String(required=False, example="admin", description="stack owner")
    environment = fields.Dict(required=False, default={}, description="additional environment")
    parameters = fields.Dict(
        required=True,
        example={"image_id": "centos7-guestagent"},
        description="stack input parameters",
    )
    files = fields.Dict(
        required=False,
        default={"myfile": '#!\/bin\/bash\necho "Hello" > \/root\/testfile.txt'},
        description="stack input files",
    )


class CreateStackParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    parameters = fields.Dict(
        required=True,
        example={"image_id": "centos7-guestagent"},
        description="stack input parameters",
    )
    templates = fields.Nested(
        CreateStackTemplateRequestSchema,
        many=True,
        required=True,
        allow_none=True,
        description="list of stack template per availability zone",
    )
    resolve = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if stack instances must registered on the availability_zone dns zone",
    )


class CreateStackRequestSchema(Schema):
    stack = fields.Nested(CreateStackParamRequestSchema)


class CreateStackBodyRequestSchema(Schema):
    body = fields.Nested(CreateStackRequestSchema, context="body")


class CreateStack(ProviderStack):
    definitions = {
        "CreateStackRequestSchema": CreateStackRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateStackBodyRequestSchema)
    parameters_schema = CreateStackRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """
        Create stack
        Create stack
        """
        return self.create_resource(controller, data)


class UpdateStackParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateStackRequestSchema(Schema):
    stack = fields.Nested(UpdateStackParamRequestSchema)


class UpdateStackBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateStackRequestSchema, context="body")


class UpdateStack(ProviderStack):
    definitions = {
        "UpdateStackRequestSchema": UpdateStackRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateStackBodyRequestSchema)
    parameters_schema = UpdateStackRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update stack
        Update stack
        """
        return self.update_resource(controller, oid, data)


class DeleteStack(ProviderStack):
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete stack
        Delete stack
        """
        return self.expunge_resource(controller, oid)


class GetManageResponseSchema(Schema):
    is_managed = fields.Boolean(
        required=True,
        description="Return True if compute zone is managed by ssh module",
    )


class GetManage(ProviderStack):
    definitions = {
        "GetManageResponseSchema": GetManageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetManageResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Check stack is managed
        Check stack is managed
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.is_managed()
        return {"is_managed": res}


class AddManageRequestParamSchema(Schema):
    user = fields.String(required=False, description="Node user", missing="root", example="root")
    password = fields.String(required=False, description="Node user password", missing="", example="test")
    key = fields.String(required=True, description="ssh key name or uuid", example="prova123")


class AddManageRequestSchema(Schema):
    manage = fields.Nested(AddManageRequestParamSchema, required=True, description="Management params")


class AddManageRequestBodySchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddManageRequestSchema, context="body")


class AddManageResponseSchema(Schema):
    manage = fields.Boolean(required=True, description="Ssh group uuid")


class AddManage(ProviderStack):
    definitions = {
        "AddManageRequestSchema": AddManageRequestSchema,
        "AddManageResponseSchema": AddManageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddManageRequestBodySchema)
    parameters_schema = AddManageRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": AddManageResponseSchema}})

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Manage stack
        Manage stack
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.manage(**data.get("manage"))
        return {"manage": res}


class DeleteManage(ProviderStack):
    definitions = {"CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "success"}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Unmanage stack
        Unmanage stack
        """
        stack = self.get_resource_reference(controller, oid)
        res = stack.unmanage()
        return None


class GetStackDnsResponseSchema(Schema):
    dns = fields.Dict(required=True)


class GetStackDns(ProviderStack):
    definitions = {
        "GetStackDnsResponseSchema": GetStackDnsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetStackDnsResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server dns recorda
        Get server dns recorda
        """
        obj = self.get_resource_reference(controller, oid, run_customize=False)
        res = obj.get_dns_recorda()
        resp = {"dns": [i.detail() for i in res]}
        return resp


class SetStackDnsResponseSchema(Schema):
    uuids = fields.List(fields.UUID, required=True)


class SetStackDns(ProviderStack):
    definitions = {
        "SetStackDnsResponseSchema": SetStackDnsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SetStackDnsResponseSchema}})

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Set server dns recorda
        Set server dns recorda
        """
        obj = self.get_resource_reference(controller, oid, run_customize=False)

        # check instance status
        if obj.get_base_state() != "ACTIVE":
            raise ApiManagerError("Stack %s is not in ACTIVE state" % obj.uuid)

        res = obj.set_dns_recorda(force=True, ttl=30)
        resp = {"uuids": res}
        return resp


class UnSetStackDnsResponseSchema(Schema):
    uuids = fields.List(fields.UUID, required=True)


class UnSetStackDns(ProviderStack):
    definitions = {
        "UnSetStackDnsResponseSchema": UnSetStackDnsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": UnSetStackDnsResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Unset server dns recorda
        Unset server dns recorda
        """
        obj = self.get_resource_reference(controller, oid, run_customize=False)

        # check instance status
        if obj.get_base_state() != "ACTIVE":
            raise ApiManagerError("Stack %s is not in ACTIVE state" % obj.uuid)

        res = obj.unset_dns_recorda()
        resp = {"uuids": res}
        return resp


class StackProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            # - filter by: compute_zone
            ("%s/stacks" % base, "GET", ListStacks, {}),
            ("%s/stacks/<oid>" % base, "GET", GetStack, {}),
            ("%s/stacks/<oid>/resources" % base, "GET", GetStackResources, {}),
            ("%s/stacks/<oid>/inputs" % base, "GET", GetStackInputs, {}),
            ("%s/stacks/<oid>/outputs" % base, "GET", GetStackOutputs, {}),
            ("%s/stacks" % base, "POST", CreateStack, {}),
            ("%s/stacks/<oid>" % base, "PUT", UpdateStack, {}),
            ("%s/stacks/<oid>" % base, "DELETE", DeleteStack, {}),
            ("%s/stacks/<oid>/manage" % base, "GET", GetManage, {}),
            ("%s/stacks/<oid>/manage" % base, "POST", AddManage, {}),
            ("%s/stacks/<oid>/manage" % base, "DELETE", DeleteManage, {}),
            ("%s/stacks/<oid>/dns" % base, "GET", GetStackDns, {}),
            ("%s/stacks/<oid>/dns" % base, "POST", SetStackDns, {}),
            ("%s/stacks/<oid>/dns" % base, "DELETE", UnSetStackDns, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
