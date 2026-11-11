"""Master Codebase Analyzer Pipeline.

Coordinates structural inspection, file ownership resolution, language dispatching,
partial failure aggregation, and candidate relationship generation with deterministic evidence.
"""

from collections import Counter
from pathlib import Path
from typing import Any

from packages.shared.config import settings
from packages.shared.ingestion.extractors.config_and_ownership_extractor import (
    ConfigAndOwnershipExtractor,
)
from packages.shared.ingestion.extractors.migration_extractor import MigrationExtractor
from packages.shared.ingestion.extractors.python_extractor import PythonExtractor
from packages.shared.ingestion.extractors.typescript_extractor import TypeScriptExtractor
from packages.shared.ingestion.models import (
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

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "coverage",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".pyc",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".zip",
    ".tar",
    ".gz",
    ".bin",
    ".woff",
    ".woff2",
    ".ttf",
}


class CodebaseAnalyzer:
    """Recursively analyzes an extracted repository sandbox and compiles normalized artifacts."""

    def __init__(self, max_file_size_bytes: int | None = None) -> None:
        self.max_file_size = max_file_size_bytes or settings.MAX_FILE_SIZE_BYTES
        self.ts_extractor = TypeScriptExtractor()

    def analyze_repository(
        self,
        repo_root: Path | str,
        tenant_id: str,
        repository_id: str,
        commit_sha: str,
        source_type: IngestionSourceType = IngestionSourceType.LOCAL_GIT,
    ) -> IngestionArtifact:
        """Executes holistic static analysis across all supported source and configuration files."""
        root = Path(repo_root).resolve()

        symbols: list[CodeSymbol] = []
        imports_exports: list[ImportExport] = []
        routes: list[RouteDefinition] = []
        client_calls: list[HttpClientCall] = []
        env_vars: list[EnvVarReference] = []
        events: list[EventPattern] = []
        db_patterns: list[DatabasePattern] = []
        migrations: list[DatabaseMigration] = []
        configs: list[ConfigDependency] = []
        ownership_rules: list[OwnershipRule] = []
        partial_errors: list[dict[str, Any]] = []

        total_files = 0
        total_loc = 0
        lang_counts: Counter[str] = Counter()

        # 1. Walk directory hierarchy
        for path in root.rglob("*"):
            if path.is_symlink():
                if not str(path.resolve()).startswith(str(root)):
                    partial_errors.append(
                        {"file_path": path.name, "error": "Symlink pointing outside sandbox skipped."}
                    )
                    continue
            if not path.is_file():
                continue

            # Check for ignored directories in path parts
            rel_parts = path.relative_to(root).parts
            if any(part in IGNORED_DIRECTORIES for part in rel_parts):
                continue

            rel_str = str(path.relative_to(root)).replace("\\", "/")
            ext = path.suffix.lower()

            if ext in BINARY_EXTENSIONS:
                continue

            file_size = path.stat().st_size
            if file_size > self.max_file_size:
                partial_errors.append(
                    {
                        "file_path": rel_str,
                        "error": f"File size {file_size} exceeds maximum limit of {self.max_file_size} bytes. Skipped.",
                    }
                )
                continue

            # Read content safely
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception as read_err:
                partial_errors.append({"file_path": rel_str, "error": f"Failed reading file content: {read_err}"})
                continue

            total_files += 1
            lines = content.splitlines()
            total_loc += len(lines)

            # Check for CODEOWNERS
            fname = path.name.lower()
            if fname == "codeowners":
                ownership_rules.extend(ConfigAndOwnershipExtractor.extract_codeowners(content, rel_str))
                continue

            # Check for Config Dependencies
            config = ConfigAndOwnershipExtractor.extract_config(content, rel_str)
            if config:
                configs.append(config)

            # Check for Migrations
            if MigrationExtractor.is_migration_file(rel_str):
                mig = MigrationExtractor.extract_migration(content, rel_str)
                if mig:
                    migrations.append(mig)

            # Dispatch Language Analyzers
            if ext == ".py":
                lang_counts["Python"] += 1
                try:
                    res = PythonExtractor.extract_source(content, rel_str)
                    if res.get("error"):
                        partial_errors.append({"file_path": rel_str, "error": res["error"]})
                    symbols.extend(res.get("symbols", []))
                    imports_exports.extend(res.get("imports_exports", []))
                    routes.extend(res.get("routes", []))
                    client_calls.extend(res.get("client_calls", []))
                    env_vars.extend(res.get("env_vars", []))
                    events.extend(res.get("events", []))
                    db_patterns.extend(res.get("db_patterns", []))
                except Exception as py_err:
                    partial_errors.append({"file_path": rel_str, "error": f"Python parser error: {py_err}"})

            elif ext in {".ts", ".tsx"}:
                lang_counts["TypeScript"] += 1
                try:
                    res = self.ts_extractor.extract_source(content, rel_str)
                    if res.get("error"):
                        partial_errors.append({"file_path": rel_str, "error": res["error"]})
                    symbols.extend(res.get("symbols", []))
                    imports_exports.extend(res.get("imports_exports", []))
                    routes.extend(res.get("routes", []))
                    client_calls.extend(res.get("client_calls", []))
                    env_vars.extend(res.get("env_vars", []))
                    events.extend(res.get("events", []))
                    db_patterns.extend(res.get("db_patterns", []))
                except Exception as ts_err:
                    partial_errors.append({"file_path": rel_str, "error": f"TypeScript parser error: {ts_err}"})

            elif ext in {".js", ".jsx", ".mjs", ".cjs"}:
                lang_counts["JavaScript"] += 1
                try:
                    res = self.ts_extractor.extract_source(content, rel_str)
                    if res.get("error"):
                        partial_errors.append({"file_path": rel_str, "error": res["error"]})
                    symbols.extend(res.get("symbols", []))
                    imports_exports.extend(res.get("imports_exports", []))
                    routes.extend(res.get("routes", []))
                    client_calls.extend(res.get("client_calls", []))
                    env_vars.extend(res.get("env_vars", []))
                    events.extend(res.get("events", []))
                    db_patterns.extend(res.get("db_patterns", []))
                except Exception as js_err:
                    partial_errors.append({"file_path": rel_str, "error": f"JavaScript parser error: {js_err}"})

        # 2. Derive Candidate Relationships with Provenance and Concrete Evidence Citations
        candidate_relationships: list[CandidateRelationship] = []

        # CALLS Candidate Relationships from Client Calls
        for call in client_calls:
            target_urn = f"urn:cseo:target:{call.url_or_path.replace(' ', '_')}"
            evidence_citation = (
                f"Static client call {call.method} {call.url_or_path} in {call.file_path}:{call.line_number}"
            )
            candidate_relationships.append(
                CandidateRelationship(
                    source_urn=f"urn:cseo:repo:{repository_id}:{call.file_path}",
                    source_type="Module",
                    target_urn=target_urn,
                    target_type="APIEndpoint",
                    rel_type="CALLS",
                    provenance="STATIC_CONFIRMED" if not call.is_dynamic else "ONTOLOGY_INFERRED",
                    confidence=1.0 if not call.is_dynamic else 0.75,
                    evidence_refs=[evidence_citation],
                    source_repo_version=commit_sha,
                )
            )

        # IMPORTS Relationships
        for imp in imports_exports:
            if imp.kind == "import" and not imp.is_external:
                evidence_citation = f"Internal import '{imp.module}' in {imp.file_path}:{imp.start_line}"
                candidate_relationships.append(
                    CandidateRelationship(
                        source_urn=f"urn:cseo:repo:{repository_id}:{imp.file_path}",
                        source_type="Module",
                        target_urn=f"urn:cseo:repo:{repository_id}:{imp.module}",
                        target_type="Module",
                        rel_type="IMPORTS",
                        provenance="STATIC_CONFIRMED",
                        confidence=1.0,
                        evidence_refs=[evidence_citation],
                        source_repo_version=commit_sha,
                    )
                )

        # Database READS/WRITES Relationships
        for db in db_patterns:
            rel_kind = "WRITES" if db.operation in {"INSERT", "UPDATE", "DELETE", "MODEL_DEF"} else "READS"
            evidence_citation = (
                f"ORM {db.operation} access to table '{db.table_or_model}' in {db.file_path}:{db.line_number}"
            )
            candidate_relationships.append(
                CandidateRelationship(
                    source_urn=f"urn:cseo:repo:{repository_id}:{db.file_path}",
                    source_type="Module",
                    target_urn=f"urn:cseo:table:{db.table_or_model}",
                    target_type="DatabaseTable",
                    rel_type=rel_kind,
                    provenance="STATIC_CONFIRMED",
                    confidence=1.0,
                    evidence_refs=[evidence_citation],
                    source_repo_version=commit_sha,
                )
            )

        # PUBLISHES / SUBSCRIBES_TO Event Relationships
        for ev in events:
            rel_type = "PUBLISHES" if ev.pattern_type == "producer" else "SUBSCRIBES_TO"
            evidence_citation = (
                f"{ev.framework} {ev.pattern_type} of '{ev.event_name_or_topic}' in {ev.file_path}:{ev.line_number}"
            )
            candidate_relationships.append(
                CandidateRelationship(
                    source_urn=f"urn:cseo:repo:{repository_id}:{ev.file_path}",
                    source_type="Module",
                    target_urn=f"urn:cseo:eventschema:{ev.event_name_or_topic}",
                    target_type="EventSchema",
                    rel_type=rel_type,
                    provenance="STATIC_CONFIRMED",
                    confidence=1.0,
                    evidence_refs=[evidence_citation],
                    source_repo_version=commit_sha,
                )
            )

        return IngestionArtifact(
            tenant_id=tenant_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            source_type=source_type,
            root_path=str(root),
            total_files=total_files,
            total_lines_of_code=total_loc,
            languages=dict(lang_counts),
            symbols=symbols,
            imports_exports=imports_exports,
            routes=routes,
            client_calls=client_calls,
            env_vars=env_vars,
            events=events,
            db_patterns=db_patterns,
            migrations=migrations,
            configs=configs,
            ownership_rules=ownership_rules,
            candidate_relationships=candidate_relationships,
            partial_errors=partial_errors,
        )
