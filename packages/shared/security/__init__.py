"""ChangeScope Security, Authentication, and Authorization Foundation."""

from packages.shared.security.audit import AuditLogger
from packages.shared.security.authorization import (
    ROLE_WEIGHTS,
    SecurityContext,
    TenantRole,
    get_current_security_context,
    normalize_role,
    require_role,
)
from packages.shared.security.crypto import CredentialEncryption, EncryptionError
from packages.shared.security.jwt_handler import (
    SESSION_COOKIE_NAME,
    TokenPayload,
    clear_session_cookie,
    create_access_token,
    decode_token,
    get_session_cookie,
    set_secure_session_cookie,
)
from packages.shared.security.middleware import (
    CorrelationIdMiddleware,
    RequestTimeoutMiddleware,
    SecurityHeadersMiddleware,
    get_correlation_id,
)
from packages.shared.security.oidc import (
    OIDCClient,
    OIDCConfig,
    oidc_client,
)
from packages.shared.security.rate_limiter import (
    InMemoryRateLimiter,
    RateLimiter,
    RateLimitExceededError,
    rate_limiter,
)
from packages.shared.security.ssrf import (
    SSRFProtectionError,
    SSRFProtector,
)
from packages.shared.security.uploads import (
    UploadSecurityError,
    UploadValidator,
)
from packages.shared.security.webhooks import (
    WebhookVerificationError,
    WebhookVerifier,
)

__all__ = [
    "AuditLogger",
    "SecurityContext",
    "TenantRole",
    "ROLE_WEIGHTS",
    "get_current_security_context",
    "normalize_role",
    "require_role",
    "TokenPayload",
    "create_access_token",
    "decode_token",
    "SESSION_COOKIE_NAME",
    "set_secure_session_cookie",
    "get_session_cookie",
    "clear_session_cookie",
    "CorrelationIdMiddleware",
    "SecurityHeadersMiddleware",
    "RequestTimeoutMiddleware",
    "get_correlation_id",
    "OIDCClient",
    "OIDCConfig",
    "oidc_client",
    "CredentialEncryption",
    "EncryptionError",
    "SSRFProtector",
    "SSRFProtectionError",
    "WebhookVerifier",
    "WebhookVerificationError",
    "UploadValidator",
    "UploadSecurityError",
    "RateLimiter",
    "InMemoryRateLimiter",
    "RateLimitExceededError",
    "rate_limiter",
]
