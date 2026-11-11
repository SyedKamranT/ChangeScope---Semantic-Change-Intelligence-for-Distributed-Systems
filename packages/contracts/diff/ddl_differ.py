"""Database Schema & DDL Migration Differ for Change Intelligence."""

from packages.contracts.ddl_parser import DDLEvent
from packages.contracts.models import (
    ChangeCategory,
    ContractFinding,
    ExtractedORMModel,
    FindingSeverity,
)


class DDLDiffer:
    """Evaluates database schema alterations and migration events against active ORM models."""

    @classmethod
    def diff_ddl_events(
        cls,
        ddl_events: list[DDLEvent],
        active_orm_models: list[ExtractedORMModel] | None = None,
        consumer_service_name: str = "service",
    ) -> list[ContractFinding]:
        """Analyzes SQL DDL migration events and flags breaking schema changes."""
        findings: list[ContractFinding] = []
        models = active_orm_models or []
        table_to_models: dict[str, list[ExtractedORMModel]] = {}
        for m in models:
            table_to_models.setdefault(m.table_name, []).append(m)

        for ev in ddl_events:
            table = ev.table_name
            matching_models = table_to_models.get(table, [])
            affected_services = [consumer_service_name]

            # 1. Column Dropped
            if ev.operation == "DROP_COLUMN":
                is_actively_mapped = (
                    any(any(c.get("name") == ev.column_name for c in m.columns) for m in matching_models)
                    if matching_models
                    else True
                )

                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.DATABASE,
                        change_type="COLUMN_DROPPED",
                        severity=FindingSeverity.BLOCKING if matching_models else FindingSeverity.WARNING,
                        confidence=1.0 if matching_models else 0.85,
                        before_state={"table": table, "column": ev.column_name},
                        after_state={},
                        affected_entities=[f"{table}.{ev.column_name}"] + affected_services,
                        supporting_evidence={
                            "table": table,
                            "column": ev.column_name,
                            "is_actively_mapped": is_actively_mapped,
                            "matching_orm_models": [m.model_name for m in matching_models],
                        },
                        recommended_verification=f"Database column '{ev.column_name}' was dropped from table '{table}'. Remove ORM queries referencing this column.",
                        file_path=matching_models[0].file_path if matching_models else "migration.sql",
                        start_line=matching_models[0].start_line if matching_models else 1,
                        end_line=matching_models[0].end_line if matching_models else 1,
                    )
                )

            # 2. Column Renamed
            elif ev.operation in {"RENAME_COLUMN", "ALTER_COLUMN_RENAME"}:
                old_name = ev.metadata.get("old_column_name") or ev.column_name
                new_name = ev.metadata.get("new_column_name") or ev.metadata.get("target_name")
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.DATABASE,
                        change_type="COLUMN_RENAMED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=1.0,
                        before_state={"table": table, "column": old_name},
                        after_state={"table": table, "column": new_name},
                        affected_entities=[f"{table}.{old_name}"] + affected_services,
                        supporting_evidence={
                            "table": table,
                            "old_column": old_name,
                            "new_column": new_name,
                            "matching_orm_models": [m.model_name for m in matching_models],
                        },
                        recommended_verification=f"Column '{old_name}' renamed to '{new_name}' in table '{table}'. Update ORM entity definitions.",
                        file_path=matching_models[0].file_path if matching_models else "migration.sql",
                        start_line=matching_models[0].start_line if matching_models else 1,
                        end_line=matching_models[0].end_line if matching_models else 1,
                    )
                )

            # 3. Column Type Changed / Shrunk
            elif ev.operation == "ALTER_COLUMN_TYPE":
                is_shrunk = False
                if ev.old_length and ev.length and ev.length < ev.old_length:
                    is_shrunk = True

                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.DATABASE,
                        change_type="COLUMN_TYPE_CHANGED",
                        severity=FindingSeverity.BLOCKING,
                        confidence=1.0,
                        before_state={
                            "table": table,
                            "column": ev.column_name,
                            "old_type": ev.old_data_type or ev.data_type,
                        },
                        after_state={
                            "table": table,
                            "column": ev.column_name,
                            "new_type": ev.data_type,
                            "length": ev.length,
                        },
                        affected_entities=[f"{table}.{ev.column_name}"] + affected_services,
                        supporting_evidence={
                            "table": table,
                            "column": ev.column_name,
                            "new_type": ev.data_type,
                            "is_shrunk": is_shrunk,
                            "matching_orm_models": [m.model_name for m in matching_models],
                        },
                        recommended_verification=f"Column '{ev.column_name}' type altered to '{ev.data_type}' in table '{table}'. Verify potential data truncation.",
                        file_path=matching_models[0].file_path if matching_models else "migration.sql",
                        start_line=matching_models[0].start_line if matching_models else 1,
                        end_line=matching_models[0].end_line if matching_models else 1,
                    )
                )

            # 4. Column Nullability Tightened (SET NOT NULL without default)
            elif ev.operation in {"ALTER_COLUMN_NULLABLE", "ADD_COLUMN"} and not ev.is_nullable:
                has_default = "default" in ev.metadata or "DEFAULT" in str(ev.metadata)
                if not has_default:
                    findings.append(
                        ContractFinding(
                            change_category=ChangeCategory.DATABASE,
                            change_type="COLUMN_NOT_NULL_WITHOUT_DEFAULT",
                            severity=FindingSeverity.BLOCKING,
                            confidence=0.95,
                            before_state={"table": table, "column": ev.column_name, "nullable": True},
                            after_state={
                                "table": table,
                                "column": ev.column_name,
                                "nullable": False,
                                "has_default": False,
                            },
                            affected_entities=[f"{table}.{ev.column_name}"] + affected_services,
                            supporting_evidence={
                                "table": table,
                                "column": ev.column_name,
                                "operation": ev.operation,
                            },
                            uncertainty_explanation="Adding a NOT NULL constraint without a default value will fail on existing rows with nulls, and breaks inserts omitting this column.",
                            recommended_verification=f"Column '{ev.column_name}' in table '{table}' set to NOT NULL without a default value. Provide a default value or backfill migration.",
                            file_path=matching_models[0].file_path if matching_models else "migration.sql",
                            start_line=matching_models[0].start_line if matching_models else 1,
                            end_line=matching_models[0].end_line if matching_models else 1,
                        )
                    )

            # 5. Default Value Shift in Database Column
            elif ev.operation == "ALTER_COLUMN_DEFAULT":
                old_def = ev.metadata.get("old_default")
                new_def = ev.metadata.get("new_default")
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.DATABASE,
                        change_type="COLUMN_DEFAULT_SHIFT",
                        severity=FindingSeverity.WARNING,
                        confidence=0.90,
                        before_state={"table": table, "column": ev.column_name, "default": old_def},
                        after_state={"table": table, "column": ev.column_name, "default": new_def},
                        affected_entities=[f"{table}.{ev.column_name}"],
                        supporting_evidence={
                            "table": table,
                            "column": ev.column_name,
                            "old_default": old_def,
                            "new_default": new_def,
                        },
                        recommended_verification=f"Default value of '{table}.{ev.column_name}' shifted from '{old_def}' to '{new_def}'. Verify insert semantics.",
                        file_path="migration.sql",
                    )
                )

            # 6. Table Dropped
            elif ev.operation == "DROP_TABLE":
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.DATABASE,
                        change_type="TABLE_DROPPED",
                        severity=FindingSeverity.BLOCKING if matching_models else FindingSeverity.WARNING,
                        confidence=1.0,
                        before_state={"table": table},
                        after_state={},
                        affected_entities=[table] + affected_services,
                        supporting_evidence={
                            "table": table,
                            "matching_orm_models": [m.model_name for m in matching_models],
                        },
                        recommended_verification=f"Database table '{table}' dropped. Remove ORM queries referencing this table.",
                        file_path=matching_models[0].file_path if matching_models else "migration.sql",
                        start_line=matching_models[0].start_line if matching_models else 1,
                        end_line=matching_models[0].end_line if matching_models else 1,
                    )
                )

            # 7. Unique Constraint / Foreign Key Added
            elif ev.operation in {"ADD_CONSTRAINT_UNIQUE", "ADD_CONSTRAINT_FK"}:
                c_name = ev.metadata.get("constraint_name", "unnamed_constraint")
                findings.append(
                    ContractFinding(
                        change_category=ChangeCategory.DATABASE,
                        change_type="DATABASE_CONSTRAINT_ADDED",
                        severity=FindingSeverity.WARNING,
                        confidence=0.90,
                        before_state={"table": table},
                        after_state={"table": table, "constraint": c_name, "type": ev.operation},
                        affected_entities=[f"{table}:{c_name}"],
                        supporting_evidence={"table": table, "constraint": c_name, "type": ev.operation},
                        uncertainty_explanation="Constraint addition may fail if legacy rows in table violate the new constraint condition.",
                        recommended_verification=f"New constraint '{c_name}' added to table '{table}'. Verify all existing rows satisfy condition.",
                        file_path="migration.sql",
                    )
                )

        return findings
