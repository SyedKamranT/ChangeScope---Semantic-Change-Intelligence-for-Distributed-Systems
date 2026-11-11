"""GitHub App REST API client with RS256 authentication, token lifecycle, and rate limit resilience."""

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt

from packages.shared.config import settings
from packages.shared.errors import ChangeScopeBaseError
from packages.shared.integrations.github.models import (
    GitHubCheckRunCreate,
    GitHubCheckRunResponse,
    GitHubFileChange,
    GitHubInstallationToken,
    GitHubPullRequest,
)
from packages.shared.logger import logger


class GitHubIntegrationError(ChangeScopeBaseError):
    """Raised when GitHub API operations fail."""

    status_code = 502
    error_type = "https://changescope.io/errors/github-integration-failure"
    title = "GitHub Integration Failure"


class GitHubRateLimitError(GitHubIntegrationError):
    """Raised when GitHub API rate limit is exceeded and retries are exhausted."""

    status_code = 429
    error_type = "https://changescope.io/errors/github-rate-limit-exceeded"
    title = "GitHub Rate Limit Exceeded"


def sanitize_secret(text: str | None) -> str:
    """Sanitizes sensitive tokens or private keys from error messages or logs."""
    if not text:
        return ""
    # Mask ghs_, ghp_, github_pat_, Bearer tokens
    sanitized = re.sub(r"(gh[srop]_[A-Za-z0-9_]{10,})", r"gh_***[REDACTED]", text)
    sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", r"\1[REDACTED]", sanitized)
    sanitized = re.sub(
        r"-----BEGIN[A-Z\s]+PRIVATE KEY-----.*?-----END[A-Z\s]+PRIVATE KEY-----",
        "[PRIVATE KEY REDACTED]",
        sanitized,
        flags=re.DOTALL,
    )
    return sanitized


