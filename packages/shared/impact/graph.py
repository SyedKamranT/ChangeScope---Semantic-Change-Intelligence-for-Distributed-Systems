"""In-Memory Multi-Layer Knowledge Graph for Deterministic Impact Traversal."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from packages.shared.impact.models import ExposureLevel, ServiceTier


@dataclass
class GraphNode:
    """Represents a discrete entity node within the multi-layer dependency graph."""

    id: str
    name: str
    entity_type: str  # Service, APIEndpoint, APIField, Event, DatabaseTable, Workflow, etc.
    tenant_id: str
    tier: ServiceTier = ServiceTier.TIER_2
    exposure: ExposureLevel = ExposureLevel.INTERNAL_SERVICE
    owner: str | None = None
    permissions: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Represents a directed relationship between two entities."""

    id: str = field(default_factory=lambda: f"edge-{uuid.uuid4().hex[:10]}")
    source_id: str = ""  # The dependent / consumer / caller / subscriber
    target_id: str = ""  # The dependency / callee / provider / publisher
    relationship_type: str = "CALLS"  # CALLS, SUBSCRIBES_TO, READS, MAPS_TO, PART_OF_WORKFLOW, etc.
    confidence: float = 1.0
    provenance: str = "STATIC_CONFIRMED"  # STATIC_CONFIRMED, RUNTIME_OBSERVED, etc.
    is_observed: bool = False
    call_count_7d: int = 0
    p95_latency_ms: float = 0.0
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    evidence_refs: list[str] = field(default_factory=list)
    is_disputed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, at_time: datetime | None = None) -> bool:
        """Determines whether this relationship is expired based on valid_to."""
        check_time = at_time or datetime.now(UTC)
        if self.valid_to is not None:
            # Handle timezone awareness safely
            val_to = self.valid_to if self.valid_to.tzinfo else self.valid_to.replace(tzinfo=UTC)
            chk = check_time if check_time.tzinfo else check_time.replace(tzinfo=UTC)
            return val_to < chk
        return False


