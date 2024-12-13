# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from re import match
from six import ensure_str
from beecell.simple import id_gen, dict_get
from beehive.common.task_v2 import task_step, run_sync_task, TaskError
from beehive_resource.model import ResourceState
from beehive_resource.plugins.provider.entity.stack_v2 import (
    ComputeStackV2,
    ComputeStackAction,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.provider.entity.volume import ComputeVolume


class StackV2Task(AbstractProviderResourceTask):
    """Stack V2 task"""

    name = "stack_v2_task"
    entity_class = ComputeStackV2

    regex_pattern = r"\$\$(action_resource|resource)\.[\-_\w\d\.\:]+\$\$"

    @staticmethod
    @task_step()
    def create_stack_actions_step(task, step_id, params, *args, **kvargs):
        """Create stack action resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        actions = params.pop("actions")

        compute_stack = task.get_simple_resource(oid)
        provider = task.get_container(cid)

        params["actions"] = []
        for action in actions:
            action["parent"] = oid
            action["name"] = compute_stack.name + "-" + action["name"]
            action_resource, code = provider.resource_factory(ComputeStackAction, **action)
            res_uuid = action_resource["uuid"]
            resource = task.get_simple_resource(res_uuid)
            action["id"] = resource.oid
            resource.update_internal(active=False, state=ResourceState.PENDING)
            task.progress(step_id, msg="create stack %s action %s" % (oid, res_uuid))
            params["actions"].append(action)

        return oid, params

    @staticmethod
    @task_step()
    def run_stack_action_step(task, step_id, params, action_name, *args, **kvargs):
        """Run stack action

        :param task: parent celery task
        :param str step_id: step id
        :param action_name: action name
        :param dict params: step params
        :return: resource_id, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        compute_stack = task.get_simple_resource(oid)
        compute_stack.set_container(provider)
        stack_action = compute_stack.get_actions(name=action_name)
        stack_action.set_container(provider)

        # change action state
        stack_action.update_state(ResourceState.BUILDING)

        # run command to resource
        try:
            resource_id = StackV2Task.exec_resource_operation(task, step_id, compute_stack, stack_action)
        except:
            stack_action.update_internal(state=ResourceState.ERROR)
            raise

        # update action
        stack_action.update_internal(state=ResourceState.ACTIVE, active=True)

        return resource_id, params

    @staticmethod
    def exec_resource_operation(task, step_id, compute_stack, action, **params):
        """exec resource operation

        :param task: parent celery task
        :param step_id: step id
        :param compute_stack: compute stack resource
        :param action: action resource
        :param dict params: step params
        :return: resource id, params
        """
        action_id = action.oid
        action_resource = action.get_attribs(key="resource")
        action_params = action.get_attribs(key="params")
        resource_class = ComputeStackV2.get_resource_class(action_resource.get("type", None))
        resource_operation = action_resource.get("operation", None)
        action_params["sync"] = True

        # parse action params with '$$action.' or '$$resource.' as prefix and '$$' as suffix
        StackV2Task.parse_stack_action_params_v2(task, step_id, compute_stack, action_params, StackV2Task.regex_pattern)

        if resource_operation == "create":
            # uncomment only if you run 'stack' (not to be confused with '<db> stack', e.g. 'sql stack') unit tests
            # action_params['name'] = compute_stack.name + '-' + action_params['name']
            attribute = {}
            res, code = action.container.resource_factory(
                resource_class,
                ext_id=None,
                active=False,
                has_quotas=False,
                attribute=attribute,
                tags="",
                **action_params,
            )
            # link resource to compute stack
            resource_id = res["uuid"]
            action.set_configs(key="resource.id", value=resource_id)
            compute_stack.add_link(
                "stack-resource-%s" % id_gen(),
                "resource.%s" % resource_id,
                resource_id,
                attributes={},
            )
            task.progress(
                step_id,
                msg="link resource %s to stack %s" % (resource_id, compute_stack.oid),
            )

            if res.get("task", None) is not None:
                run_sync_task(res, task, step_id)
            task.progress(step_id, msg="create action %s resource %s" % (action_id, resource_id))
        elif resource_operation == "import":
            # uncomment only if you run 'stack' (not to be confused with '<db> stack', e.g. 'sql stack') unit tests
            # action_params['name'] = compute_stack.name + '-' + action_params['name']
            # attribute = {}
            # res, code = action.container.resource_factory(resource_class, ext_id=None, active=False, has_quotas=False,
            #                                               attribute=attribute, tags='', **action_params)
            # link resource to compute stack
            resource_id = action_params["uuid"]
            action.set_configs(key="resource.id", value=resource_id)
            compute_stack.add_link(
                "stack-resource-%s" % id_gen(),
                "resource.%s" % resource_id,
                resource_id,
                attributes={},
            )
            task.progress(
                step_id,
                msg="link resource %s to stack %s" % (resource_id, compute_stack.oid),
            )

            # if res.get('task', None) is not None:
            #     run_sync_task(res, task, step_id)
            task.progress(step_id, msg="import action %s resource %s" % (action_id, resource_id))
        else:
            resource_id = action_params.get("oid", None)
            if resource_id is None:
                raise TaskError("resource id cannot be null at this point")

            resource = task.get_resource(resource_id)
            func = getattr(resource, resource_operation, None)
            if func is None:
                raise TaskError(
                    "operation %s in resource %s does not exist" % (resource_operation, resource.__class__.__name__)
                )

            try:
                res = func(**action_params)
            except (AttributeError, TypeError) as ex:
                raise TaskError(
                    "operation %s in resource class %s can not be called in stack"
                    % (resource_operation, resource.__class__.__name__)
                )

            if isinstance(res, list) or isinstance(res, tuple):
                res = res[0]
            if res.get("task", None) is not None:
                run_sync_task(res, task, step_id)
            task.progress(
                step_id,
                msg="run action %s resource %s operation %s" % (action_id, resource_id, resource_operation),
            )

        return resource_id

    @staticmethod
    @task_step()
    def set_stack_outputs_step(task, step_id, params, *args, **kvargs):
        """Update stack outputs

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource_id, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        compute_stack = task.get_simple_resource(oid)
        compute_stack.set_container(provider)

        outputs = compute_stack.get_outputs()
        for output in list(outputs.values()):
            name = output.get("name")
            value = output.get("value")
            if isinstance(value, str) and match(StackV2Task.regex_pattern, ensure_str(value)) is not None:
                data = StackV2Task.get_attrib_value_v2(task, compute_stack, value)
                output["value"] = data
                compute_stack.set_output(name, output)
                task.progress(step_id, msg="set stack %s output %s to %s" % (oid, name, data))

        return oid, params

    @staticmethod
    @task_step()
    def set_monitoring_step(task, step_id, params, *args, **kvargs):
        """Update stack outputs

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource_id, params
        """
        try:
            print("+++++ AAA set_monitoring_step")
            cid = params.get("cid")
            oid = params.get("id")

            provider = task.get_container(cid)
            compute_stack: ComputeStackV2 = task.get_simple_resource(oid)
            compute_stack.set_container(provider)

            for resource in compute_stack.get_child_resources():
                from beehive_resource.plugins.provider.entity.instance import ComputeInstance

                if isinstance(resource, ComputeInstance):
                    print("+++++ AAA set_monitoring_step - resource %s" % resource)
                    computeInstance: ComputeInstance = resource

                    resource.set_configs(key="monitoring_enabled", value=True)

                    # res containers synchronizes every 4 hours
                    from datetime import datetime, timedelta

                    dt = datetime.now()
                    monitoring_wait_sync_till = dt + timedelta(hours=4)
                    str_monitoring_wait_sync_till = monitoring_wait_sync_till.strftime("%m/%d/%Y, %H:%M:%S")
                    resource.set_configs(key="monitoring_wait_sync_till", value=str_monitoring_wait_sync_till)
                    print(
                        "+++++ AAA set_monitoring_step - str_monitoring_wait_sync_till %s"
                        % str_monitoring_wait_sync_till
                    )

        except Exception as err:
            msg = str(err)
            # print("+++++ AAA set_monitoring_step - ex %s" % ex)
            print("+++++ AAA set_monitoring_step - error")
            print("+++++ AAA set_monitoring_step - msg %s" % msg)

        return oid, params

    @staticmethod
    @task_step()
    def add_stack_links_step(task, step_id, params, replica_master, *args, **kvargs):
        """Create links among the nodes of the replication system

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param replica_master: id, uuid or name of master server in db replication system
        :return: True (dummy value), params
        """
        cid = params.get("cid")
        oid = params.get("id")

        # get compute stack object
        provider = task.get_container(cid)
        compute_stack = task.get_simple_resource(oid)
        compute_stack.set_container(provider)

        # get master compute stack object
        master_stack = task.get_simple_resource(replica_master)

        # create link from current compute stack to master compute stack
        compute_stack.add_link(
            name="stack-replica-%s" % id_gen(),
            type="replica.%s" % compute_stack.uuid,
            end_resource=master_stack.oid,
            attributes={},
        )
        task.progress(
            step_id,
            msg="link stack %s to stack %s" % (compute_stack.oid, master_stack.oid),
        )
        # create link from master compute stack to current compute stack
        master_stack.add_link(
            name="stack-replica-%s" % id_gen(),
            type="replica.%s" % master_stack.uuid,
            end_resource=compute_stack.oid,
            attributes={},
        )
        task.progress(
            step_id,
            msg="link stack %s to stack %s" % (master_stack.oid, compute_stack.oid),
        )

        return True, params

    @staticmethod
    @task_step()
    def delete_stack_links_step(task, step_id, params, replica_master, *args, **kvargs):
        """Delete links among the nodes of the replication system

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param replica_master: id, uuid or name of master server in db replication system
        :return: True (dummy value), params
        """
        cid = params.get("cid")
        oid = params.get("id")

        # get compute stack object
        provider = task.get_container(cid)
        compute_stack = task.get_simple_resource(oid)
        compute_stack.set_container(provider)

        # get master compute stack object
        master_stack = task.get_simple_resource(replica_master)

        # delete link from current compute stack to master compute stack
        compute_stack.del_link(master_stack.oid)
        task.progress(
            step_id,
            msg="delete link from stack %s to stack %s" % (compute_stack.oid, master_stack.oid),
        )
        # delete link from current compute stack to master compute stack
        master_stack.del_link(compute_stack.oid)
        task.progress(
            step_id,
            msg="delete link from stack %s to stack %s" % (master_stack.oid, compute_stack.oid),
        )

        return True, params

    @staticmethod
    @task_step()
    def remove_stack_action_step(task, step_id, params, action_id, *args, **kvargs):
        """Remove stack action

        :param task: parent celery task
        :param str step_id: step id
        :param action_id: action id
        :param dict params: step params
        :return: action_id, params
        """
        # cid = params.get('cid')
        oid = params.get("id")

        # compute_stack = task.get_simple_resource(oid)
        action = task.get_simple_resource(action_id)

        action.update_state(ResourceState.EXPUNGING)
        action.expunge()
        task.progress(step_id, msg="remove stack %s action %s" % (oid, action.uuid))

        return action_id, params

    @staticmethod
    @task_step()
    def remove_stack_resource_step(task, step_id, params, action_id, *args, **kvargs):
        """Remove stack action resource

        :param task: parent celery task
        :param str step_id: step id
        :param action_id: action id
        :param dict params: step params
        :return: action_id, params
        """
        oid = params.get("id")

        action = task.get_simple_resource(action_id)
        resource_id = action.get_attribs(key="resource.id")
        # preserve = action.get_attribs(key='resource.preserve')

        action.update_internal(state=ResourceState.DELETING, active=False)

        # update action and remove resource
        if resource_id is None or resource_id == "":
            task.progress(
                step_id,
                msg="no stack %s action %s resource to delete. do nothing" % (oid, action.uuid),
            )
        else:
            resource = task.get_resource(resource_id)
            res, code = resource.expunge(sync=True)

            # follow sub task
            if res.get("task", None) is not None:
                run_sync_task(res, task, step_id)

            action.set_configs(key="resource.id", value="")
            task.progress(step_id, msg="remove stack %s action %s resource" % (oid, action.uuid))

        return action_id, params

    #
    # Utility methods
    #

    # -----------------------
    # Version 1 - NO MORE USED
    # $$resource.<resource_name>::<k1>...<kN>$$
    # e.g. $$resource._testlab1-prv-instance-for-dbaas-01::vpcs.0.fixed_ip.ip$$
    # -----------------------

    @staticmethod
    def parse_stack_action_params(task, step_id, action_params, pattern):
        """Walks through the elements of a complex dictionary and parse its values matching to the regex pattern.

        :param task: parent Celery task
        :param step_id: step id
        :param action_params: dictionary to visit and parse
        :param pattern: regex pattern to be satisfied
        :return:
        """
        for key, value in action_params.items():
            if isinstance(value, str) and match(pattern, ensure_str(value)) is not None:
                data = StackV2Task.get_attrib_value(task, value)
                action_params[key] = data
                task.progress(step_id, msg="set stack action param %s to %s" % (key, data))
            elif isinstance(value, str):
                continue
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        StackV2Task.parse_stack_action_params(task, step_id, item, pattern)
            elif isinstance(value, dict):
                StackV2Task.parse_stack_action_params(task, step_id, value, pattern)

    @staticmethod
    def get_attrib_value(task, ref):
        """Get a value from a dictionary. The dictionary is the output of resource.detail(), and the key is 'attrib'.
        The key can be composed (e.g. vpcs.0.fixed_ip.ip) in order to get a field in a complex and nested dict that
        contains other dict, list and string.

        :param task: parent Celery task
        :param ref: string to parse that contains a reference to the resource and a reference to the key to search
        :return: dictionary value
        """
        ref = ref.replace("$$resource.", "").replace("$$", "")
        res_id, attrib = ref.split("::")
        resource = task.get_resource(res_id)
        data = dict_get(resource.detail(), attrib)
        return data

    # -----------------------
    # Version 2
    # Manage two markers:
    # $$action_resource.<action_name>::<k1>...<kN>$$
    #   e.g. $$action_resource._testlab1-prv-mysql-stack-01-create_server1::vpcs.0.fixed_ip.ip$$
    # $$resource.<resource_name>::<k1>...<kN>$$
    #   e.g. $$resource._testlab1-prv-instance-for-dbaas-01::runstate$$
    # -----------------------

    @staticmethod
    def parse_stack_action_params_v2(task, step_id, compute_stack, action_params, pattern):
        """Walks through the elements of a complex dictionary and parse its values matching to the regex pattern.

        :param task: parent Celery task
        :param step_id: step id
        :param compute_stack: compute stack resource
        :param action_params: dictionary to visit and parse
        :param pattern: regex pattern to be satisfied
        :return:
        """
        for key, value in action_params.items():
            if isinstance(value, str) and match(pattern, ensure_str(value)) is not None:
                data = StackV2Task.get_attrib_value_v2(task, compute_stack, value)
                action_params[key] = data
                task.progress(step_id, msg="set stack action param %s to %s" % (key, data))
            elif isinstance(value, str):
                continue
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        StackV2Task.parse_stack_action_params_v2(task, step_id, compute_stack, item, pattern)
            elif isinstance(value, dict):
                StackV2Task.parse_stack_action_params_v2(task, step_id, compute_stack, value, pattern)

    @staticmethod
    def get_attrib_value_v2(task, compute_stack, ref):
        """Get a value from a dictionary. The dictionary is the output of resource.detail(), and the key is 'attrib'.
        The key can be composed (e.g. vpcs.0.fixed_ip.ip) in order to get a field in a complex and nested dict that
        contains other dict, list and string.

        :param task: parent Celery task
        :param compute_stack: compute stack resource
        :param ref: string to parse that contains a reference to the resource and a reference to the key to search
        :return: dictionary value
        """
        if "action_resource" in ref:
            # remove prefix and suffix
            ref = ref.replace("$$action_resource.", "").replace("$$", "")
            # get action name
            action_name, res_attrib = ref.split("::")
            # get action object from name
            action = compute_stack.get_actions(name=action_name)
            # get action object id
            res_id = action.get_attribs(key="resource.id")
        else:
            # remove prefix and suffix
            ref = ref.replace("$$resource.", "").replace("$$", "")
            # get resource name
            res_id, res_attrib = ref.split("::")
        # get resource object from res id
        resource = task.get_resource(res_id)
        # get value from attrib
        data = dict_get(resource.detail(), res_attrib)
        return data


class StackV2SqlTask(AbstractProviderResourceTask):
    """Stack V2 mysql task"""

    name = "stack_v2_mysql_task"
    entity_class = ComputeStackV2

    @staticmethod
    @task_step()
    def sql_run_action_on_server_step(task, step_id, params, compute_instance_id, *args, **kvargs):
        """Run a given action on database server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param str compute_instance_id: id of compute instance linked to stack
        :return: oid, params
        """
        oid = params.get("id")
        operation = params.get("action_name")

        from beehive_resource.plugins.provider.entity.instance import ComputeInstance

        compute_instance: ComputeInstance = task.get_resource(compute_instance_id)
        task.progress(step_id, msg="get resource %s" % compute_instance.uuid)

        # manage cases that need some extra work
        if operation == "resize":
            # rename operation to fit with the compute instance method implementing the operation
            operation = "add_volume"
            volume_id = params.get("last_step_response")
            params.update({"data": {"action": {"add_volume": {"volume": volume_id}}}})

        params["sync"] = True
        prepared_task, code = compute_instance.action(operation, **params)
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Run %s action on db server %s" % (operation, compute_instance.uuid),
        )

        return oid, params

    @staticmethod
    @task_step()
    def sql_invoke_apply_customization_step(task, step_id, params, compute_instance_id, data, *args, **kvargs):
        """Call apply_customization method of ComputeInstance class, that runs the applied customization
        defined in data.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param str compute_instance_id: id of compute instance linked to stack
        :param dict data: params for applied customization
        :return: oid, params
        """
        oid = params.get("id")
        operation = params.get("action_name")
        compute_instance = task.get_resource(compute_instance_id)
        task.progress(step_id, msg="get resource %s" % compute_instance.oid)

        prepared_task, code = compute_instance.apply_customization(operation, data, sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Run %s action on server %s using applied customization" % (operation, compute_instance.oid),
        )

        return oid, params

    @staticmethod
    @task_step()
    def sql_enable_mailx_step(task, step_id, params, compute_instance_id, relayhost, domain, *args, **kvargs):
        """Install and configure mailx"""
        data = {
            "customization": "os-utility",
            "playbook": "install_mailx.yml",
            "extra_vars": {"relayhost": relayhost, "domain": domain},
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def haproxy_save_port(task, step_id, params, *args, **kvargs):
        """Get certificate from stdout of previous step and add to extra_vars

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        stackV2SqlTask: StackV2SqlTask = task
        stackV2SqlTask.logger.debug("+++++ haproxy_save_port - params: {}".format(params))
        stackV2SqlTask.logger.debug("+++++ haproxy_save_port - args: {}".format(args))
        stackV2SqlTask.logger.debug("+++++ haproxy_save_port - kvargs: {}".format(kvargs))

        shared_data = stackV2SqlTask.get_shared_data()
        stackV2SqlTask.logger.debug("+++++ haproxy_save_port - shared_data: {}".format(shared_data))
        stdout_data = stackV2SqlTask.get_stdout_data()
        stackV2SqlTask.logger.debug("+++++ haproxy_save_port - stdout_data: {}".format(stdout_data))

        haproxy_port = "???"

        # update resource attribute
        oid = params.get("id")
        resource = task.get_simple_resource(oid)
        resource.set_configs(key="haproxy_port", value=haproxy_port)
        task.progress(step_id, msg="Save resource %s haproxy port in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def sql_haproxy_registration_step(  # aaa useless?
        task,
        step_id,
        params,
        compute_instance_id,
        server_name,
        server_ip,
        engine_port,
        operation,
        *args,
        **kvargs,
    ):
        """Register db instance server on haproxy"""
        data = {
            "customization": "haproxy",
            "playbook": "manage_reg.yml",
            "extra_vars": {
                "server_name": server_name,
                "server_ip": server_ip,
                "engine_port": engine_port,
                "operation": operation,
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def sql_haproxy_deregistration_step(  # aaa useless?
        task,
        step_id,
        params,
        compute_instance_id,
        server_name,
        operation,
        *args,
        **kvargs,
    ):
        """Deregister db instance server from haproxy"""
        data = {
            "customization": "haproxy",
            "playbook": "manage_reg.yml",
            "extra_vars": {"server_name": server_name, "operation": operation},
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def sql_create_compute_volume_step(task, step_id, params, compute_instance_id, size, *args, **kvargs):
        """Create compute instance volume.

        :param task: parent celery task
        :param step_id: step id
        :param params: step params
        :param compute_instance_id: database server id
        :param size: volume size in GiB
        :return: the id of the created volume, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)

        compute_stack = task.get_simple_resource(oid)
        compute_stack_attribs = compute_stack.get_attribs()
        volume_flavor_name = compute_stack_attribs.get("volume_flavor")
        volume_flavor = task.get_simple_resource(volume_flavor_name)

        compute_instance = task.get_resource(compute_instance_id)
        compute_instance_attribs = compute_instance.get_attribs()
        site = compute_instance_attribs.get("availability_zone")
        orchestrator_type = compute_instance_attribs.get("type")
        has_quotas = compute_instance_attribs.get("has_quotas", True)

        volumes = compute_instance.detail().get("block_device_mapping")
        max_boot_idx = 0
        for volume in volumes:
            boot_idx = int(volume.get("boot_index"))
            max_boot_idx = max(max_boot_idx, boot_idx)
        next_boot_idx = max_boot_idx + 1

        volume_params = {
            "name": "%s-volume-%s" % (compute_instance.name, next_boot_idx),
            "parent": compute_instance.parent_id,
            "compute_zone": compute_instance.parent_id,
            "availability_zone": site,
            "size": size,
            "type": orchestrator_type,
            "flavor": volume_flavor.oid,
            "sync": True,
        }

        # create volume
        prepared_task, code = provider.resource_factory(ComputeVolume, has_quotas=has_quotas, **volume_params)
        volume_id = prepared_task["uuid"]

        # wait task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create volume %s in availability zone %s" % (volume_id, site))

        return volume_id, params

    @staticmethod
    @task_step()
    def sql_update_allocated_storage_step(task, step_id, params, size, *args, **kvargs):
        """Update allocated storage attribute value for compute stack resource.

        :param task: parent celery task
        :param step_id: step id
        :param params: step params
        :param size: the storage capacity of the db instance after resize
        :return: True (dummy value), params
        """
        oid = params.get("id")

        compute_stack = task.get_simple_resource(oid)
        compute_stack.set_configs(key="allocated_storage", value=size)

        task.progress(
            step_id,
            msg="Update allocated storage of stack %s: %s GiB" % (oid, str(size)),
        )
        return True, params


class StackV2MysqlTask(StackV2SqlTask):
    """Stack V2 mysql task"""

    name = "stack_v2_mysql_task"
    entity_class = ComputeStackV2

    @staticmethod
    @task_step()
    def mysql_manage_engine_step(task, step_id, params, compute_instance_id, *args, **kvargs):
        """Manage (i.e. start, stop, restart) database engine"""
        data = {
            "customization": "db-utility",
            "playbook": "manage.yml",
            "extra_vars": {
                "engine": params.get("engine"),
                "version": params.get("version"),
                "operation": params.get("action_name"),
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_add_db_step(task, step_id, params, compute_instance_id, db_name, charset, *args, **kvargs):
        """Create database and schema"""
        data = StackV2MysqlTask.mysql_commons(params)
        data["playbook"] = "DbMgmtMysql.yml"
        extras = {
            "p_mysql_db_name": db_name,
            "p_mysql_db_encoding": charset,
            "p_mysql_db_mgmt_type": "add",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_drop_db_step(task, step_id, params, compute_instance_id, db_name, *args, **kvargs):
        """Delete database"""
        data = StackV2MysqlTask.mysql_commons(params)
        data["playbook"] = "DbMgmtMysql.yml"
        extras = {"p_mysql_db_name": db_name, "p_mysql_db_mgmt_type": "delete"}
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_add_user_step(
        task,
        step_id,
        params,
        compute_instance_id,
        usr_name,
        usr_password,
        *args,
        **kvargs,
    ):
        """Create db user"""
        data = {
            "customization": "db-utility",
            "playbook": "manage.yml",
            "extra_vars": {
                "engine": params.get("engine"),
                "operation": params.get("action_name"),
                "p_port": params.get("port"),
                "p_admin_usr": params.get("admin_usr"),
                "p_admin_pwd": params.get("admin_pwd"),
                "p_usr_name": usr_name,
                "p_usr_pwd": usr_password,
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_change_pwd_step(
        task,
        step_id,
        params,
        compute_instance_id,
        usr_name,
        new_password,
        *args,
        **kvargs,
    ):
        """Update db user password"""
        data = StackV2MysqlTask.mysql_commons(params)
        data["playbook"] = "UserMgmtMysql.yml"
        extras = {
            "p_mysql_users": [{"name": usr_name, "pwd": new_password}],
            "p_mysql_user_mgmt_type": "chpwdusr",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_drop_user_step(task, step_id, params, compute_instance_id, usr_name, *args, **kvargs):
        """Delete db user"""
        data = StackV2MysqlTask.mysql_commons(params)
        data["playbook"] = "UserMgmtMysql.yml"
        extras = {
            "p_mysql_users": [{"name": usr_name}],
            "p_mysql_user_mgmt_type": "delusr",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_grant_privs_step(
        task,
        step_id,
        params,
        compute_instance_id,
        privileges,
        db_name,
        usr_name,
        *args,
        **kvargs,
    ):
        """Assign privileges to db user"""
        data = StackV2MysqlTask.mysql_commons(params)
        data["playbook"] = "UserMgmtMysql.yml"
        extras = {
            "p_mysql_users": [{"name": usr_name, "privs": "{}.*:{}".format(db_name, privileges)}],
            "p_mysql_user_mgmt_type": "addpriv",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_revoke_privs_step(
        task,
        step_id,
        params,
        compute_instance_id,
        privileges,
        db_name,
        usr_name,
        *args,
        **kvargs,
    ):
        """Revoke privileges from db user"""
        data = StackV2MysqlTask.mysql_commons(params)
        data["playbook"] = "UserMgmtMysql.yml"
        extras = {
            "p_mysql_users": [{"name": usr_name, "privs": "{} ON {}.*".format(privileges, db_name)}],
            "p_mysql_user_mgmt_type": "revokepriv",
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def mysql_install_extensions_step(
        task,
        step_id,
        params,
        compute_instance_id,
        ip_repository,
        extensions,
        *args,
        **kvargs,
    ):
        """Install db extension(s)"""
        data = {
            "customization": "mysql",
            "playbook": "extensionMgmtMysql.yml",
            "extra_vars": {
                "p_mysql_db_port": params.get("port"),
                "p_mysql_root_username": params.get("admin_usr"),
                "p_mysql_root_password": params.get("admin_pwd"),
                "p_ip_repository": ip_repository,
                "p_mysql_extensions": extensions,
                "p_mysql_db_restart": 1,
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    def mysql_commons(params):
        return {
            "customization": "mysql",
            "extra_vars": {
                "p_mysql_db_port": params.get("port"),
                "p_mysql_login_name": params.get("admin_usr"),
                "p_mysql_login_password": params.get("admin_pwd"),
            },
        }


class StackV2PostgresqlTask(StackV2SqlTask):
    """Stack V2 postgresql task"""

    name = "stack_v2_pgsql_task"
    entity_class = ComputeStackV2

    @staticmethod
    @task_step()
    def pgsql_manage_engine_step(task, step_id, params, compute_instance_id, *args, **kvargs):
        """Manage (i.e. start, stop, restart) database engine"""
        version = params.get("version")
        if version == "12.4":
            version = "12"
        data = {
            "customization": "db-utility",
            "playbook": "manage.yml",
            "extra_vars": {
                "engine": params.get("engine"),
                "version": version,
                "operation": params.get("action_name"),
            },
        }
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def pgsql_add_db_step(
        task,
        step_id,
        params,
        compute_instance_id,
        db_name,
        charset,
        schema_name,
        *args,
        **kvargs,
    ):
        """Create database"""
        data = StackV2PostgresqlTask.pgsql_commons(params)
        data["playbook"] = "dbMgmtPostgres.yml"
        extras = {
            "p_postgres_db_name": db_name,
            "p_postgres_schema_name": schema_name,
            "p_postgres_db_encoding": charset,
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def pgsql_drop_db_step(
        task,
        step_id,
        params,
        compute_instance_id,
        db_name,
        schema_name,
        *args,
        **kvargs,
    ):
        """Delete database"""
        data = StackV2PostgresqlTask.pgsql_commons(params)
        data["playbook"] = "dbMgmtPostgres.yml"
        extras = {
            "p_postgres_db_name": db_name,
            "p_postgres_schema_name": schema_name,
        }
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def pgsql_add_user_step(
        task,
        step_id,
        params,
        compute_instance_id,
        name,
        password,
        attribs,
        *args,
        **kvargs,
    ):
        """Create db user"""
        data = StackV2PostgresqlTask.pgsql_commons(params)
        data["playbook"] = "userMgmtPostgres.yml"
        user = {"name": name, "pwd": password, "attribs": attribs}
        extras = {"p_postgres_users": [user]}
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def pgsql_change_user_pwd_step(task, step_id, params, compute_instance_id, name, new_password, *args, **kvargs):
        """Update db user password"""
        data = StackV2PostgresqlTask.pgsql_commons(params)
        data["playbook"] = "userMgmtPostgres.yml"
        user = {"name": name, "pwd": new_password}
        extras = {"p_postgres_users": [user]}
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def pgsql_drop_user_step(task, step_id, params, compute_instance_id, name, force, *args, **kvargs):
        """Delete db user"""
        data = StackV2PostgresqlTask.pgsql_commons(params)
        data["playbook"] = "userMgmtPostgres.yml"
        user = {"name": name}
        extras = {"p_postgres_users": [user], "p_postgres_mgmt_force": force}
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    @task_step()
    def pgsql_manage_privs_step(
        task,
        step_id,
        params,
        compute_instance_id,
        privileges,
        db_name,
        schema_name,
        usr_name,
        *args,
        **kvargs,
    ):
        """Manage (i.e. grant or revoke) privileges to db user"""
        data = StackV2PostgresqlTask.pgsql_commons(params)
        data["playbook"] = "privsMgmtPostgres.yml"
        privs = {
            "privs": privileges,
            "db": db_name,
            "schema": schema_name,
            "user": usr_name,
        }
        extras = {"p_postgres_privs": [privs]}
        data["extra_vars"].update(extras)
        return StackV2SqlTask.sql_invoke_apply_customization_step(
            task, step_id, params, compute_instance_id, data, *args, **kvargs
        )

    @staticmethod
    def pgsql_commons(params):
        return {
            "customization": "postgresql",
            "extra_vars": {
                "p_postgres_db_port": params.get("port"),
                "p_postgres_login_username": params.get("admin_usr"),
                "p_postgres_login_password": params.get("admin_pwd"),
                "p_postgres_mgmt_action": params.get("action_name"),
            },
        }
