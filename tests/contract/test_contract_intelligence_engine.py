"""Comprehensive Test Suite for ChangeScope Contract Intelligence Engine.

Validates at least 30 distinct change scenarios across:
1. Structural Changes (OpenAPI / JSON Schema)
2. Semantic Changes (Currency, Time, Timezones, Identifiers, Ratios, Statuses, Polysemy)
3. Event Changes (AsyncAPI, Ordering, Versioning, Delivery Assumptions)
4. Database Changes (DDL Migrations, Dropped/Renamed Columns, Nullability, Types, Constraints)
5. Code-to-Contract Parity Alignment
"""

from packages.contracts import (
    ChangeCategory,
    ConsumerContractProfile,
    ContractIntelligenceEngine,
    DDLEvent,
    ExtractedClientCall,
    ExtractedORMModel,
    ExtractedRoute,
    FindingSeverity,
)

# ==============================================================================
# SECTION A: STRUCTURAL CHANGES (Scenarios 1 - 24)
# ==============================================================================


def test_scenario_01_field_removed_in_response():
    """Scenario 1: Field removed from response schema (BLOCKING)."""
    base = {"type": "object", "properties": {"id": {"type": "string"}, "email": {"type": "string"}}}
    head = {"type": "object", "properties": {"id": {"type": "string"}}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=True)
    f = next(f for f in findings if f.change_type == "FIELD_REMOVED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.change_category == ChangeCategory.STRUCTURAL
    assert f.confidence == 1.0
    assert "email" in f.supporting_evidence["removed_field"]


def test_scenario_02_field_removed_in_request():
    """Scenario 2: Field removed from request schema (WARNING/INFO)."""
    base = {"type": "object", "properties": {"id": {"type": "string"}, "nickname": {"type": "string"}}}
    head = {"type": "object", "properties": {"id": {"type": "string"}}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=False)
    f = next(f for f in findings if f.change_type == "FIELD_REMOVED")
    assert f.severity == FindingSeverity.WARNING
    assert f.confidence == 1.0


def test_scenario_03_required_field_added_in_request():
    """Scenario 3: Newly added field is required in request schema (BLOCKING)."""
    base = {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}
    head = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "api_key": {"type": "string"}},
        "required": ["id", "api_key"],
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=False)
    f = next(f for f in findings if f.change_type == "REQUIRED_FIELD_ADDED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.confidence == 1.0
    assert f.supporting_evidence["added_required_field"] == "api_key"


def test_scenario_04_optional_field_added_closed_world_consumer():
    """Scenario 4: Optional field added to response with closed-world consumer (BLOCKING)."""
    base = {"type": "object", "properties": {"id": {"type": "string"}}}
    head = {"type": "object", "properties": {"id": {"type": "string"}, "tags": {"type": "array"}}}
    consumers = [
        ConsumerContractProfile(
            service_id="srv-legacy",
            service_name="legacy-client",
            validation_mode="CLOSED_WORLD",
            additional_properties_allowed=False,
            known_properties={"id"},
        )
    ]
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, consumers=consumers, is_response=True)
    f = next(f for f in findings if f.change_type == "CLOSED_WORLD_COLLISION")
    assert f.severity == FindingSeverity.BLOCKING
    assert "legacy-client" in f.affected_entities


def test_scenario_05_optional_field_added_open_world():
    """Scenario 5: Optional field added to request schema (INFO)."""
    base = {"type": "object", "properties": {"id": {"type": "string"}}}
    head = {"type": "object", "properties": {"id": {"type": "string"}, "note": {"type": "string"}}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=False)
    f = next(f for f in findings if f.change_type == "OPTIONAL_FIELD_ADDED")
    assert f.severity == FindingSeverity.INFO


