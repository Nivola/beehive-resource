# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte

from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator
from .entity.ssh_gateway_configuration import SshGatewayConfiguration

from typing import TypeVar
T_SSHGWCONT = TypeVar('T_SSHGWCONT',bound="SshGatewayContainer")

class SshGatewayContainer(Orchestrator):
    """Ssh gateway container
    :param connection: json string like {}
    """
    objdef = 'SshGateway'
    objdesc = 'Ssh Gateway Container'
    objuri = 'nrs/sshgateway'
    version = 'v1.0'
    
    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)
        
        self.child_classes = [
            SshGatewayConfiguration
        ]

        self.conn = None
        
    def ping(self):
        """Ping container.
        
        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        res = False
        try:
           # decrypt password
            pwd = self.conn_params.get('pwd')
            pwd = self.decrypt_data(pwd)
            user = self.conn_params.get('user')
            port = self.conn_params.get('port')
            hosts = self.conn_params.get('hosts')

            for h in hosts:
                # TODO
                res = True
                # try reaching them in order
                # as soon as I get a reply, success
                # self.conn = beedrones method
                #res = self.conn.ping()

                # maybe simple flask api running on port to check service status and/or restart it
                # or just specific ssh user+psw to execute remote scripts
                if res:
                    break
        except:
            self.logger.warning('ping ko', exc_info=True)
        self.container_ping = res
        return res
            
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
        
        # encrypt pwd
        conn['pwd'] = controller.encrypt_data(conn['pwd'])

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

