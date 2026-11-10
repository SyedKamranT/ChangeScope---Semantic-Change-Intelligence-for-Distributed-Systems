"""Local Hermetic Ontology Provider for ChangeScope.

Enables the entire application, test suite, and benchmarks to execute without
external network connectivity, third-party containers, or NVIDIA credentials.
"""

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.contracts.ontology_validator import OntologyValidator
from packages.shared.database import async_session_factory
from packages.shared.errors import NotFoundError, SemanticValidationError
from packages.shared.models import utc_now
from packages.shared.ontology.base import (
    CandidateDiscoveryResult,
    CertificationResult,
    ConceptReconciliationResult,
    ModelExportResult,
    ModelImportResult,
    OntologyProvider,
    ProviderStatus,
    RelationshipResolutionResult,
    ValidationResult,
)
from packages.shared.ontology.ossie_serializer import OssieSerializer
from packages.shared.ontology_governance import OntologyGovernanceManager
from packages.shared.ontology_models import (
    BusinessConceptEntity,
    CandidateReviewStatus,
    OntologyCandidate,
    OntologyEntity,
    OntologyRelationship,
    RelationshipStatus,
)


class LocalOntologyProvider(OntologyProvider):
    """Hermetic local ontology provider backed by ChangeScope's canonical relational storage."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession] | None = None) -> None:
        self.session_maker = session_maker or async_session_factory

    async def discover_candidates(
        self,
        tenant_id: str,
        scope: dict[str, Any] | None = None,
    ) -> CandidateDiscoveryResult:
        """Discovers uncertified entity and relationship candidates from local store or provided scope."""
        async with self.session_maker() as session:
            stmt = select(OntologyCandidate).where(
                OntologyCandidate.tenant_id == tenant_id,
                OntologyCandidate.review_status.in_(
                    [CandidateReviewStatus.CANDIDATE.value, CandidateReviewStatus.REVIEW_PENDING.value]
                ),
            )
            res = await session.execute(stmt)
            candidates = list(res.scalars().all())

            payloads: list[dict[str, Any]] = [
                {
                    "candidate_id": c.id,
                    "candidate_type": c.candidate_type,
                    "proposed_payload": c.proposed_payload,
                    "source_scanner": c.source_scanner,
                    "confidence": c.confidence,
                    "evidence_refs": c.evidence_refs,
                    "review_status": c.review_status,
                }
                for c in candidates
            ]

            # Ingest any raw uncertified candidates from scope
            if scope and "raw_candidates" in scope:
                for raw in scope["raw_candidates"]:
                    cand = await OntologyGovernanceManager.propose_candidate(
                        session=session,
                        tenant_id=tenant_id,
                        candidate_type=raw.get("candidate_type", "ENTITY"),
                        proposed_payload=raw.get("proposed_payload", {}),
                        source_scanner=raw.get("source_scanner", "AST"),
                        confidence=float(raw.get("confidence", 0.8)),
                        evidence_refs=raw.get("evidence_refs", []),
                    )
                    payloads.append(
                        {
                            "candidate_id": cand.id,
                            "candidate_type": cand.candidate_type,
                            "proposed_payload": cand.proposed_payload,
                            "source_scanner": cand.source_scanner,
                            "confidence": cand.confidence,
                            "evidence_refs": cand.evidence_refs,
                            "review_status": cand.review_status,
                        }
                    )
                await session.commit()

            return CandidateDiscoveryResult(
                tenant_id=tenant_id,
                discovered_candidates=payloads,
                total_count=len(payloads),
                status="COMPLETED",
            )

    async def reconcile_concepts(
        self,
        tenant_id: str,
        term_candidates: list[dict[str, Any]],
    ) -> ConceptReconciliationResult:
        """Reconciles terms against canonical business concepts, separating synonyms and polysemic contexts."""
        async with self.session_maker() as session:
            # Fetch existing canonical business concepts
            stmt = select(BusinessConceptEntity).where(BusinessConceptEntity.tenant_id == tenant_id)
            concepts = list((await session.execute(stmt)).scalars().all())

            reconciled: list[dict[str, Any]] = []
            synonym_matches: list[dict[str, Any]] = []
            polysemic_distinctions: list[dict[str, Any]] = []
            unresolved_disputes: list[dict[str, Any]] = []

            for term in term_candidates:
                term_name = term.get("term", "").lower()
                bcontext = term.get("bounded_context")
                field_id = term.get("field_id", term_name)

                matching_concepts: list[BusinessConceptEntity] = []

                for c in concepts:
                    c_synonyms = [s.lower() for s in c.synonyms]
                    if term_name == c.name.lower() or term_name in c_synonyms:
                        matching_concepts.append(c)

                if len(matching_concepts) == 1:
                    matched = matching_concepts[0]
                    # Check if synonym match
                    if term_name in [s.lower() for s in matched.synonyms]:
                        synonym_matches.append(
                            {
                                "term": term_name,
                                "matched_concept_urn": matched.urn,
                                "concept_name": matched.name,
                            }
                        )
                    reconciled.append(
                        {
                            "term": term_name,
                            "concept_urn": matched.urn,
                            "bounded_context": matched.bounded_context,
                            "confidence": 1.0,
                        }
                    )
                elif len(matching_concepts) > 1:
                    # Polysemy detected! Check bounded context
                    resolved_by_context = False
                    if bcontext:
                        for c in matching_concepts:
                            if c.bounded_context == bcontext:
                                polysemic_distinctions.append(
                                    {
                                        "term": term_name,
                                        "bounded_context": bcontext,
                                        "matched_concept_urn": c.urn,
                                        "concept_name": c.name,
                                    }
                                )
                                reconciled.append(
                                    {
                                        "term": term_name,
                                        "concept_urn": c.urn,
                                        "bounded_context": bcontext,
                                        "confidence": 0.95,
                                    }
                                )
                                resolved_by_context = True
                                break

                    if not resolved_by_context:
                        # Ambiguity cannot be resolved: persist dispute!
                        dispute = await OntologyGovernanceManager.record_dispute(
                            session=session,
                            tenant_id=tenant_id,
                            entity_id_or_field=field_id,
                            competing_concepts=[c.urn for c in matching_concepts],
                        )
                        unresolved_disputes.append(
                            {
                                "field_id": field_id,
                                "dispute_id": dispute.id,
                                "competing_concepts": dispute.competing_concepts,
                            }
                        )

            await session.commit()

            conf_score = 1.0 if not unresolved_disputes else 0.85
            return ConceptReconciliationResult(
                tenant_id=tenant_id,
                reconciled_concepts=reconciled,
                synonym_matches=synonym_matches,
                polysemic_distinctions=polysemic_distinctions,
                unresolved_disputes=unresolved_disputes,
                confidence_score=conf_score,
            )

    async def resolve_relationships(
        self,
        tenant_id: str,
        entities: list[dict[str, Any]],
    ) -> RelationshipResolutionResult:
        """Validates and resolves candidate structural relationships against the 15-type constraint matrix."""
        resolved: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        errors: list[str] = []

        now = utc_now()
        for rel in entities:
            rel_type = rel.get("rel_type", "")
            src_type = rel.get("source_type", "")
            tgt_type = rel.get("target_type", "")
            prov = rel.get("provenance", "STATIC_CONFIRMED")
            conf = float(rel.get("confidence", 1.0))
            refs = rel.get("evidence_refs", ["ref:01"])

            try:
                OntologyValidator.validate_relationship(
                    rel_type=rel_type,
                    source_type=src_type,
                    target_type=tgt_type,
                    provenance=prov,
                    confidence=conf,
                    first_observed_at=now,
                    last_observed_at=now,
                    valid_from=now,
                    evidence_refs=refs,
                )
                resolved.append(rel)
            except SemanticValidationError as err:
                rejected.append(rel)
                errors.append(str(err))

        return RelationshipResolutionResult(
            tenant_id=tenant_id,
            resolved_relationships=resolved,
            rejected_relationships=rejected,
            validation_errors=errors,
        )

    async def validate_definition(
        self,
        tenant_id: str,
        definition: dict[str, Any],
    ) -> ValidationResult:
        """Validates relationship or business concept definitions against ontological invariants."""
        errors: list[str] = []
        warnings: list[str] = []
        now = utc_now()

        if "rel_type" in definition:
            try:
                OntologyValidator.validate_relationship(
                    rel_type=definition["rel_type"],
                    source_type=definition.get("source_type", ""),
                    target_type=definition.get("target_type", ""),
                    provenance=definition.get("provenance", "STATIC_CONFIRMED"),
                    confidence=float(definition.get("confidence", 1.0)),
                    first_observed_at=definition.get("first_observed_at", now),
                    last_observed_at=definition.get("last_observed_at", now),
                    valid_from=definition.get("valid_from", now),
                    evidence_refs=definition.get("evidence_refs"),
                )
            except SemanticValidationError as err:
                errors.append(str(err))
        elif "category" in definition and "urn" in definition:
            try:
                OntologyValidator.validate_business_concept_disambiguation(
                    concept_category=definition["category"],
                    urn=definition["urn"],
                    bounded_context=definition.get("bounded_context"),
                    synonyms=definition.get("synonyms", []),
                    homonym_distinctions=definition.get("homonym_distinctions", {}),
                )
            except SemanticValidationError as err:
                errors.append(str(err))
        else:
            warnings.append("Definition does not declare a recognizable relationship or concept schema.")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details={"definition": definition},
        )

    async def certify_definition(
        self,
        tenant_id: str,
        candidate_id: str,
        reviewer: str,
        notes: str | None = None,
    ) -> CertificationResult:
        """Promotes an untrusted candidate to HUMAN_CERTIFIED in canonical relational models."""
        async with self.session_maker() as session:
            try:
                materialized = await OntologyGovernanceManager.certify_candidate(
                    session=session,
                    tenant_id=tenant_id,
                    candidate_id=candidate_id,
                    reviewer=reviewer,
                    notes=notes,
                )
                await session.commit()
                return CertificationResult(
                    success=True,
                    candidate_id=candidate_id,
                    review_status=CandidateReviewStatus.HUMAN_CERTIFIED.value,
                    entity_or_rel_id=materialized.id,
                    reviewed_by=reviewer,
                    reviewed_at=datetime.now(UTC).isoformat(),
                    notes=notes,
                )
            except (NotFoundError, SemanticValidationError) as err:
                await session.rollback()
                return CertificationResult(
                    success=False,
                    candidate_id=candidate_id,
                    review_status="FAILED",
                    reviewed_by=reviewer,
                    reviewed_at=datetime.now(UTC).isoformat(),
                    notes=f"Certification failed: {err}",
                )

    async def import_model(
        self,
        tenant_id: str,
        payload: str | dict[str, Any],
        format: str = "ossie_yaml",
    ) -> ModelImportResult:
        """Imports model definition in Apache Ossie YAML or CSEO JSON-LD."""
        errors: list[str] = []
        warnings: list[str] = []

        if format == "ossie_yaml":
            yaml_str = payload if isinstance(payload, str) else str(payload)
            parsed = OssieSerializer.from_ossie_yaml(yaml_str)
        elif format == "cseo_json":
            parsed = payload if isinstance(payload, dict) else {}
        else:
            return ModelImportResult(
                success=False,
                format=format,
                errors=[f"Unsupported import format '{format}'. Supported: 'ossie_yaml', 'cseo_json'."],
            )

        entities = parsed.get("entities", [])
        relationships = parsed.get("relationships", [])
        concepts = parsed.get("business_concepts", [])

        async with self.session_maker() as session:
            # 1. Ingest Business Concepts
            imported_concepts = 0
            for c in concepts:
                c_stmt = select(BusinessConceptEntity).where(
                    BusinessConceptEntity.tenant_id == tenant_id,
                    BusinessConceptEntity.urn == c["urn"],
                )
                existing_c = (await session.execute(c_stmt)).scalar_one_or_none()
                if not existing_c:
                    new_concept = BusinessConceptEntity(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        urn=c["urn"],
                        name=c["name"],
                        category=c["category"],
                        bounded_context=c.get("bounded_context"),
                        description=c.get("description"),
                        synonyms=c.get("synonyms", []),
                        homonym_distinctions=c.get("homonym_distinctions", {}),
                        constraints_payload=c.get("constraints", {}),
                        created_at=utc_now(),
                    )
                    session.add(new_concept)
                    imported_concepts += 1

            # 2. Ingest Entities
            imported_entities = 0
            for e in entities:
                e_stmt = select(OntologyEntity).where(
                    OntologyEntity.tenant_id == tenant_id,
                    OntologyEntity.canonical_urn == e["canonical_urn"],
                )
                existing_e = (await session.execute(e_stmt)).scalar_one_or_none()
                if not existing_e:
                    new_e = OntologyEntity(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        entity_type=e["entity_type"],
                        canonical_urn=e["canonical_urn"],
                        name=e["name"],
                        description=e.get("description"),
                        properties_payload=e.get("properties", {}),
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    session.add(new_e)
                    imported_entities += 1

            await session.flush()

            # Build entity urn to id mapping
            all_e_stmt = select(OntologyEntity).where(OntologyEntity.tenant_id == tenant_id)
            all_entities = list((await session.execute(all_e_stmt)).scalars().all())
            urn_to_id = {ent.canonical_urn: ent.id for ent in all_entities}

            # 3. Ingest Relationships
            imported_rels = 0
            now = utc_now()
            for r in relationships:
                src_urn = r.get("source_urn")
                tgt_urn = r.get("target_urn")
                src_id = urn_to_id.get(src_urn)
                tgt_id = urn_to_id.get(tgt_urn)

                if src_id and tgt_id:
                    new_rel = OntologyRelationship(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        source_id=src_id,
                        target_id=tgt_id,
                        rel_type=r["rel_type"],
                        source_repo_version_id=r.get("source_repo_version"),
                        evidence_refs=r.get("evidence_refs", []),
                        provenance=r.get("provenance", "STATIC_CONFIRMED"),
                        confidence=float(r.get("confidence", 1.0)),
                        first_observed_at=now,
                        last_observed_at=now,
                        valid_from=now,
                        status=RelationshipStatus.ACTIVE.value,
                        created_at=now,
                    )
                    session.add(new_rel)
                    imported_rels += 1
                else:
                    warnings.append(
                        f"Skipping relationship {src_urn} -> {tgt_urn}: entity endpoints not found in tenant."
                    )

            await session.commit()

        return ModelImportResult(
            success=True,
            format=format,
            imported_entities_count=imported_entities,
            imported_relationships_count=imported_rels,
            imported_concepts_count=imported_concepts,
            errors=errors,
            warnings=warnings,
        )

    async def export_model(
        self,
        tenant_id: str,
        format: str = "ossie_yaml",
    ) -> ModelExportResult:
        """Exports ChangeScope's knowledge graph into Apache Ossie YAML or CSEO JSON-LD."""
        async with self.session_maker() as session:
            e_stmt = select(OntologyEntity).where(OntologyEntity.tenant_id == tenant_id)
            entities = list((await session.execute(e_stmt)).scalars().all())

            r_stmt = select(OntologyRelationship).where(
                OntologyRelationship.tenant_id == tenant_id,
                OntologyRelationship.status == RelationshipStatus.ACTIVE.value,
            )
            relationships = list((await session.execute(r_stmt)).scalars().all())

            c_stmt = select(BusinessConceptEntity).where(BusinessConceptEntity.tenant_id == tenant_id)
            concepts = list((await session.execute(c_stmt)).scalars().all())

            id_to_urn = {ent.id: ent.canonical_urn for ent in entities}

            ent_dicts: list[dict[str, Any]] = [
                {
                    "canonical_urn": ent.canonical_urn,
                    "entity_type": ent.entity_type,
                    "name": ent.name,
                    "description": ent.description,
                    "properties": ent.properties_payload,
                }
                for ent in entities
            ]

            rel_dicts: list[dict[str, Any]] = [
                {
                    "id": rel.id,
                    "source_urn": id_to_urn.get(rel.source_id, rel.source_id),
                    "target_urn": id_to_urn.get(rel.target_id, rel.target_id),
                    "rel_type": rel.rel_type,
                    "provenance": rel.provenance,
                    "confidence": rel.confidence,
                    "status": rel.status,
                    "evidence_refs": rel.evidence_refs,
                    "source_repo_version": rel.source_repo_version_id,
                }
                for rel in relationships
            ]

            concept_dicts: list[dict[str, Any]] = [
                {
                    "urn": c.urn,
                    "name": c.name,
                    "category": c.category,
                    "bounded_context": c.bounded_context,
                    "description": c.description,
                    "synonyms": c.synonyms,
                    "homonym_distinctions": c.homonym_distinctions,
                    "constraints": c.constraints_payload,
                }
                for c in concepts
            ]

            if format == "ossie_yaml":
                payload = OssieSerializer.to_ossie_yaml(
                    model_name=f"ChangeScope-Tenant-{tenant_id}",
                    description=f"Exported software ontology for tenant {tenant_id}",
                    entities=ent_dicts,
                    relationships=rel_dicts,
                    concepts=concept_dicts,
                )
            else:
                import json

                payload = json.dumps(
                    {
                        "entities": ent_dicts,
                        "relationships": rel_dicts,
                        "concepts": concept_dicts,
                    },
                    indent=2,
                )

            return ModelExportResult(
                success=True,
                format=format,
                payload=payload,
                exported_entities_count=len(ent_dicts),
                exported_relationships_count=len(rel_dicts),
                exported_concepts_count=len(concept_dicts),
            )

    async def get_status(self) -> ProviderStatus:
        """Returns health and availability diagnostics."""
        start = time.perf_counter()
        async with self.session_maker() as session:
            # Simple ping
            await session.execute(select(1))
        latency = (time.perf_counter() - start) * 1000.0

        return ProviderStatus(
            provider_name="LocalOntologyProvider",
            is_healthy=True,
            is_available=True,
            deployment_type="local_in_memory",
            circuit_breaker=None,
            latency_ms=round(latency, 2),
            details={"storage": "canonical_relational_session", "mode": "hermetic"},
        )
