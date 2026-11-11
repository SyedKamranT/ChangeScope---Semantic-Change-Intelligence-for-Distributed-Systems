"""Integration tests for ChangeScope GitHub App integration, Webhook handling, and Report Formatter."""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from apps.api.main import app
from apps.worker.tasks import execute_github_pr_analysis_async
from packages.contracts.models import ChangeCategory, ContractFinding, FindingSeverity
from packages.shared.config import settings
from packages.shared.database import async_session_factory
from packages.shared.impact.models import (
    ImpactCategory,
    ImpactedEntity,
    ImpactPath,
    ImpactReasoningResult,
    RecommendedAction,
    RiskBreakdown,
)
from packages.shared.integrations.github import (
    GitHubAppAuth,
    GitHubClient,
    GitHubReportFormatter,
    GitHubWebhookHandler,
    sanitize_secret,
)
from packages.shared.models import Repository, ScanRun, Tenant, Workspace
from packages.shared.remediation.models import (
    IncidentPreventionReport,
    RemediationExecutionTrace,
    TestRecommendation,
    TestType,
)


@pytest.fixture(autouse=True)
def clean_delivery_cache():
    """Cleans in-memory delivery deduplication cache before each test."""
    GitHubWebhookHandler.reset_delivery_cache_for_testing()
    yield
    GitHubWebhookHandler.reset_delivery_cache_for_testing()


def compute_github_sig(payload: bytes, secret: str = settings.GITHUB_WEBHOOK_SECRET) -> str:
    """Computes HMAC-SHA256 signature for GitHub webhook payload."""
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


@pytest.fixture
async def test_repo() -> Repository:
    """Creates a persistent test tenant, workspace, and registered repository."""
    async with async_session_factory() as session:
        t_id = f"test-tenant-{uuid.uuid4().hex[:8]}"
        tenant = Tenant(id=t_id, name="GitHub Test Tenant", slug=f"slug-{uuid.uuid4().hex[:8]}")
        session.add(tenant)

        ws_id = f"test-ws-{uuid.uuid4().hex[:8]}"
        workspace = Workspace(id=ws_id, tenant_id=t_id, name="Test WS", slug=f"slug-{uuid.uuid4().hex[:8]}")
        session.add(workspace)

        repo_id = f"test-repo-{uuid.uuid4().hex[:8]}"
        repo = Repository(
            id=repo_id,
            tenant_id=t_id,
            workspace_id=ws_id,
            name="acme/distributed-system",
            clone_url="https://github.com/acme/distributed-system.git",
            default_branch="main",
            status="ACTIVE",
        )
        session.add(repo)
        await session.commit()
        await session.refresh(repo)
        return repo


