"""Audit event recording service for security-critical actions and compliance tracking."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.logger import logger
from packages.shared.models import AuditLog


class AuditLogger:
    """Records durable, tenant-scoped security audit events."""

    @classmethod
    async def record_event(
        cls,
        db: AsyncSession,
        tenant_id: str,
        actor_id: str,
        actor_role: str,
        event_type: str,
        resource_type: str,
        resource_id: str | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        status: str = "SUCCESS",
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Asynchronously writes a durable audit entry to the relational database."""
        event_entry = AuditLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_role=actor_role,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            client_ip=client_ip,
            user_agent=user_agent,
            status=status,
            details=details or {},
            created_at=datetime.now(UTC),
        )
        db.add(event_entry)

        log_fn = logger.warning if status in ("DENIED", "FAILED") else logger.info
        log_fn(
            "security_audit_event",
            tenant_id=tenant_id,
            actor_id=actor_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
        )
        return event_entry

    @classmethod
    async def list_events(
        cls,
        db: AsyncSession,
        tenant_id: str,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Queries tenant-scoped audit logs with pagination."""
        from sqlalchemy import select

        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        safe_limit = min(max(1, limit), 100)
        safe_offset = max(0, offset)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(safe_limit).offset(safe_offset)
        res = await db.execute(stmt)
        return list(res.scalars().all())
