# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class ImageTask(AbstractResourceTask):
    """Image task"""

    name = "image_task"
    entity_class = OpenstackImage

    @staticmethod
    @task_step()
    def image_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        data_path = params.get("data_path")
        task.progress(step_id, msg="Get configuration params")

        container = task.get_container(cid)
        conn = container.conn
        inst = conn.image.create(name)
        inst_id = inst["id"]
        task.progress(step_id, msg="Create image %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")

        # upload data
        f = open(data_path, "rb+")
        data = f.read()
        f.close()
        conn.image.upload(inst_id, data)
        inst_id = inst["id"]
        task.progress(step_id, msg="Upload image %s" % inst_id)

        return oid, params

    @staticmethod
    @task_step()
    def image_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def image_delete_physical_step(task, step_id, params, *args, **kvargs):
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
                # check image exists
                conn.image.get(resource.ext_id)

                # delete openstack image
                conn.image.delete(resource.ext_id)
                task.progress(step_id, msg="Delete image %s" % resource.ext_id)
            except:
                pass

        return oid, params


task_manager.tasks.register(ImageTask())
