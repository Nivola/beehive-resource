# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from logging import getLogger

from beecell.simple import id_gen
from beehive_resource.task_v2 import AbstractResourceTask
from beehive.common.task_v2.manager import get_task_manager
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.ontap.controller import OntapNetappContainer
from beehive.common.task_v2 import task_step, run_sync_task

logger = getLogger(__name__)


class OntapVolumeTask(AbstractResourceTask):
    """Ontap Volume task"""

    name = "ontap_volume_task"
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

        cid = params.get("cid")
        oid = params.get("id")

        name = params.get("name")
        ontap_name = params.get("remote_name")

        share_params = params.get("share_params")
        extra_vars = params.get("extra_vars")

        awx_playbook = params.get("awx_playbook","volume.yaml")

        task.progress(step_id, msg="Getting awx params")

        # get container from orchestrator and awx conf data
        awx_params = params.get("awx_params")
        awx_orchestrator_id = awx_params.get("awx_orchestrator_id")
        awx_container = task.get_container(awx_orchestrator_id)
        awx_project_id = awx_params.get("awx_project_id")
        #awx_project = task.get_simple_resource(awx_project_id)
        awx_organization_id = awx_params.get("awx_organization_id")
        awx_vault_cred_id = awx_params.get("awx_vault_cred_id")

        # set awx_job_template params
        awx_job_template_params = {
            "name": f"create-{name}-jobtemplate-{id_gen(6)}",
            "desc": f"Awx Job Template {name}",
            "add": {
                "organization": awx_organization_id,
                "project": awx_project_id,
                "playbook": awx_playbook,
                "verbosity": 1,  # verbosity, 0 = normal = default 1 = verbose
            },
            "launch": {
                "vault_cred_id": awx_vault_cred_id,
                "extra_vars": extra_vars,
            },
            "attribute": {},
            "job_template_type": "remote_only",
            "sync": True,
        }

        from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate

        # create awx_job_template
        task.progress(step_id, msg="Creating awx_job_template")
        prepared_task, code = awx_container.resource_factory(AwxJobTemplate, **awx_job_template_params)
        job_template_id = prepared_task["uuid"]

        task.get_session(reopen=True)
        task.progress(step_id, msg="Running task %s and waiting for it to end" % job_template_id)
        run_sync_task(prepared_task, task, step_id)

        task.progress(step_id, msg="Searching for created volume")
        ontapContainer: OntapNetappContainer = task.get_container(cid)
        res = ontapContainer.conn2.volume.list(name=ontap_name,svm=share_params.get("svm"))
        if len(res)==0:
            raise Exception("Created volume not found on expected container %d with expected name %s!" % (cid,ontap_name))
        if len(res)>1:
            task.progress(msg ="""
                More than one volume found on container %d with the exact name %s.
                This should not happen.
            """ % (cid,ontap_name))
            raise Exception("""
                More than one volume found on container %d with the exact name %s.
                This should not happen.
            """ % (cid,ontap_name))

        # update ext_id
        params["ext_id"] = res[0].get("uuid")
        task.progress(step_id, msg="Setting ext_id: %s" % params["ext_id"])
        return oid, params

    @staticmethod
    @task_step()
    def volume_import_physical_step(task: 'AbstractResourceTask', step_id, params, *args, **kwargs):
        task.progress(step_id, msg="Getting configuration params")

        cid = params.get("cid")
        oid = params.get("id")
        ontap_name = params.get("remote_name")

        share_params = params.get("share_params")

        task.progress(step_id, msg="Searching for volume to import")
        ontapContainer: OntapNetappContainer = task.get_container(cid)
        res = ontapContainer.conn2.volume.list(name=ontap_name,svm=share_params.get("svm"))
        if len(res)==0:
            raise Exception("Volume not found on expected container %d with expected name %s!" % (cid,ontap_name))
        if len(res)>1:
            task.progress(msg ="""
                More than one volume found on container %d with the exact name %s.
                This should not happen and could be an error
            """
                % (cid, ontap_name)
            )

        # update ext_id
        params["ext_id"] = res[0].get("uuid")
        task.progress(step_id, msg="Setting ext_id: %s" % params["ext_id"])
        return oid, params

    @staticmethod
    @task_step()
    def volume_delete_physical_step(task: 'AbstractResourceTask', step_id, params, awx_playbook, extra_vars, *args, **kwargs):
        task.progress(step_id, msg="Getting configuration params")

        oid = params.get("id")

        #extra_vars = params.get("extra_vars")
        volume_name = extra_vars.get("p_volume")

        task.progress(step_id, msg="Getting awx params")

        awx_params = params.get("awx_params")
        if awx_params is None:
            raise Exception("Unable to execute playbook for deletion. Awx params missing. Fill in the attribs, or delete manually on container.")

        awx_orchestrator_id = awx_params.get("awx_orchestrator_id")
        awx_container = task.get_container(awx_orchestrator_id)
        awx_project_id = awx_params.get("awx_project_id")
        awx_organization_id = awx_params.get("awx_organization_id")
        awx_vault_cred_id = awx_params.get("awx_vault_cred_id")

        # set awx_job_template params
        awx_job_template_params = {
            "name": f"delete-{volume_name}-jobtemplate-{id_gen(6)}",
            "desc": f"Awx Job Template {volume_name}",
            "add": {
                "organization": awx_organization_id,
                "project": awx_project_id,
                "playbook": awx_playbook,
                "verbosity": 1, # verbosity, 0 = normal = default 1 = verbose
            },
            "launch": {
                "vault_cred_id": awx_vault_cred_id,
                "extra_vars": extra_vars,
            },
            "attribute": {},
            "job_template_type": "remote_only",
            "sync": True,
        }

        from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate

        # create awx_job_template
        task.progress(step_id, msg="Creating awx_job_template")
        prepared_task, code = awx_container.resource_factory(AwxJobTemplate, **awx_job_template_params)
        job_template_id = prepared_task["uuid"]

        task.get_session(reopen=True)
        task.progress(step_id, msg="Running task %s and waiting for it to end" % job_template_id)
        run_sync_task(prepared_task, task, step_id)

        return oid, params

    @staticmethod
    @task_step()
    def check_update_info_against_remote_volume(task: 'AbstractResourceTask', step_id, params, oid, *args, **kwargs):
        phy_resource: OntapNetappVolume = task.get_simple_resource(oid)
        phy_resource.check_update_info_against_remote_volume()
        return oid, params

    @staticmethod
    @task_step()
    def check_update_info_against_remote_volume_v2(task: 'AbstractResourceTask', step_id, params, *args, **kwargs):
        oid = params.get("id")
        phy_resource: OntapNetappVolume = task.get_simple_resource(oid)
        phy_resource.check_update_info_against_remote_volume()
        return oid, params

