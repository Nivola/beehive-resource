# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from celery.utils.log import get_task_logger

from beehive_resource.plugins.provider.entity.vpc import SiteNetwork, PrivateNetwork
from beehive_resource.tasks import ResourceJobTask
from beehive.common.task.manager import task_manager
from beehive.common.task.job import job_task

logger = get_task_logger(__name__)


@task_manager.task(bind=True, base=ResourceJobTask)
@job_task()
def task_vpc_assign_network(self, options, network_id):
    """Create vpc network.

    **Parameters:**

        * **options** (tupla): Tupla with some useful options.
            (class_name, objid, job, job id, start time,
             time before new query, user)
        * **network_id**: site or private network id
        * **sharedarea** (dict):

            * **cid** (int): container id

    **Return:**

    """
    self.set_operation()
    params = self.get_shared_data()
    
    # input params
    cid = params.get('cid')
    oid = params.get('id')
    self.update('PROGRESS', msg='Set configuration params')

    # get provider
    self.get_session()
    resource = self.get_resource(oid)
    network = self.get_resource(network_id)
    self.update('PROGRESS', msg='Get vpc %s resource' % oid)

    # link network to vpc
    self.get_session()
    if isinstance(network, SiteNetwork):
        site_id = network.parent_id
        attributes = {'reuse': True}
    if isinstance(network, PrivateNetwork):
        site_id = network.get_site().oid
        attributes = {}

    resource.add_link('%s-%s-network-link' % (oid, network_id), 'relation.%s' % site_id, network_id,
                      attributes=attributes)
    self.update('PROGRESS', msg='Link network %s to vpc %s' % (network_id, oid))

    return oid

