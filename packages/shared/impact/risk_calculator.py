"""Deterministic and Explainable Risk Scoring Engine for ChangeScope."""

import math

from packages.shared.impact.models import (
    ExposureLevel,
    ImpactedEntity,
    RecommendedAction,
    RiskBreakdown,
    ServiceTier,
)


class RiskCalculator:
    """Transparent, deterministic risk assessment engine separating impact breadth from failure significance."""

    SEVERITY_WEIGHTS = {
        "BLOCKING": 50.0,
        "WARNING": 25.0,
        "INFO": 5.0,
    }

    TIER_BASE_WEIGHTS = {
        ServiceTier.TIER_1: 20.0,
        ServiceTier.TIER_2: 10.0,
        ServiceTier.TIER_3: 5.0,
    }

    EXPOSURE_MULTIPLIERS = {
        ExposureLevel.PUBLIC_INTERNET: 1.30,
        ExposureLevel.PARTNER_API: 1.15,
        ExposureLevel.INTERNAL_SERVICE: 1.00,
        ExposureLevel.RESTRICTED: 0.85,
    }

    @classmethod
    def calculate_risk(
        cls,
        max_severity: str,
        impacted_entities: list[ImpactedEntity],
        affected_workflows: list[str],
        has_conflicts: bool = False,
        dispute_count: int = 0,
        uncertified_candidate_count: int = 0,
    ) -> tuple[int, str, RecommendedAction, RiskBreakdown]:
        """Calculates deterministic risk score (0-100), risk level, action, and complete explainable breakdown."""
        # 1. Base Severity Score
        base_sev = cls.SEVERITY_WEIGHTS.get(max_severity.upper(), 10.0)

        accumulated_impact = 0.0

        total_reachability = 0.0
        total_usage_factor = 0.0
        total_criticality = 0.0
        total_exposure = 0.0
        total_freshness = 0.0

        explanation_lines: list[str] = [f"1. Base Severity: {base_sev:.1f} (from max severity: {max_severity.upper()})"]

        # 2. Per-Consumer Reachability, Criticality, Usage, Exposure, and Freshness
        for entity in impacted_entities:
            # Criticality
            tier_val = (
                ServiceTier(entity.service_tier)
                if entity.service_tier in ServiceTier._value2member_map_
                else ServiceTier.TIER_2
            )
            crit = cls.TIER_BASE_WEIGHTS.get(tier_val, 10.0)
            if any(wf in affected_workflows for wf in entity.ontology_concepts) or len(affected_workflows) > 0:
                crit += 5.0  # Workflow involvement boost

            # Reachability (decay by hop distance)
            hop = max(1, entity.hop_distance)
            reachability = (1.0 / hop) * max(0.1, min(1.0, entity.path_confidence))

            # Observed Usage
            usage_mult = math.log10(max(0, entity.call_frequency_7d) + 10.0)

            # Exposure
            exp_val = (
                ExposureLevel(entity.exposure)
                if entity.exposure in ExposureLevel._value2member_map_
                else ExposureLevel.INTERNAL_SERVICE
            )
            exposure_mult = cls.EXPOSURE_MULTIPLIERS.get(exp_val, 1.0)

            # Freshness
            freshness_mult = 1.0
            if entity.is_runtime_confirmed:
                freshness_mult = 1.0  # Freshly observed in current active window
            else:
                freshness_mult = 0.85  # Static-only or unexercised

            # Semantic Confidence
            sem_conf = max(0.5, min(1.0, entity.path_confidence))

            entity_score = crit * reachability * usage_mult * exposure_mult * freshness_mult * sem_conf
            accumulated_impact += entity_score

            total_reachability += reachability
            total_usage_factor += usage_mult
            total_criticality += crit
            total_exposure += exposure_mult
            total_freshness += freshness_mult

        consumer_count = len(impacted_entities)
        avg_reach = (total_reachability / consumer_count) if consumer_count > 0 else 0.0
        avg_usage = (total_usage_factor / consumer_count) if consumer_count > 0 else 1.0
        avg_crit = (total_criticality / consumer_count) if consumer_count > 0 else 0.0
        avg_exp = (total_exposure / consumer_count) if consumer_count > 0 else 1.0
        avg_fresh = (total_freshness / consumer_count) if consumer_count > 0 else 1.0

        explanation_lines.append(
            f"2. Downstream Consumers: {consumer_count} entities evaluated. "
            f"Accumulated Impact Score: {accumulated_impact:.2f} "
            f"(Avg Criticality: {avg_crit:.1f}, Avg Reachability: {avg_reach:.2f}, Avg Usage Multiplier: {avg_usage:.2f})"
        )

        # 3. Uncertainty and Dispute Penalty
        uncertainty_penalty = 0.0
        if has_conflicts or dispute_count > 0:
            uncertainty_penalty += min(15.0, dispute_count * 7.5 if dispute_count > 0 else 10.0)
            explanation_lines.append(
                f"3. Uncertainty Penalty: +{uncertainty_penalty:.1f} due to {dispute_count} active ontology disputes."
            )
        if uncertified_candidate_count > 0:
            candidate_penalty = min(10.0, uncertified_candidate_count * 2.5)
            uncertainty_penalty += candidate_penalty
            explanation_lines.append(
                f"   Uncertified Candidates Penalty: +{candidate_penalty:.1f} ({uncertified_candidate_count} candidates)."
            )

        if uncertainty_penalty == 0.0:
            explanation_lines.append("3. Uncertainty Penalty: 0.0 (All relationships certified, zero disputes).")

        # 4. Total Raw & Final Score Calculation
        total_raw = base_sev + accumulated_impact + uncertainty_penalty
        final_score = min(100, max(0, int(round(total_raw))))

        explanation_lines.append(
            f"4. Total Score: min(100, round({base_sev:.1f} + {accumulated_impact:.2f} + {uncertainty_penalty:.1f})) = {final_score}"
        )

        # 5. Risk Level and Action Determination
        risk_level = cls.classify_risk_level(final_score)
        recommended_action = cls.determine_recommended_action(risk_level, max_severity)

        explanation_lines.append(f"5. Classification: {risk_level} Risk -> Action: {recommended_action.value}")

        breakdown = RiskBreakdown(
            base_severity_score=base_sev,
            reachability_score=round(avg_reach, 3),
            usage_multiplier=round(avg_usage, 3),
            criticality_score=round(avg_crit, 2),
            exposure_factor=round(avg_exp, 2),
            freshness_factor=round(avg_fresh, 2),
            semantic_confidence_factor=1.0,
            uncertainty_penalty=round(uncertainty_penalty, 2),
            total_raw_score=round(total_raw, 2),
            final_score=final_score,
            formula_explanation="\n".join(explanation_lines),
            factors={
                "base_severity": base_sev,
                "accumulated_impact": accumulated_impact,
                "uncertainty_penalty": uncertainty_penalty,
                "consumer_count": float(consumer_count),
                "workflows_count": float(len(affected_workflows)),
            },
        )

        return final_score, risk_level, recommended_action, breakdown

    @staticmethod
    def classify_risk_level(score: int) -> str:
        """Categorizes raw risk score into actionable levels."""
        if score >= 80:
            return "CRITICAL"
        elif score >= 60:
            return "HIGH"
        elif score >= 35:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def determine_recommended_action(risk_level: str, severity: str) -> RecommendedAction:
        """Determines engineering gate policy based on risk and change severity."""
        if risk_level == "CRITICAL" or (severity.upper() == "BLOCKING" and risk_level in {"CRITICAL", "HIGH"}):
            return RecommendedAction.BLOCK_MERGE
        elif risk_level == "HIGH":
            return RecommendedAction.REQUIRE_MANUAL_APPROVAL
        elif risk_level == "MEDIUM":
            return RecommendedAction.RUN_CANARY_TESTS
        elif severity.upper() == "WARNING":
            return RecommendedAction.NOTIFY_SERVICE_OWNERS
        return RecommendedAction.PROCEED_WITH_MONITORING
