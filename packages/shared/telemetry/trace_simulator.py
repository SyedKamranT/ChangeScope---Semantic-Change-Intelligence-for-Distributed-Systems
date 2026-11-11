"""Five-Service Distributed Tracing Demo Simulator for OpenTelemetry Evaluation."""

import time
import uuid
from typing import Any


class TelemetryTraceGenerator:
    """Generates synthetic W3C-compliant OpenTelemetry OTLP trace graphs across 5 microservices.

    Topology:
      1. api-gateway (HTTP Ingress)
      2. order-service (Business Logic & Orchestration)
      3. payment-service (Financial Processing & Database Access)
      4. inventory-service (gRPC Stock Reservation & Database Access)
      5. notification-service (Async Event Consumer)
    """

    @classmethod
    def generate_5service_trace(
        cls,
        tenant_id: str = "tenant-demo-1",
        environment: str = "production",
        include_pii: bool = True,
        is_error: bool = False,
    ) -> dict[str, Any]:
        """Produces a single multi-hop distributed trace batch spanning 5 microservices in OTLP format."""
        trace_id = uuid.uuid4().hex
        now_ns = int(time.time() * 1_000_000_000)

        # Span IDs
        span_gw_srv = uuid.uuid4().hex[:16]
        span_gw_cli = uuid.uuid4().hex[:16]

        span_order_srv = uuid.uuid4().hex[:16]
        span_order_pay_cli = uuid.uuid4().hex[:16]
        span_order_inv_cli = uuid.uuid4().hex[:16]
        span_order_msg_prod = uuid.uuid4().hex[:16]

        span_pay_srv = uuid.uuid4().hex[:16]
        span_pay_db = uuid.uuid4().hex[:16]

        span_inv_srv = uuid.uuid4().hex[:16]
        span_inv_db = uuid.uuid4().hex[:16]

        span_notif_cons = uuid.uuid4().hex[:16]

        # 1. api-gateway spans
        gw_spans = [
            {
                "traceId": trace_id,
                "spanId": span_gw_srv,
                "name": "POST /api/v1/orders/checkout",
                "kind": 2,  # SERVER
                "startTimeUnixNano": str(now_ns),
                "endTimeUnixNano": str(now_ns + 120_000_000),
                "attributes": [
                    {"key": "http.method", "value": {"stringValue": "POST"}},
                    {"key": "http.route", "value": {"stringValue": "/api/v1/orders/checkout"}},
                    {"key": "http.status_code", "value": {"intValue": 500 if is_error else 201}},
                    *(
                        [
                            {"key": "authorization", "value": {"stringValue": "Bearer super_secret_jwt_token_xyz"}},
                            {"key": "customer.email", "value": {"stringValue": "customer.vip@company.com"}},
                            {"key": "customer.card", "value": {"stringValue": "4111 2222 3333 4444"}},
                        ]
                        if include_pii
                        else []
                    ),
                ],
                "status": {"code": 2 if is_error else 1},
            },
            {
                "traceId": trace_id,
                "spanId": span_gw_cli,
                "parentSpanId": span_gw_srv,
                "name": "POST http://order-service.internal/orders",
                "kind": 3,  # CLIENT
                "startTimeUnixNano": str(now_ns + 5_000_000),
                "endTimeUnixNano": str(now_ns + 115_000_000),
                "attributes": [
                    {"key": "http.method", "value": {"stringValue": "POST"}},
                    {"key": "http.url", "value": {"stringValue": "http://order-service.internal/orders"}},
                    {"key": "http.route", "value": {"stringValue": "/orders"}},
                    {"key": "peer.service", "value": {"stringValue": "order-service"}},
                    {"key": "http.status_code", "value": {"intValue": 500 if is_error else 201}},
                ],
                "status": {"code": 2 if is_error else 1},
            },
        ]

        # 2. order-service spans
        order_spans = [
            {
                "traceId": trace_id,
                "spanId": span_order_srv,
                "parentSpanId": span_gw_cli,
                "name": "POST /orders",
                "kind": 2,  # SERVER
                "startTimeUnixNano": str(now_ns + 10_000_000),
                "endTimeUnixNano": str(now_ns + 110_000_000),
                "attributes": [
                    {"key": "http.method", "value": {"stringValue": "POST"}},
                    {"key": "http.route", "value": {"stringValue": "/orders"}},
                    {"key": "http.status_code", "value": {"intValue": 201}},
                ],
                "status": {"code": 1},
            },
            {
                "traceId": trace_id,
                "spanId": span_order_pay_cli,
                "parentSpanId": span_order_srv,
                "name": "POST http://payment-service.internal/charges",
                "kind": 3,  # CLIENT
                "startTimeUnixNano": str(now_ns + 15_000_000),
                "endTimeUnixNano": str(now_ns + 65_000_000),
                "attributes": [
                    {"key": "http.method", "value": {"stringValue": "POST"}},
                    {"key": "http.url", "value": {"stringValue": "http://payment-service.internal/charges"}},
                    {"key": "http.route", "value": {"stringValue": "/charges"}},
                    {"key": "peer.service", "value": {"stringValue": "payment-service"}},
                    {"key": "http.status_code", "value": {"intValue": 200}},
                ],
                "status": {"code": 1},
            },
            {
                "traceId": trace_id,
                "spanId": span_order_inv_cli,
                "parentSpanId": span_order_srv,
                "name": "InventoryService/ReserveStock",
                "kind": 3,  # CLIENT
                "startTimeUnixNano": str(now_ns + 70_000_000),
                "endTimeUnixNano": str(now_ns + 95_000_000),
                "attributes": [
                    {"key": "rpc.system", "value": {"stringValue": "grpc"}},
                    {"key": "rpc.service", "value": {"stringValue": "InventoryService"}},
                    {"key": "rpc.method", "value": {"stringValue": "ReserveStock"}},
                    {"key": "peer.service", "value": {"stringValue": "inventory-service"}},
                ],
                "status": {"code": 1},
            },
            {
                "traceId": trace_id,
                "spanId": span_order_msg_prod,
                "parentSpanId": span_order_srv,
                "name": "publish orders.events",
                "kind": 4,  # PRODUCER
                "startTimeUnixNano": str(now_ns + 100_000_000),
                "endTimeUnixNano": str(now_ns + 105_000_000),
                "attributes": [
                    {"key": "messaging.system", "value": {"stringValue": "kafka"}},
                    {"key": "messaging.destination", "value": {"stringValue": "orders.events"}},
                    {"key": "messaging.operation", "value": {"stringValue": "publish"}},
                ],
                "status": {"code": 1},
            },
        ]

        # 3. payment-service spans
        payment_spans = [
            {
                "traceId": trace_id,
                "spanId": span_pay_srv,
                "parentSpanId": span_order_pay_cli,
                "name": "POST /charges",
                "kind": 2,  # SERVER
                "startTimeUnixNano": str(now_ns + 20_000_000),
                "endTimeUnixNano": str(now_ns + 60_000_000),
                "attributes": [
                    {"key": "http.method", "value": {"stringValue": "POST"}},
                    {"key": "http.route", "value": {"stringValue": "/charges"}},
                    {"key": "http.status_code", "value": {"intValue": 200}},
                ],
                "status": {"code": 1},
            },
            {
                "traceId": trace_id,
                "spanId": span_pay_db,
                "parentSpanId": span_pay_srv,
                "name": "INSERT INTO payments_db.charges",
                "kind": 3,  # CLIENT
                "startTimeUnixNano": str(now_ns + 25_000_000),
                "endTimeUnixNano": str(now_ns + 55_000_000),
                "attributes": [
                    {"key": "db.system", "value": {"stringValue": "postgresql"}},
                    {"key": "db.name", "value": {"stringValue": "payments_db"}},
                    {"key": "db.operation", "value": {"stringValue": "INSERT"}},
                    {
                        "key": "db.statement",
                        "value": {"stringValue": "INSERT INTO charges (id, amount) VALUES ('c1', 5000)"},
                    },
                ],
                "status": {"code": 1},
            },
        ]

        # 4. inventory-service spans
        inventory_spans = [
            {
                "traceId": trace_id,
                "spanId": span_inv_srv,
                "parentSpanId": span_order_inv_cli,
                "name": "InventoryService/ReserveStock",
                "kind": 2,  # SERVER
                "startTimeUnixNano": str(now_ns + 75_000_000),
                "endTimeUnixNano": str(now_ns + 90_000_000),
                "attributes": [
                    {"key": "rpc.system", "value": {"stringValue": "grpc"}},
                    {"key": "rpc.service", "value": {"stringValue": "InventoryService"}},
                    {"key": "rpc.method", "value": {"stringValue": "ReserveStock"}},
                ],
                "status": {"code": 1},
            },
            {
                "traceId": trace_id,
                "spanId": span_inv_db,
                "parentSpanId": span_inv_srv,
                "name": "UPDATE inventory_db.stock",
                "kind": 3,  # CLIENT
                "startTimeUnixNano": str(now_ns + 78_000_000),
                "endTimeUnixNano": str(now_ns + 88_000_000),
                "attributes": [
                    {"key": "db.system", "value": {"stringValue": "postgresql"}},
                    {"key": "db.name", "value": {"stringValue": "inventory_db"}},
                    {"key": "db.operation", "value": {"stringValue": "UPDATE"}},
                    {
                        "key": "db.statement",
                        "value": {"stringValue": "UPDATE stock SET reserved = reserved + 1 WHERE sku = 'item-1'"},
                    },
                ],
                "status": {"code": 1},
            },
        ]

        # 5. notification-service spans
        notif_spans = [
            {
                "traceId": trace_id,
                "spanId": span_notif_cons,
                "parentSpanId": span_order_msg_prod,
                "name": "consume orders.events",
                "kind": 5,  # CONSUMER
                "startTimeUnixNano": str(now_ns + 120_000_000),
                "endTimeUnixNano": str(now_ns + 140_000_000),
                "attributes": [
                    {"key": "messaging.system", "value": {"stringValue": "kafka"}},
                    {"key": "messaging.destination", "value": {"stringValue": "orders.events"}},
                    {"key": "messaging.operation", "value": {"stringValue": "process"}},
                ],
                "status": {"code": 1},
            }
        ]

        # Assemble OTLP resourceSpans
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "api-gateway"}},
                            {"key": "deployment.environment", "value": {"stringValue": environment}},
                            {"key": "changescope.tenant_id", "value": {"stringValue": tenant_id}},
                        ]
                    },
                    "scopeSpans": [{"spans": gw_spans}],
                },
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "order-service"}},
                            {"key": "deployment.environment", "value": {"stringValue": environment}},
                            {"key": "changescope.tenant_id", "value": {"stringValue": tenant_id}},
                        ]
                    },
                    "scopeSpans": [{"spans": order_spans}],
                },
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "payment-service"}},
                            {"key": "deployment.environment", "value": {"stringValue": environment}},
                            {"key": "changescope.tenant_id", "value": {"stringValue": tenant_id}},
                        ]
                    },
                    "scopeSpans": [{"spans": payment_spans}],
                },
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "inventory-service"}},
                            {"key": "deployment.environment", "value": {"stringValue": environment}},
                            {"key": "changescope.tenant_id", "value": {"stringValue": tenant_id}},
                        ]
                    },
                    "scopeSpans": [{"spans": inventory_spans}],
                },
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "notification-service"}},
                            {"key": "deployment.environment", "value": {"stringValue": environment}},
                            {"key": "changescope.tenant_id", "value": {"stringValue": tenant_id}},
                        ]
                    },
                    "scopeSpans": [{"spans": notif_spans}],
                },
            ]
        }
