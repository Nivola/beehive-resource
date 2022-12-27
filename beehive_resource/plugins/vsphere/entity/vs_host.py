# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beecell.simple import truncate, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.vsphere.entity import VsphereResource
from beehive.common.data import trace


class VsphereHost(VsphereResource):
    objdef = 'Vsphere.DataCenter.Cluster.Host'
    objuri = 'hosts'
    objname = 'host'
    objdesc = 'Vsphere hosts'
    
    default_tags = ['vsphere']
    
    def __init__(self, *args, **kvargs):
        """ """
        VsphereResource.__init__(self, *args, **kvargs)
        
        # child classes
        self.child_classes = []

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)         
           
        :raises ApiManagerError:
        """
        from .vs_cluster import VsphereCluster
        from .vs_datacenter import VsphereDatacenter
        
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []
        for datacenter in datacenters:
            for node in datacenter.hostFolder.childEntity:
                obj_type = type(node).__name__
                if obj_type == 'vim.ClusterComputeResource':
                    for host in node.host:
                        items.append((host._moId, host.name, node._moId, VsphereCluster))
                elif obj_type == 'vim.HostSystem':
                    items.append((node._moId, node.name, datacenter._moId, VsphereDatacenter))

        # add new item to final list
        res = []
        for item in items:
            if item[0] not in res_ext_ids:
                parent_id = item[2]
                parent_class = item[3]
                resclass = VsphereHost
                res.append((resclass, item[0], parent_id, resclass.objdef, item[1], parent_class))
        
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        # query vsphere
        content = container.conn.si.RetrieveContent()
        datacenters = content.rootFolder.childEntity
        items = []
              
        for datacenter in datacenters:
            for node in datacenter.hostFolder.childEntity:
                obj_type = type(node).__name__
                if obj_type == 'vim.ClusterComputeResource':
                    for host in node.host:
                        items.append({'id': host._moId, 'name': host.name})
                elif obj_type == 'vim.HostSystem':
                    items.append({'id': node._moId, 'name': node.name})
        
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
        from .vs_cluster import VsphereCluster
        
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        parent_class = entity[5]
        
        parent = container.get_resource_by_extid(parent_id)
        parent_id = parent.oid

        if parent_class == VsphereCluster:
            objid = '%s//%s' % (parent.objid, id_gen())
        # get parent datacenter
        else:
            objid = '%s//none//%s' % (parent.objid, id_gen())
        
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
        """Post list function. Extend this function to execute some operation after entity was created. Used only for 
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params            
        :return: None            
        :raises ApiManagerError:
        """
        remote_entities = container.conn.cluster.host.list()
        
        # create index of remote objs
        remote_entities_index = {i['obj']._moId: i for i in remote_entities}
        
        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)
            except:
                container.logger.warn('', exc_info=1)
        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:            
        :raises ApiManagerError:
        """
        try:
            ext_obj = self.container.conn.cluster.host.get(self.ext_id)
            self.set_physical_entity(ext_obj)
        except:
            pass
    
    #
    # info
    #    
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = VsphereResource.info(self)

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = VsphereResource.detail(self)
        if self.ext_obj is not None:
            details = info['details']
            data = self.container.conn.cluster.host.detail(self.ext_obj)
            details.update(data)
        
        return info
    
    #
    # custom info
    #
    @trace(op='hardware.use')
    def get_hardware(self):
        """Get details.
        
        :return:
        
            {"biosInfo": {"biosVersion": "6.0.7", "dynamicProperty": [], "dynamicType": None,
                          "releaseDate": 1313625600},
             "cpuFeature": [{"dynamicProperty": [],
                              "dynamicType": None,
                              "eax": "0000:0000:0000:0000:0000:0000:0000:1011",
                              "ebx": "0111:0101:0110:1110:0110:0101:0100:0111",
                              "ecx": "0110:1100:0110:0101:0111:0100:0110:1110",
                              "edx": "0100:1001:0110:0101:0110:1110:0110:1001",
                              "level": 0,
                              "vendor": None},
                             ...],
             "cpuInfo": {"dynamicProperty": [], "dynamicType": None, "hz": 3058999535L, "numCpuCores": 12,
                         "numCpuPackages": 2, "numCpuThreads": 24},
             "cpuPkg": [{"busHz": 132999976,
                          "cpuFeature": [{"dynamicProperty": [],
                                           "dynamicType": None,
                                           "eax": "1000:0000:0000:0000:0000:0000:0000:1000",
                                           "ebx": "0000:0000:0000:0000:0000:0000:0000:0000",
                                           "ecx": "0000:0000:0000:0000:0000:0000:0000:0000",
                                           "edx": "0000:0000:0000:0000:0000:0000:0000:0000",
                                           "level": -2147483648L,
                                           "vendor": None},
                                          ...],
                          "description": "Intel(R) Xeon(R) CPU           X5675  @ 3.07GHz",
                          "dynamicProperty": [],
                          "dynamicType": None,
                          "hz": 3058999459L,
                          "index": 0,
                          "threadId": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
                          "vendor": "intel"},
                         {"busHz": 132999956,
                          "cpuFeature": [{"dynamicProperty": [],
                                           "dynamicType": None,
                                           "eax": "1000:0000:0000:0000:0000:0000:0000:1000",
                                           "ebx": "0000:0000:0000:0000:0000:0000:0000:0000",
                                           "ecx": "0000:0000:0000:0000:0000:0000:0000:0000",
                                           "edx": "0000:0000:0000:0000:0000:0000:0000:0000",
                                           "level": -2147483648L,
                                           "vendor": None},
                                          ...],
                          "description": "Intel(R) Xeon(R) CPU           X5675  @ 3.07GHz",
                          "dynamicProperty": [],
                          "dynamicType": None,
                          "hz": 3058999611L,
                          "index": 1,
                          "threadId": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
                          "vendor": "intel"}],
             "cpuPowerManagementInfo": {"currentPolicy": "Balanced", "dynamicProperty": [], "dynamicType": None,
                                        "hardwareSupport": "ACPI C-states"},
             "dynamicProperty": [],
             "dynamicType": None,
             "memorySize": 77295800320L,
             "numaInfo": {"dynamicProperty": [],
                           "dynamicType": None,
                           "numNodes": 2,
                           "numaNode": [{"cpuID": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
                                          "dynamicProperty": [],
                                          "dynamicType": None,
                                          "memoryRangeBegin": 39728447488L,
                                          "memoryRangeLength": 38654705664L,
                                          "typeId": 0},
                                         {"cpuID": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
                                          "dynamicProperty": [],
                                          "dynamicType": None,
                                          "memoryRangeBegin": 4294967296L,
                                          "memoryRangeLength": 35433480192L,
                                          "typeId": 1}],
                           "type": "NUMA"},
             "pciDevice": [{"bus": 0,
                             "classId": 1536,
                             "deviceId": 13315,
                             "deviceName": "PowerEdge R610 I/O Hub to ESI Port",
                             "dynamicProperty": [],
                             "dynamicType": None,
                             "function": 0,
                             "id": "0000:00:00.0",
                             "parentBridge": None,
                             "slot": 0,
                             "subDeviceId": 566,
                             "subVendorId": 4136,
                             "vendorId": -32634,
                             "vendorName": "Intel Corporation"},
                            {"bus": 0,
                             "classId": 1540,
                             "deviceId": 13320,
                             "deviceName": "5520/5500/X58 I/O Hub PCI Express Root Port 1",
                             "dynamicProperty": [],
                             "dynamicType": None,
                             "function": 0,
                             "id": "0000:00:01.0",
                             "parentBridge": None,
                             "slot": 1,
                             "subDeviceId": 0,
                             "subVendorId": 0,
                             "vendorId": -32634,
                             "vendorName": "Intel Corporation"},
                            ...],
             "reliableMemoryInfo": None,
             "smcPresent": False,
             "systemInfo": {"dynamicProperty": [],
                             "dynamicType": None,
                             "model": "PowerEdge R610",
                             "otherIdentifyingInfo": [{"dynamicProperty": [],
                                                        "dynamicType": None,
                                                        "identifierType": {"dynamicProperty": [],
                                                                            "dynamicType": None,
                                                                            "key": "AssetTag",
                                                                            "label": "Asset Tag",
                                                                            "summary": "Asset tag of the system"},
                                                        "identifierValue": " unknown"},
                                                        ...],
                             "uuid": "4c4c4544-0054-5410-805a-c4c04f35354a",
                             "vendor": "Dell Inc."}}
        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions('use')
        
        try:
            data = {}
            if self.ext_obj is not None:
                data = self.container.conn.cluster.host.hardware(self.ext_obj)
            
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)      

    @trace(op='runtime.use')
    def get_runtime(self):
        """Get details.
        
        :return: {"boot_time": 1454517716, "maintenance": False, "power_state": "poweredOn"}
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions('use')
        
        try:
            data = {}
            if self.ext_obj is not None:
                data = self.container.conn.cluster.host.runtime(self.ext_obj)
            
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)      

    @trace(op='configuration.use')
    def get_configuration(self):
        """Get details.
        
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions('use')
        
        try:
            data = {}
            if self.ext_obj is not None:
                data = self.container.conn.cluster.host.configuration(self.ext_obj)
            
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)   

    @trace(op='usage.use')
    def get_usage(self):
        """Get details.
        
        :return:
        
            {
                "distributedCpuFairness": 2863,
                "distributedMemoryFairness": 1071,
                "dynamicProperty": [],
                "dynamicType": None,
                "overallCpuUsage": 1232,
                "overallMemoryUsage": 19011,
                "uptime": 5266303
            }
        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions('use')
        
        try:
            data = {}
            if self.ext_obj is not None:
                data = self.container.conn.cluster.host.usage(self.ext_obj)
            
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)      
    
    @trace(op='services.use')
    def get_services(self):
        """Get service.
        
        :return:
        
            {
                "dynamicProperty": [],
                "dynamicType": None,
                "service": [
                {
                    "dynamicProperty": [],
                    "dynamicType": None,
                    "key": "DCUI",
                    "label": "Direct Console UI",
                    "policy": "on",
                    "required": False,
                    "ruleset": [],
                    "running": True,
                    "sourcePackage": {
                        "description": "This VIB contains all of the base functionality of vSphere ESXi.",
                        "dynamicProperty": [],
                        "dynamicType": None,
                        "sourcePackageName": "esx-base"
                    }
                },...
                ]
            }
        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions('use')
        
        try:
            if self.ext_obj is not None:
                data = self.container.conn.cluster.host.services(self.ext_obj)

            self.logger.debug('Get host %s services: %s...' % (self.oid, truncate(data)))
            return data
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)  
    
    @trace(op='physical-nics.use')
    def get_physical_nics(self):
        """Get physical nics.
        
        :return:
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        self.verify_permisssions('use')
        
        try:
            res = self.ext_obj.config.network.pnic

            self.logger.debug('Get host %s physical mics: %s...' % (self.oid, truncate(res)))
            return res
        except ApiManagerError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=ex.code)     
