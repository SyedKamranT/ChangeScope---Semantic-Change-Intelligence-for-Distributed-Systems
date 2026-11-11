"""Base evaluation baseline class interface."""

from abc import ABC, abstractmethod

from packages.benchmarks.models import BaselinePrediction, BenchmarkScenario


class BaseBaseline(ABC):
    """Abstract base contract for evaluation baselines."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def evaluate(self, scenario: BenchmarkScenario) -> BaselinePrediction:
        """Executes change detection on a scenario and returns standardized predictions."""
        pass
