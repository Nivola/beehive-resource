# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from datetime import datetime
from beecell.db import QueryError
from beecell.types.type_string import truncate
from beecell.types.type_dict import dict_get
from beecell.types.type_date import format_date
from beedrones.openstack.project import OpenstackProject
from beehive.common.apiclient import BeehiveApiClientError
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace, operation
from beehive_resource.container import Resource
from beehive_resource.model import Resource as ModelResource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource, ComputeQuotas
from beehive_resource.plugins.provider.entity.region import Region
from beehive_resource.plugins.provider.entity.site import Site, SiteChildResource


class ComputeZone(ComputeProviderResource):
    """Compute zone
    """
    objdef = 'Provider.ComputeZone'
    objuri = '%s/compute_zones/%s'
    objname = 'compute_zone'
    objdesc = 'Provider Compute Zone'
    task_path = 'beehive_resource.plugins.provider.task_v2.zone.ZoneTask.'

    create_task = None
    import_task = None
    update_task = None
    patch_task = None
    delete_task = None
    expunge_task = None
    # action_task = 'beehive_resource.task_v2.core.resource_action_task'

    BCK_WORKLOAD_PREFIX = 'WRKL-'

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        # from beehive_resource.plugins.provider.entity.stack import ComputeStack
        from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2
        from beehive_resource.plugins.provider.entity.share import ComputeFileShare
        from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
        from beehive_resource.plugins.provider.entity.image import ComputeImage
        from beehive_resource.plugins.provider.entity.instance import ComputeInstance
        from beehive_resource.plugins.provider.entity.rule import ComputeRule
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc
        from beehive_resource.plugins.provider.entity.volume import ComputeVolume
        from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
        from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
        # from beehive_resource.plugins.provider.entity.security_group_acl import SecurityGroupAcl
        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway
        from beehive_resource.plugins.provider.entity.bastion import ComputeBastion
        from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
        from beehive_resource.plugins.provider.entity.monitoring_folder import ComputeMonitoringFolder
        from beehive_resource.plugins.provider.entity.load_balancer import ComputeLoadBalancer

        self.quotas = ComputeQuotas(self.get_attribs().get('quota', {}))
        self.availability_zones = []
        self.site_idx = None
        self.region_idx = None

        self.child_classes = [
            Vpc,
            ComputeRule,
            # SecurityGroupAcl,
            ComputeInstance,
            ComputeVolume,
            ComputeVolumeFlavor,
            ComputeFlavor,
            ComputeImage,
            # ComputeStack,
            ComputeStackV2,
            ComputeFileShare,
            ComputeCustomization,
            ComputeGateway,
            ComputeBastion,
            ComputeLoggingSpace,
            ComputeMonitoringFolder,
            ComputeLoadBalancer,
        ]

    def get_availability_zones(self):
        """Get child availability zones"""
        # zones, total = self.get_linked_resources(link_type_filter='relation%')
        for z in self.availability_zones:
            z.site = self.site_idx.get(z.parent_id)
            z.region = self.region_idx.get(z.site.parent_id)
        return self.availability_zones

    def get_availability_zone(self, site_id):
        link_type = 'relation.%s' % site_id
        zones = self.controller.get_directed_linked_resources_internal(
            resources=[self.oid], link_type=link_type, objdef=AvailabilityZone.objdef, run_customize=False)
        zone = zones.get(self.oid, [])
        if len(zone) > 0:
            return zone[0]
        return None

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info.pop('attributes')
        zones = self.get_availability_zones()
        info['availability_zones'] = [self.site_idx.get(z.parent_id).name for z in zones]
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        info.pop('attributes')
        zones = self.get_availability_zones()
        info['availability_zones'] = [self.site_idx.get(z.parent_id).name for z in zones]
        # availability_zones = []
        # for z in zones:
        #     avz = z.get_site().info()
        #     # avz['name'] = z.get_site().name
        #     availability_zones.append(avz)
        # info['availability_zones'] = availability_zones
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
        site_idx = controller.index_resources_by_id(entity_class=Site)
        region_idx = controller.index_resources_by_id(entity_class=Region)
        resource_ids = []
        for e in entities:
            e.site_idx = site_idx
            e.region_idx = region_idx
            resource_ids.append(e.oid)
        zones = controller.get_directed_linked_resources_internal(resources=resource_ids, link_type='relation%',
                                                                  objdef=AvailabilityZone.objdef, run_customize=False)
        for e in entities:
            e.availability_zones = zones.get(e.oid, [])
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method. Extend this function to extend description
        info returned after query.

        :raise ApiManagerError:
        """
        self.site_idx = self.controller.index_resources_by_id(entity_class=Site)
        self.region_idx = self.controller.index_resources_by_id(entity_class=Region)
        zones, total = self.get_linked_resources(link_type_filter='relation%', objdef=AvailabilityZone.objdef,
                                                 details=False)
        self.availability_zones = zones

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

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
        :param kvargs.managed: if True create ssh group where register compute instance reference
        :param kvargs.quota: quota
        :param kvargs.compute.instances: 2
        :param kvargs.compute.images: 2
        :param kvargs.compute.volumes: 2
        :param kvargs.compute.blocks: 1024
        :param kvargs.compute.ram: 10
        :param kvargs.compute.cores: 4
        :param kvargs.compute.networks: 2
        :param kvargs.compute.floatingips: 2
        :param kvargs.compute.security_groups: 2
        :param kvargs.compute.security_group_rules: 10
        :param kvargs.compute.keypairs: 2
        :param kvargs.database.instances: 2
        :param kvargs.share.instances: 2
        :param kvargs.appengine.instances: 2
        :return: (:py:class:`dict`)
        :raise ApiManagerError:
        """
        quota = kvargs.get('quota')
        params = {
            'attribute': {
                'quota': quota,
                'configs': {}
            }
        }
        kvargs.update(params)

        return kvargs

    @staticmethod
    def post_create(controller, *args, **kvargs):
        """Post create function. This function is used in object_factory method.
        Used only for synchronous creation. Extend this function to execute some operation after entity was created.

        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.managed: if True create ssh group where register compute instance reference
        :return: None
        :raise ApiManagerError:
        """
        group_name = kvargs.get('desc')
        group_name = group_name.replace(' ', '_')
        uuid = kvargs.get('uuid')
        managed = kvargs.get('managed')
        managed_by = kvargs.get('managed_by', None)

        if managed is True:
            # if compute zone is managed create group in ssh
            group_uuid = None
            res = controller.api_client.exist_ssh_group(group_name)
            if res is True:
                group_uuid = 1
                controller.logger.warning('Ssh group %s already exists. Compute zone %s can not be managed' %
                                          (group_name, uuid), exc_info=1)

            if group_uuid is None:
                # create group
                desc = 'Group %s' % kvargs.get('desc')
                desc = desc.replace('.', ' ')
                attribute = ''
                group_uuid = controller.api_client.add_ssh_group(group_name, desc, attribute)

                # assign role to a group or a user
                if managed_by is not None:
                    user = None
                    group = None
                    if managed_by.find('@') > 0:
                        user = managed_by
                    else:
                        group = managed_by
                    try:
                        controller.api_client.set_ssh_group_authorization(group_uuid, 'master', user=user, group=group)
                    except BeehiveApiClientError as ex:
                        controller.logger.warn('Could not set ssh group authorization for user/group %s' % user)
                    except Exception as ex:
                        controller.logger.warn('Could not set ssh group authorization for user/group %s' % user)

                controller.logger.debug('Compute zone %s is now managed by ssh group %s' % (uuid, group_uuid))

        return None

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        # check related availability zones
        avzones, total = self.get_linked_resources(link_type_filter='relation%')
        if total > 0:
            raise ApiManagerError('Compute zone has related availability zones')

        # check related objects
        vpcs, total = self.get_linked_resources(link_type='vpc')
        if len(vpcs) > 0:
            raise ApiManagerError('Compute zone has related vpcs')

        # check if exists an ssh management group. If it exixts, delete
        group_uuid = None
        group_name = self.desc
        group_name = group_name.replace(' ', '_')
        try:
            res = self.api_client.get_ssh_group(group_name)
            group_uuid = res.get('uuid')
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                self.logger.warning('Compute zone %s is not managed by ssh module' % self.uuid, exc_info=1)

        if group_uuid is not None:
            self.api_client.delete_ssh_group(group_name)
            self.logger.debug('Compute zone %s is now unmanaged by ssh group %s' % (self.uuid, group_uuid))

        # get avzones
        # avzones, total = self.get_linked_resources(link_type='relation%')

        # params = {'childs':[p.oid for p in avzones]}
        # kvargs.update(params)
        return kvargs

    @trace(op='update')
    def add_site(self, params):
        """Add site

        :param params: dict with params
        :param kvargs.id: site id
        :param kvargs.orchestrator_tag: remote orchestrator tag
        :param kvargs.quota: availability zone quota
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions('update')

        site_id = params.get('id')
        site = self.container.get_resource(site_id, entity_class=Site)

        # check availability zone already exists
        avzone, total = self.get_linked_resources(link_type='relation.%s' % site.oid)

        if total > 0:
            raise ApiManagerError('Compute zone %s is already linked to site %s' % (self.oid, site.oid))

        orchestrator_tag = params.get('orchestrator_tag')
        quota = params.get('quota', None)
        if quota is None:
            quota = self.get_attribs().get('quota')
        name = '%s-avz%s' % (self.name, site.oid)
        res = self.container.resource_factory(AvailabilityZone, name=name, desc=self.desc, ext_id=None, active=False,
                                              attribute={}, parent=site.oid, tags='', site=site.oid, zone=self.oid,
                                              orchestrator_tag=orchestrator_tag, quota=quota)
        return res

    @trace(op='update')
    def delete_site(self, params):
        """Delete site

        :param params: dict with params
        :param kvargs.id: site id
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions('update')

        site_id = params.get('id')
        site = self.container.get_resource(site_id, entity_class=Site)

        # get avzones
        avzone, total = self.get_linked_resources(link_type='relation.%s' % site.oid)

        if total > 0:
            res = avzone[0].expunge()
        else:
            raise ApiManagerError('Compute zone %s is not linked to site %s' % (self.oid, site.oid))

        return res

    #
    # manage through ssh module
    #
    @trace(op='update')
    def get_ssh_group(self):
        """Get compute zone ssh module group.

        :return: ssh group uuid
        :raise ApiManagerError:
        """
        try:
            group = self.api_client.get_ssh_group(self.desc)
        except BeehiveApiClientError as ex:
            self.logger.error('Compute zone %s' % self.uuid, exc_info=1)
            if ex.code == 404:
                raise ApiManagerError('Compute zone %s is not managed by ssh module' % self.uuid)
            raise
        self.logger.debug('Get compute zone %s ssh group: %s' % (self.uuid, group))
        return group.get('uuid')

    @trace(op='update')
    def is_managed(self):
        """Check compute zone is managed with ssh module.

        :return: True if it is managed
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions('update')

        group_name = self.desc
        group_name = group_name.replace(' ', '_')

        try:
            self.api_client.get_ssh_group(group_name)
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                self.logger.debug('Compute zone %s is not managed by ssh module' % self.uuid)
                return False
            self.logger.error('Compute zone %s' % self.uuid, exc_info=1)
            raise
        self.logger.debug('Compute zone %s is managed by ssh module' % self.uuid)
        return True

    @trace(op='manage.update')
    def manage(self):
        """Manage compute zone server with ssh module. Create group in ssh module where register server.

        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions('update')

        group_name = self.desc
        group_name = group_name.replace(' ', '_')

        try:
            res = self.api_client.get_ssh_group(group_name)
            uuid = res.get('uuid')
            self.logger.warning('Compute zone %s is already managed by ssh module' % self.uuid, exc_info=1)
            return uuid
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                pass
            else:
                raise

        desc = 'Group %s' % self.desc
        desc.replace('.', ' ')
        attribute = ''
        uuid = self.api_client.add_ssh_group(group_name, desc, attribute)

        self.logger.debug('Compute zone %s is now managed by ssh group %s' % (self.uuid, uuid))
        return uuid

    @trace(op='unmanage.update')
    def unmanage(self):
        """Unmanage compute zone server with ssh module. Remove group in ssh module where register server.

        :return: True
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions('update')

        group_name = self.desc
        group_name = group_name.replace(' ', '_')

        try:
            res = self.api_client.get_ssh_group(group_name)
            uuid = res.get('uuid')
        except BeehiveApiClientError as ex:
            if ex.code == 404:
                self.logger.warning('Compute zone %s is not managed by ssh module' % self.uuid, exc_info=1)
            else:
                raise

        uuid = self.api_client.delete_ssh_group(group_name)

        self.logger.debug('Compute zone %s is now unmanaged by ssh module' % (self.uuid))
        return True

    @trace(op='update')
    def get_ssh_keys(self, oid=None, *args, **kvargs):
        """Get ssh keys

        :return: list of ssh keys
        :raise ApiManagerError:
        """
        # check authorization
        self.verify_permisssions('use')

        try:
            res = self.api_client.get_ssh_keys(oid)
        except BeehiveApiClientError:
            raise ApiManagerError('Ssh key %s does not exists' % oid, code=404)

        return res

    #
    # query methods
    #
    def get_bastion_host(self):
        """Get bastion host"""
        links, total = self.get_links(type='bastion')
        if total == 1:
            link = links[0]
            bastion = link.get_end_resource()
            bastion.public_host = link.get_attribs(key='host')
            bastion.public_port = link.get_attribs(key='port')
            self.logger.debug('get compute zone %s bastion host: %s' % (self.oid, bastion.oid))
            return bastion
        self.logger.warning('get compute zone %s has no bastion host' % self.oid)
        return None

    def get_default_gateway(self):
        """Get default gateway"""
        from beehive_resource.plugins.provider.entity.gateway import ComputeGateway
        gws, tot = self.get_resources(authorize=False, run_customize=False, type=ComputeGateway.objdef)
        if tot == 0:
            raise ApiManagerError('no default gateway found in compute zone %s' % self.oid)
        gw = gws[0]
        self.logger.debug('get default compute zone %s gateway: %s' % (self.oid, gw.oid))
        return gw

    def get_default_vpc(self):
        """Get default vpc"""
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc
        vpcs, tot = self.get_resources(authorize=False, run_customize=False, type=Vpc.objdef)
        if tot == 0:
            raise ApiManagerError('no default vpc found in compute zone %s' % self.oid)
        vpc = vpcs[0]
        self.logger.debug('get default compute zone %s vpc: %s' % (self.oid, vpc.oid))
        return vpc

    def get_default_security_groups(self, vpc_ids):
        """Get default security groups

        :param vpc_ids: list of vpc ids
        """
        from beehive_resource.plugins.provider.entity.security_group import SecurityGroup

        security_groups = []
        sgs, tot = self.container.get_resources(parent_list=vpc_ids, authorize=False, run_customize=False,
                                                type=SecurityGroup.objdef)
        if tot == 0:
            raise ApiManagerError('no default security group found in compute zone %s' % self.oid)

        for sg in sgs:
            sg.check_active()
            security_groups.append(sg)
        self.logger.debug('get default compute zone %s security groups: %s' % (self.oid, truncate(security_groups)))
        return security_groups

    def get_network_appliance_helper(self, orchestrator_type, controller, site):
        """Return orchestrator helper.

        :param orchestrator_type: type of orchestrator like vsphere, opnsense, haproxy, etc.
        :param controller:
        :param site:
        :return: helper instance
        """
        from beehive_resource.plugins.provider.helper.network_appliance.load_balancer import ProviderVsphereHelper, \
            ProviderOPNsenseHelper, ProviderHAproxyHelper

        helpers = {
            'vsphere': ProviderVsphereHelper,
            'opnsense': ProviderOPNsenseHelper,
            'haproxy': ProviderHAproxyHelper,
        }
        helper = helpers.get(orchestrator_type, None)
        if helper is None:
            raise ApiManagerError('Network appliance helper for orchestrator %s does not exist' % orchestrator_type)

        orchestrator_idx = site.get_orchestrators(select_types=[orchestrator_type])
        orchestrator = list(orchestrator_idx.values())[0]
        self.logger.warning('____orchestrator={}'.format(orchestrator))

        return helper(controller=controller, orchestrator=orchestrator, compute_zone=self)

    #
    # backup
    #
    # @trace(op='view')
    # def __get_backups_physical_instance(self, instances):
    #     """Get physical backup info for instance (aka virtual machine)
    #
    #     :param instances: list of instance
    #     """
    #     bck_jobs = []
    #     for instance in instances:
    #
    #
    #
    # @trace(op='view')
    # def get_backups(self):
    #     """Get backup info
    #     """
    #     # verify permissions
    #     self.verify_permisssions('use')
    #
    #     quotas = self.quotas.get()
    #     allocated = self.get_quotas_allocated()
    #     for item in quotas:
    #         item['allocated'] = allocated.get(item['quota'])
    #     res = sorted(quotas, key=lambda k: k['quota'])
    #     self.logger.debug('Get quotas allocated: %s' % res)
    #     return res

    #
    # quotas
    #
    @trace(op='update')
    def set_quotas(self, *args, **kvargs):
        """Set quotas

        :param quotas: list of quotas like:
        :param orchestrator_tag: remote orchestrator tag
        :param kvargs.quotas:
        :param kvargs.compute.instances: 2
        :param kvargs.compute.images: 2
        :param kvargs.compute.volumes: 2
        :param kvargs.compute.blocks: 1024
        :param kvargs.compute.ram: 10
        :param kvargs.compute.cores: 4
        :param kvargs.compute.networks: 2
        :param kvargs.compute.floatingips: 2
        :param kvargs.compute.security_groups: 2
        :param kvargs.compute.security_group_rules: 10
        :param kvargs.compute.keypairs: 2
        :param kvargs.database.instances: 2
        :param kvargs.share.instances: 2
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        """
        zones = self.get_availability_zones()
        kvargs['availability_zones'] = [z.oid for z in zones]

        quotas = self.quotas.get_simple()
        quotas.update(kvargs['quotas'])
        kvargs['quotas'] = quotas
        # kvargs['sync'] = True

        tasks = [self.task_path + 'compute_zone_set_quotas_step']
        res = self.action('set_quota', tasks, log='Set compute zone quotas', *args, **kvargs)
        return res

    @trace(op='view')
    def get_quotas(self):
        """Get quotas
        """
        # verify permissions
        self.verify_permisssions('use')

        quotas = self.quotas.get()
        allocated = self.get_quotas_allocated()
        for item in quotas:
            item['allocated'] = allocated.get(item['quota'])
        res = sorted(quotas, key=lambda k: k['quota'])
        self.logger.debug('Get quotas allocated: %s' % res)
        return res

    @trace(op='view')
    def get_quotas_allocated(self):
        """Get quotas allocated
        """
        from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2
        from beehive_resource.plugins.provider.entity.stack import ComputeStack
        from beehive_resource.plugins.provider.entity.image import ComputeImage
        from beehive_resource.plugins.provider.entity.instance import ComputeInstance
        from beehive_resource.plugins.provider.entity.volume import ComputeVolume
        from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc
        from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
        from beehive_resource.plugins.provider.entity.share import ComputeFileShare
        from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
        from beehive_resource.plugins.provider.entity.monitoring_folder import ComputeMonitoringFolder

        # verify permissions
        self.verify_permisssions('use')

        quotas = {}
        for key in list(self.quotas.classes.keys()):
            quotas[key] = 0

        entity_classes = [
            (ComputeInstance, True),
            (Vpc, False),
            (ComputeImage, False),
            (ComputeVolume, True),
            (ComputeStack, True),
            (ComputeStackV2, False),
            (ComputeFileShare, False),
            (ComputeLoggingSpace, False),
            (ComputeMonitoringFolder, False),
        ]
        for entity_class, run_customize in entity_classes:
            childs, total = self.container.get_resources(parent_id=self.oid, authorize=False, size=-1,
                                                         run_customize=run_customize, type=entity_class.objdef)
            for item in childs:
                # if resource quotas must not be calculated bypass resource
                computeProviderResource: ComputeProviderResource = item
                if computeProviderResource.has_quotas() is False:
                    continue
                item_quotas = computeProviderResource.get_quotas()

                if isinstance(item, ComputeInstance):
                    computeInstance: ComputeInstance = item
                    if computeInstance.is_monitoring_enabled():
                        quotas['monitoring.instances'] += 1

                    if computeInstance.is_logging_enabled():
                        quotas['logging.instances'] += 1

                    quotas['compute.volumes'] += item_quotas.get('compute.volumes')
                    quotas['compute.blocks'] += item_quotas.get('compute.blocks')
                    quotas['compute.instances'] += item_quotas.get('compute.instances')
                    quotas['compute.cores'] += item_quotas.get('compute.cores')
                    quotas['compute.ram'] += item_quotas.get('compute.ram')

                elif isinstance(item, Vpc):
                    quotas['compute.networks'] += 1

                    # append child security_group
                    sgs, total = self.container.get_resources(parent_id=item.oid, authorize=False, size=-1,
                                                              run_customize=False, type=SecurityGroup.objdef)
                    quotas['compute.security_groups'] += total

                elif isinstance(item, ComputeImage):
                    quotas['compute.images'] += 1

                elif isinstance(item, ComputeVolume):
                    quotas['compute.volumes'] += item_quotas.get('compute.volumes')
                    quotas['compute.snapshots'] += item_quotas.get('compute.snapshots')
                    quotas['compute.blocks'] += item_quotas.get('compute.blocks')

                elif isinstance(item, ComputeStackV2):
                    stack_type = item.get_attribs(key='stack_type')
                    if stack_type == 'sql_stack':
                        for k, v in item_quotas.items():
                            quotas['database.%s' % k] += v

                elif isinstance(item, ComputeStack):
                    stack_type = item.get_attribs(key='stack_type')
                    if stack_type == 'sql_stack':
                        for k, v in item_quotas.items():
                            quotas['database.%s' % k] += v
                    elif stack_type == 'app_engine':
                        for k, v in item_quotas.items():
                            quotas['appengine.%s' % k] += v

                elif isinstance(item, ComputeFileShare):
                    for k, v in item_quotas.items():
                        quotas['share.%s' % k] += v

                elif isinstance(item, ComputeLoggingSpace):
                    quotas['logging.spaces'] += item_quotas.get('logging.spaces')

                elif isinstance(item, ComputeMonitoringFolder):
                    quotas['monitoring.folders'] += item_quotas.get('monitoring.folders')

        quotas['compute.ram'] = float(quotas['compute.ram']) / 1024

        #     elif isinstance(item, ComputeVolume):
        #         quotas['compute.volumes'] += item_quotas.get('compute.volumes')
        #         quotas['compute.snapshots'] += item_quotas.get('compute.snapshots')
        #         quotas['compute.blocks'] += item_quotas.get('compute.blocks')
        #     elif isinstance(item, ComputeStack):
        #         stack_type = item.get_attribs(key='stack_type')
        #         if stack_type == 'sql_stack':
        #             for k, v in item_quotas.items():
        #                 quotas['database.%s' % k] += v
        #         elif stack_type == 'app_engine':
        #             for k, v in item_quotas.items():
        #                 quotas['appengine.%s' % k] += v
        #     # todo: count share
        #
        # quotas['compute.ram'] = float(quotas['compute.ram']) / 1024

        self.logger.debug('Get quotas allocated: %s' % quotas)
        return quotas

    def check_quotas(self, quotas):
        """Check quotas

        :param quotas: new quotas to allocate
        """
        # verify permissions
        self.verify_permisssions('use')

        res = self.quotas.check_availability(self.get_quotas_allocated(), quotas)
        self.logger.debug('Check new quotas %s: %s' % (quotas, res))
        return res

    #
    # backup job
    #
    def __get_backup_job(self, job_id, hypervisor_tag='default'):
        """get backup job list

        :param job_id: job id
        :param hypervisor_tag: hypervisor tag default='default'
        :return: (resource_type, site, hypervisor, hypervisor_tag, workload)
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        hypervisor = None
        resource_type = None
        workloads = []
        avzs = self.get_availability_zones()
        for avz in avzs:
            site = avz.get_site()
            project = avz.get_openstack_project(hypervisor_tag)
            workloads.extend([(w, site) for w in project.get_backup_jobs() if w['id'] == job_id])
            hypervisor = 'openstack'
            resource_type = 'ComputeInstance'

        if len(workloads) == 0:
            raise ApiManagerError('no backup job found for id %s' % job_id)
        workload = workloads[0]
        return resource_type, workload[1], hypervisor, hypervisor_tag, workload[0]

    def exist_backup_job(self, avz, hypervisor, resource_type, job_id=None, job_name=None):
        """check if backup job exist

        :param avz: availability zone
        :param hypervisor: hypervisor
        :param resource_type: backup resource type
        :param job_id: job id [optional]
        :param job_name: job name [optional]
        :return: job
        :raise ApiManagerError:
        """
        if resource_type == 'ComputeInstance':
            if hypervisor == 'openstack':
                project = avz.get_openstack_project('default')
                jobs = project.get_backup_jobs()
                res = None
                self.logger.debug('+++++ exist_backup_job new - id: %s - name: %s' % (job_id, job_name))
                for job in jobs:
                    self.logger.debug('+++++ exist_backup_job exist - id: %s - name: %s' % (job['id'], job['name']))
                    if job_id is not None and job['id'] == job_id:
                        res = job
                    elif job_name is not None and job['name'] == job_name:
                        res = job
                return res
            else:
                raise ApiManagerError('hypervisor %s is not supported in backup operations' % hypervisor)
        else:
            raise ApiManagerError('resource type %s is not supported in backup operations' % resource_type)

    @trace(op='use')
    def get_backup_jobs(self, hypervisor_tag='default'):
        """get backup job list

        :param hypervisor_tag: hypervisor tag default='default'
        :return: backup jobs list
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        jobs = []
        avzs = self.get_availability_zones()
        for avz in avzs:
            availabilityZone: AvailabilityZone = avz
            site = avz.get_site()
            from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
            project: OpenstackProject = availabilityZone.get_openstack_project(hypervisor_tag)
            workloads = project.get_backup_jobs()

            for workload in workloads:
                job = {
                    'hypervisor': 'openstack',
                    'site': site.name,
                    'resource_type': 'ComputeInstance',
                    'id':  workload.get('id'),
                    'name': workload.get('name'),
                    'created': workload.get('created_at'),
                    'updated': workload.get('updated_at'),
                    'error': workload.get('error_msg'),
                    'usage': dict_get(workload, 'storage_usage.usage'),
                    'schedule': dict_get(workload, 'jobschedule'),
                    'status': workload.get('status'),
                    'type': workload.get('workload_type_id'),
                    'instances': len(workload.get('instances'))
                }
                jobs.append(job)

        return jobs

    @trace(op='use')
    def get_backup_job(self, job_id, hypervisor_tag='default', resource_type=None):
        """get backup job list

        :param job_id: job id
        :param hypervisor_tag: hypervisor tag [default='default']
        :param resource_type: resource type [optional]
        :return: backup jobs list
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        workloads = []
        avzs = self.get_availability_zones()
        for avz in avzs:
            site = avz.get_site()
            if resource_type is None or resource_type == 'ComputeInstance':
                from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
                project: OpenstackProject = avz.get_openstack_project(hypervisor_tag)
                for w in project.get_backup_jobs():
                    if w['id'] == job_id:
                        w['site'] = site
                        workloads.append(w)

        if len(workloads) == 0:
            raise ApiManagerError('no backup job found for id %s' % job_id)
        workload = workloads[0]

        instances = []
        for wrkl_instance in workload.get('instances'):
            entity = self.controller.get_resource_by_extid(wrkl_instance['id'])
            if entity is None:
                self.logger.warning('workload instance not found - job_id: %s - id: %s' % (job_id, wrkl_instance['id']))
            else:
                resource_id = entity.oid
                instance = self.container.get_aggregated_resource_from_physical_resource(resource_id)
                instances.append(instance.small_info())

        job = {
            'hypervisor': 'openstack',
            'site': workload.get('site').name,
            'resource_type': 'ComputeInstance',
            'id':  workload.get('id'),
            'name': workload.get('name'),
            'desc': workload.get('description'),
            'created': workload.get('created_at'),
            'updated': workload.get('updated_at'),
            'error': workload.get('error_msg'),
            'usage': dict_get(workload, 'storage_usage.usage'),
            'schedule': dict_get(workload, 'jobschedule'),
            'status': workload.get('status'),
            'type': workload.get('workload_type_id'),
            'instances': instances
        }

        return job

    @trace(op='update')
    def create_backup_job(self, name, desc, site, hypervisor='openstack', resource_type='ComputeInstance', instances=None,
                          fullbackup_interval=2, start_date=None, end_date=None, start_time='0:00 AM', interval='24hrs',
                          restore_points=4, timezone='Europe/Rome', hypervisor_tag='default', job_type='Parallel'):
        """Create backup job

        :param name: workload name
        :param site: site id
        :param fullbackup_interval: workload interval between full backup
        :param start_date: workload start date
        :param end_date: workload end date
        :param start_time: workload start time
        :param interval: workload interval
        :param restore_points: number of restore points to retain
        :param timezone: workload timezone
        :param job_type: workload job type. Can be Serial or Parallel
        :param hypervisor: hypervisor. Can be Parallel, Serial
        :param hypervisor_tag: hypervisor tag default='default'
        :param resource_type: backup resource type. ComputeInstance
        :param instances: list of instance ids of type resource_type
        :return: job id
        :raise ApiManagerError:
        """
        self.verify_permisssions('update')

        site = self.controller.get_simple_resource(site).oid
        avz = self.get_availability_zone(site)

        newJobName = (self.BCK_WORKLOAD_PREFIX + '%s') % name.upper() # naming convention
        workload = self.exist_backup_job(avz, hypervisor, resource_type, job_id=None, job_name=newJobName)
        if workload is not None:
            raise ApiManagerError('backup job %s already exist' % name)

        if resource_type == 'ComputeInstance':
            if hypervisor not in ['openstack']:
                raise ApiManagerError('hypervisor %s is not supported for backup operations' % hypervisor)

            if hypervisor == 'openstack':
                name = (self.BCK_WORKLOAD_PREFIX + '%s') % name.upper() # naming convention
                if desc is None:
                    desc = name
                metadata = {}
                if start_date is None:
                    now = datetime.today()
                    start_date = '%s/%s/%s' % (now.day, now.month, now.year)

                # get instances
                servers = []
                if instances is None:
                    raise ApiManagerError('no backup instances configured')
                for instance_id in instances:
                    instance = self.controller.get_resource(instance_id)
                    from .instance import ComputeInstance
                    if not isinstance(instance, ComputeInstance):
                        raise ApiManagerError('instance %s is not of type %s' % (instance.oid, resource_type))
                    servers.append(instance.get_physical_server().ext_id)

                from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
                project: OpenstackProject = avz.get_openstack_project(hypervisor_tag)
                job = project.create_backup_job(name, servers, metadata=metadata, desc=desc,
                                                fullbackup_interval=fullbackup_interval, start_date=start_date,
                                                end_date=end_date, start_time=start_time, interval=interval,
                                                snapshots_to_retain=restore_points, timezone=timezone,
                                                job_type=job_type)
                self.logger.debug('create backup job %s' % job['id'])
        else:
            raise ApiManagerError('resource type %s is not supported for backup operations' % resource_type)
        return job['id']

    @trace(op='update')
    def update_backup_job(self, job_id, name=None, instances=None, desc=None, fullbackup_interval=None,
                          start_date=None, end_date=None, start_time=None, interval=None, restore_points=None,
                          timezone=None, enabled=None, hypervisor_tag='default'):
        """Update backup job

        :param job_id: backup job id
        :param name: workload name
        :param instances: list of instance ids of type resource_type
        :param fullbackup_interval: workload interval between full backup
        :param start_date: workload start date
        :param end_date: workload end date
        :param start_time: workload start time
        :param interval: workload interval
        :param restore_points: number of restore points to retain
        :param timezone: workload timezone
        :param hypervisor: hypervisor. Can be Parallel, Serial
        :param hypervisor_tag: hypervisor tag default='default'
        :param resource_type: backup resource type. ComputeInstance
        :param enabled: workload enable state
        :return: job id
        :raise ApiManagerError:
        """
        self.verify_permisssions('update')

        resource_type, site, hypervisor, hypervisor_tag, job = self.__get_backup_job(
            job_id, hypervisor_tag=hypervisor_tag)
        avz = self.get_availability_zone(site.oid)

        if resource_type == 'ComputeInstance':
            if hypervisor not in ['openstack']:
                raise ApiManagerError('hypervisor %s is not supported for backup operations' % hypervisor)

            if hypervisor == 'openstack':
                if name is not None:
                    name = (self.BCK_WORKLOAD_PREFIX + '%s') % name.upper()

                # new servers list
                if instances is None:
                    servers = None
                else:
                    # get actual servers
                    servers = [i['id'] for i in job['instances']]
                    for instance in instances:
                        instance_resource = self.controller.get_resource(instance['instance'])
                        from .instance import ComputeInstance
                        if not isinstance(instance_resource, ComputeInstance):
                            raise ApiManagerError('instance %s is not of type %s' %
                                                  (instance_resource.oid, resource_type))
                        new_server = instance_resource.get_physical_server().ext_id
                        action = instance['action']
                        if action == 'add' and new_server not in servers:
                            servers.append(new_server)
                        elif action == 'del' and new_server in servers:
                            servers.remove(new_server)

                project = avz.get_openstack_project(hypervisor_tag)
                project.update_backup_job(job_id, name=name, instances=servers, metadata=None, desc=desc,
                                          fullbackup_interval=fullbackup_interval, start_date=start_date,
                                          end_date=end_date, start_time=start_time, interval=interval,
                                          snapshots_to_retain=restore_points, timezone=timezone,
                                          enabled=enabled)
                self.logger.debug('update backup job %s' % job_id)
        else:
            raise ApiManagerError('resource type %s is not supported for backup operations' % resource_type)
        return job_id

    @trace(op='update')
    def delete_backup_job(self, job_id, hypervisor_tag='default'):
        """Delete backup job

        :param job_id: backup job id
        :param hypervisor_tag: hypervisor tag default='default'
        :return: job id
        :raise ApiManagerError:
        """
        self.verify_permisssions('update')

        resource_type, site, hypervisor, hypervisor_tag, job = self.__get_backup_job(
            job_id, hypervisor_tag=hypervisor_tag)
        avz = self.get_availability_zone(site.oid)

        # site = self.controller.get_simple_resource(site).oid
        # avz = self.get_availability_zone(site)
        #
        # workload = self.exist_backup_job(avz, hypervisor, resource_type, job_id=job_id, job_name=None)
        # if workload is None:
        #     raise ApiManagerError('backup job %s does not exist' % job_id)

        if resource_type == 'ComputeInstance':
            if hypervisor not in ['openstack']:
                raise ApiManagerError('hypervisor %s is not supported for backup operations' % hypervisor)

            if hypervisor == 'openstack':
                project = avz.get_openstack_project(hypervisor_tag)
                project.delete_backup_job(job_id)
                self.logger.debug('delete backup job %s' % job_id)
        else:
            raise ApiManagerError('resource type %s is not supported for backup operations' % resource_type)
        return job_id

    #
    # backup job restore point
    #
    @trace(op='use')
    def get_backup_restore_points(self, job_id, restore_point_id=None, hypervisor_tag='default'):
        """get backup job restore points list

        :param job_id: job id
        :param hypervisor_tag: hypervisor tag default='default'
        :return: (resource_type, site, hypervisor, hypervisor_tag, workload)
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        resource_type, site, hypervisor, hypervisor_tag, job = self.__get_backup_job(
            job_id, hypervisor_tag=hypervisor_tag)
        avz = self.get_availability_zone(site.oid)

        restore_points = []
        if resource_type == 'ComputeInstance':
            if hypervisor not in ['openstack']:
                raise ApiManagerError('hypervisor %s is not supported for backup operations' % hypervisor)

            if hypervisor == 'openstack':
                project = avz.get_openstack_project(hypervisor_tag)
                if restore_point_id is None:
                    restore_points = project.get_backup_restore_points(job_id)
                else:
                    restore_points = [project.get_backup_restore_point(restore_point_id)]
                for r in restore_points:
                    restore_point_instances = r.get('instances', None)
                    if restore_point_instances is not None:
                        instances = []
                        for restore_point_instance in restore_point_instances:
                            resource_id = self.controller.get_resource_by_extid(restore_point_instance['id']).oid
                            instance = self.container.get_aggregated_resource_from_physical_resource(resource_id)
                            instances.append(instance.small_info())
                        r['instances'] = instances

                    r.update({
                        'hypervisor': hypervisor,
                        'site': site.name,
                        'resource_type': resource_type,
                    })

        self.logger.debug('get compute zone %s backup job %s restore points: %s' %
                          (self.oid, job_id, truncate(restore_points)))
        return restore_points

    @trace(op='update')
    def create_backup_restore_point(self, job_id, name, desc=None, full=True, hypervisor_tag='default'):
        """Create backup job restore point

        :param job_id: job id
        :param name: restore point name
        :param desc: restore point description [optional]
        :param full: if True create a full restore point type, otherwise crate an incremental
        :param hypervisor_tag: hypervisor tag default='default'
        :return: {'taskid': .., 'uuid': ..}
        :raise ApiManagerError:
        """
        self.verify_permisssions('update')

        resource_type, site, hypervisor, hypervisor_tag, job = self.__get_backup_job(
            job_id, hypervisor_tag=hypervisor_tag)
        avz = self.get_availability_zone(site.oid)

        res = None
        if resource_type == 'ComputeInstance':
            if hypervisor == 'openstack':
                project = avz.get_openstack_project(hypervisor_tag)
                res = project.add_backup_restore_point(restore_point_job_id=job_id, restore_point_name=name,
                                                       restore_point_desc=desc, restore_point_full=full)
            else:
                raise ApiManagerError('backup hypervisor not supported')
        else:
            raise ApiManagerError('backup resource type not supported')

        return res

    @trace(op='update')
    def delete_backup_restore_point(self, job_id, restore_point_id, hypervisor_tag='default'):
        """Delete backup job

        :param job_id: job id
        :param restore_point_id: restore point id
        :param hypervisor_tag: hypervisor tag default='default'
        :return: {'taskid': .., 'uuid': ..}
        :raise ApiManagerError:
        """
        self.verify_permisssions('update')

        resource_type, site, hypervisor, hypervisor_tag, job = self.__get_backup_job(
            job_id, hypervisor_tag=hypervisor_tag)
        avz = self.get_availability_zone(site.oid)

        res = None
        if resource_type == 'ComputeInstance':
            if hypervisor == 'openstack':
                project = avz.get_openstack_project(hypervisor_tag)
                try:
                    project.get_backup_restore_point(restore_point_id)
                except:
                    raise ApiManagerError('backup restore point %s does not exists' % restore_point_id)
                res = project.del_backup_restore_point(restore_point_job_id=job_id, restore_point_id=restore_point_id)
            else:
                raise ApiManagerError('backup hypervisor not supported')
        else:
            raise ApiManagerError('backup resource type not supported')

        return res

    #
    # metrics
    #
    def get_metrics(self):
        """Get metrics

        :return: list of dict

            [{
                "id": "1",
                "uuid": "vm1",
                "metrics": [
                    {
                        "key": "ram",
                        "value: 10,
                        "unit": 1
                    }],
                "extraction_date": "2018-03-04 12:00:34 200",
                "resource_uuid": "12u956-2425234-23654573467-567876"

            }.. ]
        """
        # verify permissions
        self.verify_permisssions('use')

        res = []
        from .instance import ComputeInstance
        from .stack import ComputeStack
        from .stack_v2 import ComputeStackV2
        from .share import ComputeFileShare
        from .volume import ComputeVolume
        from beehive_resource.plugins.provider.entity.logging_space import ComputeLoggingSpace
        from beehive_resource.plugins.provider.entity.monitoring_folder import ComputeMonitoringFolder
        #from .elasticip import ComputeElasticIp
        entity_classes = [
            (ComputeInstance, True),
            (ComputeFileShare, False),
            (ComputeStack, True),
            (ComputeStackV2, False),
            (ComputeVolume, False),
            # (ComputeLoggingSpace, False),
            # (ComputeMonitoringFolder, False),
            # (ComputeElasticIp, False),
        ]
        ttl = 86400
        zone_metric_vm_bck = 0

        for entity_class, run_customize in entity_classes:
            # self.logger.debug('+++++ get_metrics - entity_class: %s' % (entity_class))
            childs, total = self.container.get_resources(parent_id=self.oid, with_perm_tag=False, size=-1,
                                                         run_customize=False, type=entity_class.objdef)

            for item in childs:
                # if resource quotas must not be calculated bypass resource
                if item.has_quotas() is False:
                    # self.logger.debug('+++++ get_metrics - has no quotas: {}'.format(item))
                    continue

                # get item metrics
                if item.state == 2 or item.state == 3:
                    internalkey = 'metrics.%s' % item.oid
                    metrics = self.controller.cache.get(internalkey)
                    # self.logger.debug('+++++ get_metrics - metrics {}'.format(metrics))
                    # operation.cache = False   # scommentare per test da cli
                    if operation.cache is False or metrics is None or metrics == {} or metrics == []:
                        # get data
                        # self.logger.debug('+++++ get_metrics - get data')
                        if run_customize is True:
                            item.post_get()
                        metrics = item.get_metrics()
                        # save data in cache
                        self.controller.cache.set(internalkey, metrics, ttl=ttl)
                    else:
                        # extend key time
                        # self.logger.debug('+++++ get_metrics - extend key time')
                        self.controller.cache.expire(internalkey, ttl)

                    if metrics is not None and metrics != {}:
                        res.append(metrics)
                        self.logger.warn(metrics)

                # if isinstance(item, ComputeInstance):
                #     backup_status = item.get_physical_backup()
                #     zone_metric_vm_bck += backup_status.get('usage', 0)

        # get backup metrics
        # avzs = self.get_availability_zones()
        # for avz in avzs:
        #     site = avz.get_site()

        #     from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
        #     project: OpenstackProject = avz.get_openstack_project('default')
        #     workloads = project.get_backup_jobs()

        #     for workload in workloads:
        #         zone_metric_vm_bck += dict_get(workload, 'storage_usage.usage')

        # zone_metric_data = {
        #     'id': self.oid,
        #     'uuid': self.uuid,
        #     'resource_uuid': self.uuid,
        #     'type': self.objdef,
        #     'metrics': [
        #         {'key': 'vm_bck_os', 'value': round(zone_metric_vm_bck / 1073741824, 2), 'type': 1, 'unit': 'GB'}
        #     ],
        #     'extraction_date': format_date(datetime.today())
        # }
        # res.append(zone_metric_data)

        self.logger.debug('Get compute zone %s metrics: %s' % (self.uuid, truncate(res)))
        return res

    #
    # childs
    #
    def get_childs(self):
        """Get childs

        :return: list of resources
        """
        # verify permissions
        self.verify_permisssions('use')

        childs, total = self.get_resources(size=-1)
        sgs, total = self.get_linked_resources(link_type='sg')
        childs.extend(sgs)

        self.logger.debug('Get compute zone %s childs: %s' % (self.uuid, truncate(childs)))
        return childs


