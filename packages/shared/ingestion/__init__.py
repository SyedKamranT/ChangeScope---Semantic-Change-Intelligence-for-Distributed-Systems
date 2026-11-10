"""ChangeScope Repository Ingestion Subsystem."""

from packages.shared.ingestion.extractors.codebase_analyzer import CodebaseAnalyzer
from packages.shared.ingestion.extractors.config_and_ownership_extractor import (
    ConfigAndOwnershipExtractor,
)
from packages.shared.ingestion.extractors.migration_extractor import MigrationExtractor
from packages.shared.ingestion.extractors.python_extractor import PythonExtractor
from packages.shared.ingestion.extractors.typescript_extractor import TypeScriptExtractor
from packages.shared.ingestion.models import (
    CallRelationship,
    CandidateRelationship,
    CodeSymbol,
    ConfigDependency,
    DatabaseMigration,
    DatabasePattern,
    EnvVarReference,
    EventPattern,
    HttpClientCall,
    ImportExport,
    IngestionArtifact,
    IngestionSourceType,
    OwnershipRule,
    RouteDefinition,
)
from packages.shared.ingestion.pipeline import IngestionPipeline
from packages.shared.ingestion.safety import RepoSafetyGuard
from packages.shared.ingestion.sources.archive import ArchiveSource
from packages.shared.ingestion.sources.github import GitHubRepoSource
from packages.shared.ingestion.sources.github_pr import ChangedFile, GitHubPRIngestor, PRMetadata
from packages.shared.ingestion.sources.local_git import LocalGitSource

__all__ = [
    "RepoSafetyGuard",
    "IngestionSourceType",
    "CodeSymbol",
    "ImportExport",
    "CallRelationship",
    "RouteDefinition",
    "HttpClientCall",
    "EnvVarReference",
    "EventPattern",
    "DatabasePattern",
    "DatabaseMigration",
    "ConfigDependency",
    "OwnershipRule",
    "CandidateRelationship",
    "IngestionArtifact",
    "PythonExtractor",
    "TypeScriptExtractor",
    "MigrationExtractor",
    "ConfigAndOwnershipExtractor",
    "CodebaseAnalyzer",
    "LocalGitSource",
    "ArchiveSource",
    "GitHubRepoSource",
    "GitHubPRIngestor",
    "PRMetadata",
    "ChangedFile",
    "IngestionPipeline",
]
