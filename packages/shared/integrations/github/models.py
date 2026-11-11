"""Pydantic v2 domain schemas for GitHub App and Webhook integrations."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    """GitHub user or bot actor model."""

    login: str
    id: int
    type: str = "User"
    avatar_url: str | None = None


class GitHubRepository(BaseModel):
    """GitHub repository reference model."""

    id: int
    name: str
    full_name: str
    private: bool = False
    html_url: str = ""
    clone_url: str = ""
    default_branch: str = "main"
    owner: GitHubUser | None = None


class GitHubCommitRef(BaseModel):
    """Git commit SHA and branch reference pointer."""

    label: str | None = None
    ref: str = ""
    sha: str
    repo: GitHubRepository | None = None


class GitHubPullRequest(BaseModel):
    """GitHub Pull Request entity representation."""

    id: int
    number: int
    state: str = "open"  # open, closed
    title: str
    body: str | None = None
    user: GitHubUser
    html_url: str
    diff_url: str | None = None
    base: GitHubCommitRef
    head: GitHubCommitRef
    merged: bool = False
    mergeable: bool | None = None


class GitHubFileChange(BaseModel):
    """A file modified in a GitHub Pull Request or commit diff."""

    filename: str
    status: Literal["added", "removed", "modified", "renamed", "copied", "changed", "unchanged"] = "modified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    blob_url: str | None = None
    raw_url: str | None = None


class GitHubInstallation(BaseModel):
    """GitHub App Installation descriptor."""

    id: int
    account: dict[str, Any] = Field(default_factory=dict)
    app_id: int | None = None
    target_id: int | None = None
    target_type: str | None = None
    permissions: dict[str, str] = Field(default_factory=dict)
    events: list[str] = Field(default_factory=list)


class GitHubInstallationToken(BaseModel):
    """Short-lived GitHub App Installation Access Token."""

    token: str
    expires_at: datetime
    permissions: dict[str, str] = Field(default_factory=dict)
    repository_selection: str = "all"


class GitHubCheckRunAnnotation(BaseModel):
    """Line-level annotation for a GitHub Check Run."""

    path: str
    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None
    annotation_level: Literal["notice", "warning", "failure"]
    message: str
    title: str | None = None
    raw_details: str | None = None


class GitHubCheckRunOutput(BaseModel):
    """Output summary payload for a GitHub Check Run."""

    title: str
    summary: str
    text: str | None = None
    annotations: list[GitHubCheckRunAnnotation] = Field(default_factory=list)


class GitHubCheckRunCreate(BaseModel):
    """Payload to create or update a GitHub Check Run."""

    name: str = "ChangeScope Semantic Intelligence"
    head_sha: str
    details_url: str | None = None
    external_id: str | None = None
    status: Literal["queued", "in_progress", "completed"] = "completed"
    conclusion: Literal[
        "action_required",
        "cancelled",
        "failure",
        "neutral",
        "success",
        "skipped",
        "stale",
        "timed_out",
    ] = "neutral"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: GitHubCheckRunOutput


class GitHubCheckRunResponse(BaseModel):
    """GitHub API response for a created or updated Check Run."""

    id: int
    name: str
    head_sha: str
    status: str
    conclusion: str | None = None
    html_url: str
    details_url: str | None = None


class GitHubWebhookResult(BaseModel):
    """Unified result schema returned by ChangeScope webhook processing."""

    status: str  # ACCEPTED, DUPLICATE_IGNORED, UNAUTHORIZED_REPOSITORY, EVENT_IGNORED, PONG
    delivery_id: str | None = None
    event_type: str | None = None
    action: str | None = None
    repository: str | None = None
    scan_id: str | None = None
    message: str | None = None
