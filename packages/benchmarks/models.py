"""Domain schemas and evaluation metrics for the ChangeScope Benchmark Suite."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ScenarioCategory(StrEnum):
    """The 15 canonical benchmark change scenario categories."""

    FIELD_RENAME = "FIELD_RENAME"
    FIELD_REMOVAL = "FIELD_REMOVAL"
    TYPE_INCOMPATIBILITY = "TYPE_INCOMPATIBILITY"
    MONETARY_UNIT_CHANGE = "MONETARY_UNIT_CHANGE"
    TIMESTAMP_INTERPRETATION_CHANGE = "TIMESTAMP_INTERPRETATION_CHANGE"
    IDENTIFIER_SEMANTIC_DRIFT = "IDENTIFIER_SEMANTIC_DRIFT"
    ENUM_SEMANTIC_CHANGES = "ENUM_SEMANTIC_CHANGES"
    EVENT_SCHEMA_EVOLUTION = "EVENT_SCHEMA_EVOLUTION"
    EVENT_ORDERING_ISSUES = "EVENT_ORDERING_ISSUES"
    DATABASE_MIGRATION_IMPACT = "DATABASE_MIGRATION_IMPACT"
    HIDDEN_DOWNSTREAM_CONSUMERS = "HIDDEN_DOWNSTREAM_CONSUMERS"
    TRANSITIVE_SERVICE_DEPENDENCIES = "TRANSITIVE_SERVICE_DEPENDENCIES"
    RUNTIME_ONLY_DEPENDENCIES = "RUNTIME_ONLY_DEPENDENCIES"
    PERMISSION_CHANGES = "PERMISSION_CHANGES"
    UNRELATED_CHANGES = "UNRELATED_CHANGES"


class DatasetSplit(StrEnum):
    """Evaluation split to strictly isolate holdout test data from development fixtures."""

    DEVELOPMENT = "DEVELOPMENT"
    HOLDOUT = "HOLDOUT"


class GroundTruthFinding(BaseModel):
    """Ground truth expectations for an evaluation scenario."""

    finding_code: str
    severity: str  # BLOCKING, WARNING, INFO, NONE
    is_breaking: bool
    is_semantic_drift: bool
    expected_affected_entities: list[str] = Field(default_factory=list)
    expected_impact_paths: list[list[str]] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    description: str


class BenchmarkScenario(BaseModel):
    """A fully specified, reproducible change intelligence test scenario."""

    scenario_id: str  # e.g., SCEN-01
    name: str
    category: ScenarioCategory
    split: DatasetSplit = DatasetSplit.DEVELOPMENT
    description: str
    changed_artifact: str  # e.g. "api/openapi.yaml", "models/order.py", "migrations/002.sql"
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    static_graph: dict[str, Any] = Field(default_factory=dict)
    runtime_traces: list[dict[str, Any]] = Field(default_factory=list)
    ontology_annotations: dict[str, Any] = Field(default_factory=dict)
    ground_truth: GroundTruthFinding
    expected_non_findings: list[str] = Field(default_factory=list)


class BaselinePrediction(BaseModel):
    """Output prediction emitted by a specific baseline evaluation engine."""

    baseline_name: str  # Baseline A, Baseline B, or Baseline C (ChangeScope)
    scenario_id: str
    flagged_as_breaking: bool
    detected_semantic_drift: bool
    severity: str  # BLOCKING, WARNING, INFO, NONE
    affected_entities: list[str] = Field(default_factory=list)
    impact_paths: list[list[str]] = Field(default_factory=list)
    emitted_findings: list[str] = Field(default_factory=list)
    execution_latency_ms: float
    llm_latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    llm_narrative: str | None = None
    llm_used_fallback: bool | None = None
    telemetry_used: bool = False
    ontology_used: bool = False


class MetricSummary(BaseModel):
    """Rigorous evaluation metrics computed over a dataset split or category."""

    baseline_name: str
    split: str
    total_scenarios: int
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    accuracy: float = 0.0
    breaking_detection_rate: float = 0.0
    semantic_drift_detection_rate: float = 0.0
    consumer_discovery_accuracy: float = 0.0
    impact_path_accuracy: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
