# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte
import json

from time import sleep

import logging
from beecell.simple import id_gen, dict_get, truncate
from beehive_resource.plugins.awx.entity import AwxResource

logger = logging.getLogger(__name__)


class AwxAdHocCommand(AwxResource):
    objdef = 'Awx.AdHocCommand'
    objuri = 'ad_hoc_commands'
    objname = 'ad_hoc_command'
    objdesc = 'Awx AdHocCommand'
    
    default_tags = ['awx']
    task_base_path = 'beehive_resource.plugins.awx.task_v2.awx_ad_hoc_command.AwxAdHocCommandTask.'

    create_task = None
    # clone_task = 'beehive_resource.task_v2.core.resource_clone_task'
    import_task = None
    update_task = None
    patch_task = None
    delete_task = None
    expunge_task = None
    action_task = None

    def __init__(self, *args, **kvargs):
        """ """
        AwxResource.__init__(self, *args, **kvargs)

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to communicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)
        :raises ApiManagerError:
        """
        # get from awx
        if ext_id is not None:
            remote_entities = container.conn.ad_hoc_command.get(ext_id)
        else:
            remote_entities = container.conn.ad_hoc_command.list()

        # add new item to final list
        res = []
        for item in remote_entities:
            if item['id'] not in res_ext_ids:
                level = None
                name = item['name']
                parent_id = None
                res.append((AwxAdHocCommand, item['id'], parent_id, AwxAdHocCommand.objdef, name, level))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # get from awx
        items = []
        remote_entities = container.conn.ad_hoc_command.list()
        for item in remote_entities:
            items.append({
                'id': item['id'],
                'name': item['name']
            })

        return items
    
    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]

        objid = '%s//%s' % (container.objid, id_gen())

        res = {
            'resource_class': resclass,
            'objid': objid,
            'name': name,
            'ext_id': ext_id,
            'active': True,
            'desc': resclass.objdesc,
            'attrib': {},
            'parent': parent_id,
            'tags': resclass.default_tags
        }

        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        # get from awx
        remote_entities = container.conn.ad_hoc_command.list()

        # create index of remote objs
        remote_entities_index = {i['id']: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn('', exc_info=1)

        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        ext_obj = self.get_remote_ad_hoc_command(self.controller, self.ext_id, self.container, self.ext_id)
        self.set_physical_entity(ext_obj)
        
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.organization: organization id
        :param kvargs.hosts: hosts definition {'ip_addr':.., 'extra_vars':..}
        :param kvargs.verbosity: verbosity
        :param kvargs.ssh_creds: ssh credential {'username':.., 'password':..} [optional]
        :param kvargs.ssh_cred_id: ssh credential id [optional]
        :param kvargs.inventory: inventory id [optional]
        :param kvargs.module_name: module name [optional]
        :param kvargs.module_args: module args [optional]
        :param kvargs.extra_vars: extra vars [optional]
        :return: kvargs            
        :raise ApiManagerError: 
        """
        awx_name = kvargs.get('name')

        def to_dict(extras):
            variables = {}
            if extras is not None:
                for item in extras.split(';'):
                    k, v = item.split(':', 1)
                    # remove string quotes at start and end if present
                    v = v.strip('\'')
                    if k == 'host_groups' or k == 'host_templates':
                        # convert string to list
                        v = v.replace('[', '').replace(']', '').split(', ')
                    variables[k] = v
            return variables

        def get_organization_id(name):
            res = container.conn.organization.list(name=name)
            if len(res) > 1:
                msg = 'More than an organization with the same name'
                logger.error(msg)
                raise Exception(msg)
            return res[0].get('id')

        def add_ssh_credentials(organization, ssh_creds, rand):
            # append random code to avoid getting duplicate name error from awx
            name = '-'.join(('TEMP-%s-creds-ssh', rand)) % awx_name
            username = ssh_creds.get('username')
            password = ssh_creds.get('password')
            res = container.conn.credential.add_ssh(name, organization, username, password)
            ext_id = res.get('id')
            logger.info('Ssh credentials \'{}\' created: {}'.format(name, ext_id))
            return ext_id

        def del_ssh_credentials(credential):
            container.conn.credential.delete(credential)
            logger.info('Ssh credentials \'{}\' deleted'.format(credential))

        def add_inventory(organization, rand):
            # append random code to avoid getting duplicate name error from awx
            name = '-'.join(('TEMP-%s-inventory', rand)) % awx_name
            res = container.conn.inventory.add(name, organization)
            ext_id = res.get('id')
            logger.info('Inventory \'{}\' created: {}'.format(name, ext_id))
            return ext_id

        def del_inventory(inventory):
            container.conn.inventory.delete(inventory)
            logger.info('Inventory \'{}\' deleted'.format(inventory))

        def add_hosts(hosts, inventory):
            host_extids = []
            for host in hosts:
                ip_addr = host.get('ip_addr')
                extra_vars = host.get('extra_vars', None)
                if isinstance(extra_vars, str):
                    extra_vars = to_dict(extra_vars)
                res = container.conn.host.add(ip_addr, inventory, vars=extra_vars)
                ext_id = res.get('id')
                host_extids.append(ext_id)
                logger.info('Host \'{}\' added to inventory: {}'.format(ip_addr, ext_id))
            return host_extids

        def del_hosts(hosts):
            for host in hosts:
                container.conn.host.delete(host)
                logger.info('Host \'{}\' deleted'.format(host))

        def add_ad_hoc_command(inventory_id, credential_id, module_name, module_args, verbosity=0, extra_vars=''):
            res = container.conn.ad_hoc_command.add(inventory_id, limit='', credential=credential_id,
                                                    module_name=module_name, module_args=module_args,
                                                    verbosity=verbosity, extra_vars=extra_vars, become_enabled=False)
            ext_id = res.get('id')
            logger.info('Ad hoc command for inventory \'{}\' created: {}'.format(inventory_id, ext_id))
            return ext_id

        org_name = kvargs.pop('organization')
        hosts = kvargs.pop('hosts', None)
        ssh_creds = kvargs.pop('ssh_creds', None)
        extra_vars = kvargs.pop('extra_vars', None)
        module_name = kvargs.pop('module_name', None)
        module_args = kvargs.pop('module_args', None)

        try:
            rand = id_gen(8)
            # get organization id
            org_ext_id = get_organization_id(org_name)
            # create temporary ssh credentials
            ssh_creds_ext_id = kvargs.pop('ssh_cred_id', None)
            delete_ssh_cred = False
            if ssh_creds_ext_id is None:
                ssh_creds_ext_id = add_ssh_credentials(org_ext_id, ssh_creds, rand)
                delete_ssh_cred = True
            # create temporary inventory
            inventory_ext_id = kvargs.pop('inventory', None)
            delete_inventory = False
            if inventory_ext_id is None:
                inventory_ext_id = add_inventory(org_ext_id, rand)
                delete_inventory = True
                # add hosts to inventory
                host_extids = add_hosts(hosts, inventory_ext_id)
            # create ad hoc command
            kvargs['ext_id'] = add_ad_hoc_command(inventory_ext_id, ssh_creds_ext_id, module_name, module_args,
                                                  verbosity=0, extra_vars=extra_vars)
            # # delete hosts
            # if delete_inventory is True:
            #     del_hosts(host_extids)
            #     del_inventory(inventory_ext_id)
            #
            # if delete_ssh_cred is True:
            #     del_ssh_credentials(ssh_creds_ext_id)

        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise Exception(ex)



        # kvargs['add']['inventory'] = inventory_ext_id
        # kvargs['add']['project'] = project_ext_id
        # kvargs['launch']['ssh_creds_id'] = ssh_creds_ext_id
        # kvargs['launch']['extra_vars'] = to_dict(extra_vars)
        #
        # steps = [
        #     AwxAdHocCommand.task_base_path + 'create_resource_pre_step',
        #     AwxAdHocCommand.task_base_path + 'awx_ad_hoc_command_create_physical_step',
        #     AwxAdHocCommand.task_base_path + 'awx_ad_hoc_command_launch_step',
        #     AwxAdHocCommand.task_base_path + 'awx_job_report_step',
        #     AwxAdHocCommand.task_base_path + 'create_resource_post_step',
        # ]
        # kvargs['steps'] = steps
        # # kvargs['sync'] = True

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params            
        :return: kvargs            
        :raises ApiManagerError:
        """
        # steps = [
        #     AwxAdHocCommand.task_base_path + 'update_resource_pre_step',
        #     AwxAdHocCommand.task_base_path + 'awx_ad_hoc_command_update_physical_step',
        #     AwxAdHocCommand.task_base_path + 'update_resource_post_step'
        # ]
        # kvargs['steps'] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params            
        :return: kvargs            
        :raises ApiManagerError:
        """
        # steps = [
        #     AwxAdHocCommand.task_base_path + 'expunge_resource_pre_step',
        #     AwxAdHocCommand.task_base_path + 'awx_ad_hoc_command_delete_physical_step',
        #     AwxAdHocCommand.task_base_path + 'expunge_resource_post_step'
        # ]
        # kvargs['steps'] = steps
        return kvargs

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = AwxResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = AwxResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            info['details'].update(data)

        return info

    def get_stdout(self, parse='json'):
        """Get stdout

        :param parse: set output parser. json or text
        :return: command output
        """
        res = {}
        status = None
        elasped = 0
        delta = 0.5
        maxtime = 15
        while status not in ['successful', 'failed', 'error', 'canceled']:
            status = self.container.conn.ad_hoc_command.get(self.ext_id).get('status')
            sleep(delta)
            elasped += delta
            if elasped > maxtime:
                break
        if status == 'successful':
            res = self.container.conn.ad_hoc_command.stdout(self.ext_id)

            res = dict_get(res, 'content')

            if parse == 'json':
                n = res.find('{"')
                m = res.find('}\x1b') + 1
                res = res[n:m]
                self.logger.warn(res)
                res = json.loads(res)
            elif parse == 'text':
                n = res.find('>>')+2
                res = res[n:]
                res = res.replace('\x1b[0m', '').replace('\x1b[0;33m', '')
                res = res.lstrip('\n').rstrip('\n')

        self.logger.debug('get ad hoc command %s stdout: %s' % (self.oid, truncate(res)))
        return res
