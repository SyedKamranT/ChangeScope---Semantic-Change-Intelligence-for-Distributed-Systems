"""GitHub webhook event handler with HMAC signature verification, deduplication, and scan scheduling."""

import json
import time
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.config import settings
from packages.shared.database import async_session_factory
from packages.shared.errors import ChangeScopeBaseError
from packages.shared.ingestion.safety import RepoSafetyGuard
from packages.shared.integrations.github.client import sanitize_secret
from packages.shared.integrations.github.models import GitHubWebhookResult
from packages.shared.logger import logger
from packages.shared.models import OutboxEvent, Repository, ScanRun
from packages.shared.security.webhooks import WebhookVerifier


class GitHubWebhookError(ChangeScopeBaseError):
    """Raised when an incoming webhook is invalid, untrusted, or unauthorized."""

    status_code = 400
    error_type = "https://changescope.io/errors/github-webhook-error"
    title = "GitHub Webhook Error"


class GitHubWebhookHandler:
    """Processes incoming GitHub webhooks securely with signature validation and deduplication."""

    # In-memory delivery cache: {delivery_id: timestamp_seconds}
    _seen_deliveries: dict[str, float] = {}
    _DELIVERY_TTL_SECONDS = 3600  # 1 hour delivery deduplication window

    @classmethod
    def _is_duplicate_delivery(cls, delivery_id: str) -> bool:
        """Checks if a delivery ID has been seen within the TTL window and purges expired entries."""
        now = time.time()
        # Purge expired
        expired = [d for d, ts in cls._seen_deliveries.items() if now - ts > cls._DELIVERY_TTL_SECONDS]
        for d in expired:
            cls._seen_deliveries.pop(d, None)

        if delivery_id in cls._seen_deliveries:
            return True

        cls._seen_deliveries[delivery_id] = now
        return False

    @classmethod
    def reset_delivery_cache_for_testing(cls) -> None:
        """Helper for unit and integration test isolation."""
        cls._seen_deliveries.clear()

    @classmethod
    async def handle_webhook(
        cls,
        payload_bytes: bytes,
        signature_header: str | None,
        event_type: str | None,
        delivery_id: str | None,
        session: AsyncSession | None = None,
        schedule_worker_task: bool = True,
    ) -> GitHubWebhookResult:
        """Verifies signature, checks idempotency, parses payload, and orchestrates actions."""
        # 1. Cryptographic HMAC-SHA256 signature verification
        WebhookVerifier.verify_github_signature(
            payload_bytes=payload_bytes,
            signature_header=signature_header,
            secret=settings.GITHUB_WEBHOOK_SECRET,
        )

        # 2. Webhook delivery deduplication
        if delivery_id and cls._is_duplicate_delivery(delivery_id):
            logger.info("github_webhook_duplicate_delivery_ignored", delivery_id=delivery_id, webhook_event=event_type)
            return GitHubWebhookResult(
                status="DUPLICATE_IGNORED",
                delivery_id=delivery_id,
                event_type=event_type,
                message=f"Delivery '{delivery_id}' has already been processed.",
            )

        # 3. Parse JSON payload
        try:
            payload: dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
        except Exception as exc:
            raise GitHubWebhookError(f"Failed to parse GitHub webhook JSON body: {exc}") from exc

        logger.info(
            "github_webhook_verified_and_received",
            webhook_event=event_type,
            delivery_id=delivery_id,
            action=payload.get("action"),
        )

        # 4. Handle event types
        if event_type == "ping":
            return GitHubWebhookResult(
                status="PONG",
                delivery_id=delivery_id,
                event_type=event_type,
                message=payload.get("zen", "GitHub ping received"),
            )

        if event_type in {"installation", "installation_repositories"}:
            action = payload.get("action", "unknown")
            inst_id = payload.get("installation", {}).get("id")
            logger.info("github_app_installation_event", action=action, installation_id=inst_id)
            return GitHubWebhookResult(
                status="ACCEPTED",
                delivery_id=delivery_id,
                event_type=event_type,
                action=action,
                message=f"Installation event '{action}' processed successfully.",
            )

        if event_type == "pull_request":
            return await cls._handle_pull_request_event(
                payload=payload,
                delivery_id=delivery_id,
                session=session,
                schedule_worker_task=schedule_worker_task,
            )

        if event_type == "push":
            return await cls._handle_push_event(
                payload=payload,
                delivery_id=delivery_id,
                session=session,
            )

        # Default for unsupported or unhandled GitHub events
        return GitHubWebhookResult(
            status="EVENT_IGNORED",
            delivery_id=delivery_id,
            event_type=event_type,
            action=payload.get("action"),
            message=f"Event '{event_type}' acknowledged but requires no scan action.",
        )

    @classmethod
    async def _handle_pull_request_event(
        cls,
        payload: dict[str, Any],
        delivery_id: str | None,
        session: AsyncSession | None = None,
        schedule_worker_task: bool = True,
    ) -> GitHubWebhookResult:
        """Processes Pull Request webhook events (opened, synchronize, reopened)."""
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})

        repo_full_name = repo_data.get("full_name", "")
        clone_url = repo_data.get("clone_url", "")
        pr_number = pr_data.get("number") or payload.get("number", 0)

        # We only trigger scans on PR opened, synchronize (new commits pushed), or reopened
        if action not in {"opened", "synchronize", "reopened"}:
            return GitHubWebhookResult(
                status="EVENT_IGNORED",
                delivery_id=delivery_id,
                event_type="pull_request",
                action=action,
                repository=repo_full_name,
                message=f"Pull request action '{action}' does not require scan execution.",
            )

        # Handle minimal payload without repository context (e.g. basic ping/heartbeat PR webhooks)
        if not repo_full_name:
            return GitHubWebhookResult(
                status="ACCEPTED",
                delivery_id=delivery_id,
                event_type="pull_request",
                action=action,
                message="Pull request payload accepted without repository metadata.",
            )

        base_sha = pr_data.get("base", {}).get("sha") or ("0" * 40)
        head_sha = pr_data.get("head", {}).get("sha") or ("0" * 40)

        # Validate SHAs for security
        try:
            clean_base_sha = RepoSafetyGuard.validate_commit_sha(base_sha)
            clean_head_sha = RepoSafetyGuard.validate_commit_sha(head_sha)
        except Exception as exc:
            raise GitHubWebhookError(f"Invalid commit SHA in PR payload: {exc}") from exc

        # Repository access restriction: Check if repository exists in ChangeScope
        async def _resolve_repo(db: AsyncSession) -> tuple[Repository | None, str | None]:
            # Match by clone_url or full_name
            repo_stmt = select(Repository).where(
                or_(
                    Repository.clone_url == clone_url,
                    Repository.name == repo_full_name,
                    Repository.name == repo_data.get("name"),
                ),
                Repository.status == "ACTIVE",
            )
            res = await db.execute(repo_stmt)
            found_repo = res.scalars().first()
            return found_repo, getattr(found_repo, "tenant_id", None)

        if session is not None:
            repo, tenant_id = await _resolve_repo(session)
        else:
            async with async_session_factory() as db:
                repo, tenant_id = await _resolve_repo(db)

        if not repo:
            logger.warning(
                "github_webhook_unauthorized_repository",
                repo_full_name=repo_full_name,
                clone_url=sanitize_secret(clone_url),
            )
            return GitHubWebhookResult(
                status="UNAUTHORIZED_REPOSITORY",
                delivery_id=delivery_id,
                event_type="pull_request",
                action=action,
                repository=repo_full_name,
                message=f"Repository '{repo_full_name}' is not registered or active in ChangeScope.",
            )

        # Create ScanRun record
        scan_id = str(uuid.uuid4())
        scan_run = ScanRun(
            id=scan_id,
            tenant_id=tenant_id or repo.tenant_id,
            repository_id=repo.id,
            base_sha=clean_base_sha,
            head_sha=clean_head_sha,
            status="QUEUED",
        )

        installation_id = payload.get("installation", {}).get("id")

        outbox_event = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id or repo.tenant_id,
            aggregate_type="ScanRun",
            aggregate_id=scan_id,
            event_type="scan.github_pr_enqueued",
            payload={
                "scan_id": scan_id,
                "repo_id": repo.id,
                "base_sha": clean_base_sha,
                "head_sha": clean_head_sha,
                "pr_number": pr_number,
                "installation_id": installation_id,
            },
        )

        if session is not None:
            session.add(scan_run)
            session.add(outbox_event)
            await session.commit()
        else:
            async with async_session_factory() as db:
                db.add(scan_run)
                db.add(outbox_event)
                await db.commit()

        logger.info(
            "github_pr_scan_queued",
            scan_id=scan_id,
            repo_id=repo.id,
            pr_number=pr_number,
            head_sha=clean_head_sha,
        )

        # Dispatch background Celery task if in staging or production
        if schedule_worker_task and settings.ENVIRONMENT in {"staging", "production"}:
            try:
                from apps.worker.tasks import process_github_pr_task

                process_github_pr_task.delay(
                    scan_id=scan_id,
                    repo_id=repo.id,
                    base_sha=clean_base_sha,
                    head_sha=clean_head_sha,
                    pr_number=pr_number,
                    installation_id=installation_id,
                )
            except Exception as exc:
                logger.warning(
                    "github_worker_dispatch_fallback",
                    error=str(exc),
                    scan_id=scan_id,
                )

        return GitHubWebhookResult(
            status="ACCEPTED",
            delivery_id=delivery_id,
            event_type="pull_request",
            action=action,
            repository=repo_full_name,
            scan_id=scan_id,
            message="Pull Request analysis scheduled successfully.",
        )

    @classmethod
    async def _handle_push_event(
        cls,
        payload: dict[str, Any],
        delivery_id: str | None,
        session: AsyncSession | None = None,
    ) -> GitHubWebhookResult:
        """Processes Push webhook events."""
        repo_data = payload.get("repository", {})
        repo_full_name = repo_data.get("full_name", "")
        clone_url = repo_data.get("clone_url", "")
        after_sha = payload.get("after", "")

        # If it's a branch deletion, after_sha is all zeroes
        if after_sha == "0" * 40:
            return GitHubWebhookResult(
                status="EVENT_IGNORED",
                delivery_id=delivery_id,
                event_type="push",
                repository=repo_full_name,
                message="Branch deletion event ignored.",
            )

        async def _check_repo(db: AsyncSession) -> Repository | None:
            stmt = select(Repository).where(
                or_(
                    Repository.clone_url == clone_url,
                    Repository.name == repo_full_name,
                    Repository.name == repo_data.get("name"),
                ),
                Repository.status == "ACTIVE",
            )
            res = await db.execute(stmt)
            return res.scalars().first()

        if session is not None:
            repo = await _check_repo(session)
        else:
            async with async_session_factory() as db:
                repo = await _check_repo(db)

        if not repo:
            return GitHubWebhookResult(
                status="UNAUTHORIZED_REPOSITORY",
                delivery_id=delivery_id,
                event_type="push",
                repository=repo_full_name,
                message=f"Repository '{repo_full_name}' is not registered in ChangeScope.",
            )

        return GitHubWebhookResult(
            status="ACCEPTED",
            delivery_id=delivery_id,
            event_type="push",
            repository=repo_full_name,
            message=f"Push event recorded for commit {after_sha[:7] if len(after_sha) >= 7 else after_sha}.",
        )
