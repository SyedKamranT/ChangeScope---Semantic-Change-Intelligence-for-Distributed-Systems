"""End-to-End Ingestion Pipeline Orchestrator."""

import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.shared.database import async_session_factory
from packages.shared.ingestion.extractors.codebase_analyzer import CodebaseAnalyzer
from packages.shared.ingestion.models import IngestionArtifact, IngestionSourceType
from packages.shared.ingestion.safety import RepoSafetyGuard
from packages.shared.ingestion.sources.archive import ArchiveSource
from packages.shared.ingestion.sources.github import GitHubRepoSource
from packages.shared.ingestion.sources.local_git import LocalGitSource
from packages.shared.models import ASTSymbol, ScanRun, utc_now
from packages.shared.ontology_models import CandidateReviewStatus, OntologyCandidate


class IngestionPipeline:
    """Orchestrates source fetching, sandboxed extraction, static analysis, and database persistence."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession] | None = None) -> None:
        self.session_maker = session_maker or async_session_factory
        self.analyzer = CodebaseAnalyzer()

    async def ingest_and_analyze(
        self,
        tenant_id: str,
        workspace_id: str,
        repository_id: str,
        source_type: IngestionSourceType,
        source_location: str | Path,
        commit_sha: str | None = None,
        auth_token: str | None = None,
        scan_id: str | None = None,
    ) -> IngestionArtifact:
        """Executes full sandboxed ingestion and AST analysis, persisting symbols to canonical storage."""
        # 1. Prepare tenant-scoped sandbox directory
        target_sha = commit_sha or "0000000000000000000000000000000000000000"
        dest_dir = RepoSafetyGuard.get_tenant_storage_path(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            repo_id=repository_id,
            commit_sha=target_sha,
        )

        # 2. Extract source files & execute static analysis with guaranteed ephemeral wipe
        try:
            extracted_dir: Path
            final_sha: str

            if source_type == IngestionSourceType.LOCAL_GIT:
                extracted_dir, final_sha = LocalGitSource.ingest_local_repo(
                    source_path=source_location,
                    destination_dir=dest_dir,
                    commit_sha=commit_sha,
                )
            elif source_type == IngestionSourceType.UPLOADED_ARCHIVE:
                extracted_dir, final_sha = ArchiveSource.ingest_archive(
                    archive_path=source_location,
                    destination_dir=dest_dir,
                    commit_sha=commit_sha,
                )
            elif source_type == IngestionSourceType.GITHUB_REPO:
                extracted_dir, final_sha = GitHubRepoSource.ingest_remote_repo(
                    clone_url=str(source_location),
                    commit_sha=commit_sha or "0" * 40,
                    destination_dir=dest_dir,
                    auth_token=auth_token,
                )
            else:
                extracted_dir, final_sha = dest_dir, target_sha

            # 3. Execute deterministic static analysis
            artifact = self.analyzer.analyze_repository(
                repo_root=extracted_dir,
                tenant_id=tenant_id,
                repository_id=repository_id,
                commit_sha=final_sha,
                source_type=source_type,
            )
        finally:
            # Zero-Source-Code-Retention invariant (ADR-008): wipe ephemeral sandbox immediately after extraction
            shutil.rmtree(dest_dir, ignore_errors=True)

        # 4. Persist extracted AST Symbols and Candidates to canonical relational database
        async with self.session_maker() as session:
            # Query or update scan run if provided
            if scan_id:
                scan_stmt = select(ScanRun).where(ScanRun.id == scan_id)
                scan_res = await session.execute(scan_stmt)
                scan = scan_res.scalar_one_or_none()
                if scan:
                    scan.base_sha = scan.base_sha or final_sha
                    scan.head_sha = final_sha
                    # Record partial errors without failing scan
                    if artifact.partial_errors:
                        metadata = getattr(scan, "metadata_payload", {}) or {}
                        metadata["partial_errors"] = artifact.partial_errors
                        scan.error_message = f"{len(artifact.partial_errors)} file(s) had partial parsing warnings."

            # Insert ASTSymbol records
            for sym in artifact.symbols:
                ast_sym = ASTSymbol(
                    id=str(uuid.uuid4()),
                    scan_id=scan_id or str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    file_path=sym.file_path,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    symbol_type=sym.symbol_type,
                    name=sym.name,
                    signature=sym.signature,
                    metadata_payload={
                        "decorators": sym.decorators,
                        "docstring": sym.docstring,
                    },
                )
                session.add(ast_sym)

            # Insert Candidate Relationships into ontology_candidates table
            for cand_rel in artifact.candidate_relationships:
                cand = OntologyCandidate(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    candidate_type="RELATIONSHIP",
                    proposed_payload={
                        "rel_type": cand_rel.rel_type,
                        "source_type": cand_rel.source_type,
                        "target_type": cand_rel.target_type,
                        "source_urn": cand_rel.source_urn,
                        "target_urn": cand_rel.target_urn,
                        "provenance": cand_rel.provenance,
                        "source_repo_version": cand_rel.source_repo_version,
                    },
                    source_scanner="STATIC_AST",
                    confidence=cand_rel.confidence,
                    evidence_refs=cand_rel.evidence_refs,
                    review_status=CandidateReviewStatus.CANDIDATE.value,
                    created_at=utc_now(),
                )
                session.add(cand)

            await session.commit()

        return artifact
