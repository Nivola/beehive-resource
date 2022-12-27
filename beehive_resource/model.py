# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import logging
import datetime
import ujson as json
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, Text
from sqlalchemy import Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text
from beecell.simple import truncate, get_timestamp_from_date, get_date_from_timestamp, format_date
from sqlalchemy.sql.expression import column, desc
from beecell.db import ModelError
from uuid import uuid4
from beehive.common.data import query, transaction, cache_query
from beehive.common.model import Base, AbstractDbManager, BaseEntity
from beecell.simple import jsonDumps

Base = declarative_base()

logger = logging.getLogger(__name__)

# Many-to-Many Relationship among tags and containers
tags_containers = Table('tags_containers', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('tag_id', Integer(), ForeignKey('resource_tag.id')),
    Column('container_id', Integer(), ForeignKey('container.id')))

# Many-to-Many Relationship among tags and resources
tags_resources = Table('tags_resources', Base.metadata,
    Column('id', Integer, primary_key=True),                       
    Column('tag_id', Integer(), ForeignKey('resource_tag.id')),
    Column('resource_id', Integer(), ForeignKey('resource.id')))

# Many-to-Many Relationship among tags and resources
tags_links = Table('tags_resources_links', Base.metadata,
    Column('id', Integer, primary_key=True),                   
    Column('tag_id', Integer(), ForeignKey('resource_tag.id')),
    Column('link_id', Integer(), ForeignKey('resource_link.id')))


class ResourceTag(Base, BaseEntity):
    __tablename__ = 'resource_tag'
    
    def __init__(self, value, objid):
        """Create new tag
        
        :param value: tag value
        """
        self.uuid = str(uuid4())
        self.name = value
        self.objid = objid
        self.desc = value
        self.active = True
        self.creation_date = datetime.today()
        self.modification_date = self.creation_date


class ResourceTagCount(declarative_base()):
    __tablename__ = 'resource_tag'
    
    id = Column(Integer, primary_key=True)
    count = Column(Integer)


class ResourceTagOccurrences(declarative_base()):
    __tablename__ = 'resource_tag'
    
    id = Column(Integer, primary_key=True)
    uuid = Column(String(50), unique=True)
    objid = Column(String(400))
    name = Column(String(100), unique=True)
    desc = Column(String(255))
    active = Column(Boolean())
    creation_date = Column(DateTime())
    modification_date = Column(DateTime())
    expiry_date = Column(DateTime())
    resources = Column(Integer)
    containers = Column(Integer)
    links = Column(Integer)
    
    def __init__(self, tag, resources, containers, links):
        self.id = tag.id
        self.uuid = tag.uuid
        self.objid = tag.objid
        self.name = tag.name
        self.desc = tag.desc
        self.active = tag.active
        self.creation_date = tag.creation_date
        self.modification_date = tag.modification_date
        self.expiry_date = tag.expiry_date
        self.resources = resources
        self.containers = containers
        self.links = links
        
    
class ContainerType(Base):
    __tablename__ = 'container_type'
    __table_args__ = {'mysql_engine':'InnoDB'}    
    
    id = Column(Integer, primary_key=True)
    category = Column(String(50))
    value = Column(String(50), unique = True)
    objclass = Column(String(100))

    def __init__(self, category, value, objclass):
        """
        :param category: container category. String like orchestrator, hypervisor
        :param value: container type. String like cloudstack
        :param objclass: object class. String like Cloudstack
        """
        self.category = category
        self.value = value
        self.objclass = objclass
    
    def __repr__(self):
        return '<ResourceType id=%s, category=%s, value=%s>' % (
            self.id, self.category, self.value)


class ContainerState(object):
    PENDING = 0
    BUILDING = 1
    ACTIVE = 2
    UPDATING = 3
    ERROR = 4
    DELETING = 5
    DELETED = 6
    EXPUNGING = 7
    EXPUNGED = 8
    SYNCHRONIZE = 9
    DISABLED = 10
    
    state = [
        'PENDING',
        'BUILDING',
        'ACTIVE',
        'UPDATING',
        'ERROR',
        'DELETING',
        'DELETED',
        'EXPUNGING',
        'EXPUNGED',
        'SYNCHRONIZE',
        'DISABLED'
    ]


class Container(Base, BaseEntity):
    __tablename__ = 'container'

    state = Column(Integer())
    connection = Column(String(1024), default='')
    type_id = Column(Integer(), ForeignKey('container_type.id'))
    type = relationship('ContainerType')
    remove_date = Column(DateTime())
    tag = relationship('ResourceTag', secondary=tags_containers, backref=backref('container', lazy='dynamic'))

    def __init__(self, objid, name, ctype, connection, desc='', active=False):
        """
        :param str objid: container object id.
        :param name str: container name.
        :param ctype :class:`ContainerType`: container type
        :param connection json: connection string
        :param desc str: description [default='']
        :param active bool:  Status. If True is active [default=True] 
        """
        BaseEntity.__init__(self, objid, name, desc, active)
        
        self.type = ctype
        self.connection = connection
        self.tag = []
        self.state = ContainerState.PENDING
    
    def __repr__(self):
        return '<%s id=%s, uuid=%s, obid=%s, name=%s, type=%s, category=%s>' % (
                    self.__class__.__name__, self.id, self.uuid, self.objid, 
                    self.name, self.type.category, self.type.value)                


class ResourceType(Base):
    __tablename__ = 'resource_type'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    
    id = Column(Integer, primary_key=True)
    value = Column(String(100), unique=True)
    objclass = Column(String(100))

    def __init__(self, value, objclass):
        """
        :param value: object type value. String like virtual machine
        :param objclass: object class. String like Cloudstack
        """
        self.value = value
        self.objclass = objclass
    
    def __repr__(self):
        return '<ResourceType id=%s, value=%s>' % (self.id, self.value)


class ResourceState(object):
    PENDING = 0
    BUILDING = 1
    ACTIVE = 2
    UPDATING = 3
    ERROR = 4
    DELETING = 5
    DELETED = 6
    EXPUNGING = 7
    EXPUNGED = 8
    UNKNOWN = 9
    DISABLED = 10
    
    state = [
        'PENDING',
        'BUILDING',
        'ACTIVE',
        'UPDATING',
        'ERROR',
        'DELETING',
        'DELETED',
        'EXPUNGING',
        'EXPUNGED',
        'UNKNOWN',
        'DISABLED'
    ]


