"""Domain and Data Models for ChangeScope Deterministic Impact Reasoning Engine."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ImpactCategory(StrEnum):
    """Classification of impact propagation mechanism."""

    DIRECT = "DIRECT"
    TRANSITIVE = "TRANSITIVE"
    SEMANTIC = "SEMANTIC"
    RUNTIME_OBSERVED = "RUNTIME_OBSERVED"
    WORKFLOW = "WORKFLOW"
    PERMISSION = "PERMISSION"
    UNKNOWN = "UNKNOWN"


class ServiceTier(StrEnum):
    """Operational criticality tier of a service."""

    TIER_1 = "TIER_1"  # Mission Critical (User-facing, revenue path)
    TIER_2 = "TIER_2"  # Core Business (Async processing, vital dependencies)
    TIER_3 = "TIER_3"  # Internal / Operational (Batch, reporting, analytics)


class ExposureLevel(StrEnum):
    """Network and boundary exposure classification."""

    PUBLIC_INTERNET = "PUBLIC_INTERNET"
    PARTNER_API = "PARTNER_API"
    INTERNAL_SERVICE = "INTERNAL_SERVICE"
    RESTRICTED = "RESTRICTED"


class RecommendedAction(StrEnum):
    """Deterministic, actionable guidance produced from risk assessment."""

    BLOCK_MERGE = "BLOCK_MERGE"
    REQUIRE_MANUAL_APPROVAL = "REQUIRE_MANUAL_APPROVAL"
    RUN_CANARY_TESTS = "RUN_CANARY_TESTS"
    NOTIFY_SERVICE_OWNERS = "NOTIFY_SERVICE_OWNERS"
    PROCEED_WITH_MONITORING = "PROCEED_WITH_MONITORING"


class ProposedChange(BaseModel):
    """Represents a discrete entity mutation in a proposed ChangeSet."""

    change_id: str = Field(default_factory=lambda: f"chg-{uuid.uuid4().hex[:8]}")
    entity_id: str
    entity_name: str
    entity_type: str  # APIEndpoint, APIField, DatabaseTable, DatabaseColumn, Event, Function
    change_type: str = (
        "MODIFIED"  # REMOVED, TYPE_CHANGED, REQUIRED_ADDED, NULLABILITY_CHANGED, CONSTRAINT_TIGHTENED, etc.
    )
    severity: str = "BLOCKING"  # BLOCKING, WARNING, INFO
    is_breaking: bool = True
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    field_name: str | None = None
    endpoint_path: str | None = None
    http_method: str | None = None
    service_id: str | None = None
    concepts: list[str] = Field(default_factory=list)


class ChangeSetInput(BaseModel):
    """The complete input payload provided to the impact reasoning engine."""

    change_set_id: str = Field(default_factory=lambda: f"cs-{uuid.uuid4().hex[:10]}")
    tenant_id: str
    repository_id: str | None = None
    base_commit: str = "0000000000000000000000000000000000000000"
    head_commit: str = "1111111111111111111111111111111111111111"
    target_branch: str = "main"
    source_branch: str = "feature"
    changes: list[ProposedChange] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ImpactedEntity(BaseModel):
    """A distinct downstream entity affected directly or transitively by a change."""

    entity_id: str
    entity_name: str
    entity_type: str
    impact_category: ImpactCategory
    hop_distance: int = 1
    path: list[str] = Field(default_factory=list)
    path_confidence: float = 1.0
    is_runtime_confirmed: bool = False
    call_frequency_7d: int = 0
    p95_latency_ms: float = 0.0
    service_tier: ServiceTier = ServiceTier.TIER_2
    exposure: ExposureLevel = ExposureLevel.INTERNAL_SERVICE
    owner: str | None = None
    required_permissions: list[str] = Field(default_factory=list)
    ontology_concepts: list[str] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    uncertainty_reasons: list[str] = Field(default_factory=list)


class ImpactPath(BaseModel):
    """An evidence-backed directed traversal path from root change to affected consumer."""

    source_entity: str
    target_entity: str
    path_hops: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)
    cumulative_confidence: float = 1.0
    evidence_references: list[str] = Field(default_factory=list)
    has_runtime_evidence: bool = False


class RiskBreakdown(BaseModel):
    """Transparent and auditable breakdown of deterministic risk calculation factors."""

    base_severity_score: float = 0.0
    reachability_score: float = 0.0
    usage_multiplier: float = 1.0
    criticality_score: float = 0.0
    exposure_factor: float = 1.0
    freshness_factor: float = 1.0
    semantic_confidence_factor: float = 1.0
    uncertainty_penalty: float = 0.0
    total_raw_score: float = 0.0
    final_score: int = 0
    formula_explanation: str
    factors: dict[str, float] = Field(default_factory=dict)


class ImpactReasoningResult(BaseModel):
    """Authoritative, deterministic output from the ChangeScope Impact Reasoning Engine."""

    change_set_id: str
    tenant_id: str
    root_changed_entities: list[str] = Field(default_factory=list)
    affected_entities: list[ImpactedEntity] = Field(default_factory=list)
    impacted_services_count: int = 0
    impacted_endpoints_count: int = 0
    affected_workflows: list[str] = Field(default_factory=list)
    graph_paths: list[ImpactPath] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    overall_confidence: float = 1.0
    overall_uncertainty: float = 0.0
    risk_score: int = 0  # 0 to 100
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    risk_breakdown: RiskBreakdown
    recommended_action: RecommendedAction
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    summary_narrative: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
