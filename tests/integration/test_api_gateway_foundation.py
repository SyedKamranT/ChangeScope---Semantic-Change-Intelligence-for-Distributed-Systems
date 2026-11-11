"""Integration tests for the ChangeScope API Gateway, Authentication, and Correlation Middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.shared.security.jwt_handler import create_access_token


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_liveness_probe_endpoint(client: AsyncClient) -> None:
    """Verifies that /health/live returns HTTP 200 with service metadata."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ChangeScope" in data["app"]
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_probe_endpoint(client: AsyncClient) -> None:
    """Verifies that /health/ready returns status and datastore checks."""
    response = await client.get("/health/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert "checks" in data
    assert "database" in data["checks"]


@pytest.mark.asyncio
async def test_correlation_id_middleware(client: AsyncClient) -> None:
    """Verifies that requests receive and propagate X-Request-ID headers."""
    # 1. Server generates new correlation ID when none provided
    resp1 = await client.get("/health/live")
    assert "X-Request-ID" in resp1.headers
    generated_id = resp1.headers["X-Request-ID"]
    assert len(generated_id) > 10

    # 2. Server preserves client-provided correlation ID
    custom_id = "test-correlation-id-998877"
    resp2 = await client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert resp2.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_unauthenticated_request_triggers_rfc7807_error(client: AsyncClient) -> None:
    """Verifies that accessing protected endpoints without tokens yields 401 Problem Details."""
    response = await client.get("/api/v1/workspaces")
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 401
    assert "Authentication Required" in problem["title"]
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_token_acquisition_and_profile_endpoint(client: AsyncClient) -> None:
    """Verifies that /api/v1/auth/token generates a functional token valid for /api/v1/me."""
    token_resp = await client.post(
        "/api/v1/auth/token",
        json={"username": "alice_dev", "role": "engineer"},
    )
    assert token_resp.status_code == 200
    token_data = token_resp.json()
    access_token = token_data["access_token"]
    assert len(access_token) > 20

    # Access /api/v1/me with bearer token
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = await client.get("/api/v1/me", headers=auth_headers)
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert profile["user_id"] == "alice_dev"
    assert "engineer" in profile["roles"]


@pytest.mark.asyncio
async def test_workspace_rbac_and_tenant_isolation(client: AsyncClient) -> None:
    """Verifies that workspace creation requires ADMIN role, and isolates data across tenants."""
    # 1. Engineer tries to create workspace -> 403 Forbidden
    engineer_token = create_access_token(
        {
            "sub": "bob_eng",
            "tenant_id": "tenant-corp-a",
            "roles": ["engineer"],
        }
    )
    denied_resp = await client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {engineer_token}"},
        json={"name": "Core Banking", "slug": "core-banking"},
    )
    assert denied_resp.status_code == 403
    assert denied_resp.headers["content-type"] == "application/problem+json"

    # 2. Admin in Tenant A creates workspace -> 201 Created
    admin_token_a = create_access_token(
        {
            "sub": "admin_a",
            "tenant_id": "tenant-corp-a",
            "roles": ["admin"],
        }
    )
    create_resp = await client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {admin_token_a}"},
        json={"name": "Core Banking", "slug": "core-banking"},
    )
    assert create_resp.status_code == 201
    created_ws = create_resp.json()
    assert created_ws["name"] == "Core Banking"

    # 3. List workspaces for Tenant A -> contains "Core Banking"
    list_a_resp = await client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {admin_token_a}"},
    )
    assert list_a_resp.status_code == 200
    ws_slugs_a = [w["slug"] for w in list_a_resp.json()]
    assert "core-banking" in ws_slugs_a

    # 4. List workspaces for Tenant B -> must NOT contain Tenant A's workspace (Tenant Isolation)
    admin_token_b = create_access_token(
        {
            "sub": "admin_b",
            "tenant_id": "tenant-corp-b",
            "roles": ["admin"],
        }
    )
    list_b_resp = await client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {admin_token_b}"},
    )
    assert list_b_resp.status_code == 200
    ws_slugs_b = [w["slug"] for w in list_b_resp.json()]
    assert "core-banking" not in ws_slugs_b


@pytest.mark.asyncio
async def test_list_scans_endpoint(client: AsyncClient) -> None:
    token = create_access_token({"sub": "user_analyst", "tenant_id": "tenant-corp-a", "roles": ["analyst"]})
    res = await client.get("/api/v1/scans", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_list_audit_logs_endpoint(client: AsyncClient) -> None:
    # Viewer role denied
    viewer_token = create_access_token({"sub": "user_viewer", "tenant_id": "tenant-corp-a", "roles": ["viewer"]})
    denied = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {viewer_token}"})
    assert denied.status_code == 403

    # Administrator allowed
    admin_token = create_access_token({"sub": "user_admin", "tenant_id": "tenant-corp-a", "roles": ["admin"]})
    res = await client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_ontology_concepts_endpoint(client: AsyncClient) -> None:
    token = create_access_token({"sub": "user_analyst", "tenant_id": "tenant-corp-a", "roles": ["analyst"]})
    res = await client.get("/api/v1/ontology/concepts", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "entities" in data
    assert "relationships" in data
    entity_names = [e["name"] for e in data["entities"]]
    assert "Service" in entity_names
    assert "APIEndpoint" in entity_names
    assert "BusinessConcept" in entity_names


@pytest.mark.asyncio
async def test_workflows_endpoint(client: AsyncClient) -> None:
    import uuid
    from datetime import UTC, datetime

    from packages.shared.database import async_session_factory
    from packages.shared.models import Tenant
    from packages.shared.ontology_models import OntologyEntity

    wf_id = f"wf-checkout-{uuid.uuid4().hex[:6]}"
    async with async_session_factory() as session:
        if not await session.get(Tenant, "tenant-corp-a"):
            session.add(Tenant(id="tenant-corp-a", name="Corp A", slug="corp-a"))
        session.add(
            OntologyEntity(
                id=wf_id,
                tenant_id="tenant-corp-a",
                entity_type="Workflow",
                canonical_urn=f"urn:changescope:workflow:{wf_id}",
                name="Customer Checkout & Payment Flow",
                description="Critical checkout orchestration",
                properties_payload={
                    "criticality": "TIER_1_CRITICAL",
                    "owner": "checkout-platform-team",
                    "steps": [{"step_index": 1, "service": "api-gateway", "operation": "POST /v1/checkout"}],
                },
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()

    token_a = create_access_token({"sub": "user_analyst", "tenant_id": "tenant-corp-a", "roles": ["analyst"]})
    res = await client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    workflows = res.json()
    assert any(w["id"] == wf_id for w in workflows)

    # Tenant isolation check: tenant-corp-b must not see tenant-corp-a's workflow
    token_b = create_access_token({"sub": "user_b", "tenant_id": "tenant-corp-b", "roles": ["analyst"]})
    res_b = await client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    assert not any(w["id"] == wf_id for w in res_b.json())
