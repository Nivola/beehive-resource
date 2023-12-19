# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
from beedrones.vsphere.client import VsphereError
from beehive.common.task_v2 import task_step, TaskError
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfw
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class NsxDfwTask(AbstractResourceTask):
    """NsxDfwTask"""

    name = "nsx_dfw_task"
    entity_class = NsxDfw

    @staticmethod
    @task_step()
    def nsx_dfw_section_create_entity_step(task, step_id, params, *args, **kvargs):
        """Add nsx dfw section

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :params params.cid: container id
        :params params.name: section name
        :params params.action: new action value. Ie: allow, deny, reject [default=allow]
        :params params.logged: if True rule is logged [default=false]
        :return: section id, params
        """
        cid = params.get("cid", None)
        name = params.get("name", None)
        action = params.get("action", "allow")
        logged = params.get("logged", "false")

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # create nsx dfw section
        conn.network.nsx.dfw.query_status()  # get etag
        res = conn.network.nsx.dfw.create_section(name, action, logged)
        task.progress(step_id, msg="Create nsx dfw section: %s" % res)

        return res["id"], params

    @staticmethod
    @task_step()
    def nsx_dfw_section_delete_entity_step(task, step_id, params, *args, **kvargs):
        """Delete nsx dfw section

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :params params.cid: container id
        :params params.sectionid: section id
        :return: True, params
        """
        cid = params.get("cid", None)
        section_id = params.get("sectionid", None)

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # delete nsx dfw section
        conn.network.nsx.dfw.query_status()  # get etag
        res = conn.network.nsx.dfw.delete_section(section_id)
        task.progress(step_id, msg="Delete nsx dfw section %s" % section_id)

        return True, params

    @staticmethod
    @task_step()
    def nsx_dfw_rule_create_entity_step(task, step_id, params, *args, **kvargs):
        """Add nsx dfw rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :params params.cid: container id
        :params params.sectionid: section id
        :params params.name: rule name
        :params params.action: new action value. Ie: allow, deny, reject [optional]
        :params params.logged: if 'true' rule is logged
        :params params.direction: rule direction: in, out, inout
        :params params.sources: List like [{'name':, 'value':, 'type':, }] [optional]
        :params params.destinations: List like [{'name':, 'value':, 'type':, }] [optional]
        :params params.services: List like examples [optional]
        :params params.appliedto: List like [{'name':, 'value':, 'type':, }] [optional]
        :return: rule id, params
        """
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

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # create nsx dfw rule
        conn.network.nsx.dfw.get_layer3_section(sectionid=sectionid)  # get etag
        # conn.network.nsx.dfw.query_status()  # get etag
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
            task.progress(step_id, msg="Create nsx dfw rule %s" % res)

            params["result"] = res["id"]
            task.set_shared_data(params)
            task.progress(step_id, msg="Update shared area")

            return res["id"], params
        except VsphereError as ex:
            if ex.code == 412:
                # check rule was created
                section = conn.network.nsx.dfw.get_layer3_section(sectionid=sectionid)
                rules = section.get("rule", [])
                for rule in rules:
                    if rule.get("name") == name:
                        conn.network.nsx.dfw.delete_rule(sectionid, rule.get("id"))

                logger.error("Rule %s can not be created" % name, exc_info=True)
                raise TaskError("Rule %s can not be created" % name)
            else:
                raise

    @staticmethod
    @task_step()
    def nsx_dfw_rule_move_entity_step(task, step_id, params, *args, **kvargs):
        """move nsx dfw rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :params params.cid: container id
        :params params.sectionid: section id
        :params params.ruleid: rule id
        :params params.ruleafter: rule id, put rule after this.
        :return: True, params
        """
        cid = params.get("cid", None)
        sectionid = params.get("sectionid", None)
        ruleid = params.get("ruleid", None)
        ruleafter = params.get("ruleafter", None)

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # move nsx dfw rule
        conn.network.nsx.dfw.query_status()  # get etag
        res = conn.network.nsx.dfw.move_rule(sectionid, ruleid, ruleafter=ruleafter)
        task.progress(step_id, msg="Move nsx dfw rule %s" % res)

        return True, params

    @staticmethod
    @task_step()
    def nsx_dfw_rule_update_entity_step(task, step_id, params, *args, **kvargs):
        """update nsx dfw rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :params params.cid: container id
        :params params.sectionid: section id
        :params params.ruleid: rule id
        :params params.name: new rule name [optionale]
        :params params.action: new action value. Ie: allow, deny, reject [optional]
        :params params.disable: True if rule is disbles [optional]
        :return: True, params
        """
        cid = params.get("cid", None)
        sectionid = params.get("sectionid", None)
        ruleid = params.get("ruleid", None)
        name = params.get("name", None)
        action = params.get("action", None)
        disable = params.get("disable", None)

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # update nsx dfw rule
        conn.network.nsx.dfw.query_status()  # get etag
        res = conn.network.nsx.dfw.update_rule(sectionid, ruleid, new_action=action, new_disable=disable, new_name=name)
        task.progress(step_id, msg="Update nsx dfw rule %s" % res)

        return True, params

    @staticmethod
    @task_step()
    def nsx_dfw_rule_delete_entity_step(task, step_id, params, *args, **kvargs):
        """delete nsx dfw rule

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :params params.cid: container id
        :params params.sectionid: section id
        :params params.ruleid: rule id
        :return: True, params
        """
        cid = params.get("cid", None)
        sectionid = params.get("sectionid", None)
        ruleid = params.get("ruleid", None)

        container = task.get_container(cid)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # check rule exists
        try:
            # delete nsx dfw rule
            conn.network.nsx.dfw.query_status()  # get etag
            res = conn.network.nsx.dfw.delete_rule(sectionid, ruleid)
            task.progress(step_id, msg="Delete nsx dfw rule %s" % ruleid)
        except:
            task.progress(step_id, msg="ERROR: nsx dfw rule %s does not exist" % ruleid)

        return True, params


