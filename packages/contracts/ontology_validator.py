"""Ontology Relationship and Entity Validation Engine for ChangeScope."""

from datetime import datetime

from packages.shared.errors import SemanticValidationError
from packages.shared.ontology_models import (
    CoreEntityType,
    ProvenanceType,
    RelationshipType,
)

# Strict source-to-target entity type constraint matrix for the 15 relationships
RELATIONSHIP_CONSTRAINTS: dict[RelationshipType, tuple[set[CoreEntityType], set[CoreEntityType]]] = {
    RelationshipType.CALLS: (
        {CoreEntityType.FUNCTION, CoreEntityType.SERVICE},
        {CoreEntityType.API_ENDPOINT, CoreEntityType.FUNCTION},
    ),
    RelationshipType.IMPORTS: (
        {CoreEntityType.MODULE},
        {CoreEntityType.MODULE, CoreEntityType.FUNCTION},
    ),
    RelationshipType.PRODUCES: (
        {CoreEntityType.FUNCTION, CoreEntityType.API_ENDPOINT},
        {CoreEntityType.API_FIELD, CoreEntityType.EVENT},
    ),
    RelationshipType.CONSUMES: (
        {CoreEntityType.FUNCTION, CoreEntityType.API_ENDPOINT},
        {CoreEntityType.API_FIELD, CoreEntityType.EVENT},
    ),
    RelationshipType.MAPS_TO: (
        {CoreEntityType.API_FIELD, CoreEntityType.DATABASE_COLUMN},
        {CoreEntityType.BUSINESS_CONCEPT},
    ),
    RelationshipType.READS: (
        {CoreEntityType.FUNCTION, CoreEntityType.SERVICE},
        {CoreEntityType.DATABASE_COLUMN, CoreEntityType.DATABASE_TABLE},
    ),
    RelationshipType.WRITES: (
        {CoreEntityType.FUNCTION, CoreEntityType.SERVICE},
        {CoreEntityType.DATABASE_COLUMN, CoreEntityType.DATABASE_TABLE},
    ),
    RelationshipType.PERSISTS_AS: (
        {CoreEntityType.API_FIELD, CoreEntityType.EVENT_SCHEMA},
        {CoreEntityType.DATABASE_COLUMN},
    ),
    RelationshipType.PUBLISHES: (
        {CoreEntityType.SERVICE, CoreEntityType.FUNCTION},
        {CoreEntityType.EVENT_SCHEMA},
    ),
    RelationshipType.SUBSCRIBES_TO: (
        {CoreEntityType.SERVICE, CoreEntityType.FUNCTION},
        {CoreEntityType.EVENT_SCHEMA},
    ),
    RelationshipType.PART_OF_WORKFLOW: (
        {CoreEntityType.SERVICE, CoreEntityType.API_ENDPOINT, CoreEntityType.EVENT},
        {CoreEntityType.WORKFLOW},
    ),
    RelationshipType.OWNED_BY: (
        {CoreEntityType.SERVICE, CoreEntityType.REPOSITORY, CoreEntityType.DATABASE},
        {CoreEntityType.OWNER},
    ),
    RelationshipType.REQUIRES_PERMISSION: (
        {CoreEntityType.API_ENDPOINT, CoreEntityType.FUNCTION},
        {CoreEntityType.PERMISSION},
    ),
    RelationshipType.DEPENDS_ON: (
        {CoreEntityType.SERVICE, CoreEntityType.MODULE},
        {CoreEntityType.SERVICE, CoreEntityType.MODULE},
    ),
    RelationshipType.TRANSFORMS_INTO: (
        {CoreEntityType.API_FIELD, CoreEntityType.DATABASE_COLUMN},
        {CoreEntityType.API_FIELD, CoreEntityType.DATABASE_COLUMN},
    ),
}


