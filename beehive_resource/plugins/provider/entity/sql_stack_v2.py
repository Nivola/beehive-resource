# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import logging

from beecell.simple import random_password, bool2str, dict_get, truncate, id_gen
from beecell.types.type_dict import dict_set
from beecell.types.type_string import str2bool
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.provider.entity.flavor import ComputeFlavor
from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.stack_v2 import ComputeStackV2, ComputeStackAction, \
    ComputeStackMysqlAction, ComputeStackPostgresqlAction
from beehive_resource.plugins.provider.entity.volumeflavor import ComputeVolumeFlavor
from beehive_resource.plugins.provider.entity.instance import ComputeInstance
from beehive_resource.plugins.provider.entity.image import ComputeImage
from beehive.common.task_v2 import prepare_or_run_task
from logging import getLogger
from typing import Any, Dict

from beehive_resource.plugins.provider.entity.vpc_v2 import Vpc

logger = getLogger(__name__)


class MysqlBase(object):
    engine_params = {
        'versions': ['5.7', '8'],
        'port': 3306,
        'hypervisor': 'openstack',
        'image': 'Centos7',
        'volume_flavor': 'vol.default',
        'host_group': 'default',
        'customization': 'mysql',
        'playbook': {
            'install': 'installMysql.yml',
            'config_replica': 'configMysqlReplica.yml'
        },
        'license': 'general-public-license',
        'charset': 'latin1',
        'service_users': {
            'zabbix': [
                {
                    'name': 'rou',
                    'pwd': 'Rou!142018',
                    'host': '%',
                    'privs': '*.*:SELECT'
                }
            ],
            'trilio': [
                {
                    'name': 'trilio',
                    'pwd': 'Oliri10!',
                    'host': 'localhost',
                    'privs': '*.*:SELECT,PROCESS,RELOAD'
                }
            ],
            'backup': [
                {
                    'name': 'mybck',
                    'pwd': 'y!7t0oNv',
                    'host': '%',
                    'privs': '*.*:SELECT,PROCESS,EXECUTE,SHOW VIEW,EVENT'
                }
            ]
        },
        'lvm': {
            'volume_group': {
                'data': 'vg_data',
                'backup': 'vg_backup'
            },
            'logical_volume': {
                'data': 'lv_fsdata',
                'backup': 'lv_fsbackup'
            }
        },
        'mount_point': {
            'data': '/data',
            # 'backup': '/BCK_fisici'
        }
    }


class PostgresqlBase(object):
    engine_params = {
        'versions': ['9.6', '11', '12.4'],
        'port': 5432,
        'hypervisor': 'openstack',
        'image': 'OracleLinux8',
        'volume_flavor': 'vol.default',
        'host_group': 'default',
        'customization': 'postgresql',
        'playbook': {
            'install': 'installPostgres.yml',
            'config_replica': 'configPostgresReplica.yml'
        },
        'license': 'general-public-license',
        'charset': 'utf8',
        'service_users': {
            'zabbix': [
                {
                    'name': 'zabbute',
                    'pwd': '7nTo6jviqVbD',
                    'attribs': 'NOSUPERUSER,INHERIT,NOCREATEDB,NOCREATEROLE,NOREPLICATION',
                    'privs': 'CONNECT:postgres'
                },
                {
                    'name': 'rou',
                    'pwd': 'rou!14',
                    'attribs': 'NOSUPERUSER,INHERIT,NOCREATEDB,NOCREATEROLE',
                    'privs': 'CONNECT:postgres'
                }
            ]
        },
        'lvm': {
            'volume_group': {
                'data': 'vg_data',
                'backup': 'vg_backup'
            },
            'logical_volume': {
                'data': 'lv_fsdata',
                'backup': 'lv_backup'
            }
        },
        'mount_point': {
            'data': '/data',
            # 'backup': '/BCK_fisici'
        }
    }

#
# doppio /oradata e in sqlstack_v2.py (Resource) leggere i nuovi parametri (lvm....)
#
class OracleBase(object):
    engine_params = {
        'versions': {
            '11EE': {
                'os_user': 'ora11g',
                'oversion': '11g'
            },
            '12EE': {
                'os_user': 'ora12c',
                'oversion': '12c'
            },
            '19EE': {
                'os_user': 'ora19c',
                'oversion': '19c'
            }
        },
        'port': 1521,
        'hypervisor': 'vsphere',
        'image': 'Oracle12EE',
        'volume_flavor': 'vol.oracle.default',
        'host_group': 'default',
        'customization': 'oracle',
        'playbook': {
            'install': 'CreateDboracle.yml',
            'delete': 'DeleteDbOracle.yml'
        },
        'license': 'license-included',
        'arch_mode': 'Y',
        'part_option': 'Y',
        'db_name': 'ORCL0',
        'nat_charset': 'AL16UTF16',
        'charset': 'WE8ISO8859P1',
        'lsn_port': '1522',
        'service_users': {
            'zabbix': [
                {
                    'name': 'rou',
                    'pwd': 'Rou!142018',
                    'host': '%',
                    'privs': '*.*:SELECT'
                }
            ]
        },
        'lvm': {
            'volume_group': {
                'data': 'vg_oradata',
                'backup': 'vg_orabck'
            },
            'logical_volume': {
                'data': 'lv_oradata',
                'backup': 'lv_orabck'
            }
        },
        'mount_point': {
            'data': '/oradata',
            'backup': '/BCK_fisici'
        }
    }


class SqlserverBase(object):
    engine_params = {
        'versions': ['2017'],
        'port': 1433,
        'hypervisor': 'vsphere',
        'image': 'mssql2017',
        'volume_flavor': 'vol.default',
        'host_group': 'default',
        'customization': 'sqlserver',
        'playbook': {
            'install': 'installSqlserver.yml',
            'config_replica': 'configSqlserverReplica.yml'
        },
        'license': 'license-included'
    }


class SqlHelper(object):
    def __init__(self, *args, **kvargs):
        self.logger = logging.getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)

        self.args = args
        self.kvargs = kvargs

        self.engines = [
            'mysql',
            'postgresql',
            'oracle',
            'sqlserver'
        ]

        self.engine_params = {}
        self.stack_v2_params = {}
        self.inputs = []
        self.outputs = []
        self.actions = []

    @staticmethod
    def get_engine_major_version(version, n):
        l = version.split('.')
        if len(l) > n:
            for i in range(n):
                return '.'.join(l[:n])
        return version

    @staticmethod
    def get_db_monit_user(users):
        """Get credentials of db user account used to collect database metrics

        :param users: dictionary of non-administrative database user accounts
        :return: a dict like this: {'name' ..., 'pwd': ...}
        """
        try:
            monit_user = users.get('zabbix')[0]
            username = monit_user.get('name')
            password = monit_user.get('pwd')
            if not username or not password:
                return None
            return {'name': username, 'pwd': password}
        except:
            return None


