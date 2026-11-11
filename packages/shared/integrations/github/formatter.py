"""GitHub PR comment and Check Run report formatter with 8 mandated sections."""

from typing import Literal

from packages.contracts.models import ChangeCategory, ContractFinding, FindingSeverity
from packages.shared.config import settings
from packages.shared.impact.models import ImpactReasoningResult
from packages.shared.integrations.github.models import (
    GitHubCheckRunAnnotation,
    GitHubCheckRunCreate,
    GitHubCheckRunOutput,
)
from packages.shared.remediation.models import IncidentPreventionReport


class GitHubReportFormatter:
    """Formats ChangeScope scan results into Markdown reports and GitHub Check Run payloads."""

    def __init__(
        self,
        scan_id: str,
        repo_name: str,
        base_sha: str,
        head_sha: str,
        risk_score: int,
        risk_level: str,
        findings: list[ContractFinding] | None = None,
        impact_result: ImpactReasoningResult | None = None,
        incident_report: IncidentPreventionReport | None = None,
        pr_number: int | None = None,
        frontend_base_url: str | None = None,
    ) -> None:
        self.scan_id = scan_id
        self.repo_name = repo_name
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.risk_score = risk_score
        self.risk_level = risk_level.upper()
        self.findings = findings or []
        self.impact_result = impact_result
        self.incident_report = incident_report
        self.pr_number = pr_number
        self.frontend_base_url = (frontend_base_url or settings.FRONTEND_URL).rstrip("/")

    @property
    def report_url(self) -> str:
        """Deep link to ChangeScope interactive scan dashboard."""
        return f"{self.frontend_base_url}/scans/{self.scan_id}"

    def build_markdown_report(self) -> str:
        """Constructs full Markdown report containing all 8 mandated sections."""
        short_base = self.base_sha[:7] if len(self.base_sha) >= 7 else self.base_sha
        short_head = self.head_sha[:7] if len(self.head_sha) >= 7 else self.head_sha

        badge_emoji = "🟢" if self.risk_level == "LOW" else "🟡" if self.risk_level == "MEDIUM" else "🔴"

        sections = [
            "# 🔬 ChangeScope Semantic Intelligence Report\n",
            f"{badge_emoji} **Risk Score: `{self.risk_score}/100` ({self.risk_level})**",
            f"**Repository**: `{self.repo_name}` | **Commit**: `{short_base}...{short_head}`",
            f"🔗 [**View Full Interactive Analysis & Blast Radius Graph**]({self.report_url})\n",
            "---\n",
            self._render_section_1_change_summary(),
            self._render_section_2_breaking_changes(),
            self._render_section_3_semantic_risks(),
            self._render_section_4_affected_downstream_services(),
            self._render_section_5_runtime_evidence(),
            self._render_section_6_impact_paths(),
            self._render_section_7_recommended_regression_tests(),
            self._render_section_8_confidence_and_uncertainty(),
            "---\n",
            "*ChangeScope deterministic change intelligence. Non-blocking informational mode.*",
        ]
        return "\n".join(sections)

    def _render_section_1_change_summary(self) -> str:
        breaking_count = sum(1 for f in self.findings if f.severity == FindingSeverity.BLOCKING)
        semantic_count = sum(1 for f in self.findings if f.change_category == ChangeCategory.SEMANTIC)
        services_count = self.impact_result.impacted_services_count if self.impact_result else 0
        endpoints_count = self.impact_result.impacted_endpoints_count if self.impact_result else 0

        lines = [
            "### 1. Change Summary\n",
            f"- **Total Findings**: {len(self.findings)}",
            f"- **Breaking Contract Changes**: {breaking_count}",
            f"- **Semantic Risk Anomaly Count**: {semantic_count}",
            f"- **Impacted Downstream Services**: {services_count}",
            f"- **Impacted Endpoints / Handlers**: {endpoints_count}",
        ]
        if self.incident_report and self.incident_report.executive_summary:
            lines.append(f"\n> **Executive Summary**: {self.incident_report.executive_summary}\n")
        return "\n".join(lines) + "\n"

    def _render_section_2_breaking_changes(self) -> str:
        breaking_findings = [f for f in self.findings if f.severity == FindingSeverity.BLOCKING]
        lines = ["### 2. Breaking Changes\n"]
        if not breaking_findings:
            lines.append(
                "✅ **No breaking contract changes detected.** All modifications maintain backwards compatibility.\n"
            )
            return "\n".join(lines)

        lines.append("| Type | File / Entity | Severity | Details |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for f in breaking_findings:
            target = ", ".join(f.affected_entities) if f.affected_entities else f.file_path
            lines.append(f"| `{f.change_type}` | `{target}` | **{f.severity.value}** | {f.recommended_verification} |")
        lines.append("")
        return "\n".join(lines)

    def _render_section_3_semantic_risks(self) -> str:
        semantic_findings = [f for f in self.findings if f.change_category == ChangeCategory.SEMANTIC]
        lines = ["### 3. Semantic Risks\n"]
        if not semantic_findings:
            lines.append("✅ **No semantic anomalies or subtle unit/type mismatches detected.**\n")
            return "\n".join(lines)

        lines.append("| Entity | Anomaly Type | Confidence | Description |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for f in semantic_findings:
            entity_str = ", ".join(f.affected_entities) if f.affected_entities else "General"
            conf_pct = int(f.confidence * 100)
            lines.append(f"| `{entity_str}` | `{f.change_type}` | `{conf_pct}%` | {f.recommended_verification} |")
        lines.append("")
        return "\n".join(lines)

    def _render_section_4_affected_downstream_services(self) -> str:
        lines = ["### 4. Affected Downstream Services\n"]
        affected: list[str] = []
        if self.impact_result and self.impact_result.affected_entities:
            for entity in self.impact_result.affected_entities:
                if entity.entity_type in {"service", "service_client", "database_table"}:
                    cat = (
                        entity.impact_category.value
                        if hasattr(entity.impact_category, "value")
                        else str(entity.impact_category)
                    )
                    affected.append(
                        f"- **`{entity.entity_name}`** (`{entity.entity_type}`): {cat} (Hop: {entity.hop_distance})"
                    )

        if not affected:
            lines.append("No downstream services are directly impacted by this change.\n")
        else:
            lines.extend(affected)
            lines.append("")
        return "\n".join(lines)

    def _render_section_5_runtime_evidence(self) -> str:
        lines = [
            "### 5. Runtime Evidence\n",
        ]
        evidence_list: list[str] = []
        if self.impact_result and self.impact_result.evidence_references:
            evidence_list.extend(f"- {ev}" for ev in self.impact_result.evidence_references)

        if not evidence_list:
            lines.append("No active runtime communication traces recorded during observation window.\n")
        else:
            lines.extend(evidence_list)
            lines.append("")

        # Crucial runtime sampling disclaimer
        lines.append(
            "> ⚠️ **Runtime Trace Sampling Disclaimer**: Observed dependencies reflect real OpenTelemetry traces. "
            "Absence of trace traffic does not guarantee absence of dependency (dynamic traffic sampling, off-peak dormancy, "
            "or uninstrumented clients may apply).\n"
        )
        return "\n".join(lines)

    def _render_section_6_impact_paths(self) -> str:
        lines = ["### 6. Impact Paths\n"]
        if not self.impact_result or not self.impact_result.graph_paths:
            lines.append("No transitive impact paths observed across service boundaries.\n")
            return "\n".join(lines)

        for path in self.impact_result.graph_paths[:5]:  # Show top 5 paths
            hops = path.path_hops or [path.source_entity, path.target_entity]
            path_str = " ➔ ".join(f"`{hop}`" for hop in hops)
            rel = ", ".join(path.relationship_types) if path.relationship_types else "DEPENDS_ON"
            lines.append(f"- **Path [{rel}]**: {path_str} *(Confidence: {path.cumulative_confidence:.2f})*")
        lines.append("")
        return "\n".join(lines)

    def _render_section_7_recommended_regression_tests(self) -> str:
        lines = ["### 7. Recommended Regression Tests\n"]
        test_recs = self.incident_report.test_recommendations if self.incident_report else []
        if not test_recs:
            lines.append("No regression test additions required for this change.\n")
            return "\n".join(lines)

        for rec in test_recs[:5]:  # Top 5 recommendations
            conf_pct = int(rec.confidence * 100)
            lines.extend(
                [
                    f"#### 🧪 `{rec.test_id}`: {rec.test_objective}",
                    f"- **Affected Service**: `{rec.affected_service}`",
                    f"- **Expected Behavior**: {rec.expected_behavior}",
                    f"- **Relevant Finding**: {rec.relevant_finding}",
                    f"- **Confidence**: `{conf_pct}%` *(Status: {rec.review_status})*",
                    "",
                ]
            )
        return "\n".join(lines)

    def _render_section_8_confidence_and_uncertainty(self) -> str:
        conf = self.impact_result.overall_confidence if self.impact_result else 1.0
        uncertainty = self.impact_result.overall_uncertainty if self.impact_result else 0.0
        conf_pct = int(conf * 100)
        uncertainty_pct = int(uncertainty * 100)

        lines = [
            "### 8. Confidence and Uncertainty\n",
            f"- **Engine Confidence**: `{conf_pct}%`",
            f"- **Uncertainty Factor**: `{uncertainty_pct}%`",
        ]
        if uncertainty > 0.0:
            lines.append(
                "- **Uncertainty Factors**: Dynamic runtime evaluation or external client calls with unverified specifications."
            )
        else:
            lines.append(
                "- **Deterministic Guarantee**: 100% grounded in verified source ASTs and deterministic graph traversal."
            )

        lines.append(f"\n[🔗 **Inspect Full Details on ChangeScope**]({self.report_url})\n")
        return "\n".join(lines)

    def build_check_run_payload(self) -> GitHubCheckRunCreate:
        """Constructs GitHub Check Run payload with non-blocking conclusion and annotations."""
        summary_text = (
            f"Risk Score {self.risk_score}/100 ({self.risk_level}). "
            f"Evaluated {len(self.findings)} findings across {self.repo_name}."
        )

        annotations: list[GitHubCheckRunAnnotation] = []
        for finding in self.findings:
            # Map severity to check run annotation level
            level: Literal["notice", "warning", "failure"] = (
                "failure"
                if finding.severity == FindingSeverity.BLOCKING
                else "warning"
                if finding.severity == FindingSeverity.WARNING
                else "notice"
            )

            # Extract line numbers from evidence if available, else line 1
            line = 1
            if finding.supporting_evidence and "line" in finding.supporting_evidence:
                try:
                    line = int(finding.supporting_evidence["line"])
                except (ValueError, TypeError):
                    line = 1

            annotations.append(
                GitHubCheckRunAnnotation(
                    path=finding.file_path or "contract.yaml",
                    start_line=max(1, line),
                    end_line=max(1, line),
                    annotation_level=level,
                    title=f"[{finding.severity.value}] {finding.change_type}",
                    message=f"{finding.recommended_verification}",
                )
            )

        conclusion_setting = settings.GITHUB_CHECK_RUN_CONCLUSION_DEFAULT
        # Respect non-blocking default ("neutral")
        return GitHubCheckRunCreate(
            name="ChangeScope Semantic Intelligence",
            head_sha=self.head_sha,
            details_url=self.report_url,
            external_id=self.scan_id,
            status="completed",
            conclusion=conclusion_setting,
            output=GitHubCheckRunOutput(
                title=f"ChangeScope: Risk {self.risk_score}/100 ({self.risk_level})",
                summary=summary_text,
                text=self.build_markdown_report(),
                annotations=annotations,
            ),
        )
