"""Authenticated Encryption at Rest for Sensitive Stored Credentials (AES-256-GCM)."""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from packages.shared.config import settings
from packages.shared.errors import ChangeScopeBaseError


class EncryptionError(ChangeScopeBaseError):
    """Raised when cryptographic encryption or decryption of credentials fails."""

    status_code = 500
    error_type = "https://changescope.io/errors/credential-encryption-failure"
    title = "Credential Encryption Failure"


class CredentialEncryption:
    """Production-grade authenticated encryption using AES-256-GCM.

    Derives a 256-bit encryption key using SHA-256 from the master secret.
    Generates a cryptographically random 96-bit (12-byte) initialization vector (nonce)
    for every encryption operation to prevent replay and ciphertext analysis.
    """

    KEY_VERSION = "v1"

    @classmethod
    def _derive_key(cls, master_secret: str | None = None) -> bytes:
        secret = master_secret or settings.JWT_SECRET
        return hashlib.sha256(secret.encode("utf-8")).digest()

    @classmethod
    def encrypt(cls, plaintext: str, master_secret: str | None = None) -> str:
        """Encrypts a plaintext string into a versioned, base64-encoded AES-256-GCM payload."""
        if not plaintext:
            return ""

        key = cls._derive_key(master_secret)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit standard GCM nonce
        plaintext_bytes = plaintext.encode("utf-8")

        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)
        combined = nonce + ciphertext_with_tag
        encoded = base64.urlsafe_b64encode(combined).decode("ascii")
        return f"{cls.KEY_VERSION}:{encoded}"

    @classmethod
    def decrypt(cls, encrypted_text: str, master_secret: str | None = None) -> str:
        """Decrypts a versioned AES-256-GCM ciphertext back to plaintext."""
        if not encrypted_text:
            return ""

        parts = encrypted_text.split(":", 1)
        if len(parts) != 2:
            raise EncryptionError("Invalid encrypted payload format. Expected 'version:ciphertext'.")

        version, encoded_payload = parts
        if version != cls.KEY_VERSION:
            raise EncryptionError(f"Unsupported key version '{version}'.")

        try:
            combined = base64.urlsafe_b64decode(encoded_payload.encode("ascii"))
            if len(combined) < 28:  # 12 bytes nonce + at least 16 bytes auth tag
                raise EncryptionError("Corrupt ciphertext payload.")

            nonce = combined[:12]
            ciphertext_with_tag = combined[12:]

            key = cls._derive_key(master_secret)
            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            return decrypted_bytes.decode("utf-8")
        except Exception as exc:
            raise EncryptionError(f"Failed to decrypt credential: {exc}") from exc
