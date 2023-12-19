# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from celery.utils.log import get_task_logger
from beedrones.vsphere.client import VsphereError
from beehive.common.task.manager import task_manager
from beehive_resource.tasks import ResourceJobTask, ResourceJob
from beehive.common.task.job import job_task, task_local, job, Job, JobError
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfw

logger = get_task_logger(__name__)

#
# entity management
#

### section


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_dfw_section_create_entity(self, options):
    """Add nsx dfw section

    **Parameters:**

        * **options** (:py:class:`tupla`): tupla that must contain
            (class_name, objid, job, job id, start time, time before new query)
        * **params** (:py:class:`dict`): [shared data] task input params

            * **cid** (int): container id
            * **name**: section name
            * **action**: new action value. Ie: allow, deny, reject [default=allow]
            * **logged**: if True rule is logged [default=false]

    **Returns:**

        section id
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid", None)
    name = params.get("name", None)
    action = params.get("action", "allow")
    logged = params.get("logged", "false")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # create nsx dfw section
    res = conn.network.nsx.dfw.create_section(name, action, logged)
    self.update("PROGRESS", msg="Create nsx dfw section: %s" % res)

    params["result"] = res["id"]
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return res["id"]


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_dfw_section_delete_entity(self, options):
    """Delete nsx dfw section

    **Parameters:**

        * **options** (:py:class:`tupla`): tupla that must contain
            (class_name, objid, job, job id, start time, time before new query)
        * **params** (:py:class:`dict`): [shared data] task input params

            * **cid** (int): container id
            * **sectionid**: section id

    **Returns:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid", None)
    section_id = params.get("sectionid", None)
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # delete nsx dfw section
    res = conn.network.nsx.dfw.delete_section(section_id)
    self.update("PROGRESS", msg="Delete nsx dfw section %s" % section_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_dfw_rule_create_entity(self, options):
    """Add nsx dfw rule

    **Parameters:**

        * **options** (:py:class:`tupla`): tupla that must contain
            (class_name, objid, job, job id, start time, time before new query)
        * **params** (:py:class:`dict`): [shared data] task input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **name**: rule name
            * **action**: new action value. Ie: allow, deny, reject [optional]
            * **logged**: if 'true' rule is logged
            * **direction**: rule direction: in, out, inout
            * **sources**: List like [{'name':, 'value':, 'type':, }] [optional]
            * **destinations**: List like [{'name':, 'value':, 'type':, }] [optional]
            * **services**: List like examples [optional]
            * **appliedto**: List like [{'name':, 'value':, 'type':, }] [optional]

    **Returns:**

        rule id
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid", None)
    sectionid = params.get("sectionid", None)
    name = params.get("name", None)
    action = params.get("action", "allow")
    direction = params.get("direction", None)
    logged = params.get("logged", "true")
    sources = params.get("sources", None)
    destinations = params.get("destinations", None)
    services = params.get("services", None)
    appliedto = params.get("appliedto", None)
    precedence = params.get("precedence", "default")
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # create nsx dfw rule
    exist = False
    try:
        res = conn.network.nsx.dfw.create_rule(
            sectionid,
            name,
            action,
            direction=direction,
            logged=logged,
            sources=sources,
            destinations=destinations,
            services=services,
            appliedto=appliedto,
            precedence=precedence,
        )

        self.update("PROGRESS", msg="Create nsx dfw rule %s" % res)

        params["result"] = res["id"]
        self.set_shared_data(params)
        self.update("PROGRESS", msg="Update shared area")

        return res["id"]
    except VsphereError as ex:
        if ex.code == 412:
            # check rule was created
            section = conn.network.nsx.dfw.get_layer3_section(sectionid=sectionid)
            rules = section.get("rule", [])
            for rule in rules:
                if rule.get("name") == name:
                    conn.network.nsx.dfw.delete_rule(sectionid, rule.get("id"))

            raise JobError("Rule % can not be created" % name)
        else:
            raise


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_dfw_rule_move_entity(self, options):
    """move nsx dfw rule

    **Parameters:**

        * **options** (:py:class:`tupla`): tupla that must contain
            (class_name, objid, job, job id, start time, time before new query)
        * **params** (:py:class:`dict`): [shared data] task input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **ruleid**: rule id
            * **ruleafter**: rule id, put rule after this.

    **Returns:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid", None)
    sectionid = params.get("sectionid", None)
    ruleid = params.get("ruleid", None)
    ruleafter = params.get("ruleafter", None)
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # move nsx dfw rule
    res = conn.network.nsx.dfw.move_rule(sectionid, ruleid, ruleafter=ruleafter)
    self.update("PROGRESS", msg="Move nsx dfw rule %s" % res)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_dfw_rule_update_entity(self, options):
    """update nsx dfw rule

    **Parameters:**

        * **options** (:py:class:`tupla`): tupla that must contain
            (class_name, objid, job, job id, start time, time before new query)
        * **params** (:py:class:`dict`): [shared data] task input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **ruleid**: rule id
            * **name**: new rule name [optionale]
            * **action**: new action value. Ie: allow, deny, reject [optional]
            * **disable**: True if rule is disbles [optional]

    **Returns:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid", None)
    sectionid = params.get("sectionid", None)
    ruleid = params.get("ruleid", None)
    name = params.get("name", None)
    action = params.get("action", None)
    disable = params.get("disable", None)
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # update nsx dfw rule
    res = conn.network.nsx.dfw.update_rule(sectionid, ruleid, new_action=action, new_disable=disable, new_name=name)
    self.update("PROGRESS", msg="Update nsx dfw rule %s" % res)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def nsx_dfw_rule_delete_entity(self, options):
    """delete nsx dfw rule

    **Parameters:**

        * **options** (:py:class:`tupla`): tupla that must contain
            (class_name, objid, job, job id, start time, time before new query)
        * **params** (:py:class:`dict`): [shared data] task input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **ruleid**: rule id

    **Returns:**

        True
    """
    # get params from shared data
    params = self.get_shared_data()
    self.update("PROGRESS", msg="Get shared area")

    # validate input params
    cid = params.get("cid", None)
    sectionid = params.get("sectionid", None)
    ruleid = params.get("ruleid", None)
    self.update("PROGRESS", msg="Get configuration params")

    # create session
    self.get_session()

    # get container
    container = self.get_container(cid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # check rule exists
    try:
        # delete nsx dfw rule
        res = conn.network.nsx.dfw.delete_rule(sectionid, ruleid)
        self.update("PROGRESS", msg="Delete nsx dfw rule %s" % ruleid)
    except:
        self.update("PROGRESS", msg="ERROR: nsx dfw rule %s does not exist" % ruleid)

    return True


#
# JOB
#

### section


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxDfw, name="section.insert", delta=1)
def job_section_add_task(self, objid, params):
    """Create dfw section

    **Parameters:**

        * **params** (:py:class:`dict`): add params

            * **cid** (int): container id
            * **name**: section name
            * **action**: new action value. Ie: allow, deny, reject [default=allow]
            * **logged**: if True rule is logged [default=false]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_dfw_section_create_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxDfw, name="section.delete", delta=1)
