# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

import re
from marshmallow.validate import OneOf
from marshmallow.decorators import validates_schema
from marshmallow.exceptions import ValidationError
from beecell.util import ensure_text
from beehive_resource.plugins.provider.entity.share import ComputeFileShare
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


class ProviderShare(LocalProviderApiView):
    resclass = ComputeFileShare
    parentclass = ComputeZone


class ListSharesRequestSchema(ListResourcesRequestSchema):
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


class ShareVpcResponseSchema(Schema):
    uuid = fields.UUID(
        required=False,
        allow_none=True,
        dump_default="6d960236-d280-46d2-817d-f3ce8f0aeff7",
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


class ShareResponseSchema(ResourceResponseSchema):
    availability_zone = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
    )

    vpcs = fields.Nested(
        ShareVpcResponseSchema,
        required=True,
    )


class ListSharesResponseSchema(PaginatedResponseSchema):
    shares = fields.Nested(
        ShareResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListShares(ProviderShare):
    definitions = {
        "ListSharesRequestSchema": ListSharesRequestSchema,
        "ListSharesResponseSchema": ListSharesResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(ListSharesRequestSchema)
    parameters_schema = ListSharesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListSharesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List shares
        List shares
        """
        data["details"] = True

        zone_id = data.get("parent_list", None)
        vpc_id = data.get("vpc", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, **data)
        elif vpc_id is not None:
            return self.get_linked_resources(controller, vpc_id, Vpc, **data)
        return self.get_resources(controller, **data)


class GetShareResponseSchema(Schema):
    share = fields.Nested(
        ShareResponseSchema,
        required=True,
        allow_none=True,
    )


class GetShare(ProviderShare):
    definitions = {"GetShareResponseSchema": GetShareResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetShareResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get share
        """
        return self.get_resource(controller, oid)


class CreateShareParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(
        required=True,
        metadata={
            "example": '1',
            "description": 'parent compute zone id or uuid',
        },
    )

    network = fields.String(
        required=True,
        metadata={
            "example": '50',
            "description": 'id or uuid of the vpc',
        },
    )

    subnet = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": '10.102.167.90/24',
            "description": 'subnet cidr',
        },
    )

    availability_zone = fields.String(
        required=True,
        metadata={
            "description": 'availability zone',
        },
    )

    multi_avz = fields.Boolean(
        load_default=True,
        required=False,
        metadata={
            "example": False,
            "description": 'Define if instance must be deployed to work in all the availability zones',
        },
    )

    type = fields.String(
        required=False,
        load_default="openstack",
        metadata={
            "example": 'openstack',
            "description": 'type of the instance: vsphere or openstack',
        },
    )

    share_proto = fields.String(
        required=True,
        validate=OneOf(ComputeFileShare.protos),
        metadata={
            "description": 'Share protocol. Use one of %s' % ','.join(ComputeFileShare.protos),
        },
    )

    size = fields.Integer(
        required=True,
        metadata={
            "description": 'share size, in GBs',
        },
    )

    share_label = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'project',
            "description": 'custom label to be used when you want to use a labelled share type',
        },
    )

    share_volume = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'ru7d9e',
            "description": 'existing ontap volume physical id',
        },
    )


class CreateShareRequestSchema(Schema):
    share = fields.Nested(CreateShareParamRequestSchema)


class CreateShareBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateShareRequestSchema,
        context="body",
    )


class CreateShare(ProviderShare):
    definitions = {
        "CreateShareRequestSchema": CreateShareRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateShareBodyRequestSchema)
    parameters_schema = CreateShareRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create share
        """
        return self.create_resource(controller, data)


class UpdateShareGrantRequestSchema(Schema):
    access_level = fields.String(
        required=False,
        validate=OneOf(['RO', 'ro', 'RW', 'rw']),
        metadata={
            "example": 'rw',
            "description": 'The access level to the share',
        },
    )

    access_type = fields.String(
        required=False,
        validate=OneOf(['IP', 'ip', 'cert', 'CERT', 'USER', 'user']),
        metadata={
            "example": 'ip',
            "description": 'The access rule type',
        },
    )

    access_to = fields.String(
        required=False,
        metadata={
            "example": '10.102.186.0/24',
            "description": (
                'The value that defines the access. - ip. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX. For'
                'example 0.0.0.0/0. - cert. A valid value is any string up to 64 characters long in the common name'
                '(CN) of the certificate. - user. A valid value is an alphanumeric string that can contain some'
                'special characters and is from 4 to 32 characters long.'
            ),
        },
    )

    access_id = fields.String(
        required=False,
        metadata={
            "example": '52bea969-78a2-4f7e-ae84-fb4599dc06ca',
            "description": 'The UUID of the access rule to which access is granted.',
        },
    )

    access_ids = fields.List(
        fields.String,
        required=False,
    ) # for grant delete compat with v2

    action = fields.String(
        required=False,
        validate=OneOf(['add', 'del']),
        metadata={
            "example": 'ip',
            "description": 'Set grant action: add or del',
        },
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
            if re.match(r"^[A-Za-z0-9;_\`'\-\.\{\}\[\]]{4,32}$", access_to) is None:
                raise ValidationError(
                    "parameter access_to is malformed. A valid value is an alphanumeric string that "
                    "can contain some special characters and is from 4 to 32 characters long"
                )
        elif access_type == "cert":
            if re.match("^[A-Za-z0-9]{1,64}$", access_to) is None:
                # raise ValidationError('parameter access_to is malformed. A valid value is any '
                #         'string up to 64 characters long in the common name (CN) of the certificate')
                raise ValidationError('parameter access_to "cert|CERT" value is not supported')


class UpdateShareParamRequestSchema(UpdateProviderResourceRequestSchema):
    size = fields.Integer(
        required=False,
        metadata={
            "description": 'share size, in GBs',
        },
    )

    grant = fields.Nested(
        UpdateShareGrantRequestSchema,
        required=False,
        metadata={
            "description": 'grant configuration',
        },
    )


class UpdateShareRequestSchema(Schema):
    share = fields.Nested(UpdateShareParamRequestSchema)


class UpdateShareBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateShareRequestSchema, context="body")


class UpdateShare(ProviderShare):
    definitions = {
        "UpdateShareRequestSchema": UpdateShareRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateShareBodyRequestSchema)
    parameters_schema = UpdateShareRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update share

        To add a grant use action=add and set access_level, access_type and access_to.
        To remove a grant use action=del and set access_id
        """
        return self.update_resource(controller, oid, data)


class DeleteShare(ProviderShare):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete share
        """
        return self.expunge_resource(controller, oid)


class ShareProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/shares" % base, "GET", ListShares, {}),
            ("%s/shares" % base, "POST", CreateShare, {}),
            ("%s/shares/<oid>" % base, "GET", GetShare, {}),
            ("%s/shares/<oid>" % base, "PUT", UpdateShare, {}),
            ("%s/shares/<oid>" % base, "DELETE", DeleteShare, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
