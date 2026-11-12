"""Reconcile core ORM columns on workspaces, repositories, scans, violations, contracts, AST, and telemetry.

Revision ID: 0004_reconcile_core_orm_cols
Revises: 0003_reconcile_sec_telemetry
Create Date: 2026-11-12 19:34:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_reconcile_core_orm_cols"
down_revision: str | None = "0003_reconcile_sec_telemetry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Workspaces & Repositories: allow ORM inserts without explicit updated_at
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

    # 2. ScanRuns: rename base_commit/head_commit -> base_sha/head_sha and relax legacy created_at
    with op.batch_alter_table("scan_runs") as batch_op:
        batch_op.alter_column(
            "base_commit",
            new_column_name="base_sha",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "head_commit",
            new_column_name="head_sha",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
    op.create_index("idx_scan_runs_repo_shas", "scan_runs", ["repository_id", "base_sha", "head_sha"])

    # 3. Contracts: relax legacy required columns superseded by contract_revisions
    with op.batch_alter_table("contracts") as batch_op:
        batch_op.alter_column("version", existing_type=sa.String(length=64), nullable=True)
        batch_op.alter_column("content_hash", existing_type=sa.String(length=64), nullable=True)
        batch_op.alter_column("canonical_schema", existing_type=sa.JSON(), nullable=True)

    # 4. Violations: align column names and add impacted_service_id
    with op.batch_alter_table("violations") as batch_op:
        batch_op.add_column(sa.Column("impacted_service_id", sa.String(length=36), nullable=True))
        batch_op.alter_column(
            "evidence",
            new_column_name="evidence_payload",
            existing_type=sa.JSON(),
            existing_nullable=False,
        )

    # 5. ASTSymbols: align scan_id, signature, metadata_payload and relax legacy fields
    with op.batch_alter_table("ast_symbols") as batch_op:
        batch_op.add_column(sa.Column("scan_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("signature", sa.Text(), nullable=True))
        batch_op.alter_column(
            "metadata",
            new_column_name="metadata_payload",
            existing_type=sa.JSON(),
            existing_nullable=False,
        )
        batch_op.alter_column("repository_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )
        batch_op.create_foreign_key(
            "fk_ast_symbols_scan_id",
            "scan_runs",
            ["scan_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index("ix_ast_symbols_scan_id", "ast_symbols", ["scan_id"])

    # 6. RuntimeDependencies: reconcile OpenTelemetry dependency schema columns & constraints
    with op.batch_alter_table("runtime_dependencies") as batch_op:
        batch_op.alter_column("source_service", existing_type=sa.String(length=128), nullable=True)
        batch_op.alter_column("target_service", existing_type=sa.String(length=128), nullable=True)
        batch_op.alter_column("target_endpoint", existing_type=sa.String(length=256), nullable=True)
        batch_op.alter_column("call_rate_rpm", existing_type=sa.Float(), nullable=True)
        batch_op.alter_column("p99_latency_ms", existing_type=sa.Float(), nullable=True)
        batch_op.alter_column("metadata", existing_type=sa.JSON(), nullable=True)
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

        batch_op.add_column(
            sa.Column("caller_service_name", sa.String(length=255), nullable=False, server_default="unknown")
        )
        batch_op.add_column(
            sa.Column("callee_service_name", sa.String(length=255), nullable=False, server_default="unknown")
        )
        batch_op.add_column(sa.Column("http_route", sa.String(length=255), nullable=False, server_default="/"))
        batch_op.add_column(sa.Column("http_method", sa.String(length=10), nullable=False, server_default="ANY"))
        batch_op.add_column(sa.Column("protocol", sa.String(length=32), nullable=False, server_default="HTTP"))
        batch_op.add_column(sa.Column("messaging_destination", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("db_system", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("db_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("environment", sa.String(length=64), nullable=False, server_default="production"))
        batch_op.add_column(sa.Column("call_count_7d", sa.BigInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("error_count", sa.BigInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("p95_latency_ms", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(sa.Column("is_sampled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("sample_rate", sa.Float(), nullable=False, server_default="1.0"))
        batch_op.add_column(sa.Column("exemplar_trace_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("exemplar_span_id", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column(
                "first_observed_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(sa.Column("metadata_payload", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.create_unique_constraint(
            "uq_runtime_dep_tenant_services_route",
            [
                "tenant_id",
                "caller_service_name",
                "callee_service_name",
                "http_route",
                "http_method",
                "protocol",
                "environment",
            ],
        )

    op.create_index("idx_runtime_dep_tenant_caller", "runtime_dependencies", ["tenant_id", "caller_service_name"])
    op.create_index("idx_runtime_dep_tenant_callee", "runtime_dependencies", ["tenant_id", "callee_service_name"])


def downgrade() -> None:
    op.drop_index("idx_runtime_dep_tenant_callee", table_name="runtime_dependencies")
    op.drop_index("idx_runtime_dep_tenant_caller", table_name="runtime_dependencies")

    with op.batch_alter_table("runtime_dependencies") as batch_op:
        batch_op.drop_constraint("uq_runtime_dep_tenant_services_route", type_="unique")
        for col in (
            "metadata_payload",
            "first_observed_at",
            "exemplar_span_id",
            "exemplar_trace_id",
            "sample_rate",
            "is_sampled",
            "p95_latency_ms",
            "error_count",
            "call_count_7d",
            "environment",
            "db_name",
            "db_system",
            "messaging_destination",
            "protocol",
            "http_method",
            "http_route",
            "callee_service_name",
            "caller_service_name",
        ):
            batch_op.drop_column(col)

        batch_op.alter_column(
            "created_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=None
        )
        batch_op.alter_column("metadata", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("p99_latency_ms", existing_type=sa.Float(), nullable=False)
        batch_op.alter_column("call_rate_rpm", existing_type=sa.Float(), nullable=False)
        batch_op.alter_column("target_endpoint", existing_type=sa.String(length=256), nullable=False)
        batch_op.alter_column("target_service", existing_type=sa.String(length=128), nullable=False)
        batch_op.alter_column("source_service", existing_type=sa.String(length=128), nullable=False)

    op.drop_index("ix_ast_symbols_scan_id", table_name="ast_symbols")
    with op.batch_alter_table("ast_symbols") as batch_op:
        batch_op.drop_constraint("fk_ast_symbols_scan_id", type_="foreignkey")
        batch_op.alter_column(
            "created_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=None
        )
        batch_op.alter_column("repository_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.alter_column(
            "metadata_payload",
            new_column_name="metadata",
            existing_type=sa.JSON(),
            existing_nullable=False,
        )
        batch_op.drop_column("signature")
        batch_op.drop_column("scan_id")

    with op.batch_alter_table("violations") as batch_op:
        batch_op.alter_column(
            "evidence_payload",
            new_column_name="evidence",
            existing_type=sa.JSON(),
            existing_nullable=False,
        )
        batch_op.drop_column("impacted_service_id")

    with op.batch_alter_table("contracts") as batch_op:
        batch_op.alter_column("canonical_schema", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("content_hash", existing_type=sa.String(length=64), nullable=False)
        batch_op.alter_column("version", existing_type=sa.String(length=64), nullable=False)

    op.drop_index("idx_scan_runs_repo_shas", table_name="scan_runs")
    with op.batch_alter_table("scan_runs") as batch_op:
        batch_op.alter_column(
            "created_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=None
        )
        batch_op.alter_column(
            "head_sha",
            new_column_name="head_commit",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "base_sha",
            new_column_name="base_commit",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )

    with op.batch_alter_table("repositories") as batch_op:
        batch_op.alter_column(
            "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=None
        )

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.alter_column(
            "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=None
        )
