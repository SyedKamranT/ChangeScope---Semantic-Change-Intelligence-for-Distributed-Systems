"""Workspace authorization and tenant-scoped security context for ChangeScope."""

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from packages.shared.config import settings
from packages.shared.errors import AuthenticationError, AuthorizationError
from packages.shared.security.jwt_handler import TokenPayload, decode_token, get_session_cookie
from packages.shared.security.oidc import oidc_client

security_scheme = HTTPBearer(auto_error=False)


class TenantRole(StrEnum):
    """Hierarchical roles for tenant workspace access control."""

    ORGANIZATION_OWNER = "organization_owner"
    ADMINISTRATOR = "administrator"
    ANALYST = "analyst"
    VIEWER = "viewer"

    # Backward compatibility and title aliases
    OWNER = "owner"
    ADMIN = "admin"
    ENGINEER = "engineer"
    AUDITOR = "auditor"


ROLE_WEIGHTS: dict[TenantRole, int] = {
    TenantRole.ORGANIZATION_OWNER: 100,
    TenantRole.OWNER: 100,
    TenantRole.ADMINISTRATOR: 80,
    TenantRole.ADMIN: 80,
    TenantRole.ANALYST: 50,
    TenantRole.ENGINEER: 50,
    TenantRole.AUDITOR: 30,
    TenantRole.VIEWER: 10,
}


def normalize_role(role_name: str) -> TenantRole | None:
    """Normalizes role strings (e.g. 'Organization Owner' -> TenantRole.ORGANIZATION_OWNER)."""
    clean = role_name.strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return TenantRole(clean)
    except ValueError:
        # Fallback aliases
        mapping = {
            "organization_owner": TenantRole.ORGANIZATION_OWNER,
            "owner": TenantRole.ORGANIZATION_OWNER,
            "administrator": TenantRole.ADMINISTRATOR,
            "admin": TenantRole.ADMINISTRATOR,
            "analyst": TenantRole.ANALYST,
            "engineer": TenantRole.ANALYST,
            "auditor": TenantRole.AUDITOR,
            "viewer": TenantRole.VIEWER,
            "read_only": TenantRole.VIEWER,
        }
        return mapping.get(clean)


class SecurityContext(BaseModel):
    """Authenticated user context containing tenant isolation metadata and active roles."""

    user_id: str = Field(description="Subject identifier")
    tenant_id: str = Field(description="Tenant isolation UUID")
    roles: list[str] = Field(default_factory=list, description="Assigned roles")
    email: str | None = Field(default=None, description="User email if present")
    claims: dict[str, Any] = Field(default_factory=dict, description="Raw token claims")

    def has_role(self, required_role: TenantRole) -> bool:
        """Determines if the active context meets or exceeds the required role level."""
        req_weight = ROLE_WEIGHTS.get(required_role, 0)
        for role_str in self.roles:
            role_enum = normalize_role(role_str)
            if role_enum and ROLE_WEIGHTS.get(role_enum, 0) >= req_weight:
                return True
        return False

    def assert_role(self, required_role: TenantRole) -> None:
        """Enforces minimum required role privileges at the domain or service layer."""
        if not self.has_role(required_role):
            raise AuthorizationError(
                f"Insufficient privileges: Action requires '{required_role.value}', but user possesses {self.roles}."
            )

    def assert_tenant_access(self, target_tenant_id: str) -> None:
        """Enforces tenant isolation by asserting context tenant matches the resource tenant."""
        if self.tenant_id != target_tenant_id:
            raise AuthorizationError(
                f"Tenant isolation violation: Context tenant '{self.tenant_id}' cannot access resource in '{target_tenant_id}'."
            )


async def get_current_security_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
) -> SecurityContext:
    """FastAPI dependency to extract, cryptographically verify, and construct the SecurityContext."""
    raw_token: str | None = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials
    else:
        raw_token = get_session_cookie(request)

    if not raw_token:
        raise AuthenticationError(
            "Authentication token is missing. Please provide 'Authorization: Bearer <token>' header or session cookie."
        )

    # 1. External OIDC Provider Verification
    if oidc_client.is_configured:
        try:
            signing_key = oidc_client.get_signing_key_for_token(raw_token)
            payload: TokenPayload = decode_token(
                token=raw_token,
                key=signing_key,
                algorithms=["RS256"],
                audience=settings.OIDC_AUDIENCE,
                issuer=settings.OIDC_ISSUER_URL,
            )
        except Exception as exc:
            raise AuthenticationError(f"OIDC token verification failed: {exc}") from exc
    else:
        # 2. Internal Symmetric JWT Verification
        payload = decode_token(
            token=raw_token,
            key=settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

    # Use header tenant_id only if verified token allows multi-tenant or default tenant matches
    tenant_id = payload.tenant_id
    if x_tenant_id and tenant_id == settings.DEFAULT_TENANT_ID:
        tenant_id = x_tenant_id

    return SecurityContext(
        user_id=payload.sub,
        tenant_id=tenant_id,
        roles=payload.roles,
        email=payload.email,
        claims=payload.model_dump(),
    )


def require_role(min_role: TenantRole) -> Callable[[SecurityContext], SecurityContext]:
    """Dependency factory enforcing minimum required role privileges."""

    def role_checker(context: SecurityContext = Depends(get_current_security_context)) -> SecurityContext:
        if not context.has_role(min_role):
            raise AuthorizationError(
                f"Insufficient privileges. Required role level '{min_role.value}', but user possesses {context.roles}."
            )
        return context

    return role_checker
