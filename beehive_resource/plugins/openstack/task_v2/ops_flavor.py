# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class FlavorTask(AbstractResourceTask):
    """Flavor task"""

    name = "flavor_task"
    entity_class = OpenstackFlavor

    @staticmethod
    @task_step()
    def flavor_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        desc = params.get("desc")
        vcpus = params.get("vcpus")
        ram = params.get("ram")
        disk = params.get("disk")
        task.progress(step_id, msg="Get configuration params")

        container = task.get_container(cid)
        conn = container.conn
        inst = conn.flavor.create(name, vcpus, ram, disk, desc)
        inst_id = inst["id"]
        task.progress(step_id, msg="Create flavor %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def flavor_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        extra_specs = params.get("extra_specs")

        container = task.get_container(cid)
        conn = container.conn
        inst = conn.flavor.extra_spec_create(ext_id, extra_specs)
        task.progress(step_id, msg="Update flavor %s" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def flavor_delete_physical_step(task, step_id, params, *args, **kvargs):
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
                # check flavor exists
                conn.flavor.get(resource.ext_id)

                # delete openstack flavor
                conn.flavor.delete(resource.ext_id)
                task.progress(step_id, msg="Delete flavor %s" % resource.ext_id)
            except:
                pass

        return oid, params


task_manager.tasks.register(FlavorTask())
