# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

#import re

from marshmallow import validate
from marshmallow.validate import OneOf #,Length
from marshmallow.decorators import validates_schema
from typing import TYPE_CHECKING

from beecell.types.type_dict import dict_get
from beehive_resource.plugins.provider.entity.share_v2 import ComputeFileShareV2
from beehive_resource.plugins.provider.entity.zone import ComputeZone

from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
)

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)

from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema

from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
)

from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.views import ProviderComplianceRequestParams

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController

class ProviderShareV2(LocalProviderApiView):
    resclass = ComputeFileShareV2
    parentclass = ComputeZone

class ShareV2BaseRequestParams(Schema):
    """
    :size: volume size, in GBs
    :share_proto: share protocol (nfs,cifs)
    """
    size = fields.Integer(
        required=True,
        metadata={
            "example": 10,
            "description": 'share size, in GBs',
        },
    )

    share_proto = fields.String(
        required=True,
        validate=OneOf(ComputeFileShareV2.protocols),
        metadata={
            "description": 'Share protocol; use one of %s' % ','.join(ComputeFileShareV2.protocols),
        },
    )

class ShareV2CreateRequestParams(ShareV2BaseRequestParams):
    """
    :size: volume size, in GBs
    :share_proto: share protocol (nfs,cifs)
    :encrypted: if encrypted or not (False until supported)
    :snapshot_policy: the snapshot policy to apply to the volume
    """
    encrypted = fields.Bool(
        required=False,
        validate=OneOf([True, False]),
        load_default=False,
    )

    snapshot_policy = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'staas_snap_8h_21d_14w_6m',
        },
    )

class ListShareV2sRequestSchema(ListResourcesRequestSchema):
    compute_zone = fields.String(
        context="query",
        metadata={
            "description": 'super zone id or uuid',
        },
    )

    vpc = fields.String(
        context="query",
        metadata={
            "description": 'vpc id or uuid',
        },
    )


class ShareV2VpcResponseSchema(Schema):
    uuid = fields.UUID(
        required=False,
        allow_none=True,
        metadata={
            "example": '6d960236-d280-46d2-817d-f3ce8f0aeff7',
        },
    )

    name = fields.String(
        required=False,
        dump_default="test",
        allow_none=True,
        metadata={
            "example": 'test',
        },
    )


class ShareV2ResponseSchema(ResourceResponseSchema):
    availability_zone = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
    )

    vpcs = fields.Nested(
        ShareV2VpcResponseSchema,
        required=True,
    )


class ListShareV2sResponseSchema(PaginatedResponseSchema):
    shares = fields.Nested(
        ShareV2ResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListShareV2s(ProviderShareV2):
    definitions = {
        "ListShareV2sRequestSchema": ListShareV2sRequestSchema,
        "ListShareV2sResponseSchema": ListShareV2sResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ListShareV2sRequestSchema)
    parameters_schema = ListShareV2sRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListShareV2sResponseSchema}})

    def get(self, controller: 'ResourceController', data, *args, **kwargs):
        """
        List shares
        """
        data['details'] = False
        zone_id = data.get("parent_list", None)
        if zone_id and len(zone_id)==1:
            return self.get_resources_by_parent(controller, zone_id, **data)
        return self.get_resources(controller, **data)


class GetShareV2ResponseSchema(Schema):
    share = fields.Nested(
        ShareV2ResponseSchema,
        required=True,
        allow_none=True,
    )


