# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.task_v2 import task_step, run_sync_task, TaskError
from beehive_resource.plugins.provider.entity.load_balancer import ComputeLoadBalancer, LoadBalancer
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.task_v2 import AbstractProviderResourceTask
from beecell.simple import dict_get, import_class

from logging import getLogger
logger = getLogger(__name__)


class LoadBalancerTask(AbstractProviderResourceTask):
    """Load Balancer task
    """
    name = 'load_balancer_task'
    entity_class = ComputeLoadBalancer

    @staticmethod
    @task_step()
    def create_zone_load_balancer_step(task, step_id, params, availability_zone_id, *args, **kvargs):
        """Create compute load balancer

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param availability_zone_id: availability zone id
        :return: True, params
        """
        cid = params.get('cid')
        oid = params.get('id')

        provider = task.get_container(cid)
        availability_zone = task.get_simple_resource(availability_zone_id)
        site = availability_zone.get_parent()
        site_id = site.oid
        task.progress(step_id, msg='Get resources')

        # create load balancer
        load_balancer_params = {
            'name': '%s-avz%s' % (params.get('name'), site_id),
            'desc': 'Zone load balancer %s' % params.get('name'),
            'parent': availability_zone_id,
            'orchestrator_tag': params.get('orchestrator_tag'),
            'orchestrator_type': dict_get(params, 'attribute.type'),
            'lb_configs': params.get('lb_configs'),
            'helper_class': params.get('helper_class'),
            'attribute': {}
        }
        prepared_task, code = provider.resource_factory(LoadBalancer, **load_balancer_params)
        load_balancer_id = prepared_task['uuid']

        # add link between load balancer and compute load balancer
        task.get_session(reopen=True)
        compute_load_balancer = task.get_simple_resource(oid)
        compute_load_balancer.add_link('%s-lb-link' % load_balancer_id, 'relation.%s' % site_id, load_balancer_id,
                                       attributes={})
        task.progress(step_id, msg='Link load balancer %s to compute load balancer %s' % (load_balancer_id, oid))

        # wait for task to complete
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Create load balancer in availability zone %s' % availability_zone_id)

        return True, params

    @staticmethod
    @task_step()
    def create_load_balancer_physical_resource_step(task, step_id, params, orchestrator_type, *args, **kvargs):
        """Create load balancer physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param orchestrator_type: orchestrator type
        :return: gateway_id, params
        """
        oid = params.get('id')

        # get orchestrator
        avz_id = params.get('parent')
        avz = task.controller.get_simple_resource(avz_id)
        orchestrator_idx = avz.get_orchestrators(select_types=[orchestrator_type])
        orchestrator = list(orchestrator_idx.values())[0]

        helper_class_path = params.get('helper_class')
        if helper_class_path is None:
            raise TaskError('None helper class')

        # instantiate helper
        helper_class = import_class(helper_class_path)
        helper = helper_class(task.controller, orchestrator, None)

        # create physical resource
        lb_configs = params.get('lb_configs')
        res = helper.create_load_balancer(lb_configs)
        task.progress(step_id, msg='Create load balancer %s on %s' % (lb_configs.get('name'),
                                                                      helper.orchestrator.get('type')))

        # update attributes of local resource
        load_balancer: LoadBalancer = task.get_simple_resource(oid)
        net_appl_id = params.get('lb_configs').get('net_appl')
        load_balancer.set_configs(key='selected_net_appl', value=net_appl_id)
        load_balancer.set_configs(key='helper_class', value=helper_class_path)
        for k, v in res.items():
            load_balancer.set_configs(key=k, value=v)

        return True, params

    @staticmethod
    @task_step()
    def delete_load_balancer_step(task, step_id, params, resource_id, *args, **kvargs):
        """Delete load balancer

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param resource_id: id of the resource to delete
        :return: True, params
        """
        logger.warning('____delete_zone_load_balancer_step.params={}'.format(params))
        resource: LoadBalancer = task.get_resource(resource_id)

        lb_attribs = resource.get_attribs()
        helper_class = lb_attribs.get('helper_class')
        net_appl_id = lb_attribs.get('selected_net_appl')
        net_appl = task.get_simple_resource(net_appl_id)
        net_appl_orchestrator = net_appl.controller.get_container(net_appl.container_id)

        # instantiate helper
        helper_class = import_class(helper_class)
        helper = helper_class(task.controller, net_appl_orchestrator.info(), None)

        # delete physical load balancer
        res = helper.delete_load_balancer(lb_attribs)
        task.progress(step_id, msg='Delete load balancer')

        # release allocated ip address
        ip_pool = dict_get(lb_attribs, 'vnic.ip_pool')
        ip_addr = dict_get(lb_attribs, 'vnic.secondary_ip')
        res = helper.release_ip_address(ip_pool, ip_addr)
        task.progress(step_id, msg='Release lb ip address')

        # delete resource
        prepared_task, code = resource.expunge(sync=True)
        run_sync_task(prepared_task, task, step_id)
        task.progress(step_id, msg='Remove child %s' % resource_id)

        return True, params

    @staticmethod
    @task_step()
    def add_rule_to_target_security_group_step(task, step_id, params, target_id, ip_addr, *args, **kvargs):
        """Add proper rule to target security group so that target can receive traffic from load balancer

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :param target_id: target uuid
        :param ip_addr:
        :return: True, params
        """
        logger.warning('____add_rule_to_target_security_group_step.params={}'.format(params))
        logger.warning('____add_rule_to_target_security_group_step.kvargs={}'.format(kvargs))

        # get target object
        target = task.controller.get_simple_resource(target_id)

        # get linked security group
        sgs, tot = target.get_linked_resources(link_type='security-group', objdef=SecurityGroup.objdef,
                                               run_customize=False)
        if tot != 1:
            raise TaskError('Security group not found or name is not unique')
        sg = sgs[0]
        sg.set_container(task.controller.get_container(sg.container_id))
        sg.post_get()

        # check if rule already exists
        source = {'type': 'Cidr', 'value': '%s/32' % ip_addr}
        dest = {'type': 'SecurityGroup', 'value': sg.uuid}
        service = {'port': '%s' % dict_get(params, 'lb_configs.port'), 'protocol': '6'}
        found, rule = sg.find_rule(source, dest, service)
        # create rule
        if not found:
            res = sg.create_rule(source, dest, service)

        return True, params
