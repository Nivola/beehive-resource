# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import truncate
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity import OpenstackResource


class OpenstackKeystone(OpenstackResource):
    """Openstack keystone entity wrapper."""

    objdef = "Openstack.Keystone"
    objuri = "keystones"
    objname = "keystone"
    objdesc = "Openstack keystone"

    default_tags = ["openstack"]

    def __init__(self, *args, **kvargs):
        kvargs.pop("model", None)
        OpenstackResource.__init__(self, model=None, *args, **kvargs)

        self.container = None

    #
    # system keystone
    #
    def api(self):
        """Get keystone service info.

        :return: Dictionary with service details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.api()
            self.logger.debug("Get openstack %s keystone api version: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s keystone api version: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_roles(self, name=None):
        """Get keystone roles.

        :param name: name [optional]
        :return: Dictionary with roles details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.role.list(detail=False, name=name)
            self.logger.debug("Get openstack %s keystone roles: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s keystone roles: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_groups(self):
        """Get keystone groups.

        :return: Dictionary with groups details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.get_groups()
            self.logger.debug("Get openstack %s keystone groups: %s" % (self.container.name, res))

            return res
        except Exception as ex:
            err = "Can not get openstack %s keystone groups: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_policies(self):
        """Get keystone policies.

        :return: Dictionary with policies details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.get_policies()
            self.logger.debug("Get openstack %s keystone policies: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s keystone policies: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_users(self, name=None):
        """Get keystone users.

        :param name: name [optional]
        :return: Dictionary with users details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            # get users
            res = self.container.conn.identity.user.list(detail=False, name=name)

            # get projects
            projects = {p["id"]: p for p in self.container.conn.project.list()}

            # get domains
            domains = {p["id"]: p for p in self.container.conn.domain.list()}

            for item in res:
                try:
                    item["domain"] = domains[item["domain_id"]]
                except:
                    item["domain"] = None
                try:
                    item["default_project"] = projects[item["default_project_id"]]
                except:
                    item["default_project"] = None

            return res
        except Exception as ex:
            err = "Can not get openstack %s keystone users" % (ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_credentials(self):
        """Get keystone credentials.

        :return: Dictionary with credentials details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.get_credentials()

            # get users
            users = {p["id"]: p for p in self.container.conn.identity.user.list(detail=False, name=None)}

            # get projects
            projects = {p["id"]: p for p in self.container.conn.project.list()}

            for item in res:
                item["project"] = projects[item["project_id"]]
                item["user"] = users[item["user_id"]]

            self.logger.debug("Get openstack %s keystone credentials: %s" % (self.container.name, truncate(res)))

            return res
        except Exception as ex:
            err = "Can not get openstack %s keystone credentials: %s" % (
                self.container.name,
                ex,
            )
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)

    def get_regions(self):
        """Get identity regions.

        :return: Dictionary with regions details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            res = self.container.conn.identity.get_regions()
            self.logger.debug("Get openstack %s regions: %s" % (self.container.name, truncate(res)))
            return res
        except Exception as ex:
            err = "Can not get openstack %s regions: %s" % (self.name, ex)
            self.logger.error(err, exc_info=True)
            raise ApiManagerError(err, code=400)