class Resource(Base, BaseEntity):
    """Resource
    """
    __tablename__ = 'resource'
    
    name = Column(String(200))
    state = Column(Integer())
    ext_id = Column(String(255))
    attribute = Column(String(10000))
    remove_date = Column(DateTime())
    type_id = Column(Integer(), ForeignKey('resource_type.id'))
    type = relationship('ResourceType')
    container_id = Column(Integer(), ForeignKey('container.id'))
    container = relationship('Container')
    parent_id = Column(Integer)
    last_error = Column(Text)
    tag = relationship('ResourceTag', secondary=tags_resources, backref=backref('resource', lazy='dynamic'))
    
    def __init__(self, objid, name, rtype, container, ext_id=None, active=False, desc='', attribute='', parent_id=None):
        """
        :param str objid: resource object id.
        :param name str: resource name.
        :param ext_id str: id of resource in the container
        :param desc str: description
        :param attribute str: resource attribute
        :param active bool: status of the resource. True is active
        :param rtype :class:`ResourceType`: service type
        :param container: container_id
        """
        BaseEntity.__init__(self, objid, name, desc, active)
        
        self.type = rtype
        self.container_id = container
        self.ext_id = ext_id
        self.attribute = attribute
        self.parent_id = parent_id
        self.tag = []
        self.state = ResourceState.PENDING
        self.last_error = ''
    
    def __repr__(self):
        return '<%s id=%s, uuid=%s, obid=%s, name=%s, type=%s, container=%s>' % (
                    self.__class__.__name__, self.id, self.uuid, self.objid, 
                    self.name, self.type.value, self.container_id)

    @staticmethod
    def model_to_dict(entity):
        res = {
            'id': entity.id,
            'uuid': entity.uuid,
            'objid': entity.objid,
            'active': entity.active,
            'name': entity.name,
            'desc': entity.desc,
            'state': entity.state,
            'ext_id': entity.ext_id,
            'attribute': entity.attribute,
            'remove_date': get_timestamp_from_date(entity.remove_date),
            'creation_date': get_timestamp_from_date(entity.creation_date),
            'modification_date': get_timestamp_from_date(entity.modification_date),
            'expiry_date': get_timestamp_from_date(entity.expiry_date),
            'type_id': entity.type_id,
            'type_value': entity.type.value,
            'type_objclass': entity.type.objclass,
            'container_id': entity.container_id,
            'parent_id': entity.parent_id,
            'last_error': entity.last_error
        }
        return res

    @staticmethod
    def dict_to_model(entity):
        res_type = ResourceType(entity.get('type_value', None), entity.get('type_objclass', None))
        res_type.id = entity.get('type_id', None)
        res = Resource(entity.get('objid', None), entity.get('name', None), res_type, None,
                       ext_id=entity.get('ext_id', None), active=entity.get('active', None),
                       desc=entity.get('desc', None), attribute=entity.get('attribute', None),
                       parent_id=entity.get('parent_id', None))
        res.id = entity.get('id', None)
        res.uuid = entity.get('uuid', None)
        res.type_id = entity.get('type_id', None)
        res.container_id = entity.get('container_id', None)
        res.state = entity.get('state', None)
        res.last_error = entity.get('last_error', None)
        res.remove_date = get_date_from_timestamp(entity.get('remove_date', None))
        res.creation_date = get_date_from_timestamp(entity.get('creation_date', None))
        res.modification_date = get_date_from_timestamp(entity.get('modification_date', None))
        res.expiry_date = entity.get('expiry_date', None)
        return res


class ResourceWithLink(Resource):
    @staticmethod
    def model_to_dict(entity):
        res = {
            'id': entity.id,
            'uuid': entity.uuid,
            'objid': entity.objid,
            'active': entity.active,
            'name': entity.name,
            'desc': entity.desc,
            'state': entity.state,
            'ext_id': entity.ext_id,
            'attribute': entity.attribute,
            'remove_date': get_timestamp_from_date(entity.remove_date),
            'creation_date': get_timestamp_from_date(entity.creation_date),
            'modification_date': get_timestamp_from_date(entity.modification_date),
            'expiry_date': get_timestamp_from_date(entity.expiry_date),
            'type_id': entity.type_id,
            'type_value': entity.type.value,
            'type_objclass': entity.type.objclass,
            'container_id': entity.container_id,
            'parent_id': entity.parent_id,
            'last_error': entity.last_error,
            'link_type': entity.link_type,
            'link_attr': entity.link_attr,
            'link_creation': entity.link_creation,
        }
        return res

    @staticmethod
    def dict_to_model(entity):
        res_type = ResourceType(entity.get('type_value', None), entity.get('type_objclass', None))
        res_type.id = entity.get('type_id', None)
        res = ResourceWithLink(entity.get('objid', None), entity.get('name', None), res_type, None,
                               ext_id=entity.get('ext_id', None), active=entity.get('active', None),
                               desc=entity.get('desc', None), attribute=entity.get('attribute', None),
                               parent_id=entity.get('parent_id', None))
        res.id = entity.get('id', None)
        res.uuid = entity.get('uuid', None)
        res.type_id = entity.get('type_id', None)
        res.container_id = entity.get('container_id', None)
        res.state = entity.get('state', None)
        res.last_error = entity.get('last_error', None)
        res.remove_date = get_date_from_timestamp(entity.get('remove_date', None))
        res.creation_date = get_date_from_timestamp(entity.get('creation_date', None))
        res.modification_date = get_date_from_timestamp(entity.get('modification_date', None))
        res.expiry_date = entity.get('expiry_date', None)
        res.link_type = entity.get('link_type', None)
        res.link_attr = entity.get('link_attr', None)
        res.link_creation = entity.get('link_creation', None)
        return res


class ResourceJob(Base, BaseEntity):
    """Resource jobs
    """
    __tablename__ = 'resource_job'
    __table_args__ = {'mysql_engine': 'InnoDB'}

    id = Column(Integer, primary_key=True)
    job = Column(String(200))
    name = Column(String(200))
    params = Column(String(4000))
    creation_date = Column(DateTime())
    resource_id = Column(Integer())
    container_id = Column(Integer())
    # resource_id = Column(Integer(), ForeignKey('resource.id'))
    # resource = relationship('Resource')
    # container_id = Column(Integer(), ForeignKey('container.id'))
    # container = relationship('Container')
    
    def __init__(self, job, name, resource_id=None, container_id=None, params={}):
        """
        :param job: resource job id.
        :param name: resource job name.
        :param resource_id: id of the resource associated.
        :param params: resource job params.
        """
        self.job = job
        self.name = name
        self.resource_id = resource_id
        self.container_id = container_id
        self.params = jsonDumps(params)
        self.creation_date = datetime.today()
    
    def __repr__(self):
        return '<ResourceJob id=%s, job=%s, name=%s>' % (self.id, self.job, self.name)


class ResourceLink(Base, BaseEntity):
    __tablename__ = 'resource_link'
    
    type = Column(String(50), nullable=False)
    start_resource_id = Column(Integer(), ForeignKey('resource.id'))
    start_resource = relationship('Resource', foreign_keys=start_resource_id)
    end_resource_id = Column(Integer(), ForeignKey('resource.id'))
    end_resource = relationship('Resource', foreign_keys=end_resource_id)
    attributes = Column(String(2000))
    tag = relationship('ResourceTag', secondary=tags_links, backref=backref('resource_link', lazy='dynamic'))
    
    def __init__(self, objid, name, ltype, start_resource, end_resource, 
                 attributes=''):
        BaseEntity.__init__(self, objid, name, name, True)
        self.type = ltype
        self.objid = objid
        self.start_resource_id = start_resource
        self.end_resource_id = end_resource
        self.attributes = attributes

    def __repr__(self):
        return '<%s id=%s, uuid=%s, obid=%s, name=%s, type=%s, start=%s, end=%s>' % (
                    self.__class__.__name__, self.id, self.uuid, self.objid, 
                    self.name, self.type, self.start_resource_id, 
                    self.end_resource_id)

    @staticmethod
    def model_to_dict(entity):
        res = {
            'id': entity.id,
            'uuid': entity.uuid,
            'objid': entity.objid,
            'active': entity.active,
            'name': entity.name,
            'desc': entity.desc,
            'type': entity.type,
            'start_resource_id': entity.start_resource_id,
            'end_resource_id': entity.end_resource_id,
            'attributes': entity.attributes
        }
        return res

    @staticmethod
    def dict_to_model(entity):
        res = ResourceLink(entity.get('objid', None), entity.get('name', None), entity.get('type', None),
                           entity.get('start_resource_id', None), entity.get('end_resource_id', None),
                           entity.get('attributes', None))
        res.id = entity.get('id', None)
        res.uuid = entity.get('uuid', None)
        res.active = entity.get('active', None)
        res.desc = entity.get('desc', None)
        return res


