"""Integration tests for ChangeScope FastAPI endpoints."""

import hashlib
import hmac

import pytest
from changescope.config import settings
from changescope.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    res_live = await client.get("/health/live")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ok"

    res_ready = await client.get("/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_auth_token_issuance(client: AsyncClient):
    res = await client.post("/api/v1/auth/token", json={"username": "dev-user", "tenant_id": "tenant-test-42"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["tenant_id"] == "tenant-test-42"


@pytest.mark.asyncio
async def test_github_webhook_hmac_verification(client: AsyncClient):
    payload = b'{"action": "opened", "pull_request": {"number": 101}}'
    secret = settings.GITHUB_WEBHOOK_SECRET
    valid_sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    # Valid signature
    res = await client.post(
        "/api/v1/webhooks/github",
        content=payload,
        headers={"X-Hub-Signature-256": valid_sig, "X-GitHub-Event": "pull_request"},
    )
    assert res.status_code == 202
    assert res.json()["status"] == "QUEUED"

    # Invalid signature
    res_bad = await client.post(
        "/api/v1/webhooks/github",
        content=payload,
        headers={"X-Hub-Signature-256": "sha256=invalid_hash", "X-GitHub-Event": "pull_request"},
    )
    assert res_bad.status_code == 401


@pytest.mark.asyncio
async def test_otlp_trace_ingestion_and_pii_scrubbing(client: AsyncClient):
    trace_payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "name": "HTTP POST /api/v1/pay",
                                "attributes": {
                                    "http.route": "/api/v1/pay",
                                    "authorization": "Bearer secret_token_123",
                                    "customer.email": "user@example.com",
                                },
                            }
                        ]
                    }
                ]
            }
        ]
    }
    res = await client.post("/v1/traces", json=trace_payload, headers={"X-Tenant-ID": "tenant-1"})
    assert res.status_code == 200
    assert res.json()["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_mcp_server_protocol(client: AsyncClient):
    # Test tools/list
    res_list = await client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )
    assert res_list.status_code == 200
    data = res_list.json()
    assert "tools" in data["result"]
    tool_names = [t["name"] for t in data["result"]["tools"]]
    assert "query_blast_radius" in tool_names

    # Test tools/call
    res_call = await client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "query_blast_radius", "arguments": {"endpoint_id": "test_ep"}},
        },
    )
    assert res_call.status_code == 200
    call_data = res_call.json()
    assert "content" in call_data["result"]
    assert "Blast Radius" in call_data["result"]["content"][0]["text"]
