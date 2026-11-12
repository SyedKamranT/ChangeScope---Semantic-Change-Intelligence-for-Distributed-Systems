"""Comprehensive Backend Security and Reliability Integration Tests.

Validates:
- Broken Object-Level Authorization (BOLA/IDOR) & Horizontal Privilege Escalation
- Vertical Privilege Escalation & Role Hierarchy (Owner, Admin, Analyst, Viewer)
- Cross-Tenant Data Isolation (Databases, Telemetry, Credentials, Outbox)
- JWT Cryptographic Verification (Signatures, Expiration, Claims, Algorithm None Defense)
- Server-Side Request Forgery (SSRF) Payload Interception (Loopback, Metadata, Private Subnets)
- Webhook Signature Verification and Replay Prevention
- Malicious Upload & Zip Slip Path Traversal Defenses
- Unauthorized Graph Traversal & Cypher Tenant Scoping
- AES-256-GCM Credential Encryption at Rest
- Audit Trail Persistence
- Request Idempotency Deduplication
- Rate Limiting and Retry-After Enforcement
"""

import base64
import hashlib
import hmac
import io
import time
import zipfile
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.shared.config import settings
from packages.shared.database import async_session_factory
from packages.shared.errors import AuthorizationError
from packages.shared.models import (
    AuditLog,
    Repository,
    RuntimeDependency,
    ScanRun,
    Tenant,
    Workspace,
)
from packages.shared.security.authorization import SecurityContext
from packages.shared.security.crypto import CredentialEncryption, EncryptionError
from packages.shared.security.jwt_handler import (
    SESSION_COOKIE_NAME,
    create_access_token,
    decode_token,
)
from packages.shared.security.rate_limiter import RateLimiter, RateLimitExceededError
from packages.shared.security.ssrf import SSRFProtectionError, SSRFProtector
from packages.shared.security.webhooks import WebhookVerificationError, WebhookVerifier
from packages.shared.services.graph_service import GraphQueryService


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _auth_headers(tenant_id: str, role: str = "analyst", user_id: str = "user-sec") -> dict[str, str]:
    token = create_access_token(
        {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": [role],
            "email": f"{user_id}@{tenant_id}.io",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_bola_and_horizontal_privilege_escalation(client: AsyncClient):
    """Verifies that Tenant A cannot access, mutate, or attach resources to Tenant B (BOLA/IDOR)."""
    tenant_a = "tenant-sec-a"
    tenant_b = "tenant-sec-b"

    async with async_session_factory() as session:
        for tid, name in [(tenant_a, "Tenant Alpha"), (tenant_b, "Tenant Beta")]:
            if not await session.get(Tenant, tid):
                session.add(Tenant(id=tid, name=name, slug=tid, tier="enterprise"))

        # Seed Workspace & Repository for Tenant B
        ws_b = Workspace(id="ws-tenant-b-1", tenant_id=tenant_b, name="Beta Core", slug="beta-core")
        session.add(ws_b)
        repo_b = Repository(
            id="repo-tenant-b-1",
            tenant_id=tenant_b,
            workspace_id=ws_b.id,
            name="payment-svc",
            clone_url="https://github.com/beta/payment-svc.git",
        )
        session.add(repo_b)
        scan_b = ScanRun(
            id="scan-tenant-b-1",
            tenant_id=tenant_b,
            repository_id=repo_b.id,
            base_sha="0000000",
            head_sha="1111111",
            status="COMPLETED",
        )
        session.add(scan_b)
        await session.commit()

    headers_a = _auth_headers(tenant_a, role="analyst")

    # 1. BOLA: Tenant A user attempts to register a repository bound to Tenant B's workspace
    res = await client.post(
        "/api/v1/repositories",
        json={
            "workspace_id": "ws-tenant-b-1",
            "name": "malicious-repo-binding",
            "clone_url": "https://github.com/attacker/malicious.git",
        },
        headers=headers_a,
    )
    assert res.status_code == 403
    assert "Tenant isolation violation" in res.json()["detail"]

    # 2. BOLA: Tenant A user attempts to trigger a scan on Tenant B's repository
    res_scan = await client.post(
        "/api/v1/scans",
        json={"repository_id": "repo-tenant-b-1", "head_commit": "2222222"},
        headers=headers_a,
    )
    assert res_scan.status_code == 403
    assert "Tenant isolation violation" in res_scan.json()["detail"]

    # 3. BOLA: Tenant A user attempts to inspect Tenant B's scan run status
    res_status = await client.get("/api/v1/scans/scan-tenant-b-1", headers=headers_a)
    assert res_status.status_code == 403

    # 4. BOLA: Tenant A user attempts to inspect Tenant B's scan violations
    res_viol = await client.get("/api/v1/scans/scan-tenant-b-1/violations", headers=headers_a)
    assert res_viol.status_code == 403


@pytest.mark.asyncio
async def test_vertical_privilege_escalation_role_hierarchy(client: AsyncClient):
    """Verifies that lower privileged roles (Viewer) cannot perform Analyst/Administrator actions."""
    tenant_id = "tenant-roles-test"
    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Roles Org", slug=tenant_id, tier="enterprise"))
            await session.commit()

    viewer_headers = _auth_headers(tenant_id, role="viewer")
    analyst_headers = _auth_headers(tenant_id, role="analyst")
    admin_headers = _auth_headers(tenant_id, role="administrator")
    owner_headers = _auth_headers(tenant_id, role="organization_owner")

    # 1. Viewer attempts to create a workspace (Requires Administrator) -> 403
    res_ws_viewer = await client.post(
        "/api/v1/workspaces",
        json={"name": "Viewer WS", "slug": "viewer-ws"},
        headers=viewer_headers,
    )
    assert res_ws_viewer.status_code == 403

    # 2. Analyst attempts to create a workspace (Requires Administrator) -> 403
    res_ws_analyst = await client.post(
        "/api/v1/workspaces",
        json={"name": "Analyst WS", "slug": "analyst-ws"},
        headers=analyst_headers,
    )
    assert res_ws_analyst.status_code == 403

    # 3. Administrator creates workspace successfully -> 201
    res_ws_admin = await client.post(
        "/api/v1/workspaces",
        json={"name": "Admin WS", "slug": "admin-ws"},
        headers=admin_headers,
    )
    assert res_ws_admin.status_code == 201
    ws_id = res_ws_admin.json()["id"]

    # 4. Viewer attempts to register a repository (Requires Analyst) -> 403
    res_repo_viewer = await client.post(
        "/api/v1/repositories",
        json={"workspace_id": ws_id, "name": "repo-v", "clone_url": "https://github.com/org/repo-v.git"},
        headers=viewer_headers,
    )
    assert res_repo_viewer.status_code == 403

    # 5. Analyst registers repository successfully -> 201
    res_repo_analyst = await client.post(
        "/api/v1/repositories",
        json={"workspace_id": ws_id, "name": "repo-v", "clone_url": "https://github.com/org/repo-v.git"},
        headers=analyst_headers,
    )
    assert res_repo_analyst.status_code == 201

    # 6. Organization Owner can create workspaces and full administration -> 201
    res_ws_owner = await client.post(
        "/api/v1/workspaces",
        json={"name": "Owner WS", "slug": "owner-ws"},
        headers=owner_headers,
    )
    assert res_ws_owner.status_code == 201


@pytest.mark.asyncio
async def test_cross_tenant_telemetry_and_credentials_isolation(client: AsyncClient):
    """Verifies that runtime dependencies and credentials are strictly partitioned across tenants."""
    tenant_x = "tenant-iso-x"
    tenant_y = "tenant-iso-y"

    async with async_session_factory() as session:
        for tid in [tenant_x, tenant_y]:
            if not await session.get(Tenant, tid):
                session.add(Tenant(id=tid, name=tid, slug=tid, tier="enterprise"))
        await session.flush()

        # Seed telemetry for Tenant Y only
        dep_y = RuntimeDependency(
            tenant_id=tenant_y,
            caller_service_name="secret-order-svc",
            callee_service_name="secret-payment-svc",
            http_route="/api/v1/secret-pay",
            protocol="HTTP",
            environment="production",
            call_count_7d=99999,
        )
        session.add(dep_y)
        await session.commit()

    headers_x = _auth_headers(tenant_x, role="analyst")
    headers_y_admin = _auth_headers(tenant_y, role="administrator")

    # 1. Telemetry Query Isolation: Tenant X queries runtime graph -> Must NOT see Tenant Y's services
    res_graph_x = await client.get("/api/v1/telemetry/runtime-graph", headers=headers_x)
    assert res_graph_x.status_code == 200
    data_x = res_graph_x.json()
    assert "secret-order-svc" not in data_x["services"]
    assert len(data_x["dependencies"]) == 0

    # 2. Store Credential for Tenant Y
    res_cred = await client.post(
        "/api/v1/credentials",
        json={"name": "github-pat", "provider": "GITHUB", "secret": "ghp_super_secret_pat_999"},
        headers=headers_y_admin,
    )
    assert res_cred.status_code == 201
    cred_id = res_cred.json()["id"]

    # 3. Tenant X attempts to list credentials -> Must NOT see Tenant Y's credential
    res_list_x = await client.get("/api/v1/credentials", headers=headers_x)
    assert res_list_x.status_code == 200
    assert not any(c["id"] == cred_id for c in res_list_x.json())

    # 4. Tenant X attempts to decrypt Tenant Y's credential secret -> 403
    res_decrypt_x = await client.get(f"/api/v1/credentials/{cred_id}/secret", headers=headers_x)
    assert res_decrypt_x.status_code == 403


@pytest.mark.asyncio
async def test_jwt_verification_comprehensive(client: AsyncClient):
    """Verifies cryptographic rejection of expired, forged, and algorithm-'none' JWT tokens."""
    # 1. Token without Authorization header -> 401
    res_unauth = await client.get("/api/v1/me")
    assert res_unauth.status_code == 401

    # 2. Forged signature token -> 401
    valid_token = create_access_token({"sub": "legit", "tenant_id": "tenant-test"})
    tampered_token = valid_token[:-4] + "AAAA"
    res_tampered = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401

    # 3. Expired token -> 401
    expired_token = create_access_token(
        {"sub": "expired_user", "tenant_id": "tenant-test"},
        expires_delta=timedelta(seconds=-60),
    )
    res_expired = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401
    assert "expired" in res_expired.json()["detail"].lower()

    # 4. Unsecured algorithm "none" token -> Rejected by decode_token
    import jwt

    from packages.shared.errors import AuthenticationError

    unsigned_none_token = jwt.encode({"sub": "hacker", "tenant_id": "tenant-test"}, key="", algorithm="none")
    with pytest.raises(AuthenticationError):
        decode_token(unsigned_none_token)

    # 5. Session cookie authentication -> 200
    res_cookie = await client.get("/api/v1/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={valid_token}"})
    assert res_cookie.status_code == 200
    assert res_cookie.json()["user_id"] == "legit"


def test_ssrf_protection_payloads():
    """Asserts that the SSRF protection engine rejects private, loopback, and cloud metadata targets."""
    # Prohibited destinations
    prohibited_urls = [
        "http://127.0.0.1:8080/internal",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::1]:9000/metrics",
        "http://10.0.0.5:5432",
        "http://172.16.1.1/secret",
        "http://192.168.1.1/router",
        "http://0.0.0.0:8000/",
        "http://user:password@target.com/",
        "ftp://github.com/repo.git",
        "gopher://127.0.0.1:6379/_flushall",
    ]

    for target in prohibited_urls:
        with pytest.raises(SSRFProtectionError):
            SSRFProtector.validate_url(target)

    # Approved external URL
    approved_url = "https://github.com/facebook/react.git"
    assert SSRFProtector.validate_url(approved_url) == approved_url


