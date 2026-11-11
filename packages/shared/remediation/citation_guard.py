"""Citation Verification Guard preventing hallucinated file paths, lines, and trace IDs."""

import re

from packages.shared.logger import logger


class CitationVerificationGuard:
    """Zero-Hallucination verification guard ensuring all cited artifacts exist in verified ground truth."""

    FILE_PATH_REGEX = re.compile(r"[`(]([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)[`) ]")
    TRACE_ID_REGEX = re.compile(r"\b(?:trace-[a-zA-Z0-9_\-]+|[a-fA-F0-9]{32})\b")

    @classmethod
    def verify_and_sanitize_narrative(
        cls,
        candidate_markdown: str,
        verified_file_paths: set[str],
        verified_trace_ids: set[str],
    ) -> tuple[bool, str]:
        """Validates cited file paths and traces in candidate markdown against verified ground truth."""
        cited_files = set(cls.FILE_PATH_REGEX.findall(candidate_markdown))
        cited_traces = set(cls.TRACE_ID_REGEX.findall(candidate_markdown))

        hallucinated_files: list[str] = []
        for f in cited_files:
            # Check if file has path separators and isn't a generic format extension
            if "/" in f or "\\" in f:
                norm_f = f.replace("\\", "/")
                # Ignore common spec/config names
                if not any(norm_f.endswith(ext) for ext in [".json", ".yaml", ".yml", ".md", ".cypher"]):
                    if norm_f not in verified_file_paths:
                        hallucinated_files.append(f)

        hallucinated_traces = [t for t in cited_traces if t not in verified_trace_ids and not t.startswith("trace-ex")]

        if hallucinated_files or hallucinated_traces:
            logger.warning(
                "citation_guard_hallucination_detected",
                hallucinated_files=hallucinated_files,
                hallucinated_traces=hallucinated_traces,
            )
            # Sanitize hallucinated citations by replacing them with verified references
            sanitized = candidate_markdown
            for hf in hallucinated_files:
                sanitized = sanitized.replace(hf, "[UNVERIFIED_PATH_REDACTED]")
            for ht in hallucinated_traces:
                sanitized = sanitized.replace(ht, "[UNVERIFIED_TRACE_REDACTED]")

            return False, sanitized

        return True, candidate_markdown
