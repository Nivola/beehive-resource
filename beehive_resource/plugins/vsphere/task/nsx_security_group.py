# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beehive.common.task.manager import task_manager
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
from beehive.common.task.job import job_task, job, Job
from beehive.common.task.util import end_task, start_task
from beedrones.vsphere.client import VsphereError
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup

logger = get_task_logger(__name__)


#
# entity management
#
@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_security_group_create_entity(self, options):
    """Create nsx security_group

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
    parent_id = params.get("parent")
    name = params.get("name")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # create nsx security_group
    sgid = conn.network.nsx.sg.create(name)

    # loop until vsphere task has finished
    # inst = container.query_remote_task(self, task)
    inst_id = sgid

    # save current data in shared area
    # desc = 'Security Group %s' % name
    # params['desc'] = desc
    # params['parent'] = parent_id
    params["ext_id"] = inst_id
    params["attrib"] = {}
    self.set_shared_data(params)
    self.progress("Create security group: %s" % inst_id)

    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_security_group_delete_entity(self, options):
    """Delete nsx security_group

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

    # create session
    self.get_session()

    # get security_group resource
    container = self.get_container(cid)

    # delete vsphere security_group
    if ext_id is not None:
        conn = container.conn

        try:
            conn.network.nsx.sg.get(ext_id)
        except VsphereError:
            self.progress("Security group %s does not already exist" % ext_id)
            return None

        # search if security group is used in dfw rules
        rules = conn.network.nsx.dfw.filter_rules(security_groups=[ext_id])
        self.progress("Security group %s is used by rules: %s" % (ext_id, rules))
        for rule in rules:
            sectionid = rule.get("sectionId")
            ruleid = rule.get("id")

            # check rule exists
            try:
                rule = conn.network.nsx.dfw.get_rule(sectionid, ruleid)
            except VsphereError:
                rule = {}
            if rule == {}:
                self.progress("Rule %s:%s does not exist" % (sectionid, ruleid))
            else:
                # delete nsx dfw rule
                conn.network.nsx.dfw.delete_rule(sectionid, ruleid)
                self.progress("Delete nsx dfw rule %s:%s" % (sectionid, ruleid))

        conn.network.nsx.sg.delete(ext_id)
        # update task
        self.progress("Delete security group: %s" % ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_security_group_add_member_entity(self, options):
    """Add nsx security_group member

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
    member_ext_id = params.get("member")
    sg_ext_id = params.get("security_group")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # get member
    # sg = container.get_resources(sg_id)
    # member = container.get_resources(member_id)
    # ext_id = member.ext_id

    # create nsx security_group
    conn.network.nsx.sg.add_member(sg_ext_id, member_ext_id)

    return (sg_ext_id, member_ext_id)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_security_group_delete_member_entity(self, options):
    """Delete nsx security_group member

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
    member_ext_id = params.get("member")
    sg_ext_id = params.get("security_group")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn

    # get member
    # sg = container.get_resources(sg_id)
    # member = container.get_resources(member_id)

    # create nsx security_group
    conn.network.nsx.sg.delete_member(sg_ext_id, member_ext_id)

    return (sg_ext_id, member_ext_id)


#
# JOB
#
@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxSecurityGroup, name="insert", delta=1)
def job_security_group_create(self, objid, params):
    """Create nsx security_group

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
            * **ext_id** (str): physical id
            * **active** (bool): active
            * **attribute** (dict): attribute
            * **tags** (list): list of tags to add

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create(
        [
            end_task,
            create_resource_post,
            nsx_security_group_create_entity,
            create_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxSecurityGroup, name="update", delta=1)
def job_security_group_update(self, objid, params):
    """Update nsx security_group

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
            update_resource_post,
            # vsphere_server_update_entity,
            update_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxSecurityGroup, name="delete", delta=1)
def job_security_group_delete(self, objid, params):
    """Delete nsx security_group

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
            nsx_security_group_delete_entity,
            expunge_resource_pre,
            start_task,
        ],
        ops,
    ).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxSecurityGroup, name="member.update", delta=1)
def job_security_group_add_member(self, objid, params):
    """Nsx security group add member

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **security_group** (int): The security_group ext_id
            * **member** (id): The security_group member ext_id to add.

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_security_group_add_member_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxSecurityGroup, name="member.update", delta=1)
def job_security_group_delete_member(self, objid, params):
    """Nsx security group delete member

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **security_group** (int): The security_group ext_id
            * **member** (id): The security_group member ext_id to delete.

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_security_group_delete_member_entity, start_task], ops).delay()
    return True