#
# Create
#
class SqlCreateHelper(SqlHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self.controller = controller
        self.container = container

        self.child_classes = [
            MysqlCreateHelper,
            PostgresqlCreateHelper,
            OracleCreateHelperNew,
            # OracleCreateHelper,
            SqlserverCreateHelper
        ]

        self.name = self.kvargs.get('name')
        self.desc = self.kvargs.get('desc')
        self.multi_avz = self.kvargs.get('multi_avz')
        self.host_group = self.kvargs.get('host_group')
        self.orchestrator_tag = self.kvargs.get('orchestrator_tag', 'default')
        self.hostname = self.kvargs.get('hostname', self.name)
        self.hypervisor = self.kvargs.get('hypervisor')
        self.charset = self.kvargs.get('charset', 'latin1')
        self.timezone = self.kvargs.get('timezone', 'Europe/Rome')
        self.csi_custom = self.kvargs.get('csi_custom', False)
        self.db_monitor = self.kvargs.get('db_monitor', True)

        self.replica = self.kvargs.get('replica', False)
        self.remove_replica = self.kvargs.get('remove_replica', False)
        self.replica_arch_type = self.kvargs.get('replica_arch_type', 'MS')
        self.replica_role = self.kvargs.get('replica_role', 'S')
        self.replica_sync_type = self.kvargs.get('replica_sync_type', 'async')
        self.replica_master = self.kvargs.get('replica_master')
        self.replica_ip_master = None

        self.custom_attributes = {}

        self.image = None
        self.os_ver = None
        self.license = None
        self.monit_user = None

    def get_helper_by_engine(self, engine):
        d = dict(zip(self.engines, self.child_classes))
        return d.get(engine)

    def get_image(self):
        """Get image resource

        :param filter: custom filter
        :return: Image instance
        """
        image = self.kvargs.get('image')
        if image is None:
            image = dict_get(self.engine_params, 'image')
        return self.controller.get_resource(image, **self.filter)

    def build_repo_url(self, port=80):
        url = 'http://' + '/'.join((self.ip_repository, 'repos', self.os_ver, self.engine, self.version))
        return url

    def get_volume_device_path(self, device_letter):
        """get device path for a specific hypervisor

        :param device_letter: device letter like a, b, c
        :return: device path like /dev/sda for vpshere or /dev/vda for openstack
        """
        if self.hypervisor == 'openstack':
            res = '/dev/vd%s' % device_letter
        elif self.hypervisor == 'vsphere':
            res = '/dev/sd%s' % device_letter
        return res

    def check_params(self):
        # get compute zone
        if 'compute_zone' in self.kvargs:
            compute_zone_id = self.kvargs.get('compute_zone')
        else:
            compute_zone_id = self.kvargs.get('parent')
        self.compute_zone = self.container.get_simple_resource(compute_zone_id)
        self.compute_zone.set_container(self.container)
        self.kvargs['parent'] = self.compute_zone.oid

        # get engine
        self.engine = self.kvargs.pop('engine')
        self.version = self.kvargs.pop('version')
        self.port = self.kvargs.pop('port', None)
        if self.port is None:
            self.port = dict_get(self.engine_params, 'port')

        # get customization
        customization = self.kvargs.get('customization')
        if customization is None:
            customization = dict_get(self.engine_params, 'customization')
        self.compute_customization = self.container.get_simple_resource(customization,
                                                                        entity_class=ComputeCustomization)

        # get hypervisor
        if self.hypervisor is None:
            self.hypervisor = dict_get(self.engine_params, 'hypervisor')

        # get hostgroup
        if self.host_group is None:
            self.host_group = dict_get(self.engine_params, 'host_group')

        # get site
        self.site = self.controller.get_resource(self.kvargs.pop('availability_zone'))
        self.ip_repository = self.site.get_attribs().get('repo')

        # get zabbix server connection params
        orchestrators = self.site.get_orchestrators_by_tag('tenant', select_types=['zabbix'])
        orchestrator_idx = list(orchestrators.keys())[0]
        orchestrator = self.controller.get_container(orchestrator_idx)
        conn_params = orchestrator.conn_params['api']
        self.zbx_srv_uri = conn_params.get('uri')
        self.zbx_srv_usr = conn_params.get('user')
        pwd = conn_params.get('pwd')
        self.zbx_srv_pwd = orchestrator.decrypt_data(pwd).decode('utf-8')

        # orchestrator_idx = self.site.get_orchestrators_by_tag(self.orchestrator_tag, index_field='type')
        # self.orchestrator = orchestrator_idx.get('openstack', None)
        # if self.orchestrator is None:
        #     raise ApiManagerError('No valid orchestrator found', code=404)

        self.filter = {'container_id': self.container.oid, 'run_customize': False}

        # get flavor
        self.flavor = self.controller.get_resource(self.kvargs.pop('flavor'), entity_class=ComputeFlavor, **self.filter)
        self.flavor.check_active()

        # get ram from flavor
        self.server_ram_mb = int(self.flavor.get_configs().get('memory'))
        self.server_ram_gb = self.server_ram_mb // 1024

        # get volume flavor
        self.volume_flavor = self.controller.get_resource(self.kvargs.pop('volume_flavor'),
                                                          entity_class=ComputeVolumeFlavor, **self.filter)
        self.volume_flavor.check_active()

        # get vpc
        self.vpc = self.controller.get_resource(self.kvargs.pop('vpc'), **self.filter)
        self.vpc.check_active()
        # vpc_nets, tot = self.vpc.get_linked_resources(link_type_filter='relation.%s' % self.site.oid,
        #                                               run_customize=False)
        # # ops_net = vpc_nets[0].get_physical_resource_from_container(self.orchestrator['id'], None)
        # vpc_net = vpc_nets[0]
        #
        # # get proxy and zabbix proxy
        # self.proxy, self.set_proxy = vpc_net.get_proxy()
        # self.zbx_proxy_ip, self.zbx_proxy_name = vpc_net.get_zabbix_proxy()

        # get proxy and zabbix proxy
        all_proxy = self.vpc.get_proxies(self.site.oid)
        self.proxy, self.set_proxy = all_proxy.get('http')
        self.zbx_proxy_ip, self.zbx_proxy_name = all_proxy.get('zabbix')

        # check subnet
        self.subnet = self.kvargs.pop('subnet')
        # allocable_subnet = vpc_net.get_allocable_subnet(subnet)

        # get security group
        self.security_group = self.controller.get_resource(self.kvargs.pop('security_group'), **self.filter)
        self.security_group.check_active()

        # get key
        if self.engine == 'sqlserver':
            self.key_name = None
        else:
            key_name = self.kvargs.get('key_name')
            keys = self.compute_zone.get_ssh_keys(oid=key_name)
            if len(keys) > 0:
                self.key_name = keys[0]['uuid']
            else:
                raise ApiManagerError('ssh key %s does not exist' % key_name)

        # get db related data
        self.db_name = self.kvargs.get('db_name')

        # get disk size
        self.root_disk_size = self.kvargs.pop('root_disk_size', 40)
        self.data_disk_size = self.kvargs.pop('data_disk_size', 30)
        self.bck_disk_size = self.kvargs.pop('bck_disk_size', 20)

        # get playbook
        self.playbook = dict_get(self.engine_params, 'playbook.install')
        # logger.warning(' _______ PLAYBOOK ______{}'.format(self.playbook ))
        # raise Exception('___STOP___')

        # set zabbix hostgroup
        self.zabbix_host_groups = [self.compute_zone.desc]

        # get lvm parameters
        self.lvm_vg_data = self.kvargs.pop('lvm_vg_data', dict_get(self.engine_params, 'lvm.volume_group.data'))
        self.lvm_vg_backup = self.kvargs.pop('lvm_vg_backup', dict_get(self.engine_params, 'lvm.volume_group.backup'))
        self.lvm_lv_data = self.kvargs.pop('lvm_lv_data', dict_get(self.engine_params, 'lvm.logical_volume.data'))
        self.lvm_lv_backup = self.kvargs.pop('lvm_lv_backup', dict_get(self.engine_params, 'lvm.logical_volume.backup'))

        # get mount points
        self.data_dir = self.kvargs.pop('data_dir', dict_get(self.engine_params, 'mount_point.data'))
        # self.backup_dir = self.kvargs.pop('backup_dir', dict_get(self.engine_params, 'mount_point.backup'))

    def check_replica_params(self):
        # replica consistency check
        if self.replica and self.replica_master is None:
            raise ApiManagerError('Replica master cannot be null when replication is enabled')

        if self.replica:
            # get master stack object
            master_stack = self.controller.get_resource(self.replica_master, entity_class=ComputeStackV2)
            # get master server ip address
            resources, tot = master_stack.get_linked_resources(link_type_filter='resource.%',
                                                               objdef=ComputeInstance.objdef, run_customize=False)
            self.compute_instance = resources[0]
            vpc_links, total = self.compute_instance.get_links(type='vpc')
            self.replica_ip_master = vpc_links[0].attribs.get('fixed_ip', {}).get('ip', '')

            # users
            master_stack_attribs = master_stack.get_attribs()
            users = master_stack_attribs.get('users')
            # - admin user
            admin_pwd = users.get('administrator').get('password')
            self.admin_pwd = self.controller.decrypt_data(admin_pwd).decode('utf-8')

            # - super user
            self.db_superuser_name = users.get('superuser').get('username')
            db_superuser_pwd = users.get('superuser').get('password')
            self.db_superuser_pwd = self.controller.decrypt_data(db_superuser_pwd).decode('utf-8')

            # - app user
            self.db_appuser_name = users.get('appuser').get('username')
            db_appuser_pwd = users.get('appuser').get('password')
            self.db_appuser_pwd = self.controller.decrypt_data(db_appuser_pwd).decode('utf-8')

            # - replica user
            self.replica_user = users.get('replica').get('username')
            replica_pwd = users.get('replica').get('password')
            self.replica_pwd = self.controller.decrypt_data(replica_pwd).decode('utf-8')
        else:
            # - admin user
            self.admin_user = None
            self.admin_pwd = self.kvargs.pop('db_root_password', None)

            # - super user
            self.db_superuser_name = self.kvargs.pop('db_superuser_name', 'system')
            self.db_superuser_pwd = self.kvargs.pop('db_superuser_password', random_password(length=10, strong=False))

            # - app user
            self.db_appuser_name = self.kvargs.pop('db_appuser_name', 'test')
            self.db_appuser_pwd = self.kvargs.pop('db_appuser_password', random_password(length=10, strong=False))

            # - replica user
            self.replica_user = None
            self.replica_pwd = None

    def internal_run(self):
        """This method is overridden by engine specialized class method"""
        pass

    def set_additional_steps(self):
        """This method is overridden by engine specialized class method"""
        pass

    def run(self):
        self.check_params()
        self.check_replica_params()
        self.internal_run()

        self.stack_v2_params['inputs'] = self.inputs
        self.stack_v2_params['outputs'] = self.outputs
        self.stack_v2_params['actions'] = self.actions
        self.kvargs.update(self.stack_v2_params)
        self.kvargs['attribute'] = {
            'stack_type': 'sql_stack',
            'engine': self.engine,
            'version': self.version,
            'allocated_storage': self.data_disk_size,
            'volume_flavor': self.volume_flavor.name,
            'charset': self.charset,
            'timezone': self.timezone,
            'license': self.license,
            'replica': self.replica,
            'port': self.port,
            'users': {
                'administrator': {
                    'username': self.admin_user,
                    'password': self.controller.encrypt_data(self.admin_pwd),
                },
                'superuser': {
                    'username': self.db_superuser_name,
                    'password': self.controller.encrypt_data(self.db_superuser_pwd),
                },
                'appuser': {
                    'username': self.db_appuser_name,
                    'password': self.controller.encrypt_data(self.db_appuser_pwd)
                }
            },
            'lvm': {
                'volume_group': {
                    'data': self.lvm_vg_data,
                    'backup': self.lvm_vg_backup
                },
                'logical_volume': {
                    'data': self.lvm_lv_data,
                    'backup': self.lvm_lv_backup
                }
            },
            'mount_point': {
                'data': self.data_dir,
                # 'backup': self.backup_dir
            }
        }

        # update attributes with custom_attributes
        self.kvargs['attribute'].update(self.custom_attributes)

        if self.replica:
            self.kvargs['attribute'].update({
                'replica_role': self.replica_role,
                'replica_arch_type': self.replica_arch_type,
                'replica_sync_type': self.replica_sync_type,
                'replica_master': self.replica_master
            })
            self.kvargs['attribute']['users'].update({
                'replica': {
                    'username': self.replica_user,
                    'password': self.controller.encrypt_data(self.replica_pwd)
                }
            })

        self.kvargs['additional_steps'] = self.set_additional_steps()

        return ComputeStackV2.pre_create(self.controller, self.container, *self.args, **self.kvargs)

    def set_output(self):
        return {
            'name': 'ResourceIP',
            'desc': 'Master Server IP address',
            'value': '$$action_resource.%s-create_server1::vpcs.0.fixed_ip.ip$$' % self.name
        }

    # def action_create_server(self):
    #     return {
    #         'name': 'create_server1',
    #         'desc': 'create server',
    #         'resource': {
    #             'type': 'ComputeInstance',
    #             'operation': 'create'
    #         },
    #         'params': {
    #             'name': '%s-server01' % self.name,
    #             'desc': '%s Server 01' % self.desc,
    #             'parent': self.compute_zone.oid,
    #             'availability_zone': self.site.oid,
    #             'multi_avz': self.multi_avz,
    #             'host_group': self.host_group,
    #             'orchestrator_tag': self.orchestrator_tag,
    #             'networks': [
    #                 {
    #                     'subnet': self.subnet,
    #                     'vpc': self.vpc.oid,
    #                     'fixed_ip': {
    #                         'hostname': self.hostname
    #                     }
    #                 }
    #             ],
    #             'flavor': self.flavor.oid,
    #             'security_groups': [self.security_group.oid],
    #             'admin_pass': random_password(length=10, strong=True),
    #             'key_name': self.key_name,
    #             'type': self.hypervisor,
    #             'user_data': None,
    #             'resolve': True,
    #             'manage': True,
    #             'block_device_mapping': [
    #                 {
    #                     'boot_index': 0,
    #                     'volume_size': self.root_disk_size,
    #                     'flavor': self.volume_flavor.oid,
    #                     'uuid': self.image.oid,
    #                     'source_type': 'image',
    #                 },
    #                 {
    #                     'boot_index': 1,
    #                     'volume_size': self.data_disk_size,
    #                     'flavor': self.volume_flavor.oid,
    #                 }
    #             ]
    #         }
    #     }

    def action_create_server(self):
        res = {
            'name': 'create_server1',
            'desc': 'create server',
            'resource': {
                'type': 'ComputeInstance',
                'operation': 'create'
            },
            'params': {
                'name': '%s-server01' % self.name,
                'desc': '%s Server 01' % self.desc,
                'parent': self.compute_zone.oid,
                'availability_zone': self.site.oid,
                'multi_avz': self.multi_avz,
                'host_group': self.host_group,
                'orchestrator_tag': self.orchestrator_tag,
                'networks': [
                    {
                        'subnet': self.subnet,
                        'vpc': self.vpc.oid,
                        'fixed_ip': {
                            'hostname': self.hostname
                        }
                    }
                ],
                'flavor': self.flavor.oid,
                'security_groups': [self.security_group.oid],
                'admin_pass': random_password(length=10, strong=True),
                'key_name': self.key_name,
                'type': self.hypervisor,
                'user_data': None,
                'resolve': True,
                'manage': True,
                'block_device_mapping': [
                    {
                        'boot_index': 0,
                        'volume_size': self.root_disk_size,
                        'flavor': self.volume_flavor.oid,
                        'uuid': self.image.oid,
                        'source_type': 'image',
                    },
                    {
                        'boot_index': 1,
                        'volume_size': self.data_disk_size,
                        'flavor': self.volume_flavor.oid,
                    }
                ]
            }
        }

        if self.engine == 'oracle':
            res['params']['block_device_mapping'].append({
                'boot_index': 2,
                'volume_size': self.bck_disk_size,
                'flavor': self.volume_flavor.oid
            })


        return res

    def action_wait_ssh_up(self):
        is_private = False
        if self.compute_zone.get_bastion_host() is not None:
            is_private = True

        res = {
            'name': 'wait_ssh_is_up',
            'desc': 'wait ssh is up',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-wait_ssh_is_up' % self.name,
                'parent': 'os-utility',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'wait_ssh_is_up.yml',
                'extra_vars': {
                    'is_private': is_private
                }
            }
        }
        return res

    def action_set_yum_proxy(self):
        res = {
            'name': 'set_yum_proxy',
            'desc': 'set yum proxy',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-set_yum_proxy' % self.name,
                'parent': 'os-utility',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'set_yum_proxy.yml',
                'extra_vars': {
                    'set_proxy': self.set_proxy,
                    'proxy_server': self.proxy
                }
            }
        }
        return res

    def action_set_dnf_proxy(self):
        res = {
            'name': 'set_dnf_proxy',
            'desc': 'set dnf proxy',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-set_dnf_proxy' % self.name,
                'parent': 'os-utility',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'set_dnf_proxy.yml',
                'extra_vars': {
                    'set_proxy': self.set_proxy,
                    'proxy_server': self.proxy
                }
            }
        }
        return res

    def action_set_etc_hosts(self):
        res = {
            'name': 'set_etc_hosts',
            'desc': 'set etc/hosts',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-set_etc_hosts' % self.name,
                'parent': 'os-utility',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'set_etc_hosts.yml',
                'extra_vars': {
                    'hostname': '$$action_resource.%s-create_server1::vpcs.0.fixed_ip.hostname$$' % self.name,
                    'ip_addr': '$$action_resource.%s-create_server1::vpcs.0.fixed_ip.ip$$' % self.name
                }
            }
        }
        return res

    def action_setup_volume(self, boot_index=1, data_dir='/data', data_device='/dev/vdb', volume_group='vg_data',
                            logical_volume='lv_fsdata'):
        res = {
            'name': 'setup_volume_%d' % boot_index,
            'desc': 'setup volume %d' % boot_index,
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-setup_volume_%d' % (self.name, boot_index),
                'parent': 'os-utility',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'setup_volume.yml',
                'extra_vars': {
                    'data_dir': data_dir,
                    'data_device': data_device,
                    'volume_group': volume_group,
                    'logical_volume': logical_volume,
                    'proxy_server': self.proxy
                }
            }
        }
        return res

    def action_enable_monitoring(self):
        res = {
            'name': 'enable_monitoring',
            'desc': 'enable monitoring',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-enable_monitoring' % self.name,
                'parent': 'zabbix-agent',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'install.yml',
                'extra_vars': {
                    'p_ip_repository': self.ip_repository,
                    'p_proxy_server': self.proxy,
                    'p_no_proxy': 'localhost,10.0.0.0/8',
                    'p_zabbix_proxy_ip': self.zbx_proxy_ip,
                    'p_zabbix_proxy_name': self.zbx_proxy_name,
                    'p_zabbix_server': self.zbx_srv_uri,
                    'p_zabbix_server_username': self.zbx_srv_usr,
                    'p_zabbix_server_password': self.zbx_srv_pwd,
                    'p_custom_host_groups': self.zabbix_host_groups,
                    'p_custom_templates': [],
                    'p_target_host': '$$action_resource.%s-create_server1::attributes.fqdn$$' % self.name,
                    'p_db_monitor_flag': self.db_monitor,
                    'p_db_engine': self.engine + ':' + self.os_ver,
                    'p_db_monit_username': self.monit_user.get('name'),
                    'p_db_monit_password': self.monit_user.get('pwd')
                }
            }
        }
        return res

    def action_enable_log_forwarding(self):
        res = {
            'name': 'enable_log_forwarding',
            'desc': 'enable log forwarding',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-enable_log_forwarding' % self.name,
                'parent': 'filebeat',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'install.yml',
                'extra_vars': {
                    'p_ip_repository': self.ip_repository,
                    'p_proxy_server': self.proxy,
                }
            }
        }
        return res


