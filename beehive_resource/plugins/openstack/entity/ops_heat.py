# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import requests
from beecell.simple import truncate, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity import OpenstackResource, get_task
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


stack_entity_type_mapping = {
    'AWS::AutoScaling::AutoScalingGroup': None,
    'AWS::AutoScaling::LaunchConfiguration': None,
    'AWS::AutoScaling::ScalingPolicy': None,
    'AWS::CloudFormation::Stack': None,
    'AWS::CloudFormation::WaitCondition': None,
    'AWS::CloudFormation::WaitConditionHandle': None,
    'AWS::CloudWatch::Alarm': None,
    'AWS::EC2::EIP': None,
    'AWS::EC2::EIPAssociation': None,
    'AWS::EC2::Instance': None,
    'AWS::EC2::InternetGateway': None,
    'AWS::EC2::NetworkInterface': None,
    'AWS::EC2::RouteTable': None,
    'AWS::EC2::SecurityGroup': None,
    'AWS::EC2::Subnet': None,
    'AWS::EC2::SubnetRouteTableAssociation': None,
    'AWS::EC2::VPC': None,
    'AWS::EC2::VPCGatewayAttachment': None,
    'AWS::EC2::Volume': None,
    'AWS::EC2::VolumeAttachment': None,
    'AWS::ElasticLoadBalancing::LoadBalancer': None,
    'AWS::IAM::AccessKey': None,
    'AWS::IAM::User': None,
    'AWS::RDS::DBInstance': None,
    'AWS::S3::Bucket': None,
    'OS::Aodh::Alarm': None,
    'OS::Aodh::CombinationAlarm': None,
    'OS::Aodh::CompositeAlarm': None,
    'OS::Aodh::EventAlarm': None,
    'OS::Aodh::GnocchiAggregationByMetricsAlarm': None,
    'OS::Aodh::GnocchiAggregationByResourcesAlarm': None,
    'OS::Aodh::GnocchiResourcesAlarm': None,
    'OS::Barbican::CertificateContainer': None,
    'OS::Barbican::GenericContainer': None,
    'OS::Barbican::Order': None,
    'OS::Barbican::RSAContainer': None,
    'OS::Barbican::Secret': None,
    'OS::Cinder::EncryptedVolumeType': None,
    'OS::Cinder::QoSAssociation': None,
    'OS::Cinder::QoSSpecs': None,
    'OS::Cinder::Quota': None,
    'OS::Cinder::Volume': 'Openstack.Domain.Project.Volume',
    'OS::Cinder::VolumeAttachment': None,
    'OS::Cinder::VolumeType': None,
    'OS::Glance::Image': 'Openstack.Image',
    'OS::Heat::AccessPolicy': None,
    'OS::Heat::AutoScalingGroup': None,
    'OS::Heat::CloudConfig': None,
    'OS::Heat::DeployedServer': None,
    'OS::Heat::HARestarter': None,
    'OS::Heat::InstanceGroup': None,
    'OS::Heat::MultipartMime': None,
    'OS::Heat::None': None,
    'OS::Heat::RandomString': None,
    'OS::Heat::ResourceChain': None,
    'OS::Heat::ResourceGroup': None,
    'OS::Heat::ScalingPolicy': None,
    'OS::Heat::SoftwareComponent': None,
    'OS::Heat::SoftwareConfig': None,
    'OS::Heat::SoftwareDeployment': None,
    'OS::Heat::SoftwareDeploymentGroup': None,
    'OS::Heat::Stack': None,
    'OS::Heat::StructuredConfig': None,
    'OS::Heat::StructuredDeployment': None,
    'OS::Heat::StructuredDeploymentGroup': None,
    'OS::Heat::SwiftSignal': None,
    'OS::Heat::SwiftSignalHandle': None,
    'OS::Heat::TestResource': None,
    'OS::Heat::UpdateWaitConditionHandle': None,
    'OS::Heat::Value': None,
    'OS::Heat::WaitCondition': None,
    'OS::Heat::WaitConditionHandle': None,
    'OS::Keystone::Domain': None,
    'OS::Keystone::Endpoint': None,
    'OS::Keystone::Group': None,
    'OS::Keystone::GroupRoleAssignment': None,
    'OS::Keystone::Project': 'Openstack.Domain.Project',
    'OS::Keystone::Region': None,
    'OS::Keystone::Role': None,
    'OS::Keystone::Service': None,
    'OS::Keystone::User': None,
    'OS::Keystone::UserRoleAssignment': None,
    'OS::Manila::SecurityService': None,
    'OS::Manila::Share': None,
    'OS::Manila::ShareNetwork': None,
    'OS::Manila::ShareType': None,
    'OS::Neutron::AddressScope': None,
    'OS::Neutron::ExtraRoute': None,
    'OS::Neutron::Firewall': None,
    'OS::Neutron::FirewallPolicy': None,
    'OS::Neutron::FirewallRule': None,
    'OS::Neutron::FloatingIP': None,
    'OS::Neutron::FloatingIPAssociation': None,
    'OS::Neutron::FlowClassifier': None,
    'OS::Neutron::LBaaS::HealthMonitor': None,
    'OS::Neutron::LBaaS::L7Policy': None,
    'OS::Neutron::LBaaS::L7Rule': None,
    'OS::Neutron::LBaaS::Listener': None,
    'OS::Neutron::LBaaS::LoadBalancer': None,
    'OS::Neutron::LBaaS::Pool': None,
    'OS::Neutron::LBaaS::PoolMember': None,
    'OS::Neutron::MeteringLabel': None,
    'OS::Neutron::MeteringRule': None,
    'OS::Neutron::Net': 'Openstack.Domain.Project.Network',
    'OS::Neutron::NetworkGateway': None,
    'OS::Neutron::Port': 'Openstack.Domain.Project.Network.Port',
    'OS::Neutron::PortPair': None,
    'OS::Neutron::ProviderNet': 'Openstack.Domain.Project.Network',
    'OS::Neutron::QoSBandwidthLimitRule': None,
    'OS::Neutron::QoSDscpMarkingRule': None,
    'OS::Neutron::QoSPolicy': None,
    'OS::Neutron::Quota': None,
    'OS::Neutron::RBACPolicy': None,
    'OS::Neutron::Router': 'Openstack.Domain.Project.Router',
    'OS::Neutron::RouterInterface': None,
    'OS::Neutron::SecurityGroup': 'Openstack.Domain.Project.SecurityGroup',
    'OS::Neutron::SecurityGroupRule': None,
    'OS::Neutron::Subnet': 'Openstack.Domain.Project.Network.Subnet',
    'OS::Neutron::SubnetPool': None,
    'OS::Nova::Flavor': 'Openstack.Flavor',
    'OS::Nova::FloatingIP': None,
    'OS::Nova::FloatingIPAssociation': None,
    'OS::Nova::HostAggregate': None,
    'OS::Nova::KeyPair': None,
    'OS::Nova::Quota': None,
    'OS::Nova::Server': 'Openstack.Domain.Project.Server',
    'OS::Nova::ServerGroup': None,
    'OS::Swift::Container': None,
    'OS::Trove::Cluster': None,
    'OS::Trove::Instance': None,
}