class GetShareV2(ProviderShareV2):
    definitions = {"GetShareV2ResponseSchema": GetShareV2ResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetShareV2ResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get share
        """
        return self.get_resource(controller, oid)


class CreateShareV2ParamRequestSchema(CreateProviderResourceRequestSchema,ProviderComplianceRequestParams):
    """
    inherits: name, container, tags, desc, orchestrator_tag, compliance, compliance_site,

    other params:

    :compute_zone: compute zone id or uuid
    :orchestrator_type: orchestrator type (ontap,...)
    :awx_orchestrator_tag: awx orchestrator tag
    :site: site where to create share
    :share_params: provider share params
    """

    compute_zone = fields.String(
        required=True,
        metadata={
            "example": '1',
            "description": 'parent compute zone id or uuid',
        },
    )

    orchestrator_type = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'ontap',
            "description": 'orchestrator type',
        },
    )

    awx_orchestrator_tag = fields.String(
        required=False,
        allow_none=False,
        metadata={
            "example": 'V2',
            "description": 'tag to distinguish old awx to new one',
        },
    )

    site = fields.String(
        required=True,
        metadata={
            "example": 'SiteTorino01',
        },
    )
    share_params = fields.Nested(ShareV2CreateRequestParams, required=True)

    @validates_schema
    def validate_params(self, data, **kwargs):
        super().validate_compliance_site(data,**kwargs)



class CreateShareV2RequestSchema(Schema):
    share = fields.Nested(CreateShareV2ParamRequestSchema)


class CreateShareV2BodyRequestSchema(Schema):
    body = fields.Nested(CreateShareV2RequestSchema, context="body")


class CreateShareV2(ProviderShareV2):
    definitions = {
        "CreateShareV2RequestSchema": CreateShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateShareV2BodyRequestSchema)
    parameters_schema = CreateShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller: 'ResourceController', data, *args, **kwargs):
        """
        Create share
        """
        return self.create_resource(controller, data)


class CreateShareV2ReplicaParamRequestSchema(CreateProviderResourceRequestSchema):
    """
    inherits: name, container, tags, desc, orchestrator_tag
    name is optional as it's usually set by convention e.g. dr-<source name>
    other params:

    :compute_zone: compute zone id or uuid
    :awx_orchestrator_tag: awx orchestrator tag
    :site: site where to create replica
    :rpo: rpo
    """
    # redefine name and desc to be optional
    name = fields.String(
        required=False,
        metadata={
            "example": 'dr-test',
            "description": 'the share replica name',
        },
    )

    desc = fields.String(
        required=False,
        load_default="replica",
        metadata={
            "example": 'test',
            "description": 'The resource description',
        },
    )

    compute_zone = fields.String(
        required=True,
        metadata={
            "example": '1',
            "description": 'parent compute zone id or uuid',
        },
    )

    awx_orchestrator_tag = fields.String(
        required=False,
        allow_none=False,
        metadata={
            "example": 'V2',
            "description": 'tag to select awx orchestrator',
        },
    )

    site = fields.String(
        required=True,
        metadata={
            "example": 'SiteTorino01',
        },
    )

    rpo = fields.String(
        required=True,
        validate=OneOf(['30m', '1h', '3h', '6h', '12h', '24h']),
        metadata={
            "description": 'dr rpo',
        },
    )


class CreateShareV2ReplicaRequestSchema(Schema):
    share = fields.Nested(CreateShareV2ReplicaParamRequestSchema)


class CreateShareV2ReplicaBodyRequestSchema(Schema):
    body = fields.Nested(CreateShareV2ReplicaRequestSchema, context="body")

class CreateShareV2Replica(ProviderShareV2):
    definitions = {
        "CreateShareV2ReplicaRequestSchema": CreateShareV2ReplicaRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateShareV2ReplicaBodyRequestSchema)
    parameters_schema = CreateShareV2ReplicaRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Create share replica
        """
        data["share"]["from_id"] = oid
        # check name false as name is optional. check later in pre_create
        return self.create_resource(controller, data, check_name=False)


class ImportShareV2ParamRequestSchema(CreateProviderResourceRequestSchema):
    """
    inherits: name, container, tags, desc, orchestrator_tag

    other params:

    :compute_zone: compute zone id or uuid
    :orchestrator_type: orchestrator type (ontap,...)
    :awx_orchestrator_tag: awx orchestrator tag
    """
    compute_zone = fields.String(
        required=True,
        metadata={
            "example": '1',
            "description": 'parent compute zone id or uuid',
        },
    )

    orchestrator_type = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'ontap',
            "description": 'orchestrator type',
        },
    )

    awx_orchestrator_tag = fields.String(
        required=True,
        allow_none=False,
        metadata={
            "example": 'V2',
            "description": 'tag to distinguish old awx to new one',
        },
    )

    site = fields.String(
        required=True,
        metadata={
            "example": 'SiteTorino01',
        },
    )

    remote_name = fields.String(
        required=True,
        allow_none=False,
    )

    force_import_as_main = fields.Boolean(
        required=False,
        load_default=False,
        metadata={
            "description": (
                'in case you know volume is not a replica, but it currently is for example because syncing for'
                'migration'
            ),
        },
    )

    @validates_schema
    def validate_params(self, data, **kwargs):
        name = data.get("name")
        remote_name = data.get("remote_name")
        orchestrator_type = data.get("orchestrator_type")
        if orchestrator_type=="ontap" and ("snaplock" in name or "snaplock" in remote_name):
            raise Exception("Don't import snaplock volume with this command. It will be imported when importing main volume.")


