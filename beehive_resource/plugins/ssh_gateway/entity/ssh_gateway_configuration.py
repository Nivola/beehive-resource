# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

import imp
import logging
from beehive_resource.plugins.ssh_gateway.entity import SshGatewayResource
from beehive_resource.util import create_resource,expunge_resource
from beehive.common.task_v2 import run_async

from typing import TYPE_CHECKING, List, TypeVar

logger = logging.getLogger(__name__)

T_SSHGWCONF = TypeVar('T_SSHGWCONF',bound="SshGatewayConfiguration")
from beehive_resource.controller import ResourceController
T_RESCTRL = TypeVar('T_RESCTRL',bound="ResourceController")

if TYPE_CHECKING:
    from beehive_resource.plugins.ssh_gateway.controller import SshGatewayContainer

class SshGatewayConfiguration(SshGatewayResource):
    objdef = 'SshGateway.Configuration'
    objuri = 'configurations'
    objname = 'configuration'
    objdesc = 'Ssh Gateway Configuration'
    
    default_tags = ['sshgateway']
    
    def __init__(self, *args, **kvargs):
        """ """
        SshGatewayResource.__init__(self, *args, **kvargs)


    def info(self):
        """Get info. """
        info = SshGatewayResource.info(self)
        info['details'] = self.get_attribs()
        return info


    def detail(self):
        """ result of get when id is specified """
        info = SshGatewayResource.detail(self)
        return info


    @staticmethod
    def customize_list( controller: T_RESCTRL,
                        entities: List[T_SSHGWCONF],
                        container: 'SshGatewayContainer', *args, **kvargs):
        """ After list ( = get api, without id) """
        return entities


    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        res_id = kvargs.pop('res_id',None)
        gw_type = kvargs.pop('gw_type',None)

        kvargs['attribute'] = {
            'gw_type': gw_type,
        }
        
        kvargs['attribute'].pop('has_quotas',None) # needed?

        if res_id:
            kvargs['attribute']['res_id'] = res_id
        
        return kvargs


    @run_async(action='insert', alias='create_ssh_gw_configuration')
    @create_resource()
    def do_create(self, **params):
        """method to execute to make custom resource operations useful to complete create

        :param params: custom params required by task
        :return:
        """
        eid = params.get('entity_id',True)
        return eid


    @run_async(action='delete', alias='expunge_ssh_gw_confs')
    @expunge_resource()
    def do_expunge(self, **params):
        """method to execute to make custom resource operations useful to complete expunge

        :param params: custom params required by task
        :return:
        """
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        self.logger.warn('I am the do_expunge')
        self.logger.warn('$$$$$$$$$$$$$$$$$$$$$$$$')
        