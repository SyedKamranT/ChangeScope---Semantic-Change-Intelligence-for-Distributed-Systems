"""End-to-End Smoke Test validating complete workspace, repository, and scan flow."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.shared.security.jwt_handler import create_access_token


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_complete_e2e_scan_lifecycle(client: AsyncClient) -> None:
    """Tests full end-to-end flow: Admin creates workspace, registers repo, and triggers scan."""
    tenant_id = "tenant-e2e-suite"
    token = create_access_token(
        {
            "sub": "e2e_lead_engineer",
            "tenant_id": tenant_id,
            "roles": ["admin"],
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Workspace
    ws_resp = await client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Logistics Suite", "slug": "logistics-suite"},
    )
    assert ws_resp.status_code == 201
    workspace_id = ws_resp.json()["id"]

    # 2. Register Repository
    repo_resp = await client.post(
        "/api/v1/repositories",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "name": "fleet-management-service",
            "clone_url": "https://github.com/org/fleet-management.git",
            "default_branch": "main",
        },
    )
    assert repo_resp.status_code == 201
    repo_id = repo_resp.json()["id"]

    # 3. Trigger Scan
    scan_resp = await client.post(
        "/api/v1/scans",
        headers=headers,
        json={
            "repository_id": repo_id,
            "target_branch": "main",
            "source_branch": "feat/add-gps-telemetry",
            "base_commit": "a1b2c3d",
            "head_commit": "e4f5a6b",
            "changed_files": ["contracts/openapi.yaml"],
        },
    )
    assert scan_resp.status_code == 202
    scan_id = scan_resp.json()["scan_id"]
    assert scan_resp.json()["status"] == "QUEUED"

    # 4. Query Scan Status
    status_resp = await client.get(
        f"/api/v1/scans/{scan_id}",
        headers=headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["id"] == scan_id
    assert status_resp.json()["repository_id"] == repo_id

    # 5. Query Violations (empty at queue time)
    violations_resp = await client.get(
        f"/api/v1/scans/{scan_id}/violations",
        headers=headers,
    )
    assert violations_resp.status_code == 200
    assert isinstance(violations_resp.json(), list)
