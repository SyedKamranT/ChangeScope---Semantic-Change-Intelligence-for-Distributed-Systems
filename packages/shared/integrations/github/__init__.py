"""GitHub App & Webhook integration package."""

from packages.shared.integrations.github.client import (
    GitHubAppAuth,
    GitHubClient,
    GitHubIntegrationError,
    GitHubRateLimitError,
    sanitize_secret,
)
from packages.shared.integrations.github.formatter import GitHubReportFormatter
from packages.shared.integrations.github.models import (
    GitHubCheckRunAnnotation,
    GitHubCheckRunCreate,
    GitHubCheckRunOutput,
    GitHubCheckRunResponse,
    GitHubCommitRef,
    GitHubFileChange,
    GitHubInstallation,
    GitHubInstallationToken,
    GitHubPullRequest,
    GitHubRepository,
    GitHubUser,
    GitHubWebhookResult,
)
from packages.shared.integrations.github.webhook_handler import (
    GitHubWebhookError,
    GitHubWebhookHandler,
)

__all__ = [
    "GitHubAppAuth",
    "GitHubCheckRunAnnotation",
    "GitHubCheckRunCreate",
    "GitHubCheckRunOutput",
    "GitHubCheckRunResponse",
    "GitHubClient",
    "GitHubCommitRef",
    "GitHubFileChange",
    "GitHubInstallation",
    "GitHubInstallationToken",
    "GitHubIntegrationError",
    "GitHubPullRequest",
    "GitHubRateLimitError",
    "GitHubReportFormatter",
    "GitHubRepository",
    "GitHubUser",
    "GitHubWebhookError",
    "GitHubWebhookHandler",
    "GitHubWebhookResult",
    "sanitize_secret",
]
