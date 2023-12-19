# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.volume import Volume
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_compute_volume(self, options):
    """Create compute_volume resource - pre task

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")
    image_id = params.get("image")
    flavor_id = params.get("flavor")
    self.progress("Get configuration params")

    # get instance resource
    self.get_session()
    resource = self.get_resource(oid, run_customize=False)
    self.progress("Get resource %s" % oid)

    # link image to volume
    if image_id is not None:
        resource.add_link("%s-%s-image-link" % (oid, image_id), "image", image_id, attributes={})
        self.progress("Link image %s to volume %s" % (image_id, oid))

    # link flavor to volume
    resource.add_link("%s-%s-flavor-link" % (oid, flavor_id), "flavor", flavor_id, attributes={})
    self.progress("Link flavor %s to volume %s" % (flavor_id, oid))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_volume(self, options, availability_zone_id):
    """Create zone volume.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :return: resource physical id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    flavor_id = params.get("flavor")
    image_id = params.get("image")
    volume_id = params.get("volume")
    snapshot_id = params.get("snapshot")
    self.progress("Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    # compute_volume = self.get_resource(oid, run_customize=False)
    site_id = availability_zone.parent_id
    self.progress("Get resources")

    # verify volume is main or twin
    # - volume is main
    if availability_zone_id == params.get("main_availability_zone"):
        # set main to True because it is the main zone volume
        main = True

        # get availability zone image
        if image_id is not None:
            image = self.get_orm_linked_resources(image_id, link_type="relation.%s" % site_id)[0]
            image_id = image.id

        # get availability zone volume
        if volume_id is not None:
            volume = self.get_orm_linked_resources(volume_id, link_type="relation.%s" % site_id)[0]
            volume_id = volume.id

        # get availability zone flavor
        flavor = self.get_orm_linked_resources(flavor_id, link_type="relation.%s" % site_id)[0]
        flavor_id = flavor.id

    # - volume is a twin. Get fixed ip from main volume
    else:
        # set main to False because this main zone volume is a twin
        main = False

    if main is True:
        # create zone volume params
        volume_params = {
            "type": params.get("type"),
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Availability Zone volume %s" % params.get("desc"),
            "parent": availability_zone_id,
            "compute_volume": oid,
            "orchestrator_tag": params.get("orchestrator_tag"),
            "orchestrator_id": params.get("orchestrator_id"),
            "flavor": flavor_id,
            "volume": volume_id,
            "snapshot": snapshot_id,
            "image": image_id,
            "size": params.get("size"),
            "metadata": params.get("metadata"),
            "main": main,
            "attribute": {"main": main, "type": params.get("type"), "configs": {}},
        }
        res = provider.resource_factory(Volume, **volume_params)
        job_id = res[0]["jobid"]
        volume_id = res[0]["uuid"]
        self.progress("Create volume in availability zone %s - start job %s" % (availability_zone_id, job_id))

        # wait for job complete
        self.wait_for_job_complete(job_id)
        self.progress("Create volume %s in availability zone %s" % (volume_id, availability_zone_id))

    return volume_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_zone_volume(self, options, availability_zone_id):
    """Import zone volume.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :return: resource physical id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    flavor_id = params.get("flavor")
    resource_id = params.get("physical_id")
    self.progress("Set configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    self.progress("Get resources")

    # get availability zone flavor
    flavor = self.get_orm_linked_resources(flavor_id, link_type="relation.%s" % site_id)[0]
    flavor_id = flavor.id

    # create zone volume params
    volume_params = {
        "type": params.get("type"),
        "name": "%s-avz%s" % (params.get("name"), site_id),
        "desc": "Availability Zone volume %s" % params.get("desc"),
        "parent": availability_zone_id,
        "compute_volume": oid,
        # 'orchestrator_tag': params.get('orchestrator_tag'),
        # 'orchestrator_id': params.get('orchestrator_id'),
        "flavor": flavor_id,
        "size": params.get("size"),
        "metadata": params.get("metadata"),
        "main": True,
        "physical_id": resource_id,
        "attribute": {"main": True, "type": params.get("type"), "configs": {}},
    }
    res = provider.resource_import_factory(Volume, **volume_params)
    job_id = res[0]["jobid"]
    volume_id = res[0]["uuid"]
    self.progress("Create volume in availability zone %s - start job %s" % (availability_zone_id, job_id))

    # wait for job complete
    self.wait_for_job_complete(job_id)
    self.progress("Create volume %s in availability zone %s" % (volume_id, availability_zone_id))

    return volume_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_volume(self, options):
    """Link zone volume to compute volume

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    compute_volume_id = params.get("compute_volume")
    availability_zone_id = params.get("parent")
    oid = params.get("id")
    self.progress("Get configuration params")

    # link volume to compute volume
    self.get_session()
    compute_volume = self.get_resource(compute_volume_id, run_customize=False)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    compute_volume.add_link("%s-volume-link" % oid, "relation.%s" % site_id, oid, attributes={})
    self.progress("Link volume %s to compute volume %s" % (oid, compute_volume_id))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_main_volume(self, options):
    """Create main volume

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()

    oid = params.get("id")
    self.logger.warn(params)
    compute_volume = params.get("compute_volume")
    availability_zone_id = params.get("parent")
    orchestrators = params.get("orchestrators")
    self.progress("Get configuration params")

    # get resources
    self.get_session()
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    volume = self.get_resource(oid, run_customize=False)
    self.progress("Get resource %s" % oid)

    # get main orchestrator
    main_orchestrator_id = params.get("main_orchestrator")
    orchestrator = orchestrators.get(main_orchestrator_id)

    # get remote parent for volume
    objdef = orchestrator_mapping(orchestrator["type"], 0)
    parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

    volume_id = ProviderOrchestrator.get(orchestrator.get("type")).create_volume(
        self, orchestrator, compute_volume, volume, parent, params
    )
    self.progress("Create main volume: %s" % volume_id)

    return volume_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_main_volume(self, options):
    """Import main volume

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    oid = params.get("id")
    orchestrator_type = params.get("type")
    resource_id = params.get("physical_id")
    self.progress("Get configuration params")

    # get resources
    self.get_session()
    volume = self.get_resource(oid, run_customize=False)
    remote_volume = self.get_resource(resource_id, run_customize=False)
    self.progress("Get resource %s" % oid)

    volume_id = ProviderOrchestrator.get(orchestrator_type).import_volume(self, volume, remote_volume.oid)
    self.progress("Import main volume: %s" % volume_id)

    return volume_id
