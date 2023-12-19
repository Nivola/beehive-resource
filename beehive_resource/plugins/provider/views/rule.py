# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2020-2022 Regione Piemonte
# (C) Copyright 2018-2023 CSI-Piemonte
from copy import deepcopy

from beehive_resource.plugins.provider.entity.rule import ComputeRule
from beehive_resource.plugins.provider.entity.security_group import SecurityGroup
from beehive_resource.plugins.provider.entity.zone import ComputeZone
from beehive_resource.view import ListResourcesRequestSchema, ResourceResponseSchema
from beehive.common.apimanager import (
    PaginatedResponseSchema,
    SwaggerApiView,
    GetApiObjectRequestSchema,
    CrudApiObjectJobResponseSchema,
)
from beecell.swagger import SwaggerHelper
from flasgger import fields, Schema
from beehive_resource.plugins.provider.views import (
    ProviderAPI,
    LocalProviderApiView,
    CreateProviderResourceRequestSchema,
    UpdateProviderResourceRequestSchema,
)


class ProviderRule(LocalProviderApiView):
    resclass = ComputeRule
    parentclass = ComputeZone


class ListRulesRequestSchema(ListResourcesRequestSchema):
    compute_zone = fields.String(context="query", description="super zone id or uuid")
    security_groups = fields.String(context="query", description="list of comma separated security group id or uuid")
    source = fields.String(
        required=False,
        allow_none=True,
        description="a dictionary with source type and value. " "Syntax SecurityGroup:<uuid> or Cidr:<uuid>",
    )
    destination = fields.String(
        required=False,
        allow_none=True,
        description="a dictionary with destination type and value. " "Syntax SecurityGroup:<uuid> or Cidr:<uuid>",
    )
    service = fields.String(
        required=False,
        allow_none=True,
        description="describe protocol and ports to use in rule." "Syntax <proto>:<port>",
    )


class ListRulesParamsResponseSchema(ResourceResponseSchema):
    pass


class ListRulesResponseSchema(PaginatedResponseSchema):
    rules = fields.Nested(ListRulesParamsResponseSchema, many=True, required=True, allow_none=True)


