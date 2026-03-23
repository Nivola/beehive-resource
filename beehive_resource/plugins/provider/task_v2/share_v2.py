# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2026 CSI-Piemonte

from logging import getLogger
from typing import TYPE_CHECKING, Union, Dict, Optional, Tuple, Callable, Any, List
from beecell.simple import id_gen
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.entity.share_v2 import ComputeFileShareV2, FileShareV2
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
if TYPE_CHECKING:
    from beehive_resource.plugins.provider.entity.zone import AvailabilityZone
    from beehive_resource.plugins.provider.entity.share_v2 import OntapNetappContainer
    from beehive_resource.typing_extras.share.task import (
        FileShareV2_ImportPhysicalShareStepParams,
        FileShareV2_ImportPhysicalShareStepParams_ShareParams,
    )

logger = getLogger(__name__)

class ComputeFileShareV2Task(AbstractProviderResourceTask):
    """ComputeFileShareV2 task"""

    name = "file_share_v2_task"
    entity_class = ComputeFileShareV2

#
# Provider level steps
#

    @staticmethod
    @task_step()
    def determine_compliance_params_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        compliance_availability_zone_id: Union[str, int],
        *args,**kwargs
    ):
        """
        get or update compliance params. this is used because usually compliance_site is different from site
        where the share is created

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param compliance_availability_zone_id: id of compliance avz
        :return: oid, params
        """
        oid = params.get("id")
        task.progress(step_id, msg="Getting resources")

        compliance_avz: 'AvailabilityZone' = task.get_simple_resource(compliance_availability_zone_id)
        orchestrator_type: str = params.get("orchestrator_type")
        orchestrator_tag: str = params.get("orchestrator_tag")
        compliance_share_params: Dict = params.get("compliance_share_params")
        compliance_cluster: str = compliance_share_params.get("snaplock_cluster")

        # select remote orchestrator with the same name as the cluster
        task.progress(step_id, msg="Searching for orchestrator of type %s with tag %s, for cluster %s" %
                      (orchestrator_type, orchestrator_tag, compliance_cluster))
        container: 'OntapNetappContainer' = None
        compliance_orchestrator,container = compliance_avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, compliance_cluster)

        cluster_fqdn = container.conn_params.get("host")
        task.progress(step_id, msg="Found container: %s. Now searching for emptiest aggregate" % container.name)

        # in alternative pass to this step the ext_id directly
        emptiest_aggregate,_max_space_available = container.conn2.get_svm_emptiest_aggregate(svm_name=compliance_share_params.get("snaplock_svm"))

        task.progress(step_id,msg="Found emptiest aggregate: %s" % emptiest_aggregate)

        params["compliance_share_params"]["snaplock_cluster"] = cluster_fqdn
        params["compliance_share_params"]["snaplock_aggregate"] = emptiest_aggregate
        #params["compliance_share_params"]["snaplock_aggregate_available_space"] = max_space_available # NB: this may become stale as the task continues
        params["compliance_orchestrator"] = compliance_orchestrator
        return oid, params

    @staticmethod
    @task_step()
    def create_zone_share_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        availability_zone_id: Union[str,int],
        *args,
        **kwargs,
    ):
        """Create zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param int availability_zone_id: availability zone id
        :param bool main: if True this is the main zone
        :return: oid, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        task.progress(step_id, msg="Getting resources")
        provider = task.get_container(cid)

        avz: 'AvailabilityZone' = task.get_simple_resource(availability_zone_id)
        site_id = avz.parent_id
        orchestrator_type: str = params.get("orchestrator_type")
        orchestrator_tag: str = params.get("orchestrator_tag")
        share_params: Dict = params.get("share_params")
        cluster: str = share_params.get("cluster")

        # select remote orchestrator with the same name as the cluster
        task.progress(step_id, msg="Searching for orchestrator of type %s with tag %s, for cluster %s" %
                      (orchestrator_type, orchestrator_tag, cluster))
        container: 'OntapNetappContainer' = None
        orchestrator,container = avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, cluster)

        cluster_fqdn = container.conn_params.get("host")
        task.progress(step_id,msg="Found container: %s. Now searching for emptiest aggregate" % container.name)

        # in alternative pass to this step the ext_id directly
        emptiest_aggregate,_max_space_available = container.conn2.get_svm_emptiest_aggregate(svm_name=share_params.get("svm"))

        task.progress(step_id,msg="Found emptiest aggregate: %s" % emptiest_aggregate)

        params["share_params"]["cluster"] = cluster_fqdn
        params["share_params"]["aggregate"] = emptiest_aggregate
        #params["share_params"]["aggregate_available_space"] = max_space_available # NB: this may become stale as the task continues

        task.progress(step_id, msg="Determining awx project")

        awx_orchestrator_tag = params.get("awx_orchestrator_tag")
        awx_project = task.controller.get_awx_project(
            customization_base_name="staas",
            awx_orchestrator_tag=awx_orchestrator_tag,
            site_id=site_id,
            raise_on_error=True
        )

        # if source share id present, determine and change it with the ontap volume one
        provider_from_id = share_params.pop("from_id", None)
        if provider_from_id:
            task.progress(step_id, msg="Determining physical source share")
            try:
                source_share: ComputeFileShareV2 = task.get_simple_resource(provider_from_id, ComputeFileShareV2)
            except Exception as ex:
                raise Exception("Source compute share %s not found" % provider_from_id) from ex
            try:
                from_id = source_share.main_physical_share.oid
            except Exception as ex:
                raise Exception("Error while querying source ontap volume") from ex
            share_params["from_id"] = from_id

        task.progress(step_id, msg="Creating zone resource")

        # create zone entity params
        vol_name = params.get("share_params").get("vol_name")
        share_params = {
            "orchestrator_type": orchestrator_type,
            "orchestrator_tag": orchestrator_tag,
            "orchestrator": orchestrator,
            "name": f"{vol_name}-avz{site_id}",
            "desc": f"Zone share {vol_name}",
            "parent": availability_zone_id,
            "share_params": params.get("share_params"),
            "attribute": {
                "main": True,
                "type": orchestrator_type,
                "tag": orchestrator_tag,
            },
            "awx_orchestrator_tag": awx_orchestrator_tag,
            "awx_project_id": awx_project.oid,
            "compliance": False,
        }
        if params.get("compliance"):
            share_params.update({
                "compliance":True,
                "compliance_share_params": params.get("compliance_share_params"),
            })

        prepared_task, _ = provider.resource_factory(FileShareV2, **share_params)
        share_id = prepared_task["uuid"]

        # link share to compute share
        task.get_session(reopen=True)
        task.progress(step_id, msg="Linking share %s to compute share %s" % (share_id, oid))
        compute_share = task.get_simple_resource(oid)
        compute_share.add_link(
            "%s-share-link" % share_id,
            "relation.%s" % site_id,
            share_id,
            attributes={},
        )

        if provider_from_id:
            # link source compute share to compute share
            task.get_session(reopen=True)
            task.progress(step_id, msg="Linking source share %s to compute share %s" % (provider_from_id, oid))
            source_share.add_link(
                f"snapmirror-{provider_from_id}-{oid}",
                "snapmirror",
                oid,
                attributes={},
            )

        # create id for task so we can log it and are able to track it later
        from uuid import uuid4
        new_task_id = str(uuid4())

        # run task and wait for it to complete
        task.progress(step_id, msg="Waiting until creation task %s finishes" % new_task_id)
        run_sync_task(prepared_task, task, step_id,custom_task_id=new_task_id)
        task.progress(step_id, msg="Created share %s in availability zone %s" % (share_id, availability_zone_id))

        return share_id, params

    @staticmethod
    @task_step()
    def link_replica_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        from_id: Union[str, int],
        *args,
        **kwargs,
    ):
        oid = params.get("id")

        source_share: ComputeFileShareV2 = task.get_simple_resource(from_id, ComputeFileShareV2)
        # link source compute share to compute share
        task.progress(step_id, msg="Linking source share %s to compute share %s" % (from_id, oid))
        source_share.add_link(
            f"snapmirror-{from_id}-{oid}",
            "snapmirror",
            oid,
            attributes={},
        )
        return True, params

    @staticmethod
    @task_step()
    def remove_source_link(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        *args, **kwargs
    ):
        oid = params.get("id")
        task.progress(step_id, msg="Getting replica source with id %s" % oid)
        provider_resource: ComputeFileShareV2 = task.get_simple_resource(oid)
        task.progress(step_id, msg="Removing source link")
        provider_resource.remove_source_link()
        return oid, params

    @staticmethod
    @task_step()
    def import_zone_share_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        availability_zone_id: Union[str, int],
        main: bool,
        *args,
        **kwargs,
    ):
        cid = params.get("cid")
        oid = params.get("id")

        task.progress(step_id, msg="Getting resources")
        provider = task.get_container(cid)

        avz: 'AvailabilityZone' = task.get_simple_resource(availability_zone_id)
        site_id = avz.parent_id
        orchestrator_type = params.get("orchestrator_type")
        orchestrator_tag = params.get("orchestrator_tag")

        task.progress(step_id, msg="Importing zone resource")

        # create zone entity params
        tmp_share_params = params.get("share_params")
        tmp_compliance_share_params = params.get("compliance_share_params")

        main_vol_name = tmp_share_params.get("vol_name")
        if not main:
            # compliance volume
            name = f"{main_vol_name}-C-avz{site_id}"
            description = f"Zone share compliance {main_vol_name}"
            inner_share_params = {
                'size': tmp_share_params.get("size"),
                'share_proto': tmp_share_params.get("share_proto"),
                'vol_name': tmp_share_params.get("vol_name"),
                'svm': tmp_compliance_share_params.get("snaplock_svm"),
                'cluster': tmp_compliance_share_params.get('snaplock_cluster'),
                'aggregate': tmp_compliance_share_params.get("snaplock_aggregate")
            }
            # if provider import these are all present
            if tmp_compliance_share_params.get("from_provider_import"):
                inner_share_params["from_provider_import"] = True
            if tmp_compliance_share_params.get("vol_name"):
                inner_share_params["vol_name"] = tmp_compliance_share_params.get("vol_name")
            #
            orchestrator = params.pop("compliance_orchestrator")
            compliance = False
        else:
            # normal "main" volume
            name = f"{main_vol_name}-avz{site_id}"
            description = f"Zone share {main_vol_name}"
            inner_share_params = params.get("share_params")
            cluster = inner_share_params.get("cluster")
            orchestrator,container = avz.get_orchestrator_and_container(orchestrator_type, orchestrator_tag, cluster)
            # TODO check these lines
            # OSS: cluster fqdn or cluster name?
            cluster_fqdn = container.conn_params.get("host")
            inner_share_params["cluster"] = cluster_fqdn
            compliance = params.get("compliance") # TODO serve o no?
            #inner_share_params["vol_ext_id"] = params.get("share_params").get("vol_ext_id")

        share_params = {
            "compliance": compliance,
            "orchestrator_type": orchestrator_type,
            "orchestrator_tag": orchestrator_tag,
            "orchestrator": orchestrator,
            "name": name,
            "desc": description,
            "parent": availability_zone_id,
            "share_params": inner_share_params,
            "attribute": {
                "main": main,
                "type": orchestrator_type,
                "tag": orchestrator_tag,
            },
        }

        prepared_task, _ = provider.resource_import_factory(FileShareV2, **share_params)
        share_id = prepared_task["uuid"]

        # link share to compute share
        task.get_session(reopen=True)
        task.progress(step_id, msg="Linking share %s to compute share %s" % (share_id, oid))
        compute_share = task.get_simple_resource(oid)
        compute_share.add_link(
            "%s-share-link" % share_id,
            "relation.%s" % site_id,
            share_id,
            attributes={},
        )

        # create id for task so we can log it and are able to track it later
        from uuid import uuid4
        new_task_id = str(uuid4())

        # run task and wait for it to complete
        task.progress(step_id, msg="Waiting until import task %s finishes" % new_task_id)
        run_sync_task(prepared_task, task, step_id,custom_task_id=new_task_id)
        task.progress(step_id, msg="Imported share %s in availability zone %s" % (share_id, availability_zone_id))

        return share_id, params

    @staticmethod
    @task_step()
    def send_action_to_zone_instance_step(
        task: 'AbstractProviderResourceTask',
        step_id: str,
        params: Dict,
        zone_instance_id: Union[str, int],
        *args, **kvargs
    ):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        oid = params.get("id")
        action_name = params.get("action_name")
        action_params = params.get("action_params")
        execute_in_single_transaction = action_params.get("execute_in_single_transaction", False)
        import_params = {
            "share_params": params.get("share_params"),
            "compliance_share_params": params.get("compliance_share_params"),
        }

        task.progress(step_id, msg="Getting resources")

        session = task.get_session()
        if execute_in_single_transaction:
            session = task.get_session_advanced()
            session.begin()

        try:
            pre_step_name = action_params.get("provider_inline_pre_step_function_name")

            resource = task.get_simple_resource(oid)
            zone_instance: 'FileShareV2' = task.get_resource(zone_instance_id)

            if pre_step_name:
                pre_step_function = getattr(resource, pre_step_name, None)
                if pre_step_function:
                    res = pre_step_function(session=session,**action_params)
                    if pre_step_name == "unlink_and_rename_resource_tree":
                        phy_new_name = res.get("phy_new_name")
                        if phy_new_name:
                            action_params["new_name"] = phy_new_name

            # get awx params
            awx_orchestrator_tag = params.get("awx_orchestrator_tag", "02")
            awx_params = task.get_awx_orchestrator_config(
                task, zone_instance.parent_id,
                awx_orchestrator_tag
            )
            awx_params["awx_project_id"] = params.get("awx_project_id")

            # send action
            prepared_task, _ = zone_instance.action(
                action_name, action_params=action_params, awx_params=awx_params, import_params=import_params
            )

            if not execute_in_single_transaction:
                task.get_session(reopen=True)

            task.progress(
                step_id,
                msg="Sending action to availability zone instance %s" % zone_instance_id,
            )
            res = run_sync_task(prepared_task, task, step_id)
            task.progress(step_id, msg="Avz action completed with result %s" % res)

            # clean cache
            resource.clean_cache()

            if execute_in_single_transaction:
                session.commit()
        except Exception as ex:
            if execute_in_single_transaction:
                task.logger.error("Rollback transaction")
                session.rollback()
            raise ex
        return res, params

    @staticmethod
    @task_step()
    def update_config_from_phy_instance_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        zone_instance_id: Optional[Union[str,int]],
        keys_to_update: List[Tuple[str, str]],
        *args,
        **kwargs
    ):
        task.progress(step_id, msg="Getting resources")

        optional_transforms = params.get("transforms", {})
        if not isinstance(optional_transforms, dict):
            raise TypeError("Expected 'transforms' to be a dictionary")

        oid = params.get("id")
        provider_resource: ComputeFileShareV2 = task.get_simple_resource(oid)
        if zone_instance_id:
            zone_resource: FileShareV2 =  task.get_resource(zone_instance_id)
        else:
            # TODO always use this?
            zone_resource = provider_resource.main_zone_share
        phy_resource: OntapNetappVolume = zone_resource.physical_share

        task.progress(step_id, msg="Updating. Keys to update: %s" % keys_to_update)

        # keys are dest keys for which to apply the relevant transforms
        default_transforms: Dict[str, Callable[[Any], Any]] = {
            "size": lambda x: int(float(x))
        }
        _transforms = {**default_transforms, **optional_transforms}

        for source, dest in keys_to_update:
            new_value = phy_resource.get_attribs(source)
            if new_value:
                transform = _transforms.get(dest)
                if transform and callable(transform):
                    new_value = transform(new_value)
                provider_resource.set_configs(dest,new_value)
            else:
                raise Exception(f"Key {source} not found in physical resource attributes. Can't update provider resource")

        task.progress(step_id, msg="updated successfully")
        return True, params

    @staticmethod
    @task_step()
    def remove_child_step(
        task: 'AbstractProviderResourceTask',
        step_id: str,
        params: Dict,
        resource_id: Union[str, int],
        *args, **kwargs
    ):
        """Remove compute resource childs.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param resource_id: id of the resource to delete
        :return: True, params
        """
        source_info = params.get("source_info")
        compliance = params.get("compliance", False)
        awx_project_id = params.get("awx_project_id")
        awx_orchestrator_tag = params.get("awx_orchestrator_tag")
        resource: 'FileShareV2' = task.get_resource(resource_id)

        res_params = {
            "sync": True,
            "compliance": compliance,
        }
        if source_info:
            res_params["source_info"] = source_info
        if awx_project_id:
            res_params["awx_project_id"] = awx_project_id
        if awx_orchestrator_tag:
            res_params["awx_orchestrator_tag"] = awx_orchestrator_tag
        # delete child
        prepared_task, code = resource.expunge(**res_params)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Remove child %s" % resource_id)

        return True, params

    @staticmethod
    @task_step()
    def update_config(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        keys_to_update: List[Dict[str, Union[str,int]]],
        *args,
        **kwargs
    ):
        oid = params.get("id")
        action_name = params.get("action_name")
        provider_resource: ComputeFileShareV2 = task.get_simple_resource(oid)
        if action_name == "compliance_enable":
            for item in keys_to_update:
                k, v = next(iter(item.items()))
                if isinstance(v, int):
                    v = str(v)
                provider_resource.set_configs(k, v)
        elif action_name == "compliance_disable":
            for item in keys_to_update:
                k = list(item.keys())[0]
                provider_resource.unset_configs(k)
        return True, params

#
# Availability zone level steps
#
    @staticmethod
    @task_step()
    def remove_physical_resource_step(
        task: 'AbstractProviderResourceTask',
        step_id: str,
        params: Dict,
        orchestrator_id,
        orchestrator_type: str,
        *args, **kwargs
    ):
        """Delete resource in remote orchestrator

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        task.progress(step_id, msg="Getting resources")

        source_info = params.get("source_info", {})
        compliance = params.get("compliance", False)
        awx_project_id = params.get("awx_project_id")
        resource = params.get("id")

        awx_params = None
        if awx_project_id:
            # select awx orchestrator and get awx params
            awx_orchestrator_tag = params.get("awx_orchestrator_tag", "02")
            availability_zone_id = params.get("parent")
            awx_params = task.get_awx_orchestrator_config(
                task,
                availability_zone_id,
                awx_orchestrator_tag
            )
            awx_params["awx_project_id"] = params.get("awx_project_id")
            #

        # get all child resources
        task.progress(step_id, msg="Getting child resources")
        children = task.get_orm_linked_resources(resource, link_type="relation", container_id=orchestrator_id)
        logger.debug("+++++ remove_physical_resource_step - children: %s", children)

        # get helper and call specific remove method
        if orchestrator_type!='ontap':
            raise Exception("Unsupported orchestrator %s" % orchestrator_type)

        helper = task.get_orchestrator(orchestrator_type, task, step_id, {"id": orchestrator_id}, resource)
        logger.debug("+++++ remove_physical_resource_step - helper: %s", type(helper))

        resp = helper.remove_resource(children, source_info=source_info, compliance=compliance, awx_params=awx_params)
        task.progress(step_id, msg='Removed remote resources: %s' % resp)

        return True, params

    @staticmethod
    @task_step()
    def create_physical_share_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: Dict,
        *args, **kwargs
    ):
        """Create zone share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        task.progress(step_id, msg="Getting params")
        oid = params.get("id")

        # get container
        orchestrator = params.get("orchestrator")
        ontap_container = task.get_container(orchestrator["id"])

        task.progress(step_id, msg="Determining awx container and parameters")

        # select awx orchestrator and get awx params
        awx_orchestrator_tag = params.get("awx_orchestrator_tag", "02")
        availability_zone_id = params.get("parent")
        awx_params = task.get_awx_orchestrator_config(
            task,
            availability_zone_id,
            awx_orchestrator_tag
        )
        awx_params["awx_project_id"] = params.get("awx_project_id")
        #

        task.progress(step_id, msg="Creating physical resource")

        # create remote share
        share_params = params.get("share_params")
        vol_name = share_params.pop("vol_name",None)
        volume_params = {
            "name": vol_name,
            "desc": f"volume {vol_name}",
            "role": share_params.pop("share_role",None),
            "awx_params": awx_params,
            "share_params": share_params,
        }
        if params.get("compliance"):
            volume_params.update({
                "compliance":True,
                "compliance_share_params": params.get("compliance_share_params"),
            })

        prepared_task, _ = ontap_container.resource_factory(OntapNetappVolume, **volume_params, sync=True)
        volume_id = prepared_task.get("uuid")

        # link ontap volume to share
        task.get_session(reopen=True)
        share = task.get_simple_resource(oid)
        task.progress(step_id, msg="Linking volume %s to zone share %s" % (volume_id, oid))
        share.add_link(
            "%s-%s-link" % (id_gen(), oid),
            "relation",
            volume_id,
            attributes={}
        )

        # create id for task so we can log it and are able to track it later
        from uuid import uuid4
        new_task_id = str(uuid4())

        task.progress(step_id, msg="Waiting until creation task %s finishes." % new_task_id)
        run_sync_task(prepared_task, task, step_id, custom_task_id=new_task_id)
        task.progress(step_id, msg="Created volume %s in zone %s" % (volume_id, oid))
        return volume_id, params

    @staticmethod
    @task_step()
    def send_action_to_phyres_step(
        task: 'AbstractProviderResourceTask',
        step_id: str,
        params: Dict,
        phyvol_id: Union[str, int],
        *args, **kvargs
    ):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        task.progress(step_id, msg="Getting resources")

        action_name = params.get("action_name")
        action_params = params.get("action_params")
        awx_params = params.get("awx_params")
        import_params = params.get("import_params")
        execute_in_single_transaction = action_params.get("execute_in_single_transaction", False)

        phyvol = task.get_resource(phyvol_id)
        if phyvol is None:
            raise Exception("Physical volume %s not found" % phyvol_id)

        # get action params
        task.progress(
            step_id,
            msg="Sending action to physical volume %s" % phyvol_id,
        )
        action_func = getattr(phyvol, action_name, None)
        if action_func is None:
            logger.error("Unsupported action %s for resource %s", action_name, phyvol_id)
            raise Exception(f"Unsupported action {action_name} for resource {phyvol_id}")

        if not callable(action_func):
            logger.error("%s in class %s is not a callable", action_name, phyvol.__class__.__name__)
            raise Exception("action %s is not a callable" % action_name)

        # send action
        prepared_task, _ = action_func(**action_params, awx_params=awx_params, **import_params)

        if not execute_in_single_transaction:
            task.get_session(reopen=True)

        res = run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Physical volume action %s completed with result %s" % (action_name, res)
        )

        return res, params

    @staticmethod
    @task_step()
    def detach_compliance_physical_resource_step(
        task: 'AbstractProviderResourceTask',
        step_id: str,
        params: Dict,
        *args, **kwargs
    ):
        task.progress(step_id, msg="Getting params")
        oid = params.get("id")

        zone_res: 'FileShareV2' = task.get_resource(oid)
        if zone_res is None:
            raise Exception("Physical volume %s not found" % zone_res)

        task.progress(step_id, msg="Searching for physical snaplock volume resource")

        snaplock_link, tot = zone_res.get_links(type="relation")
        if tot==0:
            task.logger.error("Physical resource link missing for zone resource %s", zone_res.uuid)
            task.progress(step_id, msg="Physical resource link missing for zone resource %s. Skipping deletion." % zone_res.uuid)
        elif tot>1:
            task.logger.error("More than one physical resource link found for zone resource %s", zone_res.uuid)
            raise Exception("More than one physical resource link found for zone resource %s" % zone_res.uuid)
        else:
            task.progress(step_id, msg="Snaplock volume found. Setting metadata and removing link.")
            snaplock_link = snaplock_link[0]
            snaplock_resource = zone_res.physical_share
            snaplock_resource.delete_snaplock_relationship()
            snaplock_resource.schedule_for_deletion(days_offset=30)
            snaplock_link.expunge()
        return True, params

    @staticmethod
    @task_step()
    def import_physical_share_step(
        task: AbstractProviderResourceTask,
        step_id: str,
        params: 'FileShareV2_ImportPhysicalShareStepParams',
        *args, **kwargs
    ):
        """Import phy share

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        task.progress(step_id, msg="Getting params")
        oid = params.get("id")

        # get container
        orchestrator = params.get("orchestrator")
        ontap_container = task.get_container(orchestrator["id"])

        task.progress(step_id, msg="Importing physical resource")

        share_params: 'FileShareV2_ImportPhysicalShareStepParams_ShareParams' = params.get("share_params")
        # create remote share
        main_vol_name = share_params.pop("vol_name", None)
        compliance_vol_name =  share_params.pop("compliance_vol_name", None)

        if not main_vol_name and not compliance_vol_name:
            raise Exception("volume name missing")

        main = params.get("attribute").get("main")
        if not main:
            role ="snaplock"
            if compliance_vol_name: # used only for snaplock import
                vol_name = compliance_vol_name
            else:
                vol_name = OntapNetappVolume.determine_compliance_name(main_vol_name)
        else:
            # in theory should always be set
            # main for main, dr for replica
            role = share_params.pop("share_role", "main")
            vol_name = OntapNetappVolume.format_name_for_cmp(main_vol_name)

        volume_params = {
            "role": role,
            "name": vol_name,
            "desc": f"volume {vol_name}",
            "share_params": share_params,
            "compliance": False
        }

        vol_ext_id = share_params.get("vol_ext_id")
        if vol_ext_id:
            # for main volume import
            volume_params["vol_ext_id"] = vol_ext_id

        #if params.get("compliance"): # TODO check (credo da rimuovere tutto il blocco)
        #    volume_params.update({
        #        "compliance":True,
        #        "compliance_share_params": params.get("compliance_share_params"),
        #    })

        prepared_task, _ = ontap_container.resource_import_factory(OntapNetappVolume, **volume_params, sync=True)
        volume_id = prepared_task.get("uuid")

        # link ontap volume to share
        task.get_session(reopen=True)
        share = task.get_simple_resource(oid)
        task.progress(step_id, msg="Linking volume %s to zone share %s" % (volume_id, oid))
        share.add_link(
            "%s-%s-link" % (id_gen(), oid),
            "relation",
            volume_id,
            attributes={}
        )

        # create id for task so we can log it and are able to track it later
        from uuid import uuid4
        new_task_id = str(uuid4())

        task.progress(step_id, msg="Waiting until creation task %s finishes." % new_task_id)
        run_sync_task(prepared_task, task, step_id, custom_task_id=new_task_id)
        task.progress(step_id, msg="Created volume %s in zone %s" % (volume_id, oid))
        return volume_id, params
