"""Reconcile canonical security, credential, audit, idempotency, revision, and telemetry tables.

Revision ID: 0003_reconcile_security_telemetry
Revises: 0002_software_ontology
Create Date: 2026-11-12 00:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_reconcile_security_telemetry"
down_revision: str | None = "0002_software_ontology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Reconcile missing columns on existing core tables (batch mode supports SQLite & PostgreSQL)
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.add_column(sa.Column("slug", sa.String(length=100), nullable=True))

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.add_column(
            sa.Column("primary_language", sa.String(length=50), nullable=False, server_default="typescript")
        )
        batch_op.add_column(sa.Column("tier", sa.String(length=20), nullable=False, server_default="TIER_2"))

    with op.batch_alter_table("scan_runs") as batch_op:
        batch_op.add_column(sa.Column("pr_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))

    # 2. Contract Revisions
    op.create_table(
        "contract_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "contract_id", sa.String(length=36), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("canonical_spec", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("contract_id", "commit_sha", name="uq_contract_revision_commit"),
    )
    op.create_index("ix_contract_revisions_contract_id", "contract_revisions", ["contract_id"])

    # 3. Runtime Trace Spans (OTLP buffered spans)
    op.create_table(
        "runtime_trace_spans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("span_id", sa.String(length=32), nullable=False),
        sa.Column("parent_span_id", sa.String(length=32), nullable=True),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="INTERNAL"),
        sa.Column("status_code", sa.String(length=16), nullable=False, server_default="UNSET"),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("environment", sa.String(length=64), nullable=False, server_default="production"),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_runtime_spans_tenant_trace", "runtime_trace_spans", ["tenant_id", "trace_id"])
    op.create_index("idx_runtime_spans_service_observed", "runtime_trace_spans", ["service_name", "observed_at"])

    # 4. Integration Credentials (AES-256-GCM at rest)
    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False, server_default="v1"),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_integration_credential_tenant_name"),
    )
    op.create_index("idx_credentials_tenant_provider", "integration_credentials", ["tenant_id", "provider"])

    # 5. Security Audit Logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="SUCCESS"),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_logs_tenant_time", "audit_logs", ["tenant_id", "created_at"])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_logs_event_type", "audit_logs", ["event_type"])

    # 6. Idempotency Records
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_idempotency_tenant_key"),
    )
    op.create_index("idx_idempotency_expires", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_logs")
    op.drop_table("integration_credentials")
    op.drop_table("runtime_trace_spans")
    op.drop_table("contract_revisions")

    with op.batch_alter_table("scan_runs") as batch_op:
        batch_op.drop_column("error_message")
        batch_op.drop_column("pr_number")

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.drop_column("tier")
        batch_op.drop_column("primary_language")

    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_column("slug")
