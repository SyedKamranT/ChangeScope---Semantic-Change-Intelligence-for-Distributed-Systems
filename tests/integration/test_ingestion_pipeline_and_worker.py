"""Integration tests for Ingestion Pipeline and Asynchronous Celery Worker Scanning."""

import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.tasks import execute_scan_async, process_scan_task
from packages.shared.database import async_session_factory
from packages.shared.ingestion.models import IngestionSourceType
from packages.shared.ingestion.pipeline import IngestionPipeline
from packages.shared.models import ASTSymbol, OutboxEvent, Repository, ScanRun, Tenant, Workspace
from packages.shared.ontology_models import OntologyCandidate


@pytest.fixture
async def db_session():
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def sample_tenant_and_repo(db_session: AsyncSession):
    """Seeds tenant, workspace, and repository for worker tests."""
    tenant = Tenant(name="Acme Ingestion Corp", slug=f"acme-ingest-{uuid.uuid4().hex[:6]}")
    db_session.add(tenant)
    await db_session.flush()

    workspace = Workspace(
        tenant_id=tenant.id,
        name="Production Workspace",
        slug=f"ws-prod-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(workspace)
    await db_session.flush()

    repo = Repository(
        workspace_id=workspace.id,
        tenant_id=tenant.id,
        name="payment-gateway",
        clone_url="tests/fixtures/sample_repos/python_fastapi_service",
        default_branch="main",
        primary_language="python",
    )
    db_session.add(repo)
    await db_session.commit()

    return tenant, workspace, repo


@pytest.mark.asyncio
async def test_pipeline_local_git_ingestion(sample_tenant_and_repo, db_session: AsyncSession):
    """Verifies complete sandboxed ingestion, static analysis, and database symbol persistence."""
    tenant, workspace, repo = sample_tenant_and_repo
    fixture_dir = Path("tests/fixtures/sample_repos/python_fastapi_service")
    assert fixture_dir.exists()

    scan_run = ScanRun(
        tenant_id=tenant.id,
        repository_id=repo.id,
        base_sha="a" * 40,
        head_sha="b" * 40,
        status="PENDING",
    )
    db_session.add(scan_run)
    await db_session.commit()

    pipeline = IngestionPipeline()
    artifact = await pipeline.ingest_and_analyze(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        repository_id=repo.id,
        source_type=IngestionSourceType.LOCAL_GIT,
        source_location=fixture_dir,
        commit_sha=scan_run.head_sha,
        scan_id=scan_run.id,
    )

    # Invariants
    assert artifact.total_files >= 3
    assert "Python" in artifact.languages
    assert len(artifact.routes) >= 2
    assert len(artifact.client_calls) >= 1
    assert len(artifact.symbols) >= 3

    # Candidate relationships must have explicit line evidence citations
    assert len(artifact.candidate_relationships) >= 1
    call_cand = next(r for r in artifact.candidate_relationships if r.rel_type == "CALLS")
    assert len(call_cand.evidence_refs) > 0
    assert "main.py" in call_cand.evidence_refs[0]

    # Verify ASTSymbol persisted in DB
    sym_stmt = select(ASTSymbol).where(ASTSymbol.scan_id == scan_run.id)
    persisted_syms = list((await db_session.execute(sym_stmt)).scalars().all())
    assert len(persisted_syms) == len(artifact.symbols)

    # Verify OntologyCandidate persisted in DB
    cand_stmt = select(OntologyCandidate).where(OntologyCandidate.tenant_id == tenant.id)
    persisted_cands = list((await db_session.execute(cand_stmt)).scalars().all())
    assert len(persisted_cands) >= 1


@pytest.mark.asyncio
async def test_pipeline_archive_ingestion(sample_tenant_and_repo, tmp_path: Path):
    """Verifies that an uploaded ZIP archive is safely extracted and analyzed."""
    tenant, workspace, repo = sample_tenant_and_repo
    fixture_dir = Path("tests/fixtures/sample_repos/typescript_express_service")

    # Create zip file in tmp_path
    archive_path = tmp_path / "ts_service.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for f in fixture_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(fixture_dir))

    pipeline = IngestionPipeline()
    artifact = await pipeline.ingest_and_analyze(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        repository_id=repo.id,
        source_type=IngestionSourceType.UPLOADED_ARCHIVE,
        source_location=archive_path,
        commit_sha="c" * 40,
    )

    assert artifact.total_files >= 2
    assert "TypeScript" in artifact.languages
    assert len(artifact.routes) >= 2
    assert len(artifact.client_calls) >= 1


@pytest.mark.asyncio
async def test_pipeline_partial_failure_reporting(sample_tenant_and_repo, tmp_path: Path):
    """Verifies that individual file syntax errors are recorded in partial_errors without aborting the scan."""
    tenant, workspace, repo = sample_tenant_and_repo

    # Create dummy directory with 1 valid file and 1 syntax error file
    test_repo_dir = tmp_path / "mixed_repo"
    test_repo_dir.mkdir(parents=True, exist_ok=True)

    good_file = test_repo_dir / "valid.py"
    good_file.write_text("def ping():\n    return 'pong'\n", encoding="utf-8")

    broken_file = test_repo_dir / "broken.py"
    broken_file.write_text("def syntax_error(\n    invalid code here = = =\n", encoding="utf-8")

    pipeline = IngestionPipeline()
    artifact = await pipeline.ingest_and_analyze(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        repository_id=repo.id,
        source_type=IngestionSourceType.LOCAL_GIT,
        source_location=test_repo_dir,
        commit_sha="d" * 40,
    )

    assert artifact.total_files == 2
    assert len(artifact.symbols) >= 1  # 'ping' was extracted
    assert len(artifact.partial_errors) == 1
    assert "broken.py" in artifact.partial_errors[0]["file_path"]


@pytest.mark.asyncio
async def test_celery_process_scan_task_lifecycle(sample_tenant_and_repo, db_session: AsyncSession):
    """Verifies end-to-end execution of process_scan_task including outbox notification."""
    tenant, workspace, repo = sample_tenant_and_repo

    scan_run = ScanRun(
        tenant_id=tenant.id,
        repository_id=repo.id,
        base_sha="1" * 40,
        head_sha="2" * 40,
        status="PENDING",
    )
    db_session.add(scan_run)
    await db_session.commit()

    # Execute asynchronous scan task
    res = await execute_scan_async(
        scan_id=scan_run.id,
        repo_id=repo.id,
        base_sha=scan_run.base_sha,
        head_sha=scan_run.head_sha,
        source_type="LOCAL_GIT",
        source_location="tests/fixtures/sample_repos/python_fastapi_service",
    )

    assert res["status"] == "COMPLETED"
    assert res["symbols_count"] >= 3

    # Verify ScanRun status and outbox event
    await db_session.refresh(scan_run)
    assert scan_run.status == "COMPLETED"
    assert scan_run.duration_ms >= 0

    outbox_stmt = select(OutboxEvent).where(
        OutboxEvent.aggregate_id == scan_run.id,
        OutboxEvent.event_type == "scan.completed",
    )
    ev = (await db_session.execute(outbox_stmt)).scalar_one_or_none()
    assert ev is not None


@pytest.mark.asyncio
async def test_celery_duplicate_scan_detection(sample_tenant_and_repo, db_session: AsyncSession):
    """Verifies that running a duplicate scan with identical head_sha reuses prior completed result."""
    tenant, workspace, repo = sample_tenant_and_repo
    target_sha = "3" * 40

    # 1. First scan
    scan1 = ScanRun(
        tenant_id=tenant.id,
        repository_id=repo.id,
        base_sha="0" * 40,
        head_sha=target_sha,
        status="PENDING",
    )
    db_session.add(scan1)
    await db_session.commit()

    res1 = await execute_scan_async(
        scan_id=scan1.id,
        repo_id=repo.id,
        base_sha=scan1.base_sha,
        head_sha=target_sha,
        source_type="LOCAL_GIT",
        source_location="tests/fixtures/sample_repos/python_fastapi_service",
    )
    assert res1["status"] == "COMPLETED"

    # 2. Second scan for same head_sha
    scan2 = ScanRun(
        tenant_id=tenant.id,
        repository_id=repo.id,
        base_sha="0" * 40,
        head_sha=target_sha,
        status="PENDING",
    )
    db_session.add(scan2)
    await db_session.commit()

    res2 = await execute_scan_async(
        scan_id=scan2.id,
        repo_id=repo.id,
        base_sha=scan2.base_sha,
        head_sha=target_sha,
        source_type="LOCAL_GIT",
        source_location="tests/fixtures/sample_repos/python_fastapi_service",
    )
    assert res2["status"] == "COMPLETED"
    assert res2.get("reused_from") == scan1.id


@pytest.mark.asyncio
async def test_celery_cancellation_and_dead_letter_handling(sample_tenant_and_repo, db_session: AsyncSession):
    """Verifies early cancellation and dead-letter failed-job tracking."""
    tenant, workspace, repo = sample_tenant_and_repo

    # 1. Cancellation test
    cancelled_scan = ScanRun(
        tenant_id=tenant.id,
        repository_id=repo.id,
        base_sha="0" * 40,
        head_sha="4" * 40,
        status="CANCELLED",
    )
    db_session.add(cancelled_scan)
    await db_session.commit()

    res_cancel = await execute_scan_async(
        scan_id=cancelled_scan.id,
        repo_id=repo.id,
        base_sha=cancelled_scan.base_sha,
        head_sha="4" * 40,
        source_type="LOCAL_GIT",
    )
    assert res_cancel["status"] == "CANCELLED"

    # 2. Dead-letter test: Non-existent repo ID
    bad_scan = ScanRun(
        tenant_id=tenant.id,
        repository_id="non-existent-repo-id",
        base_sha="0" * 40,
        head_sha="5" * 40,
        status="PENDING",
    )
    db_session.add(bad_scan)
    await db_session.commit()

    res_fail = await execute_scan_async(
        scan_id=bad_scan.id,
        repo_id="non-existent-repo-id",
        base_sha="0" * 40,
        head_sha="5" * 40,
        source_type="LOCAL_GIT",
    )
    assert res_fail["status"] == "FAILED"

    await db_session.refresh(bad_scan)
    assert bad_scan.status == "FAILED"
    assert "not found" in (bad_scan.error_message or "").lower()


def test_process_scan_task_celery_registration():
    """Verifies that process_scan_task is correctly registered with Celery."""
    assert process_scan_task.name == "apps.worker.tasks.process_scan_task"
    assert process_scan_task.max_retries == 3
    assert process_scan_task.default_retry_delay == 5
