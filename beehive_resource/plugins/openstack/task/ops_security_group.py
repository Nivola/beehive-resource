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
from beehive.common.task.job import job_task, job, task_local, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.openstack.controller import *
from beehive.common.data import operation
from beedrones.openstack.client import OpenstackNotFound

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def security_group_create_entity(self, options):
    """Create openstack security group

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    name = params.get("name")
    desc = params.get("desc")
    parent = params.get("parent")
    self.progress("Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)
    conn = container.conn

    # get parent
    parent = container.get_resource(parent)

    # create openstack security group
    inst = conn.network.security_group.create(name, desc, parent.ext_id)
    inst_id = inst["id"]
    self.progress("Create security group %s" % inst_id)

    # save current data in shared area
    params["ext_id"] = inst_id
    self.set_shared_data(params)
    self.progress("Update shared area")

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def security_group_update_entity(self, options):
    """Update openstack security group

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    name = params.get("name")
    desc = params.get("desc")
    self.progress("Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid)

    # update openstack security group
    if ext_id is not None and ext_id != "":
        conn = container.conn
        conn.network.security_group.update(ext_id, name, desc)
        self.progress("Update security group %s" % ext_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def security_group_delete_entity(self, options):
    """Delete openstack security group

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    self.progress("Get configuration params")

    # create session
    self.get_session()
    container = self.get_container(cid)
    if ext_id is not None:
        try:
            container.conn.network.security_group.get(ext_id)
        except:
            self.progress("Security group %s does not already exist" % ext_id)
            return None

        # delete openstack security group
        container.conn.network.security_group.delete(ext_id)
        self.progress("Delete security group %s" % ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def security_group_rule_create_entity(self, options):
    """Create openstack security group rule

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    direction = params.get("direction")
    ethertype = params.get("ethertype")
    port_range_min = params.get("port_range_min")
    port_range_max = params.get("port_range_max")
    protocol = params.get("protocol")
    remote_group_ext_id = params.get("remote_group_extid")
    remote_ip_prefix = params.get("remote_ip_prefix")
    self.progress("Get configuration params")

    # openstack security group object reference
    self.get_session()
    container = self.get_container(cid)

    # create openstack security group rule
    conn = container.conn
    rule = conn.network.security_group.create_rule(
        ext_id,
        direction,
        ethertype=ethertype,
        port_range_min=port_range_min,
        port_range_max=port_range_max,
        protocol=protocol,
        remote_group_id=remote_group_ext_id,
        remote_ip_prefix=remote_ip_prefix,
    )
    self.progress("Create new security group %s rule %s" % (ext_id, rule["id"]))

    # set resource id in shared data
    params["result"] = rule["id"]
    self.set_shared_data(params)

    return rule["id"]


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def security_group_rule_delete_entity(self, options):
    """Delete openstack security group rule.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    rule_id = params.get("rule_id")
    self.progress("Get configuration params")

    # openstack security group object reference
    self.get_session()
    container = self.get_container(cid)

    # remove openstack security group rule
    conn = container.conn
    try:
        conn.network.security_group.delete_rule(rule_id)
    except OpenstackNotFound as ex:
        logger.warn(ex)
    except Exception:
        raise
    self.progress("Remove security group %s rule %s" % (ext_id, rule_id))

    # set resource id in shared data
    params["result"] = rule_id
    self.set_shared_data(params)

    return rule_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def security_group_rule_reset_entity(self, options):
    """Delete all rules of an openstack security.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

    **Return:**

    """
    # get params from shared data
    params = self.get_shared_data()
    self.progress("Get shared area")

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    self.progress("Get configuration params")

    # openstack security group object reference
    self.get_session()
    container = self.get_container(cid)

    # remove all openstack security group rule
    conn = container.conn
    grp = conn.network.security_group.get(ext_id)
    rules = []
    for rule in grp["security_group_rules"]:
        conn.network.security_group.delete_rule(rule["id"])
        rules.append(rule["id"])
    self.progress("Remove all security group %s rule %s" % (ext_id, rules))

    # set resource id in shared data
    params["result"] = rules
    self.set_shared_data(params)

    return rules


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSecurityGroup, name="insert", delta=1)
def job_security_group_create(self, objid, params):
    """Create openstack securitygroup

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

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            security_group_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSecurityGroup, name="update", delta=1)
def job_security_group_update(self, objid, params):
    """Update openstack securitygroup

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

    Job.create(
        [
            end_task,
            update_resource_post,
            security_group_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSecurityGroup, name="delete", delta=1)
def job_security_group_delete(self, objid, params):
    """Delete openstack securitygroup

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
            security_group_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSecurityGroup, name="rule.add.update", delta=1)
def job_security_group_rule_create(self, objid, params):
    """Create openstack security group rule

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid**: container id
            * **id**: security group id
            * **ext_id**: resource remote platform id
            * **direction**: ingress or egress
            * **ethertype**: Must be IPv4 or IPv6
            * **port_range_min**: The minimum port number in the range that is
                    matched by the security group rule. If the
                    protocol is TCP or UDP, this value must be
                    less than or equal to the port_range_max
                    attribute value. If the protocol is ICMP,
                    this value must be an ICMP type. [otpional]
            * **port_range_max**: The maximum port number in the range that is
                    matched by the security group rule. The
                    port_range_min attribute constrains the
                    port_range_max attribute. If the protocol is
                    ICMP, this value must be an ICMP type. [optional]
            * **protocol**: The protocol that is matched by the security group
                    rule. Valid values are null, tcp, udp, and icmp. [optional]
            * **remote_group_id**: The remote group UUID to associate with this
                    security group rule. You can specify either
                    the remote_group_id or remote_ip_prefix
                    attribute in the request body. [optional]
            * **remote_ip_prefix*+: The remote IP prefix to associate with
                    this security group rule. You can specify
                    either the remote_group_id or
                    remote_ip_prefix attribute in the request
                    body. This attribute matches the IP prefix
                    as the source IP address of the IP packet.
                    [otpional]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, security_group_rule_create_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSecurityGroup, name="rule.remove.update", delta=1)
def job_security_group_rule_delete(self, objid, params):
    """Delete openstack securitygroup

    **Parameters:**

        * **cid**: container id
        * **id**: security group id
        * **ext_id**: resource remote platform id
        * **rule_id**: rule id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, security_group_rule_delete_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackSecurityGroup, name="reset.update", delta=1)
def job_security_group_rule_reset(self, objid, params):
    """Delete all rules of an openstack securitygroup

    **Parameters:**

        * **cid**: container id
        * **id**: security group id
        * **ext_id**: resource remote platform id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, security_group_rule_reset_entity, start_task], ops).delay()
    return True
