"""Candidate Semantic Interpretation Engine (AI / Heuristic Candidate Proposer)."""

from packages.contracts.models import (
    ChangeCategory,
    ContractFinding,
    FindingSeverity,
)


class CandidateSemanticInterpreter:
    """Proposes candidate semantic interpretations of documentation diffs without replacing deterministic validation."""

    @classmethod
    def interpret_description_diff(
        cls,
        field_name: str,
        base_desc: str,
        head_desc: str,
        pointer: str = "",
        file_path: str = "contract.yaml",
    ) -> list[ContractFinding]:
        """Analyzes unstructured natural language description changes and returns candidate interpretation findings."""
        findings: list[ContractFinding] = []

        if not base_desc or not head_desc or base_desc.strip() == head_desc.strip():
            return []

        b_lower = base_desc.lower()
        h_lower = head_desc.lower()

        # Heuristic 1: Authorization / Access Control Semantic Shift
        auth_words = {"admin", "internal", "public", "confidential", "restricted", "pii", "authenticated"}
        b_auth = {w for w in auth_words if w in b_lower}
        h_auth = {w for w in auth_words if w in h_lower}
        if b_auth != h_auth and (b_auth or h_auth):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="ACCESS_SCOPE_SEMANTIC_SHIFT",
                    severity=FindingSeverity.WARNING,
                    confidence=0.70,
                    before_state={"description": base_desc, "access_scope": list(b_auth)},
                    after_state={"description": head_desc, "access_scope": list(h_auth)},
                    affected_entities=[pointer or field_name],
                    supporting_evidence={
                        "field": field_name,
                        "base_description": base_desc,
                        "head_description": head_desc,
                        "scope_shift": {"from": list(b_auth), "to": list(h_auth)},
                    },
                    uncertainty_explanation="Candidate semantic interpretation generated via NLP heuristics. Documentation indicates changed visibility or permission tier.",
                    recommended_verification="Conduct human review to verify whether access controls or tenant scoping rules changed for this field.",
                    json_pointer=pointer,
                    file_path=file_path,
                    is_ai_inferred=True,
                )
            )

        # Heuristic 2: Deprecation / Future Sunset Notice
        dep_words = {"deprecated", "sunset", "phase out", "will be removed", "do not use"}
        if not any(w in b_lower for w in dep_words) and any(w in h_lower for w in dep_words):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="FIELD_SEMANTIC_DEPRECATION",
                    severity=FindingSeverity.WARNING,
                    confidence=0.75,
                    before_state={"description": base_desc, "is_deprecated": False},
                    after_state={"description": head_desc, "is_deprecated": True},
                    affected_entities=[pointer or field_name],
                    supporting_evidence={"base_description": base_desc, "head_description": head_desc},
                    uncertainty_explanation="Natural language description signals intention to deprecate field in future releases.",
                    recommended_verification="Check deprecation timeline and notify downstream consumer service owners.",
                    json_pointer=pointer,
                    file_path=file_path,
                    is_ai_inferred=True,
                )
            )

        return findings
