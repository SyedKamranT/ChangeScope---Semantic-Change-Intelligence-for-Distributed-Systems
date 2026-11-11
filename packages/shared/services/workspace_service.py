"""Workspace data service enforcing tenant isolation and role-based permissions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.errors import AuthorizationError, ConflictError, NotFoundError
from packages.shared.models import Tenant, Workspace
from packages.shared.security.audit import AuditLogger
from packages.shared.security.authorization import SecurityContext, TenantRole


class WorkspaceService:
    """Service layer managing workspace lifecycles with strict tenancy and authorization enforcement."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_workspaces(self, context: SecurityContext) -> list[Workspace]:
        """Lists all workspaces scoped to the context tenant. Requires at least Viewer role."""
        context.assert_role(TenantRole.VIEWER)
        stmt = select(Workspace).where(Workspace.tenant_id == context.tenant_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_workspace(self, context: SecurityContext, workspace_id: str) -> Workspace:
        """Retrieves a workspace ensuring it belongs to the authenticated tenant."""
        context.assert_role(TenantRole.VIEWER)
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        res = await self.db.execute(stmt)
        workspace = res.scalar_one_or_none()

        if not workspace:
            raise NotFoundError(f"Workspace '{workspace_id}' not found.")

        # Service-layer tenancy assertion (BOLA defense)
        if workspace.tenant_id != context.tenant_id:
            await AuditLogger.record_event(
                db=self.db,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                actor_role=str(context.roles),
                event_type="BOLA_ATTEMPT_WORKSPACE_ACCESS",
                resource_type="Workspace",
                resource_id=workspace_id,
                status="DENIED",
                details={"target_workspace_tenant": workspace.tenant_id},
            )
            raise AuthorizationError(
                f"Tenant isolation violation: Cannot access workspace in tenant '{workspace.tenant_id}'."
            )

        return workspace

    async def create_workspace(
        self,
        context: SecurityContext,
        name: str,
        slug: str,
    ) -> Workspace:
        """Creates a workspace within the context tenant. Requires Administrator or Owner role."""
        context.assert_role(TenantRole.ADMINISTRATOR)

        # 1. Ensure Tenant Record Exists
        tenant_stmt = select(Tenant).where(Tenant.id == context.tenant_id)
        tenant_res = await self.db.execute(tenant_stmt)
        tenant = tenant_res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=context.tenant_id,
                name="Default Organization",
                slug=f"org-{context.tenant_id[:8]}",
                tier="enterprise",
            )
            self.db.add(tenant)
            await self.db.flush()

        # 2. Check for Slug Collision Within Tenant
        existing_stmt = select(Workspace).where(
            Workspace.tenant_id == context.tenant_id,
            Workspace.slug == slug,
        )
        existing = (await self.db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ConflictError(f"Workspace with slug '{slug}' already exists in this tenant.")

        workspace = Workspace(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            name=name,
            slug=slug,
        )
        self.db.add(workspace)
        await self.db.flush()

        await AuditLogger.record_event(
            db=self.db,
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            actor_role=str(context.roles),
            event_type="WORKSPACE_CREATED",
            resource_type="Workspace",
            resource_id=workspace.id,
            details={"name": name, "slug": slug},
        )
        return workspace
