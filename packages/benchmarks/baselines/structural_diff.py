"""Baseline A: Traditional Structural Schema Diff Only.

Evaluates changes purely through structural AST / schema field matching (OpenAPI diff, JSON Schema diff).
Blind to downstream service dependencies, runtime trace traffic, and semantic unit drift.
"""

import time

from packages.benchmarks.baselines.base import BaseBaseline
from packages.benchmarks.models import BaselinePrediction, BenchmarkScenario


class BaselineAStructuralDiff(BaseBaseline):
    """Represents industry standard structural API/schema diff tools (e.g. openapi-diff)."""

    def __init__(self) -> None:
        super().__init__(name="Baseline A (Structural Diff)")

    def evaluate(self, scenario: BenchmarkScenario) -> BaselinePrediction:
        start = time.perf_counter()

        emitted_findings: list[str] = []
        is_breaking = False
        severity = "NONE"

        before = scenario.before_state
        after = scenario.after_state

        # 1. Endpoint / Route removal
        before_paths = set(before.get("paths", {}).keys())
        after_paths = set(after.get("paths", {}).keys())
        removed_paths = before_paths - after_paths
        for p in removed_paths:
            emitted_findings.append(f"ENDPOINT_REMOVED: {p}")
            is_breaking = True
            severity = "BLOCKING"

        # 2. Schema properties comparison
        before_props = before.get("properties", {})
        after_props = after.get("properties", {})

        # Field removal
        removed_fields = set(before_props.keys()) - set(after_props.keys())
        for f in removed_fields:
            emitted_findings.append(f"FIELD_REMOVED: {f}")
            is_breaking = True
            severity = "BLOCKING"

        # Field addition (check if required)
        added_fields = set(after_props.keys()) - set(before_props.keys())
        after_required = set(after.get("required", []))
        for f in added_fields:
            if f in after_required:
                emitted_findings.append(f"REQUIRED_FIELD_ADDED: {f}")
                is_breaking = True
                severity = "BLOCKING"
            else:
                emitted_findings.append(f"OPTIONAL_FIELD_ADDED: {f}")
                if severity == "NONE":
                    severity = "INFO"

        # Field type incompatibility
        common_fields = set(before_props.keys()) & set(after_props.keys())
        for f in common_fields:
            b_type = before_props[f].get("type") if isinstance(before_props[f], dict) else None
            a_type = after_props[f].get("type") if isinstance(after_props[f], dict) else None
            if b_type and a_type and b_type != a_type:
                emitted_findings.append(f"TYPE_INCOMPATIBILITY: {f} ({b_type} -> {a_type})")
                is_breaking = True
                severity = "BLOCKING"

        # 3. Database migrations / column checks
        before_cols = before.get("columns", {})
        after_cols = after.get("columns", {})
        for col in set(before_cols.keys()) - set(after_cols.keys()):
            emitted_findings.append(f"COLUMN_DROPPED: {col}")
            is_breaking = True
            severity = "BLOCKING"
        for col in set(before_cols.keys()) & set(after_cols.keys()):
            if before_cols[col].get("type") != after_cols[col].get("type"):
                emitted_findings.append(f"COLUMN_TYPE_CHANGED: {col}")
                is_breaking = True
                severity = "BLOCKING"

        # Structural diff is blind to semantic drift (units, time interpretation, ID polysemy)
        detected_semantic_drift = False

        # Structural diff cannot identify downstream consumers
        affected_entities = [scenario.changed_artifact] if is_breaking else []

        latency_ms = (time.perf_counter() - start) * 1000.0

        return BaselinePrediction(
            baseline_name=self.name,
            scenario_id=scenario.scenario_id,
            flagged_as_breaking=is_breaking,
            detected_semantic_drift=detected_semantic_drift,
            severity=severity,
            affected_entities=affected_entities,
            impact_paths=[],  # Structural diff has no graph awareness
            emitted_findings=emitted_findings,
            execution_latency_ms=round(latency_ms, 3),
            estimated_cost_usd=0.0,
            telemetry_used=False,
            ontology_used=False,
        )