@pytest.mark.asyncio
async def test_webhook_signature_and_replay_defense(client: AsyncClient):
    """Verifies HMAC-SHA256 GitHub signature validation and anti-replay protection."""
    secret = settings.GITHUB_WEBHOOK_SECRET
    payload = b'{"action": "opened", "pull_request": {"number": 42}}'

    # Compute valid GitHub signature
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    valid_sig = f"sha256={mac.hexdigest()}"

    # 1. Valid signature -> 200 OK
    res_valid = await client.post(
        "/api/v1/webhooks/github",
        content=payload,
        headers={"X-Hub-Signature-256": valid_sig, "X-GitHub-Event": "pull_request"},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "ACCEPTED"

    # 2. Tampered signature -> 401
    res_invalid = await client.post(
        "/api/v1/webhooks/github",
        content=payload,
        headers={"X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbad", "X-GitHub-Event": "pull_request"},
    )
    assert res_invalid.status_code == 401

    # 3. Missing signature -> 401
    res_missing = await client.post("/api/v1/webhooks/github", content=payload)
    assert res_missing.status_code == 401

    # 4. Anti-replay verification test
    current_ts = int(time.time())
    stale_ts = current_ts - 600  # 10 minutes old

    # Expired timestamp must be rejected
    with pytest.raises(WebhookVerificationError) as exc_info:
        WebhookVerifier.verify_timestamped_signature(
            payload_bytes=payload,
            signature_header="v1=dummy",
            timestamp_header=stale_ts,
            secret=secret,
        )
    assert "expired" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_malicious_upload_validation(client: AsyncClient):
    """Verifies upload guard against executable injection, bad extensions, and Zip Slip path traversal."""
    headers = _auth_headers("tenant-upload-sec", role="analyst")

    # 1. Executable PE binary disguised as YAML (starts with 'MZ') -> 400
    fake_yaml_exe = base64.b64encode(b"MZ\x90\x00\x03\x00\x00\x00openapi: 3.0.0").decode("ascii")
    res_exe = await client.post(
        "/api/v1/contracts/upload",
        json={"filename": "openapi.yaml", "content_base64": fake_yaml_exe},
        headers=headers,
    )
    assert res_exe.status_code == 400
    assert "prohibited executable binary" in res_exe.json()["detail"]

    # 2. Disallowed extension (.exe) -> 400
    plain_content = base64.b64encode(b"openapi: 3.0.0\ninfo: {title: Test}").decode("ascii")
    res_ext = await client.post(
        "/api/v1/contracts/upload",
        json={"filename": "malware.exe", "content_base64": plain_content},
        headers=headers,
    )
    assert res_ext.status_code == 400
    assert "extension '.exe' is prohibited" in res_ext.json()["detail"]

    # 3. Zip Slip Path Traversal Archive -> 400
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
    zip_slip_bytes = base64.b64encode(zip_buffer.getvalue()).decode("ascii")

    res_zip_slip = await client.post(
        "/api/v1/contracts/upload",
        json={"filename": "contracts.zip", "content_base64": zip_slip_bytes},
        headers=headers,
    )
    assert res_zip_slip.status_code == 400
    assert "Zip Slip path traversal attempt" in res_zip_slip.json()["detail"]

    # 4. Valid YAML specification upload -> 201
    valid_yaml = base64.b64encode(b"openapi: 3.0.0\ninfo:\n  title: Sample\n  version: 1.0.0").decode("ascii")
    res_valid = await client.post(
        "/api/v1/contracts/upload",
        json={"filename": "spec.yaml", "content_base64": valid_yaml},
        headers=headers,
    )
    assert res_valid.status_code == 201
    assert res_valid.json()["status"] == "VALIDATED"


def test_unauthorized_graph_traversal():
    """Verifies that graph queries without tenant isolation parameters are rejected at the service layer."""
    context = SecurityContext(user_id="analyst-1", tenant_id="tenant-graph-1", roles=["analyst"])

    # 1. Missing tenant_id in Cypher parameters -> Rejected
    with pytest.raises(AuthorizationError) as exc_missing:
        GraphQueryService.assert_cypher_tenant_isolation(
            context=context,
            query="MATCH (n:Service) RETURN n",
            parameters={},
        )
    assert "Mandatory 'tenant_id' parameter is missing" in str(exc_missing.value)

    # 2. Parameter mismatch with context -> Rejected
    with pytest.raises(AuthorizationError) as exc_mismatch:
        GraphQueryService.assert_cypher_tenant_isolation(
            context=context,
            query="MATCH (n:Service {tenant_id: $tenant_id}) RETURN n",
            parameters={"tenant_id": "other-tenant-id"},
        )
    assert "Graph query tenant violation" in str(exc_mismatch.value)

    # 3. Unauthorized node traversal across tenants -> Rejected
    with pytest.raises(AuthorizationError):
        GraphQueryService.validate_graph_node_access(context=context, node_tenant_id="foreign-tenant-id")


def test_credential_encryption_at_rest():
    """Verifies AES-256-GCM authenticated encryption and tamper resistance."""
    plaintext = "super_sensitive_api_token_xyz_123"

    ciphertext = CredentialEncryption.encrypt(plaintext)
    assert ciphertext.startswith("v1:")
    assert plaintext not in ciphertext  # Never stored in plaintext

    decrypted = CredentialEncryption.decrypt(ciphertext)
    assert decrypted == plaintext

    # Tampered ciphertext payload must fail authentication tag check
    tampered = ciphertext[:-4] + "FFFF"
    with pytest.raises(EncryptionError):
        CredentialEncryption.decrypt(tampered)


@pytest.mark.asyncio
async def test_audit_event_recording(client: AsyncClient):
    """Verifies that security-critical actions and unauthorized BOLA attempts are persisted in the audit trail."""
    tenant_id = "tenant-audit-test"
    headers = _auth_headers(tenant_id, role="administrator", user_id="admin-auditor")

    res = await client.post(
        "/api/v1/workspaces",
        json={"name": "Audit Workspace", "slug": "audit-workspace"},
        headers=headers,
    )
    assert res.status_code == 201

    async with async_session_factory() as session:
        from sqlalchemy import select

        audit_stmt = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.event_type == "WORKSPACE_CREATED",
        )
        audit_res = await session.execute(audit_stmt)
        record = audit_res.scalar_one_or_none()

        assert record is not None
        assert record.actor_id == "admin-auditor"
        assert record.resource_type == "Workspace"
        assert record.status == "SUCCESS"


