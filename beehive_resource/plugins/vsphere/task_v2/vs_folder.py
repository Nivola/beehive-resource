# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beehive_resource.task_v2 import AbstractResourceTask, task_manager

logger = getLogger(__name__)


class FolderTask(AbstractResourceTask):
    """Folder task"""

    name = "folder_task"
    entity_class = VsphereFolder

    @staticmethod
    @task_step()
    def folder_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create vsphere folder

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        desc = params.get("desc")
        folder_extid = params.get("folder")
        datacenter_extid = params.get("datacenter")
        folder_type = params.get("folder_type")

        container = task.get_container(cid)
        conn = container.conn

        folder = None
        dc = None
        if folder_extid is not None:
            folder = conn.folder.get(folder_extid)

        elif datacenter_extid is not None:
            dc = conn.datacenter.get(datacenter_extid)

            # get folder type
        host = False
        network = False
        storage = False
        vm = False

        if folder_type == "host":
            host = True
        elif folder_type == "network":
            network = True
        elif folder_type == "storage":
            storage = True
        elif folder_type == "vm":
            vm = True
        else:
            raise Exception("Vsphere %s folder type is not supported" % folder_type)

        # create vsphere folder
        inst = conn.folder.create(
            name,
            folder=folder,
            datacenter=dc,
            host=host,
            network=network,
            storage=storage,
            vm=vm,
            desc=desc,
        )
        inst_id = inst._moId
        task.progress(step_id, msg="create physical folder: %s" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = {}

        return oid, params

    @staticmethod
    @task_step()
    def folder_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update vsphere folder

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        # update vsphere folder
        if resource.is_ext_id_valid() is True:
            folder = conn.folder.get(resource.ext_id)
            vsphere_task = conn.folder.update(folder, name)

            # loop until vsphere task has finished
            container.query_remote_task(task, step_id, vsphere_task)

            task.progress(step_id, msg="update physical folder: %s" % resource.ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def folder_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete vsphere folder

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        # delete vsphere folder
        if resource.is_ext_id_valid() is True:
            folder = conn.folder.get(resource.ext_id)
            if folder is None:
                task.progress(step_id, msg="Folder %s does not exist anymore" % resource.ext_id)
            else:
                vsphere_task = conn.folder.remove(folder)
                # loop until vsphere task has finished
                container.query_remote_task(task, step_id, vsphere_task)

            task.progress(step_id, msg="delete physical folder: %s" % resource.ext_id)

        # reset ext_id
        resource.update_internal(ext_id=None)

        return oid, params
