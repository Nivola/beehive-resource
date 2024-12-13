# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte
from datetime import datetime
from logging import getLogger
from re import match
from six import ensure_str
from beecell.simple import import_class, format_date, random_password, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Resource
from beehive_resource.plugins.provider.entity.aggregate import ComputeProviderResource
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beecell.simple import dict_set, dict_get
from beecell.types.type_string import str2bool

logger = getLogger(__name__)


class ComputeStackV2(ComputeProviderResource):
    """Compute stack version 2

    inputs:
      - name: key_name
        type: str
        desc: Name of the db instance. It is used to set server name
        default: "dbinstance"
      ...
    outputs:
      - name: ResourceIP
        desc: Master Server IP address
        value: { get_attr: [mysql_instance, first_address] }
      ...
    actions:
      - name: create_server
        desc: create server
        resource:
          type: ComputeInstance
          oid: 1234 [optional]
          operation: create
        params:
          k1: v1
          k2: v2
      - name: install_haproxy
        description: install haproxy
        resource:
          type: AppliedCustomization
          oid: 1234 [optional]
          operation: create
        params:
          instances: 123,456
          customization: 56
          k1: v1
    """

    objdef = "Provider.ComputeZone.ComputeStackV2"
    objuri = "%s/stacks/%s"
    objname = "stack"
    objdesc = "Provider ComputeStack V2"
    task_path = "beehive_resource.plugins.provider.task_v2.stack_v2.StackV2Task."

    RESOURCE_TYPE = {
        "ComputeInstance": "beehive_resource.plugins.provider.entity.instance.ComputeInstance",
        "AppliedComputeCustomization": "beehive_resource.plugins.provider.entity.applied_customization."
        "AppliedComputeCustomization",
        "ComputeVolume": "beehive_resource.plugins.provider.entity.volume.ComputeVolume",
    }

    def __init__(self, *args, **kvargs):
        ComputeProviderResource.__init__(self, *args, **kvargs)

        self.child_classes = [ComputeStackAction]

        self.actions = None
        self.resources = None

    def get_stack_type(self):
        """Return stack type. Example: app_stack, sql_stack"""
        return self.get_attribs("stack_type")

    def get_stack_engine(self):
        """Return stack engine info"""
        return {
            "engine": self.get_attribs("engine"),
            "version": self.get_attribs("version"),
            "engine_configs": self.get_attribs("engine_configs"),
        }

    def info(self):
        """Get info

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeProviderResource.info(self)
        info["stack_type"] = self.get_stack_type()
        info["actions"] = len(self.get_actions())
        info["resources"] = len(self.get_child_resources())

        dict_set(
            info,
            "attributes.monitoring_enabled",
            self.is_monitoring_enabled(),
        )
        dict_set(info, "attributes.hypervisor", self.get_hypervisor())

        return info

    def detail(self):
        """Get detail

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = ComputeProviderResource.detail(self)
        info["stack_type"] = self.get_stack_type()
        info["inputs"] = self.get_inputs()
        info["outputs"] = self.get_outputs()
        info["actions"] = [a.info() for a in self.get_actions()]
        info["resources"] = [s.small_info() for s in self.get_child_resources()]

        dict_set(
            info,
            "attributes.monitoring_enabled",
            str2bool(self.is_monitoring_enabled()),
        )
        dict_set(info, "attributes.hypervisor", self.get_hypervisor())

        return info

    def is_monitoring_enabled(self, cache=False, ttl=300):  # aaa
        # self.logger.debug("+++++ AAA is_monitoring_enabled")
        for resource in self.get_child_resources():
            if isinstance(resource, ComputeInstance):
                # self.logger.debug("+++++ AAA is_monitoring_enabled - resource %s" % resource)
                computeInstance: ComputeInstance = resource
                return computeInstance.is_monitoring_enabled()

        return 0

    def get_hypervisor(self):
        # self.logger.debug("+++++ AAA get_hypervisor")
        for resource in self.get_child_resources():
            if isinstance(resource, ComputeInstance):
                # self.logger.debug("+++++ AAA get_hypervisor - resource %s" % resource)
                computeInstance: ComputeInstance = resource
                return computeInstance.get_hypervisor()

        return None

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        parent_list = [e.oid for e in entities]
        actions, tot = controller.get_resources(
            parent_list=parent_list,
            run_customize=False,
            authorize=False,
            type=ComputeStackAction.objdef,
            size=-1,
        )

        action_idx = {}
        for a in actions:
            try:
                action_idx[str(a.parent_id)].append(a)
            except:
                action_idx[str(a.parent_id)] = [a]

        for entity in entities:
            entity.actions = action_idx.get(str(entity.oid))

            linked_resources = entity.get_linked_resources_with_cache()
            if len(linked_resources) > 0:
                entity.resources = []
                for linked_resource in linked_resources:
                    end_resource = linked_resource
                    link_type = end_resource.link_type
                    if link_type.find("resource") == 0:
                        entity.resources.append(linked_resource)

        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        pass

    def get_quotas(self):
        """Get resource quotas

        :return: list of resoruce quotas
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        quotas = {
            "instances": 1,
            "cores": 0,
            "ram": 0,
            "blocks": 0,
            "volumes": 0,
            "snapshots": 0,
        }

        for resource in self.get_child_resources():
            if isinstance(resource, ComputeInstance):
                volumes = resource.get_volumes()
                resource.post_get()
                if resource.is_running() is True and resource.flavor is not None:
                    cores = resource.get_attribs("quotas.database.cores")
                    ram = resource.get_attribs("quotas.database.ram")

                    if cores is None or ram is None:
                        flavor = resource.flavor.get_configs()
                        quotas["cores"] = flavor.get("vcpus", 0)
                        quotas["ram"] = flavor.get("memory", 0) / 1024

                        resource.set_configs("quotas.database.cores", flavor.get("vcpus", 0))
                        resource.set_configs("quotas.database.ram", flavor.get("memory", 0))

                    else:
                        quotas["cores"] = cores
                        quotas["ram"] = ram / 1024

                quotas["blocks"] += sum([v.get_size() for v in volumes])
                quotas["volumes"] += len(volumes)
                # quotas['snapshots'] += len(resource.list_snapshots())

        self.logger.debug2("Get resource %s quotas: %s" % (self.uuid, quotas))
        return quotas

    def get_inputs(self, name=None):
        """Get inputs.

        :param name: input name
        :return: list of inputs
        :raise ApiManagerError:
        """
        if name is not None:
            return self.get_attribs(key="inputs." + name)
        return self.get_attribs(key="inputs", default={})

    def get_outputs(self, name=None):
        """Get outputs.

        :param name: output name
        :return: list of outputs
        :raise ApiManagerError:
        """
        if name is not None:
            res = self.get_attribs(key="outputs." + name)
            # don't return output value if it is not valorised
            if res.find("$$") == 0:
                res = ""
            return res
        return self.get_attribs(key="outputs", default={})

    def set_output(self, name, value):
        """Set output

        :param name: output name
        :param value: output value
        :raise ApiManagerError:
        """
        self.set_configs(key="outputs." + name, value=value)

    def get_actions(self, name=None):
        """Get actions

        :param name: action name
        :return: actions list
        :raise ApiManagerError:
        """
        if name is None:
            if self.actions is not None:
                actions = self.actions
            else:
                actions, tot = self.controller.get_resources(
                    parent=self.oid,
                    run_customize=False,
                    size=-1,
                    objdef=ComputeStackAction.objdef,
                )
        else:
            actions, tot = self.controller.get_resources(
                parent=self.oid,
                name=name,
                run_customize=False,
                size=-1,
                objdef=ComputeStackAction.objdef,
            )
            actions = actions[0]

        return actions

    def get_child_resources(self, uuid=None):
        """Get child resources

        :param uuid: action resource uuid
        :return: resources list
        :raise ApiManagerError:
        """
        if uuid is None:
            if self.resources is not None:
                resources = self.resources
            else:
                resources, tot = self.get_linked_resources(
                    link_type_filter="resource%",
                    run_customize=False,
                    size=-1,
                    authorize=False,
                )
        else:
            resources, tot = self.get_linked_resources(
                link_type="resource.%s" % uuid, run_customize=False, authorize=False
            )
            resources = resources[0]

        return resources

    @staticmethod
    def get_resource_class(resource_type):
        """get resource class

        :param resource_type:
        :return:
        """
        resource_class_name = ComputeStackV2.RESOURCE_TYPE.get(resource_type, None)
        if resource_class_name is None:
            raise ApiManagerError("resource type %s does not exist" % resource_type)
        resource_class = import_class(resource_class_name)
        return resource_class

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
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.inputs: list of stack inputs
        :param kvargs.inputs.x.name: input name
        :param kvargs.inputs.x.desc: input description
        :param kvargs.inputs.x.value: input default value
        :param kvargs.outputs: list of stack outputs
        :param kvargs.outputs.x.name: output name
        :param kvargs.outputs.x.desc: output description
        :param kvargs.outputs.x.value: output value
        :param kvargs.actions: list of stack actions
        :param kvargs.actions.x.name: action name
        :param kvargs.actions.x.desc: action description
        :param kvargs.actions.x.resource: stack action resource
        :param kvargs.actions.x.resource.type: action resource type
        :param kvargs.actions.x.resource.oid: action resource id
        :param kvargs.actions.x.resource.operation: action resource operation to execute
        :param kvargs.actions.x.params: action params like {"k1": "v1"}
        :return: kvargs
        :raise ApiManagerError:
        """
        # get zone
        compute_zone_id = kvargs.get("parent")
        compute_zone = container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(container)
        multi_avz = True

        inputs = {}
        for i in kvargs.pop("inputs"):
            inputs[i.get("name")] = i

        outputs = {}
        for o in kvargs.pop("outputs"):
            outputs[o.get("name")] = o

        actions = []
        for action in kvargs.get("actions"):
            # set stack container as stack resource container
            action["container"] = container.oid
            # set stack compute_zone as stack resource compute_zone
            action["compute_zone"] = compute_zone.oid

            action_name = action.get("name")
            action_resource = action.get("resource")

            # check action resource type
            res_type = action_resource.get("type", None)
            if res_type is not None:
                ComputeStackV2.get_resource_class(res_type)

            # check action resource uuid exists
            res_id = action_resource.get("oid", None)
            if res_id is not None:
                container.get_simple_resource(res_id)

            if res_type is None and res_id is None:
                raise ApiManagerError("at least one of resource type or resource id must be set")

            # parse action params with prefix '$$input.'
            regex_pattern = r"\$\$input\.[\-\w\d]+\$\$"
            params = {}
            for key, value in action.get("params", {}).items():
                if isinstance(value, str) and match(regex_pattern, ensure_str(value)) is not None:
                    input_name = value.replace("$$input.", "").replace("$$", "")
                    input_item = inputs.get(input_name, None)
                    if input_item is None:
                        container.logger.error("input %s input_name does not exist")
                        raise ApiManagerError("input %s input_name does not exist")
                    value = input_item.get("value")
                params[key] = value

            action["params"] = params
            actions.append(
                {
                    "name": action_name,
                    "desc": action.get("desc", action_name),
                    "orchestrator_tag": params.get("orchestrator_tag"),
                    "active": False,
                    "attribute": {
                        "resource": action_resource,
                        "params": params,
                    },
                }
            )

        attribute = {
            "inputs": inputs,
            "outputs": outputs,
        }
        kvargs["attribute"].update(attribute)
        kvargs["actions"] = actions

        # create task workflow
        steps = [
            ComputeStackV2.task_path + "create_resource_pre_step",
            ComputeStackV2.task_path + "create_stack_actions_step",
        ]
        compute_stack_name = kvargs.get("name")
        for action in actions:
            action_name = compute_stack_name + "-" + action.get("name")
            step = {
                "step": ComputeStackV2.task_path + "run_stack_action_step",
                "args": [action_name],
            }
            steps.append(step)
        steps.append(ComputeStackV2.task_path + "set_stack_outputs_step")

        # set monitoring su ComputeInstance collegato
        enabled_monitoring = kvargs.get("enabled_monitoring", False)
        if enabled_monitoring:
            steps.append(ComputeStackV2.task_path + "set_monitoring_step")

        additional_steps = kvargs.pop("additional_steps")
        if additional_steps:
            steps.extend(additional_steps)

        steps.append(ComputeStackV2.task_path + "create_resource_post_step")

        kvargs["steps"] = steps

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used in container resource_import_factory method.

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
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :param kvargs.configs.charset: db charset [default=latin1]
        :param kvargs.configs.timezone: db timezone [default=Europe/Rome]
        :param kvargs.configs.engine: db engine
        :param kvargs.configs.version: db engine version
        :param kvargs.configs.pwd: db passwords
        :param kvargs.configs.pwd.admin: db admin password
        :return: kvargs
        :raise ApiManagerError:
        """
        physical_id = kvargs.pop("physical_id")
        resource = controller.get_resource(physical_id)

        # get compute zone
        compute_zone = resource.get_parent()
        compute_zone.set_container(container)
        compute_zone.check_active()
        kvargs["parent"] = compute_zone.oid
        kvargs["objid"] = "%s//%s" % (compute_zone.objid, id_gen())

        inputs = {}
        for i in kvargs.pop("inputs"):
            inputs[i.get("name")] = i

        outputs = {}
        for o in kvargs.pop("outputs"):
            outputs[o.get("name")] = o

        actions = []
        for action in kvargs.get("actions"):
            # set stack container as stack resource container
            action["container"] = container.oid
            # set stack compute_zone as stack resource compute_zone
            action["compute_zone"] = compute_zone.oid

            action_name = action.get("name")
            action_resource = action.get("resource")

            # check action resource type
            res_type = action_resource.get("type", None)
            if res_type is not None:
                ComputeStackV2.get_resource_class(res_type)

            # check action resource uuid exists
            res_id = action_resource.get("oid", None)
            if res_id is not None:
                container.get_simple_resource(res_id)

            if res_type is None and res_id is None:
                raise ApiManagerError("at least one of resource type or resource id must be set")

            # parse action params with prefix '$$input.'
            regex_pattern = r"\$\$input\.[\-\w\d]+\$\$"
            params = {}
            for key, value in action.get("params", {}).items():
                if isinstance(value, str) and match(regex_pattern, ensure_str(value)) is not None:
                    input_name = value.replace("$$input.", "").replace("$$", "")
                    input_item = inputs.get(input_name, None)
                    if input_item is None:
                        container.logger.error("input %s input_name does not exist")
                        raise ApiManagerError("input %s input_name does not exist")
                    value = input_item.get("value")
                params[key] = value

            action["params"] = params
            actions.append(
                {
                    "name": action_name,
                    "desc": action.get("desc", action_name),
                    "orchestrator_tag": params.get("orchestrator_tag"),
                    "active": False,
                    "attribute": {
                        "resource": action_resource,
                        "params": params,
                    },
                }
            )

        attribute = {
            "inputs": inputs,
            "outputs": outputs,
        }
        kvargs["attribute"].update(attribute)
        kvargs["actions"] = actions

        # create task workflow
        steps = [
            ComputeStackV2.task_path + "create_resource_pre_step",
            ComputeStackV2.task_path + "create_stack_actions_step",
        ]
        compute_stack_name = kvargs.get("name")
        for action in actions:
            action_name = compute_stack_name + "-" + action.get("name")
            step = {
                "step": ComputeStackV2.task_path + "run_stack_action_step",
                "args": [action_name],
            }
            steps.append(step)
        steps.append(ComputeStackV2.task_path + "set_stack_outputs_step")

        additional_steps = kvargs.pop("additional_steps", None)
        if additional_steps:
            steps.extend(additional_steps)

        steps.append(ComputeStackV2.task_path + "create_resource_post_step")

        kvargs["steps"] = steps

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method."""
        # compute_zone_id = kvargs.get('parent')
        compute_zone_id = self.parent_id
        compute_zone = self.container.get_simple_resource(compute_zone_id)
        compute_zone.check_active()
        compute_zone.set_container(self.container)

        actions = []
        for action in kvargs.get("actions", []):
            action_name = action.get("name")
            action_params = action.get("params", {})
            action_resource = action.get("resource")

            actions.append(
                {
                    "name": action_name,
                    "desc": action.get("desc", action_name),
                    "container": self.container.oid,
                    "compute_zone": compute_zone.oid,
                    "orchestrator_tag": action_params.get("orchestrator_tag"),
                    "active": False,
                    "attribute": {
                        "resource": action_resource,
                        "params": action_params,
                    },
                }
            )

        kvargs["actions"] = actions

        # update task workflow
        steps = [
            ComputeStackV2.task_path + "update_resource_pre_step",
            ComputeStackV2.task_path + "create_stack_actions_step",
        ]
        for action in actions:
            action_name = self.name + "-" + action.get("name")
            step = {
                "step": ComputeStackV2.task_path + "run_stack_action_step",
                "args": [action_name],
            }
            steps.append(step)

        additional_steps = kvargs.pop("additional_steps", [])
        if additional_steps:
            steps.extend(additional_steps)

        steps.append(ComputeStackV2.task_path + "update_resource_post_step")

        kvargs["steps"] = steps

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
        kvargs["child_num"] = 0
        preserve = kvargs.get("preserve", False)

        # get stacks
        # resources, total = self.get_linked_resources(link_type_filter='relation%')
        # actions, total = self.get_linked_resources(link_type_filter='action%')
        actions = self.get_actions()

        # childs = [p.oid for p in resources]
        # childs.extend([p.oid for p in actions])

        actions.reverse()

        # create task workflow
        steps = [
            ComputeStackV2.task_path + "expunge_resource_pre_step",
        ]
        for action in actions:
            if preserve is False:
                steps.append(
                    {
                        "step": ComputeStackV2.task_path + "remove_stack_resource_step",
                        "args": [action.oid],
                    }
                )
            steps.append(
                {
                    "step": ComputeStackV2.task_path + "remove_stack_action_step",
                    "args": [action.oid],
                }
            )
        steps.append(ComputeStackV2.task_path + "expunge_resource_post_step")
        kvargs["steps"] = steps

        return kvargs

    def send_action(self, action, *args, **kvargs):
        """Send action to stack

        :param action: action to execute. Required signature action(*args, **kvargs)
        :param args: custom params to send to action
        :param kvargs: custom params to send to action

        :return: kvargs
        :raise ApiManagerError:
        """
        self.verify_permisssions(action="update")

        res = action(self.controller, self, *args, **kvargs)
        self.logger.debug("Send action %s to stack %s" % (action.__name__, self.uuid))
        return res

    #
    # metrics
    #
    def get_metrics(self):
        """Get resource metrics

        :return: a dict like this

        {
            "id": "1",
            "uuid": "vm1",
            "metrics": [
                    {
                        "key": "ram",
                        "value: 10,
                        "type": 1,
                        "unit": "GB"
                    }],
            "extraction_date": "2018-03-04 12:00:34 200",
            "resource_uuid": "12u956-2425234-23654573467-567876"

        }
        """
        prefix = ""
        if self.get_stack_type() == "sql_stack":
            if self.get_stack_engine().get("engine") == "mysql":
                prefix = "db_mysql_"
            elif self.get_stack_engine().get("engine") == "mariadb":
                prefix = "db_mariadb_"
            elif self.get_stack_engine().get("engine") == "postgresql":
                prefix = "db_pgsql_"
            elif self.get_stack_engine().get("engine") == "oracle":
                prefix = "db_ora_"
            elif self.get_stack_engine().get("engine") == "sqlserver":
                prefix = "db_mssql_"
        elif self.get_stack_type() == "app_stack":
            if self.get_stack_engine().get("engine") == "apache-php":
                prefix = "app_php_"

        metrics = {
            "%spower_on" % prefix: 0,
            "%svcpu" % prefix: 0,
            "%sgbram" % prefix: 0,
            "%sboot_gbdisk_low" % prefix: 0,
            "%sbck_gbdisk_low" % prefix: 0,
            "%sdata_gbdisk_low" % prefix: 0,
            "%sgbdisk_low" % prefix: 0,
            "%sgbdisk_hi" % prefix: 0,
            "%slic" % prefix: 0,
        }

        metric_units = {
            "%spower_on" % prefix: "#",
            "%svcpu" % prefix: "#",
            "%sgbram" % prefix: "GB",
            "%sboot_gbdisk_low" % prefix: "GB",
            "%sbck_gbdisk_low" % prefix: "GB",
            "%sdata_gbdisk_low" % prefix: "GB",
            "%sgbdisk_low" % prefix: "GB",
            "%sgbdisk_hi" % prefix: "GB",
            "%slic" % prefix: "#",
        }

        for resource in self.get_child_resources():
            if isinstance(resource, ComputeInstance):
                volumes = resource.get_volumes()
                resource.post_get()

                # fv - metriche lette da hypervisor
                # if resource.is_running() is True and resource.flavor is not None:
                #     flavor = resource.flavor.get_configs()
                #     metrics["%svcpu" % prefix] += flavor.get("vcpus", 0)
                #     metrics["%sgbram" % prefix] += flavor.get("memory", 0) / 1024

                physical_server = resource.get_physical_server()
                if physical_server is not None:
                    data = physical_server.info().get("details")
                    memory = 0
                    cpu = 0
                    if data.get("state") == "poweredOn":
                        metrics["%spower_on" % prefix] += 1

                        memory = data.get("memory")
                        if memory is None:
                            memory = data.get("ram")
                        metrics["%sgbram" % prefix] += memory / 1024

                        cpu = data.get("cpu")
                        metrics["%svcpu" % prefix] += cpu

                        resource.set_configs("quotas.database.cores", cpu)
                        resource.set_configs("quotas.database.ram", memory)

                        if resource.flavor is not None:
                            flavor = resource.flavor.get_configs()
                            flavor_cpu = flavor.get("vcpus", 0)
                            flavor_memory = flavor.get("memory", 0) / 1024
                            if flavor_cpu != metrics["%svcpu" % prefix] or flavor_memory != metrics["%sgbram" % prefix]:
                                self.logger.warning(
                                    "+++++ resource uuid: %s - flavor cpu/ram %s/%s different from real ones %s/%s"
                                    % (
                                        self.uuid,
                                        flavor_cpu,
                                        flavor_memory,
                                        metrics["%svcpu" % prefix],
                                        metrics["%sgbram" % prefix],
                                    )
                                )

                sum_size_bootable = 0
                sum_size_backup = 0
                sum_size_data = 0
                self.logger.debug("+++++ volumes: %s" % volumes)
                for v in volumes:
                    from beehive_resource.plugins.provider.entity.volume import (
                        ComputeVolume,
                    )

                    computeVolume: ComputeVolume = v

                    from beehive_resource.controller import ResourceController

                    resourceController: ResourceController = self.controller
                    kvargs = {"resource": computeVolume.uuid}
                    tags, total = resourceController.get_tags(**kvargs)
                    # self.logger.debug('+++++ tags: %s' % tags)
                    # self.logger.debug('+++++ total: %s' % total)
                    is_backup = False
                    for tag in tags:
                        from beehive_resource.container import ResourceTag

                        resourceTag: ResourceTag = tag
                        # self.logger.debug('+++++ resourceTag: %s' % resourceTag)
                        # tag da definire
                        if resourceTag.name == "nws$volume_bck":
                            is_backup = True
                    # self.logger.debug('+++++ is_backup: %s' % is_backup)
                    # self.logger.debug('+++++ is_bootable(): %s' % computeVolume.is_bootable())

                    if computeVolume.is_bootable():
                        sum_size_bootable += computeVolume.get_size()
                    elif is_backup:
                        sum_size_backup += computeVolume.get_size()
                    else:
                        sum_size_data += computeVolume.get_size()

                self.logger.debug("+++++ sum_size_bootable: %s" % sum_size_bootable)
                self.logger.debug("+++++ sum_size_backup: %s" % sum_size_backup)
                self.logger.debug("+++++ sum_size_data: %s" % sum_size_data)

                metrics["%sboot_gbdisk_low" % prefix] += sum_size_bootable
                metrics["%sbck_gbdisk_low" % prefix] += sum_size_backup
                metrics["%sdata_gbdisk_low" % prefix] += sum_size_data

                metrics["%sgbdisk_low" % prefix] += sum([v.get_size() for v in volumes])
                self.logger.debug("+++++ sgbdisk_low: %s" % metrics["%sgbdisk_low" % prefix])

        if self.get_stack_engine().get("engine") == "oracle" or self.get_stack_engine().get("engine") == "sqlserver":
            metrics["%slic" % prefix] = 1

        metrics = [{"key": k, "value": v, "type": 1, "unit": metric_units.get(k)} for k, v in metrics.items()]
        res = {
            "id": self.oid,
            "uuid": self.uuid,
            "resource_uuid": self.uuid,
            "type": self.objdef,
            "metrics": metrics,
            "extraction_date": format_date(datetime.today()),
        }

        self.logger.debug("Get compute stack %s metrics: %s" % (self.uuid, res))
        return res

    #
    # actions
    #
    # @staticmethod
    # def set_ansible_ssh_common_args(data, name, compute_zone, username='root'):
    #     # ansible_ssh_common_args: '-o ProxyCommand="sshpass -p mypass ssh -o StrictHostKeyChecking=no -W %h:%p -q ' \
    #     #                          'root@84.1.2.3 -p 1"'
    #     bastion_host = compute_zone.get_bastion_host()
    #     if bastion_host is None:
    #         return data
    #     params = {
    #         'username': username,
    #         'pwd':  bastion_host.get_credential(username=username).get('password'),
    #         'host': bastion_host.public_host,
    #         'port': bastion_host.public_port
    #     }
    #     ansible_ssh_common_args = '-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no ' \
    #                               '-o ProxyCommand="sshpass -p {pwd} ssh -o UserKnownHostsFile=/dev/null ' \
    #                               '-o StrictHostKeyChecking=no -W %h:%p -q ' \
    #                               '{username}@{host} -p {port}"'.format(**params)
    #     compute_zone.logger.warn(ansible_ssh_common_args)
    #     data['params']['extra_vars']['ansible_ssh_common_args'] = ansible_ssh_common_args
    #     # data['params']['extra_vars']['ansible_host'] = \
    #     #     '$$action_resource.%s-create_server1::vpcs.0.fixed_ip.ip$$' % name
    #     data['params']['extra_vars']['ansible_connection'] = 'ssh'
    #     data['params']['extra_vars']['ansible_python_interpreter'] = '/usr/bin/python'
    #
    #     return data

    @staticmethod
    def set_replica_args(
        data,
        name,
        replica,
        replica_arch_type,
        replica_role,
        replica_sync_type,
        replica_ip_master,
        replica_user,
        replica_pwd,
        remove_replica,
    ):
        if replica:
            # this is to tell ansible playbook to handle multi-master config
            if replica_arch_type == "MM":
                replica_role = "MM"

            data["params"]["extra_vars"]["p_mysql_replica_flag"] = replica * 1
            data["params"]["extra_vars"]["p_mysql_replica_arch_type"] = replica_arch_type
            data["params"]["extra_vars"]["p_mysql_instance_replica_role"] = replica_role
            data["params"]["extra_vars"]["p_mysql_replica_sync_type"] = replica_sync_type
            data["params"]["extra_vars"]["p_mysql_replica_ip_master"] = replica_ip_master
            data["params"]["extra_vars"]["p_mysql_replica_server_id"] = (
                "$$action_resource.%s-create_server1::id$$" % name
            )
            data["params"]["extra_vars"]["p_mysql_replica_username"] = replica_user
            data["params"]["extra_vars"]["p_mysql_replica_password"] = replica_pwd
            data["params"]["extra_vars"]["p_mysql_remove_replica_flag"] = remove_replica * 1

        return data


class ComputeStackAction(Resource):
    objdef = "Provider.ComputeZone.ComputeStackV2.ComputeStackAction"
    objname = "action"
    objdesc = "Provider ComputeStack V2 Action"
    task_path = "beehive_resource.plugins.provider.task_v2.stack_v2.StackV2SqlTask."


class ComputeStackMysqlAction(Resource):
    objdef = "Provider.ComputeZone.ComputeStackV2.ComputeStackMysqlAction"
    objname = "mysql action"
    objdesc = "Provider ComputeStack V2 MySQL Action"
    task_path = "beehive_resource.plugins.provider.task_v2.stack_v2.StackV2MysqlTask."


class ComputeStackPostgresqlAction(Resource):
    objdef = "Provider.ComputeZone.ComputeStackV2.ComputeStackPostgresqlAction"
    objname = "postgresql action"
    objdesc = "Provider ComputeStack V2 PostgreSQL Action"
    task_path = "beehive_resource.plugins.provider.task_v2.stack_v2.StackV2PostgresqlTask."
