# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from time import sleep
from beecell.simple import truncate
from beehive.common.task_v2 import task_step, prepare_or_run_task, run_sync_task
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.openstack.entity.ops_heat import (
    OpenstackHeatStack,
    stack_entity_type_mapping,
)
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class StackTask(AbstractResourceTask):
    """Stack task"""

    name = "stack_task"
    entity_class = OpenstackHeatStack

    @staticmethod
    @task_step()
    def stack_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        template_uri = params.get("template_uri")
        parent_id = params.get("parent")
        name = params.get("name")
        environment = params.get("environment", None)
        parameters = params.get("parameters", None)
        files = params.get("files", None)
        tags = params.get("tags", "")
        stack_owner = params.get("owner")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # validate template
        heat = container.get_heat_resource()
        template = heat.validate_template(template_uri)
        task.progress(step_id, msg="Validate template %s" % template_uri)

        # create new stack
        stack = conn.heat.stack.create(
            stack_name=name,
            template=template,
            environment=environment,
            parameters=parameters,
            tags=tags,
            files=files,
            stack_owner=stack_owner,
        )
        stack_id = stack["id"]
        task.progress(step_id, msg="Create stack %s - Starting" % stack_id)

        # set ext_id
        container.update_resource(oid, ext_id=stack_id)
        task.progress(step_id, msg="Set stack remote openstack id %s" % stack_id)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackHeatStack.get_remote_stack(container.controller, stack_id, container, name, stack_id)
            status = inst.get("stack_status", None)
            if status == "CREATE_COMPLETE":
                break
            elif status == "CREATE_FAILED":
                reason = inst["stack_status_reason"]
                task.progress(step_id, msg="Create stack %s - Error: %s" % (stack_id, reason))
                raise Exception("Can not create stack %s: %s" % (stack_id, reason))

            task.progress(step_id, msg="Create stack %s - Wait" % stack_id)
            sleep(5)

        task.progress(step_id, msg="Create stack %s - Completed" % stack_id)

        # save current data in shared area
        params["ext_id"] = stack_id
        params["result"] = stack_id
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def register_child_entity_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        name = params.get("name")
        parent_id = params.get("parent")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        # get resources
        resources = conn.heat.stack.resource.list(stack_name=name, oid=ext_id)
        task.progress(step_id, msg="Get child resources: %s" % truncate(resources))

        """
        [{'resource_name': 'my_instance',
          'links': [{}],
          'logical_resource_id': 'my_instance',
          'creation_time': '2017-12-19T12:17:09Z',
          'resource_status': 'CREATE_COMPLETE',
          'updated_time': '2017-12-19T12:17:09Z',
          'required_by': [],
          'resource_status_reason': 'state changed',
          'physical_resource_id': '9d06ea46-6ab0-4e93-88b9-72f32de0cc31',
          'resource_type': 'OS::Nova::Server'}]
        """

        # get child resources objdef
        objdefs = {}
        res_ext_ids = []
        for item in resources:
            # TODO : router should need additional operation for internal port and ha network
            mapping = stack_entity_type_mapping[item["resource_type"]]
            if mapping is not None:
                objdefs[mapping] = None
                res_ext_ids.append(item["physical_resource_id"])
        task.progress(step_id, msg="get child resources objdef: %s" % objdefs)

        # run celery job
        if len(objdefs) > 0:
            params = {
                "cid": cid,
                "id": oid,
                "types": ",".join(objdefs.keys()),
                "new": True,
                "died": False,
                "changed": False,
            }
            params.update(container.get_user())
            task_name = "beehive_resource.task_v2.container.resource_container_task"
            child_task, code = prepare_or_run_task(container, task_name, params, sync=True)
            run_sync_task(child_task, task, step_id)

        # save current data in shared area
        params["res_ext_ids"] = res_ext_ids
        task.progress(step_id, msg="Update shared area")

        return oid, params

    @staticmethod
    @task_step()
    def link_child_entity_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        res_ext_ids = params.get("res_ext_ids")
        task.progress(step_id, msg="Get configuration params")

        # link child resource to stack
        task.get_session(reopen=True)
        stack = task.get_simple_resource(oid)
        for ext_id in res_ext_ids:
            child = task.get_resource_by_extid(ext_id)
            stack.add_link("%s-%s-stack-link" % (oid, child.oid), "stack", child.oid, attributes={})
            task.progress(step_id, msg="Link stack %s to child %s" % (oid, child.oid))

        return oid, params

    @staticmethod
    @task_step()
    def stack_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def stack_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        ext_id = params.get("ext_id")
        parent_id = params.get("parent_id")

        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn
        task.progress(step_id, msg="Get container %s" % cid)

        if task.is_ext_id_valid(ext_id) is True:
            res = container.get_resource_by_extid(ext_id)

            # get stack
            inst = OpenstackHeatStack.get_remote_stack(container.controller, ext_id, container, res.name, ext_id)

            # get all stack volumes
            volumes = res.get_stack_internal_resources(type="OS::Cinder::Volume")
            # task.logger.warn(volumes)
            for volume in volumes:
                # remove all the snapshots of the volume
                volume_ext_id = volume["physical_resource_id"]
                snapshots = conn.volume_v3.snapshot.list(volume_id=volume_ext_id)
                for snapshot in snapshots:
                    conn.volume_v3.snapshot.delete(snapshot["id"])
                    while True:
                        try:
                            conn.volume_v3.snapshot.get(snapshot["id"])
                            sleep(2)
                        except:
                            task.progress("Volume %s snapshot %s deleted" % (volume_ext_id, snapshot["id"]))
                            break

            # check stack
            # inst = conn.heat.stack.get(stack_name=res.name, oid=ext_id)
            if inst["stack_status"] != "DELETE_COMPLETE":
                # remove stack
                conn.heat.stack.delete(stack_name=res.name, oid=ext_id)
                task.progress(step_id, msg="Delete stack %s - Starting" % ext_id)

                # loop until entity is not deleted or get error
                while True:
                    inst = OpenstackHeatStack.get_remote_stack(
                        container.controller, ext_id, container, res.name, ext_id
                    )
                    status = inst.get("stack_status", None)
                    if status == "DELETE_COMPLETE":
                        break
                    elif status == "DELETE_FAILED":
                        err = "Delete stack %s - Error: %s" % (
                            ext_id,
                            inst.get("stack_status_reason", ""),
                        )
                        task.progress(step_id, msg=err)
                        raise Exception("Can not delete stack %s: %s" % (ext_id, inst.get("stack_status_reason", "")))

                    task.progress(step_id, msg="Delete stack %s - Wait" % ext_id)
                    sleep(2)

            res.update_internal(ext_id=None)
            task.progress(step_id, msg="Delete stack %s - Completed" % ext_id)

        return oid, params

    @staticmethod
    @task_step()
    def expunge_resource_post_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        objid = params.get("objid")

        container = task.get_container(cid)
        resources = task.get_orm_linked_resources(oid, link_type="stack", container_id=cid)

        # get child resources objdef
        objdefs = {}
        res_ids = []
        for item in resources:
            # TODO : router should need additional operation for internal port and ha network
            # objdefs[item.objdef] = None
            res_ids.append(item.id)
        for k, v in stack_entity_type_mapping.items():
            if v is not None:
                objdefs[v] = None
        task.progress(step_id, msg="Get child resources objdef: %s" % objdefs)
        task.progress(step_id, msg="Get child resources ext_id: %s" % res_ids)

        # # run celery job
        # if len(objdefs) > 0:
        #     params = {
        #         'cid': cid,
        #         'objid': objid,
        #         'types': ','.join(objdefs.keys()),
        #         'new': False,
        #         'died': True,
        #         'changed': False
        #     }
        #     params.update(container.get_user())
        #     task_name = 'beehive_resource.task_v2.container.resource_container_task'
        #     child_task, code = prepare_or_run_task(container, task_name, params, sync=True)
        #     run_sync_task(child_task, task, step_id)

        # delete stack
        task.get_session(reopen=True)
        resource = task.get_simple_resource(oid)
        resource.expunge_internal()
        task.progress(step_id, msg="Delete stack %s resource" % oid)

        return oid, params


task_manager.tasks.register(StackTask())
