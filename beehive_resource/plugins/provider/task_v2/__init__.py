# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step
from beehive_resource.container import Resource
from beehive_resource.task_v2 import AbstractResourceTask, task_manager


class AbstractProviderResourceTask(AbstractResourceTask):
    """AbstractProviderResource task
    """
    def __init__(self, *args, **kwargs):
        super(AbstractProviderResourceTask, self).__init__(*args, **kwargs)

    def get_orchestrator(self, orchestrator_type, task, step_id, orchestrator, resource):
        """Return orchestrator helper

        :param orchestrator_type: type of orchestrator like vsphere or openstack
        :param task: celery task reference
        :param step_id: task step id
        :param orchestrator: orchestrator config
        :param resource: resource reference
        :return: orchestrator helper
        """
        from beehive_resource.plugins.provider.task_v2.openstack import ProviderOpenstack
        from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere
        from beehive_resource.plugins.provider.task_v2.ontap import ProviderNetappOntap
        from beehive_resource.plugins.provider.task_v2.awx import ProviderAwx
        from beehive_resource.plugins.provider.task_v2.elk import ProviderElk
        from beehive_resource.plugins.provider.task_v2.grafana import ProviderGrafana
        helpers = {
            'vsphere': ProviderVsphere,
            'openstack': ProviderOpenstack,
            'ontap': ProviderNetappOntap,
            'awx': ProviderAwx,
            'elk': ProviderElk,
            'grafana': ProviderGrafana
        }
        helper = helpers.get(orchestrator_type, None)
        if helper is None:
            raise TaskError('Helper for orchestrator %s does not exist' % orchestrator_type)

        res = helper(task, step_id, orchestrator, resource)
        return res

    @staticmethod
    @task_step()
    def remove_physical_resource_step(task, step_id, params, orchestrator_id, orchestrator_type, *args, **kvargs):
        """Delete resource in remote orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        resource = params.get('id')

        # get all child resources
        childs = task.get_orm_linked_resources(resource, link_type='relation', container_id=orchestrator_id)
        logger.debug('+++++ remove_physical_resource_step - childs: {}'.format(childs))

        helper = task.get_orchestrator(orchestrator_type, task, step_id, {'id': orchestrator_id}, resource)
        logger.debug('+++++ remove_physical_resource_step - helper: {}'.format(type(helper)))
        resp = helper.remove_resource(childs)
        # task.progress(step_id, msg='Remove remote resource %s' % resource)

        return True, params

    @staticmethod
    @task_step()
    def run_scheduled_action_step(task, step_id, params, *args, **kvargs):
        """Run scheduled action

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get('id')
        action = params.get('action')
        action_params = params.get('action_params')
        resource = task.get_resource(oid)
        if action_params is None:
            action_params = {}
        prepared_task, code = resource.action(action, sync=True, **action_params)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='run sync scheduled action %s' % action)

        return True, params

    @staticmethod
    @task_step()
    def create_awx_job_template_step(task, step_id, params, template, orchestrator, *args, **kvargs):
        """Create awx job_template resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param template: awx job template params
        :param template.name: awx job template name
        :param template.desc: awx job template desc
        :param template.inventory: awx job template inventory id
        :param template.project: awx job template project id
        :param template.playbook: awx job template project playbook
        :param template.verbosity: awx job template verbosity
        :param template.ssh_cred_id: awx job template ssh credential id
        :param template.extra_vars: awx job template extra_vars
        :param orchestrator: availability zone orchestrator params
        :return: job_template_id, params
        """
        from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate

        awx_job_template = template

        # get container from orchestrator
        awx_container = task.get_container(orchestrator['id'])

        # set awx_job_template params
        awx_job_template_params = {
            'name': awx_job_template.get('name'),
            'desc': awx_job_template.get('desc'),
            'add': {
                'organization': orchestrator['config'].get('organization'),
                'inventory': awx_job_template.get('inventory'),
                'project': awx_job_template.get('project'),
                'playbook': awx_job_template.get('playbook'),
                'verbosity': awx_job_template.get('verbosity'),
            },
            'launch': {
                'ssh_cred_id': awx_job_template.get('ssh_cred_id'),
                'extra_vars': awx_job_template.get('extra_vars'),
            },
            'attribute': {},
            'sync': True
        }

        # create awx_job_template
        prepared_task, code = awx_container.resource_factory(AwxJobTemplate, **awx_job_template_params)
        job_template_id = prepared_task['uuid']
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create and run awx job template %s' % job_template_id)

        return job_template_id, params


class ProviderResourceAddTask(AbstractProviderResourceTask):
    """ResourceAdd task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param name: resource name
    :param desc: resource desc
    :param parent: resource parent
    :param ext_id: physical id
    :param active: active
    :param attribute: attribute
    :param tags: list of tags to add
    """
    abstract = False
    name = 'provider_resource_add_task'
    entity_class = Resource


