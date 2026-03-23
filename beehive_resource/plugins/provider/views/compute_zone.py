# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from typing import TYPE_CHECKING

from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiJobResponseSchema,
    CrudApiObjectTaskResponseSchema,
    CrudApiObjectSimpleResponseSchema,
    ApiObjectResponseSchema,
    PaginatedRequestQuerySchema,
    ApiManagerError,
)

from beehive_resource.plugins.provider.entity.zone import ComputeZone

from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)

from beehive_resource.view import (
    ListResourcesRequestSchema,
    ResourceResponseSchema,
    ResourceSmallResponseSchema,
    GetResourceMetricsResponseSchema,
)

from flasgger import fields, Schema

from beecell.swagger import SwaggerHelper
import random
from beecell.types.type_dict import dict_get

if TYPE_CHECKING:
    from beehive_resource.controller import ResourceController


class ProviderComputeZone(LocalProviderApiView):
    resclass = ComputeZone


class ListComputeZonesRequestSchema(ListResourcesRequestSchema):
    pass


class ListComputeZonesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListComputeZonesResponseSchema(PaginatedResponseSchema):
    compute_zones = fields.Nested(
        ListComputeZonesParamsResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class ListComputeZones(ProviderComputeZone):
    definitions = {"ListComputeZonesResponseSchema": ListComputeZonesResponseSchema}
    parameters = SwaggerHelper().get_parameters(ListComputeZonesRequestSchema)
    parameters_schema = ListComputeZonesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {"description": "success", "schema": ListComputeZonesResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, *args, **kwargs):
        """
        List compute_zones

        "attributes": {
          "configs": {},
          "quota": {

          }
        }
        """
        return self.get_resources(controller, **data)


class GetComputeZoneParamsResponseSchema(ResourceResponseSchema):
    availability_zones = fields.Nested(
        ResourceSmallResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetComputeZoneResponseSchema(Schema):
    compute_zone = fields.Nested(
        GetComputeZoneParamsResponseSchema,
        required=True,
        allow_none=True,
    )


class GetComputeZone(ProviderComputeZone):
    definitions = {"GetComputeZoneResponseSchema": GetComputeZoneResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetComputeZoneResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Get compute_zone

        "attributes": {
          "configs": {},
          "quota": {

          }
        }
        """
        return self.get_resource(controller, oid)


class CreateComputeZoneParamRequestSchema(CreateProviderResourceRequestSchema):
    quota = fields.Dict(
        required=True,
        allow_none=True,
        metadata={
            "description": 'allocation quota',
        },
    )

    managed = fields.Boolean(
        required=False,
        load_default=True,
        metadata={
            "description": 'set management with ssh group',
        },
    )

    managed_by = fields.String(
        required=False,
        load_default=None,
        metadata={
            "description": 'set user or group that as role master in ssh group',
        },
    )


class CreateComputeZoneRequestSchema(Schema):
    compute_zone = fields.Nested(CreateComputeZoneParamRequestSchema)


class CreateComputeZoneBodyRequestSchema(Schema):
    body = fields.Nested(
        CreateComputeZoneRequestSchema,
        context="body",
    )


class CreateComputeZone(ProviderComputeZone):
    definitions = {
        "CreateComputeZoneRequestSchema": CreateComputeZoneRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(CreateComputeZoneBodyRequestSchema)
    parameters_schema = CreateComputeZoneRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller: 'ResourceController', data, *args, **kwargs):
        """
        Create compute_zone
        * **quota**: quota
            * **compute.instances**: 2
            * **compute.images**: 2
            * **compute.volumes**: 2
            * **compute.blocks**: 1024
            * **compute.ram**: 10
            * **compute.cores**: 4
            * **compute.networks**: 2
            * **compute.floatingips**: 2
            * **compute.security_groups**: 2
            * **compute.security_group_rules**: 10
            * **compute.keypairs**: 2
            * **database.instances**: 2
            * **share.instances**: 2
            * **appengine.instances**: 2
        """
        return self.create_resource(controller, data)


class UpdateComputeZoneParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateComputeZoneRequestSchema(Schema):
    compute_zone = fields.Nested(UpdateComputeZoneParamRequestSchema)


class UpdateComputeZoneBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateComputeZoneRequestSchema, context="body")


class UpdateComputeZone(ProviderComputeZone):
    definitions = {
        "UpdateComputeZoneRequestSchema": UpdateComputeZoneRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateComputeZoneBodyRequestSchema)
    parameters_schema = UpdateComputeZoneRequestSchema

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Update compute_zone
        """
        return self.update_resource(controller, oid, data)


class DeleteComputeZone(ProviderComputeZone):
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Delete compute_zone
        """
        return self.expunge_resource(controller, oid)


class ListSiteResponseSchema(Schema):
    availability_zones = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class ListSite(ProviderComputeZone):
    definitions = {"ListSiteResponseSchema": ListSiteResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListSiteResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        List site to compute zone
        """
        obj: 'ComputeZone' = self.get_resource_reference(controller, oid)
        res = [z.info() for z in obj.get_availability_zones()]
        return {"availability_zones": res, "count": len(res)}


class AddSiteParamRequestSchema(UpdateProviderResourceRequestSchema):
    quota = fields.Dict(
        required=False,
        allow_none=True,
        load_default=None,
        metadata={
            "description": 'allocation quota',
        },
    )

    id = fields.String(
        required=True,
        metadata={
            "example": '12',
            "description": 'Site id, uuid or name',
        },
    )

    orchestrator_tag = fields.String(
        metadata={
            "example": 'default',
            "description": 'Orchestrator tag',
        },
    )

    orchestrator_select_types = fields.List(
        fields.String(example='vsphere'),
        required=False,
        allow_none=True,
        context="query",
        metadata={
            "description": 'orchestrator select types',
        },
    )


class AddSiteRequestSchema(Schema):
    availability_zone = fields.Nested(AddSiteParamRequestSchema)


class AddSiteBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddSiteRequestSchema, context="body")


class AddSite(ProviderComputeZone):
    definitions = {
        "AddSiteRequestSchema": AddSiteRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(AddSiteBodyRequestSchema)
    parameters_schema = AddSiteRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def post(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Add site to compute zone
        """
        computeZone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        return computeZone.add_site(data.get("availability_zone"))


class DeleteSiteParamRequestSchema(Schema):
    id = fields.String(
        required=True,
        metadata={
            "example": '12',
            "description": 'Site id, uuid or name',
        },
    )


class DeleteSiteRequestSchema(Schema):
    availability_zone = fields.Nested(
        DeleteSiteParamRequestSchema,
    )


class DeleteSiteBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        DeleteSiteRequestSchema,
        context="body",
    )


class DeleteSite(ProviderComputeZone):
    definitions = {
        "DeleteSiteRequestSchema": DeleteSiteRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(DeleteSiteBodyRequestSchema)
    parameters_schema = DeleteSiteRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def delete(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Delete site from compute zone
        """
        obj: 'ComputeZone' = self.get_resource_reference(controller, oid)
        return obj.delete_site(data.get("availability_zone"))


class GetComputeZoneChildsResponseSchema(Schema):
    quotas = fields.Nested(
        ApiObjectResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetComputeZoneChilds(ProviderComputeZone):
    definitions = {"GetComputeZoneChildsResponseSchema": GetComputeZoneChildsResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetComputeZoneChildsResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        List compute_zone childs
        List compute zone childs
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        childs = compute_zone.get_childs()
        return {"resources": [i.info() for i in childs], "count": len(childs)}


class GetComputeZoneQuotasValueResponseSchema(Schema):
    quota = fields.String(
        required=True,
        metadata={
            "example": 'cores',
            "description": 'Quota class',
        },
    )

    value = fields.String(
        required=True,
        metadata={
            "example": '12',
            "description": 'Quota value',
        },
    )

    unit = fields.String(
        required=True,
        metadata={
            "example": '#',
            "description": 'Quota unit',
        },
    )


class GetComputeZoneQuotasResponseSchema(Schema):
    quotas = fields.Nested(
        GetComputeZoneQuotasValueResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetComputeZoneQuotas(ProviderComputeZone):
    definitions = {"GetComputeZoneQuotasResponseSchema": GetComputeZoneQuotasResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetComputeZoneQuotasResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        List compute_zone quotas
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        quotas = compute_zone.get_quotas()
        return {"quotas": quotas}


class GetComputeZoneQuotaClasseResponseSchema(ResourceResponseSchema):
    quota = fields.String(
        required=True,
        metadata={
            "example": 'cores',
            "description": 'Quota class',
        },
    )

    default = fields.String(
        required=True,
        metadata={
            "example": 'cores',
            "description": 'Quota value',
        },
    )

    unit = fields.String(
        required=True,
        metadata={
            "example": 'cores',
            "description": 'Quota unit',
        },
    )


class GetComputeZoneQuotaClassesResponseSchema(Schema):
    quota_classes = fields.Nested(
        GetComputeZoneQuotaClasseResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetComputeZoneQuotaClasses(ProviderComputeZone):
    definitions = {"GetComputeZoneQuotaClassesResponseSchema": GetComputeZoneQuotaClassesResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetComputeZoneQuotaClassesResponseSchema,
            }
        }
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        List compute_zone quota classes
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        quota_classes = compute_zone.quotas.get_classes()
        return {"quota_classes": quota_classes}


class SetComputeZoneQuotasRequestSchema(Schema):
    quotas = fields.Dict(
        required=True,
        many=True,
        allow_none=True,
    )

    orchestrator_tag = fields.String(
        load_default="default",
        metadata={
            "example": 'default',
            "description": 'Orchestrator tag',
        },
    )


class SetComputeZoneQuotasBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(
        SetComputeZoneQuotasRequestSchema,
        context="body",
    )


class SetComputeZoneQuotaResponseSchema(Schema):
    quota = fields.String(
        required=True,
        metadata={
            "example": 'cores',
            "description": 'Quota class',
        },
    )

    value = fields.String(
        required=True,
        metadata={
            "example": '2',
            "description": 'Quota value',
        },
    )

    unit = fields.String(
        required=True,
        metadata={
            "example": 'cores',
            "description": 'Quota unit',
        },
    )


class SetComputeZoneQuotasResponseSchema(Schema):
    quotas = fields.Nested(SetComputeZoneQuotaResponseSchema, required=True, many=True, allow_none=True)


class SetComputeZoneQuotas(ProviderComputeZone):
    definitions = {
        "SetComputeZoneQuotasRequestSchema": SetComputeZoneQuotasRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(SetComputeZoneQuotasBodyRequestSchema)
    parameters_schema = SetComputeZoneQuotasRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Set compute zone quota
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        res = compute_zone.set_quotas(**data)
        return res


class CheckComputeZoneQuotasResponseSchema(Schema):
    quotas = fields.Dict(required=True, many=True, allow_none=True)

class CheckComputeZoneQuotas(ProviderComputeZone):
    definitions = {"GetComputeZoneQuotaClassesResponseSchema": GetComputeZoneQuotaClassesResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetComputeZoneQuotaClassesResponseSchema,
            }
        }
    )

    def put(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Check compute_zone quota
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        # fv - comment to create test vm
        res = compute_zone.check_quotas(quotas=data.get("quotas"), check_all=data.get("check_all"))
        return {"quotas": data.get("quotas")}


class GetManageResponseSchema(Schema):
    is_managed = fields.Boolean(
        required=True,
        metadata={
            "description": 'Return True if compute zone is managed by ssh module',
        },
    )


class GetManage(ProviderComputeZone):
    definitions = {"GetManageResponseSchema": GetManageResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetManageResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Check compute_zone is managed
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        res = compute_zone.is_managed()
        return {"is_managed": res}


class AddManageResponseSchema(Schema):
    manage = fields.Boolean(
        required=True,
        metadata={
            "description": 'Ssh group uuid',
        },
    )


class AddManage(ProviderComputeZone):
    definitions = {"AddManageResponseSchema": AddManageResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": AddManageResponseSchema}})

    def post(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Manage compute_zone
        """
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller, oid)
        res = compute_zone.manage()
        return {"manage": res}


class DeleteManage(ProviderComputeZone):
    definitions = {"CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({204: {"description": "success"}})

    def delete(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Unmanage compute_zone
        """
        compute_zone: ComputeZone = self.get_resource_reference(controller, oid)
        res = compute_zone.unmanage()
        return None


class GetComputeZoneMetricsResponseSchema(Schema):
    compute_zone = fields.Nested(
        GetResourceMetricsResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetComputeZoneMetrics(ProviderComputeZone):
    definitions = {"GetComputeZoneMetricsResponseSchema": GetComputeZoneMetricsResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetComputeZoneMetricsResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Metric compute_zone

        {"compute_zone": [{
            "id": "1",
            "uuid": "vm1",
            "type": "Provider.ComputeZone.ComputeInstance",
            "metrics": [
                {
                    "key": "ram",
                    "value: 10,
                    "type": 1,
                    "unit": "GB"
                }],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"

        },{
            "id": "2",
            "uuid": "vm2",
            "type": "Provider.ComputeZone.ComputeInstance",
            "metrics": [
                {
                    "key": "ram",
                    "value: 8,
                    "type": 1,
                    "unit": "GB"
                },
                {
                    "key": "cpu_vw",
                    "value: 10,
                    "type": 1,
                    "unit": "#"
                }
            ],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"
        }]
        }
        """
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        resource_metrics = compute_zone.get_metrics()

        return {"compute_zone": resource_metrics}

    def getResourcetree(self, controller: 'ResourceController', parent_oid):
        resources = []
        childrens = []
        try:
            childrens, total = controller.get_resources(parent_id=parent_oid)
        except Exception:
            self.logger.debug("Children none for %s" % parent_oid)

        for r in childrens:
            self.logger.debug("Children  %s" % r)
            resources.append(r)
            resources = resources + self.getResourcetree(controller, r.oid)

        return resources

    def generate_metrics(self):
        metric_type_nums = [1, 2, 3, 7]  # Numeric type
        num = random.choice([1, 2, 3])
        x = 0
        metrics = []
        metric_key = set()  # key set distinct
        retry_max = 0
        while x < num:
            metric_type = random.randint(1, 8)  # generate new key
            if metric_type in metric_type_nums:
                value = random.randint(1, 100)  # NUMBER
            else:
                value = random.randint(0, 1)  # ON OFF

            if metric_type not in metric_key:
                # Unused key
                metrics.append({"key": metric_type, "value": value})
                x += 1
                metric_key.add(metric_type)
            else:
                # Used key
                self.logger.debug("Used key %s, try again" % metric_type)
                retry_max += 1
                if retry_max > 5:  # termination
                    break
        return metrics


class DeleteComputeZoneMetricsCache(ProviderComputeZone):
    tags = ["resource"]

    definitions = {
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
        "CrudApiObjectSimpleResponseSchema": CrudApiObjectSimpleResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": CrudApiObjectSimpleResponseSchema}}
    )

    def delete(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        resource = controller.get_resource(oid)
        if isinstance(resource, ComputeZone):
            resource.delete_metrics_cache()
            return True
        else:
            raise ApiManagerError("Resource %s is not a compute zone" % oid, code=400)


class GetComputeZoneSshKeyResponseSchema(Schema):
    id = fields.Integer(
        required=True,
        metadata={
            "example": 10,
        },
    )

    uuid = fields.String(
        required=True,
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'test',
        },
    )

    desc = fields.String(
        required=True,
        metadata={
            "example": 'test',
        },
    )

    active = fields.Boolean(
        required=True,
        dump_default=True,
        metadata={
            "example": True,
        },
    )

    attribute = fields.String(required=False)
    pub_key = fields.String(required=True)


class GetComputeZoneSshKeysResponseSchema(PaginatedResponseSchema):
    sshkeys = fields.Nested(
        GetComputeZoneSshKeyResponseSchema,
        many=True,
        required=True,
        allow_none=True,
    )


class GetComputeZoneSshKeys(ProviderComputeZone):
    definitions = {"GetComputeZoneSshKeysResponseSchema": GetComputeZoneSshKeysResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetComputeZoneSshKeysResponseSchema}}
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        """
        Get Compute zone ssh keys
        """
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        sshkeys = compute_zone.get_ssh_keys()
        return {"sshkeys": sshkeys}


class GetComputeZoneBackupJobsItemResponseSchema(Schema):
    hypervisor = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'hypervisor like openstack or vsphere',
        },
    )

    site = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'availability zone name',
        },
    )

    resource_type = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'type of resource managed by job',
        },
    )

    instances = fields.Int(
        required=True,
        metadata={
            "example": 1,
            "description": 'number if instances configured in job',
        },
    )

    id = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job id',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job name',
        },
    )

    desc = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'desc job1',
            "description": 'desc job name',
        },
    )

    created = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job creation date',
        },
    )

    updated = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job update date',
        },
    )

    error = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job error',
        },
    )

    usage = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job storage usage',
        },
    )

    status = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job status',
        },
    )

    type = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job type',
        },
    )

    schedule = fields.Dict(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job schedule',
        },
    )


class GetComputeZoneBackupJobsResponseSchema(Schema):
    jobs = fields.Nested(
        GetComputeZoneBackupJobsItemResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )


class GetComputeZoneBackupJobsRequestSchema(Schema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    hypervisor = fields.String(
        required=False,
        context="query",
        metadata={
            "description": 'hypervisor',
        },
    )


class GetComputeZoneBackupJobs(ProviderComputeZone):
    summary = "Get compute zone backup configured jobs"
    description = "Get compute zone backup configured jobs"

    definitions = {
        "GetComputeZoneBackupJobsResponseSchema": GetComputeZoneBackupJobsResponseSchema,
        "GetComputeZoneBackupJobsRequestSchema": GetComputeZoneBackupJobsRequestSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetComputeZoneBackupJobsRequestSchema)
    parameters_schema = GetComputeZoneBackupJobsRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetComputeZoneBackupJobsResponseSchema,
            }
        }
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        hypervisor = dict_get(data, "hypervisor")
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        resp = compute_zone.get_backup_jobs(hypervisor=hypervisor)
        return {"jobs": resp}


class GetComputeZoneBackupJobItemResponseSchema(GetComputeZoneBackupJobsItemResponseSchema):
    instances = fields.List(
        fields.Dict,
        required=True,
        metadata={
            "example": '1',
            "description": 'list if instances configured in job',
        },
    )


class GetComputeZoneBackupJobResponseSchema(Schema):
    job = fields.Nested(
        GetComputeZoneBackupJobItemResponseSchema,
        required=True,
        many=False,
        allow_none=True,
    )


class GetComputeZoneBackupJobRequestSchema(Schema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )


class GetComputeZoneBackupJob(ProviderComputeZone):
    summary = "Get compute zone backup configured job"
    description = "Get compute zone backup configured job"

    definitions = {
        "GetComputeZoneBackupJobResponseSchema": GetComputeZoneBackupJobResponseSchema,
        "GetComputeZoneBackupJobRequestSchema": GetComputeZoneBackupJobRequestSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetComputeZoneBackupJobRequestSchema)

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetComputeZoneBackupJobResponseSchema,
            }
        }
    )

    def get(self, controller: 'ResourceController', data, oid, job, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        resp = compute_zone.get_backup_job(job)
        return {"job": resp}


class AddComputeZoneBackupJobRequestSchema(Schema):
    hypervisor = fields.String(
        required=False,
        metadata={
            "example": 'openstack',
            "description": 'hypervisor like openstack or vsphere',
        },
    )

    hypervisor_tag = fields.String(
        required=False,
        metadata={
            "example": 'default',
            "description": 'hypervisor tag',
        },
    )

    site = fields.String(
        required=True,
        metadata={
            "example": 'Test',
            "description": 'availability zone name',
        },
    )

    resource_type = fields.String(
        required=False,
        metadata={
            "example": 'ComputeInstance',
            "description": 'type of resource managed by job. Can be: ComputeInstance',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job name',
        },
    )

    desc = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "example": 'desc job1',
            "description": 'desc job name',
        },
    )

    fullbackup_interval = fields.Int(
        required=False,
        load_default=2,
        metadata={
            "example": 2,
            "description": 'interval between full backup',
        },
    )

    restore_points = fields.Int(
        required=False,
        load_default=4,
        metadata={
            "example": 4,
            "description": 'number of restore points to retain',
        },
    )

    start_date = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'dd/mm/yyyy',
            "description": 'start date like dd/mm/yyyy',
        },
    )

    end_date = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'dd/mm/yyyy',
            "description": 'end date like dd/mm/yyyy',
        },
    )

    start_time = fields.String(
        required=False,
        load_default="0:00 AM",
        metadata={
            "example": '0:00 AM',
            "description": 'start time like 0:00 AM',
        },
    )

    interval = fields.String(
        required=False,
        load_default="24hrs",
        metadata={
            "example": '24hrs',
            "description": 'job interval like 24hrs',
        },
    )

    timezone = fields.String(
        required=False,
        load_default="Europe/Rome",
        metadata={
            "example": 'Europe/Rome',
            "description": 'job timezone',
        },
    )

    job_type = fields.String(
        required=False,
        load_default="Parallel",
        metadata={
            "example": 'Parallel',
            "description": 'job type. Can be: Parallel or Serial',
        },
    )

    instances = fields.List(
        fields.String,
        required=True,
        metadata={
            "example": '["id1"]',
            "description": 'list of instances id',
        },
    )


class AddComputeZoneBackupJobBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    body = fields.Nested(
        AddComputeZoneBackupJobRequestSchema,
        context="body",
    )


class AddComputeZoneBackupJobResponseSchema(Schema):
    job = fields.String(
        required=True,
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
            "description": 'job id',
        },
    )


class AddComputeZoneBackupJob(ProviderComputeZone):
    summary = "Add compute zone backup job"
    description = "Add compute zone backup job"

    definitions = {
        "AddComputeZoneBackupJobRequestSchema": AddComputeZoneBackupJobRequestSchema,
        "AddComputeZoneBackupJobResponseSchema": AddComputeZoneBackupJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(AddComputeZoneBackupJobBodyRequestSchema)
    parameters_schema = AddComputeZoneBackupJobRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": AddComputeZoneBackupJobResponseSchema,
            }
        }
    )

    def post(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        name = data.pop("name")
        desc = data.pop("desc")
        site = data.pop("site")
        resp = compute_zone.create_backup_job(name, desc, site, **data)
        return {"job": resp}


class UpdateComputeZoneBackupJobInstanceRequestSchema(Schema):
    instance = fields.String(
        required=True,
        metadata={
            "example": 'instance1',
            "description": 'instance name',
        },
    )

    action = fields.String(
        required=True,
        metadata={
            "example": 'add',
            "description": 'action to do: add, del',
        },
    )


class UpdateComputeZoneBackupJobRequestSchema(Schema):
    name = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'job1',
            "description": 'job name',
        },
    )

    fullbackup_interval = fields.Int(
        required=False,
        load_default=None,
        metadata={
            "example": 2,
            "description": 'interval between full backup',
        },
    )

    restore_points = fields.Int(
        required=False,
        load_default=None,
        metadata={
            "example": 4,
            "description": 'number of restore points to retain',
        },
    )

    start_date = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'dd/mm/yyyy',
            "description": 'start date like dd/mm/yyyy',
        },
    )

    end_date = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'dd/mm/yyyy',
            "description": 'end date like dd/mm/yyyy',
        },
    )

    start_time = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": '0:00 AM',
            "description": 'start time like 0:00 AM',
        },
    )

    interval = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": '24hrs',
            "description": 'job interval like 24hrs',
        },
    )

    timezone = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'Europe/Rome',
            "description": 'job timezone',
        },
    )

    enabled = fields.Boolean(
        required=False,
        load_default=None,
        metadata={
            "example": True,
            "description": 'job enable status',
        },
    )

    instances = fields.Nested(
        UpdateComputeZoneBackupJobInstanceRequestSchema,
        required=False,
        many=True,
        allow_none=True,
        metadata={
            "description": 'list of instance to add or remove',
        },
    )


class UpdateComputeZoneBackupJobBodyRequestSchema(Schema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    job = fields.String(
        required=True,
        context="path",
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
            "description": 'job id',
        },
    )

    body = fields.Nested(
        UpdateComputeZoneBackupJobRequestSchema,
        context="body",
    )


class UpdateComputeZoneBackupJobResponseSchema(Schema):
    job = fields.String(
        required=True,
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
            "description": 'job id',
        },
    )


class UpdateComputeZoneBackupJob(ProviderComputeZone):
    summary = "Update compute zone backup job"
    description = "Update compute zone backup job"

    definitions = {
        "UpdateComputeZoneBackupJobRequestSchema": UpdateComputeZoneBackupJobRequestSchema,
        "UpdateComputeZoneBackupJobResponseSchema": UpdateComputeZoneBackupJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(UpdateComputeZoneBackupJobBodyRequestSchema)
    parameters_schema = UpdateComputeZoneBackupJobRequestSchema
    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": UpdateComputeZoneBackupJobResponseSchema,
            }
        }
    )

    def put(self, controller: 'ResourceController', data, oid, job, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        resp = compute_zone.update_backup_job(job, **data)
        return {"job": resp}


class DeleteComputeZoneBackupJobBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    job = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id of the job',
        },
    )


class DeleteComputeZoneBackupJobResponseSchema(Schema):
    job = fields.String(
        required=True,
        metadata={
            "example": '4cdf0ea4-159a-45aa-96f2-708e461130e1',
            "description": 'job id',
        },
    )


class DeleteComputeZoneBackupJob(ProviderComputeZone):
    summary = "Delete compute zone backup job"
    description = "Delete compute zone backup job"

    definitions = {
        "DeleteComputeZoneBackupJobResponseSchema": DeleteComputeZoneBackupJobResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(DeleteComputeZoneBackupJobBodyRequestSchema)

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": DeleteComputeZoneBackupJobResponseSchema,
            }
        }
    )

    def delete(self, controller: 'ResourceController', data, oid, job, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        resp = compute_zone.delete_backup_job(job)
        return {"job": resp}


#
# backup restore points
#
class GetComputeZoneBackupRestorePointsItemResponseSchema(Schema):
    hypervisor = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'hypervisor like openstack or vsphere',
        },
    )

    site = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'availability zone name',
        },
    )

    resource_type = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'type of resource managed by job',
        },
    )

    instances = fields.Int(
        required=True,
        metadata={
            "example": 1,
            "description": 'number if instances configured in job',
        },
    )

    id = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job id',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job name',
        },
    )

    created = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job creation date',
        },
    )

    updated = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job update date',
        },
    )

    error = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job error',
        },
    )

    usage = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job storage usage',
        },
    )

    status = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job status',
        },
    )

    type = fields.String(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job type',
        },
    )

    schedule = fields.Dict(
        required=True,
        metadata={
            "example": 'job1',
            "description": 'job schedule',
        },
    )


class GetComputeZoneBackupRestorePointsResponseSchema(Schema):
    restore_points = fields.Nested(
        GetComputeZoneBackupRestorePointsItemResponseSchema,
        required=True,
        many=True,
        allow_none=True,
    )

    restore_point_total = fields.Int(
        required=True,
        allow_none=True,
        metadata={
            "example": 1,
            "description": 'total number of restore point',
        },
    )


class GetComputeZoneBackupRestorePointsRequestSchema(Schema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    job_id = fields.String(
        required=False,
        load_default=None,
        context="query",
        metadata={
            "description": 'id of the backup job',
        },
    )

    restore_point_id = fields.String(
        required=False,
        load_default=None,
        context="query",
        metadata={
            "description": 'id of the backup job restore point',
        },
    )

    size = fields.Int(
        required=False,
        load_default=20,
        context="query",
        metadata={
            "description": 'size',
        },
    )

    page = fields.Int(
        required=False,
        load_default=0,
        context="query",
        metadata={
            "description": 'page',
        },
    )


class GetComputeZoneBackupRestorePoints(ProviderComputeZone):
    summary = "Get compute zone backup job restore points"
    description = "Get compute zone backup job restore points"

    definitions = {
        "GetComputeZoneBackupRestorePointsResponseSchema": GetComputeZoneBackupRestorePointsResponseSchema,
        "GetComputeZoneBackupRestorePointsRequestSchema": GetComputeZoneBackupRestorePointsRequestSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetComputeZoneBackupRestorePointsRequestSchema)
    parameters_schema = GetComputeZoneBackupRestorePointsRequestSchema

    responses = SwaggerApiView.setResponses(
        {
            200: {
                "description": "success",
                "schema": GetComputeZoneBackupRestorePointsResponseSchema,
            }
        }
    )

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        job_id = data.get("job_id")
        restore_point_id = data.get("restore_point_id")
        size = data.get("size")
        page = int(data.get("page"))

        restore_points, restore_point_total = compute_zone.get_backup_restore_points(
            job_id, size, page, restore_point_id=restore_point_id
        )

        return {"restore_points": restore_points, "restore_point_total": restore_point_total}


class AddComputeZoneBackupRestorePointRequestSchema(Schema):
    job_id = fields.String(
        required=True,
        metadata={
            "example": 'default',
            "description": 'hypervisor tag',
        },
    )

    name = fields.String(
        required=True,
        metadata={
            "example": 'restore_point1',
            "description": 'restore point name',
        },
    )

    desc = fields.String(
        required=False,
        load_default=None,
        metadata={
            "example": 'restore_point1',
            "description": 'restore point description',
        },
    )

    full = fields.Boolean(
        required=False,
        load_default=True,
        metadata={
            "example": True,
            "description": 'if True create a full restore point type, otherwise crate an incremental',
        },
    )


class AddComputeZoneBackupRestorePointBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    body = fields.Nested(
        AddComputeZoneBackupRestorePointRequestSchema,
        context="body",
    )


class AddComputeZoneBackupRestorePoint(ProviderComputeZone):
    summary = "Add compute zone backup job restore point"
    description = "Add compute zone backup job restore point"

    definitions = {
        "AddComputeZoneBackupRestorePointRequestSchema": AddComputeZoneBackupRestorePointRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(AddComputeZoneBackupRestorePointBodyRequestSchema)
    parameters_schema = AddComputeZoneBackupRestorePointRequestSchema

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        job_id = data.get("job_id")
        name = data.get("name")
        desc = data.get("desc")
        full = data.get("full")
        resp = compute_zone.create_backup_restore_point(job_id, name, desc=desc, full=full)
        return resp


class DeleteComputeZoneBackupRestorePointRequestSchema(Schema):
    job_id = fields.String(
        required=True,
        metadata={
            "example": 'default',
            "description": 'hypervisor tag',
        },
    )

    restore_point_id = fields.String(
        required=True,
        metadata={
            "example": 'restore_point1',
            "description": 'restore point id',
        },
    )


class DeleteComputeZoneBackupRestorePointBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(
        required=True,
        context="path",
        metadata={
            "description": 'id, uuid or name of the parent compute zone',
        },
    )

    body = fields.Nested(
        DeleteComputeZoneBackupRestorePointRequestSchema,
        context="body",
    )


class DeleteComputeZoneBackupRestorePoint(ProviderComputeZone):
    summary = "Delete compute zone backup job restore point"
    description = "Delete compute zone backup job restore point"

    definitions = {
        "DeleteComputeZoneBackupRestorePointRequestSchema": DeleteComputeZoneBackupRestorePointRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(DeleteComputeZoneBackupRestorePointBodyRequestSchema)
    parameters_schema = DeleteComputeZoneBackupRestorePointRequestSchema

    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        compute_zone: 'ComputeZone' = controller.get_resource(oid)
        job_id = data.get("job_id")
        restore_point_id = data.get("restore_point_id")
        resp = compute_zone.delete_backup_restore_point(job_id, restore_point_id)
        return resp


class CheckComputeZoneStorageConfParamsResponseSchema(ResourceResponseSchema):
    storage_conf = fields.Dict(
        required=True,
        dump_default={},
    )


class CheckComputeZoneStorageConfResponseSchema(Schema):
    compute_zone = fields.Nested(
        GetComputeZoneParamsResponseSchema,
        required=True,
        allow_none=True,
    )


class CheckComputeZoneStorageConf(ProviderComputeZone):
    summary = "Check compute zone storage configuration"
    description = "Check compute zone is correctly configured in order to use specific svms for the new ontap staas services"

    definitions = {
        "GetApiObjectRequestSchema": GetApiObjectRequestSchema,
        "CheckComputeZoneStorageConfResponseSchema": CheckComputeZoneStorageConfResponseSchema,
    }

    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CheckComputeZoneStorageConfResponseSchema}})

    def get(self, controller: 'ResourceController', data, oid, *args, **kwargs):
        compute_zone: 'ComputeZone' = self.get_resource_reference(controller,oid,run_customize=False,cache=False)
        ret = compute_zone.check_get_storage_conf()
        return {"storage_conf":ret}

class ComputeZoneAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            ("%s/compute_zones" % base, "GET", ListComputeZones, {}),
            ("%s/compute_zones/<oid>" % base, "GET", GetComputeZone, {}),
            ("%s/compute_zones" % base, "POST", CreateComputeZone, {}),
            ("%s/compute_zones/<oid>" % base, "PUT", UpdateComputeZone, {}),
            ("%s/compute_zones/<oid>" % base, "DELETE", DeleteComputeZone, {}),
            ("%s/compute_zones/<oid>/sites" % base, "POST", AddSite, {}),
            ("%s/compute_zones/<oid>/sites" % base, "DELETE", DeleteSite, {}),
            ("%s/compute_zones/<oid>/availability_zones" % base, "GET", ListSite, {}),
            ("%s/compute_zones/<oid>/availability_zones" % base, "POST", AddSite, {}),
            (
                "%s/compute_zones/<oid>/availability_zones" % base,
                "DELETE",
                DeleteSite,
                {},
            ),
            ("%s/compute_zones/<oid>/childs" % base, "GET", GetComputeZoneChilds, {}),
            ("%s/compute_zones/<oid>/quotas" % base, "GET", GetComputeZoneQuotas, {}),
            (
                "%s/compute_zones/<oid>/quotas/classes" % base,
                "GET",
                GetComputeZoneQuotaClasses,
                {},
            ),
            ("%s/compute_zones/<oid>/quotas" % base, "PUT", SetComputeZoneQuotas, {}),
            (
                "%s/compute_zones/<oid>/quotas/check" % base,
                "PUT",
                CheckComputeZoneQuotas,
                {},
            ),
            ("%s/compute_zones/<oid>/manage" % base, "GET", GetManage, {}),
            ("%s/compute_zones/<oid>/manage" % base, "POST", AddManage, {}),
            ("%s/compute_zones/<oid>/manage" % base, "DELETE", DeleteManage, {}),
            ("%s/compute_zones/<oid>/metrics" % base, "GET", GetComputeZoneMetrics, {}),
            (
                "%s/compute_zones/<oid>/metrics/cache" % base,
                "DELETE",
                DeleteComputeZoneMetricsCache,
                {},
            ),
            ("%s/compute_zones/<oid>/sshkeys" % base, "GET", GetComputeZoneSshKeys, {}),
            (
                "%s/compute_zones/<oid>/backup/jobs" % base,
                "GET",
                GetComputeZoneBackupJobs,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/jobs/<job>" % base,
                "GET",
                GetComputeZoneBackupJob,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/jobs" % base,
                "POST",
                AddComputeZoneBackupJob,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/jobs/<job>" % base,
                "PUT",
                UpdateComputeZoneBackupJob,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/jobs/<job>" % base,
                "DELETE",
                DeleteComputeZoneBackupJob,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/restore_points" % base,
                "GET",
                GetComputeZoneBackupRestorePoints,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/restore_points" % base,
                "POST",
                AddComputeZoneBackupRestorePoint,
                {},
            ),
            (
                "%s/compute_zones/<oid>/backup/restore_points" % base,
                "DELETE",
                DeleteComputeZoneBackupRestorePoint,
                {},
            ),
            (
                "%s/compute_zones/<oid>/storage/conf" % base,
                "GET",
                CheckComputeZoneStorageConf,
                {},
            )
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
