# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from copy import deepcopy
import ujson as json
from logging import getLogger
from beecell.simple import truncate, str2bool, id_gen
from beehive.common.task.job import JobError
from beehive_resource.model import ResourceState
from beehive_resource.plugins.provider.entity.applied_customization import (
    AppliedComputeCustomization,
)
from beehive_resource.plugins.provider.entity.base import orchestrator_mapping
from beehive_resource.plugins.provider.entity.instance import ComputeInstance, Instance
from beehive_resource.plugins.provider.entity.volume import ComputeVolume
from beehive.common.task_v2 import task_step, run_sync_task
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask

logger = getLogger(__name__)


class PostAction(object):
    @staticmethod
    def set_flavor(task, resource, configs):
        links, total = resource.get_links(type="flavor")
        links[0].expunge()

        # link new flavor to instance
        flavor = configs.get("flavor")
        resource.add_link("%s-flavor-link" % resource.oid, "flavor", flavor, attributes={})

    @staticmethod
    def add_volume(task, resource, configs):
        links, total = resource.get_links(type="volume%")
        index = total + 1

        # link new volume to instance
        volume = configs.get("volume")
        resource.add_link(
            "%s-%s-volume-link" % (resource.oid, volume),
            "volume.%s" % index,
            volume,
            attributes={},
        )

    @staticmethod
    def del_volume(task, resource, configs):
        volume = configs.get("volume")
        links, total = resource.get_out_links(end_resource=volume)
        links[0].expunge()

    @staticmethod
    def extend_volume(task, resource, configs):
        volume_size = configs.get("volume_size")
        volume = configs.get("volume")
        links, total = resource.get_out_links(end_resource=volume)
        volume = links[0].get_end_resource()
        volume.set_configs(key="configs.size", value=volume_size)

    @staticmethod
    def add_security_group(task, resource, configs):
        # link new security group to instance
        sg_id = configs.get("security_group")
        resource.add_link(
            "%s-%s-security-group-link" % (resource.oid, sg_id),
            "security-group",
            sg_id,
            attributes={},
        )

    @staticmethod
    def del_security_group(task, resource, configs):
        sg_id = configs.get("security_group")
        links, total = resource.get_out_links(end_resource=sg_id)
        links[0].expunge()


