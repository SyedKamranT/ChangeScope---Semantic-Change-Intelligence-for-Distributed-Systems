"""Deterministic Semantic Change Intelligence Engine."""

import re
from typing import Any

from packages.contracts.models import (
    ChangeCategory,
    ContractFinding,
    FindingSeverity,
)


class SemanticDiffer:
    """Detects subtle semantic changes across API schemas using deterministic rules."""

    @classmethod
    def analyze_schema_semantics(
        cls,
        base_schema: dict[str, Any] | None,
        head_schema: dict[str, Any] | None,
        pointer_prefix: str = "",
        file_path: str = "contract.yaml",
        line_range: tuple[int, int] = (1, 1),
    ) -> list[ContractFinding]:
        """Deeply inspects descriptions, metadata, units, and annotations for semantic shifts."""
        findings: list[ContractFinding] = []

        if not base_schema or not head_schema:
            return []

        # 1. Direct schema-level semantic checks
        findings.extend(cls._check_field_semantics(base_schema, head_schema, pointer_prefix, file_path, line_range))

        # 2. Recurse into object properties
        base_props = base_schema.get("properties", {}) if isinstance(base_schema.get("properties"), dict) else {}
        head_props = head_schema.get("properties", {}) if isinstance(head_schema.get("properties"), dict) else {}

        # 2a. Check renamed properties for semantic collisions (e.g. customer_id -> account_id)
        findings.extend(
            cls._check_identifier_semantic_shift(base_props, head_props, pointer_prefix, file_path, line_range)
        )

        # 2b. Check common properties for description and unit semantic shifts
        common_keys = set(base_props.keys()) & set(head_props.keys())
        for key in sorted(common_keys):
            b_val = base_props[key]
            h_val = head_props[key]
            if isinstance(b_val, dict) and isinstance(h_val, dict):
                sub_ptr = f"{pointer_prefix}/properties/{key}"
                findings.extend(cls._check_field_semantics(b_val, h_val, sub_ptr, file_path, line_range))
                # Recurse further into child objects
                findings.extend(
                    cls.analyze_schema_semantics(
                        b_val, h_val, pointer_prefix=sub_ptr, file_path=file_path, line_range=line_range
                    )
                )

        return findings

    @classmethod
    def _check_field_semantics(
        cls,
        base_field: dict[str, Any],
        head_field: dict[str, Any],
        pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        base_desc = str(base_field.get("description", "")).lower()
        head_desc = str(head_field.get("description", "")).lower()

        base_unit = str(base_field.get("x-unit") or base_field.get("unit") or "").lower()
        head_unit = str(head_field.get("x-unit") or head_field.get("unit") or "").lower()

        # 1. Currency Unit Changes: Cents vs Dollars
        cents_keywords = {"cents", "cent", "usd cents", "minor unit", "sub-unit"}
        dollars_keywords = {"dollars", "dollar", "usd", "eur", "major unit"}

        base_is_cents = any(w in base_desc for w in cents_keywords) or base_unit in {"cents", "cent"}
        head_is_dollars = any(w in head_desc for w in dollars_keywords) or head_unit in {"usd", "dollar", "dollars"}

        base_is_dollars = any(w in base_desc for w in dollars_keywords) or base_unit in {"usd", "dollar", "dollars"}
        head_is_cents = any(w in head_desc for w in cents_keywords) or head_unit in {"cents", "cent"}

        if (base_is_cents and head_is_dollars) or (base_is_dollars and head_is_cents):
            from_unit = "cents" if base_is_cents else "dollars"
            to_unit = "dollars" if head_is_dollars else "cents"
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="CURRENCY_UNIT_CHANGE",
                    severity=FindingSeverity.BLOCKING,
                    confidence=0.90,
                    before_state={"unit": from_unit, "description": base_field.get("description")},
                    after_state={"unit": to_unit, "description": head_field.get("description")},
                    affected_entities=[pointer],
                    supporting_evidence={
                        "from_unit": from_unit,
                        "to_unit": to_unit,
                        "base_description": base_field.get("description"),
                        "head_description": head_field.get("description"),
                    },
                    uncertainty_explanation="Detected shift in currency denomination (cents vs dollars) without primitive type modification. A 100x monetary valuation discrepancy will occur if unhandled.",
                    recommended_verification=f"Verify whether downstream services expect values in {from_unit} or {to_unit}. Update API documentation or versioning.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 2. Time Unit Changes: Seconds vs Milliseconds
        sec_keywords = {"seconds", "secs", "in seconds", "second"}
        ms_keywords = {"milliseconds", "msecs", "millis", "in milliseconds", "in ms"}

        base_is_sec = any(w in base_desc for w in sec_keywords) or base_unit in {"s", "sec", "seconds"}
        head_is_ms = any(w in head_desc for w in ms_keywords) or head_unit in {"ms", "msec", "milliseconds"}

        base_is_ms = any(w in base_desc for w in ms_keywords) or base_unit in {"ms", "msec", "milliseconds"}
        head_is_sec = any(w in head_desc for w in sec_keywords) or head_unit in {"s", "sec", "seconds"}

        if (base_is_sec and head_is_ms) or (base_is_ms and head_is_sec):
            from_time = "seconds" if base_is_sec else "milliseconds"
            to_time = "milliseconds" if head_is_ms else "seconds"
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="TIME_UNIT_CHANGE",
                    severity=FindingSeverity.BLOCKING,
                    confidence=0.85,
                    before_state={"time_unit": from_time, "description": base_field.get("description")},
                    after_state={"time_unit": to_time, "description": head_field.get("description")},
                    affected_entities=[pointer],
                    supporting_evidence={
                        "from_unit": from_time,
                        "to_unit": to_time,
                        "base_description": base_field.get("description"),
                        "head_description": head_field.get("description"),
                    },
                    uncertainty_explanation="Detected time measurement unit shift (seconds vs milliseconds) with identical primitive type. Causes 1000x calculation discrepancy.",
                    recommended_verification=f"Verify downstream service timeout and duration expectations ({from_time} vs {to_time}).",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 3. UTC vs Local Timestamp Shifts
        utc_keywords = {"utc", "gmt", "zulu", "iso-8601 utc", "coordinated universal time"}
        local_keywords = {"local time", "local timestamp", "server local", "without timezone", "server time"}

        base_is_utc = any(w in base_desc for w in utc_keywords) or base_field.get("x-timezone") == "UTC"
        head_is_local = any(w in head_desc for w in local_keywords) or head_field.get("x-timezone") == "LOCAL"

        base_is_local = any(w in base_desc for w in local_keywords) or base_field.get("x-timezone") == "LOCAL"
        head_is_utc = any(w in head_desc for w in utc_keywords) or head_field.get("x-timezone") == "UTC"

        if (base_is_utc and head_is_local) or (base_is_local and head_is_utc):
            from_tz = "UTC" if base_is_utc else "LOCAL"
            to_tz = "LOCAL" if head_is_local else "UTC"
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="TIMESTAMP_TIMEZONE_SHIFT",
                    severity=FindingSeverity.WARNING,
                    confidence=0.80,
                    before_state={"timezone": from_tz, "description": base_field.get("description")},
                    after_state={"timezone": to_tz, "description": head_field.get("description")},
                    affected_entities=[pointer],
                    supporting_evidence={
                        "from_timezone": from_tz,
                        "to_timezone": to_tz,
                        "base_description": base_field.get("description"),
                        "head_description": head_field.get("description"),
                    },
                    uncertainty_explanation="Detected timezone interpretation shift from UTC to local time. Distributed services across timezones will observe discrepancies up to 24 hours.",
                    recommended_verification=f"Timestamp interpretation altered from {from_tz} to {to_tz}. Standardize on UTC ISO-8601 timestamps.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 4. Percentage vs Absolute Values
        ratio_keywords = {"ratio", "0.0 to 1.0", "decimal fraction", "fraction (0-1)", "0 to 1"}
        pct_keywords = {"percentage points", "0 to 100", "0-100", "percent (0-100)", "basis points"}

        base_is_ratio = any(w in base_desc for w in ratio_keywords)
        head_is_pct = any(w in head_desc for w in pct_keywords)

        base_is_pct = any(w in base_desc for w in pct_keywords)
        head_is_ratio = any(w in head_desc for w in ratio_keywords)

        if (base_is_ratio and head_is_pct) or (base_is_pct and head_is_ratio):
            from_format = "ratio (0.0-1.0)" if base_is_ratio else "percentage points (0-100)"
            to_format = "percentage points (0-100)" if head_is_pct else "ratio (0.0-1.0)"
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="PERCENTAGE_VS_ABSOLUTE",
                    severity=FindingSeverity.BLOCKING,
                    confidence=0.85,
                    before_state={"scale": from_format, "description": base_field.get("description")},
                    after_state={"scale": to_format, "description": head_field.get("description")},
                    affected_entities=[pointer],
                    supporting_evidence={
                        "from_scale": from_format,
                        "to_scale": to_format,
                        "base_description": base_field.get("description"),
                        "head_description": head_field.get("description"),
                    },
                    uncertainty_explanation="Detected scale interpretation shift between decimal ratio (0.0-1.0) and percentage points (0-100). Causes a 100x numerical calculation error.",
                    recommended_verification=f"Verify calculation formula scaling: shifted from {from_format} to {to_format}.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 5. Status Definition Changes
        # Enum values are structurally unchanged, but description defines a materially different lifecycle phase
        base_enum = base_field.get("enum")
        head_enum = head_field.get("enum")
        if base_enum and head_enum and base_enum == head_enum:
            if base_desc and head_desc and base_desc != head_desc:
                # Check for significant semantic drift keywords in descriptions
                lifecycle_drift_words = {
                    "awaiting",
                    "captured",
                    "authorized",
                    "dispatched",
                    "refunded",
                    "settled",
                    "verified",
                }
                b_words = {w for w in re.findall(r"\w+", base_desc) if w in lifecycle_drift_words}
                h_words = {w for w in re.findall(r"\w+", head_desc) if w in lifecycle_drift_words}
                if b_words != h_words and (b_words or h_words):
                    findings.append(
                        ContractFinding(
                            change_category=ChangeCategory.SEMANTIC,
                            change_type="STATUS_DEFINITION_CHANGE",
                            severity=FindingSeverity.WARNING,
                            confidence=0.75,
                            before_state={"enum": base_enum, "description": base_field.get("description")},
                            after_state={"enum": head_enum, "description": head_field.get("description")},
                            affected_entities=[pointer],
                            supporting_evidence={
                                "enum": base_enum,
                                "old_description": base_field.get("description"),
                                "new_description": head_field.get("description"),
                            },
                            uncertainty_explanation="Enum values remain identical, but description documentation alters the state lifecycle meaning.",
                            recommended_verification="Review status lifecycle state machine: business meaning of status values modified.",
                            json_pointer=pointer,
                            file_path=file_path,
                            start_line=line_range[0],
                            end_line=line_range[1],
                        )
                    )

        # 6. Polysemy & Bounded Context Meaning Shifts
        base_concept = base_field.get("x-business-concept")
        head_concept = head_field.get("x-business-concept")
        if base_concept and head_concept and base_concept != head_concept:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="POLYSEMY_MEANING_SHIFT",
                    severity=FindingSeverity.WARNING,
                    confidence=0.80,
                    before_state={"concept": base_concept},
                    after_state={"concept": head_concept},
                    affected_entities=[pointer],
                    supporting_evidence={
                        "old_concept": base_concept,
                        "new_concept": head_concept,
                    },
                    uncertainty_explanation="Property mapped to distinct ontology concept across bounded contexts.",
                    recommended_verification=f"Concept shifted from '{base_concept}' to '{head_concept}'. Verify consumer domain context.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        return findings

    @classmethod
    def _check_identifier_semantic_shift(
        cls,
        base_props: dict[str, Any],
        head_props: dict[str, Any],
        pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        """Detects substitution of customer identifiers with account identifiers or vice versa."""
        findings: list[ContractFinding] = []

        customer_id_keys = {"customer_id", "customerid", "customer_uuid", "cust_id"}
        account_id_keys = {"account_id", "accountid", "billing_account_id", "acct_id"}

        base_keys = set(base_props.keys())
        head_keys = set(head_props.keys())

        has_base_customer = any(k.lower() in customer_id_keys for k in base_keys)
        has_head_account = any(k.lower() in account_id_keys for k in head_keys)

        has_base_account = any(k.lower() in account_id_keys for k in base_keys)
        has_head_customer = any(k.lower() in customer_id_keys for k in head_keys)

        if has_base_customer and not has_head_customer and has_head_account and not has_base_account:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="IDENTIFIER_SEMANTIC_COLLISION",
                    severity=FindingSeverity.BLOCKING,
                    confidence=0.85,
                    before_state={"identifier_entity": "Customer"},
                    after_state={"identifier_entity": "Account"},
                    affected_entities=[f"{pointer}/properties"],
                    supporting_evidence={"base_fields": sorted(base_keys), "head_fields": sorted(head_keys)},
                    uncertainty_explanation="Customer and Account represent distinct entities in enterprise ontology: a Customer may have multiple Accounts. Substituting one identifier for the other can cause authorization bypass or incorrect record partitioning.",
                    recommended_verification="Verify whether downstream services require customer identity or billing account identity.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        elif has_base_account and not has_head_account and has_head_customer and not has_base_customer:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.SEMANTIC,
                    change_type="IDENTIFIER_SEMANTIC_COLLISION",
                    severity=FindingSeverity.BLOCKING,
                    confidence=0.85,
                    before_state={"identifier_entity": "Account"},
                    after_state={"identifier_entity": "Customer"},
                    affected_entities=[f"{pointer}/properties"],
                    supporting_evidence={"base_fields": sorted(base_keys), "head_fields": sorted(head_keys)},
                    uncertainty_explanation="Account substituted with Customer identifier.",
                    recommended_verification="Verify identity scoping: Account replaced with Customer.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        return findings