def test_scenario_06_primitive_type_changed_string_to_int():
    """Scenario 6: Primitive type changed from string to integer (BLOCKING)."""
    base = {"type": "object", "properties": {"user_id": {"type": "string"}}}
    head = {"type": "object", "properties": {"user_id": {"type": "integer"}}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "TYPE_CHANGED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.before_state["type"] == ["string"]
    assert f.after_state["type"] == ["integer"]


def test_scenario_07_primitive_type_changed_number_to_boolean():
    """Scenario 7: Primitive type changed from number to boolean (BLOCKING)."""
    base = {"type": "object", "properties": {"is_active": {"type": "number"}}}
    head = {"type": "object", "properties": {"is_active": {"type": "boolean"}}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "TYPE_CHANGED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_08_format_changed_datetime_to_date():
    """Scenario 8: Format changed from date-time to date (BLOCKING)."""
    base = {"type": "object", "properties": {"created_at": {"type": "string", "format": "date-time"}}}
    head = {"type": "object", "properties": {"created_at": {"type": "string", "format": "date"}}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "FORMAT_CHANGED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_09_field_became_required_in_request():
    """Scenario 9: Previously optional field became required in request (BLOCKING)."""
    base = {"type": "object", "properties": {"tenant_id": {"type": "string"}}, "required": []}
    head = {"type": "object", "properties": {"tenant_id": {"type": "string"}}, "required": ["tenant_id"]}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=False)
    f = next(f for f in findings if f.change_type == "FIELD_BECAME_REQUIRED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_10_field_became_optional_in_response():
    """Scenario 10: Previously required field became optional in response (WARNING)."""
    base = {"type": "object", "properties": {"tracking_code": {"type": "string"}}, "required": ["tracking_code"]}
    head = {"type": "object", "properties": {"tracking_code": {"type": "string"}}, "required": []}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=True)
    f = next(f for f in findings if f.change_type == "FIELD_BECAME_OPTIONAL")
    assert f.severity == FindingSeverity.WARNING


def test_scenario_11_enum_narrowed():
    """Scenario 11: Allowed enum values dropped (BLOCKING)."""
    base = {"type": "string", "enum": ["PENDING", "PROCESSING", "COMPLETED", "REJECTED"]}
    head = {"type": "string", "enum": ["PENDING", "COMPLETED"]}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "ENUM_NARROWED")
    assert f.severity == FindingSeverity.BLOCKING
    assert set(f.supporting_evidence["removed_values"]) == {"PROCESSING", "REJECTED"}


def test_scenario_12_nullability_revoked():
    """Scenario 12: Nullable field made non-nullable (BLOCKING)."""
    base = {"type": "string", "nullable": True}
    head = {"type": "string", "nullable": False}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=False)
    f = next(f for f in findings if f.change_type == "NULLABILITY_REVOKED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_13_response_became_nullable():
    """Scenario 13: Non-nullable response field can now be null (WARNING)."""
    base = {"type": "string", "nullable": False}
    head = {"type": "string", "nullable": True}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head, is_response=True)
    f = next(f for f in findings if f.change_type == "RESPONSE_BECAME_NULLABLE")
    assert f.severity == FindingSeverity.WARNING


def test_scenario_14_minimum_constraint_tightened():
    """Scenario 14: Numeric minimum tightened from 1 to 10 (BLOCKING)."""
    base = {"type": "integer", "minimum": 1}
    head = {"type": "integer", "minimum": 10}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "MINIMUM_TIGHTENED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_15_maximum_constraint_tightened():
    """Scenario 15: Numeric maximum tightened from 100 to 50 (BLOCKING)."""
    base = {"type": "number", "maximum": 100.0}
    head = {"type": "number", "maximum": 50.0}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "MAXIMUM_TIGHTENED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_16_min_length_tightened():
    """Scenario 16: String minLength increased from 3 to 8 (BLOCKING)."""
    base = {"type": "string", "minLength": 3}
    head = {"type": "string", "minLength": 8}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "MIN_LENGTH_TIGHTENED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_17_max_length_tightened():
    """Scenario 17: String maxLength decreased from 255 to 64 (BLOCKING)."""
    base = {"type": "string", "maxLength": 255}
    head = {"type": "string", "maxLength": 64}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "MAX_LENGTH_TIGHTENED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_18_pattern_regex_modified():
    """Scenario 18: Regex validation pattern changed (WARNING)."""
    base = {"type": "string", "pattern": "^[a-z]+$"}
    head = {"type": "string", "pattern": "^[a-z0-9_-]{4,16}$"}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "PATTERN_MODIFIED")
    assert f.severity == FindingSeverity.WARNING


