"""Integration tests for ChangeScope Remediation Intelligence API Endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from packages.contracts.models import ChangeCategory, ContractFinding, FindingSeverity
from packages.shared.database import async_session_factory
from packages.shared.impact.models import (
    ExposureLevel,
    ImpactCategory,
    ImpactedEntity,
    ImpactPath,
    ImpactReasoningResult,
    RecommendedAction,
    RiskBreakdown,
    ServiceTier,
)
from packages.shared.models import Tenant
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
async def test_remediation_endpoint_unauthenticated(client: AsyncClient):
    """Verifies that accessing /api/v1/remediation/report without a JWT yields 401 Unauthorized."""
    res = await client.post(
        "/api/v1/remediation/report",
        json={"scan_id": "scan-123", "impact_result": {}, "findings": []},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_remediation_endpoint_authenticated(client: AsyncClient):
    """Verifies that an authenticated engineer can generate a comprehensive incident prevention report."""
    tenant_id = "tenant-remediation-api"

    async with async_session_factory() as session:
        if not await session.get(Tenant, tenant_id):
            session.add(Tenant(id=tenant_id, name="Remediation Tenant", slug=tenant_id, tier="enterprise"))
            await session.commit()

    headers = _auth_header(tenant_id)

    # Prepare impact result input
    consumer = ImpactedEntity(
        entity_id="order-service",
        entity_name="order-service",
        entity_type="Service",
        impact_category=ImpactCategory.DIRECT,
        hop_distance=1,
        path=["payment-service", "order-service"],
        path_confidence=0.98,
        is_runtime_confirmed=True,
        call_frequency_7d=12000,
        p95_latency_ms=25.0,
        service_tier=ServiceTier.TIER_1,
        exposure=ExposureLevel.INTERNAL_SERVICE,
        owner="@payments-core",
        ontology_concepts=["OrderFulfillment"],
        evidence_citations=["Trace exemplar: 4bf92f3577b34da6a3ce929d0e0e4736"],
    )

    path_obj = ImpactPath(
        source_entity="payment-service",
        target_entity="order-service",
        path_hops=["payment-service", "order-service"],
        relationship_types=["CALLS"],
        cumulative_confidence=0.98,
        evidence_references=["src/payment/client.py#L42-L55"],
        has_runtime_evidence=True,
    )

    impact_result = ImpactReasoningResult(
        change_set_id="cs-rem-101",
        tenant_id=tenant_id,
        root_changed_entities=["payment-service"],
        affected_entities=[consumer],
        graph_paths=[path_obj],
        summary_narrative="Field removed from payment-service impacts order-service.",
        risk_score=78,
        risk_level="HIGH",
        recommended_action=RecommendedAction.BLOCK_MERGE,
        risk_breakdown=RiskBreakdown(
            base_severity_score=50.0,
            reachability_score=1.2,
            usage_multiplier=1.3,
            criticality_score=1.0,
            exposure_factor=1.0,
            freshness_factor=1.0,
            semantic_confidence_factor=0.98,
            final_score=78,
            formula_explanation="High risk due to 12,000 runtime calls over 7d",
        ),
    )

    finding = ContractFinding(
        change_category=ChangeCategory.STRUCTURAL,
        change_type="RULE_FIELD_REMOVED",
        severity=FindingSeverity.BLOCKING,
        confidence=1.0,
        before_state={"charge_id": "ch_123", "amount": 100},
        after_state={"amount": 100},
        file_path="contracts/openapi/payment-api.yaml",
        start_line=45,
        end_line=45,
        affected_entities=["payment-service"],
        supporting_evidence={"field_name": "charge_id", "endpoint": "/api/v1/charges", "http_method": "POST"},
        recommended_verification="Ensure consumers tolerate removal of charge_id",
    )

    payload = {
        "scan_id": "scan-rem-prod-1",
        "impact_result": impact_result.model_dump(mode="json"),
        "findings": [finding.model_dump(mode="json")],
        "known_test_files": ["tests/integration/test_orders_api.py"],
    }

    res = await client.post("/api/v1/remediation/report", json=payload, headers=headers)
    assert res.status_code == 200
    report = res.json()

    # Invariant assertions
    assert report["scan_id"] == "scan-rem-prod-1"
    assert report["tenant_id"] == tenant_id
    assert report["risk_score"] == 78
    assert report["risk_level"] == "HIGH"
    assert report["recommended_action"] == "BLOCK_MERGE"

    # Regression test generation assertions
    assert len(report["test_recommendations"]) >= 1
    test_rec = report["test_recommendations"][0]
    assert test_rec["requires_human_review"] is True
    assert test_rec["review_status"] == "PENDING_HUMAN_REVIEW"
    assert "charge_id" in test_rec["test_objective"]
    assert test_rec["code_snippet"] is not None

    # Integration tests & contract tests
    assert len(report["affected_integration_tests"]) >= 1
    assert report["affected_integration_tests"][0]["service_name"] == "order-service"
    assert len(report["contract_test_updates"]) >= 1

    # Migration plan assertions (5 phases)
    assert len(report["migration_steps"]) == 5
    phases = [s["phase"] for s in report["migration_steps"]]
    assert phases == [
        "PHASE_1_PREPARATION",
        "PHASE_2_DUAL_WRITE",
        "PHASE_3_CONSUMER_MIGRATION",
        "PHASE_4_DEPRECATION",
        "PHASE_5_CLEANUP",
    ]

    # Ownership and compatibility patterns
    assert len(report["affected_owners"]) >= 1
    assert report["affected_owners"][0]["team_name"] == "Orders & Checkout Pod"
    assert len(report["compatibility_strategies"]) >= 1

    # Explainability facts tiering
    assert len(report["facts_and_evidence"]) >= 3
    classifications = {f["classification"] for f in report["facts_and_evidence"]}
    assert "VERIFIED_FACT" in classifications
    assert "INFERRED_FINDING" in classifications
    assert "RECOMMENDATION" in classifications

    # Auditable execution trace & Safety Invariant
    trace = report["execution_trace"]
    assert trace["status"] == "COMPLETED"
    assert trace["safety_checks_passed"] is True
    assert trace["can_deploy_or_merge"] is False  # Hard invariant: NEVER permitted to deploy or merge

    # Markdown report presentation
    md = report["markdown_report"]
    assert "# ChangeScope Incident-Prevention & Remediation Report" in md
    assert "NEVER permitted to auto-merge pull requests or deploy code" in md
    assert "Expand and Contract" in md
