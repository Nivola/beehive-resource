# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import id_gen
import logging

from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.ontap.entity import OntapNetappResource
from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm

logger = logging.getLogger(__name__)


class OntapNetappVolume(OntapNetappResource):
    objdef = "OntapNetapp.Volume"
    objuri = "volumes"
    objname = "volume"
    objdesc = "OntapNetapp Volume"

    default_tags = ["ontap", "storage"]
    # task_base_path = 'beehive_resource.plugins.ontap_netapp.task_v2.ontap_volume.OntapNetappVolumeTask.'

    def __init__(self, *args, **kvargs):
        """ """
        OntapNetappResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []

        self.svm = None
        self.snapmirror = None

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        TODO:

        :param container: client used to communicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)

        :raises ApiManagerError:
        """
        res = []
        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        TODO:

        :param container: client used to communicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        items = []
        return items

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data:

            {
                'resclass': ..,
                'objid': ..,
                'name': ..,
                'ext_id': ..,
                'active': ..,
                'desc': ..,
                'attrib': ..,
                'parent': ..,
                'tags': ..
            }

        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        status = entity[6]

        objid = "%s//%s" % (container.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent_id,
            "tags": resclass.default_tags,
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
        for entity in entities:
            entity.ext_obj = OntapNetappVolume.get_remote_volume(controller, entity.ext_id, container, entity.ext_id)
            entity.get_svm()
            entity.get_snapmirror()
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        self.ext_obj = self.get_remote_volume(self.controller, self.ext_id, self.container, self.ext_id)
        self.get_svm()
        self.get_snapmirror()

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.ontap_volume_id: physical id of volume in ontap netapp platform
        :return: kvargs
        :raise ApiManagerError:
        """
        netapp_volume_id = kvargs.get("ontap_volume_id")
        netapp_volume = OntapNetappVolume.get_remote_volume(controller, netapp_volume_id, container, netapp_volume_id)
        if netapp_volume == {}:
            raise ApiManagerError("ontap netapp volume %s was not found" % netapp_volume_id)
        kvargs["ext_id"] = netapp_volume_id

        # get svm
        netapp_svm_id = dict_get(netapp_volume, "svm.uuid")
        # netapp_svm = container.client.svm.get(netapp_svm_id)

        # check netapp svm resource exists
        svm_resource = controller.get_resource_by_extid(netapp_svm_id)

        # create netapp svm resource
        if svm_resource is None:
            netapp_svm = OntapNetappVolume.get_remote_svm(controller, netapp_svm_id, container, netapp_svm_id)
            name = netapp_svm.get("name")
            svm_conf = {
                "name": name,
                "desc": name,
                "ext_id": netapp_svm_id,
                "parent": None,
            }
            resource_uuid, code = container.resource_factory(OntapNetappSvm, **svm_conf)
            svm_resource = controller.get_simple_resource(resource_uuid.get("uuid"))

        kvargs["attribute"]["svm"] = svm_resource.oid

        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method."""
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method."""
        return kvargs

    #
    # info
    #
    def info(self):
        """Get infos.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OntapNetappResource.info(self)

        info["details"] = self.ext_obj
        info["size"] = self.get_size()
        if self.svm:
            info["svm"] = self.svm.small_info()
        if self.snapmirror:
            info["snapmirror"] = self.has_snapmirror()
        info["export_locations"] = self.get_export_locations()
        info["share_proto"] = self.get_share_proto()
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OntapNetappResource.detail(self)
        info["size"] = self.get_size()
        if self.svm:
            info["svm"] = self.svm.small_info()
        if self.snapmirror:
            info["snapmirror"] = self.has_snapmirror()
        info["export_locations"] = self.get_export_locations()
        info["share_proto"] = self.get_share_proto()
        return info

    def get_size(self):
        res = 0
        if self.ext_obj is not None:
            res = round(dict_get(self.ext_obj, "space.size") / 1073741824, 3)
        return res

    def get_svm(self):
        """get volume svm"""
        svm_resource_id = self.get_attribs("svm")
        self.svm = self.controller.get_resource(svm_resource_id)

    def get_share_proto(self):
        """get principal share protocol"""
        res = None
        if self.ext_obj is not None:
            nas_security_style = dict_get(self.ext_obj, "nas.security_style")
            if nas_security_style == "unix":
                res = "nfs"
            elif nas_security_style == "ntfs":
                res = "cifs"

        self.logger.debug("get volume %s share protocol: %s" % (self.oid, res))
        return res

    def get_export_locations(self):
        """get share export lcoations"""
        res = []
        if self.ext_obj is not None and self.svm is not None:
            nas_security_style = dict_get(self.ext_obj, "nas.security_style")
            for ip_interface in self.svm.get_ip_interfaces():
                if nas_security_style == "unix":
                    nas_path = dict_get(self.ext_obj, "nas.path")
                    export_location = "%s:%s" % (ip_interface.get("ip"), nas_path)
                    res.append(export_location)
                elif nas_security_style == "ntfs":
                    nas_path = dict_get(self.ext_obj, "nas.path", default="")
                    nas_path = nas_path.replace("/", "\\")
                    export_location = "\\\\%s%s" % (ip_interface.get("ip"), nas_path)
                    res.append(export_location)

        self.logger.debug("get volume %s export locations: %s" % (self.oid, res))
        return res

    def grant_list(self):
        """Get volume grant list

        :raise ApiManagerError:
        :return: grant list::
            [
                {
                    "access_level": "rw",
                    "state": "error",
                    "id": "507bf114-36f2-4f56-8cf4-857985ca87c1",
                    "access_type": "cert",
                    "access_to": "example.com",
                    "access_key": null
                },
                {
                    "access_level": "rw",
                    "state": "active",
                    "id": "a25b2df3-90bd-4add-afa6-5f0dbbd50452",
                    "access_type": "ip",
                    "access_to": "0.0.0.0/0",
                    "access_key": null
                }
            ]
        """
        self.verify_permisssions("use")
        res = []
        if self.ext_obj is not None and self.svm is not None:
            security_style = dict_get(self.ext_obj, "nas.security_style")
            if security_style == "ntfs":
                shares = self.get_remote_cifs_shares(self.controller, self.ext_id, self.container, self.ext_id)
                for share in shares:
                    for rule in share.pop("acls", []):
                        if rule.get("permission", None) != "full_control":
                            access_level = "ro"
                        else:
                            access_level = "rw"
                        acl = {
                            "access_key": None,
                            "created_at": None,
                            "updated_at": None,
                            "access_type": "ip",
                            "access_to": dict_get(rule, "user_or_group"),
                            "access_level": access_level,
                            "state": "active",
                            "id": None,
                        }
                        res.append(acl)
            elif security_style == "unix":
                export_policy = dict_get(self.ext_obj, "nas.export_policy")
                if export_policy is not None:
                    policy_id = export_policy.get("id")
                    export_policy = self.get_remote_nfs_export_policy(
                        self.controller, policy_id, self.container, policy_id
                    )
                    for rule in export_policy.pop("rules", []):
                        if rule.get("rw_rule", None) != "never":
                            access_level = "ro"
                        else:
                            access_level = "rw"
                        acl = {
                            "access_key": None,
                            "created_at": None,
                            "updated_at": None,
                            "access_type": "ip",
                            "access_to": dict_get(rule, "clients.0.match"),
                            "access_level": access_level,
                            "state": "active",
                            "id": rule.get("index"),
                        }
                        res.append(acl)
        return res

    def get_snapmirror(self):
        """get volume snapmirror config"""
        if self.ext_obj is not None and dict_get(self.ext_obj, "snapmirror.is_protected", default=False) is True:
            ext_id = "%s:%s" % (self.svm.name, self.ext_obj.get("name"))
            snapmirror_info = self.get_remote_snapmirror(self.controller, self.ext_id, self.container, ext_id)

            # # get destination container
            # try:
            #     container = self.controller.get_containers(desc=dict_get(snapmirror_info, 'cluster.name'))
            #     container_id = container.oid
            # except:
            #     container_id = None

            # get destination volume
            try:
                svm, volume = dict_get(snapmirror_info, "destination.path").split(":")
                volume = self.controller.get_resource(volume)
                volume_info = volume.small_info()
            except:
                volume_info = None

            self.snapmirror = {
                # 'source': {
                #     'path': dict_get(snapmirror_info, 'source.path')
                # },
                "dest": {
                    # 'container': container.info(),
                    "volume": volume_info
                    # 'path': dict_get(snapmirror_info, 'destination.path'),
                },
                "id": dict_get(snapmirror_info, "uuid"),
                "policy": dict_get(snapmirror_info, "policy"),
            }

    def has_snapmirror(self):
        """check if snapmirror is configured"""
        if self.ext_obj is not None and dict_get(self.ext_obj, "snapmirror.is_protected", default=False) is True:
            return True
        return False
