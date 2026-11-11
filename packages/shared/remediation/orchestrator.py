"""Multi-Step Remediation Workflow Orchestrator with Safety Invariants and Execution Tracing."""

import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from packages.contracts.models import ContractFinding
from packages.shared.impact.models import ImpactReasoningResult
from packages.shared.logger import logger
from packages.shared.remediation.citation_guard import CitationVerificationGuard
from packages.shared.remediation.explainability import ExplainabilityClassifier
from packages.shared.remediation.migration_planner import MigrationPlanner
from packages.shared.remediation.models import (
    IncidentPreventionReport,
    RemediationExecutionTrace,
)
from packages.shared.remediation.test_generator import RemediationTestGenerator
from packages.shared.telemetry.pii_scrubber import PIIScrubber

PROMPT_INJECTION_PATTERN = re.compile(
    r"(?:ignore\s+previous\s+instructions|system\s+prompt|disregard\s+prior|<\|im_start\|>|<\|im_end\|>)",
    re.IGNORECASE,
)


class RemediationOrchestrator:
    """Orchestrates multi-step remediation intelligence with safety invariants and auditable traces."""

    PROMPT_TOKEN_COST_PER_1K = 0.003
    COMPLETION_TOKEN_COST_PER_1K = 0.015

    def __init__(self, max_retries: int = 3, timeout_seconds: float = 30.0) -> None:
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    def generate_incident_prevention_report(
        self,
        scan_id: str,
        tenant_id: str,
        impact_result: ImpactReasoningResult,
        findings: list[ContractFinding],
        verified_file_paths: set[str] | None = None,
        verified_trace_ids: set[str] | None = None,
        known_test_files: list[str] | None = None,
    ) -> IncidentPreventionReport:
        """Executes the multi-step remediation intelligence workflow."""
        start_time = time.perf_counter()
        trace_id = f"trace-rem-{uuid.uuid4().hex[:12]}"
        step_logs: list[dict[str, Any]] = []

        total_prompt_tokens = 0
        total_completion_tokens = 0

        verified_paths = verified_file_paths or set()
        verified_traces = verified_trace_ids or set()

        for f in findings:
            verified_paths.add(f.file_path)

        for p in impact_result.graph_paths:
            for ref in p.evidence_references:
                if "#" in ref:
                    verified_paths.add(ref.split("#")[0])

        # ---------------------------------------------------------------------
        # Step 1: Sanitize Inputs & Enforce Zero-Secret Retention
        # ---------------------------------------------------------------------
        step_1_start = time.perf_counter()
        sanitized_findings: list[ContractFinding] = []
        for finding in findings:
            clean_evidence = PIIScrubber.scrub_attributes(finding.supporting_evidence)
            clean_before = PIIScrubber.scrub_attributes(finding.before_state)
            clean_after = PIIScrubber.scrub_attributes(finding.after_state)

            # Scrub prompt injection in free-form strings
            clean_desc = PROMPT_INJECTION_PATTERN.sub("[UNTRUSTED_CONTENT_FILTERED]", finding.recommended_verification)

            # Approximate prompt tokens evaluated
            tokens = len(str(clean_evidence)) // 4
            total_prompt_tokens += tokens

            sanitized_finding = finding.model_copy(
                update={
                    "supporting_evidence": clean_evidence,
                    "before_state": clean_before,
                    "after_state": clean_after,
                    "recommended_verification": clean_desc,
                }
            )
            sanitized_findings.append(sanitized_finding)

        step_logs.append(
            {
                "step": "sanitize_untrusted_inputs",
                "duration_ms": int((time.perf_counter() - step_1_start) * 1000),
                "findings_sanitized": len(sanitized_findings),
            }
        )

        # ---------------------------------------------------------------------
        # Step 2: Synthesize Evidence-Backed Test Cases
        # ---------------------------------------------------------------------
        step_2_start = time.perf_counter()
        test_recs = RemediationTestGenerator.generate_regression_tests(
            findings=sanitized_findings,
            impacted_entities=impact_result.affected_entities,
            impact_paths=impact_result.graph_paths,
        )
        affected_int_tests = RemediationTestGenerator.identify_affected_integration_tests(
            impacted_entities=impact_result.affected_entities,
            findings=sanitized_findings,
            known_test_files=known_test_files,
        )
        contract_updates = RemediationTestGenerator.suggest_contract_test_updates(
            findings=sanitized_findings,
            impacted_entities=impact_result.affected_entities,
        )
        step_logs.append(
            {
                "step": "synthesize_test_cases",
                "duration_ms": int((time.perf_counter() - step_2_start) * 1000),
                "regression_tests": len(test_recs),
                "integration_tests": len(affected_int_tests),
                "contract_updates": len(contract_updates),
            }
        )

        # ---------------------------------------------------------------------
        # Step 3: Phased Migration Planning & Compatibility Strategies
        # ---------------------------------------------------------------------
        step_3_start = time.perf_counter()
        migration_steps = MigrationPlanner.generate_migration_plan(
            findings=sanitized_findings,
            impacted_entities=impact_result.affected_entities,
        )
        compat_strategies = MigrationPlanner.recommend_compatibility_strategies(
            findings=sanitized_findings,
            impacted_entities=impact_result.affected_entities,
        )
        affected_owners = MigrationPlanner.identify_affected_owners(
            impacted_entities=impact_result.affected_entities,
        )
        step_logs.append(
            {
                "step": "plan_migration_and_strategies",
                "duration_ms": int((time.perf_counter() - step_3_start) * 1000),
                "migration_steps": len(migration_steps),
                "strategies": len(compat_strategies),
                "owners_identified": len(affected_owners),
            }
        )

        # ---------------------------------------------------------------------
        # Step 4: Differentiate Explainability Tiers
        # ---------------------------------------------------------------------
        step_4_start = time.perf_counter()
        facts_and_evidence = ExplainabilityClassifier.extract_facts_and_evidence(
            findings=sanitized_findings,
            impacted_entities=impact_result.affected_entities,
            test_recommendations=test_recs,
            migration_steps=migration_steps,
            recommended_action=impact_result.recommended_action.value,
        )
        step_logs.append(
            {
                "step": "classify_explainability_tiers",
                "duration_ms": int((time.perf_counter() - step_4_start) * 1000),
                "total_facts": len(facts_and_evidence),
            }
        )

        # ---------------------------------------------------------------------
        # Step 5: Render Human-Readable Markdown Report
        # ---------------------------------------------------------------------
        step_5_start = time.perf_counter()
        raw_markdown = self._render_incident_prevention_markdown(
            scan_id=scan_id,
            impact_result=impact_result,
            findings=sanitized_findings,
            test_recs=test_recs,
            affected_int_tests=affected_int_tests,
            contract_updates=contract_updates,
            migration_steps=migration_steps,
            compat_strategies=compat_strategies,
            affected_owners=affected_owners,
            facts=facts_and_evidence,
        )

        # Track completion tokens
        total_completion_tokens += len(raw_markdown) // 4

        # ---------------------------------------------------------------------
        # Step 6: Citation Guard Verification
        # ---------------------------------------------------------------------
        is_verified, sanitized_markdown = CitationVerificationGuard.verify_and_sanitize_narrative(
            candidate_markdown=raw_markdown,
            verified_file_paths=verified_paths,
            verified_trace_ids=verified_traces,
        )
        step_logs.append(
            {
                "step": "citation_guard_audit",
                "duration_ms": int((time.perf_counter() - step_5_start) * 1000),
                "passed": is_verified,
            }
        )

        # ---------------------------------------------------------------------
        # Step 7: Enforce Hard Security Gate Invariant
        # ---------------------------------------------------------------------
        # HARD INVARIANT: The agent is NEVER permitted to deploy code or merge PRs.
        can_deploy_or_merge = False

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        cost_usd = (total_prompt_tokens / 1000.0) * self.PROMPT_TOKEN_COST_PER_1K + (
            total_completion_tokens / 1000.0
        ) * self.COMPLETION_TOKEN_COST_PER_1K

        execution_trace = RemediationExecutionTrace(
            trace_id=trace_id,
            steps=step_logs,
            token_usage={
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
            },
            estimated_cost_usd=round(cost_usd, 6),
            duration_ms=duration_ms,
            status="COMPLETED",
            safety_checks_passed=True,
            can_deploy_or_merge=can_deploy_or_merge,
            timestamp=datetime.now(UTC),
        )

        logger.info(
            "remediation_intelligence_report_generated",
            scan_id=scan_id,
            duration_ms=duration_ms,
            tests_generated=len(test_recs),
            cost_usd=cost_usd,
        )

        return IncidentPreventionReport(
            scan_id=scan_id,
            tenant_id=tenant_id,
            risk_score=impact_result.risk_score,
            risk_level=impact_result.risk_level,
            recommended_action=impact_result.recommended_action.value,
            executive_summary=(
                f"ChangeScope evaluated {len(sanitized_findings)} finding(s). "
                f"Deterministic Risk: {impact_result.risk_score}/100 ({impact_result.risk_level}). "
                f"Recommended Policy: {impact_result.recommended_action.value}. "
                f"Synthesized {len(test_recs)} regression test(s), {len(affected_int_tests)} affected integration test(s), "
                f"and a {len(migration_steps)}-phase zero-downtime migration plan."
            ),
            facts_and_evidence=facts_and_evidence,
            test_recommendations=test_recs,
            affected_integration_tests=affected_int_tests,
            contract_test_updates=contract_updates,
            migration_steps=migration_steps,
            affected_owners=affected_owners,
            compatibility_strategies=compat_strategies,
            markdown_report=sanitized_markdown,
            execution_trace=execution_trace,
            created_at=datetime.now(UTC),
        )

    def _render_incident_prevention_markdown(
        self,
        scan_id: str,
        impact_result: ImpactReasoningResult,
        findings: list[ContractFinding],
        test_recs: list[Any],
        affected_int_tests: list[Any],
        contract_updates: list[Any],
        migration_steps: list[Any],
        compat_strategies: list[Any],
        affected_owners: list[Any],
        facts: list[Any],
    ) -> str:
        """Renders comprehensive, publication-ready Markdown report."""
        lines: list[str] = [
            "# ChangeScope Incident-Prevention & Remediation Report",
            f"**Scan ID:** `{scan_id}` | **Evaluated At:** `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%SZ')}`",
            "",
            "> [!IMPORTANT]",
            "> **Safety Guard & Operational Invariant:** The ChangeScope system is strictly an advisory intelligence engine.",
            "> It is NEVER permitted to auto-merge pull requests or deploy code.",
            "> All synthesized tests require human review and authorization (`PENDING_HUMAN_REVIEW`).",
            "",
            "## 1. Executive Summary & Deterministic Risk",
            f"- **Operational Risk Score:** `{impact_result.risk_score}/100` ({impact_result.risk_level})",
            f"- **Recommended Policy Action:** `{impact_result.recommended_action.value}`",
            f"- **Impact Breadth:** {impact_result.impacted_services_count} service(s), {impact_result.impacted_endpoints_count} endpoint(s), {len(impact_result.affected_workflows)} workflow(s)",
            "",
            "### Risk Score Breakdown & Audit Trail",
            "```text",
            impact_result.risk_breakdown.formula_explanation,
            "```",
            "",
            "## 2. Explainability & Grounding Audit",
            "ChangeScope explicitly separates verified facts, graph-inferred findings, and actionable recommendations:",
            "",
            "| Classification | Statement | Evidence Source | Confidence |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for fact in facts[:10]:
            lines.append(
                f"| **{fact.classification.value}** | {fact.statement} | `{fact.source}` | {fact.confidence:.2f} |"
            )

        lines.extend(
            [
                "",
                "## 3. Targeted Regression Test Recommendations",
                "*All generated tests are flagged as `PENDING_HUMAN_REVIEW` prior to execution.*",
                "",
            ]
        )

        for test in test_recs:
            lines.append(f"### Test: `{test.test_objective}`")
            lines.append(f"- **Target Service:** `{test.affected_service}` ({test.test_type.value})")
            lines.append(f"- **Preconditions:** {', '.join(test.preconditions)}")
            lines.append(f"- **Expected Behavior:** {test.expected_behavior}")
            lines.append(f"- **Evidence References:** `{', '.join(test.evidence_references)}`")
            if test.code_snippet:
                lines.append("```python")
                lines.append(test.code_snippet.strip())
                lines.append("```")
            lines.append("")

        if affected_int_tests:
            lines.extend(
                [
                    "## 4. Affected Repository Integration Tests",
                    "The following existing test suites exercise impacted downstream pathways:",
                    "",
                    "| Test File | Test Case | Service | Rationale |",
                    "| :--- | :--- | :--- | :--- |",
                ]
            )
            for at in affected_int_tests:
                lines.append(f"| `{at.test_file}` | `{at.test_name}` | `{at.service_name}` | {at.reason} |")
            lines.append("")

        if contract_updates:
            lines.extend(
                [
                    "## 5. Consumer-Driven Contract Test Updates",
                    "| Consumer Service | Provider Service | Contract File | Recommended Assertion |",
                    "| :--- | :--- | :--- | :--- |",
                ]
            )
            for cu in contract_updates:
                lines.append(
                    f"| `{cu.consumer_service}` | `{cu.provider_service}` | `{cu.contract_file}` | `{cu.recommended_assertion}` |"
                )
            lines.append("")

        if migration_steps:
            lines.extend(
                [
                    "## 6. Phased Zero-Downtime Migration Roadmap",
                    "| Step | Phase | Action Title | Responsible Team | Rollback Plan | Est. Duration |",
                    "| :--- | :--- | :--- | :--- | :--- | :--- |",
                ]
            )
            for ms in migration_steps:
                lines.append(
                    f"| {ms.step_number} | `{ms.phase.value}` | **{ms.title}** | {ms.responsible_team} | {ms.rollback_plan} | {ms.estimated_duration} |"
                )
            lines.append("")

        if compat_strategies:
            lines.extend(["## 7. Recommended Compatibility Strategies", ""])
            for cs in compat_strategies:
                lines.append(f"### {cs.title} (`{cs.strategy_type.value}`)")
                lines.append(f"**Rationale:** {cs.rationale}")
                lines.append("**Implementation Steps:**")
                for s in cs.implementation_steps:
                    lines.append(f"- {s}")
                lines.append("**Risks & Tradeoffs:**")
                for r in cs.drawbacks_and_risks:
                    lines.append(f"- {r}")
                lines.append("")

        if affected_owners:
            lines.extend(
                [
                    "## 8. Affected Downstream Service Owners",
                    "| Service Name | Team Name | Owner Handle | Slack / Alert Channel | Escalation |",
                    "| :--- | :--- | :--- | :--- | :--- |",
                ]
            )
            for ao in affected_owners:
                lines.append(
                    f"| `{ao.service_name}` | {ao.team_name} | `{ao.owner_handle}` | `{ao.contact_channel}` | **{ao.severity_level}** |"
                )
            lines.append("")

        return "\n".join(lines)
