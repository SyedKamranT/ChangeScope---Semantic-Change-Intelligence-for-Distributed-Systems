"""Initial canonical relational schema for ChangeScope.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tenants Table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="starter"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Workspaces Table
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_workspace_tenant_slug"),
    )
    op.create_index("ix_workspaces_tenant_id", "workspaces", ["tenant_id"])

    # 3. Repositories Table
    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "workspace_id", sa.String(length=36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("clone_url", sa.String(length=512), nullable=False),
        sa.Column("default_branch", sa.String(length=64), nullable=False, server_default="main"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repositories_tenant_id", "repositories", ["tenant_id"])
    op.create_index("ix_repositories_workspace_id", "repositories", ["workspace_id"])

    # 4. Scan Runs Table
    op.create_table(
        "scan_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "repository_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("target_branch", sa.String(length=128), nullable=False),
        sa.Column("source_branch", sa.String(length=128), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=False),
        sa.Column("head_commit", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="LOW"),
        sa.Column("blocking_violations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_violations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scan_runs_tenant_id", "scan_runs", ["tenant_id"])
    op.create_index("ix_scan_runs_repository_id", "scan_runs", ["repository_id"])

    # 5. Outbox Events Table
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])

    # 6. Contracts Table
    op.create_table(
        "contracts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "repository_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("contract_type", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_schema", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contracts_tenant_id", "contracts", ["tenant_id"])
    op.create_index("ix_contracts_repository_id", "contracts", ["repository_id"])

    # 7. Violations Table
    op.create_table(
        "violations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scan_id", sa.String(length=36), sa.ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("json_pointer", sa.String(length=256), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_violations_tenant_id", "violations", ["tenant_id"])
    op.create_index("ix_violations_scan_id", "violations", ["scan_id"])

    # 8. AST Symbols Table
    op.create_table(
        "ast_symbols",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "repository_id", sa.String(length=36), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("symbol_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ast_symbols_tenant_id", "ast_symbols", ["tenant_id"])
    op.create_index("ix_ast_symbols_repository_id", "ast_symbols", ["repository_id"])

    # 9. Runtime Dependencies Table
    op.create_table(
        "runtime_dependencies",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_service", sa.String(length=128), nullable=False),
        sa.Column("target_service", sa.String(length=128), nullable=False),
        sa.Column("target_endpoint", sa.String(length=256), nullable=False),
        sa.Column("call_rate_rpm", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("p99_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runtime_deps_tenant_id", "runtime_dependencies", ["tenant_id"])


def downgrade() -> None:
    # Reversible schema: drop tables in exact reverse topological order
    op.drop_table("runtime_dependencies")
    op.drop_table("ast_symbols")
    op.drop_table("violations")
    op.drop_table("contracts")
    op.drop_table("outbox_events")
    op.drop_table("scan_runs")
    op.drop_table("repositories")
    op.drop_table("workspaces")
    op.drop_table("tenants")
