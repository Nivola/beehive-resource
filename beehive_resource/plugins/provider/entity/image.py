# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.simple import get_value
from beehive_resource.container import Resource
from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.site import Site
from beehive_resource.plugins.provider.entity.zone import AvailabilityZoneChildResource
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer


class ComputeImage(ComputeProviderResource):
    """Compute image
    """
    objdef = 'Provider.ComputeZone.ComputeImage'
    objuri = '%s/images/%s'
    objname = 'image'
    objdesc = 'Provider ComputeImage'
    task_path = 'beehive_resource.plugins.provider.task_v2.image.ImageTask.'

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.availability_zones = []

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info['availability_zones'] = self.availability_zones
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        info['availability_zones'] = self.availability_zones
        return info

    def get_os_version(self):
        """Get OS version
        """
        os_ver = self.get_configs().get('os_ver')
        return os_ver.split('.')[0]

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
        resource_idx = {}
        for e in entities:
            resource_idx[e.oid] = e

        resource_zones = controller.get_directed_linked_resources_internal(
            resources=list(resource_idx.keys()), link_type='relation%', run_customize=False)
        sites = controller.index_resources_by_id(entity_class=Site)

        resource_zone_ids = []
        for items in resource_zones.values():
            for item in items:
                resource_zone_ids.append(item.oid)

        remote_entities = controller.get_directed_linked_resources_internal(
            resources=resource_zone_ids, link_type='relation', run_customize=False)

        for entity in entities:
            controller.logger.warn(entity.name)
            controller.logger.warn(entity.oid)
            entity_resource_zones = resource_zones.get(entity.oid, [])
            for resource_zone in entity_resource_zones:
                remote_entities2 = remote_entities.get(resource_zone.oid)
                hypervisors = []
                for remote_entity in remote_entities2:
                    if remote_entity.objdef == OpenstackImage.objdef:
                        hypervisors.append('openstack')
                    elif remote_entity.objdef == VsphereServer.objdef:
                        hypervisors.append('vsphere')
                hypervisors.sort()
                temp = resource_zone.name.find('-avz')
                site_id = int(resource_zone.name[temp+4:])
                item = {'name': sites.get(site_id).name, 'hypervisors': hypervisors}
                entity.availability_zones.append(item)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        resource_zones = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], link_type='relation%', run_customize=False)
        sites = self.controller.index_resources_by_id(entity_class=Site)

        resource_zone_ids = []
        for items in resource_zones.values():
            for item in items:
                resource_zone_ids.append(item.oid)

        remote_entities = self.controller.get_directed_linked_resources_internal(
            resources=resource_zone_ids, link_type='relation', run_customize=False)

        for resource_zone in resource_zones.get(self.oid, []):
            remote_entities2 = remote_entities.get(resource_zone.oid, [])
            hypervisors = []
            for remote_entity in remote_entities2:
                if remote_entity.objdef == OpenstackImage.objdef:
                    hypervisors.append('openstack')
                elif remote_entity.objdef == VsphereServer.objdef:
                    hypervisors.append('vsphere')
            hypervisors.sort()
            temp = resource_zone.name.find('-avz')
            site_id = int(resource_zone.name[temp+4:])
            item = {'name': sites.get(site_id).name, 'hypervisors': hypervisors}
            self.availability_zones.append(item)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.compute_zone: compute zone id
        :param kvargs.os: operating system
        :param kvargs.os_ver: operating system version
        :param kvargs.min_disk_size: minimum disk size required to run this image [default=20]
        :param kvargs.templates: list of remote orchestrator template reference
        :param kvargs.templates.x.orchestrator_type: orchestrator type. Ex. openstack, vsphere
        :param kvargs.templates.x.availability_zone: availability zone
        :param kvargs.templates.x.orchestrator: orchestrator
        :param kvargs.templates.x.template_id: template id
        :return: kvargs
        :raise ApiManagerError:
        
        Ex.

            {
                ...
                'templates':{
                    <site_id>:{
                        'orchestrator_type':..,
                        'site_id':..,
                        'availability_zone_id':..,
                        'orchestrator_id':..,
                        'template_id':..,
                        ['admin_pwd':..]
                    }
                }
            }        
        """
        # get zone
        compute_zone = container.get_resource(kvargs.get('parent'))

        # check template
        templates = {}
        for template in kvargs.get('templates'):
            orchestrator = controller.get_container(template.pop('orchestrator'))
            template['orchestrator_id'] = orchestrator.oid
            site_id = controller.get_resource(template.pop('availability_zone'), entity_class=Site).oid
            template['site_id'] = site_id
            zones, tot = compute_zone.get_linked_resources(link_type='relation.%s' % site_id)
            template['availability_zone_id'] = zones[0].oid
            template_id = template['template_id']
            if template['orchestrator_type'] == 'vsphere':
                template['template_id'] = orchestrator.get_simple_resource(template_id, entity_class=VsphereServer).oid
                get_value(template, 'template_pwd', None, exception=True)
            elif template['orchestrator_type'] == 'openstack':
                template['template_id'] = orchestrator.get_simple_resource(template_id, entity_class=OpenstackImage).oid
            try:
                templates[site_id].append(template)
            except:
                templates[site_id] = [template]

        # set attributes
        attrib = {
            'configs': {
                'os': kvargs.get('os'),
                'os_ver': kvargs.get('os_ver'),
                'min_disk_size': kvargs.get('min_disk_size')
            }
        }
        kvargs['attribute'] = attrib
        kvargs['orchestrator_tag'] = kvargs.get('orchestrator_tag', 'default')

        # create task workflow
        steps = []
        for site_id, images in templates.items():
            substep = {
                'step': ComputeImage.task_path + 'import_zone_image_step',
                'args': [site_id, images]
            }
            steps.append(substep)
        kvargs['steps'] = ComputeProviderResource.group_create_step(steps)

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method. Extend
        this function to manipulate and validate update input params.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.templates: list of remote orchestrator template reference
        :param kvargs.templates.x.orchestrator_type: orchestrator type. Ex. openstack, vsphere
        :param kvargs.templates.x.availability_zone: availability zone
        :param kvargs.templates.x.orchestrator: orchestrator
        :param kvargs.templates.x.template_id: template id
        :return: kvargs
        :raise ApiManagerError:
        
        Ex.        

            {
                ...
                'templates':{
                    <site_id>:{
                        'orchestrator_type':..,
                        'site_id':..,
                        'availability_zone_id':..,
                        'orchestrator_id':..,
                        'template_id':..,
                        ['admin_pwd':..]
                    }
                }
            }        
        """
        # get zone
        compute_zone = self.get_parent()

        # check template
        templates = {}
        for template in kvargs.get('templates', []):
            orchestrator = self.controller.get_container(template.pop('orchestrator'))
            template['orchestrator_id'] = orchestrator.oid
            site_id = self.controller.get_resource(template.pop('availability_zone'), entity_class=Site).oid
            template['site_id'] = site_id
            zones, tot = compute_zone.get_linked_resources(link_type='relation.%s' % site_id, authorize=False)
            zone_templates, tot_zone_tmpls = self.get_linked_resources(link_type='relation.%s' % site_id,
                                                                       authorize=False,
                                                                       run_customize=False)
            template['availability_zone_id'] = zones[0].oid
            template_id = template['template_id']
            if template['orchestrator_type'] == 'vsphere':
                template['template_id'] = orchestrator.get_resource(template_id, entity_class=VsphereServer).oid
            elif template['orchestrator_type'] == 'openstack':
                template['template_id'] = orchestrator.get_resource(template_id, entity_class=OpenstackImage).oid

            # check template already linked
            if tot_zone_tmpls == 0:
                try:
                    templates[site_id].append(template)
                except:
                    templates[site_id] = [template]

        self.logger.debug('Append new templates: %s' % kvargs.get('templates', []))

        # create task workflow
        steps = []
        for site_id, templates in templates.items():
            substep = {
                'step': ComputeImage.task_path + 'update_zone_template_step',
                'args': [site_id, templates]
            }
            steps.append(substep)
        kvargs['steps'] = self.group_update_step(steps)

        # set attributes
        kvargs['name'] = self.name
        kvargs['desc'] = self.desc
        kvargs['os'] = self.get_attribs(key='configs.os')
        kvargs['os_ver'] = self.get_attribs(key='configs.os_ver')

        return kvargs


