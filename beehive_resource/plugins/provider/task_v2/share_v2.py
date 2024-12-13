# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beecell.types.type_dict import dict_get
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.share_v2 import ComputeFileShareV2, FileShareV2
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class ComputeFileShareV2Task(AbstractProviderResourceTask):
    """ComputeFileShareV2 task"""

    name = "file_share_v2_task"
    entity_class = ComputeFileShareV2

    @staticmethod
    @task_step()
    def link_compute_share_step(task: AbstractProviderResourceTask, step_id, params, *args, **kvargs):
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

        # link network to share
        vpc_id = network["vpc"]
        resource.add_link("%s-%s-vpc-link" % (oid, vpc_id), "vpc", vpc_id)
        task.progress(step_id, msg="Link vpc %s to share %s" % (vpc_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def create_zone_share_step(
        task: AbstractProviderResourceTask,
        step_id,
        params,
        availability_zone_id,
        *args,
        **kwargs,
    ):
        """Create zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param int availability_zone_id: availability zone id
        :param bool main: if True this is the main zone
        :return: oid, params
        """
        task.progress(msg="%s - %s - %s" % (params, args, kwargs))  # DEBUG
        cid = params.get("cid")
        oid = params.get("id")

        task.progress(step_id, msg="Getting resources")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        orchestrator_type = params.get("orchestrator_type")
        orchestrator_tag = params.get("orchestrator_tag")

        task.progress(step_id, msg="Determining awx project")

        awx_orchestrator_tag = params.get("awx_orchestrator_tag", "V2")
        customization_name = f"staas-{awx_orchestrator_tag}"
        # get customization
        from beehive_resource.plugins.provider.entity.customization import (
            ComputeCustomization,
        )
        from beehive_resource.plugins.awx.entity.awx_project import AwxProject

        compute_customization: ComputeCustomization = task.get_simple_resource_by_name_and_entity_class(
            customization_name, ComputeCustomization
        )
        customization = compute_customization.get_local_resource(site_id)
        awx_project = customization.get_physical_resource_from_container(None, AwxProject.objdef)
        # same as above, but also gets container and executres resource post_get
        # awx_project2 = customization.get_physical_resource(AwxProject.objdef)

        task.progress(step_id, msg="Creating zone resource")
        # create zone entity params
        share_params = {
            "orchestrator_type": orchestrator_type,
            "orchestrator_tag": orchestrator_tag,
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone share %s" % params.get("name"),
            "parent": availability_zone_id,
            # "compute_share": oid, # CHECK
            "share_params": params.get("share_params"),
            "attribute": {
                "type": orchestrator_type,
                "tag": orchestrator_tag,
            },
            "awx_orchestrator_tag": awx_orchestrator_tag,
            "awx_project_id": awx_project.oid,
        }

        prepared_task, code = provider.resource_factory(FileShareV2, **share_params)
        share_id = prepared_task["uuid"]

        # link share to compute share
        task.get_session(reopen=True)
        task.progress(step_id, msg="Linking share %s to compute share %s" % (share_id, oid))
        compute_share = task.get_simple_resource(oid)
        compute_share.add_link(
            "%s-share-link" % share_id,
            "relation.%s" % site_id,
            share_id,
            attributes={},
        )

        # wait for task to complete
        task.progress(step_id, msg="Waiting until creation task finishes")
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Created share %s in availability zone %s" % (share_id, availability_zone_id))

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

        prepared_task, code = provider.resource_import_factory(FileShareV2, **share_params)
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
        print("DEBUG link_share_step: %s - %s - %s" % (params, compute_share, availability_zone))
        compute_share.add_link("%s-share-link" % oid, "relation.%s" % site_id, oid, attributes={})
        task.progress(step_id, msg="Link share %s to compute share %s" % (oid, compute_share_id))

        return oid, params

    @staticmethod
    @task_step()
    def create_physical_share_step(task: AbstractProviderResourceTask, step_id, params, *args, **kwargs):
        """Create zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        task.progress(step_id, msg="Getting params")

        oid = params.get("id")
        orchestrator = params.get("orchestrator")

        # get container
        ontap_container = task.get_container(orchestrator["id"])

        # construct remote name (aside from - _ conversion)
        share_params = params.get("share_params")
        svm = share_params.get("svm")
        vol_name = share_params.pop("vol_name")
        name = f"{svm}-{vol_name}-{id_gen(6)}"

        # name = params.get("name")
        # name = "%s-%s-share" % (name, ontap_container.oid)

        task.progress(step_id, msg="Determining awx container and parameters")

        # select awx orchestrator
        awx_orchestrator_tag = params.get("awx_orchestrator_tag", "V2")
        availability_zone_id = params.get("parent")
        availability_zone = task.get_simple_resource(availability_zone_id)
        awx_orchestrators = availability_zone.get_orchestrators_by_tag(awx_orchestrator_tag, select_types=["awx"])
        awx_orchestrator = list(awx_orchestrators.values())[0]

        # TODO grab and pass all needed configuration
        # raise Exception("%s - %s" % (awx_orchestrator,dir(awx_orchestrator)))
        # get awx inventory
        from beecell.simple import dict_get

        # inventories = dict_get(awx_orchestrator, "config.inventories", default=[])
        # if len(inventories) < 1:
        #    raise Exception("no awx inventory configured for orchestrator %s" % awx_orchestrator["id"])
        # inventory = inventories[0]
        # inventory_id = inventory.get("id")
        # ssh_cred_id = inventory.get("credential")
        # config.organization
        awx_organization = dict_get(awx_orchestrator, "config.organization")
        # TODO get vault credentials.

        task.progress(step_id, msg="Creating physical resource")
        # create remote share
        volume_params = {
            "name": name,
            "desc": f"volume {name}",
            "awx_orchestrator_id": awx_orchestrator.get("id"),
            "awx_organization_id": awx_organization,
            "awx_project_id": params.get("awx_project_id"),
            "share_params": params.get("share_params"),
        }
        prepared_task, code = ontap_container.resource_factory(OntapNetappVolume, **volume_params)
        volume_id = prepared_task.get("uuid")

        # link ontap volume to share
        task.get_session(reopen=True)
        share = task.get_simple_resource(oid)
        task.progress(step_id, msg="Linking volume %s to zone share %s" % (volume_id, oid))
        share.add_link("%s-%s-link" % (id_gen(), oid), "relation", volume_id, attributes={})

        task.progress(step_id, msg="Waiting until creation task finishes.")
        run_sync_task(prepared_task, task, step_id)

        task.progress(step_id, msg="Created volume %s in zone %s" % (volume_id, oid))
        return True, params

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
