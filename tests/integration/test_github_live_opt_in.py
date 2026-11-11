"""Opt-in live integration tests connecting to GitHub REST API.

Run only when CHANGESCOPE_LIVE_GITHUB_TEST=1 and live credentials are provided.
"""

import os

import pytest

from packages.shared.integrations.github import (
    GitHubAppAuth,
    GitHubClient,
)


@pytest.mark.skipif(
    not os.getenv("CHANGESCOPE_LIVE_GITHUB_TEST"),
    reason="Skipped: Opt-in live GitHub integration test (requires CHANGESCOPE_LIVE_GITHUB_TEST=1)",
)
@pytest.mark.asyncio
async def test_live_github_client_connection():
    """Validates live connectivity to GitHub API with live credentials or personal access token."""
    token = os.getenv("CHANGESCOPE_LIVE_GITHUB_TOKEN")
    repo = os.getenv("CHANGESCOPE_LIVE_GITHUB_REPO", "octocat/Hello-World")
    if not token:
        pytest.skip("CHANGESCOPE_LIVE_GITHUB_TOKEN not configured for live test.")

    auth = GitHubAppAuth(default_token=token)
    client = GitHubClient(auth=auth)

    # Test read operation on public repository
    diff = await client.get_commit_diff(repo, "master", "master")
    assert "status" in diff or "commits" in diff