class GitHubAppAuth:
    """Manages GitHub App RS256 JWT generation and installation access token caching."""

    def __init__(
        self,
        app_id: str | None = None,
        private_key: str | None = None,
        default_token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.app_id = app_id or settings.GITHUB_APP_ID
        self.private_key = private_key or settings.GITHUB_APP_PRIVATE_KEY
        self.default_token = default_token
        self.base_url = (base_url or settings.GITHUB_API_BASE_URL).rstrip("/")
        # In-memory token cache: {installation_id: (token, expires_at)}
        self._token_cache: dict[int, tuple[str, datetime]] = {}

    def create_app_jwt(self) -> str:
        """Generates an RS256 JWT signed with the GitHub App's private key valid for 9 minutes."""
        if not self.app_id or not self.private_key:
            raise GitHubIntegrationError("GitHub App ID and Private Key are required for App authentication.")

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60s tolerance for clock drift
            "exp": now + 540,  # 9 minutes (GitHub maximum is 10 minutes)
            "iss": str(self.app_id),
        }

        try:
            return jwt.encode(payload, self.private_key, algorithm="RS256")
        except Exception as exc:
            logger.error("github_jwt_generation_failed", error=sanitize_secret(str(exc)))
            raise GitHubIntegrationError("Failed to encode GitHub App RS256 JWT.") from exc

    async def get_installation_token(
        self,
        installation_id: int,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        """Retrieves or refreshes an installation access token, caching until 5 minutes before expiry."""
        now = datetime.now(UTC)
        if installation_id in self._token_cache:
            token, expires_at = self._token_cache[installation_id]
            # 5-minute safety renewal buffer
            if (expires_at - now).total_seconds() > 300:
                return token

        # If App ID & Private Key are missing, fallback to default static token if configured
        if not self.app_id or not self.private_key:
            if self.default_token:
                return self.default_token
            # In local or test environments without credentials, provide mock token
            if settings.ENVIRONMENT in {"local", "test"}:
                logger.debug("github_mock_installation_token_used", installation_id=installation_id)
                mock_token = f"ghs_mock_token_{installation_id}"
                self._token_cache[installation_id] = (mock_token, datetime.max.replace(tzinfo=UTC))
                return mock_token
            raise GitHubIntegrationError(
                f"No credentials available to authenticate GitHub installation '{installation_id}'."
            )

        app_jwt = self.create_app_jwt()
        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        should_close = False
        http = client
        if http is None:
            http = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            resp = await http.post(url, headers=headers)
            if resp.status_code == 404:
                raise GitHubIntegrationError(f"GitHub App installation '{installation_id}' not found.")
            resp.raise_for_status()

            data = resp.json()
            inst_token = GitHubInstallationToken.model_validate(data)
            self._token_cache[installation_id] = (inst_token.token, inst_token.expires_at)
            logger.info("github_installation_token_refreshed", installation_id=installation_id)
            return inst_token.token
        except httpx.HTTPError as exc:
            err_msg = sanitize_secret(str(exc))
            logger.error("github_installation_token_exchange_failed", installation_id=installation_id, error=err_msg)
            raise GitHubIntegrationError(f"Failed to exchange GitHub installation token: {err_msg}") from exc
        finally:
            if should_close:
                await http.aclose()


class GitHubClient:
    """Async client for interacting with GitHub REST APIs (Pull Requests, Checks, Commits)."""

    def __init__(
        self,
        auth: GitHubAppAuth | None = None,
        base_url: str | None = None,
        timeout: float = 15.0,
        max_retries: int | None = None,
    ) -> None:
        self.auth = auth or GitHubAppAuth()
        self.base_url = (base_url or settings.GITHUB_API_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries if max_retries is not None else settings.GITHUB_RATE_LIMIT_RETRIES

    async def _execute_with_retry(
        self,
        method: str,
        path: str,
        installation_id: int | None = None,
        token: str | None = None,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Executes an HTTP request with exponential backoff on HTTP 429 and rate limit 403."""
        url = f"{self.base_url}{path}"
        active_token = token
        if not active_token and installation_id is not None:
            active_token = await self.auth.get_installation_token(installation_id)
        elif not active_token:
            active_token = self.auth.default_token

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if active_token:
            headers["Authorization"] = f"Bearer {active_token}"

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        json=json_body,
                        params=params,
                    )

                # Check for rate limiting
                if resp.status_code == 429 or (
                    resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0"
                ):
                    retry_after = resp.headers.get("Retry-After")
                    sleep_sec = float(retry_after) if retry_after else (2**attempt * 0.5)
                    if attempt < self.max_retries:
                        logger.warning(
                            "github_rate_limited_retrying",
                            status_code=resp.status_code,
                            attempt=attempt + 1,
                            backoff_seconds=sleep_sec,
                        )
                        await asyncio.sleep(sleep_sec)
                        continue
                    raise GitHubRateLimitError(
                        f"GitHub rate limit exceeded after {self.max_retries} retries on {path}."
                    )

                resp.raise_for_status()
                return resp

            except httpx.HTTPStatusError as exc:
                err_msg = sanitize_secret(str(exc))
                logger.error("github_api_http_error", path=path, status=exc.response.status_code, error=err_msg)
                raise GitHubIntegrationError(f"GitHub API returned error: {err_msg}") from exc
            except httpx.RequestError as exc:
                err_msg = sanitize_secret(str(exc))
                if attempt < self.max_retries:
                    sleep_sec = 2**attempt * 0.5
                    logger.warning("github_request_error_retrying", attempt=attempt + 1, error=err_msg)
                    await asyncio.sleep(sleep_sec)
                    continue
                logger.error("github_request_failed_permanently", path=path, error=err_msg)
                raise GitHubIntegrationError(f"GitHub request connection failed: {err_msg}") from exc

        raise GitHubIntegrationError(f"GitHub request exceeded max retries for {path}.")

    async def get_pull_request(
        self,
        repo_owner_name: str,
        pr_number: int,
        installation_id: int | None = None,
    ) -> GitHubPullRequest:
        """Fetches Pull Request metadata."""
        path = f"/repos/{repo_owner_name}/pulls/{pr_number}"
        resp = await self._execute_with_retry("GET", path, installation_id=installation_id)
        return GitHubPullRequest.model_validate(resp.json())

    async def get_pull_request_files(
        self,
        repo_owner_name: str,
        pr_number: int,
        installation_id: int | None = None,
    ) -> list[GitHubFileChange]:
        """Fetches list of changed files with patch hunks from a Pull Request."""
        path = f"/repos/{repo_owner_name}/pulls/{pr_number}/files"
        resp = await self._execute_with_retry("GET", path, installation_id=installation_id, params={"per_page": 100})
        data = resp.json()
        if not isinstance(data, list):
            return []
        return [GitHubFileChange.model_validate(item) for item in data]

    async def get_commit_diff(
        self,
        repo_owner_name: str,
        base_sha: str,
        head_sha: str,
        installation_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetches commit comparison diff between base and head."""
        path = f"/repos/{repo_owner_name}/compare/{base_sha}...{head_sha}"
        resp = await self._execute_with_retry("GET", path, installation_id=installation_id)
        data = resp.json()
        return data if isinstance(data, dict) else {}

    async def create_check_run(
        self,
        repo_owner_name: str,
        check_run: GitHubCheckRunCreate,
        installation_id: int | None = None,
    ) -> GitHubCheckRunResponse:
        """Publishes a Check Run with summary, markdown report, and inline annotations."""
        path = f"/repos/{repo_owner_name}/check-runs"
        payload = check_run.model_dump(exclude_none=True, mode="json")

        # GitHub enforces maximum 50 annotations per single check run call
        if "output" in payload and "annotations" in payload["output"]:
            payload["output"]["annotations"] = payload["output"]["annotations"][:50]

        resp = await self._execute_with_retry("POST", path, installation_id=installation_id, json_body=payload)
        return GitHubCheckRunResponse.model_validate(resp.json())

    async def update_check_run(
        self,
        repo_owner_name: str,
        check_run_id: int,
        check_run: GitHubCheckRunCreate,
        installation_id: int | None = None,
    ) -> GitHubCheckRunResponse:
        """Updates an existing Check Run."""
        path = f"/repos/{repo_owner_name}/check-runs/{check_run_id}"
        payload = check_run.model_dump(exclude_none=True, mode="json")
        if "output" in payload and "annotations" in payload["output"]:
            payload["output"]["annotations"] = payload["output"]["annotations"][:50]

        resp = await self._execute_with_retry("PATCH", path, installation_id=installation_id, json_body=payload)
        return GitHubCheckRunResponse.model_validate(resp.json())

    async def post_pr_comment(
        self,
        repo_owner_name: str,
        pr_number: int,
        body: str,
        installation_id: int | None = None,
    ) -> dict[str, Any]:
        """Publishes a Markdown analysis report as an Issue/PR comment."""
        path = f"/repos/{repo_owner_name}/issues/{pr_number}/comments"
        resp = await self._execute_with_retry(
            "POST",
            path,
            installation_id=installation_id,
            json_body={"body": body},
        )
        data = resp.json()
        return data if isinstance(data, dict) else {}
