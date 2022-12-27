# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, GetApiObjectRequestSchema
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter


class VsphereClusterApiView(VsphereApiView):
    tags = ['vsphere']
    resclass = VsphereCluster
    parentclass = VsphereDatacenter


class ListClustersRequestSchema(ListResourcesRequestSchema):
    pass


class ListClustersResponseSchema(PaginatedResponseSchema):
    clusters = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListClusters(VsphereClusterApiView):
    definitions = {
        'ListClustersResponseSchema': ListClustersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListClustersRequestSchema)
    parameters_schema = ListClustersRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListClustersResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List cluster
        List cluster
        """
        return self.get_resources(controller, **data)

## get
class GetClusterResponseSchema(Schema):
    cluster = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)

class GetCluster(VsphereClusterApiView):
    definitions = {
        'GetClusterResponseSchema': GetClusterResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetClusterResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get cluster
        Get cluster
        """
        return self.get_resource(controller, oid)

class VsphereClusterAPI(VsphereAPI):
    """Vsphere base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base
        rules = [
            ('%s/clusters' % base, 'GET', ListClusters, {}),
            ('%s/clusters/<oid>' % base, 'GET', GetCluster, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