class OpenstackHeat(OpenstackResource):
    objdef = 'Openstack.Heat'
    objuri = 'heats'
    objname = 'heat'
    objdesc = 'Openstack heats'
    
    default_tags = ['openstack']

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container.conn: client used to comunicate with remote platform
        :param str ext_id: remote platform entity id
        :param dict res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, level)            
        :raise ApiManagerError:
        """
        # get heat instance from openstack
        items = [{'id': 'heat-01', 'name': 'heat'}]

        # add new item to final list
        res = []
        for item in items:
            if item['id'] not in res_ext_ids:
                level = None
                name = item['name']
                parent_id = None
                    
                res.append((OpenstackHeat, item['id'], parent_id, OpenstackHeat.objdef, name, level))
        
        return res        

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.
                   
        :param container.conn: client used to comunicate with remote platform
        :return: list of remote entities            
        :raise ApiManagerError:
        """
        items = [{'id': 'heat-01', 'name': 'heat'}]
        return items
    
    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]   
        
        objid = '%s//%s' % (container.objid, id_gen())
        
        res = {
            'resource_class': resclass,
            'objid': objid, 
            'name': name, 
            'ext_id': ext_id, 
            'active': True, 
            'desc': resclass.objdesc, 
            'attrib': {}, 
            'parent': parent_id, 
            'tags': resclass.default_tags
        }
        return res
    
    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        for entity in entities:
            entity.set_physical_entity({'id': 'heat-01', 'name': 'heat'})
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        try:
            self.set_physical_entity({'id': 'heat-01', 'name': 'heat'})
        except:
            pass

    #
    # info
    #
    def info(self):
        """Get infos.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        info = OpenstackResource.info(self)
        try:
            data = self.container.conn.heat.build_info()
            info['build_info'] = data
        except Exception as ex:
            self.logger.warn(ex)
        return info

    def status(self):
        """Get details.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = OpenstackResource.info(self)
        try:
            data = self.container.conn.heat.services_status()
            info['services'] = data['services']
        except Exception as ex:
            self.logger.error(ex)
            raise ApiManagerError(ex)
        return info

    def get_template_versions(self):
        """Get template versions.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        ver = self.container.conn.heat.template.versions()
        self.logger.debug('Get heat template versions')
        return ver

    def get_template_functions(self, template):
        """Get functions for a specific template version.

        :param template: template
        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        func = self.container.conn.heat.template.functions(template)
        self.logger.debug('Get heat template %s functions' % template)
        return func

    def validate_template(self, template_uri):
        """Validate template from http(s) uri

        :param template_uri: template_uri
        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        try:
            rq = requests.get(template_uri, timeout=5, verify=False)
            if rq.status_code == 200:
                template = load(rq.content, Loader=Loader)
                template = dump(template)
                self.logger.debug('Get template: %s' % truncate(template))
            else:
                self.logger.error('No response from uri %s found' % template_uri)

            self.container.conn.heat.template.validate(template=template, environment={})
        except:
            self.logger.error('Failed to validate heat template %s' % template_uri, exc_info=1)
            raise ApiManagerError('Failed to validate heat template %s' % template_uri)

        self.logger.debug('Validate heat template %s: True' % template_uri)
        return template


class OpenstackHeatStack(OpenstackResource):
    objdef = 'Openstack.Domain.Project.HeatStack'
    objuri = 'stacks'
    objname = 'stack'
    objdesc = 'Openstack heat stacks'

    default_tags = ['openstack']
    task_path = 'beehive_resource.plugins.openstack.task_v2.ops_stack.StackTask.'

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.outputs = {}

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container.conn: client used to comunicate withremote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids frombeehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, level)
        :raise ApiManagerError:
        """
        # get from openstack
        if ext_id is not None:
            items = container.conn.heat.stack.list(ext_id=ext_id, global_tenant=True)
        else:
            items = container.conn.heat.stack.list(global_tenant=True)

        # add new item to final list
        res = []
        for item in items:
            if item['id'] not in res_ext_ids:
                level = None
                name = item['stack_name']
                parent_id = item['project']

                res.append((OpenstackHeatStack, item['id'], parent_id, OpenstackHeatStack.objdef, name, level))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container.conn: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        items = container.conn.heat.stack.list()
        for item in items:
            item['name'] = item['stack_name']
        return items

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]

        parent = container.get_resource_by_extid(parent_id)
        objid = '%s//%s' % (parent.objid, id_gen())

        res = {
            'resource_class': resclass,
            'objid': objid,
            'name': name,
            'ext_id': ext_id,
            'active': True,
            'desc': resclass.objdesc,
            'attrib': {},
            'parent': parent.oid,
            'tags': resclass.default_tags
        }
        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        for entity in entities:
            try:
                ext_obj = OpenstackHeatStack.get_remote_stack(controller, entity.ext_id, container, entity.name,
                                                              entity.ext_id)
                # ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
                entity.outputs = entity.get_outputs()
            except:
                container.logger.warn('', exc_info=1)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        try:
            # get connection switch project to parent project
            # self.container.get_connection(projectid=self.parent_id)
            # ext_obj = self.container.conn.heat.stack.get(stack_name=self.name, oid=self.ext_id)
            ext_obj = self.get_remote_stack(self.controller, self.ext_id, self.container, self.name, self.ext_id)
            self.set_physical_entity(ext_obj)
            self.outputs = self.get_outputs()
        except:
            self.logger.warn('', exc_info=1)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributez
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.template_uri: A URI to the location containing the stack template on which to perform the
            operation. See the description of the template parameter for information about the expected
            template content located at the URI.')
        :param kvargs.environment: A JSON environment for the stack
        :param kvargs.parameters: 'Supplies arguments for parameters defined in the stack template
        :param kvargs.files: Supplies the contents of files referenced in the template or the environment
        :param kvargs.owner: stack owner name
        :return: kvargs
        :raise ApiManagerError:
        """

        steps = [
            OpenstackHeatStack.task_path + 'create_resource_pre_step',
            OpenstackHeatStack.task_path + 'stack_create_physical_step',
            OpenstackHeatStack.task_path + 'create_resource_post_step',
            OpenstackHeatStack.task_path + 'register_child_entity_step',
            OpenstackHeatStack.task_path + 'link_child_entity_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackHeatStack.task_path + 'update_resource_pre_step',
            OpenstackHeatStack.task_path + 'stack_update_physical_step',
            OpenstackHeatStack.task_path + 'update_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackHeatStack.task_path + 'expunge_resource_pre_step',
            OpenstackHeatStack.task_path + 'stack_delete_physical_step',
            OpenstackHeatStack.task_path + 'expunge_resource_post_step'
        ]
        kvargs['steps'] = steps
        return kvargs

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data['status_reason'] = self.ext_obj.get('stack_status_reason', '')
            data['status'] = self.ext_obj.get('stack_status', '')
            info['details'] = data
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        detail = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            detail['details'] = self.ext_obj
        return detail

    #
    # query stack
    #
    def get_supported_type(self):
        type_mapping = {k: v for k, v in stack_entity_type_mapping.items() if v is not None}
        return type_mapping.keys()

    def get_template(self):
        """Get template.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        template = self.container.conn.heat.stack.template(stack_name=self.name, oid=self.ext_id)
        self.logger.debug('Get stack %s template' % self.name)
        return template

    def get_environment(self):
        """Get environment.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        environment = self.container.conn.heat.stack.environment(stack_name=self.name, oid=self.ext_id)
        self.logger.debug('Get stack %s environment' % self.name)
        return environment

    def get_files(self):
        """Get files.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        files = self.container.conn.heat.stack.files(stack_name=self.name, oid=self.ext_id)
        self.logger.debug('Get stack %s files' % self.name)
        return files

    def get_inputs(self):
        """Get inputs.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        inputs = {}
        if self.ext_obj is not None:
            inputs = self.ext_obj.get('parameters', {})
            self.logger.debug('Get stack %s inputs: %s' % (self.name, truncate(inputs)))
        return inputs

    def get_outputs(self):
        """Get outputs.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        outputs = {}
        if self.ext_obj is not None:
            outputs = {
                o.get('output_key'): {'output_value': o.get('output_value', None),
                                      'output_error': o.get('output_error', None),
                                      'desc': o.get('description', None)}
                for o in self.ext_obj.get('outputs', [])
            }

        return outputs

    def get_outputs_desc(self):
        """Get outputs description.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        outputs = self.container.conn.heat.stack.outputs(stack_name=self.name, oid=self.ext_id).get('outputs', [])
        self.logger.debug('Get stack %s outputs' % self.name)
        return outputs

    def get_output(self, key):
        """Get output.

        :param key: output key
        :return:
        :raise ApiManagerError:
        """
        output = self.outputs.get(key, {})
        self.logger.debug('Get stack %s output %s: %s' % (self.name, key, output))
        return output

    def get_stack_resources(self, *args, **kvargs):
        """Get resources.

        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return:
        :raise ApiManagerError:
        """
        entities = self.get_stack_internal_resources()

        resources = []
        for entity in entities:
            try:
                self.logger.debug('Get resource for %s:%s' % (entity.get('resource_type'),
                                                              entity.get('physical_resource_id')))
                if entity.get('resource_type') in self.get_supported_type():
                    resource = self.container.get_resource_by_extid(entity.get('physical_resource_id'))
                    if resource is not None:
                        resources.append(resource)
            except:
                pass

        self.logger.debug('Get stack %s resources: %s' % (self.name, truncate(resources)))
        return resources, len(resources)

    def get_stack_internal_resources(self, name=None, status=None, type=None):
        """Get internal resources.

        :param name: resource name
        :param status: resource status
        :param type: resource type
        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')
        resources = []
        if self.ext_id is not None:
            resources = self.container.conn.heat.stack.resource.list(stack_name=self.name, oid=self.ext_id, name=name,
                                                                     status=status, type=type)
        self.logger.debug('Get stack %s internal resources: %s' % (self.name, truncate(resources)))
        return resources

    def get_events(self):
        """Get outputs.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')
        events = []
        if self.ext_id is not None:
            events = self.container.conn.heat.stack.event.list(stack_name=self.name, oid=self.ext_id)
        self.logger.debug('Get stack %s events' % self.name)
        return events

    def get_status(self):
        """Get stack status.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('view')

        status = ''
        if self.ext_obj is not None:
            status = self.ext_obj.get('stack_status', '')
            self.logger.debug('Get stack %s status reason: %s' % (self.name, status))
        return status

    def get_status_reason(self):
        """Get stack status reason.

        :return:
        :raise ApiManagerError:
        """
        self.verify_permisssions('view')

        status_reason = ''
        if self.ext_obj is not None:
            status_reason = self.ext_obj.get('stack_status_reason', '')
            self.logger.debug('Get stack %s status reason: %s' % (self.name, status_reason))
        return status_reason


