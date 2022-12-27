# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beecell.db import QueryError
from beecell.types.type_dict import dict_get, dict_set
from beecell.simple import get_value
from beehive.common.apimanager import ApiManagerError
from beehive.common.data import trace
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from beehive_resource.plugins.provider.entity.base import LocalProviderResource, get_task
from beehive_resource.plugins.vsphere.entity.vs_cluster import VsphereCluster
from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter
from beehive_resource.plugins.vsphere.entity.vs_dvs import VsphereDvs
from beehive_resource.model import Resource as ModelResource, ResourceState


class Site(LocalProviderResource):
    """Provider site
    """
    objdef = 'Provider.Region.Site'
    objuri = '%s/sites/%s'
    objname = 'site'
    objdesc = 'Provider site'
    task_path = 'beehive_resource.plugins.provider.task_v2.site.SiteTask.'

    # update orchestrator type when add a new plugin
    available_orchestrator_types = ['vsphere', 'openstack', 'awx', 'zabbix', 'elk', 'ontap']

    def __init__(self, *args, **kvargs):
        LocalProviderResource.__init__(self, *args, **kvargs)

        from beehive_resource.plugins.provider.entity.vpc_v2 import SiteNetwork
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        self.site_ping = True

        self.child_classes = [
            SiteNetwork,
            AvailabilityZone,
            # Gateway,
        ]

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

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
        :param kvargs.geo_area: geographic ares
        :param kvargs.coords: geographic coords
        :param kvargs.repo: ip address of rpm repository
        :param kvargs.limits: site limits
        :return: {}
        :raise ApiManagerError:
        """
        params = {
            'attribute': {
                'config': {
                    'geo_area': kvargs.pop('geo_area'),
                    'coords': kvargs.pop('coords')
                },
                'limits': kvargs.get('limits'),
                'repo': kvargs.get('repo'),
                'orchestrators': []
            }
        }
        kvargs.update(params)

        steps = [
            Site.task_path + 'create_resource_pre_step',
            Site.task_path + 'create_resource_post_step'
        ]
        kvargs['steps'] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params    
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource physical id            
        :return: kvargs            
        :raise ApiManagerError:
        """
        # kvargs['orchestrators'] = self.get_orchestrators()
        steps = [
            Site.task_path + 'update_resource_pre_step',
            Site.task_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params    
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource physical id                        
        :return: kvargs            
        :raise ApiManagerError:
        """
        orchestrators = self.get_orchestrators(index=False)
        if len(orchestrators) > 0:
            raise ApiManagerError('site %s contains orchestrators. It can not be deleted' % self.oid)

        steps = [
            Site.task_path + 'expunge_resource_pre_step',
            Site.task_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        ping = self.ping()
        info = LocalProviderResource.info(self)
        info['orchestrators'] = ping
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        ping = self.ping()
        info = LocalProviderResource.detail(self)
        info['orchestrators'] = ping
        return info

    def ping(self):
        orchestrators = []
        for orchestrator in self.__get_orchestrators(select_types=self.available_orchestrator_types):
            container = self.controller.get_container(orchestrator['id'], connect=False, cache=False)
            ping = container.ping()
            self.site_ping = self.site_ping and ping
            orchestrator['ping'] = ping
            orchestrator['name'] = container.name
            orchestrators.append(orchestrator)
        self.logger.debug('ping site %s orchestrators: %s' % (self.oid, orchestrators))

        return orchestrators

    def get_base_state(self):
        state = LocalProviderResource.get_base_state(self)
        if self.site_ping is False:
            state = ResourceState.state[10]
        return state

    def get_rpm_repo(self):
        """Get git repo

        :return: dns zone
        """
        zone = self.attribs.get('repo', '')
        return zone

    def get_logstash(self):
        """Get logstash server

        :return: logstash server ip
        """
        logstash = self.attribs.get('logstash', '')
        return logstash

    def get_dns_zone(self):
        """Get dns zone

        :return: dns zone
        """
        zone = self.attribs.get('zone', '')
        return zone

    def __get_orchestrators(self, select_types=None):
        """Get physical orchestrators

        :param select_types: list of types to use as filter
        :return: list of orchestrators
        """
        if select_types is None:
            select_types = ['vsphere', 'openstack']

        orchestrators = self.attribs.get('orchestrators', [])
        # self.logger.debug('+++++ __get_orchestrators select_types: %s' % (select_types))
        resp = []
        for os in orchestrators:
            os_type = os['type']
            # self.logger.debug('+++++ __get_orchestrators os_type: %s' % (os_type))
            if os_type == 'vsphere':
                # physical_networks = []
                clusters = dict_get(os, 'config.clusters')
                dict_set(os, 'config.physical_network', clusters)
            if os_type in select_types:
                resp.append(os)
        self.logger.debug('available orchestrators: %s' % resp)
        return resp

    def get_orchestrators(self, index=True, select_types=None):
        """Get physical orchestrators

        :param index: if True return a dict with id as key. If False return a list.
        :return: orchestrators list or dict
        """
        os = self.__get_orchestrators(select_types=select_types)
        if index is True:
            return {str(c['id']): c for c in os}
        else:
            return os

    def get_orchestrator_by_id(self, oid, select_types=None):
        """Get physical orchestrators

        :param oid: orchestrator id
        :return: orchestrator info or None if it does not exist
        """
        os = {str(c['id']): c for c in self.__get_orchestrators(select_types=select_types)}
        self.logger.debug('Active orchestrator of site %s: %s' % (self.oid, os))
        return os.get(str(oid), None)

    def get_orchestrators_by_tag(self, tag, index_field='id', select_types=None):
        """Get physical orchestrators by tag

        :param tag: orchestrator tag
        :param index_field: index field. Use this field to index orchestrator
        :return: extended params
        :raise ApiManagerError:
        """
        # select containers where create server and twins
        # self.logger.debug('+++++ tag %s' % (tag))
        self.logger.debug('+++++ select_types %s' % (select_types))
        orchestrator_idx = {}
        for v in self.__get_orchestrators(select_types=select_types):
            # self.logger.debug('+++++ v[tag] %s' % (v['tag']))
            if v['tag'] == tag:
                orchestrator_idx[str(v[index_field])] = v

        if len(orchestrator_idx.values()) == 0:
            raise ApiManagerError('No orchestrators found for tag %s' % tag, code=400)
        self.logger.debug('found orchestrators: %s' % orchestrator_idx)
        return orchestrator_idx

    def __check_config_item(self, orchestrator, config, key, entity_class):
        """Check config item

        :param orchestrator_id: orchestrator
        :param config: configuration
        :param key: configuration key
        :param entity_class: entity class
        """
        oid = get_value(config, key, None, exception=True)
        obj = orchestrator.get_resource(oid, entity_class=entity_class)
        config[key] = str(obj.oid)
        return config

    def __validate_vsphere_orchestrator(self, orchestrator, config):
        """Validate vsphere orchestrator configuration

        :param orchestrator_id: orchestrator
        :param config: configuration
        :param config.datacenter: Ex. 4,
        :param config.resource_pool: Ex. 298
        :param config.physical_network: Ex. 346
        :return: updated config
        :raise ApiManagerError:
        """
        config = self.__check_config_item(orchestrator, config, 'datacenter', VsphereDatacenter)
        config = self.__check_config_item(orchestrator, config, 'cluster', VsphereCluster)
        config = self.__check_config_item(orchestrator, config, 'physical_network', VsphereDvs)
        return config

    def __validate_openstack_orchestrator(self, orchestrator, config):
        """Validate openstack orchestrator configuration

        :param orchestrator_id: orchestrator
        :param config: configuration
        :param config.domain: Ex. 1459,
        :param config.availability_zone: Ex. nova
        :param config.physical_network: Ex. datacentre
        :param config.public_network: Ex. internet
        :return: updated config
        :raise ApiManagerError:
        """
        config = self.__check_config_item(orchestrator, config, 'domain', OpenstackDomain)

        avzone = get_value(config, 'availability_zone', None, exception=True)
        avzones = {z['zoneName'] for z in orchestrator.system.get_compute_zones()}
        if avzone not in avzones:
            raise ApiManagerError('Openstack availability_zone %s does not exist' % avzone, code=404)

        get_value(config, 'physical_network', None, exception=True)
        get_value(config, 'public_network', None, exception=True)
        return config

    def __validate_awx_orchestrator(self, orchestrator, config):
        """Validate awx orchestrator configuration

        :param orchestrator_id: orchestrator
        :param config.organization: Ex. Default
        :param config.scm_creds: Ex. gitlab.csi.it-creds
        :return: validated config
        :raise ApiManagerError:
        """
        get_value(config, 'organization', 'Default', exception=False)
        get_value(config, 'scm_creds', None, exception=True)
        return config

    def __validate_zabbix_orchestrator(self, orchestrator, config):
        """Validate zabbix orchestrator configuration

        :param orchestrator_id: orchestrator
        :param config: configuration
        :return: updated config
        :raise ApiManagerError:
        """
        return config

    def __validate_elk_orchestrator(self, orchestrator, config):
        """Validate elk orchestrator configuration

        :param orchestrator_id: orchestrator
        :param config.organization: Ex. Default
        :param config.scm_creds: Ex. gitlab.csi.it-creds
        :return: validated config
        :raise ApiManagerError:
        """
        self.logger.debug('+++++ validate_elk_orchestrator %s' % (orchestrator))
        # get_value(config, 'organization', 'Default', exception=False)
        # get_value(config, 'scm_creds', None, exception=True)
        return config

    def __validate_ontap_orchestrator(self, orchestrator, config):
        """Validate ontap netapp orchestrator configuration

        :param orchestrator_id: orchestrator
        :return: validated config
        :raise ApiManagerError:
        """
        self.logger.debug('+++++ validate_ontap_orchestrator %s' % (orchestrator))
        return config

    @trace(op='update')
    def add_orchestrator(self, *args, **kvargs):
        """Add orchestrator

        :param type: Orchestrator type. Ex. vsphere, openstack
        :param id: Orchestrator id
        :param tag: Orchestrator tag. Ex. default
        :param config: Orchestrator configuration

        Vsphere orchestrator::

        :param config.datacenter: Ex. 4,
        :param config.resource_pool: Ex. 298
        :param config.physical_network: Ex. 346

        Openstack orchestrator::

        :param config.domain: Ex. 1459,
        :param config.availability_zone: Ex. nova
        :param config.physical_network: Ex. datacentre
        :param config.public_network: Ex. internet

        :return: {'taskid': task.id, 'uuid': entity.uuid}, 202
        :raise ApiManagerError:
        """
        # get orchestrator id
        cid = kvargs.pop('id')

        # check orchestrator exists
        c = self.controller.get_container(cid)
        self.logger.debug('+++++ cid %s' % cid)

        # check orchestrator already joined to site
        if self.get_orchestrator_by_id(c.oid, select_types=self.available_orchestrator_types) is not None:
            raise ApiManagerError('Orchestrator %s already joined to site %s' % (cid, self.oid))

        # validate config
        config = kvargs.pop('config')
        ctype = kvargs.pop('type')

        self.logger.debug('+++++ ctype %s' % ctype)
        if ctype == 'vsphere':
            config = self.__validate_vsphere_orchestrator(c, config)
        elif ctype == 'openstack':
            config = self.__validate_openstack_orchestrator(c, config)
        elif ctype == 'awx':
            config = self.__validate_awx_orchestrator(c, config)
        elif ctype == 'zabbix':
            config = self.__validate_zabbix_orchestrator(c, config)
        elif ctype == 'elk':
            config = self.__validate_elk_orchestrator(c, config)
        elif ctype == 'ontap':
            config = self.__validate_ontap_orchestrator(c, config)

        # run celery job
        params = {
            'cid': str(self.container.oid),
            'site_id': self.oid,
            'orchestrator_id': str(c.oid),
            'orchestrator_type': ctype,
            'orchestrator_tag': kvargs.pop('tag'),
            'orchestrator_config': config
        }
        kvargs.update(params)
        steps = [self.task_path + 'add_orchestrator_step']
        res = self.action('add_orchestrator', steps, log='add orchestrator to site %s' % self.oid, check=None, **kvargs)
        return res

    @trace(op='update')
    def delete_orchestrator(self, *args, **kvargs):
        """Delete orchestrator

        :param id: Orchestrator id
        :return: {'taskid': task.id, 'uuid': entity.uuid}, 202
        :raise ApiManagerError:
        """
        # get orchestrator id
        cid = kvargs.pop('id')

        # check orchestrator exists
        c = self.controller.get_container(cid)

        # check orchestrator already joined to site
        orchestrator = self.get_orchestrator_by_id(c.oid, select_types=self.available_orchestrator_types)
        if orchestrator is None:
            raise ApiManagerError('orchestrator %s is not joined to site %s' % (cid, self.oid))

        # check site has no childs with physical resource in orchestrator
        childs, tot = self.manager.get_resources(parent_id=self.oid, with_perm_tag=False)
        for child in childs:
            res_physical = self.manager.get_linked_resources_internal(child.id, link_type='relation',
                                                                      container_id=c.oid)
            if len(res_physical) > 0:
                raise ApiManagerError('orchestrator %s contains resources' % cid)

        # run celery job
        params = {
            'cid': self.container.oid,
            'site_id': self.oid,
            'orchestrator_id': str(c.oid),
            'orchestrator_type': orchestrator['type'],
        }
        kvargs.update(params)
        steps = [self.task_path + 'del_orchestrator_step']
        res = self.action('del_orchestrator', steps, log='del orchestrator to site %s' % self.oid, check=None, **kvargs)
        return res


class SiteChildResource(LocalProviderResource):
    """SiteChildResource
    """
    task_path = 'beehive_resource.plugins.provider.task_v2.AbstractProviderResourceTask.'
    
    def get_site(self):
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

        return res

    def get_orchestrators(self, index=True, select_types=None):
        """Get physical orchestrators

        :param index: if True return a dict with id as key. If False return a list.
        :return: orchestrators list or dict
        """
        return self.get_site().get_orchestrators(index, select_types=select_types)

    def get_orchestrator_by_id(self, oid, select_types=None):
        """Get physical orchestrators

        :param oid: orchestrator id
        :return: orchestrator info or None if it does not exist
        """
        return self.get_site().get_orchestrator_by_id(oid, select_types=select_types)

    def get_orchestrators_by_tag(self, tag, index_field='id', select_types=None):
        """Get physical orchestrators by tag

        :param tag: orchestrator tag
        :return: extended params
        :raise ApiManagerError:
        """
        return self.get_site().get_orchestrators_by_tag(tag, index_field=index_field, select_types=select_types)

    @staticmethod
    def group_create_step(g_steps):
        """Create group of step used to create resource

        :param g_steps: list of additional steps
        :return: list of steps
        """
        run_steps = [SiteChildResource.task_path + 'create_resource_pre_step']
        run_steps.extend(g_steps)
        run_steps.append(SiteChildResource.task_path + 'create_resource_post_step')
        return run_steps

    def group_update_step(self, g_steps):
        """Create group of step used to update resource

        :param g_steps: list of additional steps
        :return: list of steps
        """
        run_steps = [self.task_path + 'update_resource_pre_step']
        if g_steps is not None:
            run_steps.extend(g_steps)
        run_steps.append(self.task_path + 'update_resource_post_step')
        return run_steps

    def group_patch_step(self, g_steps):
        """Create group of step used to patch resource

        :param g_steps: list of additional steps
        :return: list of steps
        """
        run_steps = [self.task_path + 'patch_resource_pre_step']
        if g_steps is not None:
            run_steps.extend(g_steps)
        run_steps.append(self.task_path + 'patch_resource_post_step')
        return run_steps

    def group_remove_step(self, orchestrators):
        """Create group of step used to remove resource

        :param childs: list of childs to remove
        :return: list of steps
        """
        run_steps = [self.task_path + 'expunge_resource_pre_step']
        for item in orchestrators.values():
            substep = {
                'step': self.task_path + 'remove_physical_resource_step', 
                'args': [str(item['id']), item['type']]
            }
            run_steps.append(substep)
        run_steps.append(self.task_path + 'expunge_resource_post_step')
        return run_steps

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method. Extend this function to manipulate and
        validate update input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs['steps'] = self.group_update_step([])
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
        # select physical orchestrators
        orchestrator_idx = self.get_orchestrators()
        kvargs['steps'] = self.group_remove_step(orchestrator_idx)
        kvargs['sync'] = True
        return kvargs
