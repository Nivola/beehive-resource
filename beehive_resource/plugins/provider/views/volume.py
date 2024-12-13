# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.volume import ComputeVolume
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
    ApiManagerError,
    CrudApiTaskResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    UpdateProviderResourceRequestSchema,
    CreateProviderResourceRequestSchema,
)


class ProviderVolume(LocalProviderApiView):
    resclass = ComputeVolume
    parentclass = ComputeZone


class ListVolumesRequestSchema(ListResourcesRequestSchema):
    compute_zone = fields.String(context="query", description="instance name or uuid")
    instance = fields.String(context="query", description="instance name or uuid")
    type = fields.String(context="query", description="volume type name or uuid")


class VolumeResponseSchema(ResourceResponseSchema):
    size = fields.Int(required=True, default=20, description="volume size in GB")


class ListVolumesResponseSchema(PaginatedResponseSchema):
    volumes = fields.Nested(VolumeResponseSchema, many=True, required=True, allow_none=True)


class ListVolumes(ProviderVolume):
    definitions = {
        "ListVolumesRequestSchema": ListVolumesRequestSchema,
        "ListVolumesResponseSchema": ListVolumesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVolumesRequestSchema)
    parameters_schema = ListVolumesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVolumesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List volumes
        List volumes
        """
        zone_id = data.get("compute_zone", None)
        inst_id = data.get("instance", None)
        type_id = data.get("type", None)

        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, **data)
        elif inst_id is not None:
            return self.get_linked_resources(controller, inst_id, ComputeInstance, **data)
        elif type_id is not None:
            return self.get_linked_resources(controller, type_id, ComputeVolumeFlavor, **data)
        return self.get_resources(controller, **data)


class GetVolumeResponseSchema(Schema):
    volume = fields.Nested(VolumeResponseSchema, required=True, allow_none=True)


class GetVolume(ProviderVolume):
    definitions = {
        "GetVolumeResponseSchema": GetVolumeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVolumeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get volume
        Get volume

        RunState:
        - noState
        - poweredOn
        - blocked
        - suspended
        - poweredOff
        - crashed
        - resize [only openstack volume]
        - update [only openstack volume]
        - deleted [only openstack volume]
        - reboot [only openstack volume]
        """
        return self.get_resource(controller, oid)


class CreateVolumeParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    availability_zone = fields.String(example="2", required=True, description="availability zone id")
    multi_avz = fields.Boolean(
        example=False,
        missing=True,
        required=False,
        description="Define if volume must be deployed to work in all the availability zones",
    )
    type = fields.String(
        required=True,
        example="vsphere",
        description="type of the volume: vsphere or openstack",
    )
    flavor = fields.String(required=True, example="12", description="id or uuid of the flavor")
    metadata = fields.Dict(
        required=False,
        example={"My Server Name": "Apache1"},
        missing={},
        description="One or more metadata key and value pairs that are associated with the volume",
    )
    volume = fields.String(
        required=False,
        missing=None,
        description="Id or name of the source volume. The API creates"
        " a new volume with the same size as the source volume.",
    )
    snapshot = fields.String(
        required=False,
        missing=None,
        description="To create a volume from an existing "
        "snapshot, specify the id or name of the volume snapshot. The volume is created in same "
        "availability zone and with same size as the snapshot.",
    )
    image = fields.String(
        required=False,
        missing=None,
        description="Id or name of the image from which you want to " "create the volume",
    )
    size = fields.Int(required=True, default=20, description="volume size in GB")


class CreateVolumeRequestSchema(Schema):
    volume = fields.Nested(CreateVolumeParamRequestSchema)


class CreateVolumeBodyRequestSchema(Schema):
    body = fields.Nested(CreateVolumeRequestSchema, context="body")


class CreateVolume(ProviderVolume):
    definitions = {
        "CreateVolumeRequestSchema": CreateVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVolumeBodyRequestSchema)
    parameters_schema = CreateVolumeRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """
        Create volume
        Create volume
        """
        return self.create_resource(controller, data)


class ImportVolumeParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    resource_id = fields.String(required=True, example="1", description="id of the physical resource to import")
    # type = fields.String(required=True, example='vsphere', description='type of the volume: vsphere or openstack')


class ImportVolumeRequestSchema(Schema):
    volume = fields.Nested(ImportVolumeParamRequestSchema)


