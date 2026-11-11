"""Data Models for OpenTelemetry Ingestion, Span Processing, and Runtime Graph Construction."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SpanKind(StrEnum):
    """OpenTelemetry Span Kind classification."""

    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class ProtocolType(StrEnum):
    """Communication protocol between services."""

    HTTP = "HTTP"
    GRPC = "GRPC"
    MESSAGING = "MESSAGING"
    DATABASE = "DATABASE"
    INTERNAL = "INTERNAL"


class CorrelationStatus(StrEnum):
    """Correlation state between static code analysis, contracts, and live runtime behavior."""

    OBSERVED_AND_STATIC_CONFIRMED = "OBSERVED_AND_STATIC_CONFIRMED"
    STATIC_ONLY = "STATIC_ONLY"
    RUNTIME_ONLY = "RUNTIME_ONLY"


class NormalizedSpan(BaseModel):
    """Structured, sanitized OpenTelemetry span representation."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    service_name: str = "unknown_service"
    name: str
    kind: SpanKind = SpanKind.INTERNAL
    status_code: str = "UNSET"  # OK, ERROR, UNSET
    start_time_unix_nano: int = 0
    end_time_unix_nano: int = 0
    duration_ms: float = 0.0

    # HTTP attributes
    http_method: str | None = None
    http_route: str | None = None
    http_url: str | None = None
    http_status_code: int | None = None

    # RPC attributes (gRPC / Thrift)
    rpc_system: str | None = None
    rpc_service: str | None = None
    rpc_method: str | None = None

    # Messaging attributes (Kafka / RabbitMQ / SQS)
    messaging_system: str | None = None
    messaging_destination: str | None = None
    messaging_operation: str | None = None

    # Database attributes
    db_system: str | None = None
    db_name: str | None = None
    db_statement: str | None = None
    db_operation: str | None = None

    # Environment and peer context
    environment: str = "production"
    peer_service: str | None = None
    telemetry_sdk: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ObservedServiceDependency(BaseModel):
    """A direct observed communication path between two services or resources."""

    caller_service_name: str
    callee_service_name: str
    protocol: ProtocolType = ProtocolType.HTTP
    operation_or_route: str = "/"
    http_method: str | None = None
    messaging_destination: str | None = None
    db_system: str | None = None
    db_name: str | None = None
    environment: str = "production"

    call_count: int = 1
    error_count: int = 0
    p95_latency_ms: float = 0.0
    first_observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    exemplar_trace_id: str | None = None
    exemplar_span_id: str | None = None
    is_sampled: bool = True
    sample_rate: float = 1.0
    evidence_citations: list[str] = Field(default_factory=list)


class RuntimeServiceGraph(BaseModel):
    """Aggregated topology graph of observed services, endpoints, databases, and dependencies."""

    tenant_id: str
    environment: str = "production"
    services: list[str] = Field(default_factory=list)
    dependencies: list[ObservedServiceDependency] = Field(default_factory=list)
    total_spans_processed: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CorrelatedDependency(BaseModel):
    """A correlated dependency linking runtime observations, static code AST, and API contracts."""

    caller_service: str
    callee_service: str
    route_or_channel: str
    correlation_status: CorrelationStatus
    runtime_observed: bool
    static_confirmed: bool
    openapi_matched: bool = False
    asyncapi_matched: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    runtime_call_count: int = 0
    runtime_p95_latency_ms: float = 0.0
    static_file_path: str | None = None
    static_line_number: int | None = None
    notes: str | None = None