class NsxDfwSectionAddTask(AbstractResourceTask):
    """NsxDfwSectionAddTask

    :params params: add params
    :params params.cid: container id
    :params params.name: section name
    :params params.action: new action value. Ie: allow, deny, reject [default=allow]
    :params params.logged: if True rule is logged [default=false]
    :return: True
    """

    name = "section_add_task"
    entity_class = NsxDfw

    def __init__(self, *args, **kwargs):
        super(NsxDfwSectionAddTask, self).__init__(*args, **kwargs)

        self.steps = [NsxDfwTask.nsx_dfw_section_create_entity_step]

    def failure(self, params, error):
        pass


class NsxDfwSectionDeleteTask(AbstractResourceTask):
    """NsxDfwSectionDeleteTask

    :params params: add params
    :params params.cid: container id
    :params params.sectionid: section id
    :return: True
    """

    name = "section_delete_task"
    entity_class = NsxDfw

    def __init__(self, *args, **kwargs):
        super(NsxDfwSectionDeleteTask, self).__init__(*args, **kwargs)

        self.steps = [NsxDfwTask.nsx_dfw_section_delete_entity_step]

    def failure(self, params, error):
        pass


class NsxDfwRuleAddTask(AbstractResourceTask):
    """NsxDfwRuleAddTask

    :params params: add params
    :params params.cid: container id
    :params params.sectionid: section id
    :params params.name: rule name
    :params params.action: new action value. Ie: allow, deny, reject [optional]
    :params params.logged: if 'true' rule is logged
    :params params.direction: rule direction: in, out, inout
    :params params.sources: List like [{'name':, 'value':, 'type':, }] [optional]
    :params params.destinations: List like [{'name':, 'value':, 'type':, }] [optional]
    :params params.services: List like examples [optional]
    :params params.appliedto: List like [{'name':, 'value':, 'type':, }] [optional]
    :return: True
    """

    name = "rule_add_task"
    entity_class = NsxDfw

    def __init__(self, *args, **kwargs):
        super(NsxDfwRuleAddTask, self).__init__(*args, **kwargs)

        self.steps = [NsxDfwTask.nsx_dfw_rule_create_entity_step]

    def failure(self, params, error):
        pass


class NsxDfwRuleMoveTask(AbstractResourceTask):
    """NsxDfwRuleMoveTask

    :params objid: objid of the resource. Ex. 110//2222//334//*
    :params params: input params
    :params params.cid: container id
    :params params.sectionid: section id
    :params params.ruleid: rule id
    :params params.ruleafter: rule id, put rule after this.
    :return: True
    """

    name = "rule_move_task"
    entity_class = NsxDfw

    def __init__(self, *args, **kwargs):
        super(NsxDfwRuleMoveTask, self).__init__(*args, **kwargs)

        self.steps = [NsxDfwTask.nsx_dfw_rule_create_entity_step]

    def failure(self, params, error):
        pass


class NsxDfwRuleUpdateTask(AbstractResourceTask):
    """NsxDfwRuleUpdateTask

    :params objid: objid of the resource. Ex. 110//2222//334//*
    :params params: input params
    :params params.cid: container id
    :params params.sectionid: section id
    :params params.ruleid: rule id
    :params params.name: new rule name [optionale]
    :params params.action: new action value. Ie: allow, deny, reject [optional]
    :params params.disable: True if rule is disbles [optional]
    :return: True
    """

    name = "rule_update_task"
    entity_class = NsxDfw

    def __init__(self, *args, **kwargs):
        super(NsxDfwRuleUpdateTask, self).__init__(*args, **kwargs)

        self.steps = [NsxDfwTask.nsx_dfw_rule_update_entity_step]

    def failure(self, params, error):
        pass


class NsxDfwRuleDeleteTask(AbstractResourceTask):
    """NsxDfwRuleDeleteTask

    :params objid: objid of the resource. Ex. 110//2222//334//*
    :params params: input params
    :params params.cid: container id
    :params params.sectionid: section id
    :params params.ruleid: rule id
    :return: True
    """

    name = "rule_delete_task"
    entity_class = NsxDfw

    def __init__(self, *args, **kwargs):
        super(NsxDfwRuleDeleteTask, self).__init__(*args, **kwargs)

        self.steps = [NsxDfwTask.nsx_dfw_rule_delete_entity_step]

    def failure(self, params, error):
        pass


task_manager.tasks.register(NsxDfwSectionAddTask())
task_manager.tasks.register(NsxDfwSectionDeleteTask())
task_manager.tasks.register(NsxDfwRuleAddTask())
task_manager.tasks.register(NsxDfwRuleMoveTask())
task_manager.tasks.register(NsxDfwRuleUpdateTask())
task_manager.tasks.register(NsxDfwRuleDeleteTask())