class MysqlCreateHelper(SqlCreateHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = MysqlBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = self.kvargs.pop('db_root_name', 'root')
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=True)
        self.engine_major_version = SqlHelper.get_engine_major_version(self.version, 2)
        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        # get users for monitoring, backup, etc.
        service_users: Dict[str, Any] = self.engine_params.get('service_users', {})
        self.monit_user = self.get_db_monit_user(service_users)
        # add user account 'root'@'%'
        service_users.update({
            'admin': [
                {
                    'name': 'root',
                    'pwd': self.admin_pwd,
                    'host': '%',
                    'privs': '*.*:ALL,GRANT'
                }
            ]
        })

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_create_server())
        # - wait ssh is up and running
        self.actions.append(self.action_wait_ssh_up())
        # - set etc/hosts
        self.actions.append(self.action_set_etc_hosts())
        if self.image.name == 'OracleLinux8':
            # - set dnf proxy
            self.actions.append(self.action_set_dnf_proxy())
        # - setup volume (prepare, format, mount)
        data_device = self.get_volume_device_path('b')
        self.actions.append(self.action_setup_volume(data_dir=self.data_dir, data_device=data_device,
                                                     volume_group=self.lvm_vg_data, logical_volume=self.lvm_lv_data))
        # - install mysql
        # todo: port, charset, timezone, db_appuser_name, db_appuser_name
        self.actions.append(self.action_install_mysql())
        # - enable login shell for mysql user
        self.actions.append(self.action_enable_login_shell(user='mysql', shell='/bin/bash'))
        # - create users for backup and monitoring
        self.actions.append(self.action_add_users(service_users))
        # - install extensions (i.e. plugins or components)
        extensions = ['audit:plugin']
        if '8.' in self.version:
            extensions.append('component_validate_password:component')
        self.actions.append(self.action_install_extensions(extensions))
        if self.monit_user:
            # - enable monitoring
            self.actions.append(self.action_enable_monitoring())
        # - enable log forwarding
        # self.actions.append(self.action_enable_log_forwarding())
        if self.csi_custom:
            # todo: add actions
            pass

    def set_additional_steps(self):
        steps = []
        if self.replica:
            steps.append({
                'step': ComputeStackV2.task_path + 'add_stack_links_step',
                'args': [self.replica_master]
            })
        return steps

    def action_install_mysql(self):
        res = {
            'name': 'install_mysql',
            'desc': 'install mysql',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-install_mysql' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': self.playbook,
                'extra_vars': {
                    'p_mysql_repo_version': self.engine_major_version,
                    'p_proxy_server': self.proxy,
                    'p_ip_repository': self.ip_repository,
                    'p_url_repository': self.url_repository,
                    'p_mysql_root_username': self.admin_user,
                    'p_mysql_root_password': self.admin_pwd,
                    'p_mysql_server_ram': self.server_ram_gb,
                }
            }
        }
        ComputeStackV2.set_replica_args(res, self.name, self.replica, self.replica_arch_type, self.replica_role,
                                        self.replica_sync_type, self.replica_ip_master, self.replica_user,
                                        self.replica_pwd, self.remove_replica)
        return res

    def action_enable_login_shell(self, user='mysql', shell='/bin/bash'):
        res = {
            'name': 'enable_login_shell',
            'desc': 'enable_login_shell',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-enable_login_shell' % self.name,
                'parent': 'os-utility',
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'enable_login_shell.yml',
                'extra_vars': {
                    'p_user': user,
                    'p_shell': shell
                }
            }
        }
        return res

    def action_add_users(self, users):
        # adapt users format to the one accepted by ansible role
        user_lst = []
        for v in users.values():
            user_lst.extend(v)

        res = {
            'name': 'add_users',
            'desc': 'add_users',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-add_users' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'UserMgmtMysql.yml',
                'extra_vars': {
                    'p_mysql_db_port': self.port,
                    'p_mysql_login_name': self.admin_user,
                    'p_mysql_login_password': self.admin_pwd,
                    'p_mysql_user_mgmt_type': 'addusr',
                    'p_mysql_users': user_lst
                }
            }
        }
        return res

    def action_install_extensions(self, extensions):
        # adapt extension format to the one accepted by ansible role
        extension_lst = []
        for extension in extensions:
            extension = extension.strip()
            name, type = extension.split(':')
            extension_lst.append({'name': name, 'type': type})

        res = {
            'name': 'install_extensions',
            'desc': 'install_extensions',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-install_extensions' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'extensionMgmtMysql.yml',
                'extra_vars': {
                    'p_mysql_db_port': self.port,
                    'p_mysql_root_username': self.admin_user,
                    'p_mysql_root_password': self.admin_pwd,
                    'p_ip_repository': self.ip_repository,
                    'p_mysql_extensions': extension_lst,
                    'p_mysql_db_restart': 1
                }
            }
        }
        return res


class PostgresqlCreateHelper(SqlCreateHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = PostgresqlBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = 'postgres'
        self.admin_pwd = random_password(length=20, strong=True)
        self.postgis_extension = bool2str(self.kvargs.get('geo_extension', True))
        self.engine_major_version = SqlHelper.get_engine_major_version(self.version, 2)
        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url(port=8080)

        # get users for monitoring, backup, etc.
        service_users: Dict[str, Any] = self.engine_params.get('service_users', {})
        self.monit_user = self.get_db_monit_user(service_users)

        self.custom_attributes = {'postgres:database': 'postgres'}

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_create_server())
        # - wait ssh is up and running
        self.actions.append(self.action_wait_ssh_up())
        # - set etc/hosts
        self.actions.append(self.action_set_etc_hosts())
        if self.image.name == 'OracleLinux8':
            # - set dnf proxy
            self.actions.append(self.action_set_dnf_proxy())
        # - setup volume (prepare, format, mount)
        data_device = self.get_volume_device_path('b')
        self.actions.append(self.action_setup_volume(data_dir=self.data_dir, data_device=data_device,
                                                     volume_group=self.lvm_vg_data, logical_volume=self.lvm_lv_data))
        # - install postgres
        # # todo: port, charset, timezone, db_appuser_name, db_appuser_name
        self.actions.append(self.action_install_postgresql())
        # - create users for backup and monitoring
        self.actions.append(self.action_add_users(service_users))
        # - grant privileges to service users
        self.actions.append(self.action_grant_privs(service_users))
        if self.monit_user:
            # - enable monitoring
            self.actions.append(self.action_enable_monitoring())
        # - enable log forwarding
        # self.actions.append(self.action_enable_log_forwarding())
        if self.csi_custom:
            # todo: add actions
            pass

    def action_install_postgresql(self):
        res = {
            'name': 'install_postgres',
            'desc': 'install postgres',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-install_postgres' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': self.playbook,
                'extra_vars': {
                    'p_proxy_server': self.proxy,
                    'p_ip_repository': self.ip_repository,
                    'p_url_repository': self.url_repository,
                    'p_postgres_repo_version': self.engine_major_version,
                    'p_postgis_ext': self.postgis_extension,
                    'p_postgres_admin_pwd': self.admin_pwd,
                    'p_postgres_server_ram': self.server_ram_mb
                }
            }
        }
        return res

    def action_add_users(self, users):
        # adapt users format to the one accepted by ansible role
        user_lst = []
        for v in users.values():
            user_lst.extend(v)

        res = {
            'name': 'add_users',
            'desc': 'add_users',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-add_users' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'userMgmtPostgres.yml',
                'extra_vars': {
                    'p_postgres_db_port': self.port,
                    'p_postgres_login_username': self.admin_user,
                    'p_postgres_login_password': self.admin_pwd,
                    'p_postgres_mgmt_action': 'add_user',
                    'p_postgres_users': user_lst
                }
            }
        }
        return res

    def action_grant_privs(self, users):
        # adapt privileges format to the one accepted by ansible role
        priv_lst = []
        for v in users.values():
            for item in v:
                usr_name = item.get('name')
                privs, db_name = item.get('privs').split(':')
                db_name = db_name.split('.')
                schema_name = '*'
                if len(db_name) > 1:
                    schema_name = db_name[1]
                db_name = db_name[0]
                priv_lst.append({'user': usr_name, 'privs': privs, 'db': db_name, 'schema': schema_name})

        res = {
            'name': 'grant_privs',
            'desc': 'grant_privs',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-grant_privs' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': 'privsMgmtPostgres.yml',
                'extra_vars': {
                    'p_postgres_db_port': self.port,
                    'p_postgres_login_username': self.admin_user,
                    'p_postgres_login_password': self.admin_pwd,
                    'p_postgres_mgmt_action': 'grant_privs',
                    'p_postgres_privs': priv_lst
                }
            }
        }
        return res


class OracleCreateHelper(SqlCreateHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = OracleBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = self.kvargs.pop('db_root_name', 'sys')
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=False)
        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_create_server())
        # - wait ssh is up and running
        self.actions.append(self.action_wait_ssh_up())
        # - set yum proxy
        self.actions.append(self.action_set_yum_proxy())
        # - install oracle
        # self.actions.append(self.action_install_oracle())
        if self.csi_custom:
            # todo: add actions
            pass

    def action_install_oracle(self):
        res = {
            'name': 'install_oracle',
            'desc': 'install oracle',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-install_oracle' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': self.playbook,
                'extra_vars': {
                    'proxy_server': self.proxy,
                    'p_ip_repository': self.ip_repository,
                    'url_repository': self.url_repository,
                    'db_name': self.db_name,
                    'db_root_name': self.admin_user,
                    'db_root_password': self.admin_pwd,
                    'db_superuser_name': self.db_superuser_name,
                    'db_superuser_password': self.db_superuser_pwd,
                    'db_schema_name': 'schematest',
                    'db_appuser_name': self.db_appuser_name,
                    'db_appuser_password': self.db_appuser_pwd,
                }
            }
        }
        # ComputeStackV2.set_ansible_ssh_common_args(res, self.name, self.compute_zone)
        return res


