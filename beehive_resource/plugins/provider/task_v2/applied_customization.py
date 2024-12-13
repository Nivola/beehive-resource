# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.applied_customization import (
    AppliedComputeCustomization,
    AppliedCustomization,
)
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beehive_resource.plugins.awx.entity.awx_job_template import AwxJobTemplate
from logging import getLogger

logger = getLogger(__name__)


class AppliedComputeCustomizationTask(AbstractProviderResourceTask):
    """AppliedComputeCustomization task"""

    name = "applied_compute_customization_task"
    entity_class = AppliedComputeCustomization

    @staticmethod
    @task_step()
    def create_zone_customization_step(task, step_id, params, availability_zone_id, project, *args, **kvargs):
        """Create zone customization.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :param project: awx project name
        :return: True, params
        """
        logger.debug("+++++ create_zone_customization_step - params: {}".format(params))
        # logger.debug('+++++ create_zone_customization_step - task: %s' % task)

        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("name")
        instances = params.get("instances")
        playbook = params.get("playbook")
        verbosity = params.get("verbosity")
        extra_vars = params.get("extra_vars")

        from beehive_resource.task_v2.core import AbstractResourceTask

        abstractResourceTask: AbstractResourceTask = task

        from beehive_resource.plugins.provider.controller import LocalProvider

        provider: LocalProvider = abstractResourceTask.get_container(cid)
        availability_zone = abstractResourceTask.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        abstractResourceTask.progress(step_id, msg="Get resources")

        # get instances
        compute_instance = None
        hosts = []
        for instance in instances:
            # obj = task.get_simple_resource(instance['id'])
            # per caricare anche l'image della resource per check os
            from beehive_resource.plugins.provider.entity.instance import (
                ComputeInstance,
            )

            compute_instance: ComputeInstance = abstractResourceTask.get_resource(instance["id"])
            zone_objs, total = compute_instance.get_linked_resources(
                link_type_filter="relation.%s" % compute_instance.availability_zone_id
            )
            obj_availability_zone_id = zone_objs[0].parent_id
            # credential = obj.get_credential()
            if obj_availability_zone_id == availability_zone_id:
                inst_extra_vars = instance.get("extra_vars")

                ssh_creds = compute_instance.get_real_admin_credential()

                if compute_instance.is_windows() is True:
                    inst_extra_vars.update(
                        {
                            # vedi https://docs.ansible.com/ansible/latest/os_guide/windows_winrm.html
                            # "ansible_user": obj.get_real_admin_user(),
                            "ansible_connection": "winrm",
                            "ansible_winrm_server_cert_validation": "ignore",
                            # "ansible_port": "5985", # default https 5986
                            # "ansible_winrm_scheme": "http", # https by default
                            # "ansible_winrm_transport": "basic", # default kerberos, basic
                        }
                    )

                    from beehive_resource.plugins.provider.entity.bastion import ComputeBastion
                    from beehive_resource.plugins.provider.entity.zone import ComputeZone

                    computeZone: ComputeZone = compute_instance.get_parent()
                    bastion_host: ComputeBastion = computeZone.get_bastion_host()
                    if bastion_host is not None:
                        raise Exception("Ansible connection with winrm is not supported through bastion")

                else:
                    inst_extra_vars.update(
                        {
                            # "ansible_user": compute_instance.get_real_admin_user(),
                            "ansible_user": ssh_creds["username"],
                            # 'ansible_password': credential.get('password'),
                            "ansible_port": compute_instance.get_real_ssh_port(),
                            # 'ansible_host': obj.get_ip_address(),
                            # 'ansible_pipelining': True,
                            "ansible_connection": "ssh",
                            "ansible_ssh_common_args": "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no",
                        }
                    )
                    # add data per account private
                    inst_extra_vars = compute_instance.set_ansible_ssh_common_args(inst_extra_vars)

                # get instance ip address
                ip_address = compute_instance.get_real_ip_address()
                # vpc_links, total = obj.get_links(type='vpc')
                # ip_address = vpc_links[0].attribs.get('fixed_ip', {}).get('ip', '')
                hosts.append(
                    {
                        "ip_addr": ip_address,
                        "extra_vars": ";".join(["%s:%s" % (k, v) for k, v in inst_extra_vars.items()]),
                    }
                )

        # if obj is not None:
        #     credential = obj.get_credential()

        if len(hosts) == 0:
            task.progress(
                step_id,
                msg="no hosts found in availability zone %s" % availability_zone_id,
            )
            return False, params

        if extra_vars is not None and len(extra_vars.keys()) > 0:
            extra_vars = ";".join(["%s:%s" % (k, v) for k, v in extra_vars.items()])
        else:
            extra_vars = None

        awx_job_template = {
            "name": "%s-jobtemplate-%s" % (name, id_gen()),
            "desc": "Awx Job Template %s" % name,
            "hosts": hosts,
            "project": project,
            "playbook": playbook,
            "verbosity": verbosity,
            # "ssh_creds": compute_instance.get_real_admin_credential(),
            "ssh_creds": ssh_creds,
            "extra_vars": extra_vars,
        }

        # create zone customization
        customization_params = {
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Zone customization %s" % params.get("desc"),
            "parent": availability_zone_id,
            "orchestrator_tag": params.get("orchestrator_tag"),
            "awx_job_template": awx_job_template,
            "attribute": {},
        }
        logger.info("+++++ create_zone_customization_step - customization_params: %s" % customization_params)
        prepared_task, code = provider.resource_factory(AppliedCustomization, **customization_params)
        customization_id = prepared_task["uuid"]

        # link applied_customization to applied_compute_customization
        task.get_session(reopen=True)
        applied_compute_customization = task.get_simple_resource(oid)
        applied_compute_customization.add_link(
            "%s-applied-customization-link" % customization_id,
            "relation.%s" % site_id,
            customization_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link applied_customization %s to applied_compute_customization %s" % (customization_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create applied_customization %s in availability_zone %s" % (customization_id, availability_zone_id),
        )

        return True, params