class AvailabilityZone(SiteChildResource):
    """AvailabilityZone
    """
    objdef = 'Provider.Region.Site.AvailabilityZone'
    objuri = '%s/availability_zones/%s'
    objname = 'availability_zone'
    objdesc = 'Provider Availability Zone'
    task_path = 'beehive_resource.plugins.provider.task_v2.zone.ZoneTask.'

    def __init__(self, *args, **kvargs):
        SiteChildResource.__init__(self, *args, **kvargs)

        self.site = None
        self.region = None

        from beehive_resource.plugins.provider.entity.flavor import Flavor
        from beehive_resource.plugins.provider.entity.image import Image
        from beehive_resource.plugins.provider.entity.instance import Instance
        from beehive_resource.plugins.provider.entity.rule import Rule
        from beehive_resource.plugins.provider.entity.security_group import RuleGroup
        from beehive_resource.plugins.provider.entity.share import FileShare
        from beehive_resource.plugins.provider.entity.stack import Stack
        from beehive_resource.plugins.provider.entity.vpc_v2 import PrivateNetwork
        from beehive_resource.plugins.provider.entity.volume import Volume
        from beehive_resource.plugins.provider.entity.volumeflavor import VolumeFlavor
        from beehive_resource.plugins.provider.entity.gateway import Gateway
        from beehive_resource.plugins.provider.entity.customization import Customization
        from beehive_resource.plugins.provider.entity.applied_customization import AppliedCustomization
        from beehive_resource.plugins.provider.entity.logging_space import LoggingSpace
        from beehive_resource.plugins.provider.entity.monitoring_folder import MonitoringFolder
        from beehive_resource.plugins.provider.entity.load_balancer import LoadBalancer

        self.child_classes = [
            PrivateNetwork,
            RuleGroup,
            Rule,
            Instance,
            Flavor,
            Volume,
            VolumeFlavor,
            Image,
            Stack,
            FileShare,
            Gateway,
            Customization,
            AppliedCustomization,
            LoggingSpace,
            MonitoringFolder,
            LoadBalancer,
        ]

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        info.pop('attributes')
        info['site'] = {}
        info['region'] = {}
        if self.site is not None:
            info['site'] = self.site.small_info()
        if self.region is not None:
            info['region'] = self.region.small_info()

        info['orchestrator'] = {}
        for o in self.get_orchestrators().values():
            host_group = None
            if o['type'] == 'vsphere':
                host_group = dict_get(o, 'config.clusters')
                if host_group is not None:
                    host_group = list(host_group.keys())
            orch = {
                'id': o['id'],
                'type': o['type'],
                'host_group': host_group
            }
            try:
                info['orchestrator'][o['tag']].append(orch)
            except:
                info['orchestrator'][o['tag']] = [orch]

        return info

    #
    # quotas
    #
    @trace(op='update')
    def set_quotas(self, *args, **kvargs):
        """Set quotas

        :param quotas: list of quotas like:
        :param orchestrator_tag: remote orchestrator tag
        :param quotas.compute.instances: 2
        :param quotas.compute.images: 2
        :param quotas.compute.volumes: 2
        :param quotas.compute.blocks: 1024
        :param quotas.compute.ram: 10
        :param quotas.compute.cores: 4
        :param quotas.compute.networks: 2
        :param quotas.compute.floatingips: 2
        :param quotas.compute.security_groups: 2
        :param quotas.compute.security_group_rules: 10
        :param quotas.compute.keypairs: 2
        :param quotas.database.instances: 2
        :param quotas.share.instances: 2
        :return: {'jobid':..}, 202
        :raise ApiManagerError:
        """
        orchestrator_idx = self.get_orchestrators_by_tag(kvargs.get('orchestrator_tag'))

        steps = [
            AvailabilityZone.task_path + 'availability_zone_set_quotas_step',
        ]

        for item in list(orchestrator_idx.values()):
            subtask = {
                'step': AvailabilityZone.task_path + 'availability_zone_set_orchestrator_quotas_step',
                'args': [item]
            }
            steps.append(subtask)

        kvargs['sync'] = True
        # kvargs['alias'] = '%s.set_quota' % self.name
        kvargs['alias'] = '%s.set_quota' % self.__class__.__name__
        res = self.action('set_quota', steps, log='Set availability zone quotas', *args, **kvargs)
        return res

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.site: site id
        :param kvargs.zone: super zone id
        :param kvargs.orchestrator_tag: remote orchestrator tag
        :param kvargs.quota: quota
        :param kvargs.quota.compute.instances: 2
        :param kvargs.quota.compute.images: 2
        :param kvargs.quota.compute.volumes: 2
        :param kvargs.quota.compute.blocks: 1024
        :param kvargs.quota.compute.ram: 10
        :param kvargs.quota.compute.cores: 4
        :param kvargs.quota.compute.networks: 2
        :param kvargs.quota.compute.floatingips: 2
        :param kvargs.quota.compute.security_groups: 2
        :param kvargs.quota.compute.security_group_rules: 10
        :param kvargs.quota.compute.keypairs: 2
        :param kvargs.quota.database.instances: 2
        :param kvargs.quota.share.instances: 2
        :return: {}
        :raise ApiManagerError:
        """
        quota = kvargs.get('quota')
        orchestrator_tag = kvargs.get('orchestrator_tag')
        site_id = kvargs.get('site')

        # get site
        site = container.get_simple_resource(site_id)

        # verify quota
        # site.check_quotas_availability(quota)

        # select remote orchestrators
        orchestrator_idx = site.get_orchestrators_by_tag(orchestrator_tag)
        kvargs['orchestrators'] = orchestrator_idx

        params = {
            'attribute': {
                'quota': quota,
                'configs': {}
            }
        }
        kvargs.update(params)

        steps = [
            AvailabilityZone.task_path + 'create_resource_pre_step',
            AvailabilityZone.task_path + 'availability_zone_link_resource_step',
        ]

        for item in list(orchestrator_idx.values()):
            substep = {
                'step': AvailabilityZone.task_path + 'availability_zone_create_orchestrator_resource_step',
                'args': [str(item['id'])]
            }
            steps.append(substep)

        steps.append(AvailabilityZone.task_path + 'create_resource_post_step')
        kvargs['steps'] = steps

        return kvargs

    def group_remove_step(self, orchestrators):
        """Create group of step used to remove resource

        :param childs: list of childs to remove
        :return: list of steps
        """
        run_steps = [
            self.task_path + 'expunge_resource_pre_step',
            self.task_path + 'remove_applied_customization_step'
        ]

        for item in orchestrators.values():
            substep = {
                'step': self.task_path + 'remove_physical_resource_step',
                'args': [str(item['id']), item['type']]
            }
            run_steps.append(substep)
        run_steps.append(self.task_path + 'expunge_resource_post_step')
        return run_steps

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param kvargs.args: custom params
        :param kvargs.kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        self.logger.warn(kvargs['child_num'])

        from .applied_customization import AppliedCustomization
        appcusts, tot = self.get_resources(entity_class=AppliedCustomization)
        kvargs['child_num'] -= tot

        self.logger.warn(kvargs['child_num'])

        # select physical orchestrators
        orchestrator_idx = self.get_orchestrators()
        kvargs['steps'] = self.group_remove_step(orchestrator_idx)
        kvargs['sync'] = True
        return kvargs

    def get_site(self):
        """Get availability zone site
        """
        oid = self.parent_id
        try:
            entity = self.manager.get_entity(ModelResource, oid)
        except QueryError as ex:
            self.logger.error(ex, exc_info=1)
            raise ApiManagerError('%s %s not found or name is not unique' % ('Site', oid), code=400)

        if entity is None:
            self.logger.warn('%s %s not found' % ('Site', oid))
            raise ApiManagerError('%s %s not found' % ('Site', oid), code=404)

        res = Site(self.controller, oid=entity.id, objid=entity.objid, name=entity.name, active=entity.active,
                   desc=entity.desc, model=entity)
        res.set_container(self.container)

        res.state = self.state
        return res

    def get_openstack_project(self, orchestrator_tag):
        from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
        orchestrator_idx = self.get_orchestrators_by_tag(orchestrator_tag, select_types=['openstack'])
        res = self.get_physical_resource_from_container(list(orchestrator_idx.keys())[0], OpenstackProject.objdef)
        return res

    def get_vsphere_folder(self, orchestrator_tag):
        from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
        orchestrator_idx = self.get_orchestrators_by_tag(orchestrator_tag, select_types=['vsphere'])
        res = self.get_physical_resource_from_container(list(orchestrator_idx.keys())[0], VsphereFolder.objdef)
        return res


class AvailabilityZoneChildResource(SiteChildResource):
    """AvailabilityZoneChildResource
    """
    objdef = 'Provider.Region.Site.AvailabilityZone.Resource'
    objuri = '%s/resources/%s'
    objname = 'availability_zone_resource'
    objdesc = 'Provider Availability Zone resource'

    def __init__(self, *args, **kvargs):
        SiteChildResource.__init__(self, *args, **kvargs)

        self.zone = self.parent_id

    def get_availability_zone(self):
        """Get availability zone
        """
        oid = self.parent_id
        try:
            entity = self.manager.get_entity(ModelResource, oid)
        except QueryError as ex:
            self.logger.error(ex, exc_info=1)
            raise ApiManagerError('%s %s not found or name is not unique' % ('AvailabilityZone', oid), code=400)

        if entity is None:
            self.logger.warn('%s %s not found' % ('AvailabilityZone', oid))
            raise ApiManagerError('%s %s not found' % ('AvailabilityZone', oid), code=404)

        res = AvailabilityZone(self.controller, oid=entity.id, objid=entity.objid, name=entity.name,
                               active=entity.active, desc=entity.desc, model=entity)
        return res

    def get_site(self):
        """Get availability zone site
        """
        avz = self.get_availability_zone()
        site = avz.get_site()
        site.state = avz.state
        return site

    def get_orchestrator_helper(self, orchestrator_type, orchestrator, resource):
        """Return orchestrator helper

        :param orchestrator_type: type of orchestrator like vsphere or openstack
        :param orchestrator: orchestrator config
        :param resource: resource reference
        :return: orchestrator helper
        """
        from beehive_resource.plugins.provider.task_v2.openstack import ProviderOpenstack
        from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere
        from beehive_resource.plugins.provider.task_v2.ontap import ProviderNetappOntap
        from beehive_resource.plugins.provider.task_v2.awx import ProviderAwx
        from beehive_resource.plugins.provider.task_v2.elk import ProviderElk
        from beehive_resource.plugins.provider.task_v2.grafana import ProviderGrafana
        helpers = {
            'vsphere': ProviderVsphere,
            'openstack': ProviderOpenstack,
            'ontap': ProviderNetappOntap,
            'awx': ProviderAwx,
            'elk': ProviderElk,
            'grafana': ProviderGrafana,
        }
        helper = helpers.get(orchestrator_type, None)
        if helper is None:
            raise ApiManagerError('Helper for orchestrator %s does not exist' % orchestrator_type)

        res = helper(None, None, orchestrator, resource, controller=self.controller)
        return res
