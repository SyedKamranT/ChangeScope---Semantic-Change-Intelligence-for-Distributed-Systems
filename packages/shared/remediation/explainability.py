"""Explainability Engine enforcing clear tiering between Verified Facts, Inferred Findings, and Recommendations."""

import uuid

from packages.contracts.models import ContractFinding
from packages.shared.impact.models import ImpactedEntity
from packages.shared.remediation.models import (
    ExplainabilityFact,
    FactClassification,
    MigrationStep,
    TestRecommendation,
)


class ExplainabilityClassifier:
    """Classifies system outputs into unambiguous epistemic tiers to prevent hallucination and false certainty."""

    @classmethod
    def extract_facts_and_evidence(
        cls,
        findings: list[ContractFinding],
        impacted_entities: list[ImpactedEntity],
        test_recommendations: list[TestRecommendation],
        migration_steps: list[MigrationStep],
        recommended_action: str,
    ) -> list[ExplainabilityFact]:
        """Extracts and categorizes all statements into VERIFIED_FACT, INFERRED_FINDING, and RECOMMENDATION."""
        classified_items: list[ExplainabilityFact] = []

        # 1. Verified Facts (Direct AST, Spec, or OTel observations)
        for finding in findings:
            classified_items.append(
                ExplainabilityFact(
                    fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                    classification=FactClassification.VERIFIED_FACT,
                    statement=f"Detected contract mutation: {finding.change_type} at {finding.file_path}#L{finding.start_line}",
                    source="SPEC_AST_DIFF",
                    evidence_reference=f"{finding.file_path}#L{finding.start_line}-L{finding.end_line}",
                    confidence=1.0,
                )
            )

        for entity in impacted_entities:
            if entity.is_runtime_confirmed:
                classified_items.append(
                    ExplainabilityFact(
                        fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                        classification=FactClassification.VERIFIED_FACT,
                        statement=(
                            f"Live runtime communication observed between provider and '{entity.entity_name}' "
                            f"({entity.call_frequency_7d:,} calls/week, p95: {entity.p95_latency_ms:.1f}ms)."
                        ),
                        source="OTEL_TELEMETRY",
                        evidence_reference="; ".join(entity.evidence_citations) if entity.evidence_citations else None,
                        confidence=1.0,
                    )
                )

        # 2. Inferred Findings (Graph traversal, semantic concepts, transitive paths)
        for entity in impacted_entities:
            if entity.hop_distance > 1:
                classified_items.append(
                    ExplainabilityFact(
                        fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                        classification=FactClassification.INFERRED_FINDING,
                        statement=(
                            f"Service '{entity.entity_name}' is transitively affected at {entity.hop_distance} hops "
                            f"along path: {' -> '.join(entity.path)}."
                        ),
                        source="KNOWLEDGE_GRAPH_TRAVERSAL",
                        evidence_reference=" -> ".join(entity.path),
                        confidence=entity.path_confidence,
                    )
                )

            if entity.ontology_concepts:
                concepts_str = ", ".join(entity.ontology_concepts)
                classified_items.append(
                    ExplainabilityFact(
                        fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                        classification=FactClassification.INFERRED_FINDING,
                        statement=f"Entity '{entity.entity_name}' resolved to domain concept(s): {concepts_str}.",
                        source="ONTOLOGY_MAPPING",
                        evidence_reference=concepts_str,
                        confidence=0.90,
                    )
                )

        # 3. Recommendations (Generated tests, migration steps, policy actions)
        classified_items.append(
            ExplainabilityFact(
                fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                classification=FactClassification.RECOMMENDATION,
                statement=f"Recommended engineering policy gate: {recommended_action}.",
                source="DETERMINISTIC_RISK_POLICY",
                confidence=1.0,
            )
        )

        for test in test_recommendations:
            classified_items.append(
                ExplainabilityFact(
                    fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                    classification=FactClassification.RECOMMENDATION,
                    statement=f"Targeted regression test proposed for {test.affected_service}: {test.test_objective}.",
                    source="TEST_SYNTHESIZER",
                    evidence_reference="; ".join(test.evidence_references),
                    confidence=test.confidence,
                )
            )

        for step in migration_steps:
            classified_items.append(
                ExplainabilityFact(
                    fact_id=f"fact-{uuid.uuid4().hex[:8]}",
                    classification=FactClassification.RECOMMENDATION,
                    statement=f"Migration Step {step.step_number} ({step.phase.value}): {step.title}.",
                    source="MIGRATION_PLANNER",
                    confidence=1.0,
                )
            )

        return classified_items
