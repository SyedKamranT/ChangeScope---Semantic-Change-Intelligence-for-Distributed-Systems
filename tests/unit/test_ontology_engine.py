"""Unit and Integration Tests for ChangeScope Software Engineering Ontology (CSEO) Engine.

Covers:
- Relationship constraint matrix and domain/range typing rules.
- Provenance confidence and evidence invariants.
- Semantic disambiguation (polysemy with bounded contexts and synonym unification).
- Governance lifecycle (proposals, review pending, human certification, rejection, dispute recording).
- SemVer versioning and deterministic ontology diffing.
- Enterprise 5-microservice reference topology schema conformity.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.ontology_validator import (
    RELATIONSHIP_CONSTRAINTS,
    OntologyValidator,
)
from packages.shared.database import async_session_factory
from packages.shared.errors import ConflictError, SemanticValidationError
from packages.shared.ontology_governance import OntologyGovernanceManager
from packages.shared.ontology_models import (
    CandidateReviewStatus,
    CoreEntityType,
    OntologyEntity,
    OntologyVersionRecord,
    ProvenanceType,
    RelationshipType,
    SemanticConceptCategory,
)


@pytest.fixture
async def db_session():
    """Provides isolated transactional async database session for ontology tests."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()


# ==============================================================================
# 1. RELATIONSHIP VALIDATOR & CONSTRAINT MATRIX TESTS
# ==============================================================================


def test_all_15_relationship_types_have_constraints():
    """Verifies all 15 canonical relationship types are defined in the constraint matrix."""
    for rel_type in RelationshipType:
        assert rel_type in RELATIONSHIP_CONSTRAINTS
        src_types, tgt_types = RELATIONSHIP_CONSTRAINTS[rel_type]
        assert len(src_types) > 0, f"Source types empty for {rel_type}"
        assert len(tgt_types) > 0, f"Target types empty for {rel_type}"


@pytest.mark.parametrize(
    "rel_type,source_type,target_type",
    [
        (RelationshipType.CALLS.value, CoreEntityType.SERVICE.value, CoreEntityType.API_ENDPOINT.value),
        (RelationshipType.IMPORTS.value, CoreEntityType.MODULE.value, CoreEntityType.MODULE.value),
        (RelationshipType.PRODUCES.value, CoreEntityType.API_ENDPOINT.value, CoreEntityType.API_FIELD.value),
        (RelationshipType.CONSUMES.value, CoreEntityType.API_ENDPOINT.value, CoreEntityType.API_FIELD.value),
        (RelationshipType.MAPS_TO.value, CoreEntityType.API_FIELD.value, CoreEntityType.BUSINESS_CONCEPT.value),
        (RelationshipType.READS.value, CoreEntityType.FUNCTION.value, CoreEntityType.DATABASE_TABLE.value),
        (RelationshipType.WRITES.value, CoreEntityType.FUNCTION.value, CoreEntityType.DATABASE_TABLE.value),
        (RelationshipType.PERSISTS_AS.value, CoreEntityType.API_FIELD.value, CoreEntityType.DATABASE_COLUMN.value),
        (RelationshipType.PUBLISHES.value, CoreEntityType.SERVICE.value, CoreEntityType.EVENT_SCHEMA.value),
        (RelationshipType.SUBSCRIBES_TO.value, CoreEntityType.SERVICE.value, CoreEntityType.EVENT_SCHEMA.value),
        (RelationshipType.PART_OF_WORKFLOW.value, CoreEntityType.SERVICE.value, CoreEntityType.WORKFLOW.value),
        (RelationshipType.OWNED_BY.value, CoreEntityType.SERVICE.value, CoreEntityType.OWNER.value),
        (
            RelationshipType.REQUIRES_PERMISSION.value,
            CoreEntityType.API_ENDPOINT.value,
            CoreEntityType.PERMISSION.value,
        ),
        (RelationshipType.DEPENDS_ON.value, CoreEntityType.SERVICE.value, CoreEntityType.SERVICE.value),
        (RelationshipType.TRANSFORMS_INTO.value, CoreEntityType.API_FIELD.value, CoreEntityType.DATABASE_COLUMN.value),
    ],
)
def test_valid_relationships_pass_validation(rel_type: str, source_type: str, target_type: str):
    """Verifies that legal domain/range entity type pairs succeed without raising errors."""
    now = datetime.now(UTC)
    OntologyValidator.validate_relationship(
        rel_type=rel_type,
        source_type=source_type,
        target_type=target_type,
        provenance=ProvenanceType.STATIC_CONFIRMED.value,
        confidence=1.0,
        first_observed_at=now,
        last_observed_at=now,
        valid_from=now,
        evidence_refs=["evidence:ast:test:01"],
    )


