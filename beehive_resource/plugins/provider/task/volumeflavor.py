# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.volumeflavor import VolumeFlavor
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_volumeflavor(self, options, availability_zone_id):
    """Create compute_flavor flavor.

    :param options: Tupla with useful options. (class_name, objid, job, job id, start time, time before new query, user)
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
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site = availability_zone.get_parent()
    site_id = site.oid
    self.update('PROGRESS', msg='Get resources')

    # create flavor
    flavor_params = {
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Zone volume flavor %s' % params.get('desc'),
        'parent': availability_zone_id,
        'orchestrator_tag': params.get('orchestrator_tag'),
        'attribute': {
            'configs': {
                'disk_iops': params.get('disk_iops'),
            }
        }
    }
    res = provider.resource_factory(VolumeFlavor, **flavor_params)
    job_id = res[0]['jobid']
    flavor_id = res[0]['uuid']
    self.update('PROGRESS', msg='Create volume flavor in availability zone %s - start job %s' %
                                 (availability_zone_id, job_id))

    # link flavor to compute flavor
    self.release_session()
    self.get_session()
    compute_flavor = self.get_resource(oid, run_customize=False)
    compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
    self.update('PROGRESS', msg='Link volume flavor %s to compute volume flavor %s' % (flavor_id, oid))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update('PROGRESS', msg='Create volume flavor in availability zone %s' % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_zone_volumeflavor(self, options, site_id, flavors):
    """Import compute flavor flavor.

    :param options: Tupla with useful options. (class_name, objid, job, job id, start time, time before new query, user)
    :param site_id: site id
    :param flavors: list of flavor config
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
        'desc': 'Zone volume flavor %s' % params.get('desc'),
        'parent': availability_zone_id,
        'orchestrator_tag': params.get('orchestrator_tag'),
        'volume_types': flavors,
        'attribute': {
            'configs': {
                'disk_iops': params.get('disk_iops'),
            }
        }
    }
    res = provider.resource_factory(VolumeFlavor, **flavor_params)
    job_id = res[0]['jobid']
    flavor_id = res[0]['uuid']
    self.update('PROGRESS', msg='Import volume flavor in availability zone %s - start job %s' %
                                 (availability_zone_id, job_id))

    # link flavor to compute flavor
    self.release_session()
    self.get_session()
    compute_flavor = self.get_resource(oid, run_customize=False)
    compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
    self.update('PROGRESS', msg='Link volume flavor %s to compute volume flavor %s' % (flavor_id, oid))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update('PROGRESS', msg='Import volume flavor in availability zone %s' % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_zone_volumeflavor(self, options, site_id, flavors):
    """Update compute_flavor flavor.

    :param options: Tupla with useful options. (class_name, objid, job, job id, start time, time before new query, user)
    :param site_id: site id
    :param flavors: list of flavor config
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

    # check zone flavor already exists
    zone_flavors = self.get_orm_linked_resources(oid, link_type='relation.%s' % site_id, container_id=cid)
    if len(zone_flavors) > 0:
        zone_flavor = provider.get_resource(zone_flavors[0].id, run_customize=False)
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
            'desc': 'Zone volume flavor %s' % params.get('desc'),
            'parent': availability_zone_id,
            'orchestrator_tag': params.get('orchestrator_tag'),
            'flavors': flavors,
            'attribute': {
                'configs': {
                    'disk_iops': params.get('disk_iops')
                }
            }
        }
        res = provider.resource_factory(VolumeFlavor, **flavor_params)
        job_id = res[0]['jobid']
        flavor_id = res[0]['uuid']
        self.update('PROGRESS', msg='Create volume flavor in availability zone %s - start job %s' %
                                     (availability_zone_id, job_id))

        # link flavor to compute flavor
        self.release_session()
        self.get_session()
        compute_flavor = self.get_resource(oid, run_customize=False)
        compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
        self.update('PROGRESS', msg='Link volume flavor %s to compute volume flavor %s' % (flavor_id, oid))

        # wait job complete
        res = self.wait_for_job_complete(job_id)
        self.update('PROGRESS', msg='Create volume flavor in availability zone %s' % availability_zone_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_volumetype_create_orchestrator_resource(self, options, orchestrator):
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
    resource = self.get_resource(oid, run_customize=False)
    self.update('PROGRESS', msg='Get volume_type %s' % oid)

    volumetype_id = ProviderOrchestrator.get(orchestrator.get('type')).create_volumetype(self, orchestrator['id'],
                                                                                          resource)
    self.update('PROGRESS', msg='Create volume_type %s' % orchestrator.get('type'))

    return volumetype_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_volumetype_import_orchestrator_resource(self, options, orchestrator):
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
    volumetype_conf = orchestrator.get('volume_type', None)
    self.update('PROGRESS', msg='Get configuration params')

    # get flavor resource
    self.get_session()
    resource = self.get_resource(oid, run_customize=False)
    self.update('PROGRESS', msg='Get volume_type %s' % oid)

    volumetype_id = None
    if volumetype_conf is not None:
        volumetype_id = ProviderOrchestrator.get(orchestrator.get('type')).import_volumetype(
            self, orchestrator['id'], resource, volumetype_conf['id'])
        self.update('PROGRESS', msg='Import volume type %s' % volumetype_conf['id'])

    return volumetype_id
