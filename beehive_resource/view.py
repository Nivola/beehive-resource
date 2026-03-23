# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte
from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Union
from flasgger import fields, Schema
from marshmallow.validate import OneOf, Range
from beecell.types.type_string import str2bool
from beecell.swagger import SwaggerHelper
from beehive_resource.container import Resource, ResourceLink
from beehive_resource.controller import ResourceController
from beehive_resource.container import Orchestrator
from beehive.common.apimanager import (
    ApiView,
    ApiManagerError,
    PaginatedRequestQuerySchema,
    SwaggerApiView,
    PaginatedResponseSchema,
    ApiObjectResponseSchema,
    ApiObjectPermsResponseSchema,
    ApiObjecCountResponseSchema,
    ApiObjectSmallResponseSchema,
    CrudApiObjectTaskResponseSchema,
    CrudApiObjectResponseSchema,
    GetApiObjectRequestSchema,
    ApiObjectPermsRequestSchema,
    CrudApiJobResponseSchema,
    CrudApiObjectSimpleResponseSchema,
)
from beehive_resource.container import Resource

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController
    from beehive_resource.container import ResourceContainer


class ResourceApiView(SwaggerApiView):
    resclass = Resource
    parentclass = None
    containerclass = None

    def get_container(
        self,
        controller: ResourceController,
        oid,
        connect=True,
        cache=True,
        *args,
        **kvargs,
    ) -> "ResourceContainer":
        """
        Get container.
        """
        container = controller.get_container(oid, connect=False, cache=cache)
        if self.containerclass is not None and container.objdef != self.containerclass.objdef:
            raise ApiManagerError(
                f"Container {oid} is not of type {self.containerclass.objdef}",
                code=400,
            )
        if connect is True:
            container.get_connection(*args, **kvargs)
        return container

    def get_resource_reference(
        self, controller: ResourceController, oid, container=None, run_customize=True, cache=None
    ):
        """
        Get resource reference.
        """
        filter_d = {}
        if container is not None:
            filter_d["container_id"] = container
        if cache is not None:
            filter_d["cache"] = cache

        # TODO fix. pass run_customize down to get_resource and check calls using run_customize=False keep working
        obj = controller.get_resource(oid, entity_class=self.resclass, **filter_d)
        return obj

    def get_resource(self, controller: ResourceController, oid):
        """
        Get Resource.
        """
        res = controller.get_resource(oid, entity_class=self.resclass)
        resp = {self.resclass.objname: res.detail()}
        return resp

    def get_resources_reference(self, controller: ResourceController, *args, **kvargs):
        """
        Get resources reference.
        """
        parents = None
        kvargs["parents"] = parents
        res, total = controller.get_resources(objdef=self.resclass.objdef, type=self.resclass.objdef, *args, **kvargs)
        return res, total

    def get_resources(self, controller: ResourceController, *args, **kvargs):
        """
        Get resources.
        """
        tags = kvargs.pop("tags", None)
        kvargs["resourcetags"] = tags
        kvargs["parents"] = None
        kvargs["filter_expired"] = False

        res, total = controller.get_resources(objdef=self.resclass.objdef, type=self.resclass.objdef, *args, **kvargs)
        resp = [r.info() for r in res]
        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **kvargs)

    def get_linked_resources(self, controller: ResourceController, oid, resource_class, link, *args, **kvargs):
        """
        Get linked resources.
        """
        parent = controller.get_resource(oid, entity_class=resource_class)
        data, total = parent.get_linked_resources(link_type=link, *args, **kvargs)
        resp = [d.info() for d in data]
        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **kvargs)

    def get_directed_linked_resources(
        self,
        controller: ResourceController,
        oids,
        resource_class,
        link,
        *args,
        **kvargs,
    ):
        """
        Get directed linked resources.
        """
        # resources = []
        res, _ = controller.get_resources(uuids=oids, objdef=resource_class.objdef)
        resources = [r.oid for r in res]
        kvargs["parents"] = None
        data, total = controller.get_directed_linked_resources(link_type=link, resources=resources, *args, **kvargs)
        resp = [d.info() for d in data]
        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **kvargs)

    def get_resources_by_parent(self, controller: ResourceController, parent_id, *args, **kvargs):
        """
        Get resources by parent.
        """
        kvargs["parents"] = None
        kvargs["parent"] = parent_id
        res, total = controller.get_resources(objdef=self.resclass.objdef, type=self.resclass.objdef, *args, **kvargs)
        resp = [r.info() for r in res]
        return self.format_paginated_response(resp, self.resclass.objname + "s", total, **kvargs)

    def create_resource(self, controller: ResourceController, data: dict, check_name=True):
        """
        Create resource.
        """
        objname = self.resclass.objname
        data = data.get(objname, {})
        # check if already exists
        cid = data.pop("container", None)
        container = self.get_container(controller, cid)

        if check_name:
            data_name = data.get("name")
            try:
                obj = self.get_resource_reference(controller, data_name, container=container.oid)
            except Exception:
                obj = None

            if obj is not None:
                raise ApiManagerError(
                    f"{objname} {data_name} already exists",
                    code=409,
                )

        if self.parentclass is not None:
            parent_id = data.pop(self.parentclass.objname, None)
            if parent_id is not None:
                self.logger.debug("Parent id: %s", parent_id)
                parent = controller.get_simple_resource(parent_id, entity_class=self.parentclass)
                data["parent"] = parent.oid
            else:
                self.logger.warning("Parent id was not specified")
                data["parent"] = None

        res = container.resource_factory(self.resclass, **data)
        return res

    def clone_resource(self, controller: ResourceController, oid, data):
        """
        Clone Resource.
        """
        objname = self.resclass.objname
        data = data.get(objname, {})
        # check if already exists
        cid = data.pop("container", None)
        container = self.get_container(controller, cid)

        clone_resource = controller.get_resource(oid, entity_class=self.resclass)
        data["clone_resource"] = clone_resource.oid
        data_name = data.get("name")

        try:
            obj = self.get_resource_reference(controller, data.get("name"), container=container.oid)
        except Exception:
            obj = None

        if obj is not None:
            raise ApiManagerError(
                f"{objname} {data_name} already exists",
                code=409,
            )

        if self.parentclass is not None:
            parent_id = data.pop(self.parentclass.objname, None)
            if parent_id is not None:
                self.logger.debug("Parent id: %s", parent_id)
                parent = controller.get_simple_resource(parent_id, entity_class=self.parentclass)
                data["parent"] = parent.oid
            else:
                self.logger.warning("Parent id was not specified")
                data["parent"] = None

        res = container.resource_clone_factory(self.resclass, **data)
        return res

    def import_resource(self, controller: ResourceController, data, check_name=True):
        """
        Import Resource.
        """
        objname = self.resclass.objname
        data = data.get(objname, {})
        data_name = data.get("name")
        # check if already exists
        cid = data.pop("container", None)
        container = self.get_container(controller, cid)

        if check_name:
            try:
                obj = self.get_resource_reference(controller, data_name, container=container.oid)
            except Exception:
                obj = None

            if obj is not None:
                raise ApiManagerError(
                    f"{objname} {data_name} already exists",
                    code=409,
                )

        if self.parentclass is not None:
            parent_id = data.pop(self.parentclass.objname, None)
            if parent_id is not None:
                self.logger.debug("Parent id: %s", parent_id)
                parent = controller.get_resource(parent_id, entity_class=self.parentclass)
                data["parent"] = parent.oid
            else:
                self.logger.warning("Parent id was not specified")
                data["parent"] = None

        res = container.resource_import_factory(self.resclass, **data)
        return res

    def update_resource(self, controller: ResourceController, oid, data):
        """
        Update resource.
        """
        data = data.get(self.resclass.objname)
        obj: "Resource" = controller.get_resource(oid, entity_class=self.resclass)
        res = obj.update(**data)
        return res

    def delete_resource(self, controller: ResourceController, oid):
        """
        Delete resource.
        """
        obj: "Resource" = controller.get_resource(oid, entity_class=self.resclass)
        if obj.get_base_state() not in ["ACTIVE", "ERROR", "UNKNOWN"]:
            objname = self.resclass.objname
            raise ApiManagerError(
                f"Resource {objname} {oid} is not in a valid state",
                code=400,
            )
        res = obj.delete()
        return res

    def expunge_resource(self, controller: ResourceController, oid, **kvargs):
        """
        Expunge resource.
        """
        obj: "Resource" = controller.get_resource(oid, entity_class=self.resclass)
        if obj.get_base_state() not in ["ACTIVE", "ERROR", "UNKNOWN"]:
            objname = self.resclass.objname
            raise ApiManagerError(
                f"Resource {objname} {oid} is not in a valid state",
                code=400,
            )
        res = obj.expunge(**kvargs)
        return res

    def expunge_resource2(self, controller: ResourceController, oid, **kvargs):
        """
        Expinge resource2.
        """
        obj: "Resource" = controller.get_resource(oid, entity_class=self.resclass)
        res = obj.expunge2(**kvargs)
        return res


