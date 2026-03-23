# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte
from uuid import uuid4
from logging import getLogger

from beehive_resource.task_v2 import AbstractResourceTask
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive.common.task_v2 import task_step

logger = getLogger(__name__)


class OntapVolumeTaskDryRun(AbstractResourceTask):
    """Ontap Volume task"""

    name = "ontap_volume_task_dry_run"
    entity_class = OntapNetappVolume

    @staticmethod
    @task_step()
    def volume_create_physical_step(task: 'AbstractResourceTask', step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        task.progress(step_id, msg="Getting configuration params")

        expected_keys = [
            "cid", "id", "name", "remote_name",
            "share_params", "extra_vars"
        ]
        for key in expected_keys:
            assert key in params, f"Missing key: {key}"

        task.progress(step_id, msg="Getting awx params")

        # get container from orchestrator and awx conf data
        awx_params = params.get("awx_params")
        assert awx_params is not None, "Missing 'awx_params' dict"

        expected_keys = [
            "awx_orchestrator_id", "awx_project_id", "awx_organization_id",
            "awx_vault_cred_id"
        ]
        for key in expected_keys:
            assert key in awx_params, f"Missing key: {key}"

        awx_orchestrator_id = awx_params.get("awx_orchestrator_id")
        task.get_container(awx_orchestrator_id)

        # create awx_job_template
        task.progress(step_id, msg="Creating awx_job_template")
        task.progress(step_id, msg="Simulating run_sync_task call")
        task.progress(step_id, msg="Searching for created volume")

        # update ext_id
        params["ext_id"] = f"DUMMY_{uuid4()}"
        task.progress(step_id, msg="Setting ext_id: %s" % params["ext_id"])
        return params.get("id"), params

    @staticmethod
    @task_step()
    def volume_delete_physical_step(task: 'AbstractResourceTask', step_id, params, awx_playbook, extra_vars, *args, **kwargs):
        task.progress(step_id, msg="Getting configuration params")

        expected_keys = [
            "id", "awx_params"
        ]
        for key in expected_keys:
            assert key in params, f"Missing key: {key}"
        oid = params.get("id")

        assert extra_vars is not None, "Missing 'extra_vars' dict"
        assert awx_playbook is not None, "Missing 'awx_playbook' str"

        expected_keys = [
            "p_volume",
        ]
        for key  in expected_keys:
            assert key in extra_vars, f"Missing key: {key}"

        task.progress(step_id, msg="Getting awx params")
        awx_params = params.get("awx_params")
        assert awx_params is not None, "Missing 'awx_params' dict"

        expected_keys = [
            "awx_orchestrator_id", "awx_project_id",
            "awx_organization_id", "awx_vault_cred_id"
        ]
        for key  in expected_keys:
            assert key in awx_params, f"Missing key: {key}"

        awx_orchestrator_id = awx_params.get("awx_orchestrator_id")
        task.get_container(awx_orchestrator_id)

        # create awx_job_template
        task.progress(step_id, msg="Creating awx_job_template")
        task.progress(step_id, msg="Simulating run_sync_task call")

        # TODO figure out a way to dry run but not delete anything
        raise Exception("full dry run progression unsupported")
        return oid, params
