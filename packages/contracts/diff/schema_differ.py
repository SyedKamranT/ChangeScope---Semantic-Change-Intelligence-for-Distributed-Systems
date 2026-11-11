"""Deep JSON Schema Differ for Structural Contract Intelligence."""

from typing import Any

from packages.contracts.models import (
    ChangeCategory,
    ConsumerContractProfile,
    ContractFinding,
    FindingSeverity,
)


class SchemaDiffer:
    """Recursively evaluates structural differences between base and head JSON schemas."""

    @classmethod
    def diff_schemas(
        cls,
        base_schema: dict[str, Any] | None,
        head_schema: dict[str, Any] | None,
        pointer_prefix: str = "",
        consumers: list[ConsumerContractProfile] | None = None,
        is_response: bool = False,
        file_path: str = "contract.yaml",
        line_range: tuple[int, int] = (1, 1),
    ) -> list[ContractFinding]:
        """Compares two JSON Schemas and returns all structural findings."""
        findings: list[ContractFinding] = []
        active_consumers = consumers or []

        # Handle null / empty schemas
        if not base_schema and not head_schema:
            return []
        if not base_schema and head_schema:
            # Entire schema added
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="SCHEMA_ADDED",
                    severity=FindingSeverity.INFO,
                    confidence=1.0,
                    before_state={},
                    after_state=head_schema,
                    affected_entities=[pointer_prefix or "/"],
                    supporting_evidence={"pointer": pointer_prefix},
                    recommended_verification="Verify downstream consumers support newly added schema.",
                    json_pointer=pointer_prefix,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )
            return findings
        if base_schema and not head_schema:
            # Entire schema removed
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="SCHEMA_REMOVED",
                    severity=FindingSeverity.BLOCKING if is_response else FindingSeverity.WARNING,
                    confidence=1.0,
                    before_state=base_schema,
                    after_state={},
                    affected_entities=[pointer_prefix or "/"],
                    supporting_evidence={"pointer": pointer_prefix},
                    recommended_verification="Verify downstream consumers are updated before removing schema payload.",
                    json_pointer=pointer_prefix,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )
            return findings

        assert base_schema is not None and head_schema is not None

        # 1. Primitive Type & Format Changes
        findings.extend(cls._check_type_and_format(base_schema, head_schema, pointer_prefix, file_path, line_range))

        # 2. Enum Changes (Narrowing & Closed-World Expansion)
        findings.extend(
            cls._check_enums(
                base_schema, head_schema, pointer_prefix, active_consumers, is_response, file_path, line_range
            )
        )

        # 3. Nullability Changes
        findings.extend(
            cls._check_nullability(base_schema, head_schema, pointer_prefix, is_response, file_path, line_range)
        )

        # 4. Validation Constraints (Min/Max, Length, Pattern, Items)
        findings.extend(cls._check_constraints(base_schema, head_schema, pointer_prefix, file_path, line_range))

        # 5. Default Value Shifts
        findings.extend(cls._check_default_shifts(base_schema, head_schema, pointer_prefix, file_path, line_range))

        # 6. Object Property Changes (Additions, Removals, Required Status)
        findings.extend(
            cls._check_object_properties(
                base_schema, head_schema, pointer_prefix, active_consumers, is_response, file_path, line_range
            )
        )

        # 7. Array Item Schema Diff
        if base_schema.get("type") == "array" or head_schema.get("type") == "array":
            base_items = base_schema.get("items")
            head_items = head_schema.get("items")
            if isinstance(base_items, dict) and isinstance(head_items, dict):
                findings.extend(
                    cls.diff_schemas(
                        base_items,
                        head_items,
                        pointer_prefix=f"{pointer_prefix}/items",
                        consumers=active_consumers,
                        is_response=is_response,
                        file_path=file_path,
                        line_range=line_range,
                    )
                )

        return findings

    @classmethod
    def _check_type_and_format(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        # Extract types (handling union types e.g. ["string", "null"])
        base_type = base_schema.get("type")
        head_type = head_schema.get("type")

        base_types = set(base_type if isinstance(base_type, list) else ([base_type] if base_type else []))
        head_types = set(head_type if isinstance(head_type, list) else ([head_type] if head_type else []))

        # Filter out 'null' for type checking (handled in nullability)
        base_core_types = {t for t in base_types if t != "null"}
        head_core_types = {t for t in head_types if t != "null"}

        if base_core_types and head_core_types and base_core_types != head_core_types:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="TYPE_CHANGED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"type": list(base_core_types)},
                    after_state={"type": list(head_core_types)},
                    affected_entities=[pointer],
                    supporting_evidence={
                        "old_type": list(base_core_types),
                        "new_type": list(head_core_types),
                        "json_pointer": pointer,
                    },
                    uncertainty_explanation=None,
                    recommended_verification=f"Data type altered from {sorted(base_core_types)} to {sorted(head_core_types)}. Update all consumer deserializers.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # Check format changes (e.g. int32 -> int64 or date-time -> date)
        base_fmt = base_schema.get("format")
        head_fmt = head_schema.get("format")
        if base_fmt and head_fmt and base_fmt != head_fmt:
            # Date-time to date or UUID to string format changes
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="FORMAT_CHANGED",
                    severity=FindingSeverity.BLOCKING
                    if base_fmt == "date-time" and head_fmt == "date"
                    else FindingSeverity.WARNING,
                    confidence=1.0,
                    before_state={"format": base_fmt},
                    after_state={"format": head_fmt},
                    affected_entities=[pointer],
                    supporting_evidence={"old_format": base_fmt, "new_format": head_fmt},
                    recommended_verification=f"Format changed from '{base_fmt}' to '{head_fmt}'. Verify parser precision and timestamp parsing.",
                    json_pointer=f"{pointer}/format",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        return findings

    @classmethod
    def _check_enums(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer: str,
        consumers: list[ConsumerContractProfile],
        is_response: bool,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        base_enum = set(base_schema.get("enum", []))
        head_enum = set(head_schema.get("enum", []))

        if not base_enum and not head_enum:
            return []

        # 1. Enum Narrowing (values dropped)
        if base_enum and head_enum:
            removed_values = base_enum - head_enum
            if removed_values:
                impacted = [c.service_name for c in consumers]
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="ENUM_NARROWED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=1.0,
                        before_state={"enum": sorted(base_enum)},
                        after_state={"enum": sorted(head_enum)},
                        affected_entities=[pointer] + impacted,
                        supporting_evidence={
                            "removed_values": sorted(removed_values),
                            "base_enum": sorted(base_enum),
                            "head_enum": sorted(head_enum),
                            "impacted_consumers": impacted,
                        },
                        uncertainty_explanation=None,
                        recommended_verification=f"Enum narrowed. Removed values: {sorted(removed_values)}. Downstream consumers might fail deserialization.",
                        json_pointer=f"{pointer}/enum",
                        file_path=file_path,
                        start_line=line_range[0],
                        end_line=line_range[1],
                    )
                )

            # 2. Enum Expansion in Response with Closed-World Consumers
            added_values = head_enum - base_enum
            if added_values and is_response:
                for consumer in consumers:
                    # If consumer only handles known enums or is closed world
                    consumed_for_field = consumer.consumed_enum_values.get(pointer, set())
                    if consumer.validation_mode == "CLOSED_WORLD" or (
                        consumed_for_field and not added_values.issubset(consumed_for_field)
                    ):
                        findings.append(
                            ContractFinding(
                                change_category=ChangeCategory.STRUCTURAL,
                                change_type="ENUM_EXPANDED_CONFLICT",
                                severity=FindingSeverity.BLOCKING,
                                confidence=0.95,
                                before_state={"enum": sorted(base_enum)},
                                after_state={"enum": sorted(head_enum)},
                                affected_entities=[pointer, consumer.service_name],
                                supporting_evidence={
                                    "added_values": sorted(added_values),
                                    "consumer": consumer.service_name,
                                    "validation_mode": consumer.validation_mode,
                                },
                                uncertainty_explanation="Consumer validates received enum values strictly against legacy enum set.",
                                recommended_verification=f"Producer added enum values {sorted(added_values)} to response, but consumer '{consumer.service_name}' enforces strict enum parsing.",
                                json_pointer=f"{pointer}/enum",
                                file_path=file_path,
                                start_line=line_range[0],
                                end_line=line_range[1],
                            )
                        )

        return findings

    @classmethod
    def _check_nullability(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer: str,
        is_response: bool,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        base_nullable = base_schema.get("nullable", False) or "null" in (
            base_schema.get("type", []) if isinstance(base_schema.get("type"), list) else []
        )
        head_nullable = head_schema.get("nullable", False) or "null" in (
            head_schema.get("type", []) if isinstance(head_schema.get("type"), list) else []
        )

        # Nullable -> Non-nullable
        if base_nullable and not head_nullable:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="NULLABILITY_REVOKED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"nullable": True},
                    after_state={"nullable": False},
                    affected_entities=[pointer],
                    supporting_evidence={"pointer": pointer},
                    recommended_verification="Field was made non-nullable. Verify clients no longer transmit null values.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # Non-nullable -> Nullable in Response
        if not base_nullable and head_nullable and is_response:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="RESPONSE_BECAME_NULLABLE",
                    severity=FindingSeverity.WARNING,
                    confidence=0.95,
                    before_state={"nullable": False},
                    after_state={"nullable": True},
                    affected_entities=[pointer],
                    supporting_evidence={"pointer": pointer},
                    recommended_verification="Response field can now be null. Ensure downstream consumers handle null gracefully without NullPointer/AttributeError.",
                    json_pointer=pointer,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        return findings

    @classmethod
    def _check_constraints(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        # 1. Minimum bound tightened (increased)
        base_min = base_schema.get("minimum")
        head_min = head_schema.get("minimum")
        if head_min is not None and (base_min is None or head_min > base_min):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="MINIMUM_TIGHTENED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"minimum": base_min},
                    after_state={"minimum": head_min},
                    affected_entities=[pointer],
                    supporting_evidence={"old_minimum": base_min, "new_minimum": head_min},
                    recommended_verification=f"Numeric minimum tightened from {base_min} to {head_min}.",
                    json_pointer=f"{pointer}/minimum",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 2. Maximum bound tightened (decreased)
        base_max = base_schema.get("maximum")
        head_max = head_schema.get("maximum")
        if head_max is not None and (base_max is None or head_max < base_max):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="MAXIMUM_TIGHTENED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"maximum": base_max},
                    after_state={"maximum": head_max},
                    affected_entities=[pointer],
                    supporting_evidence={"old_maximum": base_max, "new_maximum": head_max},
                    recommended_verification=f"Numeric maximum tightened from {base_max} to {head_max}.",
                    json_pointer=f"{pointer}/maximum",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 3. String minLength tightened (increased)
        base_min_len = base_schema.get("minLength")
        head_min_len = head_schema.get("minLength")
        if head_min_len is not None and (base_min_len is None or head_min_len > base_min_len):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="MIN_LENGTH_TIGHTENED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"minLength": base_min_len},
                    after_state={"minLength": head_min_len},
                    affected_entities=[pointer],
                    supporting_evidence={"old_minLength": base_min_len, "new_minLength": head_min_len},
                    recommended_verification=f"String minLength increased from {base_min_len} to {head_min_len}.",
                    json_pointer=f"{pointer}/minLength",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 4. String maxLength tightened (decreased)
        base_max_len = base_schema.get("maxLength")
        head_max_len = head_schema.get("maxLength")
        if head_max_len is not None and (base_max_len is None or head_max_len < base_max_len):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="MAX_LENGTH_TIGHTENED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"maxLength": base_max_len},
                    after_state={"maxLength": head_max_len},
                    affected_entities=[pointer],
                    supporting_evidence={"old_maxLength": base_max_len, "new_maxLength": head_max_len},
                    recommended_verification=f"String maxLength decreased from {base_max_len} to {head_max_len}.",
                    json_pointer=f"{pointer}/maxLength",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 5. Array minItems tightened (increased)
        base_min_items = base_schema.get("minItems")
        head_min_items = head_schema.get("minItems")
        if head_min_items is not None and (base_min_items is None or head_min_items > base_min_items):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="MIN_ITEMS_TIGHTENED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"minItems": base_min_items},
                    after_state={"minItems": head_min_items},
                    affected_entities=[pointer],
                    supporting_evidence={"old_minItems": base_min_items, "new_minItems": head_min_items},
                    recommended_verification=f"Array minItems increased from {base_min_items} to {head_min_items}.",
                    json_pointer=f"{pointer}/minItems",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 6. Array maxItems tightened (decreased)
        base_max_items = base_schema.get("maxItems")
        head_max_items = head_schema.get("maxItems")
        if head_max_items is not None and (base_max_items is None or head_max_items < base_max_items):
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="MAX_ITEMS_TIGHTENED",
                    severity=FindingSeverity.BLOCKING,
                    confidence=1.0,
                    before_state={"maxItems": base_max_items},
                    after_state={"maxItems": head_max_items},
                    affected_entities=[pointer],
                    supporting_evidence={"old_maxItems": base_max_items, "new_maxItems": head_max_items},
                    recommended_verification=f"Array maxItems decreased from {base_max_items} to {head_max_items}.",
                    json_pointer=f"{pointer}/maxItems",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 7. Regex pattern modification
        base_pat = base_schema.get("pattern")
        head_pat = head_schema.get("pattern")
        if base_pat and head_pat and base_pat != head_pat:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="PATTERN_MODIFIED",
                    severity=FindingSeverity.WARNING,
                    confidence=0.95,
                    before_state={"pattern": base_pat},
                    after_state={"pattern": head_pat},
                    affected_entities=[pointer],
                    supporting_evidence={"old_pattern": base_pat, "new_pattern": head_pat},
                    recommended_verification=f"Regex validation pattern modified from '{base_pat}' to '{head_pat}'.",
                    json_pointer=f"{pointer}/pattern",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        return findings

    @classmethod
    def _check_default_shifts(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        base_def = base_schema.get("default")
        head_def = head_schema.get("default")
        if base_def is not None and head_def is not None and base_def != head_def:
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="DEFAULT_VALUE_SHIFT",
                    severity=FindingSeverity.WARNING,
                    confidence=0.90,
                    before_state={"default": base_def},
                    after_state={"default": head_def},
                    affected_entities=[pointer],
                    supporting_evidence={"old_default": base_def, "new_default": head_def},
                    recommended_verification=f"Default value shifted from '{base_def}' to '{head_def}'. Verify consumers relying on default values.",
                    json_pointer=f"{pointer}/default",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        return findings

    @classmethod
    def _check_object_properties(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer: str,
        consumers: list[ConsumerContractProfile],
        is_response: bool,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[ContractFinding]:
        findings: list[ContractFinding] = []

        base_props = base_schema.get("properties", {}) if isinstance(base_schema.get("properties"), dict) else {}
        head_props = head_schema.get("properties", {}) if isinstance(head_schema.get("properties"), dict) else {}

        base_keys = set(base_props.keys())
        head_keys = set(head_props.keys())

        base_required = set(base_schema.get("required", []) if isinstance(base_schema.get("required"), list) else [])
        head_required = set(head_schema.get("required", []) if isinstance(head_schema.get("required"), list) else [])

        # 1. Removed Properties
        removed_keys = base_keys - head_keys
        for r_key in sorted(removed_keys):
            sub_ptr = f"{pointer}/properties/{r_key}"
            findings.append(
                ContractFinding(
                    change_category=ChangeCategory.STRUCTURAL,
                    change_type="FIELD_REMOVED",
                    severity=FindingSeverity.BLOCKING if is_response else FindingSeverity.WARNING,
                    confidence=1.0,
                    before_state={"property": r_key, "schema": base_props[r_key]},
                    after_state={},
                    affected_entities=[sub_ptr],
                    supporting_evidence={"removed_field": r_key, "is_response": is_response},
                    recommended_verification=f"Field '{r_key}' removed from schema. Update any consumers reading this field.",
                    json_pointer=sub_ptr,
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                )
            )

        # 2. Added Properties
        added_keys = head_keys - base_keys
        for a_key in sorted(added_keys):
            sub_ptr = f"{pointer}/properties/{a_key}"
            # Check if newly added property is required
            if a_key in head_required and not is_response:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="REQUIRED_FIELD_ADDED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=1.0,
                        before_state={},
                        after_state={"property": a_key, "schema": head_props[a_key], "required": True},
                        affected_entities=[sub_ptr],
                        supporting_evidence={"added_required_field": a_key},
                        recommended_verification=f"New required field '{a_key}' added to request schema. Existing clients will fail validation.",
                        json_pointer=sub_ptr,
                        file_path=file_path,
                        start_line=line_range[0],
                        end_line=line_range[1],
                    )
                )
            elif is_response:
                # Check closed-world consumers
                for consumer in consumers:
                    if not consumer.additional_properties_allowed or consumer.validation_mode == "CLOSED_WORLD":
                        if a_key not in consumer.known_properties:
                            findings.append(
                                ContractFinding(
                                    change_category=ChangeCategory.STRUCTURAL,
                                    change_type="CLOSED_WORLD_COLLISION",
                                    severity=FindingSeverity.BLOCKING,
                                    confidence=1.0,
                                    before_state={},
                                    after_state={"property": a_key, "schema": head_props[a_key]},
                                    affected_entities=[sub_ptr, consumer.service_name],
                                    supporting_evidence={
                                        "conflicting_property": a_key,
                                        "consumer": consumer.service_name,
                                    },
                                    recommended_verification=f"Producer added property '{a_key}', but consumer '{consumer.service_name}' enforces 'additionalProperties: false'.",
                                    json_pointer=sub_ptr,
                                    file_path=file_path,
                                    start_line=line_range[0],
                                    end_line=line_range[1],
                                )
                            )
            else:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="OPTIONAL_FIELD_ADDED",
                        severity=FindingSeverity.INFO,
                        confidence=1.0,
                        before_state={},
                        after_state={"property": a_key, "schema": head_props[a_key]},
                        affected_entities=[sub_ptr],
                        supporting_evidence={"added_field": a_key},
                        recommended_verification=f"Optional field '{a_key}' added to schema.",
                        json_pointer=sub_ptr,
                        file_path=file_path,
                        start_line=line_range[0],
                        end_line=line_range[1],
                    )
                )

        # 3. Existing Properties Required Status Changes
        common_keys = base_keys & head_keys
        for c_key in sorted(common_keys):
            sub_ptr = f"{pointer}/properties/{c_key}"
            was_req = c_key in base_required
            is_req = c_key in head_required

            if not was_req and is_req:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="FIELD_BECAME_REQUIRED",
                        severity=FindingSeverity.BLOCKING if not is_response else FindingSeverity.INFO,
                        confidence=1.0,
                        before_state={"required": False},
                        after_state={"required": True},
                        affected_entities=[sub_ptr],
                        supporting_evidence={"field": c_key, "is_response": is_response},
                        recommended_verification=f"Field '{c_key}' changed from optional to required. Clients omitting it will fail validation.",
                        json_pointer=sub_ptr,
                        file_path=file_path,
                        start_line=line_range[0],
                        end_line=line_range[1],
                    )
                )
            elif was_req and not is_req:
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.STRUCTURAL,
                        change_type="FIELD_BECAME_OPTIONAL",
                        severity=FindingSeverity.WARNING if is_response else FindingSeverity.INFO,
                        confidence=0.95,
                        before_state={"required": True},
                        after_state={"required": False},
                        affected_entities=[sub_ptr],
                        supporting_evidence={"field": c_key, "is_response": is_response},
                        recommended_verification=f"Field '{c_key}' changed from required to optional.",
                        json_pointer=sub_ptr,
                        file_path=file_path,
                        start_line=line_range[0],
                        end_line=line_range[1],
                    )
                )

            # Recurse into child schemas
            b_val = base_props[c_key]
            h_val = head_props[c_key]
            if isinstance(b_val, dict) and isinstance(h_val, dict):
                findings.extend(
                    cls.diff_schemas(
                        b_val,
                        h_val,
                        pointer_prefix=sub_ptr,
                        consumers=consumers,
                        is_response=is_response,
                        file_path=file_path,
                        line_range=line_range,
                    )
                )

        return findings
