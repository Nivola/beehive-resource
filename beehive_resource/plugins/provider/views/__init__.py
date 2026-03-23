# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from typing import TYPE_CHECKING, List

from beehive_resource.view import (
    CreateResourceBaseRequestSchema,
    ResourceApiView,
)

from beehive_resource.views.entity import ResourceApiView as ResourceApiViewV2
from flasgger import fields, Schema
from marshmallow import validates_schema, ValidationError
from marshmallow.validate import OneOf
from beehive.common.apimanager import ApiView
from beehive_resource.plugins.provider.controller import LocalProvider

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController
    from beehive_resource.container import ResourceContainer


class LocalProviderApiView(ResourceApiView):
    tags = ["provider"]
    containerclass = LocalProvider

    def get_resource(self, controller: 'ResourceController', oid, alternative_name=None):
        """ """
        containers: List['LocalProvider']
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        print_name = self.resclass.objname
        if alternative_name is not None:
            print_name = alternative_name
        resp = {print_name: res.detail()}
        return resp

    def update_resource(self, controller: 'ResourceController', oid, data):
        """ """
        containers: List['LocalProvider']
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        obj = container.get_resource(oid, entity_class=self.resclass)
        data = data.get(self.resclass.objname)
        res = obj.update(**data)
        return res

    def patch_resource(self, controller: 'ResourceController', oid, data):
        """ """
        containers: List['LocalProvider']
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        obj = container.get_resource(oid, entity_class=self.resclass)
        res = obj.do_patch(**data)
        return res


class LocalProviderApiViewV2(ResourceApiViewV2):
    tags = ["provider"]
    containerclass = LocalProvider

    def get_resource(self, controller: 'ResourceController', oid, alternative_name=None):
        """ """
        containers: List['LocalProvider']
        containers, tot = controller.get_containers(container_type="Provider")
        container = containers[0]
        res = container.get_resource(oid, entity_class=self.resclass)
        print_name = self.resclass.objname
        if alternative_name is not None:
            print_name = alternative_name
        resp = {print_name: res.detail()}
        return resp


class ProviderAPI(ApiView):
    """ """

    base = "nrs/provider"


class CreateProviderResourceRequestSchema(CreateResourceBaseRequestSchema):
    """
    :desc: resource description
    :orchestrator_tag: orchestrator tag
    """

    desc = fields.String(
        required=True,
        metadata={
            "example": 'test',
            "description": 'The resource description',
        },
    )

    orchestrator_tag = fields.String(
        required=False,
        load_default="default",
        metadata={
            "description": (
                'orchestrator tag. Use to select a subset of orchestrators where security group must be created.'
            ),
        },
    )


class UpdateProviderResourceRequestSchema(Schema):
    name = fields.String(
        metadata={
            "example": 'test',
        },
    )

    desc = fields.String(
        required=False,
        metadata={
            "example": 'test',
            "description": 'The resource description',
        },
    )

    orchestrator_tag = fields.String(
        required=False,
        load_default="default",
        metadata={
            "description": (
                'orchestrator tag. Use to select a subset of orchestrators where security group must be created.'
            ),
        },
    )

class ProviderComplianceRequestParams(Schema):
    """
    base schema for compliance request params.
    This should refer to a sort of "backup" that is
    invisible to and untouchable by the end user
    and meet all the security requirements

    :compliance: whether or not we are being "compliant" with cloud requirements
    :compliance_site: site where the compliance "object" is
    :compliance_rpo: recovery point objective
    """
    compliance = fields.Bool(
        required=True,
        metadata={
            "description": "whether or not we are being 'compliant' with cloud requirements",
        },
    )

    compliance_rpo = fields.String(
        required=False,
        validate=OneOf(['12h', '24h']),
        metadata={
            "description": 'compliance rpo',
        },
    )


    @validates_schema
    def validate_compliance_site(self, data, **kwargs):
        if data.get('compliance') and not data.get("compliance_rpo"):
            raise ValidationError('compliance_rpo is required when compliance is True.', 'compliance_rpo')