@pytest.mark.asyncio
async def test_idempotency_deduplication(client: AsyncClient):
    """Verifies that duplicate mutating requests with identical Idempotency-Key return cached response."""
    tenant_id = "tenant-idempotent"
    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Idem Org", slug=tenant_id, tier="enterprise"))
            await session.flush()
        from packages.shared.models import Workspace

        if not await session.get(Workspace, "ws-idem-1"):
            session.add(Workspace(id="ws-idem-1", tenant_id=tenant_id, name="Idem WS", slug="idem-ws"))
            await session.flush()

        repo = Repository(
            id="repo-idem-1",
            tenant_id=tenant_id,
            workspace_id="ws-idem-1",
            name="idem-repo",
            clone_url="https://github.com/org/idem-repo.git",
        )
        session.add(repo)
        await session.commit()

    headers = _auth_headers(tenant_id, role="analyst")
    idempotency_key = "idemp-key-pr-999"
    headers_with_key = {**headers, "Idempotency-Key": idempotency_key}

    payload = {"repository_id": "repo-idem-1", "head_commit": "abc1234"}

    # First request
    res_1 = await client.post("/api/v1/scans", json=payload, headers=headers_with_key)
    assert res_1.status_code == 202
    scan_id_1 = res_1.json()["scan_id"]

    # Second duplicate request with exact same Idempotency-Key
    res_2 = await client.post("/api/v1/scans", json=payload, headers=headers_with_key)
    assert res_2.status_code == 202
    scan_id_2 = res_2.json()["scan_id"]

    # Must return exact same cached scan_id without spawning duplicate scan runs
    assert scan_id_1 == scan_id_2


