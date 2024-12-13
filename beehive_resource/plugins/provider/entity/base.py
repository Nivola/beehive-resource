# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import get_value, import_class
from beehive_resource.container import Resource, AsyncResource
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_volume_type import (
    OpenstackVolumeType,
)
from beehive_resource.plugins.vsphere.entity.nsx_security_group import NsxSecurityGroup
from beehive_resource.plugins.vsphere.entity.vs_flavor import VsphereFlavor
from beehive_resource.plugins.vsphere.entity.vs_folder import VsphereFolder
from beehive_resource.plugins.vsphere.entity.vs_dvpg import VsphereDvpg
from beehive_resource.plugins.vsphere.entity.nsx_logical_switch import NsxLogicalSwitch
from beehive_resource.plugins.openstack.entity.ops_project import OpenstackProject
from beehive_resource.plugins.openstack.entity.ops_security_group import (
    OpenstackSecurityGroup,
)
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork


def get_task(task_name):
    return "%s.task.%s" % (__name__.rstrip(".entity.base"), task_name)


def orchestrator_mapping(mapping_type, mapping_index):
    """

    :param mapping_type: mapping type like vsphere, openstack
    :param mapping_index: mapping index. 0, 1, 2, ...
    """
    orchestrator_map = {
        "vsphere": [
            VsphereFolder.objdef,
            NsxSecurityGroup.objdef,
            VsphereDvpg.objdef,
            NsxLogicalSwitch.objdef,
            VsphereFlavor.objdef,
        ],
        "openstack": [
            OpenstackProject.objdef,
            OpenstackSecurityGroup.objdef,
            OpenstackNetwork.objdef,
            OpenstackNetwork.objdef,
            OpenstackVolumeType.objdef,
        ],
    }
    return orchestrator_map[mapping_type][mapping_index]


class LocalProviderResource(AsyncResource):
    """ """

    objdef = "Provider.Resource"
    objuri = "%s/nrs/%s"
    objname = "local_resources"
    objdesc = "Provider resource"

    create_task = "beehive_resource.plugins.provider.task_v2.provider_resource_add_task"
    import_task = "beehive_resource.plugins.provider.task_v2.provider_resource_import_task"
    update_task = "beehive_resource.plugins.provider.task_v2.provider_resource_update_task"
    patch_task = "beehive_resource.plugins.provider.task_v2.provider_resource_patch_task"
    delete_task = "beehive_resource.plugins.provider.task_v2.provider_resource_delete_task"
    expunge_task = "beehive_resource.plugins.provider.task_v2.provider_resource_expunge_task"
    action_task = "beehive_resource.plugins.provider.task_v2.provider_resource_action_task"

    def __init__(self, *args, **kvargs):
        Resource.__init__(self, *args, **kvargs)

        self.tag_name = None
        self.child_classes = []

    def info(self):
        """Get infos.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # verify permissions
        info = Resource.info(self)
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Resource.detail(self)
        return info

    def get_configs(self):
        """Get resource configs"""
        return self.attribs.get("configs", {})

    # def get_orchestrators(self, index=True):
    #     """Get availability zone site orchestrators
    #     """
    #     return None

    def __get_linked_resources(self, link_type, container=None, objdef=None):
        """Get linked resources

        :param link_type:
        :param container:
        :param objdef:
        :return:
        """
        try:
            container_id = None
            if container is not None:
                container = self.controller.get_container(container)
                container_id = container.oid

            res = self.manager.get_linked_resources_internal(
                resource=self.oid,
                link_type=link_type,
                container_id=container_id,
                objdef=objdef,
            )
            resp = []
            for entity in res:
                entity_class = import_class(entity.objclass)
                obj = entity_class(
                    self.controller,
                    oid=entity.id,
                    objid=entity.objid,
                    name=entity.name,
                    active=entity.active,
                    desc=entity.desc,
                    model=entity,
                )
                obj.container = container
                resp.append(obj)
            return resp
        except:
            self.logger.warn("", exc_info=1)
            return []

    # def get_linked_resources_internal(self, link_type, container=None, objdef=None):
    #     res = self.__get_linked_resources(link_type, container, objdef)
    #     self.logger.debug('Get linked resources: %s' % res)
    #     return res

    def get_physical_resources(self, cid, objdef):
        """Get remote resources in a certain orchestrator with an objdef

        :param cid: orchestrator id
        :param objdef: resource type
        """
        res = self.__get_linked_resources("relation", container=cid, objdef=objdef)
        return res

    def get_physical_resource_from_container(self, cid, objdef):
        """Get remote resource in a specific orchestrator

        :param cid: orchestrator id
        :param objdef: resource type
        """
        res = self.__get_linked_resources("relation", container=cid, objdef=objdef)

        if len(res) == 0:
            raise ApiManagerError(
                "No remote resource found for orchestrator %s and type %s" % (cid, objdef),
                code=404,
            )
        res = res[0]
        return res

    def get_physical_resource(self, objdef):
        """Get remote resource in a specific orchestrator

        :param objdef: resource type
        """
        res = self.__get_linked_resources("relation", objdef=objdef)

        if len(res) == 0:
            raise ApiManagerError("No remote resource found for type %s" % objdef, code=404)
        res = res[0]
        res.container = self.controller.get_container(res.model.container_id)
        res.post_get()
        return res

    def get_aggregated_resource(self):
        """Get aggregated resource"""
        res = self.__get_linked_resources("relation.%")

        if len(res) == 0:
            raise ApiManagerError("No aggregated resource found", code=404)
        res = res[0]
        res.container = self.controller.get_container(res.model.container_id)
        # res.post_get()
        return res

    def set_state(self, state):
        """Set resource state

        :param state: resource state. Valid value are ACTIVE and ERROR
        :return: True
        """
        Resource.set_state(self, state)

        # get zone childs
        childs, total = self.get_linked_resources(link_type_filter="relation", with_perm_tag=False, run_customize=False)
        for child in childs:
            child.set_state(state)

        return True
