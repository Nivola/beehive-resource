# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2024 CSI-Piemonte

from beecell.simple import truncate, get_value, id_gen
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity import OpenstackResource
from beehive.common.data import trace


class OpenstackShare(OpenstackResource):
    objdef = "Openstack.Domain.Project.Share"
    objuri = "shares"
    objname = "share"
    objdesc = "Openstack shares"

    default_tags = ["openstack"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_share.ShareTask."

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        # child classes
        self.child_classes = []

        self.share_network = None
        self.share_server = None
        self.export_locations = []

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container.conn: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, level)
        :raise ApiManagerError:
        """
        # get from openstack
        if ext_id is not None:
            items = container.conn.manila.share.get(ext_id)
        else:
            items = container.conn.manila.share.list(details=True)

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                name = item["name"]
                parent_id = item["project_id"]
                if str(parent_id) == "":
                    parent_id = None

                res.append(
                    (
                        OpenstackShare,
                        item["id"],
                        parent_id,
                        OpenstackShare.objdef,
                        name,
                        level,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container.conn: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        return container.conn.manila.share.list()

    @staticmethod
    def synchronize(container, entity):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: instance of resource container
        :param entity: entity discovered [resclass, ext_id, parent_id, obj_type, name, parent_class]
        :return: new resource data {'resclass': .., 'objid': .., 'name': .., 'ext_id': .., 'active': .., desc': ..,
            'attrib': .., 'parent': .., 'tags': .. }
        :raises ApiManagerError:
        """
        resclass = entity[0]
        ext_id = entity[1]
        parent_id = entity[2]
        name = entity[4]
        level = entity[5]

        # get parent project
        if parent_id is not None:
            parent = container.get_resource_by_extid(parent_id)
            objid = "%s//%s" % (parent.objid, id_gen())
            parent_id = parent.oid
        else:
            objid = "%s//none//none//%s" % (container.objid, id_gen())
            parent_id = None

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {},
            "parent": parent_id,
            "tags": resclass.default_tags,
        }
        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def get_entities_filter(controller, container_id, *args, **kvargs):
        """Create a list of ext_id to use as resource filter. Use when you
        want to filter resources with a subset of remote physical id.

        :param controller: controller instance
        :param container_id: list of entities
        :param args: custom params
        :param kvargs: custom params
        :return: list of ext_id
        :raise ApiManagerError:
        """
        # get container
        container = controller.get_container(container_id)

        remote_entities = container.conn.manila.share.list()

        # create index of remote objs
        ext_ids = [i["id"] for i in remote_entities]

        return ext_ids

    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation
        after entity was created. Used only for synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raise ApiManagerError:
        """
        for entity in entities:
            try:
                ext_obj = OpenstackShare.get_remote_share(controller, entity.ext_id, container, entity.ext_id)
                entity.set_physical_entity(ext_obj)

                # get share export locations
                entity.export_locations = OpenstackShare.get_remote_share_export_locations(
                    controller, entity.ext_id, container, entity.ext_id
                )
            except:
                container.logger.warn("")
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raise ApiManagerError:
        """
        try:
            ext_obj = OpenstackShare.get_remote_share(self.controller, self.ext_id, self.container, self.ext_id)
            self.set_physical_entity(ext_obj)

            # get share export locations
            self.export_locations = self.container.conn.manila.share.list_export_locations(self.ext_id)

            # get share network
            share_network_id = self.ext_obj.get("share_network_id", None)
            if share_network_id is not None:
                self.share_network = self.container.conn.manila.network.get(share_network_id)

            # get share server
            share_server_id = self.ext_obj.get("share_server_id", None)
            if share_server_id is not None:
                self.share_server = self.container.conn.manila.server.get(share_server_id)
        except:
            pass

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :param objid: resource objid
        :param parent: resource parent id
        :param cid: container id
        :param name: resource name
        :param desc: resource desc
        :param ext_id: resource ext_id
        :param active: resource active
        :param attribute: attributez
        :param tags: comma separated resource tags to assign [default='']
        :param share_proto: The Shared File Systems protocol. A valid value is NFS, CIFS,
            GlusterFS, HDFS, or CephFS. CephFS supported is starting with API v2.13.
        :param size: The share size, in GBs. The requested share size cannot be greater than
            the allowed GB quota. To view the allowed quota, issue a get limits request.
        :param share_type: (Optional) The share type name. If you omit this parameter, the
            default share type is used. To view the default share type set by the administrator, issue a list
            default share types request. You cannot specify both the share_type and volume_type parameters.
        :param snapshot_id: (Optional) The UUID of the share's base snapshot.
        :param share_group_id: (Optional) The UUID of the share group.
        :param network: (Optional) id of the neutron network to use
        :param subnet: (Optional) id of the neutron subnet to use
        :param metadata: (Optional) One or more metadata key and value pairs as a dictionary of strings.
        :param availability_zone: (Optional) The availability zone.
        :return: kvargs
        :raise ApiManagerError:
        """
        from .ops_network import OpenstackNetwork
        from .ops_subnet import OpenstackSubnet

        parent = kvargs["parent"]

        # get availability_zone
        availability_zone = get_value(kvargs, "availability_zone", None)
        zones = {z["zoneName"] for z in container.system.get_compute_zones()}
        if availability_zone not in zones:
            raise ApiManagerError(
                "Openstack availability_zone %s does not exist" % availability_zone,
                code=404,
            )
        kvargs["availability_zone"] = availability_zone

        # check network and subnet
        network = kvargs.pop("network", None)
        subnet = kvargs.pop("subnet", None)
        if network is not None and subnet is not None:
            network = container.get_simple_resource(network, entity_class=OpenstackNetwork)
            subnet = container.get_simple_resource(subnet, entity_class=OpenstackSubnet)
            kvargs["network"] = network.ext_id
            kvargs["subnet"] = subnet.ext_id

        params = {
            # 'parent_ext_id': project.ext_id,
            "desc": "Share %s" % kvargs["name"],
            "is_public": False,
        }

        # set additional params
        kvargs.update(params)

        steps = [
            OpenstackShare.task_path + "create_resource_pre_step",
            OpenstackShare.task_path + "share_create_physical_step",
            OpenstackShare.task_path + "create_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_update(self, *args, **kvargs):
        """Pre update function. This function is used in update method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        steps = [
            OpenstackShare.task_path + "update_resource_pre_step",
            OpenstackShare.task_path + "share_update_physical_step",
            OpenstackShare.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_delete(self, *args, **kvargs):
        """Pre delete function. This function is used in delete method.

        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.cid: container id
        :param kvargs.id: resource id
        :param kvargs.uuid: resource uuid
        :param kvargs.objid: resource objid
        :param kvargs.ext_id: resource remote id
        :return: kvargs
        :raise ApiManagerError:
        """
        kvargs["parent"] = self.parent_id

        steps = [
            OpenstackShare.task_path + "expunge_resource_pre_step",
            OpenstackShare.task_path + "share_expunge_physical_step",
            OpenstackShare.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    #
    # info
    #
    def info(self):
        """Get infos.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            data = {}
            data["status"] = self.ext_obj.get("status", None)
            data["size"] = self.ext_obj.get("size", None)
            data["share_type"] = self.ext_obj.get("share_type", None)
            data["availability_zone"] = self.ext_obj.get("availability_zone", None)
            data["created_at"] = self.ext_obj.get("created_at", None)
            data["export_locations"] = self.export_locations
            data["share_proto"] = self.ext_obj.get("share_proto", None)
            data["share_network_id"] = self.ext_obj.get("share_network_id", None)
            data["snapshot_id"] = self.ext_obj.get("snapshot_id", None)
            data["host"] = self.ext_obj.get("host", None)
            data["is_public"] = self.ext_obj.get("is_public", None)
            info["details"].update(data)

        return info

    def detail(self):
        """Get details.

        :return: like :class:`Resource`
        :raise ApiManagerError:
        """
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            data = {}
            data["status"] = self.ext_obj.get("status", None)
            data["size"] = self.ext_obj.get("size", None)
            data["share_type"] = self.ext_obj.get("share_type", None)
            data["availability_zone"] = self.ext_obj.get("availability_zone", None)
            data["created_at"] = self.ext_obj.get("created_at", None)
            data["export_locations"] = self.export_locations
            data["share_proto"] = self.ext_obj.get("share_proto", None)
            data["share_network"] = self.share_network
            data["share_server"] = self.share_server
            data["snapshot_id"] = self.ext_obj.get("snapshot_id", None)
            data["host"] = self.ext_obj.get("host", None)
            data["is_public"] = self.ext_obj.get("is_public", None)
            info["details"].update(data)

        return info

    #
    # other methods
    #
    def get_size(self):
        size = 0
        if self.ext_obj is not None:
            size = self.ext_obj.get("size", None)
        return size

    def get_proto(self):
        proto = None
        if self.ext_obj is not None:
            proto = self.ext_obj.get("share_proto", None)
        return proto

    @trace(op="view")
    def get_network(self):
        from beehive_resource.plugins.openstack.entity.ops_network import (
            OpenstackNetwork,
        )

        network = None
        if self.ext_obj is not None:
            net_id = self.ext_obj.get("share_network_id", None)
            if net_id is None:
                share_type = self.ext_obj.get("share_type", None)
                if share_type is not None:
                    vlan = share_type.split("-")[-1]
                    networks, tot = self.container.get_resources(
                        objdef=OpenstackNetwork.objdef,
                        type=OpenstackNetwork.objdef,
                        segmentation_id=vlan,
                    )
                    if tot > 0:
                        network = networks[0]
            else:
                network = self.container.get_resource_by_extid(net_id)
        self.logger.debug("Get share %s network: %s" % (self.uuid, truncate(network)))
        return network

    @trace(op="use")
    def grant_list(self):
        """Get share grant list

        :raise ApiManagerError:
        :return: grant list::

            [
                {
                    "access_level": "rw",
                    "state": "error",
                    "id": "507bf114-36f2-4f56-8cf4-857985ca87c1",
                    "access_type": "cert",
                    "access_to": "example.com",
                    "access_key": null
                },
                {
                    "access_level": "rw",
                    "state": "active",
                    "id": "a25b2df3-90bd-4add-afa6-5f0dbbd50452",
                    "access_type": "ip",
                    "access_to": "0.0.0.0/0",
                    "access_key": null
                }
            ]
        """
        self.verify_permisssions("use")
        try:
            res = self.container.conn.manila.share.action.list_access(self.ext_id)
            self.logger.debug("Get openstack manila share %s grant list: %s" % (self.name, res))
            return res
        except:
            self.logger.warn("", exc_info=True)
        return []

    @trace(op="update")
    def grant_add(self, params):
        """Add share grant.
        All manila shares begin with no access. Clients must be provided with explicit access via this API.
        To grant access, specify one of these supported share access levels:
        - rw. Read and write (RW) access.
        - ro. Read-only (RO) access.
        You must also specify one of these supported authentication methods:
        - ip. Authenticates an instance through its IP address. The value specified should be a valid IPv4 or an IPv6
          address, or a subnet in CIDR notation. A valid format is X:X:X:X:X:X:X:X, X:X:X:X:X:X:X:X/XX, XX.XX.XX.XX,
          or XX.XX.XX.XX/XX, etc. For example 0.0.0.0/0 or ::/0.
        - cert. Authenticates an instance through a TLS certificate. Specify the TLS identity as the IDENTKEY. A valid
          value is any string up to 64 characters long in the common name (CN) of the certificate. The meaning of a
          string depends on its interpretation.
        - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain some
          special characters and is from 4 to 255 characters long.

        :param access_level: The access level to the share. To grant or deny access to a share, you specify one of the
            following share access levels: - rw. Read and write (RW) access. - ro. Read- only (RO) access.
        :param access_type: The access rule type. A valid value for the share access rule type is one of the following
            values:
            - ip. Authenticates an instance through its IP address. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX.
              For example 0.0.0.0/0. - cert. Authenticates an instance through a TLS certificate. Specify the TLS
              identity as the IDENTKEY. A valid value is any string up to 64 characters long in the common name (CN) of
              the certificate. The meaning of a string depends on its interpretation.
            - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain some
              special characters and is from 4 to 32 characters long.
        :param access_to: The value that defines the access. The back end grants or denies the access to it. A valid
            value is one of these values:
            - ip. Authenticates an instance through its IP address. A valid format is XX.XX.XX.XX or XX.XX.XX.XX/XX.
              For example 0.0.0.0/0.
            - cert. Authenticates an instance through a TLS certificate. Specify the TLS identity as the IDENTKEY. A
              valid value is any string up to 64 characters long in the common name (CN) of the certificate. The meaning
              of a string depends on its interpretation.
            - user. Authenticates by a user or group name. A valid value is an alphanumeric string that can contain some
              special characters and is from 4 to 32 characters long.
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        grants = self.grant_list()
        for grant in grants:
            if (
                params.get("access_type") == grant.get("access_type")
                and params.get("access_to") == grant.get("access_to")
                and params.get("access_key") == grant.get("access_key")
            ):
                raise ApiManagerError("grant already assigned to share %s" % self.oid)

        name = "grant_add"
        steps = [self.task_path + "share_grant_add_step"]
        res = self.action(name, steps, log="Add share %s grant" % self.uuid, check=None, **params)
        return res

    @trace(op="update")
    def grant_remove(self, params):
        """Remove share grant

        :param access_id: The UUID of the access rule to which access is granted.
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        name = "grant_remove"
        steps = [self.task_path + "share_grant_remove_step"]
        res = self.action(name, steps, log="Remove share %s grant" % self.uuid, check=None, **params)
        return res

    @trace(op="update")
    def size_extend(self, params):
        """Extend manila share

        :param new_size: New size of the share, in GBs.
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        if params.get("new_size") <= self.get_size():
            raise ApiManagerError("new size must be grater than actual size")

        name = "size_extend"
        steps = [self.task_path + "share_size_extend_step"]
        res = self.action(name, steps, log="Extend manila share %s" % self.uuid, check=None, **params)
        return res

    @trace(op="update")
    def size_shrink(self, params):
        """Shrink manila share

        :param new_size: New size of the share, in GBs.
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        if params.get("new_size") >= self.get_size():
            raise ApiManagerError("new size must be lower than actual size")

        name = "size_extend"
        steps = [self.task_path + "share_size_shrink_step"]
        res = self.action(name, steps, log="Shrink manila share %s" % self.uuid, check=None, **params)
        return res

    @trace(op="update")
    def revert_to_snapshot(self, params):
        """Revert manila share to snapshot

        :param snapshot_id: The UUID of the snapshot.
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """
        name = "revert_to_snapshot"
        steps = [self.task_path + "share_revert_to_snapshot_step"]
        res = self.action(
            name,
            steps,
            log="Revert manila share %s to snapshot" % self.uuid,
            check=None,
            **params,
        )
        return res
