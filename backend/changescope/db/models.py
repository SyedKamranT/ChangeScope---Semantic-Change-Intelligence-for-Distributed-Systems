"""ChangeScope Canonical Relational Models (SQLAlchemy 2.0)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base model class with generic JSON column support."""

    type_annotation_map = {
        dict[str, Any]: JSON,
    }


def utc_now() -> datetime:
    return datetime.now(UTC)


class Tenant(Base):
    """Multi-tenant isolation root."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    workspaces: Mapped[list["Workspace"]] = relationship(
        "Workspace", back_populates="tenant", cascade="all, delete-orphan"
    )


class Workspace(Base):
    """Logical grouping of repositories within a tenant."""

    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_workspace_tenant_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="workspaces")
    repositories: Mapped[list["Repository"]] = relationship(
        "Repository", back_populates="workspace", cascade="all, delete-orphan"
    )


class Repository(Base):
    """Monitored software repository."""

    __tablename__ = "repositories"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_repo_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clone_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    primary_language: Mapped[str] = mapped_column(String(50), nullable=False)  # 'python', 'typescript'
    tier: Mapped[str] = mapped_column(String(20), default="TIER_2")  # 'TIER_1', 'TIER_2', 'TIER_3'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="repositories")
    scan_runs: Mapped[list["ScanRun"]] = relationship(
        "ScanRun", back_populates="repository", cascade="all, delete-orphan"
    )
    contracts: Mapped[list["Contract"]] = relationship(
        "Contract", back_populates="repository", cascade="all, delete-orphan"
    )


class ScanRun(Base):
    """PR or commit change scan execution record."""

    __tablename__ = "scan_runs"
    __table_args__ = (Index("idx_scan_runs_repo_shas", "repository_id", "base_sha", "head_sha"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0 to 100
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="scan_runs")
    violations: Mapped[list["Violation"]] = relationship(
        "Violation", back_populates="scan_run", cascade="all, delete-orphan"
    )
    symbols: Mapped[list["ASTSymbol"]] = relationship(
        "ASTSymbol", back_populates="scan_run", cascade="all, delete-orphan"
    )


class OutboxEvent(Base):
    """Transactional Outbox for asynchronous Neo4j graph projections."""

    __tablename__ = "outbox_events"
    __table_args__ = (Index("idx_outbox_pending", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'SCAN', 'TRACE_BATCH', 'CONTRACT'
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'SCAN_PROJECTION_PENDING', 'TRACES_ENRICHED'
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # 'PENDING', 'PROCESSED', 'FAILED'
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Contract(Base):
    """API or Event specification registered to a repository."""

    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("repository_id", "file_path", name="uq_contract_repo_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'OPENAPI_3', 'ASYNCAPI_2', 'ASYNCAPI_3', 'JSON_SCHEMA'
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="contracts")
    revisions: Mapped[list["ContractRevision"]] = relationship(
        "ContractRevision", back_populates="contract", cascade="all, delete-orphan"
    )


class ContractRevision(Base):
    """Versioned snapshot of an API specification tied to a Git commit."""

    __tablename__ = "contract_revisions"
    __table_args__ = (UniqueConstraint("contract_id", "commit_sha", name="uq_contract_revision_commit"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="revisions")


class Violation(Base):
    """Semantic contract or database violation identified during a scan."""

    __tablename__ = "violations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)  # 'RULE_ENUM_NARROWED', etc.
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # 'BLOCKING', 'WARNING', 'INFO'
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    json_pointer: Mapped[str | None] = mapped_column(Text, nullable=True)
    impacted_service_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="violations")


class ASTSymbol(Base):
    """Extracted code symbol (route handler, client call, ORM model)."""

    __tablename__ = "ast_symbols"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'ROUTE_HANDLER', 'CLIENT_CALL', 'ORM_MODEL'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="symbols")


class RuntimeDependency(Base):
    """Empirical service-to-service call dependency derived from OpenTelemetry."""

    __tablename__ = "runtime_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "caller_service_name",
            "callee_service_name",
            "http_route",
            "http_method",
            name="uq_runtime_dep_tenant_services_route",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    caller_service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    callee_service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    http_route: Mapped[str] = mapped_column(String(255), nullable=False)
    http_method: Mapped[str] = mapped_column(String(10), nullable=False)
    call_count_7d: Mapped[int] = mapped_column(BigInteger, default=0)
    p95_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DatabaseMigration(Base):
    """Tracked database DDL migration file."""

    __tablename__ = "database_migrations"
    __table_args__ = (UniqueConstraint("repository_id", "filename", name="uq_migration_repo_filename"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    framework: Mapped[str] = mapped_column(String(50), nullable=False)  # 'alembic', 'prisma', 'flyway'
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    version_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    parsed_ddl_events: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
