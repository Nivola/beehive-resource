# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from random import randint
from beecell.simple import truncate
from beehive_resource.container import Orchestrator
from beehive.common.data import trace
from beedrones.vsphere.client import VsphereError, VsphereManager
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity.vs_datacenter import VsphereDatacenter
from beehive_resource.plugins.vsphere.entity.nsx_manager import NsxManager
from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfw
from beehive_resource.plugins.vsphere.entity.nsx_edge import NsxEdge
from gevent.hub import sleep
from beehive.common.task.handler import task_local
from beehive_resource.plugins.vsphere.entity.vs_orchestrator import VsphereOrchestrator


def get_task(task_name):
    return '%s.task.%s' % (__name__, task_name)


class VsphereContainer(Orchestrator):
    """Vsphere orchestrator
    
    **connection syntax**:
    
        {
            'vcenter':{
                'host':'hostname',
                'usr':'user',
                'pwd':'xxxx',
                'port':'443',
                'timeout':5,
                'verified':False
            },
            'nsx':{
                'host':'', 
                'port':443, 
                'user':'', 
                'pwd':'', 
                'verified':False, 
                'timeout':5
            }
        }    
    """    
    objdef = 'Vsphere'
    objdesc = 'Vsphere container'
    version = 'v1.0'
    
    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            VsphereDatacenter,
            NsxManager,
            VsphereOrchestrator,
        ]     
        
        self.nsx_enabled = True
        self.conn = None

    def get_resource_classes(self):
        ref_child_classes = [VsphereDatacenter]
        if self.nsx_enabled is True:
            ref_child_classes.append(NsxManager)
        child_classes = [item.objdef for item in ref_child_classes]
        for item in ref_child_classes:
            child_classes.extend(item(self.controller).get_resource_classes())
        return child_classes    

    def ping(self):
        """Ping orchestrator.
        
        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self._get_connection(timeout=1)
            res = self.conn.ping()
        except:
            res = False
        self.container_ping = res
        return res

    @staticmethod
    def pre_create(controller=None, type=None, name=None, desc=None, active=None, 
                   conn=None, **kvargs):
        """Check input params
        
        :param controller: resource controller instance
            * **type** (:py:class:`str`): container type
            * **name** (:py:class:`str`): container name
            * **desc** (:py:class:`str`): container desc
            * **active** (:py:class:`str`): container active
            * **conn: container connection
            
                {
                    'vcenter':{
                        'host':'hostname',
                        'usr':'user',
                        'pwd':'xxxx',
                        'port':'443',
                        'timeout':5,
                        'verified':False
                    },
                    'nsx':{
                        'host':'', 
                        'port':443, 
                        'user':'', 
                        'pwd':'', 
                        'verified':False, 
                        'timeout':5
                    }
                }
            
        :return: kvargs
            
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # encrypt password
        conn['vcenter']['pwd'] = controller.encrypt_data(conn['vcenter']['pwd'])
        if 'nsx' in conn.keys():
            conn['nsx']['pwd'] = controller.encrypt_data(conn['nsx']['pwd'])

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
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs
    
    def pre_clean(self, **kvargs):
        """Check input params
        
        :param kvargs: custom params
        :return: kvargs            
        :raises ApiManagerError: raise :class:`.ApiManagerError`
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
        """Get container datail.
        
        :return: Dictionary with system capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Orchestrator.info(self)
        
        # get datacenter info
        # content = self.conn.si.RetrieveContent()
        # children = content.rootFolder.childEntity
        # datacenter = content.rootFolder.childEntity[0]
        
        # info['datcenter'] = {'name':datacenter.name}
        res = info
        res['details'] = {
            'nsx': {
                'enabled': self.nsx_enabled
            }
        }
        
        return res
    
    def query_remote_task(self, task, step_id, vsphere_task, waitfor=True, error=None, delta=2):
        """Query vsphere task.
        
        :param task: celery task
        :param vsphere_task: vsphere task
        :param waitfor: if True wait for task finish
        :param delta: delta wait time [default=2]
        :return: vsphere entity instance
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            def wait():
                # update task
                task.progress(step_id, msg='Query remote task %s' % vsphere_task)
                
                # sleep a litte
                sleep(delta)

            if waitfor is False:
                wait = None

            res = self.conn.query_task(vsphere_task, wait)
            return res
        except VsphereError as ex:
            if error is None:
                error = ex.value
            self.logger.error(ex.value, exc_info=True)
            raise ApiManagerError(error, code=400)
        except Exception as ex:
            if error is None:
                error = ex.value
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(error, code=400)

    def _get_connection(self, timeout=None):
        """ """
        if self.connection is not None:
            try:
                # decrypt password
                self.conn_params['vcenter']['pwd'] = self.decrypt_data(self.conn_params['vcenter']['pwd'])

                vcenter = self.conn_params['vcenter']
                nsx = None
                if 'nsx' in self.conn_params:
                    nsx = self.conn_params['nsx']
                    self.nsx_enabled = True

                    # decrypt password
                    self.conn_params['nsx']['pwd'] = self.decrypt_data(self.conn_params['nsx']['pwd'])

                if timeout is not None:
                    vcenter['timeout'] = timeout
                    nsx['timeout'] = timeout

                # get vcenter and nsx manager connection
                self.conn = VsphereManager(vcenter, nsx)
            except VsphereError as ex:
                self.logger.error(ex, exc_info=True)
                raise ApiManagerError(ex.value, code=400)
            except Exception as ex:
                self.logger.error(ex, exc_info=True)
                raise ApiManagerError(ex, code=400)
        else:
            raise ApiManagerError('Connection is not specified', code=400)
    
    def get_connection(self):
        """ """
        if self.conn is None:
            self._get_connection()

        if self.conn.get_vcenter_session() is None:
            self.logger.warn('Lost vcenter %s connection. Try to reconnect' % self.oid)
            self._get_connection()
        Orchestrator.get_connection(self)
    
    def close_connection(self):
        """ """
        if self.conn is None:
            try:
                self.conn.disconnect()              
            except VsphereError as ex:
                raise ApiManagerError(ex.value, code=5100)

    def _get_morid(self, obj):
        """Get vsphere item morId 
        
        :param obj: vsphere entity
        :return: morId or None if id can not be retrieved
        """
        try:                
            res = obj['obj']._moId
        except:
            try:
                res = obj._moId
            except:
                res = None
                
        return res

    #
    # custom get, list
    #
    @trace(op='nsx_manager.view')
    def get_nsx_manager(self):
        """Get nsx manager reference

        :return: nsx manager instance
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res, total = self.get_resources(type=NsxManager.objdef, objdef=NsxManager.objdef)
        if total == 0:
            raise ApiManagerError('Nsx manager is not available for orchestrator %s' % self.uuid, code=404)
        return res[0]    
    
    @trace(op='nsx_dfw.view')
    def get_nsx_dfw(self):
        """Get nsx dfw reference

        :return: nsx dfw instance
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res, total = self.get_resources(type=NsxDfw.objdef, objdef=NsxDfw.objdef)
        if total == 0:
            raise ApiManagerError('Nsx dfw is not available for orchestrator %s' % self.uuid, code=404)
        return res[0]

    @trace(op='nsx_edge.view')
    def get_nsx_edges(self, **kvargs):
        """Get nsx edge references

        :param kvargs.resourcetags: list of tags the nsx edges have attached
        :return: list of nsx edge instance
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        edges, total = self.get_resources(type=NsxEdge.objdef, objdef=NsxEdge.objdef, **kvargs)
        if total == 0:
            raise ApiManagerError('No nsx edges are available for orchestrator %s' % self.uuid, code=404)
        return edges

    def get_orchestrator_resource(self):
        """Get orchestrator resource
        """
        res = self.get_resource_by_extid('orchestrator-01')
        self.logger.debug('Get orchestrator resource for vsphere %s' % self.oid)
        return res

    #
    # system
    #
    def _print_system_tree_item(self, obj, objdef, parent, res_index):
        name = obj.name.split('(')[0].rstrip()
        extid = obj._moId
        try: oid = res_index[extid].oid
        except: oid = randint(10000, 20000)
        res = {'id': oid,
               'extid': extid,
               'name': name,
               'type': objdef,
               'size': 1,
               'uri': None,
               'children': []}
        parent['children'].append(res)
        parent['size'] += 1
        
        return res
    
    def _get_system_tree_child(self, obj, parent, res_index):
        """ """
        obj_type = type(obj).__name__
    
        # Resource
        if obj_type == 'vim.ClusterComputeResource':
            parent = self._print_system_tree_item(obj, 'VsphereCluster', parent, res_index)

            # get cluster hosts
            for item in obj.host:
                self._get_system_tree_child(item, parent, res_index)
                
            # get cluster resource pools
            self._get_system_tree_child(obj.resourcePool, parent, res_index)
            
        elif obj_type == 'vim.HostSystem':
            self._print_system_tree_item(obj, 'VsphereHost', parent, res_index)
        elif obj_type == 'vim.ResourcePool':
            if len(obj.resourcePool) > 0:      
                for item in obj.resourcePool:
                    self._get_system_tree_child(item, parent, res_index)
            else:
                self._print_system_tree_item(obj, 'VsphereResourcepool', parent, res_index)
        
        # Virtual Machine
        elif obj_type == 'vim.VirtualMachine':
            self._print_system_tree_item(obj, 'VsphereServer', parent, res_index)
        
        # Folder
        elif obj_type == 'vim.Folder':
            parent = self._print_system_tree_item(obj, 'VsphereFolder', parent, res_index)
            
            if hasattr(obj, 'childEntity'):
                for c in obj.childEntity:
                    self._get_system_tree_child(c, parent, res_index)            
        
        # Network
        elif obj_type == 'vim.Network':
            self._print_system_tree_item(obj, 'VsphereNetwork', parent, res_index)
        elif obj_type == 'vim.dvs.VmwareDistributedVirtualSwitch':
            parent = self._print_system_tree_item(obj, 'VsphereDvs', parent, res_index)
            for portgroup in obj.portgroup:
                self._print_system_tree_item(portgroup, 'VsphereDvp', parent, res_index)
            
        # Datastore
        elif obj_type == 'vim.Datastore':
            self._print_system_tree_item(obj, 'VsphereDatastore', parent, res_index)
    
    def _print_item(self, oid, extid, name, otype, uri='', size=0):
        """
        """
        res = {'id': oid,
               'extid': extid,
               'name': name,
               'type': otype,
               'size': size,
               'uri': uri,
               'children': []}
        return res
    
    def _get_nsx_tree_child(self):
        """Get nsx tree

        :return: None
        """
        manager = self.get_nsx_managers()[0]
        obj = self._print_item(manager.oid, manager.ext_id, 'Nsx Manager', 'NsxManager', manager.objuri, size=0)
        
        # get security groups
        items = manager.get_security_groups()
        folder = self._print_item(randint(10000, 20000), None, 'Security Groups', '', None, size=0)
        obj['children'].append(folder)
        for o in items:
            folder['children'].append(self._print_item(o.oid, o.ext_id, o.name, 'NsxSecurityGroup', o.objuri, size=0))
            folder['size'] += 1           
            
        # get logical switch
        items = manager.get_logical_switches()
        folder = self._print_item(randint(10000, 20000), None, 'Logical Siwtches', '', None, size=0)
        obj['children'].append(folder)
        for o in items:
            folder['children'].append(self._print_item(o.oid, o.ext_id, o.name, 'NsxLogicalSwitch', o.objuri, size=0))
            folder['size'] += 1         
        
        # get dlr
        items = manager.get_dlrs()
        folder = self._print_item(randint(10000, 20000), None, 'Dlrs', '', None, size=0)
        obj['children'].append(folder)
        for o in items:
            folder['children'].append(self._print_item(o.oid, o.ext_id, o.name, 'NsxDlr', o.objuri, size=0))
            folder['size'] += 1 
        
        # get edge
        items = manager.get_edges()
        folder = self._print_item(randint(10000, 20000), None, 'Edge Gateway', '', None, size=0)
        obj['children'].append(folder)
        for o in items:
            folder['children'].append(self._print_item(o.oid, o.ext_id, o.name, 'NsxEdge', o.objuri, size=0))
            folder['size'] += 1 
        
        return obj
        
    @trace(op='view')
    def get_system_tree(self, vm=True, net=True, store=True, host=True):
        """Get system tree.
        
        :return: dict [<id>:{'resource':<resource>, 'childs':[]}]
        :rtype: dict
        :raises ApiManagerError if query empty return error.
        """
        # get resources
        resources = self.get_resources()
        try:
            res_index = {r.ext_id:r for r in resources}
        except Exception as ex:
            raise ApiManagerError(ex)
            
        try:
            content = self.conn.si.RetrieveContent()
            #children = content.rootFolder.childEntity
            datacenters = content.rootFolder.childEntity
            
            objs = []
            for datacenter in datacenters:
                obj = {'id': res_index[datacenter._moId].oid,
                       'extid': datacenter._moId,
                       'name': datacenter.name,
                       'type': 'VsphereDatacenter',
                       'size': 0,
                       'uri': None,
                       'children': []}
                
                #  Virtual Machine
                if vm is True:
                    self._get_system_tree_child(datacenter.vmFolder, obj, res_index)
                #  Datastore
                if store is True:
                    self._get_system_tree_child(datacenter.datastoreFolder, obj, res_index)
                # Resource
                if host is True:
                    self._get_system_tree_child(datacenter.hostFolder, obj, res_index)
                # Network
                if net is True:
                    self._get_system_tree_child(datacenter.networkFolder, obj, res_index)
                
                objs.append(obj)

            # nsx
            if self.nsx_enabled is True:
                obj = self._get_nsx_tree_child()
                objs.append(obj)

            self.logger.debug('Get vsphere tree: %s' % truncate(objs))
            return objs
        
        except Exception as ex:
            self.logger.error(ex, exc_info=1)         
            raise ApiManagerError(ex, code=400)
