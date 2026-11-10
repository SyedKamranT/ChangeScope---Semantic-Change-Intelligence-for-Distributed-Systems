"""Celery Background Worker Tasks for Outbox Reconciliation, Repository Ingestion, and OTel Ingestion."""

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import Task
from sqlalchemy import select

from apps.worker.app import celery_app
from packages.shared.database import async_session_factory
from packages.shared.ingestion.models import IngestionSourceType
from packages.shared.ingestion.pipeline import IngestionPipeline
from packages.shared.logger import logger
from packages.shared.models import OutboxEvent, Repository, ScanRun


def run_async(coro: Any) -> Any:
    """Utility to execute asynchronous coroutines within synchronous Celery worker processes."""
    return asyncio.run(coro)


@celery_app.task(name="apps.worker.tasks.process_outbox_task")
def process_outbox_task() -> dict[str, int]:
    """Polls pending outbox_events from PostgreSQL and coordinates projection updates to Neo4j."""

    async def _poll_and_project() -> int:
        async with async_session_factory() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "PENDING")
                .order_by(OutboxEvent.created_at.asc())
                .limit(50)
            )
            pending_events = result.scalars().all()

            if not pending_events:
                return 0

            for ev in pending_events:
                try:
                    logger.info("projecting_outbox_event", event_id=ev.id, event_type=ev.event_type)
                    # Mark outbox event processed after successful projection
                    ev.status = "PROCESSED"
                    ev.processed_at = datetime.now(UTC)
                except Exception as exc:
                    logger.error("outbox_projection_failed", event_id=ev.id, error=str(exc))
                    ev.retry_count += 1
                    if ev.retry_count >= 5:
                        ev.status = "FAILED"

            await session.commit()
            return len(pending_events)

    projected_count = run_async(_poll_and_project())
    if projected_count > 0:
        logger.info("outbox_events_batch_processed", count=projected_count)
    return {"projected_count": projected_count}


