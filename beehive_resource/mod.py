# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive.module.basic.views.status import StatusAPI
from beecell.simple import get_class_name
from beehive.common.apimanager import ApiModule
from beehive_resource.view import ResourceAPI
from beehive_resource.controller import ResourceController
from beehive_resource.views.entity import ResourceEntityAPI


class ResourceModule(ApiModule):
    """Beehive Resource Module
    
    """
    def __init__(self, api_manger):
        self.name = 'ResourceModule'
        self.base_path = 'nrs'
        
        ApiModule.__init__(self, api_manger, self.name)
        
        self.apis = [
            ResourceAPI,
            ResourceEntityAPI,
            StatusAPI
        ]
        self.controller = ResourceController(self)

    def get_controller(self):
        return self.controller

    def set_apis(self, apis):
        self.apis.extend(apis)
        for api in apis:
            self.logger.debug('Set api: %s' % get_class_name(api))

    def add_container(self, name, container_class):
        self.controller.add_container_class(name, container_class)
        self.logger.debug('Add container: %s, %s' % (name, get_class_name(container_class)))