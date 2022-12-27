# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor, VolumeFlavor
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class VolumeFlavorTask(AbstractProviderResourceTask):
    """VolumeFlavor task
    """
    name = 'volumeflavor_task'
    entity_class = ComputeVolumeFlavor

    @staticmethod
    @task_step()
    def create_zone_volumeflavor_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create compute_flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        
        provider = task.get_container(cid)
        availability_zone = task.get_resource(availability_zone_id, run_customize=False)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg='Get resources')
    
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
        prepared_task, code = provider.resource_factory(VolumeFlavor, **flavor_params)
        flavor_id = prepared_task['uuid']
    
        # link flavor to compute flavor
        task.get_session(reopen=True)
        compute_flavor = task.get_simple_resource(oid)
        compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
        task.progress(step_id, msg='Link volume flavor %s to compute volume flavor %s' % (flavor_id, oid))
    
        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create volume flavor in availability zone %s' % availability_zone_id)
    
        return True, params
    
    @staticmethod
    @task_step()
    def import_zone_volumeflavor_step(task, step_id, params, site_id, flavors, *args, **kvargs):
        """Import compute flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param site_id: site id
        :param flavors: list of flavor config
        :param flavors.x.site_id:
        :param flavors.x.availability_zone_id:
        :param flavors.x.orchestrator_id: orchestrator id
        :param flavors.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param flavors.x.flavor_id:
        :return: True, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        availability_zone_id = flavors[0].get('availability_zone_id')

        provider = task.get_container(cid)
        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get provider %s' % cid)
    
        # create flavor
        flavor_params = {
            'name': '%s-avz%s' % (resource.name, site_id),
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
        prepared_task, code = provider.resource_factory(VolumeFlavor, **flavor_params)
        flavor_id = prepared_task['uuid']

        # link flavor to compute flavor
        task.get_session(reopen=True)
        compute_flavor = task.get_simple_resource(oid)
        compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
        task.progress(step_id, msg='Link volume flavor %s to compute volume flavor %s' % (flavor_id, oid))
    
        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Import volume flavor in availability zone %s' % availability_zone_id)
    
        return True, params
    
    @staticmethod
    @task_step()
    def update_zone_volumeflavor_step(task, step_id, params, site_id, flavors, *args, **kvargs):
        """Update compute_flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param site_id: site id
        :param flavors: list of flavor config
        :param flavors.x.site_id: site id
        :param flavors.x.availability_zone_id: availability zone_ id
        :param flavors.x.orchestrator_id: orchestrator id
        :param flavors.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param flavors.x.flavor_id: flavor id
        :return: True, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        availability_zone_id = flavors[0].get('availability_zone_id')

        provider = task.get_container(cid)
        task.progress(step_id, msg='Get provider %s' % cid)
    
        # check zone flavor already exists
        zone_flavors = task.get_orm_linked_resources(oid, link_type='relation.%s' % site_id, container_id=cid)
        if len(zone_flavors) > 0:
            zone_flavor = provider.get_resource(zone_flavors[0].id, run_customize=False)
            task.progress(step_id, msg='Site %s already linked to compute flavor %s' % (site_id, oid))
    
            # update flavor
            flavor_params = {
                'orchestrator_tag': params.get('orchestrator_tag'),
                'flavors': flavors
            }
            res = zone_flavor.update(**flavor_params)
            job_id = res[0]['jobid']
            task.progress(step_id, msg='Update flavor in availability zone %s - start job %s' %
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
            prepared_task, code = provider.resource_factory(VolumeFlavor, **flavor_params)
            flavor_id = prepared_task['uuid']
    
            # link flavor to compute flavor
            task.get_session(reopen=True)
            compute_flavor = task.get_simple_resource(oid)
            compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
            task.progress(step_id, msg='Link volume flavor %s to compute volume flavor %s' % (flavor_id, oid))
    
            # wait job complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg='Create volume flavor in availability zone %s' % availability_zone_id)
    
        return True, params
    
    @staticmethod
    @task_step()
    def volumetype_create_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create provider flavor in remote orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :return: volumetype_id, params
        """
        oid = params.get('id')

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get volume_type %s' % oid)

        helper = task.get_orchestrator(orchestrator.get('type'), task, step_id, orchestrator, resource)
        volumetype_id = helper.create_volumetype()
        task.progress(step_id, msg='Create volume_type %s' % orchestrator.get('type'))
    
        return volumetype_id, params
    
    @staticmethod
    @task_step()
    def volumetype_import_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Import provider flavor from remote orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :return: volumetype_id, params
        """
        oid = params.get('id')
        volumetype_conf = orchestrator.get('volume_type', None)

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg='Get volume_type %s' % oid)
    
        volumetype_id = None
        helper = task.get_orchestrator(orchestrator.get('type'), task, step_id, orchestrator, resource)
        if volumetype_conf is not None:
            volumetype_id = helper.import_volumetype(volumetype_conf['id'])
            task.progress(step_id, msg='Import volume type %s' % volumetype_conf['id'])
    
        return volumetype_id, params
