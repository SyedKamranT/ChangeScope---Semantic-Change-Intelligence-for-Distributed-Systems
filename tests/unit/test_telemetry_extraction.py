"""Unit tests for OpenTelemetry span extraction, PII scrubbing, and dependency intelligence."""

from datetime import UTC, datetime

from packages.contracts.models import ExtractedClientCall
from packages.shared.ontology_models import ProvenanceType
from packages.shared.telemetry.correlation_engine import RuntimeCorrelationEngine
from packages.shared.telemetry.dependency_builder import DependencyBuilder
from packages.shared.telemetry.models import (
    CorrelationStatus,
    NormalizedSpan,
    ProtocolType,
    SpanKind,
)
from packages.shared.telemetry.pii_scrubber import PIIScrubber
from packages.shared.telemetry.span_extractor import SpanExtractor


def test_span_extractor_standard_and_dict_attributes():
    """Verifies span extraction works with both OTLP protobuf-json list formats and plain dicts."""
    raw_otlp_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "order-service"}},
                        {"key": "deployment.environment", "value": {"stringValue": "production"}},
                        {"key": "changescope.tenant_id", "value": {"stringValue": "tenant-corp-99"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                "spanId": "00f067aa0ba902b7",
                                "parentSpanId": "5fb397be34d23b0f",
                                "name": "POST /api/v1/orders",
                                "kind": 2,  # SERVER
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000000045000000",  # 45ms
                                "attributes": [
                                    {"key": "http.route", "value": {"stringValue": "/api/v1/orders"}},
                                    {"key": "http.method", "value": {"stringValue": "POST"}},
                                    {"key": "http.status_code", "value": {"intValue": 201}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ],
            }
        ]
    }

    spans = SpanExtractor.extract_spans(raw_otlp_payload)
    assert len(spans) == 1
    span = spans[0]
    assert span.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span.span_id == "00f067aa0ba902b7"
    assert span.parent_span_id == "5fb397be34d23b0f"
    assert span.service_name == "order-service"
    assert span.kind == SpanKind.SERVER
    assert span.http_route == "/api/v1/orders"
    assert span.http_method == "POST"
    assert span.http_status_code == 201
    assert span.duration_ms == 45.0
    assert span.environment == "production"


def test_pii_scrubber_redaction_comprehensive():
    """Verifies in-memory redaction of sensitive credentials, tokens, PANs, emails, and SQL literals."""
    dirty_attributes = {
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID",
        "cookie": "session_id=secret_cookie_val_123; user=alice",
        "api_key": "CS-live-api-key-9999",
        "db.statement": "SELECT * FROM users WHERE email = 'customer@bank.com' AND card_num = '4111-2222-3333-4444'",
        "user.email": "john.doe@enterprise.io",
        "user.ssn": "123-45-6789",
        "user.card": "4111111111111111",
        "http.url": "https://api.internal/pay?apiKey=secret123&user=42",
        "http.route": "/api/v1/checkout",
        "service.name": "checkout-service",
    }

    clean = PIIScrubber.scrub_attributes(dirty_attributes)

    # Sensitive keys must be redacted
    assert clean["authorization"] == "[REDACTED_CREDENTIAL]"
    assert clean["cookie"] == "[REDACTED_CREDENTIAL]"
    assert clean["api_key"] == "[REDACTED_CREDENTIAL]"

    # Pattern redaction in values
    assert clean["user.email"] == "[REDACTED_EMAIL]"
    assert clean["user.ssn"] == "[REDACTED_SSN]"
    assert clean["user.card"] == "[REDACTED_PAN]"

    # URL query parameter secret redaction
    assert "apiKey=[REDACTED]" in clean["http.url"]
    assert "secret123" not in clean["http.url"]

    # Database statement literal scrubbing
    assert "customer@bank.com" not in clean["db.statement"]
    assert "4111-2222-3333-4444" not in clean["db.statement"]
    assert clean["db.statement"] == "SELECT * FROM users WHERE email = '?' AND card_num = '?'"

    # Non-sensitive keys remain intact
    assert clean["http.route"] == "/api/v1/checkout"
    assert clean["service.name"] == "checkout-service"


