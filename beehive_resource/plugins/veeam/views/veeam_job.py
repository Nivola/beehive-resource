# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
    ApiView,
)
from beehive_resource.plugins.veeam.entity.veeam_job import VeeamJob
from beehive_resource.plugins.provider.views import (
    ResourceApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)
from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive_resource.plugins.veeam.views import VeeamAPI, VeeamApiView


class VeeamJobView(VeeamApiView):
    tags = ["veeam"]
    resclass = VeeamJob
    parentclass = None


class ListVeeamJobsRequestSchema(ListResourcesRequestSchema):
    pass


class ListVeeamJobsParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVeeamJobsResponseSchema(PaginatedResponseSchema):
    jobs = fields.Nested(ListVeeamJobsParamsResponseSchema, many=True, required=True, allow_none=True)


class ListVeeamJobs(VeeamJobView):
    summary = "List jobs"
    description = "List jobs"
    definitions = {
        "ListVeeamJobsResponseSchema": ListVeeamJobsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVeeamJobsRequestSchema)
    parameters_schema = ListVeeamJobsRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVeeamJobsResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """List Veeam jobs"""
        view: VeeamJobView = self
        return view.get_resources(controller, **data)


class GetVeeamJobParamsResponseSchema(ResourceResponseSchema):
    jobs = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetVeeamJobResponseSchema(Schema):
    job = fields.Nested(GetVeeamJobParamsResponseSchema, required=True, allow_none=True)


class GetVeeamJob(VeeamJobView):
    summary = "Get job"
    description = "Get job"
    definitions = {
        "GetVeeamJobResponseSchema": GetVeeamJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVeeamJobResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """Get Veeam job"""
        view: VeeamJobView = self
        return view.get_resource(controller, oid)


class CreateVeeamJobParamRequestSchema(CreateProviderResourceRequestSchema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test-name-job", default="", description="Job name")
    desc = fields.String(
        required=False,
        allow_none=True,
        example="test-desc-job",
        description="The resource description",
    )


class CreateVeeamJobRequestSchema(Schema):
    job = fields.Nested(CreateVeeamJobParamRequestSchema)


class CreateVeeamJobBodyRequestSchema(Schema):
    body = fields.Nested(CreateVeeamJobRequestSchema, context="body")


class CreateVeeamJob(VeeamJobView):
    summary = "Create job"
    description = "Create job"
    definitions = {
        "CreateVeeamJobRequestSchema": CreateVeeamJobRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVeeamJobBodyRequestSchema)
    parameters_schema = CreateVeeamJobRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """Add new job to Veeam"""
        view: VeeamJobView = self
        return view.create_resource(controller, data)


class UpdateVeeamJobTemplateRequestSchema(Schema):
    name = fields.String(required=True, example="Test job", default="", description="Job name")
    desc = fields.String(
        required=False,
        example="This is the test job",
        default="",
        description="Job description",
    )


class UpdateVeeamJobParamRequestSchema(UpdateProviderResourceRequestSchema):
    jobs = fields.Nested(
        UpdateVeeamJobTemplateRequestSchema,
        required=False,
        many=True,
        description="list of orchestrator jobs to link",
        allow_none=True,
    )


class UpdateVeeamJobRequestSchema(Schema):
    job = fields.Nested(UpdateVeeamJobParamRequestSchema)


class UpdateVeeamJobBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVeeamJobRequestSchema, context="body")


class UpdateVeeamJob(VeeamJobView):
    summary = "Update job"
    description = "Update job"
    definitions = {
        "UpdateVeeamJobRequestSchema": UpdateVeeamJobRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateVeeamJobBodyRequestSchema)
    parameters_schema = UpdateVeeamJobRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """Update Veeam job"""
        return self.update_resource(controller, oid, data)


class DeleteVeeamJob(VeeamJobView):
    summary = "Delete job"
    description = "Delete job"
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """Delete Veeam job"""
        return self.expunge_resource(controller, oid)


class VeeamJobAPI(VeeamAPI):
    """Veeam job api routes"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VeeamAPI.base
        rules = [
            ("%s/jobs" % base, "GET", ListVeeamJobs, {}),
            ("%s/jobs/<oid>" % base, "GET", GetVeeamJob, {}),
            ("%s/jobs" % base, "POST", CreateVeeamJob, {}),
            ("%s/jobs/<oid>" % base, "PUT", UpdateVeeamJob, {}),
            ("%s/jobs/<oid>" % base, "DELETE", DeleteVeeamJob, {}),
        ]

        kwargs["version"] = "v1.0"
        ApiView.register_api(module, rules, **kwargs)
