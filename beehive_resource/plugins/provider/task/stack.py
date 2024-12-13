# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.stack import Stack
from beehive_resource.plugins.provider.task import (
    ProviderOpenstack,
    ProviderVsphere,
    ProviderOrchestrator,
    orchestrator_mapping,
)
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, JobError
from beehive.common.task.handler import task_local

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_stack(self, options, template, stack_id):
    """Create compute_stack stack.

    :param options: Tupla with some useful options.
        (class_name, objid, job, job id, start time, time before new query, user)
    :param template: template per availability zone
        * **site_id**: id  of the site
        * **availability_zone_id**: id  of the availability zone
        * **orchestrator_type**: Orchestrator type. Can be openstack
        * **template_uri**: remote template uri
        * **environment**: additional environment
        * **parameters**: stack input parameters
        * **files**: stack input files
    :param stack_id: stack reference id
    :sharedarea:
        * **cid** (int): container id
    :return: resource id
    """
    params = self.get_shared_data()

    # input params
    cid = params.get("cid")
    oid = params.get("id")
    availability_zone_id = template.pop("availability_zone_id")
    site_id = template.pop("site_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    # availability_zone = self.get_resource(availability_zone_id)
    # compute_stack = self.get_resource(oid)
    # site_id = availability_zone.parent_id
    self.update("PROGRESS", msg="Get resources")

    # create zone stack
    stack_params = {
        "name": "%s-avz%s" % (params.get("name"), site_id),
        "desc": "Zone stack %s %s" % (params.get("name"), stack_id),
        "parent": availability_zone_id,
        "compute_stack": oid,
        "orchestrator_tag": params.get("orchestrator_tag"),
        "attribute": {"stack": True, "template_uri": template.get("template_uri")},
        "template": template,
        "compute_stack_jobid": task_local.opid,
    }
    res = provider.resource_factory(Stack, **stack_params)
    job_id = res[0]["jobid"]
    stack_id = res[0]["uuid"]
    self.update(
        "PROGRESS",
        msg="Create stack in availability zone %s - start job %s" % (availability_zone_id, job_id),
    )

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update(
        "PROGRESS",
        msg="Create stack %s in availability zone %s" % (stack_id, availability_zone_id),
    )

    return stack_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_zone_stack_twins(self, options, availability_zone_id, stack_id):
    """Create compute_stack stack.

    :param options: Tupla with some useful options.
        (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone where create twins
    :param stack_id: stack reference id
    :sharedarea:
        * **cid** (int): container id
        * **....**: some info used to create server twins
        * **ip_addresses**: list of ip_addresses to use when create twins in other zones
    :return: resource id
    """
    params = self.get_shared_data()
    # input params
    cid = params.get("cid")
    oid = params.get("id")
    self.update("PROGRESS", msg="Get configuration params")

    # get provider
    self.get_session()
    provider = self.get_container(cid)
    # availability_zone = self.get_resource(availability_zone_id)
    # compute_stack = self.get_resource(oid)
    # site_id = availability_zone.parent_id
    self.update("PROGRESS", msg="Get resources")

    # create zone stack
    stack_params = {
        "name": "zone-stack-twin-%s-%s" % (params.get("name"), stack_id),
        "desc": "Zone stack twin %s %s" % (params.get("name"), stack_id),
        "parent": availability_zone_id,
        "compute_stack": oid,
        "orchestrator_tag": params.get("orchestrator_tag"),
        "attribute": {"stack": False, "template_uri": None},
        "template": None,
        "server_confs": params.get("server_confs"),
    }
    res = provider.resource_factory(Stack, **stack_params)
    job_id = res[0]["jobid"]
    stack_id = res[0]["uuid"]
    self.update(
        "PROGRESS",
        msg="Create stack twin in availability zone %s - start job %s" % (availability_zone_id, job_id),
    )

    # wait job complete
    res = self.wait_for_job_complete(job_id)
    self.update(
        "PROGRESS",
        msg="Create stack twin %s in availability zone %s" % (stack_id, availability_zone_id),
    )

    return stack_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_manage_compute_stack(self, options):
    """Register compute stack in ssh module

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :sharedarea:
        * **oid** (int): resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")
    key_name = params.get("key_name", None)

    # get resource
    self.get_session()
    compute_stack = self.get_resource_with_detail(oid)

    uuid = None
    if key_name is not None:
        uuid = compute_stack.manage(user="root", key=params.get("key_name"), password="")
        self.update("PROGRESS", msg="Manage compute stack %s" % oid)

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_unmanage_compute_stack(self, options):
    """Deregister compute stack from ssh module

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :sharedarea:
        * **oid** (int): resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")

    # get resoruce
    self.get_session()
    compute_stack = self.get_resource_with_detail(oid)

    uuid = None
    if compute_stack.is_managed() is True:
        uuid = compute_stack.unmanage()
        self.update("PROGRESS", msg="Unmanage stack %s" % oid)

    return uuid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_register_dns_compute_stack(self, options):
    """Register compute stack in dns

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :sharedarea:
        * **oid** (int): resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")
    resolve = params.get("resolve")

    # get resource
    self.get_session()
    compute_stack = self.get_resource_with_detail(oid)

    uuids = None
    if resolve is True:
        try:
            uuids = compute_stack.set_dns_recorda(force=True, ttl=30)
            self.update(
                "PROGRESS",
                msg="Register stack %s in dns with records %s" % (oid, uuids),
            )
        except Exception as ex:
            self.update("PROGRESS", msg="Error - Register stack %s in dns: %s" % (oid, ex))
            raise JobError("Register stack %s in dns: %s" % (oid, ex))

    return uuids


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_unregister_dns_compute_stack(self, options):
    """Deregister compute stack from dns

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param availability_zone_id: availability zone id
    :param dict sharedarea: input params
    :sharedarea:
        * **oid** (int): resource id
    :return: resource uuid
    """
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")

    # get resoruce
    self.get_session()
    compute_stack = self.get_resource_with_detail(oid)

    uuids = None
    try:
        uuids = compute_stack.unset_dns_recorda()
        self.update("PROGRESS", msg="Unregister stack %s records %s from dns" % (oid, uuids))
    except Exception as ex:
        self.update("PROGRESS", msg="Error - Deregister stack %s from dns: %s" % (oid, ex))
        raise JobError("Deregister stack %s in dns: %s" % (oid, ex))

    return uuids


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_stack(self, options):
    """Link stack to compute stack

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
        * **objid**: resource objid
        * **parent**: resource parent id
        * **cid**: container id
        * **name**: resource name
        * **desc**: resource desc
        * **ext_id**: resource ext_id
        * **active**: resource active
        * **attribute** (:py:class:`dict`): attributes [default={}]
        * **attribute.stack**: True if related to an OpenstackStack, False if related to a twin
        * **attribute.template_uri**: None if related to a twin
        * **tags**: comma separated resource tags to assign [default='']

        * **orchestrators**:
        * **orchestrators.vsphere**: {..}
        * **orchestrators.openstack**: {..}
        * **compute_stack**: id of the compute stack
        * **orchestrator_tag**: orchestrators tag
        * **template**: template per availability zone.
        * **template.orchestrator_type**: Orchestrator type. Can be openstack, vsphere
        * **template.template_uri**: remote template uri
        * **template.environment**: additional environment
        * **template.parameters**: stack input parameters
        * **template.files**: stack input files
    :return: resource id
    """
    params = self.get_shared_data()
    compute_stack_id = params.get("compute_stack")
    availability_zone_id = params.get("parent")
    oid = params.get("id")
    self.update("PROGRESS", msg="Get configuration params")

    # link stack to compute stack
    self.get_session()
    compute_stack = self.get_resource(compute_stack_id)
    availability_zone = self.get_resource(availability_zone_id)
    site_id = availability_zone.parent_id
    compute_stack.add_link("%s-stack-link" % oid, "relation.%s" % site_id, oid, attributes={})
    self.update("PROGRESS", msg="Link stack %s to compute stack %s" % (oid, compute_stack_id))

    return oid


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_stack(self, options):
    """Create main stack

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
        * **objid**: resource objid
        * **parent**: resource parent id
        * **cid**: container id
        * **name**: resource name
        * **desc**: resource desc
        * **ext_id**: resource ext_id
        * **active**: resource active
        * **attribute** (:py:class:`dict`): attributes [default={}]
        * **attribute.stack**: True if related to an OpenstackStack, False if related to a twin
        * **attribute.template_uri**: None if related to a twin
        * **tags**: comma separated resource tags to assign [default='']

        * **orchestrators**:
        * **orchestrators.vsphere**: {..}
        * **orchestrators.openstack**: {..}
        * **compute_stack**: id of the compute stack
        * **orchestrator_tag**: orchestrators tag
        * **template**: template per availability zone.
        * **template.orchestrator_type**: Orchestrator type. Can be openstack, vsphere
        * **template.template_uri**: remote template uri
        * **template.environment**: additional environment
        * **template.parameters**: stack input parameters
        * **template.files**: stack input files
    :return: stack id or None if this is a twin
    """
    params = self.get_shared_data()

    oid = params.get("id")
    availability_zone_id = params.get("parent")
    orchestrators = params.get("orchestrators")
    template = params.get("template")
    self.update("PROGRESS", msg="Get configuration params")

    if template is None:
        self.update("PROGRESS", msg="Skip stack creation. This is a twin")
        return None

    orchestrator_type = template.get("orchestrator_type")

    # get resources
    self.get_session()
    availability_zone = self.get_resource(availability_zone_id)
    stack = self.get_resource(oid)
    # provider = self.get_container(cid)
    self.update("PROGRESS", msg="Get resource %s" % oid)

    # get main orchestrator
    orchestrator = orchestrators.pop(orchestrator_type)

    # get remote parent project for stack
    objdef = orchestrator_mapping(orchestrator["type"], 0)
    parent = availability_zone.get_physical_resource_from_container(orchestrator["id"], objdef)

    # create stack
    stack_id = ProviderOrchestrator.get(orchestrator_type).create_stack(
        self, orchestrator, stack, parent, template, params.get("compute_stack_jobid")
    )
    self.update("PROGRESS", msg="Create stack: %s" % stack_id)

    return stack_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_twins(self, options):
    """Create twins

    :param tupla options: Task config params. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea: input params
    :sharedarea:
        * **objid**: resource objid
        * **parent**: resource parent id
        * **cid**: container id
        * **name**: resource name
        * **desc**: resource desc
        * **ext_id**: resource ext_id
        * **active**: resource active
        * **attribute** (:py:class:`dict`): attributes [default={}]
        * **attribute.stack**: True if related to an OpenstackStack, False if related to a twin
        * **attribute.template_uri**: None if related to a twin
        * **tags**: comma separated resource tags to assign [default='']

        * **orchestrators**:
        * **orchestrators.vsphere**: {..}
        * **orchestrators.openstack**: {..}
        * **compute_stack**: id of the compute stack
        * **orchestrator_tag**: orchestrators tag
        * **template**: template per availability zone.
        * **template.orchestrator_type**: Orchestrator type. Can be openstack, vsphere
        * **template.template_uri**: remote template uri
        * **template.environment**: additional environment
        * **template.parameters**: stack input parameters
        * **template.files**: stack input files
        * **server_confs**: list of
        * **server_confs.name**: server name
        * **server_confs.key_name**: server ssh key name
        * **server_confs.subnet_cidr**: 10.102.185.0/24'
        * **server_confs.ip_address**: 10.102.185.166
        * **server_confs.vpc**: vpc
        * **server_confs.security_groups**: List of vpc Security group. Ex. [931]
    :return: True if this is a twin, False otherwise
    """
    params = self.get_shared_data()

    oid = params.get("id")
    orchestrators = params.get("orchestrators")
    availability_zone_id = params.get("parent")
    template = params.get("template")
    server_confs = params.get("server_confs")
    self.update("PROGRESS", msg="Get configuration params")

    # create twins
    self.get_session()
    stack = self.get_resource(oid)
    availability_zone = self.get_resource(availability_zone_id)
    site_id = availability_zone.parent_id

    # create twins
    for server_conf in server_confs:
        vpc_id = server_conf["vpc"]
        # get site network
        network_id = self.get_orm_linked_resources(vpc_id, link_type="relation.%s" % site_id)[0].id
        # network_id = server_conf['network']
        subnet_cidr = server_conf["subnet_cidr"]
        fixed_ip = server_conf["ip_address"]
        security_groups = server_conf["security_groups"]
        rule_groups = []
        for item in security_groups:
            sg = self.get_resource(item)
            rgs = self.get_orm_linked_resources(sg.oid, link_type="relation.%s" % site_id)
            # rgs = self.get_orm_linked_resources(sg.oid, link_type='relation')
            rule_groups.append(rgs[0].id)

        # exec task after stack creation
        if template is not None:
            self.update("PROGRESS", msg="Create vsphere twin")
            orchestrator = orchestrators.pop("vsphere", None)
            if orchestrator is not None:
                ProviderVsphere.create_ipset(self, orchestrator["id"], stack, fixed_ip, rule_groups)
                self.update("PROGRESS", msg="Create vsphere twin - ok")
                return False

        # exec task when stack creation skipped
        else:
            self.update("PROGRESS", msg="Create all the twin")

            orchestrator = orchestrators.pop("vsphere", None)
            if orchestrator is not None:
                ProviderVsphere.create_ipset(self, orchestrator["id"], stack, fixed_ip, rule_groups)
                self.update("PROGRESS", msg="Create vsphere twin - ok")

            orchestrator = orchestrators.pop("openstack", None)
            if orchestrator is not None:
                ProviderOpenstack.create_port(
                    self,
                    orchestrator["id"],
                    stack,
                    network_id,
                    subnet_cidr,
                    fixed_ip,
                    rule_groups,
                )
                self.update("PROGRESS", msg="Create openstack twin - ok")
            return True

    return False