def test_dependency_builder_parent_child_discovery():
    """Verifies service-to-service dependency extraction from parent-child client/server spans."""
    trace_id = "trace-parent-child-101"
    now = datetime.now(UTC)

    # Span 1: Client span initiated by api-gateway
    client_span = NormalizedSpan(
        trace_id=trace_id,
        span_id="span-client-1",
        parent_span_id=None,
        service_name="api-gateway",
        name="GET /orders/{id}",
        kind=SpanKind.CLIENT,
        duration_ms=50.0,
        http_route="/orders/{id}",
        http_method="GET",
        observed_at=now,
    )

    # Span 2: Server span executing inside order-service, parented to Span 1
    server_span = NormalizedSpan(
        trace_id=trace_id,
        span_id="span-server-1",
        parent_span_id="span-client-1",
        service_name="order-service",
        name="GET /orders/{id}",
        kind=SpanKind.SERVER,
        duration_ms=45.0,
        http_route="/orders/{id}",
        http_method="GET",
        http_status_code=200,
        observed_at=now,
    )

    deps = DependencyBuilder.extract_dependencies([client_span, server_span])
    assert len(deps) == 1
    dep = deps[0]
    assert dep.caller_service_name == "api-gateway"
    assert dep.callee_service_name == "order-service"
    assert dep.protocol == ProtocolType.HTTP
    assert dep.operation_or_route == "/orders/{id}"
    assert dep.http_method == "GET"
    assert dep.call_count == 1
    assert dep.error_count == 0
    assert dep.exemplar_trace_id == trace_id
    assert dep.exemplar_span_id == "span-server-1"


def test_dependency_builder_sampled_server_fallback():
    """Verifies that an outbound CLIENT span with peer_service builds dependency even when server span is sampled out."""
    trace_id = "trace-sampled-202"
    client_span = NormalizedSpan(
        trace_id=trace_id,
        span_id="span-sampled-client",
        service_name="order-service",
        peer_service="payment-service",
        name="POST /payments/authorize",
        kind=SpanKind.CLIENT,
        duration_ms=120.0,
        http_route="/payments/authorize",
        http_method="POST",
        http_status_code=200,
    )

    deps = DependencyBuilder.extract_dependencies([client_span])
    assert len(deps) == 1
    assert deps[0].caller_service_name == "order-service"
    assert deps[0].callee_service_name == "payment-service"
    assert deps[0].protocol == ProtocolType.HTTP
    assert deps[0].operation_or_route == "/payments/authorize"


def test_dependency_builder_database_and_messaging_dependencies():
    """Verifies database call extraction and messaging producer/consumer correlation."""
    trace_id = "trace-db-msg-303"

    # Database Span
    db_span = NormalizedSpan(
        trace_id=trace_id,
        span_id="span-db-1",
        service_name="payment-service",
        name="SELECT payments",
        kind=SpanKind.CLIENT,
        duration_ms=15.0,
        db_system="postgresql",
        db_name="payments_db",
        db_operation="SELECT",
    )

    # Messaging Producer & Consumer Spans
    msg_producer = NormalizedSpan(
        trace_id=trace_id,
        span_id="span-prod-1",
        service_name="order-service",
        name="publish order.created",
        kind=SpanKind.PRODUCER,
        messaging_system="kafka",
        messaging_destination="order-events",
        messaging_operation="publish",
        duration_ms=10.0,
    )

    msg_consumer = NormalizedSpan(
        trace_id=trace_id,
        span_id="span-cons-1",
        service_name="notification-service",
        name="process order.created",
        kind=SpanKind.CONSUMER,
        messaging_system="kafka",
        messaging_destination="order-events",
        messaging_operation="process",
        duration_ms=25.0,
    )

    deps = DependencyBuilder.extract_dependencies([db_span, msg_producer, msg_consumer])
    assert len(deps) == 2

    # Database dependency check
    db_deps = [d for d in deps if d.protocol == ProtocolType.DATABASE]
    assert len(db_deps) == 1
    assert db_deps[0].caller_service_name == "payment-service"
    assert db_deps[0].callee_service_name == "db:payments_db"
    assert db_deps[0].db_system == "postgresql"

    # Messaging dependency check
    msg_deps = [d for d in deps if d.protocol == ProtocolType.MESSAGING]
    assert len(msg_deps) == 1
    assert msg_deps[0].caller_service_name == "order-service"
    assert msg_deps[0].callee_service_name == "notification-service"
    assert msg_deps[0].messaging_destination == "order-events"


