# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte

from logging import getLogger
import ujson as json
from beecell.simple import import_class
from beehive.common.task_v2 import TaskError
from beehive_resource.plugins.veeam.entity.veeam_job import VeeamJob
from beehive_resource.plugins.provider.task_v2 import AbstractProviderHelper

logger = getLogger(__name__)


class ProviderVeeam(AbstractProviderHelper):
    def create_project(self):
        """Create veeam project

        :param
        """

    def remove_resource(self, childs):
        """Delete veeam resources.

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
                    if definition in [VeeamJob.objdef]:
                        prepared_task, code = child.expunge(sync=True)
                        self.run_sync_task(prepared_task, msg="remove child %s" % child.oid)

                    resources.append(child_id)
                    self.progress("Delete child %s" % child_id)
                except:
                    self.logger.error("Can not delete veeam child %s" % child_id, exc_info=True)
                    self.progress("Can not delete veeam child %s" % child_id)
                    raise

            self.progress("Stop removing childs %s" % childs)
            return resources
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise TaskError(ex)
