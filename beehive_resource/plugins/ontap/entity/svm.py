# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
import logging

from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.ontap.entity import OntapNetappResource

logger = logging.getLogger(__name__)


class OntapNetappSvm(OntapNetappResource):
    objdef = "OntapNetapp.Svm"
    objuri = "svms"
    objname = "svm"
    objdesc = "OntapNetapp Svm"

    default_tags = ["ontap", "storage"]
    # task_base_path = 'beehive_resource.plugins.ontap_netapp.task_v2.ontap_svm.OntapNetappSvmTask.'

    def __init__(self, *args, **kvargs):
        """ """
        OntapNetappResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_remote(container, ext_id=None, name=None):
        """
        Discover remote svms that may or may not be already in cmp
        """
        manager = container.conn
        if ext_id:
            items = manager.svm.get(ext_id)
        else:
            items = manager.svm.list(**{"name": name})
        return items

    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to communicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)

        :raises ApiManagerError:
        """
        manager = container.conn
        items = manager.svm.list()
        res = []
        for item in items:
            ext_id = item.get("uuid")
            name = item.get("name")
            if ext_id not in res_ext_ids:
                res.append((OntapNetappSvm, ext_id, None, OntapNetappSvm.objdef, name, None))

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        TODO:

        :param container: client used to communicate with remote platform
        :return: list of remote entities
        :raises ApiManagerError:
        """
        manager = container.conn
        items = manager.svm.list()
        for item in items:
            # discover_died_entities expects an id field containing the "ext_id"
            item["id"] = item.get("uuid")
        return items

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        TODO:

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
        # status = entity[6]

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
            entity.ext_obj = OntapNetappSvm.get_remote_svm(controller, entity.ext_id, container, entity.ext_id)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        self.ext_obj = self.get_remote_svm(self.controller, self.ext_id, self.container, self.ext_id)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method."""
        svm_volume_id = kvargs.get("ext_id")
        netapp_svm = OntapNetappSvm.get_remote_svm(controller, svm_volume_id, container, svm_volume_id)
        if netapp_svm == {}:
            raise ApiManagerError("ontap netapp svm %s was not found" % svm_volume_id)

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
        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OntapNetappResource.info(self)
        return info

    def get_ip_interfaces(self):
        """get ip interfaces with nfs or cifs service active"""
        res = []
        if self.ext_obj is not None:
            ip_interfaces = dict_get(self.ext_obj, "ip_interfaces")
            if ip_interfaces is None:
                raise ApiManagerError("svm %s ip_interfaces field missing" % self.oid)
            else:
                for ip_interface in ip_interfaces:
                    services = dict_get(ip_interface, "services")
                    if "data_nfs" in services or "data_cifs" in services:
                        res.append(
                            {
                                "name": dict_get(ip_interface, "name"),
                                "ip": dict_get(ip_interface, "ip.address"),
                            }
                        )

        self.logger.debug("get svm %s ip interfaces: %s" % (self.oid, res))
        return res
