# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive.common.apimanager import ApiView


class DummyAPIV2(ApiView):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = "dummy/<oid>"
        rules = [
            # ('%s/syncres' % base, 'GET', None, {}),
            # ('%s/asyncres' % base, 'GET', None, {})
        ]

        ApiView.register_api(module, rules, **kwargs)
