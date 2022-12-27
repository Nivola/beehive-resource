# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from logging import getLogger
from time import sleep

from beecell.simple import id_gen
from beehive.common.task_v2 import task_step
from beehive.common.task_v2.manager import task_manager
from beehive_resource.model import ResourceState
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_port import OpenstackPort
from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.task_v2 import AbstractResourceTask

logger = getLogger(__name__)


class RouterTask(AbstractResourceTask):
    """Router task
    """
    name = 'router_task'
    entity_class = OpenstackRouter

    @staticmethod
    @task_step()
    def router_create_physical_step(task, step_id, params, *args, **kvargs):
        """Create physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        name = params.get('name')
        project_extid = params.get('project_extid')
        external_gateway_info = params.get('external_gateway_info', None)
        if external_gateway_info is not None:
            network_extid = external_gateway_info.get('network_id')
            external_ips = external_gateway_info.get('external_fixed_ips')
        else:
            network_extid = None
            external_ips = None
        routes = params.get('routes')

        container = task.get_container(cid)
        conn = container.conn

        # create openstack router
        inst = conn.network.router.create(name, project_extid, network_extid, external_ips=external_ips)
        inst_id = inst['id']
        task.progress(step_id, msg='Create router %s - Starting' % inst_id)

        # attach remote server
        container.update_resource(oid, ext_id=inst_id)
        task.progress(step_id, msg='Attach remote router %s' % inst_id)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackRouter.get_remote_router(container.controller, inst_id, container, inst_id)
            # inst = container.conn.network.router.get(oid=inst_id)
            status = inst['status']
            if status == 'ACTIVE':
                break
            if status == 'ERROR':
                task.progress(step_id, msg='Create router %s - Error' % inst_id)
                raise Exception('Can not create router %s' % name)

            # sleep a little
            task.progress(step_id, msg='Create router %s - Wait' % inst_id)
            sleep(4)

        task.progress(step_id, msg='Create router %s - Completed' % inst_id)

        # update openstack router
        inst = conn.network.router.update(inst_id, routes=routes)
        task.progress(step_id, msg='Update router %s - Starting' % inst_id)

        # loop until entity is not stopped or get error
        while True:
            inst = OpenstackRouter.get_remote_router(container.controller, inst_id, container, inst_id)
            # inst = container.conn.network.router.get(oid=inst_id)
            status = inst['status']
            if status == 'ACTIVE':
                break
            if status == 'ERROR':
                task.progress(step_id, msg='Update router %s - Error' % inst_id)
                raise Exception('Can not update router %s' % name)

            # sleep a little
            task.progress(step_id, msg='Update router %s - Wait' % inst_id)
            sleep(4)

        task.progress(step_id, msg='Update router %s - Completed' % inst_id)

        # save current data in shared area
        params['ext_id'] = inst_id
        params['attrib'] = {}

        return oid, params

    @staticmethod
    @task_step()
    def router_create_ports_physical_step(task, step_id, params, *args, **kvargs):
        """Create beehive resources related to router ports

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        ext_id = params.get('ext_id')
        parent = params.get('parent')

        container = task.get_container(cid)
        tenant = container.get_simple_resource(parent)
        conn = container.conn

        # get router ports from openstack
        res = []
        attrib = {'ha_tenant_network': []}
        ports = conn.network.port.list(device_id=ext_id)
        if len(ports) > 0:
            # get networks
            net_index = container.index_resources_by_extid(entity_class=OpenstackNetwork)

            # loop over router ports
            for port in ports:
                # HA network tenant is genereated for router and does not already exist in beehive. Register when
                # port need
                if port['network_id'] not in net_index:
                    # register new network
                    objid = '%s//%s' % (tenant.objid, id_gen())
                    remote_net = conn.network.get(oid=port['network_id'])
                    desc = remote_net['name']
                    n = container.add_resource(objid=objid, name=remote_net['name'], resource_class=OpenstackNetwork,
                                               ext_id=port['network_id'], active=True, desc=desc, attrib={},
                                               parent=tenant.oid, tags=['openstack', 'network'])
                    container.update_resource_state(n.id, ResourceState.ACTIVE)

                    # refresh network index
                    net_index = container.index_resources_by_extid(entity_class=OpenstackNetwork)

                    # append tenant network to router attribs
                    attrib['ha_tenant_network'].append(n.id)

                name = port['name']
                desc = 'Port %s' % name
                parent = net_index[port['network_id']]
                objid = '%s//%s' % (parent.objid, id_gen())
                p = container.add_resource(objid=objid, name=name, resource_class=OpenstackPort, ext_id=port['id'],
                                           active=True, desc=desc, attrib={}, parent=parent.oid,
                                           tags=['openstack', 'port'])
                container.update_resource_state(p.id, ResourceState.ACTIVE)
                res.append(p.id)
                task.progress(step_id, msg='Create port resource %s' % p.id)

        params['attrib'] = attrib

        return oid, params

    @staticmethod
    @task_step()
    def router_update_physical_step(task, step_id, params, *args, **kvargs):
        """Update physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        return oid, params

    @staticmethod
    @task_step()
    def router_delete_physical_step(task, step_id, params, *args, **kvargs):
        """Delete physical resource

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        ext_id = params.get('ext_id')
        ha_tenant_network = params.get('ha_tenant_network')

        container = task.get_container(cid)
        if ext_id is not None:
            conn = container.conn

            # delete openstack router
            conn.network.router.delete(ext_id)
            task.progress(step_id, msg='Delete router %s' % ext_id)

            # delete HA tenant network related to router
            for item in ha_tenant_network:
                net = container.get_simple_resource(item)
                # conn.network.delete(net.ext_id)
                net.expunge_internal()
                task.progress(step_id, msg='Delete ha tenant network %s' % item)

        return oid, params

    @staticmethod
    @task_step()
    def router_delete_ports_physical_step(task, step_id, params, *args, **kvargs):
        """Delete internal router port

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        ext_id = params.get('ext_id')

        container = task.get_container(cid)
        conn = container.conn

        # remove openstack router interface
        if ext_id is not None:
            ports = conn.network.port.list(device_id=ext_id)
            for port in ports:
                # get port network
                network_id = port['network_id']

                # delete port for internal network
                if port['device_owner'] in ['network:ha_router_replicated_interface']:
                    subnet_id = port['fixed_ips'][0]['subnet_id']
                    # conn.network.port.delete(port['id'])
                    conn.network.router.delete_internal_interface(ext_id, subnet_id)
                    task.progress(step_id, msg='Delete router internal interface %s' % port['id'])

                if port['device_owner'] in ['network:router_ha_interface']:
                    # subnet_id = port['fixed_ips'][0]['subnet_id']
                    conn.network.port.delete(port['id'])
                    # conn.network.router.delete_internal_interface(ext_id, subnet_id)
                    task.progress(step_id, msg='Delete router ha interface %s' % port['id'])

                # delete port resource
                res = container.get_resource_by_extid(port['id'])
                if res is not None:
                    res.expunge_internal()
                    task.progress(step_id, msg='Delete router port %s resource' % port['id'])

                params['ha_network'] = network_id

        return oid, params

    @staticmethod
    @task_step()
    def router_delete_network_physical_step(task, step_id, params, *args, **kvargs):
        """Delete HA network tenant for router

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: network_id, params
        """
        cid = params.get('cid')
        network_id = params.get('ha_network')

        container = task.get_container(cid)
        conn = container.conn

        # delete ha network
        network = container.get_resource_by_extid(network_id)
        if network is not None:
            try:
                # check network exists
                conn.network.get(network.ext_id)

                # delete opennetwork network
                conn.network.delete(network.ext_id)
                task.progress(step_id, msg='Delete ha network %s' % network.ext_id)
            except:
                pass

        return network_id, params

    @staticmethod
    @task_step()
    def router_port_add_step(task, step_id, params, *args, **kvargs):
        """Create openstack router interface

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        subnet_id = params.get('subnet_id')
        ip_address = params.get('ip_address', None)
        oid = params.get('id')
        ext_id = params.get('ext_id')

        container = task.get_container(cid)
        conn = container.conn

        # create port
        port_id = None
        name = 'internal-port-%s' % id_gen()
        if ip_address is not None:
            # name = 'port-%s' % id_gen()
            network_id = params.get('network_id', None)
            fixed_ips = [{
                'subnet_id': subnet_id,
                'ip_address': ip_address
            }]
            port = conn.network.port.create(name, network_id, fixed_ips, host_id=None, profile=None, vnic_type=None,
                                            device_owner=None, device_id=None, security_groups=None, mac_address=None,
                                            tenant_id=None, allowed_address_pairs=None)
            subnet_id = None
            port_id = port['id']

        # create interface
        interface = conn.network.router.add_internal_interface(ext_id, subnet_id, port=port_id)
        ext_id = interface['port_id']
        port = conn.network.port.get(oid=ext_id)
        task.progress(step_id, msg='Add router interface on subnet %s' % subnet_id)

        # get parent network
        net_id = port['network_id']
        parent = container.get_resource_by_extid(net_id)
        objid = '%s//%s' % (parent.objid, id_gen())
        # name = 'internal-port-%s' % port['id'][0:10]
        # desc = 'Router internal port %s' % port['id'][0:10]
        desc = name
        p = container.add_resource(objid=objid, name=name, resource_class=OpenstackPort, ext_id=ext_id,
                                   active=True, desc=desc, attrib={}, parent=parent.oid, tags=['openstack', 'port'])
        container.update_resource_state(p.id, ResourceState.ACTIVE)
        task.progress(step_id, msg='Add router internal port %s' % p.id)

        params['oid'] = p.id
        params['result'] = p.id

        return p.id, params

    @staticmethod
    @task_step()
    def router_port_delete_step(task, step_id, params, *args, **kvargs):
        """Delete openstack router interface

        :param task: parent celery task
        :param str step_id: step id
        :param dict params: step params
        :return: oid, params
        """
        cid = params.get('cid')
        oid = params.get('id')
        subnet_id = params.get('subnet_id')
        ext_id = params.get('ext_id')

        container = task.get_container(cid)
        conn = container.conn

        # find right port from router
        if ext_id is not None:
            ports = conn.network.port.list(device_id=ext_id)
            port_id = None
            for port in ports:
                fixed_ips = port['fixed_ips']
                for ip in fixed_ips:
                    if ip['subnet_id'] == subnet_id:
                        port_id = port['id']

            # remove openstack router interface
            conn.network.router.delete_internal_interface(ext_id, subnet_id)
            task.progress(step_id, msg='Remove router interface from subnet %s' % subnet_id)

            # remove port resource
            resource = container.get_resource_by_extid(port_id)
            resource.expunge_internal()
            task.progress(step_id, msg='Remove port resource %s' % resource.oid)

        return oid, params


task_manager.tasks.register(RouterTask())
