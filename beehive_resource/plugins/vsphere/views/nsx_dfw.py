# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte

from beehive_resource.plugins.vsphere.entity.nsx_dfw import NsxDfw
from beehive_resource.plugins.vsphere.views import VsphereAPI, VsphereApiView
from flasgger import fields, Schema
from beecell.swagger import SwaggerHelper
from beehive.common.apimanager import (
    SwaggerApiView,
    ApiManagerError,
    CrudApiJobResponseSchema,
)
from re import match


class NsxDfwApiView(VsphereApiView):
    tags = ["vsphere"]
    resclass = NsxDfw
    parentclass = None


class GetContainerRequestSchema(Schema):
    container = fields.String(
        required=True,
        example="12",
        description="Container id, uuid or name",
        context="query",
    )


class RuleResponseSchema(Schema):
    disabled = fields.String(required=True, example="false")
    id = fields.String(required=True, example="133069")
    logged = fields.String(required=True, example="false")
    action = fields.String(required=True, example="allow")
    appliedToList = fields.Dict(required=False)
    sources = fields.Dict(required=False)
    destinations = fields.Dict(required=False)
    direction = fields.String(required=True, example="inout")
    name = fields.String(required=True, example="prova_section-rule-01")
    packetType = fields.String(required=True, example="any")
    precedence = fields.String(required=False, example="example")
    sectionId = fields.String(required=False, example="1024")


class SectionResponseSchema(Schema):
    generationNumber = fields.String(required=True, example="1459337065205")
    id = fields.String(required=True, example="1024")
    name = fields.String(required=True, example="prova_section")
    timestamp = fields.String(required=True, example="1459337065205")
    type = fields.String(required=True, example="LAYER3")
    rules = fields.Nested(RuleResponseSchema, required=True, allow_none=True, many=True)


class ServiceResponseSchema(Schema):
    id = fields.String(required=True, example="application-5")
    name = fields.String(required=True, example="OC4J Forms / Reports Instance (8889)")
    ports = fields.String(required=True, example="8889", allow_none=True)
    proto = fields.String(required=True, example="TCP")


class GetDfwConfigResponseSchema(Schema):
    timestamp = fields.String(required=True, example="1457281010450")
    contextId = fields.String(required=True, example="globalroot-0")
    generationNumber = fields.String(required=True, example="1459337065205")
    layer2Sections = fields.List(fields.Dict, required=True)
    layer3RedirectSections = fields.List(fields.Dict, required=True)
    layer3Sections = fields.List(fields.Dict, required=True)