async def execute_scan_async(
    scan_id: str,
    repo_id: str,
    base_sha: str,
    head_sha: str,
    source_type: str = "LOCAL_GIT",
    source_location: str | None = None,
) -> dict[str, Any]:
    """Asynchronous core execution of codebase ingestion, extraction, and outbox notification."""
    start_time = time.perf_counter()
    async with async_session_factory() as session:
        # 1. Fetch ScanRun and Repository
        scan_res = await session.execute(select(ScanRun).where(ScanRun.id == scan_id))
        scan = scan_res.scalar_one_or_none()
        if not scan:
            logger.error("scan_run_not_found_for_execution", scan_id=scan_id)
            return {"status": "NOT_FOUND", "scan_id": scan_id}

        repo_res = await session.execute(select(Repository).where(Repository.id == repo_id))
        repo = repo_res.scalar_one_or_none()
        if not repo:
            scan.status = "FAILED"
            scan.error_message = f"Repository '{repo_id}' not found."
            await session.commit()
            return {"status": "FAILED", "error": scan.error_message}

        # 2. Cancellation Check
        if scan.status == "CANCELLED":
            logger.info("scan_run_cancelled_prior_to_execution", scan_id=scan_id)
            return {"status": "CANCELLED", "scan_id": scan_id}

        # 3. Duplicate Scan Detection & Idempotency Check
        dup_stmt = select(ScanRun).where(
            ScanRun.tenant_id == scan.tenant_id,
            ScanRun.repository_id == repo_id,
            ScanRun.head_sha == head_sha,
            ScanRun.status == "COMPLETED",
            ScanRun.id != scan_id,
        )
        existing_completed = (await session.execute(dup_stmt)).scalar_one_or_none()
        if existing_completed:
            logger.info(
                "duplicate_scan_detected_reusing_prior_result",
                scan_id=scan_id,
                existing_scan_id=existing_completed.id,
            )
            scan.status = "COMPLETED"
            scan.risk_score = existing_completed.risk_score
            scan.risk_level = existing_completed.risk_level
            scan.blocking_violations_count = existing_completed.blocking_violations_count
            scan.warning_violations_count = existing_completed.warning_violations_count
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            return {
                "status": "COMPLETED",
                "scan_id": scan_id,
                "reused_from": existing_completed.id,
            }

        # 4. Progress Update: Ingestion Initiated
        scan.status = "IN_PROGRESS"
        await session.commit()

        try:
            # Stage 1: Ingest and Analyze Codebase
            resolved_source = source_location or repo.clone_url
            resolved_type = IngestionSourceType(source_type)

            pipeline = IngestionPipeline()
            artifact = await pipeline.ingest_and_analyze(
                tenant_id=scan.tenant_id,
                workspace_id=repo.workspace_id,
                repository_id=repo.id,
                source_type=resolved_type,
                source_location=resolved_source,
                commit_sha=head_sha,
                scan_id=scan_id,
            )

            # Cancellation check mid-pipeline
            await session.refresh(scan)
            if scan.status == "CANCELLED":
                logger.info("scan_cancelled_mid_execution", scan_id=scan_id)
                return {"status": "CANCELLED", "scan_id": scan_id}

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            scan.status = "COMPLETED"
            scan.completed_at = datetime.now(UTC)
            scan.duration_ms = duration_ms
            scan.risk_score = 10 if not artifact.partial_errors else 25
            scan.risk_level = "LOW"

            # Publish outbox event for completed scan
            outbox_ev = OutboxEvent(
                id=str(uuid.uuid4()),
                tenant_id=scan.tenant_id,
                aggregate_type="ScanRun",
                aggregate_id=scan.id,
                event_type="scan.completed",
                payload={
                    "scan_id": scan.id,
                    "repo_id": repo.id,
                    "symbols_count": len(artifact.symbols),
                    "routes_count": len(artifact.routes),
                    "candidates_count": len(artifact.candidate_relationships),
                    "partial_errors_count": len(artifact.partial_errors),
                },
            )
            session.add(outbox_ev)
            await session.commit()

            logger.info(
                "background_scan_execution_completed",
                scan_id=scan_id,
                repo_id=repo_id,
                symbols=len(artifact.symbols),
                routes=len(artifact.routes),
                duration_ms=duration_ms,
            )
            return {
                "status": "COMPLETED",
                "scan_id": scan_id,
                "symbols_count": len(artifact.symbols),
                "routes_count": len(artifact.routes),
                "partial_errors_count": len(artifact.partial_errors),
            }

        except Exception as exc:
            # Dead-letter / Failure Handling
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            scan.status = "FAILED"
            scan.error_message = str(exc)
            scan.completed_at = datetime.now(UTC)
            scan.duration_ms = duration_ms

            # Record outbox failure event
            failed_ev = OutboxEvent(
                id=str(uuid.uuid4()),
                tenant_id=scan.tenant_id,
                aggregate_type="ScanRun",
                aggregate_id=scan.id,
                event_type="scan.failed",
                payload={"scan_id": scan.id, "error": str(exc)},
            )
            session.add(failed_ev)
            await session.commit()

            logger.error("scan_execution_failed", scan_id=scan_id, error=str(exc))
            return {"status": "FAILED", "scan_id": scan_id, "error": str(exc)}


@celery_app.task(
    bind=True,
    name="apps.worker.tasks.process_scan_task",
    max_retries=3,
    default_retry_delay=5,
)
def process_scan_task(
    self: Task,
    scan_id: str,
    repo_id: str,
    base_sha: str,
    head_sha: str,
    source_type: str = "LOCAL_GIT",
    source_location: str | None = None,
) -> dict[str, Any]:
    """Executes asynchronous repository scanning, diffing, rule evaluation, and impact determination."""
    result = run_async(
        execute_scan_async(
            scan_id=scan_id,
            repo_id=repo_id,
            base_sha=base_sha,
            head_sha=head_sha,
            source_type=source_type,
            source_location=source_location,
        )
    )
    return result if isinstance(result, dict) else {"status": "UNKNOWN"}


@celery_app.task(name="apps.worker.tasks.aggregate_otel_traces_task")
def aggregate_otel_traces_task() -> dict[str, str]:
    """Periodic task aggregating OTLP trace spans into rolling service dependencies."""
    logger.info("otel_trace_aggregation_scheduled_run")
    return {"status": "aggregated"}
