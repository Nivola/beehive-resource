# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations
from marshmallow import validates_schema, ValidationError
from marshmallow.validate import OneOf

from beecell.types.res.paas import (
    CreatePaasParamRequestSchema, 
    UpdatePaasParamRequestSchema, 
    GetPaasEngineResponseSchema, 
    CreatePaasParamRequestDict, 
    UpdatePaasParamRequestDict, 
    GetPaasEngineResponseDict,
)

from beehive_resource.plugins.provider.controller import LocalProvider
from beehive_resource.plugins.provider.entity.paas_stackv2 import PaasStackV2
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
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

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController


class ProviderPaasStackView(LocalProviderApiView):
    resclass = PaasStackV2
    parentclass = ComputeZone


class ListPaasRequestSchema(ListResourcesRequestSchema):
    compute_zones = fields.String(
        context="query",
        metadata={
            "description": 'comma separated list of compute zone id or uuid',
        },
    )


class ListPaasResponseSchema(PaginatedResponseSchema):
    paas = fields.Nested(ResourceResponseSchema, many=True, required=True)


class ListPaas(ProviderPaasStackView):
    definitions = {"ListPaasResponseSchema": ListPaasResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListPaasRequestSchema)
    parameters_schema = ListPaasRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListPaasResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        """
        List paas
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

        return self.format_paginated_response(resp, self.resclass.objname, total, **data)


class GetPaasResponseSchema(Schema):
    paas = fields.Nested(ResourceResponseSchema, required=True)


class GetPaas(ProviderPaasStackView):
    definitions = {"GetPaasResponseSchema": GetPaasResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetPaasResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        """
        Get paas
        """
        containers, tot = controller.get_containers(container_type="Provider")
        container :LocalProvider= containers[0]
        res : PaasStackV2 = container.get_resource(oid, entity_class=self.resclass)
        info = res.detail()
        return {PaasStackV2.objname: info}



class CreatePaasRequestSchema(Schema):
    paas = fields.Nested(CreatePaasParamRequestSchema, context="body")


class CreatePaasBodyRequestSchema(Schema):
    body = fields.Nested(CreatePaasRequestSchema, context="body")


class CreatePaas(ProviderPaasStackView):
    summary = "Create new paas"
    description = "Create new paas"

    definitions = {
        "CreatePaasRequestSchema": CreatePaasRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreatePaasBodyRequestSchema)
    parameters_schema = CreatePaasRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller: ResourceController, data: dict, *args, **kwargs):
        # move engine_config parameters into attribute in order to store info in model
        params: CreatePaasParamRequestDict = data["paas"]
        engine_configs = params.get("engine_configs")
        attribute: dict = data.get("attribute", {})
        # attribute.update({"engine_configs": engine_configs})
        # data["attribute"]= attribute
        res = self.create_resource(controller, data)
        return res


class UpdatePaasRequestSchema(Schema):
    paas = fields.Nested(UpdatePaasParamRequestSchema)


class UpdatePaasBodyRequestSchema(Schema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name',
        },
    )

    body = fields.Nested(UpdatePaasRequestSchema, context="body")


class UpdatePaas(ProviderPaasStackView):
    definitions = {
        "UpdatePaasRequestSchema": UpdatePaasRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdatePaasBodyRequestSchema)
    parameters_schema = UpdatePaasRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data:UpdatePaasParamRequestDict, oid:str, *args, **kwargs):
        """
        Update sql_stack
        """
        return self.update_resource(controller, oid, data)


class DeletePaas(ProviderPaasStackView):
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller: ResourceController, data, oid, *args, **kwargs):
        """
        Delete sql_stack
        """
        res = self.expunge_resource(controller, oid)
        return res


class GetPaasEnginesResponseSchema(Schema):
    engines = fields.Nested(GetPaasEngineResponseSchema, required=True)


class GetPaasEngines(ProviderPaasStackView):
    definitions = {"GetPaasEnginesResponseSchema": GetPaasEnginesResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetPaasResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        Get sql_stack engines
        """
        engines = PaasStackV2.get_engines()
        return {"engines": engines}


class PaasProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/paas" % base, "GET", ListPaas, {}),
            ("%s/paas/<oid>" % base, "GET", GetPaas, {}),
            ("%s/paas" % base, "POST", CreatePaas, {}),
            ("%s/paas/<oid>" % base, "PUT", UpdatePaas, {}),
            ("%s/paas/<oid>" % base, "DELETE", DeletePaas, {}),
            ("%s/paas/engines" % base, "GET", GetPaasEngines, {}),
        ]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
