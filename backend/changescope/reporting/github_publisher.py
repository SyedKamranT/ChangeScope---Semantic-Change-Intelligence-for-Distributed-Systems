"""GitHub Checks API and PR Markdown Comment Publisher."""

from typing import Any

import httpx
from changescope.common.logger import logger
from changescope.config import settings
from changescope.reasoning.models import RuleViolation


class GitHubPublisher:
    """Publishes ChangeScope scan findings to GitHub via Checks API and PR comments."""

    @classmethod
    async def publish_check_run(
        cls,
        repo_owner_name: str,
        head_sha: str,
        risk_score: int,
        risk_level: str,
        violations: list[RuleViolation],
        markdown_report: str,
        github_token: str | None = None,
    ) -> dict[str, Any]:
        """Publishes a Check Run with inline annotations on lines triggering violations."""
        conclusion = "failure" if risk_level in {"HIGH", "CRITICAL"} else "success"
        title = f"ChangeScope: Risk {risk_score}/100 ({risk_level})"

        annotations = []
        for v in violations:
            level = "failure" if v.severity == "BLOCKING" else "warning"
            annotations.append(
                {
                    "path": v.file_path,
                    "start_line": max(1, v.start_line),
                    "end_line": max(1, v.end_line),
                    "annotation_level": level,
                    "title": f"[{v.severity}] {v.rule_code}",
                    "message": v.message,
                }
            )

        # GitHub Limits annotations to 50 per request
        payload = {
            "name": "ChangeScope Semantic Intelligence",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": title,
                "summary": f"Identified {len(violations)} semantic violations with risk score {risk_score}/100.",
                "text": markdown_report,
                "annotations": annotations[:50],
            },
        }

        if not github_token or settings.ENVIRONMENT in {"local", "test"}:
            logger.info(
                "Offline/Mock Mode: Simulated GitHub Check Run publication",
                repo=repo_owner_name,
                head_sha=head_sha,
                conclusion=conclusion,
                annotations_count=len(annotations),
            )
            return {"status": "simulated", "conclusion": conclusion, "annotations_published": len(annotations)}

        # Live GitHub REST API request
        url = f"https://api.github.com/repos/{repo_owner_name}/check-runs"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()
            logger.info("Published live GitHub Check Run", repo=repo_owner_name, status_code=res.status_code)
            return res.json()
