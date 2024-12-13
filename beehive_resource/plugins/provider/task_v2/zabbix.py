# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from logging import getLogger
import ujson as json
from beecell.simple import import_class
from beehive.common.task_v2 import TaskError
from beehive_resource.plugins.zabbix.entity.zbx_usergroup import ZabbixUsergroup
from beehive_resource.plugins.zabbix.entity.zbx_action import ZabbixAction
from beehive_resource.plugins.provider.task_v2 import AbstractProviderHelper

logger = getLogger(__name__)


class ProviderZabbix(AbstractProviderHelper):
    def create_project(self):
        """Create zabbix project

        :param
        """

    def remove_resource(self, childs):
        """Delete zabbix resources.

        :param childs: orchestrator childs
        :return: list
        :rtype: resource list
        :raise TaskError: :class:`TaskError`
        :raise ApiManagerError: :class:`ApiManagerError`
        """
        try:
            # get all child resources
            resources = []
            self.progress("Start removing childs %s" % childs)

            resources_ZabbixUsergroup = []
            resources_ZabbixAction = []

            for child in childs:
                definition = child.objdef
                # child_id = child.id
                # attribs = json.loads(child.attribute)
                link_attr = json.loads(child.link_attr)
                reuse = link_attr.get("reuse", False)

                # get child resource
                entity_class = import_class(child.objclass)
                child_instance = entity_class(
                    self.controller,
                    oid=child.id,
                    objid=child.objid,
                    name=child.name,
                    active=child.active,
                    desc=child.desc,
                    model=child,
                )
                child_instance.container = self.container

                if reuse is True:
                    continue

                if definition == ZabbixUsergroup.objdef:
                    resources_ZabbixUsergroup.append(child_instance)
                elif definition == ZabbixAction.objdef:
                    resources_ZabbixAction.append(child_instance)

            # delete first actions then usergroup, due to object reference in Zabbix
            zabbix_resources_ordered = []
            zabbix_resources_ordered.extend(resources_ZabbixAction)
            zabbix_resources_ordered.extend(resources_ZabbixUsergroup)

            from beehive_resource.plugins.zabbix.entity import ZabbixResource

            zabbixResource: ZabbixResource
            for zabbixResource in zabbix_resources_ordered:
                try:
                    self.logger.debug(
                        "Delete zabbixResource: %s - objdef: %s" % (zabbixResource.oid, zabbixResource.objdef)
                    )
                    prepared_task, code = zabbixResource.expunge(sync=True)
                    self.run_sync_task(prepared_task, msg="remove zabbixResource %s" % zabbixResource.oid)

                    resources.append(zabbixResource.oid)
                    self.progress("Delete zabbixResource %s" % zabbixResource.oid)
                except:
                    self.logger.error("Can not delete zabbixResource %s" % zabbixResource.oid, exc_info=True)
                    self.progress("Can not delete zabbixResource %s" % zabbixResource.oid)
                    raise

            self.progress("Stop removing childs %s" % childs)
            return resources
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)
