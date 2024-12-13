# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger

from beehive.common.task_v2.manager import task_manager
from beehive_resource.task_v2 import AbstractResourceTask
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.ontap.controller import OntapNetappContainer, OntapManager
from beehive.common.task_v2 import task_step, run_sync_task

logger = getLogger(__name__)


class OntapVolumeTask(AbstractResourceTask):
    """Ontap Volume task"""

    name = "ontap_volume_task"
    entity_class = OntapNetappVolume

    @staticmethod
    @task_step()
    def volume_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        name = params.get("name")
        ontap_name = params.get("ontap_name")

        share_params = params.get("share_params")
        extra_vars = params.get("extra_vars")

        task.progress(step_id, msg="Get configuration params %s" % params)

        # ontapContainer: OntapNetappContainer = task.get_container(cid)
        # ontapManager: OntapManager = ontapContainer

        # get container from orchestrator
        awx_orchestrator_id = params.get("awx_orchestrator_id")
        awx_container = task.get_container(awx_orchestrator_id)

        # get project
        awx_project_id = params.get("awx_project_id")
        # awx_project = task.get_simple_resource(awx_project_id)

        # get other
        awx_organization_id = params.get("awx_organization_id")

        # awx_job_template = {
        #
        #    # "ssh_creds": compute_instance.get_real_admin_credential(),
        # }

        # set awx_job_template params
        awx_job_template_params = {
            "name": f"{name}-jobtemplate",
            "desc": f"Awx Job Template {name}",
            "add": {
                "organization": awx_organization_id,
                # "hosts": [{"ip_addr": "127.0.0.1", "extra_vars": { "extra": "boh"}}], # NON SERVE
                "project": awx_project_id,
                "playbook": "volume.yaml",
                "verbosity": 1,  # verbosity, 0 = normal = default 1 = verbose
            },
            "launch": {
                # "ssh_creds": {"username": "NON_SERVE", "password": "NON_SERVE"}, # NON SERVONO
                "extra_vars": extra_vars,
            },
            "attribute": {},
            "job_template_type": "remote_only",
            "sync": True,
        }

        from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate

        # create awx_job_template
        task.progress(msg="+++++ create_awx_job_template_step - awx_job_template_params: %s" % awx_job_template_params)
        prepared_task, code = awx_container.resource_factory(AwxJobTemplate, **awx_job_template_params)
        job_template_id = prepared_task["uuid"]

        # ADD LINK
        task.get_session(reopen=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create awx_job_template %s" % job_template_id)

        ontapContainer: OntapNetappContainer = task.get_container(cid)
        ontapManager: OntapManager = ontapContainer.conn
        res = ontapManager.volume.list(name=ontap_name, svm=share_params.get("svm"))
        if len(res) == 0:
            raise Exception(
                "Created volume not found on expected container %d with expected name %s!" % (cid, ontap_name)
            )
        if len(res) > 1:
            task.progress(
                msg="""
                More than one volume found on container %d with the exact name %s.
                This should not happen and could be an error
            """
                % (cid, ontap_name)
            )

        # save current data in shared area
        params["ext_id"] = res[0].get("uuid")
        params["attrib"] = {}
        task.progress(step_id, msg="Update shared area")
        return oid, params


task_manager.tasks.register(OntapVolumeTask())
