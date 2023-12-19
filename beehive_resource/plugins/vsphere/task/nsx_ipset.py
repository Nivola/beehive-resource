# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_pre,
    create_resource_post,
    expunge_resource_pre,
    expunge_resource_post,
)
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beedrones.vsphere.client import VsphereNotFound
from beehive_resource.plugins.vsphere.entity.nsx_ipset import NsxIpSet

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_ipset_create_entity(self, options):
    """Create nsx ipset.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    # ext_id = params.get('instance_id')
    name = params.get("name")
    desc = params.get("desc")
    cidr = params.get("cidr")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    container = self.get_container(cid)
    self.update("PROGRESS", msg="Get container %s" % cid)

    # create nsx ipset
    conn = container.conn
    inst_id = conn.network.nsx.ipset.create(name, desc, cidr)
    self.update("PROGRESS", msg="Create nsx ip set %s" % inst_id)

    # save current data in shared area
    params["ext_id"] = inst_id
    params["attrib"] = {"cidr": cidr}
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_ipset_delete_entity(self, options):
    """Delete nsx ipset.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid")
    # id = params.get('id')
    ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get conatiner
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # delete vsphere ipset
    if ext_id is not None:
        try:
            conn.network.nsx.ipset.delete(ext_id)
            self.update("PROGRESS", msg="Delete nsx ip set %s" % ext_id)
        except VsphereNotFound:
            self.update("PROGRESS", msg="Nsx ip set %s does not exist anymore" % ext_id)

    return ext_id


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxIpSet, name="insert", delta=1)
def job_ipset_create(self, objid, params):
    """Create nsx ipset.


    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **objid**: resource objid
            * **parent**: resource parent id
            * **cid**: container id
            * **name**: resource name
            * **desc**: resource desc
            * **ext_id**: resource ext_id
            * **active**: resource active
            * **attribute** (:py:class:`dict`): attributes
            * **tags**: comma separated resource tags to assign [default='']
            * **cidr**: ip set cidr. Ex. 10.102.34.90/32

    Params
        Params contains:

        * **cid**: container id
        * **name**: ip set name
        * **desc**: ip set description [optional]
        * **parent**: resource parent
        * **cidr**: ip set cidr. Ex. 10.102.34.90/32

        .. code-block:: python

            {
                'cid':..,
                'name':..,
                'desc':..,
                'parent':..,
                'cidr':..,
            }
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            nsx_ipset_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxIpSet, name="delete", delta=1)
def job_ipset_delete(self, objid, params):
    """Delete nsx ipset

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param cid: container id
    :param params: task input params
    :return: True
    :rtype: bool

    Params
        Params contains:

        * **cid**: container id
        * **id**: ipset id
        * **ext_id**: resource remote platform id

        .. code-block:: python

            {
                'cid':..,
                'id':..,
                'ext_id':..
            }
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            expunge_resource_post,
            nsx_ipset_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