def test_invalid_relationship_domain_raises():
    """Relationship with an illegal source entity type must be rejected."""
    now = datetime.now(UTC)
    with pytest.raises(SemanticValidationError) as exc:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.CALLS.value,
            source_type=CoreEntityType.DATABASE.value,  # Database cannot CALL an endpoint
            target_type=CoreEntityType.API_ENDPOINT.value,
            provenance=ProvenanceType.STATIC_CONFIRMED.value,
            confidence=1.0,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=["ref:01"],
        )
    assert "cannot originate from source type 'Database'" in str(exc.value)


def test_invalid_relationship_range_raises():
    """Relationship with an illegal target entity type must be rejected."""
    now = datetime.now(UTC)
    with pytest.raises(SemanticValidationError) as exc:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.MAPS_TO.value,
            source_type=CoreEntityType.API_FIELD.value,
            target_type=CoreEntityType.SERVICE.value,  # MAPS_TO must target BusinessConcept
            provenance=ProvenanceType.ONTOLOGY_INFERRED.value,
            confidence=0.85,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=["ref:01"],
        )
    assert "cannot target entity type 'Service'" in str(exc.value)


def test_unknown_relationship_or_entity_type_raises():
    """Invalid enum strings must be trapped and rejected."""
    now = datetime.now(UTC)
    with pytest.raises(SemanticValidationError) as exc1:
        OntologyValidator.validate_relationship(
            rel_type="INVENTS_NEW_REL",
            source_type=CoreEntityType.SERVICE.value,
            target_type=CoreEntityType.SERVICE.value,
            provenance=ProvenanceType.STATIC_CONFIRMED.value,
            confidence=1.0,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=["ref:01"],
        )
    assert "Invalid relationship type" in str(exc1.value)

    with pytest.raises(SemanticValidationError) as exc2:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.CALLS.value,
            source_type="NonExistentEntity",
            target_type=CoreEntityType.API_ENDPOINT.value,
            provenance=ProvenanceType.STATIC_CONFIRMED.value,
            confidence=1.0,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=["ref:01"],
        )
    assert "Invalid source entity type" in str(exc2.value)


def test_provenance_confidence_invariants():
    """Enforces strict confidence score ranges according to provenance level."""
    now = datetime.now(UTC)

    # 1. STATIC_CONFIRMED requires 1.0 confidence
    with pytest.raises(SemanticValidationError) as exc1:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.CALLS.value,
            source_type=CoreEntityType.SERVICE.value,
            target_type=CoreEntityType.API_ENDPOINT.value,
            provenance=ProvenanceType.STATIC_CONFIRMED.value,
            confidence=0.85,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=["ref:01"],
        )
    assert "mandates exact 1.0 confidence" in str(exc1.value)

    # 2. RUNTIME_OBSERVED confidence must be in [0.70, 0.99]
    with pytest.raises(SemanticValidationError) as exc2:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.CALLS.value,
            source_type=CoreEntityType.SERVICE.value,
            target_type=CoreEntityType.API_ENDPOINT.value,
            provenance=ProvenanceType.RUNTIME_OBSERVED.value,
            confidence=0.65,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=["ref:01"],
        )
    assert "must be in range [0.70, 0.99]" in str(exc2.value)

    # 3. Missing evidence refs on non-human certified
    with pytest.raises(SemanticValidationError) as exc3:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.CALLS.value,
            source_type=CoreEntityType.SERVICE.value,
            target_type=CoreEntityType.API_ENDPOINT.value,
            provenance=ProvenanceType.CONTRACT_CONFIRMED.value,
            confidence=1.0,
            first_observed_at=now,
            last_observed_at=now,
            valid_from=now,
            evidence_refs=[],
        )
    assert "requires at least one supporting evidence reference" in str(exc3.value)


