# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from datetime import datetime, timedelta
from beecell.simple import truncate
from beedrones.trilio.client import TrilioManager
from beehive_resource.container import Orchestrator
from beehive.common.data import trace
from beehive_resource.model import Resource as ModelResource
from beedrones.openstack.client import OpenstackError, OpenstackManager
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain
from beehive_resource.plugins.openstack.entity.ops_flavor import OpenstackFlavor
from beehive_resource.plugins.openstack.entity.ops_image import OpenstackImage
from beehive_resource.plugins.openstack.entity.ops_heat import OpenstackHeat, OpenstackHeatStack
from beehive_resource.plugins.openstack.entity.ops_keystone import OpenstackKeystone
from beehive_resource.plugins.openstack.entity.ops_system import OpenstackSystem
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.plugins.openstack.entity.ops_security_group import OpenstackSecurityGroup
from beehive_resource.plugins.openstack.entity.ops_volume_type import OpenstackVolumeType
from threading import RLock


def get_task(task_name):
    return '%s.task.%s' % (__name__, task_name)


class OpenstackContainer(Orchestrator):
    """Openstack orchestrator
    
    **connection syntax**:
    
        {
            "api":{
                "user":"admin",
                "project":"admin",
                "domain":"default",
                "uri":"http://10.102.184.200:5000/v3",
                "timeout":5,
                "pwd":"...",
                "region":"regionOne"
            }
        }    
    """    
    objdef = 'Openstack'
    objdesc = 'Openstack container'
    version = 'v1.0'
    
    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            OpenstackKeystone,
            OpenstackSystem,
            OpenstackDomain,
            OpenstackHeat,
            OpenstackFlavor,
            OpenstackImage,
            OpenstackVolumeType
        ]
        
        self.default_region = None
        
        self.keystone = OpenstackKeystone(*args, **kvargs)
        self.keystone.container = self
        self.system = OpenstackSystem(*args, **kvargs)
        self.system.container = self
        
        # hash of tokens indexed by project_name
        self.tokens = {}
        # openstack catalog indexed by project_name
        self.catalogs = {}
        
        # set to use a specific project during connection
        # active_container.group = None
        self.conn = None

        self.lock = RLock()

        self.logger.debug('+++++ OpenstackContainer __init__ ')

    def ping(self):
        """Ping orchestrator.
        
        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            project_name = self.__get_connection_project(None)
            self.__new_connection(project=project_name, timeout=5)
            res = True
        except:
            res = False
        self.container_ping = res
        return res

    @staticmethod
    def pre_create(controller=None, type=None, name=None, desc=None, active=None, conn=None, **kvargs):
        """Check input params
        
        :param controller: resource controller instance
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param active: container active
        :param conn: container connection
            
                {
                    "api":{
                        "user":"admin",
                        "project":"admin",
                        "domain":"default",
                        "uri":"http://10.102.184.200:5000/v3",
                        "timeout":5,
                        "pwd":"...",
                        "region":"regionOne"
                    }
                }
            
        :return: kvargs            
        :raise ApiManagerError:
        """
        # encrypt password
        conn['api']['pwd'] = controller.encrypt_data(conn['api']['pwd'])

        kvargs = {
            'type': type,
            'name': name,
            'desc': desc,
            'active': active,
            'conn': conn,
        }
        return kvargs
    
    def pre_change(self, **kvargs):
        """Check input params
        
        :param kvargs: custom params            
        :return: kvargs            
        :raise ApiManagerError:
        """
        return kvargs
    
    def pre_clean(self, **kvargs):
        """Check input params
        
        :param kvargs: custom params            
        :return: kvargs            
        :raise ApiManagerError:
        """
        return kvargs 

    def info(self):
        """Get cotainer info.
        
        :return: Dictionary with system capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        res = Orchestrator.info(self)
        
        return res
    
    def detail(self):
        """Get container detail.
        
        :return: Dictionary with system capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Orchestrator.info(self)

        # get openstack services
        info['services'] = []
        for service in self.conn.identity.catalog.values():
            region = None
            url = None
            for item in service['endpoints']:
                if item['interface'] == 'public':
                    region = item['region']
                    url = item['url']
                    
            data = {'type': service['type'],
                    'name': service['name'],
                    'id': service['id'],
                    'region': region,
                    'url': url}
            info['services'].append(data)
        
        return info
    
    def __get_connection_project(self, projectid):
        """Get openstack connection params
        """
        # get connection for project different by default
        project_name = self.conn_params['api']['project']   # admin
        self.logger.debug('+++++ project_name: %s, projectid: %s' % (project_name, projectid))

        if projectid is not None:
            try:
                project = self.manager.get_entity(ModelResource, projectid)
            except:
                raise ApiManagerError('Openstack project %s not found' % projectid, code=404)

            project_name = project.name
        
        self.logger.debug('+++++ Use project %s for connection' % project_name)
        return project_name
    
    def __new_connection(self, project, timeout=None):
        """Get openstack connection with new token
        """
        try:
            # per evitare che in tokens ci siano token relativi a project sbagliati
            with self.lock:
                self.logger.debug('+++++ Create openstack connection for project %s' % (project))

                conn_params = self.conn_params['api']
                uri = conn_params['uri']
                region = conn_params['region']
                user = conn_params['user']
                pwd = conn_params['pwd']
                domain = conn_params['domain']
                if timeout is None:
                    timeout = conn_params['timeout']

                # decrypt password
                pwd = self.decrypt_data(pwd)

                self.default_region = region
                
                openstackManager = OpenstackManager(uri=uri, default_region=region, timeout=timeout)
                openstackManager.authorize(user=user, pwd=pwd, project=project, domain=domain)
                token = openstackManager.get_token()
                
                self.tokens[project] = token
                self.catalogs[project] = openstackManager.get_catalog()
                self.logger.debug('+++++ Create openstack connection %s for project %s with token: %s' % (openstackManager, project, token))

                self.conn = openstackManager
                return openstackManager

        except OpenstackError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)
    
    def __get_connection(self, token, project):
        """Get openstack connection with existing token
        """
        try:
            conn_params = self.conn_params['api']
            uri = conn_params['uri']
            region = conn_params['region']
            timeout = conn_params['timeout']

            self.default_region = region

            openstackManager = OpenstackManager(uri=uri, default_region=region, timeout=timeout)
            openstackManager.authorize(token=token, catalog=self.catalogs[project])
            self.logger.debug2('Get openstack connection %s with token: %s' % (openstackManager, token))

            self.conn = openstackManager
            return openstackManager
        except OpenstackError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

    def get_connection(self, projectid=None):
        """Get openstack connection

        :param projectid: id of the project to use during connection
        """
        # select project for connection
        project_name = self.__get_connection_project(projectid)

        # get token for selected project
        # if local_token is not None:
        #     token = local_token
        #     self.logger.debug('Use connection token: %s' % token)
        # else:
        #     token = self.tokens.get(project_name, None)
        #     self.logger.debug('Use connection token: %s' % token)

        self.logger.debug('+++++ Use connection token - project_name: %s' % project_name)
        token = self.tokens.get(project_name, None)
        self.logger.debug('+++++ Use connection token: %s' % token)

        # create new token
        if token is None or token.get('token', None) is None:
            # self.logger.info('Active token for project %s is null' % project_name)
            openstackManager = self.__new_connection(project=project_name)
        else:
            # check token
            # validate = self.conn.validate_token(token['token'])
            
            # check token expire
            expires_at = token.get('expires_at', '1970-01-01T00:00:00.000000Z')
            a = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M:%S.%fZ')
            b = datetime.utcnow() + timedelta(minutes=30)
            self.logger.info('+++++ get_connection - a: %s' % a.strftime('%Y-%m-%d %H:%M:%S'))
            self.logger.info('+++++ get_connection - b: %s' % b.strftime('%Y-%m-%d %H:%M:%S'))

            validate = (a >= b)
            self.logger.info('+++++ get_connection - validate: %s' % validate)
            # self.logger.warn(a)
            # self.logger.warn(b)
            # self.logger.warn(validate)
            if validate is True:
                self.logger.info('+++++ Token %s is valid' % token)
                openstackManager = self.__get_connection(token, project_name)
            else:
                self.logger.info('+++++ Token %s was expired' % token)
                openstackManager = self.__new_connection(project_name)

        Orchestrator.get_connection(self)

        # return token
        return openstackManager

    def close_connection(self):
        """Close openstack connection
        """
        if self.conn is not None:
            try:
                self.conn.identity.release_token()
                self.conn = None
                self.logger.debug('Close openstack connection: %s' % self.conn)
            except OpenstackError as ex:
                self.logger.error(ex, exc_info=True)
                raise ApiManagerError(ex, code=400)

    def get_trilio_connection(self, openstackManager=None):
        """Get trilio connection

        :param projectid: id of the project to use during connection
        :return: TrilioManager instance
        """
        if openstackManager is None:
            client = TrilioManager(self.conn)
        else:
            client = TrilioManager(openstackManager)
        return client

    #
    # system
    #
    def get_heat_resource(self):
        """Get heat resource
        """
        res = self.get_resource_by_extid('heat-01')
        self.logger.debug('Get heat resource for openstack %s' % self.oid)
        return res

    @trace(op='view')
    def get_manila_share_type(self, name):
        """Get manila share type

        :return: share type
        :raise ApiManagerError:
        """
        res = self.conn.manila.share_type.list(desc=name)
        self.logger.debug('Get openstack manila share type list: %s' % truncate(res))

        if len(res) == 0 or len(res) > 1:
            raise ApiManagerError('no share type %s found' % name)
        res = res[0]
        return res

    @trace(op='view')
    def get_manila_share_type_list(self):
        """Get manila share type list

        :return: share type list
        :raise ApiManagerError:
        """
        self.verify_permisssions('view')

        res = self.conn.manila.share_type.list()
        for item in res:
            item.pop('share_type_access:is_public')

        self.logger.debug('Get openstack manila share type list: %s' % truncate(res))
        return res

    @trace(op='view')
    def get_manila_share_networks(self):
        """Get manila share networks

        :return: share networks list
        :raise ApiManagerError:
        """
        self.verify_permisssions('view')

        res = self.conn.manila.network.list(details=True)
        self.logger.debug('Get openstack manila share networks list: %s' % truncate(res))
        return res

    @trace(op='use')
    def add_manila_share_network(self, **kvargs):
        """Add manila share network

        :param kvargs: share network creation params
        :return: share networks list
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        res = self.conn.manila.network.create(**kvargs)
        self.logger.debug('Add openstack manila share network: %s' % truncate(res))
        return res['id']

    @trace(op='use')
    def delete_manila_share_network(self, network_id):
        """Add manila share network

        :param network_id: share network id
        :return: share networks list
        :raise ApiManagerError:
        """
        self.verify_permisssions('use')

        res = self.conn.manila.network.delete(network_id)
        self.logger.debug('Remove openstack manila share network %s: %s' % (network_id, truncate(res)))
        return res['id']

    @trace(op='view')
    def get_manila_share_type_prefix(self):
        """Get manila share type prefix

        :return: share type list
        :raise ApiManagerError:
        """
        self.verify_permisssions('view')

        res = self.conn.manila.share_type.list()
        prefix = None
        if len(res) > 0:
            prefix = res[0]['name'].split('-')[0]

        self.logger.debug('Get openstack manila share type prefix: %s' % prefix)
        return prefix

    @trace(op='view')
    def get_system_tree(self):
        """Get system tree.
        
        :return: dict [{'id':.., 'name':.., 'type':.., 'size':.., 'uri':.., 'children':..}]
        :rtype: dict
        :raises ApiManagerError: if query empty return error.
        """
        # get resources
        resources = self.get_resources()
        res_index = {}

        try:
            def set_item(oid, name, otype, uri, level):
                obj = {'id': oid,
                       'name': name,
                       'type': otype,
                       'size': 0,
                       'uri': uri,
                       'children': [],
                       'level': level}
                res_index[oid] = obj
            
            def set_child(parentid, oid):
                obj = res_index[oid]
                res_index[parentid]['children'].append(obj)
                res_index[parentid]['size'] += 1
            
            obj = set_item(1, 'Images', 'OpenstackFolder', None, 0)
            obj = set_item(2, 'Flavors', 'OpenstackFolder', None, 0)
            obj = set_item(3, 'Others', 'OpenstackFolder', None, 0)
            
            # add item to index
            for r in resources:
                if isinstance(r, OpenstackDomain) or isinstance(r, OpenstackHeat):
                    obj = set_item(r.oid, r.name, r.__class__.__name__, r.objuri, 0)
                else:
                    obj = set_item(r.oid, r.name, r.__class__.__name__, r.objuri, 1)

            # add item to parent
            for r in resources:
                self.logger.debug('Add item %s to tree' % r.oid)
                if isinstance(r, OpenstackImage):
                    set_child(1, r.oid)
                elif isinstance(r, OpenstackFlavor):
                    set_child(2, r.oid)
                elif isinstance(r, OpenstackProject):
                    set_child(int(r.parent_id), r.oid)
                    # create sub type children
                    set_item('%s-servers' % r.oid, 'Servers', 'OpenstackServer', None, 1)
                    set_child(int(r.oid), '%s-servers' % r.oid)
                    set_item('%s-volumes' % r.oid, 'Volumes', 'OpenstackVolume', None, 1)
                    set_child(int(r.oid), '%s-volumes' % r.oid)
                    set_item('%s-networks' % r.oid, 'Networks', 'OpenstackNetwork', None, 1)
                    set_child(int(r.oid), '%s-networks' % r.oid)
                    set_item('%s-routers' % r.oid, 'Routers', 'OpenstackRouter', None, 1)
                    set_child(int(r.oid), '%s-routers' % r.oid)
                    set_item('%s-sgs' % r.oid, 'SecurityGroups', 'OpenstackSecurityGroup', None, 1)
                    set_child(int(r.oid), '%s-sgs' % r.oid)
                    set_item('%s-stacks' % r.oid, 'Stacks', 'OpenstackHeatStack', None, 1)
                    set_child(int(r.oid), '%s-stacks' % r.oid)
                elif isinstance(r, OpenstackDomain):
                    pass
                elif r.parent_id is None or r.parent_id == '':
                    set_child(3, r.oid)
                elif isinstance(r, OpenstackServer):
                    set_child('%s-servers' % r.parent_id, r.oid)
                elif isinstance(r, OpenstackVolume):
                    set_child('%s-volumes' % r.parent_id, r.oid)
                elif isinstance(r, OpenstackNetwork):
                    set_child('%s-networks' % r.parent_id, r.oid)
                elif isinstance(r, OpenstackRouter):
                    set_child('%s-routers' % r.parent_id, r.oid)
                elif isinstance(r, OpenstackSecurityGroup):
                    set_child('%s-sgs' % r.parent_id, r.oid)
                elif isinstance(r, OpenstackHeatStack):
                    set_child('%s-stacks' % r.parent_id, r.oid)

            objs = [i for i in res_index.values() if i['level'] == 0]
            res = [{'id': 0,
                    'name': self.default_region,
                    'type': 'OpenstackRegion',
                    'size': len(objs),
                    'uri': None,
                    'children': objs}]
            self.logger.debug('Get openstack tree: %s' % truncate(res))
            self.event('Openstack.system.tree.view', {}, (True))
            return res
        except Exception as ex:
            self.event('Openstack.system.tree.view', {}, (False, ex))
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)
