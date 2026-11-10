"""Integration tests for ChangeScope's LocalOntologyProvider.

Verifies:
- Hermetic provider health diagnostics.
- Candidate discovery.
- Concept reconciliation (synonym mapping and polysemy disambiguation via bounded contexts).
- Unresolved dispute recording when polysemic ambiguity is present.
- Relationship typing matrix validation and rejection of invalid types.
- Human review and certification transitions.
- Full bidirectional Apache Ossie YAML serialization, export, and import roundtrip.
"""

from typing import Any

import pytest
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.database import async_session_factory
from packages.shared.models import utc_now
from packages.shared.ontology.local_provider import LocalOntologyProvider
from packages.shared.ontology_models import (
    BusinessConceptEntity,
    CandidateReviewStatus,
    CoreEntityType,
    OntologyCandidate,
    ProvenanceType,
    RelationshipType,
    SemanticConceptCategory,
)


@pytest.fixture
async def db_session():
    """Provides isolated transactional async database session."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def local_provider():
    """Initializes LocalOntologyProvider bound to standard session factory."""
    return LocalOntologyProvider()


@pytest.mark.asyncio
async def test_local_provider_status(local_provider: LocalOntologyProvider):
    """Verifies that local provider reports healthy status with measurable latency."""
    status = await local_provider.get_status()
    assert status.is_healthy is True
    assert status.is_available is True
    assert status.provider_name == "LocalOntologyProvider"
    assert status.deployment_type == "local_in_memory"
    assert status.latency_ms is not None
    assert status.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_local_provider_candidate_discovery(db_session: AsyncSession, local_provider: LocalOntologyProvider):
    """Verifies candidate discovery from local store and raw scope."""
    tenant_id = "tenant-prov-disc-01"

    # Pre-seed a candidate in DB
    cand1 = OntologyCandidate(
        id="cand-local-01",
        tenant_id=tenant_id,
        candidate_type="ENTITY",
        proposed_payload={"canonical_urn": "urn:cseo:service:billing", "entity_type": "Service", "name": "billing"},
        source_scanner="AST",
        confidence=0.91,
        evidence_refs=["ref:01"],
        review_status=CandidateReviewStatus.REVIEW_PENDING.value,
        created_at=utc_now(),
    )
    db_session.add(cand1)
    await db_session.commit()

    # Discover without scope
    res1 = await local_provider.discover_candidates(tenant_id)
    assert res1.total_count == 1
    assert res1.discovered_candidates[0]["candidate_id"] == "cand-local-01"

    # Discover with raw candidates in scope
    res2 = await local_provider.discover_candidates(
        tenant_id,
        scope={
            "raw_candidates": [
                {
                    "candidate_type": "ENTITY",
                    "proposed_payload": {
                        "canonical_urn": "urn:cseo:service:orders",
                        "entity_type": "Service",
                        "name": "orders",
                    },
                    "source_scanner": "SPEC",
                    "confidence": 0.85,
                    "evidence_refs": ["ref:02"],
                }
            ]
        },
    )
    assert res2.total_count == 2


@pytest.mark.asyncio
async def test_local_provider_concept_reconciliation(db_session: AsyncSession, local_provider: LocalOntologyProvider):
    """Verifies synonym resolution, bounded context polysemic disambiguation, and dispute preservation."""
    tenant_id = "tenant-prov-reconcile-01"

    # 1. Seed canonical concepts
    cust_id_concept = BusinessConceptEntity(
        id="concept-cust-id",
        tenant_id=tenant_id,
        urn="urn:cseo:concept:CustomerIdentifier",
        name="CustomerIdentifier",
        category=SemanticConceptCategory.IDENTIFIER.value,
        bounded_context="global",
        synonyms=["customer_id", "buyer_uuid", "account_holder_uuid"],
        created_at=utc_now(),
    )
    auth_account = BusinessConceptEntity(
        id="concept-auth-acc",
        tenant_id=tenant_id,
        urn="urn:cseo:concept:auth:Account",
        name="Account",
        category=SemanticConceptCategory.ACCOUNT.value,
        bounded_context="auth",
        synonyms=["user_account", "principal"],
        homonym_distinctions={"billing": "Ledger Account"},
        created_at=utc_now(),
    )
    billing_account = BusinessConceptEntity(
        id="concept-bill-acc",
        tenant_id=tenant_id,
        urn="urn:cseo:concept:billing:Account",
        name="Account",
        category=SemanticConceptCategory.ACCOUNT.value,
        bounded_context="billing",
        synonyms=["ledger_account", "wallet"],
        homonym_distinctions={"auth": "Identity Account"},
        created_at=utc_now(),
    )
    db_session.add_all([cust_id_concept, auth_account, billing_account])
    await db_session.commit()

    # 2. Reconcile terms:
    # - "buyer_uuid": should resolve to CustomerIdentifier via synonym
    # - "account" with bounded_context="auth": should resolve to auth:Account
    # - "account" without bounded_context: should be detected as polysemic dispute!
    terms_to_test: list[dict[str, Any]] = [
        {"term": "buyer_uuid", "field_id": "orders.buyer_uuid"},
        {"term": "account", "bounded_context": "auth", "field_id": "auth.user_id"},
        {"term": "account", "field_id": "unknown.account_ref"},  # Ambiguous!
    ]

    result = await local_provider.reconcile_concepts(tenant_id, terms_to_test)

    # Invariants
    assert len(result.synonym_matches) == 1
    assert result.synonym_matches[0]["matched_concept_urn"] == "urn:cseo:concept:CustomerIdentifier"

    assert len(result.polysemic_distinctions) == 1
    assert result.polysemic_distinctions[0]["matched_concept_urn"] == "urn:cseo:concept:auth:Account"

    # Crucial: Unresolved ambiguity must NOT be discarded
    assert len(result.unresolved_disputes) == 1
    assert result.unresolved_disputes[0]["field_id"] == "unknown.account_ref"
    assert "urn:cseo:concept:auth:Account" in result.unresolved_disputes[0]["competing_concepts"]
    assert "urn:cseo:concept:billing:Account" in result.unresolved_disputes[0]["competing_concepts"]


@pytest.mark.asyncio
async def test_local_provider_relationship_resolution(local_provider: LocalOntologyProvider):
    """Verifies that valid relationships are accepted and invalid relationship domains/ranges are rejected."""
    tenant_id = "tenant-prov-rels-01"

    relationships_batch = [
        {
            "rel_type": RelationshipType.CALLS.value,
            "source_type": CoreEntityType.SERVICE.value,
            "target_type": CoreEntityType.API_ENDPOINT.value,
            "provenance": ProvenanceType.STATIC_CONFIRMED.value,
            "confidence": 1.0,
            "evidence_refs": ["ref:ast:01"],
        },
        {
            "rel_type": RelationshipType.MAPS_TO.value,
            "source_type": CoreEntityType.DATABASE.value,  # Invalid: Database cannot MAPS_TO
            "target_type": CoreEntityType.BUSINESS_CONCEPT.value,
            "provenance": ProvenanceType.ONTOLOGY_INFERRED.value,
            "confidence": 0.85,
            "evidence_refs": ["ref:ast:02"],
        },
    ]

    res = await local_provider.resolve_relationships(tenant_id, relationships_batch)
    assert len(res.resolved_relationships) == 1
    assert res.resolved_relationships[0]["rel_type"] == RelationshipType.CALLS.value
    assert len(res.rejected_relationships) == 1
    assert len(res.validation_errors) == 1
    assert "cannot originate from source type 'Database'" in res.validation_errors[0]


@pytest.mark.asyncio
async def test_local_provider_validate_and_certify(db_session: AsyncSession, local_provider: LocalOntologyProvider):
    """Verifies validation and human certification lifecycle."""
    tenant_id = "tenant-prov-cert-01"

    # Validation check: Valid relationship
    val_res = await local_provider.validate_definition(
        tenant_id,
        {
            "rel_type": RelationshipType.DEPENDS_ON.value,
            "source_type": CoreEntityType.SERVICE.value,
            "target_type": CoreEntityType.SERVICE.value,
            "provenance": ProvenanceType.HUMAN_CERTIFIED.value,
            "confidence": 1.0,
        },
    )
    assert val_res.is_valid is True

    # Seed candidate to certify
    cand = OntologyCandidate(
        id="cand-cert-01",
        tenant_id=tenant_id,
        candidate_type="ENTITY",
        proposed_payload={
            "canonical_urn": "urn:cseo:service:payment-processor",
            "entity_type": CoreEntityType.SERVICE.value,
            "name": "payment-processor",
        },
        source_scanner="SPEC",
        confidence=0.95,
        evidence_refs=["ref:01"],
        review_status=CandidateReviewStatus.REVIEW_PENDING.value,
        created_at=utc_now(),
    )
    db_session.add(cand)
    await db_session.commit()

    # Certify candidate
    cert_res = await local_provider.certify_definition(
        tenant_id=tenant_id,
        candidate_id="cand-cert-01",
        reviewer="lead-architect@enterprise.internal",
        notes="Approved during architecture review.",
    )
    assert cert_res.success is True
    assert cert_res.review_status == CandidateReviewStatus.HUMAN_CERTIFIED.value
    assert cert_res.entity_or_rel_id is not None


@pytest.mark.asyncio
async def test_local_provider_ossie_yaml_roundtrip(db_session: AsyncSession, local_provider: LocalOntologyProvider):
    """Verifies complete export to Apache Ossie YAML and subsequent import into a new tenant."""
    source_tenant = "tenant-prov-ossie-src"
    target_tenant = "tenant-prov-ossie-tgt"

    # 1. Ingest entities in source tenant
    service_payload = {
        "entities": [
            {
                "canonical_urn": "urn:cseo:service:order-svc",
                "entity_type": "Service",
                "name": "order-svc",
                "description": "Order placement service",
                "properties": {"tier": "Tier-1", "runtime": "python/fastapi"},
            },
            {
                "canonical_urn": "urn:cseo:endpoint:order-svc:post_orders",
                "entity_type": "APIEndpoint",
                "name": "POST /orders",
                "description": "Endpoint for checkout",
                "properties": {"http_method": "POST", "path": "/orders"},
            },
        ],
        "relationships": [
            {
                "id": "rel-order-calls-ep",
                "source_urn": "urn:cseo:service:order-svc",
                "source_type": "Service",
                "target_urn": "urn:cseo:endpoint:order-svc:post_orders",
                "target_type": "APIEndpoint",
                "rel_type": "CALLS",
                "provenance": "STATIC_CONFIRMED",
                "confidence": 1.0,
                "evidence_refs": ["ref:ast:01"],
            }
        ],
        "business_concepts": [
            {
                "urn": "urn:cseo:concept:CustomerIdentifier",
                "name": "CustomerIdentifier",
                "category": "Identifier",
                "bounded_context": "global",
                "description": "Unique customer ID",
                "synonyms": ["customer_id", "buyer_id"],
                "homonym_distinctions": {},
                "constraints": {"format": "uuid"},
            }
        ],
    }

    import_res1 = await local_provider.import_model(source_tenant, service_payload, format="cseo_json")
    assert import_res1.success is True
    assert import_res1.imported_entities_count == 2
    assert import_res1.imported_relationships_count == 1
    assert import_res1.imported_concepts_count == 1

    # 2. Export source tenant as Apache Ossie YAML
    export_res = await local_provider.export_model(source_tenant, format="ossie_yaml")
    assert export_res.success is True
    assert export_res.format == "ossie_yaml"
    assert (
        "version: '1.0'" in export_res.payload
        or "version: 1.0" in export_res.payload
        or 'version: "1.0"' in export_res.payload
    )
    assert "datasets:" in export_res.payload
    assert "relationships:" in export_res.payload
    assert "concepts:" in export_res.payload

    # Parse raw YAML to confirm structure
    ossie_doc = yaml.safe_load(export_res.payload)
    assert ossie_doc["standard"] == "Apache Ossie (incubating)"
    assert len(ossie_doc["datasets"]) == 2
    assert len(ossie_doc["relationships"]) == 1
    assert len(ossie_doc["concepts"]) == 1

    # 3. Import the generated Ossie YAML into the target tenant
    import_res2 = await local_provider.import_model(target_tenant, export_res.payload, format="ossie_yaml")
    assert import_res2.success is True
    assert import_res2.imported_entities_count == 2
    assert import_res2.imported_relationships_count == 1
    assert import_res2.imported_concepts_count == 1

    # 4. Verify target tenant has the same entities by re-exporting
    target_export = await local_provider.export_model(target_tenant, format="ossie_yaml")
    assert target_export.exported_entities_count == 2
    assert target_export.exported_relationships_count == 1
    assert target_export.exported_concepts_count == 1
