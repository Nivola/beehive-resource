# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectTaskResponseSchema,
)
from beehive_resource.view import ResourceResponseSchema, ListResourcesRequestSchema
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject


class OpenstackVolumeApiView(OpenstackApiView):
    resclass = OpenstackVolume
    parentclass = OpenstackProject


class ListVolumesRequestSchema(ListResourcesRequestSchema):
    pass


class ListVolumesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListVolumesResponseSchema(PaginatedResponseSchema):
    volumes = fields.Nested(ResourceResponseSchema, many=True, required=True, allow_none=True)


class ListVolumes(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "ListVolumesResponseSchema": ListVolumesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListVolumesRequestSchema)
    parameters_schema = ListVolumesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListVolumesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List volume
        List volume
        """
        return self.get_resources(controller, **data)


class GetVolumeResponseSchema(Schema):
    volume = fields.Nested(ResourceResponseSchema, required=True, allow_none=True)


class GetVolume(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "GetVolumeResponseSchema": GetVolumeResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetVolumeResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get volume
        Get volume
        """
        return self.get_resource(controller, oid)


class CreateVolumeParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="container id, uuid or name")
    name = fields.String(required=True, example="test", description="name")
    desc = fields.String(required=True, example="test", description="name")
    project = fields.String(required=True, example="23", description="project id, uuid or name")
    tags = fields.String(example="prova", default="", description="comma separated list of tags")
    size = fields.Int(required=True, default=20, description="volume size in GB")
    availability_zone = fields.String(required=True, example="1", description="Specify the availability zone")
    source_volid = fields.String(
        required=False,
        missing=None,
        description="The UUID of the source volume. The API "
        "creates a new volume with the same size as the source volume.",
    )
    snapshot_id = fields.String(
        required=False,
        missing=None,
        description="To create a volume from an existing "
        "snapshot, specify the UUID of the volume snapshot. The volume is created in same "
        "availability zone and with same size as the snapshot.",
    )
    imageRef = fields.String(
        required=False,
        missing=None,
        description="The UUID of the image from which you want to "
        "create the volume. Required to create a bootable volume.",
    )
    volume_type = fields.String(
        required=True,
        example=None,
        description="The volume type. To create an environment "
        "with multiple-storage back ends, you must specify a volume type.",
    )
    metadata = fields.Dict(
        required=False,
        missing=None,
        description="One or more metadata key and value pairs that " "are associated with the volume",
    )


class CreateVolumeRequestSchema(Schema):
    volume = fields.Nested(CreateVolumeParamRequestSchema)


class CreateVolumeBodyRequestSchema(Schema):
    body = fields.Nested(CreateVolumeRequestSchema, context="body")


class CreateVolume(OpenstackVolumeApiView):
    tags = ["openstack"]
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


class UpdateVolumeParamRequestSchema(Schema):
    name = fields.String(default="test")
    desc = fields.String(default="test")
    enabled = fields.Boolean(default=True)


class UpdateVolumeRequestSchema(Schema):
    volume = fields.Nested(UpdateVolumeParamRequestSchema)


class UpdateVolumeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeRequestSchema, context="body")


class UpdateVolume(OpenstackVolumeApiView):
    tags = ["openstack"]
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


