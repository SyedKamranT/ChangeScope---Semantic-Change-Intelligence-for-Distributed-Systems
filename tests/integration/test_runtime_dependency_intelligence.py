"""Integration tests for Runtime Dependency Intelligence and OpenTelemetry Collector Ingestion."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.main import app
from apps.worker.tasks import aggregate_otel_traces_async
from packages.shared.database import async_session_factory
from packages.shared.models import OutboxEvent, RuntimeDependency, RuntimeTraceSpan, Tenant
from packages.shared.security.jwt_handler import create_access_token
from packages.shared.telemetry.trace_simulator import TelemetryTraceGenerator


@pytest.fixture
async def client():
    """Provides async HTTP client bound to FastAPI application."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _get_auth_headers(tenant_id: str, role: str = "engineer") -> dict[str, str]:
    """Generates valid bearer authentication header for testing."""
    token = create_access_token(
        {
            "sub": f"user-{tenant_id}",
            "tenant_id": tenant_id,
            "roles": [role],
            "email": f"dev@{tenant_id}.io",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_5service_telemetry_ingestion_and_runtime_graph(client: AsyncClient):
    """Verifies end-to-end ingestion of 5 microservices, database, and messaging dependencies."""
    tenant_id = "tenant-e2e-demo"

    # Ensure tenant exists in DB for foreign key constraints
    async with async_session_factory() as session:
        existing = await session.get(Tenant, tenant_id)
        if not existing:
            session.add(Tenant(id=tenant_id, name="Demo E2E Tenant", slug=tenant_id, tier="enterprise"))
            await session.commit()

    # 1. Generate 5-service OTLP trace batch with sensitive PII and DB calls
    trace_payload = TelemetryTraceGenerator.generate_5service_trace(
        tenant_id=tenant_id,
        environment="production",
        include_pii=True,
        is_error=False,
    )

    # 2. Ingest via standard OTLP/HTTP gateway endpoint
    response = await client.post(
        "/v1/traces",
        json=trace_payload,
        headers={"X-Tenant-ID": tenant_id},
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ACCEPTED"
    assert res_data["spans_ingested"] >= 10
    assert res_data["dependencies_observed"] >= 5

    # 3. Verify PII scrubbing in database buffered spans
    async with async_session_factory() as session:
        spans_res = await session.execute(select(RuntimeTraceSpan).where(RuntimeTraceSpan.tenant_id == tenant_id))
        buffered_spans = spans_res.scalars().all()
        assert len(buffered_spans) >= 10

        # Check that sensitive values were sanitized
        for s in buffered_spans:
            attrs = s.attributes or {}
            if "authorization" in attrs:
                assert attrs["authorization"] == "[REDACTED_CREDENTIAL]"
            if "customer.email" in attrs:
                assert attrs["customer.email"] == "[REDACTED_EMAIL]"
            if "customer.card" in attrs:
                assert attrs["customer.card"] == "[REDACTED_PAN]"

    # 4. Query authenticated runtime graph endpoint
    auth_headers = _get_auth_headers(tenant_id)
    graph_resp = await client.get(
        "/api/v1/telemetry/runtime-graph?environment=production",
        headers=auth_headers,
    )
    assert graph_resp.status_code == 200
    graph = graph_resp.json()

    assert graph["tenant_id"] == tenant_id
    assert graph["environment"] == "production"

    # Verify all 5 microservices are discovered
    services = set(graph["services"])
    expected_services = {
        "api-gateway",
        "order-service",
        "payment-service",
        "inventory-service",
        "notification-service",
    }
    assert expected_services.issubset(services)

    # Verify dependencies and protocols
    deps = graph["dependencies"]
    dep_pairs = {(d["caller"], d["callee"], d["protocol"]) for d in deps}

    # HTTP client-to-server: api-gateway -> order-service
    assert ("api-gateway", "order-service", "HTTP") in dep_pairs
    # HTTP client-to-server: order-service -> payment-service
    assert ("order-service", "payment-service", "HTTP") in dep_pairs
    # gRPC RPC call: order-service -> inventory-service
    assert ("order-service", "inventory-service", "GRPC") in dep_pairs
    # Kafka Messaging: order-service -> notification-service
    assert ("order-service", "notification-service", "MESSAGING") in dep_pairs
    # Database: payment-service -> db:payments_db
    assert ("payment-service", "db:payments_db", "DATABASE") in dep_pairs
    # Database: inventory-service -> db:inventory_db
    assert ("inventory-service", "db:inventory_db", "DATABASE") in dep_pairs

    # Verify metrics and exemplar trace link
    for d in deps:
        assert d["call_count"] >= 1
        assert d["exemplar_trace_id"] is not None


@pytest.mark.asyncio
async def test_tenant_isolation_in_telemetry_graph(client: AsyncClient):
    """Verifies strict tenant isolation between disparate tenants' observed runtime graphs."""
    tenant_a = "tenant-isolation-a"
    tenant_b = "tenant-isolation-b"

    async with async_session_factory() as session:
        for t in [tenant_a, tenant_b]:
            if not await session.get(Tenant, t):
                session.add(Tenant(id=t, name=f"Tenant {t}", slug=t, tier="enterprise"))
        await session.commit()

    # Ingest distinct traces for tenant A
    payload_a = TelemetryTraceGenerator.generate_5service_trace(tenant_id=tenant_a)
    await client.post("/v1/traces", json=payload_a, headers={"X-Tenant-ID": tenant_a})

    # Query tenant B graph without any ingested data
    headers_b = _get_auth_headers(tenant_b)
    resp_b = await client.get("/api/v1/telemetry/runtime-graph", headers=headers_b)
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert len(data_b["services"]) == 0
    assert len(data_b["dependencies"]) == 0

    # Query tenant A graph and verify data is present
    headers_a = _get_auth_headers(tenant_a)
    resp_a = await client.get("/api/v1/telemetry/runtime-graph", headers=headers_a)
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert len(data_a["services"]) >= 5


@pytest.mark.asyncio
async def test_authenticated_tenant_trace_submission(client: AsyncClient):
    """Verifies authenticated ingestion endpoint /api/v1/telemetry/traces."""
    tenant_id = "tenant-auth-ingest"

    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Auth Ingest Tenant", slug=tenant_id, tier="enterprise"))
            await session.commit()

    payload = TelemetryTraceGenerator.generate_5service_trace(tenant_id=tenant_id)
    headers = _get_auth_headers(tenant_id)

    res = await client.post("/api/v1/telemetry/traces", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ACCEPTED"
    assert res.json()["spans_ingested"] >= 10


@pytest.mark.asyncio
async def test_runtime_dependency_correlations_endpoint(client: AsyncClient):
    """Verifies the /api/v1/telemetry/correlations endpoint."""
    tenant_id = "tenant-corr-test"

    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Corr Tenant", slug=tenant_id, tier="enterprise"))
            await session.commit()

    payload = TelemetryTraceGenerator.generate_5service_trace(tenant_id=tenant_id)
    await client.post("/v1/traces", json=payload, headers={"X-Tenant-ID": tenant_id})

    headers = _get_auth_headers(tenant_id)
    resp = await client.get("/api/v1/telemetry/correlations", headers=headers)
    assert resp.status_code == 200
    corrs = resp.json()
    assert isinstance(corrs, list)
    assert len(corrs) >= 1
    assert "caller_service" in corrs[0]
    assert "correlation_status" in corrs[0]


@pytest.mark.asyncio
async def test_worker_span_aggregation_and_outbox_event():
    """Verifies background aggregation task processing spans into dependencies and outbox events."""
    tenant_id = "tenant-worker-agg"

    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Worker Agg Tenant", slug=tenant_id, tier="enterprise"))
            await session.flush()

        # Create two buffered spans
        s1 = RuntimeTraceSpan(
            tenant_id=tenant_id,
            trace_id="trace-worker-99",
            span_id="span-worker-1",
            service_name="frontend-app",
            name="GET /profile",
            kind="CLIENT",
            duration_ms=40.0,
            attributes={"peer.service": "user-service", "http.route": "/profile"},
        )
        session.add(s1)
        await session.commit()

    # Execute aggregation
    res = await aggregate_otel_traces_async(retention_days=7)
    assert res["status"] == "COMPLETED"
    assert res["tenants_count"] >= 1
    assert res["dependencies_updated"] >= 1

    # Check OutboxEvent created for Neo4j projection
    async with async_session_factory() as session:
        outbox_stmt = select(OutboxEvent).where(
            OutboxEvent.tenant_id == tenant_id,
            OutboxEvent.event_type == "runtime.dependencies.projected",
        )
        outbox_ev = (await session.execute(outbox_stmt)).scalar_one_or_none()
        assert outbox_ev is not None
        assert outbox_ev.payload["tenant_id"] == tenant_id

        # Verify RuntimeDependency updated
        dep_stmt = select(RuntimeDependency).where(
            RuntimeDependency.tenant_id == tenant_id,
            RuntimeDependency.caller_service_name == "frontend-app",
            RuntimeDependency.callee_service_name == "user-service",
        )
        dep = (await session.execute(dep_stmt)).scalar_one_or_none()
        assert dep is not None
        assert dep.http_route == "/profile"
