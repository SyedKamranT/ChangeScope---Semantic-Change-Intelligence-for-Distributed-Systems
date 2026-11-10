"""Unit tests for Blast Radius calculation and LangGraph Grounded Explainer."""

import pytest
from changescope.impact.blast_radius import BlastRadiusCalculator, ImpactedConsumer
from changescope.reasoning.models import RuleViolation
from changescope.reporting.langgraph_explainer import LangGraphGroundedExplainer


@pytest.mark.asyncio
async def test_blast_radius_risk_scoring_high_tier():
    # 1-hop TIER_1 consumer with 10,000 RPM
    mock_consumers = [
        ImpactedConsumer(
            service_id="srv-checkout",
            service_name="checkout-service",
            service_tier="TIER_1",
            hop_distance=1,
            path_confidence=0.95,
            is_observed=True,
            rpm=10000,
        )
    ]
    result = await BlastRadiusCalculator.compute_blast_radius(
        tenant_id="t1",
        endpoint_id="/api/v1/orders:POST",
        max_severity="BLOCKING",
        mock_impacted=mock_consumers,
    )
    # Severity 50 + (20 * 1.0 * 0.95 * log10(10010) ~= 76) -> capped at 100 or >= 80 (CRITICAL)
    assert result.risk_score >= 80
    assert result.risk_level == "CRITICAL"
    assert result.direct_consumers_count == 1
    assert result.transitive_consumers_count == 0


@pytest.mark.asyncio
async def test_blast_radius_risk_scoring_low_tier():
    # 3-hop TIER_3 consumer with 0 RPM and warning severity
    mock_consumers = [
        ImpactedConsumer(
            service_id="srv-analytics",
            service_name="analytics-worker",
            service_tier="TIER_3",
            hop_distance=3,
            path_confidence=0.70,
            is_observed=False,
            rpm=0,
        )
    ]
    result = await BlastRadiusCalculator.compute_blast_radius(
        tenant_id="t1",
        endpoint_id="/api/v1/ping:GET",
        max_severity="WARNING",
        mock_impacted=mock_consumers,
    )
    # Severity 25 + low impact -> < 40 (LOW or MEDIUM)
    assert result.risk_score < 40
    assert result.risk_level in {"LOW", "MEDIUM"}


def test_explainer_passes_citation_guard():
    pytest.helpers_blast_radius if hasattr(pytest, "helpers_blast_radius") else None

    # Create simple result
    from changescope.impact.blast_radius import BlastRadiusResult

    br = BlastRadiusResult(
        root_endpoint_id="/api/v1/items:POST",
        risk_score=85,
        risk_level="HIGH",
        direct_consumers_count=1,
        transitive_consumers_count=0,
        max_depth=1,
        impacted_consumers=[
            ImpactedConsumer(
                service_id="srv-pay",
                service_name="payment-service",
                service_tier="TIER_1",
                hop_distance=1,
                path_confidence=1.0,
                is_observed=True,
                rpm=5000,
            )
        ],
    )
    violations = [
        RuleViolation(
            rule_code="RULE_ENUM_NARROWED",
            severity="BLOCKING",
            file_path="src/schemas/item.py",
            start_line=10,
            end_line=15,
            message="Enum narrowed",
        )
    ]

    verified_files = {"src/schemas/item.py"}
    verified_traces = {"trace-1234"}

    output = LangGraphGroundedExplainer.generate_explanation(
        scan_id="scan-1",
        repo_name="inventory-service",
        blast_radius=br,
        violations=violations,
        verified_file_paths=verified_files,
        verified_trace_ids=verified_traces,
    )

    assert output["risk_score"] == 85
    assert output["citation_audit_passed"] is True
    assert "src/schemas/item.py" in output["markdown_report"]
    assert len(output["recommended_tests"]) > 0


def test_explainer_rejects_hallucinated_citations():
    from changescope.impact.blast_radius import BlastRadiusResult

    br = BlastRadiusResult(
        root_endpoint_id="/api/v1/items:POST",
        risk_score=75,
        risk_level="HIGH",
        direct_consumers_count=1,
        transitive_consumers_count=0,
        max_depth=1,
        impacted_consumers=[],
    )

    # Mock an LLM that hallucinates a nonexistent file path
    class HallucinatingLLM:
        def generate(self, prompt: str) -> str:
            return "This breaks `src/nonexistent/secret_code.py` and causes failure."

    verified_files = {"src/schemas/item.py"}
    verified_traces = set()

    output = LangGraphGroundedExplainer.generate_explanation(
        scan_id="scan-2",
        repo_name="inventory-service",
        blast_radius=br,
        violations=[],
        verified_file_paths=verified_files,
        verified_trace_ids=verified_traces,
        llm_client=HallucinatingLLM(),
    )

    # The citation verification guard must catch the hallucination!
    assert output["citation_audit_passed"] is False
    # The hallucinated file must NOT be in the sanitized report!
    assert "secret_code.py" not in output["markdown_report"]
    # Fallback template was used
    assert "ChangeScope Impact Analysis" in output["markdown_report"]
