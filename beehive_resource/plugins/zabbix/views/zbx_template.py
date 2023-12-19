# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte

from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.zabbix.entity.zbx_template import ZabbixTemplate
from beehive_resource.plugins.zabbix.views import ZabbixAPI, ZabbixApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)


class ZabbixTemplateApiView(ZabbixApiView):
    tags = ["zabbix"]
    resclass = ZabbixTemplate
    parentclass = None


class ListTemplatesRequestSchema(ListResourcesRequestSchema):
    pass


class ListTemplatesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListTemplatesResponseSchema(PaginatedResponseSchema):
    # templates = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)
    templates = fields.List(fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True))


class ListTemplates(ZabbixTemplateApiView):
    definitions = {
        "ListTemplatesResponseSchema": ListTemplatesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListTemplatesRequestSchema)
    parameters_schema = ListTemplatesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListTemplatesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """List templates"""
        return self.get_resources(controller, **data)


class GetTemplateResponseSchema(Schema):
    template = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetTemplate(ZabbixTemplateApiView):
    definitions = {
        "GetTemplateResponseSchema": GetTemplateResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetTemplateResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get template"""
        return self.get_resource(controller, oid)


class CreateTemplateParamRequestSchema(Schema):
    container = fields.String(required=True, example="1234", description="container id, uuid or name")
    name = fields.String(required=True, example="linux template")
    desc = fields.String(required=False, example="template description")
    groups = fields.List(
        fields.String(
            required=True,
            example="['50', '62']",
            many=True,
            allow_none=True,
            description="hostgroups to add the template to",
        )
    )


class CreateTemplateRequestSchema(Schema):
    template = fields.Nested(CreateTemplateParamRequestSchema)


class CreateHostBodyRequestSchema(Schema):
    body = fields.Nested(CreateTemplateRequestSchema, context="body")


class CreateTemplate(ZabbixTemplateApiView):
    definitions = {
        "CreateTemplateRequestSchema": CreateTemplateRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateHostBodyRequestSchema)
    parameters_schema = CreateTemplateRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Create template"""
        return self.create_resource(controller, data)


class UpdateTemplate(ZabbixTemplateApiView):
    def put(self, controller, data, oid, *args, **kwargs):
        """Update template"""
        return self.update_resource(controller, oid, data)


class DeleteTemplate(ZabbixTemplateApiView):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete template"""
        return self.expunge_resource(controller, oid)


class ZabbixTemplateAPI(ZabbixAPI):
    """Zabbix base platform api routes"""

    @staticmethod
    def register_api(module, *args, **kwargs):
        base = ZabbixAPI.base
        rules = [
            ("%s/templates" % base, "GET", ListTemplates, {}),
            ("%s/templates/<oid>" % base, "GET", GetTemplate, {}),
            ("%s/templates" % base, "POST", CreateTemplate, {}),
            # ('%s/templates/<oid>' % base, 'PUT', UpdateTemplate, {}),
            ("%s/templates/<oid>" % base, "DELETE", DeleteTemplate, {}),
        ]

        ZabbixAPI.register_api(module, rules, **kwargs)
