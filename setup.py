#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from sys import version_info
from setuptools import setup
from setuptools.command.install import install as _install


class install(_install):
    def pre_install_script(self):
        pass

    def post_install_script(self):
        pass

    def run(self):
        self.pre_install_script()

        _install.run(self)

        self.post_install_script()


def load_requires():
    with open("./MANIFEST.md") as f:
        requires = f.read()
    return requires


def load_version():
    with open("./beehive_resource/VERSION") as f:
        version = f.read()
    return version


if __name__ == "__main__":
    version = load_version()
    setup(
        name="beehive_resource",
        version=version,
        description="Nivola technological resource package",
        long_description="Nivola technological resource package",
        author="CSI Piemonte",
        author_email="nivola.engineering@csi.it",
        license="EUPL-1.2",
        url="",
        scripts=[],
        packages=[
            "beehive_resource",
            "beehive_resource.db_script",
            "beehive_resource.plugins",
            "beehive_resource.plugins.awx",
            "beehive_resource.plugins.awx.entity",
            "beehive_resource.plugins.awx.task_v2",
            "beehive_resource.plugins.awx.views",
            "beehive_resource.plugins.dns",
            # 'beehive_resource.plugins.dns.task.old',
            "beehive_resource.plugins.dns.views",
            "beehive_resource.plugins.dummy",
            "beehive_resource.plugins.dummy.task",
            "beehive_resource.plugins.dummy.task_v2",
            "beehive_resource.plugins.dummy_v2",
            "beehive_resource.plugins.dummy_v2.entity",
            "beehive_resource.plugins.elk",
            "beehive_resource.plugins.elk.entity",
            "beehive_resource.plugins.elk.task_v2",
            "beehive_resource.plugins.elk.views",
            "beehive_resource.plugins.grafana",
            "beehive_resource.plugins.grafana.entity",
            "beehive_resource.plugins.grafana.task_v2",
            "beehive_resource.plugins.grafana.views",
            "beehive_resource.plugins.ontap",
            "beehive_resource.plugins.ontap.entity",
            "beehive_resource.plugins.ontap.views",
            "beehive_resource.plugins.openstack",
            "beehive_resource.plugins.openstack.entity",
            "beehive_resource.plugins.openstack.task",
            "beehive_resource.plugins.openstack.task_v2",
            "beehive_resource.plugins.openstack.views",
            "beehive_resource.plugins.provider",
            "beehive_resource.plugins.provider.entity",
            "beehive_resource.plugins.provider.helper",
            "beehive_resource.plugins.provider.helper.network_appliance",
            "beehive_resource.plugins.provider.task",
            "beehive_resource.plugins.provider.task_v2",
            "beehive_resource.plugins.provider.views",
            "beehive_resource.plugins.provider.views.stacks",
            "beehive_resource.plugins.provider.views.stacks_v2",
            "beehive_resource.plugins.ssh_gateway",
            "beehive_resource.plugins.ssh_gateway.entity",
            "beehive_resource.plugins.ssh_gateway.views",
            "beehive_resource.plugins.vsphere",
            "beehive_resource.plugins.vsphere.entity",
            "beehive_resource.plugins.vsphere.task_v2",
            "beehive_resource.plugins.vsphere.views",
            "beehive_resource.plugins.zabbix",
            "beehive_resource.plugins.zabbix.entity",
            "beehive_resource.plugins.zabbix.task_v2",
            "beehive_resource.plugins.zabbix.views",
            "beehive_resource.task_v2",
            "beehive_resource.templates",
            # 'beehive_resource.views',
        ],
        namespace_packages=[],
        py_modules=[
            "beehive_resource.container",
            "beehive_resource.controller_mongodb",
            "beehive_resource.controller",
            "beehive_resource.__init__",
            "beehive_resource.model",
            "beehive_resource.mod",
            "beehive_resource.tasks",
            "beehive_resource.util",
            # 'beehive_resource.view',
            # 'beehive_resource.view.new',
        ],
        classifiers=[
            "Development Status :: %s" % version,
            "Programming Language :: Python",
        ],
        entry_points={},
        data_files=[],
        package_data={"beehive_resource": ["VERSION"]},
        install_requires=load_requires(),
        dependency_links=[],
        zip_safe=True,
        cmdclass={"install": install},
        keywords="",
        python_requires="",
        obsoletes=[],
    )
