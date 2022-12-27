# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import ujson as json
import base64
from celery.utils.log import get_task_logger
from beehive.common.task.job import job_task, task_local, job, JobError, Job
from gevent import sleep
from beehive_resource.plugins.vsphere.entity.vs_server import VsphereServer
from beecell.simple import id_gen, prefixlength_to_netmask
from beehive_resource.model import ResourceState
from beehive_resource.plugins.vsphere.entity.vs_volume import VsphereVolume
from beehive_resource.plugins.vsphere.entity.vs_volumetype import VsphereVolumeType

logger = get_task_logger(__name__)


class VsphereServerHelper(object):
    """Some vsphere server helper methods
    """
    def __init__(self, task, orchestrator, params):
        self.task = task
        self.orchestrator = orchestrator
        self.conn = orchestrator.conn
        self.params = params
        self.user = 'root'

        self.template_pwd = None
        self.__get_template_credentials()

    def __get_template_credentials(self):
        # get admin password
        self.template_pwd = self.params.get('metadata', {}).get('template_pwd', None)
        if self.template_pwd is None:
            logger.warn('Root password is not defined. Guest customization is not applicable')
            return None

    def check_server_up_and_configured(self, server):
        # get network config
        network = self.params.get('networks')[0]
        fixed_ip = network.get('fixed_ip', {})
        guest_host_name = fixed_ip.get('hostname', server.name)
        self.conn.server.wait_guest_hostname_is_set(server=server, hostname=guest_host_name, delta=20, maxtime=600)

    def is_windows(self, server):
        return self.conn.server.guest_is_windows(server)

    def reboot_windows_server(self, server):
        if self.conn.server.guest_is_windows(server) is True:
            self.conn.server.reboot(server)
            sleep(5)
            self.wait_guest_tools_is_running(server)
            self.task.progress('Reboot server %s' % server)

    def set_admin_user_name(self, server):
        if self.conn.server.guest_is_windows(server) is True:
            self.user = 'Administrator'

    def set_ext_id(self, server_id, mor_id):
        # update resource
        self.orchestrator.update_resource(server_id, ext_id=mor_id)

    def get_volume_type(self, volume):
        volume_types, tot = self.orchestrator.get_resources(type=VsphereVolumeType.objdef)
        volume_type = None
        for vt in volume_types:
            if vt.has_datastore(volume.get('storage')) is True:
                volume_type = vt
                break
        if volume_type is None:
            raise JobError('No volume type found for volume %s' % volume.get('id'))
        logger.debug('Get volume type: %s' % volume_type)
        return volume_type

    def create_volume(self, name, desc, parent_id, server, volume_type, config, boot=False):
        source_type = config.get('source_type')
        volume_size = config.get('volume_size')

        image = None
        snapshot = None
        volume_uuid = None
        if source_type == 'image':
            image = config.get('uuid')
            
            volume = self.orchestrator.resource_factory(VsphereVolume, name=name, desc=desc, parent=parent_id,
                                                        size=volume_size, volume_type=volume_type,
                                                        source_volid=volume_uuid, snapshot_id=snapshot, imageRef=image)
            volume_id = volume[0].get('uuid')
            self.task.progress('Create volume resource %s' % volume_id)
            
        elif source_type in ['volume']:
            # get existing volume
            volume_id = config.get('uuid')
            self.task.progress('Get existing volume resource %s' % volume_id)

        elif source_type is None:
            volume = self.orchestrator.resource_factory(VsphereVolume, name=name, desc=desc, parent=parent_id,
                                                        size=volume_size, volume_type=volume_type,
                                                        source_volid=volume_uuid, snapshot_id=snapshot, imageRef=image)
            volume_id = volume[0].get('uuid')
            self.task.progress('Create volume resource %s' % volume_id)

        # link volume id to server
        server.add_link('%s-%s-volume-link' % (server.oid, volume_id), 'volume', volume_id,
                        attributes={'boot': boot})
        self.task.progress('Setup volume link from %s to server %s' % (volume_id, server.oid))

        self.task.progress('Create volume %s - Completed' % volume_id)

        return volume_id

    def set_volumes_ext_id(self, inst, volumes):
        disks = self.conn.server.detail(inst).get('volumes')
        index = 0
        for volume in volumes:
            volume_ext_id = disks[index]['unit_number']
            resource = self.task.get_simple_resource(volume)
            self.orchestrator.update_resource(resource.oid, ext_id=volume_ext_id)
            index += 1

    def connect_network(self, inst, network):
        try:
            # connect network
            net_number = 1
            task = self.conn.server.hardware.update_network(inst, net_number, connect=True, network=network.ext_obj)
        except:
            # add network
            task = self.conn.server.hardware.add_network(inst, network.ext_obj)

        # loop until vsphere task has finished
        self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Connect network %s' % network.ext_id)

    def clone_from_template(self, server_id, name, folder, volume_type_id, volumes, network, resource_pool=None,
                            cluster=None, customization_spec_name='WS201x PRVCLOUD custom OS sysprep'):
        # get params
        # disk_size_gb = volumes[0].get('volume_size')
        flavor = self.params.get('flavorRef')
        # guest_id = flavor.get('guest_id')
        memory_mb = flavor.get('ram')
        cpu = flavor.get('vcpus')
        # core_x_socket = flavor.get('core_x_socket')
        # version = flavor.get('version')

        # get volumes
        disks = []
        main_volume = volumes[0]

        # get total volume size required
        total_size = sum([volume.get('volume_size') for volume in volumes])

        # get datastore for all the disks. Use the volume_type of the main volume for all the volume
        volume_type = self.task.get_simple_resource(volume_type_id)
        volume_tag = main_volume.get('tag', None)
        datastore = volume_type.get_best_datastore(total_size, tag=volume_tag)

        # get template reference
        template = self.task.get_resource(main_volume.get('image_id'))

        for volume in volumes:
            disk_type = 'secondary'
            if volume.get('boot_index', None) == 0:
                disk_type = 'main'
            disks.append({
                'type': disk_type,
                'name': '%s-disk-%s' % (name, id_gen(length=6)),
                'size': volume.get('volume_size'),
                'thin': False,
                'datastore': datastore.ext_obj
            })

        if resource_pool is not None:
            resource_pool = resource_pool.ext_obj
        elif cluster is not None:
            cluster = cluster.ext_obj

        # clone template
        task = self.conn.server.create_from_template(
            template.ext_obj, name, folder.ext_obj, datastore.ext_obj, resource_pool=resource_pool,
            cluster=cluster, power_on=False)
        self.task.progress('Clone template')

        # get physical server
        inst = self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Get physical server: %s' % inst._moId)

        # set physical server
        self.set_ext_id(server_id, inst._moId)
        self.task.progress('Set physical server: %s' % inst._moId)

        # loop until vsphere task has finished
        inst = self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Template %s cloned' % template.name)

        # shutdown server
        # self.stop(inst)

        # reconfigure vm
        task = self.conn.server.reconfigure(inst, network.ext_obj, disks=disks, memoryMB=memory_mb, numCPUs=cpu,
                                            numCoresPerSocket=1)
        self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Reconfigure server %s' % name)

        # customize windows server
        if self.is_windows(template.ext_obj) is True:
            # get network config
            fixed_ip = self.params.get('networks')[0].get('fixed_ip', {})
            guest_host_name = fixed_ip.get('hostname', name)

            # get admin pwd
            admin_pwd = self.params.get('adminPass', None)
            if admin_pwd is None:
                raise JobError('Admin password is not defined.')

            network_config = {
                'ip_address': fixed_ip.get('ip'),
                'ip_netmask': prefixlength_to_netmask(fixed_ip.get('prefix')),
                'ip_gateway': fixed_ip.get('gw'),
                'dns_server_list': fixed_ip.get('dns').split(','),
                'dns_domain': fixed_ip.get('dns_search', 'local')
            }

            task = self.conn.server.customize(inst, customization_spec_name, guest_host_name, admin_pwd, network_config)
            self.orchestrator.query_remote_task(self.task, task)

            self.task.progress('Customize server %s' % name)

        # start server
        self.start(inst)

        # check server is up and configured
        if self.is_windows(template.ext_obj) is True:
            self.check_server_up_and_configured(inst)

        self.task.progress('Clone server %s from template' % name)

        return inst

    def linked_clone_from_server(self, server_id, name, folder, volumes, network, resource_pool=None, cluster=None):
        """TODO: manage multiple disks"""
        # get server reference
        server_id = self.params.get('imageRef')
        server = self.task.get_resource(server_id)

        # get volumes
        disks = []
        for volume in volumes:
            datastore_id = volume.get('uuid')
            datastore = self.task.get_resource(datastore_id)
            disks.append({
                'name': '%s-disk-%s' % (name, id_gen(length=6)),
                'size': volume.get('volume_size'),
                'thin': False,
                'datastore': datastore.ext_obj
            })
        main_volume = disks.pop(0)
        main_datastore = main_volume.get('datastore')

        if resource_pool is not None:
            resource_pool = resource_pool.ext_obj
        elif cluster is not None:
            cluster = cluster.ext_obj

        # start creation
        task = self.conn.server.create_linked_clone(server.ext_obj, name, folder.ext_obj, main_datastore,
                                                    resource_pool=resource_pool.ext_obj, cluster=cluster,
                                                    power_on=False)

        # get physical server
        inst = self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Get physical server: %s' % inst._moId)

        # set physical server
        self.set_ext_id(server_id, inst._moId)
        self.task.progress('Set physical server: %s' % inst._moId)

        # loop until vsphere task has finished
        inst = self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Server %s cloned' % server.name)

        # todo: add other volumes

        # connect network
        self.connect_network(inst, network)

        self.task.progress('Linked clone of server %s from server' % name)

        return inst

    def create_new(self, server_id, name, folder, volumes, datastore, network, resource_pool=None, cluster=None):
        """TODO: manage multiple disks"""
        # get params
        disk_size_gb = volumes[0].get('volume_size')
        flavor = self.params.get('flavorRef')
        guest_id = flavor.get('guest_id')
        memory_mb = flavor.get('ram')
        cpu = flavor.get('vcpus')
        core_x_socket = flavor.get('core_x_socket')
        version = flavor.get('version')

        # get volumes
        disks = []
        for volume in volumes:
            datastore_id = volume.get('uuid')
            datastore = self.task.get_resource(datastore_id)
            disks.append({
                'name': '%s-disk-%s' % (name, id_gen(length=6)),
                'size': volume.get('volume_size'),
                'thin': False,
                'datastore': datastore.ext_obj,
                'datastore_name': datastore.name
            })
        main_volume = disks.pop(0)
        main_datastore = main_volume.get('datastore')

        if resource_pool is not None:
            resource_pool = resource_pool.ext_obj
        elif cluster is not None:
            cluster = cluster.ext_obj

        # start creation
        task = self.conn.server.create(name, guest_id, main_datastore, folder.ext_obj,
                                       network.ext_obj, memory_mb=memory_mb, cpu=cpu, core_x_socket=core_x_socket,
                                       disk_size_gb=int(disk_size_gb), version=version, power_on=False,
                                       resource_pool=resource_pool.ext_obj, cluster=cluster)

        # get physical server
        inst = self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Get physical server: %s' % inst._moId)

        # set physical server
        self.set_ext_id(server_id, inst._moId)
        self.task.progress('Set physical server: %s' % inst._moId)

        # loop until vsphere task has finished
        inst = self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Server %s created' % name)

        # todo: add other volumes

        return inst

    def set_security_group(self, inst):
        inst_id = inst._moId
        securitygroups = self.params.get('security_groups')
        for sg in securitygroups:
            try:
                sg = self.task.get_simple_resource(sg)
            except:
                logger.warn('Vsphere security group %s does not exist' % sg['uuid'])
                self.update('PROGRESS', msg='Vsphere security group %s does not exist' % sg['uuid'])

            self.conn.network.nsx.sg.add_member(sg.ext_id, inst_id)

    def start(self, inst):
        inst_id = inst._moId
        task = self.conn.server.start(inst)
        self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Start server %s' % inst_id)

    def stop(self, inst):
        state = inst.runtime.powerState
        oid = inst._moId
        logger.debug(u"Server %s current powerState is: %s" % (oid, state))
        if format(state) == 'poweredOn':
            task = self.conn.server.stop(inst)
            # loop until vsphere task has finished
            self.orchestrator.query_remote_task(self.task, task)
            self.task.progress('Power off server %s' % oid)

    def delete(self, resource, inst):
        # get ip and ippool
        ip_config = resource.get_ip_address_config()

        # delete vsphere server
        oid = inst._moId
        task = self.conn.server.remove(inst)
        # loop until vsphere task has finished
        self.orchestrator.query_remote_task(self.task, task)
        self.task.progress('Remove server %s' % oid)

        # release ip
        if ip_config is not None:
            subnet_pool = ip_config.get('subnet_pool', None)
            ip = ip_config.get('ip', None)
            if subnet_pool is not None and ip is not None:
                self.conn.network.nsx.ippool.release(subnet_pool, ip)
                self.task.progress('Release ip %s from subnet pool %s' % (ip, subnet_pool))

    def wait_guest_tools_is_running(self, inst, maxtime=180):
        # wait until guest tools are running
        elapsed = 0
        status = self.conn.server.guest_tools_is_running(inst)
        while status is not True:
            status = self.conn.server.guest_tools_is_running(inst)
            self.task.update('PROGRESS', msg='Wait guest tools are running')
            # sleep a little
            sleep(task_local.delta)
            elapsed += task_local.delta
            if elapsed > maxtime:
                raise Exception('Guest tools are not still running after %s s. Task will be blocked' % maxtime)
        self.task.update('PROGRESS', msg='Guest tools are running')

    def reserve_network_ip_address(self):
        # setup only the first network
        networks = self.params.get('networks')
        subnet_pool = networks[0].get('subnet_pool', None)
        fixed_ip = networks[0].get('fixed_ip', {})
        if subnet_pool is not None and fixed_ip.get('ip', None) is None:
            new_ip = self.conn.network.nsx.ippool.allocate(subnet_pool)
            '''
            {
                "dnsServer2": "10.102.184.3", 
                "id": "18", 
                "gateway": "10.102.184.1", 
                "dnsSuffix": "None", 
                "subnetId": "subnet-3", 
                "prefixLength": "24", 
                "ipAddress": "10.102.185.53", 
                "dnsServer1": "10.102.184.2"
            }
            '''
            fixed_ip.update({
                'ip': new_ip.get('ipAddress'),
                'gw': new_ip.get('gateway'),
                'dns': new_ip.get('dnsServer1') + ',' + new_ip.get('dnsServer2'),
                'dns_search': new_ip.get('dnsSuffix'),
                'prefix': new_ip.get('prefixLength')
            })
        self.params['networks'][0]['fixed_ip'] = fixed_ip

    def setup_network(self, inst):
        # get network config
        networks = self.params.get('networks')
        subnet_pool = networks[0].get('subnet_pool', None)
        config = networks[0].get('fixed_ip', {})

        # exec only for linux server
        if self.is_windows(inst) is False:
            if config is not None:
                self.wait_guest_tools_is_running(inst)
                self.set_admin_user_name(inst)

                # configure ip
                ipaddr = config.get('ip')
                macaddr = self.conn.server.hardware.get_original_devices(
                    inst, dev_type='vim.vm.device.VirtualVmxnet3')[0].macAddress
                gw = config.get('gw')
                hostname = config.get('hostname', inst.name)
                dns = config.get('dns', '')
                dns_search = config.get('dns_search', 'local')
                prefix = config.get('prefix', 24)
                self.conn.server.guest_setup_network(inst, self.template_pwd, ipaddr, macaddr, gw, hostname, dns,
                                                     dns_search, conn_name='net01', user=self.user, prefix=prefix)
            else:
                logger.warn('Network interface configuration is wrong')
        self.task.progress('Update network configuration')

        return [{'uuid': networks[0].get('uuid'), 'ip': config.get('ip'), 'subnet_pool': subnet_pool}]

    def setup_ssh_key(self, inst):
        # get ssh key
        ssh_key = self.params.get('metadata', {}).get('pubkey', None)
        if ssh_key is None:
            logger.warn('Ssh key is not defined.')
            return None

        self.conn.server.guest_setup_ssh_key(inst, self.user, self.template_pwd, ssh_key)
        self.task.progress('Setup ssh key')

    def setup_ssh_pwd(self, inst):
        # get ssh pwd
        ssh_pwd = self.params.get('adminPass', None)
        if ssh_pwd is None:
            logger.warn('Ssh password is not defined.')
            return None

        self.conn.server.guest_setup_admin_password(inst, self.user, self.template_pwd, ssh_pwd)
        self.task.progress('Setup ssh password')

    def create_server(self, name, folder_id, datastore_id, resource_pool_id, network_id, source_type='image'):
        logger.info('Create new server %s - %s - START' % name)

        # get folder
        folder = self.task.get_resource(folder_id)

        # create resource
        objid = '%s//%s' % (folder.objid, id_gen())
        model = self.orchestrator.add_resource(objid=objid, name=name, resource_class=VsphereServer, ext_id=None,
                                               active=False, desc='Stack server %s' % name, attrib={},
                                               parent=folder.oid)
        self.orchestrator.update_resource_state(model.id, ResourceState.BUILDING)

        # get resource pool
        resource_pool = self.task.get_resource(resource_pool_id)

        # get volumes
        datastore = self.task.get_resource(datastore_id)

        # get networks
        network = self.task.get_resource(network_id)

        # clone server from template
        if source_type == 'image':
            inst = self.clone_from_template(name, folder, datastore, resource_pool, network)

        # clone server from snapshot - linked clone
        elif source_type == 'snapshot':
            inst = self.linked_clone_from_server(name, folder, datastore, resource_pool, network)

        # create new server
        elif source_type == 'volume':
            volumes = None
            inst = self.create_new(name, folder, volumes, resource_pool, datastore, network)

        else:
            raise JobError('Source type %s is not supperted' % source_type)

        # set server security groups
        self.set_security_group(inst)

        # start server
        self.start(inst)

        # set network interface ip
        self.setup_network(inst)

        # setup ssh key
        self.setup_ssh_key(inst)

        # setup ssh password
        self.setup_ssh_pwd(inst)

        self.orchestrator.update_resource_state(model.id, ResourceState.ACTIVE)
        self.orchestrator.activate_resource(model.id)

        logger.info('Create new server %s - %s - STOP' % (name, model.oid))

        return model.oid
