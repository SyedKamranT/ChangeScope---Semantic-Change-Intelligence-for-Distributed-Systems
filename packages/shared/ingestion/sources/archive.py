"""Uploaded Archive (.zip, .tar.gz) Ingestion Source."""

import hashlib
from pathlib import Path

from packages.shared.ingestion.safety import RepoSafetyGuard


class ArchiveSource:
    """Ingests uploaded repository zip or tar archives, enforcing sandbox and ZipSlip safety."""

    @classmethod
    def ingest_archive(
        cls,
        archive_path: Path | str,
        destination_dir: Path | str,
        commit_sha: str | None = None,
    ) -> tuple[Path, str]:
        """Safely extracts an uploaded archive into the tenant sandbox and computes an immutable hash."""
        archive = Path(archive_path).resolve()
        dest = Path(destination_dir).resolve()

        resolved_sha = commit_sha
        if not resolved_sha:
            # Deterministic SHA256 hash of archive content as immutable commit identifier
            h = hashlib.sha256()
            with open(archive, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            resolved_sha = h.hexdigest()[:40]

        clean_sha = RepoSafetyGuard.validate_commit_sha(resolved_sha)

        # Execute safe extraction preventing ZipSlip and size bombs
        RepoSafetyGuard.safe_extract_archive(
            archive_path=archive,
            destination_dir=dest,
        )

        return dest, clean_sha
