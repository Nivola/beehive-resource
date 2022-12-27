# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

import gevent
from celery.utils.log import get_task_logger
from celery import chain, chord, group, signature
from beecell.simple import get_value, import_class
from beehive_resource.tasks import ResourceJobTask, ResourceJob,\
    create_resource_pre, create_resource_post, expunge_resource_pre,\
    expunge_resource_post, update_resource_post,\
    update_resource_pre
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task, job, task_local, Job
from beehive.common.task.util import end_task, start_task
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beedrones.openstack.client import OpenstackNotFound

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_create_entity(self, options):
    """Create openstack share
    
    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.share_proto: The Shared File Systems protocol. A valid value is NFS, CIFS,
        GlusterFS, HDFS, or CephFS. CephFS supported is starting with API v2.13.
    :param sharedarea.size: The share size, in GBs. The requested share size cannot be greater than
        the allowed GB quota. To view the allowed quota, issue a get limits request.
    :param sharedarea.share_type: (Optional) The share type name. If you omit this parameter, the
        default share type is used. To view the default share type set by the administrator, issue a list
        default share types request. You cannot specify both the share_type and volume_type parameters.
    :param sharedarea.snapshot_id: (Optional) The UUID of the share's base snapshot.
    :param sharedarea.is_public** (:py:class:`bool`): (Optional) The level of visibility for the share. Set to true to
        make share public. Set to false to make it private. Default value is false.
    :param sharedarea.share_group_id :(Optional) The UUID of the share group.
    :param sharedarea.metadata: (Optional) One or more metadata key and value pairs as a dictionary of strings.
    :param sharedarea.availability_zone: (Optional) The availability zone.
    :return: Openstack share id
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    oid = params.get('id')
    parent_id = params.get('parent')
    name = params.get('name')
    desc = params.get('desc')
    proto = params.get('share_proto')
    size = params.get('size')
    share_type = params.get('share_type')
    is_public = params.get('is_public')
    share_group_id = params.get('share_group_id')
    metadata = params.get('metadata')
    availability_zone = params.get('availability_zone')
    self.update('PROGRESS', msg='Get configuration params')
    
    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila

    # create openstack share
    inst = conn.share.create(proto, size, name=name, description=desc, share_type=share_type, is_public=is_public,
                             availability_zone=availability_zone, share_group_id=share_group_id, metadata=metadata)
    inst_id = inst['id']
    self.update('PROGRESS', msg='Create share %s - Starting' % inst_id)

    # set ext_id
    container.update_resource(oid, ext_id=inst_id)
    self.update('PROGRESS', msg='Set share remote openstack id %s' % inst_id)

    # loop until entity is not stopped or get error
    while True:
        inst = OpenstackShare.get_remote_share(container.controller, inst_id, container, inst_id)
        # inst = conn.share.get(inst_id)
        status = inst['status']
        if status == 'available':
            break
        if status == 'error':
            self.update('PROGRESS', msg='Create share %s - Error' % inst_id)
            raise Exception('Can not create share %s' % name)
        
        # update task
        self.update('PROGRESS')       

        # sleep a little
        gevent.sleep(task_local.delta)
    self.update('PROGRESS', msg='Create share %s - Completed' % inst_id)          

    # save current data in shared area
    params['ext_id'] = inst_id
    params['attrib'] = None
    self.set_shared_data(params)
    self.update('PROGRESS', msg='Update shared area')
    
    return inst_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_update_entity(self, options):
    """Update openstack share

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :return: None
    """
    # get params from shared data
    params = self.get_shared_data()

    return None


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_delete_entity(self, options):
    """Delete openstack share

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :return:
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    parent_id = params.get('parent')
    ext_id = params.get('ext_id')
    self.update('PROGRESS', msg='Get configuration params')
    
    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila
    resource = container.get_resource_by_extid(ext_id)

    if self.is_ext_id_valid(ext_id) is True:
        # check share exists
        try:
            conn.share.get(ext_id)
        except:
            self.update('PROGRESS', msg='Share %s does not exist anymore' % ext_id)
            return None

        # remove share
        conn.share.delete(ext_id)
        self.update('PROGRESS', msg='Delete share %s - Starting' % ext_id)

        # loop until entity is not deleted or get error
        while True:
            inst = OpenstackShare.get_remote_share(container.controller, ext_id, container, ext_id)
            # inst = conn.share.get(ext_id)
            status = inst.get('status', 'deleted')
            if status == 'deleted':
                break
            elif status == 'error' or status == 'error_deleting':
                self.update('PROGRESS', msg='Delete share %s - Error' % ext_id)
                raise Exception('Can not delete share %s' % ext_id)

            self.update('PROGRESS')
            gevent.sleep(task_local.delta)

        resource.update_internal(ext_id=None)
        self.update('PROGRESS', msg='Delete stack %s - Completed' % ext_id)
    
    return ext_id


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_grant_add(self, options):
    """Add grant to share

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.parent: parent id
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.access_level: The access level to the share. To grant or deny access to a share,
        you specify one of the following share access levels: - rw. Read and write (RW) access. - ro.
        Read- only (RO) access.
    :param sharedarea.access_type: The access rule type. A valid value for the share access rule type is
        one of the following values: - ip. Authenticates an instance through its IP address. A valid format is
        XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0. - cert. Authenticates an instance through a TLS
        certificate. Specify the TLS identity as the IDENTKEY. A valid value is any string up to 64 characters
        long in the common name (CN) of the certificate. The meaning of a string depends on its interpretation.
        - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain
        some special characters and is from 4 to 32 characters long.
    :param sharedarea.access_to: The value that defines the access. The back end grants or denies the
        access to it. A valid value is one of these values: - ip. Authenticates an instance through its IP
        address. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0. - cert. Authenticates
        an instance through a TLS certificate. Specify the TLS identity as the IDENTKEY. A valid value is any
        string up to 64 characters long in the common name (CN) of the certificate. The meaning of a string
        depends on its interpretation. - user. Authenticates by a user or group name. A valid value is an
        alphanumeric string that can contain some special characters and is from 4 to 32 characters long.
    :return: True
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    parent_id = params.get('parent')
    ext_id = params.get('ext_id')
    access_level = params.get('access_level')
    access_type = params.get('access_type')
    access_to = params.get('access_to')
    self.update('PROGRESS', msg='Get configuration params')

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila

    if self.is_ext_id_valid(ext_id) is True:
        conn.share.action.grant_access(ext_id, access_level, access_type, access_to)
        self.update('PROGRESS', msg='Add grant to share %s: %s - %s - %s' %
                                     (ext_id, access_level, access_type, access_to))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_grant_remove(self, options):
    """Remove grant from share

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.parent: parent id
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.access_id: The UUID of the access rule to which access is granted.
    :return: True
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    parent_id = params.get('parent')
    ext_id = params.get('ext_id')
    access_id = params.get('access_id')
    self.update('PROGRESS', msg='Get configuration params')

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila

    if self.is_ext_id_valid(ext_id) is True:
        conn.share.action.revoke_access(ext_id, access_id)
        self.update('PROGRESS', msg='Remove grant %s from share %s' % (ext_id, access_id))

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_size_extend(self, options):
    """Extend share size

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.parent: parent id
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.new_size: New size of the share, in GBs.
    :return: True
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    parent_id = params.get('parent')
    ext_id = params.get('ext_id')
    new_size = params.get('new_size')
    self.update('PROGRESS', msg='Get configuration params')

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila

    if self.is_ext_id_valid(ext_id) is True:
        # remove share
        conn.share.action.extend(ext_id, new_size)
        self.update('PROGRESS', msg='Extend share %s size - Starting' % ext_id)

        # loop until entity is not deleted or get error
        while True:
            inst = OpenstackShare.get_remote_share(container.controller, ext_id, container, ext_id)
            # inst = conn.share.get(ext_id)
            status = inst['status']
            if status == 'available':
                break
            elif status == 'error' or status == 'extending_error':
                self.update('PROGRESS', msg='Extend share %s size - Error' % ext_id)
                raise Exception('Can not Extend share %s size ' % ext_id)

            self.update('PROGRESS')
            gevent.sleep(task_local.delta)

        self.update('PROGRESS', msg='Extend share %s size - Completed' % ext_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_size_shrink(self, options):
    """Shrink share size

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.parent: parent id
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.new_size: New size of the share, in GBs.
    :return: True
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    parent_id = params.get('parent')
    ext_id = params.get('ext_id')
    new_size = params.get('new_size')
    self.update('PROGRESS', msg='Get configuration params')

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila

    if self.is_ext_id_valid(ext_id) is True:
        # remove share
        conn.share.action.shrink(ext_id, new_size)
        self.update('PROGRESS', msg='Shrink share %s size - Starting' % ext_id)

        # loop until entity is not deleted or get error
        while True:
            inst = OpenstackShare.get_remote_share(container.controller, ext_id, container, ext_id)
            # inst = conn.share.get(ext_id)
            status = inst['status']
            if status == 'available':
                break
            elif status == 'error' or status == 'shrinking_error' or status == 'shrinking_possible_data_loss_error':
                self.update('PROGRESS', msg='Shrink share %s size - Error' % ext_id)
                raise Exception('Can not Shrink share %s size ' % ext_id)

            self.update('PROGRESS')
            gevent.sleep(task_local.delta)

        self.update('PROGRESS', msg='Shrink share %s size - Completed' % ext_id)

    return True


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def share_revert_to_snapshot(self, options):
    """Revert share to snapshot

    :param options: config options. (class_name, objid, job, job id, start time, time before new query, user)
    :param sharedarea:
    :param sharedarea.cid: container id
    :param sharedarea.id: resource id
    :param sharedarea.parent: parent id
    :param sharedarea.ext_id: resource physical id
    :param sharedarea.snapshot_id: The UUID of the snapshot.
    :return: True
    """
    params = self.get_shared_data()

    cid = params.get('cid')
    parent_id = params.get('parent')
    ext_id = params.get('ext_id')
    snapshot_id = params.get('snapshot_id')
    self.update('PROGRESS', msg='Get configuration params')

    # get container
    self.get_session()
    container = self.get_container(cid, projectid=parent_id)
    conn = container.conn.manila

    if self.is_ext_id_valid(ext_id) is True:
        conn.share.action.revert(ext_id, snapshot_id)
        self.update('PROGRESS', msg='Revert share %s to snapshot: %s - %s - %s' % (ext_id, snapshot_id))

    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='insert', delta=3)