class ListRules(ProviderRule):
    definitions = {
        "ListRulesResponseSchema": ListRulesResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(ListRulesRequestSchema)
    parameters_schema = ListRulesRequestSchema
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": ListRulesResponseSchema}})

    def get(self, controller, data, *args, **kwargs):
        """
        List rules
        List rules
        <p>**filter by**: tags, super_zone, security_group</p>
        <p>**Attributes** params:</p>
        <pre>
        {
          "configs": {
            "source": {
              "type": "SecurityGroup",
              "value": 1903
            },
            "destination": {
              "type": "SecurityGroup",
              "value": 1903
            },
            "service": {
              "protocol": "*",
              "port": "*"
            }
          }
        }
        </pre>
        """
        zone_id = data.get("super_zone", None)
        sg_ids = data.get("security_groups", None)
        if zone_id is not None:
            return self.get_resources_by_parent(controller, zone_id, "SuperZone")
        elif sg_ids is not None:
            data["objdef"] = ComputeRule.objdef
            data["entity_class"] = ComputeRule
            return self.get_directed_linked_resources(controller, sg_ids, SecurityGroup, "rule", **data)

        source = data.get("source", None)
        dest = data.get("destination", None)
        service = data.get("service", None)
        attrib = []
        service_attribs = []
        if source is not None:
            source = source.split(":")
            attrib.append('"source":{')
            attrib.append('"value":"%s"' % (source[1]))
            attrib.append("}")

        if dest is not None:
            dest = dest.split(":")
            attrib.append('"destination":{')
            attrib.append('"value":"%s"' % (dest[1]))
            attrib.append("}")

        if service is not None:
            service = service.split(":")
            if len(service) > 1:
                if service[0] == "1":
                    service_attribs.append('"service":{"protocol":"%s","subprotocol":"%s"}' % (service[0], service[1]))
                    service_attribs.append('"service":{"subprotocol":"%s","protocol":"%s"}' % (service[1], service[0]))
                else:
                    service_attribs.append('"service":{"protocol":"%s","port":"%s"}' % (service[0], service[1]))
                    service_attribs.append('"service":{"port":"%s","protocol":"%s"}' % (service[1], service[0]))
            else:
                service_attribs.append('"service":{"protocol":"%s"' % service[0])

        data["attribute"] = []
        if len(attrib) > 0:
            if len(service_attribs) == 0:
                attribute = deepcopy(attrib)
                attribute = "%" + "%".join(attribute) + "%"
                attribute = attribute.replace("/", "%")
                data["attribute"].append(attribute)
            else:
                for service_attrib in service_attribs:
                    attribute = deepcopy(attrib)
                    attribute.append(service_attrib)
                    attribute = "%" + "%".join(attribute) + "%"
                    attribute = attribute.replace("/", "%")
                    data["attribute"].append(attribute)
        else:
            for service_attrib in service_attribs:
                attribute = [service_attrib]
                attribute = "%" + "%".join(attribute) + "%"
                attribute = attribute.replace("/", "%")
                data["attribute"].append(attribute)

        return self.get_resources(controller, **data)


class GetRuleParamsResponseSchema(ResourceResponseSchema):
    pass


class GetRuleResponseSchema(Schema):
    rule = fields.Nested(GetRuleParamsResponseSchema, required=True, allow_none=True)


class GetRule(ProviderRule):
    definitions = {
        "GetRuleResponseSchema": GetRuleResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({200: {"description": "success", "schema": GetRuleResponseSchema}})

    def get(self, controller, data, oid, *args, **kwargs):
        """
        Get rule
        Get rule
        <p>**Attributes** params:</p>
        <pre>
        {
          "configs": {
            "source": {
              "type": "SecurityGroup",
              "value": 1903
            },
            "destination": {
              "type": "SecurityGroup",
              "value": 1903
            },
            "service": {
              "protocol": "*",
              "port": "*"
            }
          }
        }
        </pre>
        """
        return self.get_resource(controller, oid)


class CreateRuleSourceRequestSchema(Schema):
    type = fields.String(
        required=True,
        example="SecurityGroup",
        description="Source/destination type supported: SecurityGroup, Instance, Cidr",
    )
    value = fields.String(
        required=True,
        example="3151",
        description="value is the id of the object 3151 or a cidr 10.102.185.0/24",
    )


class CreateRuleServiceRequestSchema(Schema):
    port = fields.String(
        required=False,
        example="*",
        description="can be an integer between 0 and 65535 or a range "
        "with start and end in the same interval. Range format is <start>-<end>",
    )
    protocol = fields.String(
        required=False,
        example="*",
        description="Supported **protocol** are only 6 [tcp], 17 [udp], 1 [icmp], * [all]",
    )
    subprotocol = fields.String(required=False, example=17, description="use this param with icmp")


class CreateRuleParamRequestSchema(CreateProviderResourceRequestSchema):
    compute_zone = fields.String(required=True, example="1", description="parent compute zone id or uuid")
    source = fields.Nested(
        CreateRuleSourceRequestSchema,
        required=True,
        allow_none=True,
        description="a dictionary with source type and value.",
    )
    destination = fields.Nested(
        CreateRuleSourceRequestSchema,
        required=True,
        allow_none=True,
        description="a dictionary with destination type and value.",
    )
    service = fields.Nested(
        CreateRuleServiceRequestSchema,
        required=True,
        allow_none=True,
        description="describe protocol and ports to use in rule",
    )
    reserved = fields.Boolean(
        required=False,
        missing=False,
        description="Flag to use when rule must be reserved " "to admin management",
    )


class CreateRuleRequestSchema(Schema):
    rule = fields.Nested(CreateRuleParamRequestSchema)


class CreateRuleBodyRequestSchema(Schema):
    body = fields.Nested(CreateRuleRequestSchema, context="body")


class CreateRule(ProviderRule):
    definitions = {
        "CreateRuleRequestSchema": CreateRuleRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(CreateRuleBodyRequestSchema)
    parameters_schema = CreateRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def post(self, controller, data, *args, **kwargs):
        """
        Create rule
        Create rule

        - **reserved**: use True to manage rule from business service that only admin can remove

        - **source**: source SecurityGroup, Instance, Cidr. Syntax {'type':.., 'value':..}
        - **destination**: destination SecurityGroup, Instance, Cidr. Syntax {'type':.., 'value':..}

        - **service**:

        {"port":"*", "protocol":"*"} to enable all protocols and all ports
        {"port":"*", "protocol":6} to enable tcp protocol and all ports
        {"port":80, "protocol":6} to enable tcp protocol and port 80
        {"port":80-90, "protocol":6} to enable tcp protocol and ports 80 to 90
        {"port":80, "protocol":17} to enable udp protocol and port 80
        {"protocol":1, "subprotocol":8} to enable icmp - echo request

        Supported **protocol** are only 6 [tcp], 17 [udp], 1 [icmp], * [all].
        **port** can be an integer between 0 and 65535 or a range with start
        and end in the same interval. Range format is <start>-<end>.
        """
        return self.create_resource(controller, data)


class UpdateRuleParamRequestSchema(UpdateProviderResourceRequestSchema):
    pass


class UpdateRuleRequestSchema(Schema):
    rule = fields.Nested(UpdateRuleParamRequestSchema)


class UpdateRuleBodyRequestSchema(GetApiObjectRequestSchema):
    body = fields.Nested(UpdateRuleRequestSchema, context="body")


class UpdateRule(ProviderRule):
    definitions = {
        "UpdateRuleRequestSchema": UpdateRuleRequestSchema,
        "CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema,
    }
    parameters = SwaggerHelper().get_parameters(UpdateRuleBodyRequestSchema)
    parameters_schema = UpdateRuleRequestSchema
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def put(self, controller, data, oid, *args, **kwargs):
        """
        Update rule
        Update rule
        """
        return self.update_resource(controller, oid, data)


## delete
class DeleteRule(ProviderRule):
    definitions = {"CrudApiObjectJobResponseSchema": CrudApiObjectJobResponseSchema}
    parameters = SwaggerHelper().get_parameters(GetApiObjectRequestSchema)
    responses = SwaggerApiView.setResponses({202: {"description": "success", "schema": CrudApiObjectJobResponseSchema}})

    def delete(self, controller, data, oid, *args, **kwargs):
        """
        Delete rule
        Delete rule
        """
        return self.expunge_resource(controller, oid)


class RuleProviderAPI(ProviderAPI):
    """ """

    @staticmethod
    def register_api(module, **kwargs):
        base = ProviderAPI.base
        rules = [
            # sites
            # - filter by: tags
            # - filter by: super_zone, security_group
            ("%s/rules" % base, "GET", ListRules, {}),
            ("%s/rules/<oid>" % base, "GET", GetRule, {}),
            ("%s/rules" % base, "POST", CreateRule, {}),
            ("%s/rules/<oid>" % base, "PUT", UpdateRule, {}),
            ("%s/rules/<oid>" % base, "DELETE", DeleteRule, {}),
        ]

        ProviderAPI.register_api(module, rules, **kwargs)
