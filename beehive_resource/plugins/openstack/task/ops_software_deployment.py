# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import ujson as json
from celery.utils.log import get_task_logger
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_pre,
    create_resource_post,
    expunge_resource_pre,
    expunge_resource_post,
    update_resource_pre,
    update_resource_post,
)
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, task_local, Job, JobError
from beehive.common.task.util import end_task, start_task
import gevent
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack

logger = get_task_logger(__name__)


def get_client(task, cid, project_id):
    task.get_session()
    container = task.get_container(cid, projectid=project_id)
    conn = container.conn
    task.update("PROGRESS", msg="Get container %s" % cid)
    return conn


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def create_swift_items(self, options):
    """Create swift items

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    stack_id = params.get("stack_id")
    project_id = params.get("project_id")
    resource_id = params.get("resource_id")
    cid = params.get("cid")
    self.update("PROGRESS", msg="Get configuration params")

    client = get_client(self, cid, project_id)

    """
    create swift container
    create swift key
    create swift container object
    create swift temp URL
    """

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def create_software_deployment(self, options):
    """Create software config and deployment

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    stack_id = params.get("stack_id")
    project_id = params.get("project_id")
    resource_id = params.get("resource_id")
    cid = params.get("cid")
    self.update("PROGRESS", msg="Get configuration params")

    client = get_client(self, cid, project_id)

    """
    create software config
    """

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def check_swift_object(self, options):
    """Check swift object

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    stack_id = params.get("stack_id")
    project_id = params.get("project_id")
    resource_id = params.get("resource_id")
    cid = params.get("cid")
    self.update("PROGRESS", msg="Get configuration params")

    client = get_client(self, cid, project_id)

    """
    [
      {
        "deploy_stdout": "",
        "deploy_stderr": "+ mysql -u root '--password=nnn' -e 'DROP USER IF EXISTS '\\''prova'\\''@'\\''%'\\''; DROP DATABASE IF EXISTS prova;'\nmysql: [Warning] Using a password on the command line interface can be insecure.\n",
        "deploy_status_code": 0
      },
      {
        "content-length": "275",
        "accept-ranges": "bytes",
        "last-modified": "Tue, 16 Jan 2018 14:58:21 GMT",
        "etag": "858df8ad8f1620b9e725e14dca7b4d37",
        "x-timestamp": "1516114700.79924",
        "x-trans-id": "tx7cbed03c88db4967a955f-005a5e1339",
        "date": "Tue, 16 Jan 2018 14:59:05 GMT",
        "content-type": "application/json",
        "x-openstack-request-id": "tx7cbed03c88db4967a955f-005a5e1339"
      }
    ]
    until content-length > 0

    store in shared area
      {
        "deploy_stdout": "",
        "deploy_stderr": "+ mysql -u root '--password=nnn' -e 'DROP USER IF EXISTS '\\''prova'\\''@'\\''%'\\''; DROP DATABASE IF EXISTS prova;'\nmysql: [Warning] Using a password on the command line interface can be insecure.\n",
        "deploy_status_code": 0
      },

    """

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def update_software_deployment(self, options):
    """Update software deployment

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    stack_id = params.get("stack_id")
    project_id = params.get("project_id")
    resource_id = params.get("resource_id")
    cid = params.get("cid")
    self.update("PROGRESS", msg="Get configuration params")

    client = get_client(self, cid, project_id)

    """
    if deploy_status_code = 0 update software deployemnt <config> <deploy> status_reason="Outputs received" status="COMPLETE"
    """

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def remove_swift_items(self, options):
    """Remove swift items

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    stack_id = params.get("stack_id")
    project_id = params.get("project_id")
    resource_id = params.get("resource_id")
    cid = params.get("cid")
    self.update("PROGRESS", msg="Get configuration params")

    client = get_client(self, cid, project_id)

    """
    remove swift container object
    remove swift key
    """

    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackHeatStack, name="insert", delta=3)
def job_software_deployment_apply(self, objid, params):
    """Run an openstack heat software deployment

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **stack_id**: stack oid
            * **project_id**: stack parent project oid
            * **resource_id**: resource id where apply software deployment
            * **cid**: container id


    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            remove_swift_items,
            update_software_deployment,
            check_swift_object,
            create_software_deployment,
            create_swift_items,
            start_task,
        ],
        ops,
    ).delay()
    return True
