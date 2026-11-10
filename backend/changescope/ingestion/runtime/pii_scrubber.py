"""OpenTelemetry Trace Span PII Sanitizer and Attribute Scrubber."""

import re
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "token",
    "password",
    "secret",
    "proxy-authorization",
}

PAN_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


class PIIScrubber:
    """Sanitizes incoming OTLP span attributes in-memory before buffering."""

    @classmethod
    def scrub_attributes(cls, attributes: dict[str, Any]) -> dict[str, Any]:
        """Scrubs sensitive keys and redacts regex PII matches from string values."""
        scrubbed = {}

        for k, v in attributes.items():
            k_lower = k.lower()
            if any(sensitive in k_lower for sensitive in SENSITIVE_KEYS):
                scrubbed[k] = "[REDACTED_CREDENTIAL]"
                continue

            if isinstance(v, str):
                v_clean = PAN_REGEX.sub("[REDACTED_PAN]", v)
                v_clean = SSN_REGEX.sub("[REDACTED_SSN]", v_clean)
                v_clean = EMAIL_REGEX.sub("[REDACTED_EMAIL]", v_clean)

                # Scrub raw SQL literals if db.statement
                if k == "db.statement":
                    v_clean = re.sub(r"'\w+'", "'?'", v_clean)
                    v_clean = re.sub(r"\b\d+\b", "?", v_clean)

                scrubbed[k] = v_clean
            elif isinstance(v, dict):
                scrubbed[k] = cls.scrub_attributes(v)
            else:
                scrubbed[k] = v

        return scrubbed