def test_temporal_monotonicity_invariants():
    """Temporal validity checks: first_observed <= last_observed, valid_from <= valid_to."""
    now = datetime.now(UTC)
    past = now - timedelta(hours=1)
    future = now + timedelta(hours=1)

    # first_observed after last_observed must fail
    with pytest.raises(SemanticValidationError) as exc1:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.DEPENDS_ON.value,
            source_type=CoreEntityType.SERVICE.value,
            target_type=CoreEntityType.SERVICE.value,
            provenance=ProvenanceType.HUMAN_CERTIFIED.value,
            confidence=1.0,
            first_observed_at=future,
            last_observed_at=past,
            valid_from=past,
        )
    assert "cannot be later than last_observed_at" in str(exc1.value)

    # valid_from after valid_to must fail
    with pytest.raises(SemanticValidationError) as exc2:
        OntologyValidator.validate_relationship(
            rel_type=RelationshipType.DEPENDS_ON.value,
            source_type=CoreEntityType.SERVICE.value,
            target_type=CoreEntityType.SERVICE.value,
            provenance=ProvenanceType.HUMAN_CERTIFIED.value,
            confidence=1.0,
            first_observed_at=past,
            last_observed_at=now,
            valid_from=future,
            valid_to=past,
        )
    assert "cannot be later than valid_to" in str(exc2.value)


# ==============================================================================
# 2. SEMANTIC DISAMBIGUATION & TAXONOMY TESTS
# ==============================================================================


def test_polysemy_without_bounded_context_rejected():
    """Concepts in polysemic categories (Account, Status, Resource) require bounded_context."""
    with pytest.raises(SemanticValidationError) as exc:
        OntologyValidator.validate_business_concept_disambiguation(
            concept_category=SemanticConceptCategory.ACCOUNT.value,
            urn="urn:cseo:concept:Account",
            bounded_context=None,
            synonyms=["account_record"],
            homonym_distinctions={},
        )
    assert "must declare a bounded_context to prevent false identity merging" in str(exc.value)


def test_polysemy_with_distinct_bounded_contexts_accepted():
    """Polysemic concepts with distinct bounded contexts successfully disambiguate."""
    # Identity account
    OntologyValidator.validate_business_concept_disambiguation(
        concept_category=SemanticConceptCategory.ACCOUNT.value,
        urn="urn:cseo:concept:auth:Account",
        bounded_context="auth",
        synonyms=["user_account", "login_principal"],
        homonym_distinctions={"billing": "Ledger balance account"},
    )

    # Billing ledger account
    OntologyValidator.validate_business_concept_disambiguation(
        concept_category=SemanticConceptCategory.ACCOUNT.value,
        urn="urn:cseo:concept:billing:Account",
        bounded_context="billing",
        synonyms=["ledger_account", "wallet"],
        homonym_distinctions={"auth": "Security identity account"},
    )


def test_empty_synonym_rejected():
    """Synonyms cannot be blank or whitespace."""
    with pytest.raises(SemanticValidationError) as exc:
        OntologyValidator.validate_business_concept_disambiguation(
            concept_category=SemanticConceptCategory.IDENTIFIER.value,
            urn="urn:cseo:concept:Id",
            bounded_context=None,
            synonyms=["valid_synonym", "   "],
            homonym_distinctions={},
        )
    assert "Synonym cannot be empty" in str(exc.value)


# ==============================================================================
# 3. ONTOLOGY GOVERNANCE WORKFLOW TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_propose_and_certify_candidate_entity(db_session: AsyncSession):
    """Untrusted machine candidate is created in REVIEW_PENDING and promoted to HUMAN_CERTIFIED."""
    tenant_id = "tenant-gov-01"

    # 1. Propose candidate entity with high confidence (>= 0.90 -> REVIEW_PENDING)
    candidate = await OntologyGovernanceManager.propose_candidate(
        session=db_session,
        tenant_id=tenant_id,
        candidate_type="ENTITY",
        proposed_payload={
            "canonical_urn": "urn:cseo:service:audit-service",
            "entity_type": CoreEntityType.SERVICE.value,
            "name": "audit-service",
            "description": "Compliance audit logging service",
            "properties": {"tier": "Tier-2"},
        },
        source_scanner="AST",
        confidence=0.92,
        evidence_refs=["ref:evidence:ast:01"],
    )
    assert candidate.review_status == CandidateReviewStatus.REVIEW_PENDING.value

    # 2. Human certification workflow
    certified_entity = await OntologyGovernanceManager.certify_candidate(
        session=db_session,
        tenant_id=tenant_id,
        candidate_id=candidate.id,
        reviewer="lead-architect@enterprise.internal",
        notes="Verified architecture review with security committee.",
    )

    assert isinstance(certified_entity, OntologyEntity)
    assert certified_entity.canonical_urn == "urn:cseo:service:audit-service"
    assert certified_entity.name == "audit-service"
    assert candidate.review_status == CandidateReviewStatus.HUMAN_CERTIFIED.value
    assert candidate.reviewed_by == "lead-architect@enterprise.internal"


