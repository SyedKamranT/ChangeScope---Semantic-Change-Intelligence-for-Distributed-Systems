"""Ontology Governance Workflow, Dispute Resolution, and SemVer Diff Engine for ChangeScope."""

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.contracts.ontology_validator import OntologyValidator
from packages.shared.errors import ConflictError, NotFoundError, SemanticValidationError
from packages.shared.models import utc_now
from packages.shared.ontology_models import (
    CandidateReviewStatus,
    OntologyCandidate,
    OntologyDispute,
    OntologyEntity,
    OntologyRelationship,
    OntologyVersionRecord,
    ProvenanceType,
    RelationshipStatus,
)

SEMVER_REGEX = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


class OntologyGovernanceManager:
    """Orchestrates candidate proposals, human certification, dispute preservation, and SemVer diffing."""

    @classmethod
    async def propose_candidate(
        cls,
        session: AsyncSession,
        tenant_id: str,
        candidate_type: str,
        proposed_payload: dict[str, Any],
        source_scanner: str,
        confidence: float,
        evidence_refs: list[str] | None = None,
    ) -> OntologyCandidate:
        """Records an untrusted machine-generated entity or relationship proposal."""
        if candidate_type not in {"ENTITY", "RELATIONSHIP"}:
            raise SemanticValidationError(
                f"Invalid candidate_type '{candidate_type}'. Must be 'ENTITY' or 'RELATIONSHIP'."
            )

        if not (0.0 <= confidence <= 1.0):
            raise SemanticValidationError(f"Confidence score {confidence} must be between 0.0 and 1.0.")

        refs = evidence_refs or []

        # Pre-validate relationship payload if proposing a relationship
        if candidate_type == "RELATIONSHIP":
            required_keys = {"source_type", "target_type", "rel_type", "provenance"}
            missing = required_keys - set(proposed_payload.keys())
            if missing:
                raise SemanticValidationError(f"Proposed relationship payload missing required keys: {sorted(missing)}")

            OntologyValidator.validate_relationship(
                rel_type=proposed_payload["rel_type"],
                source_type=proposed_payload["source_type"],
                target_type=proposed_payload["target_type"],
                provenance=proposed_payload["provenance"],
                confidence=confidence,
                first_observed_at=utc_now(),
                last_observed_at=utc_now(),
                valid_from=utc_now(),
                evidence_refs=refs,
            )

        # Invariant: Machine candidates with confidence >= 0.90 are REVIEW_PENDING; below are CANDIDATE.
        # Neither is automatically trusted.
        status = (
            CandidateReviewStatus.REVIEW_PENDING.value if confidence >= 0.90 else CandidateReviewStatus.CANDIDATE.value
        )

        candidate = OntologyCandidate(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            candidate_type=candidate_type,
            proposed_payload=proposed_payload,
            source_scanner=source_scanner,
            confidence=confidence,
            evidence_refs=refs,
            review_status=status,
            created_at=utc_now(),
        )
        session.add(candidate)
        await session.flush()
        return candidate

    @classmethod
    async def certify_candidate(
        cls,
        session: AsyncSession,
        tenant_id: str,
        candidate_id: str,
        reviewer: str,
        notes: str | None = None,
    ) -> OntologyEntity | OntologyRelationship:
        """Human certification workflow: reviews and promotes a candidate into the canonical graph."""
        stmt = select(OntologyCandidate).where(
            OntologyCandidate.tenant_id == tenant_id,
            OntologyCandidate.id == candidate_id,
        )
        res = await session.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            raise NotFoundError(f"OntologyCandidate '{candidate_id}' not found for tenant '{tenant_id}'.")

        if candidate.review_status == CandidateReviewStatus.REJECTED.value:
            raise ConflictError("Cannot certify a previously REJECTED candidate without re-proposal.")

        # Update candidate state
        candidate.review_status = CandidateReviewStatus.HUMAN_CERTIFIED.value
        candidate.reviewed_by = reviewer
        candidate.review_notes = notes
        candidate.reviewed_at = utc_now()

        payload = candidate.proposed_payload

        if candidate.candidate_type == "ENTITY":
            entity_urn = payload["canonical_urn"]
            # Check if entity already exists
            ent_stmt = select(OntologyEntity).where(
                OntologyEntity.tenant_id == tenant_id,
                OntologyEntity.canonical_urn == entity_urn,
            )
            ent_res = await session.execute(ent_stmt)
            existing_ent = ent_res.scalar_one_or_none()

            if existing_ent:
                existing_ent.name = payload.get("name", existing_ent.name)
                existing_ent.description = payload.get("description", existing_ent.description)
                existing_ent.properties_payload = payload.get("properties", existing_ent.properties_payload)
                existing_ent.updated_at = utc_now()
                await session.flush()
                return existing_ent
            else:
                entity = OntologyEntity(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    entity_type=payload["entity_type"],
                    canonical_urn=entity_urn,
                    name=payload["name"],
                    description=payload.get("description"),
                    repository_id=payload.get("repository_id"),
                    properties_payload=payload.get("properties", {}),
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                session.add(entity)
                await session.flush()
                return entity

        elif candidate.candidate_type == "RELATIONSHIP":
            # Human certification promotes provenance to HUMAN_CERTIFIED with confidence 1.0
            source_id = payload["source_id"]
            target_id = payload["target_id"]
            rel_type = payload["rel_type"]

            # Validate entities exist
            src_stmt = select(OntologyEntity).where(
                OntologyEntity.tenant_id == tenant_id,
                OntologyEntity.id == source_id,
            )
            tgt_stmt = select(OntologyEntity).where(
                OntologyEntity.tenant_id == tenant_id,
                OntologyEntity.id == target_id,
            )
            src_ent = (await session.execute(src_stmt)).scalar_one_or_none()
            tgt_ent = (await session.execute(tgt_stmt)).scalar_one_or_none()

            if not src_ent or not tgt_ent:
                raise NotFoundError("Source or target entity not found in tenant for relationship certification.")

            # Validate relationship constraints
            now = utc_now()
            OntologyValidator.validate_relationship(
                rel_type=rel_type,
                source_type=src_ent.entity_type,
                target_type=tgt_ent.entity_type,
                provenance=ProvenanceType.HUMAN_CERTIFIED.value,
                confidence=1.0,
                first_observed_at=now,
                last_observed_at=now,
                valid_from=now,
                evidence_refs=candidate.evidence_refs,
            )

            rel = OntologyRelationship(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                source_id=source_id,
                target_id=target_id,
                rel_type=rel_type,
                source_repo_version_id=payload.get("source_repo_version_id"),
                evidence_refs=candidate.evidence_refs,
                provenance=ProvenanceType.HUMAN_CERTIFIED.value,
                confidence=1.0,
                first_observed_at=now,
                last_observed_at=now,
                valid_from=now,
                status=RelationshipStatus.ACTIVE.value,
                metadata_payload=payload.get("metadata", {}),
                created_at=now,
            )
            session.add(rel)
            await session.flush()
            return rel

        raise SemanticValidationError(f"Unsupported candidate_type '{candidate.candidate_type}'.")

    @classmethod
    async def reject_candidate(
        cls,
        session: AsyncSession,
        tenant_id: str,
        candidate_id: str,
        reviewer: str,
        reason: str,
    ) -> OntologyCandidate:
        """Rejects a proposed candidate with explicit reasoning."""
        stmt = select(OntologyCandidate).where(
            OntologyCandidate.tenant_id == tenant_id,
            OntologyCandidate.id == candidate_id,
        )
        res = await session.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            raise NotFoundError(f"OntologyCandidate '{candidate_id}' not found for tenant '{tenant_id}'.")

        candidate.review_status = CandidateReviewStatus.REJECTED.value
        candidate.reviewed_by = reviewer
        candidate.review_notes = reason
        candidate.reviewed_at = utc_now()
        await session.flush()
        return candidate

    @classmethod
    async def record_dispute(
        cls,
        session: AsyncSession,
        tenant_id: str,
        entity_id_or_field: str,
        competing_concepts: list[str],
        competing_candidate_ids: list[str] | None = None,
    ) -> OntologyDispute:
        """Records conflicting semantic interpretations without discarding unresolved ambiguity."""
        if len(competing_concepts) < 2:
            raise SemanticValidationError("A semantic dispute requires at least two competing concepts.")

        candidate_ids = competing_candidate_ids or []

        dispute = OntologyDispute(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_id_or_field=entity_id_or_field,
            competing_concepts=competing_concepts,
            competing_candidate_ids=candidate_ids,
            status="UNRESOLVED",
            created_at=utc_now(),
        )
        session.add(dispute)

        # Mark participating candidates as DISPUTED
        if candidate_ids:
            for cid in candidate_ids:
                stmt = select(OntologyCandidate).where(
                    OntologyCandidate.tenant_id == tenant_id,
                    OntologyCandidate.id == cid,
                )
                c_res = await session.execute(stmt)
                cand = c_res.scalar_one_or_none()
                if cand:
                    cand.review_status = CandidateReviewStatus.DISPUTED.value

        await session.flush()
        return dispute

    @classmethod
    async def resolve_dispute(
        cls,
        session: AsyncSession,
        tenant_id: str,
        dispute_id: str,
        resolution_rationale: str,
        resolved_by: str,
    ) -> OntologyDispute:
        """Resolves an ontological dispute with an auditable justification."""
        stmt = select(OntologyDispute).where(
            OntologyDispute.tenant_id == tenant_id,
            OntologyDispute.id == dispute_id,
        )
        res = await session.execute(stmt)
        dispute = res.scalar_one_or_none()
        if not dispute:
            raise NotFoundError(f"OntologyDispute '{dispute_id}' not found for tenant '{tenant_id}'.")

        dispute.status = "RESOLVED"
        dispute.resolution_rationale = resolution_rationale
        dispute.resolved_by = resolved_by
        dispute.resolved_at = utc_now()
        await session.flush()
        return dispute

    @classmethod
    async def list_unresolved_disputes(
        cls,
        session: AsyncSession,
        tenant_id: str,
    ) -> list[OntologyDispute]:
        """Returns all open semantic disputes in the tenant."""
        stmt = select(OntologyDispute).where(
            OntologyDispute.tenant_id == tenant_id,
            OntologyDispute.status == "UNRESOLVED",
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    def compute_ontology_diff(
        cls,
        previous_snapshot: dict[str, Any],
        current_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculates deterministic structural and semantic diff between two ontology states.

        Identifies added, removed, and modified entities/relationships, breaking changes,
        and unresolved semantic disputes.
        """
        prev_entities = {e["canonical_urn"]: e for e in previous_snapshot.get("entities", [])}
        curr_entities = {e["canonical_urn"]: e for e in current_snapshot.get("entities", [])}

        added_entities: list[dict[str, Any]] = []
        removed_entities: list[dict[str, Any]] = []
        modified_entities: list[dict[str, Any]] = []
        breaking_reasons: list[str] = []

        for urn, ent in curr_entities.items():
            if urn not in prev_entities:
                added_entities.append(ent)
            else:
                prev_ent = prev_entities[urn]
                # Check for modifications
                changed_attrs: list[str] = []
                for field in ("name", "description", "properties"):
                    if ent.get(field) != prev_ent.get(field):
                        changed_attrs.append(field)
                if changed_attrs:
                    modified_entities.append(
                        {
                            "canonical_urn": urn,
                            "entity_type": ent.get("entity_type"),
                            "changed_attributes": changed_attrs,
                            "previous": {k: prev_ent.get(k) for k in changed_attrs},
                            "current": {k: ent.get(k) for k in changed_attrs},
                        }
                    )

        for urn, ent in prev_entities.items():
            if urn not in curr_entities:
                removed_entities.append(ent)
                breaking_reasons.append(f"Entity '{urn}' of type '{ent.get('entity_type')}' was deleted from ontology.")

        # Helper to construct unique edge key: (source, target, rel_type)
        def rel_key(r: dict[str, Any]) -> str:
            src = r.get("source_urn") or r.get("source_id", "")
            tgt = r.get("target_urn") or r.get("target_id", "")
            rtype = r.get("rel_type", "")
            return f"{src}->{rtype}->{tgt}"

        prev_rels = {rel_key(r): r for r in previous_snapshot.get("relationships", [])}
        curr_rels = {rel_key(r): r for r in current_snapshot.get("relationships", [])}

        added_relationships: list[dict[str, Any]] = []
        removed_relationships: list[dict[str, Any]] = []
        modified_relationships: list[dict[str, Any]] = []

        for key, rel in curr_rels.items():
            if key not in prev_rels:
                added_relationships.append(rel)
            else:
                prev_rel = prev_rels[key]
                diffs: dict[str, Any] = {}
                for field in ("confidence", "provenance", "status", "valid_to"):
                    if rel.get(field) != prev_rel.get(field):
                        diffs[field] = {"previous": prev_rel.get(field), "current": rel.get(field)}
                if diffs:
                    modified_relationships.append({"relationship_key": key, "changes": diffs})

        for key, rel in prev_rels.items():
            if key not in curr_rels:
                removed_relationships.append(rel)
                if rel.get("status") == RelationshipStatus.ACTIVE.value:
                    breaking_reasons.append(f"Active relationship '{key}' was removed from the ontology.")

        # Unresolved disputes
        unresolved_disputes = current_snapshot.get("unresolved_disputes", [])

        is_breaking = len(breaking_reasons) > 0

        return {
            "is_breaking": is_breaking,
            "breaking_reasons": breaking_reasons,
            "added_entities": added_entities,
            "removed_entities": removed_entities,
            "modified_entities": modified_entities,
            "added_relationships": added_relationships,
            "removed_relationships": removed_relationships,
            "modified_relationships": modified_relationships,
            "unresolved_disputes": unresolved_disputes,
            "metrics": {
                "added_entities_count": len(added_entities),
                "removed_entities_count": len(removed_entities),
                "modified_entities_count": len(modified_entities),
                "added_relationships_count": len(added_relationships),
                "removed_relationships_count": len(removed_relationships),
                "modified_relationships_count": len(modified_relationships),
                "unresolved_disputes_count": len(unresolved_disputes),
            },
        }

    @classmethod
    async def create_ontology_version(
        cls,
        session: AsyncSession,
        tenant_id: str,
        version: str,
        description: str,
        parent_version_id: str | None = None,
        previous_snapshot: dict[str, Any] | None = None,
    ) -> OntologyVersionRecord:
        """Publishes an immutable SemVer release of the ontology with computed changelog diff."""
        if not SEMVER_REGEX.match(version):
            raise SemanticValidationError(f"Version '{version}' is not a valid Semantic Version (MAJOR.MINOR.PATCH).")

        # Verify uniqueness
        v_stmt = select(OntologyVersionRecord).where(
            OntologyVersionRecord.tenant_id == tenant_id,
            OntologyVersionRecord.version == version,
        )
        existing = (await session.execute(v_stmt)).scalar_one_or_none()
        if existing:
            raise ConflictError(f"Ontology version '{version}' already exists for tenant '{tenant_id}'.")

        # Snapshot current active entities and relationships
        ent_stmt = select(OntologyEntity).where(OntologyEntity.tenant_id == tenant_id)
        entities = list((await session.execute(ent_stmt)).scalars().all())

        rel_stmt = select(OntologyRelationship).where(
            OntologyRelationship.tenant_id == tenant_id,
            OntologyRelationship.status == RelationshipStatus.ACTIVE.value,
        )
        relationships = list((await session.execute(rel_stmt)).scalars().all())

        disputes = await cls.list_unresolved_disputes(session, tenant_id)

        # Build mapping from entity id to canonical_urn
        entity_map = {e.id: e.canonical_urn for e in entities}

        curr_snapshot: dict[str, Any] = {
            "entities": [
                {
                    "canonical_urn": e.canonical_urn,
                    "entity_type": e.entity_type,
                    "name": e.name,
                    "description": e.description,
                    "properties": e.properties_payload,
                }
                for e in entities
            ],
            "relationships": [
                {
                    "source_urn": entity_map.get(r.source_id, r.source_id),
                    "target_urn": entity_map.get(r.target_id, r.target_id),
                    "rel_type": r.rel_type,
                    "provenance": r.provenance,
                    "confidence": r.confidence,
                    "status": r.status,
                    "valid_to": r.valid_to.isoformat() if r.valid_to else None,
                }
                for r in relationships
            ],
            "unresolved_disputes": [
                {
                    "id": d.id,
                    "entity_id_or_field": d.entity_id_or_field,
                    "competing_concepts": d.competing_concepts,
                }
                for d in disputes
            ],
        }

        prev_snap = previous_snapshot or {"entities": [], "relationships": [], "unresolved_disputes": []}
        diff_summary = cls.compute_ontology_diff(prev_snap, curr_snapshot)

        record = OntologyVersionRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            version=version,
            parent_version_id=parent_version_id,
            description=description,
            diff_summary=diff_summary,
            is_active=True,
            created_at=utc_now(),
        )
        session.add(record)
        await session.flush()
        return record
