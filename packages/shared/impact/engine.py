"""ChangeScope Deterministic Impact Reasoning Engine."""

from collections import deque
from datetime import UTC, datetime
from typing import Any

from packages.shared.impact.graph import DependencyKnowledgeGraph, GraphEdge
from packages.shared.impact.models import (
    ChangeSetInput,
    ExposureLevel,
    ImpactCategory,
    ImpactedEntity,
    ImpactPath,
    ImpactReasoningResult,
    ServiceTier,
)
from packages.shared.impact.risk_calculator import RiskCalculator


class ImpactReasoningEngine:
    """Core deterministic reasoning engine executing multi-hop dependency and semantic impact analysis."""

    def __init__(self, graph: DependencyKnowledgeGraph, max_traversal_depth: int = 5) -> None:
        self.graph = graph
        self.max_traversal_depth = max_traversal_depth

    def evaluate_changeset(self, changeset: ChangeSetInput) -> ImpactReasoningResult:
        """Executes the complete 10-step deterministic impact analysis algorithm on a proposed ChangeSet."""
        # ---------------------------------------------------------------------
        # 1. Identify directly changed entities
        # ---------------------------------------------------------------------
        root_entity_ids: list[str] = []
        max_severity = "INFO"

        for change in changeset.changes:
            root_id = change.entity_id
            root_entity_ids.append(root_id)

            # Ensure root node is registered in the knowledge graph
            node = self.graph.get_node(root_id)
            if not node:
                node = self.graph.add_node(
                    node_id=root_id,
                    name=change.entity_name or root_id,
                    entity_type=change.entity_type or "APIEndpoint",
                    concepts=change.concepts,
                    metadata={"change_type": change.change_type, "severity": change.severity},
                )
            elif change.concepts:
                node.concepts = list(set(node.concepts + change.concepts))

            # Track maximum change severity
            if change.severity.upper() == "BLOCKING":
                max_severity = "BLOCKING"
            elif change.severity.upper() == "WARNING" and max_severity != "BLOCKING":
                max_severity = "WARNING"

        # ---------------------------------------------------------------------
        # 2. Resolve ontology concepts for directly changed entities
        # ---------------------------------------------------------------------
        active_concepts: set[str] = set()
        for root_id in root_entity_ids:
            root_node = self.graph.get_node(root_id)
            if root_node:
                active_concepts.update(root_node.concepts)
                # Check outgoing MAPS_TO edges
                for edge in self.graph.get_dependencies(root_id):
                    if edge.relationship_type in {"MAPS_TO", "TRANSFORMS_INTO"}:
                        active_concepts.add(edge.target_id)

        # ---------------------------------------------------------------------
        # 3, 4, 5, 6, 9 & 10. Traversal (Direct, Transitive, Runtime, Cycles, Paths)
        # ---------------------------------------------------------------------
        impacted_entities_map: dict[str, ImpactedEntity] = {}
        all_impact_paths: list[ImpactPath] = []
        all_evidence_refs: set[str] = set()

        dispute_count = 0
        uncertified_candidates_count = 0
        has_conflicts = False

        for root_id in root_entity_ids:
            root_node = self.graph.get_node(root_id)
            root_name = root_node.name if root_node else root_id

            # BFS queue item: (current_node_id, current_hop, path_nodes, cumulative_confidence, path_edges)
            queue: deque[tuple[str, int, list[str], float, list[GraphEdge]]] = deque()

            # Find direct consumers of root
            direct_edges = self.graph.get_consumers(root_id, include_expired=False)
            for edge in direct_edges:
                consumer_id = edge.source_id
                if consumer_id != root_id:  # Avoid self-calls initially
                    queue.append(
                        (
                            consumer_id,
                            1,
                            [root_name, self._get_node_name(consumer_id)],
                            edge.confidence,
                            [edge],
                        )
                    )

            # Visited map tracks minimum hop distance to avoid cyclic infinite loops
            # and prune suboptimal longer paths to the same node
            visited_hops: dict[str, int] = {root_id: 0}

            while queue:
                current_id, hop, path_nodes, cum_conf, path_edges = queue.popleft()

                # Cyclic graph protection: If we've seen this node at a shorter or equal hop, skip
                if current_id in visited_hops and visited_hops[current_id] < hop:
                    continue
                visited_hops[current_id] = hop

                current_node = self.graph.get_node(current_id)
                current_name = current_node.name if current_node else current_id

                # Evaluate edge attributes along the path
                last_edge = path_edges[-1]
                has_runtime = any(e.is_observed for e in path_edges)
                max_call_count = max((e.call_count_7d for e in path_edges), default=0)
                max_p95 = max((e.p95_latency_ms for e in path_edges), default=0.0)

                # Collect citations
                for e in path_edges:
                    all_evidence_refs.update(e.evidence_refs)
                    if e.is_disputed:
                        has_conflicts = True
                        dispute_count += 1
                    if e.provenance == "ONTOLOGY_INFERRED" or e.confidence < 0.70:
                        uncertified_candidates_count += 1

                # Determine Impact Category
                if hop == 1:
                    category = ImpactCategory.RUNTIME_OBSERVED if has_runtime else ImpactCategory.DIRECT
                else:
                    category = ImpactCategory.RUNTIME_OBSERVED if has_runtime else ImpactCategory.TRANSITIVE

                # Construct ImpactPath
                path_obj = ImpactPath(
                    source_entity=root_id,
                    target_entity=current_id,
                    path_hops=path_nodes,
                    relationship_types=[e.relationship_type for e in path_edges],
                    cumulative_confidence=round(cum_conf, 4),
                    evidence_references=list(set(last_edge.evidence_refs)),
                    has_runtime_evidence=has_runtime,
                )
                all_impact_paths.append(path_obj)

                # Determine uncertainty reasons
                uncertainties: list[str] = []
                if last_edge.is_disputed:
                    uncertainties.append(f"Relationship {last_edge.id} has an unresolved semantic dispute.")
                if cum_conf < 0.75:
                    uncertainties.append(f"Cumulative path confidence is low ({cum_conf:.2f}).")
                if not has_runtime and hop > 2:
                    uncertainties.append("Transitive path unconfirmed by live runtime telemetry.")

                # Record or merge ImpactedEntity
                tier = current_node.tier if current_node else ServiceTier.TIER_2
                exposure = current_node.exposure if current_node else ExposureLevel.INTERNAL_SERVICE
                owner = current_node.owner if current_node else None
                permissions = current_node.permissions if current_node else []
                node_concepts = current_node.concepts if current_node else []
                entity_type = current_node.entity_type if current_node else "Service"

                if current_id in impacted_entities_map:
                    # Update with shorter hop or higher confidence if found
                    existing = impacted_entities_map[current_id]
                    if hop < existing.hop_distance:
                        existing.hop_distance = hop
                        existing.impact_category = category
                        existing.path = path_nodes
                    existing.path_confidence = max(existing.path_confidence, cum_conf)
                    existing.is_runtime_confirmed = existing.is_runtime_confirmed or has_runtime
                    existing.call_frequency_7d = max(existing.call_frequency_7d, max_call_count)
                    existing.p95_latency_ms = max(existing.p95_latency_ms, max_p95)
                    existing.evidence_citations = list(set(existing.evidence_citations + last_edge.evidence_refs))
                    existing.uncertainty_reasons = list(set(existing.uncertainty_reasons + uncertainties))
                else:
                    impacted_entities_map[current_id] = ImpactedEntity(
                        entity_id=current_id,
                        entity_name=current_name,
                        entity_type=entity_type,
                        impact_category=category,
                        hop_distance=hop,
                        path=path_nodes,
                        path_confidence=round(cum_conf, 4),
                        is_runtime_confirmed=has_runtime,
                        call_frequency_7d=max_call_count,
                        p95_latency_ms=max_p95,
                        service_tier=tier,
                        exposure=exposure,
                        owner=owner,
                        required_permissions=permissions,
                        ontology_concepts=node_concepts,
                        evidence_citations=list(set(last_edge.evidence_refs)),
                        uncertainty_reasons=uncertainties,
                    )

                # Downstream traversal up to max_traversal_depth
                if hop < self.max_traversal_depth:
                    # Find consumers of the current node (cascading upward call stack)
                    next_consumers = self.graph.get_consumers(current_id, include_expired=False)
                    for next_edge in next_consumers:
                        next_consumer_id = next_edge.source_id
                        # Cycle check: Do not loop back to any node already visited in this branch
                        if next_consumer_id not in path_nodes:
                            queue.append(
                                (
                                    next_consumer_id,
                                    hop + 1,
                                    path_nodes + [self._get_node_name(next_consumer_id)],
                                    cum_conf * next_edge.confidence,
                                    path_edges + [next_edge],
                                )
                            )

        # ---------------------------------------------------------------------
        # 7. Detect Semantic Mappings & Concept Shifts
        # ---------------------------------------------------------------------
        for concept_urn in active_concepts:
            # Find sibling or concept-mapped nodes that depend on or consume this concept
            concept_nodes = self.graph.get_nodes_by_concept(concept_urn)
            for c_node in concept_nodes:
                if c_node.id not in root_entity_ids and c_node.id not in impacted_entities_map:
                    # Semantic impact identified
                    impacted_entities_map[c_node.id] = ImpactedEntity(
                        entity_id=c_node.id,
                        entity_name=c_node.name,
                        entity_type=c_node.entity_type,
                        impact_category=ImpactCategory.SEMANTIC,
                        hop_distance=1,
                        path=[f"Concept({concept_urn})", c_node.name],
                        path_confidence=0.90,
                        is_runtime_confirmed=False,
                        service_tier=c_node.tier,
                        exposure=c_node.exposure,
                        owner=c_node.owner,
                        ontology_concepts=[concept_urn],
                        evidence_citations=[f"Mapped to altered concept {concept_urn}"],
                        uncertainty_reasons=[],
                    )

        # ---------------------------------------------------------------------
        # 8. Identify Affected Workflows
        # ---------------------------------------------------------------------
        affected_workflows: set[str] = set()
        for root_id in root_entity_ids:
            for wf in self.graph.get_workflows_for_entity(root_id):
                affected_workflows.add(wf)

        for ent_id in list(impacted_entities_map.keys()):
            for wf in self.graph.get_workflows_for_entity(ent_id):
                affected_workflows.add(wf)

        # Add workflow entities to impacted list
        for wf_id in sorted(affected_workflows):
            if wf_id not in impacted_entities_map:
                wf_node = self.graph.get_node(wf_id)
                impacted_entities_map[wf_id] = ImpactedEntity(
                    entity_id=wf_id,
                    entity_name=wf_node.name if wf_node else wf_id,
                    entity_type="Workflow",
                    impact_category=ImpactCategory.WORKFLOW,
                    hop_distance=1,
                    path=[f"Workflow:{wf_id}"],
                    path_confidence=1.0,
                    is_runtime_confirmed=False,
                    service_tier=ServiceTier.TIER_1,
                    exposure=ExposureLevel.INTERNAL_SERVICE,
                    ontology_concepts=[wf_id],
                    evidence_citations=["Workflow includes impacted constituents"],
                    uncertainty_reasons=[],
                )

        # ---------------------------------------------------------------------
        # Metrics and Counts
        # ---------------------------------------------------------------------
        affected_entities = list(impacted_entities_map.values())
        impacted_services_count = sum(1 for e in affected_entities if e.entity_type == "Service")
        impacted_endpoints_count = sum(1 for e in affected_entities if e.entity_type in {"APIEndpoint", "Endpoint"})

        # Confidence & Uncertainty calculations
        if affected_entities:
            overall_confidence = round(sum(e.path_confidence for e in affected_entities) / len(affected_entities), 3)
            uncertain_entities_count = sum(1 for e in affected_entities if e.uncertainty_reasons)
            overall_uncertainty = round(uncertain_entities_count / len(affected_entities), 3)
        else:
            overall_confidence = 1.0
            overall_uncertainty = 0.0

        # ---------------------------------------------------------------------
        # Deterministic Risk Calculation (Separate from Impact Breadth)
        # ---------------------------------------------------------------------
        risk_score, risk_level, recommended_action, risk_breakdown = RiskCalculator.calculate_risk(
            max_severity=max_severity,
            impacted_entities=affected_entities,
            affected_workflows=sorted(affected_workflows),
            has_conflicts=has_conflicts,
            dispute_count=dispute_count,
            uncertified_candidate_count=uncertified_candidates_count,
        )

        # ---------------------------------------------------------------------
        # Visualization Graph Nodes & Edges (@xyflow/react format)
        # ---------------------------------------------------------------------
        nodes, edges = self._build_visualization_graph(root_entity_ids, affected_entities, all_impact_paths)

        # Summary narrative
        narrative = (
            f"Evaluated ChangeSet {changeset.change_set_id}: {len(root_entity_ids)} root changes analyzed. "
            f"Impact identified across {len(affected_entities)} entities ({impacted_services_count} services, "
            f"{impacted_endpoints_count} endpoints, {len(affected_workflows)} workflows). "
            f"Deterministic risk assessed at {risk_score}/100 ({risk_level}). "
            f"Recommended Policy: {recommended_action.value}."
        )

        return ImpactReasoningResult(
            change_set_id=changeset.change_set_id,
            tenant_id=changeset.tenant_id,
            root_changed_entities=root_entity_ids,
            affected_entities=affected_entities,
            impacted_services_count=impacted_services_count,
            impacted_endpoints_count=impacted_endpoints_count,
            affected_workflows=sorted(affected_workflows),
            graph_paths=all_impact_paths,
            evidence_references=sorted(all_evidence_refs),
            overall_confidence=overall_confidence,
            overall_uncertainty=overall_uncertainty,
            risk_score=risk_score,
            risk_level=risk_level,
            risk_breakdown=risk_breakdown,
            recommended_action=recommended_action,
            nodes=nodes,
            edges=edges,
            summary_narrative=narrative,
            evaluated_at=datetime.now(UTC),
        )

    def _get_node_name(self, node_id: str) -> str:
        node = self.graph.get_node(node_id)
        return node.name if node else node_id

    def _build_visualization_graph(
        self,
        root_ids: list[str],
        impacted_entities: list[ImpactedEntity],
        paths: list[ImpactPath],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Generates standard React Flow nodes and edges for UI visualization."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        seen_nodes: set[str] = set()

        # Origin nodes
        for r_id in root_ids:
            node = self.graph.get_node(r_id)
            label = node.name if node else r_id
            nodes.append(
                {
                    "id": r_id,
                    "type": "originNode",
                    "data": {
                        "label": label,
                        "entity_type": node.entity_type if node else "Endpoint",
                        "is_origin": True,
                    },
                }
            )
            seen_nodes.add(r_id)

        # Impacted nodes
        for ent in impacted_entities:
            if ent.entity_id not in seen_nodes:
                nodes.append(
                    {
                        "id": ent.entity_id,
                        "type": "impactedNode",
                        "data": {
                            "label": ent.entity_name,
                            "tier": ent.service_tier.value
                            if hasattr(ent.service_tier, "value")
                            else str(ent.service_tier),
                            "category": ent.impact_category.value
                            if hasattr(ent.impact_category, "value")
                            else str(ent.impact_category),
                            "hop": ent.hop_distance,
                            "is_observed": ent.is_runtime_confirmed,
                            "rpm": ent.call_frequency_7d,
                            "confidence": ent.path_confidence,
                        },
                    }
                )
                seen_nodes.add(ent.entity_id)

        # Edges from shortest impact paths
        seen_edges: set[str] = set()
        for p in paths:
            hops = p.path_hops
            for i in range(len(hops) - 1):
                s_name = hops[i]
                t_name = hops[i + 1]
                edge_id = f"e-{s_name}->{t_name}"
                if edge_id not in seen_edges:
                    edges.append(
                        {
                            "id": edge_id,
                            "source": s_name,
                            "target": t_name,
                            "label": "Impact" if not p.has_runtime_evidence else "Runtime Observed",
                            "animated": p.has_runtime_evidence,
                        }
                    )
                    seen_edges.add(edge_id)

        return nodes, edges