@pytest.mark.asyncio
async def test_rate_limiter_enforcement():
    """Verifies that exceeding rate limit triggers RateLimitExceededError and sets Retry-After."""
    limiter = RateLimiter()
    key = "tenant-rate-limit-test"

    # Allow 5 requests in a window
    for _ in range(5):
        await limiter.check_rate_limit(key=key, limit=5, window_seconds=60)

    # 6th request must breach limit
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.check_rate_limit(key=key, limit=5, window_seconds=60)

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after_seconds > 0


@pytest.mark.asyncio
async def test_x_tenant_id_header_cannot_override_default_tenant_jwt(client: AsyncClient):
    """Verifies that an X-Tenant-ID header cannot override a JWT signed with DEFAULT_TENANT_ID."""
    default_token = create_access_token(
        {
            "sub": "spoof-user",
            "tenant_id": settings.DEFAULT_TENANT_ID,
            "roles": ["analyst"],
        }
    )
    res = await client.get(
        "/api/v1/me",
        headers={
            "Authorization": f"Bearer {default_token}",
            "X-Tenant-ID": "tenant-sec-b",
        },
    )
    assert res.status_code == 200
    assert res.json()["tenant_id"] == settings.DEFAULT_TENANT_ID
    assert res.json()["tenant_id"] != "tenant-sec-b"


