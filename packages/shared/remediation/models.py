"""Domain and Data Models for ChangeScope Remediation Intelligence Layer."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TestType(StrEnum):
    """Categorization of recommended test cases."""

    __test__ = False
    REGRESSION = "REGRESSION"
    INTEGRATION = "INTEGRATION"
    CONTRACT = "CONTRACT"
    END_TO_END = "END_TO_END"


class MigrationPhase(StrEnum):
    """Phases in an API and contract migration roadmap."""

    PHASE_1_PREPARATION = "PHASE_1_PREPARATION"
    PHASE_2_DUAL_WRITE = "PHASE_2_DUAL_WRITE"
    PHASE_3_CONSUMER_MIGRATION = "PHASE_3_CONSUMER_MIGRATION"
    PHASE_4_DEPRECATION = "PHASE_4_DEPRECATION"
    PHASE_5_CLEANUP = "PHASE_5_CLEANUP"


class CompatibilityStrategyType(StrEnum):
    """Pattern for mitigating breaking distributed changes."""

    ADDITIVE_EXPANSION = "ADDITIVE_EXPANSION"
    EXPAND_AND_CONTRACT = "EXPAND_AND_CONTRACT"
    TOLERANT_READER = "TOLERANT_READER"
    CONSUMER_ADAPTER_SHIM = "CONSUMER_ADAPTER_SHIM"
    EVENT_DUAL_PUBLICATION = "EVENT_DUAL_PUBLICATION"
    API_VERSIONING_ROUTING = "API_VERSIONING_ROUTING"


class FactClassification(StrEnum):
    """Explainability tier for findings and statements."""

    VERIFIED_FACT = "VERIFIED_FACT"  # Directly observed in AST, OTel trace, or valid contract spec
    INFERRED_FINDING = "INFERRED_FINDING"  # Traversed via graph paths, semantic mapping, polysemy
    RECOMMENDATION = "RECOMMENDATION"  # Suggested test case, migration step, or policy action


class TestRecommendation(BaseModel):
    """A concrete, evidence-backed test case recommendation."""

    __test__ = False
    test_id: str = Field(default_factory=lambda: f"test-rec-{uuid.uuid4().hex[:8]}")
    test_type: TestType
    test_objective: str
    preconditions: list[str] = Field(default_factory=list)
    test_inputs: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str
    affected_service: str
    relevant_finding: str
    evidence_references: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    code_snippet: str | None = None
    review_status: str = "PENDING_HUMAN_REVIEW"
    requires_human_review: bool = True


class AffectedIntegrationTest(BaseModel):
    """An existing repository integration or E2E test affected by the change."""

    __test__ = False
    test_file: str
    test_name: str
    service_name: str
    reason: str
    evidence_reference: str


class ContractTestUpdate(BaseModel):
    """A required assertion or contract mock update for consumer-driven tests."""

    __test__ = False
    consumer_service: str
    provider_service: str
    contract_file: str
    recommended_assertion: str
    breaking_field: str
    reason: str


class MigrationStep(BaseModel):
    """A discrete, actionable step in the multi-phase API migration plan."""

    step_number: int
    phase: MigrationPhase
    title: str
    description: str
    responsible_team: str
    rollback_plan: str
    estimated_duration: str


class AffectedOwner(BaseModel):
    """Team or engineer responsible for an impacted downstream service."""

    service_name: str
    team_name: str
    owner_handle: str
    contact_channel: str
    role: str = "Service Owner"
    severity_level: str = "HIGH"


class CompatibilityStrategy(BaseModel):
    """Recommended architectural pattern for maintaining backward compatibility."""

    strategy_type: CompatibilityStrategyType
    title: str
    rationale: str
    implementation_steps: list[str] = Field(default_factory=list)
    drawbacks_and_risks: list[str] = Field(default_factory=list)


class ExplainabilityFact(BaseModel):
    """A classified statement distinguishing verified facts from inferences and recommendations."""

    fact_id: str = Field(default_factory=lambda: f"fact-{uuid.uuid4().hex[:8]}")
    classification: FactClassification
    statement: str
    source: str  # AST, SPEC, OTEL, GRAPH, POLICY, MODEL
    evidence_reference: str | None = None
    confidence: float = 1.0


class RemediationExecutionTrace(BaseModel):
    """Auditable telemetry and execution trace of the remediation reasoning workflow."""

    trace_id: str = Field(default_factory=lambda: f"trace-rem-{uuid.uuid4().hex[:12]}")
    steps: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    estimated_cost_usd: float = 0.0
    duration_ms: int = 0
    status: str = "COMPLETED"
    retries_count: int = 0
    safety_checks_passed: bool = True
    can_deploy_or_merge: bool = False  # Hard invariant: NEVER permitted to deploy or merge
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IncidentPreventionReport(BaseModel):
    """Complete human-readable and machine-executable incident prevention report."""

    report_id: str = Field(default_factory=lambda: f"rep-{uuid.uuid4().hex[:10]}")
    scan_id: str
    tenant_id: str
    risk_score: int
    risk_level: str
    recommended_action: str
    executive_summary: str
    facts_and_evidence: list[ExplainabilityFact] = Field(default_factory=list)
    test_recommendations: list[TestRecommendation] = Field(default_factory=list)
    affected_integration_tests: list[AffectedIntegrationTest] = Field(default_factory=list)
    contract_test_updates: list[ContractTestUpdate] = Field(default_factory=list)
    migration_steps: list[MigrationStep] = Field(default_factory=list)
    affected_owners: list[AffectedOwner] = Field(default_factory=list)
    compatibility_strategies: list[CompatibilityStrategy] = Field(default_factory=list)
    markdown_report: str
    execution_trace: RemediationExecutionTrace
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
