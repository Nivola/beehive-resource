# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.security_group import RuleGroup
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_security_group(self, options):
    """Create security_group resource - pre task
    
    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **sharedarea** (dict):

            * **cid** (int): container id

    **Return:**
    """
    self.set_operation()
    params = self.get_shared_data()
    
    # validate input params
    oid = params.get('id')
    compute_zone_id = params.get('compute_zone_id')
    self.update('PROGRESS', msg='Get configuration params')

    # get compute_zone
    self.get_session()
    compute_zone = self.get_resource(compute_zone_id)
    self.update('PROGRESS', msg='Get compute_zone %s' % compute_zone_id)

    compute_zone.add_link('%s-sg-link' % oid, 'sg', oid, attributes={})
    self.update('PROGRESS', msg='Link security group %s to zone %s' % (oid, compute_zone.oid))
    
    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_rule_group(self, options, availability_zone_id):
    """Create security group SecurityGroups.
    
    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **availability_zone_id**: availability_zone_id
        * **sharedarea** (dict):

            * **cid** (int): container id

    **Return:**
    """
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    # rules = params.get('rules')
    self.update('PROGRESS', msg='Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id)
    site_id = availability_zone.parent_id
    self.update('PROGRESS', msg='Get provider %s' % cid)

    # create flavor
    group_params = {
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Zone security group %s' % params.get('desc'),
        'parent': availability_zone_id,
        'orchestrator_tag': params.get('orchestrator_tag'),
        # 'rules': rules,
        'attribute': {
            'configs': {
            }
        }
    }
    res = provider.resource_factory(RuleGroup, **group_params)
    job_id = res[0]['jobid']
    group_id = res[0]['uuid']
    self.update('PROGRESS', msg='Create rule group in availability zone %s - start job %s' %
                                 (availability_zone_id, job_id))

    # link rule group to compute sg
    self.get_session(reopen=True)
    sg = self.get_resource(oid)
    sg.add_link('%s-rulegroup-link' % group_id, 'relation.%s' % site_id, group_id, attributes={})
    self.update('PROGRESS', msg='Link rule group %s to security group %s' % (group_id, oid))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update('PROGRESS', msg='Create rule group %s in availability zone %s' % (group_id, availability_zone_id))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_rulegroup_create_orchestrator_resource(self, options, orchestrator):
    """Create security_group physical resource.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **orchestrator**: orchestrator
        * **sharedarea** (dict):

            * **cid** (int): container id
            * **oid** (int): resource id

    **Return:**

    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')
    availability_zone_id = params.get('parent')
    self.update('PROGRESS', msg='Get configuration params')

    # get flavor resource
    self.get_session()
    resource = self.get_resource(oid)
    availability_zone = self.get_resource(availability_zone_id)
    self.update('PROGRESS', msg='Get rule group %s' % oid)

    sg_id = ProviderOrchestrator.get(orchestrator.get('type')).create_security_group(
        self, orchestrator['id'], resource, availability_zone)
    return sg_id