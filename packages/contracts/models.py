"""Contract, AST, and Semantic Analysis Models for ChangeScope."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from pydantic import Field as PyField


class ContractType(StrEnum):
    """Supported distributed contract specification types."""

    OPENAPI = "OPENAPI"
    ASYNCAPI = "ASYNCAPI"
    JSON_SCHEMA = "JSON_SCHEMA"
    SQL_DDL = "SQL_DDL"


@dataclass
class RuleViolation:
    """A detected semantic change violation."""

    rule_code: str  # e.g. 'RULE_ENUM_NARROWED', 'RULE_CLOSED_WORLD_COLLISION'
    severity: str  # 'BLOCKING', 'WARNING', 'INFO'
    file_path: str
    start_line: int
    end_line: int
    message: str
    json_pointer: str | None = None
    impacted_service_id: str | None = None
    impacted_service_name: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsumerContractProfile:
    """Downstream consumer contract profile for compatibility checking."""

    service_id: str
    service_name: str
    validation_mode: str  # 'OPEN_WORLD' or 'CLOSED_WORLD'
    additional_properties_allowed: bool
    known_properties: set[str]
    consumed_enum_values: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class ExtractedRoute:
    """An API route definition extracted from code."""

    method: str
    path_template: str
    handler_name: str
    file_path: str
    start_line: int
    end_line: int
    framework: str  # 'FastAPI', 'Flask', 'Django', 'Express', 'NestJS'
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedClientCall:
    """An outbound HTTP or RPC call invocation extracted from code."""

    method: str
    url_or_path: str
    client_library: str  # 'requests', 'httpx', 'fetch', 'axios'
    file_path: str
    start_line: int
    end_line: int
    is_dynamic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedORMModel:
    """An ORM entity model mapped to a database table."""

    model_name: str
    table_name: str
    file_path: str
    start_line: int
    end_line: int
    columns: list[dict[str, Any]] = field(default_factory=list)


class ParsedContractSummary(BaseModel):
    """High-level summary of parsed distributed contract."""

    contract_type: ContractType
    version: str
    title: str | None = None
    endpoints_count: int = 0
    channels_count: int = 0
    schemas_count: int = 0
    metadata: dict[str, Any] = PyField(default_factory=dict)