def job_share_create(self, objid, params):
    """Create openstack share
    
    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params    
    :param params.objid: resource objid
    :param params.parent: resource parent id
    :param params.cid: container id
    :param params.name: resource name
    :param params.desc: resource desc
    :param params.ext_id: resource ext_id
    :param params.active: resource active
    :param params.attribute: attributes
    :param params.tags: comma separated resource tags to assign [default='']
    :param params.share_proto: The Shared File Systems protocol. A valid value is NFS, CIFS,
        GlusterFS, HDFS, or CephFS. CephFS supported is starting with API v2.13.
    :param params.size: The share size, in GBs. The requested share size cannot be greater than
        the allowed GB quota. To view the allowed quota, issue a get limits request.
    :param params.share_type: (Optional) The share type name. If you omit this parameter, the
        default share type is used. To view the default share type set by the administrator, issue a list
        default share types request. You cannot specify both the share_type and volume_type parameters.
    :param params.is_public** (:py:class:`bool`): (Optional) The level of visibility for the share. Set to true to make 
        hare public. Set to false to make it private. Default value is false.
    :param params.snapshot_id: (Optional) The UUID of the share's base snapshot.
    :param params.share_group_id :(Optional) The UUID of the share group.
    :param params.metadata: (Optional) One or more metadata key and value pairs as a dictionary of strings.
    :param params.availability_zone: (Optional) The availability zone.
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)
    
    Job.create([
        end_task,
        create_resource_post,
        share_create_entity,
        create_resource_pre,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='update', delta=3)
def job_share_update(self, objid, params):
    """Update openstack share
    
    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.uuid: resource uuid
    :param params.objid: resource objid
    :param params.ext_id: resource physical id
    :param params.name: resource name
    :param params.desc: resource desc
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)    

    Job.create([
        end_task,
        update_resource_post,
        share_update_entity,
        update_resource_pre,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='delete', delta=3)
def job_share_delete(self, objid, params):
    """Delete openstack share
    
    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.parent: parent id
    :param params.uuid: resource uuid
    :param params.objid: resource objid
    :param params.ext_id: resource physical id
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)    
    
    Job.create([
        end_task,
        expunge_resource_post,
        share_delete_entity,
        expunge_resource_pre,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='update', delta=1)
def job_share_grant_add(self, objid, params):
    """Add grant to share

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.parent: parent id
    :param params.ext_id: resource physical id
    :param params.access_level: The access level to the share. To grant or deny access to a share,
        you specify one of the following share access levels: - rw. Read and write (RW) access. - ro.
        Read- only (RO) access.
    :param params.access_type: The access rule type. A valid value for the share access rule type is
        one of the following values: - ip. Authenticates an instance through its IP address. A valid format is
        XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0. - cert. Authenticates an instance through a TLS
        certificate. Specify the TLS identity as the IDENTKEY. A valid value is any string up to 64 characters
        long in the common name (CN) of the certificate. The meaning of a string depends on its interpretation.
        - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain
        some special characters and is from 4 to 32 characters long.
    :param params.access_to: The value that defines the access. The back end grants or denies the
        access to it. A valid value is one of these values: - ip. Authenticates an instance through its IP
        address. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX. For example 0.0.0.0/0. - cert. Authenticates
        an instance through a TLS certificate. Specify the TLS identity as the IDENTKEY. A valid value is any
        string up to 64 characters long in the common name (CN) of the certificate. The meaning of a string
        depends on its interpretation. - user. Authenticates by a user or group name. A valid value is an
        alphanumeric string that can contain some special characters and is from 4 to 32 characters long.
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        share_grant_add,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='update', delta=1)
def job_share_grant_remove(self, objid, params):
    """Remove grant from share

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.parent: parent id
    :param params.ext_id: resource physical id
    :param params.access_id: The UUID of the access rule to which access is granted.
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        share_grant_remove,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='update', delta=3)
def job_share_size_extend(self, objid, params):
    """Extend share size

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.parent: parent id
    :param params.ext_id: resource physical id
    :param params.new_size: New size of the share, in GBs.
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        share_size_extend,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='update', delta=3)
def job_share_size_shrink(self, objid, params):
    """Shrink share size

    :param objid: objid of the resource. Ex. 110//2222//334//*
    :param params: input params
    :param params.cid: container id
    :param params.id: resource id
    :param params.parent: parent id
    :param params.ext_id: resource physical id
    :param params.new_size: New size of the share, in GBs.
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        share_size_shrink,
        start_task
    ], ops).delay()
    return True


@task_manager.task(bind=True, base=ResourceJob)
@job(entity_class=OpenstackShare, name='update', delta=3)
def job_share_revert_to_snapshot(self, objid, params):
    """Revert share to snapshot

    :param str objid: objid of the resource. Ex. 110//2222//334//*
    :param dict params: input params
    :param int params.cid: container id
    :param int params.id: resource id
    :param str params.parent: parent id
    :param str params.ext_id: resource physical id
    :param int params.snapshot_id: The UUID of the snapshot.
    :return: True
    """
    ops = self.get_options()
    self.set_shared_data(params)

    Job.create([
        end_task,
        share_revert_to_snapshot,
        start_task
    ], ops).delay()
    return True
