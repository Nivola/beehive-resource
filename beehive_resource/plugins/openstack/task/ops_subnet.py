# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

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
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.openstack.controller import *
from beehive.common.data import operation
from beedrones.openstack.client import OpenstackNotFound
from beehive.common.task.handler import task_local
from beehive_resource.model import ResourceState

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def subnet_create_entity(self, options):
    """Create openstack network subnet

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
    parent_ext_id = params.get("project_ext_id")
    network_ext_id = params.get("network_ext_id")
    gateway_ip = params.get("gateway_ip")
    cidr = params.get("cidr")
    allocation_pools = params.get("allocation_pools")
    enable_dhcp = params.get("enable_dhcp")
    host_routes = params.get("host_routes")
    dns_nameservers = params.get("dns_nameservers")
    service_types = params.get("service_types")
    self.update("PROGRESS", msg="Get configuration params")

    # openstack network object reference
    self.get_session()
    container = self.get_container(cid)

    # create openstack network subnet
    conn = container.conn
    inst = conn.network.subnet.create(
        name,
        network_ext_id,
        parent_ext_id,
        gateway_ip,
        cidr,
        allocation_pools,
        enable_dhcp,
        host_routes,
        dns_nameservers,
        service_types,
    )
    inst_id = inst["id"]
    self.update("PROGRESS", msg="Create subnet %s" % inst_id)

    # wait a little so openstack create dhcp ports
    # gevent.sleep(3)

    # set resource id in shared data
    params["ext_id"] = inst_id
    params["result"] = inst_id
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def subnet_create_dhcp_ports(self, options):
    """Create openstack network dhcp ports

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
    network_ext_id = params.get("network_ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    network = container.get_resource_by_extid(network_ext_id)
    conn = container.conn

    # get router ports from openstack
    ports = conn.network.port.list(network=network_ext_id)
    self.logger.warn("Get dhcp ports: %s" % ports)

    res = []
    for port in ports:
        name = "dhcp_port_%s" % port["id"][0:10]
        desc = "Port dhcp %s" % name
        objid = "%s//%s" % (network.objid, id_gen())
        p = container.add_resource(
            objid=objid,
            name=name,
            resource_class=OpenstackPort,
            ext_id=port["id"],
            active=True,
            desc=desc,
            attrib={},
            parent=network.oid,
            tags=["openstack", "port"],
        )
        container.update_resource_state(p.id, ResourceState.ACTIVE)
        res.append(p.id)
        self.update("PROGRESS", msg="Create port resource %s" % p.id)

    return res


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def subnet_update_entity(self, options):
    """Delete openstack network subnet

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
    oid = params.get("id")
    # parent_ext_id = params.get('parent_ext_id')
    # network_ext_id = params.get('network_ext_id')
    name = params.get("name")
    gateway_ip = params.get("gateway_ip")
    # cidr = params.get('cidr')
    allocation_pools = params.get("allocation_pools")
    enable_dhcp = params.get("enable_dhcp")
    host_routes = params.get("host_routes")
    dns_nameservers = params.get("dns_nameservers")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # create openstack network
    container = self.get_container(cid)
    conn = container.conn
    inst = conn.network.subnet.update(
        oid,
        name,
        None,
        None,
        gateway_ip,
        None,
        allocation_pools,
        enable_dhcp,
        host_routes,
        dns_nameservers,
    )
    inst_id = inst["id"]
    self.update("PROGRESS", msg="Update subnet %s" % inst_id)

    # set resource id in shared data
    params["result"] = inst_id
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def subnet_delete_entity(self, options):
    """Delete openstack network subnet

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
    subnet_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # create openstack network
    self.get_session()
    container = self.get_container(cid)
    if subnet_id is not None:
        conn = container.conn
        inst = conn.network.subnet.delete(subnet_id)
        self.update("PROGRESS", msg="Delete subnet %s" % subnet_id)

    return subnet_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def subnet_delete_dhcp_ports(self, options):
    """Delete openstack network dhcp ports

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
    subnet_ext_id = params.get("ext_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    subnet = container.get_resource_by_extid(subnet_ext_id)
    network = container.get_resource(subnet.parent)
    conn = container.conn

    # get router ports from openstack
    ports = conn.network.port.list(network=network.ext_id)
    self.logger.warn("Get all ports and filter only dhcp: %s" % ports)

    res = []
    for port in ports:
        if port["device_owner"] == "network:dhcp":
            p = container.get_resource_by_extid(port["id"])

            # delete remote entity
            # if sg.ext_id is not None:
            #    conn.network.security_group.delete(sg.ext_id)
            #    self.update('PROGRESS', msg='Remove security group %s from '\
            #                'openstack' % sg.ext_id)

            # delete resource
            p.expunge_internal()
            self.update("PROGRESS", msg="Remove port %s" % p.id)

    return res


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSubnet, name="delete", delta=1)
def job_subnet_create(self, objid, params):
    """Create openstack network subnet

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

            * **network_ext_id**: network remote platform id
            * **project_ext_id**: project remote platform id
            * **gateway_ip**: ip of the gateway
            * **cidr**: network cidr
            * **allocation_pools**: list of start and end ip of a pool
            * **enable_dhcp**: [default=True] Set to true if DHCP is enabled and
                false if DHCP is disabled.
            * **dns_nameservers**: [default=['8.8.8.7', '8.8.8.8'] A list of DNS
                name servers for the subnet. Specify each name server as an IP
                address and separate multiple entries with a space.
            **service_types**: The service types associated with the subnet. Ex. ['compute:nova'], ['compute:foo']
            * **host_routes**:  A list of host route dictionaries for the subnet.

                .. code-block:: python

                    [
                        {
                          "destination":"0.0.0.0/0",
                          "nexthop":"123.45.67.89"
                        },
                        {
                          "destination":"192.168.0.0/24",
                          "nexthop":"192.168.0.1"
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
            # subnet_create_dhcp_ports,
            subnet_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSubnet, name="update", delta=1)
def job_subnet_update(self, objid, params):
    """Delete openstack network subnet

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **id** (int): resource id
            * **uuid** (uuid): resource uuid
            * **objid** (str): resource objid
            * **ext_id** (str): physical id

            * **network_ext_id**: network remote platform id
            * **parent_ext_id**: project remote platform id
            * **gateway_ip**: ip of the gateway
            * **cidr**: network cidr
            * **allocation_pools**: list of start and end ip of a pool
            * **enable_dhcp**: [default=True] Set to true if DHCP is enabled and
                false if DHCP is disabled.
            * **dns_nameservers**: [default=['8.8.8.7', '8.8.8.8'] A list of DNS
                name servers for the subnet. Specify each name server as an IP
                address and separate multiple entries with a space.
            * **host_routes**:  A list of host route dictionaries for the subnet.

                .. code-block:: python

                    [
                        {
                          "destination":"0.0.0.0/0",
                          "nexthop":"123.45.67.89"
                        },
                        {
                          "destination":"192.168.0.0/24",
                          "nexthop":"192.168.0.1"
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
            update_resource_post,
            subnet_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSubnet, name="delete", delta=1)
def job_subnet_delete(self, objid, params):
    """Delete openstack network subnet

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
            subnet_delete_entity,
            # subnet_delete_dhcp_ports,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True
