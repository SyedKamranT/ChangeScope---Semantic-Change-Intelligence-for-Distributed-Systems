"""Unit tests for ChangeScope Deterministic Impact Reasoning Engine."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.shared.impact.engine import ImpactReasoningEngine
from packages.shared.impact.graph import DependencyKnowledgeGraph
from packages.shared.impact.models import (
    ChangeSetInput,
    ExposureLevel,
    ImpactCategory,
    ProposedChange,
    RecommendedAction,
    ServiceTier,
)


def test_cyclic_graph_termination_and_path_discovery():
    """Verifies that cyclic dependency graphs (A -> B -> C -> A) terminate safely without infinite loops."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-cyclic")

    # Cycle: srv-a -> srv-b -> srv-c -> srv-a
    # Additional branch: srv-c -> srv-d
    graph.add_node("srv-a", name="Service A", entity_type="Service", tier=ServiceTier.TIER_1)
    graph.add_node("srv-b", name="Service B", entity_type="Service", tier=ServiceTier.TIER_2)
    graph.add_node("srv-c", name="Service C", entity_type="Service", tier=ServiceTier.TIER_2)
    graph.add_node("srv-d", name="Service D", entity_type="Service", tier=ServiceTier.TIER_3)

    # Consumers: B calls A, C calls B, A calls C (Cycle), D calls C
    graph.add_edge(source_id="srv-b", target_id="srv-a", relationship_type="CALLS", confidence=1.0)
    graph.add_edge(source_id="srv-c", target_id="srv-b", relationship_type="CALLS", confidence=1.0)
    graph.add_edge(source_id="srv-a", target_id="srv-c", relationship_type="CALLS", confidence=1.0)
    graph.add_edge(source_id="srv-d", target_id="srv-c", relationship_type="CALLS", confidence=1.0)

    engine = ImpactReasoningEngine(graph=graph, max_traversal_depth=5)
    changeset = ChangeSetInput(
        tenant_id="tenant-cyclic",
        changes=[
            ProposedChange(
                entity_id="srv-a",
                entity_name="Service A",
                entity_type="Service",
                change_type="INTERFACE_BREAKING",
                severity="BLOCKING",
            )
        ],
    )

    result = engine.evaluate_changeset(changeset)

    # Must terminate and identify consumers
    impacted_ids = {e.entity_id for e in result.affected_entities}
    assert "srv-b" in impacted_ids  # Direct consumer of A
    assert "srv-c" in impacted_ids  # 2-hop consumer of A
    assert "srv-d" in impacted_ids  # 3-hop consumer of A

    # Verify hop distances
    by_id = {e.entity_id: e for e in result.affected_entities}
    assert by_id["srv-b"].hop_distance == 1
    assert by_id["srv-c"].hop_distance == 2
    assert by_id["srv-d"].hop_distance == 3

    assert result.risk_score >= 50
    assert result.risk_breakdown.formula_explanation is not None


