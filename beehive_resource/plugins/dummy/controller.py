# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.container import Orchestrator, Resource


def get_task(task_name):
    return '%s.task_v2.%s' % (__name__.rstrip('.controller'), task_name)


class DummyContainer(Orchestrator):
    """Dummy container
    
    :param connection: json string like {}
    """    
    objdef = 'Dummy'
    objdesc = 'Dummy container'
    objuri = 'dummy'
    version = 'v1.0'    
    
    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [
            DummySyncResource,
            DummyAsyncResource,
        ]
        
    def ping(self):
        """Ping container.
        
        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return True
    
    @staticmethod
    def pre_create(controller=None, type=None, name=None, desc=None, active=None, conn=None, **kvargs):
        """Check input params

        :param ResourceController controller: resource controller instance
        :param type: container type
        :param name: container name
        :param desc: container desc
        :param active: container active
        :param conn: container connection
        :return: kvargs            
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        kvargs = {
            'type': type,
            'name': name,
            'desc': desc+' test',
            'active': active,
            'conn': {
                'test': {}
            },
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
        
        
class DummyResource(Resource):
    objdef = 'Dummy.Resource'
    objuri = 'dummyresource'
    objname = 'dummyresource'
    objdesc = 'Dummy resource'
    
    def __init__(self, *args, **kvargs):
        """ """
        Resource.__init__(self, *args, **kvargs)

    def info(self):
        """Get info.
        
        :return: Dictionary with capabilities.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.
        
        :return: Dictionary with resource details.
        :rtype: dict        
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        return info
    
    
class DummySyncResource(DummyResource):
    objdef = 'Dummy.SyncResource'
    objuri = 'syncresource'
    objname = 'syncresource'
    objdesc = 'Dummy sync resource'
    
    def __init__(self, *args, **kvargs):
        DummyResource.__init__(self, *args, **kvargs)
            
        self.child_classes = [
            DummySyncChildResource,
        ]
    
    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.
        
        :param controller: controller instance
        :param entities: list of entities
        :param args:: custom params
        :param kvargs: custom params            
        :return: None
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return entities
    
    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:            
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        pass    
    
    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used 
        in container resource_factory method.

        :param ResourceController controller: resource controller instance
        :param container: container instance
        :param args:: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs
    
    @staticmethod
    def post_create(controller, container, *args, **kvargs):
        """Check input params

        :param controller: resource controller instance
        :param container: container instance
        :param args:: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        
        return None    
    
    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.
        
        :param args:: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """        
        return kvargs
    
    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args:: custom params
        :param kvargs: custom params
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        return kvargs


class DummySyncChildResource(DummyResource):
    objdef = 'Dummy.SyncResource.ChildResource'
    objuri = 'syncrchildesource'
    objname = 'syncchildresource'
    objdesc = 'Dummy sync child resource'


class DummyAsyncResource(DummyResource):
    objdef = 'Dummy.AsyncResource'
    objuri = 'asyncresource'
    objname = 'asyncresource'
    objdesc = 'Dummy async resource'

    create_task = get_task('asyncresource.asyncresource_add_task')
    update_task = get_task('asyncresource.asyncresource_update_task')
    expunge_task = get_task('asyncresource.asyncresource_expunge_task')
