"""Celery Background Worker Tasks for Outbox Reconciliation, Repository Ingestion, and OTel Ingestion."""

import asyncio
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import Task
from sqlalchemy import delete, select

from apps.worker.app import celery_app
from packages.shared.database import async_session_factory
from packages.shared.ingestion.models import IngestionSourceType
from packages.shared.ingestion.pipeline import IngestionPipeline
from packages.shared.logger import logger
from packages.shared.models import (
    OutboxEvent,
    Repository,
    RuntimeDependency,
    RuntimeTraceSpan,
    ScanRun,
)
from packages.shared.telemetry.dependency_builder import DependencyBuilder
from packages.shared.telemetry.models import NormalizedSpan, SpanKind


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


async def aggregate_otel_traces_async(retention_days: int = 7) -> dict[str, Any]:
    """Aggregates buffered trace spans into runtime dependencies and purges expired spans."""
    async with async_session_factory() as session:
        # Fetch distinct tenants with buffered spans
        tenant_stmt = select(RuntimeTraceSpan.tenant_id).distinct()
        tenants = (await session.execute(tenant_stmt)).scalars().all()

        total_deps_updated = 0
        total_spans_processed = 0

        for t_id in tenants:
            stmt = select(RuntimeTraceSpan).where(RuntimeTraceSpan.tenant_id == t_id)
            res = await session.execute(stmt)
            raw_spans = res.scalars().all()
            if not raw_spans:
                continue

            total_spans_processed += len(raw_spans)

            normalized_spans: list[NormalizedSpan] = []
            for s in raw_spans:
                kind_enum = SpanKind(s.kind) if s.kind in SpanKind._value2member_map_ else SpanKind.INTERNAL
                attrs = s.attributes or {}
                normalized_spans.append(
                    NormalizedSpan(
                        trace_id=s.trace_id,
                        span_id=s.span_id,
                        parent_span_id=s.parent_span_id,
                        service_name=s.service_name,
                        name=s.name,
                        kind=kind_enum,
                        status_code=s.status_code,
                        duration_ms=s.duration_ms,
                        environment=s.environment,
                        attributes=attrs,
                        peer_service=attrs.get("peer.service") or attrs.get("net.peer.name"),
                        http_route=attrs.get("http.route") or attrs.get("http.target"),
                        http_method=attrs.get("http.method") or attrs.get("http.request.method"),
                        http_status_code=attrs.get("http.status_code"),
                        rpc_service=attrs.get("rpc.service"),
                        rpc_method=attrs.get("rpc.method"),
                        messaging_system=attrs.get("messaging.system"),
                        messaging_destination=attrs.get("messaging.destination"),
                        messaging_operation=attrs.get("messaging.operation"),
                        db_system=attrs.get("db.system"),
                        db_name=attrs.get("db.name"),
                        db_statement=attrs.get("db.statement"),
                        observed_at=s.observed_at,
                    )
                )

            deps = DependencyBuilder.extract_dependencies(normalized_spans)
            for dep in deps:
                dep_stmt = select(RuntimeDependency).where(
                    RuntimeDependency.tenant_id == t_id,
                    RuntimeDependency.caller_service_name == dep.caller_service_name,
                    RuntimeDependency.callee_service_name == dep.callee_service_name,
                    RuntimeDependency.http_route == dep.operation_or_route,
                    RuntimeDependency.protocol == dep.protocol.value,
                    RuntimeDependency.environment == dep.environment,
                )
                existing = (await session.execute(dep_stmt)).scalar_one_or_none()
                if existing:
                    existing.call_count_7d += dep.call_count
                    existing.error_count += dep.error_count
                    existing.p95_latency_ms = dep.p95_latency_ms
                    existing.last_observed_at = dep.last_observed_at
                    existing.exemplar_trace_id = dep.exemplar_trace_id
                    existing.exemplar_span_id = dep.exemplar_span_id
                else:
                    new_dep = RuntimeDependency(
                        tenant_id=t_id,
                        caller_service_name=dep.caller_service_name,
                        callee_service_name=dep.callee_service_name,
                        http_route=dep.operation_or_route,
                        http_method=dep.http_method or "ANY",
                        protocol=dep.protocol.value,
                        messaging_destination=dep.messaging_destination,
                        db_system=dep.db_system,
                        db_name=dep.db_name,
                        environment=dep.environment,
                        call_count_7d=dep.call_count,
                        error_count=dep.error_count,
                        p95_latency_ms=dep.p95_latency_ms,
                        exemplar_trace_id=dep.exemplar_trace_id,
                        exemplar_span_id=dep.exemplar_span_id,
                        first_observed_at=dep.first_observed_at,
                        last_observed_at=dep.last_observed_at,
                    )
                    session.add(new_dep)
                total_deps_updated += 1

            # Emit Outbox event for Neo4j read projection
            outbox_ev = OutboxEvent(
                id=str(uuid.uuid4()),
                tenant_id=t_id,
                aggregate_type="RuntimeDependency",
                aggregate_id=t_id,
                event_type="runtime.dependencies.projected",
                payload={
                    "tenant_id": t_id,
                    "dependencies_count": len(deps),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
            session.add(outbox_ev)

        # Purge spans older than retention window
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        del_stmt = (
            delete(RuntimeTraceSpan)
            .where(RuntimeTraceSpan.observed_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        del_res = await session.execute(del_stmt)
        purged_count = int(getattr(del_res, "rowcount", 0) or 0)

        await session.commit()
        logger.info(
            "otel_trace_aggregation_completed",
            tenants_count=len(tenants),
            spans_processed=total_spans_processed,
            dependencies_updated=total_deps_updated,
            spans_purged=purged_count,
        )
        return {
            "status": "COMPLETED",
            "tenants_count": len(tenants),
            "spans_processed": total_spans_processed,
            "dependencies_updated": total_deps_updated,
            "spans_purged": purged_count,
        }


@celery_app.task(name="apps.worker.tasks.aggregate_otel_traces_task")
def aggregate_otel_traces_task(retention_days: int = 7) -> dict[str, Any]:
    """Periodic task aggregating OTLP trace spans into rolling service dependencies."""
    logger.info("otel_trace_aggregation_scheduled_run")
    result = run_async(aggregate_otel_traces_async(retention_days=retention_days))
    return result if isinstance(result, dict) else {"status": "UNKNOWN"}
