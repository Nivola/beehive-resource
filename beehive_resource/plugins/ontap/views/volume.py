# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from marshmallow.validate import OneOf
from marshmallow.decorators import validates_schema
from marshmallow.exceptions import ValidationError
from flasgger import fields, Schema
from typing import TYPE_CHECKING
from beecell.swagger import SwaggerHelper

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)

from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.ontap.views import OntapNetappApiView, OntapNetappAPI
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema, CreateResourceBaseRequestSchema

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController


class OntapNetappVolumeApiView(OntapNetappApiView):
    resclass = OntapNetappVolume
    parentclass = None


class OntapComplianceRequestParams(Schema):
    """
    compliance is implemented on ontap via snaplock
    snaplock is a special kind of snapmirror volume (write protected, specific deletion conditions)

    :snaplock_cluster: snaplock cluster name (if at provider level) or fqdn (at resource level)
    :snaplock_svm: snaplock svm name
    """
    cluster = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'faspod3',
            "description": 'The cluster where the snaplock of the share resides',
        },
    )

    svm = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'svmp3-provcuneo',
            "description": 'The svm where the snaplock of the share resides',
        },
    )

    rpo = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "description": 'Rpo. Choose among those defined on the svm. Also known as protection policy',
        },
    )


class OntapCreateVolumeSnapmirrorRequestParams(Schema):
    """same as compliance params, plus the source volume id
    """
    cluster = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'faspod1',
            "description": 'The cluster where the share resides',
        },
    )

    svm = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'svmp1-cmpstaas-test',
            "description": 'The svm where the share resides',
        },
    )

    rpo = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "description": 'Rpo. Choose among those defined on the svm. Also known as protection policy',
        },
    )

    source_id = fields.String(
        required=True,
        metadata={
            "description": 'Source cmp ontap volume id to use as source of snapmirror relation',
        },
    )


class OntapCreateVolumeRequestParams(Schema):
    """common share parameters (size,share_proto) and
    parameters exclusive to ontap backend, for volume creation.

    :param size: volume size in GBs
    :type size: int
    :param share_proto: share protocol (nfs,cifs)
    :type share_proto: str
    :param cluster: destination fas cluster (name at provider level, fqdn at resource level)
    :type cluster: str
    :param svm: destination svm name in destination cluster
    :type svm: str
    :param snapshot_policy: periodic snapshot creation policy.
    snapshots are created on the volume itself.
    :type snapshot_policy: str
    """
    size = fields.Integer(
        required=True,
        metadata={
            "example": '10',
            "description": 'share size, in GBs',
        },
    )

    share_proto = fields.String(
        required=True,
        validate=OneOf(['nfs', 'cifs']),
        metadata={
            "description": 'Share protocol; use one of nfs, cifs',
        },
    )

    cluster = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'faspod1',
            "description": 'The cluster where the share resides. (same as container name)',
        },
    )

    svm = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'svmp1-cmpstaas-test',
            "description": 'The svm where the share resides',
        },
    )

    snapshot_policy = fields.String(
        required=False, # at the moment it's a fixed value.
        allow_none=False,
        description="Snapshot policy. Choose among those defined on the svm",
        load_default="default"
    )


class ListVolumesRequestSchema(ListResourcesRequestSchema):
    filter_deletable_snaplocks = fields.Boolean(
        context="query",
        required=False,
    )


class ListVolumesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVolumesResponseSchema(PaginatedResponseSchema):
    volumes = fields.Nested(
        ResourceResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListVolumes(OntapNetappVolumeApiView):
    summary = "List volumes"
    description = "List volumes"
    tags = ["ontap_netapp"]

    definitions = {
        "ListVolumesResponseSchema": ListVolumesResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ListVolumesRequestSchema)
    parameters_schema = ListVolumesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVolumesResponseSchema}})

    def get(self, controller: 'ResourceController', data, *args, **kwargs):
        filter_deletable_snaplocks = data.pop("filter_deletable_snaplocks",False)
        if filter_deletable_snaplocks:
            size = data.get("size",20)
            page = data.get("page",0)
            resp, total = OntapNetappVolume.get_deletable_snaplocks(controller, limit=size, offset=page*size)
            return self.format_paginated_response(resp, self.resclass.objname + "s", total, **data)
        else:
            return self.get_resources(controller, **data)