class ComputeInstanceTask(AbstractProviderResourceTask):
    """ComputeInstance task"""

    name = "compute_instance_task"
    entity_class = ComputeInstance

    def __init__(self, *args, **kwargs):
        super(ComputeInstanceTask, self).__init__(*args, **kwargs)

    @staticmethod
    @task_step()
    def link_compute_instance_step(task, step_id, params, *args, **kvargs):
        """Create main links

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        oid = params.get("id")
        networks = params.get("networks")
        flavor_id = params.get("flavor")
        sg_ids = params.get("security_groups")

        resource = task.get_simple_resource(oid)
        task.progress(step_id, msg="get resource %s" % oid)

        # link flavor to instance
        resource.add_link("%s-flavor-link" % oid, "flavor", flavor_id, attributes={})
        task.progress(step_id, msg="Link flavor %s to instance %s" % (flavor_id, oid))

        # - link networks to instance
        for network in networks:
            vpc_id = network["vpc"]
            subnet = network["subnet"]
            fixed_ip = network.get("fixed_ip", None)
            attribs = {"subnet": subnet.get("cidr")}
            if fixed_ip is not None:
                attribs = {"subnet": subnet.get("cidr"), "fixed_ip": fixed_ip}
            resource.add_link("%s-%s-vpc-link" % (oid, vpc_id), "vpc", vpc_id, attributes=attribs)
            task.progress(step_id, msg="Link vpc %s to instance %s" % (vpc_id, oid))

        # - link security groups to instance
        for sg_id in sg_ids:
            resource.add_link(
                "%s-%s-security-group-link" % (oid, sg_id),
                "security-group",
                sg_id,
                attributes={},
            )
            task.progress(step_id, msg="Link security group %s to instance %s" % (sg_id, oid))

        return oid, params

    @staticmethod
    @task_step()
    def create_compute_volume_step(task, step_id, params, block_device, *args, **kvargs):
        """Create compute instance volume

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param block_device: block_device config
        :return: physical resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        parent = params.get("parent")
        boot_index = block_device.get("boot_index")
        source_type = block_device.get("source_type")
        from_template = block_device.get("from_template", False)
        availability_zone_id = params.get("main_availability_zone")
        attribute = params.get("attribute")
        image_id = None
        task.progress(step_id, msg="Set configuration params")

        # get has_quotas
        has_quotas = attribute.get("has_quotas", True)

        provider = task.get_container(cid)
        resource = task.get_simple_resource(oid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        task.progress(step_id, msg="Get resource %s" % oid)

        # create new volume
        if source_type in ["image", "snapshot", None]:
            metadata = block_device.get("metadata", {})
            metadata["from_template"] = from_template

            # create zone volume params
            volume_params = {
                "parent": parent,
                "name": "%s-volume-%s" % (params.get("name"), boot_index),
                "desc": "Availability Zone volume %s" % params.get("desc"),
                "compute_zone": params.get("parent"),
                "orchestrator_tag": params.get("orchestrator_tag"),
                "availability_zone": site_id,
                "multi_avz": False,
                "type": params.get("type"),
                "flavor": block_device.get("flavor"),
                "metadata": metadata,
                "size": block_device.get("volume_size"),
                "sync": True,
            }

            if source_type == "image":
                volume_params["image"] = block_device.get("uuid")
            elif source_type == "snapshot":
                volume_params["snapshot"] = block_device.get("uuid")

            prepared_task, code = provider.resource_factory(ComputeVolume, has_quotas=has_quotas, **volume_params)
            volume_id = prepared_task["uuid"]

            # link volume to instance
            task.get_session(reopen=True)
            volume = task.get_simple_resource(volume_id)
            resource.add_link(
                "%s-volume-%s-link" % (oid, volume.oid),
                "volume.%s" % boot_index,
                volume.oid,
                attributes={},
            )
            task.progress(step_id, msg="Link volume %s to instance %s" % (volume_id, oid))

            # link image to instance
            if source_type == "image":
                image_id = block_device.get("uuid")
                resource.add_link("%s-image-link" % oid, "image", image_id, attributes={})
                task.progress(step_id, msg="Link image %s to instance %s" % (image_id, oid))

            # wait task complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(
                step_id,
                msg="Create volume %s in availability zone %s" % (volume_id, availability_zone_id),
            )

        # use existing volume
        elif source_type in ["volume"]:
            metadata = block_device.get("metadata", {})
            metadata["from_template"] = from_template
            orig_volume_id = block_device.get("uuid")
            orig_volume = task.get_simple_resource(orig_volume_id)

            # create zone volume params
            volume_params = {
                "parent": parent,
                "name": "%s-volume-%s" % (params.get("name"), boot_index),
                "desc": "Availability Zone volume %s" % params.get("desc"),
                "compute_zone": params.get("parent"),
                "orchestrator_tag": params.get("orchestrator_tag"),
                "availability_zone": site_id,
                "multi_avz": False,
                "type": params.get("type"),
                "flavor": block_device.get("flavor"),
                "metadata": metadata,
                "size": block_device.get("volume_size"),
                "volume": orig_volume_id,
                "sync": True,
            }

            prepared_task, code = provider.resource_factory(ComputeVolume, has_quotas=has_quotas, **volume_params)
            volume_id = prepared_task["uuid"]

            # link volume to instance
            task.get_session(reopen=True)
            volume = task.get_simple_resource(volume_id)
            resource.add_link(
                "%s-volume-%s-link" % (oid, volume.oid),
                "volume.%s" % boot_index,
                volume.oid,
                attributes={},
            )
            task.progress(step_id, msg="Link volume %s to instance %s" % (volume_id, oid))

            # wait task complete
            run_sync_task(prepared_task, task, step_id)
            task.progress(
                step_id,
                msg="Create volume %s in availability zone %s" % (volume_id, availability_zone_id),
            )

            # link image to instance
            images, tot = orig_volume.get_linked_resources(link_type="image")
            # volume is boot
            if len(images) > 0:
                image_id = images[0].uuid
                resource.add_link("%s-image-link" % oid, "image", image_id, attributes={})
                task.progress(step_id, msg="Link image %s to instance %s" % (image_id, oid))

            # volume_id = block_device.get('uuid')
            #
            # # link volume to instance
            # task.get_session(reopen=True)
            # volume = task.get_simple_resource(volume_id)
            # resource.add_link('%s-volume-%s-link' % (oid, volume.oid), 'volume.%s' % boot_index, volume.oid,
            #                   attributes={})
            # task.progress(step_id, msg='Link volume %s to instance %s' % (volume_id, oid))
            #
            # # link image to instance
            # images, tot = volume.get_linked_resources(link_type='image')
            # image_id = images[0].uuid
            # resource.add_link('%s-image-link' % oid, 'image', image_id, attributes={})
            # task.progress(step_id, msg='Link image %s to instance %s' % (image_id, oid))

        task.progress(step_id, msg="Update shared area")
        return volume_id, params

    @staticmethod
    @task_step()
    def remove_wrong_compute_volumes_step(task, step_id, params, *args, **kvargs):
        """Remove wrong compute volumes from compute instance

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: physical resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        compute_instance = provider.get_simple_resource(oid)

        # get linked volumes
        volumes = compute_instance.get_volumes()
        for volume in volumes:
            # remove zone volume
            zone_volumes = task.controller.get_directed_linked_resources_internal(
                resources=[volume.oid], link_type="relation%"
            )
            for zone_volume in zone_volumes.get(volume.oid):
                zone_volume.expunge_internal()
                task.progress(step_id, msg="Remove zone volume %s" % zone_volume.oid)

            # remove compute volume
            volume.expunge_internal()
            task.progress(step_id, msg="Remove compute volume %s" % volume.oid)

        return oid, params

    @staticmethod
    @task_step()
    def import_compute_volumes_step(task, step_id, params, *args, **kvargs):
        """Import compute volumes from a physical server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: physical resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        image_id = params.get("image_id", None)
        physical_server_id = params.get("physical_id", None)

        provider = task.get_container(cid)
        compute_instance = task.get_resource(oid)

        # link image to instance
        if image_id is not None:
            compute_instance.add_link("%s-image-link" % oid, "image", image_id, attributes={})
            task.progress(step_id, msg="Link image %s to instance %s" % (image_id, oid))

        # get linked volumes
        volumes = compute_instance.get_volumes()
        volume_uuids = []
        for volume in volumes:
            phvolume = volume.get_physical_volume()
            if phvolume is not None:
                volume_uuids.append(phvolume.uuid)
        task.progress(
            step_id,
            msg="Get linked volumes to instance %s: %s" % (oid, truncate(volumes)),
        )

        # get physical instance
        if compute_instance.physical_server is None and physical_server_id is None:
            raise JobError("Physical resource for compute instance %s does not exist" % compute_instance.uuid)

        if compute_instance.physical_server is not None:
            physical_volumes = compute_instance.physical_server.get_volumes()
        else:
            physical_server = task.get_resource(physical_server_id)
            physical_volumes = physical_server.get_volumes()
        task.progress(
            step_id,
            msg="Get physical volumes %s: %s" % (oid, truncate(physical_volumes)),
        )
        # task.logger.warn(physical_volumes)
        # raise Exception('')

        # run import volume task
        index = 1
        for physical_volume in physical_volumes:
            if physical_volume.get("uuid") not in volume_uuids:
                bootable = str2bool(physical_volume.get("bootable"))
                if bootable is True:
                    boot_index = 0
                else:
                    boot_index = index
                    index += 1
                data = {
                    "parent": compute_instance.parent_id,
                    "name": "%s-volume-%s" % (params.get("name"), boot_index),
                    "desc": "Availability Zone volume %s" % params.get("desc"),
                    "physical_id": physical_volume.get("uuid"),
                    "sync": True,
                }
                logger.warn(physical_volume)
                prepared_task, code = provider.resource_import_factory(ComputeVolume, **data)
                volume_id = prepared_task["uuid"]
                run_sync_task(prepared_task, task, step_id)
                task.progress(
                    step_id,
                    msg="Import instance volume %s" % physical_volume.get("uuid"),
                )

                # link volume to instance
                task.get_session(reopen=True)
                volume = task.get_simple_resource(volume_id)
                compute_instance.add_link(
                    "%s-volume-%s-link" % (oid, volume.oid),
                    "volume.%s" % boot_index,
                    volume.oid,
                    attributes={},
                )
                task.progress(step_id, msg="Link volume %s to instance %s" % (volume_id, oid))

        return True, params

    @task_step()
    def import_restored_server_step(task, step_id, params, *args, **kvargs):
        """Import a new server restored from backup

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        name = params.get("instance_name")
        restore_point = params.get("restore_point")
        physical_server_id = params.get("last_step_response")

        provider = task.get_container(cid)
        compute_instance = task.get_resource(oid)
        compute_zone = compute_instance.get_parent()

        new_objid = "%s//%s" % (compute_zone.objid, id_gen())
        new_desc = "%s restored from %s" % (name, restore_point)
        image_id = compute_instance.image.oid
        key_name = compute_instance.get_key_name()
        admin_pass = compute_instance.get_credential(username="root").get("password")

        restore_data = {
            "objid": new_objid,
            "parent": compute_zone.oid,
            "cid": cid,
            "name": name,
            "desc": new_desc,
            "ext_id": None,
            "active": False,
            "attribute": {},
            "tags": "",
            "physical_id": physical_server_id,
            "configs": {
                "multi_avz": True,
                "orchestrator_tag": "default",
                "hostname": name,
                "key_name": key_name,
                "admin_pass": admin_pass,
                "image": image_id,
                "resolve": True,
                "manage": True,
            },
            "sync": True,
        }
        prepared_task, code = provider.resource_import_factory(ComputeInstance, **restore_data)
        res = run_sync_task(prepared_task, task, step_id)
        instance_uuid = task.get_simple_resource(res).uuid
        task.progress(
            step_id,
            msg="Import restored server %s in compute instance: %s" % (physical_server_id, instance_uuid),
        )
        params["result"] = instance_uuid
        return instance_uuid, params

    @staticmethod
    @task_step()
    def create_zone_instance_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create compute instance zone instance

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: physical resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        admin_username = params.get("admin_username")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        task.progress(step_id, msg="Get resources")

        image_id = None
        flavor_id = None

        # get availability zone rule group
        security_groups = []
        for sg_id in params.get("security_groups"):
            rule_group = task.get_orm_linked_resources(sg_id, link_type="relation.%s" % site_id)[0]
            security_groups.append(rule_group.id)

        # verify instance is main or twin
        # - instance is main
        if availability_zone_id == params.get("main_availability_zone"):
            # set main to True because it is the main zone instance
            main = True

            # get availability zone image
            # compute_image = task.get_resource(params.get('image'))
            image_obj = task.get_orm_linked_resources(oid, link_type="image")[0]
            image = task.get_orm_linked_resources(image_obj.id, link_type="relation.%s" % site_id)[0]
            image_id = image.id

            # get availability zone flavor
            # compute_flavor = task.get_resource(params.get('flavor'))
            flavor = task.get_orm_linked_resources(params.get("flavor"), link_type="relation.%s" % site_id)[0]
            flavor_id = flavor.id

            # get availability zone network
            networks = []
            for network in params.get("networks"):
                nets = task.get_orm_linked_resources(network["vpc"], link_type="relation.%s" % site_id)[0]
                networks.append(
                    {
                        "vpc": network["vpc"],
                        "id": nets.id,
                        "subnet": network.get("subnet"),
                        # 'other_subnets': network.get('other_subnets'),
                        "fixed_ip": network.get("fixed_ip", {}),
                    }
                )

        # - instance is a twin. Get fixed ip from main instance
        else:
            # set main to False because this main zone instance is a twin
            main = False

            # get availability zone network
            networks = []
            for network in params.get("networks"):
                # get fixed_ip from compute instance and vpc link. fixed ip is set previously by main zone instance
                link = task.get_orm_link_among_resources(oid, network["vpc"])
                attributes = json.loads(link.attributes)
                nets = task.get_orm_linked_resources(network["vpc"], link_type="relation.%s" % site_id)
                if len(nets) < 1:
                    # vpc has no network in this site
                    task.progress(
                        step_id,
                        msg="Vpc %s does not have network in availability zone %s"
                        % (network["vpc"], availability_zone_id),
                    )
                    return None, params
                else:
                    nets = nets[0]
                networks.append(
                    {
                        "vpc": network["vpc"],
                        "id": str(nets.id),
                        "subnet": network.get("subnet"),
                        "fixed_ip": attributes.get("fixed_ip", {}),
                    }
                )

        if admin_username is None:
            # Discriminate admin user by image across compute instance;
            # It can be root or non root sudoer
            current_compute_instance = task.get_resource(oid)
            admin_username = current_compute_instance.get_real_admin_user()

        # create zone instance params
        instance_params = {
            "type": params.get("type"),
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Availability Zone instance %s" % params.get("desc"),
            "hostname": params.get("name"),
            "parent": availability_zone_id,
            "compute_instance": oid,
            "orchestrator_tag": params.get("orchestrator_tag"),
            # "orchestrator_select_types": params.get("orchestrator_select_types"),
            "host_group": params.get("host_group"),
            "image": image_id,
            "flavor": flavor_id,
            "security_groups": security_groups,
            "networks": networks,
            "admin_pass": params.get("admin_pass"),
            "admin_username": admin_username,
            "user_data": params.get("user_data"),
            "metadata": params.get("metadata"),
            "personality": params.get("personality"),
            "main": main,
            "clone_source_uuid": params.get("clone_source_uuid"),
            "attribute": {"main": main, "type": params.get("type"), "configs": {}},
        }
        prepared_task, code = provider.resource_factory(Instance, **instance_params)
        instance_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Create instance %s in availability zone %s" % (instance_id, availability_zone_id),
        )

        return instance_id, params

    @staticmethod
    @task_step()
    def import_zone_instance_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Import compute_instance instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: physical resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id

        # get availability zone rule group
        security_groups = []
        for sg_id in params.get("security_groups"):
            rule_group = task.get_orm_linked_resources(sg_id, link_type="relation.%s" % site_id)[0]
            security_groups.append(rule_group.id)

        # verify instance is main or twin
        # - instance is main
        if availability_zone_id == params.get("main_availability_zone"):
            # set main to True because it is the main zone instance
            main = True

            # get availability zone network
            networks = params.get("networks")

        # - instance is a twin. Get fixed ip from main instance
        else:
            # set main to False because this main zone instance is a twin
            main = False

            # get availability zone network
            networks = []
            for network in params.get("networks"):
                # get fixed_ip from compute instance and vpc link. fixed ip is set previously by main zone instance
                link = task.get_orm_link_among_resources(oid, network["vpc"])
                attributes = json.loads(link.attributes)
                nets = task.get_orm_linked_resources(network["vpc"], link_type="relation.%s" % site_id)
                if len(nets) < 1:
                    # vpc has no network in this site
                    task.progress(
                        step_id,
                        msg="Vps %s does not have network in availability zone %s"
                        % (network["vpc"], availability_zone_id),
                    )
                    return None
                else:
                    nets = nets[0]
                networks.append(
                    {
                        "vpc": network["vpc"],
                        "id": str(nets.id),
                        "subnet": network.get("subnet"),
                        "fixed_ip": attributes.get("fixed_ip", {}),
                    }
                )

        # create zone instance params
        instance_params = {
            "type": params.get("type"),
            "name": "%s-avz%s" % (params.get("name"), site_id),
            "desc": "Availability Zone instance %s" % params.get("desc"),
            # 'hostname': params.get('name'),
            "parent": availability_zone_id,
            "compute_instance": oid,
            "physical_server_id": params.get("physical_id"),
            "orchestrator_tag": params.get("orchestrator_tag"),
            # 'host_group': params.get('host_group'),
            # # 'image': image_id,
            # 'image': image_id,
            # 'flavor': flavor_id,
            "security_groups": security_groups,
            "networks": networks,
            # 'admin_pass': params.get('admin_pass'),
            # 'block_device_mapping': params.get('block_device_mapping'),
            # 'user_data': params.get('user_data'),
            # 'metadata': params.get('metadata'),
            # 'personality': params.get('personality'),
            "main": main,
            "attribute": {"main": main, "type": params.get("type"), "configs": {}},
        }
        prepared_task, code = provider.resource_import_factory(Instance, **instance_params)
        instance_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(
            step_id,
            msg="Import instance %s in availability zone %s" % (instance_id, availability_zone_id),
        )

        return instance_id, params

    @staticmethod
    @task_step()
    def manage_compute_instance_step(task, step_id, params, *args, **kvargs):
        """Register compute instance in ssh module

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        oid = params.get("id")
        manage = params.get("manage")

        compute_instance: ComputeInstance = task.get_simple_resource(oid)
        compute_instance.post_get()

        if manage is True:
            user = compute_instance.get_real_admin_user()
            uuid = compute_instance.manage(user=user, key=params.get("key_name"), password=params.get("admin_pass"))
            task.progress(step_id, msg="Manage instance %s with ssh node %s" % (oid, uuid))

        return oid, params

    @staticmethod
    @task_step()
    def unmanage_compute_instance_step(task, step_id, params, *args, **kvargs):
        """Deregister compute_instance from ssh module

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        oid = params.get("id")

        compute_instance = task.get_simple_resource(oid)

        if compute_instance.is_managed() is True:
            uuid = compute_instance.unmanage()
            task.progress(step_id, msg="Manage instance %s with ssh node %s" % (oid, uuid))

        return oid, params

    @staticmethod
    @task_step()
    def register_dns_compute_instance_step(task, step_id, params, *args, **kvargs):
        """Register compute_instance in dns

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        oid = params.get("id")
        resolve = params.get("resolve")
        compute_instance = task.get_simple_resource(oid)

        uuid = None
        if resolve is True:
            try:
                uuid = compute_instance.set_dns_recorda(force=True)
                task.progress(
                    step_id,
                    msg="Register instance %s in dns with record: %s" % (oid, uuid),
                )
            except Exception as ex:
                task.progress(
                    step_id,
                    msg="Error - Register instance %s in dns with record %s: %s" % (oid, uuid, ex),
                )
                raise JobError("Register instance %s in dns: %s" % (oid, ex))
        else:
            task.progress(step_id, msg="Do not register instance %s in dns" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def deregister_dns_compute_instance_step(task, step_id, params, *args, **kvargs):
        """Deregister compute_instance from dns

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        oid = params.get("id")
        compute_instance = task.get_simple_resource(oid)

        if compute_instance.get_dns_recorda() is not None:
            uuid = compute_instance.unset_dns_recorda()
            task.progress(step_id, msg="Unregister instance %s record %s from dns" % (oid, uuid))

        return oid, params

    @staticmethod
    @task_step()
    def remove_compute_volume_step(task, step_id, params, volume_id, *args, **kvargs):
        """Remove compute volume.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        resource = task.get_simple_resource(oid)

        links, total = resource.get_out_links(end_resource=volume_id)
        links[0].expunge()
        task.progress(step_id, msg="Remove volume link %s" % volume_id)

        return True, params

    @staticmethod
    @task_step()
    def send_action_to_zone_instance_step(task, step_id, params, zone_instance_id, *args, **kvargs):
        """Send action to zone instance.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        cid = params.get("cid")
        oid = params.get("id")
        action = params.get("action_name")
        configs = deepcopy(params)
        configs["id"] = zone_instance_id
        hypervisor = params.get("hypervisor")
        hypervisor_tag = params.get("hypervisor_tag")

        resource = task.get_simple_resource(oid)
        zone_instance = task.get_resource(zone_instance_id)
        task.progress(step_id, msg="Get resources")

        # send action
        prepared_task, code = zone_instance.action(action, configs, hypervisor, hypervisor_tag)
        task.progress(
            step_id,
            msg="Send action to availability zone instance %s" % zone_instance_id,
        )
        res = run_sync_task(prepared_task, task, step_id)

        # clean cache
        resource.clean_cache()

        # run action post operation only for main zone instance
        if resource.get_main_zone_instance().oid == zone_instance_id:
            post_action = getattr(PostAction, action, None)
            if post_action is not None:
                post_action(task, resource, configs)

        return res, params

    @staticmethod
    @task_step()
    def pass_certificate_step(task, step_id, params, *args, **kvargs):
        """Get certificate from stdout of previous step and add to extra_vars

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        computeInstanceTask: ComputeInstanceTask = task
        computeInstanceTask.logger.debug("+++++ pass_certificate_step - params: {}".format(params))
        computeInstanceTask.logger.debug("+++++ pass_certificate_step - args: {}".format(args))
        computeInstanceTask.logger.debug("+++++ pass_certificate_step - kvargs: {}".format(kvargs))

        shared_data = computeInstanceTask.get_shared_data()
        computeInstanceTask.logger.debug("+++++ pass_certificate_step - shared_data: {}".format(shared_data))
        stdout_data = computeInstanceTask.get_stdout_data()
        computeInstanceTask.logger.debug("+++++ pass_certificate_step - stdout_data: {}".format(stdout_data))

        # get certificate from output
        end_cert = "-----END CERTIFICATE-----"
        i_start = stdout_data.find("-----BEGIN CERTIFICATE-----")
        i_stop = stdout_data.find(end_cert)
        if i_start > -1 and i_stop > -1:
            i_stop += len(end_cert)
            cert: str = stdout_data[i_start:i_stop]
            cert = cert.replace("\\n", "\n")
            cert = cert.replace("\\", "")
            computeInstanceTask.logger.info("+++++ pass_certificate_step - cert: %s" % cert)

            # add cert
            extra_vars = params.get("extra_vars", {})
            extra_vars["cert"] = cert
        else:
            computeInstanceTask.logger.info("+++++ pass_certificate_step - NO cert found")

        oid = params.get("id")
        return oid, params

    @staticmethod
    @task_step()
    def apply_customization_action_step(task, step_id, params, *args, **kvargs):
        """Apply customization to instance

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        computeInstanceTask: ComputeInstanceTask = task
        computeInstanceTask.logger.debug("+++++ apply_customization_action_step - params: {}".format(params))
        computeInstanceTask.logger.debug("+++++ apply_customization_action_step - args: {}".format(args))
        computeInstanceTask.logger.debug("+++++ apply_customization_action_step - kvargs: {}".format(kvargs))

        shared_data = computeInstanceTask.get_shared_data()
        computeInstanceTask.logger.debug("+++++ apply_customization_action_step - shared_data: {}".format(shared_data))
        stdout_data = computeInstanceTask.get_stdout_data()
        computeInstanceTask.logger.debug("+++++ apply_customization_action_step - stdout_data: {}".format(stdout_data))

        oid = params.get("id")
        cid = params.get("cid")
        action = params.get("action_name")
        customization = params.get("customization")
        playbook = params.get("playbook")
        extra_vars = params.get("extra_vars", {})
        provider = task.get_container(cid)
        resource = task.get_simple_resource(oid)
        orchestrator_tag = params.get("orchestrator_tag", "default")

        if params is None:
            params = {}
        data = {
            "name": "%s-%s" % (resource.name, action),
            "desc": "%s-%s" % (resource.name, action),
            "parent": customization,
            "has_quotas": False,
            "compute_zone": resource.parent_id,
            "instances": [{"id": oid, "extra_vars": {}}],
            "playbook": playbook,
            "extra_vars": extra_vars,
            "orchestrator_tag": orchestrator_tag,
            "sync": True,
        }

        # activate resource. With resource not active applied customization will fail
        resource.update_internal(state=ResourceState.ACTIVE)

        # create applied customization
        computeInstanceTask.logger.debug("+++++ apply_customization_action_step - data: {}".format(data))
        prepared_task, code = provider.resource_factory(AppliedComputeCustomization, **data)
        appcust_id = prepared_task["uuid"]
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="Create applied customization %s" % appcust_id)

        return oid, params

    @staticmethod
    @task_step()
    def manage_user_action_step(task, step_id, params, *args, **kvargs):
        """manage instance user in ssh module

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        cmd = params.get("cmd")
        key = params.get("key_id")
        password = params.get("password")
        extra_vars = params.get("extra_vars", {})
        user = extra_vars.get("user_name")
        resource = task.get_simple_resource(oid)

        if cmd == "add":
            resource.manage_user_with_ssh_module(user, key, password)
            task.progress(step_id, msg="Create ssh user %s" % user)
        elif cmd == "del":
            resource.unmanage_user_with_ssh_module(user)
            task.progress(step_id, msg="Delete ssh user %s" % user)
        elif cmd == "set-password":
            resource.set_user_password_with_ssh_module(user, password)
            task.progress(step_id, msg="Set ssh user %s password" % user)

        return oid, params

    @staticmethod
    @task_step()
    def link_instance_step(task, step_id, params, *args, **kvargs):
        """Link instance to compute instance

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        compute_instance_id = params.get("compute_instance")
        availability_zone_id = params.get("parent")
        oid = params.get("id")
        compute_instance = task.get_simple_resource(compute_instance_id)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site_id = availability_zone.parent_id
        compute_instance.add_link("%s-instance-link" % oid, "relation.%s" % site_id, oid, attributes={})
        task.progress(
            step_id,
            msg="Link instance %s to compute instance %s" % (oid, compute_instance_id),
        )

        return oid, params

    @staticmethod
    @task_step()
    def create_main_server_step(task, step_id, params, *args, **kvargs):
        """Create main server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        cid = params.get("cid")
        main = params.get("main")
        oid = params.get("id")
        availability_zone_id = params.get("parent")
        orchestrators = params.get("orchestrators")

        availability_zone = task.get_resource(availability_zone_id)
        resource = task.get_resource(oid)
        server_id = None

        # create server
        if main is True:
            # get main orchestrator
            main_orchestrator_id = params.get("main_orchestrator")
            orchestrator = orchestrators.get(main_orchestrator_id)
            orchestrator_type = orchestrator.get("type")

            # get remote parent for server
            objdef = orchestrator_mapping(orchestrator_type, 0)
            parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

            # da verificare import
            from beehive_resource.plugins.provider.task_v2.vsphere import (
                ProviderVsphere,
            )
            from beehive_resource.plugins.provider.task_v2.openstack import (
                ProviderOpenstack,
            )

            helper: ProviderVsphere = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)
            server_id = helper.create_server(parent, params)
            task.progress(step_id, msg="Create main server: %s" % server_id)

        return server_id, params

    @staticmethod
    @task_step()
    def import_main_server_step(task, step_id, params, *args, **kvargs):
        """Import main server

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        main = params.get("main")
        oid = params.get("id")
        orchestrators = params.get("orchestrators")
        resource = task.get_resource(oid)
        server_id = None

        # create server
        if main is True:
            # get main orchestrator
            main_orchestrator_id = params.get("main_orchestrator")
            orchestrator = orchestrators.get(main_orchestrator_id)
            orchestrator_type = orchestrator.get("type")

            helper = task.get_orchestrator(orchestrator_type, task, step_id, orchestrator, resource)
            server_id = helper.import_server(params)
            task.progress(step_id, msg="Import main server: %s" % server_id)

        return server_id, params

    @staticmethod
    @task_step()
    def configure_network_step(task, step_id, params, *args, **kvargs):
        """Configure network

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        compute_instance_id = params.get("compute_instance")
        networks = params.get("networks")

        for network in networks:
            task.progress(step_id, msg="Configure network: %s" % network)
            vpc_id = network["vpc"]
            subnet = network["subnet"]
            fixed_ip = network.get("fixed_ip", None)
            if fixed_ip is not None:
                attribs = {"subnet": subnet, "fixed_ip": fixed_ip}
                link = task.get_orm_link_among_resources(start=compute_instance_id, end=vpc_id)
                task.update_orm_link(link.id, json.dumps(attribs))
                task.progress(
                    step_id,
                    msg="Update link %s-%s-vpc-link" % (compute_instance_id, vpc_id),
                )

        return True, params

    @staticmethod
    @task_step()
    def create_twins_step(task, step_id, params, *args, **kvargs):
        """Create remote resources

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: resource id, params
        """
        oid = params.get("id")
        main = params.get("main")
        orchestrators = params.get("orchestrators")
        networks = params.get("networks")
        rule_groups = params.get("security_groups")
        resource = task.get_resource(oid)

        # remove main orchestrator
        if main is True:
            orchestrators.pop(params.get("main_orchestrator"))

        for orchestrator_id, orchestrator in orchestrators.items():
            for network in networks:
                network_id = network.get("id")
                subnet_cidr = network.get("subnet").get("cidr")
                fixed_ip = network.get("fixed_ip", None)
                orchestrator_type = orchestrator["type"]

                from beehive_resource.plugins.provider.task_v2.openstack import ProviderOpenstack
                from beehive_resource.plugins.provider.task_v2.vsphere import ProviderVsphere

                helper: ProviderVsphere = task.get_orchestrator(
                    orchestrator_type, task, step_id, orchestrator, resource
                )

                if orchestrator_type == "vsphere":
                    helper.create_ipset(fixed_ip, rule_groups)
                elif orchestrator_type == "openstack":
                    helper.create_port(network_id, subnet_cidr, fixed_ip, rule_groups)
                task.progress(step_id, msg="Create twin")
        return oid, params

    @staticmethod
    @task_step()
    def instance_action_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Send action to physical server.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        action = params.get("action_name")
        configs = deepcopy(params)
        configs["sync"] = True
        resource = task.get_simple_resource(oid)
        helper = task.get_orchestrator(orchestrator["type"], task, step_id, orchestrator, resource)
        res = helper.server_action(action, configs)
        params["result"] = res
        return res, params

    @staticmethod
    @task_step()
    def instance_security_group_action_step(task, step_id, params, orchestrator, *args, **kvargs):
        """Send action to physical resource based to orchestrator.

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")
        action = params.get("action_name")
        configs = deepcopy(params)
        configs["sync"] = True
        resource = task.get_simple_resource(oid)
        helper = task.get_orchestrator(orchestrator["type"], task, step_id, orchestrator, resource)

        remote_object = resource.get_physical_resource_from_container(orchestrator["id"], None)
        res = helper.remote_action(remote_object, action, params)

        return res, params

    @staticmethod
    @task_step()
    def enable_plugin_step(task, step_id, params, *args, **kvargs):
        """enable plugin step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")

        # update resource attribute
        resource = task.get_simple_resource(oid)
        resource.set_configs(key="plugin_enabled", value=True)
        task.progress(step_id, msg="Enable resource %s plugin in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def enable_monitoring_step(task, step_id, params, *args, **kvargs):
        """update monitoring status attribute

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        from beehive.common.task_v2.__init__ import BaseTask

        baseTask: BaseTask = task
        oid = params.get("id")

        # update resource attribute
        from beehive_resource.container import Resource

        resource: Resource = task.get_simple_resource(oid)
        resource.set_configs(key="monitoring_enabled", value=True)

        # res containers synchronizes every 4 hours
        from datetime import datetime, timedelta

        dt = datetime.now()
        monitoring_wait_sync_till = dt + timedelta(hours=4)
        str_monitoring_wait_sync_till = monitoring_wait_sync_till.strftime("%m/%d/%Y, %H:%M:%S")
        resource.set_configs(key="monitoring_wait_sync_till", value=str_monitoring_wait_sync_till)

        baseTask.progress(step_id, msg="Enable resource %s monitoring in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def disable_monitoring_step(task, step_id, params, *args, **kvargs):
        """update monitoring status attribute

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")

        # update resource attribute
        resource = task.get_simple_resource(oid)
        resource.set_configs(key="monitoring_enabled", value=False)

        # res containers synchronizes every 4 hours
        from datetime import datetime, timedelta

        dt = datetime.now()
        monitoring_wait_sync_till = dt + timedelta(hours=4)
        str_monitoring_wait_sync_till = monitoring_wait_sync_till.strftime("%m/%d/%Y, %H:%M:%S")
        resource.set_configs(key="monitoring_wait_sync_till", value=str_monitoring_wait_sync_till)

        task.progress(step_id, msg="Disable resource %s monitoring in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def enable_logging_step(task, step_id, params, *args, **kvargs):
        """enable logging step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        oid = params.get("id")

        # update resource attribute
        resource = task.get_simple_resource(oid)
        resource.set_configs(key="logging_enabled", value=True)
        task.progress(step_id, msg="Enable resource %s logging in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def enable_log_module_step(task, step_id, params, *args, **kvargs):
        """enable log module step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug("enable_log_module_step - params: {}".format(params))
        logger.debug("enable_log_module_step - args: {}".format(args))
        logger.debug("enable_log_module_step - kvargs: {}".format(kvargs))
        oid = params.get("id")

        # update resource attribute
        resource = task.get_simple_resource(oid)
        # set modulo attivato
        resource.set_configs(key="logging_module", value=True)

        task.progress(step_id, msg="Enable resource %s log module in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def disable_log_module_step(task, step_id, params, *args, **kvargs):
        """Disable log module step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug("disable_log_module_step - params: {}".format(params))
        logger.debug("disable_log_module_step - args: {}".format(args))
        logger.debug("disable_log_module_step - kvargs: {}".format(kvargs))
        oid = params.get("id")

        # update resource attribute
        resource = task.get_simple_resource(oid)
        # set modulo disattivato
        resource.set_configs(key="logging_module", value=False)

        task.progress(step_id, msg="Disable resource %s log module in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def disable_logging_step(task, step_id, params, *args, **kvargs):
        """Disable logging step

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: True, params
        """
        logger.debug("disable_logging_step - params: {}".format(params))
        logger.debug("disable_logging_step - args: {}".format(args))
        logger.debug("disable_logging_step - kvargs: {}".format(kvargs))
        oid = params.get("id")

        # update resource attribute
        resource = task.get_simple_resource(oid)
        resource.set_configs(key="logging_enabled", value=False)
        resource.set_configs(key="logging_module", value=False)

        task.progress(step_id, msg="Disable resource %s logging in attribute" % oid)

        return oid, params

    @staticmethod
    @task_step()
    def wait_ssh_up_step(task, step_id, params, *args, **kvargs):
        """Wait until server is reachable

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: object id, params
        """
        oid = params.get("id")
        cid = params.get("cid")
        resource: ComputeInstance = task.get_simple_resource(oid)
        provider = task.get_container(cid)
        compute_zone = resource.get_parent()
        compute_zone.set_container(provider)

        is_private = False
        if compute_zone.get_bastion_host() is not None:
            is_private = True

        data = {
            "customization": "os-utility",
            "playbook": "wait_ssh_is_up.yml",
            "extra_vars": {"is_private": is_private},
        }

        logger.info("+++++ wait_ssh_up_step - apply_customization")
        prepared_task, code = resource.apply_customization("wait_ssh_up", data, sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg="create bastion %s - wait ssh is up" % oid)

        return oid, params
