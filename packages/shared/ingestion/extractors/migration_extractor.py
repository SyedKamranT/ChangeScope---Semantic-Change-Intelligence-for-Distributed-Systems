"""Database Migration File Extractor for Alembic, Flyway, Prisma, and Raw SQL Migrations."""

import ast
import re
from pathlib import Path
from typing import Any

from packages.contracts.ddl_parser import DDLParser
from packages.shared.ingestion.models import DatabaseMigration
from packages.shared.logger import logger


class MigrationExtractor:
    """Discovers and parses database schema migrations across SQL and Python frameworks."""

    @classmethod
    def is_migration_file(cls, relative_path: str) -> bool:
        """Determines if a given file path corresponds to a database schema migration."""
        p = relative_path.replace("\\", "/").lower()
        if "/alembic/versions/" in p or "/migrations/versions/" in p or p.startswith("alembic/versions/"):
            return p.endswith(".py")
        if "/prisma/migrations/" in p or p.startswith("prisma/migrations/"):
            return p.endswith(".sql")
        if "/migrations/" in p or "/migrate/" in p or p.startswith("migrations/"):
            return p.endswith(".sql") or p.endswith(".py")
        if re.search(r"v\d+__.*\.sql$", p) or re.search(r"\d{14}_.*\.sql$", p):
            return True
        return False

    @classmethod
    def extract_migration(cls, content: str, file_path: str) -> DatabaseMigration | None:
        """Parses migration contents into structured schema evolution events."""
        p = file_path.replace("\\", "/").lower()

        # 1. Python Alembic Migration
        if p.endswith(".py") and (
            cls.is_migration_file(file_path)
            or "alembic" in p
            or "alembic" in content
            or "revision" in content
            or "op." in content
        ):
            return cls._extract_alembic_migration(content, file_path)

        # 2. SQL Migration (Flyway, Prisma, Raw SQL)
        if p.endswith(".sql"):
            migration_type = "prisma" if "prisma" in p else "raw_sql"
            return cls._extract_sql_migration(content, file_path, migration_type)

        return None

    @classmethod
    def _extract_alembic_migration(cls, code_str: str, file_path: str) -> DatabaseMigration:
        """Inspects upgrade() function in Alembic script for op.create_table, op.add_column, etc."""
        tables_created: list[str] = []
        tables_altered: list[str] = []
        columns_added: list[dict[str, Any]] = []

        try:
            tree = ast.parse(code_str, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call):
                            call_name = cls._get_call_name(sub.func) or ""
                            if call_name in {"op.create_table"}:
                                if (
                                    sub.args
                                    and isinstance(sub.args[0], ast.Constant)
                                    and isinstance(sub.args[0].value, str)
                                ):
                                    tables_created.append(sub.args[0].value)
                            elif call_name in {"op.add_column", "op.alter_column"}:
                                if (
                                    sub.args
                                    and isinstance(sub.args[0], ast.Constant)
                                    and isinstance(sub.args[0].value, str)
                                ):
                                    tbl = sub.args[0].value
                                    tables_altered.append(tbl)
                                    if len(sub.args) > 1:
                                        # sa.Column('col_name', ...)
                                        col_node = sub.args[1]
                                        if isinstance(col_node, ast.Call):
                                            cname = "unknown_col"
                                            if col_node.args and isinstance(col_node.args[0], ast.Constant):
                                                cname = str(col_node.args[0].value)
                                            columns_added.append({"table": tbl, "column": cname})
        except SyntaxError as exc:
            logger.warning("alembic_migration_ast_parse_failed", file_path=file_path, error=str(exc))

        ver_name = Path(file_path).stem
        return DatabaseMigration(
            migration_type="alembic",
            version_or_name=ver_name,
            file_path=file_path,
            tables_created=list(set(tables_created)),
            tables_altered=list(set(tables_altered)),
            columns_added=columns_added,
        )

    @classmethod
    def _extract_sql_migration(cls, sql_text: str, file_path: str, migration_type: str) -> DatabaseMigration:
        """Parses DDL SQL migration statements using DDLParser."""
        tables_created: list[str] = []
        tables_altered: list[str] = []
        columns_added: list[dict[str, Any]] = []

        try:
            ddl_events = DDLParser.parse_sql(sql_text)
            for ev in ddl_events:
                if ev.operation == "CREATE_TABLE":
                    tables_created.append(ev.table_name)
                elif ev.operation in {"ADD_COLUMN", "ALTER_COLUMN_TYPE"}:
                    tables_altered.append(ev.table_name)
                    if ev.column_name:
                        columns_added.append({"table": ev.table_name, "column": ev.column_name, "type": ev.data_type})
        except Exception:
            # Fallback regex if sqlglot dialect differs
            create_matches = re.findall(
                r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"']?\w+[`\"']?)", sql_text, re.IGNORECASE
            )
            tables_created = [m.strip("`\"'") for m in create_matches]

        ver_name = Path(file_path).stem
        return DatabaseMigration(
            migration_type=migration_type,
            version_or_name=ver_name,
            file_path=file_path,
            tables_created=list(set(tables_created)),
            tables_altered=list(set(tables_altered)),
            columns_added=columns_added,
        )

    @classmethod
    def _get_call_name(cls, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = cls._get_call_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return None
