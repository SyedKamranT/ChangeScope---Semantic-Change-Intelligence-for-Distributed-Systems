"""Abstract Provider Interface and Data Transfer Objects for ChangeScope Ontology Integration."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class CandidateDiscoveryResult(BaseModel):
    """Result payload from candidate ontology entity/relationship discovery."""

    tenant_id: str
    discovered_candidates: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    status: str = "COMPLETED"


class ConceptReconciliationResult(BaseModel):
    """Outcome of reconciling field/table candidates against canonical domain concepts."""

    tenant_id: str
    reconciled_concepts: list[dict[str, Any]] = Field(default_factory=list)
    synonym_matches: list[dict[str, Any]] = Field(default_factory=list)
    polysemic_distinctions: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_disputes: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 1.0


class RelationshipResolutionResult(BaseModel):
    """Outcome of resolving and typing dependencies between entities."""

    tenant_id: str
    resolved_relationships: list[dict[str, Any]] = Field(default_factory=list)
    rejected_relationships: list[dict[str, Any]] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Structural, semantic, and temporal validation report."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class CertificationResult(BaseModel):
    """Audit report for human certification promotions."""

    success: bool
    candidate_id: str
    review_status: str
    entity_or_rel_id: str | None = None
    reviewed_by: str
    reviewed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    notes: str | None = None


class ModelImportResult(BaseModel):
    """Status and entity counts resulting from an external model import."""

    success: bool
    format: str
    imported_entities_count: int = 0
    imported_relationships_count: int = 0
    imported_concepts_count: int = 0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelExportResult(BaseModel):
    """Serialized export artifact and entity counts."""

    success: bool
    format: str
    payload: str
    exported_entities_count: int = 0
    exported_relationships_count: int = 0
    exported_concepts_count: int = 0


class CircuitBreakerState(BaseModel):
    """Operational health state of external network circuit breakers."""

    state: str = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
    failure_count: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None


class ProviderStatus(BaseModel):
    """Diagnostic connectivity and health status for an ontology provider."""

    provider_name: str
    is_healthy: bool
    is_available: bool
    deployment_type: str
    circuit_breaker: CircuitBreakerState | None = None
    latency_ms: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OntologyProvider(ABC):
    """Abstract provider abstraction governing ontology discovery, reconciliation, certification, and interchange."""

    @abstractmethod
    async def discover_candidates(
        self,
        tenant_id: str,
        scope: dict[str, Any] | None = None,
    ) -> CandidateDiscoveryResult:
        """Discovers uncertified entity and relationship candidates from code ASTs or external catalogs."""
        pass

    @abstractmethod
    async def reconcile_concepts(
        self,
        tenant_id: str,
        term_candidates: list[dict[str, Any]],
    ) -> ConceptReconciliationResult:
        """Reconciles ambiguous field or table names against canonical business concepts."""
        pass

    @abstractmethod
    async def resolve_relationships(
        self,
        tenant_id: str,
        entities: list[dict[str, Any]],
    ) -> RelationshipResolutionResult:
        """Resolves structural dependencies against canonical relationship typing constraints."""
        pass

    @abstractmethod
    async def validate_definition(
        self,
        tenant_id: str,
        definition: dict[str, Any],
    ) -> ValidationResult:
        """Enforces structural, temporal, and semantic constraints across definitions."""
        pass

    @abstractmethod
    async def certify_definition(
        self,
        tenant_id: str,
        candidate_id: str,
        reviewer: str,
        notes: str | None = None,
    ) -> CertificationResult:
        """Human certification workflow: promotes an untrusted candidate into the canonical graph."""
        pass

    @abstractmethod
    async def import_model(
        self,
        tenant_id: str,
        payload: str | dict[str, Any],
        format: str = "ossie_yaml",
    ) -> ModelImportResult:
        """Ingests an external model in Apache Ossie YAML or CSEO JSON-LD."""
        pass

    @abstractmethod
    async def export_model(
        self,
        tenant_id: str,
        format: str = "ossie_yaml",
    ) -> ModelExportResult:
        """Exports ChangeScope's knowledge graph into Apache Ossie YAML or CSEO JSON-LD."""
        pass

    @abstractmethod
    async def get_status(self) -> ProviderStatus:
        """Returns health, connectivity, circuit breaker status, and latency metrics."""
        pass