class UpdateResourceTagDescRequestSchema(Schema):
    cmd = fields.String(
        required=True,
        metadata={
            "example": 'add',
        },
    )
    values = fields.List(
        fields.String(example='test'),
        required=True,
    )


class SmallDataResponseSchema(Schema):
    id = fields.Integer(
        required=False,
        metadata={
            "example": 1,
        },
    )
    uuid = fields.UUID(
        required=False,
        allow_none=True,
        metadata={
            "example": '6d960236-d280-46d2-817d-f3ce8f0aeff7',
        },
    )
    name = fields.String(
        required=False,
        dump_default="",
        allow_none=True,
        metadata={
            "example": 'test',
        },
    )


class ResourceSmallResponseSchema(ApiObjectSmallResponseSchema):
    state = fields.String(
        required=True,
        dump_default="ACTIVE",
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
        dump_default="ACTIVE",
        metadata={
            "example": 'ACTIVE',
        },
    )
    child = fields.Integer(
        required=True,
        dump_default=0,
        metadata={
            "example": 0,
        },
    )


class CreateResourceBaseRequestSchema(Schema):
    """
    :name: resource name
    :container: container id,uuid or name
    :tags: comma separated list of tags to assign
    """

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


#
# resource
#
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
    definitions = {
        "ListResourcesResponseSchema": ListResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListResourcesRequestSchema)
    parameters_schema = ListResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListResourcesResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        data["parents"] = {}
        data["run_customize"] = False
        resources, total = controller.get_resources(**data)
        res = [r.info() for r in resources]
        return self.format_paginated_response(res, "resources", total, **data)


class ListSimpleResourcesRequestSchema(ListResourcesRequestSchema):
    sg_info = fields.Boolean(
        context="query",
        required=False,
    )
    flavor_info = fields.Boolean(
        context="query",
        required=False,
    )


class ListSimpleResourcesResponseSchema(PaginatedResponseSchema):
    resources = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListSimpleResources(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListSimpleResourcesResponseSchema": ListSimpleResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListSimpleResourcesRequestSchema)
    parameters_schema = ListSimpleResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListSimpleResourcesResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        data_info = {}
        sg_info = data.pop("sg_info", False)
        data_info["sg_info"] = sg_info
        flavor_info = data.pop("flavor_info", False)
        data_info["flavor_info"] = flavor_info

        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        data["parents"] = {}
        data["run_customize"] = False
        resources, total = controller.get_resources(**data)

        # res = [r.info() for r in resources]
        res = []
        for resource in resources:
            from beehive_resource.plugins.provider.entity.instance import ComputeInstance
            from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2
            from beehive_resource.plugins.provider.entity.stack import ComputeStack

            resource: Resource = resource

            # self.logger.debug(f"fv - get - type(resource) {type(resource)}")
            if type(resource) == ComputeStackV2:
                # self.logger.debug(f"fv - get - resource.get_stack_type() {resource.get_stack_type()}")
                if resource.get_stack_type() == "sql_stack":
                    from beehive_resource.plugins.provider.entity.sql_stack_v2.sqlcomputestackv2 import SqlComputeStackV2
                    sqlComputeStackV2 = SqlComputeStackV2(
                        controller,
                        oid=resource.oid,
                        objid=resource.objid,
                        name=resource.name,
                        active=resource.active,
                        desc=resource.desc,
                        model=resource.model,
                    )
                    info = sqlComputeStackV2.simple_info(data_info)

            elif type(resource) == ComputeStack:
                # self.logger.debug(f"fv - get - resource.get_stack_type() {resource.get_stack_type()}")
                if resource.get_stack_type() == "sql_stack":
                    from beehive_resource.plugins.provider.entity.sql_stack import SqlComputeStack
                    sqlComputeStack = SqlComputeStack(
                        controller,
                        oid=resource.oid,
                        objid=resource.objid,
                        name=resource.name,
                        active=resource.active,
                        desc=resource.desc,
                        model=resource.model,
                    )
                    info = sqlComputeStack.simple_info(data_info)
            else:
                info = resource.simple_info(data_info)
            res.append(info)
        
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
        dump_default="",
    )


