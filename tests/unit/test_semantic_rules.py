"""Unit tests for the Deterministic Semantic Change Rule Engine."""

from changescope.analysis.contract.ddl_parser import DDLEvent
from changescope.analysis.static.models import ExtractedORMModel
from changescope.reasoning.models import ConsumerContractProfile
from changescope.reasoning.rule_engine import SemanticRuleEngine


def test_rule_enum_narrowing_detected():
    base_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["PENDING", "APPROVED", "CANCELLED"]}},
        }
    }
    head_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                # Producer dropped 'CANCELLED'
                "status": {"type": "string", "enum": ["PENDING", "APPROVED"]}
            },
        }
    }
    consumers = [
        ConsumerContractProfile(
            service_id="srv-checkout",
            service_name="checkout-service",
            validation_mode="OPEN_WORLD",
            additional_properties_allowed=True,
            known_properties={"status"},
        )
    ]

    violations = SemanticRuleEngine.evaluate_contract_diff(base_endpoint, head_endpoint, consumers)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_code == "RULE_ENUM_NARROWED"
    assert v.severity == "BLOCKING"
    assert "CANCELLED" in v.evidence["removed_values"]


def test_rule_closed_world_collision_detected():
    base_endpoint = {
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount": {"type": "number"},
                },
            }
        }
    }
    head_endpoint = {
        "response_schemas": {
            "200": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount": {"type": "number"},
                    # Producer added optional field 'warehouse_zone'
                    "warehouse_zone": {"type": "string"},
                },
            }
        }
    }
    # Consumer enforces additionalProperties: false
    consumers = [
        ConsumerContractProfile(
            service_id="srv-legacy",
            service_name="legacy-client",
            validation_mode="CLOSED_WORLD",
            additional_properties_allowed=False,
            known_properties={"order_id", "amount"},
        )
    ]

    violations = SemanticRuleEngine.evaluate_contract_diff(base_endpoint, head_endpoint, consumers)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_code == "RULE_CLOSED_WORLD_COLLISION"
    assert v.severity == "BLOCKING"
    assert "warehouse_zone" in v.evidence["conflicting_properties"]


def test_rule_constraint_tightening_detected():
    base_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                "quantity": {"type": "integer", "minimum": 1},
                "code": {"type": "string", "pattern": "^[a-zA-Z0-9]+$"},
            },
        }
    }
    head_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                # Tightened minimum to 5 and pattern to only uppercase
                "quantity": {"type": "integer", "minimum": 5},
                "code": {"type": "string", "pattern": "^[A-Z]+$"},
            },
        }
    }
    violations = SemanticRuleEngine.evaluate_contract_diff(base_endpoint, head_endpoint, [])
    assert len(violations) == 2
    rule_codes = {v.rule_code for v in violations}
    assert "RULE_MINIMUM_TIGHTENED" in rule_codes
    assert "RULE_PATTERN_TIGHTENED" in rule_codes


def test_rule_default_value_shift_detected():
    base_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
            },
        }
    }
    head_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                # Shifted default from 50 to 10
                "limit": {"type": "integer", "default": 10},
            },
        }
    }
    violations = SemanticRuleEngine.evaluate_contract_diff(base_endpoint, head_endpoint, [])
    assert len(violations) == 1
    assert violations[0].rule_code == "RULE_DEFAULT_VALUE_SHIFT"
    assert violations[0].severity == "WARNING"


def test_rule_ddl_mutations_detected():
    ddl_events = [
        DDLEvent(
            operation="ALTER_COLUMN_TYPE",
            table_name="orders",
            column_name="tracking_id",
            data_type="VARCHAR(16)",
            length=16,
        )
    ]
    active_models = [
        ExtractedORMModel(
            model_name="OrderModel",
            table_name="orders",
            file_path="src/models/order.py",
            start_line=12,
            end_line=45,
        )
    ]

    violations = SemanticRuleEngine.check_ddl_mutations(ddl_events, active_models, "billing-service")
    assert len(violations) == 1
    assert violations[0].rule_code == "RULE_DDL_COLUMN_SHRUNK"
    assert violations[0].severity == "BLOCKING"
    assert violations[0].file_path == "src/models/order.py"


def test_safe_changes_produce_zero_violations():
    # Adding an optional field when all consumers are OPEN_WORLD
    base_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
    }
    head_endpoint = {
        "request_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "nickname": {"type": "string"},
            },
        }
    }
    open_consumers = [
        ConsumerContractProfile(
            service_id="srv-web",
            service_name="web-client",
            validation_mode="OPEN_WORLD",
            additional_properties_allowed=True,
            known_properties={"name"},
        )
    ]
    violations = SemanticRuleEngine.evaluate_contract_diff(base_endpoint, head_endpoint, open_consumers)
    assert len(violations) == 0
