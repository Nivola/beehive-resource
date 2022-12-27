# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from copy import deepcopy
from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.volume import Volume, ComputeVolume
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class PostAction(object):
    @staticmethod
    def set_flavor(task, resource, configs):
        links, total = resource.get_links(type='flavor')
        links[0].expunge()

        # link new flavor to instance
        flavor = configs.get('flavor')
        resource.add_link('%s-flavor-link' % resource.oid, 'flavor', flavor, attributes={})


class VolumeTask(AbstractProviderResourceTask):
    """Volume task
    """
    name = 'volume_task'
    entity_class = ComputeVolume

    @staticmethod
    @task_step()
    def link_compute_volume_step(task, step_id, params, *args, **kvargs):
        """Create compute_volume resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get('id')
        image_id = params.get('image')
        volume_id = params.get('volume')
        flavor_id = params.get('flavor')

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get resource %s' % oid)
    
        # link image to volume
        if image_id is not None:
            resource.add_link('%s-%s-image-link' % (oid, image_id), 'image', image_id, attributes={})
            task.progress(step_id, msg='Link image %s to volume %s' % (image_id, oid))

        elif volume_id is not None:
            orig_volume = task.get_simple_resource(volume_id)
            images, tot = orig_volume.get_linked_resources(link_type='image')
            # volume is root volume
            if len(images) > 0:
                image_id = images[0].oid
                resource.add_link('%s-%s-image-link' % (oid, image_id), 'image', image_id, attributes={})
                task.progress(step_id, msg='Link image %s to volume %s' % (image_id, oid))

        # link flavor to volume
        resource.add_link('%s-%s-flavor-link' % (oid, flavor_id), 'flavor', flavor_id, attributes={})
        task.progress(step_id, msg='Link flavor %s to volume %s' % (flavor_id, oid))
    
        return oid, params
    
    @staticmethod
    @task_step()
    def create_zone_volume_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create zone volume.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: volume_id, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        flavor_id = params.get('flavor')
        image_id = params.get('image')
        volume_id = params.get('volume')
        snapshot_id = params.get('snapshot')

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        # compute_volume = task.get_simple_resource(oid)
        site_id = availability_zone.parent_id
        task.progress(step_id, msg='Get resources')
        
        # verify volume is main or twin
        # - volume is main
        if availability_zone_id == params.get('main_availability_zone'):
            # set main to True because it is the main zone volume
            main = True
            
            # get availability zone image
            if image_id is not None:
                image = task.get_orm_linked_resources(image_id, link_type='relation.%s' % site_id)[0]
                image_id = image.id
                # volume_site_id = site_id
    
            # get availability zone volume
            if volume_id is not None:
                # volume = task.get_orm_linked_resources(volume_id, link_type='relation.%s' % site_id)[0]
                compute_volume = task.get_simple_resource(volume_id)
                volumes, tot = compute_volume.get_linked_resources(link_type_filter='relation.%', run_customize=False,
                                                                   with_permtags=False)
                volume = volumes[0]
                volume_id = volume.oid
                # volume_site_id = volume.get_site().oid
    
            # get availability zone flavor
            flavor = task.get_orm_linked_resources(flavor_id, link_type='relation.%s' % site_id)[0]
            flavor_id = flavor.id
    
        # - volume is a twin. Get fixed ip from main volume
        else:
            # set main to False because this main zone volume is a twin
            main = False
    
        if main is True:
            # create zone volume params
            volume_params = {
                'type': params.get('type'),
                'name': '%s-avz%s' % (params.get('name'), site_id),
                'desc': 'Availability Zone volume %s' % params.get('desc'),
                'parent': availability_zone_id,
                'compute_volume': oid,
                'orchestrator_tag': params.get('orchestrator_tag'),
                'orchestrator_id': params.get('orchestrator_id'),
                'flavor': flavor_id,
                'volume': volume_id,
                'snapshot': snapshot_id,
                'image': image_id,
                'size': params.get('size'),
                'metadata': params.get('metadata'),
                'main': main,
                'attribute': {
                    'main': main,
                    'type': params.get('type'),
                    'metadata': params.get('metadata'),
                    'configs': {}
                }
            }
            prepared_task, code = provider.resource_factory(Volume, **volume_params)
            volume_id = prepared_task['uuid']
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg='Create volume %s in availability zone %s' % (volume_id, availability_zone_id))
    
        return volume_id, params
    
    @staticmethod
    @task_step()
    def import_zone_volume_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """CImport zone volume.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: volume_id, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        flavor_id = params.get('flavor')
        resource_id = params.get('physical_id')

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        task.progress(step_id, msg='Get resources')
    
        # get availability zone flavor
        flavor = task.get_orm_linked_resources(flavor_id, link_type='relation.%s' % site_id)[0]
        flavor_id = flavor.id
    
        # create zone volume params
        volume_params = {
            'type': params.get('type'),
            'name': '%s-avz%s' % (params.get('name'), site_id),
            'desc': 'Availability Zone volume %s' % params.get('desc'),
            'parent': availability_zone_id,
            'compute_volume': oid,
            'flavor': flavor_id,
            'size': params.get('size'),
            'metadata': params.get('metadata'),
            'main': True,
            'physical_id': resource_id,
            'attribute': {
                'main': True,
                'type': params.get('type'),
                'configs': {}
            }
        }
        prepared_task, code = provider.resource_import_factory(Volume, **volume_params)
        volume_id = prepared_task['uuid']
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create volume %s in availability zone %s' % (volume_id, availability_zone_id))
    
        return volume_id, params
    
    @staticmethod
    @task_step()
    def link_volume_step(task, step_id, params, *args, **kvargs):
        """Link zone volume to compute volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        compute_volume_id = params.get('compute_volume')
        availability_zone_id = params.get('parent')
        oid = params.get('id')

        compute_volume = task.get_simple_resource(compute_volume_id)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        compute_volume.add_link('%s-volume-link' % oid, 'relation.%s' % site_id, oid, attributes={})
        task.progress(step_id, msg='Link volume %s to compute volume %s' % (oid, compute_volume_id))
    
        return oid, params
    
    @staticmethod
    @task_step()
    def create_main_volume_step(task, step_id, params, *args, **kvargs):
        """Create main volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: volume_id, params
        """
        oid = params.get('id')
        compute_volume = params.get('compute_volume')
        availability_zone_id = params.get('parent')
        orchestrators = params.get('orchestrators')

        availability_zone = task.get_simple_resource(availability_zone_id)
        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get resource %s' % oid)
    
        # get main orchestrator
        main_orchestrator_id = params.get('main_orchestrator')
        orchestrator = orchestrators.get(main_orchestrator_id)
    
        # get remote parent for volume
        orchestrator_type = orchestrator['type']
        objdef = orchestrator_mapping(orchestrator_type, 0)
        parent = availability_zone.get_physical_resource_from_container(orchestrator['id'], objdef)
        helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)
        volume_id = helper.create_volume(compute_volume, parent, params)
        task.progress(step_id, msg='Create main volume: %s' % volume_id)
    
        return volume_id, params
    
    @staticmethod
    @task_step()
    def import_main_volume_step(task, step_id, params, *args, **kvargs):
        """Import main volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: volume_id, params
        """
        oid = params.get('id')
        orchestrator_type = params.get('type')
        resource_id = params.get('physical_id')

        resource = task.get_simple_resource(oid)
        remote_volume = task.get_simple_resource(resource_id)
        task.progress(step_id, msg='Get resource %s' % oid)

        helper = task.get_orchestrator(orchestrator_type, task, step_id, {'id': None}, resource)
        volume_id = helper.import_volume(remote_volume.oid)
        task.progress(step_id, msg='Import main volume: %s' % volume_id)
    
        return volume_id, params

    @staticmethod
    @task_step()
    def patch_compute_volume_step(task, step_id, params, *args, **kvargs):
        """Patch compute volume resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get('id')

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get resource %s' % oid)

        return oid, params

    @staticmethod
    @task_step()
    def patch_zone_volume_step(task, step_id, params, *args, **kvargs):
        """Patch zone volume resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get('id')

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get resource %s' % oid)

        # check link relation exist
        #sdp-mb2-0c51738b-avz710-2-server
        #sdp-mb2-0c51738b-avz710-2-server-root-volume

        #tst-services-redis-repl-comm02-portali-187ecbe0-volume-0-avz710
        #tst-services-redis-repl-comm02-portali-187ecbe0-avz710-2-server-root-volume

        return oid, params

    @staticmethod
    @task_step()
    def send_action_to_zone_volume_step(task, step_id, params, zone_volume_id, *args, **kvargs):
        """Send action to zone volume.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        action = params.get('action_name')
        configs = deepcopy(params)
        configs['id'] = zone_volume_id
        hypervisor = params.get('hypervisor')
        hypervisor_tag = params.get('hypervisor_tag')

        resource = task.get_simple_resource(oid)
        zone_volume = task.get_resource(zone_volume_id)
        task.progress(step_id, msg='Get resources')

        # send action
        prepared_task, code = zone_volume.action(action, configs, hypervisor, hypervisor_tag)
        task.progress(step_id, msg='Send action to availability zone volume %s' % zone_volume_id)
        res = run_sync_task(prepared_task, task, step_id)

        # run action post operation only for main zone volume
        if resource.get_main_zone_volume().oid == zone_volume_id:
            post_action = getattr(PostAction, action, None)
            if post_action is not None:
                post_action(task, resource, configs)

        return res, params

    @staticmethod
    @task_step()
    def volume_action_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Send action to physical server.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get('id')
        action = params.get('action_name')
        configs = deepcopy(params)
        configs['sync'] = True
        resource = task.get_simple_resource(oid)
        helper = task.get_orchestrator(orchestrator['type'], task, step_id, orchestrator, resource)
        res = helper.volume_action(action, configs)
        params['result'] = res
        return res, params
