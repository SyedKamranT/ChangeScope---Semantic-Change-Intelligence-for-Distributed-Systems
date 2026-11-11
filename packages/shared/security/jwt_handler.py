"""Cryptographic JWT token generation and validation for ChangeScope."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pydantic import BaseModel, Field

from packages.shared.config import settings
from packages.shared.errors import AuthenticationError


class TokenPayload(BaseModel):
    """Normalized ChangeScope token claims representation."""

    sub: str = Field(description="Subject identifier (user or service principal ID)")
    tenant_id: str = Field(description="Tenant isolation UUID")
    roles: list[str] = Field(default_factory=lambda: ["engineer"], description="Assigned roles within the tenant")
    email: str | None = Field(default=None, description="User email address")
    exp: int = Field(description="Unix timestamp when token expires")
    iss: str | None = Field(default=None, description="Issuer URL")
    aud: str | None = Field(default=None, description="Audience string")


def create_access_token(
    claims: dict[str, Any],
    expires_delta: timedelta | None = None,
    secret_key: str | None = None,
    algorithm: str | None = None,
) -> str:
    """Generates a cryptographically signed JWT token for authentication."""
    to_encode = claims.copy()
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    to_encode.setdefault("exp", int(expire.timestamp()))
    to_encode.setdefault("iat", int(now.timestamp()))
    to_encode.setdefault("nbf", int(now.timestamp()))

    key = secret_key or settings.JWT_SECRET
    alg = algorithm or settings.JWT_ALGORITHM
    token = jwt.encode(to_encode, key, algorithm=alg)
    return token


def decode_token(
    token: str,
    key: str | None = None,
    algorithms: list[str] | None = None,
    audience: str | None = None,
    issuer: str | None = None,
) -> TokenPayload:
    """Decodes and validates a JWT token against cryptographic constraints and expiration."""
    signing_key = key or settings.JWT_SECRET
    allowed_algorithms = algorithms or [settings.JWT_ALGORITHM]

    # Explicit defense against "none" algorithm attacks
    if "none" in [a.lower() for a in allowed_algorithms]:
        raise AuthenticationError("Unsecured JWT algorithm 'none' is strictly prohibited.")

    expected_issuer = issuer or settings.OIDC_ISSUER_URL
    expected_audience = audience or settings.OIDC_AUDIENCE

    options: dict[str, Any] = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iat": True,
        "verify_iss": bool(expected_issuer),
        "verify_aud": bool(expected_audience),
    }

    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=allowed_algorithms,
            audience=expected_audience,
            issuer=expected_issuer,
            options=options,  # type: ignore[arg-type]
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("Authentication token has expired.") from e
    except jwt.InvalidIssuerError as e:
        raise AuthenticationError(f"Token issuer verification failed: {e}") from e
    except jwt.InvalidAudienceError as e:
        raise AuthenticationError(f"Token audience verification failed: {e}") from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid authentication token: {e}") from e

    # Ensure required claims are present
    if "sub" not in payload:
        raise AuthenticationError("Token payload is missing subject claim ('sub').")

    tenant_id = payload.get("tenant_id") or settings.DEFAULT_TENANT_ID

    return TokenPayload(
        sub=str(payload["sub"]),
        tenant_id=str(tenant_id),
        roles=payload.get("roles", ["engineer"]),
        email=payload.get("email"),
        exp=int(payload.get("exp", 0)),
        iss=payload.get("iss"),
        aud=payload.get("aud"),
    )


SESSION_COOKIE_NAME = "changescope_session"


def set_secure_session_cookie(
    response: Any,
    token: str,
    max_age_seconds: int = 86400,
    secure: bool | None = None,
) -> None:
    """Sets a hardened, tamper-resistant HttpOnly session cookie."""
    is_secure = (settings.ENVIRONMENT != "local") if secure is None else secure
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )


def get_session_cookie(request: Any) -> str | None:
    """Extracts the session token from request cookies if present."""
    if hasattr(request, "cookies"):
        val = request.cookies.get(SESSION_COOKIE_NAME)
        return str(val) if val is not None else None
    return None


def clear_session_cookie(response: Any) -> None:
    """Clears the session cookie on logout."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        path="/",
    )
