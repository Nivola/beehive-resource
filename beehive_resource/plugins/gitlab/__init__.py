# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2021-2022 Regione Piemonte

from beehive_resource.plugins.gitlab.controller import GitlabContainer
from beehive_resource.plugins.gitlab.views.group import GitlabGroupAPI
from beehive_resource.plugins.gitlab.views.project import GitlabProjectAPI


class GitlabPlugin(object):
    def __init__(self, module):
        self.module = module

    def init(self):
        service = GitlabContainer(self.module.get_controller())
        service.init_object()

    def register(self):
        apis = [
            GitlabProjectAPI,
            GitlabGroupAPI,
        ]
        self.module.set_apis(apis)

        self.module.add_container(GitlabContainer.objdef, GitlabContainer)