class ImportShareV2RequestSchema(Schema):
    share = fields.Nested(ImportShareV2ParamRequestSchema)


class ImportShareV2BodyRequestSchema(Schema):
    body = fields.Nested(ImportShareV2RequestSchema, context="body")

class ImportShareV2(ProviderShareV2):
    definitions = {
        "ImportShareV2RequestSchema": ImportShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ImportShareV2BodyRequestSchema)
    parameters_schema = ImportShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller: 'ResourceController', data, *args, **kwargs):
        """
        Import share
        """
        return self.import_resource(controller, data)


class ResizeShareV2ParamRequestSchema(Schema):
    new_size = fields.Integer(
        required=False,
        metadata={
            "description": 'share size, in GBs',
        },
    )

    extend_shrink = fields.Str(
        required=True,
        validate=OneOf(['extend', 'shrink']),
    )


class ResizeShareV2RequestSchema(Schema):
    share = fields.Nested(ResizeShareV2ParamRequestSchema)


class ResizeShareV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ResizeShareV2RequestSchema, context="body")

class ResizeShareV2(ProviderShareV2):
    """
    extend or shrink share
    """
    definitions = {
        "ResizeShareV2RequestSchema": ResizeShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ResizeShareV2BodyRequestSchema)
    parameters_schema = ResizeShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        extend or shrink share
        """
        share_params = data.get("share")
        action = share_params.get("extend_shrink")
        share: 'ComputeFileShareV2' = self.get_resource_reference(controller, oid)
        if action in share.actions:
            task = share.share_action("resize", action_params=share_params, keys_to_update=[("size","size")])
        else:
            raise ApiManagerError("Action %s not supported for share" % action)
        return task


class SetStateShareV2ParamRequestSchema(Schema):
    state = fields.String(
        required=True,
        validate=OneOf(['online', 'offline']),
        metadata={
            "description": 'share state',
        },
    )


class SetStateShareV2RequestSchema(Schema):
    share = fields.Nested(SetStateShareV2ParamRequestSchema)


class SetStateShareV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        SetStateShareV2RequestSchema,
        context="body",
    )


class SetStateShareV2(ProviderShareV2):
    """
    set share state
    """
    definitions = {
        "SetStateShareV2RequestSchema": SetStateShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(SetStateShareV2BodyRequestSchema)
    parameters_schema = SetStateShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        put share mount target online or offline
        """
        share_params = data.get("share")
        state = share_params.pop("state")
        action_name = f"set_{state}"
        share: 'ComputeFileShareV2' = self.get_resource_reference(controller, oid)
        if action_name in share.actions:
            share_params["wanted_state"] = state
            task = share.share_action("set_volume_state", action_params=share_params)
        else:
            raise ApiManagerError("Action %s not supported for share" % action_name)
        return task


class UpdateSnapshotPolicyShareV2ParamRequestSchema(Schema):
    snapshot_policy = fields.String(
        required=True,
        allow_none=False,
    )


