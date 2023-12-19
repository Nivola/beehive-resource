# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2023 Regione Piemonte

from uuid import UUID
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
)
from beehive_resource.plugins.ssh_gateway.controller import SshGatewayContainer
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    ApiManagerError,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)


class ProviderSshGateway(LocalProviderApiView):
    """
    ProviderSshGateway
    """

    resclass = None
    parentclass = None


class ActivateSshGatewayResponseSchema(Schema):
    """
    ActivateSshGatewayResponseSchema
    """

    keyMaterial = fields.String(
        required=True,
        allow_none=False,
        example="",
        description="An unencrypted PEM encoded ED private key",
    )
    commandTemplate = fields.String(
        required=True,
        allow_none=False,
        example="ssh -L ...",
        description="ssh local port forwarding sample command",
    )


class ActivateSshGatewayRequestSchema(Schema):
    """
    ActivateSshGatewayRequestSchema
    """

    user = fields.String(required=True, example="user@csi.it", description="user id")
    destination = fields.String(required=True, description="destination uuid")
    port = fields.Int(required=True, example="5432", description="destination port")


class ActivateSshGatewayBodyRequestSchema(Schema):
    """
    ActivateSshGatewayBodyRequestSchema
    """

    body = fields.Nested(ActivateSshGatewayRequestSchema, context="body")


class ActivateSshGateway(LocalProviderApiView):
    """
    ActivateSshGateway
    """

    summary = "Activate ssh gateway"
    description = "generate a keypair for user to access destination through the ssh gateway. only private key is returned to the user"
    definitions = {
        "ActivateSshGatewayRequestSchema": ActivateSshGatewayRequestSchema,
        "ActivateSshGatewayResponseSchema": ActivateSshGatewayResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ActivateSshGatewayBodyRequestSchema)
    parameters_schema = ActivateSshGatewayRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ActivateSshGatewayResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """
        activate ssh gw for user
        """
        cont: SshGatewayContainer = controller.get_containers(container_type_name=SshGatewayContainer.objdef)[0][0]
        if cont is None:
            raise ApiManagerError(f"No {SshGatewayContainer.objdef} container found")

        destination = data.pop("destination")
        dest_resource = None
        fqdn = None

        try:
            UUID(destination, version=4)
        except ValueError:
            # assume destination is a fqdn
            fqdn = destination

        if not fqdn:
            # otherwise db or vm
            dest_resource = controller.get_resource(destination)
            if dest_resource.objdef != ComputeInstance.objdef:
                # not a vm. get associated vm
                linked_resource, _ = dest_resource.get_linked_resources(type=ComputeInstance.objdef)
                linked_resource = linked_resource[0]
                dest_resource = linked_resource
            try:
                fqdn = dest_resource.get_attribs().get("fqdn")
            except ValueError as ex:
                raise ApiManagerError(f"Can't find fqdn: {ex}") from ex

        data["fqdn"] = fqdn
        key_material, command_template = cont.activate_for_user(**data)
        return {"keyMaterial": key_material, "commandTemplate": command_template}


class SshGatewayProviderAPI(ProviderAPI):
    """
    SshGatewayProviderAPI
    """

    @staticmethod
    def register_api(module, **kwargs):
        """
        register_api
        """
        base = ProviderAPI.base
        rules = [(f"{base}/ssh_gateway/activate", "POST", ActivateSshGateway, {})]
        kwargs["version"] = "v1.0"
        ProviderAPI.register_api(module, rules, **kwargs)
