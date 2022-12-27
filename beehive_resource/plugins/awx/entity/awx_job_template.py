# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import logging
from beecell.simple import id_gen, dict_get, truncate
from beehive_resource.plugins.awx.entity import AwxResource
from beehive_resource.plugins.awx.entity.awx_project import AwxProject

logger = logging.getLogger(__name__)


class AwxJobTemplate(AwxResource):
    objdef = 'Awx.JobTemplate'
    objuri = 'job_templates'
    objname = 'job_template'
    objdesc = 'Awx JobTemplate'
    
    default_tags = ['awx']
    task_base_path = 'beehive_resource.plugins.awx.task_v2.awx_job_template.AwxJobTemplateTask.'
    
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
            remote_entities = container.conn.job_template.get(ext_id)
        else:
            remote_entities = container.conn.job_template.list()

        # add new item to final list
        res = []
        for item in remote_entities:
            if item['id'] not in res_ext_ids:
                level = None
                name = item['name']
                parent_id = None
                res.append((AwxJobTemplate, item['id'], parent_id, AwxJobTemplate.objdef, name, level))

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
        remote_entities = container.conn.job_template.list()
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
        remote_entities = container.conn.job_template.list()

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
        ext_obj = self.get_remote_template(self.controller, self.ext_id, self.container, self.ext_id)
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
        :param kvargs.add: add params
        :param kvargs.add.organization: organization id
        :param kvargs.add.hosts: hosts id
        :param kvargs.add.project: project id
        :param kvargs.add.playbook: project playbook
        :param kvargs.add.verbosity: verbosity
        :param kvargs.launch: launch params
        :param kvargs.launch.ssh_creds: ssh_creds [optional]
        :param kvargs.launch.ssh_cred_id: ssh credential id [optional]
        :param kvargs.launch.inventory: inventory id [optional]
        :param kvargs.launch: launch params
        :return: kvargs            
        :raise ApiManagerError: 
        """
        awx_name = kvargs.get('name')

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
            password = ssh_creds.get('password', None)
            ssh_key_data = ssh_creds.get('ssh_key_data', None)

            ssh_key_unlock = None
            if ssh_key_data is not None:
                password = None
                # ssh_key_unlock = True
            res = container.conn.credential.add_ssh(name, organization, username, password=password,
                                                    ssh_key_data=ssh_key_data, ssh_key_unlock=ssh_key_unlock)
            ext_id = res.get('id')
            logger.info('Ssh credentials \'{}\' created: {}'.format(name, ext_id))
            return ext_id

        def add_inventory(organization, rand):
            # append random code to avoid getting duplicate name error from awx
            name = '-'.join(('TEMP-%s-inventory', rand)) % awx_name
            res = container.conn.inventory.add(name, organization)
            ext_id = res.get('id')
            logger.info('Inventory \'{}\' created: {}'.format(name, ext_id))
            return ext_id

        def add_hosts(hosts, inventory):
            for host in hosts:
                ip_addr = host.get('ip_addr')
                extra_vars = host.get('extra_vars', None)
                res = container.conn.host.add(ip_addr, inventory, vars=to_dict(extra_vars))
                ext_id = res.get('id')
                logger.info('Host \'{}\' added to inventory: {}'.format(ip_addr, ext_id))

        def to_dict(extras):
            if isinstance(extras, dict):
                return extras
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

        org_name = kvargs.get('add').pop('organization')
        hosts = kvargs.get('add').pop('hosts', [])
        project_name = kvargs.get('add').pop('project')
        job_tags = kvargs.get('add').pop('job_tags', [])
        ssh_creds = kvargs.get('launch').pop('ssh_creds', None)
        extra_vars = kvargs.get('launch').pop('extra_vars', None)

        try:
            rand = id_gen(8)
            # get organization id
            org_ext_id = get_organization_id(org_name)
            # create temporary ssh credentials
            ssh_creds_ext_id = kvargs.get('launch').pop('ssh_cred_id', None)
            if ssh_creds_ext_id is None:
                ssh_creds_ext_id = add_ssh_credentials(org_ext_id, ssh_creds, rand)
            # create temporary inventory
            inventory_ext_id = kvargs.get('add').pop('inventory', None)
            if inventory_ext_id is None:
                inventory_ext_id = add_inventory(org_ext_id, rand)
                # add hosts to inventory
                add_hosts(hosts, inventory_ext_id)
            # get project ext_id
            project = container.get_simple_resource(project_name, entity_class=AwxProject)
            project_ext_id = project.ext_id
            logger.info('Project \'{}\' retrieved: {}'.format(project_name, project_ext_id))
            # create comma-separated list of job tags
            job_tags = ','.join(job_tag for job_tag in job_tags)
        except Exception as ex:
            logger.error(ex, exc_info=True)
            raise Exception(ex)

        kvargs['add']['inventory'] = inventory_ext_id
        kvargs['add']['project'] = project_ext_id
        kvargs['add']['job_tags'] = job_tags
        kvargs['launch']['ssh_creds_id'] = ssh_creds_ext_id
        kvargs['launch']['extra_vars'] = to_dict(extra_vars)

        steps = [
            AwxJobTemplate.task_base_path + 'create_resource_pre_step',
            AwxJobTemplate.task_base_path + 'awx_job_template_create_physical_step',
            AwxJobTemplate.task_base_path + 'awx_job_template_launch_step',
            # AwxJobTemplate.task_base_path + 'awx_job_report_step',
            AwxJobTemplate.task_base_path + 'create_resource_post_step',
        ]
        kvargs['steps'] = steps
        # kvargs['sync'] = True

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params            
        :return: kvargs            
        :raises ApiManagerError:
        """
        steps = [
            AwxJobTemplate.task_base_path + 'update_resource_pre_step',
            AwxJobTemplate.task_base_path + 'awx_job_template_update_physical_step',
            AwxJobTemplate.task_base_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params            
        :return: kvargs            
        :raises ApiManagerError:
        """
        steps = [
            AwxJobTemplate.task_base_path + 'expunge_resource_pre_step',
            AwxJobTemplate.task_base_path + 'awx_job_template_delete_physical_step',
            AwxJobTemplate.task_base_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps
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

    def get_last_job(self):
        """Get last job executed"""
        last_job = {}
        if self.ext_obj is not None:
            last_job_id = dict_get(self.ext_obj, 'summary_fields.last_job.id')

            last_job = self.container.conn.job.get(last_job_id)
            last_job['stdout'] = self.container.conn.job.stdout(last_job_id)

        self.logger.debug('get job template %s last job: %s' % (self.oid, truncate(last_job)))
        return last_job