class UpdateSnapshotPolicyShareV2RequestSchema(Schema):
    share = fields.Nested(UpdateSnapshotPolicyShareV2ParamRequestSchema)


class UpdateSnapshotPolicyShareV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        ResizeShareV2RequestSchema,
        context="body",
    )


class UpdateSnapshotPolicyShareV2(ProviderShareV2):
    """
    update the snapshot policy of a share
    """
    definitions = {
        "UpdateSnapshotPolicyShareV2RequestSchema": UpdateSnapshotPolicyShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateSnapshotPolicyShareV2BodyRequestSchema)
    parameters_schema = UpdateSnapshotPolicyShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        extend or shrink share
        """
        share_params = data.get("share")
        share_params["action"] = "update"
        share: 'ComputeFileShareV2' = self.get_resource_reference(controller, oid)
        task = share.share_action("manage_snapshot_policy", action_params=share_params)
        return task


class PolicyShareV2ParamRequestSchema(Schema):
    access_ids = fields.List(
        fields.Integer(example=2),
        required=False,
        metadata={
            "example": '[2, 4, 5]',
        },
    )

    su_access = fields.Boolean(
        required=False,
    )

    rw_access = fields.Str(
        required=False,
        validate=OneOf(['rw', 'ro']),
    )

    client_type = fields.Str(
        required=False,
        validate=OneOf(['id', 'cidr', 'user']),
    )

    clients = fields.List(
        fields.Str(),
        required=False,
        validate=validate.Length(min=1),
    )

    action = fields.Str(
        required=True,
        validate=OneOf(['grant_access', 'revoke_access']),
    )

    protocol = fields.String(
        required=False,
        validate=OneOf(['nfs', 'nfs3', 'cifs']),
    )


class PolicyShareV2Request1Schema(Schema):
    policy = fields.Nested(
        PolicyShareV2ParamRequestSchema,
        required=True,
        metadata={
            "description": 'ACL policy configuration',
        },
    )


class PolicyShareV2RequestSchema(Schema):
    share = fields.Nested(PolicyShareV2Request1Schema)


class PolicyShareV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        PolicyShareV2RequestSchema,
        context="body",
    )


class PolicyShareV2(ProviderShareV2):
    """
    add or remove rule to/from export policy
    """
    definitions = {
        "PolicyShareV2RequestSchema": PolicyShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(PolicyShareV2BodyRequestSchema)
    parameters_schema = PolicyShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        add or remove rule to/from export policy
        """
        share_params = dict_get(data, "share.policy")
        action = share_params.get("action")
        share: 'ComputeFileShareV2' = self.get_resource_reference(controller, oid)
        if action in share.actions:
            task = share.share_action("manage_policy", action_params=share_params)
        else:
            raise ApiManagerError("Action %s not supported for share" % action)
        return task


class DeleteShareV2(ProviderShareV2):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete share
        """
        return self.expunge_resource(controller, oid)


class ShareV2HandleReplicaParamRequestSchema(Schema):
    subaction = fields.Str(
        required=True,
        validate=OneOf(['unlink', 'suspend', 'resume', 'mount', 'update']),
    )

    new_name = fields.Str(
        required=False,
        allow_none=True,
    )

    rpo = fields.Str(
        required=False,
        allow_none=True,
    )

    @validates_schema
    def validate_unlink(self, data, **kwargs):
        if data.get("subaction")=="unlink" and not data.get("new_name"):
            raise Exception(
                "When breaking a replica relationship, a new name must be given "
                "in order for the volume to become independent."
                "This isn't needed if you want to delete the replica instead, "
                "in which case, this is the wrong endpoint."
            )


class ShareV2HandleReplicaRequestSchema(Schema):
    share = fields.Nested(ShareV2HandleReplicaParamRequestSchema)

class ShareV2HandleReplicaBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(ShareV2HandleReplicaRequestSchema, context="body")

class ShareV2HandleReplica(ProviderShareV2):
    """
    extend or shrink share
    """
    definitions = {
        "ShareV2HandleReplicaRequestSchema": ShareV2HandleReplicaRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ShareV2HandleReplicaBodyRequestSchema)
    parameters_schema = ShareV2HandleReplicaRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        suspend replica process
        """
        share_params = data.get("share")
        sub_action = share_params.pop("subaction")
        action_name = f"replica_{sub_action}"
        share: 'ComputeFileShareV2' = self.get_resource_reference(controller, oid)
        if action_name in share.actions:
            share_params["sub_action"] = action_name
            if action_name=="replica_unlink":
                task = share.share_action("replica_manage",
                                          action_params=share_params,
                                          keys_to_update=[
                                              ("role","share_role"),
                                              ("size","size")
                                          ]
                )
            else:
                task = share.share_action("replica_manage", action_params=share_params)
        else:
            raise ApiManagerError("Action %s not supported for share" % action_name)
        return task


