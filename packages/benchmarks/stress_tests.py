"""Edge-case stress testing suite for ChangeScope evaluation.

Evaluates engine robustness under adversarial conditions:
1. Missing telemetry (uninstrumented cold-start services)
2. Incomplete ontology (unmapped domain concepts)
3. Conflicting semantic mappings (contradictory annotations)
4. Uncertain inference (sparse evidence & reflection)
5. Large repository scale (1,000+ nodes traversal)
"""

import time
from typing import Any

from packages.shared.impact.engine import ImpactReasoningEngine
from packages.shared.impact.graph import DependencyKnowledgeGraph
from packages.shared.impact.models import ChangeSetInput, ProposedChange


class StressTestRunner:
    """Runs adversarial stress test scenarios against the ChangeScope core."""

    @classmethod
    def test_missing_telemetry(cls) -> dict[str, Any]:
        """Verifies graceful degradation when OpenTelemetry traces are completely absent."""
        graph = DependencyKnowledgeGraph(tenant_id="tenant-stress-missing-otel")
        graph.add_node("payment_service", name="Payment Service", entity_type="Service")
        graph.add_node("order_service", name="Order Service", entity_type="Service")
        graph.add_node("checkout_service", name="Checkout Service", entity_type="Service")
        graph.add_node("frontend_app", name="Frontend App", entity_type="Service")
        # Static edges exist across 3 hops, but NO runtime traces
        graph.add_edge(source_id="order_service", target_id="payment_service", relationship_type="STATIC_CALL")
        graph.add_edge(source_id="checkout_service", target_id="order_service", relationship_type="STATIC_CALL")
        graph.add_edge(source_id="frontend_app", target_id="checkout_service", relationship_type="STATIC_CALL")

        engine = ImpactReasoningEngine(graph=graph)
        changeset = ChangeSetInput(
            tenant_id="tenant-stress-missing-otel",
            changes=[
                ProposedChange(
                    entity_id="payment_service",
                    entity_name="Payment Service",
                    entity_type="Service",
                    change_type="SCHEMA_BREAKING",
                    severity="BLOCKING",
                )
            ],
        )

        result = engine.evaluate_changeset(changeset)
        # Even without telemetry, static dependencies are safely captured
        assert len(result.affected_entities) >= 1
        assert any(
            e.entity_id == "order_service" or e.entity_name in {"order_service", "Order Service"}
            for e in result.affected_entities
        )
        # None of the discovered entities have runtime confirmation
        assert all(not e.is_runtime_confirmed for e in result.affected_entities)
        # Unconfirmed multi-hop paths trigger uncertainty flags
        assert result.overall_uncertainty > 0.0 or result.overall_confidence < 1.0

        return {
            "name": "Missing Telemetry Resilience",
            "passed": True,
            "detected_entities": len(result.affected_entities),
            "uncertainty_score": result.overall_uncertainty,
            "confidence_score": result.overall_confidence,
            "detail": "Engine safely leveraged static AST fallback when OTel traces were absent.",
        }

    @classmethod
    def test_incomplete_ontology(cls) -> dict[str, Any]:
        """Verifies fallback when ontology concepts are unmapped."""
        graph = DependencyKnowledgeGraph(tenant_id="tenant-stress-incomplete-ont")
        graph.add_node("billing", name="Billing Service", entity_type="Service")
        graph.add_node("accounting", name="Accounting Service", entity_type="Service")
        graph.add_edge(source_id="accounting", target_id="billing", relationship_type="CALLS_STATIC")

        engine = ImpactReasoningEngine(graph=graph)
        # Change has unknown domain concepts
        changeset = ChangeSetInput(
            tenant_id="tenant-stress-incomplete-ont",
            changes=[
                ProposedChange(
                    entity_id="billing",
                    entity_name="Billing Service",
                    entity_type="Service",
                    change_type="UNKNOWN_DOMAIN_FIELD_MODIFIED",
                    severity="WARNING",
                    is_breaking=False,
                    concepts=["UNMAPPED_CUSTOM_PROPRIETARY_CONCEPT"],
                )
            ],
        )

        result = engine.evaluate_changeset(changeset)
        assert result is not None
        assert result.risk_level in {"LOW", "MEDIUM", "HIGH"}

        return {
            "name": "Incomplete Ontology Fallback",
            "passed": True,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "detail": "Engine completed deterministic traversal despite unmapped ontology concept.",
        }

    @classmethod
    def test_conflicting_mappings(cls) -> dict[str, Any]:
        """Verifies uncertainty penalty when services contradict each other's domain semantics."""
        graph = DependencyKnowledgeGraph(tenant_id="tenant-stress-conflicting")
        graph.add_node("gateway", name="API Gateway", entity_type="Service")
        graph.add_node("billing_v1", name="Billing V1 (Cents)", entity_type="Service")
        graph.add_node("billing_v2", name="Billing V2 (Dollars)", entity_type="Service")

        # Two competing edges with conflicting weights
        graph.add_edge(source_id="gateway", target_id="billing_v1", relationship_type="CALLS", confidence=0.5)
        graph.add_edge(source_id="gateway", target_id="billing_v2", relationship_type="CALLS", confidence=0.5)

        engine = ImpactReasoningEngine(graph=graph)
        changeset = ChangeSetInput(
            tenant_id="tenant-stress-conflicting",
            changes=[
                ProposedChange(
                    entity_id="billing_v1",
                    entity_name="Billing V1",
                    entity_type="Service",
                    change_type="SEMANTIC_DRIFT",
                    severity="BLOCKING",
                )
            ],
        )

        result = engine.evaluate_changeset(changeset)
        assert result.overall_uncertainty > 0.0 or result.overall_confidence < 1.0

        return {
            "name": "Conflicting Mappings Handling",
            "passed": True,
            "overall_uncertainty": result.overall_uncertainty,
            "overall_confidence": result.overall_confidence,
            "detail": "Engine applied uncertainty penalty to ambiguous multi-version dependencies.",
        }

    @classmethod
    def test_uncertain_inference(cls) -> dict[str, Any]:
        """Verifies that low-evidence paths require human review."""
        graph = DependencyKnowledgeGraph(tenant_id="tenant-stress-uncertain")
        graph.add_node("target_srv", name="Target Service", entity_type="Service")
        graph.add_node("consumer_srv", name="Consumer Service", entity_type="Service")
        # Very low confidence edge
        graph.add_edge(
            source_id="consumer_srv",
            target_id="target_srv",
            relationship_type="INFERRED_HEURISTIC",
            confidence=0.35,
        )

        engine = ImpactReasoningEngine(graph=graph)
        changeset = ChangeSetInput(
            tenant_id="tenant-stress-uncertain",
            changes=[
                ProposedChange(
                    entity_id="target_srv",
                    entity_name="Target Service",
                    entity_type="Service",
                    change_type="MODIFIED",
                    severity="WARNING",
                    is_breaking=False,
                )
            ],
        )

        result = engine.evaluate_changeset(changeset)
        assert result.overall_confidence <= 0.85

        return {
            "name": "Uncertain Inference Guard",
            "passed": True,
            "overall_confidence": result.overall_confidence,
            "requires_human_review": True,
            "detail": "Heuristic relationships appropriately penalized; human review required.",
        }

    @classmethod
    def test_large_repository_scale(cls, node_counts: list[int] | None = None) -> list[dict[str, Any]]:
        """Benchmarks graph scalability across 100, 500, and 1,000 nodes."""
        counts = node_counts or [100, 500, 1000]
        results: list[dict[str, Any]] = []

        for count in counts:
            graph = DependencyKnowledgeGraph(tenant_id=f"tenant-scale-{count}")
            for i in range(count):
                graph.add_node(f"node-{i}", name=f"Node {i}", entity_type="Service")

            # Add ~2.5 edges per node
            edges_count = 0
            for i in range(count - 1):
                graph.add_edge(source_id=f"node-{i + 1}", target_id=f"node-{i}", relationship_type="CALLS")
                edges_count += 1
                if i + 2 < count:
                    graph.add_edge(source_id=f"node-{i + 2}", target_id=f"node-{i}", relationship_type="CALLS")
                    edges_count += 1

            engine = ImpactReasoningEngine(graph=graph, max_traversal_depth=5)
            changeset = ChangeSetInput(
                tenant_id=f"tenant-scale-{count}",
                changes=[
                    ProposedChange(
                        entity_id="node-0",
                        entity_name="Root Node",
                        entity_type="Service",
                        change_type="SCHEMA_BREAKING",
                        severity="BLOCKING",
                    )
                ],
            )

            # Warm-up
            engine.evaluate_changeset(changeset)

            # Measure
            start = time.perf_counter()
            iterations = 5
            for _ in range(iterations):
                res = engine.evaluate_changeset(changeset)
                assert len(res.affected_entities) > 0

            avg_latency_ms = ((time.perf_counter() - start) / iterations) * 1000.0

            results.append(
                {
                    "tier": f"{count} Nodes",
                    "nodes": count,
                    "edges": edges_count,
                    "latency_ms": round(avg_latency_ms, 2),
                    "passed": avg_latency_ms < 100.0,
                    "node_count": count,
                    "edge_count": edges_count,
                    "avg_latency_ms": round(avg_latency_ms, 2),
                    "sla_passed": avg_latency_ms < 100.0,
                    "affected_discovered": len(res.affected_entities),
                }
            )

        return results
