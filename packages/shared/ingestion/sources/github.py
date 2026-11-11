"""GitHub Remote Repository Ingestion Source."""

import base64
import subprocess
from pathlib import Path

from packages.shared.errors import IngestionError
from packages.shared.ingestion.safety import RepoSafetyGuard


class GitHubRepoSource:
    """Ingests remote repositories from approved Git hosts via sandboxed sparse clone."""

    @classmethod
    def ingest_remote_repo(
        cls,
        clone_url: str,
        commit_sha: str,
        destination_dir: Path | str,
        auth_token: str | None = None,
    ) -> tuple[Path, str]:
        """Clones a remote repository at an exact immutable commit SHA into the tenant sandbox."""
        validated_url = RepoSafetyGuard.validate_clone_url(clone_url)
        clean_sha = RepoSafetyGuard.validate_commit_sha(commit_sha)
        dest = Path(destination_dir).resolve()
        dest.mkdir(parents=True, exist_ok=True)

        auth_config_args: list[str] = []
        if auth_token:
            basic_b64 = base64.b64encode(f"x-access-token:{auth_token}".encode()).decode("ascii")
            auth_config_args = ["-c", f"http.extraHeader=Authorization: Basic {basic_b64}"]

        try:
            # 1. Initialize git in destination
            init_cmd = RepoSafetyGuard.sanitize_command_args(["git", "init", str(dest)])
            subprocess.run(init_cmd, capture_output=True, text=True, check=True, timeout=30)

            # 2. Add remote without writing plaintext credentials to .git/config
            remote_cmd = RepoSafetyGuard.sanitize_command_args(
                ["git", "-C", str(dest), "remote", "add", "origin", validated_url]
            )
            subprocess.run(remote_cmd, capture_output=True, text=True, check=True, timeout=30)

            # 3. Fetch exact commit with depth 1 using ephemeral Authorization header
            fetch_cmd = RepoSafetyGuard.sanitize_command_args(
                ["git", *auth_config_args, "-C", str(dest), "fetch", "--depth", "1", "origin", clean_sha]
            )
            subprocess.run(fetch_cmd, capture_output=True, text=True, check=True, timeout=60)

            # 4. Checkout commit
            checkout_cmd = RepoSafetyGuard.sanitize_command_args(["git", "-C", str(dest), "checkout", clean_sha])
            subprocess.run(checkout_cmd, capture_output=True, text=True, check=True, timeout=30)

        except subprocess.TimeoutExpired as err:
            raise IngestionError(f"Git clone operation timed out after {err.timeout}s.") from err
        except subprocess.CalledProcessError as err:
            # Sanitize stderr to remove token if present
            err_msg = err.stderr.replace(auth_token, "***") if auth_token else err.stderr
            raise IngestionError(f"Git clone operation failed: {err_msg}") from err

        return dest, clean_sha