class GetVolumeResponseSchema(Schema):
    volume = fields.Nested(
        ResourceResponseSchema,
        required=True,
        allow_none=True,
    )


class GetVolume(OntapNetappVolumeApiView):
    summary = "Get volume"
    description = "Get volume"
    tags = ["ontap_netapp"]

    definitions = {
        "GetVolumeResponseSchema": GetVolumeResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVolumeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class VolumeAwxParams(Schema):
    """optional parameters that are necessary
    if you aren't creating the ontap volume from provider
    and you need to call playbooks"""
    awx_orchestrator_id = fields.Integer(
        required=True,
        metadata={
            "description": 'awx orchestrator id',
        },
    )

    awx_organization_id = fields.Str(
        required=True,
        metadata={
            "description": 'awx organization name',
        },
    )

    awx_project_id = fields.Integer(
        required=True,
        metadata={
            "description": 'awx project id',
        },
    )

    awx_vault_cred_id = fields.Integer(
        required=True,
        metadata={
            "description": 'id of the vault credentials necessary to use the specific fas from awx',
        },
    )


class ImportCreateCommonParams(CreateResourceBaseRequestSchema):
    """
    inherits name, container, tags
    """
    desc = fields.String(
        required=False,
        metadata={
            "example": 'description goes here',
        },
    )

    role = fields.String(
        required=True,
        validate=OneOf(['main', 'snaplock', 'dr']),
        metadata={
            "description": 'volume role: - main: a regular volume; - snaplock: a snaplock volume; - dr: a dr volume',
        },
    )

    share_params = fields.Nested(
        OntapCreateVolumeRequestParams,
        required=True,
    )

    compliance = fields.Boolean(
        required=True,
        metadata={
            "description": "whether or not we are being 'compliant' with cloud requirements",
        },
    )

    compliance_share_params = fields.Nested(
        OntapComplianceRequestParams,
        required=False,
    )

    awx_params = fields.Nested(
        VolumeAwxParams,
        required=False,
    )

    @validates_schema
    def validate_params(self, data, **kwargs):
        if data.get("compliance") and not data.get("compliance_share_params"):
            msg = 'compliance_share_params are required when compliance is True.','compliance_share_params'
            raise ValidationError(msg)


class ImportVolumeParamRequestSchema(ImportCreateCommonParams):
    #ext_id = fields.String(required=True, description="<uuid> of the volume to import")

    @validates_schema
    def validate_params(self, data, **kwargs):
        super().validate_params(data, **kwargs)
        if data.get("role")!="main" and data.get("compliance")==True:
            raise Exception("do not provide compliance params to import a snaplock or dr volume at this level")


class ImportVolumeRequestSchema(Schema):
    volume = fields.Nested(
        ImportVolumeParamRequestSchema,
    )


class ImportVolumeBodyRequestSchema(Schema):
    body = fields.Nested(
        ImportVolumeRequestSchema,
        context="body",
    )


class CreateVolumeParamRequestSchema(ImportCreateCommonParams):
    pass


class CreateVolumeRequestSchema(Schema):
    volume = fields.Nested(
        CreateVolumeParamRequestSchema,
    )


class CreateVolumeBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateVolumeRequestSchema,
        context="body",
    )


class CreateVolume(OntapNetappVolumeApiView):
    summary = "Create volume"
    description = "Create volume"
    tags = ["ontap_netapp"]

    definitions = {
        "CreateVolumeRequestSchema": CreateVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateVolumeBodyRequestSchema)
    parameters_schema = CreateVolumeRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class CreateVolumeSnapmirrorRequestSchema(Schema):
    volume = fields.Nested(
        OntapCreateVolumeSnapmirrorRequestParams,
    )


class CreateVolumeSnapmirrorBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateVolumeSnapmirrorRequestSchema,
        context="body",
    )