@pytest.mark.asyncio
async def test_propose_candidate_low_confidence_status(db_session: AsyncSession):
    """Candidates below 0.90 confidence are assigned CANDIDATE review status."""
    candidate = await OntologyGovernanceManager.propose_candidate(
        session=db_session,
        tenant_id="tenant-gov-02",
        candidate_type="ENTITY",
        proposed_payload={
            "canonical_urn": "urn:cseo:service:experiment-service",
            "entity_type": CoreEntityType.SERVICE.value,
            "name": "experiment-service",
        },
        source_scanner="INFERENCE",
        confidence=0.75,
        evidence_refs=["ref:01"],
    )
    assert candidate.review_status == CandidateReviewStatus.CANDIDATE.value


@pytest.mark.asyncio
async def test_reject_candidate_workflow(db_session: AsyncSession):
    """Rejection records explicit reason and prevents certification without re-proposal."""
    tenant_id = "tenant-gov-03"
    candidate = await OntologyGovernanceManager.propose_candidate(
        session=db_session,
        tenant_id=tenant_id,
        candidate_type="ENTITY",
        proposed_payload={
            "canonical_urn": "urn:cseo:service:spurious-service",
            "entity_type": CoreEntityType.SERVICE.value,
            "name": "spurious-service",
        },
        source_scanner="INFERENCE",
        confidence=0.45,
        evidence_refs=["ref:01"],
    )

    # Reject
    rejected = await OntologyGovernanceManager.reject_candidate(
        session=db_session,
        tenant_id=tenant_id,
        candidate_id=candidate.id,
        reviewer="security-engineer@enterprise.internal",
        reason="Hallucinated service endpoint from deleted repository.",
    )
    assert rejected.review_status == CandidateReviewStatus.REJECTED.value

    # Attempting to certify a rejected candidate must raise ConflictError
    with pytest.raises(ConflictError) as exc:
        await OntologyGovernanceManager.certify_candidate(
            session=db_session,
            tenant_id=tenant_id,
            candidate_id=candidate.id,
            reviewer="lead-architect@enterprise.internal",
        )
    assert "Cannot certify a previously REJECTED candidate" in str(exc.value)


@pytest.mark.asyncio
async def test_record_and_resolve_dispute(db_session: AsyncSession):
    """Competing mappings are recorded as DISPUTED without discarding ambiguity, then resolved."""
    tenant_id = "tenant-gov-04"

    # Create two competing candidate mappings
    c1 = await OntologyGovernanceManager.propose_candidate(
        session=db_session,
        tenant_id=tenant_id,
        candidate_type="ENTITY",
        proposed_payload={
            "canonical_urn": "urn:cseo:concept:candidate:1",
            "entity_type": "BusinessConcept",
            "name": "ConceptA",
        },
        source_scanner="INFERENCE",
        confidence=0.70,
        evidence_refs=["ref:01"],
    )
    c2 = await OntologyGovernanceManager.propose_candidate(
        session=db_session,
        tenant_id=tenant_id,
        candidate_type="ENTITY",
        proposed_payload={
            "canonical_urn": "urn:cseo:concept:candidate:2",
            "entity_type": "BusinessConcept",
            "name": "ConceptB",
        },
        source_scanner="INFERENCE",
        confidence=0.72,
        evidence_refs=["ref:02"],
    )

    # Record dispute
    dispute = await OntologyGovernanceManager.record_dispute(
        session=db_session,
        tenant_id=tenant_id,
        entity_id_or_field="orders.account_id",
        competing_concepts=["urn:cseo:concept:auth:Account", "urn:cseo:concept:billing:Account"],
        competing_candidate_ids=[c1.id, c2.id],
    )
    assert dispute.status == "UNRESOLVED"
    assert c1.review_status == CandidateReviewStatus.DISPUTED.value
    assert c2.review_status == CandidateReviewStatus.DISPUTED.value

    # Query active disputes
    active_disputes = await OntologyGovernanceManager.list_unresolved_disputes(db_session, tenant_id)
    assert len(active_disputes) == 1
    assert active_disputes[0].id == dispute.id

    # Resolve dispute
    resolved = await OntologyGovernanceManager.resolve_dispute(
        session=db_session,
        tenant_id=tenant_id,
        dispute_id=dispute.id,
        resolution_rationale="Field orders.account_id stores customer identity UUID, not ledger balance.",
        resolved_by="principal-architect@enterprise.internal",
    )
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_by == "principal-architect@enterprise.internal"

    # Check unresolved list is now empty
    active_now = await OntologyGovernanceManager.list_unresolved_disputes(db_session, tenant_id)
    assert len(active_now) == 0