class ImportVolumeBodyRequestSchema(Schema):
    body = fields.Nested(ImportVolumeRequestSchema, context="body")


class ImportVolume(ProviderVolume):
    definitions = {
        "ImportVolumeRequestSchema": ImportVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ImportVolumeBodyRequestSchema)
    parameters_schema = ImportVolumeRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, *args, **kwargs):
        """
        Import volume
        Import volume
        """
        return self.import_resource(controller, data)


class UpdateVolumeParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateVolumeRequestSchema(Schema):
    volume = fields.Nested(UpdateVolumeParamRequestSchema)


class UpdateVolumeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeRequestSchema, context="body")


class UpdateVolume(ProviderVolume):
    definitions = {
        "UpdateVolumeRequestSchema": UpdateVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateVolumeBodyRequestSchema)
    parameters_schema = UpdateVolumeRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update volume
        Update volume
        """
        return self.update_resource(controller, oid, data)


class DeleteVolume(ProviderVolume):
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete volume
        Delete volume
        """
        return self.expunge_resource(controller, oid)


# class GetVolumeSnapshotResponseSchema(Schema):
#     created_at = fields.String(default='2019-07-30T13:52:48.234880')
#     description = fields.String(default='prova')
#     id = fields.String(default='2c528eb9-d26d-4c50-abbc-a302462d344c')
#     metadata = fields.Dict(default={})
#     name = fields.String(default='snapshot-e542569fc0')
#     size = fields.Integer(default=10)
#     status = fields.String(default='creating')
#     updated_at = fields.String(default='2019-07-30T13:52:48.234880')
#
#
# class ListVolumeSnapshotsResponseSchema(Schema):
#     snapshots = fields.Nested(GetVolumeSnapshotResponseSchema, required=True, allow_none=True, many=True)
#
#
# class ListVolumeSnapshots(ProviderVolume):
#     definitions = {
#         'ListVolumeSnapshotsResponseSchema': ListVolumeSnapshotsResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': ListVolumeSnapshotsResponseSchema
#         }
#     })
#
#     def get(self, controller, data, oid, *args, **kwargs):
#         """
#         Get volume shapshots
#         Get volume shapshots
#         """
#         volume = self.get_resource_reference(controller, oid)
#         snapshots = volume.list_snapshots()
#         return {'snapshots': snapshots, 'count': len(snapshots)}
#
#
# class CreateVolumeSnapshotParamRequestSchema(Schema):
#     name = fields.String(default='prova', example='prova', description='Name of the snapshot')
#
#
# class CreateVolumeSnapshotRequestSchema(Schema):
#     snapshot = fields.Nested(UpdateVolumeParamRequestSchema)
#
#
# class CreateVolumeSnapshotBodyRequestSchema(GetApiObjectRequestSchema):
#     body = fields.Nested(UpdateVolumeRequestSchema, context='body')
#
#
# class CreateVolumeSnapshotResponseSchema(Schema):
#     snapshot = fields.Nested(GetVolumeSnapshotResponseSchema, required=True, allow_none=True)
#
#
# class CreateVolumeSnapshot(ProviderVolume):
#     definitions = {
#         'CreateVolumeSnapshotBodyRequestSchema': CreateVolumeSnapshotBodyRequestSchema,
#         'CreateVolumeSnapshotResponseSchema': CreateVolumeSnapshotResponseSchema,
#     }
#     parameters = SwaggerHelper().get_parameters(CreateVolumeSnapshotBodyRequestSchema)
#     parameters_schema = CreateVolumeSnapshotRequestSchema
#     responses = SwaggerApiView.setResponses({
#         200: {
#             'description': 'success',
#             'schema': CreateVolumeSnapshotResponseSchema
#         }
#     })
#
#     def post(self, controller, data, oid, *args, **kwargs):
#         """
#         Get volume shapshots
#         Get volume shapshots
#         """
#         volume = self.get_resource_reference(controller, oid)
#         snapshot = volume.add_snapshot(data.get('snapshot').get('name'))
#         return {'snapshot': snapshot}
#
#
# class RevertVolumeSnapshotRequestSchema(GetApiObjectRequestSchema):
#     sid = fields.String(required=True, description='snapshot uuid', context='path')
#
#
# class RevertVolumeSnapshot(ProviderVolume):
#     definitions = {
#         'RevertVolumeSnapshotRequestSchema': RevertVolumeSnapshotRequestSchema,
#         'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(RevertVolumeSnapshotRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectTaskResponseSchema
#         }
#     })
#
#     def put(self, controller, data, oid, sid, *args, **kwargs):
#         volume = self.get_resource_reference(controller, oid)
#         volume.revert_snapshot(sid)
#         return {'joibid': None, 'uuid': volume.uuid}
#
#
# class DeleteVolumeSnapshotRequestSchema(GetApiObjectRequestSchema):
#     sid = fields.String(required=True, description='snapshot uuid', context='path')
#
#
# class DeleteVolumeSnapshot(ProviderVolume):
#     tags = ['openstack']
#     definitions = {
#         'DeleteVolumeSnapshotRequestSchema': DeleteVolumeSnapshotRequestSchema,
#         'CrudApiObjectTaskResponseSchema': CrudApiObjectTaskResponseSchema
#     }
#     parameters = SwaggerHelper().get_parameters(DeleteVolumeSnapshotRequestSchema)
#     responses = SwaggerApiView.setResponses({
#         202: {
#             'description': 'success',
#             'schema': CrudApiObjectTaskResponseSchema
#         }
#     })
#
#     def delete(self, controller, data, oid, sid, *args, **kwargs):
#         volume = self.get_resource_reference(controller, oid)
#         volume.delete_snapshot(sid)
#         return {'joibid': None, 'uuid': volume.uuid}


