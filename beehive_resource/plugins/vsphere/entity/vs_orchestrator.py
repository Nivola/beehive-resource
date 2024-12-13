# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import requests
from beecell.simple import truncate, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import VsphereResource, get_task
from yaml import load

from beehive_resource.container import Resource

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


class VsphereOrchestrator(VsphereResource):
    objdef = "Vsphere.Orchestrator"
    objuri = "orchestrators"
    objname = "orchestrator"
    objdesc = "Vsphere orchestrators"

    default_tags = ["vsphere"]
    task_path = "beehive_resource.plugins.vsphere.task_v2.vs_orchestrator.OrchestratorTask"

    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)

        :raises ApiManagerError:
        """
        # get orchestrator instance from vsphere
        items = [{"id": "orchestrator-01", "name": "orchestrator-01"}]

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = None

                res.append(
                    (
                        VsphereOrchestrator,
                        item["id"],
                        parent_id,
                        VsphereOrchestrator.objdef,
                        name,
                        level,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        items = [{"id": "orchestrator-01", "name": "orchestrator-01"}]
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

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent_id,
            "tags": resclass.default_tags,
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
        for entity in entities:
            entity.set_physical_entity({"id": "orchestrator-01", "name": "orchestrator"})
        return entities

    def post_get(self):
        """Check input params before resource creation. This function is used  in container resource_factory method.

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
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.datacenter: parent datacenter id or uuid
        :param kvargs.folder: parent folder id or uuid
        :param kvargs.folder_type: folder type. Can be: host, network, storage, vm
        :return: kvargs
        :raises ApiManagerError:
        """
        try:
            self.set_physical_entity({"id": "orchestrator-01", "name": "orchestrator"})
        except:
            pass

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = VsphereResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = VsphereResource.detail(self)
        return info

    def status(self):
        """Get details.

        :return:

            like :class:`Resource`

            details: {
            }

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        return info

    def get_template_versions(self):
        """Get template versions.

        **Parameters:**

        :return:

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        ver = None
        # ver = self.container.conn.orchestrator.template.versions()
        self.logger.debug("Get orchestrator template versions")
        return ver

    def get_template_functions(self, template):
        """Get functions for a specific template version.

        **Parameters:**

            * **template: template

        :return:

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        # func = self.container.conn.orchestrator.template.functions(template)
        func = None
        self.logger.debug("Get orchestrator template %s functions" % template)
        return func

    def validate_template(self, template_uri):
        """Validate template from http(s) uri

        TODO: use another http client more efficient with gevent

        **Parameters:**

            * **template_uri: template_uri

        :return:

        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        try:
            rq = requests.get(template_uri, timeout=30, verify=False)
            if rq.status_code == 200:
                template = load(rq.content, Loader=Loader)
                self.logger.debug("Get template: %s" % truncate(template))
            else:
                self.logger.error("No response from uri %s found" % template_uri)

            # self.container.conn.orchestrator.template.validate(template=template, environment={})
        except:
            self.logger.error("Failed to validate orchestrator template %s" % template_uri, exc_info=1)
            raise ApiManagerError("Failed to validate orchestrator template %s" % template_uri)

        self.logger.debug("Validate orchestrator template %s: True" % template_uri)
        return template


class VsphereStack(VsphereResource):
    objdef = "Vsphere.DataCenter.Folder.Stack"
    objuri = "stacks"
    objname = "stack"
    objdesc = "Vsphere stacks"

    default_tags = ["vsphere"]
    task_path = "beehive_resource.plugins.vsphere.task_v2.vs_stack.StackTask"

    create_task = get_task("vs_stack.job_stack_create")
    update_task = get_task("vs_stack.job_stack_update")
    expunge_task = get_task("vs_stack.job_stack_delete")

    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)

        :raises ApiManagerError:
        """
        res = []
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        items = []
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

        parent = container.get_resource_by_extid(parent_id)
        objid = "%s//%s" % (parent.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent.oid,
            "tags": resclass.default_tags,
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
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used  in container resource_factory method.

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
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.template_uri: A URI to the location containing the stack template on which to perform the
            operation. See the description of the template parameter for information about the expected template
            content located at the URI.')
        :param kvargs.environment: A JSON environment for the stack
        :param kvargs.parameters: 'Supplies arguments for parameters defined in the stack template
        :param kvargs.files: Supplies the contents of files referenced in the template or the environment
        :param kvargs.owner: stack owner name
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            VsphereStack.task_path + "create_resource_pre_step",
            # VsphereStack.task_path + 'vsphere_folder_create_physical_step',
            VsphereStack.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            VsphereStack.task_path + "update_resource_pre_step",
            # VsphereStack.task_path + 'vsphere_folder_update_physical_step',
            VsphereStack.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError:
        """
        steps = [
            VsphereStack.task_path + "expunge_resource_pre_step",
            # VsphereStack.task_path + 'vsphere_folder_update_physical_step',
            VsphereStack.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
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
        info = VsphereResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = VsphereResource.detail(self)
        return info

    #
    # query stack
    #
    def get_template(self):
        """Get template.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        template = None
        self.logger.debug("Get stack %s template" % self.name)
        return template

    def get_environment(self):
        """Get environment.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        environment = None
        self.logger.debug("Get stack %s environment" % self.name)
        return environment

    def get_files(self):
        """Get files.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        files = None
        self.logger.debug("Get stack %s files" % self.name)
        return files

    def get_outputs(self):
        """Get outputs.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        outputs = []
        if self.ext_obj is not None:
            outputs = self.ext_obj.get("outputs", "")
            self.logger.debug("Get stack %s outputs: %s" % (self.name, truncate(outputs)))
        return outputs

    def get_outputs_desc(self):
        """Get outputs description.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        outputs = None
        self.logger.debug("Get stack %s outputs" % self.name)
        return outputs

    def get_output(self, key):
        """Get output.

        :param key: output key
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        outputs = None
        self.logger.debug("Get stack %s output %s" % (self.name, key))
        return outputs

    def get_stack_resources(self, *args, **kvargs):
        """Get resources.

        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        resources, total = self.get_linked_resources(link_type="stack", *args, **kvargs)

        self.logger.debug("Get stack %s resources: %s" % (self.name, truncate(resources)))
        return resources, total

    def get_stack_internal_resources(self, name=None, status=None, type=None):
        """Get internal resources.

        :param name: resource name
        :param status: resource status
        :param type: resource type
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        resources = None
        self.logger.debug("Get stack %s internal resources: %s" % (self.name, truncate(resources)))
        return resources

    def get_events(self):
        """Get outputs.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("use")

        events = self.container.conn.orchestrator.stack.event.list(stack_name=self.name, oid=self.ext_id)
        self.logger.debug("Get stack %s events" % self.name)
        return events

    def get_status_reason(self):
        """Get stack status reason.

        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions("view")

        status_reason = ""
        if self.ext_obj is not None:
            status_reason = self.ext_obj.get("status_reason", "")
            self.logger.debug("Get stack %s status reason: %s" % (self.name, status_reason))
        return status_reason
