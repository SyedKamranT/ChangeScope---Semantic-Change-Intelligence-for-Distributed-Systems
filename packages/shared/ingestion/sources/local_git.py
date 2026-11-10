"""Local Git Repository Ingestion Source."""

import shutil
import subprocess
from pathlib import Path

from packages.shared.errors import IngestionError
from packages.shared.ingestion.safety import RepoSafetyGuard


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
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    resolved_sha = res.stdout.strip()
                except Exception:
                    resolved_sha = "0000000000000000000000000000000000000000"
            else:
                resolved_sha = "0000000000000000000000000000000000000000"

        clean_sha = RepoSafetyGuard.validate_commit_sha(resolved_sha)

        # Copy repository tree into destination sandbox, ignoring .git
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.name == ".git":
                continue
            target = dest / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

        return dest, clean_sha
