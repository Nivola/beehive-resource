# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.model import BaseEntity
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource, ComputeZone
# from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
from logging import getLogger

logger = getLogger(__name__)

class ComputeLoggingRoleMapping(ComputeProviderResource):
    """Compute logging role mapping
    """
    objdef = 'Provider.ComputeZone.ComputeLoggingSpace.ComputeLoggingRoleMapping'
    objuri = '%s/logging_role_mappings/%s'
    objname = 'logging_role_mapping'
    objdesc = 'Provider ComputeLoggingRoleMapping'
    task_base_path = 'beehive_resource.plugins.provider.task_v2.logging_role_mapping.ComputeLoggingRoleMappingTask.'

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.child_classes = [
        ]

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # TODO: verify permissions

        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # TODO: verify permissions

        info = Resource.detail(self)
        # TODO metodo verificare se da implementare
        #info['applied'] = [a.small_info() for a in self.get_applied_logging_role_mapping()]
        return info

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.
        Use create when you want to create new elk role_mapping and connect to logging_role_mapping.

        :param kvargs.controller: resource controller instance
        :param kvargs.container: container instance
        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_type = kvargs.get('type')
        orchestrator_tag = kvargs.get('orchestrator_tag')
        #compute_zone_id = kvargs.get('compute_zone')
        space_id = kvargs.get('parent')

        # orchestrator_type = 'elk'
        logger.debug('+++++ orchestrator_type: %s' % (orchestrator_type))
        logger.debug('+++++ orchestrator_tag: %s' % (orchestrator_tag))
        #logger.debug('+++++ compute_zone_id: %s' % (compute_zone_id))
        logger.debug('+++++ space_id: %s' % (space_id))
        logger.debug('+++++ kvargs {0}: '.format(kvargs))

        # get compute logging space
        from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
        compute_logging_space: ComputeLoggingSpace
        compute_logging_space = container.get_simple_resource(space_id)
        compute_logging_space.check_active()
        compute_logging_space.set_container(container)
        compute_zone = compute_logging_space.get_parent()
        #compute_zone.oid - id della zone

        if compute_logging_space is None:
            raise ApiManagerError('ComputeLoggingSpace Parent not found')

        # get compute zone
        #compute_zone: ComputeZone
        #compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        multi_avz = True

        if compute_zone is None:
            raise ApiManagerError('ComputeZone Parent not found')

        # get availability zones ACTIVE
        availability_zones = ComputeProviderResource.get_active_availability_zones(compute_zone, multi_avz)

        # set params
        params = {
            'compute_zone': compute_zone.oid,
            'attribute': {
                'type': orchestrator_type,
                # 'type': 'elk',
                'orchestrator_tag': orchestrator_tag,
            }
        }
        kvargs.update(params)

        # TODO fv capire se in desc c'è la tripletta
        compute_zone_model: BaseEntity
        compute_zone_model = compute_zone.model
        controller.logger.debug2('compute_zone_model.desc %s' % (compute_zone_model.desc))

        # create task workflow
        steps = [
            ComputeLoggingRoleMapping.task_base_path + 'create_resource_pre_step',
        ]
        for availability_zone in availability_zones:
            logger.debug('+++++ role_mapping - create in availability_zone: %s' % (availability_zone))
            step = {
                'step': ComputeLoggingRoleMapping.task_base_path + 'create_zone_logging_role_mapping_step',
                'args': [availability_zone]
            }
            steps.append(step)
        steps.append(ComputeLoggingRoleMapping.task_path + 'create_resource_post_step')
        kvargs['steps'] = steps
        # fv - forzatura
        kvargs['sync'] = False

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.preserve: if True preserve resource when stack is removed
        :return: kvargs
        :raise ApiManagerError:
        """
        # check related objects

        # get logging_role_mappings
        customs, total = self.get_linked_resources(link_type_filter='relation%')
        childs = [e.oid for e in customs]

        # create task workflow
        kvargs['steps'] = self.group_remove_step(childs)

        return kvargs


class LoggingRoleMapping(AvailabilityZoneChildResource):
    """Availability Zone LoggingRoleMapping
    """
    objdef = 'Provider.Region.Site.AvailabilityZone.LoggingRoleMapping'
    objuri = '%s/logging_role_mappings/%s'
    objname = 'logging_role_mapping'
    objdesc = 'Provider Availability Zone LoggingRoleMapping'
    task_base_path = 'beehive_resource.plugins.provider.task_v2.logging_role_mapping.LoggingRoleMappingTask.'

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: parent availability zone resource id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrator tag [default=default]
        # TODO add missing params
        :return: kvargs
        :raise ApiManagerError:
        """
        avz_id = kvargs.get('parent')
        orchestrator_tag = kvargs.get('orchestrator_tag', 'default')

        # get availability_zone
        avz = container.get_simple_resource(avz_id)

        # select remote orchestrator
        orchestrator = avz.get_orchestrators_by_tag(orchestrator_tag, select_types=['elk'])

        # set container
        params = {
            'orchestrator': list(orchestrator.values())[0]
        }
        kvargs.update(params)

        # create task workflow
        steps = [
            LoggingRoleMapping.task_base_path + 'create_resource_pre_step',
            LoggingRoleMapping.task_base_path + 'create_elk_role_mapping_step',
            LoggingRoleMapping.task_base_path + 'create_resource_post_step',
        ]
        kvargs['steps'] = steps
        kvargs['sync'] = True

        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource physical id
        :return: kvargs
        :raise ApiManagerError:
        """
        # select physical orchestrator
        orchestrator_idx = self.get_orchestrators(select_types=['elk'])
        kvargs['steps'] = self.group_remove_step(orchestrator_idx)
        kvargs['sync'] = True

        return kvargs

    def get_elk_role_mapping(self):
        """get elk role mapping resource

        :return: elk role mapping resource
        """
        role_mappings, total = self.get_linked_resources(link_type_filter='relation')
        if total > 0:
            role_mapping = role_mappings[0]
            self.logger.debug('get zone logging_role_mapping %s elk role_mapping: %s' % (self.oid, role_mapping))
            return role_mapping
        else:
            raise ApiManagerError('no elk role_mapping in zone logging_role_mapping %s' % self.oid)