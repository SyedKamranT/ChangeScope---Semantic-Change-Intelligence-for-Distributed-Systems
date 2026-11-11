"""Local Git Repository Ingestion Source."""

import shutil
import subprocess
from pathlib import Path

from packages.shared.errors import IngestionError, SecurityViolationError
from packages.shared.ingestion.safety import RepoSafetyGuard
from packages.shared.logger import logger


class LocalGitSource:
    """Ingests a local filesystem repository, resolving commit identifiers safely."""

    @classmethod
    def ingest_local_repo(
        cls,
        source_path: Path | str,
        destination_dir: Path | str,
        commit_sha: str | None = None,
    ) -> tuple[Path, str]:
        """Copies or checks out local repository files into the tenant-isolated sandbox."""
        src = Path(source_path).resolve()
        dest = Path(destination_dir).resolve()

        if not src.exists() or not src.is_dir():
            raise IngestionError(f"Local repository path '{src}' does not exist or is not a directory.")

        resolved_sha = commit_sha
        if not resolved_sha:
            # Query git rev-parse HEAD if git repo
            git_dir = src / ".git"
            if git_dir.exists():
                try:
                    cmd = RepoSafetyGuard.sanitize_command_args(["git", "-C", str(src), "rev-parse", "HEAD"])
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                    resolved_sha = res.stdout.strip()
                except Exception as exc:
                    logger.warning("local_git_rev_parse_fallback", source=str(src), error=str(exc))
                    resolved_sha = "0000000000000000000000000000000000000000"
            else:
                resolved_sha = "0000000000000000000000000000000000000000"

        clean_sha = RepoSafetyGuard.validate_commit_sha(resolved_sha)

        # Copy repository tree into destination sandbox, preserving symlinks as links (never dereferencing escapes)
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.name == ".git":
                continue
            target = dest / item.name
            if item.is_symlink():
                resolved_target = item.resolve()
                if not str(resolved_target).startswith(str(src)):
                    raise SecurityViolationError(f"Symlink '{item.name}' escapes local repository root '{src}'.")
                continue
            if item.is_dir():
                shutil.copytree(item, target, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

        # Remove or reject any nested symlinks escaping dest
        for copied in list(dest.rglob("*")):
            if copied.is_symlink():
                if not str(copied.resolve()).startswith(str(dest)):
                    copied.unlink(missing_ok=True)
                    raise SecurityViolationError(f"Nested symlink '{copied.name}' escapes sandbox destination.")

        return dest, clean_sha