def test_multi_hop_dependencies_and_confidence_decay():
    """Verifies 5-hop linear dependency cascade with cumulative confidence decay."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-multihop")

    # S1 -> S2 -> S3 -> S4 -> S5 (S5 is root provider, S4 calls S5, S3 calls S4, ...)
    services = [f"svc-{i}" for i in range(1, 6)]
    for s in services:
        graph.add_node(s, name=s.upper(), entity_type="Service")

    # Add edges with confidence 0.90
    for i in range(4, 0, -1):
        caller = f"svc-{i}"
        callee = f"svc-{i + 1}"
        graph.add_edge(
            source_id=caller,
            target_id=callee,
            relationship_type="CALLS",
            confidence=0.90,
            evidence_refs=[f"static-call-{caller}->{callee}"],
        )

    engine = ImpactReasoningEngine(graph=graph, max_traversal_depth=5)
    changeset = ChangeSetInput(
        tenant_id="tenant-multihop",
        changes=[
            ProposedChange(
                entity_id="svc-5",
                entity_name="SVC-5",
                entity_type="Service",
                change_type="METHOD_REMOVED",
                severity="BLOCKING",
            )
        ],
    )

    result = engine.evaluate_changeset(changeset)
    assert result.impacted_services_count == 4

    by_id = {e.entity_id: e for e in result.affected_entities}
    assert by_id["svc-4"].hop_distance == 1
    assert by_id["svc-4"].impact_category == ImpactCategory.DIRECT
    assert pytest.approx(by_id["svc-4"].path_confidence, 0.01) == 0.90

    assert by_id["svc-3"].hop_distance == 2
    assert by_id["svc-3"].impact_category == ImpactCategory.TRANSITIVE
    assert pytest.approx(by_id["svc-3"].path_confidence, 0.01) == 0.81

    assert by_id["svc-2"].hop_distance == 3
    assert by_id["svc-2"].impact_category == ImpactCategory.TRANSITIVE
    assert pytest.approx(by_id["svc-2"].path_confidence, 0.01) == 0.729

    assert by_id["svc-1"].hop_distance == 4
    assert by_id["svc-1"].impact_category == ImpactCategory.TRANSITIVE
    assert pytest.approx(by_id["svc-1"].path_confidence, 0.01) == 0.656


def test_duplicate_edges_deduplication():
    """Verifies that multiple edges between the same endpoints are merged cleanly."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-dedup")

    # Add caller and callee
    graph.add_node("checkout-service", name="Checkout", entity_type="Service")
    graph.add_node("payment-service", name="Payment", entity_type="Service")

    # Add duplicate edges with different protocols/counts
    graph.add_edge(
        source_id="checkout-service",
        target_id="payment-service",
        relationship_type="CALLS",
        confidence=0.85,
        is_observed=False,
        call_count_7d=100,
        evidence_refs=["ast-call-1"],
    )
    # Merged duplicate edge
    graph.add_edge(
        source_id="checkout-service",
        target_id="payment-service",
        relationship_type="CALLS",
        confidence=0.98,
        is_observed=True,
        call_count_7d=500,
        evidence_refs=["ast-call-2", "trace-ex-1"],
    )

    consumers = graph.get_consumers("payment-service")
    assert len(consumers) == 1
    edge = consumers[0]
    assert edge.confidence == 0.98
    assert edge.is_observed is True
    assert edge.call_count_7d == 600
    assert set(edge.evidence_refs) == {"ast-call-1", "ast-call-2", "trace-ex-1"}

    engine = ImpactReasoningEngine(graph=graph)
    changeset = ChangeSetInput(
        tenant_id="tenant-dedup",
        changes=[ProposedChange(entity_id="payment-service", entity_name="Payment", entity_type="Service")],
    )
    result = engine.evaluate_changeset(changeset)
    assert len(result.affected_entities) == 1
    assert result.affected_entities[0].entity_id == "checkout-service"
    assert result.affected_entities[0].call_frequency_7d == 600


def test_missing_relationships_graceful_handling():
    """Verifies that isolated or disconnected nodes are handled cleanly without exceptions."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-isolated")
    graph.add_node("island-service", name="Island", entity_type="Service")

    engine = ImpactReasoningEngine(graph=graph)
    changeset = ChangeSetInput(
        tenant_id="tenant-isolated",
        changes=[
            ProposedChange(
                entity_id="island-service",
                entity_name="Island",
                entity_type="Service",
                change_type="INTERNAL_REFACTOR",
                severity="INFO",
                is_breaking=False,
            )
        ],
    )
    result = engine.evaluate_changeset(changeset)

    assert result.impacted_services_count == 0
    assert len(result.affected_entities) == 0
    assert result.risk_score <= 10
    assert result.risk_level == "LOW"
    assert result.recommended_action == RecommendedAction.PROCEED_WITH_MONITORING


def test_conflicting_evidence_and_ontology_disputes():
    """Verifies that unresolved ontology disputes incur an uncertainty penalty in risk calculation."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-disputed")

    graph.add_node("order-service", name="Order", entity_type="Service")
    graph.add_node("inventory-service", name="Inventory", entity_type="Service")

    # Edge marked as disputed
    graph.add_edge(
        source_id="order-service",
        target_id="inventory-service",
        relationship_type="CALLS",
        confidence=0.60,
        is_disputed=True,
        evidence_refs=["disputed-spec-ref"],
    )

    engine = ImpactReasoningEngine(graph=graph)
    changeset = ChangeSetInput(
        tenant_id="tenant-disputed",
        changes=[
            ProposedChange(
                entity_id="inventory-service",
                entity_name="Inventory",
                entity_type="Service",
                severity="WARNING",
            )
        ],
    )

    result = engine.evaluate_changeset(changeset)

    assert len(result.affected_entities) == 1
    ent = result.affected_entities[0]
    assert len(ent.uncertainty_reasons) > 0
    assert any("dispute" in r.lower() for r in ent.uncertainty_reasons)

    # Uncertainty penalty must be applied
    assert result.risk_breakdown.uncertainty_penalty > 0.0
    assert result.overall_uncertainty > 0.0
    assert "Uncertainty Penalty" in result.risk_breakdown.formula_explanation


