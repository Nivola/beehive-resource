# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import ujson as json
from celery.utils.log import get_task_logger

from beecell.simple import truncate, str2bool
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.instance import Instance
from beehive_resource.plugins.provider.entity.volume import ComputeVolume
from beehive_resource.plugins.provider.task import ProviderOrchestrator, ProviderVsphere, ProviderOpenstack
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, JobError

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_compute_instance(self, options):
    """Create compute_instance resource - pre task

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    
    # validate input params
    oid = params.get('id')
    networks = params.get('networks')
    flavor_id = params.get('flavor')
    sg_ids = params.get('security_groups')
    name = params.get('name')
    self.progress('Get configuration params')

    # get instance resource
    self.get_session()
    resource = self.get_resource(oid, run_customize=False)
    self.progress('Get resource %s' % oid)

    # link flavor to instance
    resource.add_link('%s-flavor-link' % oid, 'flavor', flavor_id, attributes={})
    self.progress('Link flavor %s to instance %s' % (flavor_id, oid))

    # - link networks to instance
    for network in networks:
        vpc_id = network['vpc']
        subnet = network['subnet']
        fixed_ip = network.get('fixed_ip', None)
        attribs = {
            'subnet': subnet.get('cidr')
        }
        if fixed_ip is not None:
            attribs = {
                'subnet': subnet.get('cidr'),
                'fixed_ip': fixed_ip
            }
        resource.add_link('%s-%s-vpc-link' % (oid, vpc_id), 'vpc', vpc_id, attributes=attribs)
        self.progress('Link vpc %s to instance %s' % (vpc_id, oid))
    
    # - link security groups to instance
    for sg_id in sg_ids:
        resource.add_link('%s-%s-security-group-link' % (oid, sg_id), 'security-group', sg_id, attributes={})
        self.progress('Link security group %s to instance %s' % (sg_id, oid))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_compute_volume(self, options, block_device):
    """Create compute instance volumes.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param block_device: Enables fine grained control of the block device mapping for an instance.
    :return: resource physical id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    parent = params.get('parent')
    boot_index = block_device.get('boot_index')
    source_type = block_device.get('source_type')
    availability_zone_id = params.get('main_availability_zone')
    image_id = None
    self.progress('Set configuration params')

    # get instance resource
    self.get_session(reopen=True)
    provider = self.get_container(cid)
    resource = self.get_resource(oid, run_customize=False)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    self.progress('Get resource %s' % oid)

    # create new volume
    if source_type in ['image', 'snapshot', None]:
        # create zone volume params
        volume_params = {
            'parent': parent,
            'name': '%s-volume-%s' % (params.get('name'), boot_index),
            'desc': 'Availability Zone volume %s' % params.get('desc'),
            'compute_zone': params.get('parent'),
            'orchestrator_tag': params.get('orchestrator_tag'),
            'availability_zone': site_id,
            'multi_avz': False,
            'type': params.get('type'),
            'flavor': block_device.get('flavor'),
            'metadata': block_device.get('metadata'),
            'size': block_device.get('volume_size'),
        }

        if source_type == 'image':
            volume_params['image'] = block_device.get('uuid')
        elif source_type == 'snapshot':
            volume_params['snapshot'] = block_device.get('uuid')

        res = provider.resource_factory(ComputeVolume, **volume_params)
        job_id = res[0]['jobid']
        volume_id = res[0]['uuid']
        self.progress('Create volume in availability zone %s - start job %s' % (availability_zone_id, job_id))

        # link volume to instance
        self.get_session(reopen=True)
        volume = self.get_resource(volume_id, run_customize=False)
        resource.add_link('%s-volume-%s-link' % (oid, volume.oid), 'volume.%s' % boot_index, volume.oid,
                          attributes={})
        self.progress('Link volume %s to instance %s' % (volume_id, oid))

        # link image to instance
        if source_type == 'image':
            image_id = block_device.get('uuid')
            resource.add_link('%s-image-link' % oid, 'image', image_id, attributes={})
            self.progress('Link image %s to instance %s' % (image_id, oid))

        # wait job complete
        self.wait_for_job_complete(job_id)
        self.progress('Create volume %s in availability zone %s' % (volume_id, availability_zone_id))

    # use existing volume
    elif source_type in ['volume']:
        volume_id = block_device.get('uuid')

        # link volume to instance
        self.get_session(reopen=True)
        volume = self.get_resource(volume_id, run_customize=False)
        resource.add_link('%s-volume-%s-link' % (oid, volume.oid), 'volume.%s' % boot_index, volume.oid,
                          attributes={})
        self.progress('Link volume %s to instance %s' % (volume_id, oid))

        # link image to instance
        images, tot = volume.get_linked_resources(link_type='image')
        image_id = images[0].uuid
        resource.add_link('%s-image-link' % oid, 'image', image_id, attributes={})
        self.progress('Link image %s to instance %s' % (image_id, oid))

    # params['image'] = image_id
    self.set_shared_data(params)
    self.progress('Update shared area')
    return volume_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_compute_volumes(self, options):
    """Import compute volumes from a physical server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :param sharedarea.id: resource id
    :return: True
    """
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    physical_server_id = params.get('physical_id', None)
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    # availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    compute_instance = self.get_resource_with_detail(oid)
    # site_id = availability_zone.parent_id
    self.progress('Get resources')

    # get linked volumes
    volumes = compute_instance.get_volumes()
    volume_uuids = []
    for volume in volumes:
        phvolume = volume.get_physical_volume()
        if phvolume is not None:
            volume_uuids.append(phvolume.uuid)
    self.progress('Get linked volumes to instance %s: %s' % (oid, truncate(volumes)))

    # get physical volumes
    if compute_instance.physical_server is None and physical_server_id is None:
        raise JobError('Physical resource for compute instance %s does not exist' % compute_instance.uuid)

    if compute_instance.physical_server is not None:
        physical_volumes = compute_instance.physical_server.get_volumes()
    else:
        physical_server = self.get_resource_with_detail(physical_server_id)
        physical_volumes = physical_server.get_volumes()
    self.progress('Get physical volumes %s: %s' % (oid, truncate(physical_volumes)))

    # run import volume job
    index = 1
    for physical_volume in physical_volumes:
        if physical_volume.get('uuid') not in volume_uuids:
            bootable = str2bool(physical_volume.get('bootable'))
            if bootable is True:
                boot_index = 0
            else:
                boot_index = index
                index += 1
            data = {
                'parent': compute_instance.parent_id,
                'name': '%s-volume-%s' % (params.get('name'), boot_index),
                'desc': 'Availability Zone volume %s' % params.get('desc'),
                'physical_id': physical_volume.get('uuid')
            }

            res = provider.resource_import_factory(ComputeVolume, **data)
            job_id = res[0]['jobid']
            volume_id = res[0]['uuid']
            self.progress('Import instance volume %s - start job %s' % (physical_volume.get('uuid'), job_id))

            # wait job complete
            self.wait_for_job_complete(job_id)
            self.progress('Import instance volume %s' % physical_volume.get('uuid'))

            # link volume to instance
            self.get_session(reopen=True)
            volume = self.get_resource(volume_id, run_customize=False)
            compute_instance.add_link('%s-volume-%s-link' % (oid, volume.oid), 'volume.%s' % boot_index, volume.oid,
                                      attributes={})
            self.progress('Link volume %s to instance %s' % (volume_id, oid))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_instance(self, options, availability_zone_id):
    """Create compute_instance instance.
    
    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :return: resource physical id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    compute_instance = self.get_resource(oid, run_customize=False)
    site_id = availability_zone.parent_id
    self.progress('Get resources')

    image_id = None
    flavor_id = None

    # get availability zone rule group
    security_groups = []
    for sg_id in params.get('security_groups'):
        # sg = self.get_resource(sg_id)
        rule_group = self.get_orm_linked_resources(sg_id, link_type='relation.%s' % site_id)[0]
        security_groups.append(rule_group.id)

    # verify instance is main or twin
    # - instance is main
    if availability_zone_id == params.get('main_availability_zone'):
        # set main to True because it is the main zone instance
        main = True

        # get availability zone image
        # compute_image = self.get_resource(params.get('image'))
        image_obj = self.get_orm_linked_resources(oid, link_type='image')[0]
        image = self.get_orm_linked_resources(image_obj.id, link_type='relation.%s' % site_id)[0]
        image_id = image.id

        # get availability zone flavor
        # compute_flavor = self.get_resource(params.get('flavor'))
        flavor = self.get_orm_linked_resources(params.get('flavor'), link_type='relation.%s' % site_id)[0]
        flavor_id = flavor.id

        # get availability zone network
        networks = []
        for network in params.get('networks'):
            # vpc = self.get_resource(network['vpc'])
            nets = self.get_orm_linked_resources(network['vpc'], link_type='relation.%s' % site_id)[0]
            networks.append({
                'vpc': network['vpc'],
                'id': nets.id,
                'subnet': network.get('subnet'),
                'other_subnets': network.get('other_subnets'),
                'fixed_ip': network.get('fixed_ip', {}),
            })

    # - instance is a twin. Get fixed ip from main instance
    else:
        # set main to False because this main zone instance is a twin
        main = False

        # get availability zone network
        networks = []
        for network in params.get('networks'):
            # get fixed_ip from compute instance and vpc link. fixed ip is set previously by main zone instance
            link = self.get_link_among_resources(start=oid, end=network['vpc'])
            attributes = json.loads(link.attributes)
            nets = self.get_orm_linked_resources(network['vpc'], link_type='relation.%s' % site_id)
            if len(nets) < 1:
                # vpc has no network in this site
                self.progress('Vps %s does not have network in availability zone %s' %
                              (network['vpc'], availability_zone_id))
                return None
            else:
                nets = nets[0]
            networks.append({
                'vpc': network['vpc'],
                'id': str(nets.id),
                'subnet': network.get('subnet'),
                'fixed_ip': attributes.get('fixed_ip', {}),
            })

    # create zone instance params
    instance_params = {
        'type': params.get('type'),
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Availability Zone instance %s' % params.get('desc'),
        'hostname': params.get('name'),
        'parent': availability_zone_id,
        'compute_instance': oid,
        'orchestrator_tag': params.get('orchestrator_tag'),
        'host_group': params.get('host_group'),
        # 'image': image_id,
        'image': image_id,
        'flavor': flavor_id,
        'security_groups': security_groups,
        'networks': networks,
        'admin_pass': params.get('admin_pass'),
        # 'block_device_mapping': params.get('block_device_mapping'),
        'user_data': params.get('user_data'),
        'metadata': params.get('metadata'),
        'personality': params.get('personality'),
        'main': main,
        'attribute': {
            'main': main,
            'type': params.get('type'),
            'configs': {}
        }
    }
    res = provider.resource_factory(Instance, **instance_params)
    job_id = res[0]['jobid']
    instance_id = res[0]['uuid']
    self.progress('Create instance in availability zone %s - start job %s' % (availability_zone_id, job_id))

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.progress('Create instance %s in availability zone %s' % (instance_id, availability_zone_id))

    return instance_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_zone_instance(self, options, availability_zone_id):
    """Import compute_instance instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :return: resource physical id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get('cid')
    oid = params.get('id')
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    # compute_instance = self.get_resource(oid, run_customize=False)
    site_id = availability_zone.parent_id
    self.progress('Get resources')

    # image_id = None
    # flavor_id = None

    # get availability zone rule group
    security_groups = []
    for sg_id in params.get('security_groups'):
        rule_group = self.get_orm_linked_resources(sg_id, link_type='relation.%s' % site_id)[0]
        security_groups.append(rule_group.id)

    # verify instance is main or twin
    # - instance is main
    if availability_zone_id == params.get('main_availability_zone'):
        # set main to True because it is the main zone instance
        main = True

        # # get availability zone image
        # # compute_image = self.get_resource(params.get('image'))
        # image_obj = self.get_orm_linked_resources(oid, link_type='image')[0]
        # image = self.get_orm_linked_resources(image_obj.id, link_type='relation.%s' % site_id)[0]
        # image_id = image.id
        #
        # # get availability zone flavor
        # # compute_flavor = self.get_resource(params.get('flavor'))
        # flavor = self.get_orm_linked_resources(params.get('flavor'), link_type='relation.%s' % site_id)[0]
        # flavor_id = flavor.id

        # get availability zone network
        networks = params.get('networks')
        # for network in params.get('networks'):
        #     nets = self.get_orm_linked_resources(network['vpc'], link_type='relation.%s' % site_id)[0]
        #     networks.append({
        #         'vpc': network['vpc'],
        #         'id': nets.id,
        #         'subnet': network.get('subnet'),
        #         'other_subnets': network.get('other_subnets'),
        #         'fixed_ip': network.get('fixed_ip', {}),
        #     })

    # - instance is a twin. Get fixed ip from main instance
    else:
        # set main to False because this main zone instance is a twin
        main = False

        # get availability zone network
        networks = []
        for network in params.get('networks'):
            # get fixed_ip from compute instance and vpc link. fixed ip is set previously by main zone instance
            link = self.get_link_among_resources(start=oid, end=network['vpc'])
            attributes = json.loads(link.attributes)
            nets = self.get_orm_linked_resources(network['vpc'], link_type='relation.%s' % site_id)
            if len(nets) < 1:
                # vpc has no network in this site
                self.progress('Vps %s does not have network in availability zone %s' %
                              (network['vpc'], availability_zone_id))
                return None
            else:
                nets = nets[0]
            networks.append({
                'vpc': network['vpc'],
                'id': str(nets.id),
                'subnet': network.get('subnet'),
                'fixed_ip': attributes.get('fixed_ip', {}),
            })

    # create zone instance params
    instance_params = {
        'type': params.get('type'),
        'name': '%s-avz%s' % (params.get('name'), site_id),
        'desc': 'Availability Zone instance %s' % params.get('desc'),
        # 'hostname': params.get('name'),
        'parent': availability_zone_id,
        'compute_instance': oid,
        'physical_server_id': params.get('physical_id'),
        'orchestrator_tag': params.get('orchestrator_tag'),
        # 'host_group': params.get('host_group'),
        # # 'image': image_id,
        # 'image': image_id,
        # 'flavor': flavor_id,
        'security_groups': security_groups,
        'networks': networks,
        # 'admin_pass': params.get('admin_pass'),
        # 'block_device_mapping': params.get('block_device_mapping'),
        # 'user_data': params.get('user_data'),
        # 'metadata': params.get('metadata'),
        # 'personality': params.get('personality'),
        'main': main,
        'attribute': {
            'main': main,
            'type': params.get('type'),
            'configs': {}
        }
    }
    res = provider.resource_import_factory(Instance, **instance_params)
    job_id = res[0]['jobid']
    instance_id = res[0]['uuid']
    self.progress('Import instance in availability zone %s - start job %s' % (availability_zone_id, job_id))

    # wait job complete
    self.wait_for_job_complete(job_id)
    self.progress('Import instance %s in availability zone %s' % (instance_id, availability_zone_id))

    return instance_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_manage_compute_instance(self, options):
    """Register compute_instance in ssh module

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :param sharedarea.oid: resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')

    # get resource
    self.get_session()
    compute_instance = self.get_resource(oid, run_customize=False)
    compute_instance.post_get()

    user = 'root'
    if compute_instance.is_windows() is True:
        user = 'administrator'

    uuid = compute_instance.manage(user=user, key=params.get('key_name'), password=params.get('admin_pass'))
    self.progress('Manage instance %s with ssh node %s' % (oid, uuid))

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_unmanage_compute_instance(self, options):
    """Deregister compute_instance from ssh module

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :param sharedarea.oid: resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')

    # get resource
    self.get_session()
    compute_instance = self.get_resource(oid, run_customize=False)

    uuid = None
    if compute_instance.is_managed() is True:
        uuid = compute_instance.unmanage()
        self.progress('Manage instance %s with ssh node %s' % (oid, uuid))

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_register_dns_compute_instance(self, options):
    """Register compute_instance in dns

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :param sharedarea.oid: resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')
    resolve = params.get('resolve')

    # get resource
    self.get_session()
    compute_instance = self.get_resource(oid, run_customize=False)

    uuid = None
    if resolve is True:
        try:
            uuid = compute_instance.set_dns_recorda(force=True, ttl=30)
            self.progress('Register instance %s in dns with record: %s' % (oid, uuid))
        except Exception as ex:
            self.progress('Error - Register instance %s in dns with record %s: %s' % (oid, uuid, ex))
            raise JobError('Register instance %s in dns: %s' % (oid, ex))
    else:
        self.progress('Do not register instance %s in dns' % oid)

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_deregister_dns_compute_instance(self, options):
    """Deregister compute_instance from dns

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :param sharedarea.oid: resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get('id')

    # get resource
    self.get_session()
    compute_instance = self.get_resource(oid, run_customize=False)

    uuid = None
    if compute_instance.get_dns_recorda() is not None:
        uuid = compute_instance.unset_dns_recorda()
        self.progress('Unregister instance %s record %s from dns' % (oid, uuid))

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_remove_compute_volume(self, options, volume_id):
    """Remove compute volume.

    :param options: Tupla with some options. (class_name, objid, job, job id, start time, time before new query, user)
    :param int volume_id: volume id
    :param sharedarea:
    :return: True
    """
    params = self.get_shared_data()
    cid = params.get('cid')
    oid = params.get('id')
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    resource = self.get_resource(oid, run_customize=False)
    self.progress('Get resource %s' % cid)

    links, total = resource.get_out_links(end_resource=volume_id)
    links[0].expunge()
    self.progress('Remove volume link %s' % volume_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_send_action_zone_instance(self, options, zone_instance_id):
    """Send action to zone instance.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param int zone_instance_id: availability zone instance id
    :param dict sharedarea: input params
    :return: resource uuid
    """
    params = self.get_shared_data()
    cid = params.get('cid')
    oid = params.get('id')
    action = params.get('action')
    configs = params.get('params')
    hypervisor = params.get('hypervisor')
    hypervisor_tag = params.get('hypervisor_tag')
    self.progress('Set configuration params')

    # get provider
    self.get_session()
    resource = self.get_resource(oid, run_customize=False)
    zone_instance = self.get_resource(zone_instance_id, run_customize=True)
    self.progress('Get resources')

    # send action
    res = zone_instance.action(action, configs, hypervisor, hypervisor_tag)
    job_id = res[0]['jobid']
    self.progress('Send action to availability zone instance %s - start job %s' % (zone_instance_id, job_id))

    # wait job complete
    self.wait_for_job_complete(job_id)
    self.progress('Send action to availability zone instance %s' % zone_instance_id)

    # run action post operation
    post_action = getattr(PostAction, action, None)
    if post_action is not None:
        post_action(self, resource, configs)

    return True


class PostAction(object):
    @staticmethod
    def set_flavor(task, resource, configs):
        links, total = resource.get_links(type='flavor')
        links[0].expunge()

        # link new flavor to instance
        flavor = configs.get('flavor')
        resource.add_link('%s-flavor-link' % resource.oid, 'flavor', flavor, attributes={})
        task.update('PROGRESS', msg='Link flavor %s to instance %s' % (flavor, resource.oid))

    @staticmethod
    def add_volume(task, resource, configs):
        links, total = resource.get_links(type='volume%')
        index = total + 1

        # link new volume to instance
        volume = configs.get('volume')
        resource.add_link('%s-%s-volume-link' % (resource.oid, volume), 'volume.%s' % index, volume, attributes={})
        task.update('PROGRESS', msg='Link volume %s to instance %s' % (volume, resource.oid))

    @staticmethod
    def del_volume(task, resource, configs):
        volume = configs.get('volume')
        links, total = resource.get_out_links(end_resource=volume)
        links[0].expunge()
        task.update('PROGRESS', msg='Unlink volume %s from instance %s' % (volume, resource.oid))


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_instance(self, options):
    """Link instance to compute instance

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    compute_instance_id = params.get('compute_instance')
    availability_zone_id = params.get('parent')
    oid = params.get('id')
    self.progress('Get configuration params')

    # link instance to compute instance
    self.get_session()
    compute_instance = self.get_resource(compute_instance_id, run_customize=False)
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    site_id = availability_zone.parent_id
    compute_instance.add_link('%s-instance-link' % oid, 'relation.%s' % site_id, oid, attributes={})
    self.progress('Link instance %s to compute instance %s' % (oid, compute_instance_id))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_main_server(self, options):
    """Create main server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    cid = params.get('cid')
    main = params.get('main')
    oid = params.get('id')
    # compute_instance_id = params.get('compute_instance')
    availability_zone_id = params.get('parent')
    # rule_groups = params.get('security_groups')
    orchestrators = params.get('orchestrators')
    # networks = params.get('networks')
    self.progress('Get configuration params')

    # get resources
    self.get_session()
    availability_zone = self.get_resource(availability_zone_id, run_customize=False)
    instance = self.get_resource(oid, run_customize=False)
    # provider = self.get_container(cid)
    self.progress('Get resource %s' % oid)

    server_id = None

    # create server
    if main is True:
        # get main orchestrator
        main_orchestrator_id = params.get('main_orchestrator')
        orchestrator = orchestrators.get(main_orchestrator_id)

        # get remote parent for server
        objdef = orchestrator_mapping(orchestrator['type'], 0)
        parent = availability_zone.get_physical_resource_from_container(orchestrator['id'], objdef)

        server_id = ProviderOrchestrator.get(orchestrator.get('type')).create_server(
            self, orchestrator, instance, parent, params)

        self.progress('Create main server: %s' % server_id)

    return server_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_import_main_server(self, options):
    """Import main server

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    main = params.get('main')
    oid = params.get('id')
    orchestrators = params.get('orchestrators')
    self.progress('Get configuration params')

    # get resources
    self.get_session()
    instance = self.get_resource(oid)
    self.progress('Get resource %s' % oid)

    server_id = None

    # create server
    if main is True:
        # get main orchestrator
        main_orchestrator_id = params.get('main_orchestrator')
        orchestrator = orchestrators.get(main_orchestrator_id)

        server_id = ProviderOrchestrator.get(orchestrator.get('type')).\
            import_server(self, orchestrator, instance, params)

        self.progress('Import main server: %s' % server_id)

    return server_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_configure_network(self, options):
    """Configure network

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: True
    """
    params = self.get_shared_data()

    compute_instance_id = params.get('compute_instance')
    networks = params.get('networks')

    # update compute-instance link networks attributes
    self.get_session()
    for network in networks:
        self.progress('Configure network: %s' % network)
        vpc_id = network['vpc']
        subnet = network['subnet']
        fixed_ip = network.get('fixed_ip', None)
        if fixed_ip is not None:
            attribs = {'subnet': subnet, 'fixed_ip': fixed_ip}
            link = self.get_orm_link_among_resources(start=compute_instance_id, end=vpc_id)
            self.update_orm_link(link.id, json.dumps(attribs))
            self.progress('Update link %s-%s-vpc-link' % (compute_instance_id, vpc_id))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_twins(self, options):
    """Create remote resources

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: resource id
    """
    params = self.get_shared_data()
    oid = params.get('id')
    main = params.get('main')
    orchestrators = params.get('orchestrators')
    networks = params.get('networks')
    rule_groups = params.get('security_groups')

    # create twins
    self.get_session()
    instance = self.get_resource(oid, run_customize=False)

    # remove main orchestrator
    if main is True:
        orchestrators.pop(params.get('main_orchestrator'))

    for orchestrator_id, orchestrator in orchestrators.items():
        for network in networks:
            self.logger.warn(network)
            network_id = network.get('id')
            subnet_cidr = network.get('subnet').get('cidr')
            fixed_ip = network.get('fixed_ip', None)

            if orchestrator['type'] == 'vsphere':
                ProviderVsphere.create_ipset(self, orchestrator_id, instance, fixed_ip, rule_groups)
            elif orchestrator['type'] == 'openstack':
                ProviderOpenstack.create_port(self, orchestrator_id, instance, network_id, subnet_cidr, fixed_ip,
                                              rule_groups)
            self.progress('Create twin')
    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_instance_action(self, options, orchestrator):
    """Send action to physical server.

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :return: True
    """
    # self.set_operation()
    params = self.get_shared_data()
    oid = params.get('id')
    action = params.get('action')
    configs = params.get('params')
    self.progress('Get configuration params')

    # run action over orchestrator entity
    self.get_session()
    resource = self.get_resource(oid, run_customize=False)
    self.progress('Get image %s' % oid)
    res = ProviderOrchestrator.get(orchestrator['type']).server_action(
        self, orchestrator['id'], resource, action, configs)

    return res
