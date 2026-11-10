"""GitHub Pull Request Ingestion and Diff Analyzer."""

import re
from dataclasses import dataclass, field
from typing import Any

from packages.shared.ingestion.safety import RepoSafetyGuard


@dataclass
class ChangedFile:
    """Represents a file modified in a pull request."""

    filename: str
    status: str  # 'added', 'modified', 'removed', 'renamed'
    additions: int = 0
    deletions: int = 0
    patch: str | None = None
    modified_lines: list[int] = field(default_factory=list)


@dataclass
class PRMetadata:
    """Structured Pull Request metadata payload."""

    pr_number: int
    title: str
    base_sha: str
    head_sha: str
    author: str
    changed_files: list[ChangedFile] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


class GitHubPRIngestor:
    """Extracts changed files, commit hashes, and line-level diff hunks from GitHub PR payloads."""

    @classmethod
    def parse_pr_payload(cls, payload: dict[str, Any]) -> PRMetadata:
        """Parses webhook or REST API pull request payload into normalized metadata."""
        pr_data = payload.get("pull_request", payload)
        pr_number = pr_data.get("number", 0)
        title = pr_data.get("title", "PR")
        user = pr_data.get("user", {}).get("login", "unknown")

        base_sha = RepoSafetyGuard.validate_commit_sha(pr_data.get("base", {}).get("sha", "0" * 40))
        head_sha = RepoSafetyGuard.validate_commit_sha(pr_data.get("head", {}).get("sha", "0" * 40))

        changed_files: list[ChangedFile] = []
        raw_files = payload.get("files", [])

        for rf in raw_files:
            patch = rf.get("patch")
            mod_lines = cls.parse_patch_lines(patch) if patch else []
            changed_files.append(
                ChangedFile(
                    filename=rf.get("filename", ""),
                    status=rf.get("status", "modified"),
                    additions=rf.get("additions", 0),
                    deletions=rf.get("deletions", 0),
                    patch=patch,
                    modified_lines=mod_lines,
                )
            )

        return PRMetadata(
            pr_number=pr_number,
            title=title,
            base_sha=base_sha,
            head_sha=head_sha,
            author=user,
            changed_files=changed_files,
            raw_payload=payload,
        )

    @classmethod
    def parse_patch_lines(cls, patch_str: str) -> list[int]:
        """Extracts modified line numbers in the new file from a unified git diff hunk header @@ -a,b +c,d @@."""
        lines: list[int] = []
        current_line = 0

        for text_line in patch_str.splitlines():
            hunk_match = re.match(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@", text_line)
            if hunk_match:
                current_line = int(hunk_match.group(1))
            elif text_line.startswith("+") and not text_line.startswith("+++"):
                lines.append(current_line)
                current_line += 1
            elif not text_line.startswith("-"):
                current_line += 1

        return lines