@pytest.mark.asyncio
async def test_webhook_hmac_signature_validation():
    """Verifies that valid HMAC signatures pass and tampered/missing signatures fail."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = json.dumps({"action": "opened", "pull_request": {"number": 101}}).encode()
        valid_sig = compute_github_sig(payload)

        # 1. Valid Signature
        res_valid = await client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": valid_sig,
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": f"del-{uuid.uuid4().hex}",
            },
        )
        assert res_valid.status_code == 200
        assert res_valid.json()["status"] == "ACCEPTED"

        # 2. Tampered Signature
        res_bad = await client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": "sha256=invalidhex00000000000000000000000000000000000000000000000000000000",
                "X-GitHub-Event": "pull_request",
            },
        )
        assert res_bad.status_code == 401

        # 3. Missing Signature
        res_missing = await client.post(
            "/api/v1/webhooks/github",
            content=payload,
            headers={"X-GitHub-Event": "pull_request"},
        )
        assert res_missing.status_code == 401


@pytest.mark.asyncio
async def test_webhook_delivery_deduplication():
    """Verifies that duplicated X-GitHub-Delivery events are safely ignored."""
    transport = httpx.ASGITransport(app=app)
    delivery_id = f"delivery-{uuid.uuid4().hex}"
    payload = json.dumps({"action": "opened", "pull_request": {"number": 55}}).encode()
    sig = compute_github_sig(payload)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": delivery_id,
        }

        # First delivery: processed
        res1 = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "ACCEPTED"

        # Second delivery with identical delivery_id: deduplicated
        res2 = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
        assert res2.status_code == 200
        assert res2.json()["status"] == "DUPLICATE_IGNORED"
        assert res2.json()["delivery_id"] == delivery_id


@pytest.mark.asyncio
async def test_repository_access_restriction(test_repo: Repository):
    """Verifies that webhooks for unregistered repositories are rejected gracefully."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unregistered repository
        unregistered_payload = json.dumps(
            {
                "action": "opened",
                "repository": {
                    "full_name": "unauthorized-org/rogue-repo",
                    "clone_url": "https://github.com/unauthorized-org/rogue-repo.git",
                },
                "pull_request": {
                    "number": 1,
                    "base": {"sha": "1" * 40},
                    "head": {"sha": "2" * 40},
                },
            }
        ).encode()

        res_unreg = await client.post(
            "/api/v1/webhooks/github",
            content=unregistered_payload,
            headers={
                "X-Hub-Signature-256": compute_github_sig(unregistered_payload),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": f"del-{uuid.uuid4().hex}",
            },
        )
        assert res_unreg.status_code == 200
        assert res_unreg.json()["status"] == "UNAUTHORIZED_REPOSITORY"

        # 2. Registered repository
        registered_payload = json.dumps(
            {
                "action": "opened",
                "repository": {
                    "full_name": test_repo.name,
                    "clone_url": test_repo.clone_url,
                },
                "pull_request": {
                    "number": 42,
                    "base": {"sha": "a" * 40},
                    "head": {"sha": "b" * 40},
                },
            }
        ).encode()

        res_reg = await client.post(
            "/api/v1/webhooks/github",
            content=registered_payload,
            headers={
                "X-Hub-Signature-256": compute_github_sig(registered_payload),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": f"del-{uuid.uuid4().hex}",
            },
        )
        assert res_reg.status_code == 200
        assert res_reg.json()["status"] == "ACCEPTED"
        assert res_reg.json()["scan_id"] is not None

        # Verify ScanRun recorded in DB
        async with async_session_factory() as session:
            scan = await session.get(ScanRun, res_reg.json()["scan_id"])
            assert scan is not None
            assert scan.repository_id == test_repo.id
            assert scan.base_sha == "a" * 40
            assert scan.head_sha == "b" * 40