class DeleteVolume(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {"CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, *args, **kwargs):
        return self.expunge_resource(controller, oid)


class CloneVolumeParamRequestSchema(Schema):
    name = fields.String(required=True, default="test", example="test", description="cloned volume name")
    project = fields.String(
        required=True,
        default="test",
        example="test",
        description="cloned volume project id",
    )


class CloneVolumeRequestSchema(Schema):
    volume = fields.Nested(CloneVolumeParamRequestSchema)


class CloneVolumeBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(CloneVolumeRequestSchema, context="body")


class CloneVolume(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "CloneVolumeRequestSchema": CloneVolumeRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CloneVolumeBodyRequestSchema)
    parameters_schema = CloneVolumeRequestSchema
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Clone volume
        Clone volume
        """
        obj = self.get_resource_reference(controller, oid)
        data = data.get("volume")
        name = data.get("name")
        project = data.get("project")
        res = obj.clone(name, project)
        return res


class GetVolumeMetadataResponseSchema(Schema):
    volume_metadata = fields.Dict(required=True)
    image_metadata = fields.Dict(required=True)


class GetVolumeMetadata(OpenstackVolumeApiView):
    definitions = {
        "GetVolumeMetadataResponseSchema": GetVolumeMetadataResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetVolumeMetadataResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get server metadata
        Get server metadata
        """
        obj = self.get_resource_reference(controller, oid)
        res = obj.get_metadata()
        res1 = obj.get_image_metadata()
        resp = {"volume_metadata": res, "image_metadata": res1, "count": len(res)}
        return resp


class GetVolumeSnapshotResponseSchema(Schema):
    created_at = fields.String(default="2019-07-30T13:52:48.234880")
    description = fields.String(default="prova")
    id = fields.String(default="2c528eb9-d26d-4c50-abbc-a302462d344c")
    metadata = fields.Dict(default={})
    name = fields.String(default="snapshot-e542569fc0")
    size = fields.Integer(default=10)
    status = fields.String(default="creating")
    updated_at = fields.String(default="2019-07-30T13:52:48.234880")
    volume_id = fields.String(default="2a41a3a2-07eb-432e-b3a1-e6850901a9c8")


class ListVolumeSnapshotsResponseSchema(Schema):
    snapshots = fields.Nested(GetVolumeSnapshotResponseSchema, required=True, allow_none=True, many=True)


class ListVolumeSnapshots(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "ListVolumeSnapshotsResponseSchema": ListVolumeSnapshotsResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": ListVolumeSnapshotsResponseSchema}}
    )

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get volume shapshots
        Get volume shapshots
        """
        volume = self.get_resource_reference(controller, oid)
        snapshots = volume.list_snapshots()
        return {"snapshots": snapshots, "count": len(snapshots)}


class GetVolumeSnapshotResponseSchema(GetApiObjectRequestSchema):
    sid = fields.String(required=True, description="id, uuid or name of the snapshot", context="path")


class GetVolumeSnapshot(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "GetVolumeSnapshotResponseSchema": GetVolumeSnapshotResponseSchema,
        # 'GetVolumeSnapshotResponseSchema': GetVolumeSnapshotResponseSchema
    }
    parameters = SwaggerHelper().get_parameters(GetVolumeSnapshotResponseSchema)
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetVolumeSnapshotResponseSchema}}
    )

    def get(self, controller, data, oid, sid, *args, **kwargs):
        """
        Get volume shapshots
        Get volume shapshots
        """
        volume = self.get_resource_reference(controller, oid)
        snapshot = volume.get_snapshot(sid)
        return {"snapshot": snapshot}


class CreateVolumeSnapshotParamRequestSchema(Schema):
    name = fields.String(default="prova", example="prova", description="Name of the snapshot")


class CreateVolumeSnapshotRequestSchema(Schema):
    snapshot = fields.Nested(UpdateVolumeParamRequestSchema)


class CreateVolumeSnapshotBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateVolumeRequestSchema, context="body")


class CreateVolumeSnapshotResponseSchema(Schema):
    snapshot = fields.Nested(GetVolumeSnapshotResponseSchema, required=True, allow_none=True)


class CreateVolumeSnapshot(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "CreateVolumeSnapshotBodyRequestSchema": CreateVolumeSnapshotBodyRequestSchema,
        "CreateVolumeSnapshotResponseSchema": CreateVolumeSnapshotResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateVolumeSnapshotBodyRequestSchema)
    parameters_schema = CreateVolumeSnapshotRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": CreateVolumeSnapshotResponseSchema}}
    )

    def post(self, controller, data, oid, *args, **kwargs):
        """
        Get volume shapshots
        Get volume shapshots
        """
        volume = self.get_resource_reference(controller, oid)
        snapshot = volume.add_snapshot(data.get("snapshot").get("name"))
        return {"snapshot": snapshot}


class RevertVolumeSnapshotRequestSchema(GetApiObjectRequestSchema):
    sid = fields.String(required=True, description="snapshot uuid", context="path")


class RevertVolumeSnapshot(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "RevertVolumeSnapshotRequestSchema": RevertVolumeSnapshotRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(RevertVolumeSnapshotRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def put(self, controller, data, oid, sid, *args, **kwargs):
        volume = self.get_resource_reference(controller, oid)
        volume.revert_snapshot(sid)
        return {"joibid": None, "uuid": volume.uuid}


class DeleteVolumeSnapshotRequestSchema(GetApiObjectRequestSchema):
    sid = fields.String(required=True, description="snapshot uuid", context="path")


class DeleteVolumeSnapshot(OpenstackVolumeApiView):
    tags = ["openstack"]
    definitions = {
        "DeleteVolumeSnapshotRequestSchema": DeleteVolumeSnapshotRequestSchema,
        "CrudApiObjectTaskResponseSchema": CrudApiObjectTaskResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteVolumeSnapshotRequestSchema)
    responses = SwaggerApiView.setResponses(
        {202: {"description": "success", "schema": CrudApiObjectTaskResponseSchema}}
    )

    def delete(self, controller, data, oid, sid, *args, **kwargs):
        volume = self.get_resource_reference(controller, oid)
        volume.delete_snapshot(sid)
        return {"joibid": None, "uuid": volume.uuid}


class OpenstackVolumeAPI(OpenstackAPI):
    """Openstack base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ("%s/volumes" % base, "GET", ListVolumes, {}),
            ("%s/volumes/<oid>" % base, "GET", GetVolume, {}),
            ("%s/volumes" % base, "POST", CreateVolume, {}),
            ("%s/volumes/<oid>" % base, "PUT", UpdateVolume, {}),
            ("%s/volumes/<oid>" % base, "DELETE", DeleteVolume, {}),
            ("%s/volumes/<oid>/clone" % base, "POST", CloneVolume, {}),
            ("%s/volumes/<oid>/metadata" % base, "GET", GetVolumeMetadata, {}),
            ("%s/volumes/<oid>/snapshots" % base, "GET", ListVolumeSnapshots, {}),
            ("%s/volumes/<oid>/snapshots/<sid>" % base, "GET", GetVolumeSnapshot, {}),
            ("%s/volumes/<oid>/snapshots" % base, "POST", CreateVolumeSnapshot, {}),
            # ('%s/volumes/<oid>/snapshots/<sid>' % base, 'PUT', UpdateVolumeSnapshot, {}),
            (
                "%s/volumes/<oid>/snapshots/<sid>" % base,
                "DELETE",
                DeleteVolumeSnapshot,
                {},
            ),
            # ('%s/volumes/<oid>/snapshots/<sid>/revert' % base, 'PUT', RevertVolumeSnapshot, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
