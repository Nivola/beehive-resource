# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.task.job import job_task
from beehive.common.task.manager import task_manager
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_compute_zone_set_quotas(self, options):
    """Set compute zone quotas

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: True
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    quotas = params.get("quotas")
    zones = params.get("availability_zones")
    orchestrator_tag = params.get("orchestrator_tag")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    resource = self.get_resource(oid)

    attribs = resource.get_attribs()
    attribs["quota"].update(quotas)
    resource.manager.update_resource(oid=oid, attribute=attribs)
    self.update("PROGRESS", msg="Update compute zone %s quotas: %s" % (oid, quotas))

    # update child availability zones
    for zone in zones:
        zone_resource = self.get_resource(zone)
        res = zone_resource.set_quotas(quotas=quotas, orchestrator_tag=orchestrator_tag)
        job_id = res[0]["jobid"]

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.update(
            "PROGRESS",
            msg="Update compute zone %s availability zone %s quotas: %s" % (oid, zone, quotas),
        )

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_availability_zone_link_resource(self, options):
    """Link availability zone resource to compute zone.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: id of the removed resource
    """
    params = self.get_shared_data()

    oid = params.get("id")
    site_id = params.get("site")
    zone_id = params.get("zone")

    # link zone to super zone
    self.get_session()
    zone = self.get_resource(zone_id)
    zone.add_link("%s-zone-link" % oid, "relation.%s" % site_id, oid, attributes={})
    self.update("PROGRESS", msg="Link availability zone %s to compute zone %s" % (oid, zone_id))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_availability_zone_create_orchestrator_resource(self, options, orchestrator_id):
    """Set availability zone quotas in remote orchestrator

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator_id: orchestrator id
    :param dict sharedarea: input params
    :return: uuid of the removed resource
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    site_id = params.get("site")
    orchestrators = params.get("orchestrators")
    quotas = params.get("quota")
    self.update("PROGRESS", msg="Get configuration params")

    # get container configuration
    orchestrator = orchestrators[orchestrator_id]

    # get availability_zone
    self.get_session()
    # container = self.get_container(cid)
    resource = self.get_resource(oid)
    site = self.get_resource(site_id)
    self.update("PROGRESS", msg="Get availability_zone %s" % cid)

    # create physical entities
    ProviderOrchestrator.get(orchestrator.get("type")).create_zone_childs(
        self, orchestrator, resource, site, quotas=quotas
    )

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_availability_zone_set_quotas(self, options):
    """Set availability zone quotas

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: uuid of the removed resource
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    quotas = params.get("quotas")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    resource = self.get_resource(oid)
    attribs = resource.get_attribs()
    attribs["quota"].update(quotas)
    resource.manager.update_resource(oid=oid, attribute=attribs)
    self.update("PROGRESS", msg="Update compute zone %s quotas: %s" % (oid, quotas))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_availability_zone_set_orchestrator_quotas(self, options, orchestrator, orchestrator_type):
    """Set availability zone quotas in remote orchestartor

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator id
    :param orchestrator_type: orchestrator type
    :param dict sharedarea: input params
    :return: uuid of the removed resource
    """
    self.set_operation()

    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    quotas = params.get("quotas")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    resource = self.get_resource(oid)
    ProviderOrchestrator.get(orchestrator_type).set_quotas(self, orchestrator, resource, quotas)

    return True