# class ProviderResourceCloneTask(AbstractProviderResourceTask):
#     """ResourceClone task
#
#     :param cid: container id
#     :param id: resource id
#     :param uuid: return resource id, params
#     :param objid: resource objid
#     :param name: resource name
#     :param desc: resource desc
#     :param parent: resource parent
#     :param ext_id: physical id
#     :param active: active
#     :param attribute: attribute
#     :param tags: list of tags to add
#     """
#     abstract = False
#     name = 'provider_resource_clone_task'
#     entity_class = Resource


class ProviderResourceImportTask(AbstractProviderResourceTask):
    """ResourceImport task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param ext_id: physical id
    """
    abstract = False
    name = 'provider_resource_import_task'
    entity_class = Resource


class ProviderResourceUpdateTask(AbstractProviderResourceTask):
    """ResourceUpdate task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param ext_id: physical id
    """
    abstract = False
    name = 'provider_resource_update_task'
    entity_class = Resource


class ProviderResourcePatchTask(AbstractProviderResourceTask):
    """ResourcePatch task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    :param ext_id: physical id
    """
    abstract = False
    name = 'provider_resource_patch_task'
    entity_class = Resource


class ProviderResourceDeleteTask(AbstractProviderResourceTask):
    """ResourceDelete task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    """
    abstract = False
    name = 'provider_resource_delete_task'
    entity_class = Resource


class ProviderResourceExpungeTask(AbstractProviderResourceTask):
    """ResourceExpunge task

    :param cid: container id
    :param id: resource id
    :param uuid: return resource id, params
    :param objid: resource objid
    """
    abstract = False
    name = 'provider_resource_expunge_task'
    entity_class = Resource


class ProviderResourceActionTask(AbstractProviderResourceTask):
    """ResourceAction task
    """
    abstract = False
    name = 'provider_resource_action_task'
    entity_class = Resource


class ProviderResourceScheduledActionTask(AbstractProviderResourceTask):
    abstract = False
    name = 'provider_resource_scheduled_action_task'
    entity_class = Resource


task_manager.tasks.register(ProviderResourceAddTask())
# task_manager.tasks.register(ProviderResourceCloneTask())
task_manager.tasks.register(ProviderResourceImportTask())
task_manager.tasks.register(ProviderResourceUpdateTask())
task_manager.tasks.register(ProviderResourcePatchTask())
task_manager.tasks.register(ProviderResourceDeleteTask())
task_manager.tasks.register(ProviderResourceExpungeTask())
task_manager.tasks.register(ProviderResourceActionTask())
task_manager.tasks.register(ProviderResourceScheduledActionTask())


class AbstractProviderHelper(object):
    def __init__(self, task, step, orchestrator, resource, controller=None):
        """Create a provider helper

        :param task: celery task reference
        :param step: task step id
        :param orchestrator: orchestrator config
        :param resource: resource reference
        :param controller: resource controller [optional]
        """
        self.logger = getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)

        self.task = task
        self.step = step
        self.cid = orchestrator.get('id', None)
        self.orchestrator = orchestrator
        if task is not None:
            self.controller = task.controller
        else:
            self.controller = controller
        self.container = self.get_container(self.cid)
        self.resource = resource

        # if self.container is not None:
        #     self.controller = self.container.controller

    def get_session(self, reopen=False):
        """Open a new sqlalchemy session

        :param reopen: if True close first the previous session
        """
        if self.task is not None:
            self.task.get_session(reopen=reopen)
        else:
            self.controller.get_session()

    def progress(self, msg):
        if self.task is not None:
            self.task.progress(self.step, msg=msg)
        else:
            self.logger.debug(msg)

    def get_container(self, oid):
        if self.cid is not None:
            if self.task is not None:
                return self.task.get_container(oid)
            else:
                return self.controller.get_container(oid)
        else:
            return None

    def get_resource(self, oid):
        if self.task is not None:
            return self.task.get_resource(oid)
        else:
            return self.controller.get_resource(oid)

    def get_simple_resource(self, oid):
        if self.task is not None:
            return self.task.get_simple_resource(oid)
        else:
            return self.controller.get_simple_resource(oid)

    def create_resource(self, *args, **kvargs):
        kvargs['sync'] = True
        prepared_task, code = self.container.resource_factory(*args, **kvargs)
        self.progress('start creating resource %s %s' % (args[0], kvargs['name']))
        return prepared_task

    def run_sync_task(self, prepared_task, msg=''):
        res = run_sync_task(prepared_task, self.task, self.step)
        self.progress(msg)
        return res

    def add_link(self, prepared_task=None, resource_to_link=None, attrib=None):
        self.get_session(reopen=True)
        if attrib is None:
            attrib = {}
        if prepared_task is not None:
            resource_to_link = self.get_simple_resource(prepared_task['uuid'])
            oid = resource_to_link.oid
        else:
            oid = resource_to_link.oid
        self.resource.add_link('%s-%s-link' % (id_gen(), oid), 'relation', oid, attributes=attrib)
        self.progress('setup link to resource %s' % oid)
        return resource_to_link


from .flavor import *
from .image import *
from .instance import *
from .rule import *
from .security_group import *
from .share import *
from .site import *
from .stack_v2 import *
from .vpc import *
from .zone import *
from .volumeflavor import *
from .volume import *
