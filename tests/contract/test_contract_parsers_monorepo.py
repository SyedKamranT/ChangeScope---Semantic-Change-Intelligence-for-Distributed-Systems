"""Contract tests validating packages/contracts parsers and semantic rule engine."""

from packages.contracts import (
    AsyncAPIParser,
    ConsumerContractProfile,
    DDLParser,
    OpenAPIParser,
    SemanticRuleEngine,
)


def test_monorepo_openapi_parser() -> None:
    """Verifies that OpenAPIParser dereferences components and extracts endpoints."""
    raw_spec = """
    openapi: 3.0.3
    info:
      title: Payments API
      version: 1.0.0
    paths:
      /payments:
        post:
          operationId: createPayment
          requestBody:
            content:
              application/json:
                schema:
                  $ref: '#/components/schemas/PaymentRequest'
          responses:
            '201':
              content:
                application/json:
                  schema:
                    $ref: '#/components/schemas/PaymentResponse'
    components:
      schemas:
        PaymentRequest:
          type: object
          properties:
            amount:
              type: number
            currency:
              type: string
        PaymentResponse:
          type: object
          properties:
            id:
              type: string
            status:
              type: string
    """
    dereferenced = OpenAPIParser.parse_spec(raw_spec)
    assert "paths" in dereferenced

    endpoints = OpenAPIParser.extract_canonical_endpoints(dereferenced)
    assert len(endpoints) == 1
    ep = endpoints[0]
    assert ep["method"] == "POST"
    assert ep["path_template"] == "/payments"
    assert ep["request_schema"]["properties"]["amount"]["type"] == "number"


def test_monorepo_asyncapi_parser() -> None:
    """Verifies that AsyncAPIParser extracts messaging operations and payload schemas."""
    raw_spec = """
    asyncapi: '2.6.0'
    info:
      title: Order Events
      version: 1.0.0
    channels:
      orders/created:
        publish:
          operationId: publishOrderCreated
          message:
            name: OrderCreated
            payload:
              type: object
              properties:
                order_id:
                  type: string
    """
    dereferenced = AsyncAPIParser.parse_spec(raw_spec)
    operations = AsyncAPIParser.extract_operations(dereferenced)
    assert len(operations) == 1
    op = operations[0]
    assert op.channel_name == "orders/created"
    assert op.action == "publish"
    assert "order_id" in op.payload_schema["properties"]


def test_monorepo_ddl_parser() -> None:
    """Verifies that DDLParser parses table column modifications."""
    sql = """
    ALTER TABLE customer_orders ALTER COLUMN status TYPE VARCHAR(16);
    ALTER TABLE customer_orders ADD COLUMN notes TEXT;
    """
    events = DDLParser.parse_sql(sql)
    assert len(events) == 2
    assert events[0].operation == "ALTER_COLUMN_TYPE"
    assert events[0].column_name == "status"
    assert events[0].length == 16
    assert events[1].operation == "ADD_COLUMN"
    assert events[1].column_name == "notes"


def test_monorepo_rule_engine_enum_narrowing() -> None:
    """Verifies that SemanticRuleEngine flags removed enum options."""
    base_ep = {
        "request_schema": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["PENDING", "APPROVED", "CANCELLED", "REFUNDED"]}},
        }
    }
    head_ep = {
        "request_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["PENDING", "APPROVED"]}  # Removed CANCELLED & REFUNDED
            },
        }
    }
    consumer = ConsumerContractProfile(
        service_id="svc-order",
        service_name="order-service",
        validation_mode="OPEN_WORLD",
        additional_properties_allowed=True,
        known_properties={"status"},
    )
    violations = SemanticRuleEngine.evaluate_contract_diff(base_ep, head_ep, [consumer])
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_code == "RULE_ENUM_NARROWED"
    assert v.severity == "BLOCKING"
    assert "CANCELLED" in v.evidence["removed_values"]
