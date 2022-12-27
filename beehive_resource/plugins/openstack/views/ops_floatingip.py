# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2022 CSI-Piemonte

from beehive_resource.plugins.openstack.views import OpenstackAPI, OpenstackApiView
from beehive_resource.plugins.openstack.entity.ops_domain import OpenstackDomain


class OpenstackDomainApiView(OpenstackApiView):
    resclass = OpenstackDomain
    parentclass = None


class ListDomains(OpenstackDomainApiView):
    """
    List domain
    """
    def dispatch(self, controller, data, *args, **kwargs):
        return self.get_resources(controller, *args, **kwargs)


class GetDomain(OpenstackDomainApiView):
    """
    Get domain
    """
    def dispatch(self, controller, data, oid, *args, **kwargs):
        return self.get_resource(controller, oid)


class CreateDomain(OpenstackDomainApiView):
    """
    Create domain

    """
    def dispatch(self, controller, data, oid, *args, **kwargs):
        return self.create_resource(controller, oid, data)


class UpdateDomain(OpenstackDomainApiView):
    """
    Update domain

    """
    def dispatch(self, controller, data, oid, *args, **kwargs):
        return self.update_resource(controller, data)


class DeleteDomain(OpenstackDomainApiView):
    def dispatch(self, controller, data, oid, *args, **kwargs):
        return self.delete_resource(controller, oid)


class OpenstackDomainAPI(OpenstackAPI):
    """Openstack base platform api routes:
    """
    @staticmethod
    def register_api(module, **kwargs):
        base = OpenstackAPI.base
        rules = [
            ('%s/domains' % base, 'GET', ListDomains, {}),
            ('%s/domains/<rid>' % base, 'GET', GetDomain, {}),
        ]

        OpenstackAPI.register_api(module, rules, **kwargs)