def job_section_delete_task(self, objid, params):
    """Delete dfw section

    **Parameters:**

        * **params** (:py:class:`dict`): add params

            * **cid** (int): container id
            * **sectionid**: section id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_dfw_section_delete_entity, start_task], ops).delay()
    return True


### rule


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxDfw, name="rule.insert", delta=1)
def job_rule_add_task(self, objid, params):
    """Create dfw rule

    **Parameters:**

        * **params** (:py:class:`dict`): add params

            * **cid** (int): container id
            * **sectionid**: section id
            * **name**: rule name
            * **action**: new action value. Ie: allow, deny, reject [optional]
            * **logged**: if 'true' rule is logged
            * **direction**: rule direction: in, out, inout
            * **sources**: List like [{'name':, 'value':, 'type':, }] [optional]

                Ex: [{'name':'db-vm-01', 'value':'vm-84', 'type':'VirtualMachine'}]
                Ex: [{'name':None, 'value':'10.1.1.0/24', 'type':'Ipv4Address'}]
                Ex: [{'name':'WEB-LS', 'value':'virtualwire-9',
                      'type':'VirtualWire'}]
                Ex: [{'name':'APP-LS', 'value':'virtualwire-10',
                      'type':'VirtualWire'}]
                Ex: [{'name':'SG-WEB2', 'value':'securitygroup-22',
                      'type':'SecurityGroup'}]
                Ex: [{'name':'PAN-app-vm2-01 - Network adapter 1',
                      'value':'50031300-ad53-cc80-f9cb-a97254336c01.000',
                          'type':'vnic'}]

            * **destinations**: List like [{'name':, 'value':, 'type':, }] [optional]

                Ex: [{'name':'WEB-LS', 'value':'virtualwire-9',
                      'type':'VirtualWire'}]
                Ex: [{'name':'APP-LS', 'value':'virtualwire-10',
                      'type':'VirtualWire'}]
                Ex: [{'name':'SG-WEB-1', 'value':'securitygroup-21',
                      'type':'SecurityGroup'}]

            * **services**: List like examples [optional]

                Ex: [{'name':'ICMP Echo Reply', 'value':'application-337',
                      'type':'Application'}]
                Ex: [{'name':'ICMP Echo', 'value':'application-70',
                      'type':'Application'}]
                Ex: [{'name':'SSH', 'value':'application-223',
                      'type':'Application'}]
                Ex: [{'name':'DHCP-Client', 'value':'application-223',
                      'type':'Application'},
                     {'name':'DHCP-Server', 'value':'application-223',
                      'type':'Application'}]
                Ex: [{'name':'HTTP', 'value':'application-278',
                      'type':'Application'},
                     {'name':'HTTPS', 'value':'application-335',
                      'type':'Application'}]
                Ex. [{'port':'*', 'protocol':'*'}] -> *:*
                    [{'port':'*', 'protocol':6}] -> tcp:*
                    [{'port':80, 'protocol':6}] -> tcp:80
                    [{'port':80, 'protocol':17}] -> udp:80
                    [{'protocol':1, 'subprotocol':8}] -> icmp:echo request

                Get id from https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
                For icmp Summary of Message Types:
                   0  Echo Reply
                   3  Destination Unreachable
                   4  Source Quench
                   5  Redirect
                   8  Echo
                  11  Time Exceeded
                  12  Parameter Problem
                  13  Timestamp
                  14  Timestamp Reply
                  15  Information Request
                  16  Information Reply

            * **appliedto**: List like [{'name':, 'value':, 'type':, }] [optional]

                Ex: [{'name':'DISTRIBUTED_FIREWALL',
                      'value':'DISTRIBUTED_FIREWALL',
                      'type':'DISTRIBUTED_FIREWALL'}]
                Ex: [{'name':'ALL_PROFILE_BINDINGS',
                      'value':'ALL_PROFILE_BINDINGS',
                      'type':'ALL_PROFILE_BINDINGS'}]
                Ex: [{'name':'db-vm-01', 'value':'vm-84', 'type':'VirtualMachine'}]
                Ex: [{'name':'SG-WEB-1', 'value':'securitygroup-21',
                      'type':'SecurityGroup'},
                     {'name':'SG-WEB2', 'value':'securitygroup-22',
                      'type':'SecurityGroup'}]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_dfw_rule_create_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxDfw, name="rule.move.update", delta=1)
def job_rule_move_task(self, objid, params):
    """Move dfw rule

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **ruleid**: rule id
            * **ruleafter**: rule id, put rule after this.

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_dfw_rule_move_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxDfw, name="rule.update", delta=1)
def job_rule_update_task(self, objid, params):
    """Update dfw rule

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **ruleid**: rule id
            * **name**: new rule name [optionale]
            * **action**: new action value. Ie: allow, deny, reject [optional]
            * **disable**: True if rule is disbles [optional]

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_dfw_rule_update_entity, start_task], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=NsxDfw, name="rule.delete", delta=1)
def job_rule_delete_task(self, objid, params):
    """Delete dfw rule

    **Parameters:**

        * **objid** (str): objid of the resource. Ex. 110//2222//334//*
        * **params** (:py:class:`dict`): input params

            * **cid** (int): container id
            * **sectionid**: section id
            * **ruleid**: rule id

    **Returns:**

        True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([end_task, nsx_dfw_rule_delete_entity, start_task], ops).delay()
    return True