# ==============================================================================
# 4. DETERMINISTIC DIFF & VERSIONING TESTS
# ==============================================================================


def test_deterministic_ontology_diff_detection():
    """Validates structural entity/relationship additions, removals, modifications, and breaking changes."""
    prev_snapshot = {
        "entities": [
            {
                "canonical_urn": "urn:cseo:service:service-a",
                "entity_type": "Service",
                "name": "Service A",
                "description": "Old description",
                "properties": {"tier": "Tier-1"},
            },
            {
                "canonical_urn": "urn:cseo:service:service-b",
                "entity_type": "Service",
                "name": "Service B",
                "description": "To be removed",
                "properties": {},
            },
        ],
        "relationships": [
            {
                "source_urn": "urn:cseo:service:service-a",
                "target_urn": "urn:cseo:service:service-b",
                "rel_type": "DEPENDS_ON",
                "provenance": "STATIC_CONFIRMED",
                "confidence": 1.0,
                "status": "ACTIVE",
            }
        ],
    }

    curr_snapshot = {
        "entities": [
            {
                "canonical_urn": "urn:cseo:service:service-a",
                "entity_type": "Service",
                "name": "Service A",
                "description": "Updated new description",
                "properties": {"tier": "Tier-1"},
            },
            {
                "canonical_urn": "urn:cseo:service:service-c",
                "entity_type": "Service",
                "name": "Service C",
                "description": "Brand new service",
                "properties": {},
            },
        ],
        "relationships": [
            {
                "source_urn": "urn:cseo:service:service-a",
                "target_urn": "urn:cseo:service:service-c",
                "rel_type": "DEPENDS_ON",
                "provenance": "STATIC_CONFIRMED",
                "confidence": 1.0,
                "status": "ACTIVE",
            }
        ],
    }

    diff = OntologyGovernanceManager.compute_ontology_diff(prev_snapshot, curr_snapshot)

    # Invariants
    assert diff["is_breaking"] is True  # service-b and its active relationship were removed!
    assert diff["metrics"]["added_entities_count"] == 1
    assert diff["added_entities"][0]["canonical_urn"] == "urn:cseo:service:service-c"

    assert diff["metrics"]["removed_entities_count"] == 1
    assert diff["removed_entities"][0]["canonical_urn"] == "urn:cseo:service:service-b"

    assert diff["metrics"]["modified_entities_count"] == 1
    assert diff["modified_entities"][0]["canonical_urn"] == "urn:cseo:service:service-a"
    assert "description" in diff["modified_entities"][0]["changed_attributes"]

    assert diff["metrics"]["added_relationships_count"] == 1
    assert diff["metrics"]["removed_relationships_count"] == 1


@pytest.mark.asyncio
async def test_create_ontology_version_semver_enforcement(db_session: AsyncSession):
    """Enforces valid SemVer formatting and persists version records with diff summaries."""
    tenant_id = "tenant-ver-01"

    # Invalid SemVer string raises SemanticValidationError
    with pytest.raises(SemanticValidationError) as exc:
        await OntologyGovernanceManager.create_ontology_version(
            session=db_session,
            tenant_id=tenant_id,
            version="v1.0-beta",  # Missing standard SemVer without leading 'v'
            description="Initial release",
        )
    assert "not a valid Semantic Version" in str(exc.value)

    # Valid SemVer creates record
    v1 = await OntologyGovernanceManager.create_ontology_version(
        session=db_session,
        tenant_id=tenant_id,
        version="1.0.0",
        description="Baseline version 1.0.0",
    )
    assert isinstance(v1, OntologyVersionRecord)
    assert v1.version == "1.0.0"

    # Duplicate version raises ConflictError
    with pytest.raises(ConflictError) as exc2:
        await OntologyGovernanceManager.create_ontology_version(
            session=db_session,
            tenant_id=tenant_id,
            version="1.0.0",
            description="Duplicate attempt",
        )
    assert "already exists" in str(exc2.value)


