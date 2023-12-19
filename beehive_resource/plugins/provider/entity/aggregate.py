# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

import logging
from beehive.common.data import truncate, operation
from beehive_resource.container import Resource, AsyncResource
from beehive.common.apimanager import ApiManagerError
from typing import Any, Union


def get_task(task_name):
    return "%s.task.%s" % (__name__.replace(".entity.aggregate", ""), task_name)


class ComputeQuotas(object):
    classes = {
        "compute.instances": {"default": 10, "unit": "#"},
        "compute.images": {"default": 10, "unit": "#"},
        "compute.volumes": {"default": 10, "unit": "#"},
        "compute.snapshots": {"default": 10, "unit": "#"},
        "compute.blocks": {"default": 1024, "unit": "GB"},
        "compute.ram": {"default": 1024, "unit": "GB"},
        "compute.cores": {"default": 10, "unit": "#"},
        "compute.networks": {"default": 10, "unit": "#"},
        "compute.floatingips": {"default": 10, "unit": "#"},
        "compute.security_groups": {"default": 10, "unit": "#"},
        "compute.security_group_rules": {"default": 10, "unit": "#"},
        "compute.keypairs": {"default": 10, "unit": "#"},
        "database.instances": {"default": 10, "unit": "#"},
        "database.ram": {"default": 1024, "unit": "GB"},
        "database.cores": {"default": 10, "unit": "#"},
        "database.volumes": {"default": 10, "unit": "#"},
        "database.snapshots": {"default": 10, "unit": "#"},
        "database.blocks": {"default": 1024, "unit": "GB"},
        "share.instances": {"default": 10, "unit": "#"},
        "share.blocks": {"default": 1024, "unit": "GB"},
        "appengine.instances": {"default": 10, "unit": "#"},
        "appengine.ram": {"default": 1024, "unit": "GB"},
        "appengine.cores": {"default": 10, "unit": "#"},
        "appengine.volumes": {"default": 10, "unit": "#"},
        "appengine.snapshots": {"default": 10, "unit": "#"},
        "appengine.blocks": {"default": 1024, "unit": "GB"},
        "logging.spaces": {"default": 10, "unit": "#"},
        "logging.instances": {"default": 100, "unit": "#"},
        # 'logging.blocks': {'default': 1024, 'unit': 'GB'},
        "monitoring.folders": {"default": 10, "unit": "#"},
        "monitoring.alerts": {"default": 10, "unit": "#"},
        # 'monitoring.instances': {'default': 10, 'unit': '#'},
        "monitoring.instances": {"default": 100, "unit": "#"},
        # network
        "network.gateways": {"default": 1, "unit": "#"},
        "network.networks": {"default": 20, "unit": "#"},
        "network.security_groups": {"default": 20, "unit": "#"},
        "network.security_group_rules": {"default": 100, "unit": "#"},
        "network.floatingips": {"default": 10, "unit": "#"},
        "network.loadbalancers": {"default": 10, "unit": "#"},
    }

    def __init__(self, quotas):
        """Create new instance

        :param quotas:
        """
        self.logger = logging.getLogger(self.__class__.__module__ + "." + self.__class__.__name__)

        self.quotas = {}
        for quota, value in self.classes.items():
            self.quotas[quota] = quotas.get(quota, value["default"])

    def get_classes(self):
        """Get quotas

        :return:
        """
        classes = []
        for quota, value in self.classes.items():
            item = {"quota": quota, "unit": value["unit"], "default": value["default"]}
            classes.append(item)
        return classes

    def get_simple(self):
        """Get quotas as simple dict

        :return: {'compute.instances': 10,..}
        """
        quotas = {}
        for quota, value in self.classes.items():
            quotas[quota] = self.quotas.get(quota, value["default"])
        return quotas

    def get(self):
        """Get quotas

        :return:
        """
        quotas = []
        for quota, value in self.classes.items():
            item = {
                "quota": quota,
                "unit": value["unit"],
                "value": self.quotas.get(quota, value["default"]),
            }
            quotas.append(item)
        return quotas

    def check_availability(self, allocated, to_allocate):
        """Check if new quota can be allocated or max limits are raised.

        :param allocated: quota already allocated
        :param to_allocate: quota that should be allocated
        :return: True if check is ok
        :rtype: dict
        :raises ApiManagerError: if quotas are exceeded.
        """
        total = self.quotas

        for k, v in allocated.items():
            quota_to_allocate = to_allocate.get(k, 0)
            new_allocated = v + quota_to_allocate

            quota_total = total.get(k, 0)
            if new_allocated > quota_total:
                self.logger.error(
                    "quota_total: %s, quota_to_allocate: %s, quota_allocated: %s" % (quota_total, quota_to_allocate, v)
                )
                raise ApiManagerError("Quotas %s have been exceeded" % k)

        return True


