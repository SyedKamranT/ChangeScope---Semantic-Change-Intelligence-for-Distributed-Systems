"""Phased API Migration Planning, Compatibility Strategies, and Ownership Attribution."""

from packages.contracts.models import ContractFinding
from packages.shared.impact.models import ImpactedEntity, ServiceTier
from packages.shared.remediation.models import (
    AffectedOwner,
    CompatibilityStrategy,
    CompatibilityStrategyType,
    MigrationPhase,
    MigrationStep,
)


class MigrationPlanner:
    """Plans multi-phase zero-downtime API migrations and backward-compatibility strategies."""

    # Pre-configured team ownership catalog (can be extended from repo CODEOWNERS or DB)
    DEFAULT_SERVICE_OWNERSHIP = {
        "api-gateway": ("Core Infrastructure Team", "@team-gateway", "#alerts-gateway"),
        "order-service": ("Orders & Checkout Pod", "@team-orders", "#dev-orders"),
        "payment-service": ("Payments & Billing Squad", "@team-billing", "#payments-eng"),
        "inventory-service": ("Supply Chain Team", "@team-inventory", "#inventory-alerts"),
        "notification-service": ("Customer Engagement Team", "@team-notif", "#notifications"),
        "analytics-worker": ("Data Platform Team", "@team-data", "#data-eng"),
    }

    @classmethod
    def generate_migration_plan(
        cls,
        findings: list[ContractFinding],
        impacted_entities: list[ImpactedEntity],
    ) -> list[MigrationStep]:
        """Generates a phased zero-downtime migration roadmap for breaking or warning changes."""
        steps: list[MigrationStep] = []
        has_breaking = any(
            f.severity.value == "BLOCKING" if hasattr(f.severity, "value") else str(f.severity) == "BLOCKING"
            for f in findings
        )

        if not has_breaking:
            # Safe change plan
            steps.append(
                MigrationStep(
                    step_number=1,
                    phase=MigrationPhase.PHASE_1_PREPARATION,
                    title="Direct In-Place Additive Deployment",
                    description="Deploy new schema fields and capabilities directly. Backward compatibility is preserved.",
                    responsible_team="Deploying Service Team",
                    rollback_plan="Standard rollback to previous container image version.",
                    estimated_duration="1 hour",
                )
            )
            return steps

        # Phase 1: Preparation & Compatibility Layer
        steps.append(
            MigrationStep(
                step_number=1,
                phase=MigrationPhase.PHASE_1_PREPARATION,
                title="Deploy Tolerant Consumer Adapters & Fallback Handlers",
                description=(
                    "Update downstream consumers to handle missing or newly typed fields with safe defaults. "
                    "Deploy consumers before activating provider changes."
                ),
                responsible_team="Downstream Consumer Teams",
                rollback_plan="Revert consumer PRs; verify existing contract tests pass.",
                estimated_duration="2-3 days",
            )
        )

        # Phase 2: Dual Write / Dual Representation
        steps.append(
            MigrationStep(
                step_number=2,
                phase=MigrationPhase.PHASE_2_DUAL_WRITE,
                title="Deploy Expand Phase (Dual-Write / Dual-Acceptance)",
                description=(
                    "Deploy provider supporting both legacy format and modern format simultaneously. "
                    "Database columns or API request bodies must accept either representation."
                ),
                responsible_team="Provider Service Team",
                rollback_plan="Roll back provider release; legacy endpoint remains operational.",
                estimated_duration="1 day",
            )
        )

        # Phase 3: Consumer Migration
        consumer_names = [e.entity_name for e in impacted_entities if e.entity_type == "Service"]
        consumer_str = ", ".join(consumer_names[:3]) if consumer_names else "all downstream clients"
        steps.append(
            MigrationStep(
                step_number=3,
                phase=MigrationPhase.PHASE_3_CONSUMER_MIGRATION,
                title="Migrate Active Traffic to New Contract Interface",
                description=f"Switch active client invocations in {consumer_str} to consume the updated payload contract.",
                responsible_team="Consumer Application Teams",
                rollback_plan="Toggle feature flag or routing canary back to legacy payload format.",
                estimated_duration="3-5 days",
            )
        )

        # Phase 4: Deprecation Notice & Telemetry Verification
        steps.append(
            MigrationStep(
                step_number=4,
                phase=MigrationPhase.PHASE_4_DEPRECATION,
                title="Deprecate Legacy Fields and Monitor Telemetry",
                description=(
                    "Emit HTTP 'Sunset' / 'Deprecation' response headers and verify in OpenTelemetry traces that "
                    "zero production calls utilize the deprecated schema."
                ),
                responsible_team="API Governance & Provider Team",
                rollback_plan="Remove deprecation headers if active traffic spikes.",
                estimated_duration="14 days (holding period)",
            )
        )

        # Phase 5: Contract Cleanup
        steps.append(
            MigrationStep(
                step_number=5,
                phase=MigrationPhase.PHASE_5_CLEANUP,
                title="Contract Phase (Remove Legacy Implementation)",
                description="Safely drop legacy schema fields, database columns, and adapter shims after zero usage confirmed.",
                responsible_team="Provider Service Team",
                rollback_plan="Re-apply dual-write compatibility shim if late consumer traffic arrives.",
                estimated_duration="1 day",
            )
        )

        return steps

    @classmethod
    def identify_affected_owners(
        cls,
        impacted_entities: list[ImpactedEntity],
    ) -> list[AffectedOwner]:
        """Maps impacted downstream services to their owning engineering teams and communication channels."""
        owners: list[AffectedOwner] = []
        seen_services: set[str] = set()

        for ent in impacted_entities:
            s_name = ent.entity_name
            if s_name in seen_services:
                continue
            seen_services.add(s_name)

            team_info = cls.DEFAULT_SERVICE_OWNERSHIP.get(
                s_name,
                (f"{s_name.replace('-', ' ').title()} Team", f"@team-{s_name}", f"#{s_name}-support"),
            )

            severity = (
                "CRITICAL"
                if ent.service_tier == ServiceTier.TIER_1
                else ("HIGH" if ent.service_tier == ServiceTier.TIER_2 else "MEDIUM")
            )

            owners.append(
                AffectedOwner(
                    service_name=s_name,
                    team_name=team_info[0],
                    owner_handle=team_info[1],
                    contact_channel=team_info[2],
                    role="Owning Service Team",
                    severity_level=severity,
                )
            )

        return owners

    @classmethod
    def recommend_compatibility_strategies(
        cls,
        findings: list[ContractFinding],
        impacted_entities: list[ImpactedEntity],
    ) -> list[CompatibilityStrategy]:
        """Recommends specific architectural patterns to prevent downstream breaking failures."""
        strategies: list[CompatibilityStrategy] = []

        has_database_change = any(
            (f.change_category.value if hasattr(f.change_category, "value") else str(f.change_category)) == "DATABASE"
            for f in findings
        )
        has_field_removal = any("REMOVED" in f.change_type for f in findings)
        has_event_change = any(
            (f.change_category.value if hasattr(f.change_category, "value") else str(f.change_category)) == "EVENT"
            for f in findings
        )

        # 1. Expand and Contract Pattern
        if has_database_change or has_field_removal:
            strategies.append(
                CompatibilityStrategy(
                    strategy_type=CompatibilityStrategyType.EXPAND_AND_CONTRACT,
                    title="Expand and Contract (Parallel Change) Pattern",
                    rationale=(
                        "Decouples database column and API field changes across deployment boundaries so that old "
                        "and new versions run concurrently without schema lock-in."
                    ),
                    implementation_steps=[
                        "Step 1: Add new field/column as nullable or with default value (Expand).",
                        "Step 2: Update code to write to both old and new columns.",
                        "Step 3: Backfill historical records.",
                        "Step 4: Update consumers to read only from new field.",
                        "Step 5: Drop legacy column after zero usage confirmed (Contract).",
                    ],
                    drawbacks_and_risks=[
                        "Requires multiple coordinated pull requests and deployments.",
                        "Temporary duplicate storage footprint during transition.",
                    ],
                )
            )

        # 2. Tolerant Reader Pattern
        strategies.append(
            CompatibilityStrategy(
                strategy_type=CompatibilityStrategyType.TOLERANT_READER,
                title="Tolerant Reader and Open-World Schema Validation",
                rationale=(
                    "Enforces that downstream consumers ignore unrecognized fields rather than failing "
                    "strict schema validation (closed-world assumption)."
                ),
                implementation_steps=[
                    "Configure Pydantic models with `model_config = ConfigDict(extra='ignore')`.",
                    "Ensure JSON parsers in TypeScript use optional chaining `data?.field` instead of hard assertions.",
                ],
                drawbacks_and_risks=["May mask unintentional field omissions if logging is not configured."],
            )
        )

        # 3. Dual Event Publishing
        if has_event_change:
            strategies.append(
                CompatibilityStrategy(
                    strategy_type=CompatibilityStrategyType.EVENT_DUAL_PUBLICATION,
                    title="Dual Event Schema Versioning",
                    rationale="Allows asynchronous event consumers on different sprint cadences to migrate independently.",
                    implementation_steps=[
                        "Publish both v1 and v2 event topics simultaneously (e.g. `orders.v1` and `orders.v2`).",
                        "Maintain translation lambda or bridge during consumer migration.",
                    ],
                    drawbacks_and_risks=["Double event throughput across messaging cluster."],
                )
            )

        return strategies
