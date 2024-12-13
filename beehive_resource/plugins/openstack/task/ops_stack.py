# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

import ujson as json
from celery.utils.log import get_task_logger
from beehive_resource.tasks import (
    ResourceJobTask,
    ResourceJob,
    create_resource_pre,
    create_resource_post,
    expunge_resource_pre,
    expunge_resource_post,
    update_resource_pre,
    update_resource_post,
)
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, task_local, Job, JobError
from beehive.common.task.util import end_task, start_task
import gevent
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeatStack
from beecell.simple import truncate
from beehive.common.task.canvas import signature

logger = get_task_logger(__name__)

stack_entity_type_mapping = {
    "AWS::AutoScaling::AutoScalingGroup": None,
    "AWS::AutoScaling::LaunchConfiguration": None,
    "AWS::AutoScaling::ScalingPolicy": None,
    "AWS::CloudFormation::Stack": None,
    "AWS::CloudFormation::WaitCondition": None,
    "AWS::CloudFormation::WaitConditionHandle": None,
    "AWS::CloudWatch::Alarm": None,
    "AWS::EC2::EIP": None,
    "AWS::EC2::EIPAssociation": None,
    "AWS::EC2::Instance": None,
    "AWS::EC2::InternetGateway": None,
    "AWS::EC2::NetworkInterface": None,
    "AWS::EC2::RouteTable": None,
    "AWS::EC2::SecurityGroup": None,
    "AWS::EC2::Subnet": None,
    "AWS::EC2::SubnetRouteTableAssociation": None,
    "AWS::EC2::VPC": None,
    "AWS::EC2::VPCGatewayAttachment": None,
    "AWS::EC2::Volume": None,
    "AWS::EC2::VolumeAttachment": None,
    "AWS::ElasticLoadBalancing::LoadBalancer": None,
    "AWS::IAM::AccessKey": None,
    "AWS::IAM::User": None,
    "AWS::RDS::DBInstance": None,
    "AWS::S3::Bucket": None,
    "OS::Aodh::Alarm": None,
    "OS::Aodh::CombinationAlarm": None,
    "OS::Aodh::CompositeAlarm": None,
    "OS::Aodh::EventAlarm": None,
    "OS::Aodh::GnocchiAggregationByMetricsAlarm": None,
    "OS::Aodh::GnocchiAggregationByResourcesAlarm": None,
    "OS::Aodh::GnocchiResourcesAlarm": None,
    "OS::Barbican::CertificateContainer": None,
    "OS::Barbican::GenericContainer": None,
    "OS::Barbican::Order": None,
    "OS::Barbican::RSAContainer": None,
    "OS::Barbican::Secret": None,
    "OS::Cinder::EncryptedVolumeType": None,
    "OS::Cinder::QoSAssociation": None,
    "OS::Cinder::QoSSpecs": None,
    "OS::Cinder::Quota": None,
    "OS::Cinder::Volume": "Openstack.Domain.Project.Volume",
    "OS::Cinder::VolumeAttachment": None,
    "OS::Cinder::VolumeType": None,
    "OS::Glance::Image": "Openstack.Image",
    "OS::Heat::AccessPolicy": None,
    "OS::Heat::AutoScalingGroup": None,
    "OS::Heat::CloudConfig": None,
    "OS::Heat::DeployedServer": None,
    "OS::Heat::HARestarter": None,
    "OS::Heat::InstanceGroup": None,
    "OS::Heat::MultipartMime": None,
    "OS::Heat::None": None,
    "OS::Heat::RandomString": None,
    "OS::Heat::ResourceChain": None,
    "OS::Heat::ResourceGroup": None,
    "OS::Heat::ScalingPolicy": None,
    "OS::Heat::SoftwareComponent": None,
    "OS::Heat::SoftwareConfig": None,
    "OS::Heat::SoftwareDeployment": None,
    "OS::Heat::SoftwareDeploymentGroup": None,
    "OS::Heat::Stack": None,
    "OS::Heat::StructuredConfig": None,
    "OS::Heat::StructuredDeployment": None,
    "OS::Heat::StructuredDeploymentGroup": None,
    "OS::Heat::SwiftSignal": None,
    "OS::Heat::SwiftSignalHandle": None,
    "OS::Heat::TestResource": None,
    "OS::Heat::UpdateWaitConditionHandle": None,
    "OS::Heat::Value": None,
    "OS::Heat::WaitCondition": None,
    "OS::Heat::WaitConditionHandle": None,
    "OS::Keystone::Domain": None,
    "OS::Keystone::Endpoint": None,
    "OS::Keystone::Group": None,
    "OS::Keystone::GroupRoleAssignment": None,
    "OS::Keystone::Project": "Openstack.Domain.Project",
    "OS::Keystone::Region": None,
    "OS::Keystone::Role": None,
    "OS::Keystone::Service": None,
    "OS::Keystone::User": None,
    "OS::Keystone::UserRoleAssignment": None,
    "OS::Manila::SecurityService": None,
    "OS::Manila::Share": None,
    "OS::Manila::ShareNetwork": None,
    "OS::Manila::ShareType": None,
    "OS::Neutron::AddressScope": None,
    "OS::Neutron::ExtraRoute": None,
    "OS::Neutron::Firewall": None,
    "OS::Neutron::FirewallPolicy": None,
    "OS::Neutron::FirewallRule": None,
    "OS::Neutron::FloatingIP": None,
    "OS::Neutron::FloatingIPAssociation": None,
    "OS::Neutron::FlowClassifier": None,
    "OS::Neutron::LBaaS::HealthMonitor": None,
    "OS::Neutron::LBaaS::L7Policy": None,
    "OS::Neutron::LBaaS::L7Rule": None,
    "OS::Neutron::LBaaS::Listener": None,
    "OS::Neutron::LBaaS::LoadBalancer": None,
    "OS::Neutron::LBaaS::Pool": None,
    "OS::Neutron::LBaaS::PoolMember": None,
    "OS::Neutron::MeteringLabel": None,
    "OS::Neutron::MeteringRule": None,
    "OS::Neutron::Net": "Openstack.Domain.Project.Network",
    "OS::Neutron::NetworkGateway": None,
    "OS::Neutron::Port": "Openstack.Domain.Project.Network.Port",
    "OS::Neutron::PortPair": None,
    "OS::Neutron::ProviderNet": "Openstack.Domain.Project.Network",
    "OS::Neutron::QoSBandwidthLimitRule": None,
    "OS::Neutron::QoSDscpMarkingRule": None,
    "OS::Neutron::QoSPolicy": None,
    "OS::Neutron::Quota": None,
    "OS::Neutron::RBACPolicy": None,
    "OS::Neutron::Router": "Openstack.Domain.Project.Router",
    "OS::Neutron::RouterInterface": None,
    "OS::Neutron::SecurityGroup": "Openstack.Domain.Project.SecurityGroup",
    "OS::Neutron::SecurityGroupRule": None,
    "OS::Neutron::Subnet": "Openstack.Domain.Project.Network.Subnet",
    "OS::Neutron::SubnetPool": None,
    "OS::Nova::Flavor": "Openstack.Flavor",
    "OS::Nova::FloatingIP": None,
    "OS::Nova::FloatingIPAssociation": None,
    "OS::Nova::HostAggregate": None,
    "OS::Nova::KeyPair": None,
    "OS::Nova::Quota": None,
    "OS::Nova::Server": "Openstack.Domain.Project.Server",
    "OS::Nova::ServerGroup": None,
    "OS::Swift::Container": None,
    "OS::Trove::Cluster": None,
    "OS::Trove::Instance": None,
}


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_create_stack(self, options):
    """Create opsck stack

    :param tupla options: Tupla with options. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea:
    :param sharedarea.objid: resource objid
    :param sharedarea.parent: resource parent id
    :param sharedarea.cid: container id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.ext_id: resource ext_id
    :param sharedarea.active: resource active
    :param sharedarea.attribute: attributes
    :param sharedarea.tags: comma separated resource tags to assign [default='']
    :param sharedarea.template_uri: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
    :param sharedarea.environment: A JSON environment for the stack
    :param sharedarea.parameters: 'Supplies arguments for parameters defined in the stack template
    :param sharedarea.files: Supplies the contents of files referenced in the template or the environment
    :param sharedarea.owner: stack owner name
    :return: stack id
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    template_uri = params.get("template_uri")
    parent_id = params.get("parent")
    name = params.get("name")
    environment = params.get("environment", None)
    parameters = params.get("parameters", None)
    files = params.get("files", None)
    tags = params.get("tags", "")
    stack_owner = params.get("owner")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    # resource = self.get_resource(oid)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # validate template
    heat = container.get_heat_resource()
    template = heat.validate_template(template_uri)
    self.update("PROGRESS", msg="Validate template %s" % template_uri)

    # create new stack
    stack = conn.heat.stack.create(
        stack_name=name,
        template=template,
        environment=environment,
        parameters=parameters,
        tags=tags,
        files=files,
        stack_owner=stack_owner,
    )
    stack_id = stack["id"]
    self.update("PROGRESS", msg="Create stack %s - Starting" % stack_id)

    # set ext_id
    container.update_resource(oid, ext_id=stack_id)
    self.update("PROGRESS", msg="Set stack remote openstack id %s" % stack_id)

    # loop until entity is not stopped or get error
    while True:
        inst = OpenstackHeatStack.get_remote_stack(container.controller, stack_id, container, name, stack_id)
        # inst = conn.heat.stack.get(stack_name=name, oid=stack_id)
        status = inst.get("stack_status", None)
        if status == "CREATE_COMPLETE":
            break
        elif status == "CREATE_FAILED":
            reason = inst["stack_status_reason"]
            self.update("PROGRESS", msg="Create stack %s - Error: %s" % (stack_id, reason))
            raise Exception("Can not create stack %s: %s" % (stack_id, reason))

        self.update("PROGRESS")
        gevent.sleep(task_local.delta)

    self.update("PROGRESS", msg="Create stack %s - Completed" % stack_id)

    # save current data in shared area
    params["ext_id"] = stack_id
    params["result"] = stack_id
    # params['attrib'] = {'volume':{'boot':volume.id}}
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return stack_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_register_child_entity(self, options):
    """Register opsck stack child entity

    :param tupla options: Tupla with options. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea:
    :param sharedarea.oid: resource id
    :param sharedarea.parent: resource parent id
    :param sharedarea.cid: container id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.ext_id: resource ext_id
    :param sharedarea.active: resource active
    :param sharedarea.attribute: attributes
    :param sharedarea.tags: comma separated resource tags to assign [default='']
    :param sharedarea.template_uri: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
    :param sharedarea.environment: A JSON environment for the stack
    :param sharedarea.parameters: 'Supplies arguments for parameters defined in the stack template
    :param sharedarea.files: Supplies the contents of files referenced in the template or the environment
    :param sharedarea.owner: stack owner name
    :return: stack childs remote ids
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    # oid = params.get('id')
    ext_id = params.get("ext_id")
    name = params.get("name")
    parent_id = params.get("parent")
    self.update("PROGRESS", msg="Get configuration params")

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    # get resources
    resources = conn.heat.stack.resource.list(stack_name=name, oid=ext_id)
    self.update("PROGRESS", msg="Get child resources: %s" % truncate(resources))

    """
    [{'resource_name': 'my_instance',
      'links': [{}],
      'logical_resource_id': 'my_instance',
      'creation_time': '2017-12-19T12:17:09Z',
      'resource_status': 'CREATE_COMPLETE',
      'updated_time': '2017-12-19T12:17:09Z',
      'required_by': [],
      'resource_status_reason': 'state changed',
      'physical_resource_id': '9d06ea46-6ab0-4e93-88b9-72f32de0cc31',
      'resource_type': 'OS::Nova::Server'}]
    """

    # get child resources objdef
    objdefs = {}
    res_ext_ids = []
    for item in resources:
        # TODO : router should need additional operation for internal port and ha network
        mapping = stack_entity_type_mapping[item["resource_type"]]
        if mapping is not None:
            objdefs[mapping] = None
            res_ext_ids.append(item["physical_resource_id"])
    self.update("PROGRESS", msg="get child resources objdef: %s" % objdefs)

    # run celery job
    if len(objdefs) > 0:
        params = {
            "cid": cid,
            "types": ",".join(objdefs.keys()),
            "new": True,
            "died": False,
            "changed": False,
        }
        params.update(container.get_user())
        task = signature(
            "beehive_resource.tasks.job_synchronize_container",
            (container.objid, params),
            app=task_manager,
            queue=container.celery_broker_queue,
        )
        job = task.apply_async()
        self.logger.info("Start job job_synchronize_container %s" % job.id)

        # wait job complete
        self.wait_for_job_complete(job.id)

    # save current data in shared area
    params["res_ext_ids"] = res_ext_ids
    self.set_shared_data(params)
    self.update("PROGRESS", msg="Update shared area")

    return res_ext_ids


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_link_child_entity(self, options):
    """Link opsck stack child entity

    :param tupla options: Tupla with options. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea:
    :param sharedarea.oid: resource id
    :param sharedarea.parent: resource parent id
    :param sharedarea.cid: container id
    :param sharedarea.name: resource name
    :param sharedarea.desc: resource desc
    :param sharedarea.ext_id: resource ext_id
    :param sharedarea.active: resource active
    :param sharedarea.attribute: attributes
    :param sharedarea.tags: comma separated resource tags to assign [default='']
    :param sharedarea.template_uri: A URI to the location containing the stack template on which to perform the
                operation. See the description of the template parameter for information about the expected
                template content located at the URI.')
    :param sharedarea.environment: A JSON environment for the stack
    :param sharedarea.parameters: 'Supplies arguments for parameters defined in the stack template
    :param sharedarea.files: Supplies the contents of files referenced in the template or the environment
    :param sharedarea.owner: stack owner name
    :param sharedarea.res_ext_ids: list of remote child entity
    :return: True
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    oid = params.get("id")
    res_ext_ids = params.get("res_ext_ids")
    self.update("PROGRESS", msg="Get configuration params")

    # link child resource to stack
    self.get_session()
    stack = self.get_resource(oid)
    for ext_id in res_ext_ids:
        child = self.get_resource_by_extid(ext_id)
        stack.add_link("%s-%s-stack-link" % (oid, child.oid), "stack", child.oid, attributes={})
        self.update("PROGRESS", msg="Link stack %s to child %s" % (oid, child.oid))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_delete_stack(self, options):
    """Delete opsck stack

    :param tupla options: Tupla with options. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea:
    :param sharedarea.cid: orchestrator id
    :param sharedarea.id: stack id
    :return: stack id
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    ext_id = params.get("ext_id")
    parent_id = params.get("parent_id")
    self.update("PROGRESS", msg="Get configuration params")

    # get stack resource
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn
    self.update("PROGRESS", msg="Get container %s" % cid)

    if self.is_ext_id_valid(ext_id) is True:
        res = container.get_resource_by_extid(ext_id)

        # get stack
        inst = OpenstackHeatStack.get_remote_stack(container.controller, ext_id, container, res.name, ext_id)

        # get all stack volumes
        volumes = res.get_stack_internal_resources(type="OS::Cinder::Volume")
        # self.logger.warn(volumes)
        for volume in volumes:
            # remove all the snapshots of the volume
            volume_ext_id = volume["physical_resource_id"]
            snapshots = conn.volume.snapshot.list(volume_id=volume_ext_id)
            for snapshot in snapshots:
                conn.volume.snapshot.delete(snapshot["id"])
                while True:
                    try:
                        conn.volume.snapshot.get(snapshot["id"])
                        gevent.sleep(2)
                    except:
                        self.progress("Volume %s snapshot %s deleted" % (volume_ext_id, snapshot["id"]))
                        break

        # check stack
        # inst = conn.heat.stack.get(stack_name=res.name, oid=ext_id)
        if inst["stack_status"] != "DELETE_COMPLETE":
            # remove stack
            conn.heat.stack.delete(stack_name=res.name, oid=ext_id)
            self.update("PROGRESS", msg="Delete stack %s - Starting" % ext_id)

            # loop until entity is not deleted or get error
            while True:
                inst = OpenstackHeatStack.get_remote_stack(container.controller, ext_id, container, res.name, ext_id)
                # inst = conn.heat.stack.get(stack_name=res.name, oid=ext_id)
                status = inst.get("stack_status", None)
                if status == "DELETE_COMPLETE":
                    break
                elif status == "DELETE_FAILED":
                    err = "Delete stack %s - Error: %s" % (
                        ext_id,
                        inst.get("stack_status_reason", ""),
                    )
                    self.update("PROGRESS", msg=err)
                    raise Exception("Can not delete stack %s: %s" % (ext_id, inst.get("stack_status_reason", "")))

                self.update("PROGRESS")
                gevent.sleep(task_local.delta)

        res.update_internal(ext_id=None)
        self.update("PROGRESS", msg="Delete stack %s - Completed" % ext_id)

    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def expunge_resource_post(self, options):
    """Remove stack resource in cloudapi - post task.



    :param tupla options: Tupla with options. (class_name, objid, job, job id, start time, time before new query, user)
    :param dict sharedarea:

    :param sharedarea.cid: orchestrator id
    :param sharedarea.id: stack id
    :return: stack child id
    """
    # get params from shared data
    params = self.get_shared_data()

    # validate input params
    cid = params.get("cid")
    oid = params.get("id")
    self.update("PROGRESS", msg="Get configuration params")

    # get all child resources
    self.get_session()
    container = self.get_container(cid)
    resources = self.get_linked_resources(oid, link_type="stack", container_id=cid)

    # get child resources objdef
    objdefs = {}
    res_ids = []
    for item in resources:
        # TODO : router should need additional operation for internal port and ha network
        # objdefs[item.objdef] = None
        res_ids.append(item.id)
    for k, v in stack_entity_type_mapping.items():
        if v is not None:
            objdefs[v] = None
    self.update("PROGRESS", msg="Get child resources objdef: %s" % objdefs)
    self.update("PROGRESS", msg="Get child resources ext_id: %s" % res_ids)

    # run celery job
    if len(objdefs) > 0:
        params = {
            "cid": cid,
            "types": ",".join(objdefs.keys()),
            "new": False,
            "died": True,
            "changed": False,
        }
        params.update(container.get_user())
        task = signature(
            "beehive_resource.tasks.job_synchronize_container",
            (container.objid, params),
            app=task_manager,
            queue=container.celery_broker_queue,
        )
        job = task.apply_async()
        self.logger.info("Start job job_synchronize_container %s" % job.id)

        # wait job complete
        self.wait_for_job_complete(job.id)

    # delete stack
    self.release_session()
    self.get_session()
    resource = self.get_resource(oid)
    resource.expunge_internal()
    self.update("PROGRESS", msg="Delete stack %s resource" % oid)

    return res_ids
