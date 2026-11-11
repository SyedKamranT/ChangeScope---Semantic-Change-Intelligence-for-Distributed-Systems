"""Canonical PostgreSQL 17 Relational Models (SQLAlchemy 2.0)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    """Base declarative model."""

    type_annotation_map = {
        dict[str, Any]: JSON,
    }


def utc_now() -> datetime:
    return datetime.now(UTC)


class Tenant(Base):
    """Multi-tenant root organization."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(32), default="enterprise")
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
    primary_language: Mapped[str] = mapped_column(String(50), default="typescript")
    tier: Mapped[str] = mapped_column(String(20), default="TIER_2")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="repositories")
    scan_runs: Mapped[list["ScanRun"]] = relationship(
        "ScanRun", back_populates="repository", cascade="all, delete-orphan"
    )
    contracts: Mapped[list["Contract"]] = relationship(
        "Contract", back_populates="repository", cascade="all, delete-orphan"
    )


class ScanRun(Base):
    """Change intelligence scan run execution."""

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
    target_branch: Mapped[str] = mapped_column(String(128), default="main")
    source_branch: Mapped[str] = mapped_column(String(128), default="feature")
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    blocking_violations_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_violations_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def base_commit(self) -> str:
        return self.base_sha

    @base_commit.setter
    def base_commit(self, val: str) -> None:
        self.base_sha = val

    @property
    def head_commit(self) -> str:
        return self.head_sha

    @head_commit.setter
    def head_commit(self, val: str) -> None:
        self.head_sha = val

    @property
    def created_at(self) -> datetime:
        return self.started_at

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
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Contract(Base):
    """API contract specification."""

    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("repository_id", "file_path", name="uq_contract_repo_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_type: Mapped[str] = mapped_column(String(50), nullable=False)
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
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="revisions")


class Violation(Base):
    """Detected semantic violation."""

    __tablename__ = "violations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    json_pointer: Mapped[str | None] = mapped_column(Text, nullable=True)
    impacted_service_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    @property
    def evidence(self) -> dict[str, Any]:
        return self.evidence_payload

    @evidence.setter
    def evidence(self, val: dict[str, Any]) -> None:
        self.evidence_payload = val

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="violations")


class ASTSymbol(Base):
    """Extracted code AST symbol."""

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
    symbol_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    scan_run: Mapped["ScanRun"] = relationship("ScanRun", back_populates="symbols")


class RuntimeDependency(Base):
    """Runtime dependency aggregated from OpenTelemetry trace spans."""

    __tablename__ = "runtime_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "caller_service_name",
            "callee_service_name",
            "http_route",
            "http_method",
            "protocol",
            "environment",
            name="uq_runtime_dep_tenant_services_route",
        ),
        Index("idx_runtime_dep_tenant_caller", "tenant_id", "caller_service_name"),
        Index("idx_runtime_dep_tenant_callee", "tenant_id", "callee_service_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    caller_service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    callee_service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    http_route: Mapped[str] = mapped_column(String(255), nullable=False, default="/")
    http_method: Mapped[str] = mapped_column(String(10), nullable=False, default="ANY")
    protocol: Mapped[str] = mapped_column(String(32), nullable=False, default="HTTP")  # HTTP, GRPC, MESSAGING, DATABASE
    messaging_destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    db_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    db_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment: Mapped[str] = mapped_column(String(64), nullable=False, default="production")
    call_count_7d: Mapped[int] = mapped_column(BigInteger, default=0)
    error_count: Mapped[int] = mapped_column(BigInteger, default=0)
    p95_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    is_sampled: Mapped[bool] = mapped_column(Boolean, default=True)
    sample_rate: Mapped[float] = mapped_column(Float, default=1.0)
    exemplar_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exemplar_span_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class RuntimeTraceSpan(Base):
    """Raw or buffered OpenTelemetry trace span preserved for aggregation and trace-linked evidence."""

    __tablename__ = "runtime_trace_spans"
    __table_args__ = (
        Index("idx_runtime_spans_tenant_trace", "tenant_id", "trace_id"),
        Index("idx_runtime_spans_service_observed", "service_name", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    span_id: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="INTERNAL")
    status_code: Mapped[str] = mapped_column(String(16), default="UNSET")
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    environment: Mapped[str] = mapped_column(String(64), default="production")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
