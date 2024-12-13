# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import dict_get
from beedrones.awx.client import AwxManager
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate
from beehive_resource.task_v2 import AbstractResourceTask


class AwxJobTemplateTask(AbstractResourceTask):
    """AwxJobTemplate task"""

    name = "awx_job_template_task"
    entity_class = AwxJobTemplate

    @staticmethod
    @task_step()
    def awx_job_template_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        desc = params.get("desc")
        inventory = params.get("add").get("inventory")
        project = params.get("add").get("project")
        playbook = params.get("add").get("playbook")
        job_tags = params.get("add").get("job_tags")
        verbosity = params.get("add").get("verbosity")
        task.progress(step_id, msg="Get configuration params")

        from beedrones.awx.client import AwxManager
        from beehive_resource.plugins.awx.controller import AwxContainer

        container = task.get_container(cid)
        awxContainer: AwxContainer = container
        conn: AwxManager = awxContainer.conn
        res = conn.job_template.add(
            "TEMP-" + name,
            "run",
            inventory,
            project,
            playbook,
            description=desc,
            ask_credential_on_launch=True,
            ask_variables_on_launch=True,
            ask_limit_on_launch=True,
            verbosity=verbosity,
            job_tags=job_tags,
        )
        job_template_id = res["id"]
        task.progress(step_id, msg="Create awx job_template %s" % job_template_id)

        params["ext_id"] = job_template_id
        params["attrib"] = {}
        container.update_resource(oid, ext_id=job_template_id)
        task.set_data("container", container)
        task.progress(step_id, msg="Update shared area")

        return True, params

    @staticmethod
    @task_step()
    def awx_job_template_launch_step(task, step_id, params, *args, **kvargs):
        """Launch job_template

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        awxJobTemplateTask: AwxJobTemplateTask = task

        container: AwxContainer = awxJobTemplateTask.get_data("container")
        job_template = params.get("ext_id")
        creds = []
        ssh_creds = params.get("launch").get("ssh_creds_id")
        vault_creds = params.get("launch").get("vault_creds_id")
        if ssh_creds:
            creds.append(ssh_creds)
        if vault_creds:
            creds.append(vault_creds)
        jt_params = {
            "credentials": creds,
            "extra_vars": params.get("launch").get("extra_vars"),
        }
        task.progress(step_id, msg="Get configuration params")

        conn: AwxManager = container.conn
        res = conn.job_template.launch(job_template, **jt_params)
        job_id = res["id"]
        task.progress(step_id, msg="Run awx job %s" % job_id)

        # check job status
        def job_event_msg():
            awxJobTemplateTask.logger.info("+++++ job_event_msg - job_id: %s" % job_id)
            job_events = conn.job.events(job_id, query={"failed": True})
            awxJobTemplateTask.logger.info("+++++ job_event_msg - job_events: %s" % job_events)

            job_event_msg = ""
            # check job has failed events (log lines)
            if len(job_events) > 1:
                # job_event_msg = dict_get(job_events[1], "event_data.res.msg")
                for job_event in job_events:
                    msg = dict_get(job_event, "event_data.res.msg")
                    if msg is not None:
                        job_event_msg += msg + "\n"

            else:
                # all stdout events
                job_events = conn.job.events(job_id, query={})
                awxJobTemplateTask.logger.info("+++++ job_event_msg - job_events: %s" % job_events)
                for job_event in job_events:
                    stdout = dict_get(job_event, "stdout")
                    if stdout is not None:
                        job_event_msg += stdout + "\n"

            return job_event_msg

        # get job stdout
        def job_success_stdout():
            awxJobTemplateTask.logger.info("+++++ job_success_stdout - job_id: %s" % job_id)
            res = conn.job.stdout(job_id)
            content = res.get("content").split("\n")
            job_output = ""
            for i in content:
                i = (
                    i.replace("\x1b[0;32m", "")
                    .replace("\x1b[0;33m", "")
                    .replace("\x1b[1;31m", "")
                    .replace("\x1b[1;35m", "")
                    .replace("\x1b[0;31m", "")
                    .replace("\x1b[0;36m", "")
                )
                if i == "\x1b[":
                    continue
                job_output += i.replace("\x1b[", "").replace("0m", "")

            awxJobTemplateTask.logger.info(
                "+++++ job_success_stdout - job_id: %s - job_output: %s" % (job_id, job_output)
            )
            return job_output

        from beehive_resource.plugins.awx.controller import AwxContainer

        awxContainer: AwxContainer = container
        stdout: str = awxContainer.wait_for_awx_job(
            conn.job.get, job_id, delta=2, job_error_func=job_event_msg, job_success_func=job_success_stdout
        )
        awxJobTemplateTask.set_stdout_data(stdout)

        params["job_id"] = job_id

        return True, params

    # useless - commented everywhere!
    @staticmethod
    @task_step()
    def awx_job_report_step(task, step_id, params, *args, **kvargs):
        """Gather job standard output

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        container = task.get_data("container")
        oid = params.get("id")
        job = params.get("job_id")
        task.progress(step_id, msg="Get configuration params")

        conn = container.conn
        res = conn.job.stdout(job)
        task.progress(step_id, msg="Job {} standard output:\n".format(job))
        content = res.get("content").split("\n")
        for i in content:
            if i == "":
                continue
            i = (
                i.replace("\x1b[0;31m", "")
                .replace("\x1b[0;32m", "")
                .replace("\x1b[0;33m", "")
                .replace("\x1b[0;36m", "")
                .replace("\x1b[1;35m", "")
                .replace("\x1b[1;31m", "")
            )
            if i == "\x1b[":
                continue
            msg = i.replace("\x1b[", "").replace("0m", "") + "\n"
            task.progress(step_id, msg=msg)

        return oid, params

    @staticmethod
    @task_step()
    def awx_job_template_update_physical_step(task, step_id, params, *args, **kvargs):
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
    def awx_job_template_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        container = task.get_container(cid)
        conn = container.conn
        resource = container.get_simple_resource(oid)

        if resource.is_ext_id_valid() is True:
            try:
                # check if job_template exists
                conn.job_template.get(resource.ext_id)
                # delete job_template
                conn.job_template.delete(resource.ext_id)
                task.progress(step_id, msg="Delete awx job_template %s" % resource.ext_id)
            except:
                task.progress(
                    step_id,
                    msg="Awx job_template %s does not exist anymore" % resource.ext_id,
                )

        return oid, params


task_manager.tasks.register(AwxJobTemplateTask())