class DependencyKnowledgeGraph:
    """Multi-layer in-memory directed graph supporting tenant-isolated traversals."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.nodes: dict[str, GraphNode] = {}
        # Adjacency indexes
        # incoming_edges[target_id] = list of edges where edge.target_id == target_id (Consumers of target)
        self.incoming_edges: dict[str, list[GraphEdge]] = {}
        # outgoing_edges[source_id] = list of edges where edge.source_id == source_id (Dependencies of source)
        self.outgoing_edges: dict[str, list[GraphEdge]] = {}
        # Fast edge deduplication lookup: (source_id, target_id, relationship_type) -> GraphEdge
        self._edge_index: dict[tuple[str, str, str], GraphEdge] = {}

    def add_node(
        self,
        node_id: str,
        name: str,
        entity_type: str,
        tier: ServiceTier = ServiceTier.TIER_2,
        exposure: ExposureLevel = ExposureLevel.INTERNAL_SERVICE,
        owner: str | None = None,
        permissions: list[str] | None = None,
        concepts: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        """Adds or updates a node in the graph."""
        if node_id in self.nodes:
            existing = self.nodes[node_id]
            existing.name = name or existing.name
            existing.entity_type = entity_type or existing.entity_type
            if tier != ServiceTier.TIER_2:
                existing.tier = tier
            if exposure != ExposureLevel.INTERNAL_SERVICE:
                existing.exposure = exposure
            if owner:
                existing.owner = owner
            if permissions:
                existing.permissions = list(set(existing.permissions + permissions))
            if concepts:
                existing.concepts = list(set(existing.concepts + concepts))
            if metadata:
                existing.metadata.update(metadata)
            return existing

        node = GraphNode(
            id=node_id,
            name=name,
            entity_type=entity_type,
            tenant_id=self.tenant_id,
            tier=tier,
            exposure=exposure,
            owner=owner,
            permissions=permissions or [],
            concepts=concepts or [],
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        self.incoming_edges.setdefault(node_id, [])
        self.outgoing_edges.setdefault(node_id, [])
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str = "CALLS",
        confidence: float = 1.0,
        provenance: str = "STATIC_CONFIRMED",
        is_observed: bool = False,
        call_count_7d: int = 0,
        p95_latency_ms: float = 0.0,
        first_observed_at: datetime | None = None,
        last_observed_at: datetime | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        evidence_refs: list[str] | None = None,
        is_disputed: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> GraphEdge:
        """Adds or merges a directed edge. Deduplicates multiple edges between same endpoints."""
        # Auto-create placeholder nodes if not present
        if source_id not in self.nodes:
            self.add_node(node_id=source_id, name=source_id, entity_type="Service")
        if target_id not in self.nodes:
            self.add_node(node_id=target_id, name=target_id, entity_type="Service")

        key = (source_id, target_id, relationship_type)
        refs = evidence_refs or []

        if key in self._edge_index:
            existing = self._edge_index[key]
            # Deduplication merge: take max confidence, sum counts, latest timestamp
            existing.confidence = max(existing.confidence, confidence)
            existing.is_observed = existing.is_observed or is_observed
            existing.call_count_7d += call_count_7d
            existing.p95_latency_ms = max(existing.p95_latency_ms, p95_latency_ms)
            existing.is_disputed = existing.is_disputed or is_disputed
            existing.evidence_refs = list(set(existing.evidence_refs + refs))
            if last_observed_at and (existing.last_observed_at is None or last_observed_at > existing.last_observed_at):
                existing.last_observed_at = last_observed_at
            if valid_to:
                existing.valid_to = valid_to
            if metadata:
                existing.metadata.update(metadata)
            return existing

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            confidence=confidence,
            provenance=provenance,
            is_observed=is_observed,
            call_count_7d=call_count_7d,
            p95_latency_ms=p95_latency_ms,
            first_observed_at=first_observed_at,
            last_observed_at=last_observed_at,
            valid_from=valid_from,
            valid_to=valid_to,
            evidence_refs=refs,
            is_disputed=is_disputed,
            metadata=metadata or {},
        )
        self._edge_index[key] = edge
        self.incoming_edges.setdefault(target_id, []).append(edge)
        self.outgoing_edges.setdefault(source_id, []).append(edge)
        return edge

    def get_node(self, node_id: str) -> GraphNode | None:
        """Retrieves a node by identifier."""
        return self.nodes.get(node_id)

    def get_consumers(self, target_id: str, include_expired: bool = False) -> list[GraphEdge]:
        """Returns all incoming edges (callers, subscribers, readers) pointing to target_id."""
        edges = self.incoming_edges.get(target_id, [])
        if include_expired:
            return edges
        return [e for e in edges if not e.is_expired()]

    def get_dependencies(self, source_id: str, include_expired: bool = False) -> list[GraphEdge]:
        """Returns all outgoing edges pointing from source_id to callee/dependency nodes."""
        edges = self.outgoing_edges.get(source_id, [])
        if include_expired:
            return edges
        return [e for e in edges if not e.is_expired()]

    def get_nodes_by_concept(self, concept_urn: str) -> list[GraphNode]:
        """Finds all nodes mapped to a specific ontology concept URN."""
        return [n for n in self.nodes.values() if concept_urn in n.concepts]

    def get_workflows_for_entity(self, entity_id: str) -> list[str]:
        """Finds all workflows that the entity participates in via PART_OF_WORKFLOW edges."""
        workflows: set[str] = set()
        # Direct PART_OF_WORKFLOW outgoing edges
        for edge in self.get_dependencies(entity_id):
            if edge.relationship_type == "PART_OF_WORKFLOW":
                workflows.add(edge.target_id)
        # Check if node metadata or parent service belongs to a workflow
        node = self.get_node(entity_id)
        if node and "workflow" in node.metadata:
            workflows.add(node.metadata["workflow"])
        return sorted(workflows)
