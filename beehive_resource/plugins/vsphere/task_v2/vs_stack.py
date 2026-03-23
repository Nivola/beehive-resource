# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte

from celery import signature
from logging import getLogger
from beecell.types.type_string import truncate
from beehive.common.task_v2 import task_step
from beehive_resource.plugins.vsphere.entity.vs_orchestrator import VsphereStack
from beehive_resource.plugins.vsphere.task_v2.util import VsphereServerHelper
from beehive_resource.task_v2 import AbstractResourceTask
from beehive.common.task_v2.manager import get_task_manager

logger = getLogger(__name__)
task_manager = get_task_manager()

stack_entity_type_mapping = {
    "VS::Vsphere::Server": "Vsphere.DataCenter.Folder.Server",
}


class StackTask(AbstractResourceTask):
    """Stack task"""

    name = "stack_task"
    entity_class = VsphereStack

    @staticmethod
    @task_step()
    def stack_create_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
        """Create vsphere server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        # get params from shared data
        params = task.get_shared_data()

        # validate input params
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
        task.update("PROGRESS", msg="Get configuration params")

        # get orchestrator
        task.get_session()
        orchestrator = task.get_container(cid)
        task.update("PROGRESS", msg="Get orchestrator %s" % cid)

        # validate template
        orch = orchestrator.get_orchestrator_resource()
        template = orch.validate_template(template_uri)
        task.update("PROGRESS", msg="Validate template %s" % template_uri)

        # parse template
        outputs = template.get("outputs")
        parameters = template.get("parameters")
        resources = template.get("resources")

        servers = []
        for resname, resource in resources.items():
            logger.warn(resname)
            restype = resource.get("type")
            resconf = resource.get("properties")
            logger.warn(restype)
            logger.warn(resconf)
            if restype == "VS::Vsphere::Server":
                """
                server = {
                    'name': '%s-%s' % (resname, id_gen()),
                    'imageRef':
                    'folder_id'
                    'network_id'
                    'block_device_mapping': {
                        'uuid': 'datastore_id',
                        'source_type': 'image',
                        'volume_size': '20',
                        'destination_type': 'volume',
                    }
                    'personality':
                    'user_data':
                    'networks': {'uuid':, 'fixed_ip': {
                            'ip':'172.25.5.154',
                            'gw':'172.25.5.18',
                            'hostname':name,
                            'dns':[8.8.8.8],
                            'dns_search':csi.it
                        }
                    },
                    'flavorRef': {
                        'guest_id':
                        'memory_mb':
                        'cpu':
                        'core_x_socket':
                        'version':
                    }
                    'adminPass':
                    'availability_zone': 'resource_pool_id'
                    'metadata':
                    'security_groups'
                }
                servers.append(server)"""
                pass

        # create all servers
        helper = VsphereServerHelper(task, orchestrator, params)
        for server in servers:
            node = helper.create_server(**server)

        # create new stack
        stack = {"id": "pippo"}
        stack_id = stack["id"]

        # stack_id = stack['id']
        # task.update('PROGRESS', msg='Create stack %s - Starting' % stack_id)
        #
        # # set ext_id
        # container.update_resource(oid, ext_id=stack_id)
        # task.update('PROGRESS', msg='Set stack remote openstack id %s' % stack_id)

        # # loop until entity is not stopped or get error
        # while True:
        #     inst = conn.heat.stack.get(stack_name=name, oid=stack_id)
        #     status = inst['stack_status']
        #     if status == 'CREATE_COMPLETE':
        #         break
        #     elif status == 'CREATE_FAILED':
        #         reason = inst['stack_status_reason']
        #         task.update('PROGRESS', msg='Create stack %s - Error: %s' % (stack_id, reason))
        #         raise Exception('Can not create stack %s: %s' % (stack_id, reason))
        #
        #     task.update('PROGRESS')
        #     gevent.sleep(task_local.delta)

        task.update("PROGRESS", msg="Create stack %s - Completed" % stack_id)

        # save current data in shared area
        params["ext_id"] = stack_id
        params["result"] = stack_id
        # params['attrib'] = {'volume':{'boot':volume.id}}
        task.set_shared_data(params)
        task.update("PROGRESS", msg="Update shared area")

        return stack_id, params

    @staticmethod
    @task_step()
    def stack_register_child_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
        """Register vsphere stack child entity

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        # get params from shared data
        params = task.get_shared_data()

        # validate input params
        cid = params.get("cid")
        # oid = params.get('id')
        ext_id = params.get("ext_id")
        name = params.get("name")
        parent_id = params.get("parent")
        task.update("PROGRESS", msg="Get configuration params")

        # get container
        task.get_session()
        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn
        task.update("PROGRESS", msg="Get container %s" % cid)

        # get resources
        resources = conn.heat.stack.resource.list(stack_name=name, oid=ext_id)
        task.update("PROGRESS", msg="Get child resources: %s" % truncate(resources))

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
        task.update("PROGRESS", msg="get child resources objdef: %s" % objdefs)

        # run celery job
        if len(objdefs) > 0:
            params = {
                "cid": cid,
                "types": ",".join(objdefs.keys()),
                "new": True,
                "died": False,
                "changed": False,
            }
            params.update(container.get_user())
            from beehive.common.task.job import JobTask
            task: 'JobTask' = signature(
                "beehive_resource.tasks.job_synchronize_container",
                (container.objid, params),
                app=task_manager,
                queue=container.celery_broker_queue,
            )
            job = task.apply_async()
            task.logger.info("Start job job_synchronize_container %s" % job.id)

            # wait job complete
            task.wait_for_job_complete(job.id)

        # save current data in shared area
        params["res_ext_ids"] = res_ext_ids
        task.set_shared_data(params)
        task.update("PROGRESS", msg="Update shared area")

        return res_ext_ids, params

    @staticmethod
    @task_step()
    def stack_link_child_step(task, step_id, params, *args, **kvargs):
        """Link vsphere stack child entity

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        res_ext_ids = params.get("res_ext_ids")
        task.update("PROGRESS", msg="Get configuration params")

        # link child resource to stack
        task.get_session()
        stack = task.get_resource(oid)
        for ext_id in res_ext_ids:
            child = task.get_resource_by_extid(ext_id)
            stack.add_link("%s-%s-stack-link" % (oid, child.oid), "stack", child.oid, attributes={})
            task.update("PROGRESS", msg="Link stack %s to child %s" % (oid, child.oid))

        return True, params

    @staticmethod
    @task_step()
    def stack_update_step(task, step_id, params, *args, **kvargs):
        """Update vsphere stack

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        pass

    @staticmethod
    @task_step()
    def stack_expunge_step(task, step_id, params, *args, **kvargs):
        """Update vsphere stack

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        ext_id = params.get("ext_id")
        parent_id = params.get("parent_id")
        task.update("PROGRESS", msg="Get configuration params")

        # get stack resource
        task.get_session()
        container = task.get_container(cid, projectid=parent_id)
        conn = container.conn
        task.update("PROGRESS", msg="Get container %s" % cid)

        return True