def test_scenario_19_array_min_items_tightened():
    """Scenario 19: Array minItems increased from 1 to 5 (BLOCKING)."""
    base = {"type": "array", "minItems": 1, "items": {"type": "string"}}
    head = {"type": "array", "minItems": 5, "items": {"type": "string"}}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "MIN_ITEMS_TIGHTENED")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_20_default_value_shift():
    """Scenario 20: Default value shifted from 'PENDING' to 'QUEUED' (WARNING)."""
    base = {"type": "string", "default": "PENDING"}
    head = {"type": "string", "default": "QUEUED"}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "DEFAULT_VALUE_SHIFT")
    assert f.severity == FindingSeverity.WARNING


def test_scenario_21_endpoint_removed_with_active_client_call():
    """Scenario 21: Entire OpenAPI endpoint removed while caller in code exists (BLOCKING)."""
    base_spec = """
    openapi: 3.0.3
    info: {title: Orders API, version: 1.0.0}
    paths:
      /api/v1/orders/{id}:
        get:
          operationId: getOrder
          responses:
            '200':
              content:
                application/json:
                  schema: {type: object}
    """
    head_spec = """
    openapi: 3.0.3
    info: {title: Orders API, version: 2.0.0}
    paths: {}
    """
    client_calls = [
        ExtractedClientCall(
            method="GET",
            url_or_path="/api/v1/orders/{id}",
            client_library="httpx",
            file_path="src/order_client.py",
            start_line=42,
            end_line=45,
        )
    ]
    findings = ContractIntelligenceEngine.analyze_openapi_diff(base_spec, head_spec, client_calls=client_calls)
    f = next(f for f in findings if f.change_type == "ENDPOINT_REMOVED")
    assert f.severity == FindingSeverity.BLOCKING
    assert "active_client_callers" in f.supporting_evidence
    assert f.supporting_evidence["active_client_callers"][0]["file"] == "src/order_client.py"


def test_scenario_22_http_method_changed_on_path():
    """Scenario 22: HTTP method dropped/changed on existing path (BLOCKING)."""
    base_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths:
      /items:
        post:
          operationId: createItem
          responses: {'201': {description: created}}
    """
    head_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths:
      /items:
        put:
          operationId: updateItem
          responses: {'200': {description: ok}}
    """
    findings = ContractIntelligenceEngine.analyze_openapi_diff(base_spec, head_spec)
    f = next(f for f in findings if f.change_type == "HTTP_METHOD_CHANGED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.supporting_evidence["dropped_method"] == "POST"


def test_scenario_23_response_status_code_removed():
    """Scenario 23: Response status 200 removed from endpoint (BLOCKING)."""
    base_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths:
      /ping:
        get:
          responses:
            '200':
              content:
                application/json:
                  schema: {type: string}
    """
    head_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths:
      /ping:
        get:
          responses:
            '204':
              description: No content
    """
    findings = ContractIntelligenceEngine.analyze_openapi_diff(base_spec, head_spec)
    f = next(f for f in findings if f.change_type == "RESPONSE_STATUS_REMOVED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.supporting_evidence["status_code"] == "200"


def test_scenario_24_required_parameter_added():
    """Scenario 24: New required query parameter added (BLOCKING)."""
    base_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths:
      /search:
        get:
          parameters: []
          responses: {'200': {description: ok}}
    """
    head_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths:
      /search:
        get:
          parameters:
            - name: q
              in: query
              required: true
              schema: {type: string}
          responses: {'200': {description: ok}}
    """
    findings = ContractIntelligenceEngine.analyze_openapi_diff(base_spec, head_spec)
    f = next(f for f in findings if f.change_type == "REQUIRED_PARAMETER_ADDED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.supporting_evidence["param_name"] == "q"


# ==============================================================================
# SECTION B: SEMANTIC CHANGES (Scenarios 25 - 33)
# ==============================================================================


def test_scenario_25_currency_unit_shift_cents_to_dollars():
    """Scenario 25: Field 'amount' changes from USD cents to USD dollars without type change (BLOCKING)."""
    base = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Total transaction amount in USD cents",
                "x-unit": "cents",
            }
        },
    }
    head = {
        "type": "object",
        "properties": {
            "amount": {
                "type": "integer",
                "description": "Total transaction amount in USD dollars",
                "x-unit": "USD",
            }
        },
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "CURRENCY_UNIT_CHANGE")
    assert f.change_category == ChangeCategory.SEMANTIC
    assert f.severity == FindingSeverity.BLOCKING
    assert f.confidence == 0.90
    assert "100x" in (f.uncertainty_explanation or "")


