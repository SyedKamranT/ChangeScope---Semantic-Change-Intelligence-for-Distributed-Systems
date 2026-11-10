"""Unit tests for AsyncAPI v2 and v3 Specification Parser."""

from changescope.analysis.contract.asyncapi_parser import AsyncAPIParser


def test_asyncapi_v2_parsing():
    v2_yaml = """
asyncapi: 2.6.0
info:
  title: Order Events Stream
  version: 1.0.0
channels:
  orders/created:
    publish:
      summary: Order created notification
      operationId: publishOrderCreated
      message:
        name: OrderCreatedEvent
        payload:
          $ref: '#/components/schemas/OrderCreatedPayload'
    subscribe:
      summary: Listen for order creation
      operationId: consumeOrderCreated
      message:
        name: OrderCreatedEvent
        payload:
          $ref: '#/components/schemas/OrderCreatedPayload'
components:
  schemas:
    OrderCreatedPayload:
      type: object
      required:
        - order_id
        - amount
      properties:
        order_id:
          type: string
        amount:
          type: number
        currency:
          type: string
          default: USD
"""
    spec = AsyncAPIParser.parse_spec(v2_yaml)
    assert spec["asyncapi"] == "2.6.0"

    operations = AsyncAPIParser.extract_operations(spec)
    assert len(operations) == 2

    pub_op = next(op for op in operations if op.action == "publish")
    assert pub_op.channel_name == "orders/created"
    assert pub_op.operation_id == "publishOrderCreated"
    assert pub_op.message_name == "OrderCreatedEvent"
    assert "order_id" in pub_op.payload_schema["properties"]
    assert pub_op.payload_schema["properties"]["currency"]["default"] == "USD"

    sub_op = next(op for op in operations if op.action == "subscribe")
    assert sub_op.channel_name == "orders/created"
    assert sub_op.operation_id == "consumeOrderCreated"


def test_asyncapi_v3_parsing():
    v3_yaml = """
asyncapi: 3.0.0
info:
  title: Payments Event Bus
  version: 2.0.0
channels:
  paymentProcessed:
    address: payments.processed
    messages:
      paymentMessage:
        name: PaymentProcessedMessage
        payload:
          type: object
          properties:
            paymentId:
              type: string
            status:
              type: string
              enum: [SUCCESS, REJECTED]
operations:
  onPaymentProcessed:
    action: send
    channel:
      address: payments.processed
    messages:
      - name: PaymentProcessedMessage
        payload:
          type: object
          properties:
            paymentId:
              type: string
            status:
              type: string
              enum: [SUCCESS, REJECTED]
"""
    spec = AsyncAPIParser.parse_spec(v3_yaml)
    assert spec["asyncapi"] == "3.0.0"

    operations = AsyncAPIParser.extract_operations(spec)
    assert len(operations) == 1
    op = operations[0]
    assert op.action == "publish"  # send normalized to publish
    assert op.channel_name == "payments.processed"
    assert op.operation_id == "onPaymentProcessed"
    assert "status" in op.payload_schema["properties"]
    assert op.payload_schema["properties"]["status"]["enum"] == ["SUCCESS", "REJECTED"]
