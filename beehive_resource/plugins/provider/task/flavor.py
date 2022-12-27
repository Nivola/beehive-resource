# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.flavor import Flavor
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_flavor(self, options, availability_zone_id):
    """Create compute_flavor flavor.

    :param options: Tupla with some useful options. (class_name, objid, job, job id, start time, time before new query, 
        user)
    :param availability_zone_id: availability zone id
    :param sharedarea:
    :param sharedarea.cid: container id
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()
    
    # input params
    cid = params.get('cid')
    oid = params.get('id')
    self.update('PROGRESS', msg='Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id)
    site = availability_zone.get_parent()
    site_id = site.oid
    self.update('PROGRESS', msg='Get resources')

    # create flavor
    flavor_params = {
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Zone flavor %s' % params.get('desc'),
        'parent': availability_zone_id,
        'orchestrator_tag': params.get('orchestrator_tag'),
        'attribute': {
            'configs': {
                'memory': params.get('memory'),
                'disk': params.get('disk'),
                'disk_iops': params.get('disk_iops'),
                'vcpus': params.get('vcpus'),
                'bandwidth': params.get('bandwidth')
            }
        }
    }
    res = provider.resource_factory(Flavor, **flavor_params)
    job_id = res[0]['jobid']
    flavor_id = res[0]['uuid']
    self.update('PROGRESS', msg='Create flavor in availability zone %s - start job %s' %
                                 (availability_zone_id, job_id))

    # link flavor to compute flavor
    self.release_session()
    self.get_session()
    compute_flavor = self.get_resource(oid)
    compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
    self.update('PROGRESS', msg='Link flavor %s to compute flavor %s' % (flavor_id, oid))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update('PROGRESS', msg='Create flavor in availability zone %s' % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_zone_flavor(self, options, site_id, flavors):
    """Import compute flavor flavor.

    :param options: Tupla with some useful options. (class_name, objid, job, job id, start time, time before new query,
        user)
    :param site_id: site id
    :param flavors: list of
    :param flavors.x.site_id:
    :param flavors.x.availability_zone_id:
    :param flavors.x.orchestrator_id: orchestrator id
    :param flavors.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
    :param flavors.x.flavor_id:
    :param sharedarea:
    :param sharedarea.cid: container id
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    availability_zone_id = flavors[0].get('availability_zone_id')
    self.update('PROGRESS', msg='Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    self.update('PROGRESS', msg='Get provider %s' % cid)

    # create flavor
    flavor_params = {
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Zone flavor %s' % params.get('desc'),
        'parent': availability_zone_id,
        'orchestrator_tag': params.get('orchestrator_tag'),
        'flavors': flavors,
        'attribute': {
            'configs': {
                'memory': params.get('memory'),
                'disk': params.get('disk'),
                'disk_iops': params.get('disk_iops'),
                'vcpus': params.get('vcpus'),
                'bandwidth': params.get('bandwidth')
            }
        }
    }
    res = provider.resource_factory(Flavor, **flavor_params)
    job_id = res[0]['jobid']
    flavor_id = res[0]['uuid']
    self.update('PROGRESS', msg='Import flavor in availability zone %s - start job %s' %
                                 (availability_zone_id, job_id))

    # link flavor to compute flavor
    self.release_session()
    self.get_session()
    compute_flavor = self.get_resource(oid)
    compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
    self.update('PROGRESS', msg='Link flavor %s to compute flavor %s' % (flavor_id, oid))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update('PROGRESS', msg='Import flavor in availability zone %s' % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_zone_flavor(self, options, site_id, flavors):
    """Update compute_flavor flavor.

    :param sharedarea.options: Tupla with some useful options.
        (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea.site_id: site id
    :param sharedarea.flavors: list of
    :param sharedarea.site_id:
    :param sharedarea.availability_zone_id:
    :param sharedarea.orchestrator_id: orchestrator id
    :param sharedarea.orchestrator_type** (str): Orchestrator type. Ex. vsphere, openstack
    :param sharedarea.flavor_id:    
    :param sharedarea.sharedarea** (dict):
    :param sharedarea.cid: container id
    :return:
    """
    self.set_operation()
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    availability_zone_id = flavors[0].get('availability_zone_id')
    self.update('PROGRESS', msg='Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    self.update('PROGRESS', msg='Get provider %s' % cid)

    # check zone flavor already exists
    zone_flavors = self.get_orm_linked_resources(oid, link_type='relation.%s' % site_id, container_id=cid)
    if len(zone_flavors) > 0:
        zone_flavor = provider.get_resource(zone_flavors[0].id)
        self.update('PROGRESS', msg='Site %s already linked to compute flavor %s' % (site_id, oid))

        # update flavor
        flavor_params = {
            'orchestrator_tag': params.get('orchestrator_tag'),
            'flavors': flavors
        }
        res = zone_flavor.update(**flavor_params)
        job_id = res[0]['jobid']
        self.update('PROGRESS', msg='Update flavor in availability zone %s - start job %s' %
                                     (availability_zone_id, job_id))
    else:
        # create flavor
        flavor_params = {
            'name': '%s-avz%s' % (params.get('name'), site_id),
            'desc': 'Zone flavor %s' % params.get('desc'),
            'parent': availability_zone_id,
            'orchestrator_tag': params.get('orchestrator_tag'),
            'flavors': flavors,
            'attribute': {
                'configs': {
                    'memory': params.get('memory'),
                    'disk': params.get('disk'),
                    'disk_iops': params.get('disk_iops'),
                    'vcpus': params.get('vcpus'),
                    'bandwidth': params.get('bandwidth')
                }
            }
        }
        res = provider.resource_factory(Flavor, **flavor_params)
        job_id = res[0]['jobid']
        flavor_id = res[0]['uuid']
        self.update('PROGRESS', msg='Create flavor in availability zone %s - start job %s' %
                                     (availability_zone_id, job_id))

        # link flavor to compute flavor
        self.release_session()
        self.get_session()
        compute_flavor = self.get_resource(oid)
        compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
        self.update('PROGRESS', msg='Link flavor %s to compute flavor %s' % (flavor_id, oid))

        # wait job complete
        res = self.wait_for_job_complete(job_id)
        self.update('PROGRESS', msg='Create flavor in availability zone %s' % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_flavor_create_orchestrator_resource(self, options, orchestrator):
    """Create provider flavor in remote orchestrator

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator config
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :return: uuid of the removed resource
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')
    self.update('PROGRESS', msg='Get configuration params')

    # get flavor resource
    self.get_session()
    resource = self.get_resource(oid)
    self.update('PROGRESS', msg='Get flavor %s' % oid)

    flavor_id = ProviderOrchestrator.get(orchestrator.get('type')).create_flavor(self, orchestrator['id'], resource)
    self.update('PROGRESS', msg='Create flavor %s' % orchestrator.get('type'))

    return flavor_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_flavor_import_orchestrator_resource(self, options, orchestrator):
    """Import provider flavor from remote orchestrator

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param orchestrator: orchestrator config
    :param dict sharedarea: input params
    :param sharedarea.cid: container id
    :param sharedarea.oid: resource id
    :return: uuid of the removed resource
    """
    self.set_operation()
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')
    flavor_conf = orchestrator.get('flavor', None)
    self.update('PROGRESS', msg='Get configuration params')

    # get flavor resource
    self.get_session()
    resource = self.get_resource(oid)
    self.update('PROGRESS', msg='Get flavor %s' % oid)

    flavor_id = None
    if flavor_conf is not None:
        flavor_id = ProviderOrchestrator.get(orchestrator.get('type')).import_flavor(
            self, orchestrator['id'], resource, flavor_conf['id'])
        self.update('PROGRESS', msg='Import flavor %s' % flavor_conf['id'])

    return flavor_id