def test_scenario_26_currency_unit_shift_dollars_to_cents():
    """Scenario 26: Sub-unit shift from dollars to cents in reverse."""
    base = {"type": "number", "description": "Payment amount in dollars"}
    head = {"type": "number", "description": "Payment amount in cents"}
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "CURRENCY_UNIT_CHANGE")
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_27_time_unit_shift_seconds_to_milliseconds():
    """Scenario 27: Timeout changes from seconds to milliseconds (BLOCKING)."""
    base = {
        "type": "object",
        "properties": {
            "rpc_timeout": {
                "type": "integer",
                "description": "Downstream RPC call timeout in seconds",
            }
        },
    }
    head = {
        "type": "object",
        "properties": {
            "rpc_timeout": {
                "type": "integer",
                "description": "Downstream RPC call timeout in milliseconds",
            }
        },
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "TIME_UNIT_CHANGE")
    assert f.change_category == ChangeCategory.SEMANTIC
    assert f.severity == FindingSeverity.BLOCKING
    assert f.confidence == 0.85
    assert "1000x" in (f.uncertainty_explanation or "")


def test_scenario_28_timestamp_utc_to_local_shift():
    """Scenario 28: Timestamp interpretation changes from UTC to local server time (WARNING)."""
    base = {
        "type": "object",
        "properties": {
            "event_time": {
                "type": "string",
                "description": "Event occurrence timestamp in UTC ISO-8601",
            }
        },
    }
    head = {
        "type": "object",
        "properties": {
            "event_time": {
                "type": "string",
                "description": "Event occurrence local timestamp without timezone offset",
            }
        },
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "TIMESTAMP_TIMEZONE_SHIFT")
    assert f.change_category == ChangeCategory.SEMANTIC
    assert f.severity == FindingSeverity.WARNING


def test_scenario_29_customer_id_vs_account_id_collision():
    """Scenario 29: Customer identifier substituted with Account identifier (BLOCKING)."""
    base = {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "Customer UUID"},
            "balance": {"type": "number"},
        },
    }
    head = {
        "type": "object",
        "properties": {
            "account_id": {"type": "string", "description": "Billing account UUID"},
            "balance": {"type": "number"},
        },
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "IDENTIFIER_SEMANTIC_COLLISION")
    assert f.change_category == ChangeCategory.SEMANTIC
    assert f.severity == FindingSeverity.BLOCKING
    assert "Customer" in str(f.before_state)
    assert "Account" in str(f.after_state)