class OntologyValidator:
    """Deterministic validator enforcing structural, provenance, and semantic invariants across the graph."""

    @classmethod
    def validate_relationship(
        cls,
        rel_type: str,
        source_type: str,
        target_type: str,
        provenance: str,
        confidence: float,
        first_observed_at: datetime,
        last_observed_at: datetime,
        valid_from: datetime,
        valid_to: datetime | None = None,
        evidence_refs: list[str] | None = None,
    ) -> None:
        """Validates relationship typing, permitted domains/ranges, provenance, confidence, and timestamps."""
        # 1. Validate Relationship Type Enum
        try:
            rel_enum = RelationshipType(rel_type)
        except ValueError as err:
            raise SemanticValidationError(f"Invalid relationship type '{rel_type}'.") from err

        # 2. Validate Source and Target Entity Enums
        try:
            src_enum = CoreEntityType(source_type)
        except ValueError as err:
            raise SemanticValidationError(f"Invalid source entity type '{source_type}'.") from err

        try:
            tgt_enum = CoreEntityType(target_type)
        except ValueError as err:
            raise SemanticValidationError(f"Invalid target entity type '{target_type}'.") from err

        # 3. Validate Domain & Range Constraints
        allowed_srcs, allowed_tgts = RELATIONSHIP_CONSTRAINTS[rel_enum]
        if src_enum not in allowed_srcs:
            raise SemanticValidationError(
                f"Relationship '{rel_type}' cannot originate from source type '{source_type}'. Allowed: {[s.value for s in allowed_srcs]}."
            )
        if tgt_enum not in allowed_tgts:
            raise SemanticValidationError(
                f"Relationship '{rel_type}' cannot target entity type '{target_type}'. Allowed: {[t.value for t in allowed_tgts]}."
            )

        # 4. Validate Provenance
        try:
            prov_enum = ProvenanceType(provenance)
        except ValueError as err:
            raise SemanticValidationError(f"Invalid relationship provenance '{provenance}'.") from err

        # 5. Validate Confidence Range & Provenance Invariants
        if not (0.0 <= confidence <= 1.0):
            raise SemanticValidationError(f"Confidence score {confidence} must be between 0.0 and 1.0.")

        if prov_enum in {
            ProvenanceType.STATIC_CONFIRMED,
            ProvenanceType.CONTRACT_CONFIRMED,
            ProvenanceType.HUMAN_CERTIFIED,
        }:
            if confidence < 1.0:
                raise SemanticValidationError(
                    f"Provenance '{provenance}' mandates exact 1.0 confidence, got {confidence}."
                )

        if prov_enum == ProvenanceType.RUNTIME_OBSERVED:
            if not (0.70 <= confidence <= 0.99):
                raise SemanticValidationError(
                    f"RUNTIME_OBSERVED confidence must be in range [0.70, 0.99], got {confidence}."
                )

        # 6. Validate Evidence References
        if prov_enum != ProvenanceType.HUMAN_CERTIFIED:
            if not evidence_refs or len(evidence_refs) == 0:
                raise SemanticValidationError(
                    f"Relationship with provenance '{provenance}' requires at least one supporting evidence reference."
                )

        # 7. Validate Temporal Monotonicity
        if first_observed_at > last_observed_at:
            raise SemanticValidationError(
                f"first_observed_at ({first_observed_at}) cannot be later than last_observed_at ({last_observed_at})."
            )

        if valid_to is not None and valid_from > valid_to:
            raise SemanticValidationError(f"valid_from ({valid_from}) cannot be later than valid_to ({valid_to}).")

    @classmethod
    def validate_business_concept_disambiguation(
        cls,
        concept_category: str,
        urn: str,
        bounded_context: str | None,
        synonyms: list[str],
        homonym_distinctions: dict[str, str],
    ) -> None:
        """Enforces unambiguous ontology definitions: polysemic concepts must have distinct bounded contexts."""
        polysemic_categories = {"Account", "Status", "Resource"}
        if concept_category in polysemic_categories and not bounded_context:
            raise SemanticValidationError(
                f"Concept '{urn}' belongs to polysemic category '{concept_category}' and must declare a bounded_context to prevent false identity merging."
            )

        # Ensure synonyms don't contain empty or trivial names
        for syn in synonyms:
            if not syn.strip():
                raise SemanticValidationError("Synonym cannot be empty or whitespace.")

        # Ensure homonym distinctions explicitly map conflicting contexts
        if bounded_context and bounded_context in homonym_distinctions:
            raise SemanticValidationError(
                f"Bounded context '{bounded_context}' cannot appear as a conflicting homonym distinction against itself."
            )
