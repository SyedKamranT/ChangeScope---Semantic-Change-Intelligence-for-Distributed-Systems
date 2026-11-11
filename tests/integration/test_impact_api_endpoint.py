"""Integration tests for ChangeScope Impact Reasoning API Endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.shared.database import async_session_factory
from packages.shared.models import RuntimeDependency, Tenant
from packages.shared.security.jwt_handler import create_access_token


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _auth_header(tenant_id: str, role: str = "engineer") -> dict[str, str]:
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
async def test_impact_evaluate_endpoint_unauthenticated(client: AsyncClient):
    """Verifies that accessing /api/v1/impact/evaluate without token yields 401."""
    res = await client.post("/api/v1/impact/evaluate", json={"change_set_id": "cs-test", "changes": []})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_impact_evaluate_endpoint_authenticated(client: AsyncClient):
    """Verifies that an authenticated engineer can submit a ChangeSet and receive deterministic impact results."""
    tenant_id = "tenant-impact-api"

    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Impact API Tenant", slug=tenant_id, tier="enterprise"))

        # Seed a runtime dependency for this tenant: api-gateway -> order-service
        dep = RuntimeDependency(
            tenant_id=tenant_id,
            caller_service_name="api-gateway",
            callee_service_name="order-service",
            http_route="/api/v1/orders",
            http_method="POST",
            protocol="HTTP",
            call_count_7d=5000,
            exemplar_trace_id="trace-ex-999",
        )
        session.add(dep)
        await session.commit()

    headers = _auth_header(tenant_id)
    payload = {
        "change_set_id": "cs-pr-402",
        "tenant_id": tenant_id,
        "changes": [
            {
                "entity_id": "order-service",
                "entity_name": "Order Service",
                "entity_type": "Service",
                "change_type": "FIELD_REMOVED",
                "severity": "BLOCKING",
                "is_breaking": True,
            }
        ],
    }

    res = await client.post("/api/v1/impact/evaluate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["change_set_id"] == "cs-pr-402"
    assert data["tenant_id"] == tenant_id
    assert len(data["affected_entities"]) >= 1

    # api-gateway was calling order-service
    consumer = data["affected_entities"][0]
    assert consumer["entity_id"] == "api-gateway"
    assert consumer["is_runtime_confirmed"] is True
    assert consumer["call_frequency_7d"] == 5000

    # Risk breakdown checks
    assert "risk_score" in data
    assert data["risk_score"] >= 50
    assert data["risk_breakdown"]["base_severity_score"] == 50.0
    assert "formula_explanation" in data["risk_breakdown"]
    assert "recommended_action" in data

    # Graph visualization nodes and edges
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1
