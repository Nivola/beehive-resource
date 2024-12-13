# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import import_class
from beedrones.ontapp.client import OntapManager, OntapError
from beehive.common.apimanager import ApiManagerError
from beehive_resource.container import Orchestrator, trace, QueryError, List
from beehive_resource.plugins.ontap.entity.svm import OntapNetappSvm
from beehive_resource.plugins.ontap.entity.volume import OntapNetappVolume


def get_task(task_name):
    return "%s.task.%s" % (__name__, task_name)


class OntapNetappContainer(Orchestrator):
    """Ontap Netapp orchestrator

    **connection syntax**:

        {
            "host": ..,
            "port": ..,
            "proto": ..,
            "user": ..,
            "pwd": ..,
            "timeout": 5.0,
        }
    """

    objdef = "OntapNetapp"
    objdesc = "OntapNetapp container"
    version = "v1.0"

    def __init__(self, *args, **kvargs):
        Orchestrator.__init__(self, *args, **kvargs)

        self.child_classes = [OntapNetappSvm, OntapNetappVolume]

        self.conn = None
        self.token = None

    def ping(self):
        """Ping orchestrator.

        :return: True if ping ok
        :rtype: bool
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        try:
            self.__new_connection(timeout=30)
            res = self.conn.ping()
        except (ApiManagerError, Exception) as ex:
            self.logger.warning("ping ko", exc_info=True)
            res = False
        self.container_ping = res
        return res

    def info(self):
        """Get container info.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Orchestrator.info(self)
        return info

    def detail(self):
        """Get container detail.

        :return: Dictionary with system capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = Orchestrator.info(self)

        res = info
        res["details"] = {
            "cluster": self.get_cluster_info()
            # 'version': self.conn.version()
        }

        return res

    def __new_connection(self, timeout=30.0):
        """Get zabbix connection with new token"""
        try:
            host = self.conn_params.get("host")
            port = self.conn_params.get("port", 80)
            proto = self.conn_params.get("proto", "http")
            user = self.conn_params.get("user")
            pwd = self.conn_params.get("pwd")

            # decrypt password
            pwd = self.decrypt_data(pwd)
            self.conn = OntapManager(host, user, pwd, port=port, proto=proto, timeout=timeout)
            self.conn.authorize()
        except OntapError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400) from ex

    def get_connection(self):
        """Get ontap netapp connection"""
        if self.conn is None:
            self.__new_connection()
        else:
            if self.conn.ping() is False:
                self.__new_connection()

        Orchestrator.get_connection(self)

    def close_connection(self, token):
        if self.conn is not None:
            pass

    @staticmethod
    def pre_create(
        controller=None,
        type=None,
        name=None,
        desc=None,
        active=None,
        conn=None,
        **kvargs,
    ):
        """Check input params

        :param controller: (:py:class:`ResourceController`): resource controller instance
        :param type: (:py:class:`str`): container type
        :param name: (:py:class:`str`): container name
        :param desc: (:py:class:`str`): container desc
        :param active: (:py:class:`str`): container active
        :param conn: (:py:class:`dict`): container connection
        :return: kvargs
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        # encrypt password
        conn["pwd"] = controller.encrypt_data(conn["pwd"])

        kvargs = {
            "type": type,
            "name": name,
            "desc": desc,
            "active": active,
            "conn": conn,
        }

        return kvargs

    def pre_change(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def pre_clean(self, **kvargs):
        """Check input params

        :param kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        return kvargs

    def get_cluster_info(self):
        """Get ontap netapp cluster info"""
        res = self.conn.cluster.get()
        return res

    @trace(op="use")
    def discover(self, restypes: List, ext_id=None):
        """Discover remote platform entities

        :param restype: container resource objdef
        :param ext_id: remote entity id [optional]
        :return:

            {
                'new':[
                    'resclass':..,
                    'id':..,
                    'parent':..,
                    'type':..,
                    'name':..
                ],
                'died':[],
                'changed':[]
            }

        :raise ApiManagerError:
        """
        # check authorization (TODO check whether to remove)
        self.verify_permisssions("use")

        cmp_resources = []
        remote_resources = []
        res = {"new": [], "died": [], "changed": []}

        if restypes is None or len(restypes) == 0:
            raise ApiManagerError("Invalid restypes %s for ontap container %d" % (restypes, self.oid))

        for restype in restypes:
            # 1 import the corresponding class (e.g. OntapNetappSvm, OntapNetappVolume)
            restype_class = self.manager.get_resource_types(value=restype)[0]
            resclass = import_class(restype_class.objclass)
            # 2 get resources of that type already present in cmp
            try:
                cmp_resources = self.manager.get_resources_by_type(type=restype, container=self.oid)
            except QueryError as ex:
                # TODO handle this case better and more explicitly
                self.logger.warning(ex, exc_info=False)
            # 3 create cmp resources ext_id map
            cmp_res_map = {r.ext_id: r for r in cmp_resources if r.ext_id is not None}
            # 4 discover remote resources
            remote_resources = resclass.discover_remote(container=self, ext_id=ext_id)
            for item in remote_resources:
                # 5a for each remote resource
                ext_id = item.get("uuid")
                name = item.get("name")
                # 5b get cmp corresponding resource if present
                cmp_res = cmp_res_map.get(ext_id)
                if cmp_res is None:
                    # 6a add to "new" if not present
                    # e.g. resclass = OntapNetappSvm
                    res["new"].append(
                        {
                            "resclass": "%s.%s" % (resclass.__module__, resclass.__name__),
                            "id": ext_id,
                            "parent": None,
                            "type": resclass.objdef,  # e.g. OntapNetappSvm.objdef
                            "name": name,
                        }
                    )
                    self.logger.debug("New resource found: %s.", name)
                else:
                    # 6b.1 check if changed
                    cmp_search_name = name.replace("_", "-")
                    # TODO check if size changed in case of volumes
                    # remote_size = item.get("space",{}).get("size")
                    # cmp_size = ...
                    if cmp_res.name != cmp_search_name:
                        # 6b.2 add to "changed" if changed
                        resource_class = import_class(cmp_res.type.objclass)
                        obj = resource_class(
                            self.controller,
                            oid=cmp_res.id,
                            objid=cmp_res.objid,
                            name=cmp_res.name,  # or show changed name, so cmp_search_name?
                            desc=cmp_res.desc,
                            active=cmp_res.active,
                            model=cmp_res,
                        )
                        obj.container = self
                        obj.ext_id = cmp_res.ext_id
                        data = {
                            "resclass": "%s.%s" % (obj.__class__.__module__, obj.__class__.__name__),
                            "id": obj.oid,
                            "parent": obj.parent_id,
                            "type": obj.objdef,
                            "name": obj.name,
                        }
                        res["changed"].append(data)
                        self.logger.debug("Resource %s is changed.", cmp_res.name)
                    # 6b.3 remove from map
                    cmp_res_map.pop(ext_id)
            # 7 the remaining objects in cmp_res_map, are "died", if any
            for ext_id, r in cmp_res_map.items():
                # 8 add to "died"
                resource_class = import_class(r.type.objclass)
                obj = resource_class(
                    self.controller,
                    oid=r.id,
                    objid=r.objid,
                    name=r.name,
                    desc=r.desc,
                    active=r.active,
                    model=r,
                )
                obj.container = self
                obj.ext_id = r.ext_id
                data = {
                    "resclass": "%s.%s" % (obj.__class__.__module__, obj.__class__.__name__),
                    "id": obj.oid,
                    "parent": obj.parent_id,
                    "type": obj.objdef,
                    "name": obj.name,
                }
                res["died"].append(data)
                self.logger.debug("Resource %s does not exist anymore. It can be deleted.", r.name)

        return res
