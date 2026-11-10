"""SQL DDL Migration Parser using sqlglot."""

import re
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from changescope.common.exceptions import ParseError
from sqlglot import exp


@dataclass
class DDLEvent:
    """A structured database schema modification event."""

    operation: str  # 'ALTER_COLUMN_TYPE', 'ADD_COLUMN', 'DROP_COLUMN', 'CREATE_TABLE', 'DROP_TABLE'
    table_name: str
    column_name: str | None = None
    data_type: str | None = None
    old_data_type: str | None = None
    length: int | None = None
    old_length: int | None = None
    is_nullable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class DDLParser:
    """Parses SQL DDL migration scripts across PostgreSQL and MySQL dialects."""

    @classmethod
    def parse_sql(cls, sql_text: str, dialect: str = "postgres") -> list[DDLEvent]:
        """Parses raw SQL DDL script and returns a list of DDLEvents."""
        events: list[DDLEvent] = []

        try:
            statements = sqlglot.parse(sql_text, read=dialect)
        except Exception as e:
            raise ParseError(f"Failed to parse SQL DDL script: {str(e)}") from e

        for stmt in statements:
            if not stmt:
                continue

            if isinstance(stmt, exp.Alter):
                events.extend(cls._parse_alter_table(stmt))
            elif isinstance(stmt, exp.Create):
                events.extend(cls._parse_create_table(stmt))
            elif isinstance(stmt, exp.Drop):
                events.extend(cls._parse_drop_table(stmt))

        return events

    @classmethod
    def _parse_alter_table(cls, stmt: exp.Alter) -> list[DDLEvent]:
        events = []
        table_name = stmt.this.name if stmt.this else "unknown_table"

        for action in stmt.actions:
            if isinstance(action, exp.AlterColumn):
                col_name = action.this.name if action.this else "unknown_col"
                dtype = action.args.get("dtype")
                kind_str = dtype.sql() if dtype else ""

                # Check for length in kind, e.g. VARCHAR(16)
                len_match = re.search(r"\((\d+)\)", kind_str)
                length = int(len_match.group(1)) if len_match else None

                events.append(
                    DDLEvent(
                        operation="ALTER_COLUMN_TYPE",
                        table_name=table_name,
                        column_name=col_name,
                        data_type=kind_str,
                        length=length,
                    )
                )

            elif isinstance(action, exp.ColumnDef):
                col_name = action.this.name if action.this else "unknown_col"
                kind_str = action.kind.sql() if action.kind else ""

                # Check nullability
                is_nullable = True
                for constraint in action.constraints:
                    constraint_sql = constraint.sql().upper()
                    if "NOT NULL" in constraint_sql:
                        is_nullable = False

                len_match = re.search(r"\((\d+)\)", kind_str)
                length = int(len_match.group(1)) if len_match else None

                events.append(
                    DDLEvent(
                        operation="ADD_COLUMN",
                        table_name=table_name,
                        column_name=col_name,
                        data_type=kind_str,
                        length=length,
                        is_nullable=is_nullable,
                    )
                )

            elif isinstance(action, exp.Drop) and action.args.get("kind") == "COLUMN":
                tables = action.args.get("tables", [])
                col_name = tables[0].name if tables else (action.this.name if action.this else "unknown_col")
                events.append(
                    DDLEvent(
                        operation="DROP_COLUMN",
                        table_name=table_name,
                        column_name=col_name,
                    )
                )

        return events

    @classmethod
    def _parse_create_table(cls, stmt: exp.Create) -> list[DDLEvent]:
        events = []
        if stmt.kind == "TABLE" and stmt.this:
            table_name = stmt.this.name
            events.append(
                DDLEvent(
                    operation="CREATE_TABLE",
                    table_name=table_name,
                )
            )
        return events

    @classmethod
    def _parse_drop_table(cls, stmt: exp.Drop) -> list[DDLEvent]:
        events = []
        if stmt.kind == "TABLE" and stmt.this:
            table_name = stmt.this.name
            events.append(
                DDLEvent(
                    operation="DROP_TABLE",
                    table_name=table_name,
                )
            )
        return events
