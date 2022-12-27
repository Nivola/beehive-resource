# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger

from six import ensure_text

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step
from beehive_resource.model import ResourceState
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.task_v2 import AbstractResourceTask, task_manager

logger = getLogger(__name__)


class NsxLogicalSwitchTask(AbstractResourceTask):
    """FNsxLogicalSwitchTask
    """
    name = 'nsx_logical_switch_task'
    entity_class = NsxLogicalSwitch

    @staticmethod
    @task_step()
    def nsx_logical_switch_create_step(task, step_id, params, *args, **kvargs):
        """Create nsx logical_switch
        
        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        name = params.get('name')
        desc = params.get('desc')
        # transport_zone = params.get('transport_zone')
        tenant = params.get('tenant')
        guest_allowed = params.get('guest_allowed', True)

        container = task.get_container(cid)
        conn = container.conn

        # get transport zone
        transport_zones = conn.network.nsx.lg.list_transport_zones()
        transport_zone = transport_zones['objectId']

        # create nsx logical_switch
        inst_id = conn.network.nsx.lg.create(transport_zone, name, desc, tenant, guest_allowed)
        inst_id = ensure_text(inst_id)

        # register resource for dvpg associated to logical switch
        lg = conn.network.nsx.lg.get(inst_id)
        backings = lg.get('vdsContextWithBacking', [])
        for backing in backings:
            dvpg_ext_id = ensure_text(backing.get('backingValue'))
            dvs_ext_id = ensure_text(backing.get('switch', {}).get('objectId'))
            dvpg_ext_obj = conn.network.get_network(dvpg_ext_id)
            dvs_resource = container.get_resource_by_extid(dvs_ext_id)
            folder = dvs_resource.get_parent()
            objid = '%s//%s' % (folder.objid, id_gen())
            model = container.add_resource(objid=objid, name=dvpg_ext_obj.name, resource_class=VsphereDvpg,
                                           ext_id=dvpg_ext_id, active=True, desc=dvpg_ext_obj.name,
                                           attrib={}, parent=folder.oid)
            container.update_resource_state(model.id, ResourceState.ACTIVE)

        params['ext_id'] = inst_id
        params['attrib'] = {}
        return inst_id, params
    
    @staticmethod
    @task_step()
    def nsx_logical_switch_delete_step(task, step_id, params, *args, **kvargs):
        """Delete nsx logical_switch
        
        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        ext_id = params.get('ext_id')

        container = task.get_container(cid)
        resource = container.get_resource(oid)

        # delete vsphere logical_switch
        if resource.is_ext_id_valid() is True:
            conn = container.conn

            # delete dvpg resource
            lg = conn.network.nsx.lg.get(ext_id)
            backings = lg.get('vdsContextWithBacking', [])
            for backing in backings:
                dvpg_ext_id = ensure_text(backing.get('backingValue'))
                dvpg = container.get_resource_by_extid(dvpg_ext_id)
                if dvpg is not None:
                    dvpg.expunge_internal()

            # delete logical switch
            conn.network.nsx.lg.delete(ext_id)
            task.progress(step_id, msg='Delete nsx logical switch: %s' % ext_id)        

        return oid, params
