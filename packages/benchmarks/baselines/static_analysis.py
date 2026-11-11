"""Baseline B: Static Dependency Analysis.

Combines structural schema diff with static AST import and call graphs.
Discovers static direct callers, but blind to runtime-only traces, hidden workers, and semantic domain drift.
"""

import time

from packages.benchmarks.baselines.base import BaseBaseline
from packages.benchmarks.models import BaselinePrediction, BenchmarkScenario


class BaselineBStaticAnalysis(BaseBaseline):
    """Represents static code graph analyzers (e.g. CodeQL, Dependency-Track, static AST traversers)."""

    def __init__(self) -> None:
        super().__init__(name="Baseline B (Static Analysis)")

    def evaluate(self, scenario: BenchmarkScenario) -> BaselinePrediction:
        start = time.perf_counter()

        emitted_findings: list[str] = []
        is_breaking = False
        severity = "NONE"

        before = scenario.before_state
        after = scenario.after_state

        # 1. Structural changes detection (inherited from schema diff)
        before_props = before.get("properties", {})
        after_props = after.get("properties", {})
        removed_fields = set(before_props.keys()) - set(after_props.keys())
        for f in removed_fields:
            emitted_findings.append(f"STATIC_BREAK: FIELD_REMOVED {f}")
            is_breaking = True
            severity = "BLOCKING"

        # Type changes
        for f in set(before_props.keys()) & set(after_props.keys()):
            if before_props[f].get("type") != after_props[f].get("type"):
                emitted_findings.append(f"STATIC_BREAK: TYPE_CHANGED {f}")
                is_breaking = True
                severity = "BLOCKING"

        # Endpoint removals
        before_paths = set(before.get("paths", {}).keys())
        after_paths = set(after.get("paths", {}).keys())
        for p in before_paths - after_paths:
            emitted_findings.append(f"STATIC_BREAK: ENDPOINT_REMOVED {p}")
            is_breaking = True
            severity = "BLOCKING"

        # Database schema drops
        before_cols = before.get("columns", {})
        after_cols = after.get("columns", {})
        for col in set(before_cols.keys()) - set(after_cols.keys()):
            emitted_findings.append(f"STATIC_BREAK: COLUMN_DROPPED {col}")
            is_breaking = True
            severity = "BLOCKING"

        # 2. Static Call Graph Traversal
        # Static analysis traverses edges where type in static set
        static_graph = scenario.static_graph or {}
        edges = static_graph.get("edges", [])
        affected_entities: list[str] = []
        impact_paths: list[list[str]] = []

        candidate_roots: set[str] = set()
        parts = scenario.changed_artifact.split("/")
        if parts[0] == "services" and len(parts) > 1:
            candidate_roots.add(parts[1])
        if len(parts) > 1:
            candidate_roots.add(parts[1].split(".")[0])
        candidate_roots.add(parts[-1].split(".")[0])
        candidate_roots.add(parts[0].split(".")[0])

        graph_targets = {e.get("target") for e in edges if e.get("target")}
        matched = candidate_roots & graph_targets
        target_entities = matched if matched else candidate_roots

        if is_breaking:
            for edge in edges:
                source = edge.get("source")
                target = edge.get("target")
                rel_type = edge.get("type", "STATIC_CALL")

                # Only static relationships are observed by Baseline B
                if rel_type in {"STATIC_IMPORT", "STATIC_CALL", "DIRECT_CLIENT", "CONSUMES_EVENT", "READS_DB"}:
                    if target in target_entities or any(t in scenario.changed_artifact for t in target_entities):
                        if source and source not in affected_entities:
                            affected_entities.append(source)
                            impact_paths.append([source, target])

        # Baseline B is BLIND to:
        # - Semantic unit changes (e.g. amount in cents vs dollars)
        # - Runtime-only dependencies (edges labeled RUNTIME_TRACE or DYNAMIC_RPC)
        detected_semantic_drift = False

        latency_ms = (time.perf_counter() - start) * 1000.0

        return BaselinePrediction(
            baseline_name=self.name,
            scenario_id=scenario.scenario_id,
            flagged_as_breaking=is_breaking,
            detected_semantic_drift=detected_semantic_drift,
            severity=severity,
            affected_entities=affected_entities,
            impact_paths=impact_paths,
            emitted_findings=emitted_findings,
            execution_latency_ms=round(latency_ms, 3),
            estimated_cost_usd=0.0,
            telemetry_used=False,
            ontology_used=False,
        )