class GetDfwConfig(NsxDfwApiView):
    """TODO gestire schema per section"""

    definitions = {
        "GetDfwConfigResponseSchema": GetDfwConfigResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetContainerRequestSchema)
    parameters_schema = GetContainerRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDfwConfigResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        Get dfw configuration
        Get dfw configuration
        """
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        config = dfw.get_config()
        return config


class GetDfwSectionRequestSchema(GetContainerRequestSchema):
    sid = fields.String(required=True, description="Section id", context="path")
    level = fields.String(required=True, description="Section type: l2, l3, l3r", context="path")


class GetDfwSection(NsxDfwApiView):
    definitions = {
        "SectionResponseSchema": SectionResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetDfwSectionRequestSchema)
    parameters_schema = GetContainerRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": SectionResponseSchema}})

    def get(self, controller, data, level, sid, *args, **kwargs):
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        if level == "l3":
            # get section by id
            if match("^[0-9]+$", str(sid)):
                config = dfw.get_layer3_section(oid=sid)
            # get section by name
            else:
                config = dfw.get_layer3_section(name=sid)

        return config


class CreateDfwSectionParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    name = fields.String(required=True, example="test")
    action = fields.String(
        required=False,
        example="allow",
        default="allow",
        description="Action value. Ie: allow, deny, reject",
    )
    logged = fields.String(
        required=False,
        example="true",
        default="true",
        description="If True rule is logged",
    )


class CreateDfwSectionRequestSchema(Schema):
    dfw_section = fields.Nested(CreateDfwSectionParamRequestSchema, required=True)


class CreateDfwSectionBodyRequestSchema(Schema):
    body = fields.Nested(CreateDfwSectionRequestSchema, context="body")


class CreateDfwSection(NsxDfwApiView):
    definitions = {
        "CreateDfwSectionRequestSchema": CreateDfwSectionRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateDfwSectionBodyRequestSchema)
    parameters_schema = CreateDfwSectionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        data = data.get("dfw_section")
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()

        # check section already exists
        if dfw.exist_layer3_section(name=data.get("name")) is True:
            raise ApiManagerError("Section %s already exists" % data.get("name"))

        res = dfw.create_section(data)
        return res


class DeleteDfwSectionParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    sectionid = fields.String(required=True, example=12, description="section id")


class DeleteDfwSectionRequestSchema(Schema):
    dfw_section = fields.Nested(DeleteDfwSectionParamRequestSchema, required=True)


class DeleteDfwSectionBodyRequestSchema(Schema):
    body = fields.Nested(DeleteDfwSectionRequestSchema, context="body")


class DeleteDfwSection(NsxDfwApiView):
    definitions = {
        "DeleteDfwSectionRequestSchema": DeleteDfwSectionRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteDfwSectionBodyRequestSchema)
    parameters_schema = DeleteDfwSectionRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def delete(self, controller, data, *args, **kwargs):
        data = data.get("dfw_section")
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        res = dfw.delete_section(data)
        return res


class GetDfwRuleRequestSchema(GetContainerRequestSchema):
    sid = fields.String(required=True, description="Section id", context="path")
    rid = fields.String(required=True, description="Rule id", context="path")


class GetDfwRuleResponseSchema(Schema):
    rule = fields.Nested(RuleResponseSchema, required=True, allow_none=True, many=False)


class GetDfwRule(NsxDfwApiView):
    definitions = {
        "GetDfwRuleRequestSchema": GetDfwRuleRequestSchema,
        "GetDfwRuleResponseSchema": GetDfwRuleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetDfwRuleRequestSchema)
    parameters_schema = GetContainerRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDfwRuleResponseSchema}})

    def get(self, controller, data, sid, rid, *args, **kwargs):
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        resp = dfw.get_rule(sid, rid)
        return {"rule": resp}


class CreateDfwRuleParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    sectionid = fields.String(required=True, example="1024")
    name = fields.String(required=True, example="prova_section-rule-01")
    action = fields.String(required=True, example="allow")
    direction = fields.String(required=True, example="inout", description="rule direction: in, out, inout")
    logged = fields.String(required=False, example="true", default="true")
    sources = fields.List(fields.Dict, required=False, allow_none=True)
    destinations = fields.List(fields.Dict, required=False, allow_none=True)
    services = fields.Raw(required=False, allow_none=True)
    appliedto = fields.List(fields.Dict, required=False, allow_none=True)
    precedence = fields.String(required=False, example="default", default="default")


class CreateDfwRuleRequestSchema(Schema):
    dfw_rule = fields.Nested(CreateDfwRuleParamRequestSchema, required=True)


class CreateDfwRuleBodyRequestSchema(Schema):
    body = fields.Nested(CreateDfwRuleRequestSchema, context="body")


class CreateDfwRule(NsxDfwApiView):
    definitions = {
        "CreateDfwRuleRequestSchema": CreateDfwRuleRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateDfwRuleBodyRequestSchema)
    parameters_schema = CreateDfwRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create new rule
        Create new rule
        <p>- **action** (optional): action value. Ex: allow, deny, reject</p>
        <p>- **logged** (example=true): If 'true' rule is logged</p>
        <p>- **direction**: rule direction: in, out, inout</p>
        <p>- **sources** (optional): List like <code>*[{"name":.., "value":.., "type":.., }]*</code></p>
        <pre>[{"name":"db-vm-01", "value":"vm-84", "type":"VirtualMachine"}]
        [{"name":None, "value":"10.1.1.0/24", "type":"Ipv4Address"}]
        [{"name":"WEB-LS", "value":"virtualwire-9", "type":"VirtualWire"}]
        [{"name":"SG-WEB2", "value":"securitygroup-22", "type":"SecurityGroup"}]</pre>
        <p>- **destinations** (optional): List like <code>*[{"name":.., "value":.., "type":.., }]*</code></p>
        <pre>[{"name":"WEB-LS", "value":"virtualwire-9", "type":"VirtualWire"}]
        [{"name":"APP-LS", "value":"virtualwire-10", "type":"VirtualWire"}]
        [{"name":"SG-WEB-1", "value":"securitygroup-21", "type":"SecurityGroup"}]</pre>
        <p>- **services** (optional): List like <code>*[{"name":.., "value":.., "type":.., }]*, *[{"port":.., "protocol":..}]*, *[{"protocol":.., "subprotocol":..}]*</code></p>
        <pre>[{"name":"ICMP Echo Reply", "value":"application-337","type":"Application"}]
        [{"name":"ICMP Echo", "value":"application-70", "type":"Application"}]
        [{"name":"SSH", "value":"application-223", "type":"Application"}]
        [{"name":"DHCP-Client", "value":"application-223", "type":"Application"}, {"name":"DHCP-Server", "value":"application-223", "type":"Application"}]
        [{"name":"HTTP", "value":"application-278", "type":"Application"}, {"name":"HTTPS", "value":"application-335", "type":"Application"}]
        [{u"port":u"*", u"protocol":u"*"}] -> *:*
        [{u"port":u"*", u"protocol":6}] -> tcp:*
        [{u"port":80, u"protocol":6}] -> tcp:80
        [{u"port":80, u"protocol":17}] -> udp:80
        [{u"protocol":1, u"subprotocol":8}] -> icmp:echo request</pre>
        Get id from https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml
        For icmp Summary of Message Types: **0** Echo Reply, **3** Destination Unreachable, **4** Source Quench, **5** Redirect, **8** Echo, **11** Time Exceeded, **12** Parameter Problem, **13**Timestamp, **14** Timestamp Reply, **15** Information Request, **16** Information Reply

        <p>- **appliedto** (optional): List like <code>*[{"name":.., "value":.., "type":.., }]*</code></p>
        <pre>[{"name":"DISTRIBUTED_FIREWALL", "value":"DISTRIBUTED_FIREWALL", "type":"DISTRIBUTED_FIREWALL"}]
        [{"name":"ALL_PROFILE_BINDINGS", "value":"ALL_PROFILE_BINDINGS", "type":"ALL_PROFILE_BINDINGS"}]
        [{"name":"db-vm-01", "value":"vm-84", "type":"VirtualMachine"}]
        [{"name":"SG-WEB-1", "value":"securitygroup-21", "type":"SecurityGroup"}, {"name":"SG-WEB2", "value":"securitygroup-22", "type":"SecurityGroup"}]</pre>
        """
        data = data.get("dfw_rule")
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        res = dfw.create_rule(data)
        return res


class UpdateDfwRuleParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    sectionid = fields.String(required=True, example=1024, description="section id")
    ruleid = fields.String(required=True, example=1024, description="rule id")
    ruleafter = fields.String(
        required=False,
        example=1024,
        description="rule id, put rule after this. Use with move=True",
    )
    name = fields.String(
        required=False,
        example="prova_section-rule-01",
        description="rule name. Use with move=False",
    )
    action = fields.String(
        required=False,
        example="allow",
        description="action value. Ie: allow, deny, reject. Use with move=False",
    )
    disable = fields.Boolean(
        required=False,
        example=True,
        description="True if rule is disabled. Use with move=False",
    )
    move = fields.Boolean(
        required=False,
        example=True,
        description='True if rule must be moved after "ruleafter"',
    )


class UpdateDfwRuleRequestSchema(Schema):
    dfw_rule = fields.Nested(UpdateDfwRuleParamRequestSchema, required=True)


class UpdateDfwRuleBodyRequestSchema(Schema):
    body = fields.Nested(UpdateDfwRuleRequestSchema, context="body")


class UpdateDfwRule(NsxDfwApiView):
    definitions = {
        "UpdateDfwRuleRequestSchema": UpdateDfwRuleRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateDfwRuleBodyRequestSchema)
    parameters_schema = UpdateDfwRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def put(self, controller, data, *args, **kwargs):
        """
        Update / move rule
        Update / move rule

        Update
        * **sectionid**: section id
        * **ruleid**: rule id
        * **name**: new rule name [optionale]
        * **action**: new action value. Ie: allow, deny, reject (optional)
        * **disable**: True if rule is disbles (optional)

        Move
        * **sectionid**: section id
        * **ruleid**: rule id
        * **ruleafter**: rule id, put rule after this.
        """
        data = data.get("dfw_rule")
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()

        if data.get("move", False) is True:
            res = dfw.move_rule(data)
        else:
            res = dfw.update_rule(data)
        return res


class DeleteDfwRuleParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    sectionid = fields.String(required=True, example=1024)
    ruleid = fields.String(required=True, example=102434)


class DeleteDfwRuleRequestSchema(Schema):
    dfw_rule = fields.Nested(DeleteDfwRuleParamRequestSchema)


class DeleteDfwRuleBodyRequestSchema(Schema):
    body = fields.Nested(DeleteDfwRuleRequestSchema, context="body")


class DeleteDfwRule(NsxDfwApiView):
    definitions = {
        "DeleteDfwRuleRequestSchema": DeleteDfwRuleRequestSchema,
        "CrudApiJobResponseSchema": CrudApiJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteDfwRuleBodyRequestSchema)
    parameters_schema = DeleteDfwRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiJobResponseSchema}})

    def delete(self, controller, data, *args, **kwargs):
        """
        Delete rule
        Delete rule
        """
        data = data.get("dfw_rule")
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        res = dfw.delete_rule(data)
        return res


class GetDfwExclusionListResponseSchema(Schema):
    dfw_exclusions = fields.Dict(required=True, allow_none=True)


class GetDfwExclusionList(NsxDfwApiView):
    definitions = {
        "GetDfwExclusionListResponseSchema": GetDfwExclusionListResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetContainerRequestSchema)
    parameters_schema = GetContainerRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetDfwExclusionListResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        resp = dfw.get_exclusion_list()
        return {"dfw_exclusions": resp}


class GetDfwServiceListResponseSchema(Schema):
    dfw_services = fields.Nested(ServiceResponseSchema, many=True, required=True, allow_none=True)


class GetDfwServiceList(NsxDfwApiView):
    definitions = {
        "GetDfwServiceListResponseSchema": GetDfwServiceListResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetContainerRequestSchema)
    parameters_schema = GetContainerRequestSchema
    responses = SwaggerApiView.setResponses(
        {200: {"description": "success", "schema": GetDfwServiceListResponseSchema}}
    )

    def get(self, controller, data, *args, **kwargs):
        """
        List dfw services
        List dfw services
        """
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        resp = dfw.get_services()
        return {"dfw_services": resp}


class GetDfwServiceResponseSchema(Schema):
    dfw_service = fields.Nested(ServiceResponseSchema, required=True, allow_none=True)


class GetDfwServiceRequestSchema(GetContainerRequestSchema):
    proto = fields.String(required=True, context="path", description="Protocol: TCP, UDP, ICMP")
    ports = fields.String(
        required=True,
        context="path",
        allow_none=True,
        description="Ports. Ex. 80, 8080, 7200,7210,7269,7270,7575, 9000-9100",
    )


class GetDfwService(NsxDfwApiView):
    definitions = {
        "GetDfwServiceResponseSchema": GetDfwServiceResponseSchema,
        "GetDfwServiceRequestSchema": GetDfwServiceRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetDfwServiceRequestSchema)
    parameters_schema = GetContainerRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetDfwServiceResponseSchema}})

    def get(self, controller, data, proto, ports, *args, **kwargs):
        """
        Get dfw service
        Get dfw service
        """
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        resp = dfw.get_services(proto, ports)
        return {"dfw_service": resp}


class CreateDfwServiceParamRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    proto = fields.String(required=True, example="protocol. Ex. TCP, UDP, ICMP, ..")
    ports = fields.String(
        required=True,
        example="80, 8080, 7200, 7210, 7269, 7270, 7575, 9000-9100",
        allow_none=True,
    )
    name = fields.String(required=True, example="test-service")
    desc = fields.String(required=True, example="test-service")


class CreateDfwServiceRequestSchema(Schema):
    dfw_service = fields.Nested(CreateDfwServiceParamRequestSchema, context="body", required=True)


class CreateDfwServiceBodyRequestSchema(Schema):
    body = fields.Nested(CreateDfwServiceRequestSchema, context="body")


class CreateDfwServiceResponseSchema(Schema):
    id = fields.String(resuired=True, example="test-service")


class CreateDfwService(NsxDfwApiView):
    definitions = {
        "CreateDfwServiceRequestSchema": CreateDfwServiceRequestSchema,
        "CreateDfwServiceResponseSchema": CreateDfwServiceResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateDfwServiceBodyRequestSchema)
    parameters_schema = CreateDfwServiceRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": CreateDfwServiceResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        params = data.get("dfw_service")
        cid = params.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        proto = params["proto"]
        ports = params["ports"]
        name = params["name"]
        desc = params["desc"]
        res = dfw.create_service(proto, ports, name, desc)
        return {"id": res}


class DeleteDfwServiceParamsRequestSchema(Schema):
    container = fields.String(required=True, example="12", description="Container id, uuid or name")
    id = fields.String(required=True, example=12, description="service id")


class DeleteDfwServiceRequestSchema(Schema):
    dfw_service = fields.Nested(DeleteDfwServiceParamsRequestSchema, required=True)


class DeleteDfwServiceBodyRequestSchema(Schema):
    body = fields.Nested(DeleteDfwServiceRequestSchema, context="body")


class DeleteDfwService(NsxDfwApiView):
    definitions = {
        "DeleteDfwServiceRequestSchema": DeleteDfwServiceRequestSchema,
    }
    parameters = SwaggerHelper().get_parameters(DeleteDfwServiceBodyRequestSchema)
    parameters_schema = DeleteDfwServiceRequestSchema
    responses = SwaggerApiView.setResponses(
        {
            204: {
                "description": "success",
            }
        }
    )

    def delete(self, controller, data, *args, **kwargs):
        data = data.get("dfw_service")
        cid = data.get("container")
        container = controller.get_container(cid)
        dfw = container.get_nsx_dfw()
        res = dfw.delete_service(data.get("id"))
        return None


class VsphereNsxDfwAPI(VsphereAPI):
    """Vsphere base platform api routes:"""

    @staticmethod
    def register_api(module, **kwargs):
        base = VsphereAPI.base + "/network"
        rules = [
            ("%s/nsx_dfws/sections" % base, "GET", GetDfwConfig, {}),
            ("%s/nsx_dfws/sections/<level>/<sid>" % base, "GET", GetDfwSection, {}),
            ("%s/nsx_dfws/sections" % base, "POST", CreateDfwSection, {}),
            ("%s/nsx_dfws/sections" % base, "DELETE", DeleteDfwSection, {}),
            ("%s/nsx_dfws/rules/<sid>/<rid>" % base, "GET", GetDfwRule, {}),
            ("%s/nsx_dfws/rules" % base, "POST", CreateDfwRule, {}),
            ("%s/nsx_dfws/rules" % base, "PUT", UpdateDfwRule, {}),
            ("%s/nsx_dfws/rules" % base, "DELETE", DeleteDfwRule, {}),
            ("%s/nsx_dfws/exclusion_list" % base, "GET", GetDfwExclusionList, {}),
            ("%s/nsx_dfws/services" % base, "GET", GetDfwServiceList, {}),
            ("%s/nsx_dfws/services/<proto>/<ports>" % base, "GET", GetDfwService, {}),
            ("%s/nsx_dfws/services" % base, "POST", CreateDfwService, {}),
            ("%s/nsx_dfws/services" % base, "DELETE", DeleteDfwService, {}),
        ]

        VsphereAPI.register_api(module, rules, **kwargs)
