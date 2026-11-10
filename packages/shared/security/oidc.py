"""OpenID Connect (OIDC) discovery and cryptographic key provider for ChangeScope."""

from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from pydantic import BaseModel, Field

from packages.shared.config import settings
from packages.shared.errors import AuthenticationError, ServiceUnavailableError
from packages.shared.logger import logger


class OIDCConfig(BaseModel):
    """OIDC Provider configuration metadata discovered via .well-known/openid-configuration."""

    issuer: str
    jwks_uri: str
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    response_types_supported: list[str] = Field(default_factory=list)
    id_token_signing_alg_values_supported: list[str] = Field(default_factory=lambda: ["RS256"])


class OIDCClient:
    """Production-grade client for OIDC discovery, JWKS key retrieval and caching."""

    def __init__(
        self,
        issuer_url: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.issuer_url = (issuer_url or settings.OIDC_ISSUER_URL or "").rstrip("/")
        self.timeout = timeout_seconds
        self._config: OIDCConfig | None = None
        self._jwks_client: PyJWKClient | None = None
        self._last_refresh: datetime | None = None

    @property
    def is_configured(self) -> bool:
        """Indicates whether an external OIDC provider is configured."""
        return bool(self.issuer_url)

    async def discover(self) -> OIDCConfig:
        """Fetches the OpenID Connect discovery document with timeout and error handling."""
        if not self.is_configured:
            raise AuthenticationError("OIDC provider issuer URL is not configured.")

        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
                data = response.json()
                self._config = OIDCConfig(**data)
                self._jwks_client = PyJWKClient(self._config.jwks_uri, cache_keys=True, max_cached_keys=16)
                self._last_refresh = datetime.now(UTC)
                logger.info("oidc_discovery_successful", issuer=self._config.issuer, jwks_uri=self._config.jwks_uri)
                return self._config
        except httpx.TimeoutException as exc:
            logger.error("oidc_discovery_timeout", url=discovery_url, error=str(exc))
            raise ServiceUnavailableError("OIDC identity provider discovery timed out.") from exc
        except httpx.HTTPError as exc:
            logger.error("oidc_discovery_failed", url=discovery_url, error=str(exc))
            raise ServiceUnavailableError(f"Failed to fetch OIDC configuration: {exc}") from exc
        except Exception as exc:
            logger.error("oidc_discovery_unexpected_error", error=str(exc))
            raise AuthenticationError(f"OIDC discovery error: {exc}") from exc

    def get_signing_key_for_token(self, token: str) -> Any:
        """Extracts the Key ID (kid) from the JWT header and retrieves the corresponding public key."""
        if not self._jwks_client:
            raise AuthenticationError("OIDC client has not completed discovery or JWKS is unavailable.")

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            return signing_key.key
        except jwt.PyJWKClientError as exc:
            logger.warning("oidc_jwks_key_not_found", error=str(exc))
            raise AuthenticationError(f"Unable to find cryptographic key matching token header: {exc}") from exc


oidc_client = OIDCClient()
