# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    ApiGraphResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from networkx.readwrite import json_graph


class VsphereNsxManagerApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = NsxManager
    parentclass = None


class ListNsxManagersRequestSchema(ListResourcesRequestSchema):
    pass


class ListNsxManagersParamsResponseSchema(ResourceResponseSchema):
    pass


class ListNsxManagersResponseSchema(PaginatedResponseSchema):
    nsxs = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListNsxManagers(VsphereNsxManagerApiView):
    definitions = {
        "ListNsxManagersResponseSchema": ListNsxManagersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxManagersRequestSchema)
    parameters_schema = ListNsxManagersRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListNsxManagersResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List nsx manager
        List nsx manager

        {
            'currentLoggedInUser': 'admin',
            'versionInfo': {
                'buildNumber': '3300239',
                'majorVersion': '6',
                'minorVersion': '2',
                'patchVersion': '1'
            }
        }
        """
        return self.get_resources(controller, **data)


class GetNsxManagerResponseSchema(Schema):
    nsx = fields.Dict(required=True, example={})


class GetNsxManager(VsphereNsxManagerApiView):
    definitions = {
        "GetNsxManagerResponseSchema": GetNsxManagerResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetNsxManagerResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx manager
        Get nsx manager

        {
            'applianceName': 'vShield Virtual Appliance Management',
            'cpuInfoDto': {
                'capacity': '3058 MHZ',
                'freeCapacity': '3023 MHZ',
                'totalNoOfCPUs': 4,
                'usedCapacity': '35 MHZ',
                'usedPercentage': 1
            },
            'currentSystemDate': 'Monday, 19 September 2016 12:54:16 PM CEST',
            'domainName': '2.1',
            'hostName': 'NSX-Manager-6',
            'ipv4Address': '172.25.3.3',
            'ipv6Address': None,
            'memInfoDto': {
                'freeMemory': '6953 MB',
                'totalMemory': '16025 MB',
                'usedMemory': '9072 MB',
                'usedPercentage': 57
            },
            'server': {
                'ext_id': 'vm-83',
                'id': 1053,
                'name': 'NSX-Manager-6.2.1',
                'uri': '/v1.0/resource/vsphere/14/server/1053/'
            },
            'storageInfoDto': {
                'freeStorage': '64G',
                'totalStorage': '86G',
                'usedPercentage': 26,
                'usedStorage': '22G'
            },
            'uptime': '15 days, 12 hours, 31 minutes',
            'versionInfo': {
                'buildNumber': '3300239',
                'majorVersion': '6',
                'minorVersion': '2',
                'patchVersion': '1'
            }
        }
        """
        return self.get_resource(controller, oid)


class ListNsxManagerComponentsParamsResponseSchema(Schema):
    componentGroup = fields.String(required=True, example="SYSTEM")
    componentId = fields.String(required=True, example="SSH")
    description = fields.String(required=True, example="Secure Shell")
    enabled = fields.Boolean(required=True, example=True)
    name = fields.String(required=True, example="SSH Service")
    showTechSupportLogs = fields.Boolean(required=True, example=False)
    status = fields.String(required=True, example="RUNNING")
    usedBy = fields.List(fields.String(), required=True, example=[], allow_none=True)
    uses = fields.List(fields.String(), required=True, example=[], allow_none=True)
    versionInfo = fields.Dict(required=True, example={}, allow_none=True)


