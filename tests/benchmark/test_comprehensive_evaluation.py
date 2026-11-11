"""ChangeScope Comprehensive Benchmark & Empirical Evaluation Test Suite.

Verifies:
1. 52 Seeded change scenarios across 15 categories execute without error.
2. Baseline C (Full ChangeScope) strictly outperforms Baseline A and Baseline B on F1 and Recall.
3. Semantic drift detection is 100% on ChangeScope and 0% on Baselines A and B.
4. Category 15 negative controls yield 0.0% false positive rate (no false alarms).
5. Generalization: Holdout split F1 score within 5% of Development split (no overfitting).
6. Deterministic execution latency per scenario is strictly under 250ms SLA.
7. Resilience stress tests (missing telemetry, incomplete ontology, conflicting mappings,
   uncertain inference, and 1,000-node graph scaling) pass all invariants.
8. CitationVerificationGuard properly sanitizes ungrounded narrative text.
"""

from __future__ import annotations

import pytest

from packages.benchmarks.dataset import build_golden_dataset
from packages.benchmarks.models import DatasetSplit, ScenarioCategory
from packages.benchmarks.runner import BenchmarkRunner
from packages.shared.remediation.citation_guard import CitationVerificationGuard


@pytest.fixture(scope="module")
def benchmark_results():
    """Runs full benchmark suite across all 52 scenarios and 3 baselines."""
    # Use deterministic mode for fast, reproducible regression execution
    runner = BenchmarkRunner(use_ollama=False)
    return runner.run_all(run_stress_tests=True)


