# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from typing import TYPE_CHECKING

from beehive.common.apimanager import (
    ApiView,
    ApiObjectSmallResponseSchema,
    ApiObjectResponseSchema,
    PaginatedRequestQuerySchema,
    PaginatedResponseSchema,
    SwaggerApiView,
    ApiObjecCountResponseSchema,
    GetApiObjectRequestSchema,
    ApiObjectPermsRequestSchema,
    ApiObjectPermsResponseSchema,
    CrudApiObjectResponseSchema,
    CrudApiObjectTaskResponseSchema,
    CrudApiObjectSimpleResponseSchema,
)

from flasgger import fields, Schema
from marshmallow.validate import OneOf
from beecell.swagger import SwaggerHelper
from beehive_resource.views import ResourceApiView

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController


class UpdateResourceTagDescRequestSchema(Schema):
    cmd = fields.String(default="add", required=True)
    values = fields.List(fields.String(default="test"), required=True)


class SmallDataResponseSchema(Schema):
    id = fields.Integer(required=False, example=1)
    uuid = fields.UUID(
        required=False,
        allow_none=True,
        metadata={
            "example": '6d960236-d280-46d2-817d-f3ce8f0aeff7',
        },
    )

    name = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'test',
        },
    )


class ResourceSmallResponseSchema(ApiObjectSmallResponseSchema):
    state = fields.String(
        required=True,
        metadata={
            "example": 'ACTIVE',
        },
    )


class ResourceResponseSchema(ApiObjectResponseSchema):
    details = fields.Dict(
        required=True,
        dump_default={},
    )

    attributes = fields.Dict(
        required=True,
        dump_default={},
    )

    ext_id = fields.String(
        required=True,
        allow_none=True,
        metadata={
            "example": '6d960236-d280-46d2-817d-f3ce8f0aeff7',
        },
    )

    parent = fields.Integer(
        required=True,
        allow_none=True,
    )

    container = fields.Integer(
        required=True,
        allow_none=True,
    )

    reuse = fields.Boolean(
        required=True,
        dump_default=False,
        metadata={
            "example": False,
        },
    )

    state = fields.String(
        required=True,
        metadata={
            "example": 'ACTIVE',
        },
    )

    child = fields.Integer(
        required=True,
        metadata={
            "example": '0',
        },
    )


class CreateResourceBaseRequestSchema(Schema):
    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'The security group name',
        },
    )

    container = fields.String(
        required=True,
        metadata={
            "example": '10',
            "description": 'Container id, uuid or name',
        },
    )

    tags = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'tag1,tag2',
            "description": 'comma separated list of tags to assign',
        },
    )


class ListResourcesRequestSchema(PaginatedRequestQuerySchema):
    uuids = fields.String(
        context="query",
        metadata={
            "description": 'comma separated list of uuid',
        },
    )

    tags = fields.String(
        context="query",
        metadata={
            "description": 'comma separated list of tags',
        },
    )

    type = fields.String(
        context="query",
        metadata={
            "description": 'resource type complete syntax or %partial type%',
        },
    )

    objid = fields.String(
        context="query",
        metadata={
            "description": 'resource objid',
        },
    )

    name = fields.String(
        context="query",
        metadata={
            "description": 'resource name',
        },
    )

    desc = fields.String(
        context="query",
        metadata={
            "description": 'resource description',
        },
    )

    ext_id = fields.String(
        context="query",
        metadata={
            "description": 'resource remote physical id',
        },
    )

    ext_ids = fields.String(
        context="query",
        metadata={
            "description": 'list of resource remote physical ids',
        },
    )

    container = fields.String(
        context="query",
        metadata={
            "description": 'resource container id, uuid or name',
        },
    )
    attribute = fields.String(
        context="query",
        metadata={
            "description": 'resource attribute',
        },
    )

    parent = fields.String(
        context="query",
        metadata={
            "description": 'resource parent',
        },
    )

    parent_list = fields.String(
        context="query",
        metadata={
            "description": 'resource parent list',
        },
    )

    state = fields.String(
        context="query",
        metadata={
            "description": (
                'resource state like PENDING, BUILDING, ACTIVE, UPDATING, ERROR, DELETING, DELETED, EXPUNGING,'
                'EXPUNGED, UNKNOWN, DISABLED'
            ),
        },
    )

    active = fields.Boolean(
        context="query",
        required=False,
        metadata={
            "example": True,
            "description": 'True if resource is active',
        },
    )

    show_expired = fields.Boolean(
        context="query",
        required=False,
        load_default=False,
        metadata={
            "example": True,
            "description": 'If True show expired resources',
        },
    )


class ListResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListResources(ResourceApiView):
    tags = ["resource"]
    definitions = {"ListResourcesResponseSchema": ListResourcesResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListResourcesRequestSchema)
    parameters_schema = ListResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListResourcesResponseSchema}})

    def get(self, controller: 'ResourceController', data, *args, **kwargs):
        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        data["parents"] = {}
        data["run_customize"] = False

        resources, total = controller.get_resources(**data)
        res = [r.info() for r in resources]
        return self.format_paginated_response(res, "resources", total, **data)


class ListResourceTypesRequestSchema(Schema):
    id = fields.Integer(
        context="query",
        metadata={
            "example": 23,
        },
    )

    type = fields.String(
        context="query",
        metadata={
            "example": 'resource',
        },
    )


class ListResourceTypesParamsResponseSchema(Schema):
    id = fields.Integer(
        required=True,
        metadata={
            "example": 23,
        },
    )

    type = fields.String(
        required=True,
        metadata={
            "example": 'resource',
        },
    )

    resclass = fields.String(
        required=True,
    )


class ListResourceTypesResponseSchema(Schema):
    resourcetypes = fields.Nested(
        ListResourceTypesParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )

    count = fields.Integer(required=True)


class ListResourceTypes(ResourceApiView):
    tags = ["resource"]
    definitions = {"ListResourceTypesResponseSchema": ListResourceTypesResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListResourceTypesRequestSchema)
    parameters_schema = ListResourceTypesRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListResourceTypesResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, *args, **kwargs):
        res = controller.get_resource_types(oid=data.get("id", None), rfilter=data.get("type", None))
        resp = {"resourcetypes": res, "count": len(res)}
        return resp


class CountResources(ResourceApiView):
    tags = ["resource"]
    definitions = {"ApiObjecCountResponseSchema": ApiObjecCountResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjecCountResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resp = controller.count_all_resources()
        return {"count": int(resp)}


class GetResourceResponseSchema(Schema):
    resource = fields.Nested(
        ResourceResponseSchema,
        required=True,
        allow_none=True,
    )


class GetResource(ResourceApiView):
    tags = ["resource"]
    definitions = {"GetResourceResponseSchema": GetResourceResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        return {"resource": resource.detail()}


class CheckResourcesRequestSchema(PaginatedRequestQuerySchema):
    uuids = fields.String(
        context="query",
        metadata={
            "description": 'comma separated list of uuid',
        },
    )

    tags = fields.String(
        context="query",
        metadata={
            "description": 'comma separated list of tags',
        },
    )

    type = fields.String(
        context="query",
        metadata={
            "description": 'resource type complete syntax or %partial type%',
        },
    )

    objid = fields.String(
        context="query",
        metadata={
            "description": 'resource objid',
        },
    )

    name = fields.String(
        context="query",
        metadata={
            "description": 'resource name',
        },
    )

    ext_id = fields.String(
        context="query",
        metadata={
            "description": 'resource remote physical id',
        },
    )

    ext_ids = fields.String(
        context="query",
        metadata={
            "description": 'list of resource remote physical ids',
        },
    )

    container = fields.String(
        context="query",
        metadata={
            "description": 'resource container id, uuid or name',
        },
    )

    attribute = fields.String(
        context="query",
        metadata={
            "description": 'resource attribute',
        },
    )

    parent = fields.String(
        context="query",
        metadata={
            "description": 'resource parent',
        },
    )

    parent_list = fields.String(
        context="query",
        metadata={
            "description": 'resource parent list',
        },
    )

    state = fields.String(
        context="query",
        metadata={
            "description": (
                'resource state like PENDING, BUILDING, ACTIVE, UPDATING, ERROR, DELETING, DELETED, EXPUNGING,'
                'EXPUNGED, UNKNOWN, DISABLED'
            ),
        },
    )

    active = fields.Boolean(
        context="query",
        required=False,
        metadata={
            "example": True,
            "description": 'True if resource is active',
        },
    )


class CheckResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class CheckResources(ResourceApiView):
    tags = ["resource"]
    definitions = {"CheckResourcesResponseSchema": CheckResourcesResponseSchema}
    parameters = SwaggerHelper().get_parameters(CheckResourcesRequestSchema)
    parameters_schema = CheckResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckResourcesResponseSchema}})

    def get(self, controller: 'ResourceController', data, *args, **kwargs):
        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        data["parents"] = {}
        data["run_customize"] = False
        resources, total = controller.get_resources(**data)
        res = []
        for r in resources:
            check = r.check()
            item = r.info()
            item["check"] = check
            res.append(item)
        return self.format_paginated_response(res, "resources", total, **data)