class OntapVolumeActionTask(AbstractResourceTask):
    """ResourceAction task"""

    abstract = False
    name = "ontap_volume_action_task"
    entity_class = OntapNetappVolume

    @staticmethod
    @task_step()
    def volume_action_physical_step(task: 'AbstractResourceTask', step_id, params, operation, awx_playbook, extra_vars, *args, **kwargs):
        execute_in_single_transaction = kwargs.get("execute_in_single_transaction", False)

        task.progress(step_id, msg="Getting configuration params")

        oid = params.get("id")

        common_extra_vars = params.get("common_extra_vars", {})
        if not awx_playbook:
            raise Exception("awx_playbook missing")

        # extra_vars = common extra vars + extra vars, if defined
        tmp = common_extra_vars.copy()
        if extra_vars:
            tmp.update(extra_vars)
        extra_vars = tmp

        volume_name = extra_vars.get("p_volume")

        task.progress(step_id, msg="Getting awx params")

        awx_params = params.get("awx_params")
        if awx_params is None:
            raise Exception(f"Unable to execute playbook {awx_playbook}. Awx params missing. Fill in the attribs, or run check.")

        awx_orchestrator_id = awx_params.get("awx_orchestrator_id")
        awx_container = task.get_container(awx_orchestrator_id)
        awx_project_id = awx_params.get("awx_project_id")
        awx_organization_id = awx_params.get("awx_organization_id")
        awx_vault_cred_id = awx_params.get("awx_vault_cred_id")

        # set awx_job_template params
        awx_job_template_params = {
            "name": f"{operation}-{volume_name}-jobtemplate-{id_gen(6)}",
            "desc": f"Awx Job Template {volume_name}",
            "add": {
                "organization": awx_organization_id,
                "project": awx_project_id,
                "playbook": awx_playbook,
                "verbosity": 1, # verbosity, 0 = normal = default 1 = verbose
            },
            "launch": {
                "vault_cred_id": awx_vault_cred_id,
                "extra_vars": extra_vars,
            },
            "attribute": {},
            "job_template_type": "remote_only",
            "sync": True,
        }

        from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate

        # create awx_job_template
        task.progress(step_id, msg="Creating awx_job_template")
        prepared_task, code = awx_container.resource_factory(AwxJobTemplate, **awx_job_template_params)
        job_template_id = prepared_task["uuid"]

        if not execute_in_single_transaction:
            task.get_session(reopen=True)
        task.progress(step_id, msg="Running task %s and waiting for it to end" % job_template_id)
        run_sync_task(prepared_task, task, step_id)

        # TODO generalize
        if operation=="resize":
            task.progress(step_id, msg="Updating volume size")
            from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
            resource: OntapNetappVolume = task.get_simple_resource(oid,OntapNetappVolume)
            size = resource.detail().get("details", {}).get("size")
            if size is None:
                raise Exception("Unable to get size. Run check function later to try and update.")
            else:
                resource.set_configs("size",str(size))
        return oid, params

get_task_manager().register_task(OntapVolumeTask())
get_task_manager().register_task(OntapVolumeActionTask())
