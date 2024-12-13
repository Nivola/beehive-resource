# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

import re

# from ansible_collections.community.vmware.plugins.connection.vmware_tools import example
from marshmallow import validate
from marshmallow.validate import OneOf
from marshmallow.decorators import validates_schema
from marshmallow.exceptions import ValidationError
from six import ensure_text
from beehive_resource.plugins.provider.entity.share_v2 import ComputeFileShareV2
from beehive_resource.plugins.provider.entity.vpc import Vpc
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
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)
from ipaddress import IPv4Address, AddressValueError


class ProviderShareV2(LocalProviderApiView):
    resclass = ComputeFileShareV2
    parentclass = ComputeZone


class ListShareV2sRequestSchema(ListResourcesRequestSchema):
    compute_zone = fields.String(context="query", description="super zone id or uuid")
    vpc = fields.String(context="query", description="vpc id or uuid")


class ShareV2VpcResponseSchema(Schema):
    uuid = fields.UUID(
        required=False,
        allow_none=True,
        default="6d960236-d280-46d2-817d-f3ce8f0aeff7",
        example="6d960236-d280-46d2-817d-f3ce8f0aeff7",
    )
    name = fields.String(required=False, default="test", example="test", allow_none=True)


class ShareV2ResponseSchema(ResourceResponseSchema):
    availability_zone = fields.Nested(ResourceSmallResponseSchema, required=True)
    vpcs = fields.Nested(ShareV2VpcResponseSchema, required=True)


class ListShareV2sResponseSchema(PaginatedResponseSchema):
    shares = fields.Nested(ShareV2ResponseSchema, many=True, required=True, allow_none=True)


class ListShareV2s(ProviderShareV2):
    definitions = {
        "ListShareV2sRequestSchema": ListShareV2sRequestSchema,
        "ListShareV2sResponseSchema": ListShareV2sResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListShareV2sRequestSchema)
    parameters_schema = ListShareV2sRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListShareV2sResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List shares
        List shares
        """
        data["details"] = True

        zone_id = data.get("compute_zone", None)
        vpc_id = data.get("vpc", None)

        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, **data)
        elif vpc_id is not None:
            return self.get_linked_resources(controller, vpc_id, Vpc, **data)

        return self.get_resources(controller, **data)


class GetShareV2ResponseSchema(Schema):
    share = fields.Nested(ShareV2ResponseSchema, required=True, allow_none=True)


class GetShareV2(ProviderShareV2):
    definitions = {
        "GetShareV2ResponseSchema": GetShareV2ResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetShareV2ResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get share
        Get share
        """
        return self.get_resource(controller, oid)


class ShareV2RequestParams(Schema):
    """
    :size: volume size, in GBs
    :share_proto: share protocol (nfs,cifs)
    """

    size = fields.Integer(required=True, example=10, description="share size, in GBs")
    share_proto = fields.String(
        required=True,
        validate=OneOf(ComputeFileShareV2.protos),
        description="Share protocol; use one of %s" % ",".join(ComputeFileShareV2.protos),
    )
    # share_proto_prefix = fields.String( # TODO probabilmente non serve
    #    required=False,
    #    example="",
    #    missing=None,
    #    allow_none=True,
    #    description="share protocol prefix",
    # )


class ShareV2OntapRequestParams(ShareV2RequestParams):
    """
    inherits: size, share_proto

    other params:

    :cluster: destination cluster
    :svm: destination svm in destination cluster
    :snaplock cluster: snaplock cluster
    :snaplock svm: svm in snaplock cluster
    :snapshot policy: snapshot policy (snapshots created on dest. volume)
    """

    cluster = fields.String(
        required=True, allow_none=False, description="The cluster where the share resides", example="faspod1"
    )
    svm = fields.String(
        required=True, allow_none=False, description="The svm where the share resides", example="svmp1-provcuneo"
    )
    snaplock_cluster = fields.String(
        required=False,
        allow_none=True,
        description="The cluster where the snaplock of the share resides",
        example="faspod3",
    )
    snaplock_svm = fields.String(
        required=False,
        allow_none=True,
        description="The svm where the snaplock of the share resides",
        example="svmp3-provcuneo",
    )
    snapshot_policy = fields.String(
        required=True,
        allow_none=False,
        validate=OneOf(ComputeFileShareV2.snapshot_policies),
        description="Snapshot policy; use one of %s" % ",".join(ComputeFileShareV2.snapshot_policies),
    )
    clients = fields.List(fields.Integer(), required=True, validate=validate.Length(min=1))
    # clients2 = fields.Int(
    #    required=True,
    #    allow_none = False,
    #    description="list of ids of vms that should be able to access the share",
    #    many=True
    # )
    # clients = fields.List(
    #    fields.String(example=""),
    #    required=True,
    #    allow_none=False,
    #    description="list of ids of vms that should be able to access the share",
    #    collection_format="multi",
    # )


