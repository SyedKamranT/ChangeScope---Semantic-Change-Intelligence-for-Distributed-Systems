"""ChangeScope Ontology Integration Layer Package."""

from packages.shared.ontology.base import (
    CandidateDiscoveryResult,
    CertificationResult,
    CircuitBreakerState,
    ConceptReconciliationResult,
    ModelExportResult,
    ModelImportResult,
    OntologyProvider,
    ProviderStatus,
    RelationshipResolutionResult,
    ValidationResult,
)
from packages.shared.ontology.local_provider import LocalOntologyProvider
from packages.shared.ontology.nvidia_provider import NvidiaAutoOntologyProvider
from packages.shared.ontology.ossie_serializer import OssieSerializer


def get_ontology_provider(provider_type: str | None = None) -> OntologyProvider:
    """Factory creating configured ontology provider (local or nvidia)."""
    from packages.shared.config import settings

    target = (provider_type or settings.ONTOLOGY_PROVIDER).lower()
    if target == "nvidia":
        return NvidiaAutoOntologyProvider()
    return LocalOntologyProvider()


__all__ = [
    "OntologyProvider",
    "LocalOntologyProvider",
    "NvidiaAutoOntologyProvider",
    "OssieSerializer",
    "CandidateDiscoveryResult",
    "ConceptReconciliationResult",
    "RelationshipResolutionResult",
    "ValidationResult",
    "CertificationResult",
    "ModelImportResult",
    "ModelExportResult",
    "ProviderStatus",
    "CircuitBreakerState",
    "get_ontology_provider",
]
