"""Repository Safety Guard, Sandbox Boundary Enforcement, and Path Traversal Defenses."""

import os
import re
import stat
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from packages.shared.config import settings
from packages.shared.errors import IngestionError, SecurityViolationError

# Immutable Commit SHA format: 7 to 64 hexadecimal characters
COMMIT_SHA_REGEX = re.compile(r"^[0-9a-fA-F]{7,64}$")
# Disallowed shell characters for argument sanitization
SHELL_METACHRACTERS_REGEX = re.compile(r"[\x00;&|`$><!\r\n]")


class RepoSafetyGuard:
    """Enforces strict isolation, sandboxing, and security invariants for ingested repositories."""

    @classmethod
    def validate_commit_sha(cls, commit_sha: str) -> str:
        """Enforces immutable, hexadecimal commit identifier to prevent command or argument injection."""
        clean = commit_sha.strip()
        if not COMMIT_SHA_REGEX.match(clean):
            raise SecurityViolationError(f"Invalid commit SHA '{commit_sha}'. Must be 7-64 hexadecimal characters.")
        return clean

    @classmethod
    def validate_clone_url(
        cls,
        clone_url: str,
        approved_hosts: list[str] | None = None,
    ) -> str:
        """Validates remote repository URL against approved host whitelist and injection patterns."""
        clean_url = clone_url.strip()
        if SHELL_METACHRACTERS_REGEX.search(clean_url):
            raise SecurityViolationError("Repository URL contains illegal shell metacharacters.")

        # Local directory path support for hermetic testing and development
        if (
            clean_url.startswith("file://")
            or os.path.isabs(clean_url)
            or clean_url.startswith("./")
            or clean_url.startswith("../")
        ):
            local_path = clean_url.replace("file://", "")
            if not Path(local_path).exists():
                raise IngestionError(f"Local repository path '{local_path}' does not exist.")
            return clean_url

        try:
            parsed = urlparse(clean_url)
        except Exception as err:
            raise SecurityViolationError(f"Malformed repository clone URL: {err}") from err

        if parsed.scheme not in {"https", "git", "ssh"}:
            raise SecurityViolationError(
                f"Unsupported URL scheme '{parsed.scheme}'. Only https, git, and ssh are permitted."
            )

        hosts = approved_hosts or settings.ALLOWED_GIT_HOSTS
        host = (parsed.hostname or "").lower()
        if host not in hosts:
            raise SecurityViolationError(f"Host '{host}' is not in approved repository hosts: {hosts}.")

        return clean_url

    @classmethod
    def sanitize_command_args(cls, args: list[str]) -> list[str]:
        """Validates argument lists passed to subprocesses, guaranteeing no shell interpolation."""
        clean_args: list[str] = []
        for arg in args:
            if "\x00" in arg:
                raise SecurityViolationError("Subprocess argument contains null byte.")
            clean_args.append(arg)
        return clean_args

    @classmethod
    def get_tenant_storage_path(
        cls,
        tenant_id: str,
        workspace_id: str,
        repo_id: str,
        commit_sha: str,
        base_dir: Path | str | None = None,
    ) -> Path:
        """Computes and validates a tenant-scoped, sandbox-isolated filesystem storage path."""
        cls.validate_commit_sha(commit_sha)
        root = Path(base_dir or settings.STORAGE_BASE_DIR).resolve()

        # Sanitize tenant identifiers to alphanumeric + hyphens
        for label, val in [("tenant_id", tenant_id), ("workspace_id", workspace_id), ("repo_id", repo_id)]:
            if not re.match(r"^[a-zA-Z0-9_-]+$", val):
                raise SecurityViolationError(f"Invalid identifier '{val}' for {label}.")

        dest = (root / "tenants" / tenant_id / "workspaces" / workspace_id / "repos" / repo_id / commit_sha).resolve()
        # Verify no directory traversal outside root
        if not str(dest).startswith(str(root)):
            raise SecurityViolationError("Tenant storage path attempts traversal outside storage root.")

        dest.mkdir(parents=True, exist_ok=True)
        return dest

    @classmethod
    def safe_extract_archive(
        cls,
        archive_path: Path | str,
        destination_dir: Path | str,
        max_size_bytes: int | None = None,
        max_files: int | None = None,
        max_single_file_bytes: int | None = None,
    ) -> list[Path]:
        """Safely extracts zip or tar archives, strictly preventing ZipSlip and decompression bombs."""
        archive = Path(archive_path).resolve()
        dest = Path(destination_dir).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        max_size = max_size_bytes or settings.MAX_ARCHIVE_SIZE_BYTES
        max_count = max_files or settings.MAX_ARCHIVE_FILE_COUNT
        max_single = max_single_file_bytes or settings.MAX_FILE_SIZE_BYTES

        if not archive.exists() or not archive.is_file():
            raise IngestionError(f"Archive file '{archive}' does not exist.")

        extracted_paths: list[Path] = []
        total_extracted_bytes = 0

        # Handle ZIP Archives
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive, "r") as zf:
                infolist = zf.infolist()
                if len(infolist) > max_count:
                    raise SecurityViolationError(
                        f"Archive contains {len(infolist)} files, exceeding limit of {max_count}."
                    )

                for member in infolist:
                    filename = member.filename

                    # 1. ZipSlip Path Traversal Defense
                    if filename.startswith(("/", "\\")) or ".." in Path(filename).parts:
                        raise SecurityViolationError(f"ZipSlip path traversal attempt detected in member: '{filename}'")

                    target_path = (dest / filename).resolve()
                    if not str(target_path).startswith(str(dest)):
                        raise SecurityViolationError(f"ZipSlip traversal attempt outside destination: '{filename}'")

                    # 1b. Symlink Defense inside ZIP (Unix external_attr mode S_IFLNK)
                    unix_mode = member.external_attr >> 16
                    if stat.S_ISLNK(unix_mode):
                        raise SecurityViolationError(f"Symlink entry prohibited inside ZIP archive: '{filename}'")

                    # 2. Size Bomb Defense
                    if member.file_size > max_single:
                        raise SecurityViolationError(
                            f"File '{filename}' uncompressed size {member.file_size} exceeds limit of {max_single} bytes."
                        )

                    total_extracted_bytes += member.file_size
                    if total_extracted_bytes > max_size:
                        raise SecurityViolationError(
                            f"Cumulative uncompressed archive size exceeds limit of {max_size} bytes."
                        )

                    # Extract file or directory
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as source, open(target_path, "wb") as target:
                            target.write(source.read())
                        extracted_paths.append(target_path)

            return extracted_paths

        # Handle TAR Archives (.tar, .tar.gz, .tar.bz2)
        if tarfile.is_tarfile(archive):
            with tarfile.open(archive, "r:*") as tf:
                members = tf.getmembers()
                if len(members) > max_count:
                    raise SecurityViolationError(
                        f"Archive contains {len(members)} files, exceeding limit of {max_count}."
                    )

                for tar_info in members:
                    filename = tar_info.name

                    # 1. Path Traversal Defense
                    if filename.startswith(("/", "\\")) or ".." in Path(filename).parts:
                        raise SecurityViolationError(f"Tar path traversal attempt detected in member: '{filename}'")

                    target_path = (dest / filename).resolve()
                    if not str(target_path).startswith(str(dest)):
                        raise SecurityViolationError(f"Tar traversal attempt outside destination: '{filename}'")

                    # 2. Symlink & Hardlink Escape Defense
                    if tar_info.issym() or tar_info.islnk():
                        # Resolve link target and verify it remains strictly inside destination
                        link_target = (target_path.parent / tar_info.linkname).resolve()
                        if not str(link_target).startswith(str(dest)):
                            raise SecurityViolationError(
                                f"Symlink traversal attempt escaping sandbox: '{filename}' -> '{tar_info.linkname}'"
                            )
                        # Safe to skip extracting dangerous symlinks or extract safely
                        continue

                    # 3. Size Limits
                    if tar_info.size > max_single:
                        raise SecurityViolationError(
                            f"File '{filename}' size {tar_info.size} exceeds limit of {max_single} bytes."
                        )

                    total_extracted_bytes += tar_info.size
                    if total_extracted_bytes > max_size:
                        raise SecurityViolationError(
                            f"Cumulative uncompressed archive size exceeds limit of {max_size} bytes."
                        )

                    if tar_info.isdir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    elif tar_info.isfile():
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        f = tf.extractfile(tar_info)
                        if f:
                            with open(target_path, "wb") as target:
                                target.write(f.read())
                            extracted_paths.append(target_path)

            return extracted_paths

        raise IngestionError(f"Unsupported archive format for file '{archive.name}'.")
