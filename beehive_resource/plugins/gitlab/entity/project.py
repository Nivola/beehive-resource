# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.gitlab.entity import GitlabResource
import logging

logger = logging.getLogger(__name__)


class GitlabProject(GitlabResource):
    objdef = 'Gitlab.Project'
    objuri = 'project'
    objname = 'project'
    objdesc = 'Gitlab project'

    default_tags = ['gitlab']
    task_base_path = 'beehive_resource.plugins.gitlab.task_v2.zbx_project.GitlabProjectTask.'

    def __init__(self, *args, **kvargs):
        """ """
        super().__init__(*args, **kvargs)

        # child classes
        self.child_classes = []

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
        # query gitlab
        if ext_id is not None:
            items = container.conn.project.get(ext_id)
        else:
            items = container.conn.project.list()

        # add new items to final list
        res = []
        for item in items:
            item_id = item['projectid']
            if item_id not in res_ext_ids:
                level = None
                name = item['name']
                status = item['status']
                parent_id = None
                res.append((GitlabProject, item_id, parent_id, GitlabProject.objdef, name, level, status))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to communicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # query gitlab
        items = []
        projects = container.conn.project.list()
        for project in projects:
            items.append({
                'id': project['projectid'],
                'name': project['name']
            })
        return items

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass':., 'objid':., 'name':., 'ext_id':., 'active':., 'desc':.,
                                    'attrib':., 'parent':., 'tags':.}
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        status = entity[6]

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
        # # query gitlab
        # remote_entities = container.conn.project.list()
        #
        # # create index of remote objs
        # remote_entities_index = {i['projectid']: i for i in remote_entities}
        #
        # for entity in entities:
        #     try:
        #         ext_obj = remote_entities_index.get(entity.ext_id, None)
        #         entity.set_physical_entity(ext_obj)
        #     except:
        #         container.logger.warn('', exc_info=1)
        #
        # return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        # try:
        #     ext_obj = self.container.conn.project.get(self.ext_id)
        #     self.set_physical_entity(ext_obj)
        #
        #     # retrieve projectprojects the project belongs to
        #     ext_projects = self.container.conn.project.projects(ext_obj['projectid']).get('projects', [])
        #     for item in ext_projects:
        #         project = self.controller.get_resource_by_extid(item['projectid'])
        #         self.projects.append(project)
        #
        #     # retrieve templates linked to the project
        #     ext_templates = self.container.conn.project.templates(ext_obj['projectid']).get('parentTemplates', [])
        #     for item in ext_templates:
        #         template = self.controller.get_resource_by_extid(item['templateid'])
        #         self.templates.append(template)
        #
        #     # retrieve interfaces used by the project
        #     self.ext_interfaces = self.container.conn.project.interfaces(ext_obj['projectid']).get('interfaces', [])
        # except:
        #     # pass
        #     logger.warning('', exc_info=True)

    #
    # create
    #
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """check input params before resource creation.
        """
        container.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        container.logger.warn('I am the pre_create')
        container.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        return kvargs

    def do_create(self, **params):
        """method to execute to make custom resource operations useful to complete create

        :param params: custom params required by task
        :return:
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the do_create')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        pass

    #
    # import
    #
    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """check input params before resource import.
        """
        return kvargs

    def do_import(self, **params):
        """method to execute to make custom resource operations useful to complete import

        :param params: custom params required by task
        :return:
        """
        pass

    #
    # patch
    #
    def pre_patch(self, *args, **kvargs):
        """check input params before resource patch.
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the pre_patch')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        return kvargs

    def do_patch(self, **params):
        """method to execute to make custom resource operations useful to complete patch

        :param params: custom params required by task
        :return:
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the do_patch')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        pass

    #
    # update
    #
    def pre_update(self, *args, **kvargs):
        """pre update function. This function is used in update method.
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the pre_update')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        return kvargs

    def do_update(self, **params):
        """method to execute to make custom resource operations useful to complete update

        :param params: custom params required by task
        :return:
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the do_update')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        pass

    #
    # expunge
    #
    def pre_expunge(self, *args, **kvargs):
        """check input params before resource expunge.
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the pre_expunge')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        return kvargs

    def do_expunge(self, **params):
        """method to execute to make custom resource operations useful to complete expunge

        :param params: custom params required by task
        :return:
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the do_expunge')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')

        # if self.is_ext_id_valid() is False:
        #     self.logger.warn('resource %s ext_id is not valid' % self.oid)

        # try:
        #     # check whether project exists
        #     self.container.conn.project.get(self.ext_id)
        #     # delete project
        #     self.container.conn.project.delete(self.ext_id)
        #     self.logger.debug('delete gitlab project %s' % self.ext_id)
        # except:
        #     self.logger.warning('gitlab project %s does not exist anymore' % self.ext_id)

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return super().info()

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = super().detail()
        return info
