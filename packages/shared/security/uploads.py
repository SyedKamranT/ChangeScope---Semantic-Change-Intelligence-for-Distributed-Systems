"""Secure file upload and archive validation preventing malicious uploads and Zip Slip."""

import io
import os
import zipfile
from pathlib import Path

from packages.shared.config import settings
from packages.shared.errors import ChangeScopeBaseError


class UploadSecurityError(ChangeScopeBaseError):
    """Raised when an uploaded file or archive violates security constraints."""

    status_code = 400
    error_type = "https://changescope.io/errors/upload-security-violation"
    title = "Upload Security Violation"


# Signatures for dangerous executable formats that must never be uploaded
PROHIBITED_MAGIC_SIGNATURES = [
    (b"MZ", "Windows PE / EXE / DLL executable"),
    (b"\x7fELF", "Linux ELF executable"),
    (b"\xfe\xed\xfa\xce", "Mach-O 32-bit executable"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit executable"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit reverse executable"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit reverse executable"),
    (b"\xca\xfe\xba\xbe", "Java class file or Universal Mach-O binary"),
    (b"#!", "Executable script interpreter directive"),
]


class UploadValidator:
    """Validates uploaded files and archives against path traversal, executable signatures, and size boundaries."""

    ALLOWED_SPEC_EXTENSIONS = {".json", ".yaml", ".yml", ".zip", ".tar", ".gz", ".proto"}

    @classmethod
    def validate_file_metadata(
        cls,
        filename: str,
        size_bytes: int,
        max_size_bytes: int | None = None,
        allowed_extensions: set[str] | None = None,
    ) -> None:
        """Validates filename extension and size constraints prior to reading content."""
        if not filename or not isinstance(filename, str):
            raise UploadSecurityError("Invalid filename provided.")

        limit = max_size_bytes or settings.MAX_FILE_SIZE_BYTES
        if size_bytes > limit:
            raise UploadSecurityError(
                f"File '{filename}' exceeds maximum allowed size of {limit:,} bytes (got {size_bytes:,} bytes)."
            )

        ext = Path(filename).suffix.lower()
        allowed = allowed_extensions or cls.ALLOWED_SPEC_EXTENSIONS
        if ext not in allowed:
            raise UploadSecurityError(
                f"File extension '{ext}' is prohibited. Allowed extensions: {', '.join(sorted(allowed))}."
            )

    @classmethod
    def inspect_magic_bytes(cls, content: bytes, filename: str = "upload") -> None:
        """Inspects file headers to detect masqueraded executable binaries."""
        if not content:
            return

        for signature, desc in PROHIBITED_MAGIC_SIGNATURES:
            if content.startswith(signature):
                raise UploadSecurityError(
                    f"Uploaded file '{filename}' was identified as a prohibited executable binary: {desc}."
                )

    @classmethod
    def validate_zip_archive(
        cls,
        archive_bytes: bytes,
        max_total_size: int | None = None,
        max_file_count: int | None = None,
    ) -> list[str]:
        """Inspects a ZIP archive in-memory for Zip Slip path traversal and zip bombs."""
        limit_size = max_total_size or settings.MAX_ARCHIVE_SIZE_BYTES
        limit_count = max_file_count or settings.MAX_ARCHIVE_FILE_COUNT

        if len(archive_bytes) > limit_size:
            raise UploadSecurityError(f"Archive exceeds maximum compressed size of {limit_size:,} bytes.")

        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                infolist = zf.infolist()
                if len(infolist) > limit_count:
                    raise UploadSecurityError(
                        f"Archive contains {len(infolist)} files, exceeding limit of {limit_count}."
                    )

                total_uncompressed = 0
                valid_paths: list[str] = []

                for info in infolist:
                    filename = info.filename
                    # 1. Path Traversal & Zip Slip Defense
                    normalized = os.path.normpath(filename)
                    if (
                        filename.startswith("/")
                        or filename.startswith("\\")
                        or ".." in normalized.split(os.sep)
                        or (len(filename) > 1 and filename[1] == ":")
                    ):
                        raise UploadSecurityError(
                            f"Zip Slip path traversal attempt detected in archive member: '{filename}'."
                        )

                    total_uncompressed += info.file_size
                    if total_uncompressed > limit_size * 10:
                        raise UploadSecurityError("Zip bomb detected: Uncompressed ratio exceeds safety limits.")

                    valid_paths.append(normalized)

                return valid_paths
        except zipfile.BadZipFile as exc:
            raise UploadSecurityError("Corrupt or invalid ZIP archive.") from exc