class CreateVolumeSnapmirror(OntapNetappVolumeApiView):
    summary = "Create volume snapmirror"
    description = "Create snapmirror volume of existing volume"
    tags = ["ontap_netapp"]

    definitions = {
        "CreateVolumeSnapmirrorRequestSchema": CreateVolumeSnapmirrorRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateVolumeSnapmirrorBodyRequestSchema)
    parameters_schema = CreateVolumeSnapmirrorRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        data["role"]="dr"
        return self.create_resource(controller, data)


class ImportVolume(OntapNetappVolumeApiView):
    summary = "Import volume"
    description = "Import volume"
    tags = ["ontap_netapp"]

    definitions = {
        "ImportVolumeRequestSchema": ImportVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ImportVolumeBodyRequestSchema)
    parameters_schema = ImportVolumeRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        # identico a create_resource solo che chiama pre_import invece di pre_create
        return self.import_resource(controller, data)


class DeleteVolume(OntapNetappVolumeApiView):
    summary = "Delete volume"
    description = "Delete volume"
    tags = ["ontap_netapp"]
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class OntapNetappVolumeAPI(OntapNetappAPI):
    """OntapNetapp base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OntapNetappAPI.base
        rules = [
            (f"{base}/volumes", "GET", ListVolumes, {}),
            (f"{base}/volumes/<oid>", "GET", GetVolume, {}),
            (f"{base}/volumes/<oid>", "DELETE", DeleteVolume, {}),
            (f"{base}/volumes", "POST", CreateVolume, {}),
            (f"{base}/volumes/snapmirror", "POST", CreateVolumeSnapmirror, {}),
            (f"{base}/volumes/import", "POST", ImportVolume, {})
        ]

        OntapNetappAPI.register_api(module, rules, **kwargs)

        # keep in case they are needed.
        # TODO remove in some next release
        legacy = f"{OntapNetappAPI.base}/legacy"
        rules_legacy = [
            (f"{legacy}/volumes", "POST", CreateVolumeLegacy, {}),
            (f"{legacy}/volumes/<oid>", "PUT", UpdateVolume, {}), # this likely won't work anymore and needs to be modified.
        ]

        OntapNetappAPI.register_api(module, rules_legacy, **kwargs)


# legacy views
class CreateVolumeLegacyParamRequestSchema(Schema):
    container = fields.String(
        required=True,
        metadata={
            "example": '12',
            "description": 'container id, uuid or name',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'name',
        },
    )

    desc = fields.String(
        required=False,
        metadata={
            "example": 'test',
            "description": 'name',
        },
    )

    ontap_volume_id = fields.String(
        required=True,
        metadata={
            "example": '23',
            "description": 'physical id of volume in ontap netapp platform',
        },
    )


class CreateVolumeLegacyRequestSchema(Schema):
    volume = fields.Nested(
        CreateVolumeLegacyParamRequestSchema,
    )


class CreateVolumeLegacyBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateVolumeLegacyRequestSchema,
        context="body",
    )


class CreateVolumeLegacy(OntapNetappVolumeApiView):
    summary = "Create volume"
    description = "Create volume"
    tags = ["ontap_netapp"]

    definitions = {
        "CreateVolumeLegacyRequestSchema": CreateVolumeLegacyRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateVolumeLegacyBodyRequestSchema)
    parameters_schema = CreateVolumeLegacyRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        return self.create_resource(controller, data)


class UpdateVolumeParamRequestSchema(Schema):
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

    enabled = fields.Boolean(
        metadata={
            "example": True,
        },
    )


class UpdateVolumeRequestSchema(Schema):
    volume = fields.Nested(
        UpdateVolumeParamRequestSchema,
    )


class UpdateVolumeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        UpdateVolumeRequestSchema,
        context="body",
    )


class UpdateVolume(OntapNetappVolumeApiView):
    summary = "Update volume"
    description = "Update volume"
    tags = ["ontap_netapp"]

    definitions = {
        "UpdateVolumeRequestSchema": UpdateVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateVolumeBodyRequestSchema)
    parameters_schema = UpdateVolumeRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, oid, data)
