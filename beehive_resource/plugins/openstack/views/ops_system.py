# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive.common.apimanager import (
    ApiManagerError,
    SwaggerApiView,
    GetApiObjectRequestSchema,
)
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper


class SystemTreeParamsResponseSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    size = fields.Integer(required=True)
    type = fields.String(required=True)
    uri = fields.String(required=True)
    children = fields.List(fields.Dict, required=True, allow_none=True)


class SystemTreeResponseSchema(Schema):
    tree = fields.Nested(SystemTreeParamsResponseSchema, many=True, allow_none=True)


class SystemTree(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemTreeResponseSchema": SystemTreeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemTreeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get container resource tree.
        Get container resource tree.
        """
        container = self.get_container(controller, oid)
        resp = container.get_system_tree()
        return resp


class SystemServicesResponseSchema(Schema):
    services = fields.List(fields.Dict(), required=True)


class SystemServices(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemServicesResponseSchema": SystemServicesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemServicesResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get container services.
        Get container services.
        """
        container = self.get_container(controller, oid)
        resp = container.system.get_services()
        return {"services": resp}


class SystemEndpointsResponseSchema(Schema):
    endpoints = fields.List(fields.Dict(), required=True)


class SystemEndpoints(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemEndpointsResponseSchema": SystemEndpointsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemEndpointsResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get container endpoints.
        Get container endpoints.
        """
        container = self.get_container(controller, oid)
        resp = container.system.get_endpoints()
        return {"endpoints": resp}


class SystemComputeRequestSchema(GetApiObjectRequestSchema):
    entity = fields.String(required=True, description="entity name", context="path")


class SystemComputeResponseSchema(Schema):
    services = fields.List(fields.Dict)
    zones = fields.List(fields.Dict)
    hosts = fields.List(fields.Dict)
    hostaggrs = fields.List(fields.Dict)
    servergroups = fields.List(fields.Dict)
    hypervisors = fields.List(fields.Dict)
    hypervisors_stats = fields.Dict()
    agents = fields.List(fields.Dict)


class SystemCompute(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemComputeRequestSchema": SystemComputeRequestSchema,
        "SystemComputeResponseSchema": SystemComputeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SystemComputeRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemComputeResponseSchema}})

    def get(self, controller, data, oid, entity, *args, **kwargs):
        """
        Get compute services, zones, hosts, hostaggrs, servergroups,
        hypervisors, hypervisors_stats, agents.
        Get compute services, zones, hosts, hostaggrs, servergroups,
        hypervisors, hypervisors_stats, agents.
        """
        container = self.get_container(controller, oid)

        # get compute services
        if entity == "services":
            resp = {entity: container.system.get_compute_services()}

        # get compute zones
        elif entity == "zones":
            resp = {entity: container.system.get_compute_zones()}

        # get compute hosts
        elif entity == "hosts":
            resp = {entity: container.system.get_compute_hosts()}

        # get compute hosts aggregates
        elif entity == "hostaggrs":
            resp = {entity: container.system.get_compute_host_aggregates()}

        # get compute server_groups
        elif entity == "servergroups":
            resp = {entity: container.system.get_compute_server_groups()}

        # get compute hypervisors
        elif entity == "hypervisors":
            resp = {entity: container.system.get_compute_hypervisors()}

        # get compute hypervisors statistics
        elif entity == "hypervisors_stats":
            resp = {entity: container.system.get_compute_hypervisors_statistics()}

        # get compute agents
        elif entity == "agents":
            resp = {entity: container.system.get_compute_agents()}

        else:
            raise ApiManagerError("Api request not supported", code=400)

        return resp


class SystemStorageRequestSchema(GetApiObjectRequestSchema):
    entity = fields.String(required=True, description="entity name", context="path")


class SystemStorageResponseSchema(Schema):
    services = fields.List(fields.Dict)


class SystemStorage(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemStorageRequestSchema": SystemStorageRequestSchema,
        "SystemStorageResponseSchema": SystemStorageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SystemStorageRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemStorageResponseSchema}})

    def get(self, controller, data, oid, entity, *args, **kwargs):
        """
        Get storage services
        Get storage services
        """
        container = self.get_container(controller, oid)

        if entity == "services":
            resp = container.system.get_storage_services()
        else:
            raise ApiManagerError("Api request not supported", code=400)

        return {"services": resp}


class SystemNetworkRequestSchema(GetApiObjectRequestSchema):
    entity = fields.String(required=True, description="entity name", context="path")


class SystemNetworkResponseSchema(Schema):
    agents = fields.List(fields.Dict)
    service_providers = fields.List(fields.Dict)


class SystemNetwork(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemNetworkRequestSchema": SystemNetworkRequestSchema,
        "SystemNetworkResponseSchema": SystemNetworkResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SystemNetworkRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemNetworkResponseSchema}})

    def get(self, controller, data, oid, entity, *args, **kwargs):
        """
        Get network agents or service_providers
        Get network agents or service_providers
        """
        container = self.get_container(controller, oid)

        if entity == "agents":
            resp = container.system.get_network_agents()
        elif entity == "service_providers":
            resp = container.system.get_network_service_providers()
        else:
            raise ApiManagerError("Api request not supported", code=400)

        return {entity: resp}


class SystemHeatRequestSchema(GetApiObjectRequestSchema):
    entity = fields.String(required=True, description="entity name", context="path")


class SystemHeatResponseSchema(Schema):
    services = fields.List(fields.Dict)


class SystemHeat(OpenstackApiView):
    tags = ["openstack"]
    definitions = {
        "SystemHeatRequestSchema": SystemHeatRequestSchema,
        "SystemHeatResponseSchema": SystemHeatResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SystemHeatRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SystemHeatResponseSchema}})

    def get(self, controller, data, oid, entity, *args, **kwargs):
        """
        Get heat services
        Get heat services
        """
        container = self.get_container(controller, oid)

        if entity == "services":
            resp = container.system.get_heat_services()
        else:
            raise ApiManagerError("Api request not supported", code=400)

        return {"services": resp}


class GetProjectDefaultQuotasResponseSchema(Schema):
    default_quotas = fields.List(fields.Dict)


class GetProjectDefaultQuotas(OpenstackApiView):
    tags = ["openstack"]
    definitions = {"GetProjectDefaultQuotasResponseSchema": GetProjectDefaultQuotasResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetProjectDefaultQuotasResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get heat services
        Get heat services
        """
        container = self.get_container(controller, oid)
        resp = container.system.get_default_quotas()

        return {"default_quotas": resp}


class OpenstackSystemAPI(OpenstackAPI):
    """Openstack base system api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/<oid>/system/tree" % base, "GET", SystemTree, {}),
            ("%s/<oid>/system/services" % base, "GET", SystemServices, {}),
            ("%s/<oid>/system/endpoints" % base, "GET", SystemEndpoints, {}),
            ("%s/<oid>/system/compute/<entity>" % base, "GET", SystemCompute, {}),
            ("%s/<oid>/system/storage/<entity>" % base, "GET", SystemStorage, {}),
            ("%s/<oid>/system/network/<entity>" % base, "GET", SystemNetwork, {}),
            ("%s/<oid>/system/heat/<entity>" % base, "GET", SystemHeat, {}),
            (
                "%s/<oid>/system/project/quotas" % base,
                "GET",
                GetProjectDefaultQuotas,
                {},
            ),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
