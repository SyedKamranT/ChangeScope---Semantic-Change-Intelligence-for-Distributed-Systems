"""ChangeScope Security, Authentication, and Authorization Foundation."""

from packages.shared.security.authorization import (
    ROLE_WEIGHTS,
    SecurityContext,
    TenantRole,
    get_current_security_context,
    require_role,
)
from packages.shared.security.jwt_handler import (
    TokenPayload,
    create_access_token,
    decode_token,
)
from packages.shared.security.middleware import (
    CorrelationIdMiddleware,
    get_correlation_id,
)
from packages.shared.security.oidc import (
    OIDCClient,
    OIDCConfig,
    oidc_client,
)

__all__ = [
    "SecurityContext",
    "TenantRole",
    "ROLE_WEIGHTS",
    "get_current_security_context",
    "require_role",
    "TokenPayload",
    "create_access_token",
    "decode_token",
    "CorrelationIdMiddleware",
    "get_correlation_id",
    "OIDCClient",
    "OIDCConfig",
    "oidc_client",
]
