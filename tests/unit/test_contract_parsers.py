"""Unit tests for OpenAPI 3.0/3.1 and DDL migration parsers."""

from changescope.analysis.contract.ddl_parser import DDLParser
from changescope.analysis.contract.openapi_parser import OpenAPIParser


def test_openapi_parsing_and_ref_resolution():
    spec_yaml = """
openapi: 3.0.3
info:
  title: Order Service API
  version: 1.0.0
paths:
  /api/v1/orders:
    post:
      summary: Create an order
      operationId: createOrder
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'
components:
  schemas:
    CreateOrderRequest:
      type: object
      required:
        - item_id
      properties:
        item_id:
          type: string
        status:
          type: string
          enum: [PENDING, APPROVED, CANCELLED]
    OrderResponse:
      type: object
      properties:
        id:
          type: string
        status:
          type: string
"""
    dereferenced = OpenAPIParser.parse_spec(spec_yaml)
    assert dereferenced["openapi"] == "3.0.3"

    endpoints = OpenAPIParser.extract_canonical_endpoints(dereferenced)
    assert len(endpoints) == 1
    ep = endpoints[0]
    assert ep["method"] == "POST"
    assert ep["path_template"] == "/api/v1/orders"
    assert ep["operation_id"] == "createOrder"

    # Check that $ref was resolved
    req_schema = ep["request_schema"]
    assert req_schema["type"] == "object"
    assert "status" in req_schema["properties"]
    assert req_schema["properties"]["status"]["enum"] == ["PENDING", "APPROVED", "CANCELLED"]

    resp_schema = ep["response_schemas"]["201"]
    assert "id" in resp_schema["properties"]


def test_ddl_parser_alter_and_add_columns():
    sql = """
    ALTER TABLE orders ADD COLUMN tracking_number VARCHAR(64) NOT NULL;
    ALTER TABLE items ALTER COLUMN sku TYPE VARCHAR(16);
    ALTER TABLE users DROP COLUMN legacy_token;
    """
    events = DDLParser.parse_sql(sql)
    assert len(events) == 3

    ev1 = events[0]
    assert ev1.operation == "ADD_COLUMN"
    assert ev1.table_name == "orders"
    assert ev1.column_name == "tracking_number"
    assert ev1.length == 64
    assert ev1.is_nullable is False

    ev2 = events[1]
    assert ev2.operation == "ALTER_COLUMN_TYPE"
    assert ev2.table_name == "items"
    assert ev2.column_name == "sku"
    assert ev2.length == 16

    ev3 = events[2]
    assert ev3.operation == "DROP_COLUMN"
    assert ev3.table_name == "users"
    assert ev3.column_name == "legacy_token"