class CheckResourceRequestSchema(GetApiObjectRequestSchema):
    pass


class CheckResourceResponseSchema(PaginatedResponseSchema):
    resource = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class CheckResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "CheckResourceResponseSchema": CheckResourceResponseSchema,
        "CheckResourceRequestSchema": CheckResourceRequestSchema,
    }

    parameters = SwaggerHelper().get_parameters(CheckResourceRequestSchema)
    parameters_schema = CheckResourceRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckResourcesResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        check = resource.check()
        item = resource.info()
        item["check"] = check
        if item["check"]["check"] is False:
            item["state"] = "BAD"
        resp = {"resource": item}
        return resp


class GetResourcePerms(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "ApiObjectPermsRequestSchema": ApiObjectPermsRequestSchema,
        "ApiObjectPermsResponseSchema": ApiObjectPermsResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ApiObjectPermsRequestSchema)
    parameters_schema = PaginatedRequestQuerySchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjectPermsResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        res, total = resource.authorization(**data)
        return self.format_paginated_response(res, "perms", total, **data)


class GetResourceErrorsParamsResponseSchema(Schema):
    error = fields.String(
        required=True,
        dump_default="some error",
    )


class GetResourceErrorsResponseSchema(Schema):
    resource_errors = fields.Nested(
        GetResourceErrorsParamsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )

    count = fields.Integer(
        required=True,
        dump_default=0,
    )


class GetResourceErrors(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
        "GetResourceErrorsResponseSchema": GetResourceErrorsResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceErrorsResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        res = resource.get_errors()
        resp = {"resource_errors": res, "count": len(res)}
        return resp

class GetResourceTreeRequestSchema(GetApiObjectRequestSchema):
    parent = fields.Boolean(
        required=False,
        context="query",
    )

    link = fields.Boolean(
        required=False,
        context="query",
    )


class GetResourceTreeResponseSchema(Schema):
    resourcetree = fields.Dict(required=True)


class GetResourceTree(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "GetResourceTreeRequestSchema": GetResourceTreeRequestSchema,
        "GetResourceTreeResponseSchema": GetResourceTreeResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetResourceTreeRequestSchema)
    parameters_schema = GetResourceTreeRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceTreeResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_resource(oid)
        data.pop("oid")
        res = resource.tree(**data)
        resp = {"resourcetree": res}
        return resp


class GetLinkedResourcesRequestSchema2(PaginatedRequestQuerySchema):
    type = fields.String(context="query")
    link_type = fields.String(context="query")
    container = fields.String(context="query")


class GetLinkedResourcesRequestSchema(GetLinkedResourcesRequestSchema2):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid',
        },
    )


class GetLinkedResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class GetLinkedResources(ResourceApiView):
    tags = ["resource"]
    definitions = {"GetLinkedResourcesResponseSchema": GetLinkedResourcesResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetLinkedResourcesRequestSchema)
    parameters_schema = GetLinkedResourcesRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetLinkedResourcesResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        data["parents"] = {}
        data.pop("oid")
        resources, total = resource.get_linked_resources(**data)
        res = [r.info() for r in resources]
        return self.format_paginated_response(res, "resources", total, **data)


class CreateResourceParamRequestSchema(Schema):
    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
        },
    )

    desc = fields.String(
        required=False,
        metadata={
            "example": 'test',
        },
    )

    ext_id = fields.String(
        allow_none=True,
    )

    attribute = fields.Dict(
        allow_none=True,
    )

    parent = fields.String(
        allow_none=True,
    )

    container = fields.String(
        required=True,
        metadata={
            "example": '10',
        },
    )

    resclass = fields.String(
        required=True,
        metadata={
            "example": 'Openstack.Domain',
        },
    )

    tags = fields.String(allow_none=True)

    sync = fields.Bool(
        required=False,
        load_default=False,
        metadata={
            "example": 'set api execution as sync',
        },
    )