def test_expired_relationships_exclusion():
    """Verifies that expired relationships (valid_to in the past) are omitted from active impact paths."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-expired")
    now = datetime.now(UTC)

    graph.add_node("legacy-client", name="Legacy Client", entity_type="Service")
    graph.add_node("active-client", name="Active Client", entity_type="Service")
    graph.add_node("auth-service", name="Auth Service", entity_type="Service")

    # Expired relationship: legacy-client called auth-service until last month
    graph.add_edge(
        source_id="legacy-client",
        target_id="auth-service",
        relationship_type="CALLS",
        valid_from=now - timedelta(days=90),
        valid_to=now - timedelta(days=30),  # Expired 30 days ago
    )

    # Active relationship: active-client calls auth-service
    graph.add_edge(
        source_id="active-client",
        target_id="auth-service",
        relationship_type="CALLS",
        valid_from=now - timedelta(days=30),
        valid_to=None,  # Active indefinitely
    )

    engine = ImpactReasoningEngine(graph=graph)
    changeset = ChangeSetInput(
        tenant_id="tenant-expired",
        changes=[ProposedChange(entity_id="auth-service", entity_name="Auth Service", entity_type="Service")],
    )

    result = engine.evaluate_changeset(changeset)
    impacted_ids = {e.entity_id for e in result.affected_entities}

    assert "active-client" in impacted_ids
    assert "legacy-client" not in impacted_ids  # Must be excluded due to expiration


def test_tenant_isolation_boundary():
    """Verifies strict tenant isolation where queries never traverse disparate tenants' graphs."""
    graph_a = DependencyKnowledgeGraph(tenant_id="tenant-alpha")
    graph_b = DependencyKnowledgeGraph(tenant_id="tenant-beta")

    graph_a.add_node("shared-service-name", name="Alpha Service", entity_type="Service")
    graph_a.add_edge(source_id="alpha-consumer", target_id="shared-service-name")

    graph_b.add_node("shared-service-name", name="Beta Service", entity_type="Service")
    graph_b.add_edge(source_id="beta-consumer", target_id="shared-service-name")

    engine_a = ImpactReasoningEngine(graph=graph_a)
    changeset_a = ChangeSetInput(
        tenant_id="tenant-alpha",
        changes=[ProposedChange(entity_id="shared-service-name", entity_name="Alpha Service", entity_type="Service")],
    )

    result_a = engine_a.evaluate_changeset(changeset_a)
    impacted_a = {e.entity_id for e in result_a.affected_entities}

    assert "alpha-consumer" in impacted_a
    assert "beta-consumer" not in impacted_a  # Zero tenant leakage


