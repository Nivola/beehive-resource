# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.apimanager import PaginatedResponseSchema, SwaggerApiView, \
    GetApiObjectRequestSchema, CrudApiJobResponseSchema, CrudApiObjectTaskResponseSchema, \
    CrudApiObjectSimpleResponseSchema, ApiObjectResponseSchema, \
    PaginatedRequestQuerySchema, ApiManagerError
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.plugins.provider.views import ProviderAPI, \
    LocalProviderApiView, CreateProviderResourceRequestSchema, \
    UpdateProviderResourceRequestSchema
from beehive_resource.view import ListResourcesRequestSchema, \
    ResourceResponseSchema, ResourceSmallResponseSchema, GetResourceMetricsResponseSchema
from flasgger import fields, Schema

from beecell.swagger import SwaggerHelper
import random


class ProviderComputeZone(LocalProviderApiView):
    resclass = ComputeZone


class ListComputeZonesRequestSchema(ListResourcesRequestSchema):
    pass


class ListComputeZonesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListComputeZonesResponseSchema(PaginatedResponseSchema):
    compute_zones = fields.Nested(ListComputeZonesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListComputeZones(ProviderComputeZone):
    definitions = {
        'ListComputeZonesResponseSchema': ListComputeZonesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListComputeZonesRequestSchema)
    parameters_schema = ListComputeZonesRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListComputeZonesResponseSchema
        }
    })

    def get(self, controller, data, *args, **kwargs):
        """
        List compute_zones
        List compute_zones

        "attributes": {
          "configs": {},
          "quota": {

          }
        }
        """
        return self.get_resources(controller, **data)


class GetComputeZoneParamsResponseSchema(ResourceResponseSchema):
    availability_zones = fields.Nested(ResourceSmallResponseSchema, required=True, many=True, allow_none=True)


class GetComputeZoneResponseSchema(Schema):
    compute_zone = fields.Nested(GetComputeZoneParamsResponseSchema, required=True, allow_none=True)