def test_scenario_30_percentage_ratio_vs_points():
    """Scenario 30: Scale changes from decimal ratio (0.0-1.0) to percentage points (0-100) (BLOCKING)."""
    base = {
        "type": "object",
        "properties": {
            "tax_rate": {
                "type": "number",
                "description": "Sales tax rate as a decimal fraction (0.0 to 1.0)",
            }
        },
    }
    head = {
        "type": "object",
        "properties": {
            "tax_rate": {
                "type": "number",
                "description": "Sales tax rate in percentage points (0 to 100)",
            }
        },
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "PERCENTAGE_VS_ABSOLUTE")
    assert f.change_category == ChangeCategory.SEMANTIC
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_31_status_definition_change():
    """Scenario 31: Status enum structurally identical but lifecycle meaning modified (WARNING)."""
    base = {
        "type": "string",
        "enum": ["PENDING", "SETTLED"],
        "description": "Order state: PENDING means placed and awaiting payment capture",
    }
    head = {
        "type": "string",
        "enum": ["PENDING", "SETTLED"],
        "description": "Order state: PENDING means payment captured, awaiting warehouse dispatch",
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "STATUS_DEFINITION_CHANGE")
    assert f.severity == FindingSeverity.WARNING
    assert f.confidence == 0.75


def test_scenario_32_polysemy_meaning_shift():
    """Scenario 32: Property 'balance' bounded concept shifts from ledger to credit (WARNING)."""
    base = {
        "type": "number",
        "x-business-concept": "LedgerAccountBalance",
    }
    head = {
        "type": "number",
        "x-business-concept": "AvailableCreditLimit",
    }
    findings = ContractIntelligenceEngine.analyze_json_schema_diff(base, head)
    f = next(f for f in findings if f.change_type == "POLYSEMY_MEANING_SHIFT")
    assert f.severity == FindingSeverity.WARNING


