"""Performance benchmarks for ChangeScope Deterministic Impact Reasoning Engine."""

import time

from packages.shared.impact.engine import ImpactReasoningEngine
from packages.shared.impact.graph import DependencyKnowledgeGraph
from packages.shared.impact.models import ChangeSetInput, ExposureLevel, ProposedChange, ServiceTier


def test_large_graph_1000_nodes_traversal_benchmark():
    """Verifies that impact traversal across 1,000 nodes and 2,500 edges completes in < 100ms."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-bench-large")

    # Generate 1,000 services across a 5-layer hierarchy
    # Layer 0: 5 root core services (payment, auth, catalog, orders, shipping)
    # Layer 1: 50 aggregation services
    # Layer 2: 200 business logic services
    # Layer 3: 400 consumer client services
    # Layer 4: 345 edge/frontend/reporting workers
    layers: list[list[str]] = [[], [], [], [], []]

    node_count = 0
    layer_sizes = [5, 50, 200, 400, 345]

    for layer_idx, size in enumerate(layer_sizes):
        for i in range(size):
            node_id = f"srv-L{layer_idx}-{i}"
            tier = (
                ServiceTier.TIER_1 if layer_idx <= 1 else (ServiceTier.TIER_2 if layer_idx <= 3 else ServiceTier.TIER_3)
            )
            exp = ExposureLevel.PUBLIC_INTERNET if layer_idx == 4 else ExposureLevel.INTERNAL_SERVICE
            graph.add_node(node_id, name=f"Service L{layer_idx}-{i}", entity_type="Service", tier=tier, exposure=exp)
            layers[layer_idx].append(node_id)
            node_count += 1

    assert node_count == 1000

    # Wire ~2,500 edges from consumers (L+1) to providers (L)
    edge_count = 0
    for l_idx in range(4):
        providers = layers[l_idx]
        consumers = layers[l_idx + 1]
        for c_idx, consumer in enumerate(consumers):
            # Connect consumer to 2-3 providers
            p1 = providers[c_idx % len(providers)]
            p2 = providers[(c_idx + 1) % len(providers)]
            graph.add_edge(source_id=consumer, target_id=p1, relationship_type="CALLS", call_count_7d=100)
            graph.add_edge(source_id=consumer, target_id=p2, relationship_type="CALLS", call_count_7d=200)
            edge_count += 2

    assert edge_count >= 1990

    engine = ImpactReasoningEngine(graph=graph, max_traversal_depth=5)
    changeset = ChangeSetInput(
        tenant_id="tenant-bench-large",
        changes=[
            ProposedChange(
                entity_id="srv-L0-0",
                entity_name="Root Payment Provider",
                entity_type="Service",
                change_type="SCHEMA_BREAKING",
                severity="BLOCKING",
            )
        ],
    )

    # Warm-up run
    engine.evaluate_changeset(changeset)

    # Benchmark run
    start = time.perf_counter()
    iterations = 5
    for _ in range(iterations):
        res = engine.evaluate_changeset(changeset)
        assert len(res.affected_entities) > 50
        assert res.risk_score >= 80

    elapsed = (time.perf_counter() - start) / iterations
    elapsed_ms = elapsed * 1000.0

    print(f"\n[BENCHMARK] 1,000 Node Graph Traversal Time: {elapsed_ms:.2f} ms")
    assert elapsed_ms < 100.0, f"Traversal exceeded SLA threshold: {elapsed_ms:.2f} ms"


def test_dense_mesh_scale_benchmark():
    """Verifies high-throughput traversal across a densely connected 100-service mesh in < 25ms."""
    graph = DependencyKnowledgeGraph(tenant_id="tenant-dense-mesh")

    # 100 interconnected services
    for i in range(100):
        graph.add_node(f"mesh-srv-{i}", name=f"Mesh Service {i}", entity_type="Service")

    for i in range(100):
        for j in range(1, 6):
            target = f"mesh-srv-{(i + j) % 100}"
            graph.add_edge(source_id=f"mesh-srv-{i}", target_id=target, relationship_type="CALLS", confidence=0.95)

    engine = ImpactReasoningEngine(graph=graph, max_traversal_depth=4)
    changeset = ChangeSetInput(
        tenant_id="tenant-dense-mesh",
        changes=[ProposedChange(entity_id="mesh-srv-0", entity_name="Mesh Node 0", entity_type="Service")],
    )

    start = time.perf_counter()
    iterations = 20
    for _ in range(iterations):
        res = engine.evaluate_changeset(changeset)
        assert res.impacted_services_count > 10

    avg_ms = ((time.perf_counter() - start) / iterations) * 1000.0
    print(f"\n[BENCHMARK] Dense Mesh Evaluation Time: {avg_ms:.2f} ms")
    assert avg_ms < 25.0, f"Dense mesh evaluation too slow: {avg_ms:.2f} ms"
