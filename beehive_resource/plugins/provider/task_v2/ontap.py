# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte
import json

from beecell.simple import import_class
from beecell.types.type_dict import dict_get
from beehive.common.task_v2 import TaskError
from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume
from beehive_resource.plugins.provider.task_v2 import AbstractProviderHelper, getLogger


logger = getLogger(__name__)


class ProviderNetappOntap(AbstractProviderHelper):
    def create_share(self, parent, params, compute_share):
        """Create ontap share.

        :param parent: parent [not used]
        :param params: configuration params
        :param compute_share: compute_share resource
        :return: resource id
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            name = "%s-%s-share" % (self.resource.name, self.cid)

            # get netapp volume id
            volume_id = dict_get(params, "attribute.ontap_volume")
            volume_resource = self.controller.get_resource_by_extid(volume_id)

            # create volume resource
            if volume_resource is None:
                # create remote share
                volume_conf = {
                    "name": name,
                    "desc": self.resource.desc,
                    "ontap_volume_id": volume_id,
                    "parent": None,
                }
                create_resp = self.create_resource(OntapNetappVolume, **volume_conf)
                volume_resource = self.add_link(create_resp)
            else:
                self.add_link(resource_to_link=volume_resource)

            # update compute_zone attributes
            self.get_session(reopen=True)
            volume_resource = self.get_resource(volume_resource.oid)
            export_locations = volume_resource.get_export_locations()
            attribs = compute_share.get_attribs()
            attribs["exports"] = export_locations
            attribs["host"] = None
            compute_share.update_internal(attribute=attribs)
            return volume_resource.oid
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)

    def remove_resource(self, childs):
        """delete ontap resources.

        :param childs: orchestrator childs
        :return: list
        :rtype: resource list
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            # get all child resources
            resources = []
            self.progress("Start removing ontap childs: %s" % childs)
            for child in childs:
                definition = child.objdef
                child_id = child.id
                attribs = json.loads(child.attribute)
                link_attr = json.loads(child.link_attr)
                reuse = link_attr.get("reuse", False)

                # get child resource
                entity_class = import_class(child.objclass)
                child = entity_class(
                    self.controller,
                    oid=child.id,
                    objid=child.objid,
                    name=child.name,
                    active=child.active,
                    desc=child.desc,
                    model=child,
                )
                child.container = self.container

                if reuse is True:
                    continue

                try:
                    if definition in [OntapNetappVolume.objdef, OntapNetappSvm.objdef]:
                        self.logger.warn(child)
                        prepared_task, code = child.expunge(sync=True)
                        self.logger.warn(prepared_task)
                        self.logger.warn(code)
                        # self.run_sync_task(prepared_task, msg='remove child %s' % child.oid)

                    resources.append(child_id)
                    self.progress("Delete child %s" % child_id)
                except:
                    self.logger.error("Can not delete ontap child %s" % child_id, exc_info=True)
                    self.progress("Can not delete ontap child %s" % child_id)
                    raise

            self.progress("Stop removing ontap childs: %s" % childs)
            return resources
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)