class ManageShareV2Param1RequestSchema(Schema):
    compliance = fields.Boolean(
        required=False,
        allow_none=False,
    )

    rpo = fields.Str(
        required=False,
        allow_none=False,
    )

class ManageShareV2ParamRequestSchema(Schema):
    subaction = fields.Str(
        required=True,
        validate=OneOf(['mount', 'compliance_enable', 'compliance_disable']),
    )

    subaction_params = fields.Nested(
        ManageShareV2Param1RequestSchema,
        required=False,
        allow_none=True,
    )

    metadata_only = fields.Boolean(
        required=False,
        allow_none=True,
        load_default=False,
    )


class ManageShareV2RequestSchema(Schema):
    share = fields.Nested(ManageShareV2ParamRequestSchema)


class ManageShareV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        ManageShareV2RequestSchema,
        context="body",
    )


class ManageShareV2(ProviderShareV2):
    """
    manage share (mount, ...)
    """
    definitions = {
        "ManageShareV2RequestSchema": ManageShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ManageShareV2BodyRequestSchema)
    parameters_schema = ManageShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        manage share (mount, ...)
        """
        share_params = data.get("share")
        sub_action_name = share_params.pop("subaction")
        metadata_only = share_params.get("metadata_only")
        share: 'ComputeFileShareV2' = self.get_resource_reference(controller, oid)
        if sub_action_name not in share.actions:
            raise ApiManagerError("Action %s not supported for share" % sub_action_name)
        share_params["sub_action"] = sub_action_name
        task = None
        if sub_action_name == "mount":
            task = share.share_action("manage", action_params=share_params)
        elif sub_action_name == "compliance_enable":
            task = share.compliance_action(sub_action_name, action_params=share_params, metadata_only=metadata_only)
        elif sub_action_name == "compliance_disable":
            task = share.compliance_action(sub_action_name, action_params=share_params, metadata_only=metadata_only)
        return task


class ShareV2ProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            (f"{base}/shares", "GET", ListShareV2s, {}),
            (f"{base}/shares/<oid>", "GET", GetShareV2, {}),
            (f"{base}/shares", "POST", CreateShareV2, {}),
            (f"{base}/shares/<oid>", "DELETE", DeleteShareV2, {}),
            (f"{base}/shares/<oid>", "PUT", ManageShareV2, {}),
            (f"{base}/shares/<oid>/resize", "PUT", ResizeShareV2, {}),
            (f"{base}/shares/<oid>/setstatus", "PUT", SetStateShareV2, {}),
            (f"{base}/shares/<oid>/policy", "PUT", PolicyShareV2, {}),
            (f"{base}/shares/<oid>/snapshotpolicy", "PUT", UpdateSnapshotPolicyShareV2, {}),
            (f"{base}/shares/import", "POST", ImportShareV2, {}),
            (f"{base}/shares/<oid>/replica", "POST", CreateShareV2Replica, {}),
            (f"{base}/shares/<oid>/replication", "PUT", ShareV2HandleReplica, {}),
        ]
        kwargs["version"] = "v2.0"
        ProviderAPI.register_api(module, rules, **kwargs)