def test_scenario_33_candidate_ai_interpreter_permission_shift():
    """Scenario 33: NLP candidate interpretation of permission tier shift (is_ai_inferred=True)."""
    base_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths: {}
    components:
      schemas:
        User:
          type: object
          properties:
            ssn:
              type: string
              description: Confidential internal PII field
    """
    head_spec = """
    openapi: 3.0.3
    info: {title: Test, version: 1.0.0}
    paths: {}
    components:
      schemas:
        User:
          type: object
          properties:
            ssn:
              type: string
              description: Public unrestricted display field
    """
    findings = ContractIntelligenceEngine.analyze_openapi_diff(base_spec, head_spec)
    f = next(f for f in findings if f.change_type == "ACCESS_SCOPE_SEMANTIC_SHIFT")
    assert f.is_ai_inferred is True
    assert f.confidence <= 0.75
    assert "PII" in str(f.supporting_evidence) or "internal" in str(f.supporting_evidence)


# ==============================================================================
# SECTION C: EVENT CHANGES (Scenarios 34 - 37)
# ==============================================================================


def test_scenario_34_asyncapi_channel_removed():
    """Scenario 34: Event channel removed from AsyncAPI spec (BLOCKING)."""
    base = """
    asyncapi: '2.6.0'
    info: {title: Events, version: 1.0.0}
    channels:
      telemetry/metrics:
        publish:
          operationId: pubMetrics
          message: {payload: {type: object}}
    """
    head = """
    asyncapi: '2.6.0'
    info: {title: Events, version: 1.0.0}
    channels: {}
    """
    findings = ContractIntelligenceEngine.analyze_asyncapi_diff(base, head)
    f = next(f for f in findings if f.change_type == "CHANNEL_REMOVED")
    assert f.change_category == ChangeCategory.EVENT
    assert f.severity == FindingSeverity.BLOCKING
    assert "telemetry/metrics" in f.affected_entities


def test_scenario_35_asyncapi_event_ordering_dropped():
    """Scenario 35: Strict FIFO ordering dropped on event channel (BLOCKING)."""
    base = """
    asyncapi: '2.6.0'
    info: {title: Ledger Events, version: 1.0.0}
    channels:
      orders/transactions:
        publish:
          operationId: pubTx
          bindings:
            ordering: strict
          message: {payload: {type: object}}
    """
    head = """
    asyncapi: '2.6.0'
    info: {title: Ledger Events, version: 1.0.0}
    channels:
      orders/transactions:
        publish:
          operationId: pubTx
          bindings:
            ordering: none
          message: {payload: {type: object}}
    """
    findings = ContractIntelligenceEngine.analyze_asyncapi_diff(base, head)
    f = next(f for f in findings if f.change_type == "EVENT_ORDERING_SHIFT")
    assert f.change_category == ChangeCategory.EVENT
    assert f.severity == FindingSeverity.BLOCKING
    assert f.confidence == 0.95


def test_scenario_36_asyncapi_delivery_guarantee_downgraded():
    """Scenario 36: Delivery guarantee changed from at-least-once to at-most-once (BLOCKING)."""
    base = """
    asyncapi: '2.6.0'
    info: {title: Events, version: 1.0.0}
    channels:
      billing/charges:
        publish:
          operationId: pubCharge
          bindings:
            delivery_guarantee: at-least-once
          message: {payload: {type: object}}
    """
    head = """
    asyncapi: '2.6.0'
    info: {title: Events, version: 1.0.0}
    channels:
      billing/charges:
        publish:
          operationId: pubCharge
          bindings:
            delivery_guarantee: at-most-once
          message: {payload: {type: object}}
    """
    findings = ContractIntelligenceEngine.analyze_asyncapi_diff(base, head)
    f = next(f for f in findings if f.change_type == "DELIVERY_ASSUMPTION_CHANGED")
    assert f.change_category == ChangeCategory.EVENT
    assert f.severity == FindingSeverity.BLOCKING


def test_scenario_37_asyncapi_unversioned_breaking_evolution():
    """Scenario 37: Breaking payload schema change on unversioned event channel (BLOCKING)."""
    base = """
    asyncapi: '2.6.0'
    info: {title: Events, version: 1.0.0}
    channels:
      orders:
        publish:
          operationId: pubOrders
          message:
            payload:
              type: object
              properties:
                order_id: {type: string}
                amount: {type: number}
    """
    head = """
    asyncapi: '2.6.0'
    info: {title: Events, version: 1.0.0}
    channels:
      orders:
        publish:
          operationId: pubOrders
          message:
            payload:
              type: object
              properties:
                # amount removed - breaking change!
                order_id: {type: string}
    """
    findings = ContractIntelligenceEngine.analyze_asyncapi_diff(base, head)
    f = next(f for f in findings if f.change_type == "UNVERSIONED_BREAKING_EVOLUTION")
    assert f.change_category == ChangeCategory.EVENT
    assert f.severity == FindingSeverity.BLOCKING


# ==============================================================================
# SECTION D: DATABASE CHANGES (Scenarios 38 - 43)
# ==============================================================================


def test_scenario_38_column_dropped_with_active_orm_model():
    """Scenario 38: Column dropped from table queried by active ORM model (BLOCKING)."""
    ev = DDLEvent(operation="DROP_COLUMN", table_name="users", column_name="hashed_password")
    models = [
        ExtractedORMModel(
            model_name="User",
            table_name="users",
            file_path="src/models.py",
            start_line=10,
            end_line=25,
            columns=[{"name": "hashed_password"}],
        )
    ]
    findings = ContractIntelligenceEngine.analyze_database_diff([ev], active_orm_models=models)
    f = next(f for f in findings if f.change_type == "COLUMN_DROPPED")
    assert f.change_category == ChangeCategory.DATABASE
    assert f.severity == FindingSeverity.BLOCKING
    assert f.file_path == "src/models.py"


def test_scenario_39_column_renamed():
    """Scenario 39: Column renamed in table (BLOCKING)."""
    ev = DDLEvent(
        operation="RENAME_COLUMN",
        table_name="orders",
        column_name="status",
        metadata={"old_column_name": "status", "new_column_name": "order_state"},
    )
    findings = ContractIntelligenceEngine.analyze_database_diff([ev])
    f = next(f for f in findings if f.change_type == "COLUMN_RENAMED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.after_state["column"] == "order_state"


def test_scenario_40_column_type_altered_shrunk():
    """Scenario 40: Column length shrunk from VARCHAR(64) to VARCHAR(16) (BLOCKING)."""
    ev = DDLEvent(
        operation="ALTER_COLUMN_TYPE",
        table_name="accounts",
        column_name="slug",
        data_type="VARCHAR(16)",
        old_data_type="VARCHAR(64)",
        length=16,
        old_length=64,
    )
    findings = ContractIntelligenceEngine.analyze_database_diff([ev])
    f = next(f for f in findings if f.change_type == "COLUMN_TYPE_CHANGED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.supporting_evidence["is_shrunk"] is True


def test_scenario_41_column_not_null_without_default():
    """Scenario 41: Column altered to NOT NULL without a default value (BLOCKING)."""
    ev = DDLEvent(
        operation="ALTER_COLUMN_NULLABLE",
        table_name="payments",
        column_name="currency",
        is_nullable=False,
        metadata={},
    )
    findings = ContractIntelligenceEngine.analyze_database_diff([ev])
    f = next(f for f in findings if f.change_type == "COLUMN_NOT_NULL_WITHOUT_DEFAULT")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.confidence == 0.95


def test_scenario_42_table_dropped_with_active_orm():
    """Scenario 42: Table dropped that is mapped in code (BLOCKING)."""
    ev = DDLEvent(operation="DROP_TABLE", table_name="legacy_tokens")
    models = [
        ExtractedORMModel(
            model_name="LegacyToken",
            table_name="legacy_tokens",
            file_path="src/tokens.py",
            start_line=5,
            end_line=15,
        )
    ]
    findings = ContractIntelligenceEngine.analyze_database_diff([ev], active_orm_models=models)
    f = next(f for f in findings if f.change_type == "TABLE_DROPPED")
    assert f.severity == FindingSeverity.BLOCKING
    assert f.file_path == "src/tokens.py"


def test_scenario_43_unique_constraint_added():
    """Scenario 43: Unique constraint added to table (WARNING)."""
    ev = DDLEvent(
        operation="ADD_CONSTRAINT_UNIQUE",
        table_name="customers",
        metadata={"constraint_name": "uq_customers_email"},
    )
    findings = ContractIntelligenceEngine.analyze_database_diff([ev])
    f = next(f for f in findings if f.change_type == "DATABASE_CONSTRAINT_ADDED")
    assert f.severity == FindingSeverity.WARNING


# ==============================================================================
# SECTION E: CODE-TO-CONTRACT ALIGNMENT (Scenario 44)
# ==============================================================================


def test_scenario_44_uncontracted_code_endpoint():
    """Scenario 44: Route implemented in code is uncontracted in OpenAPI (WARNING)."""
    code_routes = [
        ExtractedRoute(
            method="POST",
            path_template="/internal/debug/dump",
            handler_name="debug_dump",
            file_path="src/debug.py",
            start_line=15,
            end_line=25,
            framework="FastAPI",
        )
    ]
    openapi_endpoints = [{"method": "GET", "path_template": "/health"}]
    findings = ContractIntelligenceEngine.analyze_code_contract_alignment(code_routes, openapi_endpoints)
    f = next(f for f in findings if f.change_type == "UNCONTRACTED_ENDPOINT")
    assert f.severity == FindingSeverity.WARNING
    assert f.file_path == "src/debug.py"
    assert "/internal/debug/dump" in f.affected_entities[0]