class CreateShareV2ParamRequestSchema(CreateProviderResourceRequestSchema):
    """
    inherits: name, container, tags, desc, orchestrator_tag

    other params:

    :compute_zone: compute zone id or uuid
    :orchestrator_type: orchestrator type (ontap,...)
    :awx_orchestrator_tag: awx orchestrator tag
    :ontap_share_params: ontap share params

    when adding support for more orchestrator types, add a nested schema
    like for ontap_share_params, and extend validation checks.
    """

    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    orchestrator_type = fields.String(
        required=True,
        example="ontap",
        allow_none=False,
        description="orchestrator type",
    )
    awx_orchestrator_tag = fields.String(
        required=True,
        example="V2",
        allow_none=False,
        description="tag to distinguish old awx to new one",
    )
    site = fields.String(required=True, example="SiteTorino01")
    ontap_share_params = fields.Nested(ShareV2OntapRequestParams, allow_none=True)
    # other_share_params = ...


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

    def post(self, controller, data, *args, **kwargs):
        """
        Create share
        Create share
        """
        if data.get("orchestrator_type") == "ontap" and data.get("ontap_share_params") is None:
            raise ValidationError("Ontap orchestrator type specified but ontap parameters missing")
        return self.create_resource(controller, data)


# TODO check all other APIS
class UpdateShareV2GrantRequestSchema(Schema):
    access_level = fields.String(
        required=False,
        example="rw",
        description="The access level to the share",
        validate=OneOf(["RO", "ro", "RW", "rw"]),
    )
    access_type = fields.String(
        required=False,
        example="ip",
        description="The access rule type",
        validate=OneOf(["IP", "ip", "cert", "CERT", "USER", "user"]),
    )
    access_to = fields.String(
        required=False,
        example="10.102.186.0/24",
        description="The value that defines the access. - ip. A valid format is XX.XX.XX.XX or "
        "XX.XX.XX.XX/XX. For example 0.0.0.0/0. - cert. A valid value is any "
        "string up to 64 characters long in the common name (CN) of the certificate."
        " - user. A valid value is an alphanumeric string that can contain some "
        "special characters and is from 4 to 32 characters long.",
    )
    access_id = fields.String(
        required=False,
        example="52bea969-78a2-4f7e-ae84-fb4599dc06ca",
        description="The UUID of the access rule to which access is granted.",
    )
    action = fields.String(
        required=False,
        example="ip",
        validate=OneOf(["add", "del"]),
        description="Set grant action: add or del",
    )

    @validates_schema
    def validate_grant_access_parameters(self, data, *args, **kvargs):
        msg1 = "parameter is malformed. Range network prefix must be >= 0 and <= 32"
        access_type = data.get("access_type", "").lower()
        access_to = data.get("access_to", "")
        if access_type == "ip":
            try:
                ip, prefix = access_to.split("/")
                prefix = int(prefix)
                if prefix < 0 or prefix > 32:
                    raise ValidationError(msg1)
                IPv4Address(ensure_text(ip))
            except AddressValueError:
                raise ValidationError("parameter access_to is malformed. Use xxx.xxx.xxx.xxx/xx syntax")
            except ValueError:
                raise ValidationError(msg1)
        elif access_type == "user":
            # '^[A-Za-z0-9]{4,32}$'
            if re.match("^[A-Za-z0-9;_\`'\-\.\{\}\[\]]{4,32}$", access_to) is None:
                raise ValidationError(
                    "parameter access_to is malformed. A valid value is an alphanumeric string that "
                    "can contain some special characters and is from 4 to 32 characters long"
                )
        elif access_type == "cert":
            if re.match("^[A-Za-z0-9]{1,64}$", access_to) is None:
                # raise ValidationError('parameter access_to is malformed. A valid value is any '
                #         'string up to 64 characters long in the common name (CN) of the certificate')
                raise ValidationError('parameter access_to "cert|CERT" value is not supported')


class UpdateShareV2ParamRequestSchema(UpdateProviderResourceRequestSchema):
    size = fields.Integer(required=False, description="share size, in GBs")
    grant = fields.Nested(UpdateShareV2GrantRequestSchema, required=False, description="grant configuration")


class UpdateShareV2RequestSchema(Schema):
    share = fields.Nested(UpdateShareV2ParamRequestSchema)


class UpdateShareV2BodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateShareV2RequestSchema, context="body")


class UpdateShareV2(ProviderShareV2):
    definitions = {
        "UpdateShareV2RequestSchema": UpdateShareV2RequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateShareV2BodyRequestSchema)
    parameters_schema = UpdateShareV2RequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update share
        Update share

        To add a grant use action=add and set access_level, access_type and access_to.
        To remove a grant use action=del and set access_id
        """
        return self.update_resource(controller, oid, data)


class DeleteShareV2(ProviderShareV2):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete share
        Delete share
        """
        return self.expunge_resource(controller, oid)


class ShareV2ProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/shares" % base, "GET", ListShareV2s, {}),
            ("%s/shares" % base, "POST", CreateShareV2, {}),
            ("%s/shares/<oid>" % base, "GET", GetShareV2, {}),
            ("%s/shares/<oid>" % base, "PUT", UpdateShareV2, {}),
            ("%s/shares/<oid>" % base, "DELETE", DeleteShareV2, {}),
        ]
        kwargs["version"] = "v2.0"
        ProviderAPI.register_api(module, rules, **kwargs)
