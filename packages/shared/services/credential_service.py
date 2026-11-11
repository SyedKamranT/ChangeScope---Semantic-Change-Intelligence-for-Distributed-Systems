"""Integration Credential data service managing encrypted credentials and tenant ownership."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.errors import AuthorizationError, ConflictError, NotFoundError
from packages.shared.models import IntegrationCredential
from packages.shared.security.audit import AuditLogger
from packages.shared.security.authorization import SecurityContext, TenantRole
from packages.shared.security.crypto import CredentialEncryption


class CredentialService:
    """Service layer managing third-party integration credentials with at-rest encryption and tenant boundaries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def store_credential(
        self,
        context: SecurityContext,
        name: str,
        provider: str,
        secret_plaintext: str,
        scopes: list[str] | None = None,
    ) -> IntegrationCredential:
        """Stores a third-party token with authenticated encryption. Requires Administrator role."""
        context.assert_role(TenantRole.ADMINISTRATOR)

        # Check for duplicate credential name within tenant
        existing_stmt = select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == context.tenant_id,
            IntegrationCredential.name == name,
        )
        existing = (await self.db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ConflictError(f"Integration credential '{name}' already exists in this tenant.")

        encrypted_val = CredentialEncryption.encrypt(secret_plaintext)
        cred = IntegrationCredential(
            id=str(uuid.uuid4()),
            tenant_id=context.tenant_id,
            name=name,
            provider=provider.upper(),
            encrypted_secret=encrypted_val,
            key_id=CredentialEncryption.KEY_VERSION,
            scopes=scopes or [],
        )
        self.db.add(cred)
        await self.db.flush()

        await AuditLogger.record_event(
            db=self.db,
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            actor_role=str(context.roles),
            event_type="CREDENTIAL_STORED",
            resource_type="IntegrationCredential",
            resource_id=cred.id,
            details={"name": name, "provider": provider},
        )
        return cred

    async def get_decrypted_secret(self, context: SecurityContext, credential_id: str) -> str:
        """Decrypts and returns the plaintext secret. Requires Administrator role and strict tenant match."""
        context.assert_role(TenantRole.ADMINISTRATOR)

        stmt = select(IntegrationCredential).where(IntegrationCredential.id == credential_id)
        res = await self.db.execute(stmt)
        cred = res.scalar_one_or_none()

        if not cred:
            raise NotFoundError(f"Credential '{credential_id}' not found.")

        if cred.tenant_id != context.tenant_id:
            await AuditLogger.record_event(
                db=self.db,
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                actor_role=str(context.roles),
                event_type="BOLA_ATTEMPT_CREDENTIAL_ACCESS",
                resource_type="IntegrationCredential",
                resource_id=credential_id,
                status="DENIED",
                details={"target_cred_tenant": cred.tenant_id},
            )
            raise AuthorizationError(
                f"Tenant isolation violation: Cannot access credentials owned by '{cred.tenant_id}'."
            )

        plaintext = CredentialEncryption.decrypt(cred.encrypted_secret)
        await AuditLogger.record_event(
            db=self.db,
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            actor_role=str(context.roles),
            event_type="CREDENTIAL_DECRYPTED",
            resource_type="IntegrationCredential",
            resource_id=credential_id,
            details={"name": cred.name, "provider": cred.provider},
        )
        return plaintext

    async def list_credentials(self, context: SecurityContext) -> list[IntegrationCredential]:
        """Lists integration credentials for the tenant without decrypting secrets."""
        context.assert_role(TenantRole.VIEWER)
        stmt = select(IntegrationCredential).where(IntegrationCredential.tenant_id == context.tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