class ComputeProviderResource(AsyncResource):
    """Compute provider resource. This resource aggregate other resource"""

    objdef = "Provider.ComputeResource"
    objuri = "%s/compute_resources/%s"
    objname = "compute_resource"
    objdesc = "Provider compute resource"

    task_path = "beehive_resource.plugins.provider.task_v2.AbstractResourceTask."
    create_task = "beehive_resource.plugins.provider.task_v2.provider_resource_add_task"
    # clone_task = 'beehive_resource.plugins.provider.task_v2.provider_resource_clone_task'
    import_task = "beehive_resource.plugins.provider.task_v2.provider_resource_import_task"
    update_task = "beehive_resource.plugins.provider.task_v2.provider_resource_update_task"
    patch_task = "beehive_resource.plugins.provider.task_v2.provider_resource_patch_task"
    delete_task = "beehive_resource.plugins.provider.task_v2.provider_resource_delete_task"
    expunge_task = "beehive_resource.plugins.provider.task_v2.provider_resource_expunge_task"
    action_task = "beehive_resource.plugins.provider.task_v2.provider_resource_action_task"

    def __init__(self, *args, **kvargs):
        Resource.__init__(self, *args, **kvargs)

    def get_configs(self):
        return self.attribs.get("configs")

    @staticmethod
    def get_active_availability_zone(compute_zone, site):
        """Get availability zone ACTIVE

        :param compute_zone: compute zone instance
        :param site: site instance
        :return: list of availability zone resources
        """
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        availability_zone, total = compute_zone.get_linked_resources(
            link_type="relation.%s" % site.oid,
            entity_class=AvailabilityZone,
            objdef=AvailabilityZone.objdef,
            run_customize=False,
        )
        if availability_zone[0].is_active() is False:
            raise ApiManagerError("Availability zone %s has not a correct state" % availability_zone[0].uuid)

        return availability_zone[0].oid

    @staticmethod
    def get_active_availability_zones(compute_zone, multi_avz=True):
        """Get availability zones ACTIVE

        :param compute_zone: compute zone instance
        :param multi_avz: if True return a list of active availability zones
        :return: list of availability zone resources
        """
        from beehive_resource.plugins.provider.entity.zone import AvailabilityZone

        availability_zones = []
        if multi_avz is True:
            avzs, total = compute_zone.get_linked_resources(
                link_type_filter="relation%",
                entity_class=AvailabilityZone,
                objdef=AvailabilityZone.objdef,
                run_customize=False,
            )
            for avz in avzs:
                if avz.is_active() is True:
                    availability_zones.append(avz.oid)

        return availability_zones

    def get_dedploy_availability_zones(self):
        """Get availability zones where entity is deployed

        :return: list of availability zone id
        """
        availability_zones = []
        objs, tot = self.get_linked_resources(link_type="relation%", run_customize=False, size=-1, with_perm_tag=False)
        for obj in objs:
            availability_zones.append(obj.get_parent().parent_id)

        return availability_zones

    def get_active_availability_zone_child(self, site_id):
        """Get active availability zone child by parent site

        :param site_id: site id
        :return: availability zone child
        """
        objs, tot = self.get_linked_resources(
            link_type="relation.%s" % site_id,
            run_customize=False,
            size=-1,
            with_perm_tag=False,
        )
        if len(objs) == 0:
            raise ApiManagerError("resource %s does not have child in site %s" % (self.oid, site_id))
        obj = objs[0]
        obj.check_active()
        return obj

    def get_local_resource(self, site_id):
        """Get local resource in a specific availability zone related to an aggregated resource

        :param site_id: site id
        :return: availability zone local resource
        """
        objs, tot = self.get_linked_resources(
            link_type="relation.%s" % site_id,
            run_customize=False,
            size=-1,
            with_perm_tag=False,
        )
        if len(objs) == 0:
            raise ApiManagerError("resource %s does not have child in site %s" % (self.oid, site_id))
        obj = objs[0]
        obj.check_active()
        return obj

    @staticmethod
    def group_create_step(g_steps):
        """Create group of step used to create resource

        :param g_steps: list of additional steps
        :return: list of steps
        """
        run_steps = [ComputeProviderResource.task_path + "create_resource_pre_step"]
        run_steps.extend(g_steps)
        run_steps.append(ComputeProviderResource.task_path + "create_resource_post_step")
        return run_steps

    def group_update_step(self, g_steps):
        """Create group of step used to update resource

        :param g_steps: list of additional steps
        :return: list of steps
        """
        run_steps = [self.task_path + "update_resource_pre_step"]
        if g_steps is not None:
            run_steps.extend(g_steps)
        run_steps.append(self.task_path + "update_resource_post_step")
        return run_steps

    def group_patch_step(self, g_steps):
        """Create group of step used to patch resource

        :param g_steps: list of additional steps
        :return: list of steps
        """
        run_steps = [self.task_path + "patch_resource_pre_step"]
        if g_steps is not None:
            run_steps.extend(g_steps)
        run_steps.append(self.task_path + "patch_resource_post_step")
        return run_steps

    def group_remove_step(self, childs):
        """Create group of step used to remove resource

        :param childs: list of childs to remove
        :return: list of steps
        """
        run_steps = [self.task_path + "expunge_resource_pre_step"]
        for child in childs:
            substep = {"step": self.task_path + "remove_child_step", "args": [child]}
            run_steps.append(substep)
        run_steps.append(self.task_path + "expunge_resource_post_step")
        return run_steps

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError
        """
        objs, total = self.get_linked_resources(link_type_filter="relation%")
        childs = [p.oid for p in objs]
        kvargs["steps"] = self.group_remove_step(childs)
        return kvargs

    def set_state(self, state):
        """Set resource state

        :param state: resource state. Valid value are ACTIVE and ERROR
        :return: True
        """
        Resource.set_state(self, state)

        # get zone childs
        childs, total = self.get_linked_resources(
            link_type_filter="relation%", with_perm_tag=False, run_customize=False
        )
        for child in childs:
            child.set_state(state)

        return True

    def __cache_key(self, method):
        return "%s.%s.%s" % (self.__class__.__name__, method, self.uuid)

    def reset_cache(self, method: str) -> bool:
        """TODO decidere se spostarla in Resource o ApiObject ?
        Reset chace for method
        if method is "*" in order to reset alla cached values
        for current resource
        """
        # save data in cache
        if operation.cache is False or self.model is None:
            return False
        key = self.__cache_key(method)
        return self.controller.cache.delete_by_pattern(key)

    def set_cache(self, method: str, value: Any, ttl=2500, pickling=False) -> bool:
        """TODO decidere se spostarla in Resource o ApiObject ?
        Cache a value
        :param method is the method's name to be cached
        :param value the value tu bi caches
        :param ttl optional time to live in second
        :param picling optional flag to use pckle while mmarshaling
        """
        # check if cache is enalbled and model has been loaded
        if operation.cache is False or self.model is None:
            return False

        key = self.__cache_key(method)
        return self.controller.cache.set(key, value, ttl=ttl, pickling=pickling)

    def get_cached(
        self,
        method: str,
    ) -> Union[Any, None]:
        """TODO decidere se spostarla in Resource o ApiObject
        get a chached record value
        :param method
        """
        if operation.cache is False or self.model is None:
            return None
        key = self.__cache_key(method)
        ret = None
        try:
            ret = self.controller.cache.get(key)
            if ret is None or ret == {} or ret == []:
                return None
            else:
                self.logger.debug2("Cache %s:%s" % (key, truncate(ret)))
        except Exception as ex:
            self.logger.error(ex)
            raise
        return ret

    def clean_cache(self):
        """Clean cache"""
        # self.logger.debug("+++++ clean_cache - ComputeProviderResource")
        AsyncResource.clean_cache(self)
        self.reset_cache("*")
