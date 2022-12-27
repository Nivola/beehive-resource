# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class DvpgTask(AbstractResourceTask):
    """Dvpg task
    """
    name = 'dvpg_task'
    entity_class = VsphereDvpg

    @staticmethod
    @task_step()
    def dvpg_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create vsphere dvpg

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid', None)
        name = params.get('name', None)
        desc = params.get('desc', None)
        dvs_ext_id = params.get('dvs_ext_id', None)
        segmentation_id = params.get('segmentation_id', None)
        numports = params.get('numports', None)

        container = task.get_container(cid)
        conn = container.conn

        # get parent dvs
        dvs_ext = conn.network.get_distributed_virtual_switch(dvs_ext_id)
        task.progress(step_id, msg='Get parent dvs %s' % dvs_ext_id)

        # create vsphere network
        vsphere_task = conn.network.create_distributed_port_group(name, desc, segmentation_id, dvs_ext, numports)

        # loop until vsphere task has finished
        inst = container.query_remote_task(task, step_id, vsphere_task)
        inst_id = inst._moId
        params['ext_id'] = inst_id
        params['attrib'] = {}
        task.progress(step_id, msg='Create vsphere dvpg: %s' % inst_id)

        return inst_id, params

    @staticmethod
    @task_step()
    def dvpg_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update vsphere dvpg

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get('id')
        return oid, params

    @staticmethod
    @task_step()
    def dvpg_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete vsphere dvpg

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_resource(oid)

        # delete vsphere network        
        if resource.is_ext_id_valid() is True:
            network = conn.network.get_network(resource.ext_id)
            if network is not None:
                vsphere_task = conn.network.remove_network(network)                
                # loop until vsphere task has finished
                container.query_remote_task(task, step_id, vsphere_task)

            task.progress(step_id, msg='delete physical dvpg: %s' % resource.ext_id)

        # reset ext_id
        resource.update_internal(ext_id=None)

        return oid, params