class Image(AvailabilityZoneChildResource):
    """Availability Zone Image
    """
    objdef = 'Provider.Region.Site.AvailabilityZone.Image'
    objuri = '%s/images/%s'
    objname = 'image'
    objdesc = 'Provider Availability Zone Image'
    task_path = 'beehive_resource.plugins.provider.task_v2.image.ImageTask.'

    def __init__(self, *args, **kvargs):
        AvailabilityZoneChildResource.__init__(self, *args, **kvargs)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input kvargs before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom kvargs
        :param kvargs: custom kvargs
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.configs:
        :param kvargs.os:
        :param kvargs.os_ver:
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.templates: list of temaplte config
        :param kvargs.templates.x.site_id:
        :param kvargs.templates.x.availability_zone_id:
        :param kvargs.templates.x.orchestrator_id: orchestrator id
        :param kvargs.templates.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param kvargs.templates.x.template_id:
        :param kvargs.templates.x.template_pwd: [only for vsphere]
        :param kvargs.templates.x.guest_id: [only for vsphere]
        :return: kvargs
        :raise ApiManagerError:
        
        Ex.
        
            {
                ...
                'orchestrators':{
                    '1':{
                        'template':{
                            'id':..,
                            'template_pwd':..,
                            'guest_if':..
                        }
                    },
                    ...
                }
            }        
        """
        orchestrator_tag = kvargs.get('orchestrator_tag', 'default')
        templates = kvargs.get('templates')

        # get zone
        zone = container.get_simple_resource(kvargs.get('parent'))

        # select remote orchestrators
        orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
        orchestrator_ids = list(orchestrator_idx.keys())

        # assign template to orchestrator
        for t in templates:
            orchestrator_id = t.get('orchestrator_id')
            # remove template if container not in subset selected via tag
            if str(orchestrator_id) in orchestrator_ids:
                orchestrator_idx[str(orchestrator_id)]['template'] = {
                    'id': t['template_id'], 
                    'guest_id': t.get('guest_id', None),
                    'template_pwd': t.get('template_pwd', None),
                    'customization_spec_name': t.get('customization_spec_name', None)
                }

        params = {
            'orchestrators': orchestrator_idx
        }

        kvargs.update(params)

        # create task workflow
        steps = []
        for item in orchestrator_idx.values():
            substep = {
                'step': Image.task_path + 'image_import_orchestrator_resource_step',
                'args': [item]
            }
            steps.append(substep)

        kvargs['steps'] = AvailabilityZoneChildResource.group_create_step(steps)
        kvargs['sync'] = True

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method. Extend
        this function to manipulate and validate update input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :param cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.templates: list of temaplte config
        :param kvargs.templates.x.site_id:
        :param kvargs.templates.x.availability_zone_id:
        :param kvargs.templates.x.orchestrator_id: orchestrator id
        :param kvargs.templates.x.orchestrator_type: Orchestrator type. Ex. vsphere, openstack
        :param kvargs.templates.x.template_id:
        :param kvargs.templates.x.template_pwd: [only for vsphere]
        :param kvargs.templates.x.guest_id: [only for vsphere]
        :return: kvargs
        :raise ApiManagerError:
        """
        orchestrator_tag = kvargs.get('orchestrator_tag', 'default')
        templates = kvargs.get('templates', None)

        # get zone
        zone = self.get_parent()

        # assign template to orchestrator
        steps = None
        if templates is not None:
            # select remote orchestrators
            orchestrator_idx = zone.get_orchestrators_by_tag(orchestrator_tag)
            orchestrator_ids = list(orchestrator_idx.keys())

            for t in templates:
                orchestrator_id = t.get('orchestrator_id')
                # remove template if container not in subset selected via tag
                if str(orchestrator_id) in orchestrator_ids:
                    orchestrator_idx[str(orchestrator_id)]['template'] = {
                        'id': t['template_id'],
                        'guest_id': t.get('guest_id', None),
                        'template_pwd': t.get('template_pwd', None)
                    }

            # create task workflow
            steps = []
            for item in orchestrator_idx.values():
                substep = {
                    'step': Image.task_path + 'image_import_orchestrator_resource_step',
                    'args': [item]
                }
                steps.append(substep)

        kvargs['steps'] = self.group_update_step(steps)
        kvargs['sync'] = True

        return kvargs

    def get_vsphere_image(self):
        """Get vsphere server template"""
        res, tot = self.get_linked_resources(link_type_filter='relation', objdef=VsphereServer.objdef)
        if tot > 0:
            return res[0]
        return None

    def get_openstack_image(self):
        """Get openstack image"""
        res, tot = self.get_linked_resources(link_type_filter='relation', objdef=OpenstackImage.objdef)
        if tot > 0:
            return res[0]
        return None
