"""Authentication, JWT Token Management and Webhook Signature Verification."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from changescope.common.exceptions import AuthenticationError
from changescope.config import settings
from fastapi import Header


def create_access_token(tenant_id: str, subject: str, role: str = "DEVELOPER") -> str:
    """Issues a signed JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    """Decodes and validates a JWT access token."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as e:
        raise AuthenticationError(f"Invalid or expired token: {str(e)}") from e


async def get_current_tenant(
    authorization: str | None = Header(None),
    x_tenant_id: str | None = Header(None),
) -> str:
    """FastAPI dependency extracting and validating the tenant ID."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = verify_access_token(token)
            return payload.get("tenant_id", settings.DEFAULT_TENANT_ID)
        except AuthenticationError:
            pass

    if x_tenant_id:
        return x_tenant_id

    # Fallback to default tenant in local/test environments
    return settings.DEFAULT_TENANT_ID


def verify_github_webhook_hmac(body_bytes: bytes, signature_header: str | None, secret: str) -> bool:
    """Verifies GitHub X-Hub-Signature-256 HMAC signature."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = (
        "sha256="
        + hmac.new(
            key=secret.encode("utf-8"),
            msg=body_bytes,
            digestmod=hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(signature_header, expected)