class GetComputeZone(ProviderComputeZone):
    definitions = {
        'GetComputeZoneResponseSchema': GetComputeZoneResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get compute_zone
        Get compute_zone

        "attributes": {
          "configs": {},
          "quota": {

          }
        }
        """
        return self.get_resource(controller, oid)


class CreateComputeZoneParamRequestSchema(CreateProviderResourceRequestSchema):
    quota = fields.Dict(required=True, description='allocation quota', allow_none=True)
    managed = fields.Boolean(required=False, description='set management with ssh group', missing=True)
    managed_by = fields.String(required=False, description='set user or group that as role master in ssh group',
                               missing=None)


class CreateComputeZoneRequestSchema(Schema):
    compute_zone = fields.Nested(CreateComputeZoneParamRequestSchema)


class CreateComputeZoneBodyRequestSchema(Schema):
    body = fields.Nested(CreateComputeZoneRequestSchema, context='body')


class CreateComputeZone(ProviderComputeZone):
    definitions = {
        'CreateComputeZoneRequestSchema': CreateComputeZoneRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(CreateComputeZoneBodyRequestSchema)
    parameters_schema = CreateComputeZoneRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, *args, **kwargs):
        """
        Create compute_zone
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
    body = fields.Nested(UpdateComputeZoneRequestSchema, context='body')


class UpdateComputeZone(ProviderComputeZone):
    definitions = {
        'UpdateComputeZoneRequestSchema': UpdateComputeZoneRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(UpdateComputeZoneBodyRequestSchema)
    parameters_schema = UpdateComputeZoneRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update compute_zone
        Update compute_zone
        """
        return self.update_resource(controller, oid, data)


class DeleteComputeZone(ProviderComputeZone):
    definitions = {
        'CrudApiObjectTaskResponseSchema':CrudApiObjectTaskResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete compute_zone
        Delete compute_zone
        """
        return self.expunge_resource(controller, oid)


class ListSiteResponseSchema(Schema):
    availability_zones = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class ListSite(ProviderComputeZone):
    definitions = {
        'ListSiteResponseSchema': ListSiteResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': ListSiteResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List site to compute zone
        List site to compute zone
        """
        obj = self.get_resource_reference(controller, oid)
        res = [z.info() for z in obj.get_availability_zones()]
        return {'availability_zones': res, 'count': len(res)}


class AddSiteParamRequestSchema(UpdateProviderResourceRequestSchema):
    quota = fields.Dict(required=False, description='allocation quota', allow_none=True, missing=None)
    id = fields.String(required=True, example='12', description='Site id, uuid or name')
    orchestrator_tag = fields.String(example='default', default='default', description='Orchestrator tag')


class AddSiteRequestSchema(Schema):
    availability_zone = fields.Nested(AddSiteParamRequestSchema)


class AddSiteBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(AddSiteRequestSchema, context='body')


class AddSite(ProviderComputeZone):
    definitions = {
        'AddSiteRequestSchema': AddSiteRequestSchema,
        'CrudApiJobResponseSchema': CrudApiJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(AddSiteBodyRequestSchema)
    parameters_schema = AddSiteRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiJobResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Add site to compute zone
        Add site to compute zone
        """
        obj = self.get_resource_reference(controller, oid)
        return obj.add_site(data.get('availability_zone'))


class DeleteSiteParamRequestSchema(Schema):
    id = fields.String(required=True, example='12', description='Site id, uuid or name')


class DeleteSiteRequestSchema(Schema):
    availability_zone = fields.Nested(DeleteSiteParamRequestSchema)


class DeleteSiteBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(DeleteSiteRequestSchema, context='body')


class DeleteSite(ProviderComputeZone):
    definitions = {
        'DeleteSiteRequestSchema': DeleteSiteRequestSchema,
        'CrudApiJobResponseSchema': CrudApiJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(DeleteSiteBodyRequestSchema)
    parameters_schema = DeleteSiteRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete site from compute zone
        Delete site from compute zone
        """
        obj = self.get_resource_reference(controller, oid)
        return obj.delete_site(data.get('availability_zone'))


class GetComputeZoneChildsResponseSchema(Schema):
    quotas = fields.Nested(ApiObjectResponseSchema, required=True, many=True, allow_none=True)


class GetComputeZoneChilds(ProviderComputeZone):
    definitions = {
        'GetComputeZoneChildsResponseSchema': GetComputeZoneChildsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneChildsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List compute_zone childs
        List compute zone childs
        """
        compute_zone = self.get_resource_reference(controller, oid)
        childs = compute_zone.get_childs()
        return {'resources': [i.info() for i in childs], 'count': len(childs)}


class GetComputeZoneQuotasValueResponseSchema(Schema):
    quota = fields.String(required=True, example='cores', description='Quota class')
    value = fields.String(required=True, example='12', description='Quota value')
    unit = fields.String(required=True, example='#', description='Quota unit')


class GetComputeZoneQuotasResponseSchema(Schema):
    quotas = fields.Nested(GetComputeZoneQuotasValueResponseSchema, required=True, many=True, allow_none=True)


class GetComputeZoneQuotas(ProviderComputeZone):
    definitions = {
        'GetComputeZoneQuotasResponseSchema': GetComputeZoneQuotasResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneQuotasResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List compute_zone quotas
        List compute zone quotas
        """
        compute_zone: ComputeZone = self.get_resource_reference(controller, oid)
        quotas = compute_zone.get_quotas()
        return {'quotas': quotas}


class GetComputeZoneQuotaClasseResponseSchema(ResourceResponseSchema):
    quota = fields.String(required=True, example='cores', description='Quota class')
    default = fields.String(required=True, example='cores', description='Quota value')
    unit = fields.String(required=True, example='cores', description='Quota unit')


class GetComputeZoneQuotaClassesResponseSchema(Schema):
    quota_classes = fields.Nested(GetComputeZoneQuotaClasseResponseSchema, required=True, many=True, allow_none=True)


class GetComputeZoneQuotaClasses(ProviderComputeZone):
    definitions = {
        'GetComputeZoneQuotaClassesResponseSchema': GetComputeZoneQuotaClassesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneQuotaClassesResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        List compute_zone quota classes
        List compute zone quota classes
        """
        compute_zone = self.get_resource_reference(controller, oid)
        quota_classes = compute_zone.quotas.get_classes()
        return {'quota_classes': quota_classes}


class SetComputeZoneQuotasRequestSchema(Schema):
    quotas = fields.Dict(required=True, many=True, allow_none=True)
    orchestrator_tag = fields.String(example='default', missing='default', description='Orchestrator tag')


class SetComputeZoneQuotasBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SetComputeZoneQuotasRequestSchema, context='body')


class SetComputeZoneQuotaResponseSchema(Schema):
    quota = fields.String(required=True, example='cores', description='Quota class')
    value = fields.String(required=True, example=2, description='Quota value')
    unit = fields.String(required=True, example='cores', description='Quota unit')


class SetComputeZoneQuotasResponseSchema(Schema):
    quotas = fields.Nested(SetComputeZoneQuotaResponseSchema, required=True, many=True, allow_none=True)


class SetComputeZoneQuotas(ProviderComputeZone):
    definitions = {
        'SetComputeZoneQuotasRequestSchema': SetComputeZoneQuotasRequestSchema,
        'CrudApiJobResponseSchema': CrudApiJobResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(SetComputeZoneQuotasBodyRequestSchema)
    parameters_schema = SetComputeZoneQuotasRequestSchema
    responses = SwaggerApiView.setResponses({
        202: {
            'description': 'success',
            'schema': CrudApiJobResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Set compute_zone quota
        Set compute zone quota
        """
        compute_zone = self.get_resource_reference(controller, oid)
        res = compute_zone.set_quotas(**data)
        return res


class CheckComputeZoneQuotasResponseSchema(Schema):
    quotas = fields.Dict(required=True, many=True, allow_none=True)


class CheckComputeZoneQuotas(ProviderComputeZone):
    definitions = {
        'GetComputeZoneQuotaClassesResponseSchema': GetComputeZoneQuotaClassesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneQuotaClassesResponseSchema
        }
    })

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Check compute_zone quota
        Check compute zone quota
        """
        compute_zone: ComputeZone = self.get_resource_reference(controller, oid)
        # fv - comment to create test vm
        res = compute_zone.check_quotas(data.get('quotas'))
        return {'quotas': data.get('quotas')}


class GetManageResponseSchema(Schema):
    is_managed = fields.Boolean(required=True, description='Return True if compute zone is managed by ssh module')


class GetManage(ProviderComputeZone):
    definitions = {
        'GetManageResponseSchema': GetManageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetManageResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Check compute_zone is managed
        Check compute zone is managed
        """
        compute_zone = self.get_resource_reference(controller, oid)
        res = compute_zone.is_managed()
        return {'is_managed': res}


class AddManageResponseSchema(Schema):
    manage = fields.Boolean(required=True, description='Ssh group uuid')


class AddManage(ProviderComputeZone):
    definitions = {
        'AddManageResponseSchema': AddManageResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': AddManageResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Manage compute_zone
        Manage compute zone
        """
        compute_zone = self.get_resource_reference(controller, oid)
        res = compute_zone.manage()
        return {'manage': res}


class DeleteManage(ProviderComputeZone):
    definitions = {
        'CrudApiObjectSimpleResponseSchema': CrudApiObjectSimpleResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        204: {
            'description': 'success'
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Unmanage compute_zone
        Unmanage compute zone
        """
        compute_zone = self.get_resource_reference(controller, oid)
        res = compute_zone.unmanage()
        return None


class GetComputeZoneMetricsResponseSchema(Schema):
    compute_zone = fields.Nested(GetResourceMetricsResponseSchema, required=True, many=True, allow_none=True)


class GetComputeZoneMetrics(ProviderComputeZone):
    definitions = {
        'GetComputeZoneMetricsResponseSchema': GetComputeZoneMetricsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneMetricsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Metric compute_zone
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
        compute_zone = controller.get_resource(oid)
        resource_metrics = compute_zone.get_metrics()

        # resources = self.getResourcetree(controller, compute_zone.oid)
        # self.logger.warn(resources)
        # extraction_date = datetime.today()
        # resource_metrics = []
        # for r in resources:
        #     self.logger.debug2('resource :%s' % r)
        #     try:
        #         if r.uuid is not None:
        #             resource_metric = {
        #                 'id': '%s' % r.oid,
        #                 'uuid': r.uuid ,
        #                 'extraction_date':format_date(extraction_date),
        #                 # 'platform_id': str(random.choice([10, 20])),
        #                 'service_id': r.ext_id
        #             }
        #             metrics = self.generate_metrics()
        #             resource_metric.update({'metrics':metrics})
        #             resource_metrics.append(resource_metric)
        #     except Exception as ex:
        #         self.logger.warn(ex)
        return {'compute_zone': resource_metrics}

    def getResourcetree(self, controller, parent_oid):
        resources = []
        childrens = []
        try:
            childrens, total = controller.get_resources(parent_id = parent_oid)
        except Exception:
            self.logger.debug('Children none for %s' % parent_oid)

        for r in childrens:
            self.logger.debug('Children  %s' % r)
            resources.append(r)
            resources = resources + self.getResourcetree(controller, r.oid)

        return resources

    def generate_metrics(self):
        metric_type_nums = [1, 2, 3, 7] # Numeric type
        num = random.choice([1, 2, 3])
        x=0
        metrics = []
        metric_key=set() # key set distinct
        retry_max=0
        while x < num:
            metric_type = random.randint(1,8) # generate new key
            if metric_type in metric_type_nums:
                value = (random.randint(1,100)) # NUMBER
            else:
                value = (random.randint(0,1)) # ON OFF

            if metric_type not in metric_key:
                # Unused key
                metrics.append({'key': metric_type, 'value': value})
                x+=1
                metric_key.add(metric_type)
            else:
                # Used key
                self.logger.debug('Used key %s, try again' %metric_type)
                retry_max += 1
                if retry_max > 5: # termination
                    break
        return metrics


class GetComputeZoneSshKeyResponseSchema(Schema):
    id = fields.Integer(required=True, default=10, example=10)
    uuid = fields.String(required=True,  default='4cdf0ea4-159a-45aa-96f2-708e461130e1',
                         example='4cdf0ea4-159a-45aa-96f2-708e461130e1')
    name = fields.String(required=True, default='test', example='test')
    desc = fields.String(required=True, default='test', example='test')
    active = fields.Boolean(required=True, default=True, example=True)
    attribute = fields.String(required=False)
    pub_key = fields.String(required=True)


class GetComputeZoneSshKeysResponseSchema(PaginatedResponseSchema):
    sshkeys = fields.Nested(GetComputeZoneSshKeyResponseSchema, many=True, required=True, allow_none=True)


class GetComputeZoneSshKeys(ProviderComputeZone):
    definitions = {
        'GetComputeZoneSshKeysResponseSchema': GetComputeZoneSshKeysResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneSshKeysResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get Compute zone ssh keys
        Get Compute zone ssh keys
        """
        compute_zone = controller.get_resource(oid)
        sshkeys = compute_zone.get_ssh_keys()
        return {'sshkeys': sshkeys}


class GetComputeZoneBackupJobsItemResponseSchema(Schema):
    hypervisor = fields.String(required=True, example='job1', description='hypervisor like openstack or vsphere')
    site = fields.String(required=True, example='job1', description='availability zone name')
    resource_type = fields.String(required=True, example='job1', description='type of resource managed by job')
    instances = fields.Int(required=True, example=1, description='number if instances configured in job')
    id = fields.String(required=True, example='job1', description='job id')
    name = fields.String(required=True, example='job1', description='job name')
    desc = fields.String(required=False, allow_none=True, example='desc job1', description='desc job name')
    created = fields.String(required=True, example='job1', description='job creation date')
    updated = fields.String(required=True, example='job1', description='job update date')
    error = fields.String(required=True, example='job1', description='job error')
    usage = fields.String(required=True, example='job1', description='job storage usage')
    status = fields.String(required=True, example='job1', description='job status')
    type = fields.String(required=True, example='job1', description='job type')
    schedule = fields.Dict(required=True, example='job1', description='job schedule')


class GetComputeZoneBackupJobsResponseSchema(Schema):
    jobs = fields.Nested(GetComputeZoneBackupJobsItemResponseSchema, required=True, many=True, allow_none=True)


class GetComputeZoneBackupJobsRequestSchema(Schema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')


class GetComputeZoneBackupJobs(ProviderComputeZone):
    summary = 'Get compute zone backup configured jobs'
    description = 'Get compute zone backup configured jobs'
    definitions = {
        'GetComputeZoneBackupJobsResponseSchema': GetComputeZoneBackupJobsResponseSchema,
        'GetComputeZoneBackupJobsRequestSchema': GetComputeZoneBackupJobsRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetComputeZoneBackupJobsRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneBackupJobsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        compute_zone: ComputeZone = controller.get_resource(oid)
        resp = compute_zone.get_backup_jobs()
        return {'jobs': resp}


class GetComputeZoneBackupJobItemResponseSchema(GetComputeZoneBackupJobsItemResponseSchema):
    instances = fields.List(fields.Dict, required=True, example=1, description='list if instances configured in job')


class GetComputeZoneBackupJobResponseSchema(Schema):
    job = fields.Nested(GetComputeZoneBackupJobItemResponseSchema, required=True, many=False, allow_none=True)


class GetComputeZoneBackupJobRequestSchema(Schema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')


class GetComputeZoneBackupJob(ProviderComputeZone):
    summary = 'Get compute zone backup configured job'
    description = 'Get compute zone backup configured job'
    definitions = {
        'GetComputeZoneBackupJobResponseSchema': GetComputeZoneBackupJobResponseSchema,
        'GetComputeZoneBackupJobRequestSchema': GetComputeZoneBackupJobRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetComputeZoneBackupJobRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneBackupJobResponseSchema
        }
    })

    def get(self, controller, data, oid, job, *args, **kwargs):
        compute_zone: ComputeZone = controller.get_resource(oid)
        resp = compute_zone.get_backup_job(job)
        return {'job': resp}


class AddComputeZoneBackupJobRequestSchema(Schema):
    hypervisor = fields.String(required=False, example='openstack', missing='openstack',
                               description='hypervisor like openstack or vsphere')
    hypervisor_tag = fields.String(required=False, example='default', missing='default', description='hypervisor tag')
    site = fields.String(required=True, example='Test', description='availability zone name')
    resource_type = fields.String(required=False, example='ComputeInstance', missing='ComputeInstance',
                                  description='type of resource managed by job. Can be: ComputeInstance')
    name = fields.String(required=True, example='job1', description='job name')
    desc = fields.String(required=False, allow_none=True, example='desc job1', description='desc job name')
    fullbackup_interval = fields.Int(required=False, example=2, missing=2, description='interval between full backup')
    restore_points = fields.Int(required=False, example=4, missing=4, description='number of restore points to retain')
    start_date = fields.String(required=False, example='dd/mm/yyyy', missing=None,
                               description='start date like dd/mm/yyyy')
    end_date = fields.String(required=False, example='dd/mm/yyyy', missing=None,
                             description='end date like dd/mm/yyyy')
    start_time = fields.String(required=False, example='0:00 AM', missing='0:00 AM',
                               description='start time like 0:00 AM')
    interval = fields.String(required=False, example='24hrs', missing='24hrs', description='job interval like 24hrs')
    timezone = fields.String(required=False, example='Europe/Rome', missing='Europe/Rome', description='job timezone')
    job_type = fields.String(required=False, example='Parallel', missing='Parallel',
                             description='job type. Can be: Parallel or Serial')
    instances = fields.List(fields.String, required=True, example='["id1"]', description='list of instances id')


class AddComputeZoneBackupJobBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')
    body = fields.Nested(AddComputeZoneBackupJobRequestSchema, context='body')


class AddComputeZoneBackupJobResponseSchema(Schema):
    job = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1', description='job id')


class AddComputeZoneBackupJob(ProviderComputeZone):
    summary = 'Add compute zone backup job'
    description = 'Add compute zone backup job'
    definitions = {
        'AddComputeZoneBackupJobRequestSchema': AddComputeZoneBackupJobRequestSchema,
        'AddComputeZoneBackupJobResponseSchema': AddComputeZoneBackupJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddComputeZoneBackupJobBodyRequestSchema)
    parameters_schema = AddComputeZoneBackupJobRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': AddComputeZoneBackupJobResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        compute_zone: ComputeZone = controller.get_resource(oid)
        name = data.pop('name')
        desc = data.pop('desc')
        site = data.pop('site')
        resp = compute_zone.create_backup_job(name, desc, site, **data)
        return {'job': resp}


class UpdateComputeZoneBackupJobInstanceRequestSchema(Schema):
    instance = fields.String(required=True, example='instance1', description='instance name')
    action = fields.String(required=True, example='add', description='action to do: add, del')


class UpdateComputeZoneBackupJobRequestSchema(Schema):
    name = fields.String(required=False, example='job1', missing=None, description='job name')
    fullbackup_interval = fields.Int(required=False, example=2, missing=None,
                                     description='interval between full backup')
    restore_points = fields.Int(required=False, example=4, missing=None,
                                description='number of restore points to retain')
    start_date = fields.String(required=False, example='dd/mm/yyyy', missing=None,
                               description='start date like dd/mm/yyyy')
    end_date = fields.String(required=False, example='dd/mm/yyyy', missing=None,
                             description='end date like dd/mm/yyyy')
    start_time = fields.String(required=False, example='0:00 AM', missing=None, description='start time like 0:00 AM')
    interval = fields.String(required=False, example='24hrs', missing=None, description='job interval like 24hrs')
    timezone = fields.String(required=False, example='Europe/Rome', missing=None, description='job timezone')
    enabled = fields.Boolean(required=False, example=True, missing=None, description='job enable status')
    instances = fields.Nested(UpdateComputeZoneBackupJobInstanceRequestSchema, required=False, many=True,
                              allow_none=True, description='list of instance to add or remove')


class UpdateComputeZoneBackupJobBodyRequestSchema(Schema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')
    job = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1', context='path',
                        description='job id')
    body = fields.Nested(UpdateComputeZoneBackupJobRequestSchema, context='body')


class UpdateComputeZoneBackupJobResponseSchema(Schema):
    job = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1', description='job id')


class UpdateComputeZoneBackupJob(ProviderComputeZone):
    summary = 'Update compute zone backup job'
    description = 'Update compute zone backup job'
    definitions = {
        'UpdateComputeZoneBackupJobRequestSchema': UpdateComputeZoneBackupJobRequestSchema,
        'UpdateComputeZoneBackupJobResponseSchema': UpdateComputeZoneBackupJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateComputeZoneBackupJobBodyRequestSchema)
    parameters_schema = UpdateComputeZoneBackupJobRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': UpdateComputeZoneBackupJobResponseSchema
        }
    })

    def put(self, controller, data, oid, job, *args, **kwargs):
        compute_zone = controller.get_resource(oid)
        resp = compute_zone.update_backup_job(job, **data)
        return {'job': resp}


# class DeleteComputeZoneBackupJobRequestSchema(Schema):
#     job = fields.String(required=True, description='id of the job', context='path')
#     site = fields.String(required=True, example='Test', description='availability zone name')
#     hypervisor = fields.String(required=False, example='openstack', missing='openstack',
#                                description='hypervisor like openstack or vsphere')
#     hypervisor_tag = fields.String(required=False, example='default', missing='default', description='hypervisor tag')
#     resource_type = fields.String(required=False, example='ComputeInstance', missing='ComputeInstance',
#                                   description='type of resource managed by job. Can be: ComputeInstance')


class DeleteComputeZoneBackupJobBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')
    job = fields.String(required=True, description='id of the job', context='path')
    # body = fields.Nested(DeleteComputeZoneBackupJobRequestSchema, context='body')


class DeleteComputeZoneBackupJobResponseSchema(Schema):
    job = fields.String(required=True, example='4cdf0ea4-159a-45aa-96f2-708e461130e1', description='job id')


class DeleteComputeZoneBackupJob(ProviderComputeZone):
    summary = 'Delete compute zone backup job'
    description = 'Delete compute zone backup job'
    definitions = {
        # 'DeleteComputeZoneBackupJobRequestSchema': DeleteComputeZoneBackupJobRequestSchema,
        'DeleteComputeZoneBackupJobResponseSchema': DeleteComputeZoneBackupJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteComputeZoneBackupJobBodyRequestSchema)
    # parameters_schema = DeleteComputeZoneBackupJobRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': DeleteComputeZoneBackupJobResponseSchema
        }
    })

    def delete(self, controller, data, oid, job, *args, **kwargs):
        compute_zone = controller.get_resource(oid)
        # job = data.pop('job')
        # site = data.pop('site')
        resp = compute_zone.delete_backup_job(job)
        return {'job': resp}


#
# backup restore points
#
class GetComputeZoneBackupRestorePointsItemResponseSchema(Schema):
    hypervisor = fields.String(required=True, example='job1', description='hypervisor like openstack or vsphere')
    site = fields.String(required=True, example='job1', description='availability zone name')
    resource_type = fields.String(required=True, example='job1', description='type of resource managed by job')
    instances = fields.Int(required=True, example=1, description='number if instances configured in job')
    id = fields.String(required=True, example='job1', description='job id')
    name = fields.String(required=True, example='job1', description='job name')
    created = fields.String(required=True, example='job1', description='job creation date')
    updated = fields.String(required=True, example='job1', description='job update date')
    error = fields.String(required=True, example='job1', description='job error')
    usage = fields.String(required=True, example='job1', description='job storage usage')
    status = fields.String(required=True, example='job1', description='job status')
    type = fields.String(required=True, example='job1', description='job type')
    schedule = fields.Dict(required=True, example='job1', description='job schedule')


class GetComputeZoneBackupRestorePointsResponseSchema(Schema):
    restore_points = fields.Nested(GetComputeZoneBackupRestorePointsItemResponseSchema, required=True, many=True,
                                   allow_none=True)


class GetComputeZoneBackupRestorePointsRequestSchema(Schema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')
    job_id = fields.String(required=False, missing=None, description='id of the backup job', context='query')
    restore_point_id = fields.String(required=False, missing=None, context='query',
                                     description='id of the backup job restore point')


class GetComputeZoneBackupRestorePoints(ProviderComputeZone):
    summary = 'Get compute zone backup job restore points'
    description = 'Get compute zone backup job restore points'
    definitions = {
        'GetComputeZoneBackupRestorePointsResponseSchema': GetComputeZoneBackupRestorePointsResponseSchema,
        'GetComputeZoneBackupRestorePointsRequestSchema': GetComputeZoneBackupRestorePointsRequestSchema
    }
    parameters = SwaggerHelper().get_parameters(GetComputeZoneBackupRestorePointsRequestSchema)
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': GetComputeZoneBackupRestorePointsResponseSchema
        }
    })

    def get(self, controller, data, oid, *args, **kwargs):
        compute_zone: ComputeZone = controller.get_resource(oid)
        job_id = data.get('job_id')
        restore_point_id = data.get('restore_point_id')
        resp = compute_zone.get_backup_restore_points(job_id, restore_point_id=restore_point_id)
        return {'restore_points': resp}


class AddComputeZoneBackupRestorePointRequestSchema(Schema):
    job_id = fields.String(required=True, example='default', description='hypervisor tag')
    name = fields.String(required=True, example='restore_point1', description='restore point name')
    desc = fields.String(required=False, example='restore_point1', missing=None,
                         description='restore point description')
    full = fields.Boolean(required=False, example=True, missing=True,
                          description='if True create a full restore point type, otherwise crate an incremental')


class AddComputeZoneBackupRestorePointBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')
    body = fields.Nested(AddComputeZoneBackupRestorePointRequestSchema, context='body')


class AddComputeZoneBackupRestorePoint(ProviderComputeZone):
    summary = 'Add compute zone backup job restore point'
    description = 'Add compute zone backup job restore point'
    definitions = {
        'AddComputeZoneBackupRestorePointRequestSchema': AddComputeZoneBackupRestorePointRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(AddComputeZoneBackupRestorePointBodyRequestSchema)
    parameters_schema = AddComputeZoneBackupRestorePointRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def post(self, controller, data, oid, *args, **kwargs):
        compute_zone = controller.get_resource(oid)
        job_id = data.get('job_id')
        name = data.get('name')
        desc = data.get('desc')
        full = data.get('full')
        resp = compute_zone.create_backup_restore_point(job_id, name, desc=desc, full=full)
        return resp


class DeleteComputeZoneBackupRestorePointRequestSchema(Schema):
    job_id = fields.String(required=True, example='default', description='hypervisor tag')
    restore_point_id = fields.String(required=True, example='restore_point1', description='restore point id')


class DeleteComputeZoneBackupRestorePointBodyRequestSchema(GetApiObjectRequestSchema):
    oid = fields.String(required=True, description='id, uuid or name of the parent compute zone', context='path')
    body = fields.Nested(DeleteComputeZoneBackupRestorePointRequestSchema, context='body')


class DeleteComputeZoneBackupRestorePoint(ProviderComputeZone):
    summary = 'Delete compute zone backup job restore point'
    description = 'Delete compute zone backup job restore point'
    definitions = {
        'DeleteComputeZoneBackupRestorePointRequestSchema': DeleteComputeZoneBackupRestorePointRequestSchema,
        'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteComputeZoneBackupRestorePointBodyRequestSchema)
    parameters_schema = DeleteComputeZoneBackupRestorePointRequestSchema
    responses = SwaggerApiView.setResponses({
        200: {
            'description': 'success',
            'schema': CrudApiObjectTaskResponseSchema
        }
    })

    def delete(self, controller, data, oid, *args, **kwargs):
        compute_zone = controller.get_resource(oid)
        job_id = data.get('job_id')
        restore_point_id = data.get('restore_point_id')
        resp = compute_zone.delete_backup_restore_point(job_id, restore_point_id)
        return resp


class ComputeZoneAPI(ProviderAPI):
    """
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # - filter by: tags
            ('%s/compute_zones' % base, 'GET', ListComputeZones, {}),
            ('%s/compute_zones/<oid>' % base, 'GET', GetComputeZone, {}),
            ('%s/compute_zones' % base, 'POST', CreateComputeZone, {}),
            ('%s/compute_zones/<oid>' % base, 'PUT', UpdateComputeZone, {}),
            ('%s/compute_zones/<oid>' % base, 'DELETE', DeleteComputeZone, {}),
            ('%s/compute_zones/<oid>/sites' % base, 'POST', AddSite, {}),
            ('%s/compute_zones/<oid>/sites' % base, 'DELETE', DeleteSite, {}),

            ('%s/compute_zones/<oid>/availability_zones' % base, 'GET', ListSite, {}),
            ('%s/compute_zones/<oid>/availability_zones' % base, 'POST', AddSite, {}),
            ('%s/compute_zones/<oid>/availability_zones' % base, 'DELETE', DeleteSite, {}),

            ('%s/compute_zones/<oid>/childs' % base, 'GET', GetComputeZoneChilds, {}),

            ('%s/compute_zones/<oid>/quotas' % base, 'GET', GetComputeZoneQuotas, {}),
            ('%s/compute_zones/<oid>/quotas/classes' % base, 'GET', GetComputeZoneQuotaClasses, {}),
            ('%s/compute_zones/<oid>/quotas' % base, 'PUT', SetComputeZoneQuotas, {}),
            ('%s/compute_zones/<oid>/quotas/check' % base, 'PUT', CheckComputeZoneQuotas, {}),

            ('%s/compute_zones/<oid>/manage' % base, 'GET', GetManage, {}),
            ('%s/compute_zones/<oid>/manage' % base, 'POST', AddManage, {}),
            ('%s/compute_zones/<oid>/manage' % base, 'DELETE', DeleteManage, {}),

            ('%s/compute_zones/<oid>/metrics' % base, 'GET', GetComputeZoneMetrics, {}),

            ('%s/compute_zones/<oid>/sshkeys' % base, 'GET', GetComputeZoneSshKeys, {}),

            ('%s/compute_zones/<oid>/backup/jobs' % base, 'GET', GetComputeZoneBackupJobs, {}),
            ('%s/compute_zones/<oid>/backup/jobs/<job>' % base, 'GET', GetComputeZoneBackupJob, {}),
            ('%s/compute_zones/<oid>/backup/jobs' % base, 'POST', AddComputeZoneBackupJob, {}),
            ('%s/compute_zones/<oid>/backup/jobs/<job>' % base, 'PUT', UpdateComputeZoneBackupJob, {}),
            ('%s/compute_zones/<oid>/backup/jobs/<job>' % base, 'DELETE', DeleteComputeZoneBackupJob, {}),

            ('%s/compute_zones/<oid>/backup/restore_points' % base, 'GET', GetComputeZoneBackupRestorePoints, {}),
            ('%s/compute_zones/<oid>/backup/restore_points' % base, 'POST', AddComputeZoneBackupRestorePoint, {}),
            ('%s/compute_zones/<oid>/backup/restore_points' % base, 'DELETE', DeleteComputeZoneBackupRestorePoint, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
