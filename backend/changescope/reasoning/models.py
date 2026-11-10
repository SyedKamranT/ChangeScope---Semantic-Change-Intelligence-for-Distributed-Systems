"""Data models for Semantic Change Violations and Rule Evaluation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleViolation:
    """A detected semantic change violation."""

    rule_code: str  # 'RULE_ENUM_NARROWED', 'RULE_CLOSED_WORLD_COLLISION', etc.
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
