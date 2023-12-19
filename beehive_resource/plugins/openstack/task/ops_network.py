# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from celery import chain, chord, group, signature
from beecell.simple import get_value, import_class
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_pre,
    create_resource_post,
    expunge_resource_pre,
    expunge_resource_post,
    update_resource_post,
    update_resource_pre,
)
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, task_local, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.openstack.controller import *
from beehive.common.data import operation
from beedrones.openstack.client import OpenstackNotFound

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def network_create_entity(self, options):
    """Create openstack network

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
    parent_ext_id = params.get("parent_ext_id")
    name = params.get("name")
    shared = params.get("shared")
    # tenant_id = params.get('tenant_id')
    qos_policy_id = params.get("qos_policy_id")
    external = params.get("external")
    segments = params.get("segments")
    physical_network = params.get("physical_network")
    network_type = params.get("network_type")
    segmentation_id = params.get("segmentation_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn

    # create openstack network
    inst = conn.network.create(
        name,
        parent_ext_id,
        physical_network,
        shared,
        qos_policy_id,
        external,
        segments,
        network_type,
        segmentation_id,
    )
    inst_id = inst["id"]
    self.update("PROGRESS", msg="Create network %s - Starting" % inst_id)

    # loop until entity is not stopped or get error
    while True:
        inst = container.conn.network.get(oid=inst_id)
        status = inst["status"]
        if status == "ACTIVE":
            break
        if status == "ERROR":
            self.update("PROGRESS", msg="Create network %s - Error" % inst_id)
            raise Exception("Can not create network %s" % (name))

        # update task
        self.update("PROGRESS")

        # sleep a little
        gevent.sleep(task_local.delta)
    self.update("PROGRESS", msg="Create network %s - Completed" % inst_id)

    # save current data in shared area
    params["ext_id"] = inst_id
    params["attrib"] = None
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def network_update_entity(self, options):
    """Update openstack network

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
    ext_id = params.get("ext_id")
    name = params.get("name")
    shared = params.get("shared")
    qos_policy_id = params.get("qos_policy_id")
    external = params.get("external")
    segments = params.get("segments")
    self.update("PROGRESS", msg="Get configuration params")

    # get openstack network
    self.get_session()
    container = self.get_container(cid)

    # update openstack network
    conn = container.conn

    if ext_id is not None:
        conn.network.update(ext_id, name, shared, qos_policy_id, external, segments)
        self.update("PROGRESS", msg="Update network %s - Starting" % ext_id)

        # loop until entity is not stopped or get error
        while True:
            inst = container.conn.network.get(oid=ext_id)
            status = inst["status"]
            if status == "ACTIVE":
                break
            if status == "ERROR":
                self.update("PROGRESS", msg="Update network %s - Error" % ext_id)
                raise Exception("Can not update network %s" % (name))

            # update task
            self.update("PROGRESS")

            # sleep a little
            gevent.sleep(task_local.delta)
        self.update("PROGRESS", msg="Update network %s - Completed" % ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def network_delete_entity(self, options):
    """Delete openstack network

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
    # oid = params.get('id')
    ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    container = self.get_container(cid)

    if ext_id is not None:
        conn = container.conn

        # delete openstack network
        conn.network.delete(ext_id)
        self.update("PROGRESS", msg="Delete network %s" % ext_id)

    return ext_id


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackNetwork, name="insert", delta=1)
def job_network_create(self, objid, params):
    """Create openstack network

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

            * **parent_ext_id**: parent project physical id
            * **shared**: [default=false] Indicates whether this network is shared
                across all tenants. By default, only administrative users can
                change this value.
            * **qos_policy_id**: [optional] Admin-only. The UUID of the QoS
                policy associated with this network. The policy will need to have
                been created before the network to associate it with.
            * **external**: [optional] Indicates whether this network is externally
                accessible.
            * **segments**: [optional] A list of provider segment objects.
            * **physical_network**: [optional] The physical network where
                this network object is implemented. The Networking API v2.0 does not
                provide a way to list available physical networks. For example, the
                Open vSwitch plug-in configuration file defines a symbolic name that
                maps to specific bridges on each Compute host.
            * **network_type**: [default=vlan] The type of physical network
                that maps to this network resource. For example, flat, vlan, vxlan,
                or gre.
            * **segmentation_id**: [optional] An isolated segment on the
                physical network. The network_type attribute defines the
                segmentation model. For example, if the network_type value is vlan,
                this ID is a vlan identifier. If the network_type value is gre, this
                ID is a gre key.

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            network_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackNetwork, name="update", delta=1)
def job_network_update(self, objid, params):
    """Update openstack network

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): resource physical id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            update_resource_post,
            network_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackNetwork, name="delete", delta=1)
def job_network_delete(self, objid, params):
    """Delete openstack network

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): resource physical id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            expunge_resource_post,
            network_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
