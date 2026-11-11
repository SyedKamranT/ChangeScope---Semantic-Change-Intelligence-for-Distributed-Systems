"""Webhook cryptographic signature verification with replay protection."""

import hashlib
import hmac
import time

from packages.shared.errors import ChangeScopeBaseError


class WebhookVerificationError(ChangeScopeBaseError):
    """Raised when an incoming webhook signature or replay check fails."""

    status_code = 401
    error_type = "https://changescope.io/errors/webhook-verification-failure"
    title = "Webhook Verification Failure"


class WebhookVerifier:
    """Verifies HMAC-SHA256 webhook signatures and enforces strict replay prevention windows."""

    DEFAULT_TOLERANCE_SECONDS = 300  # 5 minutes replay window

    @classmethod
    def verify_github_signature(
        cls,
        payload_bytes: bytes,
        signature_header: str | None,
        secret: str,
    ) -> bool:
        """Verifies GitHub 'X-Hub-Signature-256' header (sha256=<hex_digest>)."""
        if not signature_header:
            raise WebhookVerificationError("Missing 'X-Hub-Signature-256' header.")

        prefix = "sha256="
        if not signature_header.startswith(prefix):
            raise WebhookVerificationError("Invalid signature format. Expected 'sha256=<hex_digest>'.")

        expected_sig = signature_header[len(prefix) :].strip()
        mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
        computed_sig = mac.hexdigest()

        if not hmac.compare_digest(computed_sig, expected_sig):
            raise WebhookVerificationError("HMAC signature verification failed.")

        return True

    @classmethod
    def verify_timestamped_signature(
        cls,
        payload_bytes: bytes,
        signature_header: str | None,
        timestamp_header: str | int | None,
        secret: str,
        tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    ) -> bool:
        """Verifies an HMAC signature bound to a timestamp header to prevent replay attacks.

        Computes HMAC-SHA256 over: f"{timestamp}.{payload_str}".
        """
        if not signature_header:
            raise WebhookVerificationError("Missing signature header.")
        if timestamp_header is None:
            raise WebhookVerificationError("Missing timestamp header for replay protection.")

        try:
            ts = int(timestamp_header)
        except (ValueError, TypeError) as exc:
            raise WebhookVerificationError("Invalid timestamp header format.") from exc

        # Replay Window Check
        current_time = int(time.time())
        if current_time - ts > tolerance_seconds:
            raise WebhookVerificationError(
                f"Webhook timestamp expired. Delivered at {ts}, current time {current_time} "
                f"(tolerance: {tolerance_seconds}s)."
            )
        if ts - current_time > 60:
            raise WebhookVerificationError("Webhook timestamp is in the future. Clock skew detected.")

        # Compute HMAC over f"{ts}.{payload}"
        msg = f"{ts}.".encode() + payload_bytes
        mac = hmac.new(secret.encode("utf-8"), msg=msg, digestmod=hashlib.sha256)
        computed_sig = mac.hexdigest()

        # Handle optional 'v1=' prefix if present
        clean_sig = signature_header.replace("v1=", "").strip()

        if not hmac.compare_digest(computed_sig, clean_sig):
            raise WebhookVerificationError("HMAC timestamped signature verification failed.")

        return True
