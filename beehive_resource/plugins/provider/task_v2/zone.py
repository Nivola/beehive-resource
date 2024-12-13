# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class ZoneTask(AbstractProviderResourceTask):
    """Zone task"""

    name = "zone_task"
    entity_class = ComputeZone

    @staticmethod
    @task_step()
    def availability_zone_link_resource_step(task, step_id, params, *args, **kvargs):
        """Link availability zone resource to compute zone.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        site_id = params.get("site")
        zone_id = params.get("zone")

        zone = task.get_resource(zone_id)
        zone.add_link("%s-zone-link" % oid, "relation.%s" % site_id, oid, attributes={})
        task.progress(step_id, msg="Link availability zone %s to compute zone %s" % (oid, zone_id))

        return oid, params

    @staticmethod
    @task_step()
    def availability_zone_create_orchestrator_resource_step(task, step_id, params, orchestrator_id, *args, **kvargs):
        """Set availability zone quotas in remote orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator_id: orchestrator id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        site_id = params.get("site")
        orchestrators = params.get("orchestrators")
        quotas = params.get("quota")
        orchestrator = orchestrators[orchestrator_id]

        resource = task.get_simple_resource(oid)
        site = task.get_simple_resource(site_id)
        task.progress(step_id, msg="Get availability_zone %s" % cid)

        # create physical entities
        from beehive_resource.plugins.provider.task_v2.openstack import (
            ProviderOpenstack,
        )
        from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere

        helper: ProviderVsphere = task.get_orchestrator(orchestrator.get("type"), task, step_id, orchestrator, resource)
        helper.create_zone_childs(site, quotas=quotas)

        return True, params

    @staticmethod
    @task_step()
    def compute_zone_set_quotas_step(task, step_id, params, *args, **kvargs):
        """Set compute zone quotas

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        quotas = params.get("quotas")
        zones = params.get("availability_zones")
        orchestrator_tag = params.get("orchestrator_tag")

        resource = task.get_simple_resource(oid)

        attribs = resource.get_attribs()
        attribs["quota"].update(quotas)
        resource.manager.update_resource(oid=oid, attribute=attribs)
        task.progress(step_id, msg="Update compute zone %s quotas: %s" % (oid, quotas))

        # update child availability zones
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        for zone in zones:
            zone_resource: AvailabilityZone = task.get_resource(zone)
            if zone_resource.is_active() is False:
                task.progress(
                    step_id,
                    msg="compute zone %s availability zone %s is not active" % (oid, zone),
                )
            else:
                prepared_task, code = zone_resource.set_quotas(quotas=quotas, orchestrator_tag=orchestrator_tag)
                run_sync_task(prepared_task, task, step_id)
                task.progress(
                    step_id,
                    msg="Update compute zone %s availability zone %s quotas: %s" % (oid, zone, quotas),
                )

        return True, params

    @staticmethod
    @task_step()
    def availability_zone_set_quotas_step(task, step_id, params, *args, **kvargs):
        """Set availability zone quotas

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        quotas = params.get("quotas")

        resource = task.get_resource(oid)
        attribs = resource.get_attribs()
        attribs["quota"].update(quotas)
        resource.manager.update_resource(oid=oid, attribute=attribs)
        task.progress(step_id, msg="Update compute zone %s quotas: %s" % (oid, quotas))

        return True, params

    @staticmethod
    @task_step()
    def availability_zone_set_orchestrator_quotas_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Set availability zone quotas in remote orchestartor

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator: orchestrator id
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        quotas = params.get("quotas")

        resource = task.get_resource(oid)

        from beehive_resource.plugins.provider.task_v2.openstack import (
            ProviderOpenstack,
        )
        from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere

        helper: ProviderVsphere = task.get_orchestrator(orchestrator["type"], task, step_id, orchestrator, resource)
        helper.set_quotas(quotas)

        return True, params

    @staticmethod
    @task_step()
    def remove_applied_customization_step(task, step_id, params, *args, **kvargs):
        """remove applied customizations

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        resource = task.get_resource(oid)

        # remove applied customization
        from .applied_customization import AppliedCustomization

        appcusts, tot = resource.get_resources(entity_class=AppliedCustomization)
        for appcust in appcusts:
            site = appcust.get_site()
            parents, total = appcust.get_linked_resources(link_type="relation.%s" % site.oid)
            task.logger.warn("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            for parent in parents:
                prepared_task, code = parent.expunge(sync=True)
                run_sync_task(prepared_task, task, step_id)
                task.progress(step_id, msg="remove applied customization %s" % parent.oid)

            task.logger.warn(parents)
            task.logger.warn(appcust)
            task.logger.warn("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

        return True, params
