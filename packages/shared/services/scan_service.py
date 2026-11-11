"""Scan run data service enforcing repository ownership, scan access controls, and outbox isolation."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.errors import AuthorizationError, NotFoundError
from packages.shared.models import OutboxEvent, Repository, ScanRun, Violation
from packages.shared.security.audit import AuditLogger
from packages.shared.security.authorization import SecurityContext, TenantRole


class ScanService:
    """Service layer managing semantic change scans with strict tenancy and authorization enforcement."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger_scan(
        self,
        context: SecurityContext,
        repository_id: str,
        target_branch: str = "main",
        source_branch: str = "feat/contract-update",
        base_commit: str = "0000000",
        head_commit: str = "1111111",
        changed_files: list[str] | None = None,
    ) -> ScanRun:
        """Triggers a scan. Enforces Analyst role and repository tenant ownership."""
        context.assert_role(TenantRole.ANALYST)

        # 1. Tenancy Assertion: Verify repository exists and belongs to context tenant
        repo_stmt = select(Repository).where(Repository.id == repository_id)
        repo_res = await self.db.execute(repo_stmt)
        repo = repo_res.scalar_one_or_none()

        if not repo:
            raise NotFoundError(f"Repository '{repository_id}' not found.")

        if repo.tenant_id != context.tenant_id:
            await AuditLogger.record_event(
                db=self.db,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                actor_role=str(context.roles),
                event_type="BOLA_ATTEMPT_TRIGGER_SCAN",
                resource_type="Repository",
                resource_id=repository_id,
                status="DENIED",
                details={"target_repo_tenant": repo.tenant_id},
            )
            raise AuthorizationError(
                f"Tenant isolation violation: Cannot trigger scan on repository owned by '{repo.tenant_id}'."
            )

        scan_id = str(uuid.uuid4())
        scan_run = ScanRun(
            id=scan_id,
            tenant_id=context.tenant_id,
            repository_id=repository_id,
            target_branch=target_branch,
            source_branch=source_branch,
            base_sha=base_commit,
            head_sha=head_commit,
            status="QUEUED",
        )
        self.db.add(scan_run)

        # Durable Outbox Event for Asynchronous Celery Processing
        outbox_event = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            aggregate_type="ScanRun",
            aggregate_id=scan_id,
            event_type="SCAN_ENQUEUED",
            payload={
                "scan_id": scan_id,
                "repository_id": repository_id,
                "base_commit": base_commit,
                "head_commit": head_commit,
                "changed_files": changed_files or [],
                "tenant_id": context.tenant_id,
            },
        )
        self.db.add(outbox_event)
        await self.db.flush()

        await AuditLogger.record_event(
            db=self.db,
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            actor_role=str(context.roles),
            event_type="SCAN_TRIGGERED",
            resource_type="ScanRun",
            resource_id=scan_id,
            details={"repository_id": repository_id, "head_commit": head_commit},
        )
        return scan_run

    async def get_scan(self, context: SecurityContext, scan_id: str) -> ScanRun:
        """Retrieves scan status ensuring context tenant matches scan tenant."""
        context.assert_role(TenantRole.VIEWER)
        stmt = select(ScanRun).where(ScanRun.id == scan_id)
        res = await self.db.execute(stmt)
        scan = res.scalar_one_or_none()

        if not scan:
            raise NotFoundError(f"Scan run '{scan_id}' not found.")

        if scan.tenant_id != context.tenant_id:
            await AuditLogger.record_event(
                db=self.db,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                actor_role=str(context.roles),
                event_type="BOLA_ATTEMPT_SCAN_STATUS",
                resource_type="ScanRun",
                resource_id=scan_id,
                status="DENIED",
                details={"target_scan_tenant": scan.tenant_id},
            )
            raise AuthorizationError(f"Tenant isolation violation: Cannot access scan owned by '{scan.tenant_id}'.")

        return scan

    async def get_scan_violations(self, context: SecurityContext, scan_id: str) -> list[Violation]:
        """Retrieves violations for a scan with strict tenant validation."""
        # 1. Enforce scan access authorization first
        await self.get_scan(context, scan_id)

        # 2. Query violations explicitly scoped by tenant_id
        stmt = select(Violation).where(
            Violation.scan_id == scan_id,
            Violation.tenant_id == context.tenant_id,
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
