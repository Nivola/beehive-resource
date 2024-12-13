# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from time import sleep
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class NetworkTask(AbstractResourceTask):
    """Network task"""

    name = "network_task"
    entity_class = OpenstackNetwork

    @staticmethod
    @task_step()
    def network_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_ext_id = params.get("parent_ext_id")
        name = params.get("name")
        shared = params.get("shared")
        qos_policy_id = params.get("qos_policy_id")
        external = params.get("external")
        segments = params.get("segments")
        physical_network = params.get("physical_network")
        network_type = params.get("network_type")
        segmentation_id = params.get("segmentation_id")

        container = task.get_container(cid)
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
        task.progress(step_id, msg="Create network %s - Starting" % inst_id)

        # loop until entity is not stopped or get error
        while True:
            inst = container.conn.network.get(oid=inst_id)
            status = inst["status"]
            if status == "ACTIVE":
                break
            if status == "ERROR":
                task.progress(step_id, msg="Create network %s - Error" % inst_id)
                raise Exception("Can not create network %s" % name)

            task.progress(step_id, msg="Create network %s - Wait" % inst_id)
            sleep(2)

        task.progress(step_id, msg="Create network %s - Completed" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = None

        return oid, params

    @staticmethod
    @task_step()
    def network_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        name = params.get("name")
        shared = params.get("shared")
        qos_policy_id = params.get("qos_policy_id")
        external = params.get("external")
        segments = params.get("segments")

        container = task.get_container(cid)
        conn = container.conn

        if ext_id is not None:
            conn.network.update(ext_id, name, shared, qos_policy_id, external, segments)
            task.progress(step_id, msg="Update network %s - Starting" % ext_id)

            # loop until entity is not stopped or get error
            while True:
                inst = container.conn.network.get(oid=ext_id)
                status = inst["status"]
                if status == "ACTIVE":
                    break
                if status == "ERROR":
                    task.progress(step_id, msg="Update network %s - Error" % ext_id)
                    raise Exception("Can not update network %s" % name)

                task.progress(step_id, msg="Update network %s - Wait" % ext_id)
                sleep(2)

            task.progress(step_id, msg="Update network %s - Completed" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def network_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        # delete vsphere folder
        if resource.is_ext_id_valid() is True:
            try:
                # check network exists
                conn.network.get(resource.ext_id)

                # delete opennetwork network
                conn.network.delete(resource.ext_id)
                task.progress(step_id, msg="Delete network %s" % resource.ext_id)
            except:
                pass

        return oid, params


task_manager.tasks.register(NetworkTask())