class ResourceDbManager(AbstractDbManager):
    """
    """
    @staticmethod
    def create_table(db_uri):
        """Create all tables in the engine. This is equivalent to "Create Table" statements in raw SQL."""
        AbstractDbManager.create_table(db_uri)
        
        try:
            engine = create_engine(db_uri)
            engine.execute("SET FOREIGN_KEY_CHECKS=1;")
            Base.metadata.create_all(engine)
            logger.info('Create tables on : %s' % db_uri)
            del engine
        except exc.DBAPIError as e:
            raise Exception(e)
    
    @staticmethod
    def remove_table(db_uri):
        """ Remove all tables in the engine. This is equivalent to "Drop Table" statements in raw SQL."""
        AbstractDbManager.remove_table(db_uri)
        
        try:
            engine = create_engine(db_uri)
            engine.execute("SET FOREIGN_KEY_CHECKS=0;")
            Base.metadata.drop_all(engine)
            logger.info('Remove tables from : %s' % db_uri)
            del engine
        except exc.DBAPIError as e:
            raise Exception(e)

    def order_query_resourcetags(self, kvargs):
        """Order resource tags by name
        
        :param kvargs: query params            
        :return: kvargs updated       
        """
        tags = kvargs.get('resourcetags')
        tags = tags.split(',')
        tags.sort()
        kvargs['resourcetag_list'] = tags
        kvargs['resourcetags'] = ','.join(tags)
        return kvargs

    #
    # tags
    #
    def count_tags(self):
        """Get tags count.
        
        :return: tags number
        :raises QueryError: raise :class:`QueryError`  
        """
        return self.count_entities(ResourceTag)  
    
    def get_tags(self, *args, **kvargs):
        """Get tags.
        
        :param value: tag value [optional]
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of ResourceTag     
        :raises QueryError: raise :class:`QueryError`
        """
        filters = []
        if 'value' in kvargs and kvargs.get('value') is not None:
            filters = ['AND name like :value']
        
        tags, total = self.get_paginated_entities(ResourceTag, filters=filters, *args, **kvargs)
        resources = self.get_tags_resource_occurrences(*args, **kvargs)
        containers = self.get_tags_container_occurrences(*args, **kvargs)
        links = self.get_tags_link_occurrences(*args, **kvargs)
        
        res = []
        for tag in tags:
            res.append(ResourceTagOccurrences(tag, resources.get(tag.id, 0), 
                                              containers.get(tag.id, 0), 
                                              links.get(tag.id, 0)))
        
        return res, total
    
    def get_tags_resource_occurrences(self, *args, **kvargs):
        """Get tags occurrences for resources.
        
        :param value: tag value [optional]
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of tags with occurrences
        :raises QueryError: raise :class:`QueryError`           
        """
        tables = [('tags_resources', 't4')]
        select_fields = ['count(t4.resource_id) as count']
        filters = ['AND t4.tag_id=t3.id']
        if 'value' in kvargs and kvargs.get('value') is not None:
            filters.append('AND name like :value')
        res, total = self.get_paginated_entities(ResourceTagCount,
                                                 tables=tables,
                                                 select_fields=select_fields,
                                                 filters=filters, 
                                                 *args, **kvargs)
        return {i.id:i.count for i in res}
    
    def get_tags_container_occurrences(self, *args, **kvargs):
        """Get tags occurrences for containers.
        
        :param value: tag value [optional]
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of tags with occurrences
        :raises QueryError: raise :class:`QueryError`           
        """
        tables = [('tags_containers', 't4')]
        select_fields = ['count(t4.container_id) as count']
        filters = ['AND t4.tag_id=t3.id']
        if 'value' in kvargs and kvargs.get('value') is not None:
            filters.append('AND name like :value')
        res, total = self.get_paginated_entities(ResourceTagCount,
                                                 tables=tables,
                                                 select_fields=select_fields,
                                                 filters=filters, 
                                                 *args, **kvargs)
        return {i.id: i.count for i in res}
    
    def get_tags_link_occurrences(self, *args, **kvargs):
        """Get tags occurrences for links.
        
        :param value: tag value [optional]
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of tags with occurrences
        :raises QueryError: raise :class:`QueryError`           
        """
        tables = [('tags_resources_links', 't4')]
        select_fields = ['count(t4.link_id) as count']
        filters = ['AND t4.tag_id=t3.id']
        if 'value' in kvargs and kvargs.get('value') is not None:
            filters.append('AND name like :value')
        res, total = self.get_paginated_entities(ResourceTagCount,
                                                 tables=tables,
                                                 select_fields=select_fields,
                                                 filters=filters, 
                                                 *args, **kvargs)
        return {i.id:i.count for i in res}

    def add_tag(self, value, objid):
        """Add tag.
    
        :param str value: tag value.
        :param str objid: objid
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.add_entity(ResourceTag, value, objid)
        return res
        
    def update_tag(self, *args, **kvargs):
        """Update tag.
    
        :param int oid: entity id. [optional]
        :param value: tag value. [optional]
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        kvargs['name'] = kvargs.pop('value', None)
        res = self.update_entity(ResourceTag, *args, **kvargs)
        return res  
    
    def delete_tag(self, *args, **kvargs):
        """Remove tag.
        :param int oid: entity id. [optional]
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.remove_entity(ResourceTag, *args, **kvargs)
        return res

    #
    # Container Type manipulation methods
    #
    @query
    def get_container_type(self, oid=None, value=None, category=None):
        """Get container type.
        
        :param int oid: container type id. [optional]
        :param str value: container type value. String like cloudstack, kvm [optional]
        :param category str: container category. String like orchestrator, hypervisor [optional]
        :rtype: list of :class:`ContainerType`
        :raises QueryError: raise :class:`QueryError`  
        """
        session = self.get_session()
        if oid is not None:  
            res = session.query(ContainerType).filter_by(id=oid).all()
        elif value is not None:
            res = session.query(ContainerType).filter_by(value=value).all()
        elif category is not None:
            res = session.query(ContainerType).filter_by(category=category).all()                
        else:
            res = session.query(ContainerType).all()
            
        if len(res) == 0:
            self.logger.error('No container types found')
            raise ModelError('No container types found', code=404)
                 
        self.logger.debug2('Get container types: %s' % truncate(res))
        return res

    @transaction
    def add_container_type(self, category, value, objclass):
        """Add a container type.
        
        :param str value: container type value. String like cloudstack, kvm
        :param category str: container category. String like orchestrator, hypervisor
        :param objclass: object class. String like Cloudstack
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()        
        record = ContainerType(category, value, objclass)
        session.add(record)
        session.flush()
        self.logger.debug2('Add container type: %s' % record)
        return record
    
    @transaction
    def remove_container_type(self, oid=None, value=None):
        """Remove container type. Specify oid or value.
        
        :param int oid: container type id.
        :param str value: container type value. String like cloudstack, kvm
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        if oid is not None:  
            res = session.query(ContainerType).filter_by(id=oid).firt()
        elif value is not None:
            res = session.query(ContainerType)\
                         .filter(ContainerType.value.like('%'+value+'%'))\
                         .first()                           
        else:
            self.logger.error('Specify at least one params')
            raise ModelError('Specify at least one params')
        
        if res is not None:
            session.delete(res)
        else:
            self.logger.error('No container types found')
            raise ModelError('No container type found', code=404)
        self.logger.debug2('Remove container type: %s' % res)
        return True

    #
    # Container
    #
    def count_container(self):
        """Get containers count.
        
        :raises QueryError: raise :class:`QueryError`  
        """
        return self.count_entities(Container)

    def get_containers(self, *args, **kvargs):
        """Get containers.

        :param type_id: container type id [optional]
        :param state: container state [optional]
        :param desc: container desc [optional]
        :param resourcetags: list of tags comma separated. All tags in the list must be met [optional]
        :param creation_date: creation_date [optional]
        :param modification_date: modification_date [optional]
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :param state: state [optional]
        :rtype: list of :class:`Container`
        :raises QueryError: raise :class:`QueryError`  
        """
        filters = []
        custom_select = None
        if kvargs.get('type_id', None) is not None:
            filters.append('AND type_id=:type_id')
        if kvargs.get('state', None) is not None:
            filters.append('AND state=:state')
        if kvargs.get('desc', None) is not None:
            filters.append('AND desc=:desc')
        if kvargs.get('resourcetags', None) is not None:
            custom_select = '(SELECT t1.*, GROUP_CONCAT(t2.name) as tags '\
                     'FROM container t1, resource_tag t2, tags_containers t3 '\
                     'WHERE t3.tag_id=t2.id and t3.container_id=t1.id '\
                     'and (t2.name in :resourcetag_list) '\
                     'GROUP BY t1.id ORDER BY t2.name)'
            kvargs = self.order_query_resourcetags(kvargs)
            filters.append('AND t3.tags=:resourcetags')
        
        res, total = self.get_paginated_entities(Container, filters=filters,
                                                 custom_select=custom_select,
                                                 *args, **kvargs)     
        return res, total

    def get_containers_from_tags(self, *args, **kvargs):
        """Get containers with all the of tags specified.
        
        :param resource_tags: list of tags that containers must have
        :return: list of container instances
        :raises QueryError: raise :class:`QueryError`          
        """
        tables = [('tags_containers', 't4'),
                  ('resource_tag', 't5')]
        select_fields = ['GROUP_CONCAT(t5.value) as tags']
        filters = [
            'AND t4.tag_id=t5.id',
            'AND t3.id=t4.container_id',
            'AND t5.value IN :resource_tags']
        res, total = self.get_paginated_entities(Container, filters=filters, 
                                                 tables=tables, 
                                                 select_fields=select_fields,
                                                 *args, **kvargs)
        return res, total

    def add_container(self, objid, name, ctype, connection, desc='', active=True):
        """Add a container.
        
        :param str objid: container object id.
        :param str name: container name.
        :param ContainerType ctype: container type.
        :param str connection: connection string
        :param str desc: description [default='']
        :param bool active: Status. If True is active [default=True]
        :return: :class:`Container`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.add_entity(Container, objid, name, ctype, connection, 
                              desc=desc, active=active)
        return res  
    
    def get_container_tags(self, container, *args, **kvargs):
        """Get container tags.
        
        :param container: container id
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of ResourceTag paginated, total
        :raises QueryError: raise :class:`QueryError`
        """
        tables = [('tags_containers', 't4')]
        filters = [
            'AND t3.id=t4.tag_id',
            'AND t4.container_id=:container']
        res, total = self.get_paginated_entities(ResourceTag, filters=filters, 
                                                 tables=tables,
                                                 container=container,
                                                 *args, **kvargs)
        return res, total
    
    @query
    def get_containers_index(self):
        """Get containers indexed by id.
                                    
        :return: dictionary of Container instances
        :rtype: dict
        :raises QueryError: raise :class:`QueryError`        
        """
        session = self.get_session()
        sql = ['SELECT t1.*', 
               'FROM container t1, container_type t2',
               'WHERE t1.type_id=t2.id']
    
        params = {}
            
        smtp = text(' '.join(sql))    
        query = session.query(Container).from_statement(smtp).params(**params)
                
        query = query.all()
        res = {}
        for item in query:
            res[item.id] = item
        
        self.logger.debug2('Get containers index: %s' % (truncate(res)))
        return res
    
    @query
    def get_containers_by_type(self, type=None, types=None):
        """Get containers by type.
        
        :param types: resource type list. [OPTIONAL]
                Ex. ['vsphere.dc.folder','vsphere.dc.folder.server']
        :param type: resource type complete or partial value. [OPTIONAL] 
                Ex. 'vsphere.dc.folder'
                Ex. '%folder'                          
        :return: dictionary of Container instances
        :rtype: dict
        :raises QueryError: raise :class:`QueryError`        
        """
        session = self.get_session()
        sql = ['SELECT t1.*', 
               'FROM container t1, container_type t2',
               'WHERE t1.type_id=t2.id']

        params = {}

        if type is not None:
            sql.append('AND t2.value like :type')
            params['type'] = type
        elif types is not None:
            sql.append('AND t2.value in :types')
            params['types'] = types
            
        smtp = text(' '.join(sql))    
        query = session.query(Container).from_statement(smtp).params(**params)
                
        res = query.all()
        
        self.logger.debug2('Get Container by type: %s' % (truncate(res)))
        return res      
    
    @transaction
    def add_container_tag(self, container, tag):
        """Add a tag to a container.
        
        :param container: container instance
        :param tag: tag instance.
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        tags = container.tag
        if tag not in tags:
            tags.append(tag)
        self.logger.debug2('Add tag %s to container: %s' % (tag, container))
        return True
    
    @transaction
    def remove_container_tag(self, container, tag):
        """Remove a tag from a container.
        
        :param container Container: container instance
        :param tag ResourceTag: tag instance.
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        tags = container.tag
        if tag in tags:
            tags.remove(tag)
        self.logger.debug2('Remove tag %s from container: %s' % (tag, container))
        return True
    
    def update_container(self, *args, **kvargs):
        """Update container.
    
        :param name: container name. [optional]
        :param connection: new connection string [optional]
        :param desc: new description [optional]
        :param active: If True is active [optional]
        :param state: container state [optional] 
        :return: :class:`Container`
        :raises TransactionError: raise :class:`TransactionError`
        """
        connection = kvargs.pop('conn', None)
        if connection is not None and isinstance(connection, dict):
            kvargs['connection'] = jsonDumps(connection)
        res = self.update_entity(Container, *args, **kvargs)
        return res
    
    def update_container_state(self, oid, state):
        """Update container state.
       
        :param int oid: entity id.
        :param state: container state
        :return: :class:`Resource`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.update_entity(Container, oid=oid, state=state)
        return res     
    
    def delete_container(self, *args, **kvargs):
        """Remove container softly.
        
        :param int oid: entity id. [optional]
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        kvargs['state'] = ContainerState.DELETED
        kvargs['remove_date'] = datetime.today()
        kvargs['expiry_date'] = datetime.today()
        res = self.update_entity(Container, *args, **kvargs)
        return res
    
    def expunge_container(self, *args, **kvargs):
        """Remove container.
        
        :param int oid: entity id. [optional]
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        self.del_jobs(container_id=kvargs['oid'])
        res = self.remove_entity(Container, *args, **kvargs)
        return res

    #
    # Resource Type
    #
    @query
    def get_resource_types(self, oid=None, value=None, filter=None):
        """Get resource type.
        
        :param int oid: resource type id.
        :param str value: resource type value. String like org or vm
        :param filter str: resource type partial value
        :rtype: list of :class:`ResourceType`
        :raises QueryError: raise :class:`QueryError`  
        """
        session = self.get_session()
        query = session.query(ResourceType)
        if oid is not None:  
            query = query.filter_by(id=oid)
        elif value is not None:
            query = query.filter_by(value=value)
        elif filter is not None:
            query = query.filter(ResourceType.value.like(filter))    
        
        res = query.all()
            
        if len(res) == 0:
            self.logger.error('No resource types found')
            raise ModelError('No resource types found', code=404)
                 
        self.logger.debug2('Get resource types: %s' % truncate(res))
        return res

    @transaction
    def add_resource_type(self, value, objclass):
        """Add a resource type.
        
        :param str value: resource type value. String like vm
        :param objclass: object class. String like Cloudstack
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()       
        record = ResourceType(value, objclass)
        session.add(record)
        session.flush()
        self.logger.debug2('Add resource type: %s' % record)
        return record

    @transaction
    def remove_resource_type(self, oid=None, value=None):
        """Remove resource type. Specify oid or value.
        
        :param oid: id of the system object type [optional]
        :param value: resource type value. String like vm [optional]
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        if oid is not None:  
            res = session.query(ResourceType).filter_by(id=oid)
        elif value is not None:
            res = session.query(ResourceType)\
                         .filter(ResourceType.value.like('%'+value+'%'))
        else:
            self.logger.error('Specify resource type oid or value')
            raise ModelError('Specify resource type oid or value')
        
        res_type = res.first()
        if res_type is not None:
            session.delete(res_type)
        else:
            self.logger.error('No resource types found')
            raise ModelError('No resource type found', code=404)
        self.logger.debug2('Remove resource type: %s' % res_type)
        return True

    #
    # Resource
    #
    @query
    def count_resource(self, rtype=None, container=None, parent_id=None):
        """Get resources count.

        :param rtype :class:`ResourceType`: service type
        :param container :class:`Container`: resource container   
        :param parent_id: parent id     
        :rtype: int
        :raises QueryError: raise :class:`QueryError`  
        """
        session = self.get_session()
        res = session.query(Resource).filter(Resource.expiry_date == None)
        if rtype is not None: 
            res = res.filter(Resource.type == rtype)
        if container is not None: 
            res = res.filter(Resource.container == container)
        if parent_id is not None:  
            res = res.filter(Resource.parent_id == parent_id)
        res = res.count()

        self.logger.debug2('Get resources count: %s' % res)
        return res    
    
    @query
    def get_resource_by_extid(self, ext_id, container=None):
        """Get single resource by id in remote platform.
    
        :param ext_id: entity remote platform id
        :param container :class:`int`: resource container id
        :return: Resource
        :raises QueryError: raise :class:`QueryError`  
        """
        session = self.get_session()
        res = session.query(Resource).filter(Resource.ext_id == ext_id)
        if container is not None:
            res = res.filter(Resource.container_id == container)

        try:
            res = res.one()
        except:
            raise ModelError('No resource found for ext_id %s in container %s' % (ext_id, container))

        self.logger.debug2('Get resource by ext_id %s: %s' % (ext_id, truncate(res)))
        return res      
    
    def get_resources(self, *args, **kvargs):
        """Get resources.

        :param with_perm_tag: if False disable control of permission tags [default=True]
        :param ids: list of resource oid [optional]
        :param uuids: list of resource uuid [optional]
        :param objid: resource objid [optional]
        :param name: resource name [optional]
        :param ext_id: id of resource in the remote container [optional]
        :param ext_ids: list of id of resource in the remote container [optional]
        :param types: resource type id list [optional]
        :param container_id: resource container id [optional]
        :param attribute: resource attribute [optional]
        :param json_attribute_contain: resource json attribute [optional]
        :param parent_id: parent id [optional]
        :param parent_ids: parent list id [optional]
        :param active: active [optional]
        :param state: state [optional]
        :param resourcetags: list of tags comma separated. All tags in the list must be met [optional]
        :param creation_date: creation_date [optional]
        :param modification_date: modification_date [optional]
        :param show_expired: if True show expired resources [default=False]
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :rtype: list of :class:`Resource`
        :raises QueryError: raise :class:`QueryError`  
        """
        self.logger.debug2('Get resources params: %s' % truncate(kvargs))
        filters = []
        kvargs.update(filter_expiry_date=datetime.today())
        custom_select = None
        name = kvargs.pop('name', None)
        if kvargs.get('ids', None) is not None:
            filters.append('AND t1.id in :ids')
        if kvargs.get('uuids', None) is not None:
            filters.append('AND uuid in :uuids')
        if kvargs.get('objid', None) is not None:
            filters.append('AND objid like :objid')
        if name is not None:
            kvargs['name_like'] = name
            filters.append('AND name like :name_like')
        if kvargs.get('ext_id', None) is not None:
            filters.append('AND ext_id = :ext_id')
        if kvargs.get('ext_ids', None) is not None:
            filters.append('AND ext_id in :ext_ids')
        if kvargs.get('types', None) is not None:
            filters.append('AND type_id in :types')
        if kvargs.get('container_id', None) is not None:
            filters.append('AND container_id=:container_id')
        if kvargs.get('json_attribute_contain', None) is not None:
            attribute = kvargs.pop('json_attribute_contain', None)
            if attribute is not None and isinstance(attribute, dict):
                filters.append("AND JSON_CONTAINS(`attribute`, '%s', '$.%s')=1" %
                               (attribute.get('value'), attribute.get('field')))
            elif attribute is not None and isinstance(attribute, list):
                for a in attribute:
                    filters.append("AND JSON_CONTAINS(`attribute`, '%s', '$.%s')=1" %
                                   (a.get('value'), a.get('field')))

        attributes = kvargs.get('attribute', None)
        if attributes is not None and len(attributes) > 0:
            len_attributes = len(attributes)
            if isinstance(attributes, list):
                filters.append('AND (')
                kvargs['attribute_0'] = attributes[0]
                filters.append('attribute like :attribute_0')
                if len_attributes > 1:
                    for index in range(1, len_attributes):
                        key = 'attribute_%s' % index
                        kvargs[key] = attributes[index]
                        filters.append('OR attribute like :attribute_%s' % index)
                        index += 1
                filters.append(')')
            else:
                filters.append('AND attribute like :attribute')
        if kvargs.get('parent_id', None) is not None:
            filters.append('AND parent_id=:parent_id')
        if kvargs.get('parent_ids', None) is not None:
            filters.append('AND parent_id in :parent_ids')
        state = kvargs.get('state', None)
        if state is not None:
            if isinstance(state, str):
                kvargs['state'] = getattr(ResourceState, state)
            filters.append('AND state=:state')
        if kvargs.get('show_expired', False) is True:
            filters.append(' AND t3.expiry_date<=:filter_expiry_date')
        else:
            filters.append(' AND (t3.expiry_date>:filter_expiry_date OR t3.expiry_date is null)')
        if kvargs.get('resourcetags', None) is not None:
            custom_select = '(SELECT t1.*, GROUP_CONCAT(DISTINCT t2.name ORDER BY t2.name) as tags '\
                     'FROM resource t1, resource_tag t2, tags_resources t3 '\
                     'WHERE t3.tag_id=t2.id and t3.resource_id=t1.id '\
                     'and (t2.name in :resourcetag_list) '\
                     'GROUP BY t1.id)'
            kvargs = self.order_query_resourcetags(kvargs)
            filters.append('AND t3.tags=:resourcetags')
        
        res, total = self.get_paginated_entities(Resource, filters=filters, custom_select=custom_select,
                                                 *args, **kvargs)
        return res, total
        
    @query
    def get_resources_by_type(self, type=None, types=None, container=None):
        """Get resources by type.
        
        :param int container: container id. [OPTIONAL]
        :param list types resource type list. [OPTIONAL]
            Ex. ['vsphere.dc.folder','vsphere.dc.folder.server']
        :param str type: resource type complete or partial value. [OPTIONAL] 
            Ex. 'vsphere.dc.folder'
            Ex. '%folder'
        :return: list of Resource instances
        :raise QueryError:   
        """
        session = self.get_session()
        sql = ['SELECT t1.* FROM resource t1, resource_type t2 WHERE t1.type_id=t2.id']

        params = {}

        if container is not None:
            sql.append('AND t1.container_id = :container')
            params['container'] = container
        if type is not None:
            sql.append('AND t2.value like :type')
            params['type'] = type
        elif types is not None:
            sql.append('AND t2.value in :types')
            params['types'] = types
            
        smtp = text(' '.join(sql))    
        query = session.query(Resource).from_statement(smtp).params(**params)

        res = query.all()
        
        self.logger.debug2('Get resources by type: %s' % (truncate(res)))
        return res    
        
    def get_resource_links_internal(self, resource):
        """Get resource links. Use this method for internal query without 
        authorization.

        :param resource: resource id
        :return: ResourceLink instance list
        :raise QueryError:
        """
        session = self.get_session()
        res = session.query(ResourceLink)\
            .filter((ResourceLink.start_resource_id == resource) | (ResourceLink.end_resource_id == resource)).all()
        self.logger.debug2('Get resource %s links: %s' % (resource, truncate(res)))
        return res

    def get_link_among_resources_internal(self, start, end):
        """Get link among resources. Use this method for internal query without authorization.

        :param start: start resource id
        :param end: end resource id
        :return: ResourceLink instance list
        :raise QueryError:
        """
        session = self.get_session()
        res = session.query(ResourceLink) \
            .filter((ResourceLink.start_resource_id == start) & (ResourceLink.end_resource_id == end)).one()
        self.logger.debug2('Get link among resource %s and %s: %s' % (start, end, truncate(res)))
        return res
    
    def get_linked_resources(self, resource=None, link_type=None, link_type_filter=None, container_id=None, types=None,
                             *args, **kvargs):
        """Get linked resources.

        :param resource: resource id
        :param link_type: link type
        :param link_type_filter: link type filter
        :param container_id: container id
        :param types: resource definition list
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]         
        :return: ist of records            
        :raise QueryError:
        """
        tables = [('resource_link', 't4')]
        filters = [
            'AND (t4.start_resource_id=:resource OR t4.end_resource_id=:resource)',
            'AND (t4.start_resource_id=t3.id OR t4.end_resource_id=t3.id)',
            'AND t3.id!=:resource'
        ]
        if link_type is not None:
            filters.append('AND t4.type=:link_type')
        if link_type_filter is not None:
            filters.append('AND t4.type like :link_type_filter')
        if types is not None:
            filters.append('AND type_id in :types')
        if container_id is not None:
            filters.append('AND container_id=:container_id')            
        
        res, total = self.get_paginated_entities(Resource, filters=filters, resource=resource, types=types,
                                                 link_type=link_type, link_type_filter=link_type_filter,
                                                 container_id=container_id, tables=tables, *args, **kvargs)
        self.logger.debug2('Get linked resources: %s' % truncate(res))
        return res, total

    @cache_query('list')
    def get_linked_resources_with_cache(self, entity_class, resource, link_type=None, *args, **kvargs):
        """Get linked resources using also cache info. Permissions are not verified. Use this method for internal
        usage

        :param resource: start or end resource id [optional]
        :param link_type: link type or partial type [optional]
        :return: list of Resources linked
        :raises QueryError: raise :class:`QueryError`
        """
        filters = ['AND (end_resource_id=:resource or start_resource_id=:resource)']
        kvargs['filters'] = filters
        kvargs['resource'] = resource
        links, tot = self.get_paginated_entities(ResourceLink, size=-1, with_perm_tag=False, *args, **kvargs)

        res = []
        for link in links:
            if link_type is not None and link.type.find(link_type) >= 0:
                continue

            if link.start_resource_id != resource:
                resource_id = link.start_resource_id
            elif link.end_resource_id != resource:
                resource_id = link.end_resource_id

            entity = self.get_entity(Resource, resource_id)
            entity.link_attr = link.attributes
            entity.link_type = link.type
            entity.link_creation = format_date(link.creation_date)
            res.append(entity)

        self.logger.debug2('get resource %s linked resources: %s' % (resource, truncate(res)))
        return res

    def get_directed_linked_resources(self, resources=None, link_type=None, link_type_filter=None, container_id=None,
                                      types=None, *args, **kvargs):
        """Get resources direct linked to a list of resources.

        :param resources: resource ids list
        :param link_type: link type
        :param link_type_filter: link type filter
        :param container_id: container id
        :param types: resource definition list
        :param page: users list page to show [default=0]
        :param size: number of users to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of records
        :raise QueryError:
        """
        tables = [('resource_link', 't4')]
        filters = [
            'AND (t4.start_resource_id in :resources OR t4.end_resource_id in :resources)',
            'AND (t4.start_resource_id=t3.id OR t4.end_resource_id=t3.id)',
            'AND t3.id not in :resources'
        ]
        if link_type is not None:
            filters.append('AND t4.type=:link_type')
        if link_type_filter is not None:
            filters.append('AND t4.type like :link_type_filter')
        if types is not None:
            filters.append('AND type_id in :types')
        if container_id is not None:
            filters.append('AND container_id=:container_id')

        res, total = self.get_paginated_entities(Resource, filters=filters, resources=resources, types=types,
                                                 link_type=link_type, link_type_filter=link_type_filter,
                                                 container_id=container_id, tables=tables, *args, **kvargs)
        self.logger.debug2('Get direct linked resources: %s' % truncate(res))
        return res, total
        
    @query    
    def get_linked_resources_internal(self, resource, link_type=None, container_id=None, objdef=None):
        """Get linked resources. Use this method for internal query without authorization.

        :param resource: resource id
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :return: list of records
        :raise QueryError:
        """
        session = self.get_session()
        sql = ['SELECT t1.id, t1.uuid, t1.objid, t1.name, t1.ext_id,',
               't1.desc, t1.active, t1.parent_id, t1.container_id,', 
               't1.attribute, t1.state, t3.objclass, t3.value as objdef,',
               't1.creation_date, t1.modification_date, t1.expiry_date, ',
               't2.attributes as link_attr',
               'FROM resource t1, resource_link t2, resource_type t3',
               'WHERE (t1.type_id=t3.id) AND',
               '(t2.start_resource_id=:oid or t2.end_resource_id=:oid) AND',
               '(t2.start_resource_id=t1.id or t2.end_resource_id=t1.id) AND',
               't1.id != :oid']

        params = {'oid': resource}

        if link_type is not None:
            sql.append('AND t2.type like :link_type')
            params['link_type'] = link_type
        if container_id is not None:
            sql.append('AND t1.container_id = :container_id')
            params['container_id'] = container_id
        if objdef is not None:
            sql.append('AND t3.value = :objdef')
            params['objdef'] = objdef
            
        smtp = text(' '.join(sql))
        fields = self.map_field_to_column(['id', 'objid', 'name', 'ext_id', 'uuid', 'container_id', 'parent_id',
                                           'state', 'objclass', 'objdef', 'desc', 'active', 'attribute',
                                           'creation_date', 'modification_date', 'expiry_date', 'link_attr'])
        query = session.query(*fields).from_statement(smtp).params(**params)
                
        res = query.all()
        
        self.logger.debug2('Get linked resources: %s' % (truncate(res)))
        return res

    @query
    def get_directed_linked_resources_internal(self, resources, link_type=None, container_id=None, objdef=None, 
                                               objdefs=None):
        """Get direct linked resources. Use this method for internal query without authorization.

        :param resources: start resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :return: list of records
        :raise QueryError:
        """
        session = self.get_session()
        sql = ['SELECT t2.start_resource_id as resource,'
               't1.id, t1.uuid, t1.objid, t1.name, t1.ext_id,',
               't1.desc, t1.active, t1.parent_id, t1.container_id,',
               't1.attribute, t1.state, t3.objclass, t3.value as objdef,',
               't1.creation_date, t1.modification_date, t1.expiry_date,',
               't2.attributes as link_attr, t2.type as link_type, t2.creation_date as link_creation',
               'FROM resource t1, resource_link t2, resource_type t3',
               'WHERE (t1.type_id=t3.id) AND',
               '(t2.start_resource_id in :resources) AND',
               '(t2.end_resource_id=t1.id) AND',
               't1.id not in :resources']

        params = {'resources': resources}

        if link_type is not None:
            sql.append('AND t2.type like :link_type')
            params['link_type'] = link_type
        if container_id is not None:
            sql.append('AND t1.container_id = :container_id')
            params['container_id'] = container_id
        if objdef is not None:
            sql.append('AND t3.value = :objdef')
            params['objdef'] = objdef
        if objdefs is not None:
            sql.append('AND t3.value in :objdefs')
            params['objdefs'] = objdefs

        smtp = text(' '.join(sql))
        fields = self.map_field_to_column(['resource', 'id', 'objid', 'name', 'ext_id', 'uuid', 'container_id',
                                           'parent_id', 'state', 'objclass', 'objdef', 'desc', 'active', 'attribute',
                                           'creation_date', 'modification_date', 'expiry_date', 'link_attr',
                                           'link_type', 'link_creation'])
        query = session.query(*fields).from_statement(smtp).params(**params)
        res = query.all()
        self.logger.debug2('Get direct linked resources: %s' % truncate(res))
        return res

    @query
    def get_indirected_linked_resources_internal(self, resources, link_type=None, container_id=None, objdef=None,
                                                 objdefs=None):
        """Get indirect linked resources. Use this method for internal query without authorization.

        :param resources: end resource id list
        :param link_type: link type
        :param container_id: container id
        :param objdef: resource definition
        :param objdefs: resource definitions
        :return: list of records
        :raise QueryError:
        """
        session = self.get_session()
        sql = ['SELECT t2.end_resource_id as resource,'
               't1.id, t1.uuid, t1.objid, t1.name, t1.ext_id,',
               't1.desc, t1.active, t1.parent_id, t1.container_id,',
               't1.attribute, t1.state, t3.objclass, t3.value as objdef,',
               't1.creation_date, t1.modification_date, t1.expiry_date,',
               't2.attributes as link_attr, t2.type as link_type, t2.creation_date as link_creation',
               'FROM resource t1, resource_link t2, resource_type t3',
               'WHERE (t1.type_id=t3.id) AND',
               '(t2.end_resource_id in :resources) AND',
               '(t2.start_resource_id=t1.id) AND',
               't1.id not in :resources']

        params = {'resources': resources}

        if link_type is not None:
            sql.append('AND t2.type like :link_type')
            params['link_type'] = link_type
        if container_id is not None:
            sql.append('AND t1.container_id = :container_id')
            params['container_id'] = container_id
        if objdef is not None:
            sql.append('AND t3.value = :objdef')
            params['objdef'] = objdef
        if objdefs is not None:
            sql.append('AND t3.value in :objdefs')
            params['objdefs'] = objdefs

        smtp = text(' '.join(sql))
        fields = self.map_field_to_column(['resource', 'id', 'objid', 'name', 'ext_id', 'uuid', 'container_id',
                                           'parent_id', 'state', 'objclass', 'objdef', 'desc', 'active', 'attribute',
                                           'creation_date', 'modification_date', 'expiry_date', 'link_attr',
                                           'link_type', 'link_creation'])
        query = session.query(*fields).from_statement(smtp).params(**params)
        res = query.all()
        self.logger.debug2('Get indirect linked resources: %s' % truncate(res))
        return res

    def add_resource(self, objid=None, name=None, rtype=None, container=None, 
                     ext_id=None, active=True, desc='', attribute='', 
                     parent_id=None):
        """Add a resource.
        
        :param objid: resource object id.
        :param name: resource name.
        :param rtype: resource type.
        :param container: container id
        :param ext_id: physical resource id [default='']
        :param active: Status. If True is active [default=True]
        :param desc: description
        :param attribute: attribute
        :param parent_id: parent id
        :return: :class:`Resource`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.add_entity(Resource, objid, name, rtype, container, 
                              ext_id=ext_id, active=active, desc=desc, 
                              attribute=attribute, parent_id=parent_id)
        return res  

    def get_resource_tags(self, resource, *args, **kvargs):
        """Get resource tags.
        
        :param resource: resource id
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of ResourceTag paginated, total
        :raises QueryError: raise :class:`QueryError`
        """
        tables = [('tags_resources', 't4')]
        filters = [
            'AND t3.id=t4.tag_id',
            'AND t4.resource_id=:resource']        
        res, total = self.get_paginated_entities(ResourceTag, filters=filters, 
                                                 tables=tables, resource=resource, 
                                                 *args, **kvargs)
        return res, total
    
    @transaction
    def add_resource_tag(self, resource, tag):
        """Add a tag to a resource.
        
        :param Resource resource: resource instance
        :param ResourceTag tag: tag instance.
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        tags = resource.tag
        if tag not in tags:
            resource.tag.append(tag)
        self.logger.debug2('Add tag %s to resource: %s' % (tag, resource))
        return True
    
    @transaction
    def remove_resource_tag(self, resource, tag):
        """Remove a tag from a resource.
        
        :param resource Resource: resource instance
        :param tag ResourceTag: tag instance.
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        tags = resource.tag
        if tag in tags:
            tags.remove(tag)
        self.logger.debug2('Remove tag %s from resource: %s' % (tag, resource))
        return True

    def update_resource(self, *args, **kvargs):
        """Update resource.
    
        :param int oid: entity id.
        :param name: resource name. [optional]
        :param desc: new description [optional]
        :param active: If True is active [optional]
        :param state: resource state [optional]
        :param attribute: resource attribute [optional]
        :param parent_id: new parent id [optional]
        :param ext_id: new external id [optional]
        :return: :class:`Resource`
        :raises TransactionError: raise :class:`TransactionError`
        """
        attribute = kvargs.pop('attribute', None)
        if isinstance(attribute, dict) or isinstance(attribute, list):
            # if attribute is not None and isinstance(attribute, dict):
            kvargs['attribute'] = jsonDumps(attribute)
        res = self.update_entity(Resource, *args, **kvargs)
        return res
    
    def update_resource_state(self, oid, state, last_error=''):
        """Update resource state.
    
        :param int oid: entity id.
        :param state: resource state
        :param last_error: last error
        :return: :class:`Resource`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.update_entity(Resource, oid=oid, state=state, last_error=last_error)
        return res
    
    def delete_resource(self, *args, **kvargs):
        """Remove resource softly.
        
        :param int oid: entity id.
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        kvargs['state'] = ResourceState.DELETED
        kvargs['remove_date'] = datetime.today()
        kvargs['expiry_date'] = datetime.today()
        kvargs['active'] = False
        res = self.update_entity(Resource, *args, **kvargs)
        return res
    
    @transaction
    def expunge_resource(self, *args, **kvargs):
        """Remove resource.
        
        :param int oid: entity id. [optional]
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        # self.del_jobs(resource_id=kvargs['oid'])
        res = self.remove_entity(Resource, *args, **kvargs)
        return res
    
    #
    # job
    #
    @query
    def get_jobs(self, job=None, name=None, resource=None, container=None, resources=None, from_date=None, size=10):
        """Get jobs

        :param job: job id. [optional]
        :param name: job name. [optional]
        :param resource: resource id. [optional]
        :param resources: resource ids. [optional]
        :param container: container id. [optional]
        :param from_date: filter start date > from_date [optional]
                :param size: max number of jobs [default=10]
        :return: list of ResourceJob instance
        :raises TransactionError: raise :class:`TransactionError`        
        """        
        session = self.get_session()

        if job is not None:  
            rec = session.query(ResourceJob).filter_by(job=job)
        elif name is not None:
            rec = session.query(ResourceJob).filter_by(name=name)
        elif resource is not None:
            rec = session.query(ResourceJob).filter_by(resource_id=resource)
        elif resources is not None:
            rec = session.query(ResourceJob).filter(ResourceJob.resource_id.in_(resources))
        elif container is not None:
            rec = session.query(ResourceJob).filter_by(container_id=container)
        elif from_date is not None:
            rec = session.query(ResourceJob).filter(ResourceJob.creation_date >= from_date)
        else:
            rec = session.query(ResourceJob)

        count = rec.count()
        res = rec.order_by(desc(ResourceJob.creation_date)).limit(size).all()
            
        self.logger.debug2('Get resource job: %s' % truncate(res))
        return res, count
    
    def add_job(self, job, name, resource_id=None, container_id=None, params={}):
        """Add job.
    
        :param job: resource job id.
        :param name: resource job name.
        :param resource_id: id of the resource associated.
        :param container_id: id of the container associated.
        :param params: resource job params.
        :return: :class:`ResourceTag`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.add_entity(ResourceJob, job, name, resource_id, container_id, params=params)
        return res
    
    @transaction
    def del_jobs(self, resource_id=None, container_id=None):
        """Delete all jobs associated to a resource.
    
        :param resource_id: id of the resource associated.
        :param container_id: id of the container associated.
        :return: True
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()

        if resource_id is not None:
            rec = session.query(ResourceJob).filter_by(resource_id=resource_id).all()
        elif container_id is not None:
            rec = session.query(ResourceJob).filter_by(container_id=container_id).all()
        
        for item in rec:
            session.delete(item)
        self.logger.debug2('Remove resource %s jobs' % resource_id)  
        return True
    
    #
    # link
    #
    def count_links(self):
        """Get links count.
        
        :return: links number
        :raises QueryError: raise :class:`QueryError`  
        """
        return self.count_entities(ResourceLink)
    
    @query    
    def is_linked(self, start_resource, end_resource):
        """Verifiy if two resources are linked

        :param start_resource: start resource id
        :param end_resource: end resource id
        :return: list of :class:`ResourceLink`
        :raises TransactionError: raise :class:`TransactionError`
        """           
        session = self.get_session()
        res = session.query(ResourceLink).filter_by(start_resource_id=start_resource)\
            .filter_by(end_resource_id=end_resource)
        res = res.all()
            
        if len(res) == 0:
            resp = False
        else:
            resp = True
        self.logger.warning('Check resource %s is linked to resource %s: %s' % (start_resource, end_resource, resp))
        return resp
    
    def get_links(self, *args, **kvargs):
        """Get links.

        :param start_resources: start resource ids [optional]
        :param start_resource: start resource id [optional]
        :param end_resource: end resource id [optional]
        :param resource: start or end resource id [optional]
        :param type: link type or partial type with % as jolly character [optional]
        :param resourcetags: list of tags comma separated. All tags in the list must be met [optional]
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of ResourceLink     
        :raises QueryError: raise :class:`QueryError`
        """
        filters = []
        custom_select = None
        if kvargs.get('resource', None) is not None:
            filters.append('AND (end_resource_id=:resource or start_resource_id=:resource)')
        else:
            if kvargs.get('start_resources', None) is not None:
                filters.append('AND start_resource_id in start_resources')
            elif kvargs.get('start_resource', None) is not None:
                filters.append('AND start_resource_id=:start_resource')
            if kvargs.get('end_resource', None) is not None:
                filters.append('AND end_resource_id=:end_resource')
        if kvargs.get('type', None) is not None:
            filters.append('AND t3.type like :type')
        if kvargs.get('resourcetags', None) is not None:
            custom_select = '(SELECT t1.*, GROUP_CONCAT(DISTINCT t2.name ORDER BY t2.name) as tags '\
                     'FROM resource_link t1, resource_tag t2, tags_resources_links t3 '\
                     'WHERE t3.tag_id=t2.id and t3.link_id=t1.id '\
                     'and (t2.name in :resourcetag_list) '\
                     'GROUP BY t1.id)'
            kvargs = self.order_query_resourcetags(kvargs)
            filters.append('AND t3.tags=:resourcetags')
        
        res, total = self.get_paginated_entities(ResourceLink, filters=filters, custom_select=custom_select,
                                                 *args, **kvargs)     
        return res, total

    def get_links_with_cache(self, resource, link_type, *args, **kvargs):
        """Get links with cache

        :param resource: start or end resource id [optional]
        :param link_type: link type or partial type [optional]
        :return: list of ResourceLink
        :raises QueryError: raise :class:`QueryError`
        """
        filters = []
        filters.append('AND (end_resource_id=:resource or start_resource_id=:resource)')
        kvargs['resource'] = resource

        links = self.get_entities_with_cache(ResourceLink, resource, filters=filters, *args, **kvargs)
        res = []
        for link in links:
            if link_type is not None and link.type.find(link_type) >= 0:
                continue
            res.append(link)

        return res

    def get_links_from_tags(self, *args, **kvargs):
        """Get Links with all the of tags specified.
        
        :param resource_tags: list of tags that links must have
        :return: list of Link instances
        :raises QueryError: raise :class:`QueryError`          
        """
        tables = [('tags_Links', 't4'), ('resource_tag', 't5')]
        select_fields = ['GROUP_CONCAT(t5.value) as tags']
        filters = [
            'AND t4.tag_id=t5.id',
            'AND t3.id=t4.Link_id',
            'AND t5.value IN :resource_tags']
        res, total = self.get_paginated_entities(ResourceLink, filters=filters,
                                                 select_fields=select_fields,
                                                 tables=tables, *args, **kvargs)
        return res, total
        
    def add_link(self, objid=None, name=None, ltype=None, start_resource=None, end_resource=None, attributes=''):
        """Add link.

        :param objid:  link objid
        :param name:  link name
        :param ltype:  link type
        :param start_resource: start resource reference
        :param end_resource: end resource reference
        :param attributes: link attributes
        :return: :class:`ResourceLink`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.add_entity(ResourceLink, objid, name, ltype, start_resource, end_resource, attributes=attributes)
        return res  
        
    def update_link(self, *args, **kvargs):
        """Update link.

        :param int oid: entity id. [optional]
        :param name: link name [optional]
        :param ltype: link type [optional]
        :param start_resource: start_resource id [optional]
        :param end_resource: end_resource id [optional]
        :param attributes: resource attributes [optional]
        :return: :class:`ResourceLink`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.update_entity(ResourceLink, *args, **kvargs)
        return res         
        
    def delete_link(self, *args, **kvargs):
        """Remove link.

        :param int oid: entity id. [optional]
        :return: :class:`ResourceLink`
        :raises TransactionError: raise :class:`TransactionError`
        """
        res = self.remove_entity(ResourceLink, *args, **kvargs)
        return res
    
    def get_link_tags(self, link, *args, **kvargs):
        """Get link tags.
        
        :param link: link id
        :param page: entities list page to show [default=0]
        :param size: number of entities to show in list per page [default=0]
        :param order: sort order [default=DESC]
        :param field: sort field [default=id]
        :return: list of ResourceTag paginated, total
        :raises QueryError: raise :class:`QueryError`
        """
        tables = [('tags_resources_links', 't4')]
        filters = [
            'AND t3.id=t4.tag_id',
            'AND t4.link_id=:link']          
        res, total = self.get_paginated_entities(ResourceTag, filters=filters, 
                                                 tables=tables, link=link, 
                                                 *args, **kvargs)
        return res, total
    
    @transaction
    def add_link_tag(self, link, tag):
        """Add a tag to a link.
        
        :param link ResourceLink: link instance
        :param tag Tag: tag instance.
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        tags = link.tag
        if tag not in tags:
            tags.append(tag)
        self.logger.debug2('Add tag %s to link: %s' % (tag, link))
        return True
    
    @transaction
    def remove_link_tag(self, link, tag):
        """Remove a tag from a link.
        
        :param link Resource: link instance
        :param tag Tag: tag instance.
        :return: True if operation is successful, False otherwise
        :rtype: bool
        :raises TransactionError: raise :class:`TransactionError`
        """
        session = self.get_session()
        tags = link.tag
        if tag in tags:
            tags.remove(tag)
        self.logger.debug2('Remove tag %s from link: %s' % (tag, link))
        return True