class SendVolumeActionParamsMigrateRequestSchema(Schema):
    live = fields.Boolean(
        required=False,
        missing=False,
        default=True,
        description="If True attempt to run a live migration",
    )
    flavor = fields.String(required=True, example="12", description="id or uuid of the volume flavor")


class SendVolumeActionParamsRequestSchema(Schema):
    set_flavor = fields.Nested(SendVolumeActionParamsMigrateRequestSchema, description="change volume flavor")


class SendVolumeActionRequestSchema(Schema):
    action = fields.Nested(SendVolumeActionParamsRequestSchema, required=True)
    schedule = fields.Dict(
        required=False,
        missing=None,
        description="schedule to use when you want to run a scheduled " "action",
    )


class SendVolumeActionBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(SendVolumeActionRequestSchema, context="body")


class SendVolumeAction(ProviderVolume):
    summary = "Send server action"
    description = "Send server action"
    definitions = {
        "SendVolumeActionRequestSchema": SendVolumeActionRequestSchema,
        "CrudApiTaskResponseSchema": CrudApiTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(SendVolumeActionBodyRequestSchema)
    parameters_schema = SendVolumeActionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiTaskResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        volume = self.get_resource_reference(controller, oid)
        actions = data.get("action")
        schedule = data.get("schedule")
        action = list(actions.keys())[0]
        params = actions[action]
        if not isinstance(params, dict):
            params = {"param": params}
        volume.check_active()
        if action in volume.actions:
            if schedule is not None:
                task = volume.scheduled_action(action, schedule=schedule, params=params)
            else:
                task = volume.action(action, **params)
        else:
            raise ApiManagerError("Action %s not supported for volume" % action)

        return task


class VolumeProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            ("%s/volumes" % base, "GET", ListVolumes, {}),
            ("%s/volumes/<oid>" % base, "GET", GetVolume, {}),
            ("%s/volumes" % base, "POST", CreateVolume, {}),
            # ('%s/volumes/import' % base, 'POST', ImportVolume, {}),
            ("%s/volumes/<oid>" % base, "PUT", UpdateVolume, {}),
            ("%s/volumes/<oid>" % base, "DELETE", DeleteVolume, {}),
            # ('%s/volumes/<oid>/actions' % base, 'GET', GetVolumeActions, {}),
            # ('%s/volumes/<oid>/actions/<aid>' % base, 'GET', GetVolumeAction, {}),
            ("%s/volumes/<oid>/actions" % base, "PUT", SendVolumeAction, {}),
            # ('%s/volumes/<oid>/snapshots' % base, 'GET', ListVolumeSnapshots, {}),
            # ('%s/volumes/<oid>/snapshots' % base, 'POST', CreateVolumeSnapshot, {}),
            # ('%s/volumes/<oid>/snapshots/<sid>' % base, 'DELETE', DeleteVolumeSnapshot, {}),
            # ('%s/volumes/<oid>/snapshots/<sid>/revert' % base, 'PUT', RevertVolumeSnapshot, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
