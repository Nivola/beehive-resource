# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from time import sleep

from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class ShareTask(AbstractResourceTask):
    """Share task"""

    name = "share_task"
    entity_class = OpenstackShare

    @staticmethod
    @task_step()
    def share_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        name = params.get("name")
        desc = params.get("desc")
        proto = params.get("share_proto")
        size = params.get("size")
        share_type = params.get("share_type")
        is_public = params.get("is_public")
        share_group_id = params.get("share_group_id")
        metadata = params.get("metadata")
        availability_zone = params.get("availability_zone")
        network_id = params.get("network")
        subnet_id = params.get("subnet")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila

        # if network and subnet are not None check share_network or create a new one
        share_network_id = None
        if network_id is not None and subnet_id is not None:
            share_networks = conn.network.list(neutron_net_id=network_id, neutron_subnet_id=subnet_id)
            if len(share_networks) > 0:
                share_network_id = share_networks[0]["id"]
            else:
                network = container.conn.network.get(network_id)
                share_network = conn.network.create(
                    name=network["name"],
                    availability_zone="nova",
                    neutron_net_id=network_id,
                    neutron_subnet_id=subnet_id,
                )
                share_network_id = share_network["id"]

        # create openstack share
        inst = conn.share.create(
            proto,
            size,
            name=name,
            description=desc,
            share_type=share_type,
            is_public=is_public,
            availability_zone=availability_zone,
            share_group_id=share_group_id,
            metadata=metadata,
            share_network_id=share_network_id,
        )
        inst_id = inst["id"]
        task.progress(step_id, msg="Create share %s - Starting" % inst_id)

        # set ext_id
        container.update_resource(oid, ext_id=inst_id)
        task.progress(step_id, msg="Set share remote openstack id %s" % inst_id)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackShare.get_remote_share(container.controller, inst_id, container, inst_id)
            status = inst["status"]
            if status == "available":
                break
            if status == "error":
                task.progress(step_id, msg="Create share %s - Error" % inst_id)
                raise Exception("Can not create share %s" % name)

            task.progress(step_id, msg="Create share %s - Wait" % inst_id)
            sleep(2)

        task.progress(step_id, msg="Create share %s - Completed" % inst_id)

        # save current data in shared area
        params["ext_id"] = inst_id
        params["attrib"] = None

        return oid, params

    @staticmethod
    @task_step()
    def share_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def share_expunge_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        ext_id = params.get("ext_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila
        resource = container.get_resource(oid)

        if resource.is_ext_id_valid() is True:
            # check share exists
            try:
                share = conn.share.get(ext_id)

                share_network_id = share.get("share_network_id")
                if share_network_id is not None:
                    # check share network is used only by this share. If this is so removes it
                    share_network = conn.network.get(share.get("share_network_id"))

                    all_shares = conn.share.list(share_network_id=share_network["id"])
                    all_share_ids = [s["id"] for s in all_shares]
                    all_share_ids.remove(share["id"])
                    task.progress(
                        step_id,
                        msg="Share network %s is also used by shares: %s" % (share_network["id"], all_share_ids),
                    )
            except:
                task.progress(step_id, msg="Share %s does not exist anymore" % ext_id)
                return None, params

            # remove share
            conn.share.delete(ext_id)
            task.progress(step_id, msg="Delete share %s - Starting" % ext_id)

            # loop until entity is not deleted or get error
            while True:
                inst = OpenstackShare.get_remote_share(container.controller, ext_id, container, ext_id)
                status = inst.get("status", "deleted")
                if status == "deleted":
                    break
                elif status == "error" or status == "error_deleting":
                    task.progress(step_id, msg="Delete share %s - Error" % ext_id)
                    raise Exception("Can not delete share %s" % ext_id)

                task.progress(step_id, msg="Delete share %s - Wait" % ext_id)
                sleep(2)

            resource.update_internal(ext_id=None)
            task.progress(step_id, msg="Delete share %s - Completed" % ext_id)

            # remove share network and share server
            if share_network_id is not None and len(all_share_ids) == 0:
                conn.network.delete(share_network_id)
                task.progress(step_id, msg="Delete share network %s" % share_network_id)

        return oid, params

    @staticmethod
    @task_step()
    def share_grant_add_step(task, step_id, params, *args, **kvargs):
        """Add grant to share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        ext_id = params.get("ext_id")
        access_level = params.get("access_level")
        access_type = params.get("access_type")
        access_to = params.get("access_to")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila
        resource = container.get_resource(oid)

        # delete vsphere folder
        if resource.is_ext_id_valid() is True:
            conn.share.action.grant_access(ext_id, access_level, access_type, access_to)
            task.progress(
                step_id,
                msg="Add grant to share %s: %s - %s - %s" % (ext_id, access_level, access_type, access_to),
            )

        return oid, params

    @staticmethod
    @task_step()
    def share_grant_remove_step(task, step_id, params, *args, **kvargs):
        """Remove grant from share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        ext_id = params.get("ext_id")
        access_id = params.get("access_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila
        resource = container.get_resource(oid)

        if resource.is_ext_id_valid() is True:
            conn.share.action.revoke_access(ext_id, access_id)
            task.progress(step_id, msg="Remove grant %s from share %s" % (ext_id, access_id))

        return oid, params

    @staticmethod
    @task_step()
    def share_size_extend_step(task, step_id, params, *args, **kvargs):
        """Extend share size

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        ext_id = params.get("ext_id")
        new_size = params.get("new_size")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila
        resource = container.get_resource(oid)

        if resource.is_ext_id_valid() is True:
            # remove share
            conn.share.action.extend(ext_id, new_size)
            task.progress(step_id, msg="Extend share %s size - Starting" % ext_id)

            # loop until entity is not deleted or get error
            while True:
                inst = OpenstackShare.get_remote_share(container.controller, ext_id, container, ext_id)
                status = inst["status"]
                if status == "available":
                    break
                elif status == "error" or status == "extending_error":
                    task.progress(step_id, msg="Extend share %s size - Error" % ext_id)
                    raise Exception("Can not Extend share %s size " % ext_id)

                task.progress(step_id, msg="Extend share %s size - Wait" % ext_id)
                sleep(2)

            task.progress(step_id, msg="Extend share %s size - Completed" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def share_size_shrink_step(task, step_id, params, *args, **kvargs):
        """Shrink share size

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        ext_id = params.get("ext_id")
        new_size = params.get("new_size")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila
        resource = container.get_resource(oid)

        if resource.is_ext_id_valid() is True:
            # remove share
            conn.share.action.shrink(ext_id, new_size)
            task.progress(step_id, msg="Shrink share %s size - Starting" % ext_id)

            # loop until entity is not deleted or get error
            while True:
                inst = OpenstackShare.get_remote_share(container.controller, ext_id, container, ext_id)
                status = inst["status"]
                if status == "available":
                    break
                elif status == "error" or status == "shrinking_error" or status == "shrinking_possible_data_loss_error":
                    task.progress(step_id, msg="Shrink share %s size - Error" % ext_id)
                    raise Exception("Can not Shrink share %s size " % ext_id)

                task.progress(step_id, msg="Shrink share %s size - Wait" % ext_id)
                sleep(2)

            task.progress(step_id, msg="Shrink share %s size - Completed" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def share_revert_to_snapshot_step(task, step_id, params, *args, **kvargs):
        """Revert share to snapshot

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent_id = params.get("parent")
        ext_id = params.get("ext_id")
        snapshot_id = params.get("snapshot_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn.manila
        resource = container.get_resource(oid)

        if resource.is_ext_id_valid() is True:
            conn.share.action.revert(ext_id, snapshot_id)
            task.progress(
                step_id,
                msg="Revert share %s to snapshot: %s" % (ext_id, snapshot_id),
            )

        return oid, params


task_manager.tasks.register(ShareTask())
