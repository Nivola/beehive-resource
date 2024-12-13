# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beecell.types.type_dict import dict_get
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.share import ComputeFileShare, FileShare
from beehive_resource.plugins.provider.task_v2 import (
    AbstractProviderResourceTask,
    orchestrator_mapping,
)

logger = getLogger(__name__)


class ComputeFileShareTask(AbstractProviderResourceTask):
    """ComputeFileShare task"""

    name = "file_share_task"
    entity_class = ComputeFileShare

    @staticmethod
    @task_step()
    def create_compute_share_link_step(task: AbstractProviderResourceTask, step_id, params, *args, **kvargs):
        """Create compute_share link

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        network = params.get("network")

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg="Get resource %s" % oid)

        # - link network to share
        vpc_id = network["vpc"]
        attribs = {"vlan": network.get("vlan", None)}
        resource.add_link("%s-%s-vpc-link" % (oid, vpc_id), "vpc", vpc_id, attributes=attribs)
        task.progress(step_id, msg="Link vpc %s to share %s" % (vpc_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def create_zone_share_step(
        task: AbstractProviderResourceTask,
        step_id,
        params,
        availability_zone_id,
        main,
        *args,
        **kvargs,
    ):
        """Create zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param int availability_zone_id: availability zone id
        :param bool main: if True this is the main zone
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        orchestrator_type = params.get("type")
        task.progress(step_id, msg="Get resources")

        # create zone instance params
        share_params = {
            "type": orchestrator_type,
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone share %s" % params.get("desc"),
            "parent": availability_zone_id,
            "compute_share": oid,
            "share_proto": params.get("share_proto"),
            "size": params.get("size", 0),
            # 'snapshot_id': params.get('snapshot_id'),
            # 'share_group_id':  params.get('share_group_id'),
            "orchestrator_tag": params.get("orchestrator_tag"),
            "orchestrator_type": params.get("orchestrator_type"),
            "network": params.get("network"),
            "tags": params.get("tags"),
            "metadata": params.get("metadata"),
            "main": main,
            "attribute": {"main": main, "type": params.get("type")},
        }

        if orchestrator_type == "ontap":
            share_params["attribute"]["ontap_volume"] = dict_get(params, "attribute.ontap_volume")

        prepared_task, code = provider.resource_factory(FileShare, **share_params)
        share_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create share %s in availability zone %s" % (share_id, availability_zone_id),
        )

        return share_id, params

    @staticmethod
    @task_step()
    def import_zone_share_step(
        task: AbstractProviderResourceTask,
        step_id,
        params,
        availability_zone_id,
        *args,
        **kvargs,
    ):
        """Import zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param dict params: step params:param availability_zone_id: availability zone id
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        resource_id = params.get("physical_id")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        orchestrator_type = params.get("type")
        task.progress(step_id, msg="Get resources")

        # create zone share params
        share_params = {
            "type": orchestrator_type,
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Availability Zone volume %s" % params.get("desc"),
            "parent": availability_zone_id,
            "compute_share": oid,
            "share_proto": params.get("share_proto"),
            "size": params.get("size", 0),
            "network": params.get("network"),
            "main": True,
            "physical_id": resource_id,
            "attribute": {"main": True, "type": params.get("type"), "configs": {}},
        }

        if orchestrator_type == "ontap":
            share_params["attribute"]["ontap_volume"] = dict_get(params, "attribute.ontap_volume")

        prepared_task, code = provider.resource_import_factory(FileShare, **share_params)
        share_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Import share %s in availability zone %s" % (share_id, availability_zone_id),
        )

        return share_id, params

    @staticmethod
    @task_step()
    def update_zone_share_step(
        task: AbstractProviderResourceTask,
        step_id,
        params,
        zone_share_id,
        *args,
        **kvargs,
    ):
        """Update compute_share instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param int zone_share_id: availability zone share id
        :return: oid, params
        """
        oid = params.get("id")
        size = params.get("size", None)
        grant = params.get("grant", None)

        compute_share = task.get_simple_resource(oid)
        zone_share = task.get_simple_resource(zone_share_id)
        avz_id = zone_share.parent_id
        task.progress(step_id, msg="Get resources")

        # update size
        if size is not None:
            old_size = params.get("attribute").get("size")
            prepared_task, code = zone_share.update_size(old_size, size)
            run_sync_task(prepared_task, task, step_id)
            task.progress(
                step_id,
                msg="Update share %s size in availability zone %s" % (oid, avz_id),
            )

            # update attributes
            compute_share.set_configs(key="size", value=size)

        # set grant
        if grant is not None:
            prepared_task, code = zone_share.grant_set(grant)
            run_sync_task(prepared_task, task, step_id)
            task.progress(
                step_id,
                msg="Update share %s grant in availability zone %s" % (oid, avz_id),
            )

        return zone_share_id, params

    @staticmethod
    @task_step()
    def link_share_step(task: AbstractProviderResourceTask, step_id, params, *args, **kvargs):
        """Link share to compute share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        compute_share_id = params.get("compute_share")
        availability_zone_id = params.get("parent")
        oid = params.get("id")

        compute_share = task.get_simple_resource(compute_share_id)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        compute_share.add_link("%s-share-link" % oid, "relation.%s" % site_id, oid, attributes={})
        task.progress(step_id, msg="Link share %s to compute share %s" % (oid, compute_share_id))

        return oid, params

    @staticmethod
    @task_step()
    def create_main_share_step(task: AbstractProviderResourceTask, step_id, params, *args, **kvargs):
        """Create zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        main = params.get("main")
        oid = params.get("id")
        availability_zone_id = params.get("parent")
        compute_share_id = params.get("compute_share")

        availability_zone = task.get_simple_resource(availability_zone_id)
        compute_share = task.get_simple_resource(compute_share_id)
        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg="Get resource %s" % oid)

        # create share
        share_id = None
        if main is True:
            # get main orchestrator
            main_orchestrator_id = params.get("main_orchestrator")
            orchestrator = params.get("orchestrators").get(main_orchestrator_id)
            orchestrator_type = orchestrator.get("type")

            # get remote parent for share
            if orchestrator_type == "ontap":
                parent = None
            else:
                objdef = orchestrator_mapping(orchestrator_type, 0)
                parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

            helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)
            share_id = helper.create_share(parent, params, compute_share)
            task.progress(step_id, msg="Create share: %s" % share_id)

        return share_id, params

    @staticmethod
    @task_step()
    def import_main_share_step(task: AbstractProviderResourceTask, step_id, params, *args, **kvargs):
        """Import main share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        orchestrator_type = params.get("type")
        resource_id = params.get("physical_id")

        resource = task.get_simple_resource(oid)
        remote_share = task.get_simple_resource(resource_id)
        task.progress(step_id, msg="Get resource %s" % oid)

        helper = task.get_orchestrator(orchestrator_type, task, step_id, {}, resource)
        share_id = helper.import_share(remote_share.oid)
        task.progress(step_id, msg="Import main share: %s" % share_id)

        return share_id, params
