# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import logging

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from flasgger import fields, Schema
from marshmallow.decorators import validates_schema
from marshmallow.exceptions import ValidationError
from marshmallow.validate import OneOf

from beecell.swagger import SwaggerHelper

logger = logging.getLogger(__name__)


class OpenstackNetworkApiView(OpenstackApiView):
    resclass = OpenstackNetwork
    parentclass = OpenstackProject


class ListNetworksRequestSchema(ListResourcesRequestSchema):
    segmentation_id = fields.Integer(
        example=345,
        context="query",
        description="[optional] An isolated segment on the "
        "physical network. The network_type attribute defines the segmentation model. For "
        "example, if the network_type value is vlan, this ID is a vlan identifier. If the "
        "network_type value is gre, this ID is a gre key",
    )
    shared = fields.Boolean(
        context="query",
        example=False,
        description="Indicates whether this network is shared "
        "across all tenants. By default, only administrative users can change this value",
    )
    external = fields.Boolean(
        context="query",
        example=False,
        description="Indicates whether this network is " "externally accessible",
    )

    @validates_schema
    def validate_networks(self, data, *args, **kvargs):
        keys = data.keys()
        if "segmentation_id" in keys or "shared" in keys or "external" in keys:
            if "container" not in keys:
                raise ValidationError(
                    "container is required when segmentation_id, shared or esternal are used as " "filter"
                )


class ListNetworksParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNetworksResponseSchema(PaginatedResponseSchema):
    networks = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNetworks(OpenstackNetworkApiView):
    tags = ["openstack"]
    definitions = {
        "ListNetworksResponseSchema": ListNetworksResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNetworksRequestSchema)
    parameters_schema = ListNetworksRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListNetworksResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List network
        List network
        """
        return self.get_resources(controller, **data)


class GetNetworkResponseSchema(Schema):
    network = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetNetwork(OpenstackNetworkApiView):
    tags = ["openstack"]
    definitions = {
        "GetNetworkResponseSchema": GetNetworkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetNetworkResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get network
        Get network
        """
        return self.get_resource(controller, oid)


class CreateNetworkParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test", description="Name")
    desc = fields.String(required=False, example="test", default="", description="Description")
    tags = fields.String(default="", example="tag1,tag2", description="Comma separated list of tags")
    shared = fields.Boolean(
        default=False,
        example=False,
        description="Indicates whether this network is shared across "
        "all tenants. By default, only administrative users can change this value",
    )
    external = fields.Boolean(
        default=False,
        example=False,
        description="Indicates whether this network is externally " "accessible",
    )
    project = fields.String(
        default="12",
        example="12",
        required=True,
        description="The id or uuid of the project that " "owns the network",
    )
    qos_policy_id = fields.UUID(
        allow_none=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="The openstack UUID of the QoS policy associated with this network. The "
        "policy will need to have been created before the network to associate it "
        "with",
    )
    segments = fields.String(allow_none=True, example="", description="A list of provider segment objects")
    physical_network = fields.String(
        default="vs1",
        example="vs1",
        required=False,
        description="[optional] The physical network where this network  object is "
        "implemented. The Networking API v2.0 does not provide a  way to list "
        "available physical networks. For example, the Open vSwitch plug-in "
        "configuration file defines a symbolic name that maps to specific "
        "bridges on each Compute host",
    )
    network_type = fields.String(
        default="vxlan",
        example="vlan",
        description="[default=vlan] The type of physical "
        "network that maps to this network resource. For example, flat, vlan, vxlan, or gre",
        validate=OneOf(["vlan", "vxlan", "gre", "flat"]),
    )
    segmentation_id = fields.Integer(
        example=345,
        allow_none=True,
        description="[optional] An isolated segment on he "
        "physical network.  The network_type attribute defines the segmentation model. "
        "For example, if the network_type value is vlan, this ID is a vlan identifier. "
        "If the network_type value is gre, this ID is a gre key",
    )


class CreateNetworkRequestSchema(Schema):
    network = fields.Nested(CreateNetworkParamRequestSchema)


class CreateNetworkBodyRequestSchema(Schema):
    body = fields.Nested(CreateNetworkRequestSchema, context="body")


class CreateNetwork(OpenstackNetworkApiView):
    tags = ["openstack"]
    definitions = {
        "CreateNetworkRequestSchema": CreateNetworkRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateNetworkBodyRequestSchema)
    parameters_schema = CreateNetworkRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create network
        Create network
        """
        return self.create_resource(controller, data)


class UpdateNetworkParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    shared = fields.Boolean(
        default=False,
        example=False,
        description="Indicates whether this network is shared across "
        "all tenants. By default, only administrative users can change this value",
    )
    external = fields.Boolean(
        default=False,
        example=False,
        description="Indicates whether this network is externally " "accessible",
    )
    qos_policy_id = fields.UUID(
        allow_none=True,
        example="4cdf0ea4-159a-45aa-96f2-708e461130e1",
        description="The openstack UUID of the QoS policy associated with this network. The "
        "policy will need to have been created before the network to associate it "
        "with",
    )
    segments = fields.String(allow_none=True, example="", description="A list of provider segment objects")


class UpdateNetworkRequestSchema(Schema):
    network = fields.Nested(UpdateNetworkParamRequestSchema)


class UpdateNetworkBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateNetworkRequestSchema, context="body")


class UpdateNetwork(OpenstackNetworkApiView):
    tags = ["openstack"]
    definitions = {
        "UpdateNetworkRequestSchema": UpdateNetworkRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateNetworkBodyRequestSchema)
    parameters_schema = UpdateNetworkRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update network
        Update network
        """
        return self.update_resource(controller, oid, data)


class DeleteNetwork(OpenstackNetworkApiView):
    tags = ["openstack"]
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class OpenstackNetworkAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/networks" % base, "GET", ListNetworks, {}),
            ("%s/networks/<oid>" % base, "GET", GetNetwork, {}),
            ("%s/networks" % base, "POST", CreateNetwork, {}),
            ("%s/networks/<oid>" % base, "PUT", UpdateNetwork, {}),
            ("%s/networks/<oid>" % base, "DELETE", DeleteNetwork, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
