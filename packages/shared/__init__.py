"""ChangeScope Shared Kernel Package."""

from packages.shared.ontology import (
    LocalOntologyProvider,
    NvidiaAutoOntologyProvider,
    OntologyProvider,
    OssieSerializer,
    get_ontology_provider,
)
from packages.shared.ontology_governance import OntologyGovernanceManager
from packages.shared.ontology_models import (
    BusinessConceptEntity,
    CandidateReviewStatus,
    CoreEntityType,
    OntologyCandidate,
    OntologyDispute,
    OntologyEntity,
    OntologyRelationship,
    OntologyVersionRecord,
    ProvenanceType,
    RelationshipStatus,
    RelationshipType,
    SemanticConceptCategory,
)

__version__ = "0.1.0"

__all__ = [
    "OntologyEntity",
    "OntologyRelationship",
    "BusinessConceptEntity",
    "OntologyCandidate",
    "OntologyDispute",
    "OntologyVersionRecord",
    "CoreEntityType",
    "RelationshipType",
    "ProvenanceType",
    "RelationshipStatus",
    "CandidateReviewStatus",
    "SemanticConceptCategory",
    "OntologyGovernanceManager",
    "OntologyProvider",
    "LocalOntologyProvider",
    "NvidiaAutoOntologyProvider",
    "OssieSerializer",
    "get_ontology_provider",
]