class OracleCreateHelperNew(SqlCreateHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = OracleBase.engine_params

    def check_params(self):
        super().check_params()

        # password utenti oracle di monitoraggio
        self.ora_user_eidp_pwd = random_password(length=20, strong=False)
        self.ora_user_csimon_pwd = random_password(length=20, strong=False)
        self.ora_user_perfstat_pwd = random_password(length=20, strong=False)
        self.ora_user_fw_pwd = random_password(length=20, strong=False)
        self.ora_user_pdbadmin_pwd = random_password(length=20, strong=False)

        oracle_parameters = self.kvargs.get('oracle_params')

        self.ora_version = dict_get(self.engine_params,'versions.' + self.version + '.oversion')

        self.ora_db_name =  oracle_parameters.get('oracle_db_name')
        if self.ora_db_name is None:
            self.ora_db_name = self.engine_params.get('db_name')

        self.ora_charset = oracle_parameters.get('oracle_charset')
        if self.ora_charset is None:
            self.ora_charset = self.engine_params.get('charset')

        self.charset = self.ora_charset

        self.ora_nat_cset = oracle_parameters.get('oracle_natcharset')
        if self.ora_nat_cset is None:
            self.ora_nat_cset = self.engine_params.get('nat_charset')

        self.ora_dataf_path = self.data_dir
        if self.ora_dataf_path is None:
            self.ora_dataf_path = self.engine_params.get('mount_point.data')

        self.backup_dir = self.kvargs.get('backup_dir')

        #if self.backup_dir is None:
        #    self.backup_dir = self.engine_params.get('mount_point.backup')
        #

        self.ora_os_user = oracle_parameters.get('oracle_os_user')
        if self.ora_os_user is None:
            self.ora_os_user = dict_get(self.engine_params, 'versions.' + self.version + '.os_user')

        self.ora_arch_mode = oracle_parameters.get('oracle_archivelog_mode')
        if self.ora_arch_mode is None:
            self.ora_arch_mode = self.engine_params.get('arch_mode')

        self.ora_part_option = oracle_parameters.get('oracle_partitioning_option')
        if self.ora_part_option is None:
            self.ora_part_option = self.engine_params.get('part_option')

        self.ora_lsn_port = oracle_parameters.get('oracle_listener_port')
        if self.ora_lsn_port is None:
            self.ora_lsn_port = self.engine_params.get('lsn_port')

        self.oracle_data_disk_size = oracle_parameters.get('oracle_data_disk_size')
        self.oracle_bck_disk_size = oracle_parameters.get('oracle_bck_disk_size')


        self.ora_recovf_path = self.backup_dir + '/orabck_' + self.ora_db_name + '/RMan'

        self.ora_splunkdir_fwuser = self.ora_dataf_path + '/' + self.ora_db_name + '/FW/fwsplunk'
        self.ora_dir_fwuser = self.ora_dataf_path + '/' + self.ora_db_name + '/FW/fw'
        self.ora_logdir_fwuser = self.ora_dataf_path + '/' + self.ora_db_name + '/FW/fwlog'


    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        #
        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        # get users for monitoring
        service_users: Dict[str, Any] = self.engine_params.get('service_users', {})
        self.monit_user = self.get_db_monit_user(service_users)
        self.outputs.append(self.set_output())

        #
        # - super user = system
        # valorizzato nel metodo check_replica_param , eseguito prima di internal_run
        #

        self.admin_user = self.kvargs.pop('db_root_name', 'sys')
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=False)

        self.ora_user_sys = self.admin_user
        self.ora_user_sys_pwd =  random_password(length=20, strong=False)
        self.ora_user_system = self.db_superuser_name
        self.ora_user_system_pwd = random_password(length=20, strong=False)

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_create_server())

        # - wait ssh is up and running
        self.actions.append(self.action_wait_ssh_up())
        #

        # PROXY
        self.actions.append(self.action_set_yum_proxy())

        #
        # - setup ORADATA volume (prepare, format, mount)
        # verifica se presente parametro option 'oracle_dbfdisksize' da cli. Nel caso, valorizza self.data_disk_size
        # Altrimenti utilizza il default definito su data_disk_size, con valore proveniente
        # da 'AllocatedStorage' di service (se specificato in cli, parametro 'storage')
        #
        if self.oracle_data_disk_size is not None:
            self.data_disk_size = self.oracle_data_disk_size
        #
        ora_data_device = self.get_volume_device_path('c')
        self.actions.append(self.action_setup_volume(boot_index=2, data_dir=self.ora_dataf_path, data_device=ora_data_device,
                                                     volume_group=self.lvm_vg_data, logical_volume=self.lvm_lv_data))
        # - setup BACKUP volume
        self.bck_disk_size = self.oracle_bck_disk_size
        bck_data_device = self.get_volume_device_path('d')
        self.actions.append(self.action_setup_volume(boot_index=3, data_dir=self.backup_dir, data_device=bck_data_device,
                                                     volume_group=self.lvm_vg_backup, logical_volume=self.lvm_lv_backup))
        # - install oracle
        self.actions.append(self.action_install_oracle())

        # enable monitoring
        if self.monit_user:
            self.actions.append(self.action_enable_monitoring())

        if self.csi_custom:
            # todo: add actions
            pass


    def action_install_oracle(self):
        res = {
            'name': 'install_oracle',
            'desc': 'install oracle',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-install_oracle' % self.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': '$$action_resource.%s-create_server1::id$$' % self.name,
                        'extra_vars': {}
                    }
                ],
                'playbook': self.playbook,
                'extra_vars': {
                    'p_oracle_user': self.ora_os_user,                  # da versione, O
                    'p_db_name': self.ora_db_name,                      # O
                    'p_listener_port': self.ora_lsn_port,               # D=1522
                    'p_system_pwd': self.ora_user_system_pwd,           # generato
                    'p_sys_pwd': self.ora_user_sys_pwd,                 # generato
                    'p_datafile_path': self.ora_dataf_path,             # D=/oradata
                    'p_controlfile_path': self.ora_dataf_path,          # D=/oradata
                    'p_flash_recov_path': self.ora_recovf_path,         # D=/BCK_fisici/orabck_$p_db_name/RMan
                    'p_redolog_path': self.ora_dataf_path,              # D=/oradata
                    'p_archivelogmode': self.ora_arch_mode,             # D=Y
                    'p_archivelog_path': self.ora_recovf_path,          # D=/BCK_fisici/orabck_$p_db_name/RMan
                    'p_dbcharset': self.ora_charset,                    # O
                    'p_national_charset': self.ora_nat_cset,            # D=AL16UTF16
                    'p_partitioning': self.ora_part_option,             # D=Y
                    'p_eidp_pwd': self.ora_user_eidp_pwd,               # generato
                    'p_csimon_pwd': self.ora_user_csimon_pwd,           # generato
                    'p_perfstat_pwd': self.ora_user_perfstat_pwd,       # generato
                    'p_fwuser_pwd': self.ora_user_fw_pwd,               # generato
                    'p_fwuser_dir': self.ora_dir_fwuser,                # D=/oradata/$p_db_name/FW/fw
                    'p_fwuser_logdir': self.ora_logdir_fwuser,          # D=/oradata/$p_db_name/FW/fwlog
                    'p_fwuser_splunkdir': self.ora_splunkdir_fwuser,    # D=/oradata/$p_db_name/FW/fwsplunk
                    'p_pdbadmin_pwd': self.ora_user_pdbadmin_pwd,       # generato
                    'p_oracle_version': self.ora_version,               # O in (11g,12c,19c)
                    'p_adv_sec': 'N',                                   # fisso
                }
            }
        }

        # ComputeStackV2.set_ansible_ssh_common_args(res, self.name, self.compute_zone)
        return res


class SqlserverCreateHelper(SqlCreateHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlCreateHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = SqlserverBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = self.kvargs.pop('db_root_name', 'admin')
        if self.admin_pwd is None:
            self.admin_pwd = random_password(length=20, strong=False)
        self.image = self.get_image()
        self.os_ver = self.image.get_os_version()
        self.url_repository = self.build_repo_url()

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_create_server())
        # - other actions
        # ...
        # ...
        # ...
        if self.csi_custom:
            # todo: add actions
            pass


