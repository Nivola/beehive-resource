# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from celery.utils.log import get_task_logger
from celery import chain, chord, group, signature
from beecell.simple import get_value, import_class
from beehive_resource.tasks import ResourceJobTask, ResourceJob,\
    create_resource_pre, create_resource_post, expunge_resource_pre,\
    expunge_resource_post, update_resource_post, update_resource_pre
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beedrones.openstack.client import OpenstackNotFound
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort

logger = get_task_logger(__name__)

#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def network_port_create_entity(self, options):
    """Create openstack network port.
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
    **Return:**
    
    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress('Get shared area')
    
    # validate input params
    cid = params.get('cid')
    name = params.get('name')
    network = params.get('network')
    fixed_ips = params.get('fixed_ips')
    host_id = params.get('host_id')
    profile = params.get('profile')
    vnic_type = params.get('vnic_type')
    device_owner = params.get('device_owner')
    device_id = params.get('device_id')
    sgs = params.get('security_groups')
    mac_address = params.get('mac_address')
    project_ext_id = params.get('project_ext_id')
    #project_id = params.get('project_id')
    self.progress('Get configuration params')
    
    # openstack network object reference
    self.get_session()  
    container = self.get_container(cid)
    
    # create openstack network port
    conn = container.conn
    inst = conn.network.port.create(name, network, fixed_ips, host_id, 
                                    profile, vnic_type, device_owner, 
                                    device_id, sgs, mac_address, project_ext_id)
    inst_id = inst['id']
    self.progress('Create port %s' % inst_id)
    
    # save current data in shared area
    params['ext_id'] = inst_id
    params['attrib'] = {}
    self.set_shared_data(params)
    self.progress('Update shared area')

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def network_port_update_entity(self, options):
    """Delete openstack network port. 
    TODO
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
    **Return:**
    
    """
    # get params from shared data
    params = self.get_shared_data()


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def network_port_delete_entity(self, options):
    """Delete openstack network port
    
    **Parameters:**    
    
        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time, 
             time before new query, user)
        * **sharedarea** (dict):
        
    **Return:**
    
    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress('Get shared area')
    
    # validate input params
    cid = params.get('cid')
    #id = params.get('id')
    ext_id = params.get('ext_id')
    self.progress('Get configuration params')
    
    # get conatiner
    self.get_session()
    container = self.get_container(cid)
    if ext_id is not None:
        try:
            container.conn.network.port.get(oid=ext_id)
        except:
            self.progress('Port %s does not already exist' % ext_id)
            return None
        
        # delete openstack port
        container.conn.network.port.delete(ext_id)
        self.progress('Delete port %s' % ext_id)

    return ext_id

#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackPort, name='insert', delta=2)
def job_network_port_create(self, objid, params):
    """Create openstack network port.
    
    
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
    
            * **tenant**: id or uuid of the tenant
            * **network**: id or uuid of the network
            * **fixed_ips**: specify the subnet. Ex.
            
                without ip:
                [{
                    "subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2",
                },..]
                
                with fixed ip:
                [{
                    "subnet_id": "a0304c3a-4f08-4c43-88af-d796509c97d2",
                    "ip_address": "10.0.0.2"
                },..]
                
            * **security_groups**: One or more security group UUIDs.
            * **device_id**: The UUID of the device that uses this port. For example, a virtual server.
            * **host_id**: The ID of the host where the port is allocated. In some cases, different implementations
                    can run on different hosts.
            * **profile**: A dictionary that enables the application running on the host to pass and receive virtual
                    network interface (VIF) port-specific information to the plug-in.
            * **vnic_type**: The virtual network interface card (vNIC) type that is bound to the neutron port. A
                    valid value is normal, direct, or macvtap.
            * **device_owner**: The UUID of the entity that uses this port. For example, a DHCP agent.
    """
    ops = self.get_options()
    self.set_shared_data(params)
    
    Job.create([
        end_task,
        create_resource_post,
        network_port_create_entity,
        create_resource_pre,
        start_task
    ], ops).delay()
    return True

@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackPort, name='update', delta=1)
def job_network_port_update(self, objid, params):
    """Delete openstack network port
    
    **Parameters:**
    
        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): physical id

    **Returns:**
    
        True
    """
    ops = self.get_options()
    self.set_shared_data(params)
    
    Job.create([
        end_task,
        update_resource_post,
        network_port_update_entity,
        update_resource_pre,
        start_task
    ], ops).delay()
    return True

@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackPort, name='delete', delta=1)
def job_network_port_delete(self, objid, params):
    """Delete openstack network port
    
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
    
    Job.create([
        end_task,
        expunge_resource_post,
        network_port_delete_entity,
        expunge_resource_pre,
        start_task
    ], ops).delay()
    return True