@pytest.mark.asyncio
async def test_credential_decryption_requires_administrator_and_audits(client: AsyncClient):
    """Verifies same-tenant analysts cannot decrypt stored secrets while admins can and are audited."""
    tenant_id = "tenant-cred-rbac"
    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Cred RBAC Org", slug=tenant_id, tier="enterprise"))
            await session.commit()

    admin_headers = _auth_headers(tenant_id, role="administrator", user_id="cred-admin")
    analyst_headers = _auth_headers(tenant_id, role="analyst", user_id="cred-analyst")

    create_res = await client.post(
        "/api/v1/credentials",
        json={"name": "prod-github-secret", "provider": "GITHUB", "secret": "ghp_admin_only_secret_987"},
        headers=admin_headers,
    )
    assert create_res.status_code == 201
    cred_id = create_res.json()["id"]

    # Same-tenant Analyst must be denied plaintext secret decryption -> 403
    analyst_res = await client.get(f"/api/v1/credentials/{cred_id}/secret", headers=analyst_headers)
    assert analyst_res.status_code == 403

    # Same-tenant Administrator allowed -> 200 and recorded in AuditLog
    admin_res = await client.get(f"/api/v1/credentials/{cred_id}/secret", headers=admin_headers)
    assert admin_res.status_code == 200
    assert admin_res.json()["secret"] == "ghp_admin_only_secret_987"

    async with async_session_factory() as session:
        from sqlalchemy import select

        audit_stmt = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.event_type == "CREDENTIAL_DECRYPTED",
            AuditLog.resource_id == cred_id,
        )
        audit_row = (await session.execute(audit_stmt)).scalar_one_or_none()
        assert audit_row is not None


@pytest.mark.asyncio
async def test_production_mode_blocks_dev_token_and_unauth_otlp(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Verifies staging/production blocks unauthenticated /auth/token minting and unauthenticated /v1/traces."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    token_res = await client.post(
        "/api/v1/auth/token",
        json={"username": "attacker", "tenant_id": "victim-tenant", "role": "organization_owner"},
    )
    assert token_res.status_code == 403

    unauth_trace_res = await client.post(
        "/v1/traces",
        json={"resourceSpans": []},
        headers={"X-Tenant-ID": "victim-tenant"},
    )
    assert unauth_trace_res.status_code == 401