#
# Import
#
class SqlImportHelper(SqlHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self.controller = controller
        self.container = container

        self.child_classes = [
            MysqlImportHelper,
            PostgresqlImportHelper,
            OracleImportHelper,
            SqlserverImportHelper
        ]

        physical_id = self.kvargs.get('physical_id')
        params = self.kvargs.pop('configs', {})

        # check server type from ext_id
        self.compute_instance = controller.get_resource(physical_id)
        if isinstance(self.compute_instance, ComputeInstance) is False:
            raise ApiManagerError('SqlComputeStack require ComputeInstance as physical resource')

        self.compute_instance_info = self.compute_instance.info()
        self.compute_instance_avz_num = len(self.compute_instance.get_dedploy_availability_zones())

        # # get compute zone
        # self.compute_zone = self.compute_instance.get_parent()
        # self.compute_zone.set_container(self.container)
        # self.kvargs['parent'] = self.compute_zone.oid
        # self.kvargs['objid'] = '%s//%s' % (self.compute_zone.objid, id_gen())

        self.name = self.kvargs.get('name')
        self.desc = self.kvargs.get('desc')

        self.multi_avz = True if self.compute_instance_avz_num > 0 else False
        self.host_group = dict_get(self.compute_instance_info, 'attributes.host_group')
        self.orchestrator_tag = dict_get(self.compute_instance_info, 'attributes.orchestrator_tag')
        self.hostname = dict_get(self.compute_instance_info, 'attributes.fqdn')
        self.hypervisor = dict_get(self.compute_instance_info, 'hypervisor')
        self.charset = params.get('charset', 'latin1')
        self.timezone = params.get('timezone', 'Europe/Rome')
        self.engine = params.get('engine')
        self.version = params.get('version')

        # get engine port
        self.port = params.get('port', None)

        # get data size
        block_device_mapping = self.compute_instance_info.get('block_device_mapping')
        self.data_disk_size = sum([b['volume_size'] for b in block_device_mapping[1:]])

        # get volume flavor
        main_volume = self.controller.get_resource(block_device_mapping[0]['id'])
        # self.volume_flavor_name = main_volume.get_flavor().get('name')
        self.volume_flavor_name = main_volume.get_flavor().name

        # super user
        self.admin_pwd = dict_get(params, 'pwd.admin')
        self.db_superuser_name = dict_get(params, 'db_superuser_name', default='system')
        self.db_superuser_pwd = dict_get(params, 'pwd.db_superuser', default='')
        self.db_appuser_name = dict_get(params, 'db_appuser_name', default='test')
        self.db_appuser_pwd = dict_get(params, 'pwd.db_appuser', default='')

        self.custom_attributes = {}

        self.image = None
        self.license = None

        self.replica = False

    def get_helper_by_engine(self, engine):
        d = dict(zip(self.engines, self.child_classes))
        return d.get(engine)

    def internal_run(self):
        pass

    def check_params(self):
        if self.port is None:
            self.port = dict_get(self.engine_params, 'port')

    def run(self):
        self.check_params()
        self.internal_run()

        self.stack_v2_params['inputs'] = self.inputs
        self.stack_v2_params['outputs'] = self.outputs
        self.stack_v2_params['actions'] = self.actions
        self.kvargs.update(self.stack_v2_params)
        self.kvargs['attribute'] = {
            'stack_type': 'sql_stack',
            'engine': self.engine,
            'version': self.version,
            'allocated_storage': self.data_disk_size,
            'volume_flavor': self.volume_flavor_name,
            'charset': self.charset,
            'timezone': self.timezone,
            'license': self.license,
            'replica': self.replica,
            'port': self.port,
            'postgres:database': 'postgres',
            'has_quotas': True,
            'users': {
                'administrator': {
                    'username': self.admin_user,
                    'password': self.controller.encrypt_data(self.admin_pwd),
                },
                'superuser': {
                    'username': self.db_superuser_name,
                    'password': self.controller.encrypt_data(self.db_superuser_pwd),
                },
                'appuser': {
                    'username': self.db_appuser_name,
                    'password': self.controller.encrypt_data(self.db_appuser_pwd)
                }
            }
        }

        # update attributes with custom_attributes
        self.kvargs['attribute'].update(self.custom_attributes)

        # set additional steps
        # self.kvargs['additional_steps'] = self.set_additional_steps()

        return ComputeStackV2.pre_import(self.controller, self.container, *self.args, **self.kvargs)

    def set_output(self):
        return {
            'name': 'ResourceIP',
            'desc': 'Master Server IP address',
            'value': '$$action_resource.%s-import_server1::vpcs.0.fixed_ip.ip$$' % self.name
        }

    def action_import_server(self):
        return {
            'name': 'import_server1',
            'desc': 'import server',
            'resource': {
                'type': 'ComputeInstance',
                'operation': 'import'
            },
            'params': {
                'uuid': self.compute_instance.uuid,
                # 'name': '%s-server01' % self.name,
                # 'desc': '%s Server 01' % self.desc,
                # 'parent': self.compute_zone.oid,
                # 'availability_zone': self.site.oid,
                # 'multi_avz': self.multi_avz,
                # 'host_group': self.host_group,
                # 'orchestrator_tag': self.orchestrator_tag,
                # 'networks': [
                #     {
                #         'subnet': self.subnet,
                #         'vpc': self.vpc.oid,
                #         'fixed_ip': {
                #             'hostname': self.hostname
                #         }
                #     }
                # ],
                # 'flavor': self.flavor.oid,
                # 'security_groups': [self.security_group.oid],
                # 'admin_pass': random_password(length=10, strong=True),
                # 'key_name': self.key_name,
                # 'type': self.hypervisor,
                # 'user_data': None,
                # 'resolve': True,
                # 'manage': True,
                # 'block_device_mapping': [
                #     {
                #         'boot_index': 0,
                #         'volume_size': self.root_disk_size,
                #         'flavor': self.volume_flavor.oid,
                #         'uuid': self.image.oid,
                #         'source_type': 'image',
                #     },
                #     {
                #         'boot_index': 1,
                #         'volume_size': self.data_disk_size,
                #         'flavor': self.volume_flavor.oid,
                #     }
                # ]
            }
        }


class MysqlImportHelper(SqlImportHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlImportHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = MysqlBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = self.kvargs.pop('db_root_name', 'root')

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_import_server())


class PostgresqlImportHelper(SqlImportHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlImportHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = PostgresqlBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = 'postgres'

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_import_server())


class OracleImportHelper(SqlImportHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlImportHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = OracleBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = self.kvargs.pop('db_root_name', 'sys')

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_import_server())


class SqlserverImportHelper(SqlImportHelper):
    def __init__(self, controller, container, *args, **kvargs):
        SqlImportHelper.__init__(self, controller, container, *args, **kvargs)
        # set default engine params
        self.engine_params = SqlserverBase.engine_params

    def internal_run(self):
        self.license = dict_get(self.engine_params, 'license')
        self.admin_user = self.kvargs.pop('db_root_name', 'admin')

        self.outputs.append(self.set_output())

        # define actions workflow
        # - create vm and volumes
        self.actions.append(self.action_import_server())


#
# Update
#
class SqlUpdateHelper(SqlHelper):
    def __init__(self, stack, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self.child_classes = [
            MysqlUpdateHelper,
            PostgresqlUpdateHelper,
            OracleUpdateHelper,
            SqlserverUpdateHelper
        ]

        self.stack = stack

    def get_helper_by_engine(self, engine):
        d = dict(zip(self.engines, self.child_classes))
        return d.get(engine)

    def check_params(self):
        # get compute zone
        self.compute_zone = self.stack.get_parent()
        self.kvargs['parent'] = self.compute_zone.oid

        # get engine
        self.engine = self.stack.get_attribs(key='engine')

        # get compute customization
        customization = self.kvargs.get('customization')
        if customization is None:
            customization = dict_get(self.engine_params, 'customization')
        self.compute_customization = self.stack.container.get_simple_resource(customization,
                                                                              entity_class=ComputeCustomization)

        # get playbook
        self.playbook = dict_get(self.engine_params, 'playbook.config_replica')

        # users
        # - admin user
        self.admin_user = self.stack.get_attribs('users').get('administrator').get('username')
        admin_pwd = self.stack.get_attribs('users').get('administrator').get('password')
        self.admin_pwd = self.stack.controller.decrypt_data(admin_pwd).decode('utf-8')

    def check_replica_params(self):
        self.remove_replica = self.kvargs.get('remove_replica', False)
        if self.remove_replica:
            # get replica params from stack object attributes
            stack_attribs = self.stack.get_attribs()
            self.replica_arch_type = stack_attribs.get('replica_arch_type')
            self.replica_role = stack_attribs.get('replica_role')
            self.replica_sync_type = stack_attribs.get('replica_sync_type')
            self.replica_master = stack_attribs.get('replica_master')
        else:
            # get replica params from kvargs
            self.replica_arch_type = self.kvargs.get('replica_arch_type', 'MS')
            self.replica_role = self.kvargs.get('replica_role', 'S')
            self.replica_sync_type = self.kvargs.get('replica_sync_type', 'async')
            self.replica_master = self.kvargs.get('replica_master')

        # replica consistency checks
        if self.replica_role == 'S' and self.replica_master is None:
            raise ApiManagerError('Missing replica master')

        # get compute instance linked to stack
        resources = self.stack.controller.get_directed_linked_resources_internal(resources=[self.stack.oid],
                                                                                 link_type='resource%',
                                                                                 objdef=ComputeInstance.objdef)
        self.compute_instance = resources.get(self.stack.oid)[0]

        if self.replica_role == 'M':
            # get compute instance ip address and set it as ip address of master server
            vpc_links, total = self.compute_instance.get_links(type='vpc')
            self.replica_ip_master = vpc_links[0].attribs.get('fixed_ip', {}).get('ip', '')

            # users
            # - replica user
            self.replica_user = self.kvargs.get('replica_username', 'replica')
            self.replica_pwd = self.kvargs.get('replica_password', random_password(length=20, strong=True))
        # slave
        else:
            # get master stack object
            master_stack = self.stack.controller.get_resource(self.replica_master, entity_class=ComputeStackV2)
            # get master stack attributes
            master_stack_attribs = master_stack.get_attribs()
            # get compute instance linked to master stack
            resources, tot = master_stack.get_linked_resources(link_type_filter='resource.%',
                                                               objdef=ComputeInstance.objdef, run_customize=False)
            master_compute_instance = resources[0]
            # get master compute instance ip address and set it as ip address of master server
            vpc_links, total = master_compute_instance.get_links(type='vpc')
            self.replica_ip_master = vpc_links[0].attribs.get('fixed_ip', {}).get('ip', '')

            # users
            # - replica user
            users = master_stack_attribs.get('users')
            self.replica_user = users.get('replica').get('username')
            replica_pwd = users.get('replica').get('password')
            self.replica_pwd = self.stack.controller.decrypt_data(replica_pwd).decode('utf-8')

    def internal_run(self):
        """This method is overridden by engine specialized class method"""
        pass

    def set_additional_steps(self):
        """This method is overridden by engine specialized class method"""
        pass

    def run(self):
        self.check_params()
        self.check_replica_params()
        self.internal_run()

        # update stack params
        self.stack_v2_params['actions'] = self.actions
        self.kvargs.update(self.stack_v2_params)

        # additional steps
        self.kvargs['additional_steps'] = self.set_additional_steps()

        # update object attributes
        attribs = {
            'replica_arch_type': self.replica_arch_type,
            'replica_role': self.replica_role,
            'replica_sync_type': self.replica_sync_type,
            'replica_master': self.replica_master,
        }
        if self.remove_replica:
            self.stack.set_configs(key='replica', value=False)
            for k in attribs.keys():
                self.stack.unset_configs(key=k)
            self.stack.unset_configs(key='users.replica')
        else:
            self.stack.set_configs(key='replica', value=True)
            for k, v in attribs.items():
                self.stack.set_configs(key=k, value=v)
            self.stack.set_configs(key='users.replica.username', value=self.replica_user)
            self.stack.set_configs(key='users.replica.password',
                                   value=self.stack.controller.encrypt_data(self.replica_pwd))

        return ComputeStackV2.pre_update(self.stack, *self.args, **self.kvargs)


class MysqlUpdateHelper(SqlUpdateHelper):
    def __init__(self, *args, **kvargs):
        SqlUpdateHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = MysqlBase.engine_params

    def internal_run(self):
        engine_version = self.stack.get_attribs('version')
        self.engine_major_version = SqlHelper.get_engine_major_version(engine_version, 2)
        # append action to the action list
        self.actions.append(self.action_config_replica_mysql())

    def set_additional_steps(self):
        steps = []
        if self.remove_replica:
            steps.append({
                'step': ComputeStackV2.task_path + 'delete_stack_links_step',
                'args': [self.replica_master]
            })
        else:
            if self.replica_role == 'S' or self.replica_arch_type == 'MM':
                steps.append({
                    'step': ComputeStackV2.task_path + 'add_stack_links_step',
                    'args': [self.replica_master]
                })
        return steps

    def action_config_replica_mysql(self):
        res = {
            'name': 'config_replica_mysql',
            'desc': 'config replica mysql',
            'resource': {
                'type': 'AppliedComputeCustomization',
                'operation': 'create'
            },
            'params': {
                'name': '%s-config_replica_mysql' % self.stack.name,
                'parent': self.compute_customization.oid,
                'compute_zone': self.compute_zone.oid,
                'instances': [
                    {
                        'id': self.compute_instance.oid,
                        'extra_vars': {}
                    }
                ],
                'playbook': self.playbook,
                'extra_vars': {
                    'p_mysql_repo_version': self.engine_major_version,
                    'p_mysql_root_username': self.admin_user,
                    'p_mysql_root_password': self.admin_pwd
                }
            }
        }
        # ComputeStackV2.set_ansible_ssh_common_args(res, self.stack.name, self.compute_zone)
        ComputeStackV2.set_replica_args(res, self.stack.name, True, self.replica_arch_type, self.replica_role,
                                        self.replica_sync_type, self.replica_ip_master, self.replica_user,
                                        self.replica_pwd, self.remove_replica)
        return res


class PostgresqlUpdateHelper(SqlUpdateHelper):
    def __init__(self, *args, **kvargs):
        SqlUpdateHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = PostgresqlBase.engine_params

    def internal_run(self):
        pass


class OracleUpdateHelper(SqlUpdateHelper):
    def __init__(self, *args, **kvargs):
        SqlUpdateHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = OracleBase.engine_params

    def internal_run(self):
        pass


class SqlserverUpdateHelper(SqlUpdateHelper):
    def __init__(self, *args, **kvargs):
        SqlUpdateHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = SqlserverBase.engine_params

    def internal_run(self):
        pass


#
# Actions
#
class SqlActionHelper(SqlHelper):
    def __init__(self, stack, operation, *args, **kvargs):
        SqlHelper.__init__(self, *args, **kvargs)

        self.logger = getLogger(self.__class__.__module__ + '.' + self.__class__.__name__)

        self.child_classes = [
            MysqlActionHelper,
            PostgresqlActionHelper,
            OracleActionHelper,
            SqlserverActionHelper
        ]

        self.stack = stack
        self.operation = operation

    def get_helper_by_engine(self, engine):
        d = dict(zip(self.engines, self.child_classes))
        return d.get(engine)

    def get_compute_instance(self):
        """Get compute instance linked to stack"""
        resources = self.stack.controller.get_directed_linked_resources_internal(resources=[self.stack.oid],
                                                                                 link_type='resource%',
                                                                                 objdef=ComputeInstance.objdef)
        resources = resources.get(self.stack.oid)
        if resources is not None and len(resources) > 0:
            self.compute_instance = resources[0]
        else:
            self.compute_instance = None

    def check_params(self):
        # verify permissions
        self.stack.verify_permisssions('update')

        # check state is ACTIVE
        self.stack.check_active()

        # get compute zone
        self.compute_zone = self.stack.get_parent()
        self.kvargs['parent'] = self.compute_zone.oid
        self.get_compute_instance()

    def internal_run(self):
        """This method is overridden by engine specialized class method"""
        pass

    def set_additional_steps(self):
        """This method is overridden by engine specialized class method"""
        pass

    def get_db_admin_user(self):
        users = self.stack.get_attribs('users')
        # new user registration
        if users.get('administrator', None) is not None:
            admin_usr = self.stack.get_attribs('users.administrator.username')
            admin_pwd = self.stack.get_attribs('users.administrator.password')
        # old user registration
        else:
            # todo: verify for the other db engine except for mysql
            admin_usr = 'root'
            admin_pwd = self.stack.get_attribs('users.root')
        admin_pwd = self.stack.controller.decrypt_data(admin_pwd).decode('utf-8')

        return {'name': admin_usr, 'pwd': admin_pwd}

    def add_security_group(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def del_security_group(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def set_flavor(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_monitoring(self, **kwargs):
        monit_user = self.get_db_monit_user(self.engine_params.get('service_users'))
        if not monit_user:
            raise ApiManagerError('Unable to find user account for database monitoring')

        # get image
        resources = self.compute_instance.controller.get_directed_linked_resources_internal(
            resources=[self.compute_instance.oid], link_type='image', objdef=ComputeImage.objdef)
        image = resources.get(self.compute_instance.oid)[0]
        os_ver = image.get_os_version()

        # add specific db monitoring parameters for ansible playbook
        kwargs.update({
            'extra_vars': {
                'p_db_monitor_flag': True,
                'p_db_engine': self.stack.get_attribs(key='engine') + ':' + os_ver,
                'p_db_monit_username': monit_user.get('name'),
                'p_db_monit_password': monit_user.get('pwd')
            }
        })
        SqlActionHelper.run_server_action(self, **kwargs)

    def disable_monitoring(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_logging(self, **kwargs):
        SqlActionHelper.run_server_action(self, **kwargs)

    def enable_mailx(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # get site attributes
        site_id = self.compute_instance.get_attribs(key='availability_zone')
        site = self.compute_instance.controller.get_resource(site_id)
        site_attribs = site.get_attribs(key='config')

        # get domain
        domain = site_attribs.get('zone')

        # get relayhost
        relayhost = self.kvargs.get('relayhost')
        if relayhost is None:
            relayhost = site_attribs.get('postfix_relayhost')

        # create task workflow
        steps = [{
            'step': ComputeStackAction.task_path + 'sql_enable_mailx_step',
            'args': [self.compute_instance.oid, relayhost, domain]
        }]
        self.kvargs['steps'] = steps

    def pre_register_deregister(self):
        """Common operations to do before registering on / de-registering from haproxy
        """
        # get site
        site_id = self.compute_instance.get_attribs().get('availability_zone')
        site = self.compute_instance.controller.get_resource(site_id)

        # get awx container
        orchestrator_tag = 'default'
        orchestrators = site.get_orchestrators_by_tag(orchestrator_tag, select_types=['awx'])
        orchestrator = next(iter(orchestrators.values()))

        # get awx inventory
        inventories = dict_get(orchestrator, 'config.inventories', default=[])
        if len(inventories) < 1:
            raise ApiManagerError('No awx inventory configured for orchestrator %s' % orchestrator['id'])
        inventory = inventories[0]
        inventory_id = inventory.get('id')
        ssh_cred_id = inventory.get('credential')

        # get awx project
        from beehive_resource.plugins.provider.entity.customization import ComputeCustomization
        from beehive_resource.plugins.awx.entity.awx_project import AwxProject
        compute_customization = self.stack.container.get_simple_resource('haproxy', entity_class=ComputeCustomization)
        customization = compute_customization.get_local_resource(site_id)
        awx_project = customization.get_physical_resource(AwxProject.objdef)

        return [
            {
                'inventory': inventory_id,
                'project': awx_project.oid,
                'playbook': 'manage_reg.yml',
                'verbosity': 0,
                'ssh_cred_id': ssh_cred_id,
            },
            orchestrator
        ]

    def haproxy_register(self, **kwargs):
        """Register database server on haproxy
        """
        res = self.pre_register_deregister()
        job_template_args = res[0]
        orchestrator = res[1]

        # get db engine port
        engine_port = self.stack.get_attribs(key='port')

        # get db server ip address
        vpc_links, total = self.compute_instance.get_links(type='vpc')
        server_ip = vpc_links[0].attribs.get('fixed_ip', {}).get('ip', '')

        job_template_args['name'] = '%s-register_on_haproxy-jobtemplate-%s' % (self.stack.name, id_gen(10))
        job_template_args['desc'] = 'register database server on haproxy'
        job_template_args['extra_vars'] = {
            'server_name': self.stack.name,
            'server_ip': server_ip,
            'engine_port': engine_port,
            'operation': 'add'
        }

        # get initial and final port numbers of haproxy range of ports the clients can connect to
        hap_port_ini = self.kvargs.get('port_ini')
        hap_port_fin = self.kvargs.get('port_fin')

        if (hap_port_ini is not None) and (hap_port_fin is not None):
            job_template_args['extra_vars'].update({
                'hap_port_ini': hap_port_ini,
                'hap_port_fin': hap_port_fin,
            })

        # create task workflow
        steps = [{
            'step': ComputeStackAction.task_path + 'create_awx_job_template_step',
            'args': [job_template_args, orchestrator]
        }]
        self.kvargs['steps'] = steps

    def haproxy_deregister(self, **kwargs):
        """Deregister database server from haproxy
        """
        res = self.pre_register_deregister()
        job_template_args = res[0]
        orchestrator = res[1]

        job_template_args['name'] = '%s-deregister_from_haproxy-jobtemplate-%s' % (self.stack.name, id_gen(10))
        job_template_args['desc'] = 'deregister database server from haproxy'
        job_template_args['extra_vars'] = {
            'server_name': self.stack.name,
            'operation': 'del'
        }

        # create task workflow
        steps = [{
            'step': ComputeStackAction.task_path + 'create_awx_job_template_step',
            'args': [job_template_args, orchestrator]
        }]
        self.kvargs['steps'] = steps

    def resize(self, **kwargs):
        """Increase database storage capacity
        """
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # validate disk size
        data_disk_size = self.stack.get_allocated_storage()
        #data_disk_size = self.stack.get_attribs(key='allocated_storage')
        new_data_disk_size = self.kvargs.pop('new_data_disk_size')
        if new_data_disk_size < data_disk_size:
            raise ApiManagerError('New storage value must be greater than the current value')
        disk_size = new_data_disk_size - data_disk_size

        # get vpc
        vpcs, total = self.compute_instance.get_linked_resources(link_type='vpc')
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.compute_instance.get_attribs().get('availability_zone')

        # get proxy
        all_proxies = vpc.get_proxies(site_id)
        proxy, set_proxy = all_proxies.get('http')

        # get hypervisor
        hypervisor = self.compute_instance.get_hypervisor()

        # get lvm parameters
        vg_data = self.stack.get_attribs(key='lvm.volume_group.data')
        if vg_data is None:
            vg_data = dict_get(self.engine_params, 'lvm.volume_group.data')
        lv_data = self.stack.get_attribs(key='lvm.logical_volume.data')
        if lv_data is None:
            lv_data = dict_get(self.engine_params, 'lvm.logical_volume.data')

        ac_params = {
            'customization': 'os-utility',
            'playbook': 'extend_volume.yml',
            'extra_vars': {
                'volume_group': vg_data,
                'logical_volume': lv_data,
                'proxy_server': proxy,
                'hypervisor': hypervisor
            }
        }

        # create task workflow
        steps = [
            # - create volume
            {
                'step': ComputeStackAction.task_path + 'sql_create_compute_volume_step',
                'args': [self.compute_instance.oid, disk_size]
            },
            # - attach volume to vm
            {
                'step': ComputeStackAction.task_path + 'sql_run_action_on_server_step',
                'args': [self.compute_instance.oid]
            },
            # - extend vg and lv
            {
                'step': ComputeStackAction.task_path + 'sql_invoke_apply_customization_step',
                'args': [self.compute_instance.oid, ac_params]
            },
            # - update allocated storage attribute
            {
                'step': ComputeStackAction.task_path + 'sql_update_allocated_storage_step',
                'args': [new_data_disk_size]
            }
        ]

        self.kvargs['steps'] = steps

    def run_server_action(self, **kwargs):
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # get extra vars if exist
        extra_vars = kwargs.pop('extra_vars', None)
        if extra_vars is not None:
            self.kvargs['extra_vars'] = extra_vars

        # create task workflow
        steps = [{
            'step': ComputeStackAction.task_path + 'sql_run_action_on_server_step',
            'args': [self.compute_instance.oid]
        }]
        self.kvargs['steps'] = steps

    def run(self):
        self.check_params()
        self.internal_run()

        # get engine
        engine = self.stack.get_attribs(key='engine')

        # get engine major version
        engine_version = self.stack.get_attribs(key='version')
        engine_major_version = SqlHelper.get_engine_major_version(engine_version, 2)

        # get port
        port = self.stack.get_attribs(key='port')

        # get db admin credentials
        admin_user = self.get_db_admin_user()
        admin_usr = admin_user.get('name')
        admin_pwd = admin_user.get('pwd')

        # task workflow
        run_steps = [ComputeStackV2.task_path + 'action_resource_pre_step']
        run_steps.extend(self.kvargs.pop('steps', []))
        run_steps.append(ComputeStackV2.task_path + 'action_resource_post_step')

        # manage params
        params = {
            'cid': self.stack.container.oid,
            'id': self.stack.oid,
            'objid': self.stack.objid,
            'ext_id': self.stack.ext_id,
            'engine': engine,
            'version': engine_major_version,
            'port': port,
            'admin_usr': admin_usr,
            'admin_pwd': admin_pwd,
            'action_name': self.operation,
            'steps': run_steps,
            'alias': '%s.%s' % (self.__class__.__name__, self.operation),
            # 'sync': True
        }
        params.update(self.kvargs)
        params.update(self.stack.get_user())
        res = prepare_or_run_task(self.stack, self.stack.action_task, params, sync=False)
        self.logger.info('Execute %s action on compute stack %s using task' % (self.operation, self.stack.uuid))
        return res


class MysqlActionHelper(SqlActionHelper):
    def __init__(self, *args, **kvargs):
        SqlActionHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = MysqlBase.engine_params

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)

    def stop(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is already stopped' % self.compute_instance.uuid)

        force = self.kvargs.get('force', False)

        # create task workflow
        steps = []
        # - stop engine
        if not force:
            steps.append({
                'step': ComputeStackMysqlAction.task_path + 'mysql_manage_engine_step',
                'args': [self.compute_instance.oid]
            })
        # - stop server
        steps.append({
            'step': ComputeStackAction.task_path + 'sql_run_action_on_server_step',
            'args': [self.compute_instance.oid]
        })

        self.kvargs['steps'] = steps

    def start(self, **kvargs):
        if self.compute_instance.is_running() is True:
            raise ApiManagerError('Server %s is already running' % self.compute_instance.uuid)

        # create task workflow
        # - start server
        steps = [{
            'step': ComputeStackAction.task_path + 'sql_run_action_on_server_step',
            'args': [self.compute_instance.oid]
        }]
        # - wait server is up and running
        data = {
            'customization': 'os-utility',
            'playbook': 'wait_ssh_is_up.yml',
        }
        steps.append({
            'step': ComputeStackAction.task_path + 'sql_invoke_apply_customization_step',
            'args': [self.compute_instance.oid, data]
        })
        # - start engine
        steps.append({
            'step': ComputeStackMysqlAction.task_path + 'mysql_manage_engine_step',
            'args': [self.compute_instance.oid]
        })
        self.kvargs['steps'] = steps

    def restart(self, **kvargs):
        steps = []
        if self.compute_instance.is_running() is True:
            self.logger.info('Server %s is running, restart database service' % self.compute_instance.uuid)
            # restart engine
            steps.append({
                'step': ComputeStackMysqlAction.task_path + 'mysql_manage_engine_step',
                'args': [self.compute_instance.oid]
            })
            self.kvargs['steps'] = steps
        else:
            self.logger.info('Server %s is stopped, start server and database service' % self.compute_instance.uuid)
            self.start(**kvargs)

    def __run_mysql_query(self, query):
        # get db admin credentials
        admin_user = self.get_db_admin_user()

        # cmd = "mysqlsh --json=raw --sql --uri '%s:%s@localhost:3306' -e '%s' | head -2 | tail -1" % \
        #       (admin_user.get('name'), admin_user.get('pwd'), query)

        # --skip-column-names
        cmd = "mysql -e '%s' -B -r -p'%s' | sed 's/\t/,/g'" % (query, admin_user.get('pwd'))
        res = self.compute_instance.run_ad_hoc_command(cmd, parse='text')
        res = res.split('\n')[1:]
        return res

    @staticmethod
    def __remove_warning(s):
        idx = s.find('mysql: [Warning]')
        # warning msg not found
        if idx == -1:
            return s
        # warning msg found
        return s[:idx]

    def get_dbs(self):
        """"""
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        query = 'SELECT * FROM information_schema.schemata;'
        dbs = self.__run_mysql_query(query)

        res = []
        for item in dbs:
            item = self.__remove_warning(item)
            item = item.split(',')
            if item[1] in ['performance_schema', 'information_schema', 'sys', 'mysql']:
                continue
            res.append({
                'db_name': item[1],
                'charset': item[2],
                'collation': item[3],
                'access_privileges': None,
            })
        self.logger.info('get sql stack %s dbs: %s' % (self.stack.oid, res))
        return res

    def add_db(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        db_name = self.kvargs.get('db_name')
        charset = self.kvargs.get('charset')
        if charset is None:
            charset = dict_get(self.engine_params, 'charset')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_add_db_step',
            'args': [self.compute_instance.oid, db_name, charset]
        }]
        self.kvargs['steps'] = steps

    def drop_db(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        db_name = self.kvargs.get('db_name')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_drop_db_step',
            'args': [self.compute_instance.oid, db_name]
        }]
        self.kvargs['steps'] = steps

    def get_users(self):
        """"""
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        query = 'SELECT Host,User,max_connections,plugin,account_locked FROM mysql.user;'
        users = self.__run_mysql_query(query)

        query = 'SELECT * from information_schema.SCHEMA_PRIVILEGES;'
        grants = self.__run_mysql_query(query)
        grants_res = {}
        for item in grants:
            item = item.split(',')
            grant = {'db': item[2], 'privilege': item[3]}
            try:
                grants_res[item[0]].append(grant)
            except:
                grants_res[item[0]] = [grant]

        res = []
        for item in users:
            item = self.__remove_warning(item)
            item = item.split(',')
            res.append({
                'host': item[0],
                'user': item[1],
                'grants': grants_res.get('\'%s\'@\'%s\'' % (item[1], item[0])),
                'max_connections': item[2],
                'plugin': item[3],
                'account_locked': item[4],
            })
        self.logger.info('get sql stack %s dbs: %s' % (self.stack.oid, truncate(res)))
        return res

    def add_user(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        usr_name = self.kvargs.get('name')
        usr_password = self.kvargs.get('password')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_add_user_step',
            'args': [self.compute_instance.oid, usr_name, usr_password]
        }]
        self.kvargs['steps'] = steps

    def drop_user(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        usr_name = self.kvargs.get('name')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_drop_user_step',
            'args': [self.compute_instance.oid, usr_name]
        }]
        self.kvargs['steps'] = steps

    def grant_privs(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        privileges = self.kvargs.get('privileges')
        db_name = self.kvargs.get('db_name')
        usr_name = self.kvargs.get('usr_name')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_grant_privs_step',
            'args': [self.compute_instance.oid, privileges, db_name, usr_name, ]
        }]
        self.kvargs['steps'] = steps

    def revoke_privs(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        privileges = self.kvargs.get('privileges')
        db_name = self.kvargs.get('db_name')
        usr_name = self.kvargs.get('usr_name')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_revoke_privs_step',
            'args': [self.compute_instance.oid, privileges, db_name, usr_name, ]
        }]
        self.kvargs['steps'] = steps

    def change_pwd(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        usr_name = self.kvargs.get('name')
        usr_new_password = self.kvargs.get('new_password')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_change_pwd_step',
            'args': [self.compute_instance.oid, usr_name, usr_new_password]
        }]
        self.kvargs['steps'] = steps

    def install_extensions(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        # get extensions
        extensions = self.kvargs.get('extensions')
        if not isinstance(extensions, list):
            extensions = [extensions]

        # get vpc
        vpcs, total = self.compute_instance.get_linked_resources(link_type='vpc', authorize=False, run_customize=False)
        vpc = vpcs[0]
        vpc.check_active()

        # get site
        site_id = self.compute_instance.get_attribs().get('availability_zone')
        site = self.compute_instance.controller.get_resource(site_id)
        ip_repository = site.get_attribs().get('repo')

        # create task workflow
        steps = [{
            'step': ComputeStackMysqlAction.task_path + 'mysql_install_extensions_step',
            'args': [self.compute_instance.oid, ip_repository, extensions]
        }]
        self.kvargs['steps'] = steps


class PostgresqlActionHelper(SqlActionHelper):
    def __init__(self, *args, **kvargs):
        SqlActionHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = PostgresqlBase.engine_params

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)

    def stop(self, **kwargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is already stopped' % self.compute_instance.uuid)

        force = self.kvargs.get('force', False)

        # create task workflow
        steps = []
        # - stop engine
        if not force:
            steps.append({
                'step': ComputeStackPostgresqlAction.task_path + 'pgsql_manage_engine_step',
                'args': [self.compute_instance.oid]
            })
        # - stop server
        steps.append({
            'step': ComputeStackAction.task_path + 'sql_run_action_on_server_step',
            'args': [self.compute_instance.oid]
        })

        self.kvargs['steps'] = steps

    def start(self, **kvargs):
        if self.compute_instance.is_running() is True:
            raise ApiManagerError('Server %s is already running' % self.compute_instance.uuid)

        # create task workflow
        # - start server
        steps = [{
            'step': ComputeStackAction.task_path + 'sql_run_action_on_server_step',
            'args': [self.compute_instance.oid]
        }]
        # - wait server is up and running
        data = {
            'customization': 'os-utility',
            'playbook': 'wait_ssh_is_up.yml'
        }
        steps.append({
            'step': ComputeStackAction.task_path + 'sql_invoke_apply_customization_step',
            'args': [self.compute_instance.oid, data]
        })
        # - start engine
        steps.append({
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_manage_engine_step',
            'args': [self.compute_instance.oid]
        })
        self.kvargs['steps'] = steps

    def restart(self, **kvargs):
        steps = []
        if self.compute_instance.is_running() is True:
            self.logger.info('Server %s is running, restart database service' % self.compute_instance.uuid)
            # restart engine
            steps.append({
                'step': ComputeStackPostgresqlAction.task_path + 'pgsql_manage_engine_step',
                'args': [self.compute_instance.oid]
            })
            self.kvargs['steps'] = steps
        else:
            self.logger.info('Server %s is stopped, start server and database service' % self.compute_instance.uuid)
            self.start(**kvargs)

    def __run_pgsql_query(self, query, database='postgres'):
        # get db admin credentials
        # admin_user = self.get_db_admin_user()
        #
        # cmd = "mysqlsh --json=raw --sql --uri '%s:%s@localhost:3306' -e '%s' | head -2 | tail -1" % \
        #       (admin_user.get('name'), admin_user.get('pwd'), query)

        # --skip-column-names
        # cmd = "mysql -e '%s' -B -r | sed 's/\t/,/g'" % query
        cmd = "su - postgres -c \"psql -c \\\"%s\\\" -At -R '+++' -F '|' -d '%s'\"" % (query, database)
        self.logger.warn(cmd)
        res = self.compute_instance.run_ad_hoc_command(cmd, parse='text')
        res = res.replace('\n', ',').split('+++')
        return res

    def get_dbs(self):
        """"""
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        query = '\l+'
        # query = 'SELECT * FROM pg_catalog.pg_database;'
        # SELECT * FROM information_schema.schemata;
        dbs = self.__run_pgsql_query(query)
        self.logger.warn(dbs)
        res = []
        for item in dbs:
            item = item.split('|')

            if item[0].find('template') >= 0:
                continue

            # get database schemas
            query = 'SELECT schema_name FROM information_schema.schemata;'
            schemas = self.__run_pgsql_query(query, database=item[0])
            res_schemas = []
            for schema in schemas:
                if schema == 'information_schema' or schema.find('pg_') >= 0:
                    continue
                res_schemas.append(schema)

            res.append({
                'db_name': item[0],
                'charset': item[2],
                'collation': item[3],
                'access_privileges': item[5],
                'size': item[6],
                'schemas': res_schemas
            })
        self.logger.info('get sql stack %s dbs: %s' % (self.stack.oid, res))
        return res

    def add_db(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        db_name = self.kvargs.get('db_name')
        db_name = db_name.split('.')
        schema = '*'
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]
        charset = self.kvargs.get('charset')
        if charset is None:
            charset = dict_get(self.engine_params, 'charset')
        charset = charset.upper()

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_add_db_step',
            'args': [self.compute_instance.oid, db_name, charset, schema]
        }]
        self.kvargs['steps'] = steps

    def drop_db(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        db_name = self.kvargs.get('db_name')
        db_name = db_name.split('.')
        schema = '*'
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_drop_db_step',
            'args': [self.compute_instance.oid, db_name, schema]
        }]
        self.kvargs['steps'] = steps

    def get_users(self):
        """"""
        self.get_compute_instance()
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        query = '\du'
        users = self.__run_pgsql_query(query)

        # query = 'SELECT * from information_schema.SCHEMA_PRIVILEGES;'
        # grants = self.__run_pgsql_query(query)
        # grants_res = {}
        # for item in grants[1:]:
        #     item = item.split('|')
        #     grant = {'db': item[2], 'privilege': item[3]}
        #     try:
        #         grants_res[item[0]].append(grant)
        #     except:
        #         grants_res[item[0]] = [grant]

        # query = "select r.rolname as user, nspname as schema_name, " \
        #         "pg_catalog.has_schema_privilege(r.rolname, nspname, 'CREATE') as create_grant, " \
        #         "pg_catalog.has_schema_privilege(r.rolname, nspname, 'USAGE') as usage_grant from pg_namespace pn," \
        #         "pg_catalog.pg_roles r where array_to_string(nspacl,',') like '%'||r.rolname||'%'  and nspowner > 1;"
        # res_grants = self.__run_pgsql_query(query)
        # self.logger.warn(res_grants)

        res = []
        for item in users:
            item = item.split('|')
            res.append({
                'host': '%',
                'user': item[0],
                'grants': [], # grants_res.get('\'%s\'@\'%s\'' % (item[1], item[0])),
                'max_connections': '',
                'plugin': '',
                'account_locked': '',
            })
        self.logger.info('get sql stack %s dbs: %s' % (self.stack.oid, truncate(res)))
        return res

    def add_user(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        usr_name = self.kvargs.get('name')
        usr_password = self.kvargs.get('password')
        usr_attribs = self.kvargs.get('attribs', '')

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_add_user_step',
            'args': [self.compute_instance.oid, usr_name, usr_password, usr_attribs]
        }]
        self.kvargs['steps'] = steps

    def drop_user(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        usr_name = self.kvargs.get('name')
        force = bool2str(self.kvargs.get('force', False))

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_drop_user_step',
            'args': [self.compute_instance.oid, usr_name, force]
        }]
        self.kvargs['steps'] = steps

    def grant_privs(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        privileges = self.kvargs.get('privileges')
        usr_name = self.kvargs.get('usr_name')
        db_name = self.kvargs.get('db_name')
        db_name = db_name.split('.')
        schema = '*'
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_manage_privs_step',
            'args': [self.compute_instance.oid, privileges, db_name, schema, usr_name]
        }]
        self.kvargs['steps'] = steps

    def revoke_privs(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        privileges = self.kvargs.get('privileges')
        db_name = self.kvargs.get('db_name')
        usr_name = self.kvargs.get('usr_name')
        db_name = db_name.split('.')
        schema = '*'
        if len(db_name) > 1:
            schema = db_name[1]
        db_name = db_name[0]

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_manage_privs_step',
            'args': [self.compute_instance.oid, privileges, db_name, schema, usr_name]
        }]
        self.kvargs['steps'] = steps

    def change_pwd(self, **kvargs):
        if self.compute_instance.is_running() is False:
            raise ApiManagerError('Server %s is stopped' % self.compute_instance.uuid)

        # TODO: check engine status

        usr_name = self.kvargs.get('name')
        usr_new_password = self.kvargs.get('new_password')

        # create task workflow
        steps = [{
            'step': ComputeStackPostgresqlAction.task_path + 'pgsql_change_user_pwd_step',
            'args': [self.compute_instance.oid, usr_name, usr_new_password]
        }]
        self.kvargs['steps'] = steps


