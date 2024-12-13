# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.common.task.job import job_task, job, Job
from beehive.common.task.manager import task_manager
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.task.openstack import ProviderOpenstack
from beehive_resource.plugins.provider.task.vsphere import ProviderVsphere
from beehive_resource.tasks import ResourceJobTask, ResourceJob
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def add_orchestrator_task(self, options):
    """Add orchestrator

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

            * **cid** (int): container id
            * **site_id** (int): site id
            * **orchestrator_id** (int): orchestrator id
            * **orchestrator_type** (str): Orchestrator type. Ex. vsphere, openstack
            * **orchestrator_tag** (str): Orchestrator tag. Ex. default
            * **config** (dict): Orchestrator configuration

    **Return:**

    """
    params = self.get_shared_data()

    # validate input params
    site_id = params.get("site_id")
    orchestrator_id = params.get("orchestrator_id")
    orchestrator_type = params.get("orchestrator_type")
    orchestrator_tag = params.get("orchestrator_tag")
    orchestrator_config = params.get("orchestrator_config")
    self.update("PROGRESS", msg="Get configuration params")

    # get resource
    self.get_session()
    resource = self.get_resource(site_id, details=False)

    # base orchestrator
    data = {
        "type": orchestrator_type,
        "id": orchestrator_id,
        "tag": orchestrator_tag,
        "config": orchestrator_config,
    }

    # create project/folder
    if orchestrator_type == "vsphere":
        datacenter = orchestrator_config["datacenter"]
        folder_id = ProviderVsphere.create_folder(self, orchestrator_id, resource, datacenter, None)
        data["config"]["folder"] = folder_id

    elif orchestrator_type == "openstack":
        domain = orchestrator_config["domain"]
        project_id = ProviderOpenstack.create_project(self, orchestrator_id, resource, domain, None)
        data["config"]["project"] = project_id

    # update resource
    self.get_session()
    attribute = resource.get_attribs()
    attribute["orchestrators"].append(data)
    resource.update_internal(attribute=attribute)
    self.update("PROGRESS", msg="Update resource %s" % site_id)

    return orchestrator_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def delete_orchestrator_task(self, options):
    """Delete orchestrator

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

            * **cid** (int): container id
            * **site_id** (int): site id
            * **orchestrator_id** (int): orchestrator id
            * **orchestrator_type** (str): Orchestrator type. Ex. vsphere, openstack

    **Return:**

    """
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    site_id = params.get("site_id")
    orchestrator_id = params.get("orchestrator_id")
    orchestrator_type = params.get("orchestrator_type")
    self.update("PROGRESS", msg="Get configuration params")

    # get resource
    self.get_session()
    container = self.get_container(cid)
    resource = self.get_resource(site_id, details=False)

    # get all child resources
    childs = self.get_linked_resources(site_id, link_type="relation", container_id=orchestrator_id)

    # delete all childs
    if orchestrator_type == "vsphere":
        resp = ProviderVsphere.remove_resource(self, container, orchestrator_id, childs)
    elif orchestrator_type == "openstack":
        resp = ProviderOpenstack.remove_resource(self, container, orchestrator_id, childs)

    # update resource
    orchestrators = resource.get_orchestrators()
    orchestrators.pop(orchestrator_id)
    attribute = resource.get_attribs()
    attribute["orchestrators"] = orchestrators.values()
    logger.warn(attribute)
    resource.update_internal(attribute=attribute)
    self.update(
        "PROGRESS",
        msg="Delete orchestrator %s from site %s" % (orchestrator_id, site_id),
    )

    return orchestrator_id


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Site, name="orchestrator-add.update", delta=1)
def job_add_orchestrator(self, objid, params):
    """Add openstack orchestrator

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **site_id** (int): site id
            * **orchestrator_id** (int): orchestrator id
            * **orchestrator_type** (str): Orchestrator type. Ex. vsphere, openstack
            * **orchestrator_tag** (str): Orchestrator tag. Ex. default
            * **config** (dict): Orchestrator configuration

                Vsphere orchestrator:

                * **datacenter**: Ex. 4,
                * **resource_pool**: Ex. 298
                * **physical_network**: Ex. 346

                Openstack orchestrator:

                * **domain**: Ex. 1459,
                * **availability_zone**: Ex. nova
                * **physical_network**: Ex. datacentre
                * **public_network**: Ex. internet

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            add_orchestrator_task,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=Site, name="orchestrator-delete.update", delta=1)
def job_delete_orchestrator(self, objid, params):
    """Delete openstack orchestrator

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **site_id** (int): site id
            * **orchestrator_id** (int): orchestrator id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            delete_orchestrator_task,
            start_task,
        ],
        ops,
    ).delay()
    return True


# #
# # NETWORK JOB
# #
# # external network
# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=SiteNetwork, name='network.insert', delta=1)
# def job_site_network_create(self, objid, params):
#     """Create external network.
#     """
#     return job_network_create(self, objid, params)
#
#
# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=SiteNetwork, name='network.update', delta=1)
# def job_site_network_update(self, objid, params):
#     """Update external network
#     """
#     return job_network_update(self, objid, params)
#
#
# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=SiteNetwork, name='network.delete', delta=1)
# def job_site_network_delete(self, objid, params):
#     """Delete external network
#     """
#     return job_network_delete(self, objid, params)


# @task_manager.task(bind=True, base=ResourceJob)
# @job(entity_class=SiteNetwork, name='network.add_network.update', delta=1)
# def job_site_network_add_network(self, objid, params):
#     """Add vsphere network to provider network
#     """
#     return job_network_add_network(self, objid, params)
