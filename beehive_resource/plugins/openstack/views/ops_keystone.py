# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    GetApiObjectRequestSchema,
    SwaggerApiView,
    ApiManagerError,
)


class SystemIdentityGetRequestSchema(GetApiObjectRequestSchema):
    entity = fields.String(required=True, description="entity type", context="path")
    name = fields.String(required=False, description="entity name", context="query")


class SystemIdentityGetResponseSchema(Schema):
    api = fields.Dict()
    roles = fields.List(fields.Dict)
    users = fields.List(fields.Dict)
    groups = fields.List(fields.Dict)
    policies = fields.List(fields.Dict)
    credentials = fields.List(fields.Dict)
    regions = fields.List(fields.Dict)


class SystemIdentityGet(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemIdentityGetRequestSchema": SystemIdentityGetRequestSchema,
        "SystemIdentityGetResponseSchema": SystemIdentityGetResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SystemIdentityGetRequestSchema)
    parameters_schema = SystemIdentityGetRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": SystemIdentityGetResponseSchema}}
    )

    def get(self, controller, data, oid, entity, *args, **kwargs):
        container = self.get_container(controller, oid)

        name = data.get("name", None)

        if entity == "api":
            resp = container.keystone.api()

        # get keystone roles
        elif entity == "roles":
            resp = container.keystone.get_roles(name=name)

        # get keystone users
        elif entity == "users":
            resp = container.keystone.get_users(name=name)

        # get keystone groups
        elif entity == "groups":
            resp = container.keystone.get_groups()

        # get keystone policies
        elif entity == "policies":
            resp = container.keystone.get_policies()

        # get keystone policies
        elif entity == "credentials":
            resp = container.keystone.get_credentials()

        # get keystone policies
        elif entity == "regions":
            resp = container.keystone.get_regions()

        else:
            raise ApiManagerError("Api request not supported", code=400)

        return {entity: resp}


class OpenstackKeystoneAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/<oid>/keystone/<entity>" % base, "GET", SystemIdentityGet, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