class OracleActionHelper(SqlActionHelper):
    def __init__(self, *args, **kvargs):
        SqlActionHelper.__init__(self, *args, **kvargs)
        # set default engine params
        self.engine_params = OracleBase.engine_params

    def internal_run(self):
        check = getattr(self, self.operation)
        if check is not None:
            check(**self.kvargs)


class SqlserverActionHelper(SqlActionHelper):
    pass


class SqlComputeStackV2(ComputeStackV2):
    """Sql compute stack
    """
    objuri = '%s/sql_stacks/%s'
    objname = 'sql_stack'
    task_path = 'beehive_resource.plugins.provider.task_v2.stack_v2.StackV2Task.'

    def __init__(self, *args, **kvargs):
        ComputeStackV2.__init__(self, *args, **kvargs)

        self.compute_instance = None

        self.actions = [
            'start',
            'stop',
            'restart',
            'get_dbs',
            'add_db',
            'drop_db',
            'get_users',
            'add_user',
            'drop_user',
            'grant_privs',
            'revoke_privs',
            'change_pwd',
            'add_security_group',
            'del_security_group',
            'set_flavor',
            'install_extensions',
            'enable_monitoring',
            'disable_monitoring',
            'enable_logging',
            'enable_mailx',
            'haproxy_register',
            'haproxy_deregister',
            'resize',
        ]

    def is_monitoring_enabled(self, cache=True, ttl=1800):
        res = False
        if self.compute_instance is not None:
            res = self.compute_instance.is_monitoring_enabled(cache=cache, ttl=ttl)
        return res

    def is_logging_enabled(self):
        res = False
        if self.compute_instance is not None:
            res = self.compute_instance.is_logging_enabled()
        return res

    def get_allocated_storage(self):
        if self.compute_instance is not None:
            res = sum([b.get_size() for b in self.compute_instance.get_volumes()])
        else:
            res = self.get_attribs(key='allocated_storage')
        return res

    def __get_services(self, info):
        dict_set(info, 'attributes.backup_enabled', False)
        dict_set(info, 'attributes.monitoring_enabled', str2bool(self.is_monitoring_enabled()))
        dict_set(info, 'attributes.logging_enabled', str2bool(self.is_logging_enabled()))
        return info

    def info(self):
        """Get infos.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        # verify permissions
        info = ComputeStackV2.info(self)
        info['flavor'] = None
        info['vpc'] = None
        info['security_groups'] = []
        info['allocated_storage'] = 0
        info = self.__get_services(info)

        if self.compute_instance is not None:
            info['availability_zone'] = self.compute_instance.get_main_availability_zone().small_info()

        objdefs = [ComputeFlavor.objdef, SecurityGroup.objdef, Vpc.objdef]
        if self.compute_instance is not None:
            info['allocated_storage'] = sum([b.get_size() for b in self.compute_instance.get_volumes()])

            linked = self.controller.get_directed_linked_resources_internal(
                resources=[self.compute_instance.oid], objdefs=objdefs, run_customize=False)

            for resource, entities in linked.items():
                for entity in entities:
                    if isinstance(entity, ComputeFlavor):
                        info['flavor'] = entity.small_info()
                    elif isinstance(entity, SecurityGroup):
                        info['security_groups'].append(entity.small_info())
                    elif isinstance(entity, Vpc):
                        info['vpc'] = entity.small_info()

        info['listener'] = {
            'address': self.get_outputs('ResourceIP.value'),
            'port': self.get_attribs('port')
        }

        return info

    def detail(self):
        """Get details.

        :return: dict like :class:`Resource`
        :raise ApiManagerError:
        """
        info = self.info()
        return info

    @staticmethod
    def get_engines():
        return SqlHelper().engines

    def get_child_resources(self, uuid=None):
        """Get child resources

        :param uuid: action resource uuid
        :return: resources list
        :raise ApiManagerError:
        """
        resources = super().get_child_resources(uuid=uuid)
        for resource in resources:
            if isinstance(resource, ComputeInstance):
                self.compute_instance = resource
        return resources

    def get_compute_instance(self):
        """Get sql stack compute instance"""
        # get compute instance linked to stack
        resources = self.controller.get_directed_linked_resources_internal(resources=[self.oid],
                                                                           link_type='resource%',
                                                                           objdef=ComputeInstance.objdef)
        compute_instance = resources.get(self.oid)
        if compute_instance is not None and len(compute_instance) > 0:
            compute_instance = compute_instance[0]
        else:
            compute_instance = None
        self.logger.debug('get sql stack %s compute instance: %s' % (self.oid, compute_instance))
        return compute_instance

    def get_runstate(self, cache=True, ttl=1800):
        """Get resource running state if exist.

        :param cache: if True get data from cache
        :param ttl: cache time to live [default=1800]
        :return: None if runstate does not exist
        """
        res = None
        ci = self.get_compute_instance()
        if ci is not None:
            res = ci.get_runstate(cache=cache, ttl=ttl)
        return res

    def get_credentials(self):
        """Get database credentials"""
        self.verify_permisssions('use')

        res = []
        users = self.get_attribs('users')
        # new user registration
        if users.get('administrator', None) is not None:
            for k, v in users.items():
                res.append(({'type': k,
                             'name': v.get('username'),
                             'password': self.controller.decrypt_data(v.get('password'))}))
        # old user registration
        else:
            for k, v in users.items():
                res.append(({'type': None, 'name': k, 'password': self.controller.decrypt_data(v)}))
        return res

    def set_credential(self, user, password):
        """Set database credential

        :param user: user name. In new style use administrator
        :param password: user password
        :return: True
        """
        self.verify_permisssions('update')

        password = self.controller.encrypt_data(password)

        users = self.get_attribs('users')
        # new user registration
        if users.get('administrator', None) is not None:
            self.set_configs(key='users.%s.password' % user, value=password)
        # old user registration
        else:
            self.set_configs(key='users.%s' % user, value=password)

        return True

    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        entities = ComputeStackV2.customize_list(controller, entities, *args, **kvargs)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :raise ApiManagerError:
        """
        get_resources = self.controller.get_directed_linked_resources_internal

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.orchestrator_tag: orchestrators tag
        :param kvargs.compute_zone: parent compute zone id or uuid
        :param kvargs.availability_zone: id, uuid or name of the site where create the database
        :param kvargs.multi_avz: if True deploy instance over all the active availability zones
        :param kvargs.host_group: Define the optional host group where put the instance [optional]
        :param kvargs.flavor: id, uuid or name of the flavor
        :param kvargs.image: id, uuid or name of the image
        :param kvargs.hypervisor: type of hypervisor
        :param kvargs.customization: customization used to install db
        :param kvargs.vpc: id, uuid or name of the vpc
        :param kvargs.subnet: subnet reference
        :param kvargs.security_group: id, uuid or name of the security group
        :param kvargs.hostname: hostname
        :param kvargs.key_name: public key name
        :param kvargs.volumeflavor: volume flavor to use in compute instance
        :param kvargs.db_root_name: The database admin account username
        :param kvargs.db_root_password: The database admin password
        :param kvargs.db_name: First app database name
        :param kvargs.db_appuser_name: First app user name
        :param kvargs.db_appuser_password: First app user password
        :param kvargs.engine: Database engine
        :param kvargs.version: Database engine version
        :param kvargs.port: database instance port [optional]
        :param kvargs.root_disk_size: root disk size [default=40GB]
        :param kvargs.data_disk_size: data disk size [default=30GB]
        :param kvargs.charset: database charset [default=latin1]
        :param kvargs.timezone: database timezone [default=Europe/Rome]
        :param kvargs.replica: enable database replica [default=False]
        :param kvargs.mysql: dictionary with mysql specific configuration params [optional]
        :param kvargs.postgresql: dictionary with postgres specific configuration params [optional]
        :param kvargs.postgresql.geo_extension: if True enable geographic extension [default=False]
        :param kvargs.oracle: dictionary with oracle specific configuration params [optional]
        :param kvargs.sqlserver: dictionary with sqlserver specific configuration params [optional]
        :param kvargs.csi_custom: flag to enable post-installation CSI setup [optional]
        :return: dict
        :raise ApiManagerError:
        """
        helper_class = SqlCreateHelper(controller, container, *args, **kvargs)\
            .get_helper_by_engine(kvargs.get('engine'))
        helper = helper_class(controller, container, *args, **kvargs)

        kvargs = helper.run()

        return kvargs

    @staticmethod
    def pre_import(controller, container, *args, **kvargs):
        """Check input params before resource import. This function is used in container resource_import_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.physical_id: physical resource id [default=None]
        :param kvargs.configs: custom configurations
        :param kvargs.configs.charset: db charset [default=latin1]
        :param kvargs.configs.timezone: db timezone [default=Europe/Rome]
        :param kvargs.configs.engine: db engine
        :param kvargs.configs.version: db engine version
        :param kvargs.configs.pwd: db passwords
        :param kvargs.configs.pwd.admin: db admin password
        :return: kvargs
        :raise ApiManagerError:
        """
        engine = dict_get(kvargs, 'configs.engine')
        helper_class = SqlImportHelper(controller, container, *args, **kvargs).get_helper_by_engine(engine)
        helper = helper_class(controller, container, *args, **kvargs)
        kvargs = helper.run()
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.
        Following updates are handled:
        - from standalone DB instance to master replica DB instance
        - from standalone DB instance to slave replica DB instance
        - from master replica DB instance to standalone DB instance
        - from slave replica DB instance to standalone DB instance

        :param args: custom params
        :param dict kvargs: custom params
        :return: dict
        :raise ApiManagerError:
        """
        engine = self.get_attribs(key='engine')
        helper_class = SqlUpdateHelper(self).get_helper_by_engine(engine)
        helper = helper_class(self, *args, **kvargs)
        kvargs = helper.run()
        return kvargs

    def action(self, action, *args, **kvargs):
        """Execute an action

        :param action: action name
        :param args: custom params
        :param dict kvargs: custom params
        :return: dict
        :raise ApiManagerError:
        """
        engine = self.get_attribs(key='engine')
        helper_class = SqlActionHelper(self, action).get_helper_by_engine(engine)
        helper = helper_class(self, action, *args, **kvargs)
        kvargs = helper.run()
        return kvargs

    def get_schemas(self):
        engine = self.get_attribs(key='engine')
        helper_class = SqlActionHelper(self, None).get_helper_by_engine(engine)
        helper = helper_class(self, None)
        dbs = helper.get_dbs()
        return dbs

    def get_users(self):
        engine = self.get_attribs(key='engine')
        helper_class = SqlActionHelper(self, None).get_helper_by_engine(engine)
        helper = helper_class(self, None)
        dbs = helper.get_users()
        return dbs
