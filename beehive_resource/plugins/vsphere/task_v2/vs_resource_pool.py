# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.vsphere.entity.vs_resource_pool import VsphereResourcePool
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class ResourcePoolTask(AbstractResourceTask):
    """ResourcePool task"""

    name = "resource_pool_task"
    entity_class = VsphereResourcePool

    @staticmethod
    @task_step()
    def resource_pool_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create vsphere resource pool

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid", None)
        name = params.get("name", None)
        cluster_ext_id = params.get("cluster_ext_id", None)
        cpu = params.get("cpu", None)
        memory = params.get("memory", None)
        shares = params.get("shares", "normal")

        container = task.get_container(cid)
        conn = container.conn
        cluster = conn.cluster.get(cluster_ext_id)

        # create vsphere resourcepool
        inst = conn.cluster.resource_pool.create(cluster, name, cpu, memory, shares)
        inst_id = inst._moId
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Create vsphere resource pool: %s" % inst_id)

        return inst_id, params

    @staticmethod
    @task_step()
    def resource_pool_update_physical_step(task, step_id, params, *args, **kvargs):
        """Create vsphere resource pool

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid", None)
        oid = params.get("id", None)
        name = params.get("name", None)
        cpu = params.get("cpu", None)
        memory = params.get("memory", None)
        shares = params.get("shares", "normal")

        container = task.get_container(cid)
        conn = container.conn

        # get parent dvs
        respool_obj = container.get_resource(oid)
        respool = conn.cluster.resource_pool.get(respool_obj.ext_id)

        # create vsphere resourcepool
        conn.cluster.resource_pool.update(respool, name, cpu, memory, shares)
        inst_id = respool_obj.ext_id

        return inst_id, params

    @staticmethod
    @task_step()
    def resource_pool_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Create vsphere resource pool

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid", None)
        oid = params.get("id")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        # delete vsphere network
        if resource.is_ext_id_valid() is True:
            respool = conn.cluster.resource_pool.get(resource.ext_id)

            if respool is None:
                task.progress(
                    step_id,
                    msg="resource pool %s does not exist anymore" % resource.ext_id,
                )
            else:
                vsphere_task = conn.cluster.resource_pool.remove(respool)
                # loop until vsphere task has finished
                container.query_remote_task(task, step_id, vsphere_task)

            task.progress(step_id, msg="delete physical resource pool: %s" % resource.ext_id)

        # reset ext_id
        resource.update_internal(ext_id=None)

        return oid, params
