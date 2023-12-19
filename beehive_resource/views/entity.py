# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

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
from marshmallow import fields, Schema
from marshmallow.validate import OneOf, Range
from beecell.swagger import SwaggerHelper
from beehive_resource.views import ResourceApiView


class UpdateResourceTagDescRequestSchema(Schema):
    cmd = fields.String(default="add", required=True)
    values = fields.List(fields.String(default="test"), required=True)


class SmallDataResponseSchema(Schema):
    id = fields.Integer(required=False, default=1, example=1)
    uuid = fields.UUID(
        required=False,
        allow_none=True,
        default="6d960236-d280-46d2-817d-f3ce8f0aeff7",
        example="6d960236-d280-46d2-817d-f3ce8f0aeff7",
    )
    name = fields.String(required=False, default="test", example="test", allow_none=True)


class ResourceSmallResponseSchema(ApiObjectSmallResponseSchema):
    state = fields.String(required=True, default="ACTIVE", example="ACTIVE")


class ResourceResponseSchema(ApiObjectResponseSchema):
    details = fields.Dict(required=True, default={}, example={})
    attributes = fields.Dict(required=True, default={}, example={})
    ext_id = fields.String(
        required=True,
        allow_none=True,
        default="6d960236-d280-46d2-817d-f3ce8f0aeff7",
        example="6d960236-d280-46d2-817d-f3ce8f0aeff7",
    )
    # parent = fields.Nested(SmallDataResponseSchema, required=True, allow_none=True)
    # container = fields.Nested(SmallDataResponseSchema, required=True, allow_none=True)
    parent = fields.Integer(required=True, allow_none=True)
    container = fields.Integer(required=True, allow_none=True)
    reuse = fields.Boolean(required=True, default=False, example=False)
    state = fields.String(required=True, default="ACTIVE", example="ACTIVE")
    child = fields.Integer(required=True, default=0, example=0)


class CreateResourceBaseRequestSchema(Schema):
    name = fields.String(required=True, example="test", description="The security group name")
    container = fields.String(required=True, default="10", description="Container id, uuid or name")
    tags = fields.String(
        required=False,
        default="",
        example="tag1,tag2",
        allow_none=True,
        description="comma separated list of tags to assign",
    )


class ListResourcesRequestSchema(PaginatedRequestQuerySchema):
    uuids = fields.String(context="query", description="comma separated list of uuid")
    tags = fields.String(context="query", description="comma separated list of tags")
    type = fields.String(context="query", description="resource type complete syntax or %partial type%")
    objid = fields.String(context="query", description="resource objid")
    name = fields.String(context="query", description="resource name")
    desc = fields.String(context="query", description="resource description")
    ext_id = fields.String(context="query", description="resource remote physical id")
    ext_ids = fields.String(context="query", description="list of resource remote physical ids")
    container = fields.String(context="query", description="resource container id, uuid or name")
    attribute = fields.String(context="query", description="resource attribute")
    parent = fields.String(context="query", description="resource parent")
    parent_list = fields.String(context="query", description="resource parent list")
    state = fields.String(
        context="query",
        description="resource state like PENDING, BUILDING, ACTIVE, UPDATING, "
        "ERROR, DELETING, DELETED, EXPUNGING, EXPUNGED, UNKNOWN, "
        "DISABLED",
    )
    active = fields.Boolean(
        context="query",
        required=False,
        example=True,
        description="True if resource is active",
    )
    show_expired = fields.Boolean(
        context="query",
        required=False,
        example=True,
        missing=False,
        description="If True show expired resources",
    )


class ListResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListResources(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListResourcesResponseSchema": ListResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListResourcesRequestSchema)
    parameters_schema = ListResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListResourcesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        data["parents"] = {}
        data["run_customize"] = False

        from beehive_resource.controller import ResourceController

        resourceController: ResourceController = controller
        resources, total = resourceController.get_resources(**data)
        res = [r.info() for r in resources]
        return self.format_paginated_response(res, "resources", total, **data)


class ListResourceTypesRequestSchema(Schema):
    id = fields.Integer(default=23, context="query")
    type = fields.String(default="resource", context="query")


class ListResourceTypesParamsResponseSchema(Schema):
    id = fields.Integer(required=True, default=23)
    type = fields.String(required=True, default="resource")
    resclass = fields.String(required=True, default="")


class ListResourceTypesResponseSchema(Schema):
    resourcetypes = fields.Nested(ListResourceTypesParamsResponseSchema, many=True, required=True, allow_none=True)
    count = fields.Integer(required=True, default=1)


class ListResourceTypes(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListResourceTypesResponseSchema": ListResourceTypesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListResourceTypesRequestSchema)
    parameters_schema = ListResourceTypesRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListResourceTypesResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        res = controller.get_resource_types(oid=data.get("id", None), rfilter=data.get("type", None))
        resp = {"resourcetypes": res, "count": len(res)}
        return resp


class CountResources(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjecCountResponseSchema": ApiObjecCountResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjecCountResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        resp = controller.count_all_resources()
        return {"count": int(resp)}


class GetResourceResponseSchema(Schema):
    resource = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetResource(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetResourceResponseSchema": GetResourceResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        return {"resource": resource.detail()}


class CheckResourcesRequestSchema(PaginatedRequestQuerySchema):
    uuids = fields.String(context="query", description="comma separated list of uuid")
    tags = fields.String(context="query", description="comma separated list of tags")
    type = fields.String(context="query", description="resource type complete syntax or %partial type%")
    objid = fields.String(context="query", description="resource objid")
    name = fields.String(context="query", description="resource name")
    ext_id = fields.String(context="query", description="resource remote physical id")
    ext_ids = fields.String(context="query", description="list of resource remote physical ids")
    container = fields.String(context="query", description="resource container id, uuid or name")
    attribute = fields.String(context="query", description="resource attribute")
    parent = fields.String(context="query", description="resource parent")
    parent_list = fields.String(context="query", description="resource parent list")
    state = fields.String(
        context="query",
        description="resource state like PENDING, BUILDING, ACTIVE, UPDATING, "
        "ERROR, DELETING, DELETED, EXPUNGING, EXPUNGED, UNKNOWN, "
        "DISABLED",
    )
    active = fields.Boolean(
        context="query",
        required=False,
        example=True,
        description="True if resource is active",
    )


class CheckResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class CheckResources(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "CheckResourcesResponseSchema": CheckResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CheckResourcesRequestSchema)
    parameters_schema = CheckResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckResourcesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
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
        self.logger.warn(3)
        return self.format_paginated_response(res, "resources", total, **data)


class CheckResourceRequestSchema(GetApiObjectRequestSchema):
    pass


class CheckResourceResponseSchema(PaginatedResponseSchema):
    resource = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class CheckResource(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "CheckResourceResponseSchema": CheckResourceResponseSchema,
        "CheckResourceRequestSchema": CheckResourceRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(CheckResourceRequestSchema)
    parameters_schema = CheckResourceRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckResourcesResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
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

    def get(self, controller, data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        res, total = resource.authorization(**data)
        return self.format_paginated_response(res, "perms", total, **data)


# class GetResourceJobParamsResponseSchema(Schema):
#     job = fields.String(required=True, default='4cdf0ea4-159a-45aa-96f2-708e461130e1')
#     name = fields.String(required=True, default='test_job')
#     params = fields.Dict(required=True, default={})
#     timestamp = fields.DateTime(required=True, default='1990-12-31T23:59:59Z')
#
#
# class GetResourceJobResponseSchema(Schema):
#     resourcejobs = fields.Nested(GetResourceJobParamsResponseSchema, required=True, many=True, allow_none=True)
#     count = fields.Integer(required=True, default=0)
#
#
# class GetResourceJobs(ResourceApiView):
#     tags = ['resource']
#     definitions = {
#         'GetApiObjectRequestSchema': GetApiObjectRequestSchema,
#         'GetResourceJobResponseSchema': GetResourceJobResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': GetResourceJobResponseSchema
#         }
#     })
#
#     def get(self, controller, data, oid, *args, **kwargs):
#         resource = controller.get_simple_resource(oid)
#         res, total = resource.get_jobs()
#         resp = {'resourcejobs': res,
#                 'count': total}
#         return resp


class GetResourceErrorsParamsResponseSchema(Schema):
    # job = fields.String(required=True, default='4cdf0ea4-159a-45aa-96f2-708e461130e1')
    # timestamp = fields.DateTime(required=True, default='1990-12-31T23:59:59Z')
    error = fields.String(required=True, default="some error")


class GetResourceErrorsResponseSchema(Schema):
    resource_errors = fields.Nested(GetResourceErrorsParamsResponseSchema, required=True, many=True, allow_none=True)
    count = fields.Integer(required=True, default=0)


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

    def get(self, controller, data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        res = resource.get_errors()
        resp = {"resource_errors": res, "count": len(res)}
        return resp


class GetResourceTreeParamsRequestSchema(Schema):
    parent = fields.Boolean(required=False, default=True)
    link = fields.Boolean(required=False, default=True)


class GetResourceTreeRequestSchema(GetApiObjectRequestSchema, GetResourceTreeParamsRequestSchema):
    pass


class GetResourceTreeResponseSchema(Schema):
    resourcetree = fields.Dict(required=True)


class GetResourceTree(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetResourceTreeParamsRequestSchema": GetResourceTreeParamsRequestSchema,
        "GetResourceTreeResponseSchema": GetResourceTreeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetResourceTreeRequestSchema)
    parameters_schema = GetResourceTreeRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceTreeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
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
    oid = fields.String(required=True, description="id, uuid", context="path")


class GetLinkedResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class GetLinkedResources(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetLinkedResourcesResponseSchema": GetLinkedResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetLinkedResourcesRequestSchema)
    parameters_schema = GetLinkedResourcesRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetLinkedResourcesResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        data["parents"] = {}
        data.pop("oid")
        resources, total = resource.get_linked_resources(**data)
        res = [r.info() for r in resources]
        return self.format_paginated_response(res, "resources", total, **data)


class CreateResourceParamRequestSchema(Schema):
    name = fields.String(required=True, default="test")
    desc = fields.String(required=False, default="test")
    ext_id = fields.String(default="", allow_none=True)
    attribute = fields.Dict(default={}, allow_none=True)
    parent = fields.String(default="", allow_none=True)
    container = fields.String(required=True, default="10")
    resclass = fields.String(required=True, default="Openstack.Domain")
    tags = fields.String(default="", allow_none=True)
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


class CreateResourceRequestSchema(Schema):
    resource = fields.Nested(CreateResourceParamRequestSchema)


class CreateResourceBodyRequestSchema(Schema):
    body = fields.Nested(CreateResourceRequestSchema, context="body")


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

    def post(self, controller, data, *args, **kwargs):
        resp = self.create_resource(controller, data, check_name=True)
        return resp


class ImportResourceParamRequestSchema(Schema):
    name = fields.String(required=True, default="test")
    desc = fields.String(required=True, default="test")
    ext_id = fields.String(missing=None, default="", description="Physical resource id")
    attribute = fields.Dict(default={}, allow_none=True)
    parent = fields.String(default="")
    container = fields.String(required=True, default="10")
    resclass = fields.String(required=True, default="Openstack.Domain")
    tags = fields.String(default="")
    configs = fields.Dict(missing={}, default={}, description="Custom configurations")
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


class ImportResourceRequestSchema(Schema):
    resource = fields.Nested(ImportResourceParamRequestSchema)


class ImportResourceBodyRequestSchema(Schema):
    body = fields.Nested(ImportResourceRequestSchema, context="body")


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

    def post(self, controller, data, *args, **kwargs):
        resp = self.import_resource(controller, data, check_name=True)
        return resp


class CloneResourceParamRequestSchema(Schema):
    name = fields.String(required=True, default="test", description="resource name")
    desc = fields.String(required=True, default="test", description="resource description")
    parent = fields.String(required=False, default="123", description="resource parent id")
    container = fields.String(required=False, default="10", description="resource container id")
    configs = fields.Dict(required=False, missing={}, default={}, description="Custom configurations")
    sync = fields.Bool(required=False, missing=False, description="set api execution as sync")
    resource_id = fields.String(required=True, default="", description="id of the resource to clone")


class CloneResourceRequestSchema(Schema):
    resource = fields.Nested(CloneResourceParamRequestSchema)


class CloneResourceBodyRequestSchema(Schema):
    body = fields.Nested(CloneResourceRequestSchema, context="body")


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

    def post(self, controller, data, *args, **kwargs):
        resp = self.clone_resource(controller, data, check_name=True)
        return resp


class UpdateResourceParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    ext_id = fields.String(default="345t6", allow_none=True)
    active = fields.Boolean(default=True)
    attribute = fields.Dict(default={})
    # parent_id = fields.String(default='10')
    state = fields.String(default="ACTIVE")
    tags = fields.Nested(UpdateResourceTagDescRequestSchema, allow_none=True)
    force = fields.Boolean(default=False)
    enable_quotas = fields.Boolean(example=True, missing=None, description="enable resource quotas discover")
    disable_quotas = fields.Boolean(example=True, missing=None, description="disable resource quotas discover")
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


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

    def put(self, controller, data, oid, *args, **kwargs):
        resp = self.update_resource(controller, oid, data)
        return resp


class PatchResourceRequestSchema(Schema):
    resource = fields.Dict(description="Custom key value params")


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

    def patch(self, controller, data, oid, *args, **kwargs):
        resp = self.patch_resource(controller, oid, data)
        return resp


class DeleteResourceRequest2Schema(Schema):
    force = fields.Boolean(
        context="query",
        description="if true force delete with all the resource state",
        missing=False,
    )
    deep = fields.Boolean(
        context="query",
        description="if True run deep delete. If False delete only resource",
        missing=True,
    )
    sync = fields.Bool(required=False, missing=False, example="set api execution as sync")


class DeleteResourceRequestSchema(GetApiObjectRequestSchema, DeleteResourceRequest2Schema):
    pass


class DeleteResource(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "DeleteResourceRequestSchema": DeleteResourceRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteResourceRequestSchema)
    parameters_schema = DeleteResourceRequest2Schema
    responses = SwaggerApiView.setResponses(
        {
            200: {"description": "success", "schema": CrudApiObjectResponseSchema},
            202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema},
        }
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        res = self.expunge_resource(controller, oid, **data)
        return res


class MetricParamsResponseSchema(Schema):
    key = fields.String(required=True)
    value = fields.String(required=True)
    unit = fields.String(required=True)
    type = fields.Integer(required=True)


class GetResourceMetricsParamsResponseSchema(Schema):
    metrics = fields.Nested(MetricParamsResponseSchema, required=True, many=True, allow_none=True)
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
    definitions = {
        "GetResourceMetricsResponseSchema": GetResourceMetricsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceMetricsResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get resource metrics
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
    config = fields.Dict(equired=True)


class GetResourceConfig(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetResourceConfigResponseSchema": GetResourceConfigResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceConfigResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        return {"config": resource.get_attribs()}


class UpdateResourceConfigParamRequestSchema(Schema):
    key = fields.String(default="test", required=True)
    value = fields.String(default="test", required=False, missing=None)


class UpdateResourceConfigRequestSchema(Schema):
    config = fields.Nested(
        UpdateResourceConfigParamRequestSchema,
        required=True,
        many=False,
        allow_none=True,
    )


class UpdateResourceConfigBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateResourceConfigRequestSchema, context="body")


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

    def put(self, controller, data, oid, *args, **kwargs):
        resource = controller.get_simple_resource(oid)
        if data.get("config").get("value") is None:
            resource.unset_configs(key=data.get("config").get("key"))
        else:
            resource.set_configs(**data.get("config"))
        return True


class UpdateResourceStateRequestSchema(Schema):
    state = fields.String(
        required=True,
        description="Resource state to set",
        validate=OneOf(["ACTIVE", "ERROR", "DISABLED"]),
    )


class UpdateResourceStateBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateResourceStateRequestSchema, context="body")


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

    def put(self, controller, data, oid, *args, **kwargs):
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

    def get(self, controller, data, oid, *args, **kwargs):
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

    def put(self, controller, data, oid, *args, **kwargs):
        from beehive_resource.container import Resource

        resource: Resource = controller.get_simple_resource(oid)
        resource.clean_cache()
        return {"uuid": resource.uuid}


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
        ]
        kwargs["version"] = "v2.0"
        ApiView.register_api(module, rules, **kwargs)
