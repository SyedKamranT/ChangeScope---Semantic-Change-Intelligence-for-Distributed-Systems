"""Configuration and Code Ownership Candidate Extractor.

Extracts file ownership rules from CODEOWNERS and configuration dependencies
from pyproject.toml, package.json, requirements.txt, and docker-compose.
"""

import json
import re

from packages.shared.ingestion.models import ConfigDependency, OwnershipRule


class ConfigAndOwnershipExtractor:
    """Parses repository configuration files and ownership attribution manifests."""

    @classmethod
    def extract_codeowners(cls, content: str, file_path: str) -> list[OwnershipRule]:
        """Parses GitHub / GitLab style CODEOWNERS files."""
        rules: list[OwnershipRule] = []
        for line_idx, line in enumerate(content.splitlines(), start=1):
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue

            parts = clean.split()
            if len(parts) >= 2:
                pattern = parts[0]
                owners = parts[1:]
                rules.append(
                    OwnershipRule(
                        pattern=pattern,
                        owners=owners,
                        file_path=file_path,
                        line_number=line_idx,
                    )
                )
        return rules

    @classmethod
    def extract_config(cls, content: str, file_path: str) -> ConfigDependency | None:
        """Parses package manifests and configuration declarations."""
        clean_path = file_path.replace("\\", "/").lower()
        fname = clean_path.split("/")[-1]

        # 1. Node.js package.json
        if fname == "package.json":
            try:
                data = json.loads(content)
                deps: dict[str, str] = {}
                deps.update(data.get("dependencies", {}))
                deps.update(data.get("devDependencies", {}))
                return ConfigDependency(
                    config_type="package_json",
                    file_path=file_path,
                    dependencies=deps,
                )
            except Exception:
                return None

        # 2. Python requirements.txt
        if fname.endswith("requirements.txt") or fname == "requirements.txt":
            deps = {}
            for line in content.splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#"):
                    match = re.match(r"^([a-zA-Z0-9_-]+)(.*)$", clean)
                    if match:
                        deps[match.group(1)] = match.group(2).strip()
            return ConfigDependency(
                config_type="requirements",
                file_path=file_path,
                dependencies=deps,
            )

        # 3. Environment Variable Examples
        if fname in {".env.example", ".env.sample", ".env.template"}:
            keys = []
            for line in content.splitlines():
                clean = line.strip()
                if clean and not clean.startswith("#") and "=" in clean:
                    k = clean.split("=", 1)[0].strip()
                    if k:
                        keys.append(k)
            return ConfigDependency(
                config_type="env_example",
                file_path=file_path,
                env_keys=keys,
            )

        return None