class TestComprehensiveEvaluation:
    """Rigorous scientific verification of ChangeScope against Baselines A & B."""

    def test_golden_dataset_structure(self):
        """Verifies dataset has at least 50 scenarios and strictly separates dev and holdout splits."""
        scenarios = build_golden_dataset()
        assert len(scenarios) >= 50, f"Expected at least 50 scenarios, found {len(scenarios)}"

        # Check all 15 categories are populated
        present_categories = {s.category for s in scenarios}
        assert len(present_categories) == 15, f"Expected 15 categories, found {len(present_categories)}"

        # Check strict split separation
        dev_count = sum(1 for s in scenarios if s.split == DatasetSplit.DEVELOPMENT)
        holdout_count = sum(1 for s in scenarios if s.split == DatasetSplit.HOLDOUT)
        assert dev_count >= 30, f"Development set too small: {dev_count}"
        assert holdout_count >= 15, f"Holdout set too small: {holdout_count}"

    def test_all_scenarios_execute_across_baselines(self, benchmark_results):
        """Ensures all 52 scenarios execute through Baselines A, B, and C without exceptions."""
        raw_preds = benchmark_results["raw_predictions"]
        assert "Baseline A (Structural Diff)" in raw_preds
        assert "Baseline B (Static Analysis)" in raw_preds
        assert "Baseline C (ChangeScope)" in raw_preds

        assert len(raw_preds["Baseline A (Structural Diff)"]) == 52
        assert len(raw_preds["Baseline B (Static Analysis)"]) == 52
        assert len(raw_preds["Baseline C (ChangeScope)"]) == 52

    def test_changescope_f1_superiority(self, benchmark_results):
        """Verifies Baseline C achieves strictly superior F1-score compared to Baseline A and Baseline B."""
        overall = benchmark_results["split_metrics"]["OVERALL"]
        f1_a = overall["Baseline A (Structural Diff)"].f1_score
        f1_b = overall["Baseline B (Static Analysis)"].f1_score
        f1_c = overall["Baseline C (ChangeScope)"].f1_score

        # ChangeScope must exceed baselines by at least 20 percentage points
        assert f1_c > f1_a + 0.20, f"F1_C ({f1_c}) not significantly higher than F1_A ({f1_a})"
        assert f1_c > f1_b + 0.20, f"F1_C ({f1_c}) not significantly higher than F1_B ({f1_b})"
        assert f1_c >= 0.95, f"Expected ChangeScope F1 >= 0.95, got {f1_c}"

    def test_semantic_drift_detection(self, benchmark_results):
        """Verifies ChangeScope detects 100% of semantic drift scenarios where Baselines A and B score 0%."""
        overall = benchmark_results["split_metrics"]["OVERALL"]
        sem_a = overall["Baseline A (Structural Diff)"].semantic_drift_detection_rate
        sem_b = overall["Baseline B (Static Analysis)"].semantic_drift_detection_rate
        sem_c = overall["Baseline C (ChangeScope)"].semantic_drift_detection_rate

        assert sem_a == 0.0, f"Baseline A unexpectedly detected semantic drift: {sem_a}"
        assert sem_b == 0.0, f"Baseline B unexpectedly detected semantic drift: {sem_b}"
        assert sem_c == 1.0, f"Baseline C missed semantic drift scenarios: {sem_c}"

    def test_zero_false_positive_rate_on_controls(self, benchmark_results):
        """Verifies Category 15 negative controls produce exactly 0% false positive rate on ChangeScope."""
        overall = benchmark_results["split_metrics"]["OVERALL"]
        fpr_c = overall["Baseline C (ChangeScope)"].false_positive_rate
        assert fpr_c == 0.0, f"ChangeScope had false positives on harmless changes: FPR={fpr_c}"

        # Inspect raw predictions for Category 15 scenarios (SCEN-46 to SCEN-52)
        scenarios = build_golden_dataset()
        c_preds = benchmark_results["raw_predictions"]["Baseline C (ChangeScope)"]
        for sc, pred in zip(scenarios, c_preds, strict=True):
            if sc.category == ScenarioCategory.UNRELATED_CHANGES:
                assert not pred.flagged_as_breaking, (
                    f"False alarm on negative control {sc.scenario_id}: {pred.emitted_findings}"
                )

    def test_holdout_generalization_no_overfitting(self, benchmark_results):
        """Verifies Holdout split F1 score is within 5% of Development split, proving no overfitting."""
        dev_m = benchmark_results["split_metrics"]["DEVELOPMENT"]["Baseline C (ChangeScope)"]
        holdout_m = benchmark_results["split_metrics"]["HOLDOUT"]["Baseline C (ChangeScope)"]

        # Ensure performance on unseen holdout test cases is exceptionally high
        assert holdout_m.f1_score >= 0.90, f"Holdout F1 too low: {holdout_m.f1_score}"
        delta = abs(dev_m.f1_score - holdout_m.f1_score)
        assert delta <= 0.05, f"Overfitting detected: dev F1={dev_m.f1_score}, holdout F1={holdout_m.f1_score}"

    def test_deterministic_latency_sla(self, benchmark_results):
        """Verifies that deterministic execution latency per scenario is strictly under 250ms SLA."""
        c_preds = benchmark_results["raw_predictions"]["Baseline C (ChangeScope)"]
        for pred in c_preds:
            assert pred.execution_latency_ms < 250.0, (
                f"Scenario {pred.scenario_id} violated <250ms latency SLA: {pred.execution_latency_ms}ms"
            )

        overall_c = benchmark_results["split_metrics"]["OVERALL"]["Baseline C (ChangeScope)"]
        assert overall_c.avg_latency_ms < 5.0, f"Average latency too high: {overall_c.avg_latency_ms}ms"

    def test_edge_case_stress_resilience(self, benchmark_results):
        """Verifies engine robustness across missing telemetry, incomplete ontology, and 1,000 nodes."""
        stress = benchmark_results["stress_tests"]

        # 1. Missing telemetry
        assert stress["missing_telemetry"]["passed"] is True
        assert stress["missing_telemetry"]["detected_entities"] >= 1

        # 2. Incomplete ontology
        assert stress["incomplete_ontology"]["passed"] is True

        # 3. Conflicting mappings
        assert stress["conflicting_mappings"]["passed"] is True

        # 4. Uncertain inference
        assert stress["uncertain_inference"]["passed"] is True
        assert stress["uncertain_inference"]["requires_human_review"] is True

        # 5. Graph scalability across 100, 500, 1000 nodes
        scales = stress["scalability_benchmarks"]
        assert len(scales) == 3
        for scale in scales:
            assert scale["passed"] is True
            assert scale["latency_ms"] < 100.0, f"Scale tier {scale['tier']} exceeded 100ms SLA"

    def test_citation_verification_guard_invariant(self):
        """Verifies CitationVerificationGuard sanitizes ungrounded narrative text and trace IDs."""
        verified_files = {"services/payment/openapi.yaml"}
        verified_traces = {"trace-12345678901234567890123456789012"}

        # 1. Grounded narrative passes cleanly
        valid_narrative = (
            "Change to (`services/payment/openapi.yaml`) verified by trace-12345678901234567890123456789012."
        )
        is_valid, sanitized = CitationVerificationGuard.verify_and_sanitize_narrative(
            candidate_markdown=valid_narrative,
            verified_file_paths=verified_files,
            verified_trace_ids=verified_traces,
        )
        assert is_valid is True
        assert sanitized == valid_narrative

        # 2. Hallucinated file path and unverified trace ID are redacted
        hallucinated_narrative = (
            "Change to (`services/unverified/ghost.py`) verified by trace-99999999999999999999999999999999."
        )
        is_valid, sanitized = CitationVerificationGuard.verify_and_sanitize_narrative(
            candidate_markdown=hallucinated_narrative,
            verified_file_paths=verified_files,
            verified_trace_ids=verified_traces,
        )
        assert is_valid is False
        assert "[UNVERIFIED_PATH_REDACTED]" in sanitized
        assert "[UNVERIFIED_TRACE_REDACTED]" in sanitized
        assert "ghost.py" not in sanitized
        assert "trace-99999999999999999999999999999999" not in sanitized
