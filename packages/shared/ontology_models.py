"""ChangeScope Software Engineering Ontology (CSEO) Canonical Relational Models (SQLAlchemy 2.0)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from packages.shared.models import Base, utc_now


class ProvenanceType(StrEnum):
    """Permitted relationship evidence provenance levels."""

    STATIC_CONFIRMED = "STATIC_CONFIRMED"
    RUNTIME_OBSERVED = "RUNTIME_OBSERVED"
    CONTRACT_CONFIRMED = "CONTRACT_CONFIRMED"
    ONTOLOGY_INFERRED = "ONTOLOGY_INFERRED"
    HUMAN_CERTIFIED = "HUMAN_CERTIFIED"


class RelationshipStatus(StrEnum):
    """Operational status of an ontological relationship edge."""

    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    SUPERSEDED = "SUPERSEDED"
    DISPUTED = "DISPUTED"


class CandidateReviewStatus(StrEnum):
    """Governance review state for machine-generated candidates."""

    CANDIDATE = "CANDIDATE"
    REVIEW_PENDING = "REVIEW_PENDING"
    HUMAN_CERTIFIED = "HUMAN_CERTIFIED"
    REJECTED = "REJECTED"
    DISPUTED = "DISPUTED"


class CoreEntityType(StrEnum):
    """The 26 first-class ontology entity types."""

    ORGANIZATION = "Organization"
    WORKSPACE = "Workspace"
    REPOSITORY = "Repository"
    REPOSITORY_VERSION = "RepositoryVersion"
    COMMIT = "Commit"
    CHANGE_SET = "ChangeSet"
    SERVICE = "Service"
    MODULE = "Module"
    FUNCTION = "Function"
    API_ENDPOINT = "APIEndpoint"
    API_FIELD = "APIField"
    EVENT = "Event"
    EVENT_SCHEMA = "EventSchema"
    DATABASE = "Database"
    DATABASE_TABLE = "DatabaseTable"
    DATABASE_COLUMN = "DatabaseColumn"
    BUSINESS_CONCEPT = "BusinessConcept"
    WORKFLOW = "Workflow"
    PERMISSION = "Permission"
    OWNER = "Owner"
    TRACE = "Trace"
    TRACE_SPAN = "TraceSpan"
    DEPENDENCY = "Dependency"
    FINDING = "Finding"
    EVIDENCE = "Evidence"
    TEST_CASE = "TestCase"
    RECOMMENDATION = "Recommendation"


class RelationshipType(StrEnum):
    """The 15 canonical ontology relationship types."""

    CALLS = "CALLS"
    IMPORTS = "IMPORTS"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    MAPS_TO = "MAPS_TO"
    READS = "READS"
    WRITES = "WRITES"
    PERSISTS_AS = "PERSISTS_AS"
    PUBLISHES = "PUBLISHES"
    SUBSCRIBES_TO = "SUBSCRIBES_TO"
    PART_OF_WORKFLOW = "PART_OF_WORKFLOW"
    OWNED_BY = "OWNED_BY"
    REQUIRES_PERMISSION = "REQUIRES_PERMISSION"
    DEPENDS_ON = "DEPENDS_ON"
    TRANSFORMS_INTO = "TRANSFORMS_INTO"


class SemanticConceptCategory(StrEnum):
    """Core semantic concept classifications for disambiguation."""

    MONETARY_VALUE = "MonetaryValue"
    IDENTIFIER = "Identifier"
    TIMESTAMP = "Timestamp"
    STATUS = "Status"
    MEASUREMENT_UNIT = "MeasurementUnit"
    CUSTOMER = "Customer"
    TRANSACTION = "Transaction"
    ACCOUNT = "Account"
    RESOURCE = "Resource"


class OntologyEntity(Base):
    """Canonical representation of an entity in the ChangeScope knowledge graph."""

    __tablename__ = "ontology_entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canonical_urn", name="uq_ontology_entity_tenant_urn"),
        Index("ix_ontology_entities_type", "tenant_id", "entity_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    canonical_urn: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    properties_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @property
    def properties(self) -> dict[str, Any]:
        return self.properties_payload

    @properties.setter
    def properties(self, val: dict[str, Any]) -> None:
        self.properties_payload = val


class OntologyRelationship(Base):
    """Strictly versioned, provenance-tracked relationship between two ontology entities."""

    __tablename__ = "ontology_relationships"
    __table_args__ = (
        Index("ix_ontology_rel_endpoints", "tenant_id", "source_id", "target_id", "rel_type"),
        Index("ix_ontology_rel_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=False
    )
    rel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_repo_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=RelationshipStatus.ACTIVE.value)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source_entity: Mapped["OntologyEntity"] = relationship("OntologyEntity", foreign_keys=[source_id])
    target_entity: Mapped["OntologyEntity"] = relationship("OntologyEntity", foreign_keys=[target_id])


class BusinessConceptEntity(Base):
    """Canonical domain term used for synonym unification and polysemy disambiguation."""

    __tablename__ = "ontology_business_concepts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "urn", name="uq_business_concept_tenant_urn"),
        Index("ix_business_concepts_category", "tenant_id", "category"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    urn: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    bounded_context: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list)
    homonym_distinctions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    constraints_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OntologyCandidate(Base):
    """Machine-generated candidate entities or relationships awaiting human certification or corroboration."""

    __tablename__ = "ontology_candidates"
    __table_args__ = (Index("ix_ontology_candidates_status", "tenant_id", "review_status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'ENTITY' or 'RELATIONSHIP'
    proposed_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_scanner: Mapped[str] = mapped_column(String(64), nullable=False)  # 'AST', 'OTEL', 'SPEC', 'INFERENCE'
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_status: Mapped[str] = mapped_column(String(32), default=CandidateReviewStatus.CANDIDATE.value)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OntologyDispute(Base):
    """Records conflicting, competing semantic mappings without discarding ambiguity."""

    __tablename__ = "ontology_disputes"
    __table_args__ = (Index("ix_ontology_disputes_status", "tenant_id", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id_or_field: Mapped[str] = mapped_column(String(255), nullable=False)
    competing_concepts: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    competing_candidate_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="UNRESOLVED")
    resolution_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OntologyVersionRecord(Base):
    """SemVer version snapshot and changelog audit record."""

    __tablename__ = "ontology_versions"
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_ontology_tenant_version"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    diff_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
