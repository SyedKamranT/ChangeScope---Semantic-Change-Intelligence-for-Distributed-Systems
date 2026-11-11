"""Repository data service enforcing workspace and repository tenancy boundaries."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.errors import AuthorizationError, NotFoundError
from packages.shared.models import Repository, Workspace
from packages.shared.security.audit import AuditLogger
from packages.shared.security.authorization import SecurityContext, TenantRole
from packages.shared.security.ssrf import SSRFProtector


class RepositoryService:
    """Service layer managing repository registrations with BOLA and SSRF defenses."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_repositories(
        self,
        context: SecurityContext,
        workspace_id: str | None = None,
    ) -> list[Repository]:
        """Lists repositories scoped to tenant. If workspace_id is provided, validates workspace ownership."""
        context.assert_role(TenantRole.VIEWER)

        if workspace_id:
            # Validate workspace tenancy before listing repositories
            ws_stmt = select(Workspace).where(Workspace.id == workspace_id)
            ws = (await self.db.execute(ws_stmt)).scalar_one_or_none()
            if not ws:
                raise NotFoundError(f"Workspace '{workspace_id}' not found.")
            if ws.tenant_id != context.tenant_id:
                raise AuthorizationError(
                    f"Tenant isolation violation: Workspace '{workspace_id}' belongs to another tenant."
                )

        stmt = select(Repository).where(Repository.tenant_id == context.tenant_id)
        if workspace_id:
            stmt = stmt.where(Repository.workspace_id == workspace_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_repository(self, context: SecurityContext, repository_id: str) -> Repository:
        """Retrieves a repository ensuring it belongs to the authenticated tenant."""
        context.assert_role(TenantRole.VIEWER)
        stmt = select(Repository).where(Repository.id == repository_id)
        res = await self.db.execute(stmt)
        repo = res.scalar_one_or_none()

        if not repo:
            raise NotFoundError(f"Repository '{repository_id}' not found.")

        if repo.tenant_id != context.tenant_id:
            await AuditLogger.record_event(
                db=self.db,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                actor_role=str(context.roles),
                event_type="BOLA_ATTEMPT_REPOSITORY_ACCESS",
                resource_type="Repository",
                resource_id=repository_id,
                status="DENIED",
                details={"target_repo_tenant": repo.tenant_id},
            )
            raise AuthorizationError(
                f"Tenant isolation violation: Cannot access repository in tenant '{repo.tenant_id}'."
            )

        return repo

    async def register_repository(
        self,
        context: SecurityContext,
        workspace_id: str,
        name: str,
        clone_url: str,
        default_branch: str = "main",
    ) -> Repository:
        """Registers a repository. Enforces Analyst role, workspace ownership, and clone URL SSRF checks."""
        context.assert_role(TenantRole.ANALYST)

        # 1. BOLA Defense: Verify target workspace exists and belongs strictly to the context tenant
        ws_stmt = select(Workspace).where(Workspace.id == workspace_id)
        ws_res = await self.db.execute(ws_stmt)
        workspace = ws_res.scalar_one_or_none()

        if not workspace:
            raise NotFoundError(f"Target workspace '{workspace_id}' not found.")

        if workspace.tenant_id != context.tenant_id:
            await AuditLogger.record_event(
                db=self.db,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                actor_role=str(context.roles),
                event_type="BOLA_ATTEMPT_REGISTER_REPOSITORY",
                resource_type="Workspace",
                resource_id=workspace_id,
                status="DENIED",
                details={"target_workspace_tenant": workspace.tenant_id},
            )
            raise AuthorizationError(
                f"Tenant isolation violation: Workspace '{workspace_id}' belongs to another tenant."
            )

        # 2. SSRF Validation for HTTP(S) Clone URLs
        if clone_url.startswith("http://") or clone_url.startswith("https://"):
            SSRFProtector.validate_url(clone_url)

        repo = Repository(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            workspace_id=workspace_id,
            name=name,
            clone_url=clone_url,
            default_branch=default_branch,
        )
        self.db.add(repo)
        await self.db.flush()

        await AuditLogger.record_event(
            db=self.db,
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            actor_role=str(context.roles),
            event_type="REPOSITORY_REGISTERED",
            resource_type="Repository",
            resource_id=repo.id,
            details={"workspace_id": workspace_id, "name": name, "clone_url": clone_url},
        )
        return repo