class AppliedCustomizationTask(AbstractProviderResourceTask):
    """Customization task"""

    name = "applied_customization_task"
    entity_class = AppliedCustomization

    @staticmethod
    @task_step()
    def create_awx_job_template_step(task, step_id, params, *args, **kvargs):
        """Create awx job_template resource.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        awx_job_template = params.get("awx_job_template")
        orchestrator = params.get("orchestrator")

        # get container from orchestrator
        awx_container = task.get_container(orchestrator["id"])

        # set awx_job_template params
        awx_job_template_params = {
            "name": awx_job_template.get("name"),
            "desc": awx_job_template.get("desc"),
            "add": {
                "organization": orchestrator["config"].get("organization"),
                "hosts": awx_job_template.get("hosts"),
                "project": awx_job_template.get("project"),
                "playbook": awx_job_template.get("playbook"),
                "verbosity": awx_job_template.get("verbosity"),
            },
            "launch": {
                "ssh_creds": awx_job_template.get("ssh_creds"),
                "extra_vars": awx_job_template.get("extra_vars"),
            },
            "attribute": {},
            "sync": True,
        }

        # create awx_job_template
        logger.debug("+++++ create_awx_job_template_step - awx_container: %s" % awx_container)
        logger.debug("+++++ create_awx_job_template_step - awx_job_template_params: %s" % awx_job_template_params)
        prepared_task, code = awx_container.resource_factory(AwxJobTemplate, **awx_job_template_params)
        job_template_id = prepared_task["uuid"]

        # link awx_job_template to applied_customization
        task.get_session(reopen=True)
        applied_customization = task.get_simple_resource(oid)
        applied_customization.add_link(
            "%s-awx_job_template-link" % job_template_id,
            "relation",
            job_template_id,
            attributes={},
        )
        task.progress(
            step_id,
            msg="Link awx_job_template %s to applied_customization %s" % (job_template_id, oid),
        )

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create awx_job_template %s" % job_template_id)

        return True, params
