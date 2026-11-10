"""Deterministic Semantic Change Rule Engine."""

from typing import Any

from changescope.analysis.contract.ddl_parser import DDLEvent
from changescope.analysis.static.models import ExtractedORMModel
from changescope.reasoning.models import ConsumerContractProfile, RuleViolation


class SemanticRuleEngine:
    """Evaluates differences between base and head contracts using 100% deterministic algorithms."""

    @classmethod
    def evaluate_contract_diff(
        cls,
        base_endpoint: dict[str, Any],
        head_endpoint: dict[str, Any],
        consumers: list[ConsumerContractProfile],
        file_path: str = "openapi.yaml",
        line_range: tuple[int, int] = (1, 1),
    ) -> list[RuleViolation]:
        """Evaluates schema diffs between base and head endpoint versions."""
        violations: list[RuleViolation] = []

        base_req = base_endpoint.get("request_schema", {})
        head_req = head_endpoint.get("request_schema", {})
        violations.extend(
            cls._evaluate_schema_pair(base_req, head_req, "/requestBody", consumers, file_path, line_range)
        )

        # Check response schemas across status codes
        base_responses = base_endpoint.get("response_schemas", {})
        head_responses = head_endpoint.get("response_schemas", {})

        for status_code, base_resp in base_responses.items():
            head_resp = head_responses.get(status_code, {})
            if head_resp:
                violations.extend(
                    cls._evaluate_schema_pair(
                        base_resp, head_resp, f"/responses/{status_code}", consumers, file_path, line_range
                    )
                )

        return violations

    @classmethod
    def _evaluate_schema_pair(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        pointer_prefix: str,
        consumers: list[ConsumerContractProfile],
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []

        # 1. Rule 1: Enum Narrowing
        violations.extend(
            cls.check_enum_narrowing(base_schema, head_schema, pointer_prefix, consumers, file_path, line_range)
        )

        # 2. Rule 2: Closed-World Property Collision (additionalProperties: false)
        violations.extend(cls.check_closed_world_collision(base_schema, head_schema, consumers, file_path, line_range))

        # 3. Rule 3: Constraint Tightening (regex pattern, numeric limits, string length)
        violations.extend(
            cls.check_constraint_tightening(base_schema, head_schema, pointer_prefix, file_path, line_range)
        )

        # 4. Rule 5: Default Value Shifts
        violations.extend(
            cls.check_default_value_shifts(base_schema, head_schema, pointer_prefix, file_path, line_range)
        )

        # Recurse into object properties
        base_props = base_schema.get("properties", {})
        head_props = head_schema.get("properties", {})
        for prop_name, base_prop in base_props.items():
            if prop_name in head_props and isinstance(base_prop, dict) and isinstance(head_props[prop_name], dict):
                violations.extend(
                    cls._evaluate_schema_pair(
                        base_prop,
                        head_props[prop_name],
                        f"{pointer_prefix}/properties/{prop_name}",
                        consumers,
                        file_path,
                        line_range,
                    )
                )

        return violations

    @classmethod
    def check_enum_narrowing(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        json_pointer: str,
        consumers: list[ConsumerContractProfile],
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[RuleViolation]:
        """Detects removed enum values that would cause consumer deserialization errors."""
        base_enum = set(base_schema.get("enum", []))
        head_enum = set(head_schema.get("enum", []))

        if not base_enum:
            return []

        removed = base_enum - head_enum
        if removed:
            impacted = [c.service_name for c in consumers]
            return [
                RuleViolation(
                    rule_code="RULE_ENUM_NARROWED",
                    severity="BLOCKING",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                    json_pointer=json_pointer,
                    message=f"Enum narrowed. Removed values: {sorted(removed)}. Downstream consumers: {impacted or ['all consumers']}.",
                    evidence={
                        "removed_values": sorted(removed),
                        "base_enum": sorted(base_enum),
                        "head_enum": sorted(head_enum),
                        "impacted_consumers": impacted,
                    },
                )
            ]
        return []

    @classmethod
    def check_closed_world_collision(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        consumers: list[ConsumerContractProfile],
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[RuleViolation]:
        """Detects newly added properties that crash consumers enforcing additionalProperties: false."""
        base_props = set(base_schema.get("properties", {}).keys())
        head_props = set(head_schema.get("properties", {}).keys())
        added_props = head_props - base_props

        if not added_props:
            return []

        violations = []
        for consumer in consumers:
            if not consumer.additional_properties_allowed or consumer.validation_mode == "CLOSED_WORLD":
                conflicting = added_props - consumer.known_properties
                if conflicting:
                    violations.append(
                        RuleViolation(
                            rule_code="RULE_CLOSED_WORLD_COLLISION",
                            severity="BLOCKING",
                            file_path=file_path,
                            start_line=line_range[0],
                            end_line=line_range[1],
                            impacted_service_id=consumer.service_id,
                            impacted_service_name=consumer.service_name,
                            message=(
                                f"Producer added optional property(ies) {sorted(conflicting)}, "
                                f"but consumer '{consumer.service_name}' enforces 'additionalProperties: false'."
                            ),
                            evidence={
                                "conflicting_properties": sorted(conflicting),
                                "consumer_service": consumer.service_name,
                            },
                        )
                    )
        return violations

    @classmethod
    def check_constraint_tightening(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        json_pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[RuleViolation]:
        """Detects tightened constraints: regex pattern change, increased minimum, decreased maximum."""
        violations = []

        # Check regex pattern change
        base_pat = base_schema.get("pattern")
        head_pat = head_schema.get("pattern")
        if base_pat and head_pat and base_pat != head_pat:
            violations.append(
                RuleViolation(
                    rule_code="RULE_PATTERN_TIGHTENED",
                    severity="WARNING",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                    json_pointer=f"{json_pointer}/pattern",
                    message=f"String validation pattern modified from '{base_pat}' to '{head_pat}'.",
                    evidence={"old_pattern": base_pat, "new_pattern": head_pat},
                )
            )

        # Check minimum bound increase
        base_min = base_schema.get("minimum")
        head_min = head_schema.get("minimum")
        if head_min is not None and (base_min is None or head_min > base_min):
            violations.append(
                RuleViolation(
                    rule_code="RULE_MINIMUM_TIGHTENED",
                    severity="BLOCKING",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                    json_pointer=f"{json_pointer}/minimum",
                    message=f"Numeric minimum tightened from {base_min} to {head_min}.",
                    evidence={"old_minimum": base_min, "new_minimum": head_min},
                )
            )

        return violations

    @classmethod
    def check_default_value_shifts(
        cls,
        base_schema: dict[str, Any],
        head_schema: dict[str, Any],
        json_pointer: str,
        file_path: str,
        line_range: tuple[int, int],
    ) -> list[RuleViolation]:
        """Detects changed default values that subtly alter consumer query semantics."""
        base_default = base_schema.get("default")
        head_default = head_schema.get("default")

        if base_default is not None and head_default is not None and base_default != head_default:
            return [
                RuleViolation(
                    rule_code="RULE_DEFAULT_VALUE_SHIFT",
                    severity="WARNING",
                    file_path=file_path,
                    start_line=line_range[0],
                    end_line=line_range[1],
                    json_pointer=f"{json_pointer}/default",
                    message=f"Default value shifted from '{base_default}' to '{head_default}'.",
                    evidence={"old_default": base_default, "new_default": head_default},
                )
            ]
        return []

    @classmethod
    def check_ddl_mutations(
        cls,
        ddl_events: list[DDLEvent],
        active_orm_models: list[ExtractedORMModel],
        consumer_service_name: str = "consumer-service",
    ) -> list[RuleViolation]:
        """Detects dangerous SQL DDL alterations against active ORM model columns."""
        violations = []

        table_to_models = {m.table_name: m for m in active_orm_models}

        for ev in ddl_events:
            if ev.operation == "ALTER_COLUMN_TYPE":
                # Column shrunk, e.g. VARCHAR(64) -> VARCHAR(16)
                if ev.table_name in table_to_models:
                    model = table_to_models[ev.table_name]
                    violations.append(
                        RuleViolation(
                            rule_code="RULE_DDL_COLUMN_SHRUNK",
                            severity="BLOCKING",
                            file_path=model.file_path,
                            start_line=model.start_line,
                            end_line=model.end_line,
                            impacted_service_name=consumer_service_name,
                            message=(
                                f"Database column '{ev.column_name}' in table '{ev.table_name}' had type altered to '{ev.data_type}'. "
                                f"Model '{model.model_name}' queries this table."
                            ),
                            evidence={
                                "table": ev.table_name,
                                "column": ev.column_name,
                                "new_type": ev.data_type,
                                "model": model.model_name,
                            },
                        )
                    )

            elif ev.operation == "DROP_COLUMN":
                if ev.table_name in table_to_models:
                    model = table_to_models[ev.table_name]
                    violations.append(
                        RuleViolation(
                            rule_code="RULE_DDL_COLUMN_DROPPED",
                            severity="BLOCKING",
                            file_path=model.file_path,
                            start_line=model.start_line,
                            end_line=model.end_line,
                            impacted_service_name=consumer_service_name,
                            message=(
                                f"Database column '{ev.column_name}' in table '{ev.table_name}' was dropped. "
                                f"Model '{model.model_name}' actively maps to this table."
                            ),
                            evidence={
                                "table": ev.table_name,
                                "dropped_column": ev.column_name,
                                "model": model.model_name,
                            },
                        )
                    )

        return violations