class CreateResourceRequestSchema(Schema):
    resource = fields.Nested(CreateResourceParamRequestSchema)


class CreateResourceBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateResourceRequestSchema,
        context="body",
    )


class CreateResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "CreateResourceRequestSchema": CreateResourceRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateResourceBodyRequestSchema)
    parameters_schema = CreateResourceRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            201: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def post(self, controller: 'ResourceController', data, *args, **kwargs):
        resp = self.create_resource(controller, data, check_name=True)
        return resp


class ImportResourceParamRequestSchema(Schema):
    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'test',
        },
    )

    ext_id = fields.String(
        load_default=None,
        metadata={
            "description": 'Physical resource id',
        },
    )

    attribute = fields.Dict(allow_none=True)
    parent = fields.String()

    container = fields.String(
        required=True,
        metadata={
            "example": '10',
        },
    )

    resclass = fields.String(
        required=True,
        metadata={
            "example": 'Openstack.Domain',
        },
    )

    tags = fields.String()

    configs = fields.Dict(
        load_default={},
        metadata={
            "description": 'Custom configurations',
        },
    )

    sync = fields.Bool(
        required=False,
        load_default=False,
        metadata={
            "example": 'set api execution as sync',
        },
    )


class ImportResourceRequestSchema(Schema):
    resource = fields.Nested(ImportResourceParamRequestSchema)


class ImportResourceBodyRequestSchema(Schema):
    body = fields.Nested(
        ImportResourceRequestSchema,
        context="body",
    )


class ImportResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "ImportResourceRequestSchema": ImportResourceRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ImportResourceBodyRequestSchema)
    parameters_schema = ImportResourceRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            201: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def post(self, controller: 'ResourceController', data, *args, **kwargs):
        resp = self.import_resource(controller, data, check_name=True)
        return resp


class CloneResourceParamRequestSchema(Schema):
    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'resource name',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'resource description',
        },
    )

    parent = fields.String(
        required=False,
        metadata={
            "example": '123',
            "description": 'resource parent id',
        },
    )

    container = fields.String(
        required=False,
        metadata={
            "example": '10',
            "description": 'resource container id',
        },
    )

    configs = fields.Dict(
        required=False,
        load_default={},
        metadata={
            "description": 'Custom configurations',
        },
    )

    sync = fields.Bool(
        required=False,
        load_default=False,
        metadata={
            "description": 'set api execution as sync',
        },
    )

    resource_id = fields.String(
        required=True,
        metadata={
            "description": 'id of the resource to clone',
        },
    )


class CloneResourceRequestSchema(Schema):
    resource = fields.Nested(CloneResourceParamRequestSchema)


class CloneResourceBodyRequestSchema(Schema):
    body = fields.Nested(
        CloneResourceRequestSchema,
        context="body",
    )


class CloneResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "CloneResourceRequestSchema": CloneResourceRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CloneResourceBodyRequestSchema)
    parameters_schema = CloneResourceRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            201: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def post(self, controller: 'ResourceController', data, *args, **kwargs):
        raise NotImplementedError()
        #resp = self.clone_resource(controller, data, check_name=True)
        #return resp


class UpdateResourceParamRequestSchema(Schema):
    name = fields.String(
        metadata={
            "example": 'test',
        },
    )

    desc = fields.String(
        metadata={
            "example": 'test',
        },
    )

    ext_id = fields.String(
        allow_none=True,
        metadata={
            "example": '345t6',
        },
    )

    active = fields.Boolean(
        metadata={
            "example": True,
        },
    )

    attribute = fields.Dict()

    state = fields.String(
        metadata={
            "example": 'ACTIVE',
        },
    )

    tags = fields.Nested(
        UpdateResourceTagDescRequestSchema,
        allow_none=True,
    )

    force = fields.Boolean(
        metadata={
            "example": False,
        },
    )

    enable_quotas = fields.Boolean(
        load_default=None,
        metadata={
            "example": True,
            "description": 'enable resource quotas discover',
        },
    )
    
    disable_quotas = fields.Boolean(
        load_default=None,
        metadata={
            "example": True,
            "description": 'disable resource quotas discover',
        },
    )

    sync = fields.Bool(
        required=False,
        load_default=False,
        metadata={
            "example": 'set api execution as sync',
        },
    )


class UpdateResourceRequestSchema(Schema):
    resource = fields.Nested(UpdateResourceParamRequestSchema)


class UpdateResourceBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateResourceRequestSchema, context="body")


class UpdateResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "UpdateResourceRequestSchema": UpdateResourceRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateResourceBodyRequestSchema)
    parameters_schema = UpdateResourceRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            200: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resp = self.update_resource(controller, oid, data)
        return resp


class PatchResourceRequestSchema(Schema):
    resource = fields.Dict(
        metadata={
            "description": 'Custom key value params',
        },
    )


class PatchResourceBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(PatchResourceRequestSchema, context="body")


class PatchResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "PatchResourceRequestSchema": PatchResourceRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(PatchResourceBodyRequestSchema)
    parameters_schema = PatchResourceRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            200: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def patch(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resp = self.patch_resource(controller, oid, data)
        return resp


class DeleteResourceRequest2Schema(Schema):
    force = fields.Boolean(
        context="query",
        load_default=False,
        metadata={
            "description": 'if true force delete with all the resource state',
        },
    )

    deep = fields.Boolean(
        context="query",
        load_default=True,
        metadata={
            "description": 'if True run deep delete. If False delete only resource',
        },
    )

    sync = fields.Bool(
        context="query",
        required=False,
        load_default=False,
        metadata={
            "example": 'set api execution as sync',
        },
    )


class DeleteResourceRequestv20Schema(GetApiObjectRequestSchema, DeleteResourceRequest2Schema):
    pass


class DeleteResource(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "DeleteResourceRequestv20Schema": DeleteResourceRequestv20Schema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(DeleteResourceRequestv20Schema)
    parameters_schema = DeleteResourceRequest2Schema

    responses = SwaggerApiView.setResponses(
        {
            200: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def delete(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        res = self.expunge_resource(controller, oid, **data)
        return res


class MetricParamsResponseSchema(Schema):
    key = fields.String(required=True)
    value = fields.String(required=True)
    unit = fields.String(required=True)
    type = fields.Integer(required=True)


class GetResourceMetricsParamsResponseSchema(Schema):
    metrics = fields.Nested(
        MetricParamsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )

    id = fields.String(required=True)
    uuid = fields.String(required=True)
    type = fields.String(required=True)
    extraction_date = fields.DateTime(required=True)
    resource_uuid = fields.String(required=True)


class GetResourceMetricsResponseSchema(Schema):
    resource = fields.Nested(
        GetResourceMetricsParamsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetResourceMetrics(ResourceApiView):
    definitions = {"GetResourceMetricsResponseSchema": GetResourceMetricsResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceMetricsResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Get resource metrics

        {"resource": [{
            "id": "1",
            "uuid": "vm1",
            "type": "Provider.ComputeZone.ComputeFileShare",
            "metrics": [
                {
                    "key": "ram",
                    "value: 10
                }],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"
        },{
            "id": "2",
            "uuid": "vm2",
            "type": "Provider.ComputeZone.ComputeFileShare",
            "metrics": [
                {
                    "key": "ram",
                    "value: 8
                },
                {
                    "key": "cpu_vw",
                    "value: 10
                }
            ],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"
        }]
        }
        """
        res = controller.get_resource(oid)
        resource_metrics = res.get_metrics()
        return {"resource": resource_metrics}


class GetResourceConfigResponseSchema(Schema):
    config = fields.Dict(required=True)


class GetResourceConfig(ResourceApiView):
    tags = ["resource"]
    definitions = {"GetResourceConfigResponseSchema": GetResourceConfigResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceConfigResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        return {"config": resource.get_attribs()}


class UpdateResourceConfigParamRequestSchema(Schema):
    key = fields.String(
        required=True,
        metadata={
            "example": 'test',
        },
    )

    value = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'test',
        },
    )


class UpdateResourceConfigRequestSchema(Schema):
    config = fields.Nested(
        UpdateResourceConfigParamRequestSchema,
        required=True,
        many=False,
        allow_none=True,
    )


class UpdateResourceConfigBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        UpdateResourceConfigRequestSchema,
        context="body",
    )


class UpdateResourceConfig(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "UpdateResourceConfigRequestSchema": UpdateResourceConfigRequestSchema,
        "GetResourceConfigResponseSchema": GetResourceConfigResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateResourceConfigBodyRequestSchema)
    parameters_schema = UpdateResourceConfigRequestSchema

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceConfigResponseSchema}}
    )

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        if data.get("config").get("value") is None:
            resource.unset_configs(key=data.get("config").get("key"))
        else:
            resource.set_configs(**data.get("config"))
        return True


class UpdateResourceStateRequestSchema(Schema):
    state = fields.String(
        required=True,
        validate=OneOf(['ACTIVE', 'ERROR', 'DISABLED']),
        metadata={
            "description": 'Resource state to set',
        },
    )


class UpdateResourceStateBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        UpdateResourceStateRequestSchema,
        context="body",
    )


class UpdateResourceState(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "UpdateResourceStateRequestSchema": UpdateResourceStateRequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateResourceStateBodyRequestSchema)
    parameters_schema = UpdateResourceStateRequestSchema

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        resource.set_state(data.get("state"))
        return {"state": data.get("state")}


class GetResourceCache(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        res = resource.get_cache()
        return res


class CleanResourceCache(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        resource.clean_cache()
        return {"uuid": resource.uuid}


class UpdateResourceRegisterRequestSchema(Schema):
    pass


class UpdateResourceRegisterBodyRequestSchema(Schema):
    pass


class UpdateResourceRegisterResponseSchema(Schema):
    pass


class UpdateResourceRegister(ResourceApiView):
    tags = ["resource"]

    definitions = {
        "UpdateResourceRegisterRequestSchema": UpdateResourceRegisterRequestSchema,
        "UpdateResourceRegisterResponseSchema": UpdateResourceRegisterResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateResourceRegisterBodyRequestSchema)
    parameters_schema = UpdateResourceRegisterRequestSchema

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": UpdateResourceRegisterResponseSchema}}
    )

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        objids = resource.objid.split("//")
        resource.register_object_permtags(objids)


class ResourceEntityAPI(ApiView):
    """Resource api routes v2 :"""

    @staticmethod
    def register_api(module, **kwargs):
        rules = [
            ("%s/entities" % module.base_path, "GET", ListResources, {}),
            ("%s/entities" % module.base_path, "POST", CreateResource, {}),
            ("%s/entities/import" % module.base_path, "POST", ImportResource, {}),
            ("%s/entities/clone" % module.base_path, "POST", CloneResource, {}),
            ("%s/entities/count" % module.base_path, "GET", CountResources, {}),
            ("%s/entities/types" % module.base_path, "GET", ListResourceTypes, {}),
            ("%s/entities/<oid>" % module.base_path, "GET", GetResource, {}),
            ("%s/entities/<oid>" % module.base_path, "PUT", UpdateResource, {}),
            ("%s/entities/<oid>" % module.base_path, "PATCH", PatchResource, {}),
            ("%s/entities/<oid>" % module.base_path, "DELETE", DeleteResource, {}),
            ("%s/entities/check" % module.base_path, "GET", CheckResources, {}),
            # ('%s/entities/<oid>/jobs' % module.base_path, 'GET', GetResourceJobs, {}),
            (
                "%s/entities/<oid>/errors" % module.base_path,
                "GET",
                GetResourceErrors,
                {},
            ),
            ("%s/entities/<oid>/tree" % module.base_path, "GET", GetResourceTree, {}),
            ("%s/entities/<oid>/perms" % module.base_path, "GET", GetResourcePerms, {}),
            (
                "%s/entities/<oid>/linked" % module.base_path,
                "GET",
                GetLinkedResources,
                {},
            ),
            (
                "%s/entities/<oid>/metrics" % module.base_path,
                "GET",
                GetResourceMetrics,
                {},
            ),
            (
                "%s/entities/<oid>/config" % module.base_path,
                "GET",
                GetResourceConfig,
                {},
            ),
            (
                "%s/entities/<oid>/config" % module.base_path,
                "PUT",
                UpdateResourceConfig,
                {},
            ),
            (
                "%s/entities/<oid>/state" % module.base_path,
                "PUT",
                UpdateResourceState,
                {},
            ),
            ("%s/entities/<oid>/cache" % module.base_path, "GET", GetResourceCache, {}),
            (
                "%s/entities/<oid>/cache" % module.base_path,
                "PUT",
                CleanResourceCache,
                {},
            ),
            ("%s/entities/<oid>/check" % module.base_path, "GET", CheckResource, {}),
            (
                "%s/entities/<oid>/register" % module.base_path,
                "PUT",
                UpdateResourceRegister,
                {},
            ),
        ]
        kwargs["version"] = "v2.0"
        ApiView.register_api(module, rules, **kwargs)
