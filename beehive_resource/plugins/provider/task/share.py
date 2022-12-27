# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.share import FileShare
from beehive_resource.plugins.provider.task import ProviderOrchestrator
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_compute_share_link(self, options):
    """Create compute_share resource - pre task
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    
    # validate input params
    oid = params.get('id')
    network = params.get('network')
    self.progress('Get configuration params')

    # get instance resource
    self.get_session()
    resource = self.get_resource(oid, details=False)
    self.progress('Get resource %s' % oid)

    # - link network to share
    vpc_id = network['vpc']
    attribs = {
        'vlan': network.get('vlan', None)
    }
    resource.add_link('%s-%s-vpc-link' % (oid, vpc_id), 'vpc', vpc_id, attributes=attribs)
    self.progress('Link vpc %s to share %s' % (vpc_id, oid))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_share(self, options, avz_id, main):
    """Create compute_share instance.
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int avz_id: availability zone id
    :param bool main: if True this is the main zone
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    cid = params.get('cid')
    oid = params.get('id')
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    self.progress('Get resources')

    # create zone instance params
    instance_params = {
        'type': params.get('type'),
        'name': 'zone-share-%s' % params.get('name'),
        'desc': 'Zone share %s' % params.get('desc'),
        'parent': avz_id,
        'compute_share': oid,
        'share_proto': params.get('share_proto'),
        'size': params.get('size', 0),
        # 'snapshot_id': params.get('snapshot_id'),
        # 'share_group_id':  params.get('share_group_id'), 
        'orchestrator_tag': params.get('orchestrator_tag'),
        'orchestrator_type': params.get('orchestrator_type'),
        'network': params.get('network'),
        'tags': params.get('tags'),
        'metadata': params.get('metadata'),
        'main': main,
        'attribute': {
            'main': main,
            'type': params.get('type')
        }
    }
    
    res = provider.resource_factory(FileShare, **instance_params)
    job_id = res[0]['jobid']
    share_id = res[0]['uuid']
    self.progress('Create share in availability zone %s - start job %s' % (avz_id, job_id))

    # wait job complete
    self.wait_for_job_complete(job_id)
    self.progress('Create share %s in availability zone %s' % (share_id, avz_id))

    return share_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_zone_share(self, options, availability_zone_id):
    """Create compute_share instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :return: resource physical id
    """
    params = self.get_shared_data()
    cid = params.get('cid')
    oid = params.get('id')
    resource_id = params.get('physical_id')
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    self.progress('Get resources')
    
    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    self.progress('Get resources')

    # create zone share params
    share_params = {
        'type': params.get('type'),
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Availability Zone volume %s' % params.get('desc'),
        'parent': availability_zone_id,
        'compute_share': oid,
        'share_proto': params.get('share_proto'),
        'size': params.get('size', 0),
        'network': params.get('network'),
        'main': True,
        'physical_id': resource_id,
        'attribute': {
            'main': True,
            'type': params.get('type'),
            'configs': {}
        }
    }
    res = provider.resource_import_factory(FileShare, **share_params)
    job_id = res[0]['jobid']
    share_id = res[0]['uuid']
    self.progress('Create share in availability zone %s - start job %s' % (availability_zone_id, job_id))

    # wait for job complete
    self.wait_for_job_complete(job_id)
    self.progress('Create share %s in availability zone %s' % (share_id, availability_zone_id))

    return share_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_update_zone_share(self, options, zone_share_id, main):
    """Update compute_share instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int zone_share_id: availability zone share id
    :param bool main: if True this is the main zone 
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    oid = params.get('id')
    size = params.get('size', None)
    grant = params.get('grant', None)
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    compute_share = self.get_resource(oid)
    zone_share = self.get_resource(zone_share_id)
    avz_id = zone_share.parent_id
    self.progress('Get resources')
    
    # update size
    if size is not None:
        old_size = params.get('attribute').get('size')
        res = zone_share.update_size(old_size, size)
        job_id = res[0]['jobid']
        self.progress('Update share size in availability zone %s - start job %s' % (oid, job_id))
    
        # wait job complete
        self.wait_for_job_complete(job_id)
        self.progress('Update share %s size in availability zone %s' % (oid, avz_id))

        # update attributes
        attribs = compute_share.get_attribs()
        attribs['size'] = size
        params['attribute'] = attribs
        self.set_shared_data(params)

    # set grant
    if grant is not None:
        res = zone_share.grant_set(grant)
        job_id = res[0]['jobid']
        self.progress('Update share grant in availability zone %s - start job %s' % (oid, job_id))

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.progress('Update share %s grant in availability zone %s' % (oid, avz_id))

    return zone_share_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_share(self, options):
    """Link share to compute share

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    compute_share_id = params.get('compute_share')
    availability_zone_id = params.get('parent')
    oid = params.get('id')
    self.progress('Get configuration params')

    # link share to compute share
    self.get_session()
    compute_share = self.get_resource(compute_share_id)
    availability_zone = self.get_resource(availability_zone_id)
    site_id = availability_zone.parent_id
    compute_share.add_link('%s-share-link' % oid, 'relation.%s' % site_id, oid, attributes={})
    self.progress('Link share %s to compute share %s' % (oid, compute_share_id))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_main_share(self, options):
    """Create share

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()

    main = params.get('main')
    oid = params.get('id')
    availability_zone_id = params.get('parent')
    compute_share_id = params.get('compute_share')
    self.progress('Get configuration params')

    # get resources
    self.get_session()
    availability_zone = self.get_resource(availability_zone_id)
    compute_share = self.get_resource(compute_share_id)
    share = self.get_resource(oid)
    self.progress('Get resource %s' % oid)

    # create share
    share_id = None
    if main is True:
        # get main orchestrator
        main_orchestrator_id = params.get('main_orchestrator')
        orchestrator = params.get('orchestrators').get(main_orchestrator_id)

        # get remote parent for server
        objdef = orchestrator_mapping(orchestrator['type'], 0)
        parent = availability_zone.get_physical_resource_from_container(orchestrator['id'], objdef)

        share_id = ProviderOrchestrator.get(orchestrator.get('type')).create_share(
            self, orchestrator, share, parent, params, compute_share)

        self.progress('Create share: %s' % share_id)

    return share_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_main_share(self, options):
    """Import main share

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    oid = params.get('id')
    orchestrator_type = params.get('type')
    resource_id = params.get('physical_id')
    self.progress('Get configuration params')

    # get resources
    self.get_session()
    share = self.get_resource(oid, run_customize=False)
    remote_share = self.get_resource(resource_id, run_customize=False)
    self.progress('Get resource %s' % oid)

    volume_id = ProviderOrchestrator.get(orchestrator_type).import_share(self, share, remote_share.oid)
    self.progress('Import main share: %s' % volume_id)

    return volume_id
