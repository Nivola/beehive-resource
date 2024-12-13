# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import id_gen
from beehive_resource.plugins.provider.entity.base import LocalProviderResource


class Region(LocalProviderResource):
    """Provider region"""

    objdef = "Provider.Region"
    objuri = "%s/regions/%s"
    objname = "region"
    objdesc = "Provider region"

    create_task = None
    import_task = None
    update_task = None
    patch_task = None
    delete_task = None
    expunge_task = None
    action_task = None

    def __init__(self, *args, **kvargs):
        LocalProviderResource.__init__(self, *args, **kvargs)

        from beehive_resource.plugins.provider.entity.site import Site

        self.child_classes = [
            Site,
        ]

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used
        in container resource_factory method.

        :param controller** (:py:class:`ResourceController`): resource controller instance
        :param container** (:py:class:`DummyContainer`): container instance
        :param args: custom params
        :param kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id [default=None]
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id [default=None]
        :param kvargs.active: resource active [default=False]
        :param kvargs.attribute: attributes [default={}]
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.geo_area: geographic ares
        :param kvargs.coords: geographic coords
        :return: {}
        :raise ApiManagerError:
        """
        new_kvargs = {
            "objid": container.objid + "//" + id_gen(),
            "active": True,
            "attribute": {
                "config": {
                    "geo_area": kvargs.pop("geo_area"),
                    "coords": kvargs.pop("coords"),
                }
            },
            "parent": None,
        }

        kvargs.update(new_kvargs)
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param args: custom params
        :param kvargs: custom params
        :param cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs["attribute"] = {
            "geo_area": kvargs.pop("geo_area", None),
            "coords": kvargs.pop("coords", None),
        }
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param args: custom params
        :param kvargs: custom params
        :param cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs
