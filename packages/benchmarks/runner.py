"""ChangeScope Comprehensive Benchmark Execution & Metrics Calculation Engine."""

from typing import Any

from packages.benchmarks.baselines.base import BaseBaseline
from packages.benchmarks.baselines.changescope_engine import BaselineCFullChangeScope
from packages.benchmarks.baselines.static_analysis import BaselineBStaticAnalysis
from packages.benchmarks.baselines.structural_diff import BaselineAStructuralDiff
from packages.benchmarks.dataset import build_golden_dataset
from packages.benchmarks.models import (
    BaselinePrediction,
    BenchmarkScenario,
    DatasetSplit,
    MetricSummary,
)
from packages.benchmarks.stress_tests import StressTestRunner


class BenchmarkRunner:
    """Orchestrates multi-baseline benchmark evaluation across Development and Holdout dataset splits."""

    def __init__(
        self,
        scenarios: list[BenchmarkScenario] | None = None,
        use_ollama: bool = True,
        ollama_model: str = "qwen3:4b",
        ollama_sample_count: int | None = 3,
        baseline_filter: str = "all",
    ) -> None:
        self.scenarios = scenarios or build_golden_dataset()
        all_baselines: list[BaseBaseline] = [
            BaselineAStructuralDiff(),
            BaselineBStaticAnalysis(),
            BaselineCFullChangeScope(
                use_ollama=use_ollama,
                ollama_model=ollama_model,
                ollama_sample_count=ollama_sample_count,
            ),
        ]
        if baseline_filter == "a":
            self.baselines = [b for b in all_baselines if "Baseline A" in b.name]
        elif baseline_filter == "b":
            self.baselines = [b for b in all_baselines if "Baseline B" in b.name]
        elif baseline_filter == "c":
            self.baselines = [b for b in all_baselines if "Baseline C" in b.name]
        else:
            self.baselines = all_baselines

    def run_all(self, run_stress_tests: bool = True) -> dict[str, Any]:
        """Executes full benchmark evaluation across all baselines, splits, and stress tests."""
        raw_predictions: dict[str, list[BaselinePrediction]] = {}
        split_metrics: dict[str, dict[str, MetricSummary]] = {
            "OVERALL": {},
            "DEVELOPMENT": {},
            "HOLDOUT": {},
        }

        # 1. Run Baselines
        for baseline in self.baselines:
            preds: list[BaselinePrediction] = []
            for sc in self.scenarios:
                pred = baseline.evaluate(sc)
                preds.append(pred)
            raw_predictions[baseline.name] = preds

            # Compute metrics for overall, dev, and holdout splits
            split_metrics["OVERALL"][baseline.name] = self._compute_metrics(
                baseline_name=baseline.name,
                split_name="OVERALL",
                scenarios=self.scenarios,
                predictions=preds,
            )

            dev_scenarios = [s for s in self.scenarios if s.split == DatasetSplit.DEVELOPMENT]
            dev_preds = [p for s, p in zip(self.scenarios, preds, strict=True) if s.split == DatasetSplit.DEVELOPMENT]
            split_metrics["DEVELOPMENT"][baseline.name] = self._compute_metrics(
                baseline_name=baseline.name,
                split_name="DEVELOPMENT",
                scenarios=dev_scenarios,
                predictions=dev_preds,
            )

            holdout_scenarios = [s for s in self.scenarios if s.split == DatasetSplit.HOLDOUT]
            holdout_preds = [p for s, p in zip(self.scenarios, preds, strict=True) if s.split == DatasetSplit.HOLDOUT]
            split_metrics["HOLDOUT"][baseline.name] = self._compute_metrics(
                baseline_name=baseline.name,
                split_name="HOLDOUT",
                scenarios=holdout_scenarios,
                predictions=holdout_preds,
            )

        # 2. Run Stress Tests
        stress_results = {}
        if run_stress_tests:
            stress_results = {
                "missing_telemetry": StressTestRunner.test_missing_telemetry(),
                "incomplete_ontology": StressTestRunner.test_incomplete_ontology(),
                "conflicting_mappings": StressTestRunner.test_conflicting_mappings(),
                "uncertain_inference": StressTestRunner.test_uncertain_inference(),
                "scalability_benchmarks": StressTestRunner.test_large_repository_scale(),
            }

        return {
            "scenarios_count": len(self.scenarios),
            "dev_count": sum(1 for s in self.scenarios if s.split == DatasetSplit.DEVELOPMENT),
            "holdout_count": sum(1 for s in self.scenarios if s.split == DatasetSplit.HOLDOUT),
            "split_metrics": split_metrics,
            "raw_predictions": raw_predictions,
            "stress_tests": stress_results,
        }

    def _compute_metrics(
        self,
        baseline_name: str,
        split_name: str,
        scenarios: list[BenchmarkScenario],
        predictions: list[BaselinePrediction],
    ) -> MetricSummary:
        """Calculates rigorous precision, recall, F1, FPR, FNR, consumer discovery, and path accuracy."""
        tp = fp = tn = fn = 0
        actual_breaking_count = 0
        detected_breaking_count = 0
        actual_semantic_count = 0
        detected_semantic_count = 0

        consumer_jaccard_scores: list[float] = []
        path_accuracy_scores: list[float] = []
        latencies: list[float] = []
        total_cost = 0.0

        for sc, pred in zip(scenarios, predictions, strict=True):
            gt = sc.ground_truth
            latencies.append(pred.execution_latency_ms)
            total_cost += pred.estimated_cost_usd

            # Breaking change ground truth
            if gt.is_breaking:
                actual_breaking_count += 1
                if pred.flagged_as_breaking:
                    tp += 1
                    detected_breaking_count += 1
                else:
                    fn += 1
            else:
                if pred.flagged_as_breaking:
                    fp += 1
                else:
                    tn += 1

            # Semantic drift ground truth
            if gt.is_semantic_drift:
                actual_semantic_count += 1
                if pred.detected_semantic_drift:
                    detected_semantic_count += 1

            # Consumer discovery Jaccard accuracy: |A ∩ B| / |A ∪ B|
            gt_consumers = set(gt.expected_affected_entities)
            pred_consumers = set(pred.affected_entities)
            if not gt_consumers and not pred_consumers:
                consumer_jaccard_scores.append(1.0)
            elif not gt_consumers or not pred_consumers:
                consumer_jaccard_scores.append(0.0)
            else:
                inter = len(gt_consumers & pred_consumers)
                union = len(gt_consumers | pred_consumers)
                consumer_jaccard_scores.append(inter / union if union > 0 else 0.0)

            # Impact path accuracy: proportion of expected paths matched
            if not gt.expected_impact_paths:
                path_accuracy_scores.append(1.0 if not pred.impact_paths else 0.5)
            else:
                matched_paths = 0
                for exp_path in gt.expected_impact_paths:
                    for pred_path in pred.impact_paths:
                        # Match if endpoints or hops intersect
                        if set(exp_path).issubset(set(pred_path)) or set(pred_path).issubset(set(exp_path)):
                            matched_paths += 1
                            break
                path_accuracy_scores.append(min(1.0, matched_paths / len(gt.expected_impact_paths)))

        # Precision, Recall, F1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / len(scenarios) if scenarios else 0.0

        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

        breaking_detection_rate = detected_breaking_count / actual_breaking_count if actual_breaking_count > 0 else 1.0
        semantic_detection_rate = detected_semantic_count / actual_semantic_count if actual_semantic_count > 0 else 1.0

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        sorted_latencies = sorted(latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[p95_idx] if sorted_latencies else 0.0

        avg_consumer_acc = (
            sum(consumer_jaccard_scores) / len(consumer_jaccard_scores) if consumer_jaccard_scores else 0.0
        )
        avg_path_acc = sum(path_accuracy_scores) / len(path_accuracy_scores) if path_accuracy_scores else 0.0

        return MetricSummary(
            baseline_name=baseline_name,
            split=split_name,
            total_scenarios=len(scenarios),
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1_score=round(f1, 4),
            accuracy=round(accuracy, 4),
            breaking_detection_rate=round(breaking_detection_rate, 4),
            semantic_drift_detection_rate=round(semantic_detection_rate, 4),
            consumer_discovery_accuracy=round(avg_consumer_acc, 4),
            impact_path_accuracy=round(avg_path_acc, 4),
            false_positive_rate=round(fpr, 4),
            false_negative_rate=round(fnr, 4),
            avg_latency_ms=round(avg_latency, 2),
            p95_latency_ms=round(p95_latency, 2),
            total_cost_usd=round(total_cost, 4),
        )
