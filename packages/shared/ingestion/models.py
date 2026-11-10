"""Normalized Data Models and Artifact Types for Ingestion Subsystem."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IngestionSourceType(StrEnum):
    """Supported repository ingestion input sources."""

    LOCAL_GIT = "LOCAL_GIT"
    UPLOADED_ARCHIVE = "UPLOADED_ARCHIVE"
    GITHUB_REPO = "GITHUB_REPO"
    GITHUB_PR = "GITHUB_PR"


class CodeSymbol(BaseModel):
    """Extracted class, function, or interface symbol definition."""

    name: str
    symbol_type: str  # 'class', 'function', 'async_function', 'method', 'interface'
    file_path: str
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None
    decorators: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportExport(BaseModel):
    """File-level module import or exported symbol statement."""

    file_path: str
    kind: str  # 'import', 'export', 're_export'
    module: str
    symbols: list[str] = Field(default_factory=list)
    start_line: int
    is_external: bool = False


class CallRelationship(BaseModel):
    """Candidate function call dependency extracted from code."""

    caller_name: str
    callee_name: str
    file_path: str
    line_number: int
    is_internal: bool = True
    confidence: float = 1.0
    evidence: str = ""


class RouteDefinition(BaseModel):
    """API server route handler extracted from web framework."""

    method: str  # GET, POST, PUT, DELETE, PATCH, etc.
    path_template: str
    handler_name: str
    file_path: str
    start_line: int
    end_line: int
    framework: str  # 'FastAPI', 'Flask', 'Django', 'Express', 'NestJS'
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HttpClientCall(BaseModel):
    """Outbound HTTP or RPC request extracted from code."""

    method: str
    url_or_path: str
    client_library: str  # 'httpx', 'requests', 'aiohttp', 'axios', 'fetch'
    file_path: str
    line_number: int
    is_dynamic: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnvVarReference(BaseModel):
    """Configuration environment variable reference."""

    name: str
    file_path: str
    line_number: int
    default_value: str | None = None
    has_fallback: bool = False


class EventPattern(BaseModel):
    """Asynchronous event publish or subscribe construct."""

    pattern_type: str  # 'producer', 'consumer'
    event_name_or_topic: str
    channel: str | None = None
    file_path: str
    line_number: int
    framework: str  # 'Celery', 'Kafka', 'RabbitMQ', 'EventEmitter'
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatabasePattern(BaseModel):
    """Database table or ORM access pattern."""

    operation: str  # 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MODEL_DEF', 'RAW_QUERY'
    table_or_model: str
    file_path: str
    line_number: int
    orm_framework: str | None = None  # 'SQLAlchemy', 'Prisma', 'TypeORM', 'DjangoORM'
    columns: list[str] = Field(default_factory=list)


class DatabaseMigration(BaseModel):
    """Schema migration file definition and DDL events."""

    migration_type: str  # 'alembic', 'prisma', 'flyway', 'raw_sql'
    version_or_name: str
    file_path: str
    tables_created: list[str] = Field(default_factory=list)
    tables_altered: list[str] = Field(default_factory=list)
    columns_added: list[dict[str, Any]] = Field(default_factory=list)
    raw_statements: list[str] = Field(default_factory=list)


class ConfigDependency(BaseModel):
    """Project configuration manifest and dependencies."""

    config_type: str  # 'pyproject', 'package_json', 'requirements', 'docker_compose', 'env_example'
    file_path: str
    dependencies: dict[str, str] = Field(default_factory=dict)
    env_keys: list[str] = Field(default_factory=list)


class OwnershipRule(BaseModel):
    """File ownership mapping candidate derived from CODEOWNERS."""

    pattern: str
    owners: list[str]
    file_path: str
    line_number: int


class CandidateRelationship(BaseModel):
    """Normalized ontology relationship candidate with deterministic evidence."""

    source_urn: str
    source_type: str
    target_urn: str
    target_type: str
    rel_type: str
    provenance: str
    confidence: float
    evidence_refs: list[str] = Field(default_factory=list)
    source_repo_version: str | None = None


class IngestionArtifact(BaseModel):
    """Comprehensive structured output produced by scanning an ingested repository."""

    tenant_id: str
    repository_id: str
    commit_sha: str
    source_type: IngestionSourceType
    root_path: str
    total_files: int = 0
    total_lines_of_code: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    symbols: list[CodeSymbol] = Field(default_factory=list)
    imports_exports: list[ImportExport] = Field(default_factory=list)
    call_relationships: list[CallRelationship] = Field(default_factory=list)
    routes: list[RouteDefinition] = Field(default_factory=list)
    client_calls: list[HttpClientCall] = Field(default_factory=list)
    env_vars: list[EnvVarReference] = Field(default_factory=list)
    events: list[EventPattern] = Field(default_factory=list)
    db_patterns: list[DatabasePattern] = Field(default_factory=list)
    migrations: list[DatabaseMigration] = Field(default_factory=list)
    configs: list[ConfigDependency] = Field(default_factory=list)
    ownership_rules: list[OwnershipRule] = Field(default_factory=list)
    candidate_relationships: list[CandidateRelationship] = Field(default_factory=list)
    partial_errors: list[dict[str, Any]] = Field(default_factory=list)