# ==============================================================================
# 5. ENTERPRISE 5-MICROSERVICE TOPOLOGY SCHEMA CONFORMITY
# ==============================================================================


def test_enterprise_5services_topology_fixture_conforms():
    """Exhaustively parses and validates the reference 5-microservice enterprise topology fixture."""
    fixture_path = Path("ontology/examples/enterprise_topology_5services.json")
    assert fixture_path.exists(), f"Reference fixture missing at {fixture_path.absolute()}"

    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)

    # 1. Validate Business Concepts & Disambiguation
    concepts = data.get("business_concepts", [])
    assert len(concepts) >= 5, "Fixture must define at least 5 business concepts"
    concept_urns = {c["urn"] for c in concepts}

    # Verify both polysemic Account concepts exist
    assert "urn:cseo:concept:auth:Account" in concept_urns
    assert "urn:cseo:concept:billing:Account" in concept_urns

    for concept in concepts:
        OntologyValidator.validate_business_concept_disambiguation(
            concept_category=concept["category"],
            urn=concept["urn"],
            bounded_context=concept.get("bounded_context"),
            synonyms=concept.get("synonyms", []),
            homonym_distinctions=concept.get("homonym_distinctions", {}),
        )

    # 2. Validate Entities
    entities = data.get("entities", [])
    assert len(entities) >= 50, "Enterprise fixture must declare rich entity graph (>= 50 entities)"
    entity_urns = {e["canonical_urn"] for e in entities}
    entity_type_set = {e["entity_type"] for e in entities}

    # Verify key entity types
    for expected_type in [
        CoreEntityType.SERVICE.value,
        CoreEntityType.MODULE.value,
        CoreEntityType.FUNCTION.value,
        CoreEntityType.API_ENDPOINT.value,
        CoreEntityType.API_FIELD.value,
        CoreEntityType.EVENT_SCHEMA.value,
        CoreEntityType.DATABASE.value,
        CoreEntityType.DATABASE_TABLE.value,
        CoreEntityType.DATABASE_COLUMN.value,
        CoreEntityType.TRACE.value,
        CoreEntityType.WORKFLOW.value,
        CoreEntityType.OWNER.value,
        CoreEntityType.PERMISSION.value,
    ]:
        assert expected_type in entity_type_set, f"Entity type '{expected_type}' missing in topology"

    # 3. Validate Relationships
    relationships = data.get("relationships", [])
    assert len(relationships) >= 15, "Topology must have at least 15 relationships"
    observed_rel_types = {r["rel_type"] for r in relationships}

    # Verify all 15 canonical relationship types are represented
    for rel_type in RelationshipType:
        assert rel_type.value in observed_rel_types, f"Canonical relationship '{rel_type.value}' missing in fixture"

    # Validate each relationship against OntologyValidator rules and entity URN resolution
    for rel in relationships:
        assert rel["source_urn"] in entity_urns, f"Relationship source '{rel['source_urn']}' not defined in entities"
        assert rel["target_urn"] in entity_urns, f"Relationship target '{rel['target_urn']}' not defined in entities"
        first_obs = datetime.fromisoformat(rel["first_observed_at"].replace("Z", "+00:00"))
        last_obs = datetime.fromisoformat(rel["last_observed_at"].replace("Z", "+00:00"))
        valid_from = datetime.fromisoformat(rel["valid_from"].replace("Z", "+00:00"))
        valid_to = datetime.fromisoformat(rel["valid_to"].replace("Z", "+00:00")) if rel.get("valid_to") else None

        OntologyValidator.validate_relationship(
            rel_type=rel["rel_type"],
            source_type=rel["source_type"],
            target_type=rel["target_type"],
            provenance=rel["provenance"],
            confidence=rel["confidence"],
            first_observed_at=first_obs,
            last_observed_at=last_obs,
            valid_from=valid_from,
            valid_to=valid_to,
            evidence_refs=rel.get("evidence_refs"),
        )
