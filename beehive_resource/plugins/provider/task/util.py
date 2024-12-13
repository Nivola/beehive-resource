# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive.module.scheduler.tasks import job_task
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def remove_remote_resource(self, options, orchestrator_id, orchestrator_type):
    """Delete resource in remote orchestrator

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **orchestrator_id: remote orchestrator it
        * **orchestrator_type** (str): remote orchestrator type
        * **sharedarea:

    :return:

        delete response

    """
    params = self.get_shared_data()
    # cid = params.get('cid')
    resource = params.get("id")
    self.update("PROGRESS", msg="Get configuration params")

    # get parent resource
    self.get_session()
    container = None
    # container = self.get_container(cid)

    # get all child resources
    childs = self.get_linked_resources(resource, link_type="relation", container_id=orchestrator_id)

    # delete all childs
    # if orchestrator_type == 'vsphere':
    #     resp = ProviderVsphere.remove_resource(self, container, orchestrator_id, childs)
    # elif orchestrator_type == 'openstack':
    #     resp = ProviderOpenstack.remove_resource(self, container, orchestrator_id, childs)

    resp = ProviderOrchestrator.get(orchestrator_type).remove_resource(self, container, orchestrator_id, childs)

    return resp


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def compute_resource_remove_child(self, options, resource_id):
    """Remove compute resource childs.

    :param options: Tupla with some options. (class_name, objid, job, job id, start time, time before new query, user)
    :param resource_id: resource id
    :param sharedarea:
    :param int sharedarea.cid: container id
    :return: True
    """
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    # oid = params.get('oid')
    self.update("PROGRESS", msg="Set configuration params")

    # get provider
    self.get_session()
    # provider = self.get_container(cid)
    resource = self.get_resource(resource_id)
    self.update("PROGRESS", msg="Get provider %s" % cid)

    # delete child
    # - run celery job
    job = resource.expunge()
    job_id = job[0]["jobid"]
    self.update("PROGRESS", msg="Remove child %s - start job %s" % (resource_id, job_id))

    # - wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update("PROGRESS", msg="Remove child %s" % resource_id)

    return True
