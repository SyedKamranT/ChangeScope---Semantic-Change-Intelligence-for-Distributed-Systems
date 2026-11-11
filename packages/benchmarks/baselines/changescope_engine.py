"""Baseline C: Full ChangeScope Platform.

Unifies deterministic AST analysis, contract intelligence, semantic ontology reconciliation,
runtime OpenTelemetry trace correlation, transitive graph reasoning, and local Ollama LLM explainability.
"""

import time

from packages.benchmarks.baselines.base import BaseBaseline
from packages.benchmarks.models import BaselinePrediction, BenchmarkScenario
from packages.benchmarks.ollama_client import OllamaClient
from packages.shared.impact.engine import ImpactReasoningEngine
from packages.shared.impact.graph import DependencyKnowledgeGraph
from packages.shared.impact.models import ChangeSetInput, ProposedChange
from packages.shared.remediation.citation_guard import CitationVerificationGuard


class BaselineCFullChangeScope(BaseBaseline):
    """ChangeScope full semantic change intelligence pipeline."""

    def __init__(
        self,
        use_ollama: bool = True,
        ollama_model: str = "qwen3:4b",
        ollama_sample_count: int | None = 3,
    ) -> None:
        super().__init__(name="Baseline C (ChangeScope)")
        self.use_ollama = use_ollama
        self.ollama = OllamaClient(model=ollama_model)
        self.ollama_sample_count = ollama_sample_count
        self._ollama_calls = 0

    def evaluate(self, scenario: BenchmarkScenario) -> BaselinePrediction:
        start = time.perf_counter()

        emitted_findings: list[str] = []
        is_breaking = False
        is_semantic_drift = False
        severity = "NONE"
        telemetry_used = False
        ontology_used = False

        before = scenario.before_state
        after = scenario.after_state

        # Resolve root entity candidates against static graph and runtime traces
        candidate_roots: set[str] = set()
        parts = scenario.changed_artifact.split("/")
        if parts[0] == "services" and len(parts) > 1:
            candidate_roots.add(parts[1])
        if len(parts) > 1:
            candidate_roots.add(parts[1].split(".")[0])
        candidate_roots.add(parts[-1].split(".")[0])
        candidate_roots.add(parts[0].split(".")[0])

        graph_targets = {e.get("target") for e in scenario.static_graph.get("edges", []) if e.get("target")}
        graph_targets |= {t.get("target_service") for t in scenario.runtime_traces if t.get("target_service")}

        matched = candidate_roots & graph_targets
        root_entities = list(matched) if matched else (list(candidate_roots)[:1] if candidate_roots else ["root"])
        root_entity = root_entities[0]

        # ---------------------------------------------------------------------
        # 1. Contract & Structural Intelligence Engine
        # ---------------------------------------------------------------------
        before_props = before.get("properties", {})
        after_props = after.get("properties", {})

        # Field removal
        for f in set(before_props.keys()) - set(after_props.keys()):
            emitted_findings.append(f"FIELD_REMOVED: {f}")
            is_breaking = True
            severity = "BLOCKING"

        # Type incompatibility
        for f in set(before_props.keys()) & set(after_props.keys()):
            if before_props[f].get("type") != after_props[f].get("type"):
                emitted_findings.append(f"TYPE_INCOMPATIBILITY: {f}")
                is_breaking = True
                severity = "BLOCKING"

        # Endpoint removals
        for p in set(before.get("paths", {}).keys()) - set(after.get("paths", {}).keys()):
            emitted_findings.append(f"ENDPOINT_REMOVED: {p}")
            is_breaking = True
            severity = "BLOCKING"

        # Database schema migrations
        before_cols = before.get("columns", {})
        after_cols = after.get("columns", {})
        for col in set(before_cols.keys()) - set(after_cols.keys()):
            emitted_findings.append(f"DATABASE_COLUMN_DROPPED: {col}")
            is_breaking = True
            severity = "BLOCKING"

        # Database column type changes
        for col in set(before_cols.keys()) & set(after_cols.keys()):
            if before_cols[col].get("type") != after_cols[col].get("type"):
                emitted_findings.append(f"DATABASE_COLUMN_TYPE_CHANGED: {col}")
                is_breaking = True
                severity = "BLOCKING"

        # Database non-nullable added without default
        for col in set(after_cols.keys()) - set(before_cols.keys()):
            c_info = after_cols[col]
            if not c_info.get("nullable", True) and c_info.get("default") is None:
                emitted_findings.append(f"DATABASE_NON_NULLABLE_NO_DEFAULT: {col}")
                is_breaking = True
                severity = "BLOCKING"

        # Enum value removal / alteration
        for f in set(before_props.keys()) & set(after_props.keys()):
            b_enum = set(before_props[f].get("enum", [])) if isinstance(before_props[f], dict) else set()
            a_enum = set(after_props[f].get("enum", [])) if isinstance(after_props[f], dict) else set()
            if b_enum and (b_enum - a_enum):
                emitted_findings.append(f"ENUM_VALUE_REMOVED: {f} removed {b_enum - a_enum}")
                is_breaking = True
                severity = "BLOCKING"

        # Permission scope escalation
        before_perm = before.get("required_permissions", [])
        after_perm = after.get("required_permissions", [])
        if set(after_perm) - set(before_perm):
            new_perms = set(after_perm) - set(before_perm)
            emitted_findings.append(f"PERMISSION_REQUIREMENT_ESCALATED: {', '.join(new_perms)}")
            is_breaking = True
            severity = "BLOCKING"

        # Event ordering assumption changes
        if before.get("delivery_order") != after.get("delivery_order") and after.get("delivery_order") == "UNORDERED":
            emitted_findings.append("EVENT_ORDERING_ASSUMPTION_VIOLATED: sequential ordering removed")
            is_breaking = True
            severity = "BLOCKING"

        # ---------------------------------------------------------------------
        # 2. Semantic Ontology Reconciliation Layer
        # ---------------------------------------------------------------------
        ont_before = before.get("ontology", {}) or scenario.ontology_annotations.get("before", {})
        ont_after = after.get("ontology", {}) or scenario.ontology_annotations.get("after", {})

        if ont_before or ont_after:
            ontology_used = True

            # Monetary unit change (e.g. cents vs dollars)
            b_unit = ont_before.get("unit")
            a_unit = ont_after.get("unit")
            if b_unit and a_unit and b_unit != a_unit:
                emitted_findings.append(f"SEMANTIC_DRIFT_MONETARY_UNIT: {b_unit} -> {a_unit}")
                is_semantic_drift = True
                is_breaking = True
                severity = "BLOCKING"

            # Timestamp interpretation change (e.g. epoch_seconds vs epoch_millis, or UTC vs LOCAL)
            b_ts = ont_before.get("time_format")
            a_ts = ont_after.get("time_format")
            if b_ts and a_ts and b_ts != a_ts:
                emitted_findings.append(f"SEMANTIC_DRIFT_TIMESTAMP: {b_ts} -> {a_ts}")
                is_semantic_drift = True
                is_breaking = True
                severity = "BLOCKING"

            # Identifier semantic drift (e.g. user_id -> tenant_account_id)
            b_concept = ont_before.get("concept")
            a_concept = ont_after.get("concept")
            if b_concept and a_concept and b_concept != a_concept:
                emitted_findings.append(f"SEMANTIC_DRIFT_IDENTIFIER: {b_concept} -> {a_concept}")
                is_semantic_drift = True
                is_breaking = True
                severity = "BLOCKING"

            # Enum semantic shifts
            b_enums = ont_before.get("enum_meanings", {})
            a_enums = ont_after.get("enum_meanings", {})
            if b_enums != a_enums and (b_enums or a_enums):
                emitted_findings.append("SEMANTIC_DRIFT_ENUM: state lifecycle meaning modified")
                is_semantic_drift = True
                if severity == "NONE":
                    severity = "WARNING"

        # ---------------------------------------------------------------------
        # 3. Transitive Blast Radius Graph Traversal (Static + Runtime Traces)
        # ---------------------------------------------------------------------
        graph = DependencyKnowledgeGraph(tenant_id=f"bench-{scenario.scenario_id}")
        graph.add_node(root_entity, name=root_entity, entity_type="Service")

        # Static edges
        static_graph = scenario.static_graph or {}
        for node in static_graph.get("nodes", []):
            graph.add_node(node["id"], name=node.get("name", node["id"]), entity_type=node.get("type", "Service"))

        for edge in static_graph.get("edges", []):
            graph.add_edge(
                source_id=edge["source"],
                target_id=edge["target"],
                relationship_type=edge.get("type", "CALLS_STATIC"),
                confidence=1.0,
            )

        # Runtime OTel trace evidence correlation
        if scenario.runtime_traces:
            telemetry_used = True
            for trace in scenario.runtime_traces:
                client_srv = trace["client_service"]
                target_srv = trace["target_service"]
                graph.add_node(client_srv, name=client_srv, entity_type="Service")
                graph.add_node(target_srv, name=target_srv, entity_type="Service")
                graph.add_edge(
                    source_id=client_srv,
                    target_id=target_srv,
                    relationship_type="RUNTIME_OBSERVED",
                    call_count_7d=trace.get("call_count_7d", 1000),
                    confidence=trace.get("confidence", 0.98),
                )

        affected_entities: list[str] = []
        impact_paths: list[list[str]] = []

        if is_breaking or is_semantic_drift:
            engine = ImpactReasoningEngine(graph=graph, max_traversal_depth=5)
            changes = [
                ProposedChange(
                    entity_id=re,
                    entity_name=re,
                    entity_type="Service",
                    change_type="SCHEMA_MODIFIED" if not is_semantic_drift else "SEMANTIC_DRIFT",
                    severity=severity,
                    is_breaking=is_breaking,
                )
                for re in root_entities
            ]
            changeset = ChangeSetInput(
                tenant_id=f"bench-{scenario.scenario_id}",
                changes=changes,
            )
            impact_res = engine.evaluate_changeset(changeset)
            for aff in impact_res.affected_entities:
                if aff.entity_id not in root_entities and aff.entity_id not in affected_entities:
                    affected_entities.append(aff.entity_id)
                elif aff.entity_name not in root_entities and aff.entity_name not in affected_entities:
                    affected_entities.append(aff.entity_name)
            for path in impact_res.graph_paths:
                impact_paths.append(path.path_hops)

        deterministic_latency_ms = (time.perf_counter() - start) * 1000.0

        # ---------------------------------------------------------------------
        # 4. Narrative Synthesis via Local Ollama (qwen3:4b) + Citation Guard
        # ---------------------------------------------------------------------
        narrative: str | None = None
        llm_latency_ms = 0.0
        llm_used_fallback: bool | None = None
        if (is_breaking or is_semantic_drift) and self.use_ollama:
            if self.ollama_sample_count is None or self._ollama_calls < self.ollama_sample_count:
                llm_start = time.perf_counter()
                prompt = (
                    f"Explain distributed system change impact in one concise sentence: "
                    f"Artifact: {scenario.changed_artifact}. "
                    f"Findings: {'; '.join(emitted_findings[:2])}. "
                    f"Affected services: {', '.join(affected_entities[:3])}."
                )
                raw_text, _, _ = self.ollama.generate_narrative(prompt, max_tokens=50)
                llm_latency_ms = (time.perf_counter() - llm_start) * 1000.0
                llm_used_fallback = self.ollama.last_used_fallback
                self._ollama_calls += 1

                # Enforce Citation Guard invariant: reject fabricated entities
                verified_paths = {scenario.changed_artifact} | set(affected_entities)
                _, sanitized_narrative = CitationVerificationGuard.verify_and_sanitize_narrative(
                    candidate_markdown=raw_text,
                    verified_file_paths=verified_paths,
                    verified_trace_ids=set(),
                )
                narrative = sanitized_narrative

        return BaselinePrediction(
            baseline_name=self.name,
            scenario_id=scenario.scenario_id,
            flagged_as_breaking=is_breaking,
            detected_semantic_drift=is_semantic_drift,
            severity=severity,
            affected_entities=affected_entities,
            impact_paths=impact_paths,
            emitted_findings=emitted_findings,
            execution_latency_ms=round(deterministic_latency_ms, 3),
            llm_latency_ms=round(llm_latency_ms, 3),
            estimated_cost_usd=0.0,  # 100% free local Ollama execution
            llm_narrative=narrative,
            llm_used_fallback=llm_used_fallback,
            telemetry_used=telemetry_used,
            ontology_used=ontology_used,
        )
