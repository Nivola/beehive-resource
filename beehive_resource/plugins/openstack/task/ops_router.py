# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

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
from beehive_resource.model import ResourceState

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_create_entity(self, options):
    """Create openstack router

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
    name = params.get("name")
    project_extid = params.get("project_extid")
    external_gateway_info = params.get("external_gateway_info")
    network_extid = external_gateway_info.get("network_id")
    external_ips = external_gateway_info.get("external_fixed_ips")
    routes = params.get("routes")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn

    # create openstack router
    inst = conn.network.router.create(name, project_extid, network_extid, external_ips, routes)
    inst_id = inst["id"]
    self.update("PROGRESS", msg="Create router %s - Starting" % inst_id)

    # loop until entity is not stopped or get error
    while True:
        inst = container.conn.network.router.get(oid=inst_id)
        status = inst["status"]
        if status == "ACTIVE":
            break
        if status == "ERROR":
            self.update("PROGRESS", msg="Create router %s - Error" % inst_id)
            raise Exception("Can not create router %s" % (name))

        # update task
        self.update("PROGRESS")

        # sleep a little
        gevent.sleep(task_local.delta)
    self.update("PROGRESS", msg="Create router %s - Completed" % inst_id)

    # save current data in shared area
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_create_ports_resource(self, options):
    """Create beehive resources related to router ports

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    parent = params.get("parent")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    tenant = container.get_resource(parent)
    conn = container.conn

    # get router ports from openstack
    res = []
    attrib = {"ha_tenant_network": []}
    ports = conn.network.port.list(device_id=ext_id)
    if len(ports) > 0:
        # get networks
        net_index = container.index_resources_by_extid(entity_class=OpenstackNetwork)

        # loop over router ports
        for port in ports:
            # HA network tenant is genereated for router and does not already exist in beehive. Register when port need
            if port["network_id"] not in net_index:
                # register new network
                objid = "%s//%s" % (tenant.objid, id_gen())
                remote_net = conn.network.get(oid=port["network_id"])
                desc = remote_net["name"]
                n = container.add_resource(
                    objid=objid,
                    name=remote_net["name"],
                    resource_class=OpenstackNetwork,
                    ext_id=port["network_id"],
                    active=True,
                    desc=desc,
                    attrib={},
                    parent=tenant.oid,
                    tags=["openstack", "network"],
                )
                container.update_resource_state(n.id, ResourceState.ACTIVE)

                # refresh network index
                net_index = container.index_resources_by_extid(entity_class=OpenstackNetwork)

                # append tenant network to router attribs
                attrib["ha_tenant_network"].append(n.id)

            name = port["name"]
            desc = "Port %s" % name
            parent = net_index[port["network_id"]]
            objid = "%s//%s" % (parent.objid, id_gen())
            p = container.add_resource(
                objid=objid,
                name=name,
                resource_class=OpenstackPort,
                ext_id=port["id"],
                active=True,
                desc=desc,
                attrib={},
                parent=parent.oid,
                tags=["openstack", "port"],
            )
            container.update_resource_state(p.id, ResourceState.ACTIVE)
            res.append(p.id)
            self.update("PROGRESS", msg="Create port resource %s" % p.id)

    params["attrib"] = attrib
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_update_entity(self, options):
    """Update openstack router

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


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_delete_ports(self, options):
    """Remove router ports and port resources.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn

    # remove openstack router interface
    if ext_id is not None:
        ports = conn.network.port.list(device_id=ext_id)
        for port in ports:
            # delete port for internal network
            if port["device_owner"] == "network:router_interface":
                subnet_id = port["fixed_ips"][0]["subnet_id"]
                conn.network.router.delete_internal_interface(ext_id, subnet_id)
                self.update("PROGRESS", msg="Delete router port %s" % port["id"])

            # delete port resource
            res = container.get_resource_by_extid(port["id"])
            if res is not None:
                res.expunge_internal()
                self.update("PROGRESS", msg="Delete router port %s resource" % port["id"])

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_delete_entity(self, options):
    """Delete openstack router

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    # oid = params.get('id')
    ext_id = params.get("ext_id")
    ha_tenant_network = params.get("ha_tenant_network")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    container = self.get_container(cid)
    if ext_id is not None:
        conn = container.conn

        # delete openstack router
        conn.network.router.delete(ext_id)
        self.update("PROGRESS", msg="Delete router %s" % ext_id)

        # delete HA tenant network related to router
        for item in ha_tenant_network:
            net = container.get_resource(item)
            # conn.network.delete(net.ext_id)
            net.expunge_internal()
            self.update("PROGRESS", msg="Delete ha tenant network %s" % item)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_port_create_entity(self, options):
    """Create openstack router interface

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
    subnet_id = params.get("subnet_id")
    oid = params.get("id")
    ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    container = self.get_container(cid)

    # create openstack router interface
    conn = container.conn
    interface = conn.network.router.add_internal_interface(ext_id, subnet_id)
    ext_id = interface["port_id"]
    port = conn.network.port.get(oid=ext_id)
    self.update("PROGRESS", msg="Add router interface on subnet %s" % subnet_id)

    # get parent network
    net_id = port["network_id"]
    parent = container.get_resource_by_extid(net_id)
    objid = "%s//%s" % (parent.objid, id_gen())
    name = "internal-port-%s" % port["id"][0:10]
    desc = "Router internal port %s" % port["id"][0:10]
    p = container.add_resource(
        objid=objid,
        name=name,
        resource_class=OpenstackPort,
        ext_id=ext_id,
        active=True,
        desc=desc,
        attrib={},
        parent=parent.oid,
        tags=["openstack", "port"],
    )
    container.update_resource_state(p.id, ResourceState.ACTIVE)
    self.update("PROGRESS", msg="Add router internal port %s" % p.id)

    params["oid"] = p.id
    params["result"] = p.id
    self.set_shared_data(params)

    return p.id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def router_port_delete_entity(self, options):
    """Delete openstack router interface

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
    subnet_id = params.get("subnet_id")
    ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn

    # find right port from router
    if ext_id is not None:
        ports = conn.network.port.list(device_id=ext_id)
        port_id = None
        for port in ports:
            fixed_ips = port["fixed_ips"]
            for ip in fixed_ips:
                if ip["subnet_id"] == subnet_id:
                    port_id = port["id"]

        # remove openstack router interface
        conn.network.router.delete_internal_interface(ext_id, subnet_id)
        self.update("PROGRESS", msg="Remove router interface from subnet %s" % subnet_id)

        # remove port resource
        resource = container.get_resource_by_extid(port_id)
        resource.expunge_internal()
        self.update("PROGRESS", msg="Remove port resource %s" % resource.oid)

    return resource.oid


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackRouter, name="insert", delta=1)
def job_router_create(self, objid, params):
    """Create openstack router.

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **name** (str): resource name
            * **desc** (str): resource desc
            * **parent** (int): resource parent
            * **tags** (list): list of tags to add
            * **routes** (dict): [optional] A list of dictionary pairs in this format:

                .. code-block:: python

                    [
                        {
                            'nexthop':'IPADDRESS',
                            'destination':'CIDR'
                        }
                    ]

            * **external_gateway_info** (dict):

                * **network_id**: router external network id
                * **external_fixed_ips**: [optional] router external_ips. Ex.

                    .. code-block:: python

                        [
                            {
                                'subnet_id': '255.255.255.0',
                                'ip': '192.168.10.1'
                            }
                        ]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            router_create_ports_resource,
            router_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackRouter, name="update", delta=1)
def job_router_update(self, objid, params):
    """Update openstack router.

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param cid: container id
    :param params: task input params
    :return: True
    :rtype: bool

    Params
        Params contains:

        * **cid**: container id
        * **id**: router id
        * **name**: router name
        * **desc**: router description
        * **ext_id**: resource remote platform id
        * **network_id**: router external network id
        * **external_fixed_ips**: [optional] router external_ips. Ex.

            .. code-block:: python

                [
                    {
                        'subnet_id': '255.255.255.0',
                        'ip': '192.168.10.1'
                    }
                ]

        * **routes: [optional] A list of dictionary pairs in this format:

            .. code-block:: python

                [
                    {
                        'nexthop':'IPADDRESS',
                        'destination':'CIDR'
                    }
                ]

        .. code-block:: python

            {
                'cid':..,
                'id':..,
                'ext_id':..,
                'name':..,
                'desc':..
                'routes':..,
                'external_gateway_info': {
                    'network_id':..
                    'external_fixed_ips':..
                }
            }
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            update_resource_post,
            # router_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackRouter, name="delete", delta=1)
def job_router_delete(self, objid, params):
    """Delete openstack router.

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
            router_delete_entity,
            router_delete_ports,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackRouter, name="port.add.update", delta=1)
def job_router_port_add(self, objid, params):
    """Add openstack router interface.

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id**: resource remote platform id
            * **subnet_id**: subnet id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            router_port_create_entity,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackRouter, name="port.remove.update", delta=1)
def job_router_port_delete(self, objid, params):
    """Remove openstack router interface.

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id**: resource remote platform id
            * **subnet_id**: subnet id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            router_port_delete_entity,
            start_task,
        ],
        ops,
    ).delay()
    return True