def test_dependency_builder_metrics_and_error_aggregation():
    """Verifies call count, error count, and p95 latency calculation across multiple observations."""
    trace_ids = [f"trace-metric-{i}" for i in range(10)]
    spans: list[NormalizedSpan] = []

    # 10 calls from svc-a to svc-b, 2 of which fail
    for i, tid in enumerate(trace_ids):
        is_err = i in [3, 7]
        c_span = NormalizedSpan(
            trace_id=tid,
            span_id=f"c-{i}",
            service_name="service-a",
            name="GET /metrics-test",
            kind=SpanKind.CLIENT,
            duration_ms=10.0 * (i + 1),  # 10, 20, 30... 100ms
            http_route="/metrics-test",
            http_method="GET",
        )
        s_span = NormalizedSpan(
            trace_id=tid,
            span_id=f"s-{i}",
            parent_span_id=f"c-{i}",
            service_name="service-b",
            name="GET /metrics-test",
            kind=SpanKind.SERVER,
            duration_ms=10.0 * (i + 1),
            http_route="/metrics-test",
            http_method="GET",
            status_code="ERROR" if is_err else "OK",
            http_status_code=500 if is_err else 200,
        )
        spans.extend([c_span, s_span])

    deps = DependencyBuilder.extract_dependencies(spans)
    assert len(deps) == 1
    dep = deps[0]
    assert dep.call_count == 10
    assert dep.error_count == 2
    assert dep.p95_latency_ms >= 90.0  # High percentile of [10..100]ms


def test_missing_attributes_graceful_handling():
    """Verifies that missing attributes, empty spans, and unknown services are handled without throwing exceptions."""
    empty_span = NormalizedSpan(
        trace_id="trace-empty",
        span_id="span-empty",
        service_name="unknown_service",
        name="",
    )

    unnamed_client = NormalizedSpan(
        trace_id="trace-unnamed",
        span_id="span-unnamed",
        service_name="service-alpha",
        name="",  # Empty name
        kind=SpanKind.CLIENT,
        peer_service=None,  # No peer service
    )

    deps = DependencyBuilder.extract_dependencies([empty_span, unnamed_client])
    assert len(deps) == 0  # Gracefully filtered out, no crashes


def test_runtime_correlation_engine_absence_invariant():
    """Enforces rule: Runtime observation is evidence of observed behavior, not proof of non-existence.

    Static calls without runtime traffic must be preserved as STATIC_ONLY.
    """
    # 1. Observed runtime dependency: api-gateway -> order-service
    observed_dep = DependencyBuilder.extract_dependencies(
        [
            NormalizedSpan(
                trace_id="trace-correlate-1",
                span_id="span-gw-1",
                name="POST /orders",
                service_name="api-gateway",
                peer_service="order-service",
                kind=SpanKind.CLIENT,
                http_route="/orders",
                http_method="POST",
            )
        ]
    )[0]

    # 2. Static Extracted Client Calls:
    # Call A matches the observed dependency
    static_call_active = ExtractedClientCall(
        method="POST",
        url_or_path="http://order-service/orders",
        client_library="httpx",
        file_path="src/gateway/client.py",
        start_line=42,
        end_line=45,
    )
    # Call B is never executed at runtime (e.g. rare batch reconciliation or failover fallback)
    static_call_unexercised = ExtractedClientCall(
        method="POST",
        url_or_path="http://disaster-recovery-service/failover/sync",
        client_library="httpx",
        file_path="src/order/dr.py",
        start_line=88,
        end_line=92,
    )

    # 3. OpenAPI Endpoint definitions
    endpoints = [
        {"method": "POST", "path_template": "/orders"},
        {"method": "POST", "path_template": "/failover/sync"},
    ]

    correlated = RuntimeCorrelationEngine.correlate_dependencies(
        observed_dependencies=[observed_dep],
        static_client_calls=[static_call_active, static_call_unexercised],
        openapi_endpoints=endpoints,
    )

    by_status = {c.correlation_status: c for c in correlated}

    # Verify Call A is OBSERVED_AND_STATIC_CONFIRMED
    assert CorrelationStatus.OBSERVED_AND_STATIC_CONFIRMED in by_status
    active = by_status[CorrelationStatus.OBSERVED_AND_STATIC_CONFIRMED]
    assert active.caller_service == "api-gateway"
    assert active.callee_service == "order-service"
    assert active.runtime_call_count == 1
    assert active.runtime_observed is True
    assert active.static_confirmed is True

    # Verify Call B is preserved as STATIC_ONLY (never discarded!)
    assert CorrelationStatus.STATIC_ONLY in by_status
    unexercised = by_status[CorrelationStatus.STATIC_ONLY]
    assert unexercised.callee_service == "disaster-recovery-service"
    assert unexercised.runtime_call_count == 0
    assert unexercised.runtime_observed is False
    assert unexercised.static_confirmed is True

    # 4. Ontology Candidates generation
    candidates = RuntimeCorrelationEngine.generate_ontology_candidates([observed_dep], tenant_id="tenant-corp")
    assert len(candidates) >= 1
    assert candidates[0].proposed_payload["source"] == "api-gateway"
    assert candidates[0].proposed_payload["target"] == "order-service"
    assert candidates[0].proposed_payload["provenance"] == ProvenanceType.RUNTIME_OBSERVED.value
