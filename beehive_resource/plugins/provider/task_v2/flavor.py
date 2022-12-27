# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor, Flavor
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class FlavorTask(AbstractProviderResourceTask):
    """Flavor task
    """
    name = 'flavor_task'
    entity_class = ComputeFlavor

    @staticmethod
    @task_step()
    def create_zone_flavor_step(task, step_id, params, availability_zone_id, *args, **kvargs):
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
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg='Get resources')
    
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
        prepared_task, code = provider.resource_factory(Flavor, **flavor_params)
        flavor_id = prepared_task['uuid']

        # link flavor to compute flavor
        task.get_session(reopen=True)
        compute_flavor = task.get_simple_resource(oid)
        compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
        task.progress(step_id, msg='Link flavor %s to compute flavor %s' % (flavor_id, oid))
    
        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create flavor in availability zone %s' % availability_zone_id)
    
        return True, params
    
    @staticmethod
    @task_step()
    def import_zone_flavor_step(task, step_id, params, site_id, flavors, *args, **kvargs):
        """Import compute flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param site_id: site id
        :param flavors: list of
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
        task.progress(step_id, msg='Get provider %s' % cid)
    
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
        prepared_task, code = provider.resource_factory(Flavor, **flavor_params)
        flavor_id = prepared_task['uuid']
    
        # link flavor to compute flavor
        task.get_session(reopen=True)
        compute_flavor = task.get_simple_resource(oid)
        compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
        task.progress(step_id, msg='Link flavor %s to compute flavor %s' % (flavor_id, oid))
    
        # wait task complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Import flavor in availability zone %s' % availability_zone_id)
    
        return True, params
    
    @staticmethod
    @task_step()
    def update_zone_flavor_step(task, step_id, params, site_id, flavors, *args, **kvargs):
        """Update compute_flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param sharedarea.site_id: site id
        :param sharedarea.flavors: list of
        :param sharedarea.site_id:
        :param sharedarea.availability_zone_id:
        :param sharedarea.orchestrator_id: orchestrator id
        :param sharedarea.orchestrator_type Orchestrator type. Ex. vsphere, openstack
        :param sharedarea.flavor_id:    
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
            zone_flavor = provider.get_resource(zone_flavors[0].id)
            task.progress(step_id, msg='Site %s already linked to compute flavor %s' % (site_id, oid))
    
            # update flavor
            flavor_params = {
                'orchestrator_tag': params.get('orchestrator_tag'),
                'flavors': flavors
            }
            prepared_task, code = zone_flavor.update(**flavor_params)
            run_sync_task(prepared_task, task, step_id)
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
            prepared_task, code = provider.resource_factory(Flavor, **flavor_params)
            flavor_id = prepared_task['uuid']
    
            # link flavor to compute flavor
            task.get_session(reopen=True)
            compute_flavor = task.get_simple_resource(oid)
            compute_flavor.add_link('%s-flavor-link' % flavor_id, 'relation.%s' % site_id, flavor_id, attributes={})
            task.progress(step_id, msg='Link flavor %s to compute flavor %s' % (flavor_id, oid))
    
            # wait task complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg='Create flavor in availability zone %s' % availability_zone_id)
    
        return True, params
    
    @staticmethod
    @task_step()
    def flavor_create_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create compute_flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :return: flavor_id, params
        """
        oid = params.get('id')

        resource = task.get_resource(oid)
        task.progress(step_id, msg='Get flavor %s' % oid)

        helper = task.get_orchestrator(orchestrator.get('type'), task, step_id, orchestrator, resource)
        flavor_id = helper.create_flavor()
        task.progress(step_id, msg='Create flavor %s' % orchestrator.get('type'))
    
        return flavor_id, params
    
    @staticmethod
    @task_step()
    def flavor_import_orchestrator_resource_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Create compute_flavor flavor.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator config
        :return: flavor_id, params
        """
        oid = params.get('id')
        flavor_conf = orchestrator.get('flavor', None)

        resource = task.get_resource(oid)
        task.progress(step_id, msg='Get flavor %s' % oid)
    
        flavor_id = None
        if flavor_conf is not None:
            helper = task.get_orchestrator(orchestrator.get('type'), task, step_id, orchestrator, resource)
            flavor_id = helper.import_flavor(flavor_conf['id'])
            task.progress(step_id, msg='Import flavor %s' % flavor_conf['id'])
    
        return flavor_id, params