class ListResourceTypesResponseSchema(Schema):
    resourcetypes = fields.Nested(
        ListResourceTypesParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )
    count = fields.Integer(
        required=True,
        metadata={
            "example": 1,
        },
    )


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

    def get(self, controller: ResourceController, data, *args, **kwargs):
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

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
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
    definitions = {
        "GetResourceResponseSchema": GetResourceResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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
    definitions = {
        "CheckResourcesResponseSchema": CheckResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CheckResourcesRequestSchema)
    parameters_schema = CheckResourcesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckResourcesResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
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
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckResourceResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
        res, total = resource.authorization(**data)
        return self.format_paginated_response(res, "perms", total, **data)


class GetResourceJobParamsResponseSchema(Schema):
    job = fields.String(
        required=True,
        metadata={"example": "4cdf0ea4-159a-45aa-96f2-708e461130e1"},
    )
    name = fields.String(
        required=True,
        metadata={"example": 'test_job'},
    )
    params = fields.Dict(
        required=True,
        dump_default={},
    )
    timestamp = fields.DateTime(
        required=True,
        dump_default=datetime(1990, 12, 31, 23, 59, 59),
    )


class GetResourceJobResponseSchema(Schema):
    resourcejobs = fields.Nested(
        GetResourceJobParamsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )
    count = fields.Integer(
        required=True,
        dump_default=0,
    )


class GetResourceJobs(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
        "GetResourceJobResponseSchema": GetResourceJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceJobResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
        res, total = controller.get_jobs(resource=resource)
        resp = {"resourcejobs": res, "count": total}
        return resp


class GetResourceErrorsParamsResponseSchema(Schema):
    # job = fields.String(required=True, dump_default='4cdf0ea4-159a-45aa-96f2-708e461130e1')
    # timestamp = fields.DateTime(required=True, dump_default='1990-12-31T23:59:59Z')
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
        "GetResourceJobResponseSchema": GetResourceJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceJobResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
        res = resource.get_errors()
        resp = {"resource_errors": res, "count": len(res)}
        return resp

class GetResourceTreeRequestSchema(GetApiObjectRequestSchema):
    parent = fields.Boolean(
        required=False,
        context="query",
        load_default=True,
    ) # this parameter is unused
    link = fields.Boolean(
        required=False,
        context="query",
        load_default=True,
    )


class GetResourceTreeResponseSchema(Schema):
    resourcetree = fields.Dict(
        required=True,
    )


class GetResourceTree(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetResourceTreeRequestSchema": GetResourceTreeRequestSchema,
        "GetResourceTreeResponseSchema": GetResourceTreeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetResourceTreeRequestSchema)
    parameters_schema = GetResourceTreeRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetResourceTreeResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_resource(oid)
        data.pop("oid")
        #raise Exception("%s" % data)
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
    definitions = {
        "GetLinkedResourcesResponseSchema": GetLinkedResourcesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetLinkedResourcesRequestSchema)
    parameters_schema = GetLinkedResourcesRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetLinkedResourcesResponseSchema}}
    )

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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
            "example": 10,
        },
    )
    resclass = fields.String(
        required=True,
        metadata={
            "example": 'Openstack.Domain',
        },
    )
    tags = fields.String(
        allow_none=True,
    )


class CreateResourceRequestSchema(Schema):
    resource = fields.Nested(
        CreateResourceParamRequestSchema,
    )


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

    def post(self, controller: ResourceController, data, *args, **kwargs):
        data = data.get("resource")
        cid = data.pop("container")
        container = self.get_container(controller, cid)
        resclass = data.pop("resclass")
        resp = container.resource_factory(resclass, **data)
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
    )
    attribute = fields.Dict(
        allow_none=True,
    )
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

    physical_id = fields.String(
        load_default=None,
        metadata={
            "description": 'Physical resource id',
        },
    )
    configs = fields.Dict(
        load_default={},
        metadata={
            "description": 'Custom configurations',
        },
    )


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

    def post(self, controller: ResourceController, data, *args, **kwargs):
        data = data.get("resource")
        cid = data.pop("container")
        container = self.get_container(controller, cid)
        resclass = data.pop("resclass")
        resp = container.resource_import_factory(resclass, **data)
        return resp


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

    # parent_id = fields.String(dump_default='10')
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
        load_default=False,
    ) # TODO check
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


class UpdateResourceRequestSchema(Schema):
    resource = fields.Nested(UpdateResourceParamRequestSchema)


class UpdateResourceBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        UpdateResourceRequestSchema,
        context="body",
    )


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

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_resource(oid, cache=False)
        data = data.get("resource")

        # update tags
        tags = data.pop("tags", None)
        if tags is not None:
            cmd = tags.get("cmd")
            values = tags.get("values")
            # add tag
            if cmd == "add":
                for value in values:
                    resource.add_tag(value)
            elif cmd == "remove":
                for value in values:
                    resource.remove_tag(value)

        # update quotas get status
        if data.pop("enable_quotas", True) is True:
            resource.enable_quotas()
        elif data.pop("disable_quotas", True) is True:
            resource.disable_quotas()

        # update resource
        resp = resource.update(**data)
        return resp


class PatchResourceRequestSchema(Schema):
    resource = fields.Dict(
        metadata={
            "description": 'Custom key value params',
        },
    )


class PatchResourceBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        PatchResourceRequestSchema,
        context="body",
    )


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

    def patch(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_resource(oid)
        data = data.get("resource")
        resp = resource.patch(**data)
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

    def delete(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_resource(oid)
        if str2bool(data.get("deep")) is False:
            resp = resource.expunge_internal()
            return resp
        elif str2bool(data.get("force")) is True or resource.get_base_state() in [
            "ACTIVE",
            "ERROR",
            "UNKNOWN",
            "EXPUNGING",
        ]:
            resp = resource.expunge()
            return resp
        raise ApiManagerError(f"Resource {oid} is not in a valid state", code=400)


class MetricParamsResponseSchema(Schema):
    key = fields.String(
        required=True,
    )
    value = fields.String(
        required=True,
    )
    unit = fields.String(
        required=True,
    )
    type = fields.Integer(
        required=True,
    )


class GetResourceMetricsParamsResponseSchema(Schema):
    metrics = fields.Nested(
        MetricParamsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )
    id = fields.String(
        required=True,
    )
    uuid = fields.String(
        required=True,
    )
    type = fields.String(
        required=True,
    )
    extraction_date = fields.DateTime(
        required=True,
    )
    resource_uuid = fields.String(
        required=True,
    )


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

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
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
        res: "Resource" = controller.get_resource(oid)
        resource_metrics = res.get_metrics()
        return {"resource": resource_metrics}


class GetResourceConfigResponseSchema(Schema):
    config = fields.Dict(required=True)


class GetResourceConfig(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetResourceConfigResponseSchema": GetResourceConfigResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetResourceConfigResponseSchema}}
    )

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
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

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        resource: "Resource" = controller.get_simple_resource(oid)
        resource.clean_cache()
        return {"uuid": resource.uuid}


#
# container
#
class ListContainersRequestSchema(PaginatedRequestQuerySchema):
    tags = fields.String(
        context="query",
    )
    container_type = fields.String(
        context="query",
        metadata={
            "example": 'provider',
        },
    )
    container_type_name = fields.String(
        context="query",
        required=False,
        metadata={
            "example": 'Zabbix',
            "description": 'container type name',
        },
    )
    name = fields.String(
        context="query",
        required=False,
        metadata={
            "example": 'Podto1Elk',
            "description": 'container name',
        },
    )


class ListContainersParamsResponseSchema(ApiObjectResponseSchema):
    category = fields.String(
        required=True,
        metadata={
            "example": 'provider',
        },
    )
    state = fields.String(
        required=True,
        metadata={
            "example": 'ACTIVE',
        },
    )
    conn = fields.Dict(
        required=True,
        dump_default={},
    )


class ListContainersResponseSchema(PaginatedResponseSchema):
    resourcecontainers = fields.Nested(
        ListContainersParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListContainers(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListContainersResponseSchema": ListContainersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListContainersRequestSchema)
    parameters_schema = ListContainersRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListContainersResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        containers, total = controller.get_containers(**data)
        res = [r.info() for r in containers]
        return self.format_paginated_response(res, "resourcecontainers", total, **data)


class CountContainers(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjecCountResponseSchema": ApiObjecCountResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjecCountResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resp = controller.count_all_containers()
        return {"count": int(resp)}


class ListContainerTypesParamsResponseSchema(Schema):
    category = fields.String(
        required=True,
        metadata={
            "example": 'Openstack',
        },
    )
    type = fields.String(
        required=True,
        metadata={
            "example": 'orchestrator',
        },
    )
    id = fields.Integer(
        required=True,
        metadata={
            "example": 1,
        },
    )


class ListContainerTypesResponseSchema(Schema):
    resourcecontainertypes = fields.Nested(
        ListContainerTypesParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )
    count = fields.Integer(
        required=True,
        metadata={
            "example": 1,
        },
    )


class ListContainerTypes(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListContainerTypesResponseSchema": ListContainerTypesResponseSchema,
    }
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListContainerTypesResponseSchema}}
    )

    def get(self, controller: ResourceController, data, *args, **kwargs):
        res = controller.get_container_types()
        resp = {"resourcecontainertypes": res, "count": len(res)}
        return resp


class GetContainerParamsResponseSchema(ApiObjectResponseSchema):
    category = fields.String(
        required=True,
        metadata={
            "example": 'provider',
        },
    )
    state = fields.String(
        required=True,
        metadata={
            "example": 'ACTIVE',
        },
    )
    conn = fields.Dict(
        required=True,
        dump_default={},
    )
    resources = fields.Integer(
        required=True,
        metadata={
            "example": 10,
        },
    )


class GetContainerResponseSchema(Schema):
    resourcecontainer = fields.Nested(
        GetContainerParamsResponseSchema,
        required=True,
        allow_none=True,
    )


class GetContainer(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetContainerResponseSchema": GetContainerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetContainerResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid, cache=False)
        return {"resourcecontainer": container.detail()}


class GetContainerPerms(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjectPermsRequestSchema": ApiObjectPermsRequestSchema,
        "ApiObjectPermsResponseSchema": ApiObjectPermsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ApiObjectPermsRequestSchema)
    parameters_schema = PaginatedRequestQuerySchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjectPermsResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        res, total = container.authorization(**data)
        return self.format_paginated_response(res, "perms", total, **data)


class PingContainerResponseSchema(Schema):
    uuid = fields.UUID(
        required=True,
        metadata={
            "example": '6d960236-d280-46d2-817d-f3ce8f0aeff7',
        },
    )
    ping = fields.Boolean(
        required=True,
        metadata={
            "example": True,
        },
    )


class PingContainer(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "PingContainerResponseSchema": PingContainerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": PingContainerResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid, connect=False)
        return {"uuid": container.uuid, "ping": container.ping()}


"""
class GetContainerResourcesCount(ResourceApiView):
    def dispatch(self, controller, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        resp = container.count_all_resources()
        return resp"""

"""
class GetContainerRoles(ResourceApiView):
    def dispatch(self, controller, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        res = container.get_roles()
        resp = {'roles':res,
                'count':len(res)}
        return resp  """


class CreateContainerParamRequestSchema(Schema):
    type = fields.String(
        required=True,
        metadata={
            "example": 'Provider',
        },
    )
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
    conn = fields.Dict(
        required=True,
    )


class CreateContainerRequestSchema(Schema):
    resourcecontainer = fields.Nested(
        CreateContainerParamRequestSchema,
    )


class CreateContainerBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateContainerRequestSchema,
        context="body",
    )


class CreateContainer(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "CreateContainerRequestSchema": CreateContainerRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateContainerBodyRequestSchema)
    parameters_schema = CreateContainerRequestSchema
    responses = SwaggerApiView.setResponses({201: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller: ResourceController, data, *args, **kwargs):
        resp = controller.add_container(**data.get("resourcecontainer"))
        return ({"uuid": resp}, 201)


class UpdateContainerParamRequestSchema(Schema):
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
    active = fields.Boolean(
        metadata={
            "example": True,
        },
    )
    conn = fields.Dict()
    state = fields.Integer(
        metadata={
            "example": 0,
        },
    )
    tags = fields.Nested(
        UpdateResourceTagDescRequestSchema,
        allow_none=True,
    )


class UpdateContainerRequestSchema(Schema):
    resourcecontainer = fields.Nested(
        UpdateContainerParamRequestSchema,
    )


class UpdateContainerBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        UpdateContainerRequestSchema,
        context="body",
    )


class UpdateContainer(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "UpdateContainerRequestSchema": UpdateContainerRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateContainerBodyRequestSchema)
    parameters_schema = UpdateContainerRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        data = data.get("resourcecontainer")
        tags = data.pop("tags", None)
        resp = container.update(**data)
        if tags is not None:
            cmd = tags.get("cmd")
            values = tags.get("values")
            # add tag
            if cmd == "add":
                for value in values:
                    container.add_tag(value)
            elif cmd == "remove":
                for value in values:
                    container.remove_tag(value)
        return {"uuid": resp}


class DeleteContainerRequestSchema(Schema):
    force = fields.Boolean(
        context="query",
        metadata={
            "description": 'If True force removal',
        },
    )


class DeleteContainer2RequestSchema(GetApiObjectRequestSchema, DeleteContainerRequestSchema):
    pass


class DeleteContainer(ResourceApiView):
    tags = ["resource"]
    definitions = {}
    parameters = SwaggerHelper().get_parameters(DeleteContainer2RequestSchema)
    parameters_schema = DeleteContainerRequestSchema
    responses = SwaggerApiView.setResponses({204: {"description": "no response"}})

    def delete(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid, connect=False)
        resp = container.expunge(**data)
        return resp, 204


class GetContainerJobRequestSchema(GetApiObjectRequestSchema):
    jobstatus = fields.String(
        required=False,
        context="query",
        metadata={
            "example": 'SUCCESS',
        },
    )


class GetContainerJobParamsResponseSchema(Schema):
    job = fields.String(
        required=True,
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
        },
    )
    name = fields.String(
        required=True,
        metadata={
            "example": 'test_job',
        },
    )
    params = fields.Dict(
        required=True,
        dump_default={},
    )
    timestamp = fields.DateTime(
        required=True,
        dump_default=datetime(1990, 12, 31, 23, 59, 59),
    )
    status = fields.String(
        required=True,
        metadata={
            "example": 'SUCCESS',
        },
    ) # TODO check
    worker = fields.String(
        required=True,
        dump_default="",
    )
    children = fields.Integer(
        required=True,
        dump_default=0,
    )
    elapsed = fields.Float(
        required=True,
        dump_default=0.0,
    )


class GetContainerJobResponseSchema(Schema):
    resourcejobs = fields.Nested(
        GetContainerJobParamsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )
    count = fields.Integer(
        required=True,
        dump_default=0,
    )


class GetContainerJobs(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetContainerJobRequestSchema": GetContainerJobRequestSchema,
        "GetContainerJobResponseSchema": GetContainerJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetContainerJobRequestSchema)
    parameters_schema = GetContainerJobRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetContainerJobResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid, connect=False)
        res, total = container.get_jobs(**data)
        resp = {"containerjobs": res, "count": total}
        return resp


class DiscoverRequestSchema(GetApiObjectRequestSchema):
    type = fields.String(
        required=False,
        context="query",
        metadata={
            "example": 'Dummy.SyncResource',
        },
    )


class DiscoverParamsDetailsResponseSchema(Schema):
    type = fields.String(
        metadata={
            "example": 'beehive_resource.plugins.dummy.controller.DummySyncResource',
        },
    )
    id = fields.String(
        metadata={
            "example": '15',
        },
    )
    parent = fields.String(
        allow_none=True,
        metadata={
            "example": '10',
        },
    )
    type = fields.String(
        metadata={
            "example": 'DummySyncResource',
        },
    )
    name = fields.String(
        metadata={
            "example": 'test',
        },
    )
    # level = fields.Integer(example=0)


class DiscoverParamsResponseSchema(Schema):
    new = fields.Nested(
        DiscoverParamsDetailsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )

    died = fields.Nested(
        DiscoverParamsDetailsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )

    changed = fields.Nested(
        DiscoverParamsDetailsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class DiscoverResponseSchema(Schema):
    discover_resources = fields.Nested(
        DiscoverParamsResponseSchema,
        required=True,
        allow_none=True,
    )


class Discover(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "DiscoverResponseSchema": DiscoverResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DiscoverRequestSchema)
    parameters_schema = DiscoverRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": DiscoverResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        restype = data.get("type")
        if restype is None:
            restypes = container.get_resource_classes()
        else:
            restypes = [restype]
        res = container.discover(restypes)
        resp = {"discover_resources": res}
        return resp


class DiscoverRemoteRequestSchema(GetApiObjectRequestSchema):
    type = fields.String(
        required=False,
        context="query",
        metadata={
            "example": 'Dummy.SyncResource',
        },
    )
    name = fields.String(
        required=False,
        context="query",
        metadata={
            "description": 'optional name or name pattern',
        },
    )


class DiscoverRemote(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "DiscoverResponseSchema": DiscoverResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DiscoverRemoteRequestSchema)
    parameters_schema = DiscoverRemoteRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": DiscoverResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        restype = data.get("type")
        resname = data.get("name")
        if restype is None:
            restypes = container.get_resource_classes()
        else:
            restypes = [restype]
        res = container.discover_remote(restypes, name=resname)
        resp = {"discover_resources": res}
        return resp


## list discover class
class DiscoverTypeResponseSchema(Schema):
    discover_types = fields.List(fields.String)


class DiscoverType(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "DiscoverTypeResponseSchema": DiscoverTypeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": DiscoverTypeResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        """
        Discover resource classes
        """
        container = self.get_container(controller, oid)
        res = container.get_resource_classes()
        # res = ['%s.%s' % (r.__module__, r.__name__) for r in resclasses]
        resp = {"discover_types": res}
        return resp


class SynchronizeResourcesParamRequestSchema(Schema):
    types = fields.String(
        metadata={
            "example": 'test',
        },
    )
    ext_id = fields.String(
        metadata={
            "example": 'test',
            "description": 'id of the physical entity',
        },
    )
    new = fields.Boolean(
        load_default=True,
        metadata={
            "description": 'if True add new physical entity not already in cmp',
        },
    )
    died = fields.Boolean(
        load_default=False,
        metadata={
            "description": 'if True remove not alive physical entity already in cmp',
        },
    )
    changed = fields.Boolean(
        load_default=False,
        metadata={
            "description": 'if True update physical entity in cmp',
        },
    )


class SynchronizeResourcesRequestSchema(Schema):
    synchronize = fields.Nested(
        SynchronizeResourcesParamRequestSchema,
    )


class SynchronizeResourcesBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        SynchronizeResourcesRequestSchema,
        context="body",
    )


class SynchronizeResources(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "SynchronizeResourcesRequestSchema": SynchronizeResourcesRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SynchronizeResourcesBodyRequestSchema)
    parameters_schema = SynchronizeResourcesRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        """
        Synchronize resource by classes
        Synchronize resource by classes
        """
        container = self.get_container(controller, oid)
        job = container.synchronize_resources(data.get("synchronize"))
        return {"taskid": job}, 202


class GetScheduler(ResourceApiView):
    tags = ["resource"]
    definitions = {}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "no response"}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        resp = container.get_discover_scheduler()
        return resp


class CreateSchedulerParamRequestSchema(Schema):
    minutes = fields.Integer(
        metadata={
            "example": 5,
        },
    )


class CreateSchedulerRequestSchema(Schema):
    scheduler = fields.Nested(
        CreateSchedulerParamRequestSchema,
    )


class CreateSchedulerBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        CreateSchedulerRequestSchema,
        context="body",
    )


class CreateScheduler(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "CreateSchedulerRequestSchema": CreateSchedulerRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateSchedulerBodyRequestSchema)
    parameters_schema = CreateSchedulerRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        minutes = data.get("minutes", 5)
        resp = container.add_discover_scheduler(minutes)
        return resp, 201


class RemoveScheduler(ResourceApiView):
    tags = ["resource"]
    definitions = {}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "no response"}})

    def delete(self, controller: ResourceController, data, oid, *args, **kwargs):
        container = self.get_container(controller, oid)
        resp = container.remove_discover_scheduler()
        return resp, 204


#
# link
#
class ListLinksRequestSchema(PaginatedRequestQuerySchema):
    start_resource = fields.String(context="query")
    end_resource = fields.String(context="query")
    resource = fields.String(context="query")
    type = fields.String(context="query")
    tags = fields.String(context="query")

    size = fields.Integer(
        load_default=20,
        context="query",
        validate=Range(min=-1, max=1000, error='Size is out from range'),
        metadata={
            "example": 20,
            "description": 'entities list page size. -1 to get all the records',
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
            "description": 'link name like',
        },
    )


class ListLinksParamsDetailsResponseSchema(Schema):
    type = fields.String(
        required=True,
        metadata={
            "example": 'relation',
        },
    )

    attributes = fields.Dict(
        required=True,
        dump_default={},
    )

    start_resource = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
        allow_none=True,
    )

    end_resource = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
        allow_none=True,
    )


class ListLinksParamsResponseSchema(ApiObjectResponseSchema):
    details = fields.Nested(
        ListLinksParamsDetailsResponseSchema,
        allow_none=True,
    )


class ListLinksResponseSchema(PaginatedResponseSchema):
    resourcelinks = fields.Nested(
        ListLinksParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListLinks(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListLinksResponseSchema": ListLinksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListLinksRequestSchema)
    parameters_schema = ListLinksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListLinksResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        tags = data.pop("tags", None)
        data["resourcetags"] = tags
        links, total = controller.get_links(**data)
        res = [r.info() for r in links]
        return self.format_paginated_response(res, "resourcelinks", total, **data)


class CountLinks(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjecCountResponseSchema": ApiObjecCountResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjecCountResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        resp = controller.count_all_links()
        return {"count": int(resp)}


class GetLinkParamsDetailsResponseSchema(Schema):
    type = fields.String(
        required=True,
        metadata={
            "example": 'relation',
        },
    )

    attributes = fields.Dict(
        required=True,
        dump_default={},
    )

    start_resource = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
        allow_none=True,
    )

    end_resource = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
        allow_none=True,
    )


class GetLinkParamsResponseSchema(ApiObjectResponseSchema):
    details = fields.Nested(
        ListLinksParamsDetailsResponseSchema,
        required=True,
        allow_none=True,
    )


class GetLinkResponseSchema(Schema):
    resourcelink = fields.Nested(
        GetLinkParamsResponseSchema,
        required=True,
        allow_none=True,
    )


class GetLink(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetLinkResponseSchema": GetLinkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetLinkResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        link = controller.get_link(oid)
        return {"resourcelink": link.detail()}


class GetLinkPerms(SwaggerApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjectPermsRequestSchema": ApiObjectPermsRequestSchema,
        "ApiObjectPermsResponseSchema": ApiObjectPermsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ApiObjectPermsRequestSchema)
    parameters_schema = PaginatedRequestQuerySchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjectPermsResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        link = controller.get_link(oid)
        res, total = link.authorization(**data)
        return self.format_paginated_response(res, "perms", total, **data)


class CreateLinkParamRequestSchema(Schema):
    type = fields.String(
        required=True,
        metadata={
            "example": 'relation',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": '1',
        },
    )

    attributes = fields.Dict(
        required=True,
    )

    start_resource = fields.String(
        required=True,
        metadata={
            "example": '2',
        },
    )
    end_resource = fields.String(
        required=True,
        metadata={
            "example": '3',
        },
    )


class CreateLinkRequestSchema(Schema):
    resourcelink = fields.Nested(
        CreateLinkParamRequestSchema,
    )


class CreateLinkBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateLinkRequestSchema,
        context="body",
    )


class CreateLink(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "CreateLinkRequestSchema": CreateLinkRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateLinkBodyRequestSchema)
    parameters_schema = CreateLinkRequestSchema
    responses = SwaggerApiView.setResponses({201: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller: ResourceController, data, *args, **kwargs):
        resp = controller.add_link(**data.get("resourcelink"))
        return {"uuid": resp}, 201


class UpdateLinkParamRequestSchema(Schema):
    type = fields.String(
        metadata={
            "example": 'relation',
        },
    )

    name = fields.String(
        metadata={
            "example": '1',
        },
    )

    attributes = fields.Dict(
        load_default={},
    )
    start_resource = fields.String(
        metadata={
            "example": '2',
        },
    )

    end_resource = fields.String(
        metadata={
            "example": '3',
        },
    )

    tags = fields.Nested(
        UpdateResourceTagDescRequestSchema,
        allow_none=True,
    )


class UpdateLinkRequestSchema(Schema):
    resourcelink = fields.Nested(
        UpdateLinkParamRequestSchema,
    )


class UpdateLinkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        UpdateLinkRequestSchema,
        context="body",
    )


class UpdateLink(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "UpdateLinkRequestSchema": UpdateLinkRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateLinkBodyRequestSchema)
    parameters_schema = UpdateLinkRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        link = controller.get_link(oid)
        data = data.get("resourcelink")
        tags = data.pop("tags", None)
        resp = link.update(**data)
        if tags is not None:
            cmd = tags.get("cmd")
            values = tags.get("values")
            # add tag
            if cmd == "add":
                for value in values:
                    link.add_tag(value)
            elif cmd == "remove":
                for value in values:
                    link.remove_tag(value)
        return {"uuid": resp}


class DeleteLink(ResourceApiView):
    tags = ["resource"]
    definitions = {}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "no response"}})

    def delete(self, controller: ResourceController, data, oid, *args, **kwargs):
        link = controller.get_link(oid)
        resp = link.expunge()
        return resp, 204


class UpdateLinkRegisterRequestSchema(Schema):
    pass


class UpdateLinkRegisterBodyRequestSchema(Schema):
    pass


class UpdateLinkRegisterResponseSchema(Schema):
    pass


class UpdateLinkRegister(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "UpdateLinkRegisterRequestSchema": UpdateLinkRegisterRequestSchema,
        "UpdateLinkRegisterResponseSchema": UpdateLinkRegisterResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateLinkRegisterBodyRequestSchema)
    parameters_schema = UpdateLinkRegisterRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": UpdateLinkRegisterResponseSchema}}
    )

    def put(self, controller: ResourceController, data, oid, *args, **kwargs):
        link: ResourceLink = controller.get_link(oid)
        objids = link.objid.split("//")
        link.register_object_permtags(objids)


#
# tags
#
class ListTagsRequestSchema(PaginatedRequestQuerySchema):
    name = fields.String(
        context="query",
    )
    container = fields.String(
        context="query",
    )
    resource = fields.String(
        context="query",
    )
    link = fields.String(
        context="query",
    )


class ListTagsParamsResponseSchema(ApiObjectResponseSchema):
    containers = fields.Integer(
        dump_default=0,
    )
    resources = fields.Integer(
        dump_default=0,
    )
    links = fields.Integer(
        dump_default=0,
    )


class ListTagsResponseSchema(PaginatedResponseSchema):
    resourcetags = fields.Nested(
        ListTagsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListTags(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ListTagsResponseSchema": ListTagsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListTagsRequestSchema)
    parameters_schema = ListTagsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListTagsResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        tags, total = controller.get_tags(**data)
        res = [r.info() for r in tags]
        return self.format_paginated_response(res, "resourcetags", total, **data)


class CountTags(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjecCountResponseSchema": ApiObjecCountResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjecCountResponseSchema}})

    def get(self, controller: ResourceController, data, *args, **kwargs):
        resp = controller.count_all_tags()
        return {"count": int(resp)}


class GetTagParamsResponseSchema(ApiObjectResponseSchema):
    resources = fields.List(
        fields.Dict,
        required=True,
    )

    containers = fields.List(
        fields.Dict,
        required=True,
    )


class GetTagResponseSchema(Schema):
    resourcetag = fields.Nested(
        GetTagParamsResponseSchema,
        required=True,
        allow_none=True,
    )


class GetTag(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "GetTagResponseSchema": GetTagResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetTagResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        tag = controller.get_tag(oid)
        return {"resourcetag": tag.detail()}


class GetTagPerms(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "ApiObjectPermsRequestSchema": ApiObjectPermsRequestSchema,
        "ApiObjectPermsResponseSchema": ApiObjectPermsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ApiObjectPermsRequestSchema)
    parameters_schema = PaginatedRequestQuerySchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ApiObjectPermsResponseSchema}})

    def get(self, controller: ResourceController, data, oid, *args, **kwargs):
        tag = controller.get_tag(oid)
        res, total = tag.authorization(**data)
        return self.format_paginated_response(res, "perms", total, **data)


class CreateTagParamRequestSchema(Schema):
    value = fields.String(required=True)


class CreateTagRequestSchema(Schema):
    resourcetag = fields.Nested(CreateTagParamRequestSchema)


class CreateTagBodyRequestSchema(Schema):
    body = fields.Nested(CreateTagRequestSchema, context="body")


class CreateTag(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "CreateTagRequestSchema": CreateTagRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateTagBodyRequestSchema)
    parameters_schema = CreateTagRequestSchema
    responses = SwaggerApiView.setResponses({201: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        resp = controller.add_tag(**data.get("resourcetag"))
        return {"uuid": resp}, 201


class UpdateTagParamRequestSchema(Schema):
    value = fields.String()


class UpdateTagRequestSchema(Schema):
    resourcetag = fields.Nested(UpdateTagParamRequestSchema)


class UpdateTagBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateTagRequestSchema, context="body")


class UpdateTag(ResourceApiView):
    tags = ["resource"]
    definitions = {
        "UpdateTagRequestSchema": UpdateTagRequestSchema,
        "CrudApiObjectResponseSchema": CrudApiObjectResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateTagBodyRequestSchema)
    parameters_schema = UpdateTagRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CrudApiObjectResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        tag = controller.get_tag(oid)
        resp = tag.update(**data.get("resourcetag"))
        return {"uuid": resp}


class DeleteTag(ResourceApiView):
    tags = ["resource"]
    definitions = {}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "no response"}})

    def delete(self, controller, data, oid, *args, **kwargs):
        tag = controller.get_tag(oid)
        resp = tag.expunge()
        return (resp, 204)


class DeleteCacheContainerRequestSchema(Schema):
    pass


class DeleteCacheContainer(ResourceApiView):
    tags = ["resource"]
    definitions = {}
    parameters = SwaggerHelper().get_parameters(DeleteCacheContainerRequestSchema)
    parameters_schema = DeleteCacheContainerRequestSchema
    responses = SwaggerApiView.setResponses({204: {"description": "no response"}})

    def delete(self, controller: ResourceController, data, *args, **kwargs):
        self.logger.debug("controller.containers: %s", controller.containers)
        controller.containers = {}
        return 204


class ResourceAPI(ApiView):
    """Resource api routes V1:"""

    @staticmethod
    def register_api(module, **kwargs):
        mbp = module.base_path
        rules = [
            # new route
            (f"{mbp}/containers", "GET", ListContainers, {}),
            (f"{mbp}/containers", "POST", CreateContainer, {}),
            (f"{mbp}/containers/cache", "DELETE", DeleteCacheContainer, {}),
            (f"{mbp}/containers/count", "GET", CountContainers, {}),
            (f"{mbp}/containers/types", "GET", ListContainerTypes, {}),
            (f"{mbp}/containers/<oid>", "GET", GetContainer, {}),
            (f"{mbp}/containers/<oid>", "PUT", UpdateContainer, {}),
            (f"{mbp}/containers/<oid>", "DELETE", DeleteContainer, {}),
            (f"{mbp}/containers/<oid>/ping", "GET", PingContainer, {}),
            (
                f"{mbp}/containers/<oid>/perms",
                "GET",
                GetContainerPerms,
                {},
            ),
            (f"{mbp}/containers/<oid>/discover", "GET", Discover, {}),
            (f"{mbp}/containers/<oid>/discover_remote", "GET", DiscoverRemote, {}),
            (
                f"{mbp}/containers/<oid>/discover/types",
                "GET",
                DiscoverType,
                {},
            ),
            (
                f"{mbp}/containers/<oid>/discover",
                "PUT",
                SynchronizeResources,
                {},
            ),
            (
                f"{mbp}/containers/<oid>/discover/scheduler",
                "GET",
                GetScheduler,
                {},
            ),
            (
                f"{mbp}/containers/<oid>/discover/scheduler",
                "POST",
                CreateScheduler,
                {},
            ),
            (
                f"{mbp}/containers/<oid>/discover/scheduler",
                "DELETE",
                RemoveScheduler,
                {},
            ),
            (f"{mbp}/simple_entities", "GET", ListSimpleResources, {}),
            (f"{mbp}/entities", "GET", ListResources, {}),
            (f"{mbp}/entities", "POST", CreateResource, {}),
            (f"{mbp}/entities/import", "POST", ImportResource, {}),
            (f"{mbp}/entities/count", "GET", CountResources, {}),
            (f"{mbp}/entities/types", "GET", ListResourceTypes, {}),
            (f"{mbp}/entities/<oid>", "GET", GetResource, {}),
            (f"{mbp}/entities/<oid>", "PUT", UpdateResource, {}),
            (f"{mbp}/entities/<oid>", "PATCH", PatchResource, {}),
            (f"{mbp}/entities/<oid>", "DELETE", DeleteResource, {}),
            (f"{mbp}/entities/check", "GET", CheckResources, {}),
            (
                f"{mbp}/entities/<oid>/errors",
                "GET",
                GetResourceErrors,
                {},
            ),
            (f"{mbp}/entities/<oid>/tree", "GET", GetResourceTree, {}),
            (f"{mbp}/entities/<oid>/perms", "GET", GetResourcePerms, {}),
            (
                f"{mbp}/entities/<oid>/linked",
                "GET",
                GetLinkedResources,
                {},
            ),
            (
                f"{mbp}/entities/<oid>/metrics",
                "GET",
                GetResourceMetrics,
                {},
            ),
            (
                f"{mbp}/entities/<oid>/config",
                "GET",
                GetResourceConfig,
                {},
            ),
            (
                f"{mbp}/entities/<oid>/config",
                "PUT",
                UpdateResourceConfig,
                {},
            ),
            (
                f"{mbp}/entities/<oid>/state",
                "PUT",
                UpdateResourceState,
                {},
            ),
            (f"{mbp}/entities/<oid>/cache", "GET", GetResourceCache, {}),
            (
                f"{mbp}/entities/<oid>/cache",
                "PUT",
                CleanResourceCache,
                {},
            ),
            (f"{mbp}/entities/<oid>/check", "GET", CheckResource, {}),
            (f"{mbp}/links", "GET", ListLinks, {}),
            (f"{mbp}/links", "POST", CreateLink, {}),
            (f"{mbp}/links/count", "GET", CountLinks, {}),
            (f"{mbp}/links/<oid>", "GET", GetLink, {}),
            (f"{mbp}/links/<oid>", "DELETE", DeleteLink, {}),
            (f"{mbp}/links/<oid>", "PUT", UpdateLink, {}),
            (f"{mbp}/links/<oid>/perms", "GET", GetLinkPerms, {}),
            (f"{mbp}/links/<oid>/register", "PUT", UpdateLinkRegister, {}),
            (f"{mbp}/tags", "GET", ListTags, {}),
            (f"{mbp}/tags", "POST", CreateTag, {}),
            (f"{mbp}/tags/count", "GET", CountTags, {}),
            (f"{mbp}/tags/<oid>", "GET", GetTag, {}),
            (f"{mbp}/tags/<oid>", "PUT", UpdateTag, {}),
            (f"{mbp}/tags/<oid>", "DELETE", DeleteTag, {}),
            (f"{mbp}/tags/<oid>/perms", "GET", GetTagPerms, {}),
            #(f"{mbp}/jobs", "GET", ListJobs, {}),
        ]

        ApiView.register_api(module, rules, **kwargs)