def test_workflow_impact_detection():
    """Verifies that changes affecting constituents of a business workflow tag the workflow."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-wf")

    graph.add_node("order-service", name="Order Service", entity_type="Service")
    graph.add_node("payment-service", name="Payment Service", entity_type="Service")
    graph.add_node("workflow:checkout_to_ship", name="Checkout to Ship Flow", entity_type="Workflow")

    # Payment is called by Order
    graph.add_edge(source_id="order-service", target_id="payment-service", relationship_type="CALLS")
    # Payment and Order participate in workflow:checkout_to_ship
    graph.add_edge(
        source_id="payment-service", target_id="workflow:checkout_to_ship", relationship_type="PART_OF_WORKFLOW"
    )
    graph.add_edge(
        source_id="order-service", target_id="workflow:checkout_to_ship", relationship_type="PART_OF_WORKFLOW"
    )

    engine = ImpactReasoningEngine(graph=graph)
    changeset = ChangeSetInput(
        tenant_id="tenant-wf",
        changes=[ProposedChange(entity_id="payment-service", entity_name="Payment Service", entity_type="Service")],
    )

    result = engine.evaluate_changeset(changeset)
    assert "workflow:checkout_to_ship" in result.affected_workflows
    wf_entities = [e for e in result.affected_entities if e.impact_category == ImpactCategory.WORKFLOW]
    assert len(wf_entities) == 1
    assert wf_entities[0].entity_id == "workflow:checkout_to_ship"


def test_semantic_concept_shift_detection():
    """Verifies impact propagation to entities mapped to common domain concepts (e.g. monetary value)."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-sem")

    # Two fields in different services mapped to the same concept URN
    concept_urn = "urn:concept:monetary_value"
    graph.add_node(
        "field:order.total_amount", name="Order Total Amount", entity_type="APIField", concepts=[concept_urn]
    )
    graph.add_node("field:invoice.subtotal", name="Invoice Subtotal", entity_type="APIField", concepts=[concept_urn])

    engine = ImpactReasoningEngine(graph=graph)
    changeset = ChangeSetInput(
        tenant_id="tenant-sem",
        changes=[
            ProposedChange(
                entity_id="field:order.total_amount",
                entity_name="Order Total Amount",
                entity_type="APIField",
                change_type="UNIT_SHIFT",
                concepts=[concept_urn],
            )
        ],
    )

    result = engine.evaluate_changeset(changeset)
    semantic_entities = [e for e in result.affected_entities if e.impact_category == ImpactCategory.SEMANTIC]
    assert len(semantic_entities) == 1
    assert semantic_entities[0].entity_id == "field:invoice.subtotal"
    assert concept_urn in semantic_entities[0].ontology_concepts


def test_separation_of_impact_breadth_and_risk_significance():
    """Enforces rule: Impact describes what may be affected; Risk estimates significance of possible failure."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-sep")

    # Scenario A: High Impact Breadth (5 low-tier consumers), but INFO safe change
    for i in range(5):
        s_id = f"analytics-worker-{i}"
        graph.add_node(s_id, name=s_id, entity_type="Service", tier=ServiceTier.TIER_3)
        graph.add_edge(source_id=s_id, target_id="metrics-endpoint", relationship_type="CALLS", call_count_7d=10)

    engine = ImpactReasoningEngine(graph=graph)
    changeset_a = ChangeSetInput(
        tenant_id="tenant-sep",
        changes=[
            ProposedChange(
                entity_id="metrics-endpoint",
                entity_name="Metrics Endpoint",
                entity_type="APIEndpoint",
                change_type="FIELD_ADDED_OPTIONAL",
                severity="INFO",
                is_breaking=False,
            )
        ],
    )
    result_a = engine.evaluate_changeset(changeset_a)
    # Impact count is 5, but risk remains LOW/MEDIUM
    assert len(result_a.affected_entities) == 5
    assert result_a.risk_score < 40
    assert result_a.risk_level in {"LOW", "MEDIUM"}
    assert result_a.recommended_action in {
        RecommendedAction.PROCEED_WITH_MONITORING,
        RecommendedAction.RUN_CANARY_TESTS,
    }

    # Scenario B: Low Impact Breadth (1 consumer), but BLOCKING breaking change on TIER_1 checkout
    graph_b = DependencyKnowledgeGraph(tenant_id="tenant-sep-b")
    graph_b.add_node(
        "checkout-web",
        name="Checkout Web",
        entity_type="Service",
        tier=ServiceTier.TIER_1,
        exposure=ExposureLevel.PUBLIC_INTERNET,
    )
    graph_b.add_edge(
        source_id="checkout-web",
        target_id="charge-endpoint",
        relationship_type="CALLS",
        call_count_7d=10000,
        is_observed=True,
    )

    engine_b = ImpactReasoningEngine(graph=graph_b)
    changeset_b = ChangeSetInput(
        tenant_id="tenant-sep-b",
        changes=[
            ProposedChange(
                entity_id="charge-endpoint",
                entity_name="Charge Endpoint",
                entity_type="APIEndpoint",
                change_type="ENDPOINT_REMOVED",
                severity="BLOCKING",
                is_breaking=True,
            )
        ],
    )
    result_b = engine_b.evaluate_changeset(changeset_b)
    # Impact count is only 1, but risk is CRITICAL (>= 80)
    assert len(result_b.affected_entities) == 1
    assert result_b.risk_score >= 80
    assert result_b.risk_level == "CRITICAL"
    assert result_b.recommended_action == RecommendedAction.BLOCK_MERGE
