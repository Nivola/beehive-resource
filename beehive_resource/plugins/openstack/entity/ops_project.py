# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beecell.simple import id_gen, truncate
from beecell.types.type_dict import dict_get
from beehive.common.apimanager import ApiManagerError
from beehive_resource.plugins.openstack.entity.ops_server import OpenstackServer
from beehive_resource.plugins.openstack.entity.ops_volume import OpenstackVolume
from beehive_resource.plugins.openstack.entity.ops_network import OpenstackNetwork
from beehive_resource.plugins.openstack.entity.ops_router import OpenstackRouter
from beehive_resource.plugins.openstack.entity.ops_security_group import (
    OpenstackSecurityGroup,
)
from beehive_resource.plugins.openstack.entity.ops_heat import (
    OpenstackHeatStack,
    OpenstackHeatTemplate,
    OpenstackHeatSWconfig,
    OpenstackHeatSWdeployment,
)
from beehive_resource.plugins.openstack.entity.ops_share import OpenstackShare
from beehive.common.data import trace
from beedrones.openstack.client import OpenstackError, OpenstackNotFound
from beehive_resource.plugins.openstack.entity import OpenstackResource


class OpenstackProject(OpenstackResource):
    objdef = "Openstack.Domain.Project"
    objuri = "projects"
    objname = "project"
    objdesc = "Openstack projects"

    default_tags = ["openstack"]
    task_path = "beehive_resource.plugins.openstack.task_v2.ops_project.ProjectTask."

    def __init__(self, *args, **kvargs):
        """ """
        OpenstackResource.__init__(self, *args, **kvargs)

        self.level = self.attribs.get("level", None)

        # child classes
        self.child_classes = [
            OpenstackServer,
            OpenstackVolume,
            OpenstackNetwork,
            OpenstackRouter,
            OpenstackSecurityGroup,
            OpenstackHeatStack,
            # OpenstackHeatTemplate,
            # OpenstackHeatSWconfig,
            # OpenstackHeatSWdeployment,
            OpenstackShare,
        ]

    #
    # discover, synchronize
    #
    @staticmethod
    def discover_new(container, ext_id, res_ext_ids):
        """Discover method used when synchronize beehive container with remote platform.

        :param container: client used to comunicate with remote platform
        :param ext_id: remote platform entity id
        :param res_ext_ids: list of remote platform entity ids from beehive resources
        :return: list of tuple (resource class, ext_id, parent_id, resource class objdef, name, parent_class)
        :raises ApiManagerError:
        """
        # get projects from openstack
        if ext_id is not None:
            items = container.conn.project.get(oid=ext_id)
        else:
            items = container.conn.project.list()

        def get_level(items, oid):
            pid = items[oid][1]["parent_id"]
            did = items[oid][1]["domain_id"]
            if pid is None or pid == did:
                return 0
            else:
                level = get_level(items, str(pid))
            return level + 1

        level_items = {}
        for item in items:
            level_items[item["id"]] = (0, item)

        for k, v in level_items.items():
            level = get_level(level_items, k)
            v[1]["level"] = level
            level_items[k] = (level, v[1])

        items = sorted(level_items.values(), key=lambda item: item[0])
        items = [i[1] for i in items]

        # add new item to final list
        res = []
        for item in items:
            if item["id"] not in res_ext_ids:
                level = None
                parent_id = None
                name = item["name"]
                if name is None or name == "":
                    name = item["id"]
                level = item["level"]
                if level == 0:
                    parent_id = "%s-%s" % (container.oid, item["domain_id"])
                else:
                    parent_id = item["parent_id"]

                res.append(
                    (
                        OpenstackProject,
                        item["id"],
                        parent_id,
                        OpenstackProject.objdef,
                        name,
                        level,
                    )
                )

        return res

    @staticmethod
    def discover_died(container):
        """Discover method used when check if resource already exists in remote platform or was been modified.

        :param container: client used to comunicate with remote platform
        :return: list of remote entities
        :raise ApiManagerError:
        """
        return container.conn.project.list()

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

        # get parent domain
        parent = container.get_resource_by_extid(parent_id)

        # first level project
        if level > 0:
            objid = parent.objid + "." + id_gen()
        # other level organization
        else:
            objid = "%s//%s" % (parent.objid, id_gen())

        res = {
            "resource_class": resclass,
            "objid": objid,
            "name": name,
            "ext_id": ext_id,
            "active": True,
            "desc": resclass.objdesc,
            "attrib": {"level": level},
            "parent": parent.oid,
            "tags": resclass.default_tags,
        }
        return res

    #
    # internal list, get, create, update, delete
    #
    @staticmethod
    def customize_list(controller, entities, container, *args, **kvargs):
        """Post list function. Extend this function to execute some operation after entity was created. Used only for
        synchronous creation.

        :param controller: controller instance
        :param entities: list of entities
        :param container: container instance
        :param args: custom params
        :param kvargs: custom params
        :return: None
        :raises ApiManagerError:
        """
        remote_entities = container.conn.project.list()

        # create index of remote objs
        remote_entities_index = {i["id"]: i for i in remote_entities}

        for entity in entities:
            try:
                ext_obj = remote_entities_index.get(entity.ext_id, None)
                entity.set_physical_entity(ext_obj)

            except:
                container.logger.warn("", exc_info=True)
        return entities

    def post_get(self):
        """Post get function. This function is used in get_entity method.
        Extend this function to extend description info returned after query.

        :return:
        :raises ApiManagerError:
        """
        try:
            if self.ext_id is not None:
                ext_obj = self.container.conn.project.get(oid=self.ext_id)
                self.set_physical_entity(ext_obj)
        except:
            self.logger.warn("", exc_info=True)

    @staticmethod
    def pre_create(controller, container, *args, **kvargs):
        """Check input params before resource creation. This function is used in container resource_factory method.

        :param controller: resource controller instance
        :param container: container instance
        :param list args: custom params
        :param dict kvargs: custom params
        :param kvargs.objid: resource objid
        :param kvargs.parent: resource parent id
        :param kvargs.cid: container id
        :param kvargs.name: resource name
        :param kvargs.desc: resource desc
        :param kvargs.ext_id: resource ext_id
        :param kvargs.active: resource active
        :param kvargs.attribute: attributes
        :param kvargs.tags: comma separated resource tags to assign [default='']
        :param kvargs.domain_id: parent domain id or uuid
        :param kvargs.project_id: parent project id or uuid
        :param kvargs.enabled: True if enable [default=True]
        :param kvargs.is_domain: parent domain id or uuid [default=False]
        :return: kvargs
        :raise ApiManagerError:
        """
        from .ops_domain import OpenstackDomain

        parent = kvargs.get("project_id", None)
        domain_id = kvargs["domain_id"]

        # get parent domain
        domain = controller.get_resource(domain_id, entity_class=OpenstackDomain)

        if parent is not None:
            prj = container.get_resource(parent, entity_class=OpenstackProject)
            parent_level = int(prj.attribs.get("level", 0))
            level = parent_level + 1
            objid = "%s.%s" % (prj.objid, id_gen())
            parent = prj
            parent_ext_id = parent.ext_id
        else:
            objid = "%s//%s" % (domain.objid, id_gen())
            parent = domain
            parent_ext_id = None
            level = 0

        data = {
            "objid": objid,
            "domain_ext_id": domain.ext_id,
            "parent": parent.oid,
            "parent_extid": parent_ext_id,
            "attribute": {"level": level},
        }
        kvargs.update(data)

        steps = [
            OpenstackProject.task_path + "create_resource_pre_step",
            OpenstackProject.task_path + "project_create_physical_step",
            OpenstackProject.task_path + "project_register_securitygroup_step",
            OpenstackProject.task_path + "create_resource_post_step",
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
            OpenstackProject.task_path + "update_resource_pre_step",
            OpenstackProject.task_path + "project_update_physical_step",
            OpenstackProject.task_path + "update_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    def pre_patch(self, *args, **kvargs):
        """Pre patch function. This function is used in update method. Extend this function to manipulate and
        validate patch input params.

        :param list args: custom params
        :param dict kvargs: custom params
        :return: kvargs
        :raise ApiManagerError:
        """
        # assign admin and trilio_backup_role roles to project
        if self.ext_id is not None:
            user = self.container.conn.identity.user.list(name="admin")[0]
            role_admin = self.container.conn.identity.role.list(name="admin")[0]
            role_trilio = self.container.conn.identity.role.list(name="trilio_backup_role")[0]
            self.container.conn.project.assign_member(self.ext_id, user["id"], role_admin["id"])
            self.logger.debug("Assign admin role for project %s to admin user" % self.ext_id)
            self.container.conn.project.assign_member(self.ext_id, user["id"], role_trilio["id"])
            self.logger.debug("Assign trilio_backup_role role for project %s to admin user" % self.ext_id)

        steps = [
            OpenstackProject.task_path + "patch_resource_pre_step",
            OpenstackProject.task_path + "patch_resource_post_step",
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
        kvargs["sgs"] = []
        sgs, total = self.container.get_resources(
            parent=self.oid,
            run_customize=False,
            entity_class=OpenstackSecurityGroup,
            objdef=OpenstackSecurityGroup.objdef,
        )
        for i in sgs:
            kvargs["sgs"].append(i.oid)

        kvargs["child_num"] -= total

        steps = [
            OpenstackProject.task_path + "expunge_resource_pre_step",
            OpenstackProject.task_path + "project_deregister_securitygroup_step",
            OpenstackProject.task_path + "project_delete_physical_step",
            OpenstackProject.task_path + "expunge_resource_post_step",
        ]
        kvargs["steps"] = steps
        return kvargs

    #
    # info
    #
    def info(self):
        """Get info.

        :return: Dictionary with capabilities.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OpenstackResource.info(self)

        if self.ext_obj is not None:
            info["details"].update({"enabled": self.ext_obj.get("enabled"), "level": self.level})

        return info

    def detail(self):
        """Get details.

        :return: Dictionary with resource details.
        :rtype: dict
        :raises ApiManagerError: raise :class:`.ApiManagerError`
        """
        info = OpenstackResource.detail(self)

        if self.ext_obj is not None:
            info["details"].update({"enabled": self.ext_obj.get("enabled"), "level": self.level})

        return info

    @trace(op="use")
    def get_quotas(self):
        """Get quotas set for the project.

        :return: Dictionary with quotas.
        :raise ApiManagerError:
        """
        self.verify_permisssions("use")

        res = {}
        try:
            res = self.container.conn.project.get_quotas(oid=self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)

        self.logger.debug("Get openstack project %s quotas: %s" % (self.name, res))
        return res

    @trace(op="update")
    def set_quotas(self, quotas):
        """Set quotas for the project.

        :param quotas: list of {'type':.., 'quota':.., 'value':..}
        :return: Dictionary with quotas.
        :raise ApiManagerError:
        """
        self.verify_permisssions("update")

        if isinstance(quotas, list) is False:
            raise ApiManagerError("project quotas must be a list")

        res = {}
        try:
            for quota in quotas:
                self.logger.debug("Set openstack project %s - quota: %s" % (self.name, quota))
                res = self.container.conn.project.update_quota(
                    self.ext_id,
                    quota.get("type"),
                    quota.get("quota"),
                    quota.get("value"),
                )
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex)

        self.logger.debug("Set openstack project %s quotas: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_limits(self):
        """Gets limits of the project.

        :return: Dictionary with limits.
        :raise ApiManagerError:
        """
        self.verify_permisssions("use")

        try:
            res = self.container.conn.project.get_limits()
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack project %s limits: %s" % (self.name, res))
        return res

    @trace(op="use")
    def get_members(self):
        """Gets members of the project

        :return: members list
        :raise ApiManagerError:
        """
        self.verify_permisssions("use")

        try:
            res = self.container.conn.project.get_members(self.ext_id)
        except Exception as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Get openstack project %s members: %s" % (self.name, res))
        return res

    @trace(op="update")
    def assign_member(self, user, role):
        """Assign member to openstack project

        :param user: openstack user id
        :param role: openstack role id
        :return: openstack user id
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("update")

        try:
            res = self.container.conn.project.assign_member(self.ext_id, user, role)
        except OpenstackError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Assign user %s with role %s to openstack project %s" % (user, role, self.name))
        return self.uuid

    @trace(op="update")
    def deassign_member(self, user, role):
        """Deassign member from openstack project

        :param user: openstack user id
        :param role: openstack role id
        :return: openstack user id
        :raise ApiManagerError:
        """
        # verify permissions
        self.verify_permisssions("update")

        try:
            res = self.container.conn.project.remove_member(self.ext_id, user, role)
        except OpenstackError as ex:
            self.logger.error(ex, exc_info=True)
            raise ApiManagerError(ex, code=400)

        self.logger.debug("Deassign user %s with role %s from openstack project %s" % (user, role, self.name))
        return self.uuid

    @trace(op="use")
    def get_security_groups(self):
        """Gets security groups of the project

        :return: security groups list
        :raise ApiManagerError:
        """
        self.verify_permisssions("use")

        sgs, total = self.controller.get_resources(
            parent=self.oid,
            type=OpenstackSecurityGroup.objdef,
            objdef=OpenstackSecurityGroup.objdef,
            parents={self.oid: {"id": self.oid, "name": self.name, "uuid": self.uuid}},
        )

        self.logger.debug("Get openstack project %s security groups: %s" % (self.name, sgs))
        return sgs, total

    #
    # backup job
    #

    def check_workload(self, trilio_conn, workload_id):
        """check if trilio workload exits and is not empty

        :param trilio_conn: trilio connection
        :param workload_id: trilio workload id
        :return: True or False
        """
        workload = trilio_conn.workload.get(workload_id)
        if workload == {}:
            raise ApiManagerError("trilio workload %s does not exist" % workload_id, code=404)
        if len(workload.get("instances")) > 0:
            raise ApiManagerError("trilio workload %s contains servers" % workload_id, code=409)
        return True

    @trace(op="use")
    def get_backup_jobs(self):
        """Get configured trilio workloads

        :return: trilio workloads list
        """
        self.verify_permisssions("use")

        trilio_conn = self.get_trilio_manager(self.oid)
        res = []
        try:
            if trilio_conn is not None:
                workloads = trilio_conn.workload.list()
                for workload in workloads:
                    workload = trilio_conn.workload.get(workload.get("id"))
                    res.append(workload)
            self.logger.debug("get trilio workloads: %s" % truncate(res))
        except OpenstackError as ex:
            raise ApiManagerError("trilio workload query error: %s" % ex.value, code=ex.code)
        return res

    @trace(op="update")
    def create_backup_job(
        self,
        name,
        instances,
        metadata={},
        desc=None,
        fullbackup_interval=2,
        start_date=None,
        end_date=None,
        start_time="0:00 AM",
        interval="24hrs",
        snapshots_to_retain=4,
        timezone="Europe/Rome",
        job_type="Parallel",
    ):
        """Create trilio workload

        :param name: workload name
        :param instances: workload protected servers
        :param metadata: workload metadata
        :param desc: workload description
        :param fullbackup_interval: workload interval between full backup
        :param start_date: workload start date
        :param end_date: workload end date
        :param start_time: workload start time
        :param interval: workload interval
        :param snapshots_to_retain: workload number of snapshot to retain
        :param timezone: workload timezone
        :param job_type: workload job type. Can be Serial or Parallel
        :return: trilio workload
        """
        self.verify_permisssions("update")

        trilio_conn = self.get_trilio_manager(self.oid)
        res = None
        try:
            if trilio_conn is not None:
                workloads = trilio_conn.workload.list()
                if len(workloads) == 5:
                    raise OpenstackError("no more job backup allowed")

                # get workload types
                if job_type not in ["Parallel", "Serial"]:
                    raise OpenstackError("trilio backup workload type %s does not exists" % job_type)
                workload_type_id = [t["id"] for t in trilio_conn.workload.types() if t["name"] == job_type][0]

                res = trilio_conn.workload.add(
                    name,
                    workload_type_id,
                    instances,
                    metadata=metadata,
                    desc=desc,
                    fullbackup_interval=fullbackup_interval,
                    start_date=start_date,
                    end_date=end_date,
                    start_time=start_time,
                    interval=interval,
                    snapshots_to_retain=snapshots_to_retain,
                    timezone=timezone,
                )
        except OpenstackError as ex:
            raise ApiManagerError(ex.value, code=ex.code)
        return res

    @trace(op="update")
    def update_backup_job(
        self,
        job_id,
        name=None,
        instances=None,
        metadata=None,
        desc=None,
        fullbackup_interval=None,
        start_date=None,
        end_date=None,
        start_time=None,
        interval=None,
        snapshots_to_retain=None,
        timezone=None,
        enabled=None,
    ):
        """Update trilio workload

        :param job_id: trilio workload id
        :param name: workload name
        :param instances: workload protected servers
        :param metadata: workload metadata
        :param desc: workload description
        :param fullbackup_interval: workload interval between full backup
        :param start_date: workload start date
        :param end_date: workload end date
        :param start_time: workload start time
        :param interval: workload interval
        :param snapshots_to_retain: workload number of snapshot to retain
        :param timezone: workload timezone
        :param enabled: workload enable state
        :return: True
        """
        self.verify_permisssions("update")

        trilio_conn = self.get_trilio_manager(self.oid)
        try:
            if trilio_conn is not None:
                workload = trilio_conn.workload.get(job_id)
                if workload == {}:
                    raise OpenstackNotFound("backup job %s does not exist" % job_id)
                if workload["status"] not in ["available"]:
                    raise OpenstackNotFound("backup job %s is in a wrong status" % job_id)
                if instances is not None and len(instances) > 10:
                    raise OpenstackNotFound("backup job %s must contains max 10 instances" % job_id)

                if enabled is None:
                    enabled = dict_get(workload, "jobschedule.enabled")

                trilio_conn.workload.update(
                    job_id,
                    name=name,
                    instances=instances,
                    metadata=metadata,
                    desc=desc,
                    fullbackup_interval=fullbackup_interval,
                    start_date=start_date,
                    end_date=end_date,
                    start_time=start_time,
                    interval=interval,
                    snapshots_to_retain=snapshots_to_retain,
                    timezone=timezone,
                    enabled=enabled,
                )
        except OpenstackError as ex:
            raise ApiManagerError(ex.value, code=400)
        return True

    @trace(op="update")
    def delete_backup_job(self, job_id):
        """Delete trilio workload

        :param job_id: trilio workload id
        :return: True
        """
        self.verify_permisssions("update")

        trilio_conn = self.get_trilio_manager(self.oid)
        try:
            if trilio_conn is not None:
                workload = trilio_conn.workload.get(job_id)
                if workload == {}:
                    raise OpenstackNotFound("backup job %s does not exist" % job_id)
                if workload["status"] not in ["available"]:
                    raise OpenstackNotFound("backup job %s is in a wrong status" % job_id)
                # if len(workload.get('instances')) > 0:
                #     raise OpenstackError('backup job %s contains instances' % job_id, code=409)

                trilio_conn.workload.delete(job_id)
        except OpenstackError as ex:
            raise ApiManagerError(ex.value, code=ex.code)
        return True

    #
    # backup restore point
    #
    def get_backup_restore_points(self, job_id):
        """get backup restore points

        :param job_id: job id
        :return: snapshots list
        """
        # snapshot_number = dict_get(job, 'schedule.retention_policy_value')
        # snapshot_number = 30
        # now = datetime.today()
        # date_from = '%s-%s-%sT' % (now.year, now.month, now.day - snapshot_number)
        # date_to = '%s-%s-%sT' % (now.year, now.month, now.day)

        trilio_conn = self.get_trilio_manager(self.oid)

        snapshots = trilio_conn.snapshot.list(all=True, workload_id=job_id)
        # snapshots = trilio_conn.snapshot.list(all=True, workload_id=workload_id, date_from=date_from, date_to=date_to)
        self.logger.debug("get backup job %s restore points: %s" % (job_id, snapshots))
        res = [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "desc": s.get("description"),
                "created": s.get("created_at"),
                "type": s.get("snapshot_type"),
                "status": s.get("status"),
            }
            for s in snapshots
        ]
        return res

    def get_backup_restore_point(self, restore_point_id):
        """get backup restore point

        :param restore_point_id: restore point id
        :return: snapshot
        """
        trilio_conn = self.get_trilio_manager(self.oid)

        s = trilio_conn.snapshot.get(restore_point_id)
        self.logger.debug("get backup job restore point %s: %s" % (restore_point_id, s))
        instances = [{"id": i.get("id")} for i in s.get("instances", [])]
        metadata = [
            {
                "id": m.get("id"),
                "created": m.get("created_at"),
                "key": m.get("key"),
                "value": m.get("value"),
            }
            for m in s.get("metadata", [])
        ]
        res = {
            "id": s.get("id"),
            "name": s.get("name"),
            "desc": s.get("description"),
            "created": s.get("created_at"),
            "finished": s.get("finished_at"),
            "updated": s.get("updated_at"),
            "type": s.get("snapshot_type"),
            "status": s.get("status"),
            "size": {
                "tot": s.get("size"),
                "restore": s.get("restore_size"),
                "uploaded": s.get("uploaded_size"),
            },
            "time_taken": s.get("time_taken"),
            "progress": s.get("progress_percent"),
            "message": {
                "warning": s.get("warning_msg"),
                "progress": s.get("progress_msg"),
                "error": s.get("error_msg"),
            },
            "metadata": metadata,
            "instances": instances,
        }
        return res

    @trace(op="update")
    def add_backup_restore_point(self, *args, **kvargs):
        """add physical backup restore point

        :param kvargs.job_id: restore point job id
        :param kvargs.restore_point_name: restore point name
        :param kvargs.restore_point_desc: restore point description
        :param kvargs.restore_point_full: if True make a full restore point. If False make an incremental restore point
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            name = kvargs.get("restore_point_name")
            kvargs["restore_point_name"] = name
            kvargs["restore_point_desc"] = kvargs.get("restore_point_desc", name)
            kvargs["restore_point_full"] = kvargs.get("restore_point_full", True)
            # if self.has_backup() is False:
            #     raise ApiManagerError('server %s has no backup job associated' % self.oid)
            return kvargs

        steps = [OpenstackProject.task_path + "project_add_backup_restore_point"]
        res = self.action(
            "add_backup_restore_point",
            steps,
            log="Add backup restore point",
            check=check,
            **kvargs,
        )
        return res

    @trace(op="update")
    def del_backup_restore_point(self, *args, **kvargs):
        """delete physical backup restore point

        :param restore_point_job_id: restore point job id
        :param restore_point_id: restore point id
        :return: {'taskid':..}, 202
        :raise ApiManagerError:
        """

        def check(*args, **kvargs):
            workload_id = kvargs["restore_point_job_id"]
            restore_point = kvargs["restore_point_id"]
            return kvargs

        steps = [OpenstackProject.task_path + "project_del_backup_restore_point"]
        res = self.action(
            "del_backup_restore_point",
            steps,
            log="Delete backup restore point",
            check=check,
            **kvargs,
        )
        return res
