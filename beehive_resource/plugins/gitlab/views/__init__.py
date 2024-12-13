# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte
# (C) Copyright 2018-2024 CSI-Piemonte

from beehive_resource.plugins.gitlab import GitlabContainer
from beehive.common.apimanager import ApiView
from beehive_resource.views import ResourceApiView


class GitlabApiView(ResourceApiView):
    containerclass = GitlabContainer


class GitlabAPI(ApiView):
    base = "nrs/gitlab"
