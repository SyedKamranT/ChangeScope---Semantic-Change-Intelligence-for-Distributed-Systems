"""OpenTelemetry Span In-Memory PII & Credential Sanitizer."""

import re
from typing import Any

SENSITIVE_KEY_SUBSTRINGS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api_key",
    "api-key",
    "apikey",
    "token",
    "password",
    "passwd",
    "secret",
    "private_key",
    "proxy-authorization",
    "client_secret",
}

PAN_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
JWT_REGEX = re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+")
QUERY_SECRET_REGEX = re.compile(r"([?&][^=]*(?:token|key|secret|password|passwd|auth|sig)[^=]*=)[^&]+", re.IGNORECASE)


class PIIScrubber:
    """Sanitizes incoming OTLP span attributes and resource labels in-memory before buffering."""

    @classmethod
    def scrub_attributes(cls, attributes: dict[str, Any]) -> dict[str, Any]:
        """Scrubs sensitive keys, tokens, emails, PANs, and parameters from an attribute mapping."""
        scrubbed: dict[str, Any] = {}

        for k, v in attributes.items():
            k_lower = str(k).lower()

            # 1. Exact or partial sensitive key match
            if any(sensitive in k_lower for sensitive in SENSITIVE_KEY_SUBSTRINGS):
                scrubbed[k] = "[REDACTED_CREDENTIAL]"
                continue

            # 2. String values scrubbing
            if isinstance(v, str):
                v_clean = JWT_REGEX.sub("[REDACTED_JWT]", v)
                v_clean = PAN_REGEX.sub("[REDACTED_PAN]", v_clean)
                v_clean = SSN_REGEX.sub("[REDACTED_SSN]", v_clean)
                v_clean = EMAIL_REGEX.sub("[REDACTED_EMAIL]", v_clean)
                v_clean = QUERY_SECRET_REGEX.sub(r"\1[REDACTED]", v_clean)

                # Scrub raw SQL statements
                if k in {"db.statement", "sql.query"}:
                    v_clean = re.sub(r"'[^']*'", "'?'", v_clean)
                    v_clean = re.sub(r"\b\d+\b", "?", v_clean)

                scrubbed[k] = v_clean
            elif isinstance(v, dict):
                scrubbed[k] = cls.scrub_attributes(v)
            elif isinstance(v, list):
                scrubbed[k] = [
                    cls.scrub_attributes(item)
                    if isinstance(item, dict)
                    else (cls.scrub_string(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                scrubbed[k] = v

        return scrubbed

    @classmethod
    def scrub_string(cls, val: str) -> str:
        """Sanitizes a standalone string containing potential PII or JWTs."""
        v = JWT_REGEX.sub("[REDACTED_JWT]", val)
        v = PAN_REGEX.sub("[REDACTED_PAN]", v)
        v = SSN_REGEX.sub("[REDACTED_SSN]", v)
        v = EMAIL_REGEX.sub("[REDACTED_EMAIL]", v)
        return QUERY_SECRET_REGEX.sub(r"\1[REDACTED]", v)
