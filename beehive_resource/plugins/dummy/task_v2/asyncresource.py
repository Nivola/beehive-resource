# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger
from gevent import sleep
from beehive.common.task_v2.manager import task_manager
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.dummy.controller import DummyAsyncResource
from beehive_resource.task_v2.core import AbstractResourceTask

logger = getLogger(__name__)


class AsyncResourceTask(AbstractResourceTask):
    """AsyncResource task
    """
    name = 'asyncresource_task'
    entity_class = DummyAsyncResource
    
    def __init__(self, *args, **kwargs):
        super(AsyncResourceTask, self).__init__(*args, **kwargs)

    @staticmethod
    @task_step()
    def asyncresource_wait_step(task, step_id, params, *args, **kvargs):
        """Wait some second

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        sleep(5)
        return True, params


class AsyncResourceAddTask(AsyncResourceTask):
    """AsyncResourceAdd task
    
    :param cid: container id
    :param id: resource id
    :param uuid: resource uuid
    :param objid: resource objid
    :param name: resource name
    :param desc: resource desc
    :param parent: resource parent
    :param ext_id: physical id
    :param active: active
    :param attribute: attribute
    :param tags: list of tags to add    
    """
    name = 'asyncresource_add_task'
    
    def __init__(self, *args, **kwargs):
        super(AsyncResourceAddTask, self).__init__(*args, **kwargs)

        self.steps = [
            AsyncResourceTask.create_resource_pre_step,
            AsyncResourceTask.asyncresource_wait_step,
            AsyncResourceTask.create_resource_post_step
        ]


class AsyncResourceUpdateTask(AsyncResourceTask):
    """AsyncResourceUpdate task

    :param cid: container id
    :param id: resource id
    :param uuid: resource uuid
    :param objid: resource objid
    :param ext_id: physical id    
    """
    name = 'asyncresource_update_task'

    def __init__(self, *args, **kwargs):
        super(AsyncResourceUpdateTask, self).__init__(*args, **kwargs)

        self.steps = [
            AsyncResourceTask.update_resource_pre_step,
            AsyncResourceTask.asyncresource_wait_step,
            AsyncResourceTask.update_resource_post_step
        ]


class AsyncResourceExpungeTask(AsyncResourceTask):
    """AsyncResourceExpunge task

    :param cid: container id
    :param id: resource id
    :param uuid: resource uuid
    :param objid: resource objid 
    """
    name = 'asyncresource_expunge_task'

    def __init__(self, *args, **kwargs):
        super(AsyncResourceExpungeTask, self).__init__(*args, **kwargs)

        self.steps = [
            AsyncResourceTask.expunge_resource_pre_step,
            AsyncResourceTask.asyncresource_wait_step,
            AsyncResourceTask.expunge_resource_post_step
        ]


task_manager.tasks.register(AsyncResourceAddTask())
task_manager.tasks.register(AsyncResourceUpdateTask())
task_manager.tasks.register(AsyncResourceExpungeTask())