class OpenstackHeatTemplate(OpenstackResource):
    objdef = 'Openstack.Domain.Project.StackTemplate'
    objuri = 'stack_templates'
    objname = 'stack_template'
    objdesc = 'Openstack heat stack templates'

    default_tags = ['openstack']

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OpenstackResource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        detail = OpenstackResource.info(self)

        if self.ext_obj is not None:
            detail['attribute'] = self.attribute
            self.logger.debug("External Object :  %s" % self.ext_obj.templ_id)
            if self.ext_obj.templ_id is not None:
                data = {}
                detail['details'] = data
            else:
                self.logger.warning("No template found")
        return detail


class OpenstackHeatSWconfig(OpenstackResource):
    objdef = 'Openstack.Domain.Project.SwConfig'
    objuri = 'swconfigs'
    objname = 'swconfig'
    objdesc = 'Openstack heat software configurations'

    default_tags = ['openstack']

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        detail = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            try:
                data = self.container.conn.heat.software_configs_details(self.ext_obj['id'])
            except:
                self.logger.warning("No swconfig found")
            detail['details'] = data
        else:
            self.logger.warning("No swconfig found")
        return detail


class OpenstackHeatSWdeployment(OpenstackResource):
    objdef = 'Openstack.Domain.Project.SwDeploy'
    objuri = 'swdeploys'
    objname = 'swdeploy'
    objdesc = 'Openstack heat software deployments'

    default_tags = ['openstack']

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        detail = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            try:
                data = self.container.conn.heat.software_deployments_details(self.ext_obj['id']) 
            except:
                self.logger.warning("No swconfig found")
            detail['details'] = data
        else: 
            self.logger.warning("No swconfig found")
        return detail
