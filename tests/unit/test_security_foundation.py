"""Unit tests for the ChangeScope Security & Authentication Foundation."""

from datetime import timedelta

import pytest

from packages.shared.errors import AuthenticationError, AuthorizationError
from packages.shared.security.authorization import (
    SecurityContext,
    TenantRole,
)
from packages.shared.security.jwt_handler import (
    TokenPayload,
    create_access_token,
    decode_token,
)
from packages.shared.security.oidc import OIDCClient


def test_jwt_create_and_decode_valid() -> None:
    """Verifies that a signed token can be successfully created and decoded with all claims."""
    claims = {
        "sub": "user_architect_01",
        "tenant_id": "tenant-abc-123",
        "roles": ["admin"],
        "email": "architect@changescope.io",
    }
    token = create_access_token(claims)
    assert isinstance(token, str)
    assert len(token) > 20

    payload: TokenPayload = decode_token(token)
    assert payload.sub == "user_architect_01"
    assert payload.tenant_id == "tenant-abc-123"
    assert "admin" in payload.roles
    assert payload.email == "architect@changescope.io"


def test_jwt_expired_token_raises_authentication_error() -> None:
    """Verifies that an expired JWT triggers a typed AuthenticationError."""
    claims = {"sub": "user_expired", "tenant_id": "tenant-test"}
    # Token expired 10 minutes ago
    expired_token = create_access_token(claims, expires_delta=timedelta(minutes=-10))

    with pytest.raises(AuthenticationError) as exc_info:
        decode_token(expired_token)
    assert "expired" in str(exc_info.value).lower()


def test_jwt_tampered_signature_raises_authentication_error() -> None:
    """Verifies that a token with an invalid signature is rejected."""
    claims = {"sub": "user_attacker", "tenant_id": "tenant-victim"}
    valid_token = create_access_token(claims)

    with pytest.raises(AuthenticationError) as exc_info:
        # Decode with an incorrect secret key
        decode_token(valid_token, key="completely_different_secret_key_32bytes_long")
    assert "invalid" in str(exc_info.value).lower()


def test_security_context_role_hierarchy() -> None:
    """Verifies that role weights accurately permit higher-tier roles to access lower-tier actions."""
    owner_context = SecurityContext(
        user_id="u_owner",
        tenant_id="tenant-1",
        roles=["owner"],
    )
    admin_context = SecurityContext(
        user_id="u_admin",
        tenant_id="tenant-1",
        roles=["admin"],
    )
    engineer_context = SecurityContext(
        user_id="u_eng",
        tenant_id="tenant-1",
        roles=["engineer"],
    )
    viewer_context = SecurityContext(
        user_id="u_view",
        tenant_id="tenant-1",
        roles=["viewer"],
    )

    # Owner satisfies all role requirements
    assert owner_context.has_role(TenantRole.OWNER) is True
    assert owner_context.has_role(TenantRole.ADMIN) is True
    assert owner_context.has_role(TenantRole.ENGINEER) is True
    assert owner_context.has_role(TenantRole.VIEWER) is True

    # Admin satisfies Admin, Engineer, Viewer, but not Owner
    assert admin_context.has_role(TenantRole.OWNER) is False
    assert admin_context.has_role(TenantRole.ADMIN) is True
    assert admin_context.has_role(TenantRole.ENGINEER) is True

    # Engineer satisfies Engineer and Viewer, but not Admin
    assert engineer_context.has_role(TenantRole.ADMIN) is False
    assert engineer_context.has_role(TenantRole.ENGINEER) is True

    # Viewer does not satisfy Engineer
    assert viewer_context.has_role(TenantRole.ENGINEER) is False
    assert viewer_context.has_role(TenantRole.VIEWER) is True


def test_security_context_tenant_isolation_boundary() -> None:
    """Verifies that assert_tenant_access raises AuthorizationError when tenant boundaries are breached."""
    context = SecurityContext(
        user_id="u_isolated",
        tenant_id="tenant-alpha",
        roles=["admin"],
    )
    # Matching tenant passes
    context.assert_tenant_access("tenant-alpha")

    # Divergent tenant triggers AuthorizationError
    with pytest.raises(AuthorizationError) as exc_info:
        context.assert_tenant_access("tenant-beta")
    assert "Tenant isolation violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_oidc_client_unconfigured_behavior() -> None:
    """Verifies that OIDCClient correctly identifies unconfigured states and raises typed errors."""
    client = OIDCClient(issuer_url=None)
    assert client.is_configured is False

    with pytest.raises(AuthenticationError) as exc_info:
        await client.discover()
    assert "not configured" in str(exc_info.value).lower()
