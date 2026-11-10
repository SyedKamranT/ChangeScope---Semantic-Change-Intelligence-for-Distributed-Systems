"""Add ChangeScope Software Engineering Ontology (CSEO) Canonical Relational Tables.

Revision ID: 0002_software_ontology
Revises: 0001_initial_schema
Create Date: 2026-11-11 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_software_ontology"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Ontology Entities
    op.create_table(
        "ontology_entities",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("canonical_urn", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "repository_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("properties_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "canonical_urn", name="uq_ontology_entity_tenant_urn"),
    )
    op.create_index("ix_ontology_entities_tenant_id", "ontology_entities", ["tenant_id"])
    op.create_index("ix_ontology_entities_type", "ontology_entities", ["tenant_id", "entity_type"])

    # 2. Ontology Relationships
    op.create_table(
        "ontology_relationships",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source_id", sa.String(length=64), sa.ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_id", sa.String(length=64), sa.ForeignKey("ontology_entities.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("rel_type", sa.String(length=50), nullable=False),
        sa.Column("source_repo_version_id", sa.String(length=64), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ontology_rel_endpoints", "ontology_relationships", ["tenant_id", "source_id", "target_id", "rel_type"]
    )
    op.create_index("ix_ontology_rel_status", "ontology_relationships", ["tenant_id", "status"])

    # 3. Business Concepts
    op.create_table(
        "ontology_business_concepts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("urn", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("bounded_context", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("synonyms", sa.JSON(), nullable=False),
        sa.Column("homonym_distinctions", sa.JSON(), nullable=False),
        sa.Column("constraints_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "urn", name="uq_business_concept_tenant_urn"),
    )
    op.create_index("ix_business_concepts_category", "ontology_business_concepts", ["tenant_id", "category"])

    # 4. Ontology Candidates
    op.create_table(
        "ontology_candidates",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_type", sa.String(length=32), nullable=False),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("source_scanner", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="CANDIDATE"),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ontology_candidates_status", "ontology_candidates", ["tenant_id", "review_status"])

    # 5. Ontology Disputes
    op.create_table(
        "ontology_disputes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id_or_field", sa.String(length=255), nullable=False),
        sa.Column("competing_concepts", sa.JSON(), nullable=False),
        sa.Column("competing_candidate_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UNRESOLVED"),
        sa.Column("resolution_rationale", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ontology_disputes_status", "ontology_disputes", ["tenant_id", "status"])

    # 6. Ontology Versions
    op.create_table(
        "ontology_versions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("parent_version_id", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("diff_summary", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "version", name="uq_ontology_tenant_version"),
    )


def downgrade() -> None:
    op.drop_table("ontology_versions")
    op.drop_table("ontology_disputes")
    op.drop_table("ontology_candidates")
    op.drop_table("ontology_business_concepts")
    op.drop_table("ontology_relationships")
    op.drop_table("ontology_entities")