class ListNsxManagerComponentsResponseSchema(Schema):
    count = fields.Integer(required=True, default=10, example=10)
    nsx_components = fields.Nested(
        ListNsxManagerComponentsParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListNsxManagerComponents(VsphereNsxManagerApiView):
    definitions = {
        "ListNsxManagerComponentsResponseSchema": ListNsxManagerComponentsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": ListNsxManagerComponentsResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        manager = self.get_resource_reference(controller, oid)
        resp = manager.get_manager_components()
        return {"nsx_components": resp, "count": len(resp)}


class ListNsxManagerEventsRequestSchema(GetApiObjectRequestSchema):
    page = fields.Integer(
        required=False,
        missing=0,
        example=0,
        context="query",
        description="start index is an optional parameter which specifies the starting point for "
        "retrieving the logs. If this parameter is not specified, logs are retrieved "
        "from the beginning.",
    )
    size = fields.Integer(
        required=False,
        missing=20,
        example=20,
        context="query",
        description="page size is an optional parameter that limits the maximum number of entries "
        "returned by the API. The default value for this parameter is 256 and the valid "
        "range is 1-1024.",
    )


class ListNsxManagerEventsResponseSchema(PaginatedResponseSchema):
    nsx_events = fields.List(fields.Dict, required=True, allow_none=True)


class ListNsxManagerEvents(VsphereNsxManagerApiView):
    definitions = {
        "ListNsxManagerEventsRequestSchema": ListNsxManagerEventsRequestSchema,
        "ListNsxManagerEventsResponseSchema": ListNsxManagerEventsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxManagerEventsRequestSchema)
    parameters_schema = ListNsxManagerEventsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListNsxManagerEventsResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List nsx manager events
        List nsx managers events

        [
            {
                'eventCode': '30148',
                'eventId': '96883',
                'eventMetadata': {
                    'data': [
                    {'key': 'message', 'value': 'CPU usage: 92.94%'},..
                    ]
                },
                'eventSource': 'edge-358',
                'isResourceUniversal': 'false',
                'message': 'NSX Edge CPU usage has ..',
                'module': 'vShield Edge Appliance',
                'objectId': 'vm-606',
                'reporterName': 'vShield Manager',
                'reporterType': '4',
                'severity': 'Critical',
                'sourceType': '4',
                'timestamp': '1474152543000'
            },..
        ]
        """
        manager = self.get_resource_reference(controller, oid)
        resp = manager.get_system_events(start_index=data.get("page", 0), page_size=data.get("size", 20))
        paging = resp.get("pagingInfo")
        res = resp.get("systemEvent")
        order = "ASC"
        if paging.get("sortOrderAscending") == "false":
            order = "DESC"
        return {
            "nsx_events": res,
            "count": len(res),
            "page": int(paging.get("pageSize")),
            "total": int(paging.get("totalCount")),
            "sort": {"field": "eventId", "order": order},
        }


class ListNsxManagerAuditsRequestSchema(GetApiObjectRequestSchema):
    page = fields.Integer(
        required=False,
        missing=0,
        example=0,
        context="query",
        description="start index is an optional parameter which specifies the starting point for "
        "retrieving the logs. If this parameter is not specified, logs are retrieved "
        "from the beginning.",
    )
    size = fields.Integer(
        required=False,
        missing=20,
        example=20,
        context="query",
        description="page size is an optional parameter that limits the maximum number of entries "
        "returned by the API. The default value for this parameter is 256 and the valid "
        "range is 1-1024.",
    )


class ListNsxManagerAuditsResponseSchema(PaginatedResponseSchema):
    nsx_audits = fields.List(fields.Dict, required=True, allow_none=True)


class ListNsxManagerAudits(VsphereNsxManagerApiView):
    definitions = {
        "ListNsxManagerAuditsResponseSchema": ListNsxManagerAuditsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListNsxManagerAuditsRequestSchema)
    parameters_schema = ListNsxManagerAuditsRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListNsxManagerAuditsResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List nsx manager events
        List nsx managers events

        [
            {
                'id': '970860',
                'isResourceUniversal': 'false',
                'module': 'ACCESS_CONTROL',
                'operation': 'LOGIN',
                'resource': 'admin',
                'resourceId': 'userinfo-3',
                'status': 'SUCCESS',
                'timestamp': '1474289184780',
                'userName': 'System'
            },..
        ]
        """
        manager = self.get_resource_reference(controller, oid)
        resp = manager.get_system_audit_logs(start_index=data.get("page", 0), page_size=data.get("size", 20))
        paging = resp.get("pagingInfo")
        res = resp.get("auditLog")
        order = "ASC"
        if paging.get("sortOrderAscending") == "false":
            order = "DESC"
        return {
            "nsx_audits": res,
            "count": len(res),
            "page": int(paging.get("pageSize")),
            "total": int(paging.get("totalCount")),
            "sort": {"field": "id", "order": order},
        }


class ListNsxManagerControllersResponseSchema(Schema):
    count = fields.Integer(required=True, default=10, example=10)
    nsx_controllers = fields.List(fields.Dict(), required=True)


class ListNsxManagerControllers(VsphereNsxManagerApiView):
    definitions = {
        "ListNsxManagerControllersResponseSchema": ListNsxManagerControllersResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": ListNsxManagerControllersResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List nsx manager controllers
        Retrieves details and runtime status for controller.
        Runtime status can be one of the following:
        - Deploying: controller is being deployed and the procedure has not completed yet.
        - Removing: controller is being removed and the procedure has not completed yet.
        - Running: controller has been deployed and can respond to API invocation.
        - Unknown: controller has been deployed but fails to respond to API invocation.

        [{'clientHandle': None,
          'clusterInfo': {'clientHandle': None,
                           'extendedAttributes': None,
                           'isUniversal': 'false',
                           'name': 'MGMT_Cluster',
                           'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                           'objectId': 'domain-c40',
                           'objectTypeName': 'ClusterComputeResource',
                           'revision': '308',
                           'scope': {'id': 'datacenter-2', 'name': 'Datacenter_NuvolaCSI', 'objectTypeName': 'Datacenter'},
                           'type': {'typeName': 'ClusterComputeResource'},
                           'universalRevision': '0',
                           'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'},
          'controllerClusterStatus': None,
          'datastoreInfo': {'clientHandle': None,
                             'extendedAttributes': None,
                             'isUniversal': 'false',
                             'name': 'Local_lab1-1',
                             'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                             'objectId': 'datastore-24',
                             'objectTypeName': 'Datastore',
                             'revision': '1',
                             'type': {'typeName': 'Datastore'},
                             'universalRevision': '0',
                             'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'},
          'hostInfo': {'clientHandle': None,
                        'extendedAttributes': None,
                        'isUniversal': 'false',
                        'name': 'esx-lab1-1.nuvolacsi.it',
                        'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                        'objectId': 'host-23',
                        'objectTypeName': 'HostSystem',
                        'revision': '1791',
                        'scope': {'id': 'domain-c40', 'name': 'MGMT_Cluster', 'objectTypeName': 'ClusterComputeResource'},
                        'type': {'typeName': 'HostSystem'},
                        'universalRevision': '0',
                        'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'},
          'id': 'controller-9',
          'ipAddress': '172.25.3.230',
          'isUniversal': 'false',
          'managedBy': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055',
          'resourcePoolInfo': {'clientHandle': None,
                                'extendedAttributes': None,
                                'isUniversal': 'false',
                                'name': 'Resources',
                                'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                                'objectId': 'resgroup-41',
                                'objectTypeName': 'ResourcePool',
                                'revision': '148',
                                'scope': {'id': 'domain-c40', 'name': 'MGMT_Cluster', 'objectTypeName': 'ClusterComputeResource'},
                                'type': {'typeName': 'ResourcePool'},
                                'universalRevision': '0',
                                'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'},
          'revision': '0',
          'status': 'RUNNING',
          'universalRevision': '0',
          'upgradeAvailable': 'true',
          'upgradeStatus': 'NOT_STARTED',
          'version': '6.2.45566',
          'virtualMachineInfo': {'clientHandle': None,
                                  'extendedAttributes': None,
                                  'isUniversal': 'false',
                                  'name': 'NSX_Controller_db83ca66-b8fd-4a84-8c3e-b2b7e884d154',
                                  'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                                  'objectId': 'vm-1163',
                                  'objectTypeName': 'VirtualMachine',
                                  'revision': '13',
                                  'scope': {'id': 'domain-c40', 'name': 'MGMT_Cluster', 'objectTypeName': 'ClusterComputeResource'},
                                  'type': {'typeName': 'VirtualMachine'},
                                  'universalRevision': '0',
                                  'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'}}}]
        """
        manager = self.get_resource_reference(controller, oid)
        resp = manager.get_controllers()
        return {"nsx_controllers": resp, "count": len(resp)}


class ListNsxManagerTransportZoneResponseSchema(Schema):
    count = fields.Integer(required=True, default=10, example=10)
    nsx_transport_zones = fields.List(fields.Dict(), required=True)


class ListNsxManagerTransportZone(VsphereNsxManagerApiView):
    definitions = {
        "ListNsxManagerTransportZoneResponseSchema": ListNsxManagerTransportZoneResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": ListNsxManagerTransportZoneResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List nsx manager events
        List nsx managers events

        [{'clusters': [{'clientHandle': None,
                         'extendedAttributes': None,
                         'isUniversal': 'false',
                         'name': 'MGMT_Cluster',
                         'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                         'objectId': 'domain-c40',
                         'objectTypeName': 'ClusterComputeResource',
                         'revision': '308',
                         'scope': {'id': 'datacenter-2', 'name': 'Datacenter_NuvolaCSI', 'objectTypeName': 'Datacenter'},
                         'type': {'typeName': 'ClusterComputeResource'},
                         'universalRevision': '0',
                         'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'},
                        {'clientHandle': None,
                         'extendedAttributes': None,
                         'isUniversal': 'false',
                         'name': 'CARBON_Cluster',
                         'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                         'objectId': 'domain-c44',
                         'objectTypeName': 'ClusterComputeResource',
                         'revision': '262',
                         'scope': {'id': 'datacenter-2', 'name': 'Datacenter_NuvolaCSI', 'objectTypeName': 'Datacenter'},
                         'type': {'typeName': 'ClusterComputeResource'},
                         'universalRevision': '0',
                         'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'}],
          'details': {'clientHandle': None,
                       'controlPlaneMode': 'UNICAST_MODE',
                       'description': None,
                       'extendedAttributes': None,
                       'isUniversal': 'false',
                       'nodeId': '4d15227a-244e-41a0-9a0f-453ea93daef3',
                       'objectId': 'vdnscope-1',
                       'objectTypeName': 'VdnScope',
                       'revision': '3',
                       'type': {'typeName': 'VdnScope'},
                       'universalRevision': '0',
                       'virtualWireCount': '14',
                       'vsmUuid': '4226DA33-0ACB-65B7-D8D0-49BC2F1CB055'},
          'ext_id': 'vdnscope-1',
          'id': 'vdnscope-1',
          'name': 'nuovotir'},..
        ]
        """
        manager = self.get_resource_reference(controller, oid)
        resp = manager.get_transport_zones()
        return {"nsx_transport_zones": resp, "count": len(resp)}


class GetSecurityGroupsGraphResponseSchema(Schema):
    nsx_security_group_graph = fields.Nested(ApiGraphResponseSchema, required=True, allow_none=True)


class GetSecurityGroupsGraph(VsphereNsxManagerApiView):
    definitions = {
        "GetSecurityGroupsGraphResponseSchema": GetSecurityGroupsGraphResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetSecurityGroupsGraphResponseSchema,
            }
        }
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx_security_group graph
        Get nsx_security_group graph

        node syntax:
        {
            'attributes': '',
            'container': 14,
            'id': 929,
            'label': 'vSphere nsx vsphere_test1 secur...',
            'name': 'default (2e053df8-fec5-44be-a716-ee68e71dac27)',
            'type': 'vsphere.nsx.security_group',
            'uri': '/v1.0/resource/nsx/14/security_group/929/'
        }
        """
        manager = self.get_resource_reference(controller, oid)
        obj = manager.get_security_groups_graph()
        resp = json_graph.node_link_data(obj)
        return {"nsx_security_group_graph": resp}


class GetSecurityGroupsTreeResponseSchema(Schema):
    nsx_security_group_tree = fields.Dict(required=True)


class GetSecurityGroupsTree(VsphereNsxManagerApiView):
    definitions = {
        "GetSecurityGroupsTreeResponseSchema": GetSecurityGroupsTreeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetSecurityGroupsTreeResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get nsx_security_group tree
        Get nsx_security_group tree

        {
            'attributes': '',
            'children': [{'attributes': '',
                           'children': [{'attributes': '',
                                          'container': 14,
                                          'id': 929,
                                          'label': 'vSphere nsx vsphere_test1 security group default (2e053df8-fec5-44be-a716-ee68e71dac27)',
                                          'name': 'default (2e053df8-fec5-44be-a716-ee68e71dac27)',
                                          'size': 1,
                                          'type': 'vsphere.nsx.security_group',
                                          'uri': '/v1.0/resource/nsx/14/security_group/929/'},
                                         ...],
                           'container': 14,
                           'id': 897,
                           'label': 'vSphere nsx vsphere_test1 security group OpenStack Security Group container',
                           'name': 'OpenStack Security Group container',
                           'size': 1,
                           'type': 'vsphere.nsx.security_group',
                           'uri': '/v1.0/resource/nsx/14/security_group/897/'},
                          ...],
            'container': '',
            'id': 0,
            'label': 'root',
            'name': 'root',
            'size': 1,
            'type': '',
            'uri': ''
        }
        """
        manager = self.get_resource_reference(controller, oid)
        obj = manager.get_security_groups_tree()
        resp = json_graph.tree_data(obj, root=0)
        return {"nsx_security_group_tree": resp}


class VsphereNsxManagerAPI(VsphereAPI):
    """Vsphere nsx manager platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + "/network"
        rules = [
            ("%s/nsxs" % base, "GET", ListNsxManagers, {}),
            ("%s/nsxs/<oid>" % base, "GET", GetNsxManager, {}),
            ("%s/nsxs/<oid>/components" % base, "GET", ListNsxManagerComponents, {}),
            ("%s/nsxs/<oid>/events" % base, "GET", ListNsxManagerEvents, {}),
            ("%s/nsxs/<oid>/audits" % base, "GET", ListNsxManagerAudits, {}),
            ("%s/nsxs/<oid>/controllers" % base, "GET", ListNsxManagerControllers, {}),
            (
                "%s/nsxs/<oid>/transport_zones" % base,
                "GET",
                ListNsxManagerTransportZone,
                {},
            ),
            (
                "%s/nsxs/<oid>/security_groups_graph" % base,
                "GET",
                GetSecurityGroupsGraph,
                {},
            ),
            (
                "%s/nsxs/<oid>/security_groups_tree" % base,
                "GET",
                GetSecurityGroupsTree,
                {},
            ),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