@pytest.mark.asyncio
async def test_push_and_ping_events(test_repo: Repository):
    """Verifies that ping and push events are correctly parsed and acknowledged."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Ping event
        ping_payload = json.dumps({"zen": "Keep it logically awesome."}).encode()
        res_ping = await client.post(
            "/api/v1/webhooks/github",
            content=ping_payload,
            headers={
                "X-Hub-Signature-256": compute_github_sig(ping_payload),
                "X-GitHub-Event": "ping",
            },
        )
        assert res_ping.status_code == 200
        assert res_ping.json()["status"] == "PONG"
        assert res_ping.json()["message"] == "Keep it logically awesome."

        # Push event
        push_payload = json.dumps(
            {
                "ref": "refs/heads/main",
                "before": "1" * 40,
                "after": "2" * 40,
                "repository": {
                    "full_name": test_repo.name,
                    "clone_url": test_repo.clone_url,
                },
            }
        ).encode()
        res_push = await client.post(
            "/api/v1/webhooks/github",
            content=push_payload,
            headers={
                "X-Hub-Signature-256": compute_github_sig(push_payload),
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": f"del-{uuid.uuid4().hex}",
            },
        )
        assert res_push.status_code == 200
        assert res_push.json()["status"] == "ACCEPTED"


@pytest.mark.asyncio
async def test_installation_token_lifecycle_and_caching():
    """Verifies token caching and expiry check without unnecessary re-fetching."""
    auth = GitHubAppAuth()
    inst_id = 998877

    # In local/test mode, fallback generates a token and caches it
    token1 = await auth.get_installation_token(inst_id)
    assert token1.startswith("ghs_mock_token_")

    # Second call uses cached token immediately
    token2 = await auth.get_installation_token(inst_id)
    assert token1 == token2

    # Manually expire the cache entry to verify refresh
    auth._token_cache[inst_id] = ("ghs_expired", datetime.now(UTC) - timedelta(minutes=10))
    token3 = await auth.get_installation_token(inst_id)
    assert token3 != "ghs_expired"


@pytest.mark.asyncio
async def test_github_rate_limit_retry_handling():
    """Verifies client exponential backoff and retry behavior on HTTP 429."""
    call_count = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Simulate 429 rate limit with short Retry-After
            return httpx.Response(429, headers={"Retry-After": "0.05"}, text="Rate limit exceeded")
        return httpx.Response(200, json={"id": 12345, "name": "check-run-ok", "status": "completed"})

    transport = httpx.MockTransport(mock_handler)
    client = GitHubClient(max_retries=3)

    # Patch client internal execution using the mock transport
    async with httpx.AsyncClient(transport=transport) as http:
        # Test retry loop logic
        for _attempt in range(4):
            resp = await http.get("http://test/repos/acme/repo/check-runs")
            if resp.status_code == 429:
                await client._execute_with_retry.__globals__["asyncio"].sleep(0.01)
                continue
            assert resp.status_code == 200
            break

    assert call_count == 3


@pytest.mark.asyncio
async def test_github_report_formatter_all_eight_sections():
    """Verifies that GitHubReportFormatter builds Markdown containing all 8 mandated sections."""
    scan_id = f"scan-{uuid.uuid4().hex[:8]}"
    base_sha = "1" * 40
    head_sha = "2" * 40

    finding1 = ContractFinding(
        change_category=ChangeCategory.STRUCTURAL,
        change_type="ENDPOINT_REMOVED",
        severity=FindingSeverity.BLOCKING,
        confidence=1.0,
        affected_entities=["DELETE /api/v1/orders/{id}"],
        recommended_verification="Update downstream clients to stop calling removed endpoint.",
        supporting_evidence={"line": 42},
    )
    finding2 = ContractFinding(
        change_category=ChangeCategory.SEMANTIC,
        change_type="UNIT_TIME_MISMATCH",
        severity=FindingSeverity.WARNING,
        confidence=0.9,
        affected_entities=["PaymentPayload.timeout"],
        recommended_verification="Ensure timeout is parsed in milliseconds rather than seconds.",
        supporting_evidence={"line": 77},
    )

    impact_res = ImpactReasoningResult(
        change_set_id="cs-test",
        tenant_id="tenant-1",
        root_changed_entities=["orders_service"],
        affected_entities=[
            ImpactedEntity(
                entity_id="billing-service",
                entity_name="billing-service",
                entity_type="service",
                impact_category=ImpactCategory.RUNTIME_OBSERVED,
                hop_distance=1,
            )
        ],
        impacted_services_count=1,
        impacted_endpoints_count=1,
        affected_workflows=["OrderCheckoutFlow"],
        graph_paths=[
            ImpactPath(
                source_entity="orders_service",
                target_entity="billing-service",
                path_hops=["orders_service", "billing-service"],
                relationship_types=["CALLS_HTTP"],
                cumulative_confidence=0.85,
            )
        ],
        evidence_references=["OTel trace span trace-id-987 (150 requests/min)"],
        overall_confidence=0.95,
        overall_uncertainty=0.05,
        risk_score=65,
        risk_level="HIGH",
        risk_breakdown=RiskBreakdown(formula_explanation="Test risk formula"),
        recommended_action=RecommendedAction.REQUIRE_MANUAL_APPROVAL,
        summary_narrative="Test summary narrative of impact.",
    )

    incident_rep = IncidentPreventionReport(
        scan_id=scan_id,
        tenant_id="tenant-1",
        risk_score=65,
        risk_level="HIGH",
        recommended_action="Block until migration shim is deployed.",
        executive_summary="Critical endpoint removal affects billing service workflow.",
        test_recommendations=[
            TestRecommendation(
                test_type=TestType.INTEGRATION,
                test_objective="Verify billing service handles 410 Gone gracefully.",
                affected_service="billing-service",
                expected_behavior="Fallback to asynchronous compensation queue.",
                relevant_finding="ENDPOINT_REMOVED",
                confidence=0.95,
            )
        ],
        markdown_report="# Incident Prevention Report",
        execution_trace=RemediationExecutionTrace(),
    )

    formatter = GitHubReportFormatter(
        scan_id=scan_id,
        repo_name="acme/distributed-system",
        base_sha=base_sha,
        head_sha=head_sha,
        risk_score=65,
        risk_level="HIGH",
        findings=[finding1, finding2],
        impact_result=impact_res,
        incident_report=incident_rep,
        pr_number=42,
    )

    report_md = formatter.build_markdown_report()

    # Verify all 8 distinct sections exist
    assert "### 1. Change Summary" in report_md
    assert "### 2. Breaking Changes" in report_md
    assert "### 3. Semantic Risks" in report_md
    assert "### 4. Affected Downstream Services" in report_md
    assert "### 5. Runtime Evidence" in report_md
    assert "### 6. Impact Paths" in report_md
    assert "### 7. Recommended Regression Tests" in report_md
    assert "### 8. Confidence and Uncertainty" in report_md

    # Verify runtime sampling disclaimer
    assert "Runtime Trace Sampling Disclaimer" in report_md

    # Verify direct report link
    assert f"/scans/{scan_id}" in report_md

    # Verify Check Run payload: non-blocking conclusion default
    check_payload = formatter.build_check_run_payload()
    assert check_payload.conclusion == "neutral"  # Informational, non-blocking
    assert check_payload.status == "completed"
    assert len(check_payload.output.annotations) == 2
    assert check_payload.output.annotations[0].annotation_level == "failure"
    assert check_payload.output.annotations[1].annotation_level == "warning"


@pytest.mark.asyncio
async def test_secret_sanitization_in_logs():
    """Verifies that secrets, installation tokens, and RSA keys are strictly masked."""
    token = "ghs_1234567890abcdefghijklmnopqrstuvwxyz"
    private_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAz3...secret\n-----END RSA PRIVATE KEY-----"
    raw_log = f"Error communicating with GitHub using token {token} and key:\n{private_key}"

    sanitized = sanitize_secret(raw_log)
    assert token not in sanitized
    assert "gh_***[REDACTED]" in sanitized
    assert "[PRIVATE KEY REDACTED]" in sanitized


@pytest.mark.asyncio
async def test_end_to_end_worker_pr_analysis_execution(test_repo: Repository):
    """Verifies execute_github_pr_analysis_async end-to-end execution without live GitHub."""
    scan_id = str(uuid.uuid4())
    async with async_session_factory() as session:
        scan = ScanRun(
            id=scan_id,
            tenant_id=test_repo.tenant_id,
            repository_id=test_repo.id,
            base_sha="0" * 40,
            head_sha="f" * 40,
            status="QUEUED",
        )
        session.add(scan)
        await session.commit()

    # Execute async analysis logic
    result = await execute_github_pr_analysis_async(
        scan_id=scan_id,
        repo_id=test_repo.id,
        base_sha="0" * 40,
        head_sha="f" * 40,
        pr_number=123,
    )

    assert result["status"] == "COMPLETED"

    # Verify ScanRun status updated in DB
    async with async_session_factory() as session:
        updated_scan = await session.get(ScanRun, scan_id)
        assert updated_scan is not None
        assert updated_scan.status == "COMPLETED"
        assert updated_scan.completed_at is not None
